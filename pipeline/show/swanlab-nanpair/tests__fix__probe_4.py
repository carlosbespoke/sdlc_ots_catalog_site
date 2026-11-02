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
            project="eval-every-5",
            mode="local",
            log_dir=logdir,
            settings=swanlab.Settings(probe=swanlab.Settings.Probe(monitor=False)),
        )
        swanlab.log({"reward": 1.5, "eval/win_rate": 0.4}, step=0)
        swanlab.log({"reward": 0}, step=5)
        swanlab.log({"reward": -0.0, "eval/win_rate": 0.0}, step=10)
        swanlab.log({"reward": -2.0, "eval/win_rate": 0.6}, step=15)
        swanlab.log({"eval/win_rate": 0.0}, step=15)
        swanlab.log({"reward": 0.0, "eval/win_rate": 0.8}, step=20)
        swanlab.finish()
        obs["dashboard"] = dashboard(logdir)
    except Exception as error:  # observations only
        obs["error"] = type(error).__name__
    print(json.dumps(obs, sort_keys=True))


main()
