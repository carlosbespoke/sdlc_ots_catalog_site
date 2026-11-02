"""Trusted verifier writer for RCA tasks: binary Harbor reward, partial reward, component breakdown.

Copy to tests/reward_writer.py. Call only from the trusted grader (tests/grade.py) with the
grader's own observations, never with candidate-supplied scores. Infrastructure errors must not
call this writer: test.sh pre-writes reward.txt = -1 and a crash leaves it there.

Components (docs/task-contract.md):

  R    reproduce  0/1  the reproducer named in a valid rca.json (else meta.json
                       `default_reproducer`; neither -> R = 0) fails on the clean buggy tree AND
                       passes on buggy + gold.patch AND passes on buggy + each meta.json
                       `alt_fixes` patch (rows from rca_grading.reproducer_checks:
                       repro:fails_on_buggy, repro:passes_with_gold, repro:passes_with_alt_fix_N)
  L    locate     0/1  every meta.json gold cause (`root_causes`, each with its own accept-list;
                       legacy `root_cause` = one cause) is matched by an rca.json `root_causes`
                       entry, and the answer has at most len(gold causes) entries (rows from
                       rca_grading.answer_checks: locate:cause_N, locate:entries; a missing or
                       invalid rca.json -> the single row L, L = 0)
  F    fix      [0,1]  on the clean buggy tree + only the agent's non-test changes: the fraction
                       of the hidden fix tests (meta.json `fix_tests`: gold reproducer + 1-3
                       variants) that pass; 0 when the existing suite (P2P) regresses
  P2P  gate       0/1  the existing-suite selection (meta.json `p2p`) still passes; not scored on
                       its own, it only gates F

  binary reward   1 iff R == 1 and L == 1 and F == 1
  partial reward  (R + L + F) / 3, an exact fraction, so partial == 1 <=> binary == 1

Check rows: {"id", "component": R|L|F|P2P, "status": passed|failed|missing|error, "detail"?,
"crashed"?}. `crashed` (a signal name such as "SIGSEGV", set by rca_grading.reproducer_checks when
the reproducer process was killed by a signal) never changes the score -- the row's status is
"failed" -- but the row reads `crashed: <SIGNAME>` in reproducer_checks (metrics.json, eval.json)
and in rewards.txt, so a crash is not mistaken for an ordinary failure.
R, L and P2P pass when every row of theirs passed (so L = 1 iff every cause row and the entries
row passed). Each F row is one hidden fix test. Every
component needs at least one row: a missing check is never a pass. Nothing here is judged by a
model.

Files written into the verifier directory (/logs/verifier), in this order:

  eval.json            detailed: every check with status and a short reason, component values,
                       each reproducer check (buggy, gold, each alt fix), each locate check (per
                       gold cause, entry count), each fix test's result,
                       the P2P result, formula, grader run details. Never put gold or alt-fix
                       content here -- the verifier directory is returned to Horizon as rollout
                       feedback. Give fix tests neutral ids (fix:gold, fix:variant1, ...).
  metrics.json         concise: reward, partial_reward, R/L/F, P2P, per-reproducer-check,
                       per-locate-check (per-cause match) and per-fix-test status.
  partial_reward.txt   the partial reward in [0, 1] as decimal text.
  rewards.txt          breakdown, `key=value` per line; first line `reward=<binary>`.
  reward.json          EXACTLY {"reward": <binary>}. Horizon averages every numeric key in
                       reward.json into the score, so nothing else may ever go in it.
  reward.txt           the binary reward, committed last so a crash above leaves -1.

Harbor reads only reward.json / reward.txt. Horizon keeps the other files as rollout feedback
(grade_result.metadata.feedback), which is where scripts/count-steps.py reads partial_reward.txt.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

SCHEMA_METRICS = "rca-metrics/4"
SCHEMA_EVAL = "rca-eval/4"
COMPONENTS = {"R": "reproduce", "L": "locate", "F": "fix", "P2P": "p2p"}
SCORED = ("R", "L", "F")
FORMULA = "(R + L + F) / 3"
BINARY = "R == 1 and L == 1 and F == 1"
STATUSES = {"passed", "failed", "missing", "error"}
CHECK_ID = re.compile(r"^[^\s=]{1,120}$")
SIGNAL_NAME = re.compile(r"^(?:SIG[A-Z0-9+-]{1,12}|signal \d{1,3}|unknown signal)$")
MAX_DETAIL = 400


def _decimal_text(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 28
        text = str(Decimal(value.numerator) / Decimal(value.denominator))
    if (Fraction(text) == 1) != (value == 1):  # rounding must never turn a near-1 into 1
        raise ValueError("partial reward text does not preserve partial == 1")
    return text


def _validated(checks):
    rows, seen = [], set()
    for item in checks:
        name, component, status = item.get("id"), item.get("component"), item.get("status")
        if not isinstance(name, str) or not CHECK_ID.match(name) or name in seen:
            raise ValueError("each check needs a unique id without whitespace or '='")
        if component not in COMPONENTS:
            raise ValueError(f"check {name}: component must be one of {list(COMPONENTS)}")
        if status not in STATUSES:
            raise ValueError(f"check {name}: status must be one of {sorted(STATUSES)}")
        seen.add(name)
        row = {"id": name, "component": component, "status": status}
        if item.get("detail"):
            row["detail"] = str(item["detail"])[:MAX_DETAIL]
        if item.get("crashed") is not None:
            if status != "failed" or not isinstance(item["crashed"], str) or not SIGNAL_NAME.match(item["crashed"]):
                raise ValueError(f"check {name}: crashed must be a signal name on a failed row")
            row["crashed"] = item["crashed"]
        rows.append(row)
    for component in COMPONENTS:
        if not any(row["component"] == component for row in rows):
            raise ValueError(f"component {component} has no checks; a missing check is not a pass")
    return rows


def score(checks):
    """(values {R, L, F, P2P}, partial Fraction, binary int) for validated check rows."""
    def all_passed(component):
        return int(all(r["status"] == "passed" for r in checks if r["component"] == component))

    fix_rows = [r for r in checks if r["component"] == "F"]
    values = {"R": all_passed("R"), "L": all_passed("L"), "P2P": all_passed("P2P")}
    passed = sum(r["status"] == "passed" for r in fix_rows)
    values["F"] = Fraction(passed, len(fix_rows)) if values["P2P"] else Fraction(0)
    partial = (values["R"] + values["L"] + values["F"]) / 3
    binary = int(values["R"] == 1 and values["L"] == 1 and values["F"] == 1)
    if (partial == 1) != (binary == 1):  # holds by construction; guard against edits
        raise ValueError("partial reward 1 must mean binary reward 1")
    return values, partial, binary


def _shown(row):
    """A row's status as reported: `crashed: SIGSEGV` for a crashed row, else its status."""
    return f"crashed: {row['crashed']}" if row.get("crashed") else row["status"]


