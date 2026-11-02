#!/usr/bin/env python3
"""Unprivileged grader, entered after the shared-container phase transition."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import time
import traceback
from pathlib import Path

from correctness_contract import isolated_retry_test
from score_contract import (
    WORKLOAD_MAX_TIME_RATIO,
    ALLOCATION_CLUSTER_RELATIVE_TOLERANCE,
    ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS,
    CONTROL_WORKLOAD,
    MAX_ALLOCATION_RATE_SPREAD,
    MIN_ALLOCATION_CLUSTER_SAMPLES,
    OPTIMIZED_WORKLOADS,
    TIME_SIGNIFICANCE_ALPHA,
    score,
)
from source_contract import candidate_copy_ignore, changed_sources, scan_violation
from evidence_contract import MEASURED_INPUTS, measured_rows, measured_snapshot
from measurement_contract import retryable_measurement_verdict

TESTS_DIR = Path("/tests")
WORKSPACE = Path("/app")
TRUSTED_BASELINE = Path("/opt/baseline")
SOLUTION_PATCH = TESTS_DIR / "opt" / "solution.patch"
WORKLOAD_FILE = TESTS_DIR / "workloads" / "zstd_opt_verifier_test.go"
MEASURE = json.loads((TESTS_DIR / "opt" / "measure.json").read_text())
CONFIG = json.loads((TESTS_DIR / "config.json").read_text())

SCRATCH = Path("/var/lib/fasthttp-verifier/work/grade")
BASE_REPO = SCRATCH / "baseline"
CAND_REPO = SCRATCH / "candidate"
EXPERT_REPO = SCRATCH / "expert"
BIN_DIR = SCRATCH / "bin"
SANDBOX_ROOT = Path("/var/lib/fasthttp-verifier/work/sandbox")
LOGS_DIR = Path("/logs/verifier")

GO = "/usr/local/go/bin/go"
GIT = "/usr/bin/git"
LANDLOCK = "/usr/local/bin/landlock-exec"
SOURCE_SCAN = "/usr/local/bin/fasthttp-source-scan"
SAFE_PATH = "/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE_ENV = {
    "PATH": SAFE_PATH,
    "HOME": str(SCRATCH / "home"),
    "LANG": "C.UTF-8",
    "GOTOOLCHAIN": "local",
    "GOFLAGS": "-mod=readonly -buildvcs=false",
    "GOPROXY": "off",
    "GOWORK": "off",
    "GOENV": "off",
    "GOPATH": "/go",
    "GOMODCACHE": "/go/pkg/mod",
    "GOCACHE": str(SCRATCH / "gocache"),
    "GOMAXPROCS": str(MEASURE["gomaxprocs"]),
    "GOTELEMETRY": "off",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}
WORKLOADS = (*OPTIMIZED_WORKLOADS, CONTROL_WORKLOAD)
LAUNCHES = int(MEASURE["launches"])
BENCHTIME = str(MEASURE["benchtime"])
BENCHMARK_GOMAXPROCS = int(MEASURE["benchmark_gomaxprocs"])
MAX_FULL_COHORT_RETRIES = int(MEASURE["max_full_cohort_retries"])
_PHASE = "init"


class CandidateFailure(RuntimeError):
    pass


def phase(name: str) -> None:
    global _PHASE
    _PHASE = name
    print(f"PHASE={name}", flush=True)


def run(cmd, *, cwd=None, env=None, timeout=600):
    command = [str(part) for part in cmd]
    if command and command[0] == GIT:
        command = [GIT, "-c", "safe.directory=*", "-c", "core.hooksPath=/dev/null", *command[1:]]
    started = time.monotonic()
    proc = subprocess.run(
        command, cwd=cwd, env=env or BASE_ENV,
        text=True, capture_output=True, timeout=timeout,
    )
    proc.wall_seconds = time.monotonic() - started
    return proc


def must(cmd, *, cwd=None, timeout=600):
    proc = run(cmd, cwd=cwd, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed rc={proc.returncode}: {' '.join(str(x) for x in cmd)}\n"
            f"{(proc.stdout + proc.stderr)[-1200:]}"
        )
    return proc


def sandbox_run(side: str, cmd, *, cwd: Path, timeout=600, record_path: Path | None = None):
    runtime = SANDBOX_ROOT / side
    runtime.mkdir(parents=True, exist_ok=True)
    for child in ("home", "cache", "tmp"):
        (runtime / child).mkdir(exist_ok=True)
    env = {
        **BASE_ENV,
        "HOME": str(runtime / "home"),
        "GOCACHE": str(runtime / "cache"),
        "TMPDIR": str(runtime / "tmp"),
        "GOTMPDIR": str(runtime / "tmp"),
    }
    if record_path is not None:
        env["ZSTD_OPT_RECORD"] = str(record_path)
    policy = []
    for path in (
        cwd, Path("/usr"), Path("/bin"), Path("/lib"), Path("/lib64"),
        Path("/etc"), Path("/go"), Path("/dev"),
        Path(cmd[0]),
        Path("/proc/sys/net/core/somaxconn"),
    ):
        if path.exists():
            policy += ["--ro", str(path)]
    policy += ["--rw", str(runtime)]
    if Path("/dev/null").exists():
        policy += ["--rw", "/dev/null"]
    return run([LANDLOCK, *policy, "--", *cmd], cwd=cwd, env=env, timeout=timeout)


def run_recorded(side: str, command, repo: Path, label: str):
    """Use a fresh channel for every invocation and retain the raw record.

    Landlock protects other sides and final verdict paths. Write authority for
    this in-process harness also relies on source capability restrictions.
    """
    record_path = SANDBOX_ROOT / side / "records" / f"{label}.jsonl"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    if record_path.exists() or record_path.is_symlink():
        raise RuntimeError("refusing to reuse a metric record path")
    proc = sandbox_run(side, command, cwd=repo, timeout=120, record_path=record_path)
    record_process(label, proc)
    if proc.returncode != 0:
        if side == "candidate":
            raise CandidateFailure(f"candidate measurement failed: {label}")
        raise RuntimeError(f"{side} measurement failed: {label}")
    if not record_path.is_file() or record_path.is_symlink() or record_path.stat().st_size > 16 * 1024 * 1024:
        raise RuntimeError(f"missing or unsafe harness record: {label}")
    text = record_path.read_text()
    (LOGS_DIR / f"{label}.records.jsonl").write_text(text)
    return proc, text


def finish(reward: float | None, status: str, detail: dict, *, solver_failure: bool) -> None:
    if reward is not None:
        reward = 1.0 if reward == 1 else 0.0
    body = {
        "reward": reward,
        "status": status,
        "count_as_solver_failure": solver_failure,
        "phase": _PHASE,
        **detail,
    }
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    reward_file = LOGS_DIR / "reward.txt"
    if reward is None:
        reward_file.unlink(missing_ok=True)
    else:
        reward_file.write_text(f"{reward:.6f}\n")
    (LOGS_DIR / "result.json").write_text(json.dumps(body, indent=2))
    print(f"STATUS={status} REWARD={reward}", flush=True)
    print(f"DETAIL={json.dumps(body)[:12000]}", flush=True)
    raise SystemExit(2 if reward is None else 0)


def record_process(label: str, proc) -> None:
    (LOGS_DIR / f"{label}.log").write_text(proc.stdout + proc.stderr)
    (LOGS_DIR / f"{label}.json").write_text(json.dumps({
        "exit_code": proc.returncode, "wall_seconds": proc.wall_seconds,
    }, indent=2))


def validate_workspace() -> None:
    if not (WORKSPACE / "zstd.go").is_file() or not (WORKSPACE / "go.mod").is_file():
        raise CandidateFailure("artifact is not the fasthttp source tree")
    file_count = 0
    byte_count = 0
    for path in WORKSPACE.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise CandidateFailure(f"symbolic links are not permitted: {path.relative_to(WORKSPACE)}")
        if stat.S_ISREG(info.st_mode):
            file_count += 1
            byte_count += info.st_size
        elif not stat.S_ISDIR(info.st_mode):
            raise CandidateFailure(f"unsupported filesystem entry: {path.relative_to(WORKSPACE)}")
    if file_count > 5000 or byte_count > 200 * 1024 * 1024:
        raise CandidateFailure("artifact exceeds verifier file or size limits")


def copy_candidate() -> None:
    shutil.copytree(WORKSPACE, CAND_REPO, ignore=candidate_copy_ignore)
    if (CAND_REPO / "go.mod").read_bytes() != (BASE_REPO / "go.mod").read_bytes():
        raise CandidateFailure("go.mod changes are outside this task")
    if not (CAND_REPO / "go.sum").is_file() or (CAND_REPO / "go.sum").read_bytes() != (BASE_REPO / "go.sum").read_bytes():
        raise CandidateFailure("go.sum changes are outside this task")


def validate_source_contract() -> None:
    phase("source-contract")
    changed, error = changed_sources(BASE_REPO, CAND_REPO)
    if error:
        raise CandidateFailure(error)
    base = must([SOURCE_SCAN, BASE_REPO])
    candidate = must([SOURCE_SCAN, CAND_REPO])
    error = scan_violation(json.loads(base.stdout), json.loads(candidate.stdout), changed)
    if error:
        raise CandidateFailure(error)
    (LOGS_DIR / "source-contract.json").write_text(json.dumps({
        "passed": True, "changed_sources": sorted(changed),
    }, indent=2))


def make_scratch_writable(root: Path) -> None:
    """Only scratch copies are writable; sealed verifier inputs stay read-only."""
    root.chmod(root.stat().st_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    for path in root.rglob("*"):
        mode = path.stat().st_mode | stat.S_IRUSR | stat.S_IWUSR
        if path.is_dir():
            mode |= stat.S_IXUSR
        path.chmod(mode)


def restore_tests(repo: Path) -> None:
    for path in repo.rglob("*_test.go"):
        path.unlink()
    for source in TRUSTED_BASELINE.rglob("*_test.go"):
        relative = source.relative_to(TRUSTED_BASELINE)
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for source in (TESTS_DIR / "workloads").glob("*_test.go"):
        shutil.copy2(source, repo / source.name)


def derive_trees() -> None:
    phase("derive-trees")
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)
    SCRATCH.mkdir(parents=True)
    BIN_DIR.mkdir()
    shutil.copytree(TRUSTED_BASELINE, BASE_REPO)
    make_scratch_writable(BASE_REPO)
    copy_candidate()
    validate_source_contract()
    shutil.copytree(BASE_REPO, EXPERT_REPO)
    make_scratch_writable(EXPERT_REPO)
    must([GIT, "apply", "--check", SOLUTION_PATCH], cwd=EXPERT_REPO)
    must([GIT, "apply", SOLUTION_PATCH], cwd=EXPERT_REPO)
    for repo in (BASE_REPO, CAND_REPO, EXPERT_REPO):
        restore_tests(repo)


def correctness() -> None:
    phase("correctness")
    command = [GO, "test", "-p=1", "./...", "-skip", "^(TestDialerGetDialFunc|TestDialerGetDialFuncForTLSNoProxy)$", "-count=1", "-timeout=300s"]
    for side, repo in (("base", BASE_REPO), ("expert", EXPERT_REPO), ("candidate", CAND_REPO)):
        correctness_repo = SANDBOX_ROOT / side / "correctness-src"
        correctness_repo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(repo, correctness_repo)
        make_scratch_writable(correctness_repo)
        proc = sandbox_run(side, command, cwd=correctness_repo, timeout=360)
        record_process(f"{side}-correctness", proc)
        if proc.returncode != 0:
            output = proc.stdout + proc.stderr
            retry_test = isolated_retry_test(output)
            if retry_test is not None:
                attempts = []
                for attempt in range(1, 3):
                    retry_command = [
                        GO, "test", ".", "-run", f"^{retry_test}$",
                        "-count=1", "-timeout=60s",
                    ]
                    retry = sandbox_run(
                        side, retry_command, cwd=correctness_repo, timeout=90,
                    )
                    label = f"{side}-correctness-retry-{attempt}"
                    record_process(label, retry)
                    attempts.append({
                        "attempt": attempt,
                        "exit_code": retry.returncode,
                        "wall_seconds": retry.wall_seconds,
                    })
                    if retry.returncode == 0:
                        (LOGS_DIR / f"{side}-correctness-recovery.json").write_text(
                            json.dumps({
                                "recovered": True,
                                "test": retry_test,
                                "initial_exit_code": proc.returncode,
                                "attempts": attempts,
                            }, indent=2)
                        )
                        break
                else:
                    (LOGS_DIR / f"{side}-correctness-recovery.json").write_text(
                        json.dumps({
                            "recovered": False,
                            "test": retry_test,
                            "initial_exit_code": proc.returncode,
                            "attempts": attempts,
                        }, indent=2)
                    )
                    raise RuntimeError(
                        f"{side} known upstream correctness race persisted "
                        f"through {len(attempts)} isolated retries"
                    )
                continue
            if side == "candidate":
                finish(0, "correctness_failed", {"error": output[-1600:]}, solver_failure=True)
            raise RuntimeError(f"{side} sandbox correctness failed: {output[-1200:]}")


def compile_binaries() -> dict[str, Path]:
    phase("compile")
    binaries = {side: BIN_DIR / f"{side}.test" for side in ("base", "candidate", "expert")}
    for side, repo in (("base", BASE_REPO), ("expert", EXPERT_REPO)):
        proc = run([GO, "test", "-c", "-o", binaries[side], "."], cwd=repo)
        record_process(f"{side}-compile", proc)
        if proc.returncode != 0:
            raise RuntimeError(f"{side} benchmark compilation failed")
    candidate_binary = SANDBOX_ROOT / "candidate" / "candidate.test"
    proc = sandbox_run("candidate", [GO, "test", "-c", "-o", candidate_binary, "."], cwd=CAND_REPO)
    record_process("candidate-compile", proc)
    if proc.returncode != 0:
        finish(0, "correctness_failed", {"error": (proc.stdout + proc.stderr)[-1600:]}, solver_failure=True)
    binaries["candidate"] = candidate_binary
    return binaries


def differential_correctness(binaries: dict[str, Path]) -> dict:
    phase("differential-correctness")
    snapshots = {}
    for side, repo in (("base", BASE_REPO), ("expert", EXPERT_REPO), ("candidate", CAND_REPO)):
        command = [binaries[side], "-test.run=^TestZstdOptDifferentialSnapshot$", "-test.v"]
        proc, text = run_recorded(side, command, repo, f"{side}-differential")
        snapshots[side] = measured_snapshot(text)
        if side == "base":
            continue
        expected = snapshots["base"]
        actual = snapshots[side]
        if [row["id"] for row in actual] != [row["id"] for row in expected]:
            raise RuntimeError(f"{side} differential case coverage mismatch")
        differences = [want["id"] for want, got in zip(expected, actual) if want != got]
        if differences:
            if side == "candidate":
                raise CandidateFailure(f"candidate differs from baseline: {differences[:12]}")
            raise RuntimeError(f"expert differs from baseline: {differences[:12]}")
    detail = {"passed": True, "cases_per_side": len(snapshots["base"]), "differences": 0}
    (LOGS_DIR / "differential-result.json").write_text(json.dumps(detail, indent=2))
    return detail


def measure(binaries: dict[str, Path], *, attempt: int) -> dict:
    phase("measure")
    samples = {side: {name: [] for name in WORKLOADS} for side in binaries}
    orders = (
        ("base", "candidate", "expert"),
        ("candidate", "expert", "base"),
        ("expert", "base", "candidate"),
    )
    for launch in range(LAUNCHES):
        for side in orders[launch % len(orders)]:
            # Correctness ran in a different process. Do not warm caches with a
            # pre-pass over measured inputs. The timed loop checks every result.
            command = [binaries[side], "-test.run=^$", "-test.bench", "^BenchmarkZstdOpt", f"-test.benchtime={BENCHTIME}", "-test.benchmem", "-test.count=1", f"-test.cpu={BENCHMARK_GOMAXPROCS}"]
            repo = {"base": BASE_REPO, "candidate": CAND_REPO, "expert": EXPERT_REPO}[side]
            label = f"{side}-benchmark-{launch + 1}"
            if attempt > 1:
                label = f"{side}-benchmark-attempt-{attempt}-{launch + 1}"
            proc, text = run_recorded(side, command, repo, label)
            rows = measured_rows(text, WORKLOADS, proc.wall_seconds,
                                 benchmark_gomaxprocs=BENCHMARK_GOMAXPROCS)
            for name, row in rows.items():
                samples[side][name].append(row)
    return samples


def verify_configuration() -> None:
    if LAUNCHES != 10 or BENCHTIME != f"{MEASURED_INPUTS}x" or MEASURE["optimized_workloads"] != list(OPTIMIZED_WORKLOADS):
        raise RuntimeError("measure.json and score contract disagree")
    if MEASURE.get("measured_inputs_per_workload") != MEASURED_INPUTS:
        raise RuntimeError("measured input count mismatch")
    if BENCHMARK_GOMAXPROCS != 1:
        raise RuntimeError("single-thread benchmark runtime mismatch")
    if MAX_FULL_COHORT_RETRIES != 1:
        raise RuntimeError("measurement retry contract mismatch")
    if MEASURE["control_workload"] != CONTROL_WORKLOAD:
        raise RuntimeError("control workload mismatch")
    expected = {
        "min_allocation_recovery": 0.75,
        "max_optimized_time_ratio": 0.85,
        "max_control_time_ratio": 1.2,
        "time_significance_alpha": TIME_SIGNIFICANCE_ALPHA,
    }
    for key, value in expected.items():
        if MEASURE.get(key) != value:
            raise RuntimeError(f"threshold mismatch: {key}")
    if MEASURE.get("workload_max_time_ratio", {}) != WORKLOAD_MAX_TIME_RATIO:
        raise RuntimeError("per-workload time ratio mismatch")
    if MEASURE.get("allocation_rate") != "raw_mallocs_divided_by_measured_inputs":
        raise RuntimeError("allocation-rate contract mismatch")
    if MEASURE.get("allocation_estimator") != "median_of_dominant_raw_malloc_cluster":
        raise RuntimeError("allocation-estimator contract mismatch")
    if MEASURE.get("allocation_cluster_tolerance_raw_mallocs") != ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS:
        raise RuntimeError("allocation-cluster tolerance mismatch")
    if MEASURE.get("allocation_cluster_relative_tolerance") != ALLOCATION_CLUSTER_RELATIVE_TOLERANCE:
        raise RuntimeError("allocation-cluster relative tolerance mismatch")
    if MEASURE.get("allocation_min_cluster_samples") != MIN_ALLOCATION_CLUSTER_SAMPLES:
        raise RuntimeError("allocation-cluster size mismatch")
    if MAX_ALLOCATION_RATE_SPREAD != ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS / MEASURED_INPUTS:
        raise RuntimeError("allocation-comparison tolerance mismatch")
    if MEASURE.get("timing_statistical_test") != "exact_one_sided_mann_whitney_permutation":
        raise RuntimeError("timing-test contract mismatch")
    tree = must([GIT, "rev-parse", "HEAD^{tree}"], cwd=TRUSTED_BASELINE).stdout.strip()
    if tree != CONFIG["base_tree"]:
        raise RuntimeError(f"trusted baseline tree mismatch: {tree}")


def main() -> None:
    if os.geteuid() != 1001 or os.getegid() != 1001 or os.getgroups():
        raise RuntimeError("grading must run as isolated uid/gid 1001 with no supplementary groups")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    verify_configuration()
    validate_workspace()
    derive_trees()
    correctness()
    binaries = compile_binaries()
    differential = differential_correctness(binaries)
    measurement_attempts = []
    for attempt in range(1, MAX_FULL_COHORT_RETRIES + 2):
        samples = measure(binaries, attempt=attempt)
        (LOGS_DIR / f"samples-attempt-{attempt}.json").write_text(
            json.dumps(samples, indent=2)
        )
        verdict = score({"correctness_passed": True, "samples": samples})
        measurement_attempts.append({
            "attempt": attempt,
            "status": verdict["status"],
            "score": verdict["score"],
            "reasons": verdict["reasons"],
        })
        if not retryable_measurement_verdict(verdict):
            break
    (LOGS_DIR / "measurement-attempts.json").write_text(
        json.dumps(measurement_attempts, indent=2)
    )
    (LOGS_DIR / "samples.json").write_text(json.dumps(samples, indent=2))
    if verdict["score"] is None:
        finish(None, "verifier_error", {"error": verdict["reasons"], "threshold_status": MEASURE["status"]}, solver_failure=False)
    finish(verdict["score"], verdict["status"], {
        "score_detail": verdict, "threshold_status": MEASURE["status"],
        "correctness_passed": True, "differential": differential,
        "excluded_test": "(TestDialerGetDialFunc|TestDialerGetDialFuncForTLSNoProxy)",
    }, solver_failure=verdict["score"] == 0)


if __name__ == "__main__":
    try:
        main()
    except CandidateFailure as exc:
        finish(0, "correctness_failed", {"error": str(exc)}, solver_failure=True)
    except SystemExit:
        raise
    except Exception as exc:
        finish(None, "verifier_error", {"error": str(exc), "traceback": traceback.format_exc()[-4000:]}, solver_failure=False)
