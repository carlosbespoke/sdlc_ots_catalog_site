"""Rules for retrying a complete measurement cohort without cherry-picking."""
from __future__ import annotations


_ALLOCATION_STABILITY_REASON = "raw malloc samples in an allocation stability cluster"


def retryable_measurement_verdict(verdict: dict) -> bool:
    """Retry only a full cohort rejected solely for allocation launch jitter."""
    reasons = verdict.get("reasons")
    return (
        verdict.get("score") is None
        and verdict.get("status") == "invalid_evidence"
        and isinstance(reasons, list)
        and len(reasons) == 1
        and isinstance(reasons[0], str)
        and _ALLOCATION_STABILITY_REASON in reasons[0]
    )
