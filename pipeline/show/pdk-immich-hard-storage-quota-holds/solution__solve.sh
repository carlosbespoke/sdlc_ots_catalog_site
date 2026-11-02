#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
git checkout -b feature/solution 2>/dev/null || true
git add -A
git -c user.name=oracle -c user.email=oracle@local commit -q --no-verify -m "Apply reference solution" || true
mkdir -p /logs/artifacts
git diff --binary 116a9436ad1f8164d9dee904551e5067d724be99 HEAD > /logs/artifacts/model.patch
