"""Binary performance verdict with per-workload statistical evidence."""
from __future__ import annotations

import math
from itertools import combinations
import statistics

from evidence_contract import MEASURED_INPUTS

OPTIMIZED_WORKLOADS = (
    "BenchmarkZstdOptAppendWithFrameSize",
    "BenchmarkZstdOptRequestBodyUnzstd",
    "BenchmarkZstdOptWriteFreshBuffer",
)
CONTROL_WORKLOAD = "BenchmarkZstdOptSmallBodyControl"
SIDES = ("base", "candidate", "expert")
REQUIRED_SAMPLES = 10
MIN_ALLOCATION_RECOVERY = 0.75
MAX_OPTIMIZED_TIME_RATIO = 0.85
# Per-workload time bars. On shared hosted VMs the reference speeds up decoding into
# a fresh bytes.Buffer by only 13-17% (time ratio 0.83-0.87), so a 0.85 bar there
# passes or fails the reference itself at random. The other workloads keep 0.85.
WORKLOAD_MAX_TIME_RATIO = {"BenchmarkZstdOptWriteFreshBuffer": 0.90}
MAX_CONTROL_TIME_RATIO = 1.20
TIME_SIGNIFICANCE_ALPHA = 0.05
ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS = 1
# A stability cluster may also span this fraction of its lower bound. A
# baseline whose allocations include GC-timed runtime work (goroutine
# descriptors, cleanups, pool refills) wanders by a fraction of a percent
# between launches. Small counts stay exact: the one-malloc floor applies.
ALLOCATION_CLUSTER_RELATIVE_TOLERANCE = 0.01
MIN_ALLOCATION_CLUSTER_SAMPLES = 9
MAX_ALLOCATION_RATE_SPREAD = ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS / MEASURED_INPUTS


def _invalid(reason: str) -> dict:
    return {"score": None, "status": "invalid_evidence", "reasons": [reason]}


