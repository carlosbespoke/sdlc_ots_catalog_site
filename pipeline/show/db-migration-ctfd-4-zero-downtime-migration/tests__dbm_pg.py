"""PostgreSQL 16 engine adapter: a private cluster per scenario (a plain server process, no Docker), snapshot build and
restore, the app role's connections, a normalized catalog, and the lock evidence the zero-downtime rules are judged on
(csvlog statements with DEBUG1 evidence, event-trigger DDL records, relfilenodes, xmin batch sizes)."""
import csv
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from dbm_util import chown_tree, debug, is_root, norm_value, qident, run, say, tail, wait_for

PGBIN = Path(os.environ.get("DBM_PGBIN", "/usr/lib/postgresql/16/bin"))
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "dbm_audit")

TYPE_ALIASES = {
    "int": "integer", "int4": "integer", "int8": "bigint", "int2": "smallint", "serial": "integer",
    "bigserial": "bigint", "bool": "boolean", "float8": "double precision", "float4": "real",
    "timestamptz": "timestamp with time zone", "timestamp": "timestamp without time zone",
    "timetz": "time with time zone", "time": "time without time zone", "varchar": "character varying",
    "char": "character", "decimal": "numeric",
}


def norm_type(t):
    """Canonical PostgreSQL type spelling (format_type style) for a spec's type string."""
    t = re.sub(r"\s+", " ", (t or "").strip().lower())
    m = re.match(r"^([a-z0-9_ ]+?)\s*(\(.*\))?(\[\])?$", t)
    if not m:
        return t
    base, args, arr = m.group(1).strip(), (m.group(2) or "").replace(" ", ""), m.group(3) or ""
    base = TYPE_ALIASES.get(base, base)
    if base == "timestamp without time zone" and args:
        base, args = "timestamp", args
        return f"timestamp{args} without time zone{arr}"
    if base == "timestamp with time zone" and args:
        return f"timestamp{args} with time zone{arr}"
    return f"{base}{args}{arr}"


# fixed rendering for content checksums (the database's own defaults, e.g. a TimeZone, must not matter)
RENDER_SETTINGS = {"TimeZone": "UTC", "DateStyle": "ISO, MDY", "IntervalStyle": "postgres", "extra_float_digits": "1",
                   "bytea_output": "hex"}


