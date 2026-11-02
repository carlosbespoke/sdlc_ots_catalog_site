#!/bin/bash
set -uo pipefail

VERIFIER_SYS_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
VERIFIER_BIN=$(mktemp -d /tmp/verifier-bin.XXXXXXXX 2>/dev/null) || VERIFIER_BIN=
if [ -n "$VERIFIER_BIN" ]; then
  chmod 755 "$VERIFIER_BIN" 2>/dev/null
  for verifier_tool in git rm mkdir bash sh junit-to-ctrf id chown chmod setpriv runuser; do
    verifier_found=$(PATH=$VERIFIER_SYS_PATH command -v "$verifier_tool" 2>/dev/null) || continue
    ln -sf "$verifier_found" "$VERIFIER_BIN/$verifier_tool" 2>/dev/null
  done
  export PATH="$VERIFIER_BIN:$PATH"
fi
VERIFIER_PY=$(PATH=$VERIFIER_SYS_PATH command -v python3 2>/dev/null) || VERIFIER_PY=python3
echo "[verifier] tools pinned to $VERIFIER_BIN, grader interpreter $VERIFIER_PY"

trap 'if [ ! -f /logs/verifier/reward.json ] && [ ! -f /logs/verifier/reward.txt ]; then mkdir -p /logs/verifier; echo -1 > /logs/verifier/reward.txt; fi' EXIT
cd /app || exit 6

"$VERIFIER_PY" /tests/grader.py prepare || exit $?
[ -f /logs/verifier/reward.txt ] && exit 0
[ -f /logs/verifier/reward.json ] && exit 0
mkdir -p /logs/verifier

echo "[verifier] graded suite runs under pytest: tests/test_outputs.py"
VERIFIER_TEST_USER="${VERIFIER_TEST_USER:-agent}"
VERIFIER_DROP=""
VERIFIER_TEST_HOME="${HOME:-/root}"
mkdir -p /logs/verifier 2>/dev/null || true
if [ "$(id -u)" = "0" ] && id -u "$VERIFIER_TEST_USER" >/dev/null 2>&1; then
  verifier_uid=$(id -u "$VERIFIER_TEST_USER")
  verifier_gid=$(id -g "$VERIFIER_TEST_USER")
  if setpriv --reuid="$verifier_uid" --regid="$verifier_gid" --init-groups true >/dev/null 2>&1; then
    VERIFIER_DROP="setpriv --reuid=$verifier_uid --regid=$verifier_gid --init-groups --"
  elif runuser -p -u "$VERIFIER_TEST_USER" -- true >/dev/null 2>&1; then
    VERIFIER_DROP="runuser -p -u $VERIFIER_TEST_USER --"
  fi
