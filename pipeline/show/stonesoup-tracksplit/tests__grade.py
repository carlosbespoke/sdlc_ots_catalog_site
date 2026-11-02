"""R/L/F grader for a format-1 Python RCA task (docs/task-format.md). Copy to tests/grade.py.

    python -I -S -B /tests/grade.py --prepare     # verifier image build (tests/Dockerfile)
    python -I -S -B /tests/grade.py /workdir      # grading (tests/test.sh)

Everything task-specific comes from tests/meta.json and tests/rca-task.json; the only code a task
may change is the block between the `rca:hooks` markers (`rca check` compares the rest with this
template).

Trust model. This process is the trusted parent: it runs as root, imports only the stdlib and the
two templates beside it, and never imports candidate code. Every candidate run (the agent's
reproducer, the hidden observation probes, the project's suite) is a Sandbox child: demoted to
the agent's uid (a failed demotion raises), in its own session, with the image's own environment
(rca_grading.ordinary_environment: what the agent's processes saw), RLIMIT_AS/RLIMIT_CPU/RLIMIT_FSIZE caps and a wall-clock timeout bounded by an overall budget.
Between runs the sandbox kills the agent's processes and undoes its writes outside /workdir.

Grading context. The tree under test is always rebuilt at /workdir, owned by the agent, and the
interpreter finds it through a `.pth` file in the venv (written at --prepare), exactly as the
agent's editable install did: no PYTHONPATH, no verifier-named file or directory anywhere in the
tree, no hidden-test path in any argv. A probe runs as an ordinary script: copied to a randomly
named `<name>.py` in a fresh, neutrally named directory the agent owns and run with no other
argument, once per rg.PROBE_RUNS setting on a fresh tree (`python <name>.py` from that directory
with a terminal on stdin; `python <abs path>` from /workdir with stdin /dev/null, as the suite
runs), then deleted. It passes only when every run observes the expected values, so a fix gated
on cwd, the script's location or isatty() cannot be correct "only under the probe". The JUnit report
path of a pytest run travels in PYTEST_ADDOPTS. The parent itself runs with -S, so the `.pth`
never puts candidate code on a root interpreter's path, and with -B (plus
sys.dont_write_bytecode, since -I ignores PYTHONDONTWRITEBYTECODE), so it never writes
/tests/__pycache__; --prepare also deletes any that exists (image rule I5).

Candidate changes. The fix trees (probes, P2P) get only the agent's non-test changes; runner-control
files outside the test paths (sitecustomize.py, usercustomize.py, *.pth, conftest.py, pytest
config files, and a pyproject.toml/setup.cfg/tox.ini whose pytest settings changed) stay pristine
on every tree and are listed in eval.json run.runner_control_excluded (rg.classify_changes).

Observation probes. A hidden fix probe (meta.json fix_tests, under tests/) imports the project,
drives a scenario and prints ONE JSON object as its last "{"-line on stdout. It holds no
assertion and no expected value. --prepare records the gold tree's observations in
/opt/rca/fix_expected.json (root-only); grading compares in this process (RTOL/ATOL). A probe
that fails at grading runs once more in full, like the suite, and passes only if that rerun
passes (rca_grading.probe_with_rerun); --prepare never reruns.

One launcher, one environment. Every candidate run (the reproducer, the rebuilt-buggy run, each
probe, the suite) goes through rca_grading.Sandbox.run as the agent, under the agent's login shell
from the same environment, the same rlimits, and the same non-interactive stdin: an empty regular
file, never /dev/null (a character device) or a tty, so a fix gated on isatty() or on stdin being
a character device is inactive and caught (gosmtp-clientserver-v3). Only the pytest runs add the
report path (PYTEST_ADDOPTS), and only one hidden-probe setting swaps in a tty, so the two probe
runs differ in cwd and in every stat dimension of stdin.

Reproducer trees. The agent's test files go onto every reproducer tree; nothing else the agent
wrote does (no REPORT.md, no edited evidence/, no answer file). When the task ships evidence,
every reproducer tree also gets the task's own pristine copy (tests/evidence/, the byte mirror
of environment/evidence/) at /workdir/evidence, where the ask says a test may read it
(rca_grading.task_evidence). Besides buggy, gold, each alt fix and
the runtime fix, the reproducer also runs on the buggy tree with one comment line appended to
every non-test .py file (rca_grading.perturb_sources) and must fail there too
(repro:fails_on_buggy_rebuilt).

Accepted limits:
- The existing-suite check (P2P) reads the result of a pytest process that has the candidate's
  code loaded, so that code can rewrite the suite's report or exit status. This can hide a
  regression of the existing suite: a fix that passes every hidden probe but breaks other tests
  can then score 1, and on an unfixed tree the partial row that reads the suite (fix:suite_catch)
  can rise. It cannot pass a hidden probe without a real fix: the probes' expected values never
  reach a candidate process.
- The rebuilt-buggy run above stops a regression test that recognises the exact buggy files
  (a hash of the source tree, a marker file) from earning the reproduce score. A test that
  fingerprints only what a trailing comment leaves unchanged (the compiled bytecode or the text
  of individual functions) can still earn it; the alt fixes and the runtime fix catch the
  per-function form. Such a test gains the reproduce score only: the fix and the diagnosis must
  still be complete.
- A payload that needs facts only this tests/ directory holds (how the grader builds or runs
  each tree, probe names, expected values, the gold location) is out of scope: the solver never
  sees tests/.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # -I ignores PYTHONDONTWRITEBYTECODE: no /tests/__pycache__ (I5)
sys.path.insert(0, str(TESTS))  # -I drops the script directory from sys.path

import rca_grading as rg  # noqa: E402
from rca_grading import (answer_checks, load_answer, reproducer_checks, reproducer_missing,  # noqa: E402
                         reproducer_path, reproducer_trees)
from reward_writer import write_rewards  # noqa: E402

# --- rca:hooks begin (the only task-editable block) ---
PYTHON = "/opt/venv/bin/python"                      # the toolchain interpreter (root-owned venv)
CHILD_PATH = ""                                      # "" = the image's PATH (as the agent saw it); set only to override
IMPORT_ROOTS = ["."]                                 # tree-relative import roots, e.g. ["src"]
PTH_NAME = "__editable__.workdir.pth"                # the .pth that exposes /workdir to children
REPRO_COMMAND = ["python", "-m", "pytest", "-p", "no:cacheprovider", "-q", "{reproducer}"]
PYTEST_ADDOPTS = "--timeout=60"                      # e.g. "-o addopts=" if repo addopts must not apply
EXTRA_ENV: dict[str, str] = {}                       # e.g. {"MPLBACKEND": "Agg", "OMP_NUM_THREADS": "1"}
RTOL, ATOL = 1e-9, 1e-12                             # probe comparison tolerances
TIMEOUT = {"repro": 300, "probe": 300, "p2p": 1200}  # seconds per step
BUDGET = 2700                                        # whole grading run; below [verifier] timeout_sec
MEMORY = 8 << 30                                     # RLIMIT_AS per candidate process
PREPARE_ALT_P2P = True                               # --prepare also runs the suite on each alt fix
MAX_OUTPUT = 4 << 20                                 # stdout tail kept per child (diagnostics, probe line)
# --- rca:hooks end ---

OPT = Path("/opt/rca")
PRISTINE = OPT / "pristine"
EXPECTED = OPT / "fix_expected.json"
BASELINE = OPT / "p2p_baseline.txt"
UNSTABLE = OPT / "p2p_unstable.txt"          # flaky at build: excluded from the baseline
CATCH = OPT / "p2p_catch.txt"                 # suite tests that fail on buggy and pass on gold + every fix
RECEIPT = OPT / "prepare.json"
WORKDIR = Path("/workdir")
OUT = Path("/logs/verifier")
MAX_JUNIT = 1 << 30           # JUnit report cap; streamed (iterparse), so memory stays bounded
PYTEST_COMPLETE = (0, 1)      # pytest exit codes of a finished run: all passed / some failed


# --- the Python runner ----------------------------------------------------------------------------

FIXED_ENV = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
             "PYTHONUNBUFFERED": "1"}                 # the template agent image's ENV declares the same


def child_env():
    """The sandbox's base environment (the image's own, as the agent's processes saw it, with the
    grader's fixed settings and EXTRA_ENV on top). Candidate runs are login runs from the image
    ENV plus EXTRA_ENV (rca_grading.Sandbox.login_env). --prepare reports any variable whose
    value differs from the image's (receipt `child_env_overrides`): each is a possible marker."""
    env = rg.ordinary_environment()
    env.update(FIXED_ENV)
    env["PATH"] = CHILD_PATH or env.get("PATH") or "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin"
    env.update(EXTRA_ENV)
    return env


