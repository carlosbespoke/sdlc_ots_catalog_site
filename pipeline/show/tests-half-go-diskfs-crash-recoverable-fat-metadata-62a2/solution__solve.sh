#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
git checkout -b feature/solution 2>/dev/null || true
git add -A
git -c user.name=oracle -c user.email=oracle@local commit -q --no-verify -m "Apply reference solution" || true
mkdir -p /logs/artifacts
git diff --binary 5ec1662c401c4ab58904983f283244fc1b3fd4c6 HEAD > /logs/artifacts/model.patch
