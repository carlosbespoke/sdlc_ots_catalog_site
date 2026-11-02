#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
cp /solution/reproducer/internal/core/tree/repro_test.go internal/core/tree/repro_test.go
cp /solution/rca.json /workdir/rca.json