def child_env_overrides():
    image = rg.ordinary_environment()
    return sorted(k for k, v in child_env().items() if image.get(k) != v)


def purelib():
    """site-packages of the toolchain interpreter, worked out without running it: a root
    interpreter without -S would process the .pth into /workdir and import a candidate
    sitecustomize. (Under -S, sysconfig does not see the venv: venv detection lives in site.)"""
    venv = Path(PYTHON).parent.parent
    if (venv / "pyvenv.cfg").is_file():
        found = sorted(venv.glob("lib/python3*/site-packages"))
        if len(found) != 1:
            raise RuntimeError(f"cannot locate site-packages under {venv}")
        return found[0]
    import sysconfig
    return Path(sysconfig.get_paths()["purelib"])


@contextlib.contextmanager
def runtime_fix(spec_dir):
    """Activate the verifier-owned runtime fix: its files (e.g. sitecustomize.py) are placed in
    site-packages for the duration of one run and removed afterwards. Repository files are not
    touched, and the child's environment and sys.path entries are the same as on every other tree."""
    target, placed = purelib(), []
    try:
        for source in sorted(Path(spec_dir).iterdir()):
            if not source.is_file() or source.is_symlink() or source.name.startswith("."):
                continue
            dest = target / source.name
            if dest.exists() or dest.is_symlink():
                raise RuntimeError(f"runtime fix would replace an installed file: {source.name}")
            shutil.copyfile(source, dest)
            os.chmod(dest, 0o644)
            placed.append(dest)
        yield
    finally:
        for dest in placed:
            dest.unlink(missing_ok=True)


