#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /logs/artifacts
cp /solution/solution.patch /logs/artifacts/model.patch
