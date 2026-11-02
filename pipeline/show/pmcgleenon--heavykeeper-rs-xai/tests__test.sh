#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier /logs/artifacts
printf '{"reward": 0.0}' > /logs/verifier/reward.json
printf '0.0\n' > /logs/verifier/reward.txt
cd /app
git config --global --add safe.directory /app 2>/dev/null || true
P=/logs/artifacts/model.patch
if [ -s "$P" ]; then git apply --whitespace=nowarn "$P" 2>/tmp/pa.err || git apply --3way --whitespace=nowarn "$P" 2>>/tmp/pa.err || echo "[test.sh] patch FAILED"; else echo "[test.sh] no patch"; fi
MIG_VERIFIER_DIR=/logs/verifier python3 /tests/grader_tests.py /app/port /tests/spec /tests/spec/manifest.json
