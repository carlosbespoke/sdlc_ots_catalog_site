#!/usr/bin/env python3
"""Verifier for the secured loan origination task (OpenFinova core banking, loan-service).

Subcommands, all run as root by tests/test.sh:

  prepare <state-dir>
      Rebuild the graded tree in /app from the verifier's own root-owned copy of the
      base repository: reset to base, apply /logs/artifacts/model.patch, put every build
      and test file back to base (pom.xml files, .mvn/, mvnw, every src/test tree, JUnit
      and annotation-processor service registrations), add the hidden tests from
      tests/test.patch, plant a report canary, and give loan-service a verifier-owned
      Surefire configuration and the H2 test dependency the hidden suite runs on. The
      test JVM that runs submission code is started as the unprivileged `agent` account
      through a launcher kept in <state-dir>; Maven itself
      (and so the Surefire XML reports) stays root.

  grade <state-dir>
      Read the Surefire reports sealed into <state-dir>/sealed and write the reward.
      Reward is 1.0 only when the canary is reported failed (the reports come from this
      run), every fail-to-pass and pass-to-pass test in tests/config.json is reported
      passed, and the fail-to-pass list is not empty. Anything else is 0.0.
"""

import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

APP = pathlib.Path("/app")
TESTS = pathlib.Path("/tests")
LOGS = pathlib.Path("/logs/verifier")
ARTIFACTS = pathlib.Path("/logs/artifacts")
VERIFIER_GIT = "/opt/verifier/git"
MODULE = "loan/loan-service"
SUITE_PACKAGE = "com.openfinova.banking.loan.origination"
SUITE_DIR = MODULE + "/src/test/java/" + SUITE_PACKAGE.replace(".", "/")
REPORTS_DIR = MODULE + "/target/verifier-reports"
AGENT_USER = "agent"
# Base tests written against the entry point the task retires (createLoanAccount(UUID, String) and
# LoanAccountCreateRequest). A correct submission removes that API, so these base copies cannot compile against it;
# the behaviour they covered is graded by the hidden suite instead.
RETIRED_PATH_TESTS = (
    MODULE + "/src/test/java/com/openfinova/banking/loan/service/LoanAccountServiceAccountOpeningTest.java",
    MODULE + "/src/test/java/com/openfinova/banking/loan/controller/LoanAccountControllerTest.java",
)


def log(msg):
    print("[grader] " + msg, flush=True)


def load_config():
    with open(TESTS / "config.json") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------- git

def git(*args, check=False, **kw):
    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "GIT_DIR": VERIFIER_GIT,
        "GIT_WORK_TREE": str(APP),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
    }
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
           "-c", "safe.directory=*", *args]
    result = subprocess.run(cmd, cwd=APP, env=env, **kw)
    if check and result.returncode != 0:
        raise SystemExit("git %s failed with exit %d" % (" ".join(args), result.returncode))
    return result


def git_lines(*args):
    out = git(*args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    return [line for line in out.decode("utf-8", "surrogateescape").split("\0") if line]


# --------------------------------------------------------------------------- reward

def write_reward(value, metrics):
    LOGS.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json", "metrics.json"):
        target = LOGS / name
        if target.is_symlink() or target.exists():
            target.unlink()
    (LOGS / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True) + "\n")
    (LOGS / "reward.json").write_text(json.dumps({"reward": value}) + "\n")
    (LOGS / "reward.txt").write_text("%s\n" % value)
    log("reward %s" % value)


# --------------------------------------------------------------------------- prepare

def is_protected(rel):
    """Build and test files the submission may not change: they are reset to base."""
    name = rel.rsplit("/", 1)[-1]
    if name == "pom.xml" or rel in ("mvnw", "mvnw.cmd") or rel.startswith(".mvn/"):
        return True
    if rel.startswith("src/test/") or "/src/test/" in rel:
        return True
    if name == "junit-platform.properties":
        return True
    if "META-INF/services/" in rel and (name.startswith("org.junit")
                                         or name.startswith("javax.annotation.processing")
                                         or name.startswith("org.apache.maven")):
        return True
    return False


def restore_protected(base):
    changed = git_lines("diff", "-z", "--name-only", base)
    added = git_lines("ls-files", "-z", "--others")
    restored = []
    for rel in sorted(set(changed)):
        if not is_protected(rel):
            continue
        rc = git("checkout", "-q", base, "--", rel, stderr=subprocess.DEVNULL).returncode
        if rc != 0:
            path = APP / rel
            if path.is_symlink() or path.is_file():
                path.unlink()
        restored.append(rel)
    for rel in sorted(set(added)):
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if is_protected(rel):
            path = APP / rel
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            restored.append(rel)
    for rel in restored:
        log("reset to base (build and test files are not part of the submission): " + rel)
    return restored


H2_TEST_DEPENDENCY = """	<!-- verifier-owned test dependency -->
		<dependency>
			<groupId>com.h2database</groupId>
			<artifactId>h2</artifactId>
			<scope>test</scope>
		</dependency>
"""

