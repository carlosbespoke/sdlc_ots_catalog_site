"""Trusted Rust grader (spec-drift-ots; docs/plans/rust.md section 4). Same trust boundary, comparison
and scoring as grade.py, whose `close`, `score`, `seal_check` and `readable_workspace` it reuses
unchanged, and the same reward files through the unchanged reward_writer.

Root (this process) checks the seals, proves the expected values are unreadable to `nobody`, checks
the documentation (pages by bytes; `.rs` doc comments by lexing root-only copies with the sealed
`rslex` helper, rustc's own lexer, after checking its sha256: rs_doc_digest.py), re-stamps the
candidate's files so cargo rebuilds them, and writes the harness sources and a fresh cargo
configuration outside /workdir. It never runs cargo, rustc or anything the build produced. `nobody` builds the harness (build scripts and proc macros are
candidate code) and runs every case in its own process from a root-owned copy of the program. After
the build and after every case, every `nobody` process is killed before root reads anything. Root
reads each case's raw result file, compares it with the sealed expected value and scores.

A case that no longer compiles fails alone: an error whose primary span (followed out of macro
expansions) lies in the harness's own src/cases/cNNNN.rs cuts that case out, and the harness is
rebuilt (at most three passes in all). Any other error means the candidate crate does not build,
and every case fails. The attribution is not authenticated (a proc macro can print any line); it
only ever cuts a case out, never passes one.

    python3 -I -S grade_rs.py /workdir                         # grade (tests dir = this file's dir)
    python3 -I -S grade_rs.py /workdir --measure N OUT.json    # record: every case N times, no expected values
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
import rs_doc_digest  # noqa: E402
from reward_writer import write_rewards  # noqa: E402

DOCS_OBSERVATION = "OBS-DOCS"
OPT = Path("/opt/spec-drift")
VENDOR, PREBUILT, HARNESS_LOCK = OPT / "vendor", OPT / "target", OPT / "harness.lock"
BUILD_BUDGET, CASE_BUDGET, MAX_PASSES = 1200, 900, 3
MAX_RESULT_BYTES = 1024 * 1024
STUB = "#[allow(unused)]\npub fn run() -> crate::prelude::Obs { crate::prelude::Obs(\"null\".into()) }\n"
libc = ctypes.CDLL(None, use_errno=True)


def cargo_config(rustflags):
    """The only cargo configuration the build reads: vendored sources, offline, the repo's trusted
    compiler flags. The image's pre-build writes the same text, so its output is reused."""
    text = (f'[source.crates-io]\nreplace-with = "vendored-sources"\n[source.vendored-sources]\n'
            f'directory = "{VENDOR}"\n[net]\noffline = true\n')
    if rustflags:
        text += "[build]\nrustflags = " + json.dumps(list(rustflags)) + "\n"
    return text


def demoted_limits(fsize, nproc):
    def apply():
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        # PR_SET_NO_NEW_PRIVS: no exec in the child can gain privileges (setuid, file capabilities).
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    return apply


def as_subject(subject, command, *, cwd, env, timeout, stdin=b"", stdout=None, fsize, nproc):
    """Run as the subject uid in a new session; kill the whole group afterwards. (exit code, timed out)."""
    with tempfile.TemporaryFile() as handle:
        handle.write(stdin)
        handle.seek(0)
        child = subprocess.Popen(command, cwd=cwd, env=env, user=subject.pw_uid, group=subject.pw_gid,
                                 extra_groups=[], start_new_session=True, preexec_fn=demoted_limits(fsize, nproc),
                                 stdin=handle, stdout=stdout or subprocess.DEVNULL, stderr=subprocess.STDOUT)
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


def restamp(app):
    """Cargo rebuilds a path crate only when a source is newer than its last build output; the solver
    image stamps every file 2001-01-01. Stamp the whole candidate tree with now (docs/plans/rust.md 4.4)."""
    now = time.time()
    for directory, dirs, files in os.walk(app):
        for name in dirs + files:
            os.utime(os.path.join(directory, name), (now, now), follow_symlinks=False)
    os.utime(app, (now, now))


