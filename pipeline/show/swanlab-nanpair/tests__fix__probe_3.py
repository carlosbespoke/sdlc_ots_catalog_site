import glob
import json
import math
import os
import sqlite3
import tempfile

import swanlab


def show(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            return "nonfinite"
        return round(value, 9)
    return value


def dashboard(logdir):
    (run_dir,) = glob.glob(os.path.join(logdir, "run-*"))
    db = sqlite3.connect(os.path.join(logdir, "runs.swanlab"))
    try:
        tags = list(db.execute("SELECT name, folder FROM tag"))
    finally:
        db.close()
    out = {}
    for name, folder in tags:
        points = []
        for path in sorted(glob.glob(os.path.join(run_dir, "logs", folder, "*.log"))):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    item = json.loads(line)
                    points.append([item["index"], show(item["data"])])
        with open(os.path.join(run_dir, "logs", folder, "_summary.json"), encoding="utf-8") as f:
            summary = {k: show(v) for k, v in json.load(f).items()}
        out[name] = {"points": sorted(points), "summary": summary}
    return out


def main():
    obs = {}
    try:
        logdir = os.path.join(tempfile.mkdtemp(), "swanlog")
        swanlab.init(
            project="warmup",
            mode="local",
            log_dir=logdir,
            settings=swanlab.Settings(probe=swanlab.Settings.Probe(monitor=False)),
        )
        rows = [
            {"acc": 0.0, "lr": 0.0, "errors": 4, "is_best": True, "loss": 2.0},
            {"acc": 0.25, "lr": 0.001, "errors": 1, "is_best": False, "loss": 1.5},
            {"acc": 0.5, "lr": 0.002, "errors": 0, "is_best": True, "loss": float("nan")},
            {"acc": 0.75, "lr": 0.001, "errors": 0, "is_best": False, "loss": 0.5},
        ]
        for row in rows:
            swanlab.log(row)
        swanlab.finish()
        obs["dashboard"] = dashboard(logdir)
    except Exception as error:  # observations only
        obs["error"] = type(error).__name__
    print(json.dumps(obs, sort_keys=True))


main()
