"""Trusted grader (spec-drift-ots; ported from the delivered tau-canonical-ots grader).

The expected observations never leave this process. Before any candidate code runs, this root
parent checks every private file against the seals in ``tests/private_manifest.json`` and checks,
as the subject uid, that the expected observations are unreadable. It then checks the candidate's
documentation (ast and byte reads only, nothing is imported).

A child running as ``nobody`` reads the case sources on **stdin** (an ordered list with no
identifiers: this parent keeps the identifiers and maps the returned observations back by
position), runs every case in a fresh interpreter that imports the candidate's own code from
``/workdir`` (after the standard library and site-packages), and writes what it saw to a file. The
child only returns raw values; every comparison is made here, against the sealed expected values
(``close``: floats within a small tolerance, everything else exactly; a raised exception by its class
lineage, so a subclass of the documented exception matches), and the F2P/P2P groups declared in
``tests/private_manifest.json`` are scored here. A missing or malformed observation fails its
check; a self-reported verdict is never read.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import signal
import stat
import subprocess
import sys
import tempfile
from fractions import Fraction

# Python -I excludes the script directory; add only this trusted, root-owned verifier directory,
# never the candidate workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
from reward_writer import write_rewards  # noqa: E402
from doc_digest import documentation_preserved  # noqa: E402

DOCS_OBSERVATION = "OBS-DOCS"
# Floats only. The driver rounds every float to 6 decimals, so a last-digit difference between CPUs
# can move a value by one rounding step (1e-6); the tolerance must stay above that step.
ATOL = 1e-4
RTOL = 1e-4
MAX_LINEAGE = 64
MAX_RESULT_BYTES = 16 * 1024 * 1024
# A negative zero inside text ("-0", "-0.0000", "-0.00E+00"): its sign depends on the host's
# floating-point details (ISSUE-431). Not preceded by a word character or a dot (a hyphen in
# "node-0" or "1-0" is not a sign) and not followed by one ("-0.5" and "-01" are not zeros).
_NEGATIVE_ZERO = re.compile(r"(?<![\w.])-(0(?:\.0+)?(?:[eE][+-]?0+)?)(?![\w.])")


def unsigned_zero(text):
    """`text` with every negative zero written without its sign."""
    return _NEGATIVE_ZERO.sub(r"\1", text)


def _lineage(value):
    """True for an exception observation {"raised": [class names, most specific first]}: what the
    case helpers raised()/attempt() return. A real class lineage is short, names each class once and
    contains BaseException; a list that repeats or omits names is no lineage and matches nothing."""
    if not (isinstance(value, dict) and set(value) == {"raised"} and isinstance(value["raised"], list)):
        return False
    names = value["raised"]
    return (0 < len(names) <= MAX_LINEAGE and all(isinstance(name, str) and name for name in names)
            and len(set(names)) == len(names) and "BaseException" in names)


def _raised_matches(observed, expected):
    """A candidate's exception matches the documented one when it is that class or a subclass of it.

    The child reports only the raw lineage of what was raised; the decision is made here. Python's
    method resolution order keeps every ancestor's own order (C3 monotonicity), so a genuine
    subclass's lineage contains the reference exception's whole lineage, in order. Requiring that
    (not just the class name) rejects an unrelated class that merely shares the documented name."""
    if not _lineage(observed):
        return False
    remaining = iter(observed["raised"])
    return all(name in remaining for name in expected["raised"])


def close(observed, expected):
    """True when an observation matches its expected value (the reference's observation).

    Exact, except where the host decides a detail:
    - integers, booleans, strings, bytes, None and container structure match exactly, and a bool is
      never a number (True is not 1): a grader that accepted 10001 for 10000 would reward wrong
      answers (ISSUE-438). An integer and a float are compared by exact value (60 equals 60.0,
      10001 never equals 10000.0);
    - only a float compared with a float has a tolerance, |a - b| <= ATOL + RTOL * |b|, so a
      last-digit difference between CPUs never decides a case;
    - a negative zero equals zero, also inside text (ISSUE-431);
    - an exception observation matches the documented class or any subclass of it.
    Non-finite floats arrive as the strings "nan", "inf" and "-inf"."""
    if _lineage(expected):
        return _raised_matches(observed, expected)
    if isinstance(expected, bool) or expected is None:
        return type(observed) is type(expected) and observed == expected
    if isinstance(expected, (int, float)):
        if type(observed) not in (int, float):
            return False
        if type(observed) is int or type(expected) is int:
            return observed == expected
        if not (math.isfinite(observed) and math.isfinite(expected)):
            return False
        return abs(observed - expected) <= ATOL + RTOL * abs(expected)
    if isinstance(expected, str):
        return isinstance(observed, str) and unsigned_zero(observed) == unsigned_zero(expected)
    if isinstance(expected, list):
        return (isinstance(observed, list) and len(observed) == len(expected)
                and all(close(o, e) for o, e in zip(observed, expected)))
    if isinstance(expected, dict):
        return (isinstance(observed, dict) and set(observed) == set(expected)
                and all(close(observed[key], expected[key]) for key in expected))
    return False


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


# Never kept on a workspace file: set-user/group-id bits (the upload makes every file root-owned,
# so a setuid bit the agent set would hand the subject uid root) and group/other write.
STRIPPED_BITS = stat.S_ISUID | stat.S_ISGID | 0o022


def readable_workspace(app):
    """Make the uploaded workspace readable (never writable) by the subject uid, without following
    symlinks: a candidate's umask or modes must not decide whether its own code can be imported."""
    for directory, subdirectories, names in os.walk(app):
        for name in subdirectories + names:
            path = os.path.join(directory, name)
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode):
                continue
            os.chmod(path, (stat.S_IMODE(mode) | (0o555 if stat.S_ISDIR(mode) else 0o444)) & ~STRIPPED_BITS)
    mode = os.lstat(app).st_mode
    os.chmod(app, (stat.S_IMODE(mode) | 0o555) & ~STRIPPED_BITS)


