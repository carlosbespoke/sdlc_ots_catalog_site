#!/usr/bin/env python3
"""dbmigrate verifier: grade a submitted repository's migrations against real database servers.

Runs in the separate verifier container as root (test.sh). Builds the production snapshot and the hidden-salt snapshot
from the task's schema and dataset (or reuses prebuilt ones from DBM_SNAPSHOTS), then runs every scenario in
scenario.json against private server processes, with the submission's migration tool executed as the unprivileged
OS user `solver`. Writes /logs/verifier/reward.txt, reward.json (numeric only) and metrics.json.

Environment (all optional): DBM_TESTS (default: this file's directory), DBM_SUBMISSION (default: the artifact path in
scenario.json), DBM_WORK, DBM_LOGS, DBM_SNAPSHOTS, DBM_MODE (grade|record), DBM_EXPECTED_OUT (record mode output),
DBM_PORT, DBM_FAST_FAIL=1, DBM_ONLY=scenario,scenario.
"""
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dbm_core import Runner, write_metrics  # noqa: E402
from dbm_snapshot import build, make_engine  # noqa: E402
from dbm_util import is_root, say, user_ids  # noqa: E402


def build_snapshots(sc, tests, work, port, server_user, names):
    snaps = work / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    recipe = sc.get("recipe") or []
    files = tests / "snapshot"
    for name in names:
        info = sc["snapshots"][name]
        out = snaps / name
        if out.exists():
            continue
        t0 = time.time()
        db = sc["database"]
        eng = make_engine(sc["engine"], work / f"build-{name}", port, server_user, db["name"], db["role"],
                          db["password"])
        try:
            build(eng, info.get("recipe", recipe), files, files / "dataset.py", info["salt"], info["variant"], out)
        finally:
            eng.stop()
            shutil.rmtree(work / f"build-{name}", ignore_errors=True)
        say(f"snapshot {name} ready in {time.time() - t0:.0f}s")
    return snaps


def main():
    tests = Path(os.environ.get("DBM_TESTS", HERE))
    sc = json.loads((tests / "scenario.json").read_text())
    sub = Path(os.environ.get("DBM_SUBMISSION", sc["artifact"]))
    work = Path(os.environ.get("DBM_WORK", "/tmp/dbm-grade"))
    logs = Path(os.environ.get("DBM_LOGS", "/logs/verifier"))
    mode = os.environ.get("DBM_MODE", "grade")
    port = int(os.environ.get("DBM_PORT", "5432" if sc["engine"] == "postgres16" else "3306"))
    only = [x for x in os.environ.get("DBM_ONLY", "").split(",") if x] or None
    server_user = sc.get("server_user", "postgres" if sc["engine"] == "postgres16" else "mysql")
    if is_root() and not user_ids(server_user):
        server_user = "nobody"
    solver_user = "solver" if is_root() else None
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o755)
    expected = {}
    if mode == "grade":
        expected = json.loads((tests / "expected.json").read_text())
    extra = {"engine": sc["engine"], "tool": sc["tool"], "task_type": sc["task_type"]}
    t0 = time.time()
    try:
        needed = sorted({s["snapshot"] for s in sc["scenarios"] if not only or s["name"] in only})
        snaps = Path(os.environ["DBM_SNAPSHOTS"]) if os.environ.get("DBM_SNAPSHOTS") else \
            build_snapshots(sc, tests, work, port, server_user, needed)
        runner = Runner(sc, tests / "repo", sub, work / "run", snaps, mode=mode, expected=expected, port=port,
                        server_user=server_user, solver_user=solver_user,
                        fast_fail={"1": True, "core": "core"}.get(os.environ.get("DBM_FAST_FAIL", ""), False), only=only)
        grading = runner.run()
    except Exception as exc:  # an infrastructure fault: never a graded result
        traceback.print_exc()
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "grading.json").write_text(json.dumps({"error": f"{type(exc).__name__}: {exc}"[:2000]}))
        if mode == "record":
            raise
        sys.exit(3)
    extra["seconds"] = round(time.time() - t0)
    if mode == "record":
        out = Path(os.environ.get("DBM_EXPECTED_OUT", work / "expected.json"))
        out.write_text(json.dumps(runner.recorded, indent=1, sort_keys=True))
        say(f"recorded {len(runner.recorded)} expected outputs -> {out}")
    write_metrics(grading, logs, extra)


if __name__ == "__main__":
    main()
