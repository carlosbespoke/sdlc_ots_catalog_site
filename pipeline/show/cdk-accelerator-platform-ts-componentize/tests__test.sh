#!/bin/bash
# Verifier entrypoint (separate verifier container). The agent's /workspace/accelerator-platform arrives as an artifact; grade.py grades
# it offline against the verifier's own expected templates and writes /logs/verifier/reward.txt (and metrics.json).
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/metrics.json
# A crash or an infrastructure problem must never look like a graded submission: reward -1 unless grade.py wrote one.
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
export PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in node python3 runuser cdk; do command -v "$tool" >/dev/null || exit 6; done
id -u nobody >/dev/null || exit 6
if [ ! -d /workspace/accelerator-platform ]; then
  echo "[verifier] no /workspace/accelerator-platform artifact was collected; grading an empty submission"
  mkdir -p /workspace/accelerator-platform
fi
cd /
/usr/bin/python3 /tests/grade.py 2>&1 | tee /logs/verifier/grade.log
