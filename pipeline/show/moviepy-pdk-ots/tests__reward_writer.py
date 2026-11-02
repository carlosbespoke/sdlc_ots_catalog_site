"""Trusted verifier writer: binary Harbor reward, partial reward, concise metrics, detailed eval.

Copy to tests/reward_writer.py. Call only from the trusted grader with actual private
observation results, never candidate-supplied scores. Infrastructure errors must not call
this writer: the grader leaves reward.txt at -1 instead.

Files written into the verifier directory (/logs/verifier), in this order:

  eval.json            detailed: every group and every observation, with its status and a short
                       failure reason, plus the grader's run details. Expected values never
                       appear here -- the verifier directory is captured as rollout feedback.
  metrics.json         concise headline numbers: reward, partial reward, F2P/P2P pass summary
                       and the per-group pass counts that partition-check and
                       preservation-per-run read.
  partial_reward.txt   the partial reward in [0, 1] as exact decimal text.
  rewards.txt          the binary reward, 0 or 1.
  reward.json          {"reward": <binary>}; Harbor reads this first.
  reward.txt           the binary reward, committed last so a crash above leaves -1.

Harbor 0.22 reads only reward.json / reward.txt. Horizon keeps every other file in the
verifier directory as rollout feedback (grade_result.metadata.feedback), which is where the
project's tooling reads partial_reward.txt for rollout acceptance.
"""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

SCHEMA_METRICS = "spec-drift-metrics/1"
SCHEMA_EVAL = "spec-drift-eval/1"
DEFAULT_FORMULA = "mean(F2P group pass rates) x mean(P2P group pass rates)"
OBSERVATION_STATUSES = {"passed", "failed", "missing", "error"}
MAX_DETAIL = 400
# This task's copy: requirement text in eval.json is capped (feedback size, ISSUE-396).
MAX_REQUIREMENT = 120


def _decimal_text(value: Fraction) -> str:
    """Never round before flooring or print a near-one partial as 1."""
    with localcontext() as context:
        context.prec = max(28, len(str(value.denominator)) + 10)
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def _short(requirement, limit=MAX_REQUIREMENT):
    """eval.json repeats each group's requirement for feedback only; the sealed manifest keeps the full text."""
    if not isinstance(requirement, str) or len(requirement) <= limit:
        return requirement
    return requirement[:limit - 3] + "..."


def _validated_groups(groups):
    manifest = json.loads(Path(__file__).with_name("private_manifest.json").read_text())
    declared = manifest["scoring"]["groups"]
    expected = {group["id"]: group for group in declared}
    if len(expected) != len(declared) or not expected:
        raise ValueError("private manifest scoring groups must be unique and nonempty")
    partitions, ids, rows = {"f2p": [], "p2p": []}, set(), []
    for group in groups:
        name, kind = group.get("id"), group.get("kind")
        passed, total = group.get("passed"), group.get("total")
        if not isinstance(name, str) or not name or name in ids or kind not in partitions:
            raise ValueError("invalid or duplicate scoring group")
        if type(passed) is not int or type(total) is not int or not 0 <= passed <= total or total == 0:
            raise ValueError("invalid counts: missing/skipped tests cannot count as passes")
        sealed = expected.get(name)
        if sealed is None or sealed["kind"] != kind or len(sealed["tests"]) != total:
            raise ValueError("group kind/count differs from the sealed private manifest")
        ids.add(name)
        partitions[kind].append(Fraction(passed, total))
        rows.append({"id": name, "kind": kind, "passed": passed, "total": total})
    if ids != set(expected):
        raise ValueError("missing required scoring groups")
    if not all(partitions.values()):
        raise ValueError("both F2P and P2P evidence are required")
    return rows, partitions, expected


