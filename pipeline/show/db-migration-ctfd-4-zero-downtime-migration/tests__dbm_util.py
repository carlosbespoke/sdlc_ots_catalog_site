"""Shared helpers for the dbmigrate grader: running commands as other OS users, value normalization, hashing."""
import datetime
import decimal
import hashlib
import ipaddress
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

VERBOSE = os.environ.get("DBM_VERBOSE") == "1"


def say(msg):
    print(f"[grade] {msg}", flush=True)


def debug(msg):
    if VERBOSE:
        print(f"[grade:debug] {msg}", flush=True)


def is_root():
    return os.geteuid() == 0


def user_ids(name):
    """(uid, gid, home) of an OS user, or None when it does not exist."""
    try:
        p = pwd.getpwnam(name)
        return p.pw_uid, p.pw_gid, p.pw_dir
    except KeyError:
        return None


def as_user(cmd, user):
    """Prefix a command so it runs as `user` when we are root (no-op otherwise)."""
    if user and is_root() and user != "root":
        return ["setpriv", f"--reuid={user}", f"--regid={user}", "--init-groups", "--"] + list(cmd)
    return list(cmd)


_NSS = None


def nss_env():
    """LD_PRELOAD nss_wrapper with a passwd entry for the current uid when it has none (the authoring container runs
    as an arbitrary uid; initdb and mysqld look their user up)."""
    global _NSS
    if _NSS is not None:
        return _NSS
    _NSS = {}
    if is_root():
        return _NSS
    try:
        pwd.getpwuid(os.getuid())
        return _NSS
    except KeyError:
        pass
    lib = os.environ.get("DBM_NSS_WRAPPER") or "/usr/lib/x86_64-linux-gnu/libnss_wrapper.so"
    if not os.path.exists(lib):
        return _NSS
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="dbm-nss-"))
    (d / "passwd").write_text(Path("/etc/passwd").read_text() + f"dbm:x:{os.getuid()}:{os.getgid()}:dbm:/tmp:/bin/sh\n")
    (d / "group").write_text(Path("/etc/group").read_text() + f"dbm:x:{os.getgid()}:\n")
    _NSS = {"LD_PRELOAD": lib, "NSS_WRAPPER_PASSWD": str(d / "passwd"), "NSS_WRAPPER_GROUP": str(d / "group")}
    return _NSS


def run(cmd, user=None, env=None, cwd=None, timeout=900, stdin=None, clean_env=False):
    """Run a command (optionally as another user); returns CompletedProcess with text output, never raises on exit."""
    base = {} if clean_env else dict(os.environ)
    full = {**base, **nss_env(), **(env or {})}
    try:
        return subprocess.run(as_user(cmd, user), env=full, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              input=stdin, errors="replace")
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(cmd, 124, out, err + f"\n[timed out after {timeout}s]")


def run_tool(cmd, user=None, env=None, cwd=None, timeout=1800):
    """Run the submission's migration tool: output to a file (a leftover child holding a pipe cannot stall the
    grader), its own process group, a hard timeout. Returns (exit code, output, leftover process count); leftovers in
    the group are killed (and, as root, every process of the user)."""
    import signal
    import tempfile
    full = {**(env or {}), **nss_env()}
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(as_user(cmd, user), env=full, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = 124
        left = 0
        try:
            os.killpg(p.pid, 0)
            left = 1
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if code == 124:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        if user and is_root():
            left += kill_user_processes(user)
        out.seek(0)
        text = out.read().decode(errors="replace")
    if code == 124:
        text += f"\n[timed out after {timeout}s]"
    return code, text, (left if code != 124 else 0)


def kill_user_processes(user):
    """Kill every process of an OS user (the solver's leftovers after a tool run). Returns how many there were."""
    ids = user_ids(user)
    if not ids or not is_root():
        return 0
    uid = ids[0]
    found = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            if d.stat().st_uid == uid and int(d.name) != os.getpid():
                found.append(int(d.name))
        except OSError:
            pass
    for pid in found:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    return len(found)


def error_digest(text, n=6):
    """The root-cause line of a failed tool run (the database error, not the end of a traceback) and the last lines."""
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    key = [ln.strip() for ln in lines if re.search(
        r"(psycopg\.errors\.\w+|sqlalchemy\.exc\.\w+|pymysql\.err\.\w+|\bERROR\b:|Caused by:|Reason:|FATAL|"
        r"error: |Error: )", ln)]
    head = key[-1][:400] if key else ""
    rest = tail(text, n)
    return (head + " | " + rest) if head and head not in rest else rest


def tail(text, n=30):
    """The last n lines of a tool's output, Java stack frames left out (Liquibase prints the reason before them)."""
    lines = (text or "").strip().splitlines()
    if any(re.match(r"^\s+at [\w.$<>]+\(", ln) for ln in lines):
        lines = [ln for ln in lines if ln.strip() and not re.match(r"^\s+at [\w.$<>]+\(", ln)
                 and not re.match(r"^\s*\.\.\. \d+ more", ln)]
    return "\n".join(lines[-n:])


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_value(v):
    """A JSON-stable form of a database value, the same whichever driver returned it."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if v != v:
            return "NaN"
        if v in (float("inf"), float("-inf")):
            return str(v)
        return float(f"{v:.12g}")
    if isinstance(v, decimal.Decimal):
        if not v.is_finite():
            return str(v)
        t = v.normalize()
        s = format(t, "f")
        return s
    if isinstance(v, datetime.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(datetime.timezone.utc)
            return v.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        return v.strftime("%Y-%m-%dT%H:%M:%S.%f")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, datetime.time):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return f"interval:{v.total_seconds()}"
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "\\x" + bytes(v).hex()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (ipaddress.IPv4Interface, ipaddress.IPv6Interface)):
        if v.network.prefixlen == v.max_prefixlen:
            return str(v.ip)
        return str(v)
    if isinstance(v, (ipaddress.IPv4Address, ipaddress.IPv6Address, ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return str(v)
    if isinstance(v, dict):
        return {str(k): norm_value(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [norm_value(x) for x in v]
    return str(v)


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def short(obj, n=300):
    s = obj if isinstance(obj, str) else canon(obj)
    return s if len(s) <= n else s[: n - 3] + "..."


def wait_for(pred, timeout=30.0, step=0.1):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return pred()


def copytree(src, dst):
    if Path(dst).exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)


def chown_tree(path, user):
    ids = user_ids(user) if user else None
    if not ids or not is_root():
        return
    uid, gid, _ = ids
    for root, dirs, files in os.walk(path):
        os.lchown(root, uid, gid)
        for n in dirs + files:
            try:
                os.lchown(os.path.join(root, n), uid, gid)
            except OSError:
                pass


IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def qident(name):
    return '"' + name.replace('"', '""') + '"'


def load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