def _valid_samples(payload: dict) -> str | None:
    samples = payload.get("samples")
    if not isinstance(samples, dict):
        return "samples must be an object"
    for side in SIDES:
        workloads = samples.get(side)
        if not isinstance(workloads, dict):
            return f"missing {side} workloads"
        for name in (*OPTIMIZED_WORKLOADS, CONTROL_WORKLOAD):
            rows = workloads.get(name)
            if not isinstance(rows, list) or len(rows) != REQUIRED_SAMPLES:
                return f"{side}/{name} must contain exactly {REQUIRED_SAMPLES} samples"
            for row in rows:
                if not isinstance(row, dict):
                    return f"{side}/{name} sample is not an object"
                for metric in ("ns_per_op", "allocs_per_op"):
                    value = row.get(metric)
                    if not isinstance(value, (int, float)) or isinstance(value, bool):
                        return f"{side}/{name}/{metric} is not numeric"
                    if not math.isfinite(value) or value < 0 or (metric == "ns_per_op" and value == 0):
                        return f"{side}/{name}/{metric} is invalid"
                if "raw_mallocs" in row:
                    raw_mallocs = row["raw_mallocs"]
                    if type(raw_mallocs) is not int or raw_mallocs < 0:
                        return f"{side}/{name}/raw_mallocs is invalid"
                    expected_rate = raw_mallocs / MEASURED_INPUTS
                    if not math.isclose(row["allocs_per_op"], expected_rate, rel_tol=0, abs_tol=1e-12):
                        return f"{side}/{name}/allocs_per_op does not match raw_mallocs"
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _mann_whitney_less(candidate: list[float], baseline: list[float]) -> float:
    """Exact one-sided permutation p-value for candidate timings < baseline."""
    combined = candidate + baseline
    ordered = sorted(range(len(combined)), key=combined.__getitem__)
    ranks = [0.0] * len(combined)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and combined[ordered[end]] == combined[ordered[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            ranks[index] = average_rank
        start = end

    candidate_count = len(candidate)
    observed = sum(ranks[:candidate_count])
    at_least_as_fast = sum(
        1
        for chosen in combinations(range(len(combined)), candidate_count)
        if sum(ranks[index] for index in chosen) <= observed
    )
    return at_least_as_fast / math.comb(len(combined), candidate_count)


def _cluster_tolerance(lower: int) -> int:
    return max(
        ALLOCATION_CLUSTER_TOLERANCE_RAW_MALLOCS,
        math.floor(ALLOCATION_CLUSTER_RELATIVE_TOLERANCE * lower),
    )


def _stable_allocation_summary(rows: list[dict], side: str, name: str) -> tuple[dict | None, str | None]:
    """Use a dominant near-exact cluster while retaining outlier diagnostics."""
    raw_presence = ["raw_mallocs" in row for row in rows]
    if any(raw_presence) and not all(raw_presence):
        return None, f"{side}/{name} mixes raw and normalized allocation evidence"
    if not any(raw_presence):
        # Compatibility for the shared synthetic contract suite. Production
        # evidence always carries exact raw counts from evidence_contract.py.
        rates = [row["allocs_per_op"] for row in rows]
        spread = max(rates) - min(rates)
        if spread > MAX_ALLOCATION_RATE_SPREAD + 1e-12:
            return None, f"{side}/{name} legacy allocation spread exceeds one raw malloc per launch"
        median_rate = statistics.median(rates)
        median_raw_mallocs = median_rate * MEASURED_INPUTS
        return {
            "rate": median_rate,
            "median_raw_mallocs": median_raw_mallocs,
            "min_raw_mallocs": min(rates) * MEASURED_INPUTS,
            "max_raw_mallocs": max(rates) * MEASURED_INPUTS,
            "spread_raw_mallocs": spread * MEASURED_INPUTS,
            "inlier_count": len(rates),
            "outlier_count": 0,
        }, None

    values = sorted(row["raw_mallocs"] for row in rows)
    best_cluster: list[int] = []
    for start, lower in enumerate(values):
        cluster = [
            value
            for value in values[start:]
            if value - lower <= _cluster_tolerance(lower)
        ]
        if len(cluster) > len(best_cluster):
            best_cluster = cluster

    if len(best_cluster) < MIN_ALLOCATION_CLUSTER_SAMPLES:
        return None, (
            f"{side}/{name} has only {len(best_cluster)} of {REQUIRED_SAMPLES} "
            "raw malloc samples in an allocation stability cluster"
        )

    median_raw_mallocs = statistics.median(best_cluster)
    return {
        "rate": median_raw_mallocs / MEASURED_INPUTS,
        "median_raw_mallocs": median_raw_mallocs,
        "min_raw_mallocs": min(values),
        "max_raw_mallocs": max(values),
        "spread_raw_mallocs": max(values) - min(values),
        "inlier_count": len(best_cluster),
        "outlier_count": len(values) - len(best_cluster),
    }, None


def score(payload: dict) -> dict:
    """Return score 0/1 for valid evidence; invalid evidence is never scored."""
    if not isinstance(payload, dict):
        return _invalid("payload must be an object")
    error = _valid_samples(payload)
    if error:
        return _invalid(error)
    if not isinstance(payload.get("correctness_passed"), bool):
        return _invalid("correctness_passed must be boolean")
    if not payload["correctness_passed"]:
        return {"score": 0, "status": "correctness_failed", "reasons": ["correctness hard gate failed"]}

    samples = payload["samples"]
    details = {}
    failures = []
    partial_scores = []
    for name in OPTIMIZED_WORKLOADS:
        values = {}
        for side in SIDES:
            rows = samples[side][name]
            allocation, allocation_error = _stable_allocation_summary(rows, side, name)
            if allocation_error:
                return _invalid(allocation_error)
            values[side] = {
                "allocs": allocation["rate"],
                "allocation": allocation,
                "median_ns": statistics.median(row["ns_per_op"] for row in rows),
            }
        headroom = values["base"]["allocs"] - values["expert"]["allocs"]
        if headroom <= 0:
            return _invalid(f"expert has no allocation headroom for {name}")
        recovery = (values["base"]["allocs"] - values["candidate"]["allocs"]) / headroom
        candidate_times = [row["ns_per_op"] for row in samples["candidate"][name]]
        baseline_times = [row["ns_per_op"] for row in samples["base"][name]]
        time_ratio = values["candidate"]["median_ns"] / values["base"]["median_ns"]
        time_p_value = _mann_whitney_less(candidate_times, baseline_times)
        max_time_ratio = WORKLOAD_MAX_TIME_RATIO.get(name, MAX_OPTIMIZED_TIME_RATIO)
        allocation_progress = _clamp01(recovery / MIN_ALLOCATION_RECOVERY)
        time_progress = (
            _clamp01((1.0 - time_ratio) / (1.0 - max_time_ratio))
            if max_time_ratio < 1.0
            else float(time_ratio < 1.0)
        )
        workload_partial_score = min(allocation_progress, time_progress)
        workload_passed = (
            recovery >= MIN_ALLOCATION_RECOVERY
            and time_ratio <= max_time_ratio
            and time_p_value <= TIME_SIGNIFICANCE_ALPHA
        )
        partial_scores.append(workload_partial_score)
        details[name] = {
            "allocation_recovery": recovery,
            "allocation_progress": allocation_progress,
            "median_base_ns": values["base"]["median_ns"],
            "median_candidate_ns": values["candidate"]["median_ns"],
            "time_ratio": time_ratio,
            "max_time_ratio": max_time_ratio,
            "time_progress": time_progress,
            "time_p_value": time_p_value,
            "statistical_test": "exact one-sided Mann-Whitney permutation",
            "allocation_evidence": {
                side: values[side]["allocation"] for side in SIDES
            },
            "workload_partial_score": workload_partial_score,
            "passed": workload_passed,
        }
        if recovery < MIN_ALLOCATION_RECOVERY:
            failures.append(f"{name}: allocation recovery {recovery:.3f} < {MIN_ALLOCATION_RECOVERY:.2f}")
        if time_ratio > max_time_ratio:
            failures.append(f"{name}: time ratio {time_ratio:.3f} > {max_time_ratio:.2f}")
        if time_p_value > TIME_SIGNIFICANCE_ALPHA:
            failures.append(
                f"{name}: one-sided timing p-value {time_p_value:.4f} > "
                f"{TIME_SIGNIFICANCE_ALPHA:.2f}"
            )

    control = {}
    for side in SIDES:
        rows = samples[side][CONTROL_WORKLOAD]
        allocation, allocation_error = _stable_allocation_summary(rows, side, CONTROL_WORKLOAD)
        if allocation_error:
            return _invalid(allocation_error)
        control[side] = {
            "allocs": allocation["rate"],
            "allocation": allocation,
            "median_ns": statistics.median(row["ns_per_op"] for row in rows),
        }
    control_ratio = control["candidate"]["median_ns"] / control["base"]["median_ns"]
    details[CONTROL_WORKLOAD] = {
        "allocation_delta": control["candidate"]["allocs"] - control["base"]["allocs"],
        "allocation_evidence": {
            side: control[side]["allocation"] for side in SIDES
        },
        "time_ratio": control_ratio,
        "role": "non-regression control",
    }
    # Identical code can differ by a few raw mallocs between cohorts when the
    # control path allocates from GC-timed runtime work, so the comparison uses
    # the same counter-noise floor as the stability cluster.
    control_noise = _cluster_tolerance(int(control["base"]["allocation"]["median_raw_mallocs"])) / MEASURED_INPUTS
    if control["candidate"]["allocs"] > control["base"]["allocs"] + control_noise:
        failures.append(f"{CONTROL_WORKLOAD}: allocation regression")
    if control_ratio > MAX_CONTROL_TIME_RATIO:
        failures.append(
            f"{CONTROL_WORKLOAD}: time ratio {control_ratio:.3f} > {MAX_CONTROL_TIME_RATIO:.2f}"
        )

    partial_score = statistics.mean(partial_scores)
    if failures:
        return {
            "score": 0,
            "partial_score": partial_score,
            "status": "performance_failed",
            "reasons": failures,
            "details": details,
        }
    return {
        "score": 1,
        "partial_score": partial_score,
        "status": "passed",
        "reasons": [],
        "details": details,
    }