SUREFIRE_CONFIG = """
	<!-- verifier-owned test configuration -->
	<build>
		<plugins>
			<plugin>
				<groupId>org.apache.maven.plugins</groupId>
				<artifactId>maven-surefire-plugin</artifactId>
				<configuration>
					<jvm>{launcher}</jvm>
					<forkCount>1</forkCount>
					<reuseForks>true</reuseForks>
					<argLine>-Xmx1g -XX:+UseSerialGC -Djava.io.tmpdir={agent_tmp}</argLine>
					<forkNode implementation="org.apache.maven.plugin.surefire.extensions.SurefireForkNodeFactory"/>
					<reportsDirectory>${{project.build.directory}}/verifier-reports</reportsDirectory>
					<redirectTestOutputToFile>true</redirectTestOutputToFile>
					<trimStackTrace>false</trimStackTrace>
					<runOrder>alphabetical</runOrder>
					<failIfNoSpecifiedTests>false</failIfNoSpecifiedTests>
					<skipAfterFailureCount>0</skipAfterFailureCount>
				</configuration>
			</plugin>
		</plugins>
	</build>
"""

LAUNCHER = """#!/bin/bash
# Starts the Surefire test JVM, which runs submission code, as the unprivileged
# account. Maven (root) keeps writing the reports into a root-owned directory.
for arg in "$@"; do
  if [ -f "$arg" ] && [ ! -L "$arg" ]; then chmod a+r -- "$arg" 2>/dev/null; fi
done
if [ -d {surefire_tmp} ]; then chmod -R a+rX {surefire_tmp} 2>/dev/null; fi
exec /usr/bin/setpriv --reuid={uid} --regid={gid} --init-groups -- \\
  /usr/bin/env -i PATH=/opt/java/openjdk/bin:/usr/bin:/bin HOME={agent_home} LANG=C.UTF-8 \\
  JAVA_HOME=/opt/java/openjdk /opt/java/openjdk/bin/java "$@"
"""

CANARY = """package {package};

import static org.junit.jupiter.api.Assertions.fail;

import org.junit.jupiter.api.Test;

class {cls} {{

    @Test
    void {method}() {{
        fail("report canary: this test always fails");
    }}
}}
"""


