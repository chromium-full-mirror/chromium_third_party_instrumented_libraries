# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import subprocess

PATTERN = re.compile(r".*\.so[.0-9]*$")


def fix_rpaths(directory: str):
    dpkg_arch_cmd = ["dpkg-architecture", "-qDEB_HOST_MULTIARCH"]
    dpkg_arch = subprocess.check_output(dpkg_arch_cmd, text=True).strip()
    lib_dirs = [
        "/usr/lib/%s/" % dpkg_arch,
        "/lib/%s/" % dpkg_arch,
        "/lib/",
    ]

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.startswith("ld-linux"):
                continue
            filepath = os.path.join(root, filename)
            if not PATTERN.match(filename) or os.path.islink(filepath):
                continue
            result = subprocess.run(
                ["patchelf", "--print-rpath", filepath], capture_output=True, text=True
            )
            rpath = result.stdout.strip()
            if result.returncode != 0:
                continue
            paths = []
            for path in rpath.split(":"):
                if not os.path.isabs(path):
                    paths.append(path)
                    continue
                for prefix in lib_dirs:
                    if path.startswith(prefix):
                        path = path.removeprefix(prefix)
                        break
                else:
                    raise ValueError(
                        f"No matching prefix found for {path} in {filepath}"
                    )
                relative_path = os.path.relpath(os.path.join(directory, path), root)
                paths.append(os.path.join("$ORIGIN", relative_path))

            # Ensure the RPATH always includes an entry pointing to the instrumented
            # libraries.  This is required for libraries that are dlopen()ed.
            relative_path = os.path.relpath(directory, root)
            default_path = os.path.join("$ORIGIN", relative_path)
            if default_path not in paths:
                paths.append(default_path)

            new_rpath = ":".join(paths)
            subprocess.run(["patchelf", "--set-rpath", new_rpath, filepath], check=True)
