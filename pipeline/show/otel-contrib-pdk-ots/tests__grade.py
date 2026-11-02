"""Trusted grader for otel-contrib-pdk-ots.

The expected observations never leave this process. A child running as ``nobody`` reads the case
sources on **stdin** (an ordered list with no identifiers: this parent keeps the identifiers and
maps the returned observations back by position), runs every case in a fresh interpreter that
imports the candidate's own SDK packages (the staged repository's ``packages/`` directory, appended
after the standard library and site-packages), drives the public ``atproto_client`` API with
local fakes at the transport boundary (no network), and writes what it saw to a file.
This parent compares that against the sealed expected values and scores the F2P/P2P groups
declared in ``tests/private_manifest.json``.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from fractions import Fraction

# Python -I excludes the script directory; add only this trusted, root-owned
# verifier directory, never the candidate workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
from reward_writer import write_rewards
from doc_digest import documentation_preserved

MAX_FILE_BYTES = 8 * 1024 * 1024
SKIP_DIRECTORIES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                    ".venv", "venv", ".nox", ".tox"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def seal_check(private, manifest):
    """Refuse to grade when any private byte differs from the sealed inventory."""
    actual = {}
    for path in sorted(private.rglob("*")):
        if path.is_symlink():
            raise ValueError("private assets must not contain symlinks")
        if path.is_dir():
            continue
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("private asset is not a regular file")
        actual[path.relative_to(private).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    declared = manifest["private_files"]
    if actual != declared:
        differences = {
            "missing": sorted(declared.keys() - actual.keys()),
            "unexpected": sorted(actual.keys() - declared.keys()),
            "changed": sorted(name for name in actual.keys() & declared.keys()
                              if actual[name] != declared[name]),
        }
        detail = "; ".join(f"{kind}: {names}" for kind, names in differences.items() if names)
        raise ValueError("private inventory or byte binding changed; " + detail)


MAX_STAGED_ENTRIES = 200000


def _inside(path, root):
    return path == root or path.startswith(root + os.sep)


def _link_target(link, app_real):
    """The fully resolved target of a symlink when it exists and stays inside the workspace.

    None for a dangling or cyclic link (strict resolution fails) and for any link whose final
    target, after every hop, lies outside the workspace (for example /tests, /logs or /etc)."""
    try:
        target = os.path.realpath(link, strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    return target if _inside(target, app_real) else None


def _stage_dir(source, dest, relative, app_real, stack, state):
    """Copy `source` (a real directory) into `dest`, materialising in-workspace symlinks.

    A symlink whose resolved target stays inside the workspace is copied as a regular file
    (its target's bytes) or, for a directory, as a copy of the target's contents. `stack`
    holds the resolved directories being expanded, so a link back to one of them (a cycle) is
    skipped. Anything else that is not a regular file or directory is skipped, as are links
    that dangle, loop or leave the workspace."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        entries = sorted(os.scandir(source), key=lambda entry: entry.name)
    except OSError:
        state["skipped"].append(relative.as_posix() or ".")
        return
    for entry in entries:
        name = relative / entry.name
        if state["entries"] >= MAX_STAGED_ENTRIES:
            state["skipped"].append(name.as_posix())
            continue
        state["entries"] += 1
        if entry.is_symlink():
            target = _link_target(entry.path, app_real)
            if target is None:
                state["skipped"].append(name.as_posix())
                continue
            mode = os.stat(target).st_mode
            if stat.S_ISDIR(mode):
                if entry.name in SKIP_DIRECTORIES or any(
                        target == seen or _inside(seen, target) for seen in stack):
                    state["skipped"].append(name.as_posix())
                    continue
                _stage_dir(target, dest / entry.name, name, app_real, stack + [target], state)
            elif stat.S_ISREG(mode) and os.stat(target).st_size <= MAX_FILE_BYTES:
                shutil.copyfile(target, dest / entry.name)
                state["copied"] += 1
            else:
                state["skipped"].append(name.as_posix())
            continue
        mode = entry.stat(follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            if entry.name in SKIP_DIRECTORIES:
                continue
            _stage_dir(entry.path, dest / entry.name, name, app_real,
                       stack + [os.path.realpath(entry.path)], state)
        elif stat.S_ISREG(mode) and entry.stat(follow_symlinks=False).st_size <= MAX_FILE_BYTES:
            shutil.copyfile(entry.path, dest / entry.name)
            state["copied"] += 1
        else:
            state["skipped"].append(name.as_posix())


def stage_candidate(app, root):
    """Copy the complete candidate worktree, so additions and deletions are both observed.

    Symlinks that resolve to a file or directory inside the workspace are materialised as
    copies (a solver may legitimately organise a repair with in-tree links); links that
    dangle, loop or resolve outside the workspace are skipped and never followed."""
    tree = root / "candidate"
    tree.mkdir(mode=0o755)
    app_real = os.path.realpath(app)
    state = {"copied": 0, "skipped": [], "entries": 0}
    _stage_dir(app_real, tree, Path(""), app_real, [app_real], state)
    for path in [tree, *tree.rglob("*")]:
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    return tree, state["copied"], state["skipped"]


def observe(command, cwd, env, cases, subject, timeout):
    """Run the child under its own uid, with limits and process-group cleanup here."""
    import resource

    def limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))

    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, \
            tempfile.TemporaryFile() as stderr:
        stdin.write(cases.encode())
        stdin.seek(0)
        child = subprocess.Popen(command, cwd=cwd, env=env, user=subject.pw_uid,
                                 group=subject.pw_gid, extra_groups=[], start_new_session=True,
                                 preexec_fn=limit, stdin=stdin, stdout=stdout, stderr=stderr)
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ValueError("observation child timed out") from None
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        stderr.seek(0)
        return child.returncode, stderr.read(4096).decode(errors="replace")


