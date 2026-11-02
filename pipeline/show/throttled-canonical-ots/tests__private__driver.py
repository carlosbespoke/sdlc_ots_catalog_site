"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(the directory holding ``throttled``) appended *after* the standard library and site-packages: a
candidate file named like a standard-library or third-party module can never replace one. Each
case is a short Python module that assigns ``result``; its source is passed to the runner on
**stdin**, read before any candidate code is imported, and executed from memory as
``case_module``. The runner also points its standard input at /dev/null and marks itself
non-dumpable before the case starts. The case runs in its own empty working directory (an opaque
temporary name that reveals nothing about the case), and no file, path, argument or environment
variable the candidate can read names or contains the case. Cases run one at a time, and before each
case starts the driver kills every other process of its own uid (anything an earlier case left
running), so no candidate process is alive while a runner holds an unread case on its stdin. The driver records the
JSON-normalised ``result`` of each case, or the name of the exception class when a case raises,
and writes the list of observations to ``argv[1]``. It never sees an expected value: the trusted
parent holds those and compares.

    python driver.py RESULT_PATH CANDIDATE_TREE < case-sources.json
"""
import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile


def seal_self():
    """Detach stdin and make this process non-dumpable (no /proc/<pid>/{fd,mem,environ} for peers)."""
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    try:
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE, 0
    except (OSError, AttributeError):
        pass


def live_peers(me, uid):
    """Other live (non-zombie) processes of this uid."""
    peers = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            with open("/proc/%s/status" % pid) as handle:
                fields = dict(line.split(":", 1) for line in handle if ":" in line)
        except (OSError, ValueError):
            continue
        if int(fields.get("Uid", "-1").split()[0]) == uid and fields.get("State", "").split()[:1] not in (["Z"], ["X"]):
            peers.append(int(pid))
    return peers


def sweep_peers():
    """Kill every other process of this uid before the next case starts (none is legitimate)."""
    me, uid = os.getpid(), os.getuid()
    if uid == 0:
        return  # authoring harnesses run this driver as root; the grader always runs it as nobody
    for _ in range(200):
        try:
            os.kill(-1, signal.SIGKILL)  # every process this uid may signal, except this one
        except ProcessLookupError:
            pass
        if not live_peers(me, uid):
            return
    raise RuntimeError("a previous case left processes that could not be stopped")


RUNNER = r'''
import ctypes, json, os, sys, types, warnings
case_dir = os.getcwd()
tree = os.environ.pop("CASE_TREE")
# The case source arrives on stdin and is consumed and compiled before any candidate code runs. No global
# keeps the source text or the compiled case: the code object is popped from this list when it is executed.
_pending = [compile(sys.stdin.read(), "<case>", "exec")]
null = os.open(os.devnull, os.O_RDONLY)
os.dup2(null, 0)
os.close(null)
sys.stdin = open(os.devnull)
try:
    ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)
except (OSError, AttributeError):
    pass
# The runner starts with -I -S (ISSUE-419): no site initialisation ran, so no sitecustomize/usercustomize
# module and no .pth file could execute before this point. Set up the venv's site-packages here as
# site.main() would, minus those two customization imports, and keep the candidate tree off sys.path.
import site
site.venv(None)
site.addsitepackages(set())
sys.path[:] = [entry for entry in sys.path
               if not (entry == "/workdir" or entry.startswith("/workdir/") or entry == tree or entry.startswith(tree + os.sep))]
# Standard-library and third-party modules that the cases and throttled import, loaded from the standard
# library and site-packages before the candidate tree is reachable.
import asyncio, collections, concurrent.futures, contextlib, dataclasses, datetime, functools, inspect, io  # noqa: E401,F401
import json, logging, math, re, threading, time, typing, urllib.parse  # noqa: E401,F401
import anyio, fakeredis, fakeredis.aioredis, fastapi, fastapi.testclient, httpx, lupa, pydantic, redis  # noqa: E401,F401
import redis.asyncio, starlette, starlette.middleware.base, starlette.testclient  # noqa: E401,F401
import opentelemetry.metrics, opentelemetry.sdk.metrics, opentelemetry.sdk.metrics.export  # noqa: E401,F401
# Bind every namespace package of site-packages (a directory without __init__.py, such as opentelemetry)
# before the tree is appended: a regular package of the same name in the candidate tree would otherwise win
# the lookup over the namespace portions that precede it. Importing a namespace package runs no code.
import importlib
for _site_dir in [entry for entry in sys.path if entry.endswith("site-packages")]:
    for _name in sorted(os.listdir(_site_dir)):
        _path = os.path.join(_site_dir, _name)
        if (_name.isidentifier() and not _name.startswith("_") and os.path.isdir(_path)
                and not os.path.exists(os.path.join(_path, "__init__.py"))):
            try:
                importlib.import_module(_name)
            except Exception:  # noqa: BLE001
                pass
sys.path.append(tree)
warnings.simplefilter("ignore")


def norm(value, depth=0):
    if depth > 14:
        return repr(value)[:500]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        return {"bytes": value.decode("latin-1")[:2000]}
    if isinstance(value, dict):
        return {str(k): norm(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return {"set": sorted((norm(v, depth + 1) for v in value), key=repr)}
    if isinstance(value, (list, tuple)):
        return [norm(v, depth + 1) for v in value]
    return {"repr": repr(value)[:500]}


try:
    case_module = types.ModuleType("case_module")
    sys.modules["case_module"] = case_module
    exec(_pending.pop(), case_module.__dict__)
    out = {"value": norm(case_module.result)}
except BaseException as exception:  # noqa: BLE001
    out = {"error": type(exception).__name__[:100]}
sys.stdout.flush()
with open(os.path.join(case_dir, "result.json"), "w") as handle:
    json.dump(out, handle)
os._exit(0)
'''

PREAMBLE = r'''import asyncio
import contextlib
import io
import json
import logging
import time
import warnings

warnings.simplefilter("ignore")


class VirtualClock:
    """A deterministic clock: time.time / time.monotonic read it, time.sleep and asyncio.sleep advance it.

    Wall-clock time starts at an instant that is a whole number of weeks since the epoch, so every fixed
    window (second, minute, hour, day, week) starts exactly at the beginning of a case."""

    WALL0 = 1799884800.0
    MONO0 = 100000.0

    def __init__(self):
        self.offset = 0.0

    def advance(self, seconds):
        self.offset = round(self.offset + float(seconds), 9)

    def wall(self):
        return self.WALL0 + self.offset

    def mono(self):
        return self.MONO0 + self.offset

    def elapsed(self):
        return round(self.offset, 6)


clock = VirtualClock()
_real_async_sleep = asyncio.sleep


def _fake_sleep(seconds):
    clock.advance(max(0.0, float(seconds)))


async def _fake_async_sleep(seconds, *args, **kwargs):
    clock.advance(max(0.0, float(seconds)))
    await _real_async_sleep(0)
    return args[0] if args else kwargs.get("result")


time.time = clock.wall
time.time_ns = lambda: int(round(clock.wall() * 1e9))
time.monotonic = clock.mono
time.monotonic_ns = lambda: int(round(clock.mono() * 1e9))
time.sleep = _fake_sleep
asyncio.sleep = _fake_async_sleep

import throttled  # noqa: E402
import throttled.asyncio  # noqa: E402
from throttled import exceptions  # noqa: E402


def state(st):
    """A RateLimitState as [limit, remaining, reset_after, retry_after] (floats rounded to 6 places)."""
    return [st.limit, st.remaining, round(float(st.reset_after), 6), round(float(st.retry_after), 6)]


def res(rl):
    """A RateLimitResult as [limited, state]."""
    return [bool(rl.limited), state(rl.state)]


def brief(rl):
    """A RateLimitResult as [limited, limit, remaining, reset_after] (no retry_after)."""
    return [bool(rl.limited), rl.state.limit, rl.state.remaining, round(float(rl.state.reset_after), 6)]


def run(awaitable):
    """Run a coroutine to completion in a fresh event loop."""
    return asyncio.run(awaitable)


def raised(function, *args, **kwargs):
    """The exception class name raised by the call, or None."""
    try:
        function(*args, **kwargs)
    except BaseException as problem:  # noqa: BLE001
        return type(problem).__name__
    return None


async def araised(awaitable):
    """The exception class name raised by awaiting, or None."""
    try:
        await awaitable
    except BaseException as problem:  # noqa: BLE001
        return type(problem).__name__
    return None


def redis_store():
    """A sync RedisStore backed by an in-process fakeredis server (fresh per call)."""
    import fakeredis
    server = fakeredis.FakeServer()

    class _Conn(fakeredis.FakeConnection):
        def __init__(self, *args, **kwargs):
            kwargs["server"] = server
            super().__init__(*args, **kwargs)

    return throttled.RedisStore(options={
        "REDIS_CLIENT_CLASS": "fakeredis.FakeRedis",
        "CONNECTION_POOL_KWARGS": {"connection_class": _Conn},
        "REUSE_CONNECTION": False,
    })


def async_redis_store():
    """An async RedisStore backed by an in-process fakeredis server (fresh per call)."""
    import fakeredis
    import fakeredis.aioredis
    server = fakeredis.FakeServer()

    class _Conn(fakeredis.aioredis.FakeConnection):
        def __init__(self, *args, **kwargs):
            kwargs["server"] = server
            super().__init__(*args, **kwargs)

    return throttled.asyncio.RedisStore(options={
        "REDIS_CLIENT_CLASS": "fakeredis.aioredis.FakeRedis",
        "CONNECTION_POOL_KWARGS": {"connection_class": _Conn},
        "REUSE_CONNECTION": False,
    })


def http(client, method, path, **kwargs):
    """[status, json body or text, rate-limit headers (lower-cased names)] of one TestClient request."""
    response = client.request(method, path, **kwargs)
    names = ("ratelimit-limit", "ratelimit-remaining", "ratelimit-reset", "retry-after")
    headers = {name: response.headers[name] for name in names if name in response.headers}
    try:
        body = response.json()
    except ValueError:
        body = response.text[:200]
    return [response.status_code, body, headers]


def fastapi_app(limiter=None, middleware=True, handler=True, **app_options):
    """A FastAPI app wired as the contrib documentation shows (middleware + 429 handler)."""
    from fastapi import FastAPI
    from throttled.asyncio.contrib.fastapi import (
        RateLimitExceededError,
        RateLimitMiddleware,
        rate_limit_exceeded_handler,
    )
    app = FastAPI(**app_options)
    if middleware:
        app.add_middleware(RateLimitMiddleware)
    if handler:
        app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
    return app


def client_for(app, **kwargs):
    from fastapi.testclient import TestClient
    return TestClient(app, **kwargs)


class Events:
    """An ordered record of hook events."""

    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)


def log_lines(logger_name, function):
    """Run function with a handler on `logger_name`; [outcome, [[level, logger, exception type or None], ...]]."""
    lines = []

    class _Handler(logging.Handler):
        def emit(self, record):
            lines.append([record.levelname, record.name,
                          record.exc_info[0].__name__ if record.exc_info else None])

    handler = _Handler(logging.DEBUG)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        got = function()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
    return [got, lines]


def quiet(function, *args, **kwargs):
    """Call function with stdout/stderr captured: [outcome, stdout]."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            got = function(*args, **kwargs)
        except BaseException as problem:  # noqa: BLE001
            got = {"raised": type(problem).__name__}
    return [got, out.getvalue()]


def as_json(data):
    return json.loads(json.dumps(data, default=str))
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "CASE_TREE": tree}
    try:
        subprocess.run([sys.executable, "-I", "-S", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       input=(PREAMBLE + "\n" + source + "\n").encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=180)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        with open(os.path.join(directory, "result.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"error": "no-result"}


def main():
    sources = json.loads(sys.stdin.read())
    seal_self()
    result_path, tree = sys.argv[1], os.path.abspath(sys.argv[2])
    scratch = tempfile.mkdtemp(prefix="obs-")
    results = []
    for source in sources:
        sweep_peers()
        results.append(run_case(source, tree, scratch))
    sweep_peers()
    with open(result_path, "w") as handle:
        json.dump({"results": results}, handle)


if __name__ == "__main__":
    main()