def parse_junit(path):
    """{"tests", "failures", "errors", "skipped", "passed": {id}, "failed": {id}, "collected": {id}}
    or None (no report, a symlink, over MAX_JUNIT, or not well-formed: a cut-off report never
    half-counts).
    The report is a file pytest writes, never the bounded stdout tail, and it is streamed with
    iterparse, every element cleared once read, so a large suite's report (or long failure
    texts) stays out of memory."""
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": set(), "failed": set(),
              "collected": set()}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            if os.fstat(stream.fileno()).st_size > MAX_JUNIT:
                return None
            for _, element in ET.iterparse(stream, events=("end",)):
                if element.tag != "testcase":
                    if element.tag not in ("testsuite", "testsuites"):
                        element.clear()             # keeps the tag the enclosing testcase reads
                    continue
                counts["tests"] += 1
                kinds = {child.tag for child in element}
                case_id = f"{element.get('classname')}::{element.get('name')}"
                counts["collected"].add(case_id)
                element.clear()
                if "failure" in kinds:
                    counts["failures"] += 1
                    counts["failed"].add(case_id)
                elif "error" in kinds:
                    counts["errors"] += 1
                    counts["failed"].add(case_id)
                elif "skipped" in kinds:
                    counts["skipped"] += 1
                else:
                    counts["passed"].add(case_id)
    except (OSError, ET.ParseError):
        return None
    counts["passed"] -= counts["failed"]     # a test id reported twice counts as failed
    return counts


def pytest_run(sandbox, argv, timeout, label):
    """Run a pytest command line as the agent from /workdir; (RunResult, junit counts or None)."""
    report_dir = sandbox.private_dir()
    report = report_dir / "report.xml"
    env = {"PYTEST_ADDOPTS": f"--junitxml={report} {PYTEST_ADDOPTS}".strip()}
    result = sandbox.run(argv, cwd=WORKDIR, timeout=timeout, env=env, label=label)
    return result, (None if result["timed_out"] else parse_junit(report))


def describe(result, junit):
    if result["timed_out"]:
        return "timed out"
    if junit is None:
        return f"no test report (exit {result['code']})"
    return (f"exit {result['code']}: {junit['tests']} tests, {junit['failures']} failed, "
            f"{junit['errors']} errors, {junit['skipped']} skipped")


def reproducer_outcome(sandbox, rel, timeout, label):
    """fail | pass | error | crashed (with a neutral detail), as rca_grading.reproducer_checks
    expects; a process killed by a signal is "crashed" (rg.crash_outcome), never a bare error."""
    argv = [part.replace("{reproducer}", rel) for part in REPRO_COMMAND]
    result, junit = pytest_run(sandbox, argv, timeout, label)
    if junit is not None and not result["timed_out"]:
        if result["code"] == 1 and junit["failures"] >= 1:
            outcome = "fail"
        elif (result["code"] == 0 and junit["failures"] == 0 and junit["errors"] == 0
              and junit["tests"] - junit["skipped"] >= 1):
            outcome = "pass"
        else:
            outcome = "error"
    else:
        outcome = "error"
    return rg.crash_outcome({"outcome": outcome, "detail": describe(result, junit)},
                            result["code"], result["timed_out"])


