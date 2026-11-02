"""Trusted TypeScript grader (spec-drift-ots; docs/plans/typescript.md section 4). Same trust boundary,
comparison and scoring as grade.py, whose `close`, `score`, `seal_check` and `readable_workspace` it
reuses unchanged, and the same reward files through the unchanged reward_writer.

Root (this process) checks the seals, proves the expected values are unreadable to `nobody`, checks
that Node, the runner and the installed dependencies are sealed, replaces every `node_modules` the
candidate's tree carries with the image's own links (a planted copy cannot stand in for a sealed
dependency), and checks the documentation (pages by bytes; TypeScript JSDoc by parsing root-only
copies with the sealed `tsparse` helper: ts_doc_digest.py). Root runs Node only on that helper.

Every case runs in its own fresh Node process as `nobody`, with a clean environment, in a fresh
case folder: root's runner (/opt/spec-drift/runner, the pinned tsx as the load hook) reads the case
module (tests/private/cases.json, written by BuildTask around the authored case) and the resolution
map on stdin, imports the case, and writes the raw observation to
./result.json. The resolution map sends the in-scope package names to the candidate's sources, so
a built dist/ (stale, or pristine) is never what a case observes (plan 4.4). Before writing, the
runner kills every other process of its uid; after every case root kills every `nobody` process,
and keeps a result only when the runner exited 0 (plan 4.3).

A case that imports an export the candidate removed fails alone: the import fails at link time in
that case's own process. A candidate module that throws while loading fails every case importing it.

    python3 -I -S grade_ts.py /workdir                         # grade (tests dir = this file's dir)
    python3 -I -S grade_ts.py /workdir --measure N OUT.json    # record: every case N times, no expected values
"""
import ctypes
import hashlib
import json
import os
import pwd
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Python -I excludes the script directory; add only this trusted, root-owned verifier directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
import grade  # noqa: E402  (close, score, seal_check, readable_workspace: reused unchanged)
from doc_digest import documentation_preserved  # noqa: E402
import ts_doc_digest  # noqa: E402
from reward_writer import write_rewards  # noqa: E402

DOCS_OBSERVATION = "OBS-DOCS"
NODE = Path("/usr/local/bin/node")
TOOLCHAIN = Path("/usr/local/lib/node_modules")
OPT = Path("/opt/spec-drift")
RUNNER, NESTED, DEPENDENCIES = OPT / "runner", OPT / "nested", Path("/node_modules")
HELPER = "tsparse.cjs"
CASE_BUDGET = 900
# RLIMIT_NPROC counts every thread of the uid on the host (no user namespaces), and one Node case
# uses at least 10: 256 (Rust's per-case value) aborted cases while other containers ran (plan 4.3).
NPROC = 4096
MAX_RESULT_BYTES = 1024 * 1024
libc = ctypes.CDLL(None, use_errno=True)


# --- running as the subject uid (the same rules as grade_rs.py) ----------------------------------------

def demoted_limits(fsize, nproc):
    def apply():
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        # PR_SET_NO_NEW_PRIVS: no exec in the child can gain privileges (setuid, file capabilities).
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    return apply


