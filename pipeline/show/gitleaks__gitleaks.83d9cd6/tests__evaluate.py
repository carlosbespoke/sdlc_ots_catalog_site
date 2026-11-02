#!/usr/bin/env python3
"""Run branch tests inside a Harbor verifier."""

from __future__ import annotations

import hashlib
import hmac
import json
import mmap
import os
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


WORKSPACE = Path("/workspace")
# A separate verifier runs in its own container, so the agent's workspace
# arrives as a collected artifact rather than as a live directory.
ARTIFACT_WORKSPACE = Path("/logs/artifacts/workspace")
VERIFIER_IMAGE_MARKER = Path("/etc/task-verifier")
REFERENCE_EXECUTABLE = Path("/opt/task-reference/executable")
ORACLE_AUTH_PATH = WORKSPACE / "oracle-auth-token"
ORACLE_AUTH_SHA256 = "64a2cd0109619b79cf0ef28b9a2ba7b8fe0b1c4cfe643f35bd47b77139a72024"
TESTS_DIR = Path("/tests")
BRANCHES_DIR = TESTS_DIR / "branches"
LOG_DIR = Path("/logs/verifier")
RESULT_PATH = LOG_DIR / "eval.json"
REWARD_PATH = LOG_DIR / "reward.txt"
METRICS_PATH = LOG_DIR / "metrics.json"
COMPILE_TIMEOUT_SEC = 900
UNTRUSTED_UID = 65534
UNTRUSTED_GID = 65534
COMPILE_HOME = Path("/tmp/task-compile-home")
BRANCH_SIGNAL_RETRIES = 2
# 128 + N is a shell's report of death by signal N.
_SIGNAL_RETURN_CODES = frozenset({139, 134, 132, 136, -11, -6, -4, -8})
BRANCH_TIMEOUT_SEC = 3600
PROJECT_FILE_EXCLUDED_ROOTS = frozenset(
    {
        ".cache",
        ".git",
        ".venv",
        "assets",
        "build",
        "dist",
        "docs",
        "node_modules",
        "target",
    }
)
SOURCE_TEXT_SAMPLE_BYTES = 64 * 1024


def _is_oracle_mode() -> bool:
    try:
        supplied = hashlib.sha256(ORACLE_AUTH_PATH.read_bytes()).hexdigest()
    except OSError:
        return False
    ORACLE_AUTH_PATH.unlink(missing_ok=True)
    return hmac.compare_digest(supplied, ORACLE_AUTH_SHA256)


def _remove_reference_for_candidate(oracle_mode: bool) -> bool:
    """Remove the verifier-only reference before untrusted build code runs."""

    if oracle_mode:
        return False
    existed = REFERENCE_EXECUTABLE.exists() or REFERENCE_EXECUTABLE.is_symlink()
    REFERENCE_EXECUTABLE.unlink(missing_ok=True)
    return existed


def _active_expected(branch: dict[str, Any]) -> list[str]:
    ignored = {
        str(item.get("name", ""))
        for item in branch.get("ignored_tests", [])
        if isinstance(item, dict)
    }
    return [
        str(name)
        for name in branch.get("tests", [])
        if str(name) not in ignored
    ]


def _ignored_names(branch_id: str, branch: dict[str, Any]) -> set[str]:
    return {
        f"{branch_id}/{item.get('name', '')}"
        for item in branch.get("ignored_tests", [])
        if isinstance(item, dict)
    }


def _not_run(
    branch_id: str,
    branch: dict[str, Any],
    error_code: str,
) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "branch": branch_id,
            "status": "not_run",
            "extra": {"error_code": error_code},
        }
        for name in _active_expected(branch)
    ]


def _clear_directory(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
    untrusted: bool = False,
) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            preexec_fn=_drop_privileges if untrusted and os.geteuid() == 0 else None,
        )
        return completed.returncode, completed.stdout, time.monotonic() - started
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return 124, output, time.monotonic() - started


def _drop_privileges() -> None:
    """Run candidate-controlled code without access to verifier-owned files."""

    os.setgroups([])
    os.setgid(UNTRUSTED_GID)
    os.setuid(UNTRUSTED_UID)


def _kill_untrusted_processes() -> None:
    """Stop every process the candidate's build or program left running."""

    if os.geteuid() != 0:
        return
    pid = os.fork()
    if pid == 0:
        try:
            _drop_privileges()
            os.kill(-1, signal.SIGKILL)
        finally:
            os._exit(0)
    os.waitpid(pid, 0)