class PgEngine:
    kind = "postgres16"
    superuser = "postgres"

    def __init__(self, root, port=5432, os_user=None, db="app", role="app", password="app"):
        self.root = Path(root)
        self.port = int(port)
        self.os_user = os_user if is_root() else None
        self.db, self.role, self.password = db, role, password
        self.data = self.root / "data"
        self.sock = self.root / "sock"
        self.logdir = self.root / "log"
        self._log_pos = 0
        self.running = False
        # lock-judged scenarios decode every committed row change (logical decoding) to measure transaction sizes
        self.decode_writes = False

    # ---- cluster lifecycle ------------------------------------------------------------------------------------------
    def _prep_dirs(self):
        for d in (self.root, self.sock, self.logdir):
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(self.sock, 0o700)
        chown_tree(self.root, self.os_user)

    def initdb(self):
        self._prep_dirs()
        if self.data.exists():
            shutil.rmtree(self.data)
        p = run([str(PGBIN / "initdb"), "-D", str(self.data), "-U", self.superuser, "-E", "UTF8", "--locale=C.UTF-8",
                 "--auth-local=trust", "--auth-host=scram-sha-256", "--no-sync"], user=self.os_user, timeout=300)
        if p.returncode != 0:
            raise RuntimeError(f"initdb failed: {tail(p.stdout + p.stderr)}")
        self.configure()

    def configure(self):
        conf = self.data / "postgresql.auto.conf"
        conf.write_text("\n".join([
            "# dbmigrate private cluster",
            "listen_addresses = '127.0.0.1'",
            f"port = {self.port}",
            f"unix_socket_directories = '{self.sock}'",
            "unix_socket_permissions = 0700",
            "max_connections = 60",
            "shared_buffers = '256MB'",
            "maintenance_work_mem = '128MB'",
            "fsync = off", "synchronous_commit = off", "full_page_writes = off",
            ("wal_level = logical" if self.decode_writes else "wal_level = minimal"), "max_wal_senders = 0",
            ("max_replication_slots = 2" if self.decode_writes else "max_replication_slots = 0"), "max_wal_size = '2GB'",
            "autovacuum = off",
            "logging_collector = on", "log_destination = 'csvlog'", f"log_directory = '{self.logdir}'",
            "log_filename = 'pg.log'", "log_rotation_age = 0", "log_rotation_size = 0", "log_file_mode = 0600",
            "log_min_messages = warning", "log_timezone = 'UTC'", "timezone = 'UTC'", "datestyle = 'iso, mdy'",
            "lc_messages = 'C'", "max_locks_per_transaction = 256", "jit = off",
            "",
        ]))
        (self.data / "pg_hba.conf").write_text(
            "local all postgres trust\n"
            "local all all reject\n"
            "host all postgres 0.0.0.0/0 reject\n"
            "host all postgres ::/0 reject\n"
            "host all all 127.0.0.1/32 scram-sha-256\n")
        chown_tree(self.data, self.os_user)

    def start(self, timeout=180):
        self._prep_dirs()
        p = run([str(PGBIN / "pg_ctl"), "-D", str(self.data), "-w", "-t", str(timeout), "-l",
                 str(self.root / "start.log"), "start"], user=self.os_user, timeout=timeout + 30)
        if p.returncode != 0:
            log = (self.root / "start.log").read_text(errors="replace") if (self.root / "start.log").exists() else ""
            raise RuntimeError(f"postgres did not start: {tail(p.stdout + p.stderr + log)}")
        self.running = True
        self._log_pos = 0

    def stop(self):
        if not self.data.exists():
            return
        run([str(PGBIN / "pg_ctl"), "-D", str(self.data), "-m", "fast", "-w", "-t", "120", "stop"],
            user=self.os_user, timeout=180)
        self.running = False

    def save(self, dest):
        """Copy the stopped cluster's data directory to dest (a snapshot)."""
        self.stop()
        dest = Path(dest)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.data, dest, symlinks=True)

    def restore(self, src):
        """Replace the data directory with a copy of a snapshot and reconfigure it for this engine's port/paths."""
        self.stop()
        if self.data.exists():
            shutil.rmtree(self.data)
        self._prep_dirs()
        shutil.copytree(src, self.data, symlinks=True)
        for stale in ("postmaster.pid", "postmaster.opts"):
            (self.data / stale).unlink(missing_ok=True)
        self.configure()
        os.chmod(self.data, 0o700)
        chown_tree(self.root, self.os_user)
        if self.logdir.exists():
            for f in self.logdir.iterdir():
                f.unlink()

    # ---- connections ------------------------------------------------------------------------------------------------
    def admin(self, db=None, autocommit=True):
        import psycopg
        return psycopg.connect(host=str(self.sock), port=self.port, user=self.superuser, dbname=db or self.db,
                               autocommit=autocommit, connect_timeout=20)

    def app(self, autocommit=True):
        import psycopg
        return psycopg.connect(host="127.0.0.1", port=self.port, user=self.role, password=self.password,
                               dbname=self.db, autocommit=autocommit, connect_timeout=20)

    def tool_url(self, scheme="postgresql+psycopg"):
        return f"{scheme}://{self.role}:{self.password}@127.0.0.1:{self.port}/{self.db}"

    def env_for_tools(self):
        return {"PGHOST": "127.0.0.1", "PGPORT": str(self.port), "PGUSER": self.role, "PGDATABASE": self.db,
                "PGPASSWORD": self.password}

    def migrate_url(self):
        """golang-migrate's connection URL (the application role)."""
        return f"postgres://{self.role}:{self.password}@127.0.0.1:{self.port}/{self.db}?sslmode=disable"

    def jdbc_url(self):
        return f"jdbc:postgresql://127.0.0.1:{self.port}/{self.db}"

    def query_rows(self, sql):
        """Rows of one query as the superuser, None when it fails (e.g. the table does not exist yet)."""
        try:
            with self.admin() as c:
                return [tuple(r) for r in c.execute(sql).fetchall()]
        except Exception:  # noqa: BLE001
            return None

    def create_app(self):
        from psycopg import sql
        with self.admin(db="postgres") as c:
            c.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(self.role), sql.Literal(self.password)))
            c.execute(f"CREATE DATABASE {qident(self.db)} OWNER {qident(self.role)} TEMPLATE template0 "
                      f"ENCODING 'UTF8' LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8'")
        with self.admin() as c:
            c.execute(f"ALTER SCHEMA public OWNER TO {qident(self.role)}")

    def psql_file(self, path, as_app=True, timeout=900):
        """Run an SQL script with psql (stops at the first error)."""
        if as_app:
            cmd = [str(PGBIN / "psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p", str(self.port),
                   "-U", self.role, "-d", self.db, "-f", str(path)]
            env = {"PGPASSWORD": self.password}
        else:
            cmd = [str(PGBIN / "psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-h", str(self.sock), "-p",
                   str(self.port), "-U", self.superuser, "-d", self.db, "-f", str(path)]
            env = {}
        # psql runs as the caller (root in the containers; it reaches the 0700 socket directory and reads the
        # root-only snapshot files), never as the server's user
        p = run(cmd, env=env, timeout=timeout)
        if p.returncode != 0:
            raise RuntimeError(f"psql {Path(path).name} failed: {tail(p.stdout + p.stderr, 15)}")

    def load_rows(self, table, columns, rows):
        from dbm_data import pg_copy_value
        cols = ", ".join(qident(c) for c in columns)
        n = 0
        with self.admin() as c:
            with c.cursor() as cur:
                with cur.copy(f"COPY {qident(table)} ({cols}) FROM STDIN") as cp:
                    buf = []
                    for row in rows:
                        buf.append("\t".join(pg_copy_value(v) for v in row))
                        n += 1
                        if len(buf) >= 5000:
                            cp.write("\n".join(buf) + "\n")
                            buf = []
                    if buf:
                        cp.write("\n".join(buf) + "\n")
        return n

    def finish_load(self):
        """After a bulk load: move every owned sequence past its column's maximum, then freeze and analyze."""
        with self.admin() as c:
            seqs = c.execute("""
                SELECT s.relname, t.relname, a.attname
                FROM pg_class s JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i')
                JOIN pg_class t ON t.oid = d.refobjid JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
                JOIN pg_namespace n ON n.oid = s.relnamespace
                WHERE s.relkind = 'S' AND n.nspname NOT IN ('pg_catalog', 'information_schema')""").fetchall()
            for seq, table, col in seqs:
                mx = c.execute(f"SELECT max({qident(col)}) FROM {qident(table)}").fetchone()[0]
                if mx is not None:
                    c.execute("SELECT setval(%s::regclass, %s)", (qident(seq), int(mx)))
            c.execute("VACUUM (FREEZE, ANALYZE)")
            c.execute("CHECKPOINT")

    def dump_schema(self, out_dir):
        """pre-data / post-data schema of the app database (no owners, no privileges) and the migration tool's
        bookkeeping table data, as the snapshot builder replays them."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for section in ("pre-data", "post-data"):
            p = run([str(PGBIN / "pg_dump"), "-h", str(self.sock), "-p", str(self.port), "-U", self.superuser,
                     "--schema-only", "--no-owner", "--no-privileges", f"--section={section}", self.db],
                    user=self.os_user, timeout=300)
            if p.returncode != 0:
                raise RuntimeError(f"pg_dump {section} failed: {tail(p.stderr)}")
            (out_dir / f"{section.replace('-data', '')}.sql").write_text(clean_dump(p.stdout))

    def dump_table_data(self, tables):
        args = []
        for t in tables:
            args += ["-t", t]
        p = run([str(PGBIN / "pg_dump"), "-h", str(self.sock), "-p", str(self.port), "-U", self.superuser,
                 "--data-only", "--no-owner", "--no-privileges", "--inserts", *args, self.db],
                user=self.os_user, timeout=300)
        if p.returncode != 0:
            raise RuntimeError(f"pg_dump data failed: {tail(p.stderr)}")
        return clean_dump(p.stdout)

    # ---- grading hooks ----------------------------------------------------------------------------------------------
    def instrument(self):
        """Statement + DEBUG1 evidence for the app role, and an event trigger that logs every DDL command with the
        session's lock_timeout (RAISE LOG only: it writes nothing, so it cannot change what the migration does)."""
        with self.admin() as c:
            c.execute("CREATE SCHEMA IF NOT EXISTS dbm_audit")
            c.execute("REVOKE ALL ON SCHEMA dbm_audit FROM PUBLIC")
            c.execute("""
                CREATE OR REPLACE FUNCTION dbm_audit.ddl_end() RETURNS event_trigger LANGUAGE plpgsql AS $f$
                DECLARE r record;
                BEGIN
                  FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
                    RAISE LOG 'dbm-ddl|%|%|%|%', r.command_tag, r.object_type, r.object_identity,
                      current_setting('lock_timeout');
                  END LOOP;
                END $f$""")
            c.execute("""
                CREATE OR REPLACE FUNCTION dbm_audit.ddl_drop() RETURNS event_trigger LANGUAGE plpgsql AS $f$
                DECLARE r record;
                BEGIN
                  FOR r IN SELECT * FROM pg_event_trigger_dropped_objects() LOOP
                    IF r.original THEN
                      RAISE LOG 'dbm-ddl|%|%|%|%', tg_tag, r.object_type, r.object_identity,
                        current_setting('lock_timeout');
                    END IF;
                  END LOOP;
                END $f$""")
            c.execute("DROP EVENT TRIGGER IF EXISTS dbm_ddl_end")
            c.execute("DROP EVENT TRIGGER IF EXISTS dbm_ddl_drop")
            c.execute("CREATE EVENT TRIGGER dbm_ddl_end ON ddl_command_end EXECUTE FUNCTION dbm_audit.ddl_end()")
            c.execute("CREATE EVENT TRIGGER dbm_ddl_drop ON sql_drop EXECUTE FUNCTION dbm_audit.ddl_drop()")
            for setting in ("log_statement = 'all'", "log_min_messages = 'debug1'",
                            "log_min_error_statement = 'debug1'"):
                c.execute(f"ALTER ROLE {qident(self.role)} IN DATABASE {qident(self.db)} SET {setting}")
        if self.decode_writes:
            # every committed INSERT/UPDATE/DELETE/TRUNCATE, per transaction and table (R4 counts row writes, deletes
            # included, which the rows' xmin cannot show); only a superuser or a REPLICATION role can read or drop it
            with self.admin(db=self.db) as c:
                c.execute("SELECT pg_create_logical_replication_slot('dbm_writes', 'test_decoding')")

    def terminate_app_sessions(self):
        with self.admin() as c:
            c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = %s AND pid <> "
                      "pg_backend_pid()", (self.role,))

    def current_revision(self, table):
        try:
            with self.admin() as c:
                rows = c.execute(f"SELECT * FROM {qident(table)}").fetchall()
            return sorted(r[0] for r in rows)
        except Exception as exc:  # noqa: BLE001
            return [f"<error: {type(exc).__name__}>"]

    def next_xid(self):
        with self.admin() as c:
            return int(c.execute("SELECT txid_snapshot_xmax(txid_current_snapshot())").fetchone()[0])

    def relfiles(self):
        with self.admin() as c:
            rows = c.execute("""
                SELECT c.relname, pg_relation_filenode(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'm', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'dbm_audit')
                  AND n.nspname NOT LIKE 'pg_toast%%' AND n.nspname NOT LIKE 'pg_temp%%'""").fetchall()
        return {r[0]: r[1] for r in rows}

    def row_counts(self, tables):
        out = {}
        with self.admin() as c:
            for t in tables:
                try:
                    out[t] = int(c.execute(f"SELECT count(*) FROM {qident(t)}").fetchone()[0])
                except Exception:  # noqa: BLE001
                    out[t] = None
        return out

    def relfiles_by_oid(self):
        with self.admin() as c:
            rows = c.execute("""
                SELECT c.oid, c.relname, pg_relation_filenode(c.oid), c.reltuples, n.nspname,
                       (SELECT i.inhparent FROM pg_inherits i WHERE i.inhrelid = c.oid LIMIT 1)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'm', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'dbm_audit')
                  AND n.nspname NOT LIKE 'pg_toast%%' AND n.nspname NOT LIKE 'pg_temp%%'""").fetchall()
        return {int(r[0]): {"name": r[1], "node": r[2], "rows": float(r[3] or 0), "schema": r[4],
                            "parent": int(r[5]) if r[5] is not None else None} for r in rows}

    def lock_snapshot(self):
        snap = {"xid": self.next_xid(), "rel": self.relfiles_by_oid()}
        if self.decode_writes:
            # the insert position orders every commit record (asynchronous commits included): transactions that
            # committed before it are outside the window, the step's own commits are inside the next one
            with self.admin(db=self.db) as c:
                snap["lsn"] = str(c.execute("SELECT pg_current_wal_insert_lsn()").fetchone()[0])
        return snap

    def decoded_writes(self, start_lsn, end_lsn):
        """{(xid, table): {"INSERT": n, "UPDATE": n, "DELETE": n, "TRUNCATE": n}} of the transactions that committed
        between two lock snapshots (what one migration step did; the slot skips everything before start_lsn)."""
        out = {}
        # decoding reads flushed WAL only: a synchronous commit of a transaction that wrote WAL flushes everything
        # inserted before it (the server runs with synchronous_commit = off, and a migration may turn it off for its
        # own commits too). A transactional logical message is such a write and touches no table.
        with self.admin(db=self.db, autocommit=False) as c:
            c.execute("SET LOCAL synchronous_commit = on")
            c.execute("SELECT pg_logical_emit_message(true, 'dbm-flush', '')")
            c.commit()
        with self.admin(db=self.db) as c:
            c.execute("SELECT pg_replication_slot_advance('dbm_writes', %s::pg_lsn) FROM pg_replication_slots "
                      "WHERE slot_name = 'dbm_writes' AND confirmed_flush_lsn < %s::pg_lsn", (start_lsn, start_lsn))
            rows = c.execute("""
                SELECT xid::text, m[1], m[2], count(*) FROM (
                  SELECT xid, regexp_match(data, '^table ([^:]+): (INSERT|UPDATE|DELETE|TRUNCATE):') AS m
                  FROM pg_logical_slot_get_changes('dbm_writes', %s::pg_lsn, NULL, 'skip-empty-xacts', '1')) d
                WHERE m IS NOT NULL GROUP BY 1, 2, 3""", (end_lsn,)).fetchall()
        for xid, table, op_, n in rows:
            name = table.split(".", 1)[1] if table.startswith("public.") else table
            out.setdefault((xid, name.strip('"')), {})[op_] = int(n)
        return out

    def collect_evidence(self, step, before, after, mark, end, baseline):
        """What one migration step did to the tables that existed before the migration started."""
        recs = self.log_records(mark, end)
        ev = lock_evidence(self, recs, self.role)
        base = set(baseline or before["rel"])
        pre = {before["rel"][o]["name"] for o in base if o in before["rel"]} | \
              {after["rel"][o]["name"] for o in base if o in after["rel"]}
        rewrites = sorted(after["rel"][o]["name"] for o in base if o in before["rel"] and o in after["rel"]
                          and before["rel"][o]["node"] is not None
                          and before["rel"][o]["node"] != after["rel"][o]["node"])
        now = sorted(after["rel"][o]["name"] for o in base if o in after["rel"] and after["rel"][o]["node"] is not None)
        # an existing table whose name another table holds after the step (dropped and created again, or another
        # table renamed onto it) is a rewrite; attaching the original as a partition of the new holder (the online
        # partitioning pattern) copies nothing and is not
        names_after = {(v.get("schema"), v["name"]): o for o, v in after["rel"].items()}
        recreated = []
        for o in base:
            if o not in before["rel"]:
                continue
            holder = names_after.get((before["rel"][o].get("schema"), before["rel"][o]["name"]))
            if holder is None or holder == o:
                continue
            if o in after["rel"] and after["rel"][o].get("parent") == holder:
                continue
            recreated.append(before["rel"][o]["name"])
        recreated.sort()
        batch = self.max_rows_per_xact(now, before["xid"], after["xid"])
        truncated = []
        if self.decode_writes:
            per = {}
            for (xid, table), ops in self.decoded_writes(before["lsn"], after["lsn"]).items():
                n = ops.get("INSERT", 0) + ops.get("UPDATE", 0) + ops.get("DELETE", 0)
                per[table] = max(per.get(table, 0), n)
                if ops.get("TRUNCATE"):
                    truncated.append(table)
            for t in set(batch) | set(per):
                batch[t] = max(batch.get(t, 0), per.get(t, 0))
        return {"step": step, "pre_names": sorted(pre), "evidence": ev, "rewrites": sorted(set(rewrites) | set(recreated)),
                "batch": batch, "truncated": sorted(set(truncated)), "decoded": self.decode_writes,
                "statements": sum(1 for r in recs if r["user"] == self.role and r["message"].startswith("statement:"))}

    def judge_locks(self, evidence, cfg):
        """The zero-downtime lock rules over every judged migration step -> {rule: (ok, detail)}."""
        rules = cfg.get("rules") or ["concurrent_indexes", "no_validation_scan", "no_table_rewrite", "batched_writes",
                                     "lock_timeout"]
        scope = cfg.get("scope", "all")
        max_rows = int(cfg.get("max_rows_per_txn", 10000))
        max_lt = int(cfg.get("lock_timeout_max_ms", 5000))
        lt_tags = {"ALTER TABLE", "CREATE TRIGGER", "DROP TRIGGER", "ALTER TRIGGER", "CREATE RULE", "DROP RULE",
                   "CREATE POLICY", "ALTER POLICY", "DROP POLICY", "DROP TABLE"}
        lt_types = {"table", "table column", "trigger", "table constraint", "rule", "policy"}
        excluded = {t.lower() for t in cfg.get("exclude") or []}
        out = {}
        for rule in rules:
            bad = []
            for e in evidence:
                pre = set(e["pre_names"])

                def ins(t):  # an existing table, not the migration tool's own bookkeeping table
                    return t in pre and (scope == "all" or t in scope) and (t or "").lower() not in excluded
                ev = e["evidence"]
                if rule == "concurrent_indexes":
                    bad += [f"{e['step']}: index {x['index']} on {x['table']} was built by a blocking statement "
                            f"`{x['statement'][:100]}`" for x in ev["concurrent_indexes"] if not x["ok"] and ins(x["table"])]
                elif rule == "no_validation_scan":
                    bad += [f"{e['step']}: `{x['statement'][:110]}` scanned {x['table']} under a blocking lock "
                            f"(add the constraint NOT VALID and VALIDATE it separately)"
                            for x in ev["no_validation_scan"] if not x["ok"] and (x["table"] is None or ins(x["table"]))]
                elif rule == "no_table_rewrite":
                    names = sorted(set(t for t in e["rewrites"] if ins(t)) |
                                   set(x["table"] for x in ev["no_table_rewrite_log"] if ins(x["table"])))
                    stm = {x["table"]: x["statement"] for x in ev["no_table_rewrite_log"]}
                    bad += [f"{e['step']}: table {t} was rewritten" + (f" by `{stm[t][:100]}`" if t in stm else "")
                            for t in names]
                    bad += [f"{e['step']}: table {t} was truncated" for t in e.get("truncated", []) if ins(t)
                            and t not in names]
                elif rule == "batched_writes":
                    if not e.get("decoded", False):
                        raise RuntimeError("batched_writes needs the decoded row changes of the step")
                    bad += [f"{e['step']}: one transaction wrote {n} rows of {t} (inserted, updated or deleted; "
                            f"limit {max_rows})" for t, n in sorted(e["batch"].items()) if n > max_rows and ins(t)]
                    bad += [f"{e['step']}: table {t} was truncated in one transaction" for t in e.get("truncated", [])
                            if ins(t)]
                elif rule == "lock_timeout":
                    for x in ev["lock_timeout"]:
                        if x["tag"] not in lt_tags or x["table"] is None or not ins(x["table"]):
                            continue
                        if not x["object"] or x["tag"] == "DROP TABLE" and x["table"] not in pre:
                            continue
                        lt = x["lock_timeout_ms"]
                        if lt is None or lt <= 0 or lt > max_lt:
                            bad.append(f"{e['step']}: `{x['statement'][:100]}` ({x['tag']} on {x['table']}) ran with "
                                       f"lock_timeout={'0 (none)' if not lt else str(lt) + 'ms'}")
                else:
                    raise RuntimeError(f"unknown lock rule {rule}")
            out[rule] = (not bad, "; ".join(bad[:3]) + (f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""))
        return out

    def max_rows_per_xact(self, tables, xid_from, xid_to):
        """For each table: the largest number of its current rows last written by one transaction in [from, to)."""
        out = {}
        with self.admin() as c:
            for t in tables:
                try:
                    row = c.execute(
                        f"SELECT xmin::text::bigint AS x, count(*) FROM {qident(t)} "
                        f"WHERE xmin::text::bigint >= %s AND xmin::text::bigint < %s GROUP BY 1 ORDER BY 2 DESC LIMIT 1",
                        (xid_from, xid_to)).fetchone()
                    out[t] = int(row[1]) if row else 0
                except Exception:  # noqa: BLE001  (the table is gone or renamed)
                    out[t] = 0
        return out

    def content_checksum(self, table, cols, types=None):
        """Row count and a hash of the given columns of every row, as a multiset (rows sorted by their text), json
        normalized through jsonb, rendered with fixed session settings -> a run_statement outcome; a missing table
        or column is an error outcome."""
        types = types or {}
        with self.admin(db=self.db) as c:
            if not cols:
                return self.run_statement(c, f"SELECT count(*) FROM {qident(table)}", None, read_only=True,
                                          timeout_ms=300000)
            parts = [f"{qident(col)}::jsonb" if (types.get(col) or "").lower() == "json" else qident(col)
                     for col in cols]
            row = "ROW(" + ", ".join(parts) + ")::text"
            return self.run_statement(
                c, f"SELECT count(*), md5(coalesce(string_agg(r, E'\\n' ORDER BY r COLLATE \"C\"), '')) "
                   f"FROM (SELECT {row} AS r FROM {qident(table)}) x", None, read_only=True, timeout_ms=600000,
                settings=RENDER_SETTINGS)

    # ---- log -------------------------------------------------------------------------------------------------------
    def log_mark(self):
        """Flush a unique marker through the log collector; returns the byte offset just after it."""
        token = uuid.uuid4().hex
        with self.admin() as c:
            c.execute(f"DO $$ BEGIN RAISE LOG 'dbm-mark {token}'; END $$")
        path = self.logdir / "pg.csv"

        def seen():
            try:
                return f"dbm-mark {token}" in path.read_text(errors="replace")[-200000:]
            except OSError:
                return False
        wait_for(seen, timeout=30)
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def log_records(self, start, end):
        path = self.logdir / "pg.csv"
        if not path.exists():
            return []
        with open(path, "rb") as fh:
            fh.seek(start)
            blob = fh.read(max(0, end - start)).decode("utf-8", errors="replace")
        out = []
        for row in csv.reader(blob.splitlines(keepends=True)):
            if len(row) < 20:
                continue
            out.append({"user": row[1], "session": row[5], "line": row[6], "tag": row[7], "vxid": row[9],
                        "xid": row[10], "severity": row[11], "state": row[12], "message": row[13], "detail": row[14],
                        "query": row[19], "context": row[18]})
        return out

    # ---- catalog ---------------------------------------------------------------------------------------------------
    def catalog(self):
        q = {}
        with self.admin() as c:
            sch = "n.nspname NOT IN ('pg_catalog','information_schema','dbm_audit') AND n.nspname NOT LIKE 'pg_toast%%' " \
                  "AND n.nspname NOT LIKE 'pg_temp%%'"
            rels = c.execute(f"""
                SELECT c.oid, n.nspname, c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity,
                       c.relispartition, pg_get_expr(c.relpartbound, c.oid), CASE WHEN c.relkind = 'p' THEN pg_get_partkeydef(c.oid) END,
                       c.relpersistence
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE {sch} AND c.relkind IN ('r','p','v','m','f')""").fetchall()
            tables, views = {}, {}
            names = {}
            for oid, nsp, name, kind, rls, frls, ispart, bound, partkey, persist in rels:
                key = name if nsp == "public" else f"{nsp}.{name}"
                names[oid] = key
                if kind in ("v", "m"):
                    d = c.execute("SELECT pg_get_viewdef(%s, true)", (oid,)).fetchone()[0]
                    views[key] = {"kind": kind, "definition": re.sub(r"\s+", " ", d or "").strip()}
                    continue
                tables[key] = {"kind": kind, "rls": bool(rls), "force_rls": bool(frls), "partition_of": None,
                               "partition_bound": bound, "partition_key": partkey, "unlogged": persist == "u",
                               "columns": {}, "column_order": []}
            for oid, nsp, name, kind, *_ in rels:
                if kind in ("v", "m"):
                    cols = c.execute("""SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
                                        WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum""",
                                     (oid,)).fetchall()
                    views[names[oid]]["columns"] = {a: t for a, t in cols}
            cols = c.execute(f"""
                SELECT a.attrelid, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                       pg_get_expr(d.adbin, d.adrelid), a.attidentity, a.attgenerated,
                       CASE WHEN a.attcollation <> t.typcollation THEN co.collname END
                FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_type t ON t.oid = a.atttypid
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                LEFT JOIN pg_collation co ON co.oid = a.attcollation
                WHERE {sch} AND c.relkind IN ('r','p') AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attrelid, a.attnum""").fetchall()
            for relid, col, typ, notnull, default, ident, gen, coll in cols:
                t = tables.get(names.get(relid))
                if t is None:
                    continue
                t["columns"][col] = {"type": typ, "not_null": bool(notnull), "default": default,
                                     "identity": ident or None, "generated": gen or None, "collation": coll}
                t["column_order"].append(col)
            for relid, parent in c.execute("SELECT inhrelid, inhparent FROM pg_inherits").fetchall():
                if names.get(relid) in tables:
                    tables[names[relid]]["partition_of"] = names.get(parent)
            cons = c.execute(f"""
                SELECT co.conrelid, co.conname, co.contype, pg_get_constraintdef(co.oid), co.convalidated,
                       co.condeferrable, co.condeferred, co.confrelid,
                       ARRAY(SELECT a.attname FROM unnest(co.conkey) WITH ORDINALITY k(n, i)
                             JOIN pg_attribute a ON a.attrelid = co.conrelid AND a.attnum = k.n ORDER BY k.i),
                       ARRAY(SELECT a.attname FROM unnest(co.confkey) WITH ORDINALITY k(n, i)
                             JOIN pg_attribute a ON a.attrelid = co.confrelid AND a.attnum = k.n ORDER BY k.i),
                       co.confdeltype, co.confupdtype
                FROM pg_constraint co JOIN pg_class c ON c.oid = co.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE {sch} AND co.contype IN ('p','u','f','c','x')""").fetchall()
            actions = {"a": "no action", "r": "restrict", "c": "cascade", "n": "set null", "d": "set default"}
            constraints = {}
            for relid, name, typ, defn, valid, deferrable, deferred, frel, ckey, fkey, dtype, utype in cons:
                tname = names.get(relid)
                if tname is None:
                    continue
                constraints.setdefault(tname, []).append({
                    "name": name, "type": {"p": "primary_key", "u": "unique", "f": "foreign_key", "c": "check",
                                           "x": "exclusion"}[typ],
                    "definition": defn, "validated": bool(valid), "deferrable": bool(deferrable),
                    "deferred": bool(deferred), "columns": list(ckey or []),
                    "references": names.get(frel) if frel else None, "ref_columns": list(fkey or []),
                    "on_delete": actions.get(dtype) if typ == "f" else None,
                    "on_update": actions.get(utype) if typ == "f" else None})
            idx = c.execute(f"""
                SELECT i.indrelid, ic.relname, i.indisunique, i.indisprimary, i.indisvalid, pg_get_indexdef(i.indexrelid),
                       am.amname, pg_get_expr(i.indpred, i.indrelid),
                       ARRAY(SELECT pg_get_indexdef(i.indexrelid, k, true) FROM generate_series(1, i.indnkeyatts) k),
                       EXISTS (SELECT 1 FROM pg_constraint co WHERE co.conindid = i.indexrelid AND co.contype IN ('p','u','x'))
                FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid JOIN pg_class c ON c.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_am am ON am.oid = ic.relam
                WHERE {sch}""").fetchall()
            indexes = {}
            for relid, name, uniq, prim, valid, defn, method, pred, keys, backs in idx:
                tname = names.get(relid)
                if tname is None:
                    continue
                shape = re.sub(r"^CREATE (UNIQUE )?INDEX \S+ ON (ONLY )?\S+ ", "", defn)
                indexes.setdefault(tname, []).append({
                    "name": name, "unique": bool(uniq), "primary": bool(prim), "valid": bool(valid),
                    "method": method, "columns": [k.strip('"') for k in keys], "predicate": pred, "shape": shape,
                    "constraint": bool(backs)})
            trig = c.execute(f"""
                SELECT t.tgrelid, t.tgname, pg_get_triggerdef(t.oid), t.tgenabled, p.proname
                FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_proc p ON p.oid = t.tgfoid
                WHERE {sch} AND NOT t.tgisinternal""").fetchall()
            triggers = {}
            for relid, name, defn, enabled, func in trig:
                tname = names.get(relid)
                if tname is None:
                    continue
                triggers.setdefault(tname, []).append({"name": name, "definition": defn, "enabled": enabled,
                                                       "function": func})
            funcs = c.execute(f"""
                SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid), p.prokind, md5(p.prosrc)
                FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE {sch} AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')"""
                              ).fetchall()
            functions = sorted(f"{nsp}.{name}({args})" if nsp != "public" else f"{name}({args})"
                               for nsp, name, args, kind, _ in funcs)
            seqs = c.execute(f"""
                SELECT c.relname, format_type(s.seqtypid, NULL), s.seqincrement
                FROM pg_sequence s JOIN pg_class c ON c.oid = s.seqrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE {sch}""").fetchall()
            sequences = {name: {"type": typ, "increment": int(inc)} for name, typ, inc in seqs}
            enums = {}
            for tname, label in c.execute(f"""
                SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
                JOIN pg_namespace n ON n.oid = t.typnamespace WHERE {sch} ORDER BY t.typname, e.enumsortorder""").fetchall():
                enums.setdefault(tname, []).append(label)
            policies = {}
            for tname, pol, cmd, roles, qual, check in c.execute(
                    "SELECT tablename, policyname, cmd, roles::text[], qual, with_check FROM pg_policies "
                    "WHERE schemaname NOT IN ('dbm_audit')").fetchall():
                policies.setdefault(tname, []).append({"name": pol, "command": cmd, "roles": sorted(roles or []),
                                                       "using": qual, "with_check": check})
            exts = sorted(r[0] for r in c.execute("SELECT extname FROM pg_extension WHERE extname <> 'plpgsql'"
                                                  ).fetchall())
        q.update({"engine": self.kind, "tables": tables, "views": views, "constraints": constraints,
                  "indexes": indexes, "triggers": triggers, "functions": functions, "sequences": sequences,
                  "enums": enums, "policies": policies, "extensions": exts})
        return q

    # ---- queries ---------------------------------------------------------------------------------------------------
    def run_statement(self, conn, sql, params, read_only, timeout_ms=30000, settings=None):
        """Execute one corpus statement in its own transaction (with transaction-local session settings, e.g. the
        tenant of a multi-tenant application). Returns a JSON-able outcome."""
        import psycopg
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                    cur.execute("SET LOCAL lock_timeout = 10000")
                    for k, v in (settings or {}).items():
                        cur.execute("SELECT set_config(%s, %s, true)", (k, str(v)))
                    if read_only:
                        cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute(sql, params or None)
                    rows = cur.fetchall() if cur.description else None
                    cols = [d.name for d in cur.description] if cur.description else None
                    return {"columns": cols, "rows": [[norm_value(v) for v in r] for r in rows] if rows is not None
                            else None, "rowcount": cur.rowcount}
        except psycopg.Error as exc:
            state = getattr(exc, "sqlstate", None) or "XX000"
            return {"error": state, "message": str(exc).strip().splitlines()[0][:200] if str(exc).strip() else ""}

    def app_session(self):
        return self.app(autocommit=True)


def clean_dump(text):
    """Strip pg_dump's session preamble noise that does not matter for replay (keeps statements)."""
    out = []
    for line in text.splitlines():
        if line.startswith("-- Dumped") or line.startswith("\\restrict") or line.startswith("\\unrestrict"):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


# ---- lock-rule evidence -------------------------------------------------------------------------------------------
INDEX_BUILD = re.compile(r'^building index "([^"]+)" on table "([^"]+)"')
VERIFY = re.compile(r'^verifying table "([^"]+)"')
REWRITE = re.compile(r'^rewriting table "([^"]+)"')
FK_VALIDATE = re.compile(r'^validating foreign key constraint "([^"]+)"')
DDL_EVENT = re.compile(r"^dbm-ddl\|([^|]*)\|([^|]*)\|([^|]*)\|(.*)$")


def _parse(sql):
    try:
        from pglast import parse_sql
        return [s.stmt for s in parse_sql(sql)]
    except Exception:  # noqa: BLE001  (unparsable text: judged by its evidence alone)
        return None


def _stmt_kind(sql):
    """('cic' | 'reindex_conc' | 'validate_only' | 'alter' | 'other', target table or None) of a logged statement."""
    stmts = _parse(sql)
    if not stmts or len(stmts) != 1:
        return "other", None
    st = stmts[0]
    name = type(st).__name__
    if name == "IndexStmt":
        return ("cic" if st.concurrent else "index"), st.relation.relname
    if name == "ReindexStmt":
        params = [getattr(p, "defname", "") for p in (st.params or [])]
        return ("reindex_conc" if "concurrently" in params else "reindex"), None
    if name == "AlterTableStmt":
        from pglast.enums.parsenodes import AlterTableType
        subs = [AlterTableType(c.subtype).name for c in (st.cmds or [])]
        if subs and all(s == "AT_ValidateConstraint" for s in subs):
            return "validate_only", st.relation.relname
        return "alter", st.relation.relname
    return "other", None


def _ms(setting):
    s = (setting or "").strip().lower()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(ms|s|min|h|d)?$", s)
    if not m:
        return None
    v = float(m.group(1))
    return int(v * {"ms": 1, "s": 1000, "min": 60000, "h": 3600000, "d": 86400000, None: 1}[m.group(2)])


def _event_table(otype, ident):
    ident = ident or ""
    if otype in ("table", "view", "materialized view"):
        return ident.split(".")[-1].strip('"')
    if otype == "table column":
        parts = ident.split(".")
        return parts[-2].strip('"') if len(parts) >= 2 else None
    if otype in ("trigger", "table constraint", "rule", "policy") and " on " in ident:
        return ident.split(" on ", 1)[1].split(".")[-1].strip('"')
    return None


def lock_evidence(engine, records, role):
    """Classify one migration step's log records into rule findings (lists of strings per rule)."""
    found = {"concurrent_indexes": [], "no_validation_scan": [], "no_table_rewrite_log": [], "lock_timeout": []}
    for r in records:
        if r["user"] != role:
            continue
        msg, query = r["message"] or "", r["query"] or ""
        m = INDEX_BUILD.match(msg)
        if m:
            index, table = m.group(1), m.group(2)
            if table.startswith("pg_toast"):
                continue
            kind, _ = _stmt_kind(query)
            found["concurrent_indexes"].append({"table": table, "index": index, "ok": kind in ("cic", "reindex_conc"),
                                                "statement": query[:240]})
            continue
        m = VERIFY.match(msg)
        if m:
            kind, _ = _stmt_kind(query)
            found["no_validation_scan"].append({"table": m.group(1), "ok": kind == "validate_only",
                                                "statement": query[:240]})
            continue
        m = FK_VALIDATE.match(msg)
        if m:
            kind, table = _stmt_kind(query)
            found["no_validation_scan"].append({"table": table, "constraint": m.group(1), "ok": kind == "validate_only",
                                                "statement": query[:240]})
            continue
        m = REWRITE.match(msg)
        if m:
            found["no_table_rewrite_log"].append({"table": m.group(1), "ok": False, "statement": query[:240]})
            continue
        m = DDL_EVENT.match(msg)
        if m:
            tag, otype, ident, lt = m.groups()
            table = _event_table(otype, ident)
            if tag in ("CREATE INDEX", "DROP INDEX", "REINDEX", "COMMENT", "GRANT", "REVOKE"):
                continue
            kind, _ = _stmt_kind(query)
            if kind in ("cic", "reindex_conc"):
                continue
            found["lock_timeout"].append({"table": table, "tag": tag, "object": ident, "lock_timeout_ms": _ms(lt),
                                          "statement": query[:240]})
    return found
