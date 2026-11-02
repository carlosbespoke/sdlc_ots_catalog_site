import csv
import json
import math
import os
import tempfile

import swanlab
from swanlab.plugin.writer.csv_writer import CSVWriter


def show(text):
    try:
        value = float(text)
    except ValueError:
        return text
    if not math.isfinite(value):
        return "nonfinite"
    return round(value, 9)


def sweep(workdir):
    logdir = os.path.join(workdir, "swanlog")
    os.makedirs(logdir)
    runs = {
        "lr-0.01": [(2.1, 2.3), (1.4, 1.6), (0.9, 1.2), (0.7, 1.05)],
        "lr-0.3": [(2.0, 2.2), (6.5, 7.1), (float("nan"), float("nan")), (float("nan"), float("nan"))],
        "lr-1.0": [(2.4, 2.5), (float("inf"), float("inf")), (float("nan"), float("nan")), (float("inf"), 31.0)],
        "lr-0.1": [(1.9, 2.0), (1.1, 1.3), (0.8, 1.1), (0.6, float("nan"))],
    }
    for name, epochs in runs.items():
        swanlab.init(
            project="sweep",
            experiment_name=name,
            mode="local",
            log_dir=logdir,
            callbacks=[CSVWriter(dir=workdir)],
            settings=swanlab.Settings(probe=swanlab.Settings.Probe(monitor=False)),
        )
        for epoch, (train, val) in enumerate(epochs):
            lr = 0.5 * (1 + math.cos(math.pi * epoch / (len(epochs) - 1)))
            swanlab.log({"train/loss": train, "val/loss": val, "lr": round(lr, 6)}, step=epoch)
        swanlab.finish()
    rows = {}
    with open(os.path.join(workdir, "swanlab_runs.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["experiment_name"]] = {k: show(row[k]) for k in ("train/loss", "val/loss", "lr")}
    return rows


def main():
    obs = {}
    try:
        obs["csv"] = sweep(tempfile.mkdtemp())
    except Exception as error:  # observations only
        obs["error"] = type(error).__name__
    print(json.dumps(obs, sort_keys=True))


main()
