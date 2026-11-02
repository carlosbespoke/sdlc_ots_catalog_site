#!/usr/bin/env python3
"""platformctl: lifecycle of a task's live platform services, restored from a snapshot. Backend-agnostic core with one
adapter per backend (postgres, vault, grafana); a task lists its backends in /opt/platform/platform.json
({"backends": ["postgres", "vault"]}) or via --backends.

Used unchanged in three places: the agent image (the healthcheck runs `up`, the solver runs `platform-reset`), the
verifier (a fresh instance per graded run) and the build tools (`init` + `snapshot` create the snapshot).

  platformctl.py up       [--root R] [--snapshot S] [--user U]  restore (when R holds no data) + start; idempotent; exit 0
                                                                only when every backend is ready
  platformctl.py ready    [--root R]                            exit 0 when every backend answers
  platformctl.py down     [--root R]                            stop every backend
  platformctl.py reset    [--root R] [--snapshot S] [--user U]  down + wipe + up, and restore the pristine tool state
  platformctl.py init     --root R --out S [--user U]           (build) brand-new services; their secrets go to S
  platformctl.py snapshot --root R --out S                      (build) dump/stop/archive every backend into S

Run as root, the services run as --user (default: the owner of R, else `agent`); run as any other user, they run as that
user. Every daemon is fully detached (own session, no inherited stdio) so a `docker exec` healthcheck returns at once.
Snapshot files (S): postgres.sql + postgres.password; vault-data.tar.gz + vault-unseal.key + vault-root.token;
grafana.db + grafana-admin.password; terraform.tfstate (the tool state, restored to R/terraform/ on up/reset).
Endpoints: PostgreSQL 127.0.0.1:5432 (scram over TCP, trust on the private socket dir R/pg/run), Vault
http://127.0.0.1:8200, Grafana http://127.0.0.1:3000.
"""
import argparse
import fcntl
import hashlib
import json
import os
import pwd
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path("/opt/platform/platform.json")


def say(msg):
    print(f"[platform] {msg}", flush=True)

def ensure_identity():
    """initdb (and libpq's defaults) need the current uid in /etc/passwd. Tools run as an arbitrary uid (docker -u) have
    none: fake one with nss_wrapper (shipped by the postgres base image, as its own entrypoint does). Sets os.environ, so
    every child process inherits it. No-op as root or when the uid exists."""
    if os.geteuid() == 0 or os.environ.get("NSS_WRAPPER_PASSWD"):
        return
    try:
        pwd.getpwuid(os.geteuid())
        return
    except KeyError:
        pass
    lib = next((p for p in ("/usr/lib/x86_64-linux-gnu/libnss_wrapper.so", "/usr/lib/libnss_wrapper.so")
                if os.path.exists(p)), None)
    if not lib:
        return
    uid, gid = os.geteuid(), os.getegid()
    d = Path(os.environ.get("TMPDIR", "/tmp")) / f".nss-{uid}"
    d.mkdir(exist_ok=True)
    home = os.environ.get("HOME", "/tmp")
    (d / "passwd").write_text(Path("/etc/passwd").read_text() + f"livesvc:x:{uid}:{gid}:livesvc:{home}:/bin/bash\n")
    (d / "group").write_text(Path("/etc/group").read_text() + f"livesvc:x:{gid}:\n")
    os.environ.update({"LD_PRELOAD": lib, "NSS_WRAPPER_PASSWD": str(d / "passwd"), "NSS_WRAPPER_GROUP": str(d / "group")})
    os.environ.setdefault("USER", "livesvc")