def _secure_log_dir() -> None:
    """Harbor creates /logs/verifier world-writable; keep candidate code out."""

    if os.geteuid() == 0:
        os.chown(LOG_DIR, 0, 0)
    LOG_DIR.chmod(0o755)


def _give_workspace_to_untrusted() -> None:
    """Make only the submitted workspace and compile home candidate-writable."""

    COMPILE_HOME.mkdir(parents=True, exist_ok=True)
    for root in (WORKSPACE, COMPILE_HOME):
        for path in [root, *root.rglob("*")]:
            try:
                os.chown(path, UNTRUSTED_UID, UNTRUSTED_GID, follow_symlinks=False)
            except OSError:
                continue


def _lock_verifier_inputs() -> None:
    """Make hidden tests unreadable and unwritable by candidate processes."""

    for path in [TESTS_DIR, *TESTS_DIR.rglob("*")]:
        try:
            path.chmod(0o700 if path.is_dir() else 0o600)
        except OSError:
            continue


def _compile_environment() -> dict[str, str]:
    """Give the isolated builder private writable caches for every toolchain."""

    environment = dict(os.environ)
    environment.update(
        {
            "HOME": COMPILE_HOME.as_posix(),
            "XDG_CACHE_HOME": (COMPILE_HOME / ".cache").as_posix(),
            "XDG_CONFIG_HOME": (COMPILE_HOME / ".config").as_posix(),
            "GOCACHE": (COMPILE_HOME / "go-build").as_posix(),
            "GOMODCACHE": (COMPILE_HOME / "go-mod").as_posix(),
            "GOPATH": (COMPILE_HOME / "go").as_posix(),
            "GOTELEMETRY": "off",
            "CARGO_HOME": (COMPILE_HOME / "cargo").as_posix(),
            "PIP_CACHE_DIR": (COMPILE_HOME / "pip").as_posix(),
            "CCACHE_DIR": (COMPILE_HOME / "ccache").as_posix(),
        }
    )
    return environment


def _run_compile_offline(
    compile_script: Path,
    *,
    untrusted: bool,
) -> tuple[int, str, float]:
    resolv_conf = Path("/etc/resolv.conf")
    backup = resolv_conf.read_bytes()
    try:
        resolv_conf.write_text("nameserver 0.0.0.0\n")
        if resolv_conf.read_text().strip() != "nameserver 0.0.0.0":
            raise RuntimeError("failed to block DNS during compile")
        return _run(
            [str(compile_script)],
            cwd=WORKSPACE,
            timeout=COMPILE_TIMEOUT_SEC,
            env=_compile_environment(),
            untrusted=untrusted,
        )
    finally:
        resolv_conf.write_bytes(backup)


def _import_submitted_workspace() -> bool:
    """Materialize the submitted project if it arrives under the artifacts root.

    A separate verifier is normally handed the collected workspace at
    `/workspace` already, and a shared verifier grades the agent's own
    `/workspace`, so neither case needs this. It stays as a fallback for
    a host that delivers the artifact under the artifacts root instead.
    """

    if not ARTIFACT_WORKSPACE.is_dir():
        return False
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    _clear_directory(WORKSPACE)
    for item in sorted(ARTIFACT_WORKSPACE.iterdir()):
        target = WORKSPACE / item.name
        if item.is_dir() and not item.is_symlink():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target, follow_symlinks=False)
    return True


def _archive_compiled_workspace(destination: Path) -> None:
    """Save the complete build so relative executable symlinks stay valid."""

    with tarfile.open(destination, "w:gz") as archive:
        archive.add(WORKSPACE, arcname=".")


def _restore_compiled_workspace(source: Path) -> None:
    """Restore one clean copy of the complete candidate build."""

    _clear_directory(WORKSPACE)
    with tarfile.open(source, "r:gz") as archive:
        # Debian bookworm's Python predates extraction filters. The archive is
        # created by this verifier from an already materialized workspace, not
        # supplied as attacker-controlled tar bytes.
        archive.extractall(WORKSPACE)


def _record_executable(executable: Path) -> tuple[bool, str | None]:
    """Record the built executable without making provenance claims."""

    executable_present = executable.is_file()
    executable_hash = None
    if executable_present:
        executable_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    return executable_present, executable_hash


def _is_probable_source_input(path: Path) -> bool:
    """Return whether a candidate file can contain portable source text."""

    try:
        with path.open("rb") as stream:
            sample = stream.read(SOURCE_TEXT_SAMPLE_BYTES)
    except OSError:
        return False
    if not sample or b"\0" in sample:
        return False
    try:
        return bool(sample.decode("utf-8").strip())
    except UnicodeDecodeError:
        return False


