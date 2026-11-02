#!/bin/sh
set -eu
mkdir -p /logs/verifier
chown root:root /logs/verifier
printf '%s\n' '-1' > /logs/verifier/reward.txt
chmod 700 /tests
chmod 755 /logs/verifier
PY=/opt/venv/bin/python
[ -x "$PY" ] || PY=python3
# -I -S: ignore PYTHON* and skip site/.pth so a candidate sitecustomize cannot run as root.
exec "$PY" -I -S /tests/grade.py /workdir
