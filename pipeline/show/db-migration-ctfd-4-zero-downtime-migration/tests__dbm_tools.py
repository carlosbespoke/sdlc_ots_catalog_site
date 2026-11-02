"""Migration-tool adapters: run the submission's migrations exactly as the team's deploy pipeline does, as an
unprivileged OS user, against the scenario's database. Implemented: alembic, liquibase, golang-migrate. Designed (same
interface): flyway, goose, django, prisma, knex, rails, sqitch."""
import json
import os
import re
import shutil
from pathlib import Path

from dbm_util import chown_tree, is_root, run_tool, tail, user_ids

VENV = Path(os.environ.get("DBM_VENV", "/opt/dbm/venv"))
LIQUIBASE_HOME = Path(os.environ.get("DBM_LIQUIBASE_HOME", "/opt/liquibase"))
JAVA_HOME = Path(os.environ.get("DBM_JAVA_HOME", "/opt/java"))


class ToolResult:
    def __init__(self, code, output, leftovers=0):
        self.code, self.output, self.leftovers = code, output, leftovers

    @property
    def ok(self):
        return self.code == 0


class Tool:
    name = "tool"

    def __init__(self, repo, engine, cfg, run_as=None, timeout=1800):
        self.repo = Path(repo)
        self.engine = engine
        self.cfg = cfg or {}
        self.run_as = run_as if is_root() else None
        self.timeout = int(self.cfg.get("timeout_s", timeout))
        self.cwd = self.repo / self.cfg.get("cwd", ".")
        self.home = self.repo.parent / "solver-home"
        self.home.mkdir(parents=True, exist_ok=True)
        if self.run_as:
            chown_tree(self.repo, self.run_as)
            chown_tree(self.home, self.run_as)

    def base_env(self):
        return {"PATH": f"{VENV}/bin:{JAVA_HOME}/bin:/usr/local/bin:/usr/bin:/bin", "HOME": str(self.home),
                "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(self.cwd)}

    def _run(self, cmd, env=None):
        code, output, left = run_tool(cmd, user=self.run_as, env={**self.base_env(), **(env or {})},
                                      cwd=str(self.cwd), timeout=self.timeout)
        self.engine.terminate_app_sessions()
        return ToolResult(code, output, left)


class AlembicTool(Tool):
    name = "alembic"

    def env(self):
        return {**self.engine.env_for_tools(), self.cfg.get("url_env", "DATABASE_URL"): self.engine.tool_url()}

    def cmd(self, *args):
        return [str(VENV / "bin" / "alembic"), "-c", self.cfg.get("config", "alembic.ini"), *args]

    def migrate(self, target):
        return self._run(self.cmd("upgrade", target), self.env())

    def rollback(self, target):
        return self._run(self.cmd("downgrade", target), self.env())

    def stamp(self, target):
        return self._run(self.cmd("stamp", target), self.env())

    def current(self):
        return self.engine.current_revision(self.cfg.get("version_table", "alembic_version"))

    def graph(self):
        """{"heads": [...], "down": {rev: [down revisions]}} of the submission's script directory (its revision
        files are imported, so this runs as the solver too)."""
        code = ("import json,sys\nfrom alembic.config import Config\nfrom alembic.script import ScriptDirectory\n"
                f"sd = ScriptDirectory.from_config(Config({self.cfg.get('config', 'alembic.ini')!r}))\n"
                "down = {}\nfor r in sd.walk_revisions():\n"
                "    d = r.down_revision\n    down[r.revision] = list(d) if isinstance(d, (tuple, list)) else ([d] if d else [])\n"
                "print('DBM-GRAPH ' + json.dumps({'heads': list(sd.get_heads()), 'down': down}))\n")
        res = self._run([str(VENV / "bin" / "python3"), "-c", code], self.env())
        m = re.search(r"^DBM-GRAPH (.*)$", res.output, re.M)
        if not m:
            return None, tail(res.output, 15)
        return json.loads(m.group(1)), None


class LiquibaseTool(Tool):
    """Liquibase 4.33 (the last Apache-2.0 release) driven by the repository's liquibase.properties-equivalent
    settings from the spec (changelog file, contexts, labels). The JDBC URL points at the scenario's database."""
    name = "liquibase"

    def jdbc(self):
        return self.engine.jdbc_url()

    def args(self):
        a = [f"--changelog-file={self.cfg.get('changelog', 'db/changelog/db.changelog-master.xml')}",
             f"--url={self.jdbc()}", f"--username={self.engine.role}", f"--password={self.engine.password}",
             "--log-level=WARNING", "--show-banner=false"]
        if self.cfg.get("contexts"):
            a.append(f"--contexts={self.cfg['contexts']}")
        if self.cfg.get("labels"):
            a.append(f"--label-filter={self.cfg['labels']}")
        if self.cfg.get("search_path"):
            a.append(f"--search-path={self.cfg['search_path']}")
        return a

    def cmd(self, command, *extra):
        java_opts = "-Xmx512m -XX:TieredStopAtLevel=1 -Duser.timezone=UTC"
        return [str(LIQUIBASE_HOME / "liquibase"), *self.args(), command, *extra], {
            "JAVA_OPTS": java_opts, "LIQUIBASE_HOME": str(LIQUIBASE_HOME), "JAVA_HOME": str(JAVA_HOME),
            "LIQUIBASE_ANALYTICS_ENABLED": "false", "LIQUIBASE_SHOW_BANNER": "false"}

    def _lb(self, command, *extra):
        cmd, env = self.cmd(command, *extra)
        return self._run(cmd, env)

    def migrate(self, target):
        if target in (None, "", "head", "latest"):
            return self._lb("update")
        return self._lb("update-to-tag", f"--tag={target}")

    def rollback(self, target):
        return self._lb("rollback", f"--tag={target}")

    def stamp(self, target):
        if target in (None, "", "head", "latest"):
            return self._lb("changelog-sync")
        return self._lb("changelog-sync-to-tag", f"--tag={target}")

    def validate(self):
        return self._lb("validate")

    def status(self):
        return self._lb("status", "--verbose")

    def current(self):
        return self.engine.changelog_state(self.cfg.get("changelog_table", "DATABASECHANGELOG"))

    @staticmethod
    def pending(output):
        """Pending changesets from `liquibase status --verbose` output (None when it cannot tell)."""
        if re.search(r"is up to date", output):
            return 0
        m = re.search(r"(\d+) changesets? (?:have|has) not been applied", output)
        return int(m.group(1)) if m else None


class GoMigrateTool(Tool):
    """golang-migrate v4 (MIT): numbered `<version>_<title>.up.sql` / `.down.sql` files in one directory, the state in
    schema_migrations (version, dirty). The pipeline runs `migrate -path <dir> -database $DATABASE_URL goto <version>`
    (`up` for the newest); `goto` also migrates down; `force <version>` records a version without running it."""
    name = "migrate"

    def cmd(self, *args):
        return [self.cfg.get("binary", "/usr/local/bin/migrate"), "-path", self.cfg.get("path", "migrations"),
                "-database", self.engine.migrate_url(), *args]

    def migrate(self, target):
        if target in (None, "", "head", "latest"):
            return self._run(self.cmd("up"))
        return self._run(self.cmd("goto", str(target)))

    def rollback(self, target):
        if str(target) in ("0", "base", "nil", "none"):
            return self._run(self.cmd("down", "-all"))
        return self._run(self.cmd("goto", str(target)))

    def stamp(self, target):
        return self._run(self.cmd("force", str(target)))

    def current(self):
        """[version] (with " (dirty)" when the last migration failed half way), [] before the first migration."""
        rows = self.engine.query_rows(f"SELECT version, dirty FROM {self.cfg.get('version_table', 'schema_migrations')}")
        if rows is None:
            return []
        return sorted(f"{v}{' (dirty)' if d else ''}" for v, d in rows)


TOOLS = {"alembic": AlembicTool, "liquibase": LiquibaseTool, "golang-migrate": GoMigrateTool}


def make_tool(name, repo, engine, cfg, run_as):
    if name not in TOOLS:
        raise RuntimeError(f"tool {name!r} has no adapter yet (implemented: {sorted(TOOLS)})")
    return TOOLS[name](repo, engine, cfg, run_as)


def prepare_repo(src, dst, run_as):
    """A private copy of the submission for one scenario (the solver's code may write next to itself)."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    if run_as and user_ids(run_as) and is_root():
        chown_tree(dst, run_as)
    return dst
