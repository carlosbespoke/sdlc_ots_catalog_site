"""Identify the one known upstream fasthttp correctness-test race."""
from __future__ import annotations

import re


KNOWN_FLAKY_TEST = "TestStreamBodyRequestContentLength"
KNOWN_FLAKY_ERROR = (
    "Unexpected error from serveConn: error when reading request headers: "
    "small read buffer."
)
_FAILED_TEST = re.compile(r"^--- FAIL: ([A-Za-z0-9_]+)(?:/[^ ]+)? ", re.MULTILINE)


def isolated_retry_test(output: str) -> str | None:
    """Return the test to retry only for its exact known scheduling failure.

    A broad retry can hide a real candidate regression. Recovery is therefore
    permitted only when this is the sole failed test and its known error text
    is present in the complete Go test output.
    """
    failures = set(_FAILED_TEST.findall(output))
    if failures == {KNOWN_FLAKY_TEST} and KNOWN_FLAKY_ERROR in output:
        return KNOWN_FLAKY_TEST
    return None
