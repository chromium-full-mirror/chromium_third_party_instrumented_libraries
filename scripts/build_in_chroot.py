#!/usr/bin/env python3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Builds the instrumented libraries inside an unprivileged Ubuntu chroot.

No root, debootstrap, schroot, or container runtime is needed. An Ubuntu base
tarball is extracted into a directory, and its apt sources are pinned to a fixed
snapshot.ubuntu.com timestamp, so package sources and build dependencies are
reproducible. Commands run inside it using one of two isolation mechanisms:

  namespace: `unshare --user --map-root-user` + chroot. Needs unprivileged user
             namespaces. Runs at native speed.
  proot:     ptrace-based fake chroot/root. Needs only ptrace. Slower, since
             a tracer process has to handle every traced syscall.

Only a single uid/gid is mapped in either mode, so dpkg can't chown files to
other users (e.g. setgid helpers in libpam-modules-bin). During package
installation, a tiny LD_PRELOAD shim turns those EINVAL failures into success.
None of the affected files are used by the build.

Stock proot loads executables at 0x500000000000, which is inside MSan's shadow
memory, so the MSan-instrumented programs that configure scripts compile and run
fail to start. The chroot setup therefore builds a proot from pinned source with
relocated load addresses, and that proot runs the build. The stock release
binary is only used to bootstrap the chroot.

A single proot tracer can't keep up with a parallel build, so in proot mode
ninja runs on the host instead, and every GN action (i.e. every package build)
runs under its own proot instance. This is done by generating the build files
with a --script-executable wrapper that enters the chroot. gn gen and packaging
still run inside the chroot.

The Chromium source tree is bind-mounted at the same absolute path inside the
chroot, and build_and_package.py runs there. The resulting tarballs are written
to the root of the source tree.

The chroot and build directories are reused across runs. If only the package
lists change, the packages are installed into the existing chroot instead of
recreating it (use --recreate to start from scratch), and ninja only rebuilds
packages that failed or whose inputs changed. For quicker iteration on
individual packages, see --packages, --keep-going, and --no-clobber.

snapshot.ubuntu.com is slow, so packages are downloaded in parallel ahead of
time (from archive.ubuntu.com when possible), and kept in a cache next to the
chroot. apt verifies them against the snapshot's signed indices as usual.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
INSTRUMENTED_LIBS_DIR = os.path.join(SRC_DIR, "third_party",
                                     "instrumented_libs")

# Bump this to pick up newer package versions.
SNAPSHOT = "20261001T000000Z"
SNAPSHOT_URL = f"https://snapshot.ubuntu.com/ubuntu/{SNAPSHOT}/"
# Packages are fetched from here instead of SNAPSHOT_URL when possible, since
# it's much faster. apt verifies them against the snapshot's indices.
ARCHIVE_URL = "http://archive.ubuntu.com/ubuntu/"

RELEASES = {
    "noble": {
        "base_tarball_url":
        "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/"
        "ubuntu-base-24.04.3-base-amd64.tar.gz",
        "base_tarball_sha256":
        "6bc2cde3930ad088b3bb46fa45279e96d25bc3810f209850ecbe4722711874f9",
        # Package name -> version to pin.
        "apt_pins": {
            # tar >= 1.35+dfsg-3ubuntu0.3 (the CVE-2026-5704 fix) fails to
            # create subdirectories when run under proot, which breaks
            # dpkg-source. Keep the release version. It only extracts
            # apt-verified source packages. Pinned in both modes so the chroot
            # contents don't depend on the mode.
            "tar": "1.35+dfsg-3build1",
        },
    },
    "resolute": {
        "base_tarball_url":
        "https://cdimage.ubuntu.com/ubuntu-base/releases/26.04/release/"
        "ubuntu-base-26.04.1-base-amd64.tar.gz",
        "base_tarball_sha256":
        "a496a960472ce474a59590b8987d3a1135d3cbef1991f3b1abe8cacfea8bf85a",
        "apt_pins": {},
    },
}

PROOT_URL = "https://github.com/proot-me/proot/releases/download/v5.5.0/proot"
PROOT_SHA256 = (
    "db185300a9daabbce86aca7632d8c7fdc4249f6f153171954013b70c5f491ec0")

