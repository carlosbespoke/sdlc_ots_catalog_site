#!/bin/sh
set -eu
cd /workdir
git -c safe.directory='*' apply --whitespace=nowarn /solution/gold.patch
mkdir -p starlark
cp /solution/reproducer/starlark/repro_test.go starlark/repro_test.go
cp /solution/rca.json /workdir/rca.json