def probe_observation(sandbox, probe, rebuild, timeout, label, verbose=False):
    """[(observations or None, neutral detail)], one per rg.PROBE_RUNS setting, each on a tree
    `rebuild()` makes afresh. The probe runs like any script a user writes and runs: its source is
    copied to a randomly named `<name>.py` in a fresh, neutrally named directory the agent owns,
    then `python <name>.py` runs from that directory with a terminal on stdin ("own-dir"), and
    `python /home/agent/<dir>/<name>.py` from /workdir with stdin /dev/null ("project": the
    setting of the agent's own commands), each in the user's own environment (the image ENV
    through the agent's login shell, no grader variable: Sandbox.run(login=True)); the directory
    is deleted afterwards. Nothing in argv, cwd, stdin, the environment or the tree
    names a probe (`python -` with the source on stdin was detectable: octodns v4 Argus Lite), and
    no single setting is the probe's, so a fix gated on cwd or isatty() fails one (octodns v5)."""
    runs = []
    for setting in rg.PROBE_RUNS:
        rebuild()
        where, cwd = rg.probe_layout(sandbox, setting)
        try:
            script = sandbox.place(where, rg.neutral_name() + ".py", Path(probe).read_bytes())
            result = sandbox.run(["python", rg.program_path(script, cwd)], cwd=cwd, timeout=timeout(),
                                 stdin=setting["stdin"], label=f"{label}:{setting['name']}", login=True)
        finally:
            rg._remove(where)
        if result["timed_out"]:
            runs.append((None, rg.PROBE_TIMED_OUT))
            continue
        observed = rg.parse_observation(result["stdout"])
        detail = "observations recorded" if observed is not None else f"no observations (exit {result['code']})"
        if verbose and observed is None:       # --prepare only: grading feedback stays neutral
            detail += f"; stderr: {result['stderr'][-600:]}"
        runs.append((observed, detail))
    return runs


def suite_run(sandbox, command, timeout, label):
    """(passing ids or None, detail) of the project's own suite on the tree at /workdir, read from
    its JUnit report (never stdout). A run that did not finish (pytest exit code other than 0/1:
    interrupted, internal error, usage error, no tests, killed) is None, "not recorded":
    --prepare fails the build on it, and grading never reads a test missing from a partial report
    as a regression of the candidate."""
    result, junit = pytest_run(sandbox, shlex.split(command), timeout, label)
    if junit is None:
        return None, describe(result, junit)
    if result["code"] not in PYTEST_COMPLETE:
        return None, f"{describe(result, junit)}; incomplete record: pytest did not finish the run"
    return rg.SuiteRecord({rg.python_test_id(i) for i in junit["passed"]},
                          {rg.python_test_id(i) for i in junit.get("collected", ())}), describe(result, junit)


# --- shared by --prepare and grading ----------------------------------------------------------------

def load_inputs():
    meta = json.loads((TESTS / "meta.json").read_text())
    manifest = json.loads((TESTS / "rca-task.json").read_text())
    return meta, manifest, rg.OmitRules.from_manifest(manifest)


def make_sandbox(scratch):
    return rg.Sandbox(scratch=scratch, env=child_env(), mem_bytes=MEMORY, max_output=MAX_OUTPUT,
                      extra_env=EXTRA_ENV)


def build(sandbox, rules, view, *, patches=(), files=None, deleted=()):
    """Rebuild /workdir: view "solver" (pristine minus omit_tests, keep honoured) or "full"."""
    remove = rg.solver_view_skip(rules) if view == "solver" else None
    sandbox.populate(PRISTINE, patches=patches, files=files, deleted=deleted, remove=remove)


def rebuild_buggy(rules, extras):
    """The buggy tree at /workdir, changed without changing behaviour: one comment line appended to
    every non-test .py file (not the agent's test files, not the test paths). The reproducer must
    still fail on it (repro:fails_on_buggy_rebuilt)."""
    return rg.perturb_sources(WORKDIR, (".py",), "#", lambda rel: rel in extras or rules.matches(rel))


def scratch_dir():
    path = Path(tempfile.mkdtemp(prefix="g"))
    os.chmod(path, 0o700)
    return path


# --- --prepare: verifier image build ---------------------------------------------------------------

