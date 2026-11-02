"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(the directory holding ``sqlglot``) appended *after* the standard library and site-packages: a
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
# Standard-library modules sqlglot and the cases use, loaded before the candidate tree is reachable
# (sqlglot has no third-party runtime dependencies).
import datetime, decimal, json, logging, re, typing  # noqa: E401,F401
sys.path.append(tree)
warnings.simplefilter("ignore")


def norm(value, depth=0):
    if depth > 14:
        return repr(value)[:500]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:8000]
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

PREAMBLE = r'''import json
import sys

import sqlglot
from sqlglot import exp
from sqlglot.anonymize import anonymize, render
from sqlglot.diff import diff
from sqlglot.expressions.builders import normalize_table_name, table_name
from sqlglot.helper import (csv, dict_depth, ensure_collection, ensure_list, find_new_name,
                            flatten, is_iterable, merge_ranges, name_sequence, seq_get,
                            split_num_words, to_bool, is_date_unit)


# ---- the colleague original's replay helpers (tests/heldout/replay_driver.py without main()) ----
# Unchanged apart from names: `run` is `run_one` here, and the locals `value` are `obj`/`given`
# (so the bypass probe's answer-name list never matches a replay helper local); the computation is
# identical.
def norm(obj):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): norm(v) for k, v in sorted(obj.items(), key=lambda x: str(x[0]))}
    if isinstance(obj, (list, tuple)):
        return [norm(v) for v in obj]
    if isinstance(obj, set):
        return sorted((norm(v) for v in obj), key=str)
    return f"OBJ:{type(obj).__name__}:{str(obj)}"


def _ast_node(shape):
    if "column" in shape:
        return exp.column(shape["column"])
    kind, children = next(iter(shape.items()))
    return {"add": exp.Add, "mul": exp.Mul, "sub": exp.Sub}[kind](
        this=_ast_node(children[0]), expression=_ast_node(children[1]))


def _ast_shape(node):
    if isinstance(node, exp.Column):
        return {"column": node.name}
    kind = {exp.Add: "add", exp.Mul: "mul", exp.Sub: "sub"}[type(node)]
    return {kind: [_ast_shape(node.this), _ast_shape(node.expression)]}


def run_one(call):
    op = call["op"]
    try:
        if op == "ast_transform":
            tree = exp.Select(expressions=[_ast_node(shape) for shape in call["expressions"]])
            seen = []
            def rewrite(node):
                if isinstance(node, exp.Add):
                    return exp.column(call["replacement"])
                if isinstance(node, exp.Column):
                    seen.append(node.name)
                return node
            changed = tree.transform(rewrite, copy=call["copy"])
            return {"expressions": [_ast_shape(node) for node in changed.expressions],
                    "seen": sorted(seen), "original": [_ast_shape(node) for node in tree.expressions],
                    "same_tree": changed is tree}
        if op == "ast_pop":
            tree = exp.Select(expressions=[exp.column(name) for name in call["names"]])
            original = list(tree.expressions)
            returned = [original[index].pop() is original[index] for index in call["remove"]]
            return {"remaining": [node.name for node in tree.expressions],
                    "returns_original_nodes": returned}
        if op == "seq_get": return norm(seq_get(call["seq"], call["index"]))
        if op == "lists":
            given = call["value"]
            listed = ensure_list(given)
            return {"list": norm(listed), "list_type": type(listed).__name__, "collection": norm(ensure_collection(given)), "flat": norm(list(flatten(given if isinstance(given, list) else [given])))}
        if op == "ensure_tuple":
            listed = ensure_list(tuple(call["value"]))
            return {"value": norm(listed), "type": type(listed).__name__}
        if op == "csv": return csv(*call["args"])
        if op == "new_name": return find_new_name(set(call["taken"]), call["base"])
        if op == "name_sequence":
            gen = name_sequence(call["prefix"])
            return [gen() for _ in range(call["n"])]
        if op == "split": return norm(split_num_words(call["value"], call["sep"], call["n"]))
        if op == "split_end": return norm(split_num_words(call["value"], call["sep"], call["n"], fill_from_start=False))
        if op == "iterable": return is_iterable(call["value"])
        if op == "date_unit": return is_date_unit(None if call["value"] is None else exp.to_identifier(call["value"]))
        if op == "depth": return dict_depth(call["value"])
        if op == "bool": return norm(to_bool(call["value"]))
        if op == "ranges": return norm(sorted(merge_ranges([tuple(r) for r in call["ranges"]])))
        if op == "identifier":
            node = exp.to_identifier(call["name"])
            return {"sql": node.sql(), "quoted": node.quoted}
        if op == "identifier_copy":
            node = exp.to_identifier(call["name"], quoted=False)
            copied = exp.to_identifier(node)
            return {"same": copied is node, "quoted": copied.quoted}
        if op == "table_name": return table_name(call["table"], dialect=call["dialect"])
        if op == "normalize_table": return normalize_table_name(call["table"], dialect=call["dialect"])
        if op == "convert":
            node = exp.convert(call["value"])
            return {"type": type(node).__name__, "sql": node.sql()}
        if op == "anon":
            tokens = anonymize(call["sql"])
            return render(call["sql"], tokens)
        if op == "diff":
            edits = diff(sqlglot.parse_one(call["source"]), sqlglot.parse_one(call["target"]))
            return [type(e).__name__ for e in edits]
        if op == "sql":
            tree = sqlglot.parse_one(call["sql"])
            return {"sql": tree.sql(), "pretty": tree.sql(pretty=True), "nodes": sum(1 for _ in tree.walk())}
        return "ERR:BadOp"
    except Exception as exc:
        return f"ERR:{type(exc).__name__}"


# ---- documentation-coverage helpers (coverage_cases.py) ----
import ast as _ast
import contextlib as _contextlib
import io as _io
import re as _re

_ADDRESS = _re.compile(r" at 0x[0-9a-fA-F]+")


def _clip(text, limit=2000):
    return _ADDRESS.sub(" at 0x?", text)[:limit]


def _raised(exc):
    return f"{type(exc).__name__}: {_clip(str(exc), 300)}"


def doc_examples(module_name, sources):
    """Run a docstring's examples in order, as doctest does (a copy of the module's globals, each
    example compiled in interactive mode so an expression's repr is echoed), and return each
    example's printed output, or the exception it raised."""
    import importlib
    import sys as _sys
    globs = dict(vars(importlib.import_module(module_name)))
    outputs = []
    for source in sources:
        buffer = _io.StringIO()
        try:
            with _contextlib.redirect_stdout(buffer):
                exec(compile(source, "<example>", "single"), globs)
            outputs.append(_clip(buffer.getvalue()))
        except BaseException as exc:  # noqa: BLE001
            outputs.append(_clip(buffer.getvalue()) + "!" + _raised(exc))
        finally:
            _sys.displayhook = _sys.__displayhook__
    return outputs


def page_blocks(sources):
    """Replay a page's python blocks in one namespace (the page reads as one session) and return the
    last block's printed output and the repr of its final expression."""
    namespace = {"__name__": "__main__"}
    for source in sources[:-1]:
        try:
            with _contextlib.redirect_stdout(_io.StringIO()):
                exec(compile(source, "<page>", "exec"), namespace)
        except BaseException:  # noqa: BLE001
            pass
    tree = _ast.parse(sources[-1])
    last = None
    if tree.body and isinstance(tree.body[-1], _ast.Expr):
        last = _ast.Expression(tree.body.pop().value)
    buffer = _io.StringIO()
    try:
        with _contextlib.redirect_stdout(buffer):
            exec(compile(tree, "<page>", "exec"), namespace)
            shown = repr(eval(compile(last, "<page>", "eval"), namespace)) if last is not None else None
    except BaseException as exc:  # noqa: BLE001
        return {"printed": _clip(buffer.getvalue()), "raised": _raised(exc)}
    return {"printed": _clip(buffer.getvalue()), "shown": None if shown is None else _clip(shown)}
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
