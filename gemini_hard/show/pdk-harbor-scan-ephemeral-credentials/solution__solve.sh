#!/bin/bash
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
git add -N src/controller/scan/credential.go src/pkg/scan/lease.go src/server/middleware/security/scan_bearer.go src/server/middleware/v2auth/scanner_repository.go
mkdir -p /logs/artifacts
git diff --binary b323c0c8ec897038a6090255cf9415e747e4730a > /logs/artifacts/model.patch
