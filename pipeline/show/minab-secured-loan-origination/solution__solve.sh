#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
git checkout -b feature/solution 2>/dev/null || true
git add -A
git -c user.name=oracle -c user.email=oracle@local commit -q --no-verify -m "Apply reference solution" || true
mkdir -p /logs/artifacts
git diff --binary ea1d817dc3cca12bd47fb790dbed5e4d91e0ed30 HEAD > /logs/artifacts/model.patch
