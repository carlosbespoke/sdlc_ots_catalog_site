#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
mkdir -p stonesoup/tests
cp /solution/reproducer/stonesoup/tests/test_repro.py stonesoup/tests/test_repro.py
cp /solution/rca.json /workdir/rca.json