def observe(command, cwd, env, cases, subject, timeout):
    """Run the child under its own uid, with limits and process-group cleanup here."""
    import ctypes
    import resource

    libc = ctypes.CDLL(None, use_errno=True)

    def limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT_BYTES, MAX_RESULT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
        # PR_SET_NO_NEW_PRIVS: no exec in the child can gain privileges (setuid, file capabilities).
        # A demotion that cannot be made complete fails the run instead of grading with more privilege.
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")

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


def read_observations(result_path, cases):
    """The child's observations by case id, or {} when there are none to trust.

    The results folder belongs to the subject uid, so candidate code can put anything at this path.
    A symlink, a non-regular file or an oversized file is the candidate's doing, never a grader
    fault: it means no observations (every case fails, a behavioural 0), not -1, which stays
    reserved for a broken grader (grade_rs.read_result reads each case's file the same way)."""
    try:
        fd = os.open(result_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return {}
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESULT_BYTES:
        os.close(fd)
        return {}
    with os.fdopen(fd, "rb") as handle:
        try:
            payload = json.loads(handle.read())["results"]
        except (ValueError, KeyError, TypeError):
            return {}
    if isinstance(payload, list) and len(payload) == len(cases):
        return {case["id"]: value for case, value in zip(cases, payload)}
    return {}


def score(manifest, expected, observed):
    outcomes = {name: name in observed and close(observed[name], value)
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
    if subject.pw_uid == 0:
        raise RuntimeError("the subject uid must not be root")
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

    # A permission claim is not proof on every mount type: check as the subject uid before any
    # candidate code runs.
    guard = subprocess.run(
        [sys.executable, "-I", "-S", "-c",
         "import os,sys; sys.exit(1 if os.access(sys.argv[1], os.R_OK) else 0)",
         str(private / "expected.json")],
        user=subject.pw_uid, group=subject.pw_gid, extra_groups=[], capture_output=True, timeout=30)
    if guard.returncode:
        raise RuntimeError("the expected observations are readable by the subject uid")

    # The candidate's documentation is checked here, in the trusted parent, before any candidate
    # code runs (ast parsing and byte reads only, nothing is imported).
    documentation = documentation_preserved(
        app, json.loads((private / "documentation.json").read_text()))
    readable_workspace(app)

    with tempfile.TemporaryDirectory(prefix="grade-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o755)
        scratch = root / "child"
        scratch.mkdir(mode=0o755)
        (scratch / "driver.py").write_bytes((private / "driver.py").read_bytes())
        os.chmod(scratch / "driver.py", 0o644)
        results = scratch / "results"
        results.mkdir()
        os.chown(results, subject.pw_uid, subject.pw_gid)
        result_path = results / "observations.json"
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": str(results), "TMPDIR": str(results),
               "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC"}
        command = [sys.executable, "-I", "-S", "-B", str(scratch / "driver.py"), str(result_path), str(app),
                   "--sweep"]
        code, diagnostic = observe(command, scratch, env, sources, subject,
                                   manifest["observation_timeout_seconds"])

        observed = read_observations(result_path, cases) if code == 0 else {}

    observed[DOCS_OBSERVATION] = {"ok": documentation}
    partial, groups, outcomes = score(manifest, expected, observed)
    observations = []
    for name in sorted(expected):
        if name not in observed:
            observations.append({"id": name, "status": "missing"})
        elif outcomes[name]:
            observations.append({"id": name, "status": "passed"})
        elif isinstance(observed[name], dict) and "error" in observed[name]:
            observations.append({"id": name, "status": "error",
                                 "detail": str(observed[name].get("error"))[:100]})
        else:
            observations.append({"id": name, "status": "failed"})
    run = {"child_exit_code": code, "child_stderr_tail": diagnostic[-1000:],
           "documentation": documentation if documentation == "intact" else "changed",
           "observations_expected": len(expected), "observations_returned": len(observed)}
    metrics = write_rewards(output, partial, groups, observations=observations, run=run)
    (output / "replay.json").write_text(json.dumps({
        "child_exit_code": code,
        "observations_expected": len(expected),
        "observations_returned": len(observed),
        "failed_observation_count": sum(1 for passed in outcomes.values() if not passed),
        "partial": str(partial),
    }, indent=2, sort_keys=True))
    return metrics


if __name__ == "__main__":
    grade(Path(sys.argv[1]), Path(__file__).resolve().parent,
          Path(os.environ.get("SPEC_DRIFT_VERIFIER_DIR", "/logs/verifier")))