def _validated_observations(observations, expected_groups):
    membership = {test: group_id for group_id, group in expected_groups.items() for test in group["tests"]}
    rows, seen = [], set()
    for item in observations:
        name, status = item.get("id"), item.get("status")
        if not isinstance(name, str) or name in seen or name not in membership:
            raise ValueError("observation results must name each sealed observation once")
        if status not in OBSERVATION_STATUSES:
            raise ValueError(f"observation status must be one of {sorted(OBSERVATION_STATUSES)}")
        seen.add(name)
        row = {"id": name, "group": membership[name],
               "kind": expected_groups[membership[name]]["kind"], "status": status}
        if item.get("detail"):
            row["detail"] = str(item["detail"])[:MAX_DETAIL]
        rows.append(row)
    if seen != set(membership):
        raise ValueError("observation results must cover every sealed observation")
    return rows


def _summary(rows, kind):
    groups = [row for row in rows if row["kind"] == kind]
    passed = sum(row["passed"] for row in groups)
    total = sum(row["total"] for row in groups)
    return {"groups_passed": sum(row["passed"] == row["total"] for row in groups),
            "groups_total": len(groups), "observations_passed": passed,
            "observations_total": total}


def write_rewards(out: Path, partial: Fraction, groups: list[dict], *,
                  observations: list[dict] | None = None, formula: str = DEFAULT_FORMULA,
                  run: dict | None = None) -> dict:
    """Write every verifier output. Each group is one semantic requirement; all must pass.

    ``observations`` lists ``{"id", "status": passed|failed|missing|error, "detail"?}`` for
    every sealed observation. It is required for a complete eval.json; group counts must agree
    with it. ``run`` carries grader diagnostics (exit codes, stderr tail, file counts).
    """
    rows, partitions, expected = _validated_groups(groups)
    if not isinstance(partial, Fraction) or not 0 <= partial <= 1:
        raise ValueError("partial score must be an exact Fraction in [0,1]")
    complete = all(value == 1 for values in partitions.values() for value in values)
    if (partial == 1) != complete:
        raise ValueError("partial score 1 must mean every required group passed")
    observed = None
    if observations is not None:
        observed = _validated_observations(observations, expected)
        for row in rows:
            passed = sum(item["status"] == "passed" for item in observed if item["group"] == row["id"])
            if passed != row["passed"]:
                raise ValueError(f"group {row['id']} count disagrees with its observation results")
    binary = partial.numerator // partial.denominator
    partial_text = _decimal_text(partial)

    metrics = {"schema": SCHEMA_METRICS, "reward": binary, "partial_reward": float(partial),
               "f2p": _summary(rows, "f2p"), "p2p": _summary(rows, "p2p"),
               "groups": rows}
    failed = {row["id"]: [] for row in rows}
    for item in observed or []:
        if item["status"] != "passed":
            failed[item["group"]].append(item["id"])
    evaluation = {"schema": SCHEMA_EVAL, "reward": binary, "partial_reward": partial_text,
                  "partial_exact": {"numerator": partial.numerator, "denominator": partial.denominator},
                  "scoring": {"partial": formula,
                              "binary": "1 only when every F2P and P2P group passes"},
                  "groups": [{**row, "requirement": _short(expected[row["id"]].get("requirement")),
                              **({"failed_observations": failed[row["id"]]} if observed is not None else {})}
                             for row in rows],
                  "observations": observed, "run": run or {}}

    out.mkdir(parents=True, exist_ok=True)

    def write(name: str, text: str):
        descriptor, temporary = tempfile.mkstemp(prefix=".reward-", dir=out)
        try:
            with os.fdopen(descriptor, "w") as stream:
                stream.write(text + "\n")
            os.replace(temporary, out / name)
            os.chmod(out / name, 0o644)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    # Compact JSON (this task's copy of the shared writer): with about 225 observations in 100 groups the
    # indented form pushes the worst-case feedback past Horizon's 64 KiB grade_result limit (ISSUE-396).
    write("eval.json", json.dumps(evaluation, sort_keys=True, separators=(",", ":")))
    write("metrics.json", json.dumps(metrics, sort_keys=True, separators=(",", ":")))
    write("partial_reward.txt", partial_text)
    write("rewards.txt", str(binary))
    write("reward.json", json.dumps({"reward": binary}))
    # Commit binary success last, after every diagnostic write succeeds.
    write("reward.txt", str(binary))
    return metrics
