#!/bin/bash
# Verifier entrypoint (separate verifier container). The agent's /workspace/infra arrives as an artifact; grade.py
# grades it offline against the verifier's own pristine state and policy pack and writes /logs/verifier/reward.txt
# (plus metrics.json and grading.json; never reward.json).
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/grading.json /logs/verifier/metrics.json
# A crash or an infrastructure problem must never look like a graded submission: reward -1 unless grade.py wrote one.
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
export PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in terraform hcl2json conftest runuser python3; do command -v "$tool" >/dev/null || exit 6; done
id -u nobody >/dev/null || exit 6
if [ ! -d /workspace/infra ]; then
  echo "[verifier] no /workspace/infra artifact was collected; grading an empty submission"
  mkdir -p /workspace/infra
fi
cd /
python3 /tests/grade.py 2>&1 | tee /logs/verifier/grade.log
