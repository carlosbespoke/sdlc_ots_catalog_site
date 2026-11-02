"""MySQL 8.4 engine adapter: a private mysqld per scenario (a plain process, no Docker), snapshot build and restore,
the application account's connections, a normalized catalog from information_schema, and the evidence the online-DDL
rules are judged on (the general query log of the application account, InnoDB table ids before and after a step)."""
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from dbm_util import chown_tree, is_root, norm_value, run, tail, wait_for

MYBIN = Path(os.environ.get("DBM_MYBIN", "/opt/mysql/bin"))

TYPE_ALIASES = {"integer": "int", "bool": "tinyint(1)", "boolean": "tinyint(1)", "int4": "int", "int8": "bigint",
                "smallint": "smallint", "character varying": "varchar", "double precision": "double"}


def norm_type(t):
    t = re.sub(r"\s+", " ", (t or "").strip().lower())
    t = re.sub(r"\b(int|bigint|smallint|tinyint|mediumint)\(\d+\)", r"\1", t) if not t.startswith("tinyint(1)") else t
    for k, v in TYPE_ALIASES.items():
        if t == k or t.startswith(k + "("):
            t = v + t[len(k):]
    return t.replace(" unsigned", " unsigned")


def no_mysql_env():
    """The process environment without MYSQL_* client variables (the agent image sets them for the solver)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("MYSQL_")}


def q(name):
    return "`" + name.replace("`", "``") + "`"


class MySqlEngine:
    kind = "mysql84"
    superuser = "root"

    def __init__(self, root, port=3306, os_user=None, db="app", role="app", password="app"):
        self.root = Path(root)
        self.port = int(port)
        self.os_user = os_user if is_root() else None
        self.db, self.role, self.password = db, role, password
        self.data = self.root / "data"
        self.sock = self.root / "sock"
        self.logdir = self.root / "log"
        self.cnf = self.root / "my.cnf"
        self.proc = None
        self.running = False
        # lock-judged scenarios keep a row-based binary log to count the rows each transaction writes
        self.decode_writes = False

    # ---- lifecycle --------------------------------------------------------------------------------------------------
    def _prep_dirs(self):
        for d in (self.root, self.sock, self.logdir, self.root / "load"):
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(self.sock, 0o700)
        chown_tree(self.root, self.os_user)

    def configure(self):
        self.cnf.write_text("\n".join([
            "[mysqld]", f"datadir={self.data}", f"port={self.port}", "bind-address=127.0.0.1",
            f"socket={self.sock}/mysqld.sock", f"pid-file={self.sock}/mysqld.pid", f"log-error={self.logdir}/error.log",
            f"general_log_file={self.logdir}/general.log", "general_log=OFF", "log_output=FILE", "mysqlx=OFF",
            "skip-name-resolve",
            *([f"log-bin={self.logdir / 'binlog'}", "binlog_format=ROW", "server-id=1", "binlog_expire_logs_seconds=0",
               "sync_binlog=0"] if self.decode_writes else ["skip-log-bin"]),
            "innodb_buffer_pool_size=512M", "innodb_flush_log_at_trx_commit=0",
            "innodb_doublewrite=OFF", "innodb_redo_log_capacity=512M", "default-time-zone=+00:00",
            "character-set-server=utf8mb4", "collation-server=utf8mb4_0900_ai_ci", "max_connections=100",
            f"secure-file-priv={self.root / 'load'}", "local_infile=OFF", "performance_schema=OFF",
            "innodb_stats_persistent=ON", "lower_case_table_names=0", ""]))
        chown_tree(self.root, self.os_user)
        os.chmod(self.cnf, 0o644)

    def initdb(self):
        self._prep_dirs()
        if self.data.exists():
            shutil.rmtree(self.data)
        self.configure()
        p = run([str(MYBIN / "mysqld"), f"--defaults-file={self.cnf}", "--initialize-insecure"], user=self.os_user,
                timeout=600)
        if p.returncode != 0:
            log = (self.logdir / "error.log").read_text(errors="replace") if (self.logdir / "error.log").exists() else ""
            raise RuntimeError(f"mysqld --initialize failed: {tail(p.stdout + p.stderr + log)}")

    def start(self, timeout=240):
        self._prep_dirs()
        if not self.cnf.exists():
            self.configure()
        cmd = [str(MYBIN / "mysqld"), f"--defaults-file={self.cnf}"]
        if self.os_user and is_root():
            cmd = ["setpriv", f"--reuid={self.os_user}", f"--regid={self.os_user}", "--init-groups", "--"] + cmd
        from dbm_util import nss_env
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                                     env={**os.environ, **nss_env()})
        ok = wait_for(self._ping, timeout=timeout, step=0.3)
        if not ok:
            log = (self.logdir / "error.log").read_text(errors="replace") if (self.logdir / "error.log").exists() else ""
            raise RuntimeError(f"mysqld did not start: {tail(log)}")
        self.running = True

    def _ping(self):
        try:
            c = self.admin(db="mysql")
            c.close()
            return True
        except Exception:  # noqa: BLE001
            return False

    def stop(self):
        if self.proc is None and not (self.sock / "mysqld.pid").exists():
            return
        try:
            c = self.admin(db="mysql")
            c.cursor().execute("SHUTDOWN")
            c.close()
        except Exception:  # noqa: BLE001
            pass
        if self.proc is not None:
            try:
                self.proc.wait(timeout=180)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        else:
            wait_for(lambda: not (self.sock / "mysqld.pid").exists(), timeout=180)
        self.proc = None
        self.running = False

    def save(self, dest):
        self.stop()
        dest = Path(dest)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.data, dest, symlinks=True)

    def restore(self, src):
        self.stop()
        if self.data.exists():
            shutil.rmtree(self.data)
        self._prep_dirs()
        shutil.copytree(src, self.data, symlinks=True)
        for stale in ("auto.cnf",):
            pass
        self.configure()
        chown_tree(self.root, self.os_user)
        for f in self.logdir.iterdir():
            f.unlink()

    # ---- connections ------------------------------------------------------------------------------------------------
    def admin(self, db=None, autocommit=True):
        import pymysql
        return pymysql.connect(unix_socket=str(self.sock / "mysqld.sock"), user="root", database=db or self.db,
                               autocommit=autocommit, connect_timeout=20, charset="utf8mb4")

    def app(self, autocommit=True):
        import pymysql
        return pymysql.connect(host="127.0.0.1", port=self.port, user=self.role, password=self.password,
                               database=self.db, autocommit=autocommit, connect_timeout=20, charset="utf8mb4")

    def tool_url(self, scheme="mysql+pymysql"):
        return f"{scheme}://{self.role}:{self.password}@127.0.0.1:{self.port}/{self.db}"

    def jdbc_url(self):
        return (f"jdbc:mysql://127.0.0.1:{self.port}/{self.db}?useSSL=false&allowPublicKeyRetrieval=true"
                f"&serverTimezone=UTC&connectionTimeZone=UTC")

    def migrate_url(self):
        """golang-migrate's connection URL (the application account; several statements per file)."""
        return f"mysql://{self.role}:{self.password}@tcp(127.0.0.1:{self.port})/{self.db}?multiStatements=true"

    def query_rows(self, sql):
        """Rows of one query as root, None when it fails (e.g. the table does not exist yet)."""
        try:
            with self.admin() as c:
                cur = c.cursor()
                cur.execute(sql)
                return [tuple(r) for r in cur.fetchall()]
        except Exception:  # noqa: BLE001
            return None

    def env_for_tools(self):
        return {"MYSQL_HOST": "127.0.0.1", "MYSQL_TCP_PORT": str(self.port), "DB_USER": self.role,
                "DB_PASSWORD": self.password, "MYSQL_PWD": self.password,
                "JDBC_URL": self.jdbc_url(), "DATABASE_URL": self.tool_url()}

    def create_app(self):
        with self.admin(db="mysql") as c:
            cur = c.cursor()
            cur.execute(f"CREATE DATABASE {q(self.db)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            for host in ("127.0.0.1", "localhost"):
                cur.execute(f"CREATE USER '{self.role}'@'{host}' IDENTIFIED BY %s", (self.password,))
                cur.execute(f"GRANT ALL PRIVILEGES ON {q(self.db)}.* TO '{self.role}'@'{host}'")

    def psql_file(self, path, as_app=True, timeout=900):
        """Run an SQL script with the mysql client (stops at the first error). The client gets an environment without
        MYSQL_* variables: the agent image sets MYSQL_HOST / MYSQL_PWD for the solver's own client, and they would
        override the socket and the account this call means."""
        if as_app:
            cmd = [str(MYBIN / "mysql"), "--protocol=TCP", "-h127.0.0.1", f"-P{self.port}", f"-u{self.role}", self.db]
            env = {"MYSQL_PWD": self.password}
        else:
            cmd = [str(MYBIN / "mysql"), "--protocol=SOCKET", f"--socket={self.sock}/mysqld.sock", "-uroot", self.db]
            env = {}
        p = run(cmd, env={**no_mysql_env(), **env}, timeout=timeout, stdin=Path(path).read_text(), clean_env=True)
        if p.returncode != 0:
            raise RuntimeError(f"mysql {Path(path).name} failed: {tail(p.stdout + p.stderr, 15)}")

    def load_rows(self, table, columns, rows):
        from dbm_data import mysql_tsv_value
        f = self.root / "load" / f"{table}.tsv"
        n = 0
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write("\t".join(mysql_tsv_value(v) for v in row) + "\n")
                n += 1
        os.chmod(f, 0o644)
        chown_tree(self.root / "load", self.os_user)
        with self.admin() as c:
            cur = c.cursor()
            cur.execute("SET SESSION foreign_key_checks = 0, unique_checks = 0")
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s "
                        "AND table_name = %s", (self.db, table))
            bits = {name for name, typ in cur.fetchall() if typ == "bit"}
            targets, sets = [], []
            for k, col in enumerate(columns):
                if col in bits:  # BIT(1) booleans (Liquibase's MySQL boolean): load the text 0/1 as a number
                    targets.append(f"@b{k}")
                    sets.append(f"{q(col)} = IF(@b{k} IS NULL, NULL, CAST(@b{k} AS UNSIGNED))")
                else:
                    targets.append(q(col))
            stmt = f"LOAD DATA INFILE %s INTO TABLE {q(table)} CHARACTER SET utf8mb4 ({', '.join(targets)})"
            if sets:
                stmt += " SET " + ", ".join(sets)
            cur.execute(stmt, (str(f),))
        f.unlink()
        return n

    def finish_load(self):
        with self.admin() as c:
            cur = c.cursor()
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = "
                        "'BASE TABLE'", (self.db,))
            for (t,) in cur.fetchall():
                cur.execute(f"ANALYZE TABLE {q(t)}")
                cur.fetchall()

    def dump_schema(self, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        p = run([str(MYBIN / "mysqldump"), "--protocol=SOCKET", f"--socket={self.sock}/mysqld.sock", "-uroot", "--no-data",
                 "--skip-comments", "--routines", "--triggers", "--skip-add-drop-table", "--set-gtid-purged=OFF",
                 "--column-statistics=0", self.db], timeout=300, env=no_mysql_env(), clean_env=True)
        if p.returncode != 0:
            raise RuntimeError(f"mysqldump failed: {tail(p.stderr)}")
        text = re.sub(r" AUTO_INCREMENT=\d+", "", p.stdout)
        text = re.sub(r"DEFINER=`[^`]+`@`[^`]+` ", "", text)
        (out_dir / "pre.sql").write_text(text)
        (out_dir / "post.sql").write_text("SELECT 1;\n")

    def dump_table_data(self, tables):
        p = run([str(MYBIN / "mysqldump"), "--protocol=SOCKET", f"--socket={self.sock}/mysqld.sock", "-uroot",
                 "--no-create-info", "--skip-comments", "--complete-insert", "--skip-extended-insert",
                 "--set-gtid-purged=OFF", "--column-statistics=0", self.db, *tables], timeout=300, env=no_mysql_env(),
                clean_env=True)
        if p.returncode != 0:
            raise RuntimeError(f"mysqldump data failed: {tail(p.stderr)}")
        return p.stdout

    # ---- grading hooks ----------------------------------------------------------------------------------------------
    def instrument(self):
        pass

    def terminate_app_sessions(self):
        try:
            with self.admin(db="mysql") as c:
                cur = c.cursor()
                cur.execute("SELECT id FROM information_schema.processlist WHERE user = %s", (self.role,))
                for (pid,) in cur.fetchall():
                    try:
                        cur.execute(f"KILL {int(pid)}")
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass

    def current_revision(self, table):
        try:
            with self.admin() as c:
                cur = c.cursor()
                cur.execute(f"SELECT * FROM {q(table)}")
                return sorted(r[0] for r in cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            return [f"<error: {type(exc).__name__}>"]

    def changelog_state(self, table="DATABASECHANGELOG"):
        try:
            with self.admin() as c:
                cur = c.cursor()
                cur.execute(f"SELECT ID, AUTHOR, FILENAME, MD5SUM, EXECTYPE, TAG FROM {q(table)} ORDER BY ORDEREXECUTED")
                return [list(map(norm_value, r)) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            return [f"<error: {type(exc).__name__}>"]

    def history_fingerprint(self, table="DATABASECHANGELOG"):
        st = self.changelog_state(table)
        return [r[:5] if isinstance(r, list) else r for r in st]

    def relfiles_by_oid(self):
        with self.admin() as c:
            cur = c.cursor()
            cur.execute("SELECT NAME, TABLE_ID FROM information_schema.INNODB_TABLES WHERE NAME LIKE %s",
                        (f"{self.db}/%",))
            rows = cur.fetchall()
            cur.execute("SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = %s",
                        (self.db,))
            counts = {r[0]: r[1] for r in cur.fetchall()}
        out = {}
        for name, tid in rows:
            t = name.split("/", 1)[1]
            if "#" in t:
                continue
            out[t] = {"name": t, "node": int(tid), "rows": float(counts.get(t) or 0)}
        return out

    def lock_snapshot(self):
        binlog = None
        if self.decode_writes:  # start a fresh binary log file: the step's row events are in the files after it
            with self.admin(db="mysql") as c:
                cur = c.cursor()
                cur.execute("FLUSH BINARY LOGS")
                cur.execute("SHOW BINARY LOG STATUS")
                binlog = cur.fetchone()[0]
        return {"rel": self.relfiles_by_oid(), "log": self._log_size(), "binlog": binlog}

    def decoded_writes(self, first_file, end_file):
        """{(txn number, table): {"INSERT": n, "UPDATE": n, "DELETE": n}} from the row events in the binary log files
        written between two lock snapshots: first_file <= name < end_file (mysqlbinlog -v)."""
        with self.admin(db="mysql") as c:
            cur = c.cursor()
            cur.execute("SHOW BINARY LOGS")
            names = [r[0] for r in cur.fetchall()]
        files = [str(self.logdir / n) for n in names if first_file <= n < end_file]
        if not files:
            return {}
        p = subprocess.run([str(MYBIN / "mysqlbinlog"), "--base64-output=DECODE-ROWS", "-v", *files],
                           capture_output=True, text=True, errors="replace", timeout=900)
        if p.returncode != 0:
            raise RuntimeError(f"mysqlbinlog failed: {tail(p.stderr, 5)}")
        out, txn = {}, 0
        for line in p.stdout.splitlines():
            if line.startswith("BEGIN") or line.startswith("START TRANSACTION"):
                txn += 1
                continue
            m = re.match(r"^### (INSERT INTO|UPDATE|DELETE FROM) `([^`]+)`\.`([^`]+)`", line)
            if m and m.group(2) == self.db:
                op_ = m.group(1).split()[0]
                d = out.setdefault((txn, m.group(3)), {})
                d[op_] = d.get(op_, 0) + 1
        return out

    def _log_size(self):
        p = self.logdir / "general.log"
        return p.stat().st_size if p.exists() else 0

    def log_mark(self):
        token = uuid.uuid4().hex
        with self.admin(db="mysql") as c:
            cur = c.cursor()
            cur.execute("SET GLOBAL general_log = ON")
            cur.execute(f"SELECT 'dbm-mark {token}'")
        return self._log_size()

    def collect_evidence(self, step, before, after, mark, end, baseline):
        path = self.logdir / "general.log"
        text = ""
        if path.exists():
            with open(path, "rb") as fh:
                fh.seek(mark)
                text = fh.read().decode("utf-8", errors="replace")
        stmts = parse_general_log(text)
        base = set(baseline or before["rel"])
        rebuilt = sorted(t for t in base if t in before["rel"] and t in after["rel"]
                         and before["rel"][t]["node"] != after["rel"][t]["node"])
        batch = {}
        if self.decode_writes and before.get("binlog"):
            for (_txn, table), ops in self.decoded_writes(before["binlog"], after["binlog"]).items():
                batch[table] = max(batch.get(table, 0), sum(ops.values()))
        truncated = sorted({m.group(1) for s in stmts for m in [re.match(r"(?is)^\s*truncate\s+(?:table\s+)?`?(\w+)`?", s)]
                            if m})
        return {"step": step, "pre_names": sorted(base), "statements": stmts, "rewrites": rebuilt, "batch": batch,
                "truncated": truncated, "decoded": bool(self.decode_writes and before.get("binlog"))}

    def judge_locks(self, evidence, cfg):
        rules = cfg.get("rules") or ["online_ddl", "no_table_rebuild"]
        scope = cfg.get("scope", "all")
        excluded = {t.lower() for t in cfg.get("exclude") or []}
        out = {}
        for rule in rules:
            bad = []
            for e in evidence:
                pre = set(e["pre_names"])

                def ins(t):  # an existing table, not the migration tool's own bookkeeping table
                    return t in pre and (scope == "all" or t in scope) and (t or "").lower() not in excluded
                if rule == "online_ddl":
                    for s in e["statements"]:
                        m = re.match(r"(?is)^\s*(alter\s+table|create\s+(?:unique\s+)?index|drop\s+index)\s+"
                                     r"(?:\w+\s+on\s+)?`?(\w+)`?", s)
                        if not m:
                            continue
                        table = m.group(2)
                        if m.group(1).lower().startswith(("create", "drop")):
                            mm = re.search(r"(?is)\bon\s+`?(\w+)`?", s)
                            table = mm.group(1) if mm else table
                        if not ins(table):
                            continue
                        algo = re.search(r"(?i)\balgorithm\s*=?\s*(instant|inplace|copy|default)", s)
                        lock = re.search(r"(?i)\block\s*=?\s*(none|shared|exclusive|default)", s)
                        ok = algo and (algo.group(1).lower() == "instant" or
                                       (algo.group(1).lower() == "inplace" and lock and lock.group(1).lower() == "none"))
                        if not ok:
                            bad.append(f"{e['step']}: `{s[:110]}` on {table} must state ALGORITHM=INSTANT or "
                                       f"ALGORITHM=INPLACE, LOCK=NONE")
                elif rule == "no_table_rebuild":
                    bad += [f"{e['step']}: table {t} was rebuilt (its InnoDB table id changed)" for t in e["rewrites"]
                            if ins(t)]
                elif rule == "batched_writes":
                    if not e.get("decoded"):
                        raise RuntimeError("batched_writes needs the binary log of the step")
                    max_rows = int(cfg.get("max_rows_per_txn", 10000))
                    bad += [f"{e['step']}: one transaction wrote {n} rows of {t} (inserted, updated or deleted; "
                            f"limit {max_rows})" for t, n in sorted(e["batch"].items()) if n > max_rows and ins(t)]
                    bad += [f"{e['step']}: table {t} was truncated" for t in e.get("truncated", []) if ins(t)]
                else:
                    raise RuntimeError(f"unknown lock rule {rule}")
            out[rule] = (not bad, "; ".join(bad[:3]) + (f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""))
        return out

    # ---- catalog ----------------------------------------------------------------------------------------------------
    def catalog(self):
        with self.admin() as c:
            cur = c.cursor()
            db = self.db
            cur.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s", (db,))
            tables, views = {}, {}
            for name, ttype in cur.fetchall():
                if ttype == "VIEW":
                    views[name] = {"kind": "v"}
                else:
                    tables[name] = {"kind": "r", "rls": False, "force_rls": False, "partition_of": None,
                                    "partition_bound": None, "partition_key": None, "unlogged": False,
                                    "columns": {}, "column_order": []}
            cur.execute("""SELECT table_name, column_name, column_type, is_nullable, column_default, extra, collation_name
                           FROM information_schema.columns WHERE table_schema = %s ORDER BY table_name, ordinal_position""",
                        (db,))
            for t, col, typ, nullable, default, extra, coll in cur.fetchall():
                target = tables.get(t)
                if target is None:
                    if t in views:
                        views[t].setdefault("columns", {})[col] = typ
                    continue
                target["columns"][col] = {"type": typ, "not_null": nullable == "NO", "default": default,
                                          "identity": "auto_increment" if "auto_increment" in (extra or "") else None,
                                          "generated": "stored" if "GENERATED" in (extra or "").upper() else None,
                                          "collation": coll}
                target["column_order"].append(col)
            for v in views:
                cur.execute("SELECT view_definition FROM information_schema.views WHERE table_schema = %s AND "
                            "table_name = %s", (db, v))
                row = cur.fetchone()
                views[v]["definition"] = re.sub(r"\s+", " ", (row[0] if row else "") or "")
            constraints = {}
            cur.execute("""SELECT tc.table_name, tc.constraint_name, tc.constraint_type FROM information_schema.table_constraints tc
                           WHERE tc.table_schema = %s""", (db,))
            ctypes = cur.fetchall()
            cur.execute("""SELECT table_name, constraint_name, column_name, referenced_table_name, referenced_column_name
                           FROM information_schema.key_column_usage WHERE table_schema = %s
                           ORDER BY table_name, constraint_name, ordinal_position""", (db,))
            kcu = {}
            for t, cname, col, rt, rc in cur.fetchall():
                e = kcu.setdefault((t, cname), {"columns": [], "ref": rt, "ref_columns": []})
                e["columns"].append(col)
                if rc:
                    e["ref_columns"].append(rc)
            cur.execute("""SELECT table_name, constraint_name, delete_rule, update_rule FROM information_schema.referential_constraints
                           WHERE constraint_schema = %s""", (db,))
            rules = {(t, cn): (d.lower(), u.lower()) for t, cn, d, u in cur.fetchall()}
            cur.execute("""SELECT cc.constraint_name, cc.check_clause, tc.table_name, tc.enforced
                           FROM information_schema.check_constraints cc
                           JOIN information_schema.table_constraints tc ON tc.constraint_name = cc.constraint_name
                            AND tc.constraint_schema = cc.constraint_schema
                           WHERE cc.constraint_schema = %s""", (db,))
            checks = {(t, cn): (clause, enforced) for cn, clause, t, enforced in cur.fetchall()}
            for t, cname, ctype in ctypes:
                if t not in tables:
                    continue
                k = kcu.get((t, cname), {"columns": [], "ref": None, "ref_columns": []})
                kind = {"PRIMARY KEY": "primary_key", "UNIQUE": "unique", "FOREIGN KEY": "foreign_key",
                        "CHECK": "check"}.get(ctype, ctype.lower())
                d, u = rules.get((t, cname), (None, None))
                ck = checks.get((t, cname))
                constraints.setdefault(t, []).append({
                    "name": cname, "type": kind, "definition": ck[0] if ck else "", "validated": True,
                    "deferrable": False, "deferred": False, "columns": k["columns"], "references": k["ref"],
                    "ref_columns": k["ref_columns"], "on_delete": d.replace("_", " ") if d else None,
                    "on_update": u.replace("_", " ") if u else None, "enforced": (ck[1] if ck else "YES")})
            cur.execute("""SELECT table_name, index_name, non_unique, column_name, seq_in_index, index_type, expression
                           FROM information_schema.statistics WHERE table_schema = %s
                           ORDER BY table_name, index_name, seq_in_index""", (db,))
            idx = {}
            for t, iname, nonu, col, seq, itype, expr in cur.fetchall():
                e = idx.setdefault((t, iname), {"name": iname, "unique": not nonu, "primary": iname == "PRIMARY",
                                                "valid": True, "method": (itype or "").lower(), "columns": [],
                                                "predicate": None, "constraint": False})
                e["columns"].append(col if col else (expr or ""))
            indexes = {}
            for (t, iname), e in idx.items():
                if t in tables:
                    e["shape"] = f"{'UNIQUE ' if e['unique'] else ''}({', '.join(e['columns'])})"
                    indexes.setdefault(t, []).append(e)
            cur.execute("""SELECT event_object_table, trigger_name, action_timing, event_manipulation, action_statement
                           FROM information_schema.triggers WHERE trigger_schema = %s""", (db,))
            triggers = {}
            for t, name, timing, ev, stmt in cur.fetchall():
                triggers.setdefault(t, []).append({"name": name, "definition": f"{timing} {ev}", "enabled": "O",
                                                   "function": None, "body_md5": __import__("hashlib").md5(
                                                       (stmt or "").encode()).hexdigest()})
            cur.execute("SELECT routine_name, routine_type FROM information_schema.routines WHERE routine_schema = %s",
                        (db,))
            functions = sorted(f"{n}({t.lower()})" for n, t in cur.fetchall())
        return {"engine": self.kind, "tables": tables, "views": views, "constraints": constraints,
                "indexes": indexes, "triggers": triggers, "functions": functions, "sequences": {}, "enums": {},
                "policies": {}, "extensions": []}

    # ---- queries ----------------------------------------------------------------------------------------------------
    def run_statement(self, conn, sql, params, read_only, timeout_ms=30000, settings=None):
        import pymysql
        try:
            cur = conn.cursor()
            for k, v in (settings or {}).items():
                cur.execute(f"SET @{re.sub(r'[^A-Za-z0-9_]', '_', k)} = %s", (str(v),))
            cur.execute(f"SET SESSION max_execution_time = {int(timeout_ms)}")
            cur.execute("SET SESSION innodb_lock_wait_timeout = 10")
            conn.begin()
            if read_only:
                cur.execute("SET TRANSACTION READ ONLY") if False else None
            cur.execute(sql, params or None)
            rows = cur.fetchall() if cur.description else None
            cols = [d[0] for d in cur.description] if cur.description else None
            rc = cur.rowcount
            conn.commit()
            return {"columns": cols, "rows": [[norm_value(v) for v in r] for r in rows] if rows is not None else None,
                    "rowcount": rc}
        except pymysql.MySQLError as exc:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            code = exc.args[0] if exc.args else 0
            return {"error": mysql_sqlstate(code), "message": str(exc)[:200]}

    def app_session(self):
        return self.app(autocommit=False)

    def content_checksum(self, table, cols, types=None):
        """Row count and an order-independent hash of the given columns of every row -> a run_statement outcome;
        a missing table or column is an error outcome."""
        with self.admin() as c:
            if not cols:
                return self.run_statement(c, f"SELECT COUNT(*) FROM {q(table)}", None, read_only=True,
                                          timeout_ms=300000)
            c.cursor().execute("SET SESSION time_zone = '+00:00'")
            row = "CONCAT_WS(0x1f, " + ", ".join(f"COALESCE(CAST({q(col)} AS CHAR), 0x1e)" for col in cols) + ")"
            sql = (f"SELECT COUNT(*), SUM(CAST(CONV(SUBSTRING(MD5({row}), 1, 15), 16, 10) AS UNSIGNED)), "
                   f"SUM(CAST(CONV(SUBSTRING(MD5({row}), 16, 15), 16, 10) AS UNSIGNED)) FROM {q(table)}")
            return self.run_statement(c, sql, None, read_only=True, timeout_ms=600000)

    def table_checksum(self, table):
        """Row count and an order-independent content hash of one table -> a run_statement outcome."""
        with self.admin() as c:
            cur = c.cursor()
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
                        "ORDER BY ordinal_position", (self.db, table))
            cols = [r[0] for r in cur.fetchall()]
            if not cols:
                return {"error": "42S02", "message": f"table {table} does not exist"}
            row = "CONCAT_WS(0x1f, " + ", ".join(f"COALESCE(CAST({q(col)} AS CHAR), 0x1e)" for col in cols) + ")"
            sql = (f"SELECT COUNT(*), SUM(CAST(CONV(SUBSTRING(MD5({row}), 1, 15), 16, 10) AS UNSIGNED)), "
                   f"SUM(CAST(CONV(SUBSTRING(MD5({row}), 16, 15), 16, 10) AS UNSIGNED)) FROM {q(table)}")
            return self.run_statement(c, sql, None, read_only=True, timeout_ms=300000)


def mysql_sqlstate(code):
    """Map common MySQL error numbers to SQLSTATE classes (integrity errors -> 23xxx)."""
    integrity = {1062: "23000", 1451: "23000", 1452: "23000", 1048: "23000", 3819: "23000", 1216: "23000",
                 1217: "23000", 1557: "23000", 1586: "23000"}
    if code in integrity:
        return integrity[code]
    if code in (1146, 1054, 1064, 1109, 1356):
        return "42000"
    return f"HY{int(code):03d}"[:5] if isinstance(code, int) else "HY000"


def parse_general_log(text):
    """Statements the application account ran, from the MySQL general log (Query lines of its connections)."""
    conns, stmts, cur = {}, [], None
    for line in text.splitlines():
        m = re.match(r"^(?:\S+Z)?\s*(\d+)\s+(Connect|Query|Quit|Init DB|Prepare|Execute|Close stmt)\t?(.*)$", line)
        if m:
            tid, kind, rest = int(m.group(1)), m.group(2), m.group(3)
            if kind == "Connect":
                conns[tid] = rest
                cur = None
            elif kind in ("Query", "Execute"):
                cur = [tid, rest]
                stmts.append(cur)
            else:
                cur = None
        elif cur is not None and line and not re.match(r"^/\S+, Version:|^Tcp port:|^Time\s+Id", line):
            cur[1] += "\n" + line
    users = {tid for tid, info in conns.items() if not info.startswith("root@")}
    return [s for tid, s in stmts if tid in users and not s.startswith("SELECT 'dbm-mark")]
