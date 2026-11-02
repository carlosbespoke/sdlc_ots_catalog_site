"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself) whose ``sys.path`` gets the candidate's repository root
(the directory holding ``sklego``) appended *after* the standard library and site-packages: a
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
# The case source arrives on stdin and is consumed before any candidate code runs.
case_source = sys.stdin.read()
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
# Third-party modules first, from site-packages, before the candidate tree is reachable.
import numpy, scipy, scipy.stats, pandas, sklearn, sklearn.base, sklearn.utils, sklearn.pipeline, sklearn.preprocessing, sklearn.linear_model, narwhals, sklearn_compat, formulaic  # noqa: E401,F401
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
    exec(compile(case_source, "<case>", "exec"), case_module.__dict__)
    out = {"value": norm(case_module.result)}
except BaseException as exception:  # noqa: BLE001
    out = {"error": type(exception).__name__[:100]}
sys.stdout.flush()
with open(os.path.join(case_dir, "result.json"), "w") as handle:
    json.dump(out, handle)
os._exit(0)
'''

PREAMBLE = r'''"""Case preamble of scikit-lego-pdk-ots.

`normalize` and `_observe` are the colleague original's replay helpers (tests/private/replay_driver.py of
pdk-drift-repository-8a2db777f0b4 v2) unchanged; `observe(call)` is that driver's per-call loop body: the
normalised result, or {'error': <class name>} for ValueError, TypeError and NotFittedError.
"""
import json
import math
import numbers
import sys

import numpy as np
import pandas as pd
from sklearn.exceptions import NotFittedError
from sklearn.preprocessing import MinMaxScaler
from sklego.preprocessing import ColumnCapper
from sklego.meta import GroupedTransformer


def normalize(value):
    if isinstance(value, np.ndarray):
        return normalize(value.tolist())
    if isinstance(value, (list, tuple)):
        return [normalize(x) for x in value]
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (bool, str)) or value is None:
        return value
    if isinstance(value, numbers.Integral):
        return {'number': [int(value), 1]}
    if isinstance(value, numbers.Real):
        if math.isnan(value):
            return {'nonfinite': 'nan'}
        if math.isinf(value):
            return {'nonfinite': 'inf' if value > 0 else '-inf'}
        return {'number': list(float(value).as_integer_ratio())}
    raise TypeError(type(value).__name__)


def _observe(call):
    """Fit/transform fresh public objects; preserve state within each lifecycle case."""
    params = call.get('params', {})
    if call['op'] in ('cap', 'cap_validation'):
        model = ColumnCapper(**params)
        if call.get('unfitted'):
            return model.transform(np.asarray(call['query'], dtype=float))
        train = np.asarray(call['train'], dtype=float)
        model.fit(train)
        outputs = [model.transform(np.asarray(x, dtype=float)) for x in call.get('queries', [])]
        if 'refit' in call:
            model.fit(np.asarray(call['refit'], dtype=float))
            outputs.append(model.transform(np.asarray(call['queries'][0], dtype=float)))
        return outputs
    groups = call.get('groups', [0])
    base = MinMaxScaler() if call.get('scaler') else ColumnCapper(**params)
    kw = {'groups': groups}
    if 'global' in call:
        kw['use_global_model'] = call['global']
    model = GroupedTransformer(base, **kw)
    def data(rows):
        if call.get('frame'):
            return pd.DataFrame(rows, columns=call['columns'])
        return np.asarray(rows, dtype=float)
    model.fit(data(call['train']))
    outputs = [model.transform(data(x)) for x in call['queries']]
    if 'refit' in call:
        model.fit(data(call['refit']))
        outputs.append(model.transform(data(call['queries'][0])))
    return outputs



def observe(call):
    try:
        return normalize(_observe(call))
    except (ValueError, TypeError, NotFittedError) as exc:
        return {'error': type(exc).__name__}


# --- Coverage helpers (coverage_cases.py) ---------------------------------------------------------
def rnd(value, digits=4):
    """A JSON-ready, rounded view of arrays, frames, series and scalars (-0.0 folded into 0.0)."""
    if isinstance(value, pd.DataFrame):
        return {'columns': [str(c) for c in value.columns], 'values': rnd(value.to_numpy(), digits)}
    if isinstance(value, pd.Series):
        return rnd(value.to_numpy(), digits)
    if hasattr(value, 'toarray') and not isinstance(value, np.ndarray):
        value = value.toarray()
    if isinstance(value, np.ndarray):
        return rnd(value.tolist(), digits)
    if isinstance(value, (list, tuple)):
        return [rnd(v, digits) for v in value]
    if isinstance(value, dict):
        return {str(k): rnd(v, digits) for k, v in value.items()}
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        return round(float(value), digits) + 0.0
    return value


def raises(function, *args, **kwargs):
    """The exception class name raised by function(*args, **kwargs), or None."""
    try:
        function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__
    return None
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
