#!/usr/bin/env bash
# Verifier entry point. Writes one reward to /logs/verifier/reward.txt.
# The trap is a crash sentinel: if grading dies before writing a reward, the frame sees
# -1 rather than a stale or missing file. Absolute paths throughout, because Harbor may
# run this from any working directory.
set -uo pipefail
mkdir -p /logs/verifier
trap 'if [ ! -s /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
python3 /tests/grade.py
