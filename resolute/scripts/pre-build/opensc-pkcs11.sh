#!/bin/bash
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The p11-kit module file is installed by an arch-independent package, which
# isn't built by `dpkg-buildpackage -B`, so dh_missing would fail.
echo usr/share/p11-kit/modules/opensc.module >> debian/not-installed
