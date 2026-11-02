"""Trusted documentation check for TypeScript source files (docs/plans/typescript.md section 6.3).

The grader's root process calls :func:`changed_files` on the staged candidate tree before any
candidate code runs. Nothing of the candidate is executed: root reads each baseline TypeScript file
as bytes (no symlinks, at most MAX_BYTES), copies it into a root-only scratch folder under its own
suffix (.tsx parses JSX, .ts does not) and parses the copy with the sealed `tsparse` helper (the
TypeScript compiler's own parser, bundled; its sha256 is checked by the caller before it runs). The
pipeline builds the baseline with the same helper, so both agree on what a JSDoc block is.

Per file, the record is the ORDERED list of JSDoc blocks (`/** */`), each
``["jsdoc", 0, sha256 of the block text, owner]``. The owner is the declaration the compiler
attaches the block to, as the helper's --docs reports it (``class_declaration Registry``,
``method_declaration Registry.register``), or ``<free>`` when it attaches to nothing. The record
has the shape doc_digest.py uses for a Python module (depth always 0, no comments), so the baseline
and the matching rule are doc_digest's own, unchanged: every baseline entry must still be there, in
order, under one of its accepted owners (the delivered tree's and the reference repair's); added
JSDoc blocks pass. Plain comments are not graded (as for Python and Rust).
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
FREE_OWNER = "<free>"


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


def parse(sources, command):
    """{key: report or None} for {key: bytes} (keys are tree-relative paths; their suffix decides how
    the copy is parsed), from one run of the helper (`command`: [node, tsparse.cjs]) with --docs over
    root-only copies. None: the file does not parse."""
    if not sources:
        return {}
    keys = sorted(sources)
    with tempfile.TemporaryDirectory(prefix="tsdoc-") as scratch:
        os.chmod(scratch, 0o700)
        paths = []
        for index, key in enumerate(keys):
            path = os.path.join(scratch, f"{index:06d}{Path(key).suffix}")
            with open(path, "wb") as handle:
                handle.write(sources[key])
            paths.append(path)
        result = subprocess.run([*map(str, command), "--docs"], input=("\n".join(paths) + "\n").encode(),
                                capture_output=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, timeout=600,
                                check=False)
        reports = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if result.returncode not in (0, 1) or len(reports) != len(keys):
        raise RuntimeError(f"the TypeScript parser helper failed (exit {result.returncode})")
    return {key: (report if report.get("ok") else None) for key, report in zip(keys, reports)}


def documentation_record(source, report):
    """``{"entries": [["jsdoc", 0, sha256, owner], ...], "comments": {}}`` of one TypeScript source."""
    owners = {start: (FREE_OWNER if kind is None else f"{kind} {name}")
              for start, _end, kind, name, _exported, _member in report.get("docs") or []}
    entries = []
    for start, end, label, _kind in report["tokens"]:
        if label == "jsdoc":
            entries.append(["jsdoc", 0, hashlib.sha256(source[start:end]).hexdigest(), owners.get(start, FREE_OWNER)])
    return {"entries": entries, "comments": {}}


def records(tree, names, command):
    """{name: record or None} for tree-relative TypeScript paths (None: missing, unreadable, or not parsable)."""
    tree = Path(tree)
    sources = {name: read_source(tree / name) for name in names}
    parsed = parse({name: data for name, data in sources.items() if data is not None}, command)
    return {name: (documentation_record(sources[name], parsed[name]) if parsed.get(name) else None) for name in names}


def documentation_inventory(tree, reference, names, command):
    """{name: baseline} for the delivered `tree`, owners paired against the `reference` tree (the
    delivered tree with the reference repair applied). Raises ValueError for a file that cannot be
    read or whose baseline entries the reference repair changes."""
    delivered, repaired = records(tree, names, command), records(reference, names, command)
    out = {}
    for name in sorted(names):
        if delivered[name] is None or repaired[name] is None:
            raise ValueError(f"unreadable or not parsable TypeScript file: {name}")
        try:
            out[name] = baseline_module(delivered[name], repaired[name], True)
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from None
    return out


def changed_files(tree, baseline, command):
    """How many baseline TypeScript files lost, edited or reordered a baseline JSDoc block (0: intact)."""
    current = records(tree, sorted(baseline), command)
    changed = 0
    for name, expected in baseline.items():
        record = current.get(name)
        if record is None:
            changed += bool(expected["entries"])
        elif not _module_intact(record, expected, True):
            changed += 1
    return changed