def as_subject(subject, command, *, cwd, env, timeout, stdin=b"", fsize, nproc):
    """Run as the subject uid in a new session; kill the whole group afterwards. (exit code, timed out)."""
    with tempfile.TemporaryFile() as handle:
        handle.write(stdin)
        handle.seek(0)
        child = subprocess.Popen(command, cwd=cwd, env=env, user=subject.pw_uid, group=subject.pw_gid,
                                 extra_groups=[], start_new_session=True, preexec_fn=demoted_limits(fsize, nproc),
                                 stdin=handle, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        timed_out = False
        try:
            child.wait(timeout=max(1, timeout))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        return child.returncode, timed_out


def subject_pids(uid):
    pids = []
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open(f"/proc/{pid}/status") as handle:
                    fields = dict(line.split(":", 1) for line in handle if ":" in line)
            except (OSError, ValueError):
                continue
            if int(fields["Uid"].split()[0]) == uid and fields.get("State", "").split()[:1] not in (["Z"], ["X"]):
                pids.append(int(pid))
    return pids


def sweep(subject):
    """Kill every process of the subject uid, from the subject uid itself (kill(-1) cannot reach root),
    until none is left. A demotion or kill that cannot be completed stops the grading."""
    killer = [sys.executable, "-I", "-S", "-c", "import os\ntry: os.kill(-1, 9)\nexcept ProcessLookupError: pass"]
    for _ in range(50):
        if not subject_pids(subject.pw_uid):
            return
        subprocess.run(killer, user=subject.pw_uid, group=subject.pw_gid, extra_groups=[], timeout=30,
                       preexec_fn=demoted_limits(1 << 20, 64), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        time.sleep(0.02)
    raise RuntimeError("subject processes survive the sweep")


def sealed_tree(path):
    """Paths under `path` that are not root-owned or are group/other writable (first five)."""
    bad = []
    for directory, dirs, files in os.walk(path):
        for name in [directory] + [os.path.join(directory, f) for f in dirs + files]:
            info = os.lstat(name)
            if info.st_uid != 0 or (info.st_mode & 0o022 and not stat.S_ISLNK(info.st_mode)):
                bad.append(name)
                if len(bad) >= 5:
                    return bad
    return bad


def read_result(case_dir):
    try:
        fd = os.open(case_dir / "result.json", os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESULT_BYTES:
            return {"error": "unsafe-result"}
        try:
            value = json.loads(handle.read())
        except ValueError:
            return {"error": "malformed"}
    if isinstance(value, dict) and len(value) == 1 and ("value" in value or "error" in value):
        return value
    return {"error": "malformed"}


# --- the candidate tree ----------------------------------------------------------------------------------

def restore_links(app):
    """Delete every `node_modules` entry in the candidate's tree (a folder, a link or a file: never
    followed) and link back each per-package folder the image installed under /opt/spec-drift/nested
    (plan 7.1). A planted /workdir/node_modules/<dep> would otherwise win Node's lookup over the
    sealed /node_modules for any dependency the resolution map does not cover (plan 8)."""
    app = Path(app)
    for directory, dirs, files in os.walk(app):
        for name in dirs + files:
            if name == "node_modules":
                path = os.path.join(directory, name)
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
        dirs[:] = [d for d in dirs if d != "node_modules"]
    if not NESTED.is_dir():
        return
    real = os.path.realpath(app)
    for directory, dirs, _ in os.walk(NESTED):
        if os.path.basename(directory) != "node_modules":
            continue
        dirs[:] = []
        rel = os.path.relpath(directory, NESTED)
        parent = os.path.join(real, os.path.dirname(rel))
        # Only inside the tree, through real folders: a candidate link must not steer root's link elsewhere.
        if os.path.isdir(parent) and os.path.realpath(parent) == os.path.normpath(parent):
            os.symlink(directory, os.path.join(real, rel))


def resolution_map(app, spec):
    """{package specifier: file URL of its source file}, from the sealed harness.json (paths relative
    to the candidate tree). Root never asks the candidate's package.json where its code is."""
    return {name: Path(app, relative).resolve().as_uri() for name, relative in spec["map"].items()}


def run_case(subject, scratch, module, spec, mapping, timeout, timings):
    case_dir = Path(tempfile.mkdtemp(prefix="c-", dir=scratch))
    os.chown(case_dir, subject.pw_uid, subject.pw_gid)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(case_dir), "TMPDIR": str(case_dir),
           "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC", "TSX_DISABLE_CACHE": "1"}
    # The package's tsconfig steers only how the candidate's own code is translated (aliases, JSX,
    # decorators). tsx exits on a configured path that does not exist, so a missing (or linked) file
    # means none: tsx then searches the empty case folder and uses its defaults (plan 4.2).
    tsconfig = Path(spec["app"], spec["tsconfig"]) if spec.get("tsconfig") else None
    if tsconfig is not None and tsconfig.is_file() and not tsconfig.is_symlink():
        env["TSX_TSCONFIG_PATH"] = str(tsconfig)
    command = [str(NODE), "--import", (RUNNER / "node_modules/tsx/dist/loader.mjs").as_uri(), str(RUNNER / "main.mjs")]
    began = time.time()
    code, timed_out = as_subject(subject, command, cwd=str(case_dir), env=env, timeout=timeout,
                                 stdin=json.dumps({"map": mapping, "case": module}).encode(),
                                 fsize=MAX_RESULT_BYTES, nproc=NPROC)
    timings.append(round(time.time() - began, 3))
    sweep(subject)  # nothing of the case survives to rewrite its result before root reads it
    if timed_out:
        return {"error": "timeout"}
    if code != 0:  # the runner exits 0 only after writing its result; anything else is not its result
        return {"error": f"exit {code}"}
    result = read_result(case_dir)
    return result if result is not None else {"error": "no-result"}


def observe(app, private, cases, subject, repeats, timings):
    """Run every case `repeats` times on the tree at `app`. [[result per run] per case]."""
    spec = json.loads((private / "harness.json").read_text())
    spec["app"] = str(app)
    began = time.time()
    restore_links(app)
    grade.readable_workspace(app)
    timings["prepare_seconds"] = round(time.time() - began, 2)
    mapping = resolution_map(app, spec)
    root = Path(tempfile.mkdtemp(prefix="grade-"))
    os.chmod(root, 0o755)
    scratch = root / "runs"
    scratch.mkdir(mode=0o700)
    os.chown(scratch, subject.pw_uid, subject.pw_gid)
    sweep(subject)
    began, per_case = time.time(), []
    results = [[] for _ in cases]
    for _ in range(repeats):
        for index, case in enumerate(cases):
            remaining = CASE_BUDGET * repeats - (time.time() - began)
            if remaining <= 0:
                results[index].append({"error": "timeout"})
                continue
            results[index].append(run_case(subject, scratch, case["code"], spec, mapping,
                                           min(spec.get("case_timeout", 30), remaining), per_case))
    timings["case_runs_seconds"] = round(time.time() - began, 2)
    timings["case_runs"] = len(cases) * repeats
    if per_case:
        timings["per_case_seconds"] = {"min": min(per_case), "max": max(per_case),
                                       "mean": round(sum(per_case) / len(per_case), 3)}
    shutil.rmtree(root, ignore_errors=True)
    return results


def preflight():
    """Node, its global modules, the runner (with the pinned tsx) and the installed dependencies
    must be root-owned and not writable by anyone else: `nobody` runs them, and the agent must not
    have been able to plant them."""
    for tree in (NODE, TOOLCHAIN, RUNNER, DEPENDENCIES, NESTED):
        if not tree.exists():
            if tree == NESTED:
                continue
            raise RuntimeError(f"{tree} is missing")
        bad = sealed_tree(tree) if tree.is_dir() else (
            [] if os.lstat(tree).st_uid == 0 and not os.lstat(tree).st_mode & 0o022 else [str(tree)])
        if bad:
            raise RuntimeError(f"{tree} is not sealed (root-owned, not group/other writable): {bad}")


def sealed_helper(private):
    """[node, tests/private/tsparse.cjs] after checking the file is the pinned parser build."""
    spec = json.loads((private / "harness.json").read_text())
    if hashlib.sha256((private / HELPER).read_bytes()).hexdigest() != spec["tsparse_sha256"]:
        raise RuntimeError(f"tests/private/{HELPER} is not the pinned TypeScript parser build")
    return [str(NODE), str(private / HELPER)]


def check_documentation(app, private):
    """'intact', or what changed: every baseline page byte-identical (doc_digest) and every baseline
    TypeScript file keeping its JSDoc blocks in order under their owners (ts_doc_digest). Parsing only."""
    baseline = json.loads((private / "documentation.json").read_text())
    pages = documentation_preserved(app, baseline)
    files = baseline.get("ts_files") or {}
    if not files:
        return pages
    changed = ts_doc_digest.changed_files(app, files, sealed_helper(private))
    if pages == "intact" and not changed:
        return "intact"
    return f"{pages if pages != 'intact' else 'pages intact'}; {changed} TypeScript files changed"


def grade_main(app, tests, output):
    if os.geteuid() != 0:
        raise RuntimeError("this grader requires a root verifier; there is no same-uid fallback")
    subject = pwd.getpwnam("nobody")
    if subject.pw_uid == 0:
        raise RuntimeError("the subject uid must not be root")
    os.chmod(tests, 0o700)
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o755)
    # Keep -1 on infrastructure failure, never a misleading behavioural zero.
    (output / "reward.txt").write_text("-1\n")
    timings, started = {}, time.time()
    manifest = json.loads((tests / "private_manifest.json").read_text())
    private = tests / "private"
    grade.seal_check(private, manifest)
    expected = json.loads((private / "expected.json").read_text())["observations"]
    cases = json.loads((private / "cases.json").read_text())
    # A permission claim is not proof on every mount type: check as the subject uid.
    guard = subprocess.run([sys.executable, "-I", "-S", "-c",
                            "import os,sys; sys.exit(1 if os.access(sys.argv[1], os.R_OK) else 0)",
                            str(private / "expected.json")],
                           user=subject.pw_uid, group=subject.pw_gid, extra_groups=[], capture_output=True, timeout=30)
    if guard.returncode:
        raise RuntimeError("the expected observations are readable by the subject uid")
    preflight()
    # The documentation is checked before any candidate code runs (byte reads and parsing only).
    documentation = check_documentation(app, private)
    timings["preflight_seconds"] = round(time.time() - started, 2)
    results = observe(app, private, cases, subject, 1, timings)
    observed = {case["id"]: runs[0] for case, runs in zip(cases, results)}
    observed[DOCS_OBSERVATION] = {"ok": documentation}
    partial, groups, outcomes = grade.score(manifest, expected, observed)
    observations = []
    for name in sorted(expected):
        if name not in observed:
            observations.append({"id": name, "status": "missing"})
        elif outcomes[name]:
            observations.append({"id": name, "status": "passed"})
        elif isinstance(observed[name], dict) and "error" in observed[name]:
            observations.append({"id": name, "status": "error", "detail": str(observed[name]["error"])[:100]})
        else:
            observations.append({"id": name, "status": "failed"})
    timings["total_seconds"] = round(time.time() - started, 2)
    run = {"timings": timings, "documentation": documentation if documentation == "intact" else "changed",
           "observations_expected": len(expected), "observations_returned": len(observed)}
    metrics = write_rewards(output, partial, groups, observations=observations, run=run)
    (output / "replay.json").write_text(json.dumps({
        "observations_expected": len(expected),
        "observations_returned": len(observed),
        "failed_observation_count": sum(1 for passed in outcomes.values() if not passed),
        "partial": str(partial),
    }, indent=2, sort_keys=True))
    return metrics


def measure_main(app, private, repeats, out):
    """The recorder: run every case `repeats` times on the tree at `app` (no expected values)."""
    if os.geteuid() != 0:
        raise RuntimeError("measuring requires root (the cases run as nobody)")
    subject = pwd.getpwnam("nobody")
    preflight()
    timings = {}
    cases = json.loads((private / "cases.json").read_text())
    results = observe(app, private, cases, subject, repeats, timings)
    out.write_text(json.dumps({"results": results, "timings": timings}, indent=1))


if __name__ == "__main__":
    tests_dir = Path(__file__).resolve().parent
    if "--measure" in sys.argv:
        position = sys.argv.index("--measure")
        measure_main(Path(sys.argv[1]), tests_dir / "private", int(sys.argv[position + 1]),
                     Path(sys.argv[position + 2]))
    else:
        grade_main(Path(sys.argv[1]), tests_dir, Path(os.environ.get("SPEC_DRIFT_VERIFIER_DIR", "/logs/verifier")))
