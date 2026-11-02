"""Trusted documentation check for Rust source files (docs/plans/rust.md section 6.3).

The grader's root process calls :func:`changed_files` on the staged candidate tree before any
candidate code runs. Nothing is compiled or executed: root reads each baseline `.rs` file as bytes
(no symlinks, at most MAX_BYTES), copies it into a root-only scratch folder and tokenises the copy
with the sealed `rslex` helper (rustc's own lexer; its sha256 is checked by the caller before it
runs). The pipeline builds the baseline with the same helper, so both agree on what a doc comment
is.

Per file, the record is the ORDERED list of doc comment tokens (`///`, `//!`, `/** */`, `/*! */`),
each ``[outer | inner, 0, sha256 of the token text, owner]``. An outer doc comment's owner is the
item it documents, read from the code tokens that follow (attributes, visibility and qualifiers
skipped): ``fn parse``, ``struct Config``, ``impl < T > Read for Cursor < T >``, ``mod io``,
``macro_rules until``, or the field / variant name. Inner doc comments are owned by ``<inner>``.
The record has the shape doc_digest.py uses for a Python module (depth is always 0, no comments),
so the baseline and the matching rule are doc_digest's own, unchanged: every baseline entry must
still be there, in order, under one of its accepted owners (the delivered tree's and the reference
repair's); added doc comments pass. Plain comments are not graded (as for Python, where the
baseline's comments are off).

Blind spots, by design: two items of the same kind and name in one file (``fn new`` in two impls)
are told apart only by order, which the ordered match already enforces; an inner doc comment may
move between modules of one file as long as the order of baseline entries holds.
"""
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

from doc_digest import _module_intact, baseline_module

MAX_BYTES = 8 * 1024 * 1024
INNER_OWNER = "<inner>"
KINDS = {"doc_outer": "outer", "doc_inner": "inner"}
QUALIFIERS = frozenset({"unsafe", "async", "default", "safe"})
ITEMS = frozenset({"fn", "struct", "enum", "union", "trait", "impl", "mod", "type", "const", "static", "use",
                   "macro_rules", "extern"})
OPEN, CLOSE = {"(": ")", "[": "]", "{": "}"}, {")", "]", "}"}


def read_source(path):
    """The bytes of a regular, non-symlink file of at most MAX_BYTES, or None."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return None
        return handle.read(MAX_BYTES + 1)


def lex(sources, rslex):
    """{key: [[start, end, label, kind], ...] or None} for {key: bytes}, from one run of the helper
    at `rslex` over root-only copies. None: the file does not fully tokenise."""
    if not sources:
        return {}
    keys = sorted(sources)
    with tempfile.TemporaryDirectory(prefix="rsdoc-") as scratch:
        os.chmod(scratch, 0o700)
        paths = []
        for index, key in enumerate(keys):
            path = os.path.join(scratch, f"{index:06d}.rs")
            with open(path, "wb") as handle:
                handle.write(sources[key])
            paths.append(path)
        result = subprocess.run([str(rslex)], input=("\n".join(paths) + "\n").encode(), capture_output=True,
                                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, timeout=600, check=False)
        reports = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if result.returncode not in (0, 1) or len(reports) != len(keys):
        raise RuntimeError(f"the Rust lexer helper failed (exit {result.returncode})")
    return {key: (report["tokens"] if report.get("ok") else None) for key, report in zip(keys, reports)}


def _matching(texts, index):
    """The index of the bracket closing the one at `index` (or len(texts))."""
    depth = 0
    for position in range(index, len(texts)):
        if texts[position] in OPEN:
            depth += 1
        elif texts[position] in CLOSE:
            depth -= 1
            if depth == 0:
                return position
    return len(texts)


def _owner(texts, kinds, k):
    """The owner named by the code tokens texts[k:] (an item header, or a field / variant name)."""
    n = len(texts)

    def at(i):
        return texts[i] if i < n else ""

    while at(k) == "#" and at(k + 1) == "[":
        k = _matching(texts, k + 1) + 1
    if at(k) == "pub":
        k += 1
        if at(k) == "(":
            k = _matching(texts, k) + 1
    while True:
        if at(k) in QUALIFIERS:
            k += 1
        elif at(k) == "const" and at(k + 1) in ("fn", "unsafe", "async", "extern"):
            k += 1
        elif at(k) == "extern" and k + 1 < n and kinds[k + 1] in ("lit_str", "lit_raw_str"):
            k += 2
        else:
            break
    word = at(k)
    if word == "impl":
        header = []
        for i in range(k, min(n, k + 24)):
            if texts[i] in ("{", ";", "where"):
                break
            header.append(texts[i])
        return " ".join(header)
    if word == "macro_rules":
        return f"macro_rules {at(k + 2)}"
    if word == "extern" and at(k + 1) == "crate":
        return f"extern crate {at(k + 2)}"
    if word == "use":
        return "use"
    if word in ITEMS:
        return f"{word} {at(k + 1)}"
    return word or "<end>"


def documentation_record(source, tokens):
    """``{"entries": [[kind, 0, sha256, owner], ...], "comments": {}}`` of one Rust source."""
    code = [(i, source[t[0]:t[1]].decode("utf-8", "replace"), t[3]) for i, t in enumerate(tokens) if t[2] == "code"]
    texts, kinds = [c[1] for c in code], [c[2] for c in code]
    entries, next_code = [], 0
    for index, token in enumerate(tokens):
        kind = KINDS.get(token[2])
        if kind is None:
            continue
        while next_code < len(code) and code[next_code][0] < index:
            next_code += 1
        owner = INNER_OWNER if kind == "inner" else _owner(texts, kinds, next_code)
        entries.append([kind, 0, hashlib.sha256(source[token[0]:token[1]]).hexdigest(), owner])
    return {"entries": entries, "comments": {}}


def records(tree, names, rslex):
    """{name: record or None} for tree-relative .rs paths (None: missing, unreadable, or not lexable)."""
    tree = Path(tree)
    sources = {name: read_source(tree / name) for name in names}
    lexed = lex({name: data for name, data in sources.items() if data is not None}, rslex)
    out = {}
    for name in names:
        tokens = lexed.get(name)
        out[name] = documentation_record(sources[name], tokens) if tokens is not None else None
    return out


def documentation_inventory(tree, reference, names, rslex):
    """{name: baseline} for the delivered `tree`, owners paired against the `reference` tree (the
    delivered tree with the reference repair applied). Raises ValueError for a file that cannot be
    read or whose baseline entries the reference repair changes."""
    delivered, repaired = records(tree, names, rslex), records(reference, names, rslex)
    out = {}
    for name in sorted(names):
        if delivered[name] is None or repaired[name] is None:
            raise ValueError(f"unreadable or not lexable Rust file: {name}")
        try:
            out[name] = baseline_module(delivered[name], repaired[name], True)
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from None
    return out


def changed_files(tree, baseline, rslex):
    """How many baseline .rs files lost, edited or reordered a baseline doc comment (0: intact)."""
    current = records(tree, sorted(baseline), rslex)
    changed = 0
    for name, expected in baseline.items():
        record = current.get(name)
        if record is None:
            changed += bool(expected["entries"])
        elif not _module_intact(record, expected, True):
            changed += 1
    return changed