def cmd_prepare(argv):
    state = pathlib.Path(argv[0])
    config = load_config()
    base = config["base_commit"]
    LOGS.mkdir(parents=True, exist_ok=True)

    head = git("rev-parse", "--verify", base + "^{commit}", stdout=subprocess.PIPE,
               stderr=subprocess.DEVNULL)
    if head.returncode != 0:
        log("ERROR: the verifier's base repository does not have " + base)
        sys.exit(6)
    git("reset", "-q", "--hard", base, check=True)
    git("clean", "-ffdxq", "-e", "/.git", check=True)
    log("work tree reset to base %s from the verifier's own repository copy" % base)

    model_patch = ARTIFACTS / "model.patch"
    applied = "none"
    if model_patch.is_file() and not model_patch.is_symlink() and model_patch.stat().st_size > 0:
        local = state / "model.patch"
        shutil.copyfile(model_patch, local)
        os.chmod(local, 0o600)
        result = git("apply", "--whitespace=nowarn", "--binary", str(local),
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            log("ERROR: model.patch does not apply to base:\n"
                + result.stdout.decode("utf-8", "replace"))
            write_reward(0.0, {"reason": "model.patch does not apply", "passed": False})
            return
        applied = "%d bytes" % model_patch.stat().st_size
        log("model.patch applied (%s)" % applied)
    else:
        log("no model.patch: grading the base state")

    restore_protected(base)
    for rel in RETIRED_PATH_TESTS:
        path = APP / rel
        if path.is_file() and not path.is_symlink():
            path.unlink()
            log("not graded (exercises the retired bare entry point): " + rel)

    result = git("apply", "--whitespace=nowarn", str(TESTS / "test.patch"),
                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        log("ERROR: test.patch does not apply:\n" + result.stdout.decode("utf-8", "replace"))
        sys.exit(7)
    log("hidden tests added from tests/test.patch")

    token = secrets.token_hex(8)
    canary_cls = "ReportCanary%sTest" % token
    canary_method = "reportWrittenByThisRun" + token
    (APP / SUITE_DIR / (canary_cls + ".java")).write_text(
        CANARY.format(package=SUITE_PACKAGE, cls=canary_cls, method=canary_method))
    log("report canary planted: %s.%s" % (SUITE_PACKAGE, canary_cls))

    agent = subprocess.run(["id", "-u", AGENT_USER], stdout=subprocess.PIPE)
    uid = agent.stdout.decode().strip() if agent.returncode == 0 else ""
    if not uid.isdigit():
        log("ERROR: no unprivileged account to run the tests as")
        sys.exit(8)
    gid = subprocess.run(["id", "-g", AGENT_USER], stdout=subprocess.PIPE).stdout.decode().strip()
    agent_home = state / "agent-home"
    agent_tmp = state / "agent-tmp"
    for d in (agent_home, agent_tmp):
        d.mkdir(mode=0o700, exist_ok=True)
        os.chown(d, int(uid), int(gid))
    # The state directory is root's; the unprivileged JVM only needs to reach its own
    # home and temp directories inside it.
    os.chmod(state, 0o711)
    # Surefire only accepts a `jvm` whose file name is `java`.
    launcher_dir = state / "agent-jdk" / "bin"
    launcher_dir.mkdir(parents=True, mode=0o700)
    launcher = launcher_dir / "java"
    launcher.write_text(LAUNCHER.format(uid=uid, gid=gid, agent_home=agent_home,
                                        surefire_tmp=APP / MODULE / "target" / "surefire"))
    os.chmod(launcher, 0o700)

    pom = APP / MODULE / "pom.xml"
    text = pom.read_text()
    if "<build>" in text or text.count("</project>") != 1 or text.count("</dependencies>") != 1:
        log("ERROR: unexpected loan-service pom.xml at base")
        sys.exit(9)
    # The hidden suite runs against an in-memory H2 database (the version the Spring Boot BOM
    # manages, already in the offline repository for banking-app).
    text = text.replace("</dependencies>", H2_TEST_DEPENDENCY + "\t</dependencies>")
    text = text.replace("</project>", SUREFIRE_CONFIG.format(launcher=launcher, agent_tmp=agent_tmp)
                        + "</project>")
    pom.write_text(text)

    graded = sorted({nid.split("#", 1)[0] for nid in config["f2p_node_ids"] + config["p2p_node_ids"]})
    graded.append(SUITE_PACKAGE + "." + canary_cls)
    state_file = state / "state.json"
    state_file.touch(mode=0o600)
    state_file.write_text(json.dumps({
        "canary": SUITE_PACKAGE + "." + canary_cls + "#" + canary_method,
        "test_classes": graded,
        "model_patch": applied,
    }, indent=1))
    log("graded test classes: " + ", ".join(graded))


# --------------------------------------------------------------------------- grade

def parse_reports(sealed):
    results = {}
    problems = []
    for path in sorted(sealed.glob("TEST-*.xml")):
        try:
            root = ET.parse(str(path)).getroot()
        except ET.ParseError as exc:
            problems.append("%s is not a complete report (%s)" % (path.name, exc))
            continue
        for case in root.iter("testcase"):
            nid = "%s#%s" % (case.get("classname", ""), case.get("name", ""))
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("error") is not None:
                status = "error"
            elif case.find("skipped") is not None:
                status = "skipped"
            else:
                status = "passed"
            previous = results.get(nid)
            if previous is None or previous == "passed":
                results[nid] = status
    return results, problems


def cmd_grade(argv):
    state = pathlib.Path(argv[0])
    config = load_config()
    f2p = config["f2p_node_ids"]
    p2p = config["p2p_node_ids"]
    try:
        info = json.loads((state / "state.json").read_text())
    except (OSError, ValueError):
        write_reward(0.0, {"reason": "the verifier did not prepare this run", "passed": False})
        return
    results, problems = parse_reports(state / "sealed")
    for problem in problems:
        log("REPORT: " + problem)

    reasons = []
    canary = info["canary"]
    canary_status = results.get(canary)
    if canary_status not in ("failed", "error"):
        reasons.append("report canary %s was %s, so the reports cannot be trusted as this run's"
                       % (canary, canary_status or "not reported"))
    if not f2p:
        reasons.append("no fail-to-pass tests are configured")

    per_test = {}
    for kind, ids in (("f2p", f2p), ("p2p", p2p)):
        for nid in ids:
            status = results.get(nid, "missing")
            per_test[nid] = {"kind": kind, "status": status}
            if status != "passed":
                reasons.append("%s %s: %s" % (kind, nid, status))

    passed_f2p = sum(1 for nid in f2p if results.get(nid) == "passed")
    passed_p2p = sum(1 for nid in p2p if results.get(nid) == "passed")
    log("fail-to-pass passed %d/%d, pass-to-pass passed %d/%d, canary %s"
        % (passed_f2p, len(f2p), passed_p2p, len(p2p), canary_status or "missing"))
    for reason in reasons:
        log("NOT PASSED: " + reason)

    reward = 1.0 if not reasons else 0.0
    write_reward(reward, {
        "passed": reward == 1.0,
        "f2p_passed": passed_f2p,
        "f2p_total": len(f2p),
        "p2p_passed": passed_p2p,
        "p2p_total": len(p2p),
        "canary": canary_status or "missing",
        "report_problems": problems,
        "reasons": reasons,
        "tests": per_test,
        "model_patch": info.get("model_patch"),
    })


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("prepare", "grade"):
        sys.stderr.write("usage: grader.py prepare|grade <state-dir>\n")
        sys.exit(2)
    if sys.argv[1] == "prepare":
        cmd_prepare(sys.argv[2:])
    else:
        cmd_grade(sys.argv[2:])


if __name__ == "__main__":
    main()
