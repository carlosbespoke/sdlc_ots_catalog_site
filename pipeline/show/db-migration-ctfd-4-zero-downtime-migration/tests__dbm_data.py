"""Deterministic dataset helpers for a task's dataset.py (the production snapshot generator).

A dataset module defines `generate(ctx)` yielding `Table(name, columns, rows)` in load order (parents first). Every
random choice comes from a counter-based hash PRNG keyed by (salt, table, row index): the same salt always gives the
same rows, whatever the generation order, and a different salt (the grader's hidden one) gives different values with
the same shape. Never use the `random` module, time, or the environment in a dataset.

    from dbm_data import Table, Rng

    def generate(ctx):
        users = []
        for i in range(1, ctx.n(40000) + 1):
            r = ctx.row("users", i)
            users.append((i, r.name(), r.email(...)))
        yield Table("users", ["id", "name", "email"], users)

ctx.variant is "visible" (the snapshot the solver sees) or "hidden" (the grader's second snapshot); the hidden one may
raise the rate of the edge cases the statement describes, never add a class of case the statement does not cover.
"""
import datetime
import hashlib
import struct

FIRST = ["Ada", "Alan", "Grace", "Linus", "Barbara", "Ken", "Dennis", "Margaret", "Edsger", "Donald", "Frances", "John",
         "Radia", "Tim", "Vint", "Katherine", "Leslie", "Sophie", "Niklaus", "Hedy", "Shafi", "Yukihiro", "Guido",
         "Anita", "Chen", "Priya", "Mateo", "Amara", "Lars", "Ines", "Kwame", "Yara", "Olga", "Tariq", "Mei", "Diego",
         "Zoe", "Ravi", "Sven", "Aiko", "Fatima", "Jonas", "Lucia", "Omar", "Nadia", "Hugo", "Elif", "Kofi", "Maya"]
LAST = ["Lovelace", "Turing", "Hopper", "Torvalds", "Liskov", "Thompson", "Ritchie", "Hamilton", "Dijkstra", "Knuth",
        "Allen", "McCarthy", "Perlman", "Berners", "Cerf", "Johnson", "Lamport", "Wilson", "Wirth", "Lamarr",
        "Goldwasser", "Matsumoto", "Rossum", "Borg", "Wei", "Nair", "Garcia", "Okafor", "Nilsson", "Moreau", "Mensah",
        "Haddad", "Ivanova", "Rahman", "Lin", "Silva", "Novak", "Patel", "Berg", "Sato", "Khan", "Weber", "Rossi",
        "Farouk", "Petrova", "Laurent", "Demir", "Boateng", "Cohen"]
WORDS = ["alpha", "bravo", "cipher", "delta", "echo", "flux", "gamma", "helix", "ion", "jolt", "kilo", "lumen", "matrix",
         "nova", "omega", "pixel", "quark", "radix", "sigma", "tango", "ultra", "vector", "warp", "xenon", "yield",
         "zephyr", "binary", "kernel", "packet", "socket", "buffer", "cache", "daemon", "entropy", "fork", "glyph",
         "hash", "inode", "jump", "kludge", "lambda", "mutex", "nonce", "opcode", "parser", "queue", "regex", "shell"]


class Table:
    """One table to load: column names and an iterable of row tuples (values: None, bool, int, float, str, bytes,
    datetime/date, dict/list for JSON columns)."""

    def __init__(self, name, columns, rows):
        self.name, self.columns, self.rows = name, list(columns), rows


class Json:
    """A value for a JSON column, serialized as JSON text even when it is a scalar (true, "text", 3)."""

    def __init__(self, value):
        self.value = value


