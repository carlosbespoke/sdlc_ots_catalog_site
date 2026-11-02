"""Validate benchmark and differential records before scoring them."""
import json
import math
import re

MEASURED_INPUTS = 256


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate record field: {key}")
        result[key] = value
    return result


def records(text: str) -> list[dict]:
    if not text or len(text) > 16 * 1024 * 1024:
        raise ValueError("missing or oversized harness records")
    rows = [json.loads(line, object_pairs_hook=_unique_object) for line in text.splitlines()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("harness records must be objects")
    return rows


def measured_rows(
    text: str,
    workloads: tuple[str, ...],
    wall_seconds: float,
    *,
    benchmark_gomaxprocs: int = 2,
) -> dict:
    """Only restored-harness JSONL is accepted. stdout is not an argument."""
    found = {}
    total_ns = 0
    expected = {"type", "name", "n", "checked", "elapsed_ns", "mallocs", "allocated_bytes"}
    for row in records(text):
        if set(row) != expected or row["type"] != "benchmark":
            raise ValueError("unexpected benchmark record schema")
        name = row["name"] if isinstance(row["name"], str) else ""
        suffix = f"-{benchmark_gomaxprocs}"
        if name.endswith(suffix):
            name = name.removesuffix(suffix)
        if name not in workloads or name in found:
            raise ValueError("unexpected or duplicate workload")
        for key in expected - {"type", "name"}:
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError(f"invalid benchmark integer: {key}")
        if row["n"] != MEASURED_INPUTS or row["checked"] != MEASURED_INPUTS or row["elapsed_ns"] <= 0:
            raise ValueError("incomplete measured input coverage or invalid duration")
        n = row["n"]
        found[name] = {"ns_per_op": row["elapsed_ns"] / n,
                       # Keep the exact rate. Integer flooring can hide almost one
                       # allocation per operation when the headroom is small.
                       "allocs_per_op": row["mallocs"] / n,
                       "bytes_per_op": row["allocated_bytes"] // n,
                       "raw_mallocs": row["mallocs"], "n": n, "checked": row["checked"]}
        total_ns += row["elapsed_ns"]
    if set(found) != set(workloads):
        raise ValueError("benchmark cardinality mismatch")
    if not math.isfinite(wall_seconds) or wall_seconds <= 0 or total_ns / 1e9 > wall_seconds * 1.05:
        raise ValueError("reported duration exceeds external wall time")
    return found


def measured_snapshot(text: str) -> list[dict]:
    payload = records(text)
    if len(payload) != 1 or set(payload[0]) != {"type", "rows"} or payload[0]["type"] != "snapshot":
        raise ValueError("missing or duplicated snapshot record")
    rows = payload[0]["rows"]
    if not isinstance(rows, list) or len(rows) < 1000 or not all(isinstance(row, dict) for row in rows):
        raise ValueError("incomplete differential corpus")
    ids = [row.get("id") for row in rows]
    if not all(isinstance(key, str) for key in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid differential case identifiers")
    return rows

BENCH_ROW = re.compile(
    r"^(BenchmarkZstdOpt\w+)-2\s+(\d+)\s+([\d.]+) ns/op\s+"
    r"([\d.]+) B/op\s+([\d.]+) allocs/op$"
)


def benchmark_rows(output: str, workloads: tuple[str, ...], wall_seconds: float,
                   benchtime_seconds: float) -> dict[str, dict[str, float]]:
    found = {}
    reported_seconds = 0.0
    if output.splitlines().count("PASS") != 1 or "--- FAIL:" in output:
        raise ValueError("benchmark invocation did not complete its covering tests")
    for line in output.splitlines():
        match = BENCH_ROW.match(line.strip())
        if not match:
            if line.startswith("Benchmark") and "ns/op" in line:
                raise ValueError("unrecognized benchmark result row")
            continue
        name, count = match[1], int(match[2])
        values = [float(match[i]) for i in (3, 4, 5)]
        if name not in workloads or name in found:
            raise ValueError(f"unexpected or duplicate benchmark row: {name}")
        if count <= 0 or not all(math.isfinite(v) and v >= 0 for v in values) or values[0] == 0:
            raise ValueError(f"invalid benchmark values: {name}")
        found[name] = dict(zip(("ns_per_op", "bytes_per_op", "allocs_per_op"), values))
        reported_seconds += count * values[0] / 1e9
    if set(found) != set(workloads):
        raise ValueError(f"benchmark cardinality mismatch: {sorted(found)}")
    minimum_wall = len(workloads) * benchtime_seconds * 0.5
    if wall_seconds < minimum_wall:
        raise ValueError(f"benchmark ended too quickly: {wall_seconds:.3f}s < {minimum_wall:.3f}s")
    if reported_seconds > wall_seconds * 3 + 1:
        raise ValueError("reported benchmark duration exceeds externally measured wall time")
    return found


def snapshot_rows(output: str) -> list[dict]:
    prefix = "ZSTD_OPT_SNAPSHOT="
    records = [line[len(prefix):] for line in output.splitlines() if line.startswith(prefix)]
    if len(records) != 1 or output.splitlines().count("PASS") != 1:
        raise ValueError("missing, duplicated, or incomplete differential snapshot")
    rows = json.loads(records[0])
    if not isinstance(rows, list) or len(rows) < 1000:
        raise ValueError("differential corpus is incomplete")
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != len(ids) or not all(isinstance(key, str) for key in ids):
        raise ValueError("differential case identifiers are invalid")
    return rows
