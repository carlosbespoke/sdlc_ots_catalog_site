"""Trusted comparison of raw observations (runs only in the root grader and in authoring tools).

Case runners return raw values only: strings, integers, floats rounded to six decimals, nested lists and
dicts, byte strings as {"bytes": latin-1 text}, datetimes as {"datetime": ISO text}, exception class names.
Every verdict is made here. Integers, booleans, strings, None and container structure must match exactly;
floats match when |a - b| <= 1e-9 + 1e-9 * |b| (b is the expected value). Non-finite floats arrive as the
strings "nan", "inf" and "-inf".

One structured form carries a comparison that cannot be pinned to a fixed value: a case returns
{"same": [a, b]} for two raw values computed from one random run (for example a signature the library put in its
output and the signature recomputed independently from the same output). It matches an expected {"same": [x, y]}
when the observed a == b exactly and the expected x == y (the reference run agreed with itself), or when a != b
and x != y.
"""
import math

ATOL = 1e-9
RTOL = 1e-9


def _exact(a, b):
    """Structural equality with float tolerance."""
    if isinstance(b, bool) or b is None or isinstance(b, str):
        return type(a) is type(b) and a == b
    if isinstance(b, int):
        return isinstance(a, int) and not isinstance(a, bool) and a == b
    if isinstance(b, float):
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            return False
        x, y = float(a), float(b)
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
        return abs(x - y) <= ATOL + RTOL * abs(y)
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(_exact(o, e) for o, e in zip(a, b))
    if isinstance(b, dict):
        return isinstance(a, dict) and set(a) == set(b) and all(_exact(a[k], b[k]) for k in b)
    return False


def _pair(value):
    return (isinstance(value, dict) and set(value) == {"same"} and isinstance(value["same"], list)
            and len(value["same"]) == 2)


def close(observed, expected):
    """True when an observation matches its expected value."""
    if _pair(expected):
        if not _pair(observed):
            return False
        return _exact(*observed["same"]) == _exact(*expected["same"])
    if isinstance(expected, list):
        return (isinstance(observed, list) and len(observed) == len(expected)
                and all(close(o, e) for o, e in zip(observed, expected)))
    if isinstance(expected, dict):
        return (isinstance(observed, dict) and set(observed) == set(expected)
                and all(close(observed[key], expected[key]) for key in expected))
    return _exact(observed, expected)