class RowRng:
    """Random values for one row: draws come from a 64-byte digest, extended by re-hashing when used up."""

    def __init__(self, seed, key):
        self._seed = seed + b"|" + key
        self._buf = hashlib.blake2b(self._seed, digest_size=64).digest()
        self._pos = 0
        self._n = 0

    def _u64(self):
        if self._pos + 8 > len(self._buf):
            self._n += 1
            self._buf = hashlib.blake2b(self._seed + b"#" + str(self._n).encode(), digest_size=64).digest()
            self._pos = 0
        v = struct.unpack_from(">Q", self._buf, self._pos)[0]
        self._pos += 8
        return v

    def random(self):
        return (self._u64() >> 11) / float(1 << 53)

    def int(self, lo, hi):
        """Uniform integer in [lo, hi]."""
        return lo + self._u64() % (hi - lo + 1)

    def chance(self, p):
        return self.random() < p

    def choice(self, seq):
        return seq[self._u64() % len(seq)]

    def weighted(self, pairs):
        """pairs: [(value, weight), ...]"""
        total = sum(w for _, w in pairs)
        x = self.random() * total
        for value, w in pairs:
            x -= w
            if x < 0:
                return value
        return pairs[-1][0]

    def skewed(self, lo, hi, power=2.0):
        """Integer in [lo, hi] biased towards lo (Zipf-like popularity)."""
        return lo + int((hi - lo + 1) * (self.random() ** power))

    def word(self):
        return self.choice(WORDS)

    def words(self, lo, hi):
        return " ".join(self.word() for _ in range(self.int(lo, hi)))

    def first_name(self):
        return self.choice(FIRST)

    def last_name(self):
        return self.choice(LAST)

    def name(self):
        return f"{self.first_name()} {self.last_name()}"

    def handle(self, i):
        return f"{self.first_name().lower()}{self.choice(['', '_', '.', ''])}{self.last_name().lower()}{i}"

    def hexstr(self, n):
        out = ""
        while len(out) < n:
            out += f"{self._u64():016x}"
        return out[:n]

    def timestamp(self, start, end):
        """Naive datetime uniformly between start and end (datetime objects), microsecond precision."""
        span = int((end - start).total_seconds() * 1_000_000)
        return start + datetime.timedelta(microseconds=self._u64() % max(span, 1))

    def ipv4(self):
        return f"{self.int(1, 223)}.{self.int(0, 255)}.{self.int(0, 255)}.{self.int(1, 254)}"

    def ipv6(self):
        return ":".join(f"{self.int(0, 65535):x}" for _ in range(8))


class Context:
    """What a dataset module gets: the salt, the variant and per-row random sources."""

    def __init__(self, salt, variant, scale=1.0):
        self.salt = str(salt)
        self.variant = variant
        self.scale = scale
        self._seed = hashlib.sha256(self.salt.encode()).digest()

    def row(self, table, index, *extra):
        key = "|".join([table, str(index), *map(str, extra)]).encode()
        return RowRng(self._seed, key)

    def n(self, count):
        """A row count scaled for quick local runs (scale 1.0 in every graded build)."""
        return max(1, int(count * self.scale))

    @property
    def hidden(self):
        return self.variant == "hidden"


# ---- serialization for bulk loading ----------------------------------------------------------------------------------
def _json(v):
    import json
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def pg_copy_value(v):
    """PostgreSQL COPY text format."""
    if v is None:
        return "\\N"
    if v is True:
        return "t"
    if v is False:
        return "f"
    if isinstance(v, Json):
        v = _json(v.value)
    elif isinstance(v, (dict, list)):
        v = _json(v)
    elif isinstance(v, datetime.datetime):
        v = v.isoformat(sep=" ")
    elif isinstance(v, datetime.date):
        v = v.isoformat()
    elif isinstance(v, (bytes, bytearray)):
        return "\\\\x" + bytes(v).hex()
    else:
        v = str(v)
    return v.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def mysql_tsv_value(v):
    """MySQL LOAD DATA default format (tab separated, backslash escapes, \\N for NULL)."""
    if v is None:
        return "\\N"
    if v is True:
        return "1"
    if v is False:
        return "0"
    if isinstance(v, Json):
        v = _json(v.value)
    elif isinstance(v, (dict, list)):
        v = _json(v)
    elif isinstance(v, datetime.datetime):
        v = v.isoformat(sep=" ")
    elif isinstance(v, datetime.date):
        v = v.isoformat()
    elif isinstance(v, (bytes, bytearray)):
        v = bytes(v).decode("latin-1")
    else:
        v = str(v)
    return (v.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
            .replace("\0", "\\0"))
