#!/bin/bash
# Verifier entrypoint (separate verifier container). The agent's /workspace/pulumi arrives as an artifact; grade.py
# previews it offline against the verifier's own copy of the production Pulumi stack and writes
# /logs/verifier/reward.txt (+ metrics.json, grading.json).
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/grading.json /logs/verifier/metrics.json
# A crash or an infrastructure problem must never look like a graded submission: reward -1 unless grade.py wrote one.
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
export PATH=/opt/pulumi:/opt/node/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in pulumi python3 setpriv prlimit; do command -v "$tool" >/dev/null || exit 6; done
id -u nobody >/dev/null || exit 6
if [ ! -d /workspace/pulumi ]; then
  echo "[verifier] no /workspace/pulumi artifact was collected; grading an empty submission"
  mkdir -p /workspace/pulumi
fi
# the submission copy is root-only: the program under test runs as nobody and sees only the grader's project copy
chmod 700 /workspace
cd /
python3 /tests/grade.py 2>&1 | tee /logs/verifier/grade.log
