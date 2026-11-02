#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
mkdir -p tests
cp /solution/reproducer/tests/test_csv_diverged_runs.py tests/test_csv_diverged_runs.py
cp /solution/rca.json /workdir/rca.json
