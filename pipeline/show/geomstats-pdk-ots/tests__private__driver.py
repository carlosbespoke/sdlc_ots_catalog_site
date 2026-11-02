"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself). geomstats is not installed in the image (the solver image imports it from /workdir
through PYTHONPATH, which -I ignores): the runner drops any ``/workdir`` entry, imports the third-party
libraries the cases use from site-packages, selects the NumPy backend, and then appends the *staged* candidate
tree, so the candidate is imported from the trusted staged copy and only after the standard library and
site-packages: a candidate file named like a standard-library or third-party
module can never replace one. Each
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
# The runner starts with -I -S: no PYTHON* variable, user site, working directory, site-packages .pth file or
# sitecustomize/usercustomize module is processed at interpreter start, so no candidate file can run before
# the case (ISSUE-419). Set up the venv's site-packages here exactly as site.main() would, minus those two
# customization imports. geomstats is not installed: the solver image puts /workdir on PYTHONPATH, which -I
# ignores. Drop any /workdir entry, import the third-party libraries the cases use from site-packages before
# any candidate source is reachable, then append the staged candidate tree after the standard library and
# site-packages, so a candidate file named like a standard-library or third-party module never replaces one.
import site
site.venv(None)
site.addsitepackages(set())
sys.path[:] = [entry for entry in sys.path if not (entry == "/workdir" or entry.startswith("/workdir/"))]
os.environ["GEOMSTATS_BACKEND"] = "numpy"
os.environ["MPLBACKEND"] = "Agg"
import numpy, scipy, scipy.optimize, scipy.integrate, scipy.interpolate, scipy.linalg, scipy.stats  # noqa: E401,F401
import sklearn, sklearn.base, sklearn.cluster, sklearn.decomposition, sklearn.neighbors, sklearn.utils  # noqa: E401,F401
import joblib, pandas, matplotlib  # noqa: E401,F401
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

PREAMBLE = r'''# Case preamble of geomstats-pdk-ots: the colleague original's replay helpers (tests/private/replay_driver.py of
# pdk-drift-repository-496754855d86 v1) without its file-based main(); `run` is renamed `observe`. Every case
# executes this preamble, then its own lines, in a fresh interpreter with the NumPy backend.
"""Replay public outputs; authoritative comparisons remain in the parent.

Finite numerical results are normalized at 10 decimal places to tolerate
floating point arithmetic ordering (far below the estimator tolerance).
Integer/float spellings of equal numerical quantities are immaterial.
"""
import json
import sys
import random
import numpy as np
import geomstats.backend as gs
from geomstats.geometry.euclidean import Euclidean
from geomstats.learning.frechet_mean import linear_mean, LinearMean, FrechetMean
from geomstats.learning.kmeans import RiemannianKMeans


def numeric(value):
    a = np.asarray(value)
    if a.ndim:
        return [numeric(x) for x in a]
    v = a.item()
    if isinstance(v, (bool, str)):
        return v
    if isinstance(v, int):
        return str(v)
    if not np.isfinite(v):
        return str(v)
    return format(float(v), '.10f').rstrip('0').rstrip('.') if abs(v) >= 0.00000000005 else '0'


def observe(c):
    random.seed(910)
    np.random.seed(910)
    x = gs.array(c['x'], dtype=float)
    if c['op'] == 'weighted_mean':
        weights = c.get('weights')
        kw = {} if weights is None else {'weights': gs.array(weights, dtype=float)}
        if c['api'] == 'function':
            return {'mean': numeric(linear_mean(x, **kw))}
        space = Euclidean(x.shape[-1])
        model = LinearMean(space) if c['api'] == 'class' else FrechetMean(space, **({'method': 'linear'} if c['api'] == 'explicit' else {}))
        fitted = model.fit(x, **kw)
        return {'mean': numeric(model.estimate_), 'returns_self': fitted is model}
    if c['op'] == 'unfitted':
        try:
            RiemannianKMeans(Euclidean(x.shape[-1]), n_clusters=2).predict(x)
        except RuntimeError:
            return {'exception': 'RuntimeError'}
        return {'exception': None}
    init = gs.array(c['init'], dtype=float)
    k = len(init)
    callback_args = []
    def callback(data, count):
        callback_args.append({'data': numeric(data), 'count': numeric(count)})
        return gs.copy(init)
    opts = dict(n_clusters=k, init=callback if c.get('callable') else gs.copy(init), max_iter=c.get('iterations', 50))
    if 'tol' in c:
        opts['tol'] = c['tol']
    model = RiemannianKMeans(Euclidean(x.shape[-1]), **opts)
    fitted = model.fit(x)
    centers = np.asarray(model.cluster_centers_)
    query = gs.array(c.get('query', c['x']), dtype=float)
    predicted = np.asarray(model.predict(query))
    # Canonical order removes arbitrary cluster numbering without discarding
    # multiplicity; labels and predictions are represented by their centers.
    return {'centers': sorted(numeric(centers)),
            'assigned_centers': numeric(centers[np.asarray(model.labels_)]),
            'predicted_centers': numeric(centers[predicted]),
            'self': fitted is model,
            'callable_arguments': callback_args}
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "MPLCONFIGDIR": os.path.join(scratch, "mpl"), "CASE_TREE": tree}
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
    # matplotlib keeps its configuration cache here (one directory shared by every case, named by no case),
    # so nothing is written into a case's own working directory.
    os.mkdir(os.path.join(scratch, "mpl"), 0o700)
    results = []
    for source in sources:
        sweep_peers()
        results.append(run_case(source, tree, scratch))
    sweep_peers()
    with open(result_path, "w") as handle:
        json.dump({"results": results}, handle)


if __name__ == "__main__":
    main()
