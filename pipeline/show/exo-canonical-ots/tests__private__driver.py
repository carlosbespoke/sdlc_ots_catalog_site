"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(its ``src`` directory, which holds ``exo``) appended *after* the standard library and site-packages: a
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
import shutil
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
# Standard-library and third-party modules that the cases and exo import, loaded from the standard library and
# site-packages before the candidate tree is reachable.
import abc, argparse, ast, collections, contextlib, copy, dataclasses, difflib, enum, functools, importlib.util  # noqa: E401,F401
import inspect, io, itertools, json, linecache, math, numbers, operator, pathlib, re, shutil, string  # noqa: E401,F401
import tempfile, textwrap, tokenize, typing, weakref, fractions, pickle, configparser, tomllib  # noqa: E401,F401
import attr, attrs, asdl, asdl_adt, asdl_adt.validators, platformdirs  # noqa: E401,F401
import z3, pysmt, pysmt.shortcuts, pysmt.logics, pysmt.solvers.z3  # noqa: E401,F401
import yapf, yapf.yapflib.yapf_api  # noqa: E401,F401
# Bind every namespace package of site-packages (a directory without __init__.py, such as mpl_toolkits)
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
# The result writer is bound here, before any candidate code can run: a candidate that patches json, open or os
# later cannot rewrite the observation this runner writes through these names.
_write_dumps, _write_open, _write_join, _write_exit = json.dumps, open, os.path.join, os._exit
sys.path.append(os.path.join(tree, "src"))
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
        if value != value:
            return "nan"
        if value in (float("inf"), float("-inf")):
            return "inf" if value > 0 else "-inf"
        return value
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
try:
    sys.stdout.flush()
except BaseException:  # noqa: BLE001
    pass
with _write_open(_write_join(case_dir, "result.json"), "w") as handle:
    handle.write(_write_dumps(out))
_write_exit(0)
'''

PREAMBLE = r'''import linecache
import os
import sys
import textwrap
import types
import warnings

warnings.simplefilter("ignore")

import exo  # noqa: E402
from exo import *  # noqa: E402,F401,F403
from exo.API_scheduling import *  # noqa: E402,F401,F403
from exo.API_cursors import *  # noqa: E402,F401,F403
from exo.libs.memories import DRAM_STATIC  # noqa: E402,F401

_EXO_NAMES = {name: value for name, value in globals().items() if not name.startswith("_")}
_SOURCE_COUNT = [0]


def defs(text, **env):
    """Define Exo objects (@proc / @instr / @config definitions) from source `text`; return the new names.

    Exo's frontend reads a definition's source through ``inspect``, so the text runs as a throw-away module whose
    file name is an opaque in-memory name registered in ``linecache`` (with ``from __future__ import
    annotations``), in a namespace holding the exo API plus `env`; both registrations are removed afterwards."""
    _SOURCE_COUNT[0] += 1
    name = "<exo-%d>" % _SOURCE_COUNT[0]
    module_name = "exo_source_%d" % _SOURCE_COUNT[0]
    full = "from __future__ import annotations\n" + textwrap.dedent(text).lstrip("\n")
    module = types.ModuleType(module_name)
    module.__file__ = name
    namespace = module.__dict__
    namespace.update(_EXO_NAMES)
    namespace.update(env)
    linecache.cache[name] = (len(full), None, full.splitlines(True), name)
    sys.modules[module_name] = module
    try:
        exec(compile(full, name, "exec"), namespace)
    finally:
        linecache.cache.pop(name, None)
        sys.modules.pop(module_name, None)
    given = dict(_EXO_NAMES, **env)
    return {key: value for key, value in namespace.items()
            if not key.startswith("__") and key != "annotations" and (key not in given or given[key] is not value)}


def P(text, **env):
    """The single procedure (or instruction) defined by `text`."""
    made = [value for value in defs(text, **env).values() if isinstance(value, exo.Procedure)]
    assert len(made) == 1, len(made)
    return made[0]


def s(value):
    """Printed form of a procedure, cursor or other object."""
    return str(value)


def raised(call, *args, **kwargs):
    """Call `call`; its printed result, or "raises <ExceptionClass>"."""
    try:
        return str(call(*args, **kwargs))
    except Exception as exception:  # noqa: BLE001
        return "raises " + type(exception).__name__


def cdef(proc):
    """The C definitions that compile_procs_to_strings emits for `proc` (the .c text after its #include lines)."""
    c_text, _ = exo.compile_procs_to_strings([proc], "out.h")
    lines = c_text.splitlines()
    while lines and (lines[0].startswith("#include") or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines)


def chead(proc):
    """The .h text that compile_procs_to_strings emits for `proc`."""
    return exo.compile_procs_to_strings([proc], "out.h")[1]


def write(name, text):
    """Write `text` (dedented) to `name` in the case's working directory and return the absolute path."""
    with open(name, "w") as handle:
        handle.write(textwrap.dedent(text).lstrip("\n"))
    return os.path.abspath(name)


def listing(directory="."):
    """Sorted relative paths of every file under `directory`."""
    found = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            found.append(os.path.relpath(os.path.join(root, file_name), directory))
    return sorted(found)
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    # a separate, equally opaque home directory: library caches written at import time (yapf's grammar cache)
    # never appear in the case's working directory
    home = tempfile.mkdtemp(prefix="home-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "CASE_TREE": tree}
    try:
        subprocess.run([sys.executable, "-I", "-S", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       input=(PREAMBLE + "\n" + source + "\n").encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        with open(os.path.join(directory, "result.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"error": "no-result"}
    finally:
        # nothing a case wrote (its own files, generated C) survives into the next case
        shutil.rmtree(directory, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


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
