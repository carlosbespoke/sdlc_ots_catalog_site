#!/bin/bash
# Verifier entrypoint (separate verifier container, root). The agent's repository arrives as an artifact; grade.py
# rebuilds the production snapshot and a hidden-salt one, runs the submission's migrations against private database
# servers as the unprivileged user `solver`, and writes /logs/verifier/reward.txt, reward.json and metrics.json.
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/metrics.json
# A crash or an infrastructure problem must never look like a graded submission: reward -1 unless grade.py wrote one.
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
export PATH=/opt/dbm/venv/bin:/usr/lib/postgresql/16/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in python3 setpriv; do command -v "$tool" >/dev/null || exit 6; done
id -u solver >/dev/null || exit 6
if [ ! -d "/workspace/ctfd" ]; then
  echo "[verifier] no /workspace/ctfd artifact was collected; grading an empty submission"
  mkdir -p "/workspace/ctfd"
fi
cd /
python3 /tests/grade.py 2>&1 | tee /logs/verifier/grade.log
