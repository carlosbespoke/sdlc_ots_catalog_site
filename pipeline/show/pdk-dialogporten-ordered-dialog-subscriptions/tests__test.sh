#!/bin/bash
# Verifier entry point (tests/test.sh). Copy unchanged. It applies the submission and the hidden
# tests (grader.py prepare), stages a root-only copy of the runner and hidden tests, runs the
# repository's suites and the hidden suite with the submission's code as an unprivileged user,
# and grades the two reports (grader.py grade).
set -uo pipefail

VGEN_SYS_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin
# Root runs tools by name from here on, so PATH keeps only root-owned folders no one else can write,
# outside /app: golang images put /go/bin (mode 1777) first, where the code under test, running as
# sdapp during the repository's suites, could leave a `go` that root then runs for the hidden suite.
vgen_path=
IFS=: read -ra vgen_dirs <<< "$PATH"
for vgen_dir in "${vgen_dirs[@]}"; do
  case "$vgen_dir" in ""|.|/app|/app/*|/tmp|/tmp/*) continue ;; esac
  [ -d "$vgen_dir" ] && [ "$(stat -L -c %u "$vgen_dir" 2>/dev/null)" = 0 ] || continue
  [ -z "$(find -L "$vgen_dir" -maxdepth 0 -perm /022 2>/dev/null)" ] || continue
  vgen_path="${vgen_path:+$vgen_path:}$vgen_dir"
done
export PATH="${vgen_path:-$VGEN_SYS_PATH}"
VGEN_BIN=$(mktemp -d /tmp/vgen-bin.XXXXXXXX 2>/dev/null) || VGEN_BIN=
if [ -n "$VGEN_BIN" ]; then
  chmod 755 "$VGEN_BIN" 2>/dev/null
  for vgen_tool in git rm mkdir bash sh python3 dotnet go node npm service pg_isready psql rabbitmqctl redis-cli \
                   timeout runuser pkill pgrep find chown install mktemp env; do
    vgen_found=$(PATH=$VGEN_SYS_PATH command -v "$vgen_tool" 2>/dev/null) || continue
    ln -sf "$vgen_found" "$VGEN_BIN/$vgen_tool" 2>/dev/null
  done
  export PATH="$VGEN_BIN:$PATH"
fi
VGEN_PY=$(PATH=$VGEN_SYS_PATH command -v python3 2>/dev/null) || VGEN_PY=python3
echo "[verifier] tools pinned to $VGEN_BIN, grader interpreter $VGEN_PY"

trap 'if [ ! -f /logs/verifier/reward.json ] && [ ! -f /logs/verifier/reward.txt ]; then mkdir -p /logs/verifier; echo -1 > /logs/verifier/reward.txt; fi' EXIT
cd /app || exit 6

# The grader runs as root in isolated mode (-I): an image's PYTHONPATH often points into the
# submission's tree, where a planted module would otherwise shadow the grader's stdlib imports.
"$VGEN_PY" -I /tests/grader.py prepare || exit $?
[ -f /logs/verifier/reward.txt ] && exit 0
[ -f /logs/verifier/reward.json ] && exit 0
mkdir -p /logs/verifier

# Only root may read the grading files or write the reports.
GRADE_DIR=/var/lib/sd-grading
chmod 755 /logs /logs/verifier 2>/dev/null
chmod 700 /tests; chmod 600 /tests/* 2>/dev/null; chmod 700 /tests/test.sh 2>/dev/null
GRADE_DIR=$GRADE_DIR bash /app/test.sh stage || exit 6
# Build-time switches, never set by the hosted grader. run_matrix.sh --hidden-only sets SD_REUSE_BASE
# to the row's repository-suite report from the last full matrix (the suites' inputs are unchanged);
# the matrix sets SD_SKIP_BASE for shortcut patches, which are judged on the hidden suite alone.
if [ -n "${SD_REUSE_BASE:-}" ] && [ -f "$SD_REUSE_BASE" ]; then
  cp "$SD_REUSE_BASE" /logs/verifier/base.xml && echo "[verifier] SD_REUSE_BASE: reusing the repository-suite report"
elif [ -z "${SD_SKIP_BASE:-}" ]; then
  RUN_AS=sdapp GRADE_DIR=$GRADE_DIR JUNIT_REPORT=/logs/verifier/base.xml bash $GRADE_DIR/test.sh base
else
  echo "[verifier] SD_SKIP_BASE set: the repository's suites are not run"
fi
RUN_AS=sdapp GRADE_DIR=$GRADE_DIR JUNIT_REPORT=/logs/verifier/new.xml bash $GRADE_DIR/test.sh new

echo "===== grade ====="
"$VGEN_PY" -I /tests/grader.py grade
