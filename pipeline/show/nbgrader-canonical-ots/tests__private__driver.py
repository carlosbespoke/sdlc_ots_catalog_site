"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(the directory holding the package under test) appended *after* the standard library and site-packages: a
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
# Child processes a case starts (the alembic command the gradebook runs when it creates a database, notebook
# kernels) import the package as an installed copy would be imported: through PYTHONPATH, which names a private
# directory holding only a link to the candidate's package directory, so no other file at the root of the candidate
# tree (a module named like a standard-library one, say) can shadow anything in those children. The runner itself
# starts with -I, so this never reaches its own sys.path.
# The directory sits beside the case's working directory, not in it, so the case directory stays empty.
import tempfile as _tempfile
_package_path = _tempfile.mkdtemp(prefix="pkg-", dir=os.path.dirname(case_dir))
os.symlink(os.path.join(tree, "nbgrader"), os.path.join(_package_path, "nbgrader"))
os.environ["PYTHONPATH"] = _package_path
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
# Standard-library and third-party modules that the cases and the package under test import, loaded from the standard
# library and site-packages before the candidate tree is reachable.
import collections, contextlib, copy, dataclasses, datetime, functools, glob, hashlib, inspect, io, itertools  # noqa: E401,F401
import json, logging, math, numbers, operator, pathlib, pprint, re, shutil, sqlite3, subprocess, tempfile  # noqa: E401,F401
import textwrap, time, typing, uuid, zipfile, tarfile, fnmatch  # noqa: E401,F401
import traitlets, traitlets.config, nbformat, nbformat.v4, nbformat.notebooknode  # noqa: E401,F401
import nbconvert, nbconvert.exporters, nbconvert.preprocessors, nbclient  # noqa: E401,F401
import sqlalchemy, sqlalchemy.orm, sqlalchemy.ext.associationproxy, sqlalchemy.ext.declarative  # noqa: E401,F401
import jsonschema, dateutil, dateutil.parser, dateutil.tz, jinja2, yaml, rapidfuzz, requests  # noqa: E401,F401
import tornado, tornado.log, zmq, jupyter_core, jupyter_core.paths  # noqa: E401,F401
import jupyter_client, jupyter_client.manager, jupyter_client.kernelspec  # noqa: E401,F401
import jupyter_server, jupyter_server.base.handlers, notebook  # noqa: E401,F401
import setuptools, setuptools.archive_util  # noqa: E401,F401
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

PREAMBLE = r'''import datetime as dt
import json
import logging
import os
import warnings

warnings.simplefilter("ignore")
logging.disable(logging.CRITICAL)

import nbformat  # noqa: E402
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output, new_raw_cell  # noqa: E402

import nbgrader  # noqa: E402,F401


def cell(kind, source, **flags):
    """A notebook cell of `kind` ("code", "markdown" or "raw"); keyword flags become its nbgrader metadata.

    With any flag given, the metadata is a schema-version-3 dict with grade/solution/locked defaulting to False."""
    made = {"code": new_code_cell, "markdown": new_markdown_cell, "raw": new_raw_cell}[kind](source)
    if flags:
        meta = {"schema_version": 3, "grade": False, "solution": False, "locked": False}
        meta.update(flags)
        made.metadata["nbgrader"] = meta
    return made


def nb(*cells, language=None):
    """A v4 notebook holding `cells`; `language` sets kernelspec.language (and the kernel name)."""
    made = new_notebook()
    made.cells = list(cells)
    if language is not None:
        made.metadata["kernelspec"] = {"name": language, "display_name": language, "language": language}
    return made


def run(preprocessor, notebook, resources=None):
    """Run `preprocessor` over `notebook` and return the processed notebook."""
    processed, _ = preprocessor.preprocess(notebook, resources if resources is not None else {})
    return processed


def sources(notebook):
    return [item.source for item in notebook.cells]


def raw(value):
    """A JSON round-trip copy of `value` (NotebookNode metadata becomes plain dicts and lists)."""
    return json.loads(json.dumps(value, default=str))


def err(call, *args, **kwargs):
    """Run `call` and return its raw result, or "raises <ExceptionClass>" when it raises."""
    try:
        return raw(call(*args, **kwargs))
    except Exception as exception:  # noqa: BLE001
        return "raises " + type(exception).__name__


def save(path, notebook):
    """Write `notebook` to `path` (directories created) and return the absolute path."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        nbformat.write(notebook, handle)
    return path


def load(path):
    with open(path, encoding="utf-8") as handle:
        return nbformat.read(handle, as_version=4)


def listing(root):
    """Sorted relative paths of every file under `root`."""
    found = []
    for directory, _, files in os.walk(root):
        for name in files:
            found.append(os.path.relpath(os.path.join(directory, name), root))
    return sorted(found)


def db_url(name="gradebook.db"):
    return "sqlite:///" + os.path.abspath(name)


def res(name="gradebook.db"):
    """The resources the gradebook-backed preprocessors read: notebook p1 of ps1 submitted by hacker."""
    return {"nbgrader": {"notebook": "p1", "assignment": "ps1", "student": "hacker", "db_url": db_url(name)}}


def gradebook(name="gradebook.db"):
    from nbgrader.api import Gradebook
    return Gradebook(db_url(name))


def when(text):
    """A naive UTC datetime from ISO `text`."""
    return dt.datetime.fromisoformat(text)


def seconds(delta):
    return None if delta is None else delta.total_seconds()


def one_cell_course(gb, points=3.0, cell_type="code", duedate=None, student="hacker"):
    """Assignment ps1 / notebook p1 with one grade cell g1 worth `points`, a student and their submission."""
    gb.add_assignment("ps1", duedate=duedate)
    gb.add_notebook("p1", "ps1")
    gb.add_grade_cell("g1", "p1", "ps1", max_score=points, cell_type=cell_type)
    gb.add_student(student)
    return gb.add_submission("ps1", student)


def course():
    """A course built through the high-level API, with ps1 generated: returns (root, api, generate_result).

    Its source notebook p1 has a Markdown title, a solution region at column 0 defining add5, a locked autograded
    test cell worth 2 points (it also prints NBGRADER_EXECUTION) and a written answer cell worth 1 point."""
    from traitlets.config import Config
    from nbgrader.apps.api import NbGraderAPI
    from nbgrader.coursedir import CourseDirectory
    root = os.path.abspath("course")
    os.makedirs(root)
    source = nb(
        cell("markdown", "# Problem set 1"),
        cell("code", "### BEGIN SOLUTION\ndef add5(x):\n    return x + 5\n### END SOLUTION", solution=True,
             grade_id="add5"),
        cell("code", "assert add5(3) == 8\nimport os\nprint(os.environ.get('NBGRADER_EXECUTION'))", grade=True,
             grade_id="test_add5", points=2.0, locked=True),
        cell("markdown", "Describe add5.", grade=True, solution=True, grade_id="essay", points=1.0),
    )
    source.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    save(os.path.join(root, "source", "ps1", "p1.ipynb"), source)
    config = Config()
    config.CourseDirectory.root = root
    config.CourseDirectory.course_id = "course101"
    api = NbGraderAPI(coursedir=CourseDirectory(config=config), config=config)
    return root, api, api.generate_assignment("ps1")
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
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