def write_harness(private, spec, harness, cases, subject):
    templates = private / "harness"
    (harness / "src/cases").mkdir(parents=True)
    (harness / "Cargo.toml").write_text((templates / "Cargo.toml.in").read_text()
                                        .replace("@@DEPENDENCIES@@", spec["dependencies"]))
    if HARNESS_LOCK.is_file():
        shutil.copyfile(HARNESS_LOCK, harness / "Cargo.lock")
    shutil.copyfile(templates / "main.rs", harness / "src/main.rs")
    shutil.copyfile(templates / "prelude.rs", harness / "src/prelude.rs")
    modules, arms = [], []
    for number, case in enumerate(cases, 1):
        name = f"c{number:04d}"
        modules.append(f"pub mod {name};")
        arms.append(f"        {number} => Some({name}::run()),")
        (harness / f"src/cases/{name}.rs").write_text(
            "#![allow(unused)]\nuse crate::prelude::*;\n" + spec["preamble"].rstrip("\n") + "\n"
            + "pub fn run() -> Obs {\n" + case["code"] + "\n}\n")
    (harness / "src/cases/mod.rs").write_text(
        "\n".join(modules) + "\npub fn dispatch(n: usize) -> Option<crate::prelude::Obs> {\n    match n {\n"
        + "\n".join(arms) + "\n        _ => None,\n    }\n}\n")
    for directory, _, files in os.walk(harness):
        os.chmod(directory, 0o755)
        for name in files:
            os.chmod(os.path.join(directory, name), 0o644)
    # cargo rewrites the harness lock only when the candidate's dependencies change; let nobody do so
    # (and resolve one offline when the image ships none). The folder itself stays root-owned.
    (harness / "Cargo.lock").touch()
    os.chown(harness / "Cargo.lock", subject.pw_uid, subject.pw_gid)


def case_of_span(span, harness):
    """The case number a compiler span points at, following macro expansions out to the call site."""
    while span.get("expansion") and span["expansion"].get("span"):
        span = span["expansion"]["span"]
    path = os.path.normpath(os.path.join(harness, str(span.get("file_name", ""))))
    rel = os.path.relpath(path, harness / "src/cases")
    if len(rel) == 8 and rel.startswith("c") and rel.endswith(".rs") and rel[1:5].isdigit():
        return int(rel[1:5])
    return None


