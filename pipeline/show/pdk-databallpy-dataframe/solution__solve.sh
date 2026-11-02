#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
git checkout -b feature/solution 2>/dev/null || true
git add -A
git -c user.name=oracle -c user.email=oracle@local commit -q --no-verify -m "Apply reference solution" || true
mkdir -p /logs/artifacts
git diff --binary f21d47f9dded55b12da6e0ba16ebf48e10bad84b HEAD > /logs/artifacts/model.patch
