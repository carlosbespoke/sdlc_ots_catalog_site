#!/bin/bash
set -uo pipefail

VERIFIER_SYS_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
VERIFIER_BIN=$(mktemp -d /tmp/verifier-bin.XXXXXXXX 2>/dev/null) || VERIFIER_BIN=
if [ -n "$VERIFIER_BIN" ]; then
  chmod 755 "$VERIFIER_BIN" 2>/dev/null
  for verifier_tool in git rm mkdir bash sh junit-to-ctrf id chown chmod setpriv runuser env grep cat od tr mktemp; do
    verifier_found=$(PATH=$VERIFIER_SYS_PATH command -v "$verifier_tool" 2>/dev/null) || continue
    ln -sf "$verifier_found" "$VERIFIER_BIN/$verifier_tool" 2>/dev/null
  done
  export PATH="$VERIFIER_BIN:$PATH"
fi
VERIFIER_PY=$(PATH=$VERIFIER_SYS_PATH command -v python3 2>/dev/null) || VERIFIER_PY=python3
echo "[verifier] tools pinned to $VERIFIER_BIN, grader interpreter $VERIFIER_PY"

VERIFIER_GO=$(PATH=/usr/local/go/bin:$VERIFIER_SYS_PATH command -v go 2>/dev/null) || VERIFIER_GO=""
VERIFIER_GOPATH=$(GOENV=off GOFLAGS= "${VERIFIER_GO:-false}" env GOPATH 2>/dev/null) || VERIFIER_GOPATH=""
VERIFIER_GOMODCACHE=$(GOENV=off GOFLAGS= "${VERIFIER_GO:-false}" env GOMODCACHE 2>/dev/null) || VERIFIER_GOMODCACHE=""
VERIFIER_CTRF="${VERIFIER_GOPATH:-/go}/bin/go-ctrf-json-reporter"

trap 'if [ ! -f /logs/verifier/reward.json ] && [ ! -f /logs/verifier/reward.txt ]; then mkdir -p /logs/verifier; echo -1 > /logs/verifier/reward.txt; fi' EXIT
cd /app || exit 6

VERIFIER_TEST_USER="${VERIFIER_TEST_USER:-agent}"
VERIFIER_DROP=""
if [ "$(id -u)" = "0" ] && id -u "$VERIFIER_TEST_USER" >/dev/null 2>&1; then
  verifier_uid=$(id -u "$VERIFIER_TEST_USER")
  verifier_gid=$(id -g "$VERIFIER_TEST_USER")
  if setpriv --reuid="$verifier_uid" --regid="$verifier_gid" --init-groups true >/dev/null 2>&1; then
    VERIFIER_DROP="setpriv --reuid=$verifier_uid --regid=$verifier_gid --init-groups --"
  elif runuser -p -u "$VERIFIER_TEST_USER" -- true >/dev/null 2>&1; then
    VERIFIER_DROP="runuser -p -u $VERIFIER_TEST_USER --"
  fi
