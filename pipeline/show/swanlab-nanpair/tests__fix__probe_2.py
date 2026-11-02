import glob
import json
import math
import os
import tempfile
from types import SimpleNamespace

import numpy as np

import swanlab
from swanlab.proto.swanlab.record.v1.record_pb2 import Record
from swanlab.sdk.internal.core_python.store import DataStoreReader
from swanlab.sdk.internal.core_python.transport import sender


def show(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            return "nonfinite"
        return round(value, 9)
    return value


def offline_run(workdir):
    logdir = os.path.join(workdir, "swanlog")
    swanlab.init(
        project="grad-check",
        mode="offline",
        log_dir=logdir,
        settings=swanlab.Settings(probe=swanlab.Settings.Probe(monitor=False)),
    )
    steps = [
        {"grad_norm": 3.5, "loss": np.float64(1.25), "ratio": 0.5},
        {"grad_norm": float("inf"), "loss": np.float32("nan"), "ratio": float("-inf")},
        {"grad_norm": float("nan"), "loss": np.float64(0.75), "ratio": 0.25},
        {"grad_norm": 12, "loss": float("nan"), "ratio": -1e309},
    ]
    for row in steps:
        swanlab.log(row)
    swanlab.finish()
    (path,) = glob.glob(os.path.join(logdir, "run-*", "*.swanlab"))
    return path


def stored_scalars(path):
    reader = DataStoreReader()
    reader.open(path)
    records = []
    for raw in reader:
        record = Record()
        record.ParseFromString(raw)
        if record.HasField("scalar"):
            records.append(record)
    reader.close()
    return records


def uploaded(records):
    captured = []
    original = sender.upload_scalar
    sender.upload_scalar = lambda project_id, experiment_id, metrics: captured.extend(metrics)
    try:
        ctx = SimpleNamespace(username="u", project="p", project_id="pid", experiment_id="eid")
        sender.HttpRecordSender(ctx).upload_scalar(records)
    finally:
        sender.upload_scalar = original
    return sorted([m["key"], m["index"], show(m["data"])] for m in captured)


def main():
    obs = {}
    try:
        records = stored_scalars(offline_run(tempfile.mkdtemp()))
        obs["stored"] = sorted([r.scalar.key, r.scalar.step, show(r.scalar.value.number)] for r in records)
        obs["upload"] = uploaded(records)
    except Exception as error:  # observations only
        obs["error"] = type(error).__name__
    print(json.dumps(obs, sort_keys=True))


main()