def prepare():
    shared_before = rg.shared_entries()        # what /tmp, /var/tmp, /dev/shm held before --prepare
    meta, manifest, rules = load_inputs()
    problems = rg.meta_problems(meta) + rg.format_problems(meta, manifest, TESTS)
    if problems:
        raise SystemExit("prepare: " + "; ".join(problems))
    violations = []
    trees = manifest["trees"]
    if rg.tree_fingerprint(PRISTINE) != trees["pristine"]:
        violations.append("pristine tree fingerprint differs from rca-task.json trees.pristine")
    if rg.tree_fingerprint(PRISTINE, rg.solver_view_skip(rules)) != trees["solver"]:
        violations.append("solver view fingerprint differs from rca-task.json trees.solver")
    if rules.patterns and not any(rules.omitted(rel) for rel in rg.tree_manifest(PRISTINE)):
        violations.append("the pristine tree has no file matching omit_tests (the suite must be here)")
    command = meta["p2p"]["command"]
    if any(arg in ("-n", "--numprocesses", "--dist") or arg.startswith(("-n=", "--numprocesses="))
           for arg in shlex.split(command)):
        violations.append("p2p.command must not run pytest-xdist workers (-n)")
    if any(arg in ("-x", "--exitfirst") or arg.startswith("--maxfail") for arg in shlex.split(command)):
        violations.append("p2p.command must run the whole suite (no -x / --exitfirst / --maxfail)")
    if violations:
        raise SystemExit("prepare: " + "; ".join(violations))

    pth = purelib() / PTH_NAME
    pth.write_text("".join(f"{(WORKDIR / root).as_posix()}\n" for root in IMPORT_ROOTS))
    os.chmod(pth, 0o644)

    scratch = scratch_dir()
    sandbox = make_sandbox(scratch)
    sandbox.scan()
    fixes = reproducer_trees(meta, TESTS)
    probes = list(meta["fix_tests"])
    solver_manifest = rg.tree_manifest(PRISTINE, rg.solver_view_skip(rules))

    details = {}
    settings = [setting["name"] for setting in rg.PROBE_RUNS]

    def observe(label, kind, path):
        """{probe: [observations per rg.PROBE_RUNS setting]} on one tree."""
        seen = {}

        def runtime_unchanged():
            if kind == "runtime" and rg.tree_manifest(
                    WORKDIR, lambda rel: rg.is_build_output(rel) and rel not in solver_manifest) != solver_manifest:
                violations.append("the runtime fix changed repository files at run time")

        for probe in probes:
            built = []

            def rebuild():
                if built:
                    runtime_unchanged()
                build(sandbox, rules, "solver", patches=[path] if kind == "patch" else [])
                built.append(True)
            context = runtime_fix(path) if kind == "runtime" else contextlib.nullcontext()
            with context:
                runs = probe_observation(sandbox, TESTS / probe, rebuild, lambda: TIMEOUT["probe"],
                                         f"{label}:{probe}", verbose=True)
            runtime_unchanged()
            seen[probe] = [observed for observed, _ in runs]
            details[(label, probe)] = "; ".join(f"{name}: {detail}" for name, (_, detail) in zip(settings, runs))
        return seen

    def matches(observed, expected):
        return observed is not None and rg.observations_match(observed, expected, RTOL, ATOL)

    gold_path = fixes[0][2]
    buggy = observe("buggy", None, None)
    gold = observe("gold", "patch", gold_path)
    again = observe("gold-repeat", "patch", gold_path)
    for probe in probes:
        problem = next(filter(None, map(rg.observation_problem, gold[probe])), None)
        if problem:
            violations.append(f"{probe}: gold observations unusable ({problem}; {details[('gold', probe)]})")
            continue
        reference = gold[probe][0]
        if any(observed != reference for observed in gold[probe]):
            violations.append(f"{probe}: observations on the gold tree depend on the run setting ({', '.join(settings)}: "
                              "cwd, the script's directory or stdin); a probe must observe the same values wherever it runs")
        if again[probe] != gold[probe]:
            violations.append(f"{probe}: observations on the gold tree are not deterministic")
        for name, observed in zip(settings, buggy[probe]):
            if matches(observed, reference):
                violations.append(f"{probe}: observes the same values on the buggy tree as on gold in the {name} run "
                                  "(not fail-to-pass)")
    for label, kind, path in fixes[1:]:
        seen = observe(label, kind, path)
        for probe in probes:
            if gold[probe][0] is not None and not all(matches(observed, gold[probe][0]) for observed in seen[probe]):
                violations.append(f"{probe}: {label} observes different values than gold ({details[(label, probe)]})")

    # The P2P baseline from two runs on each tree (a flaky test must not kill the build: powercalc).
    def suite_twice(label, patches):
        runs, details = [], []
        for attempt in (1, 2):
            build(sandbox, rules, "full", patches=patches)
            passed, detail = suite_run(sandbox, command, TIMEOUT["p2p"], f"p2p:{label}:{attempt}")
            runs.append(passed)
            details.append(detail)
        return runs, "; ".join(details)

    on_buggy, buggy_detail = suite_twice("buggy", [])
    on_gold, gold_detail = suite_twice("gold", [gold_path])
    excluded = rg.p2p_excluded_ids(meta, rg.python_test_id)
    baseline, unstable, catch, collection = set(), set(), set(), set()
    if None in on_buggy or None in on_gold:
        violations.append(f"the suite cannot be recorded (buggy: {buggy_detail}; gold: {gold_detail})")
    else:
        recorded = rg.p2p_baseline(on_buggy, on_gold, excluded)
        baseline, unstable = recorded["baseline"], recorded["unstable"]
        collection = recorded["collection_unstable"]   # ids drawn at random at collection: never fail the build
        catch = rg.p2p_catch(on_buggy, on_gold, excluded)   # suite tests the defect broke (fail-to-pass)
        pinned = sorted(recorded["pinned"])
        if pinned:
            violations.append(f"{len(pinned)} suite tests pass on buggy but fail on gold and are not in "
                              f"p2p.excluded (e.g. {pinned[0]})")
        if not baseline:
            violations.append("the P2P baseline is empty" + (f" ({len(unstable)} unstable suite tests excluded)"
                                                             if unstable else ""))
        if unstable:
            print(f"prepare: {len(unstable)} unstable suite tests excluded from the baseline "
                  f"(e.g. {sorted(unstable)[0]})")
        if collection:
            print(f"prepare: {len(collection)} of them have ids not collected identically in each run of one "
                  f"tree (drawn at random at collection?), so they are unstable, never regressions "
                  f"(e.g. {sorted(collection)[0]})")
        if catch:
            print(f"prepare: {len(catch)} suite tests fail on buggy and pass on gold (fix:suite_catch)")
    # Each alt fix and the runtime fix must leave the baseline intact; a catch test that fails on
    # one pins gold internals, so it is dropped from the catch set and logged, not counted at grading.
    if PREPARE_ALT_P2P and baseline:
        for label, kind, path in fixes[1:]:
            def fix_suite(attempt, kind=kind, path=path):
                if kind == "runtime":
                    build(sandbox, rules, "full")
                    with runtime_fix(path):
                        return suite_run(sandbox, command, TIMEOUT["p2p"], f"p2p:{label}:{attempt}")
                build(sandbox, rules, "full", patches=[path])
                return suite_run(sandbox, command, TIMEOUT["p2p"], f"p2p:{label}:{attempt}")

            outcome = rg.p2p_with_rerun(fix_suite, baseline | catch)
            if not outcome["recorded"]:
                violations.append(f"the suite cannot be recorded on {label} ({outcome['detail']})")
                continue
            if outcome["lost"] & baseline:
                regressed = sorted(outcome["lost"] & baseline)
                violations.append(f"{label} regresses the suite ({outcome['detail']}; e.g. {regressed[0]})")
            dropped = outcome["lost"] & catch
            if dropped:
                print(f"prepare: {len(dropped)} fail-on-buggy suite tests fail on {label} and are dropped from "
                      f"fix:suite_catch (they pin gold internals; e.g. {sorted(dropped)[0]})")
                catch -= dropped

    sandbox.reset()
    for entry in list(os.scandir(WORKDIR)):
        rg._remove(Path(entry.path))
    shutil.rmtree(scratch, ignore_errors=True)
    removed = rg.remove_new_shared_entries(shared_before)
    if removed:
        print(f"prepare: removed {len(removed)} entries left in shared temporary directories (e.g. {removed[0]})")
    if rg.remove_bytecode_caches(TESTS):
        print("prepare: removed __pycache__ under /tests (run grade.py with -B)")
    overrides = child_env_overrides()
    if overrides:
        print(f"prepare: candidate children get {overrides} with values the image does not declare")
    if violations:
        pth.unlink(missing_ok=True)
        raise SystemExit("prepare: " + "; ".join(violations))
    expected_text = json.dumps({probe: runs[0] for probe, runs in gold.items()}, indent=1, sort_keys=True) + "\n"
    baseline_text = "".join(f"{i}\n" for i in sorted(baseline))
    unstable_text = "".join(f"{i}\n" for i in sorted(unstable))
    catch_text = "".join(f"{i}\n" for i in sorted(catch))
    EXPECTED.write_text(expected_text)
    BASELINE.write_text(baseline_text)
    UNSTABLE.write_text(unstable_text)
    CATCH.write_text(catch_text)
    RECEIPT.write_text(json.dumps({
        "language": "python", "probes": len(probes), "probe_runs": settings, "alt_fixes": len(fixes) - 1 - (fixes[-1][1] == "runtime"),
        "runtime_fix": (meta.get("runtime_fix") or {}).get("kind"), "p2p_baseline": len(baseline),
        "p2p_excluded": len(excluded), "p2p_unstable": len(unstable),
        "p2p_unstable_collection": len(collection), "p2p_catch": len(catch), "p2p_runs_per_tree": 2,
        "shared_tmp_removed": len(removed), "pristine": trees["pristine"], "child_env_overrides": overrides,
        "fix_expected_sha256": hashlib.sha256(expected_text.encode()).hexdigest(),
        "p2p_baseline_sha256": hashlib.sha256(baseline_text.encode()).hexdigest()}, sort_keys=True) + "\n")
    for path in (EXPECTED, BASELINE, UNSTABLE, CATCH, RECEIPT):
        os.chmod(path, 0o600)
    print(f"prepared: {len(probes)} probes, {len(fixes)} fix trees, {len(baseline)} baseline tests, "
          f"{len(catch)} fail-on-buggy tests")