def die(msg, code=1):
    print(f"[platform] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def tail(path, n=1500):
    try:
        return Path(path).read_text(errors="replace")[-n:]
    except OSError:
        return ""


def http(base, method, path, body=None, headers=None, timeout=10, raw=False):
    data = (body if isinstance(body, bytes) else json.dumps(body).encode()) if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data is not None and not any(k.lower() == "content-type" for k in (headers or {})):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            return r.status, (payload if raw else (json.loads(payload) if payload.strip() else {}))
    except urllib.error.HTTPError as e:
        payload = e.read()
        if raw:
            return e.code, payload
        try:
            return e.code, (json.loads(payload) if payload.strip() else {})
        except ValueError:
            return e.code, {"raw": payload.decode(errors="replace")[:500]}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return 0, {}


class Ctx:
    def __init__(self, root, snapshot=None, user=None):
        self.root = Path(root)
        self.snapshot = Path(snapshot) if snapshot else None
        if os.geteuid() == 0:
            if user is None:
                user = "agent"
                try:
                    if self.root.exists():
                        owner = pwd.getpwuid(self.root.stat().st_uid).pw_name
                        if owner != "root":
                            user = owner
                except KeyError:
                    pass
            try:
                self.pw = pwd.getpwnam(user)
            except KeyError:
                die(f"unknown user {user!r}: create it or pass --user")
        else:
            try:
                self.pw = pwd.getpwuid(os.geteuid())
            except KeyError:  # an arbitrary uid (docker -u): children see it through nss_wrapper
                from types import SimpleNamespace
                self.pw = SimpleNamespace(pw_name=os.environ.get("USER", "livesvc"), pw_uid=os.geteuid(),
                                          pw_gid=os.getegid(), pw_dir=os.environ.get("HOME", "/tmp"))
            user = self.pw.pw_name
        self.user = user
        self.state = self.root / "terraform" / "terraform.tfstate"

    def as_user(self):
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TZ", "LD_PRELOAD",
                                                             "NSS_WRAPPER_PASSWD", "NSS_WRAPPER_GROUP")}
        env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        env["PATH"] = f"{Postgres.BIN}:{env['PATH']}"
        if os.geteuid() == 0 and self.pw.pw_uid != 0:
            return {"user": self.pw.pw_uid, "group": self.pw.pw_gid, "extra_groups": [],
                    "env": {**env, "HOME": self.pw.pw_dir or "/tmp", "USER": self.user}}
        return {"env": {**env, "HOME": os.environ.get("HOME", "/tmp")}}

    def run(self, cmd, check=True, timeout=300):
        p = subprocess.run([str(x) for x in cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=timeout, **self.as_user())
        if check and p.returncode != 0:
            die(f"{' '.join(map(str, cmd))} failed ({p.returncode}): {(p.stdout + p.stderr)[-1500:]}")
        return p

    def spawn(self, cmd, log):
        """Start a fully detached daemon as the service user; returns its pid."""
        f = open(log, "ab")
        p = subprocess.Popen([str(x) for x in cmd], stdin=subprocess.DEVNULL, stdout=f, stderr=f, start_new_session=True,
                             close_fds=True, **self.as_user())
        return p

    def mkdirs(self, *dirs, mode=None):
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            self.chown(d)
            if mode is not None:
                os.chmod(d, mode)

    def chown(self, path, recursive=False):
        if os.geteuid() != 0:
            return
        paths = [path]
        if recursive:
            for dirpath, dirnames, filenames in os.walk(path):
                paths += [os.path.join(dirpath, n) for n in dirnames + filenames]
        for p in paths:
            try:
                os.chown(p, self.pw.pw_uid, self.pw.pw_gid, follow_symlinks=False)
            except FileNotFoundError:
                pass

    def secret(self, name):
        return (self.snapshot / name).read_text().strip()


def alive(pid):
    """True while the process runs. A zombie counts as gone: in a container whose PID 1 never reaps (sleep infinity),
    a stopped daemon stays in the process table and kill(pid, 0) keeps succeeding."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return state not in ("Z", "X")
    except (OSError, IndexError):
        return True


def stop_pid(pidfile):
    try:
        pid = int(Path(pidfile).read_text())
    except (OSError, ValueError):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        Path(pidfile).unlink(missing_ok=True)
        return
    for _ in range(300):
        if not alive(pid):
            break
        time.sleep(0.05)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        for _ in range(100):
            if not alive(pid):
                break
            time.sleep(0.05)
    Path(pidfile).unlink(missing_ok=True)


def pid_alive(pidfile):
    try:
        return alive(int(Path(pidfile).read_text()))
    except (OSError, ValueError):
        return False


# ---- backends ---------------------------------------------------------------------------------------------------------
class Postgres:
    BIN = Path("/usr/lib/postgresql/17/bin")
    PORT = 5432

    def __init__(self, c):
        self.c = c
        self.dir = c.root / "pg"
        self.data = self.dir / "data"
        self.run_dir = self.dir / "run"

    def has_data(self):
        return (self.data / "PG_VERSION").exists()

    def running(self):
        return self.has_data() and self.c.run([self.BIN / "pg_ctl", "-D", self.data, "status"], check=False).returncode == 0

    def ready(self):
        return subprocess.run([str(self.BIN / "pg_isready"), "-h", "127.0.0.1", "-p", str(self.PORT), "-t", "2"],
                              stdin=subprocess.DEVNULL, capture_output=True).returncode == 0

    def initdb(self, password):
        self.c.mkdirs(self.dir)
        self.c.mkdirs(self.run_dir, mode=0o700)
        pwfile = self.dir / ".pw"
        pwfile.write_text(password + "\n")
        self.c.chown(pwfile)
        os.chmod(pwfile, 0o600)
        self.c.run([self.BIN / "initdb", "-D", self.data, "-U", "postgres", "--auth-local=trust",
                    "--auth-host=scram-sha-256", f"--pwfile={pwfile}", "-E", "UTF8", "--locale=C.UTF-8",
                    "--no-instructions"], timeout=180)
        pwfile.unlink()
        (self.data / "pg_hba.conf").write_text(
            "local all all trust\nhost all all 127.0.0.1/32 scram-sha-256\nhost all all ::1/128 scram-sha-256\n")

    def start(self):
        opts = (f"-c listen_addresses=127.0.0.1 -c port={self.PORT} -c unix_socket_directories={self.run_dir} "
                "-c max_connections=300 -c fsync=off -c synchronous_commit=off -c full_page_writes=off")
        self.c.run([self.BIN / "pg_ctl", "-D", self.data, "-l", self.dir / "server.log", "-w", "-t", "90", "-o", opts,
                    "start"], timeout=120)

    def psql(self, *args, timeout=600):
        return self.c.run([self.BIN / "psql", "-X", "-q", "-h", self.run_dir, "-p", str(self.PORT), "-U", "postgres",
                           "-d", "postgres", "-v", "ON_ERROR_STOP=1", *args], timeout=timeout)

    def restore(self):
        self.initdb(self.c.secret("postgres.password"))
        self.start()
        self.psql("-f", self.c.snapshot / "postgres.sql")

    def up(self):
        if not self.has_data():
            self.restore()
        elif not self.running():
            self.c.mkdirs(self.run_dir, mode=0o700)
            self.start()

    def down(self):
        if self.running():
            self.c.run([self.BIN / "pg_ctl", "-D", self.data, "-m", "fast", "-w", "-t", "60", "stop"], check=False,
                       timeout=90)

    def init(self, out):
        password = secrets.token_urlsafe(18)
        self.initdb(password)
        self.start()
        (out / "postgres.password").write_text(password + "\n")

    def snapshot(self, out):
        dump = self.c.run([self.BIN / "pg_dumpall", "-h", self.run_dir, "-p", str(self.PORT), "-U", "postgres",
                           "--no-comments"], timeout=600).stdout
        # the bootstrap superuser already exists in a fresh cluster: keep its ALTER ROLE (password), drop its CREATE
        lines = [ln for ln in dump.splitlines() if ln.strip() != "CREATE ROLE postgres;"]
        (out / "postgres.sql").write_text("\n".join(lines) + "\n")
        self.down()

    def wipe(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Vault:
    ADDR = "http://127.0.0.1:8200"
    AUDIT_DIR = Path("/var/log/vault")

    def __init__(self, c):
        self.c = c
        self.dir = c.root / "vault"
        self.data = self.dir / "data"
        self.pidfile = self.dir / "vault.pid"

    def has_data(self):
        return self.data.exists()

    def status(self):
        code, body = http(self.ADDR, "GET", "/v1/sys/seal-status", timeout=3)
        return (code == 200, bool(body.get("initialized")) if code == 200 else False,
                bool(body.get("sealed")) if code == 200 else True)

    def ready(self):
        return http(self.ADDR, "GET", "/v1/sys/health", timeout=3)[0] == 200

    def start(self):
        self.c.mkdirs(self.dir)
        if os.geteuid() == 0:
            self.c.mkdirs(self.AUDIT_DIR)
        cfg = self.dir / "vault.hcl"
        cfg.write_text(f'storage "file" {{\n  path = "{self.data}"\n}}\nlistener "tcp" {{\n  address     = "127.0.0.1:8200"\n'
                       f'  tls_disable = true\n}}\ndisable_mlock = true\napi_addr      = "{self.ADDR}"\nui            = false\n'
                       'log_level     = "warn"\n')
        self.c.chown(cfg)
        p = self.c.spawn(["vault", "server", f"-config={cfg}"], self.dir / "server.log")
        self.pidfile.write_text(str(p.pid))
        for _ in range(300):
            if self.status()[0]:
                return
            if p.poll() is not None:
                die(f"vault server exited ({p.returncode}): {tail(self.dir / 'server.log')}")
            time.sleep(0.1)
        die(f"vault server did not answer: {tail(self.dir / 'server.log')}")

    def unseal(self, key):
        code, body = http(self.ADDR, "PUT", "/v1/sys/unseal", {"key": key})
        if code != 200 or body.get("sealed"):
            die(f"vault unseal failed ({code}): {body}")
        for _ in range(300):
            if self.ready():
                return
            time.sleep(0.1)
        die("vault did not become active after unseal")

    def restore(self):
        self.c.mkdirs(self.dir)
        self.data.mkdir(parents=True)
        with tarfile.open(self.c.snapshot / "vault-data.tar.gz") as t:
            members = t.getmembers()
            bad = [m.name for m in members if m.name.startswith("/") or ".." in Path(m.name).parts
                   or not (m.isfile() or m.isdir())]
            if bad:
                die(f"unsafe entries in the vault snapshot: {bad[:5]}")
            t.extractall(self.data, members=members)  # bookworm's python 3.11.2 has no extraction filters
        self.c.chown(self.data, recursive=True)
        os.chmod(self.data, 0o700)

    def up(self):
        if not self.has_data():
            self.restore()
        if not pid_alive(self.pidfile):
            if self.status()[0]:
                die(f"port 8200 already answers but no vault of {self.c.root} runs: stop the other server first")
            self.start()
        ok, _, sealed = self.status()
        if ok and sealed:
            self.unseal(self.c.secret("vault-unseal.key"))

    def down(self):
        stop_pid(self.pidfile)

    def init(self, out):
        self.c.mkdirs(self.dir)
        self.data.mkdir(parents=True)
        self.c.chown(self.data)
        os.chmod(self.data, 0o700)
        self.start()
        code, body = http(self.ADDR, "PUT", "/v1/sys/init", {"secret_shares": 1, "secret_threshold": 1})
        if code != 200:
            die(f"vault init failed ({code}): {body}")
        self.unseal(body["keys_base64"][0])
        (out / "vault-unseal.key").write_text(body["keys_base64"][0] + "\n")
        (out / "vault-root.token").write_text(body["root_token"] + "\n")

    def snapshot(self, out):
        self.down()
        with tarfile.open(out / "vault-data.tar.gz", "w:gz") as t:
            for p in sorted(self.data.rglob("*")):
                ti = t.gettarinfo(str(p), arcname=str(p.relative_to(self.data)))
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                ti.mtime = 0
                if p.is_file():
                    with open(p, "rb") as f:
                        t.addfile(ti, f)
                else:
                    t.addfile(ti)

    def wipe(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        try:
            for f in self.AUDIT_DIR.glob("*.log"):
                f.unlink()
        except OSError:
            pass


class Grafana:
    ADDR = "http://127.0.0.1:3000"
    HOME = Path("/usr/share/grafana")

    def __init__(self, c):
        self.c = c
        self.dir = c.root / "grafana"
        self.db = self.dir / "data" / "grafana.db"
        self.pidfile = self.dir / "grafana.pid"

    def has_data(self):
        return self.db.exists()

    def ready(self):
        code, body = http(self.ADDR, "GET", "/api/health", timeout=3)
        return code == 200 and body.get("database") == "ok"

    def write_config(self):
        self.c.mkdirs(self.dir, self.dir / "data", self.dir / "logs", self.dir / "plugins", self.dir / "provisioning")
        for sub in ("datasources", "dashboards", "alerting", "plugins", "notifiers", "access-control"):
            self.c.mkdirs(self.dir / "provisioning" / sub)
        ini = self.dir / "grafana.ini"
        ini.write_text(f"""[paths]
data = {self.dir / 'data'}
logs = {self.dir / 'logs'}
plugins = {self.dir / 'plugins'}
provisioning = {self.dir / 'provisioning'}
[server]
http_addr = 127.0.0.1
http_port = 3000
[database]
type = sqlite3
path = {self.db}
[analytics]
reporting_enabled = false
check_for_updates = false
check_for_plugin_updates = false
feedback_links_enabled = false
[security]
disable_initial_admin_creation = false
[users]
allow_sign_up = false
[auth.anonymous]
enabled = false
[news]
news_feed_enabled = false
[plugins]
preinstall_disabled = true
[log]
mode = file
level = warn
[unified_alerting]
enabled = true
[unified_alerting.state_history]
enabled = false
""")
        self.c.chown(ini)
        return ini

    def start(self, admin_password):
        ini = self.write_config()
        env_pw = self.dir / ".admin"
        env_pw.write_text(admin_password)
        self.c.chown(env_pw)
        os.chmod(env_pw, 0o600)
        p = self.c.spawn(["grafana", "server", f"--homepath={self.HOME}", f"--config={ini}",
                          f"cfg:default.security.admin_password={admin_password}"], self.dir / "server.log")
        self.pidfile.write_text(str(p.pid))
        for _ in range(900):
            if self.ready():
                return
            if p.poll() is not None:
                die(f"grafana exited ({p.returncode}): {tail(self.dir / 'server.log')}")
            time.sleep(0.1)
        die(f"grafana did not answer: {tail(self.dir / 'server.log')}")

    def restore(self):
        self.c.mkdirs(self.dir, self.dir / "data")
        shutil.copy(self.c.snapshot / "grafana.db", self.db)
        self.c.chown(self.db)

    def up(self):
        if not self.has_data():
            self.restore()
        if not pid_alive(self.pidfile):
            if self.ready():
                die(f"port 3000 already answers but no grafana of {self.c.root} runs: stop the other server first")
            self.start(self.c.secret("grafana-admin.password"))

    def down(self):
        stop_pid(self.pidfile)

    def init(self, out):
        password = secrets.token_urlsafe(18)
        self.start(password)
        (out / "grafana-admin.password").write_text(password + "\n")

    def snapshot(self, out):
        self.down()
        shutil.copy(self.db, out / "grafana.db")
        os.chmod(out / "grafana.db", 0o644)  # Grafana creates it 0640: image builds read it as another user

    def wipe(self):
        shutil.rmtree(self.dir, ignore_errors=True)


ADAPTERS = {"postgres": Postgres, "vault": Vault, "grafana": Grafana}


# ---- core -------------------------------------------------------------------------------------------------------------
def backends(c, names):
    return [ADAPTERS[n](c) for n in names]


def restore_state(c):
    if not c.state.exists() and c.snapshot and (c.snapshot / "terraform.tfstate").exists():
        c.mkdirs(c.state.parent)
        shutil.copy(c.snapshot / "terraform.tfstate", c.state)
        c.chown(c.state)


def cmd_up(c, names):
    t0 = time.time()
    if c.snapshot is None or not c.snapshot.is_dir():
        die(f"no snapshot at {c.snapshot}")
    c.mkdirs(c.root)
    for b in backends(c, names):
        b.up()
    restore_state(c)
    if not all(b.ready() for b in backends(c, names)):
        die("services started but are not ready", 3)
    say(f"{', '.join(names)} ready ({time.time() - t0:.1f}s)")


def cmd_down(c, names):
    for b in reversed(backends(c, names)):
        b.down()
    say("services stopped")


def cmd_reset(c, names):
    cmd_down(c, names)
    for b in backends(c, names):
        b.wipe()
    shutil.rmtree(c.root / "terraform", ignore_errors=True)
    cmd_up(c, names)
    say("reset to the snapshot: services, their data and the terraform state are as they were at the start")


def cmd_init(c, names, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if c.root.exists() and any(c.root.iterdir()):
        die(f"{c.root} is not empty")
    c.mkdirs(c.root, c.root / "terraform")
    for b in backends(c, names):
        b.init(out)
    say(f"initialised {', '.join(names)} under {c.root}; secrets in {out}")


def cmd_snapshot(c, names, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for b in reversed(backends(c, names)):
        b.snapshot(out)
    if c.state.exists():
        shutil.copy(c.state, out / "terraform.tfstate")
    say(f"snapshot written to {out}")


def main():
    ensure_identity()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["up", "ready", "down", "reset", "init", "snapshot"])
    ap.add_argument("--root", default=os.environ.get("PLATFORM_ROOT", "/var/lib/platform"))
    ap.add_argument("--snapshot", default=os.environ.get("PLATFORM_SNAPSHOT", "/opt/platform/snapshot"))
    ap.add_argument("--user", default=os.environ.get("PLATFORM_USER"))
    ap.add_argument("--backends", help="comma-separated; default from /opt/platform/platform.json")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.backends:
        names = a.backends.split(",")
    elif CONFIG.exists():
        names = json.loads(CONFIG.read_text())["backends"]
    else:
        die("no backends: pass --backends or write /opt/platform/platform.json")
    unknown = [n for n in names if n not in ADAPTERS]
    if unknown:
        die(f"unknown backends {unknown}; known: {sorted(ADAPTERS)}")
    c = Ctx(a.root, a.snapshot, a.user)
    if a.command == "ready":
        sys.exit(0 if all(b.ready() for b in backends(c, names)) else 1)
    # one lifecycle operation at a time per root (the healthcheck and the solver's platform-reset may overlap)
    lock = Path(f"/tmp/.platformctl-{hashlib.sha256(str(c.root.resolve()).encode()).hexdigest()[:12]}.lock")
    try:
        fd = os.open(lock, os.O_RDONLY | os.O_CREAT, 0o666)
        try:
            os.chmod(lock, 0o666)
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        pass
    if a.command == "ready":
        sys.exit(0 if all(b.ready() for b in backends(c, names)) else 1)
    if a.command in ("init", "snapshot") and not a.out:
        die("--out is required")
    {"up": lambda: cmd_up(c, names), "down": lambda: cmd_down(c, names), "reset": lambda: cmd_reset(c, names),
     "init": lambda: cmd_init(c, names, a.out), "snapshot": lambda: cmd_snapshot(c, names, a.out)}[a.command]()


if __name__ == "__main__":
    main()
