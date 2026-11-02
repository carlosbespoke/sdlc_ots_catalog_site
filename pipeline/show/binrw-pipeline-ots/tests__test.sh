#!/bin/sh
# Harbor runs this as root in the verifier image (tests/Dockerfile) after copying the agent's
# /workdir in. A crash anywhere below leaves reward -1, never a misleading behavioural 0.
set -eu
mkdir -p /logs/verifier
chown root:root /logs/verifier
printf '%s\n' '-1' > /logs/verifier/reward.txt
chmod 700 /tests
chmod 755 /logs/verifier
PY=/usr/bin/python3
[ -x "$PY" ] || PY=python3
# -I -S: ignore PYTHON* and skip site/.pth so nothing from the candidate can run as root.
exec "$PY" -I -S /tests/grade_rs.py /workdir
