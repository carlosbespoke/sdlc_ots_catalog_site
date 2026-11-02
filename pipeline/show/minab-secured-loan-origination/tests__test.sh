#!/bin/bash
# Verifier entry point (runs as root). Grades the submission in /logs/artifacts/model.patch
# against the hidden loan-service tests; writes /logs/verifier/reward.txt (1.0 or 0.0).
trap 'if [ ! -s /logs/verifier/reward.txt ]; then mkdir -p /logs/verifier; echo -1 > /logs/verifier/reward.txt; fi' EXIT
set -uo pipefail

export PATH=/opt/java/openjdk/bin:/usr/share/maven/bin:/usr/sbin:/usr/bin:/sbin:/bin
export JAVA_HOME=/opt/java/openjdk MAVEN_HOME=/usr/share/maven LANG=C.UTF-8
unset MAVEN_ARGS MAVEN_CONFIG MAVEN_DEBUG_OPTS JAVA_TOOL_OPTIONS _JAVA_OPTIONS JDK_JAVA_OPTIONS CLASSPATH
export MAVEN_OPTS="-Xmx1536m" MAVEN_SKIP_RC=1
PY=/usr/bin/python3

for d in /logs/verifier /logs/artifacts; do
  if [ -L "$d" ]; then echo "[verifier] $d is a symlink; refusing to grade" >&2; exit 5; fi
done
mkdir -p /logs/verifier /logs/artifacts
chown root:root /logs/verifier && chmod 755 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/metrics.json
if [ ! -d /app ]; then echo "[verifier] /app is missing" >&2; exit 6; fi
chown -R root:root /tests 2>/dev/null; chmod -R go-rwx /tests 2>/dev/null

# Nothing from the session keeps running while grading.
pkill -KILL -u agent 2>/dev/null; sleep 1

STATE=$(mktemp -d /tmp/verifier-state.XXXXXXXX) || exit 6
chmod 700 "$STATE"

"$PY" -I -B /tests/grader.py prepare "$STATE" || exit $?
[ -s /logs/verifier/reward.txt ] && exit 0

# The graded tree is root's and read-only to everyone else: the test JVM runs as
# `agent` and can neither edit the build nor write the reports.
chown -R root:root /app && chmod -R go-w /app

CLASSES=$("$PY" -I -B -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["test_classes"]))' "$STATE/state.json")
MAVEN_HOME_DIR="$STATE/maven-home"; mkdir -m 700 "$MAVEN_HOME_DIR"
echo "[verifier] running mvn -o test for loan-service (tests: $CLASSES)"
cd /app
HOME="$MAVEN_HOME_DIR" timeout -k 30 2400 mvn -B -ntp -o \
  -s /opt/verifier/settings.xml -gs /usr/share/maven/conf/settings.xml \
  -Dmaven.repo.local=/opt/m2/repository -Dmaven.compiler.proc=none \
  -Dtest="$CLASSES" -Dsurefire.failIfNoSpecifiedTests=false \
  -pl loan/loan-service -am test > /logs/verifier/mvn-test.log 2>&1 < /dev/null
MVN_STATUS=$?
echo "[verifier] mvn exited $MVN_STATUS"

# Whatever the test JVM left running is killed before the reports are read.
pkill -KILL -u agent 2>/dev/null; sleep 1

# Seal: copy only root-owned regular report files into a root-only directory.
mkdir -m 700 "$STATE/sealed"
REPORTS=/app/loan/loan-service/target/verifier-reports
if [ -d "$REPORTS" ] && [ ! -L "$REPORTS" ] && [ "$(stat -c %u "$REPORTS")" = "0" ]; then
  for f in "$REPORTS"/TEST-*.xml; do
    [ -f "$f" ] && [ ! -L "$f" ] && [ "$(stat -c %u "$f")" = "0" ] && cp "$f" "$STATE/sealed/"
  done
fi
echo "[verifier] sealed $(ls "$STATE/sealed" | wc -l) report file(s)"
grep -E "Tests run:|ERROR\]|BUILD" /logs/verifier/mvn-test.log | grep -v "^\[INFO\] Tests run: .*, Time elapsed" | head -60

"$PY" -I -B /tests/grader.py grade "$STATE"
cat /logs/verifier/reward.txt
