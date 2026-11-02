"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(its ``src`` directory, which holds ``datatrove``) appended *after* the standard library and site-packages: a
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
# Standard-library and third-party modules that the cases and datatrove import, loaded from the standard library
# and site-packages before the candidate tree is reachable.
import contextlib, csv, dataclasses, datetime, glob, gzip, hashlib, inspect, io, logging, pickle, random, re, shutil, struct, tempfile, threading  # noqa: E401,F401
import numpy, fsspec, fsspec.implementations.local, fsspec.implementations.dirfs, huggingface_hub, loguru, tqdm  # noqa: E401,F401
import multiprocess, dill, humanize, pyarrow, pyarrow.parquet, pyarrow.ipc, orjson, regex, ftfy, tldextract  # noqa: E401,F401
import fasteners, ahocorasick, xxhash, tokenizers, requests, spacy  # noqa: E401,F401
# The result writer is bound here, before any candidate code can run: a candidate that patches json, open or
# os later cannot rewrite the observation this runner writes.
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
try:
    sys.stdout.flush()
except BaseException:  # noqa: BLE001
    pass
with _write_open(_write_join(case_dir, "result.json"), "w") as handle:
    handle.write(_write_dumps(out))
_write_exit(0)
'''

PREAMBLE = r'''import gzip
import io
import json
import os
import sys
import warnings

warnings.simplefilter("ignore")

from datatrove.data import Document  # noqa: E402

WORK = os.getcwd()


_COUNTER = [0]


def D(text, id=None, **metadata):
    """A Document with the given text, id (default: d0, d1, ... in creation order) and metadata."""
    if id is None:
        id = "d%d" % _COUNTER[0]
        _COUNTER[0] += 1
    return Document(text=text, id=id, metadata=metadata)


def view(doc):
    """A Document as plain data: [id, text, metadata]."""
    return [doc.id, doc.text, dict(doc.metadata)]


def run(block, docs=None, rank=0, world_size=1):
    """Run one pipeline block on a list of Documents (or no input) and return the yielded Documents as plain data."""
    data = iter(docs) if docs is not None else None
    return [view(doc) for doc in block.run(data, rank, world_size)]


def ids(block, docs=None, rank=0, world_size=1):
    """The ids of the Documents a block yields."""
    data = iter(docs) if docs is not None else None
    return [doc.id for doc in block.run(data, rank, world_size)]


def raised(function, *args, **kwargs):
    """The exception class name raised by the call, or None."""
    try:
        function(*args, **kwargs)
    except BaseException as problem:  # noqa: BLE001
        return type(problem).__name__
    return None


def path(*parts):
    """A path under the case's working directory."""
    return os.path.join(WORK, *parts)


def put(folder, files):
    """Create text files (relative path -> str, or bytes) under folder; returns the folder path."""
    for relative, content in files.items():
        full = os.path.join(folder, relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if relative.endswith(".gz") and isinstance(content, str):
            content = gzip.compress(content.encode())
        with open(full, "wb" if isinstance(content, bytes) else "w") as handle:
            handle.write(content)
    return folder


def jsonl(*rows):
    """JSON Lines text of the given rows."""
    return "".join(json.dumps(row) + "\n" for row in rows)


def content(full):
    """A file's content as data: gzip is decompressed, parquet/arrow become row lists, JSON files are parsed."""
    with open(full, "rb") as handle:
        raw = handle.read()
    name = os.path.basename(full)
    if raw[:2] == b"\x1f\x8b":
        return {"gzip": content_bytes(gzip.decompress(raw), name[:-3] if name.endswith(".gz") else name)}
    return content_bytes(raw, name)


def content_bytes(raw, name):
    if raw[:4] == b"PAR1":
        import pyarrow.parquet as pq

        return {"parquet": pq.read_table(io.BytesIO(raw)).to_pylist()}
    if raw[:6] == b"ARROW1" or name.endswith((".arrow", ".ipc")):
        import pyarrow as pa

        try:
            return {"arrow": pa.ipc.open_stream(io.BytesIO(raw)).read_all().to_pylist()}
        except Exception:  # noqa: BLE001
            return {"arrow": pa.ipc.open_file(io.BytesIO(raw)).read_all().to_pylist()}
    text = raw.decode("utf-8", "replace")
    if name.endswith(".json"):
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


def tree(folder):
    """Files under folder as {relative path: content(...)}."""
    found = {}
    for top, _dirs, names in os.walk(folder):
        for name in names:
            full = os.path.join(top, name)
            found[os.path.relpath(full, folder)] = content(full)
    return found


def names(folder):
    """Sorted relative paths of the files under folder."""
    return sorted(os.path.relpath(os.path.join(top, name), folder)
                  for top, _dirs, files in os.walk(folder) for name in files)
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
