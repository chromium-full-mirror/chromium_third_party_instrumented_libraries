#!/usr/bin/env python3
# Copyright 2016 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Builds and packages instrumented libraries for dynamic tools."""

import argparse
import multiprocessing
import os
import re
import shutil
import stat
import subprocess
import tarfile

import fix_rpaths

BUILD_TYPES = {
    "msan-no-origins": [
        "is_msan = true",
        "msan_track_origins = 0",
    ],
    "msan-chained-origins": [
        "is_msan = true",
        "msan_track_origins = 2",
    ],
}

SO_PATTERN = re.compile(r'.*\.so[.0-9]*')


class Error(Exception):
    pass


class IncorrectReleaseError(Error):
    pass


def _get_release():
    return subprocess.check_output(["lsb_release",
                                    "-cs"]).decode("utf-8").strip()


def _tar_filter(tar_info):
    path = tar_info.name.split("/")

    # Ignore the build-generated stamp files.
    if path[1].endswith(".txt"):
        return None

    # Omit git directories from sources.  They can contain non-writable files.
    if path[1] == "sources" and ".git" in path:
        return None

    # Always allow directories (except .git).
    if tar_info.type == tarfile.DIRTYPE:
        # Ensure directories are writable otherwise if it has any contents,
        # the archive won't be extractable.
        tar_info.mode |= stat.S_IWUSR
        return tar_info

    # Omit non-libraries in LIBDIR and LDDIR.
    if path[1] in ("lib", "ld") and not SO_PATTERN.fullmatch(path[-1]):
        return None

    # Ensure no non-writable files exist in the archive, otherwise extraction
    # issues can occur.
    if not (tar_info.mode & stat.S_IWUSR):
        raise Exception(f"Non-writable file: {tar_info.name}")

    return tar_info


def build_libraries(build_type, ubuntu_release, jobs, use_remoteexec):
    build_dir = f"out/Instrumented-{build_type}"
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    gn_args = [
        "is_debug = false",
        f"use_remoteexec = {str(use_remoteexec).lower()}",
        "use_locally_built_instrumented_libraries = true",
        f'instrumented_libraries_release = "{ubuntu_release}"',
    ] + BUILD_TYPES[build_type]
    with open(os.path.join(build_dir, "args.gn"), "w") as f:
        f.write("\n".join(gn_args) + "\n")
    subprocess.check_call(["gn", "gen", build_dir, "--check"])
    subprocess.check_call([
        "ninja",
        f"-j{jobs}",
        "-C",
        build_dir,
        f"third_party/instrumented_libs/{ubuntu_release}:locally_built",
    ])
    release = _get_release()
    name = f"{build_type}-{release}-lib"
    lib_dir = f"{build_dir}/instrumented_libraries/lib"
    ld_dir = f"{build_dir}/instrumented_libraries/ld"
    os.makedirs(ld_dir, exist_ok=True)
    shutil.copy(os.path.join(lib_dir, "ld-linux-x86-64.so.2"),
                os.path.join(ld_dir, "ld-linux-x86-64.so.2"))
    fix_rpaths.fix_rpaths(lib_dir)
    with tarfile.open(f"{name}.tar.gz", mode="w:gz") as f:
        f.add(
            ld_dir,
            arcname=f"{name}/ld",
            filter=_tar_filter,
        )
        f.add(
            lib_dir,
            arcname=f"{name}/lib",
            filter=_tar_filter,
        )
        f.add(
            f"{build_dir}/instrumented_libraries/sources",
            arcname=f"{name}/sources",
            filter=_tar_filter,
        )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=8,
        help="the default number of jobs to use when running ninja",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="whether to run all instrumented builds in parallel",
    )
    parser.add_argument(
        "--use_remoteexec",
        action="store_true",
        default=False,
        help="whether to use reclient to compile",
    )
    parser.add_argument(
        "build_type",
        nargs="*",
        default="all",
        choices=list(BUILD_TYPES.keys()) + ["all"],
        help="the type of instrumented library to build",
    )
    parser.add_argument("release",
                        help="the name of the Ubuntu release to build with")
    args = parser.parse_args()
    if args.build_type == "all" or "all" in args.build_type:
        args.build_type = BUILD_TYPES.keys()

    if args.release != _get_release():
        raise IncorrectReleaseError(
            f"trying to build for {args.release} but the current release is "
            f"{_get_release()}")
    build_types = sorted(set(args.build_type))
    if args.parallel:
        procs = []
        for build_type in build_types:
            proc = multiprocessing.Process(
                target=build_libraries,
                args=(build_type, args.release, args.jobs, args.use_remoteexec),
            )
            proc.start()
            procs.append(proc)
        for proc in procs:
            proc.join()
    else:
        for build_type in build_types:
            build_libraries(build_type, args.release, args.jobs, args.use_remoteexec)
    print("To upload, run:")
    for build_type in build_types:
        print("upload_to_google_storage_first_class.py -b "
              "chromium-instrumented-libraries "
              f"{build_type}-{args.release}-lib.tar.gz")
    print("You should then commit the resulting .sha1 files.")


if __name__ == "__main__":
    main()