# --- grading ---------------------------------------------------------------------------------------

def sealed(path):
    st = os.lstat(path)
    return st.st_uid == 0 and not st.st_mode & 0o077 and not Path(path).is_symlink()


def read_ids(path):
    """Ids, one per line (they may contain spaces); an absent file (an older image) is empty."""
    try:
        return {line for line in Path(path).read_text().splitlines() if line}
    except FileNotFoundError:
        return set()


def unstable_note(unstable):
    return {"count": len(unstable), "examples": sorted(unstable)[:5],
            "note": "suite tests that passed in only some --prepare runs of the same tree, or whose ids those "
                    "runs did not collect identically (ids drawn at random at collection); excluded from the "
                    "P2P baseline, so they are never counted as regressions"}


def p2p_row(outcome, baseline, run):
    """The P2P check row from rca_grading.p2p_with_rerun's outcome (and its notes in `run`)."""
    lost = sorted(outcome["lost"])
    run["p2p_rerun"] = {"reran": outcome["reran"], "flaky_in_first_run": sorted(outcome["flaky"])[:5],
                        "flaky_count": len(outcome["flaky"])}
    detail = outcome["detail"]
    if not outcome["recorded"]:
        detail += "; no run produced a complete suite record, so no baseline test could be confirmed"
    elif lost:
        detail += (f"; {len(lost)} of {len(baseline)} previously passing tests no longer pass "
                   f"(e.g. {lost[0]})")
    else:
        detail += f"; {len(baseline)} baseline tests pass"
        if outcome["flaky"]:
            detail += f" ({len(outcome['flaky'])} only on the rerun)"
    unstable = run.get("p2p_unstable", {}).get("count")
    if unstable:
        detail += f"; {unstable} unstable suite tests excluded from the baseline"
    return {"id": "P2P:existing-suite", "component": "P2P",
            "status": "passed" if outcome["recorded"] and not lost else "failed", "detail": detail}