fi
verifier_reap() {
VERIFIER_REAP_STATUS=0
VERIFIER_REAP_UID="${VERIFIER_DROP:+${verifier_uid:-}}" VERIFIER_REAP_PGID="${verifier_run_pgid:-}" "${VERIFIER_PY:-python3}" -I -u -B - <<'VERIFIER_REAP_PY' || VERIFIER_REAP_STATUS=$?
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

# Nothing the solve session left running survives into grading: reap the
# graded account before the grader touches /app or /logs/verifier.
verifier_run_pgid=""
verifier_reap

# /logs/verifier is root-only for the whole run. The graded account never
# writes into it: every raw log there is a file the root shell opened and
# handed to the runner as stdout or stderr, and every report is built by root.
mkdir -p /logs/verifier
chown -h 0:0 /logs/verifier && chmod 0755 /logs/verifier
if [ "$(stat -c '%u %a' /logs/verifier 2>/dev/null)" != "0 755" ]; then
  echo "[verifier] ERROR: /logs/verifier cannot be made root-only; refusing to grade" >&2
  exit 6
fi
rm -rf /logs/verifier/reports
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/repo-suite.jsonl /logs/verifier/repo-suite.err /logs/verifier/go-test.jsonl /logs/verifier/go-test.err /logs/verifier/base-ctrf.json /logs/verifier/new-ctrf.json
chmod 0700 /tests 2>/dev/null || true

"$VERIFIER_PY" -I -u -B /tests/grader.py prepare
verifier_prepare_rc=$?
if [ "$verifier_prepare_rc" = "3" ]; then
  echo "[verifier] the grader graded this run during prepare"
  exit 0
fi
[ "$verifier_prepare_rc" = "0" ] || exit "$verifier_prepare_rc"
# Prepare did not grade, so a reward file here now was not written by it.
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json

if [ -z "$VERIFIER_GO" ] || [ ! -x "$VERIFIER_CTRF" ] || [ "$(stat -c '%u' "$VERIFIER_CTRF")" != "0" ]; then
  echo "[verifier] ERROR: no root-owned go toolchain or report writer" >&2
  exit 6
fi
VERIFIER_STATE=$(mktemp -d /tmp/verifier-state.XXXXXXXX) || exit 6
chmod 0700 "$VERIFIER_STATE"
VERIFIER_GO_HOME=$(mktemp -d /tmp/verifier-home.XXXXXXXX) || exit 6
chmod 0755 "$VERIFIER_GO_HOME"
VERIFIER_CANARY_TOKEN=$(od -An -tx1 -N8 /dev/urandom 2>/dev/null | tr -dc 'a-f0-9')
[ -n "$VERIFIER_CANARY_TOKEN" ] || VERIFIER_CANARY_TOKEN="${RANDOM}${RANDOM}$$"

# Out-of-band witness channel. The root frame opens fd 9 onto a file in this
# root-only directory for each leg; the grader-planted canaries write a witness
# line (this leg's nonce + their package and name) to fd 9 when their bodies
# actually run. The graded account can write through the inherited fd but can
# neither read nor replace anything here, and does not learn a leg's nonce from
# this directory. The grader accepts a canary as evidence only when its witness
# carries the leg's nonce, so results produced without executing the planted
# tests leave no witness and are graded as forged.
VERIFIER_WITNESS_DIR=$(mktemp -d /tmp/verifier-witness.XXXXXXXX) || exit 6
chown -h 0:0 "$VERIFIER_WITNESS_DIR" && chmod 0700 "$VERIFIER_WITNESS_DIR"
if [ "$(stat -c '%u %a' "$VERIFIER_WITNESS_DIR" 2>/dev/null)" != "0 700" ]; then
  echo "[verifier] ERROR: witness dir cannot be made root-only; refusing to grade" >&2
  exit 6
fi
export VERIFIER_WITNESS_FD=9
verifier_witness_setup() {
  # $1 = leg name. Fresh per-leg nonce, root-only nonce file, empty tsv.
  VERIFIER_WITNESS_NONCE=$(od -An -tx1 -N16 /dev/urandom 2>/dev/null | tr -dc 'a-f0-9')
  [ -n "$VERIFIER_WITNESS_NONCE" ] || VERIFIER_WITNESS_NONCE="${RANDOM}${RANDOM}${RANDOM}$$"
  export VERIFIER_WITNESS_NONCE
  printf '%s' "$VERIFIER_WITNESS_NONCE" > "$VERIFIER_WITNESS_DIR/$1.nonce"
  : > "$VERIFIER_WITNESS_DIR/$1.tsv"
  chmod 0600 "$VERIFIER_WITNESS_DIR/$1.nonce" "$VERIFIER_WITNESS_DIR/$1.tsv"
}

# Each graded leg gets a fresh build cache, a root-owned HOME and an
# environment that no go env file, GOFLAGS, workspace or toolchain switch of
# the solver's can reach.
verifier_leg() {
  local leg_cache
  leg_cache=$(mktemp -d /tmp/verifier-gocache.XXXXXXXX) || return 1
  [ -n "${VERIFIER_DROP:-}" ] && chown "$verifier_uid:$verifier_gid" "$leg_cache"
  chmod 0700 "$leg_cache"
  env -u XDG_CONFIG_HOME -u GOROOT_FINAL -u GOEXPERIMENT -u GODEBUG \
    GOENV=off GOFLAGS= GOWORK=off GOTOOLCHAIN=local GOPROXY=off \
    GOPATH="$VERIFIER_GOPATH" GOMODCACHE="$VERIFIER_GOMODCACHE" \
    GOCACHE="$leg_cache" HOME="$VERIFIER_GO_HOME" PYTHONNOUSERSITE=1 \
    PATH="/usr/local/go/bin:$VERIFIER_SYS_PATH" \
    ${VERIFIER_DROP:-} "$VERIFIER_GO" test -json -vet=off -count=1 -mod=readonly "$@"
}

if [ -n "$VERIFIER_DROP" ]; then
  echo "[verifier] graded run drops to $VERIFIER_TEST_USER (uid $verifier_uid, HOME=$VERIFIER_GO_HOME, GOENV=off, GOFLAGS empty); the frame stays root"
else
  echo "[verifier] graded run stays root: no unprivileged account to drop to" >&2
fi

echo "[verifier] base leg: repository tests named in test.patch, under go test"
"$VERIFIER_PY" -I -u -B /tests/grader.py plant-canaries --leg base --token "$VERIFIER_CANARY_TOKEN" --state "$VERIFIER_STATE" || exit 7
VERIFIER_BASE_RUN=$(cat "$VERIFIER_STATE/base-run.txt") || exit 7
verifier_witness_setup base
set -m
verifier_leg -run "$VERIFIER_BASE_RUN" ./... </dev/null >/logs/verifier/repo-suite.jsonl 2>/logs/verifier/repo-suite.err 9>>"$VERIFIER_WITNESS_DIR/base.tsv" &
verifier_run_pgid=$!
wait "$verifier_run_pgid"
set +m
verifier_reap
grep -v '"Action":"build-' /logs/verifier/repo-suite.jsonl | "$VERIFIER_CTRF" -quiet -output /logs/verifier/base-ctrf.json
cat /logs/verifier/repo-suite.err >&2

echo "[verifier] new leg: ./acceptance/... under go test"
"$VERIFIER_PY" -I -u -B /tests/grader.py plant-canaries --leg new --token "$VERIFIER_CANARY_TOKEN" --state "$VERIFIER_STATE" || exit 7
VERIFIER_CANARY_NAME=$(cat "$VERIFIER_STATE/standalone.txt") || exit 7
verifier_witness_setup new
set -m
verifier_leg -timeout 600s ./acceptance/... </dev/null >/logs/verifier/go-test.jsonl 2>/logs/verifier/go-test.err 9>>"$VERIFIER_WITNESS_DIR/new.tsv" &
verifier_run_pgid=$!
wait "$verifier_run_pgid"
set +m
verifier_reap
grep -v '"Action":"build-' /logs/verifier/go-test.jsonl | "$VERIFIER_CTRF" -quiet -output /logs/verifier/new-ctrf.json
if [ ! -f /logs/verifier/new-ctrf.json ] \
   && ( grep -q '"Action":"build-fail"' /logs/verifier/go-test.jsonl \
        || grep -qE '\.go:[0-9]+:[0-9]+: ' /logs/verifier/go-test.err ); then
  : > /logs/verifier/new-ctrf.json
fi
grep '"Action":"build-' /logs/verifier/go-test.jsonl | head -100 >&2 || true
if [ -s /logs/verifier/go-test.err ]; then
  cat /logs/verifier/go-test.err >&2
fi
chown -Rh 0:0 /logs/verifier 2>/dev/null || true
chmod -R go-w /logs/verifier 2>/dev/null || true

VERIFIER_AUDIT_STATUS=0
VERIFIER_CANARIES="$VERIFIER_STATE/canaries.tsv" "${VERIFIER_PY:-python3}" -I -u -B - <<'VERIFIER_AUDIT_PY' || VERIFIER_AUDIT_STATUS=$?
import json
import os
import pathlib
import re
import xml.etree.ElementTree as ET

AUDIT = json.loads('''
{
 "checks": [
  {
   "evidence": [
    "/logs/verifier/repo-suite.jsonl"
   ],
   "kind": "gotest-events",
   "report": "/logs/verifier/base-ctrf.json",
   "strict": true
  },
  {
   "evidence": [
    "/logs/verifier/go-test.jsonl"
   ],
   "kind": "gotest-events",
   "report": "/logs/verifier/new-ctrf.json",
   "strict": true
  }
 ],
 "reports": [
  "/logs/verifier/base-ctrf.json",
  "/logs/verifier/new-ctrf.json"
 ],
 "runner": "gotest"
}
''')

VERIFIER_DIR = pathlib.Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
DEFAULT_DIR = "/logs/verifier/"


def resolve(path):
    if path.startswith(DEFAULT_DIR):
        return VERIFIER_DIR / path[len(DEFAULT_DIR):]
    return pathlib.Path(path)


GO_STATUS = {"pass": "passed", "fail": "failed", "skip": "skipped"}


def go_events(path):
    started = set()
    finished = {}
    packages = {}
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
            package = str(event.get("Package") or "")
            action = str(event.get("Action") or "")
            test = str(event.get("Test") or "").strip()
            if not test:
                if action in GO_STATUS:
                    packages.setdefault(package, set()).add(
                        "unbuilt" if event.get("FailedBuild") else GO_STATUS[action])
                continue
            key = (package, test)
            if action == "run":
                started.add(key)
            elif action in GO_STATUS:
                finished.setdefault(key, set()).add(GO_STATUS[action])
    return started, finished, packages


def ctrf_rows(path):
    doc = json.loads(pathlib.Path(str(path)).read_text())
    rows = (doc.get("results") or {}).get("tests") or []
    if not isinstance(rows, list):
        raise ValueError("results.tests is not a list")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        suite = row.get("suite")
        if isinstance(suite, list):
            suite = "/".join(str(x) for x in suite)
        status = str(row.get("status") or "").strip().lower()
        out.setdefault((str(suite or ""), name), set()).add(status)
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
seen_events = []
audited = []
nothing_to_audit = []
for check in AUDIT["checks"]:
    report = resolve(check["report"])
    if not report.exists():
        nothing_to_audit.append(
            "%s was not written by this run" % report)
        continue
    evidence = None
    for candidate in check["evidence"]:
        found = resolve(candidate)
        if found.exists():
            evidence = found
            break
    if evidence is None:
        spelled = " or ".join(str(resolve(c)) for c in check["evidence"])
        if not check.get("strict", True):
            nothing_to_audit.append(
                "%s has no evidence log beside it (looked for %s)"
                % (report, spelled))
            continue
        reasons.append(
            "%s exists and %s does not, so nothing this run wrote says any "
            "test was executed to produce it" % (report, spelled))
        continue
    audited.append(str(report))
    try:
        if check["kind"] == "gotest-events":
            claimed = ctrf_rows(report)
            started, finished, packages = go_events(evidence)
            seen_events.append((started, finished, packages))
            unbacked, disagree = [], []
            for key in sorted(claimed):
                ends = finished.get(key, set())
                if key not in started or not ends:
                    unbacked.append(key)
                elif len(ends) > 1 or claimed[key] != ends:
                    disagree.append((key, sorted(claimed[key]), sorted(ends)))
            if unbacked:
                reasons.append(
                    "%s claims %d test result(s) and %s recorded %d test(s) "
                    "both started and finished; %d claimed result(s) have no "
                    "matched run/terminal event pair behind them, first: %s"
                    % (report, len(claimed), evidence, len(finished),
                       len(unbacked),
                       ", ".join(name_of(r) for r in unbacked[:5])))
            if disagree:
                reasons.append(
                    "%s reports a status for %d test(s) that differs from the "
                    "terminal event %s recorded for them (or the log carries "
                    "more than one outcome for one test), first: %s"
                    % (report, len(disagree), evidence,
                       ", ".join("%s claimed %s, events %s"
                                 % (name_of(k), "/".join(c), "/".join(e))
                                 for k, c, e in disagree[:3])))
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

canaries = []
try:
    with open(os.environ.get("VERIFIER_CANARIES", "/nonexistent")) as handle:
        for line in handle:
            package, _, test = line.rstrip("\n").partition("\t")
            if package and test:
                canaries.append((package, test))
except OSError:
    reasons.append("the in-package canary list of this run cannot be read")
broken, unbuilt = [], []
for package, test in canaries:
    ends, package_ends, ran, never_built = set(), set(), False, False
    for started, finished, packages in seen_events:
        never_built = never_built or "unbuilt" in packages.get(package, set())
        if (package, test) in started:
            ran = True
            ends |= finished.get((package, test), set())
            package_ends |= packages.get(package, set())
    if not ran and never_built:
        # The package failed to build, so none of its tests ran or passed.
        unbuilt.append("%s\t%s\n" % (package, test))
        continue
    if not ran or ends != {"failed"} or package_ends != {"failed"}:
        broken.append("%s.%s (run %s, outcome %s, package %s)"
                      % (package, test, ran, "/".join(sorted(ends)) or "none",
                         "/".join(sorted(package_ends)) or "none"))
if broken:
    reasons.append(
        "%d of %d in-package canaries, each failing by construction inside a "
        "package that holds graded tests, were not recorded as run and failed "
        "in a failed package, first: %s"
        % (len(broken), len(canaries), "; ".join(broken[:3])))
elif canaries:
    print("[verifier] report audit: %d in-package canaries ran and failed; "
          "%d sit in a package that did not build, so none of its tests ran"
          % (len(canaries) - len(unbuilt), len(unbuilt)))
try:
    with open(os.environ.get("VERIFIER_CANARIES", "/nonexistent")
              + ".unbuilt", "w") as handle:
        handle.write("".join(unbuilt))
except OSError:
    pass

record = {"runner": AUDIT["runner"], "reasons": reasons, "quarantined": [],
          "audited": audited, "nothing_to_audit": nothing_to_audit}
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
for note in nothing_to_audit:
    print("[verifier] report audit: %s, so there is nothing to audit for it"
          % note)
if reasons:
    print("[verifier] report audit FAILED; the graded report(s) were moved "
          "aside and this run is graded on no report at all")
elif audited:
    print("[verifier] report audit: every reported result is backed by the "
          "run's own evidence (%d report(s) checked)" % len(audited))
else:
    print("[verifier] report audit: no report was written by this run, so "
          "nothing was checked - this is not a pass")
VERIFIER_AUDIT_PY
if [ "$VERIFIER_AUDIT_STATUS" != "0" ]; then
  echo "[verifier] report audit could not run (exit $VERIFIER_AUDIT_STATUS); grading on no report" >&2
  rm -f /logs/verifier/base-ctrf.json /logs/verifier/new-ctrf.json
fi

echo "===== grade ====="
VERIFIER_SEAL_TOKEN=$(od -An -tx1 -N8 /dev/urandom 2>/dev/null | tr -dc 'a-f0-9')
[ -n "$VERIFIER_SEAL_TOKEN" ] || VERIFIER_SEAL_TOKEN="${RANDOM}${RANDOM}$$"
VERIFIER_SEAL_DIR="/tmp/sealed_reports_$VERIFIER_SEAL_TOKEN"
if mkdir -m 700 -p "$VERIFIER_SEAL_DIR"; then
  if [ -e "/logs/verifier/base-ctrf.json" ] && ! cp -p "/logs/verifier/base-ctrf.json" "$VERIFIER_SEAL_DIR/base-ctrf.json"; then VERIFIER_SEAL_DIR=""; fi
  if [ -e "/logs/verifier/new-ctrf.json" ] && ! cp -p "/logs/verifier/new-ctrf.json" "$VERIFIER_SEAL_DIR/new-ctrf.json"; then VERIFIER_SEAL_DIR=""; fi
else
  VERIFIER_SEAL_DIR=""
fi
if [ -z "$VERIFIER_SEAL_DIR" ]; then
  echo "[verifier] reports could not be sealed; grading the originals" >&2
else
  echo "[verifier] reports sealed into $VERIFIER_SEAL_DIR"
fi
"$VERIFIER_PY" -I -u -B /tests/grader.py grade --canary "$VERIFIER_CANARY_NAME" --canaries "$VERIFIER_STATE/canaries.tsv" --witness "$VERIFIER_WITNESS_DIR" --seal "$VERIFIER_SEAL_DIR"