def score(manifest, expected, observed):
    outcomes = {name: name in observed and canonical(observed[name]) == canonical(value)
                for name, value in expected.items()}
    groups = []
    for group in manifest["scoring"]["groups"]:
        missing = [name for name in group["tests"] if name not in outcomes]
        if missing:
            raise ValueError(f"group {group['id']} names unknown observations: {missing}")
        groups.append({"id": group["id"], "kind": group["kind"], "total": len(group["tests"]),
                       "passed": sum(outcomes[name] for name in group["tests"])})
    partitions = [[Fraction(group["passed"], group["total"]) for group in groups
                   if group["kind"] == kind] for kind in ("f2p", "p2p")]
    if not all(partitions):
        raise ValueError("both fault and regression observations are required")
    partial = (sum(partitions[0]) / len(partitions[0])) * (sum(partitions[1]) / len(partitions[1]))
    return partial, groups, outcomes


def grade(app, tests, output):
    if os.geteuid() != 0:
        raise RuntimeError("this grader requires a root verifier; there is no same-uid fallback")
    subject = pwd.getpwnam("nobody")
    os.chmod(tests, 0o700)
    output.mkdir(parents=True, exist_ok=True)
    # Harbor bind-mounts this directory onto the host; keep it traversable but not writable.
    os.chmod(output, 0o755)
    # Keep -1 on infrastructure failure, never a misleading behavioral zero.
    (output / "reward.txt").write_text("-1\n")

    manifest = json.loads((tests / "private_manifest.json").read_text())
    private = tests / "private"
    seal_check(private, manifest)
    expected = json.loads((private / "expected.json").read_text())["observations"]
    cases = json.loads((private / "cases.json").read_text())
    # Only the ordered case sources reach the child; the identifiers stay in this process.
    sources = json.dumps([case["code"] for case in cases])

    # A permission claim is not proof on every mount type: check as the subject uid before
    # any candidate code runs.
    guard = subprocess.run(
        [sys.executable, "-I", "-S", "-c",
         "import os,sys; sys.exit(1 if os.access(sys.argv[1], os.R_OK) else 0)",
         str(private / "expected.json")],
        user=subject.pw_uid, group=subject.pw_gid, extra_groups=[], capture_output=True, timeout=30)
    if guard.returncode:
        raise RuntimeError("the expected observations are readable by the subject uid")

    with tempfile.TemporaryDirectory(prefix="grade-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o755)
        tree, copied, skipped = stage_candidate(app, root)
        # Check the candidate's documentation here, in the trusted parent, before any candidate
        # code runs (ast parsing only, nothing is imported).
        documentation = documentation_preserved(
            tree, json.loads((private / "documentation.json").read_text()))

        scratch = root / "child"
        scratch.mkdir(mode=0o755)
        shutil.copyfile(private / "driver.py", scratch / "driver.py")
        os.chmod(scratch / "driver.py", 0o644)
        results = scratch / "results"
        results.mkdir()
        os.chown(results, subject.pw_uid, subject.pw_gid)
        result_path = results / "observations.json"

        # Empty sitecustomize/usercustomize shims win the lookup if a leftover .pth still
        # appends the candidate-writable workspace after site initialisation.
        shim = scratch / "site-shim"
        shim.mkdir(mode=0o755)
        for name in ("sitecustomize.py", "usercustomize.py"):
            (shim / name).write_text("")
            os.chmod(shim / name, 0o644)

        # Only the shim goes on PYTHONPATH. The driver runs each case in `python -I` and appends the
        # staged candidate's root directory to sys.path itself, after the standard library and
        # site-packages, so a candidate file named like a stdlib module (json.py, traceback.py, ...)
        # can never replace one (ISSUE-394).
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "PYTHONPATH": str(shim),
               "HOME": str(results), "TMPDIR": str(results),
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONHASHSEED": "42", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC"}
        command = [sys.executable, "-s", str(scratch / "driver.py"), str(result_path), str(tree)]
        code, diagnostic = observe(command, scratch, env, sources, subject,
                                   manifest["observation_timeout_seconds"])

        observed = {}
        if code == 0 and result_path.exists():
            mode = result_path.lstat().st_mode
            if not stat.S_ISREG(mode) or result_path.stat().st_size > 16 * 1024**2:
                raise ValueError("unsafe observation result file")
            try:
                payload = json.loads(result_path.read_text())["results"]
                if isinstance(payload, list) and len(payload) == len(cases):
                    observed = {case["id"]: value for case, value in zip(cases, payload)}
            except (ValueError, KeyError, TypeError):
                observed = {}

        observed["OBS-DOCS"] = {"ok": documentation}
        partial, groups, outcomes = score(manifest, expected, observed)
        observations = []
        for name in sorted(expected):
            if name not in observed:
                observations.append({"id": name, "status": "missing",
                                     "detail": "no value returned"})
            elif outcomes[name]:
                observations.append({"id": name, "status": "passed"})
            elif isinstance(observed[name], dict) and "error" in observed[name]:
                observations.append({"id": name, "status": "error",
                                     "detail": "raised an exception"})
            else:
                observations.append({"id": name, "status": "failed",
                                     "detail": "value differs"})
        run = {"child_exit_code": code, "child_stderr_tail": diagnostic[-1000:],
               "candidate_files_copied": copied, "candidate_files_skipped": [name[:120] for name in skipped[:16]],
               "observations_expected": len(expected), "observations_returned": len(observed)}
        metrics = write_rewards(output, partial, groups, observations=observations, run=run)
        (output / "replay.json").write_text(json.dumps({
            "child_exit_code": code,
            "child_stderr": diagnostic,
            "candidate_files_copied": copied,
            "candidate_files_skipped": [name[:120] for name in skipped[:16]],
            "observations_expected": len(expected),
            "observations_returned": len(observed),
            "failed_observation_count": sum(1 for passed in outcomes.values() if not passed),
            "partial": str(partial),
        }, indent=2, sort_keys=True))
        return metrics


if __name__ == "__main__":
    grade(Path(sys.argv[1]), Path(__file__).resolve().parent,
          Path(os.environ.get("MIG_VERIFIER_DIR", "/logs/verifier")))
