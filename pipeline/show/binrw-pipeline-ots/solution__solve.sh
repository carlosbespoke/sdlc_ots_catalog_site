#!/bin/sh
# Reference repair: restore the behaviour the repository's documentation specifies.
set -eu
cd /workdir
git apply --whitespace=nowarn /solution/solution.patch
