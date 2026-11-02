#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier /logs/artifacts
printf '{"reward": 0.0}' > /logs/verifier/reward.json
printf '0.0\n' > /logs/verifier/reward.txt
FB_VERIFIER_DIR=/logs/verifier python3 /tests/fb_grader.py /app /tests/spec /tests/manifest.json /logs/artifacts/model.patch
