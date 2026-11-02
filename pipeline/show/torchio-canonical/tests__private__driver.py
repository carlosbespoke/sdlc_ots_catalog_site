"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported, then runs the cases in chunks of up to CHUNK consecutive cases, each chunk in its own
fresh interpreter (``python -I``, so no PYTHON* variable, user site or working directory reaches it)
whose ``sys.path`` gets the candidate's ``src`` directory appended *after* the standard library and
site-packages: a candidate file named like a standard-library module can never replace one. Before
that, the runner imports the third-party modules torchio and the cases use, so they always come from
site-packages. Each case is a short Python module that assigns ``result``; it is written to the
chunk's own empty directory as ``case_<n>.py`` and imported from there, one after the other. The
driver records the JSON-normalised ``result`` of each case, or the name of the exception class when a
case raises, and writes the observations to ``argv[1]``. It never sees an expected value: the trusted
parent holds those and compares.

    python driver.py RESULT_PATH CANDIDATE_TREE < cases.json
"""
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile

RUNNER = r'''
import json, os, sys
case_dir = os.getcwd()
tree = os.environ.pop("CASE_TREE")
for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy",
             "all_proxy", "no_proxy", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
    os.environ.pop(name, None)
# Third-party modules first, from site-packages, before the candidate tree is reachable.
import importlib, importlib.metadata, warnings  # noqa: E401,F401
import numpy, torch, SimpleITK, nibabel, einops, jaxtyping, loguru, rich, tyro, humanize  # noqa: E401,F401
import platformdirs, fsspec, interpol, zarr, niizarr, typing_extensions  # noqa: E401,F401
torch.set_num_threads(1)
sys.path.append(os.path.join(tree, "src"))
sys.path.insert(0, case_dir)


def norm(value, depth=0):
    if depth > 12:
        return repr(value)[:200]
    if value is None or isinstance(value, (bool, str)):
        return value[:2000] if isinstance(value, str) else value
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu()
        if value.dtype == torch.bool or not value.is_floating_point():
            return {"tensor": list(value.shape), "dtype": str(value.dtype),
                    "values": [int(v) for v in value.flatten()[:500].tolist()]}
        return {"tensor": list(value.shape), "dtype": str(value.dtype),
                "values": [round(float(v), 4) for v in value.flatten()[:500].tolist()]}
    if isinstance(value, numpy.ndarray):
        return {"ndarray": list(value.shape), "dtype": str(value.dtype),
                "values": norm(value.flatten()[:500].tolist(), depth + 1)}
    if isinstance(value, numpy.generic):
        value = value.item()
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if value != value:
            return "nan"
        if value in (float("inf"), float("-inf")):
            return repr(value)
        return round(value, 4)
    if isinstance(value, bytes):
        return {"bytes": value[:2000].decode("latin-1")}
    if isinstance(value, dict):
        return {"dict": sorted(([norm(k, depth + 1), norm(v, depth + 1)] for k, v in value.items()), key=repr)}
    if isinstance(value, (set, frozenset)):
        return {"set": sorted((norm(v, depth + 1) for v in value), key=repr)}
    if isinstance(value, (list, tuple)):
        return [norm(v, depth + 1) for v in value[:500]]
    return {"repr": repr(value)[:2000]}


results = {}
for index in range(int(os.environ.pop("CASE_COUNT"))):
    try:
        module = importlib.import_module(f"case_{index}")
        out = {"value": norm(module.result)}
    except BaseException as exception:  # noqa: BLE001
        out = {"error": type(exception).__name__[:100]}
    results[str(index)] = out
    with open(os.path.join(case_dir, "result.json.tmp"), "w") as handle:
        json.dump(results, handle)
    os.replace(os.path.join(case_dir, "result.json.tmp"), os.path.join(case_dir, "result.json"))
sys.stdout.flush()
'''

PREAMBLE = r'''
import copy
import io
import math
import os
import warnings

import numpy as np
import torch

warnings.simplefilter("ignore")

import torchio as tio
from torchio import Choice


def ramp(*shape, dtype=torch.float32):
    # A deterministic tensor 0, 1, 2, ... of the given shape.
    n = 1
    for size in shape:
        n *= size
    return torch.arange(n, dtype=dtype).reshape(*shape)


def scalar(*shape, **kwargs):
    # A ScalarImage holding ramp(*shape) (shape is (C, I, J, K)).
    return tio.ScalarImage(ramp(*shape), **kwargs)


def label(tensor, **kwargs):
    return tio.LabelMap(torch.as_tensor(tensor), **kwargs)


def error_of(fn):
    # [exception class name, ""] of fn(), or ["ok", repr(return value)].
    try:
        value = fn()
    except Exception as exception:  # noqa: BLE001
        return [type(exception).__name__]
    return ["ok"]


def aff(image):
    # The 4x4 affine of an image, rounded.
    return [[round(float(v), 4) for v in row] for row in image.affine.numpy().tolist()]


def r4(values):
    return [round(float(v), 4) for v in values]
'''


CHUNK = 4


def run_chunk(chunk, tree, scratch):
    # Opaque chunk directory: nothing candidate-visible (HOME/TMPDIR/cwd path, files, environment, argv)
    # names an observation id; the child reports results by position and the parent maps them back.
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    for index, case in enumerate(chunk):
        with open(os.path.join(directory, f"case_{index}.py"), "w") as handle:
            handle.write(PREAMBLE + "\n" + case["code"] + "\n")
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "MPLBACKEND": "Agg",
                   "CASE_TREE": tree, "CASE_COUNT": str(len(chunk))}
    try:
        subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=180 + 240 * len(chunk))
        missing = "no-result"
    except subprocess.TimeoutExpired:
        missing = "timeout"
    try:
        with open(os.path.join(directory, "result.json")) as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        found = {}
    if not isinstance(found, dict):
        found = {}
    return {case["id"]: found.get(str(index), {"error": missing}) for index, case in enumerate(chunk)}


def main():
    cases = json.loads(sys.stdin.read())
    result_path, tree = sys.argv[1], os.path.abspath(sys.argv[2])
    scratch = tempfile.mkdtemp(prefix="torchio-cases-")
    results = {}
    chunks = [cases[start:start + CHUNK] for start in range(0, len(cases), CHUNK)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for found in pool.map(lambda chunk: run_chunk(chunk, tree, scratch), chunks):
            results.update(found)
    with open(result_path, "w") as handle:
        json.dump({"results": results}, handle, sort_keys=True)


if __name__ == "__main__":
    main()