# Source for the MSan-compatible proot (v5.5.0).
PROOT_GIT_URL = "https://github.com/proot-me/proot.git"
PROOT_GIT_REVISION = "25dc6a3134891f98a79f57ce1c2c1b23ff15cad1"
# MSan's x86_64 layout reserves 0x500000000000-0x510000000000 (shadow) and
# 0x600000000000-0x700000000000 (origin/invalid). Move proot's loader, PIE
# executables, and interpreters into app memory (0x510000000000-0x600000000000).
PROOT_ADDRESSES = {
    "LOADER_ADDRESS": ("0x600000000000", "0x580000000000"),
    "EXEC_PIC_ADDRESS": ("0x500000000000", "0x550000000000"),
    "INTERP_PIC_ADDRESS": ("0x6f0000000000", "0x5c0000000000"),
}
# Location inside the chroot.
MSAN_PROOT_PATH = "/usr/local/bin/proot-msan"
CHROOT_LIB_DIR = "/usr/lib/x86_64-linux-gnu"
CHROOT_LD_SO = f"{CHROOT_LIB_DIR}/ld-linux-x86-64.so.2"

# Installed first, to build the chown shim and proot-msan.
BOOTSTRAP_PACKAGES = [
    "ca-certificates",
    "gcc",
    "git",
    "libc6-dev",
    "libtalloc-dev",
    "make",
    "patchelf",
    "pkg-config",
]

# Tools needed in addition to the build dependencies listed in
# install-build-deps.sh.
EXTRA_PACKAGES = [
    "ca-certificates",
    # For dpkg-source (used by `apt-get source`) and dpkg-buildpackage.
    "dpkg-dev",
    "fakeroot",
    "git",
    "gyp",
    "help2man",
    "libdrm-dev",
    "libgtk2.0-bin",
    "lsb-release",
    "patchelf",
    "pkg-config",
    "python-is-python3",
]

# Set in the environment of everything that runs inside the chroot.
IN_CHROOT_ENV = "INSTRUMENTED_LIBS_IN_CHROOT"

# Increment to force the chroot to be recreated when the setup logic changes.
SETUP_VERSION = 4

CHOWN_SHIM_SOURCE = r"""
// Only a single uid/gid is mapped into the chroot, so chown() to any other id
// fails with EINVAL. Pretend such calls succeed so dpkg can install packages
// that ship files owned by other users.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <sys/types.h>

#define WRAP(name, params, args)                  \
  int name params {                               \
    static int (*real) params;                    \
    if (!real) real = dlsym(RTLD_NEXT, #name);    \
    int saved_errno = errno;                      \
    int r = real args;                            \
    if (r != 0 && errno == EINVAL) {              \
      errno = saved_errno;                        \
      return 0;                                   \
    }                                             \
    return r;                                     \
  }

WRAP(chown, (const char* p, uid_t o, gid_t g), (p, o, g))
WRAP(lchown, (const char* p, uid_t o, gid_t g), (p, o, g))
WRAP(fchown, (int fd, uid_t o, gid_t g), (fd, o, g))
WRAP(fchownat, (int d, const char* p, uid_t o, gid_t g, int f),
     (d, p, o, g, f))
"""

CHOWN_SHIM_PATH = "/usr/local/lib/chown_shim.so"

# Host CA bundle locations, used to bootstrap HTTPS access to the snapshot
# server before the ca-certificates package is installed.
HOST_CA_BUNDLES = [
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
    "/etc/ssl/cert.pem",
]


