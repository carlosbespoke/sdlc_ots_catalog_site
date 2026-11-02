#!/usr/bin/env python3
"""Build a production snapshot (a stopped database cluster) from a task's schema files and dataset generator.

The same code runs in three places with the same inputs, so all three hold the same database:
  - the agent container's healthcheck (root, before the agent starts): the snapshot the solver works against;
  - the verifier (test.sh): the visible snapshot plus a second one from the hidden salt;
  - iacctl build (author image): to record the reference results.
usage: dbm_snapshot.py --engine E --recipe recipe.json --files DIR --dataset dataset.py --salt S --variant V
                       --out DIR --root WORKDIR [--port N] [--os-user USER] [--db NAME --role R --password P]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dbm_util import load_module, say  # noqa: E402


def make_engine(kind, root, port, os_user, db, role, password):
    from dbm_util import is_root, user_ids
    if is_root() and not os_user:  # a database server never runs as root
        os_user = next((u for u in (("postgres", "dbm") if kind == "postgres16" else ("mysql", "dbm"))
                        if user_ids(u)), "nobody")
    if kind == "postgres16":
        from dbm_pg import PgEngine
        return PgEngine(root, port=port, os_user=os_user, db=db, role=role, password=password)
    if kind == "mysql84":
        from dbm_mysql import MySqlEngine
        return MySqlEngine(root, port=port, os_user=os_user, db=db, role=role, password=password)
    raise RuntimeError(f"engine {kind!r} has no adapter yet (implemented: postgres16, mysql84)")


def load_dataset(engine, dataset_path, salt, variant, scale=1.0, only=None):
    from dbm_data import Context
    mod = load_module(dataset_path, f"dataset_{abs(hash((str(dataset_path), salt))) % 10**8}")
    ctx = Context(salt, variant, scale)
    counts = {}
    for table in mod.generate(ctx):
        if only and table.name not in only:
            continue
        t0 = time.time()
        counts[table.name] = engine.load_rows(table.name, table.columns, table.rows)
        say(f"snapshot: {table.name}: {counts[table.name]} rows ({time.time() - t0:.1f}s)")
    return counts


def liquibase_runner(engine, step, files, contexts="mysql"):
    """Recipe step {"op": "liquibase", "release": DIR}: `liquibase update` with the changelog as it was deployed at
    that release (a directory under the snapshot files), as the application account."""
    from dbm_tools import LiquibaseTool
    import shutil as _sh
    import tempfile as _tf
    work = Path(_tf.mkdtemp(prefix="dbm-lb-"))
    try:
        repo = work / "repo"
        _sh.copytree(Path(files) / step["release"], repo)
        tool = LiquibaseTool(repo, engine, {"changelog": step.get("changelog", "db/changelog/db.changelog-master.xml"),
                                            "contexts": step.get("contexts", contexts)}, None)
        res = tool.migrate(None)
        if not res.ok:
            raise RuntimeError(f"liquibase update of {step['release']} failed: {res.output[-1500:]}")
    finally:
        _sh.rmtree(work, ignore_errors=True)


def build(engine, recipe, files, dataset, salt, variant, out, tool_runner=None, scale=1.0):
    """Run the recipe against a fresh cluster and save it to `out`. Recipe steps:
       {"op": "sql", "file": F, "as": "app"|"admin"}  run an SQL file
       {"op": "dataset"}                              load the dataset's tables
       {"op": "finish"}                               sequences past their max ids, freeze, analyze
       {"op": "tool", ...}                            run the migration tool (repair recipes; needs tool_runner)"""
    files = Path(files)
    engine.initdb()
    engine.start()
    engine.create_app()
    counts = {}
    for step in recipe:
        op = step["op"]
        if op == "sql":
            engine.psql_file(files / step["file"], as_app=step.get("as", "app") == "app")
        elif op == "dataset":
            counts.update(load_dataset(engine, dataset, salt, variant, scale, step.get("tables")))
        elif op == "finish":
            engine.finish_load()
        elif op == "liquibase":
            liquibase_runner(engine, step, files)
        elif op == "tool":
            if tool_runner is None:
                raise RuntimeError("recipe step 'tool' needs a tool runner")
            tool_runner(engine, step)
        else:
            raise RuntimeError(f"unknown recipe op {op!r}")
    engine.save(out)
    (Path(str(out) + ".json")).write_text(json.dumps({"salt_variant": variant, "rows": counts}, indent=1))
    return counts


def main():
    ap = argparse.ArgumentParser()
    for a in ("engine", "recipe", "files", "dataset", "variant", "out", "root"):
        ap.add_argument(f"--{a}", required=True)
    ap.add_argument("--salt", default=None)
    ap.add_argument("--salt-file", default=None)
    ap.add_argument("--port", type=int, default=5432)
    ap.add_argument("--os-user", default=None)
    ap.add_argument("--db", default="app")
    ap.add_argument("--role", default="app")
    ap.add_argument("--password", default="app")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    salt = a.salt if a.salt is not None else Path(a.salt_file).read_text().strip()
    eng = make_engine(a.engine, a.root, a.port, a.os_user, a.db, a.role, a.password)
    recipe = json.loads(Path(a.recipe).read_text())
    t0 = time.time()
    try:
        counts = build(eng, recipe, a.files, a.dataset, salt, a.variant, a.out, scale=a.scale)
    except Exception:
        eng.stop()
        raise
    say(f"snapshot {a.variant} built in {time.time() - t0:.0f}s: {sum(counts.values())} rows in {len(counts)} tables")


if __name__ == "__main__":
    main()