def _submitted_source_files() -> list[str]:
    """List nonempty candidate project files delivered before compilation.

    ProgramBench permits any implementation language. File extensions therefore
    cannot decide whether a submission contains source. Source is portable text,
    including an extensionless file or the build script itself. Exclude binary
    blobs, the built executable, generated directories, documentation, and assets.
    """

    sources = []
    for path in WORKSPACE.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            continue
        relative = path.relative_to(WORKSPACE)
        if (
            relative == Path("executable")
            or relative.parts[0] in PROJECT_FILE_EXCLUDED_ROOTS
        ):
            continue
        if _is_probable_source_input(path):
            sources.append(relative.as_posix())
    return sorted(sources)


def _files_containing_reference(reference: bytes) -> list[str]:
    """Find renamed, appended, or raw embedded copies of the reference."""

    if not reference:
        return []
    matches: list[str] = []
    for path in WORKSPACE.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size < len(reference):
                continue
            with path.open("rb") as stream:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                    if data.find(reference) < 0:
                        continue
        except (OSError, ValueError):
            continue
        matches.append(path.relative_to(WORKSPACE).as_posix())
    return sorted(matches)


def _result_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _parse_junit(
    xml_path: Path,
    branch_id: str,
    branch: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    root = ET.fromstring(xml_path.read_text(errors="replace"))
    parsed: list[dict[str, Any]] = []
    for case in root.iter():
        if _result_tag(case) != "testcase":
            continue
        case_name = case.get("name") or ""
        class_name = case.get("classname") or ""
        name = f"{class_name}.{case_name}" if class_name else case_name
        if not name:
            continue
        result_children = [
            child
            for child in case
            if _result_tag(child) in {"skipped", "failure", "error"}
        ]
        extra: dict[str, Any] = {}
        if case.get("time") is not None:
            extra["time"] = case.get("time")
        result_types = [_result_tag(child) for child in result_children]
        if not result_children:
            status = "passed"
        elif len(result_children) > 1 and len(set(result_types)) > 1:
            status = "system_error"
            extra["error_details"] = (
                f"expected one result child, got {result_types}"
            )
        else:
            status = result_types[0]
            child = result_children[0]
            if (
                status == "failure"
                and child.get("type") == "candidate_crash"
            ):
                status = "candidate_crash"
            if child.get("message"):
                extra["message"] = child.get("message")
            for attribute in (
                "type",
                "signal",
                "signal_number",
                "attempts",
            ):
                if child.get(attribute) is not None:
                    extra[attribute] = child.get(attribute)
            if child.text:
                extra["text"] = child.text
        parsed.append(
            {
                "name": name,
                "branch": branch_id,
                "status": status,
                "extra": extra,
            }
        )

    ignored = _ignored_names(branch_id, branch)
    filtered = [
        item
        for item in parsed
        if f"{branch_id}/{item['name']}" not in ignored
    ]
    got = {item["name"] for item in parsed}
    missing = [
        name for name in _active_expected(branch) if name not in got
    ]
    filtered.extend(
        {
            "name": name,
            "branch": branch_id,
            "status": "not_run",
            "extra": {"error_code": "missing_from_junit_xml"},
        }
        for name in missing
    )
    warnings: list[str] = []
    expected = {str(name) for name in branch.get("tests", [])}
    ignored_raw = {
        str(item.get("name", ""))
        for item in branch.get("ignored_tests", [])
        if isinstance(item, dict)
    }
    unexpected = got - expected - ignored_raw
    if unexpected:
        warnings.append(
            f"branch {branch_id} returned {len(unexpected)} unexpected tests"
        )
    return filtered, warnings


def _write_result(result: dict[str, Any]) -> None:
    _kill_untrusted_processes()
    # Harbor prefers reward.json over reward.txt; only this script may decide.
    (LOG_DIR / "reward.json").unlink(missing_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    tests = result["test_results"]
    status_counts: dict[str, int] = {}
    for item in tests:
        status = str(item.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    passed = sum(item["status"] == "passed" for item in tests)
    partial = passed / len(tests) if tests else 0.0
    reward = partial
    REWARD_PATH.write_text(f"{reward}\n")
    METRICS_PATH.write_text(
        json.dumps(
            {
                "candidate_crashes": status_counts.get(
                    "candidate_crash", 0
                ),
                "non_passing_tests": len(tests) - passed,
                "partial_score": partial,
                "passed_tests": passed,
                "reward": reward,
                "status_counts": status_counts,
                "total_tests": len(tests),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (LOG_DIR / "partial-score.json").write_text(
        json.dumps(
            {"partial_score": partial},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _write_log_if_nonempty(path: Path, output: str) -> bool:
    """Keep useful command output without creating empty log artifacts."""

    path.unlink(missing_ok=True)
    if not output:
        return False
    path.write_text(output)
    return True


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _secure_log_dir()
    imported_workspace = _import_submitted_workspace()
    tests_data = json.loads((TESTS_DIR / "tests.json").read_text())
    manifest = json.loads((TESTS_DIR / "blob-manifest.json").read_text())
    branches = tests_data.get("branches", {})
    active_branches = [
        (str(branch_id), branch)
        for branch_id, branch in branches.items()
        if isinstance(branch, dict) and not branch.get("ignored", False)
    ]
    result: dict[str, Any] = {
        "test_results": [],
        "error_code": None,
        "error_details": None,
        "log": [],
        "verifier_container": (
            "separate" if VERIFIER_IMAGE_MARKER.is_file() else "agent"
        ),
        "imported_artifact_workspace": imported_workspace,
        "artifact_roots": sorted(
            path.as_posix()
            for path in Path("/logs/artifacts").glob("*")
        ) if Path("/logs/artifacts").is_dir() else [],
        "workspace_entries": sorted(
            path.name for path in WORKSPACE.glob("*")
        ) if WORKSPACE.is_dir() else [],
        "solution_branch": "harbor",
        "test_branches": [branch_id for branch_id, _ in active_branches],
        "test_branch_errors": {},
        "executable_hash": None,
        "warnings": [],
    }

    oracle_mode = _is_oracle_mode()
    result["oracle_mode"] = oracle_mode
    reference_bytes = (
        REFERENCE_EXECUTABLE.read_bytes()
        if not oracle_mode and REFERENCE_EXECUTABLE.is_file()
        else b""
    )
    reference_removed = _remove_reference_for_candidate(oracle_mode)
    result["log"].append(
        {
            "step": "remove_verifier_reference",
            "oracle_mode": oracle_mode,
            "removed": reference_removed,
        }
    )

    expected_blobs = {
        item["branch"]: item
        for item in manifest.get("branches", [])
    }
    for branch_id, _ in active_branches:
        archive = BRANCHES_DIR / f"{branch_id}.tar.gz"
        entry = expected_blobs.get(branch_id)
        if entry is None or not archive.is_file():
            raise RuntimeError(f"missing test blob for branch {branch_id}")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            raise RuntimeError(f"test blob hash mismatch for branch {branch_id}")
    _lock_verifier_inputs()

    stale_executable = WORKSPACE / "executable"
    stale_executable.unlink(missing_ok=True)

    copied_reference_files = _files_containing_reference(reference_bytes)
    if copied_reference_files:
        result["error_code"] = "reference_artifact_submitted"
        result["error_details"] = (
            "submission contains reference executable bytes: "
            + ", ".join(copied_reference_files)
        )
        result["log"].append(
            {"step": "reference_artifact_scan", "files": copied_reference_files}
        )
        for branch_id, branch in active_branches:
            result["test_results"].extend(
                _not_run(branch_id, branch, "reference_artifact_submitted")
            )
        _write_result(result)
        return

    compile_script = WORKSPACE / "compile.sh"
    if not compile_script.is_file():
        result["error_code"] = "compile_script_missing"
        result["error_details"] = "compile.sh was not created"
        for branch_id, branch in active_branches:
            result["test_results"].extend(
                _not_run(branch_id, branch, "compile_script_missing")
            )
        _write_result(result)
        return

    source_files = _submitted_source_files()
    result["source_files"] = source_files
    if not oracle_mode and not source_files:
        result["error_code"] = "source_files_missing"
        result["error_details"] = (
            "submission must include at least one nonempty source file before compile"
        )
        for branch_id, branch in active_branches:
            result["test_results"].extend(
                _not_run(branch_id, branch, "source_files_missing")
            )
        _write_result(result)
        return

    compile_script.chmod(compile_script.stat().st_mode | 0o111)
    if not oracle_mode:
        _give_workspace_to_untrusted()
    return_code, output, wall_time = _run_compile_offline(
        compile_script,
        untrusted=not oracle_mode,
    )
    _kill_untrusted_processes()
    (LOG_DIR / "compile.log").write_text(output)
    result["log"].append(
        {
            "step": "compile",
            "returncode": return_code,
            "wall_time": wall_time,
        }
    )

    executable_present, executable_hash = _record_executable(stale_executable)
    result["executable_hash"] = executable_hash

    copied_reference_files = _files_containing_reference(reference_bytes)
    if copied_reference_files:
        result["error_code"] = "reference_artifact_submitted"
        result["error_details"] = (
            "compiled workspace contains reference executable bytes: "
            + ", ".join(copied_reference_files)
        )
        result["log"].append(
            {"step": "reference_artifact_scan", "files": copied_reference_files}
        )
        for branch_id, branch in active_branches:
            result["test_results"].extend(
                _not_run(branch_id, branch, "reference_artifact_submitted")
            )
        _write_result(result)
        return

    if return_code != 0 or not executable_present:
        error_code = (
            "compile_timeout" if return_code == 124 else "compile_failed"
        )
        if return_code == 0:
            error_code = "executable_missing"
        result["error_code"] = error_code
        result["error_details"] = output[-4000:]
        for branch_id, branch in active_branches:
            result["test_results"].extend(
                _not_run(branch_id, branch, error_code)
            )
        _write_result(result)
        return

    temporary = Path(tempfile.mkdtemp(prefix="task-verifier-"))
    compiled_workspace = temporary / "compiled-workspace.tar.gz"
    _archive_compiled_workspace(compiled_workspace)

    if oracle_mode:
        # Test programs run as nobody even for the trusted oracle. Keep the
        # verifier-only binary execute-only while allowing directory traversal.
        REFERENCE_EXECUTABLE.parent.chmod(0o711)
        REFERENCE_EXECUTABLE.chmod(0o111)

    base_env = dict(os.environ)
    base_env["PYTEST_XDIST_AUTO_NUM_WORKERS"] = str(
        max(1, os.cpu_count() or 1)
    )
    base_env["PYTEST_ADDOPTS"] = "--max-worker-restart=4"

    for branch_id, branch in active_branches:
        try:
            _restore_compiled_workspace(compiled_workspace)
            branch_root = Path(tempfile.mkdtemp(
                prefix=f"task-branch-{branch_id}-",
            ))
            with tarfile.open(
                BRANCHES_DIR / f"{branch_id}.tar.gz",
                "r:gz",
            ) as archive:
                archive.extractall(branch_root)
            run_script = branch_root / "eval" / "run.sh"
            results_xml = branch_root / "eval" / "results.xml"
            results_xml.unlink(missing_ok=True)
            if not run_script.is_file():
                raise RuntimeError("eval/run.sh is missing")
            run_script.write_text(
                run_script.read_text().replace(
                    "--timeout-method=thread",
                    "--timeout-method=signal",
                )
            )
            run_script.chmod(run_script.stat().st_mode | 0o111)
            return_code, output, wall_time = _run(
                [str(run_script)],
                cwd=branch_root,
                timeout=BRANCH_TIMEOUT_SEC,
                env=base_env,
            )
            # A branch runner killed by a signal produced no verdicts at
            # all, so every test in it would be recorded as not run. That
            # is a host failure rather than a result, and emulated hosts
            # produce it, so the branch is retried before it counts.
            attempts = 1
            while (
                return_code in _SIGNAL_RETURN_CODES
                and not results_xml.is_file()
                and attempts <= BRANCH_SIGNAL_RETRIES
            ):
                attempts += 1
                return_code, output, wall_time = _run(
                    [str(run_script)],
                    cwd=branch_root,
                    timeout=BRANCH_TIMEOUT_SEC,
                    env=base_env,
                )
            _write_log_if_nonempty(LOG_DIR / f"{branch_id}.log", output)
            result["log"].append(
                {
                    "step": "run_tests",
                    "branch": branch_id,
                    "returncode": return_code,
                    "attempts": attempts,
                    "wall_time": wall_time,
                }
            )
            if not results_xml.is_file():
                raise RuntimeError(
                    "test run did not create eval/results.xml"
                )
            branch_results, warnings = _parse_junit(
                results_xml,
                branch_id,
                branch,
            )
            result["test_results"].extend(branch_results)
            result["warnings"].extend(warnings)
        except Exception as error:
            error_code = type(error).__name__
            result["test_branch_errors"].setdefault(branch_id, []).append(
                {
                    "error_code": error_code,
                    "error_details": str(error),
                }
            )
            result["test_results"].extend(
                _not_run(branch_id, branch, error_code)
            )
        finally:
            if "branch_root" in locals():
                shutil.rmtree(branch_root, ignore_errors=True)
                del branch_root

    _write_result(result)


if __name__ == "__main__":
    main()