def _json_or_none(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def attribute(raw, harness):
    """({case numbers an error points at}, [errors outside every case]) from cargo's JSON messages."""
    cases, foreign = set(), []
    for item in filter(None, map(_json_or_none, raw.splitlines())):
        message = item.get("message")
        if item.get("reason") != "compiler-message" or not isinstance(message, dict) \
                or message.get("level") not in ("error", "error: internal compiler error"):
            continue
        primary = [s for s in message.get("spans") or [] if isinstance(s, dict) and s.get("is_primary")]
        if not primary:
            continue  # "aborting due to N previous errors"
        rendered = str(message.get("rendered", ""))[:500]
        if not str(item.get("package_id", "")).startswith("path+file://" + str(harness)):
            foreign.append(rendered)
            continue
        for span in primary:
            number = case_of_span(span, harness)
            if number is None:
                foreign.append(rendered)
            else:
                cases.add(number)
    return cases, foreign


def build(subject, harness, env, timings):
    """Build as nobody; cut out the cases that do not compile and rebuild (at most MAX_PASSES passes,
    BUILD_BUDGET seconds in all). (stubbed case numbers, failure message or None)."""
    stubbed, started = set(), time.time()
    for attempt in range(1, MAX_PASSES + 1):
        began = time.time()
        with tempfile.TemporaryFile() as out:
            code, timed_out = as_subject(
                subject, [env["CARGO"], "build", "--offline", "--message-format=json",
                          "--manifest-path", str(harness / "Cargo.toml")],
                cwd=str(harness), env=env, timeout=BUILD_BUDGET - (began - started), stdout=out,
                fsize=8 << 30, nproc=4096)
            out.seek(0)
            raw = out.read(64 << 20).decode(errors="replace")
        sweep(subject)  # nothing started at build time survives into the case runs
        compiled = sorted({item["target"].get("name", "") for item in map(_json_or_none, raw.splitlines())
                           if item and item.get("reason") == "compiler-artifact" and not item.get("fresh")
                           and isinstance(item.get("target"), dict)})
        timings.append({"pass": attempt, "seconds": round(time.time() - began, 2), "exit": code,
                        "compiled": [name[:80] for name in compiled[:50]]})  # candidate-chosen names
        if timed_out:
            return stubbed, "the build did not finish within the build budget"
        if code == 0:
            return stubbed, None
        new, foreign = attribute(raw, harness)
        new -= stubbed
        if foreign or not new:
            tail = "\n".join(foreign) or "\n".join(line for line in raw.splitlines()[-40:]
                                                   if not line.startswith("{"))
            return stubbed, "the candidate crate does not build: " + tail[:2000]
        for number in new:
            (harness / f"src/cases/c{number:04d}.rs").write_text(STUB)
        stubbed |= new
    return stubbed, "cases still fail to compile after the last pass"


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


def run_case(subject, binary, scratch, number, timeout):
    case_dir = Path(tempfile.mkdtemp(prefix="c-", dir=scratch))
    os.chown(case_dir, subject.pw_uid, subject.pw_gid)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(case_dir), "TMPDIR": str(case_dir),
           "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC"}
    # The case number travels on stdin; the program and its folder have opaque names.
    code, timed_out = as_subject(subject, [str(binary)], cwd=str(case_dir), env=env, timeout=timeout,
                                 stdin=f"{number}\n".encode(), fsize=MAX_RESULT_BYTES, nproc=256)
    sweep(subject)  # nothing of the case survives to rewrite its result before root reads it
    if timed_out:
        return {"error": "timeout"}
    result = read_result(case_dir)
    return result if result is not None else {"error": f"no-result (exit {code})"}


