#!/bin/sh
# Verifier entry point (separate mode): runs as root in the image built from tests/Dockerfile,
# with the agent's final /workdir copied in. Pre-write -1 so an infrastructure crash is never
# read as a 0 or 1 grade.
set -eu
mkdir -p /logs/verifier
chown root:root /logs/verifier
printf '%s\n' '-1' > /logs/verifier/reward.txt
chmod 700 /tests
chmod 755 /logs/verifier
PY=/opt/venv/bin/python
[ -x "$PY" ] || PY=python3
# -I -S: ignore PYTHON* and skip site/.pth so a candidate sitecustomize cannot run as root.
# -B: write no bytecode (-I ignores PYTHONDONTWRITEBYTECODE; /tests stays root-only files only).
exec "$PY" -I -S -B /tests/grade.py /workdir
