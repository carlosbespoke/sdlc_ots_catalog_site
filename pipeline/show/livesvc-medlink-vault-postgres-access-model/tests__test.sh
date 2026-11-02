#!/bin/bash
# Verifier entrypoint (separate container, no network). The agent's repository arrives as an artifact; grade.py starts
# fresh platform services from the snapshot, applies the reference and the submission, observes both and writes
# /logs/verifier/reward.txt, metrics.json and grading.json.
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/metrics.json
# A crash or an infrastructure problem must never look like a graded submission: reward -1 unless grade.py wrote one.
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
export PATH=/usr/lib/postgresql/17/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in terraform hcl2json runuser python3 initdb pg_ctl psql vault; do command -v "$tool" >/dev/null || exit 6; done
cd /
python3 /tests/grade.py --tests /tests --out /logs/verifier 2>&1 | tee /logs/verifier/grade.log