def catch_row(outcome, catch, run):
    """The fix:suite_catch F row from the same p2p_with_rerun outcome: the suite's fail-on-buggy
    tests (recorded at --prepare) that the candidate's fix must restore. Passed when every one of
    them passes (with the usual one-rerun); a correct fix restores them, a symptom-site or
    value-specific fix does not."""
    failed = sorted(outcome["lost"] & set(catch))
    run["p2p_catch"] = {"count": len(catch), "failed": failed[:5],
                        "note": "suite tests that fail on the buggy tree and pass on gold and every correct fix; "
                                "a correct fix must make them pass again"}
    if not outcome["recorded"]:
        detail = "no run produced a complete suite record, so the fail-on-buggy tests could not be confirmed"
    elif failed:
        detail = f"{len(failed)} of {len(catch)} tests the reported defect broke still do not pass (e.g. {failed[0]})"
    else:
        detail = f"the {len(catch)} tests the reported defect broke pass again"
    return {"id": "fix:suite_catch", "component": "F",
            "status": "passed" if outcome["recorded"] and not failed else "failed", "detail": detail}


def grade(workdir=WORKDIR):
    meta, manifest, rules = load_inputs()
    expected = json.loads(EXPECTED.read_text())
    baseline = {line for line in BASELINE.read_text().splitlines() if line}
    unstable = read_ids(UNSTABLE)
    catch = read_ids(CATCH)             # suite tests the defect broke; a correct fix restores them (F)
    budget = rg.Budget(BUDGET)
    scratch = scratch_dir()
    snap = rg.snapshot_tree(workdir, scratch / "agent")           # before any candidate code runs
    for path in (TESTS, OPT, EXPECTED):
        if not sealed(path):
            raise RuntimeError(f"{path} is not sealed root-only")
    sandbox = make_sandbox(scratch)
    run = {"grader": "templates/grade_python.py", "sandbox": sandbox.scan(), "snapshot_skipped": snap["skipped"],
           "p2p_unstable": unstable_note(unstable)}
    if not sandbox.unreadable(EXPECTED):
        raise RuntimeError("the candidate user can read the private expectations")
    try:
        run["prepare"] = json.loads(RECEIPT.read_text())
    except (OSError, ValueError):
        run["prepare"] = None
    checks = []

    # L
    agent = scratch / "agent"
    answer, problems = load_answer(agent / "rca.json")
    checks += answer_checks(answer, problems, meta, root=PRISTINE)   # bare names checked on buggy

    # R: the agent's reproducer on the solver view of buggy, gold, each alt fix and the runtime fix
    repro = reproducer_path(agent / "rca.json", meta)
    changes = rg.classify_changes(snap, PRISTINE, rules, repro)
    run.update({"reproducer": repro, "source_changes": len(changes["source"]),
                "deleted": len(changes["deleted"]), "test_files": len(changes["tests"]),
                "runner_control_excluded": changes["runner"]})   # never applied: pristine kept
    if repro is None or not repro.endswith(".py") or repro not in snap["files"]:
        checks += reproducer_missing("no regular .py regression test at the path rca.json names"
                                     if repro else "no reproducer path")
    else:
        extras = dict(changes["tests"])           # the agent's test files (no REPORT.md, no agent evidence/)
        extras[repro] = snap["files"][repro]
        extras.update(rg.task_evidence(manifest, TESTS))   # the task's own pristine evidence, where the agent saw it

        def outcome(label, kind, path, rebuilt=False):
            build(sandbox, rules, "solver", patches=[path] if kind == "patch" else [], files=extras)
            if rebuilt:
                rebuild_buggy(rules, extras)
            with runtime_fix(path) if kind == "runtime" else contextlib.nullcontext():
                return reproducer_outcome(sandbox, repro, budget.step(TIMEOUT["repro"]), f"repro:{label}")

        on_buggy = outcome("buggy", None, None)
        ran = on_buggy["outcome"] == "fail"       # otherwise R = 0 already; the other rows read "not run"
        on_rebuilt = outcome("rebuilt", None, None, rebuilt=True) if ran else None
        on_fixes = [(label, outcome(label, kind, path) if ran else None)
                    for label, kind, path in reproducer_trees(meta, TESTS)]
        checks += reproducer_checks(on_buggy, on_fixes, meta, on_rebuilt=on_rebuilt)

    # F: each hidden probe on the solver view + the agent's non-test changes, once per run setting
    # (rg.PROBE_RUNS), each on a fresh tree; a probe passes only when every run matches. A failed
    # probe is rerun once in full (rg.probe_with_rerun) and passes only if the rerun passes.
    run["probe_reruns"] = {}
    for index, probe in enumerate(meta["fix_tests"]):
        check_id = "fix:gold" if index == 0 else f"fix:variant{index}"
        ok, detail, reran = rg.probe_with_rerun(lambda attempt: probe_observation(
            sandbox, TESTS / probe,
            lambda: build(sandbox, rules, "solver", files=changes["source"], deleted=changes["deleted"]),
            lambda: budget.step(TIMEOUT["probe"]), check_id if attempt == 1 else f"{check_id}:rerun"),
            expected[probe], RTOL, ATOL)
        if reran:
            run["probe_reruns"][check_id] = "passed on the rerun" if ok else "failed twice"
        checks.append({"id": check_id, "component": "F", "status": "passed" if ok else "failed", "detail": detail})

    # P2P + the suite's fail-on-buggy tests: the full suite on the full pristine tree + the agent's
    # non-test changes; a watched test that fails is rerun once (whole suite) and counts only if it
    # fails in both runs. The baseline must not regress (P2P); the fail-on-buggy tests (catch) must
    # now pass (one F row, fix:suite_catch) -- a correct fix restores the upstream tests the defect
    # broke, while a symptom-site or value-specific fix leaves them failing.
    def candidate_suite(attempt):
        build(sandbox, rules, "full", files=changes["source"], deleted=changes["deleted"])
        return suite_run(sandbox, meta["p2p"]["command"], budget.step(TIMEOUT["p2p"]),
                         "p2p" if attempt == 1 else "p2p:rerun")

    outcome = rg.p2p_with_rerun(candidate_suite, baseline | catch)
    checks.append(p2p_row({**outcome, "lost": outcome["lost"] & baseline,
                           "flaky": outcome["flaky"] & baseline}, baseline, run))
    if catch:
        checks.append(catch_row(outcome, catch, run))

    # Put the agent's files back where Harbor left them, then write the six outputs.
    sandbox.populate(agent)
    run["runs"] = sandbox.runs
    write_rewards(OUT, checks, run=run)
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        prepare()
    else:
        grade(Path(sys.argv[1]) if len(sys.argv) > 1 else WORKDIR)