def write_rewards(out: Path, checks: list[dict], *, run: dict | None = None) -> dict:
    """Write all six verifier outputs. ``checks``: ``{"id", "component": R|L|F|P2P,
    "status": passed|failed|missing|error, "detail"?}``. ``run`` carries grader diagnostics."""
    rows = _validated(checks)
    values, partial, binary = score(rows)
    partial_text, fix_text = _decimal_text(partial), _decimal_text(values["F"])
    reproducer = {r["id"]: _shown(r) for r in rows if r["component"] == "R"}
    locate = {r["id"]: r["status"] for r in rows if r["component"] == "L"}
    fix_tests = {r["id"]: r["status"] for r in rows if r["component"] == "F"}
    p2p = {r["id"]: r["status"] for r in rows if r["component"] == "P2P"}
    counts = {c: {"passed": sum(r["status"] == "passed" for r in rows if r["component"] == c),
                  "total": sum(r["component"] == c for r in rows)} for c in COMPONENTS}

    metrics = {"schema": SCHEMA_METRICS, "reward": binary, "partial_reward": float(partial),
               "components": {"R": values["R"], "L": values["L"], "F": float(values["F"]),
                              "P2P": values["P2P"]},
               "reproduce": values["R"], "locate": values["L"], "fix": float(values["F"]),
               "p2p": values["P2P"], "reproducer_checks": reproducer, "locate_checks": locate,
               "fix_tests": fix_tests,
               "checks": counts}
    evaluation = {"schema": SCHEMA_EVAL, "reward": binary, "partial_reward": partial_text,
                  "partial_exact": {"numerator": partial.numerator, "denominator": partial.denominator},
                  "scoring": {"partial": FORMULA, "binary": BINARY,
                              "reproduce": "fails on buggy and passes with every correct fix (gold + alt fixes)",
                              "locate": "every gold cause matched by an answer entry, and at most one "
                                        "entry more than there are gold causes",
                              "fix": "passed fix tests / fix tests, or 0 when P2P regresses"},
                  "components": {
                      "R": {"name": COMPONENTS["R"], "value": values["R"], "checks_passed": counts["R"]["passed"],
                            "checks_total": counts["R"]["total"]},
                      "L": {"name": COMPONENTS["L"], "value": values["L"], "checks_passed": counts["L"]["passed"],
                            "checks_total": counts["L"]["total"]},
                      "F": {"name": COMPONENTS["F"], "value": fix_text,
                            "exact": f"{values['F'].numerator}/{values['F'].denominator}",
                            "fix_tests_passed": counts["F"]["passed"], "fix_tests_total": counts["F"]["total"],
                            "gated_by_p2p": not values["P2P"]},
                      "P2P": {"name": COMPONENTS["P2P"], "value": values["P2P"],
                              "checks_passed": counts["P2P"]["passed"], "checks_total": counts["P2P"]["total"]}},
                  "reproducer_checks": reproducer, "locate_checks": locate, "fix_tests": fix_tests,
                  "p2p": p2p, "checks": rows,
                  "run": run or {}}
    breakdown = [f"reward={binary}", f"partial_reward={partial_text}", f"reproduce={values['R']}",
                 f"locate={values['L']}", f"fix={fix_text}", f"p2p={values['P2P']}",
                 *(f"repro_check:{name}={status}" for name, status in reproducer.items()),
                 *(f"locate_check:{name}={status}" for name, status in locate.items()),
                 *(f"fix_test:{name}={status}" for name, status in fix_tests.items()),
                 *(f"p2p_check:{name}={status}" for name, status in p2p.items())]

    out = Path(out)
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

    write("eval.json", json.dumps(evaluation, sort_keys=True, indent=2))
    write("metrics.json", json.dumps(metrics, sort_keys=True, indent=2))
    write("partial_reward.txt", partial_text)
    write("rewards.txt", "\n".join(breakdown))
    write("reward.json", json.dumps({"reward": binary}))
    write("reward.txt", str(binary))  # committed last
    return metrics
