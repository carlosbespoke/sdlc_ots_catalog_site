#!/bin/sh
# Reference repair: restore the behavior the repository's documentation specifies.
set -eu
cd /workdir
git apply --verbose -p1 /solution/solution.patch 2>/dev/null || patch -p1 --batch --forward < /solution/solution.patch
