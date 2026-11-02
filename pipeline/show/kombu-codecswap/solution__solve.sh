#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
mkdir -p tests
cp /solution/reproducer/tests/test_legacy_charset.py tests/test_legacy_charset.py
cp /solution/rca.json /workdir/rca.json