def observe(app, private, cases, subject, repeats, timings):
    """Build once as nobody, then run every case `repeats` times. [[result per run] per case]."""
    spec = json.loads((private / "harness.json").read_text())
    toolchain = Path(spec["toolchain"])
    began = time.time()
    restamp(app)
    grade.readable_workspace(app)
    timings["restamp_seconds"] = round(time.time() - began, 2)
    root = Path(tempfile.mkdtemp(prefix="grade-"))
    os.chmod(root, 0o755)
    harness, cargo_home, home, target, scratch = (root / n for n in ("h", "cargo-home", "home", "target", "runs"))
    write_harness(private, spec, harness, cases, subject)
    cargo_home.mkdir(mode=0o755)
    (cargo_home / "config.toml").write_text(cargo_config(spec.get("rustflags") or []))
    os.chmod(cargo_home / "config.toml", 0o644)
    for folder in (home, scratch):
        folder.mkdir(mode=0o700)
        os.chown(folder, subject.pw_uid, subject.pw_gid)
    began = time.time()
    if PREBUILT.is_dir():
        shutil.copytree(PREBUILT, target, symlinks=True)
    else:
        target.mkdir()
    for directory, _, files in os.walk(target):
        os.chown(directory, subject.pw_uid, subject.pw_gid)
        for name in files:
            os.chown(os.path.join(directory, name), subject.pw_uid, subject.pw_gid, follow_symlinks=False)
    timings["copy_prebuilt_seconds"] = round(time.time() - began, 2)
    env = {"PATH": f"{toolchain}/bin:/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home),
           "CARGO_HOME": str(cargo_home), "CARGO_TARGET_DIR": str(target), "RUSTC": str(toolchain / "bin/rustc"),
           "RUSTDOC": str(toolchain / "bin/rustdoc"), "CARGO": str(toolchain / "bin/cargo"),
           "CARGO_TERM_COLOR": "never", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC"}
    sweep(subject)
    timings["build_passes"] = []
    stubbed, failure = build(subject, harness, env, timings["build_passes"])
    timings["stubbed_cases"] = sorted(stubbed)
    if failure:
        timings["build_failure"] = failure[:1500]
        return [[{"error": "build"}] * repeats for _ in cases]
    # Root copies (never runs) the program into a root-owned folder, so no case can rewrite it for the next.
    binary_dir = root / "bin"
    binary_dir.mkdir(mode=0o755)
    binary = binary_dir / "p"
    fd = os.open(target / "debug/sdh", os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source, open(binary, "wb") as sink:
        shutil.copyfileobj(source, sink)
    os.chmod(binary, 0o755)
    began = time.time()
    results = [[] for _ in cases]
    for _ in range(repeats):
        for index in range(len(cases)):
            if index + 1 in stubbed:
                results[index].append({"error": "compile"})
                continue
            remaining = CASE_BUDGET * repeats - (time.time() - began)
            if remaining <= 0:
                results[index].append({"error": "timeout"})
                continue
            results[index].append(run_case(subject, binary, scratch, index + 1,
                                           min(spec.get("case_timeout", 30), remaining)))
    timings["case_runs_seconds"] = round(time.time() - began, 2)
    timings["case_runs"] = len(cases) * repeats
    shutil.rmtree(root, ignore_errors=True)
    return results


def preflight(private):
    """The toolchain, the vendored sources and the pre-built output must be root-owned and not writable
    by anyone else: `nobody` builds against them, and the agent must not have been able to plant them."""
    spec = json.loads((private / "harness.json").read_text())
    for tree in (Path(spec["toolchain"]), VENDOR, PREBUILT):
        if tree.exists():
            bad = sealed_tree(tree)
            if bad:
                raise RuntimeError(f"{tree} is not sealed (root-owned, not group/other writable): {bad}")
        elif tree != PREBUILT:
            raise RuntimeError(f"{tree} is missing")


def sealed_lexer(private, scratch):
    """tests/private/rslex after checking it is the pinned build (the image makes it executable and
    root-only; when the upload lost the mode, a root-only copy in `scratch`)."""
    spec = json.loads((private / "harness.json").read_text())
    data = (private / "rslex").read_bytes()
    if hashlib.sha256(data).hexdigest() != spec["rslex_sha256"]:
        raise RuntimeError("tests/private/rslex is not the pinned Rust lexer build")
    if os.access(private / "rslex", os.X_OK):
        return private / "rslex"
    path = Path(scratch) / "rslex"
    path.write_bytes(data)
    os.chmod(path, 0o700)
    return path


def check_documentation(app, private):
    """'intact', or what changed: every baseline page byte-identical (doc_digest) and every baseline
    .rs file keeping its doc comments in order under their owners (rs_doc_digest). Lexing only."""
    baseline = json.loads((private / "documentation.json").read_text())
    pages = documentation_preserved(app, baseline)
    rust = baseline.get("rust_files") or {}
    if not rust:
        return pages
    with tempfile.TemporaryDirectory(prefix="rslex-") as scratch:
        os.chmod(scratch, 0o700)
        changed = rs_doc_digest.changed_files(app, rust, sealed_lexer(private, scratch))
    if pages == "intact" and not changed:
        return "intact"
    return f"{pages if pages != 'intact' else 'pages intact'}; {changed} Rust files changed"


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
    preflight(private)
    # The documentation is checked before any candidate code runs (byte reads only).
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
        "build_failure": timings.get("build_failure"),
        "stubbed_cases": timings.get("stubbed_cases"),
        "observations_expected": len(expected),
        "observations_returned": len(observed),
        "failed_observation_count": sum(1 for passed in outcomes.values() if not passed),
        "partial": str(partial),
    }, indent=2, sort_keys=True))
    return metrics


def measure_main(app, private, repeats, out):
    """The recorder: build the tree at `app` once and run every case `repeats` times (no expected values)."""
    if os.geteuid() != 0:
        raise RuntimeError("measuring requires root (the build and the cases run as nobody)")
    subject = pwd.getpwnam("nobody")
    preflight(private)
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