def log(msg):
    print(f"[build_in_chroot] {msg}", flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, sha256, dest):
    """Downloads `url` to `dest` unless a file with `sha256` already exists."""
    if os.path.exists(dest) and sha256_of(dest) == sha256:
        return dest
    log(f"Downloading {url}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.tmp"
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    actual = sha256_of(tmp)
    if actual != sha256:
        os.unlink(tmp)
        raise Exception("SHA256 mismatch for %s: expected %s, got %s" %
                        (url, sha256, actual))
    os.replace(tmp, dest)
    return dest


def write_file(path, content, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.lexists(path):
        os.unlink(path)
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, mode)


def rmtree(path):
    if not os.path.lexists(path):
        return

    def make_writable_and_retry(func, p, _):
        os.chmod(os.path.dirname(p), 0o755)
        if not os.path.islink(p) and os.path.isdir(p):
            os.chmod(p, 0o755)
        func(p)

    shutil.rmtree(path, onerror=make_writable_and_retry)


class Chroot:

    def __init__(self, root, mode, proot):
        self.root = root
        self.mode = mode
        self.proot = proot

    def _env(self, extra_env=()):
        path = ":".join([
            os.path.join(SRC_DIR, "buildtools", "linux64"),
            os.path.join(SRC_DIR, "third_party", "ninja"),
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ])
        return [
            "HOME=/root",
            "LANG=C.UTF-8",
            "LC_ALL=C.UTF-8",
            "DEBIAN_FRONTEND=noninteractive",
            "TERM=dumb",
            f"PATH={path}",
            f"{IN_CHROOT_ENV}=1",
        ] + list(extra_env)

    def _proot_argv(self, cwd):
        return [
            self.proot,
            "-0",
            "-r",
            self.root,
            "-b",
            "/dev",
            "-b",
            "/proc",
            "-b",
            "/sys",
            "-b",
            f"{SRC_DIR}:{SRC_DIR}",
            "-w",
            cwd,
        ]

    def write_proot_wrapper(self, path, interpreter, extra_env=()):
        """Writes a script that runs `interpreter` in the chroot via proot.

        The script runs in the current directory, which must be inside the
        source tree. If it's already in the chroot, it runs `interpreter`
        directly.
        """
        assert self.mode == "proot"
        cwd = "@PWD@"
        argv = self._proot_argv(cwd) + ["/usr/bin/env", "-i"
                                        ] + self._env(extra_env)
        argv = ['"$PWD"' if a == cwd else shlex.quote(a) for a in argv]
        interpreter = shlex.quote(interpreter)
        write_file(
            path, "\n".join([
                "#!/bin/sh",
                f"# Generated by {os.path.basename(__file__)}.",
                f'if [ -n "${IN_CHROOT_ENV}" ]; then',
                f'  exec {interpreter} "$@"',
                "fi",
                f'exec {" ".join(argv)} {interpreter} "$@"',
                "",
            ]), 0o755)

    def run(self, script, cwd="/", extra_env=()):
        """Runs a bash `script` inside the chroot as (fake) root."""
        inner = ["/usr/bin/env", "-i"] + self._env(extra_env) + [
            "/bin/bash", "-e", "-o", "pipefail", "-c",
            f"cd {shlex.quote(cwd)} && {script}"
        ]
        if self.mode == "proot":
            cmd = self._proot_argv("/") + inner
        else:
            root = shlex.quote(self.root)
            src = shlex.quote(SRC_DIR)
            mounts = " && ".join([
                # This must be recursive: a plain bind of a mount with locked
                # submounts fails in a user namespace. Do it first so the mounts
                # below (which are under SRC_DIR) aren't copied into it.
                f"mount --rbind {src} {root}{src}",
                f"mount --rbind /dev {root}/dev",
                f"mount --rbind /proc {root}/proc",
                f"{{ mount --rbind /sys {root}/sys || true; }}",
                "exec chroot %s %s" %
                (root, " ".join(shlex.quote(a) for a in inner)),
            ])
            cmd = [
                "unshare", "--user", "--map-root-user", "--mount", "--",
                "/bin/sh", "-e", "-c", mounts
            ]
        subprocess.check_call(cmd)


def gn_script_executable():
    """Returns the absolute path of the interpreter configured in //.gn."""
    with open(os.path.join(SRC_DIR, ".gn")) as f:
        m = re.search(r'^script_executable\s*=\s*"([^"]*)"', f.read(), re.M)
    if not m:
        return "python3"
    path = m.group(1)
    if path.startswith("//"):
        path = os.path.join(SRC_DIR, path[2:])
    return path


def install_build_deps_script(release):
    return os.path.join(INSTRUMENTED_LIBS_DIR, release, "scripts",
                        "install-build-deps.sh")


def setup_fingerprint(release):
    """Returns the configuration the chroot is set up from.

    A change to "base" requires recreating the chroot. A change to only
    "packages" is handled by installing packages into the existing one.
    """
    with open(install_build_deps_script(release), "rb") as f:
        build_deps = hashlib.sha256(f.read()).hexdigest()
    return {
        "base": {
            "setup_version": SETUP_VERSION,
            "bootstrap_packages": BOOTSTRAP_PACKAGES,
            "release": release,
            "release_config": RELEASES[release],
            "snapshot": SNAPSHOT,
        },
        "packages": {
            "extra_packages": EXTRA_PACKAGES,
            "install_build_deps": build_deps,
        },
    }


def read_stamp(path):
    try:
        with open(path) as f:
            stamp = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(stamp, dict) or "base" not in stamp:
        return None
    return stamp


def write_stamp(path, stamp):
    with open(path, "w") as f:
        json.dump(stamp, f, sort_keys=True, indent=2)


def configure_root(root, release, cache_dir):
    """Writes apt/dpkg configuration and other files into a fresh root."""
    sources = "\n".join([
        "Types: deb deb-src",
        f"URIs: {SNAPSHOT_URL}",
        f"Suites: {release} {release}-updates {release}-security",
        "Components: main restricted universe",
        "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg",
        "",
    ])
    write_file(os.path.join(root, "etc/apt/sources.list.d/ubuntu.sources"),
               sources)
    write_file(os.path.join(root, "etc/apt/sources.list"), "")

    apt_conf = [
        # The _apt user can't be switched to with a single mapped uid.
        'APT::Sandbox::User "root";',
        'APT::Install-Recommends "false";',
        'APT::Install-Suggests "false";',
        'APT::Get::Assume-Yes "true";',
        # Snapshots are immutable, so old Release files must be accepted.
        'Acquire::Check-Valid-Until "false";',
        'Acquire::Retries "10";',
    ]
    # Keep downloaded packages outside the root, so recreating it doesn't
    # download them again. This only works if the cache is in the source tree,
    # which is mounted at the same path. Packages are immutable for a snapshot.
    archives = archives_dir(cache_dir)
    if archives:
        os.makedirs(os.path.join(archives, "partial"), exist_ok=True)
        apt_conf += [
            'APT::Keep-Downloaded-Packages "true";',
            f'Dir::Cache::Archives "{archives}/";',
        ]
        # Docker images delete downloaded packages after each installation.
        docker_clean = os.path.join(root, "etc/apt/apt.conf.d/docker-clean")
        if os.path.lexists(docker_clean):
            os.unlink(docker_clean)
    for bundle in HOST_CA_BUNDLES:
        if os.path.exists(bundle):
            shutil.copy(bundle, os.path.join(root, "etc/host-ca.crt"))
            apt_conf.append('Acquire::https::CAInfo "/etc/host-ca.crt";')
            break
    write_file(os.path.join(root, "etc/apt/apt.conf.d/99chroot"),
               "\n".join(apt_conf) + "\n")

    for package, version in sorted(RELEASES[release]["apt_pins"].items()):
        write_file(
            os.path.join(root, "etc/apt/preferences.d", package), "\n".join([
                f"Package: {package}",
                f"Pin: version {version}",
                "Pin-Priority: 1001",
                "",
            ]))

    # Save space by not installing documentation.
    write_file(
        os.path.join(root, "etc/dpkg/dpkg.cfg.d/99nodoc"), "\n".join([
            "path-exclude=/usr/share/doc/*",
            "path-include=/usr/share/doc/*/copyright",
            "path-exclude=/usr/share/man/*",
            "path-exclude=/usr/share/info/*",
            "path-exclude=/usr/share/locale/*",
            "",
        ]))

    # Don't try to start daemons from maintainer scripts.
    write_file(os.path.join(root, "usr/sbin/policy-rc.d"),
               "#!/bin/sh\nexit 101\n", 0o755)

    # install-build-deps.sh uses sudo. Everything already runs as (fake) root.
    write_file(os.path.join(root, "usr/local/bin/sudo"),
               '#!/bin/sh\nexec "$@"\n', 0o755)

    shutil.copy("/etc/resolv.conf", os.path.join(root, "etc/resolv.conf.tmp"))
    os.replace(os.path.join(root, "etc/resolv.conf.tmp"),
               os.path.join(root, "etc/resolv.conf"))

    write_file(os.path.join(root, "usr/local/src/chown_shim.c"),
               CHOWN_SHIM_SOURCE)

    # Mount point for the source tree.
    os.makedirs(root + SRC_DIR, exist_ok=True)


def create_root(chroot, release, cache_dir):
    """Creates a minimal root with the chown shim and proot-msan."""
    root = chroot.root
    config = RELEASES[release]
    url = config["base_tarball_url"]
    tarball = fetch(url, config["base_tarball_sha256"],
                    os.path.join(cache_dir, os.path.basename(url)))
    log(f"Extracting base system into {root}")
    rmtree(root)
    os.makedirs(root)
    subprocess.check_call([
        "tar", "-xzf", tarball, "-C", root, "--no-same-owner",
        "--no-same-permissions", "--exclude=./dev/*"
    ])
    configure_root(root, release, cache_dir)

    log(f"Bootstrapping from snapshot {SNAPSHOT}")
    chroot.run("apt-get update")
    bootstrap = [f"apt-get install {' '.join(BOOTSTRAP_PACKAGES)}"]
    prefetch_packages(chroot, cache_dir, bootstrap)
    chroot.run(" && ".join(bootstrap + [
        # The bootstrap packages build the chown shim and proot-msan. None of
        # them ship files with non-root owners, so they don't need the shim.
        "gcc -shared -fPIC -O2 -o %s /usr/local/src/chown_shim.c -ldl" %
        CHOWN_SHIM_PATH,
    ]))
    build_msan_proot(chroot)


def archives_dir(cache_dir):
    """Returns the persistent apt package cache, or None if there isn't one."""
    if os.path.commonpath([cache_dir, SRC_DIR]) != SRC_DIR:
        return None
    return os.path.join(cache_dir, "archives")


def prefetch_packages(chroot, cache_dir, commands):
    """Downloads the packages that `commands` would install, in parallel.

    snapshot.ubuntu.com takes seconds per request, and apt downloads one file
    at a time, so installing thousands of build dependencies would take hours.
    Instead, ask apt which files it needs, download them concurrently into its
    cache, and let apt verify them against the snapshot's signed indices. Files
    are fetched from archive.ubuntu.com when they're still there, since it's
    much faster, falling back to the snapshot otherwise.
    """
    archives = archives_dir(cache_dir)
    if not archives:
        return
    uris_file = "/tmp/apt-uris"
    shim = os.path.join(chroot.root, "usr/local/sbin/apt-get")
    # PATH has /usr/local/sbin first, so this catches apt-get invocations in
    # install-build-deps.sh as well.
    write_file(
        shim, "#!/bin/sh\n"
        f'exec /usr/bin/apt-get --print-uris -qq "$@" >> {uris_file}\n', 0o755)
    try:
        if os.path.exists(chroot.root + uris_file):
            os.unlink(chroot.root + uris_file)
        try:
            chroot.run(" && ".join(commands))
        except subprocess.CalledProcessError:
            # Let the actual installation report the error.
            log("Failed to list packages to prefetch")
            return
        with open(chroot.root + uris_file) as f:
            lines = f.read().splitlines()
    finally:
        os.unlink(shim)

    files = {}
    for line in lines:
        m = re.match(r"^'([^']+)' (\S+\.deb) (\d+) (\w+):([0-9a-f]+)$", line)
        if m:
            files[m.group(2)] = m.groups()
    todo = []
    for url, name, size, hash_type, digest in files.values():
        dest = os.path.join(archives, name)
        if not os.path.exists(dest) or os.path.getsize(dest) != int(size):
            todo.append((url, dest, int(size), hash_type, digest))
    log(f"Prefetching {len(todo)} of {len(files)} packages")

    def download(item):
        url, dest, size, hash_type, digest = item
        urls = [url]
        if url.startswith(SNAPSHOT_URL):
            urls.insert(0, ARCHIVE_URL + url[len(SNAPSHOT_URL):])
        tmp = os.path.join(archives, "partial", os.path.basename(dest))
        for u in urls:
            try:
                h = hashlib.new(hash_type.lower().replace("sum", ""))
                with urllib.request.urlopen(u, timeout=120) as resp, \
                        open(tmp, "wb") as out:
                    for chunk in iter(lambda: resp.read(1 << 20), b""):
                        h.update(chunk)
                        out.write(chunk)
                if h.hexdigest() == digest and os.path.getsize(tmp) == size:
                    os.replace(tmp, dest)
                    return True
            except Exception:
                pass
        # Leave it to apt, which will report a proper error if it also fails.
        if os.path.exists(tmp):
            os.unlink(tmp)
        return False

    with concurrent.futures.ThreadPoolExecutor(32) as executor:
        failed = list(executor.map(download, todo)).count(False)
    if failed:
        log(f"Failed to prefetch {failed} packages")


def install_packages(chroot, release, cache_dir):
    """Installs the build dependencies. Safe to rerun on an existing root."""
    preload = "/etc/ld.so.preload"
    log(f"Installing packages from snapshot {SNAPSHOT}")
    chroot.run("apt-get update")
    commands = [
        "apt-get dist-upgrade",
        f"apt-get install {' '.join(EXTRA_PACKAGES)}",
        # Invoking via bash ignores the script's shebang, so pass -e here.
        f"bash -e {shlex.quote(install_build_deps_script(release))}",
    ]
    prefetch_packages(chroot, cache_dir, commands)
    chroot.run(" && ".join([
        f"echo {CHOWN_SHIM_PATH} > {preload}",
        # The shim is only needed by dpkg. Don't load it into build processes,
        # even if a command below fails.
        f"trap 'rm -f {preload}' EXIT",
    ] + commands + [
        f"lsb_release -cs | grep -qx {release}",
    ]))


def build_msan_proot(chroot):
    """Builds a proot whose load addresses don't collide with MSan."""
    log(f"Building {MSAN_PROOT_PATH}")
    workdir = "/tmp/proot-msan-build"
    arch_h = f"{workdir}/proot/src/arch.h"
    patches = []
    for name, (old, new) in sorted(PROOT_ADDRESSES.items()):
        pattern = rf"^\(#define {name} \+\){old}$"
        patches += [
            f"sed -i 's/{pattern}/\\1{new}/' {arch_h}",
            # Fail if the source changed and the substitution didn't apply.
            f"grep -Eq '^#define {name} +{new}$' {arch_h}",
        ]
    chroot.run(" && ".join([
        f"rm -rf {workdir}",
        f"mkdir -p {workdir}",
        f"cd {workdir}",
        "git init -q proot",
        "git -C proot fetch -q --depth 1 %s %s" %
        (PROOT_GIT_URL, PROOT_GIT_REVISION),
        "git -C proot checkout -q FETCH_HEAD",
        f"test $(git -C proot rev-parse HEAD) = {PROOT_GIT_REVISION}",
    ] + patches + [
        "make -C proot/src -j$(nproc) proot "
        "LDFLAGS='-ltalloc -Wl,-z,noexecstack' > make.log 2>&1 "
        "|| { tail -30 make.log; false; }",
        # proot-msan runs on the host, outside the chroot. Not every release
        # ships a static libtalloc, so link dynamically, and load the chroot's
        # libraries using its dynamic linker.
        f"patchelf --set-interpreter {chroot.root}{CHROOT_LD_SO} "
        f"--force-rpath --set-rpath {chroot.root}{CHROOT_LIB_DIR} "
        "proot/src/proot",
        f"install -m755 proot/src/proot {MSAN_PROOT_PATH}",
        "cd /",
        f"rm -rf {workdir}",
    ]))


def setup_root(chroot, release, cache_dir, recreate):
    """Creates or updates the chroot as needed."""
    root = chroot.root
    stamp_path = f"{root}.stamp"
    wanted = setup_fingerprint(release)
    stamp = None if recreate else read_stamp(stamp_path)
    if stamp is None or stamp["base"] != wanted["base"]:
        if os.path.exists(stamp_path):
            os.unlink(stamp_path)
        create_root(chroot, release, cache_dir)
        # From here on, failures can be fixed without recreating the root.
        write_stamp(stamp_path, {"base": wanted["base"]})
        install_packages(chroot, release, cache_dir)
    elif stamp.get("packages") != wanted["packages"]:
        log(f"Package lists changed. Updating chroot at {root}")
        # Invalidate the stamp first in case the installation fails.
        write_stamp(stamp_path, {"base": stamp["base"]})
        shutil.copy("/etc/resolv.conf", os.path.join(root, "etc/resolv.conf"))
        install_packages(chroot, release, cache_dir)
    else:
        log(f"Reusing chroot at {root}")
        # Pick up any changes to the host's DNS configuration.
        shutil.copy("/etc/resolv.conf", os.path.join(root, "etc/resolv.conf"))
    write_stamp(stamp_path, wanted)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release",
                        choices=sorted(RELEASES),
                        default="noble",
                        help="Ubuntu release to build the libraries for")
    parser.add_argument(
        "--mode",
        choices=["namespace", "proot"],
        default="namespace",
        help="isolation mechanism. 'namespace' requires unprivileged user "
        "namespaces. 'proot' only requires ptrace but is slower.")
    parser.add_argument(
        "--proot",
        help="path to a proot binary used to bootstrap the chroot in proot "
        "mode. If not given, a pinned static proot release is downloaded. The "
        "build itself always uses the MSan-compatible proot built during "
        "setup.")
    parser.add_argument(
        "--root-dir",
        help="where to create the chroot. It's reused across runs as long as "
        "the configuration hasn't changed. Defaults to "
        "out/instrumented_libs_chroot_<release>.")
    parser.add_argument(
        "--out-dir",
        help="directory, relative to src, in which build_and_package.py "
        "creates its Instrumented-* build dirs. Defaults to "
        "out/instrumented_libs_build_<release>, rather than out/, since "
        "out/Instrumented-* may be owned by root from a previous "
        "schroot-based build.")
    parser.add_argument("--recreate",
                        action="store_true",
                        help="recreate the chroot even if it's up to date")
    parser.add_argument("--setup-only",
                        action="store_true",
                        help="only set up the chroot; don't build")
    parser.add_argument("--jobs",
                        "-j",
                        type=int,
                        default=os.cpu_count(),
                        help="number of parallel jobs")
    parser.add_argument("--shell",
                        action="store_true",
                        help="open an interactive shell in the chroot instead "
                        "of building")
    parser.add_argument(
        "--packages",
        help="comma-separated list of packages (GN target names) to build "
        "instead of all of them. Skips packaging.")
    parser.add_argument("--keep-going",
                        action="store_true",
                        help="keep building other packages after a failure")
    parser.add_argument(
        "--no-clobber",
        action="store_true",
        help="keep each package's source and build tree after building, and "
        "reuse it (without re-downloading or re-patching) on the next build. "
        "Failed builds always keep their tree.")
    parser.add_argument("build_type",
                        nargs="*",
                        default=["all"],
                        help="build types to pass to build_and_package.py")
    args = parser.parse_args()

    release = args.release
    root = os.path.abspath(
        args.root_dir
        or os.path.join(SRC_DIR, "out", f"instrumented_libs_chroot_{release}"))
    out_dir = args.out_dir or os.path.join(
        "out", f"instrumented_libs_build_{release}")
    cache_dir = f"{root}.cache"

    proot = None
    if args.mode == "proot":
        if args.proot:
            proot = os.path.abspath(args.proot)
        else:
            proot = fetch(PROOT_URL, PROOT_SHA256,
                          os.path.join(cache_dir, "proot"))
            os.chmod(proot, 0o755)

    chroot = Chroot(root, args.mode, proot)
    setup_root(chroot, release, cache_dir, args.recreate)

    if args.mode == "proot":
        # Stock proot can't run MSan-instrumented programs. Use the one built
        # during setup from now on.
        chroot.proot = root + MSAN_PROOT_PATH

    build_env = []
    if args.no_clobber:
        build_env.append("INSTRUMENTED_LIBRARIES_NO_CLOBBER=1")

    if args.shell:
        chroot.run("exec bash -i", cwd=SRC_DIR, extra_env=build_env)
        return 0
    if args.setup_only:
        return 0

    build_and_package = os.path.join(INSTRUMENTED_LIBS_DIR, "scripts",
                                     "build_and_package.py")
    common_args = [
        "--parallel",
        f"-j{args.jobs}",
        "--out-dir",
        out_dir,
    ]
    build_args = []
    if args.packages:
        build_args.append(f"--packages={args.packages}")
    if args.keep_going:
        build_args.append("--keep-going")
    positional_args = args.build_type + [release]
    package = not args.packages

    def build_and_package_in_chroot(extra_args):
        chroot.run(" ".join(
            shlex.quote(a) for a in ["python3", build_and_package] +
            extra_args + common_args + positional_args),
                   cwd=SRC_DIR,
                   extra_env=build_env)

    log("Building instrumented libraries")
    if args.mode == "namespace":
        steps = "gen,build,package" if package else "gen,build"
        build_and_package_in_chroot([f"--steps={steps}"] + build_args)
    else:
        wrapper = os.path.join(SRC_DIR, out_dir, "python3-in-chroot")
        chroot.write_proot_wrapper(wrapper, gn_script_executable(), build_env)
        build_and_package_in_chroot(
            ["--steps=gen", f"--script-executable={wrapper}"])
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(
            [os.path.join(SRC_DIR, "third_party", "ninja"), env["PATH"]])
        subprocess.check_call(
            [sys.executable, build_and_package, "--steps=build"] + build_args +
            common_args + positional_args,
            cwd=SRC_DIR,
            env=env)
        if package:
            build_and_package_in_chroot(["--steps=package"])
    if package:
        log(f"Done. Tarballs are in {SRC_DIR}")
    else:
        log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