fi
if [ -n "$VERIFIER_DROP" ]; then
  verifier_home=$(eval echo "~$VERIFIER_TEST_USER" 2>/dev/null) || verifier_home=""
  case "$verifier_home" in /*) [ -d "$verifier_home" ] && VERIFIER_TEST_HOME="$verifier_home" ;; esac
  chmod 1777 /logs/verifier 2>/dev/null || true
  chmod 0700 /tests 2>/dev/null || true
  echo "[verifier] graded run drops to $VERIFIER_TEST_USER (uid $verifier_uid, HOME=$VERIFIER_TEST_HOME); the frame stays root"
else
  echo "[verifier] graded run stays root: no unprivileged account to drop to" >&2
fi
verifier_reap() {
VERIFIER_REAP_STATUS=0
VERIFIER_REAP_UID="${VERIFIER_DROP:+${verifier_uid:-}}" VERIFIER_REAP_PGID="${verifier_run_pgid:-}" "${VERIFIER_PY:-python3}" - <<'VERIFIER_REAP_PY' || VERIFIER_REAP_STATUS=$?
import os
import signal


def stat_of(pid):
    with open("/proc/%d/stat" % pid) as handle:
        line = handle.read()
    fields = line[line.rfind(")") + 2:].split()
    return int(fields[1]), int(fields[2])


def cmdline(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as handle:
            raw = handle.read()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()[:200]


def scope(name):
    try:
        return int((os.environ.get(name) or "").strip())
    except ValueError:
        return None


me = os.getpid()
keep = set([1, me])
walk = me
while walk > 1:
    try:
        parent = stat_of(walk)[0]
    except (OSError, ValueError, IndexError):
        break
    if parent in keep:
        break
    keep.add(parent)
    walk = parent

uid = scope("VERIFIER_REAP_UID")
if uid is None or uid == os.getuid():
    uid = None
pgid = scope("VERIFIER_REAP_PGID")
if pgid is None or pgid == os.getpgid(0):
    pgid = None

victims = []
if uid is not None or pgid is not None:
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in keep:
            continue
        try:
            owner = os.stat("/proc/%d" % pid).st_uid
            group = stat_of(pid)[1]
        except (OSError, ValueError, IndexError):
            continue
        why = []
        if uid is not None and owner == uid:
            why.append("uid %d" % owner)
        if pgid is not None and group == pgid:
            why.append("pgid %d" % group)
        if why:
            victims.append((pid, "/".join(why), cmdline(pid)))

killed = 0
for pid, why, command in victims:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError as exc:
        print("[verifier] REAP: pid %d (%s) could not be killed: %r"
              % (pid, why, exc))
        continue
    killed += 1
    print("[verifier] REAP: killed pid %d (%s), which outlived the graded "
          "run: %s" % (pid, why, command))
if killed:
    print("[verifier] REAP: %d process(es) outlived the graded run and were "
          "killed before anything read the reports" % killed)
else:
    print("[verifier] reap: nothing of the graded run is still running")
VERIFIER_REAP_PY
if [ "$VERIFIER_REAP_STATUS" != "0" ]; then
  echo "[verifier] the reap could not run (exit $VERIFIER_REAP_STATUS); anything the graded run left running is still running" >&2
fi
}
mkdir -p /logs/verifier 2>/dev/null || true
set -m
PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} --override-ini=addopts= -p no:randomly -p no:cacheprovider --junitxml=/logs/verifier/base.xml" \
  HOME="${VERIFIER_TEST_HOME:-${HOME:-/root}}" PYTHONNOUSERSITE=1 ${VERIFIER_DROP:-} bash /app/test.sh base >/logs/verifier/pytest-base.log 2>&1 </dev/null &
verifier_run_pgid=$!
wait "$verifier_run_pgid"
set +m
verifier_reap
cat /logs/verifier/pytest-base.log 2>/dev/null || true
set -m
VERIFIER_CANARY_TOKEN=$(od -An -tx1 -N8 /dev/urandom 2>/dev/null | tr -dc 'a-f0-9')
[ -n "$VERIFIER_CANARY_TOKEN" ] || VERIFIER_CANARY_TOKEN="${RANDOM}${RANDOM}$$"
VERIFIER_CANARY_NAME="test_report_written_by_this_run_$VERIFIER_CANARY_TOKEN"
VERIFIER_CANARY_FILE="/app/tests/report_canary_$VERIFIER_CANARY_TOKEN.py"
if cat > "$VERIFIER_CANARY_FILE" <<VERIFIER_CANARY_EOF
def $VERIFIER_CANARY_NAME():
    assert False, "report canary"
VERIFIER_CANARY_EOF
then
  echo "[verifier] report canary planted at $VERIFIER_CANARY_FILE"
else
  echo "[verifier] report canary could not be planted; grading without it" >&2
  VERIFIER_CANARY_NAME=""
  VERIFIER_CANARY_FILE=""
fi
PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} --override-ini=addopts= -p no:randomly -p no:cacheprovider --junitxml=/logs/verifier/new.xml $VERIFIER_CANARY_FILE" \
  HOME="${VERIFIER_TEST_HOME:-${HOME:-/root}}" PYTHONNOUSERSITE=1 ${VERIFIER_DROP:-} bash /app/test.sh new >/logs/verifier/pytest-new.log 2>&1 </dev/null &
verifier_run_pgid=$!
wait "$verifier_run_pgid"
set +m
verifier_reap
cat /logs/verifier/pytest-new.log 2>/dev/null || true
if [ -n "${VERIFIER_DROP:-}" ]; then
  chown -Rh 0:0 /logs/verifier 2>/dev/null || true
  chmod -R go-w /logs/verifier 2>/dev/null || true
  echo "[verifier] /logs/verifier is root-owned and root-writable again; the graded account cannot rewrite a report from here"
fi
VERIFIER_AUDIT_STATUS=0
"${VERIFIER_PY:-python3}" - <<'VERIFIER_AUDIT_PY' || VERIFIER_AUDIT_STATUS=$?
import json
import os
import pathlib
import re
import xml.etree.ElementTree as ET

AUDIT = json.loads('''
{
 "checks": [
  {
   "evidence": "/logs/verifier/pytest-base.log",
   "kind": "pytest-terminal",
   "report": "/logs/verifier/base.xml"
  },
  {
   "evidence": "/logs/verifier/pytest-new.log",
   "kind": "pytest-terminal",
   "report": "/logs/verifier/new.xml"
  }
 ],
 "reports": [
  "/logs/verifier/base.xml",
  "/logs/verifier/new.xml"
 ],
 "runner": "pytest"
}
''')

VERIFIER_DIR = pathlib.Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
DEFAULT_DIR = "/logs/verifier/"


def resolve(path):
    if path.startswith(DEFAULT_DIR):
        return VERIFIER_DIR / path[len(DEFAULT_DIR):]
    return pathlib.Path(path)


def go_executed(path):
    started = set()
    finished = set()
    with open(str(path), errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            test = str(event.get("Test") or "").strip()
            if not test:
                continue
            key = (str(event.get("Package") or ""), test)
            action = str(event.get("Action") or "")
            if action == "run":
                started.add(key)
            elif action in ("pass", "fail", "skip"):
                finished.add(key)
    return started & finished


def ctrf_rows(path):
    doc = json.loads(pathlib.Path(str(path)).read_text())
    rows = (doc.get("results") or {}).get("tests") or []
    if not isinstance(rows, list):
        raise ValueError("results.tests is not a list")
    out = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        suite = row.get("suite")
        if isinstance(suite, list):
            suite = "/".join(str(x) for x in suite)
        out.add((str(suite or ""), name))
    return out


def junit_counts(path):
    root = ET.parse(str(path)).getroot()
    passed = failed = 0
    for case in root.iter("testcase"):
        status = "passed"
        for child in case:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag in ("failure", "error"):
                status = "failed"
                break
            if tag == "skipped":
                status = "skipped"
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
    return passed, failed


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SECTION_LINE = re.compile(r"^(?:=+|-+|_+) (.*?) (?:=+|-+|_+)$")
SUMMARY_LINE = re.compile(r"^=+ (.*?) =+$")
BARE_SUMMARY = re.compile(
    r"^(?:no tests ran|\d+ [a-z]+(?:, \d+ [a-z]+)*)"
    r" in \d+(?:\.\d+)? ?(?:s|seconds)(?: \(\d+:\d\d:\d\d\))?$")
SUMMARY_COUNT = re.compile(
    r"(\d+) (passed|failed|errors?|xpassed|xfailed|skipped)\b")


def summary_counts(body):
    pairs = SUMMARY_COUNT.findall(body)
    if not pairs:
        return {} if "no tests ran" in body else None
    counts = {}
    for number, word in pairs:
        key = "error" if word.startswith("error") else word
        counts[key] = counts.get(key, 0) + int(number)
    return counts


def pytest_summary(path):
    found = []
    captured = False
    with open(str(path), errors="replace") as handle:
        for raw in handle:
            line = ANSI.sub("", raw.rstrip())
            section = SECTION_LINE.match(line)
            if section:
                padded = SUMMARY_LINE.match(line)
                body = padded.group(1) if padded else None
            else:
                body = line if BARE_SUMMARY.match(line) else None
            counts = summary_counts(body) if body is not None else None
            if counts is None:
                if section:
                    captured = section.group(1).startswith("Captured ")
                continue
            if captured:
                continue
            key = (counts.get("passed", 0) + counts.get("xpassed", 0),
                   counts.get("failed", 0) + counts.get("error", 0))
            if key not in [seen for seen, _ in found]:
                found.append((key, counts))
    return found


def spell(counts):
    return ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items())) \
        or "nothing"


def name_of(row):
    return (row[0] + "." + row[1]) if row[0] else row[1]


reasons = []
for check in AUDIT["checks"]:
    report = resolve(check["report"])
    if not report.exists():
        continue
    evidence = resolve(check["evidence"])
    if not evidence.exists():
        reasons.append(
            "%s exists and %s does not, so nothing this run wrote says any "
            "test was executed to produce it" % (report, evidence))
        continue
    try:
        if check["kind"] == "gotest-events":
            claimed = ctrf_rows(report)
            executed = go_executed(evidence)
            unbacked = sorted(claimed - executed)
            if unbacked:
                reasons.append(
                    "%s claims %d test result(s) and %s recorded %d test(s) "
                    "both started and finished; %d claimed result(s) have no "
                    "matched run/pass event pair behind them, first: %s"
                    % (report, len(claimed), evidence, len(executed),
                       len(unbacked),
                       ", ".join(name_of(r) for r in unbacked[:5])))
        else:
            passed, failed = junit_counts(report)
            sessions = pytest_summary(evidence)
            if len(sessions) > 1:
                if passed:
                    reasons.append(
                        "%s reports %d passing test(s) and %s carries %d "
                        "disagreeing pytest terminal summaries (%s); one "
                        "pytest session prints one, so at least one of them "
                        "was written by something other than the terminal "
                        "reporter and no count in this log is the run's own"
                        % (report, passed, evidence, len(sessions),
                           " / ".join(spell(c) for _, c in sessions)))
            elif not sessions:
                if passed:
                    reasons.append(
                        "%s reports %d passing test(s) and %s carries no "
                        "pytest summary line at all, so pytest's own count of "
                        "this run cannot be read" % (report, passed, evidence))
            else:
                (allowed, worst_failed), counts = sessions[0]
                if passed > allowed:
                    reasons.append(
                        "%s reports %d passing test(s) and pytest's own "
                        "summary in %s counted %d (%s)"
                        % (report, passed, evidence, allowed, spell(counts)))
                elif failed < worst_failed:
                    reasons.append(
                        "%s reports %d failed test(s) and pytest's own "
                        "summary in %s counted %d failure(s) or error(s) (%s)"
                        % (report, failed, evidence, worst_failed,
                           spell(counts)))
    except Exception as exc:
        reasons.append(
            "%s could not be audited against %s (%r), so nothing says its "
            "results came out of a runner" % (report, evidence, exc))

record = {"runner": AUDIT["runner"], "reasons": reasons, "quarantined": []}
if reasons:
    for path in AUDIT["reports"]:
        source = resolve(path)
        if not source.exists():
            continue
        target = source.with_name(source.name + ".unverified")
        try:
            if target.exists():
                target.unlink()
            source.rename(target)
        except OSError:
            try:
                target.write_bytes(source.read_bytes())
                source.write_bytes(b"")
            except OSError as exc:
                record.setdefault("quarantine_failed", []).append(
                    "%s: %r" % (source, exc))
                continue
        record["quarantined"].append(str(target))

reports_dir = VERIFIER_DIR / "reports"
try:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "report_audit.json").write_text(
        json.dumps(record, indent=1))
except OSError:
    pass

for reason in reasons:
    print("[verifier] REPORT AUDIT: " + reason)
if reasons:
    print("[verifier] report audit FAILED; the graded report(s) were moved "
          "aside and this run is graded on no report at all")
else:
    print("[verifier] report audit: every reported result is backed by the "
          "run's own evidence")
VERIFIER_AUDIT_PY
if [ "$VERIFIER_AUDIT_STATUS" != "0" ]; then
  echo "[verifier] report audit could not run (exit $VERIFIER_AUDIT_STATUS); grading the reports as written" >&2
fi

echo "===== grade ====="
VERIFIER_SEAL_TOKEN=$(od -An -tx1 -N8 /dev/urandom 2>/dev/null | tr -dc 'a-f0-9')
[ -n "$VERIFIER_SEAL_TOKEN" ] || VERIFIER_SEAL_TOKEN="${RANDOM}${RANDOM}$$"
VERIFIER_SEAL_DIR="/tmp/sealed_reports_$VERIFIER_SEAL_TOKEN"
if mkdir -m 700 -p "$VERIFIER_SEAL_DIR"; then
  if [ -e "/logs/verifier/base.xml" ] && ! cp -p "/logs/verifier/base.xml" "$VERIFIER_SEAL_DIR/base.xml"; then VERIFIER_SEAL_DIR=""; fi
  if [ -e "/logs/verifier/new.xml" ] && ! cp -p "/logs/verifier/new.xml" "$VERIFIER_SEAL_DIR/new.xml"; then VERIFIER_SEAL_DIR=""; fi
else
  VERIFIER_SEAL_DIR=""
fi
if [ -z "$VERIFIER_SEAL_DIR" ]; then
  echo "[verifier] reports could not be sealed; grading the originals" >&2
else
  echo "[verifier] reports sealed into $VERIFIER_SEAL_DIR"
fi
"$VERIFIER_PY" /tests/grader.py grade --canary "$VERIFIER_CANARY_NAME" --seal "$VERIFIER_SEAL_DIR"
