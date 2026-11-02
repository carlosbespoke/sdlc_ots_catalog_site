#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
cp /solution/reproducer/repro_test.go repro_test.go
cp /solution/rca.json /workdir/rca.json
