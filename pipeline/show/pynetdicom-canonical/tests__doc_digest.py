"""Trusted documentation check: the task's documentation is where the delivered tree put it.

The instruction forbids editing or deleting documentation to make a disagreement go away. The
trusted grader calls :func:`documentation_preserved` on the staged candidate tree, in its own root
process, before any candidate code runs. Nothing is imported or executed: pages are read as bytes,
Python files are parsed with :mod:`ast` and their comments read with :mod:`tokenize`.

The sealed baseline (``tests/private/documentation.json``) names every in-scope file of the
delivered tree and records:

* per documentation page, the sha256 of its bytes;
* per in-scope Python file, the ORDERED sequence of its documentation entries, one per module,
  class, function or method docstring and per bare string statement in a module or class body
  (attribute docstrings and module narrative, such as text after ``from __future__`` imports).
  Each entry is ``[kind, nesting depth, sha256 of the exact string, accepted owners]``. An
  entry's owner is the qualified name of the symbol it documents: the dotted path of the
  enclosing class and def names ending with the documented definition's own name (``Box.open``),
  the enclosing class or def for a bare string, and ``<module>`` for the module docstring and
  module-level strings. The accepted owners are the entry's owner in the delivered tree and in
  the tree after the reference repair (``solution/solution.patch``), which must yield the same
  (kind, depth, sha256) sequence;
* when the baseline's ``comments`` is ``"on"``, per in-scope Python file and per owner, the
  multiset of its comment hashes. A comment's owner is the qualified name of the innermost class
  or def whose lines (from its first decorator to its last statement) contain it, else
  ``<module>``. Its text is the ``#`` comment token with every leading ``#`` removed and then
  surrounding whitespace stripped; its hash is the sha256 of that text. Empty comments and tool
  directives are not documentation and are never recorded: a shebang (``#!`` on line 1), a
  PEP 263 coding line (line 1 or 2), and any comment whose text begins (case-insensitively) with
  ``noqa`` or ``nosec`` followed by the end, whitespace or a colon, or with ``type:``,
  ``pragma:``, ``pylint:``, ``fmt:``, ``isort:``, ``mypy:``, ``pyright:``, ``ruff:``,
  ``flake8:`` or ``yapf:`` (spaces allowed before the colon). A comment is in the
  baseline only when the same owner carries it in both the delivered and the reference-repair
  tree, so a comment the reference repair edits, moves or deletes is exempt.

``documentation_preserved`` returns ``"intact"`` exactly when every baseline page has the same
bytes, every baseline Python file yields the same (kind, depth, sha256) sequence with each
entry's current owner among its accepted owners, and (comments on) every owner still carries at
least its baseline comments. So:

* renaming an undocumented symbol passes, and so does adding, removing or changing code that
  carries no documentation (a new undocumented helper, a removed undocumented closure);
* renaming a documented symbol passes only to the name the reference repair gives it; a
  docstring cannot change owner, so moving one onto a neighbour fails even when the neighbour is
  adjacent, undocumented and of the same kind and depth;
* editing, deleting, reordering or swapping docstrings fails, as does moving one to another
  file (the file it left no longer matches);
* adding a docstring or documentation string to a baseline file fails; tolerating additions
  would let a solver edit a docstring while parking the original text elsewhere;
* with comments on, editing, deleting or moving a baseline comment to another owner fails, and
  adding comments passes;
* files that are not in the baseline are not checked, so a new module, documented or not, passes.

Shared template: ``skills/_shared/templates/doc_digest.py``. Copy it verbatim to
``tests/doc_digest.py``; the task's scope and comment setting live only in the sealed baseline,
which ``skills/_shared/scripts/doc-check.py`` writes.
"""
import ast
from collections import Counter
import hashlib
import io
from pathlib import Path
import re
import tokenize

FORMAT = "spec-drift-doc-sequence-v2"
MAX_BYTES = 8 * 1024 * 1024
MODULE_OWNER = "<module>"
_DEFINITIONS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_CODING = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")
_DIRECTIVE = re.compile(
    r"(?:noqa|nosec)(?:$|[\s:])|(?:type|pragma|pylint|fmt|isort|mypy|pyright|ruff|flake8|yapf)\s*:",
    re.IGNORECASE)
_UNREADABLE = (SyntaxError, UnicodeDecodeError, RecursionError, MemoryError, ValueError, OSError,
               tokenize.TokenError)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _readable(path):
    return path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_BYTES


def _string(statement):
    if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)):
        return statement.value.value
    return None


def _blocks(statement):
    """The statement lists nested in a compound statement (if/for/while/with/try/match)."""
    for field in ("body", "orelse", "finalbody"):
        block = getattr(statement, field, None)
        if isinstance(block, list):
            yield block
    for handler in getattr(statement, "handlers", None) or []:
        yield handler.body
    for case in getattr(statement, "cases", None) or []:
        yield case.body


def _walk(module):
    """The ordered ``[kind, depth, sha256, owner]`` entries and the (first line, last line,
    qualified name) span of every definition, outer definitions before the ones they contain."""
    entries, spans = [], []

    def walk(block, depth, container, first, prefix):
        # container: "module" or "class" (bare strings there are documentation) or "function"
        # (only nested definitions are documentation there). `first` marks the owner's own body,
        # whose leading string is the owner's docstring and was recorded by the caller.
        for index, statement in enumerate(block):
            if isinstance(statement, _DEFINITIONS):
                if isinstance(statement, ast.ClassDef):
                    kind = "class"
                else:
                    kind = "method" if container == "class" else "function"
                name = f"{prefix}.{statement.name}" if prefix else statement.name
                start = min([statement.lineno] + [d.lineno for d in statement.decorator_list])
                spans.append((start, statement.end_lineno or statement.lineno, name))
                docstring = _string(statement.body[0]) if statement.body else None
                if docstring is not None:
                    entries.append([kind, depth + 1, _sha(docstring), name])
                walk(statement.body, depth + 1,
                     "class" if kind == "class" else "function", True, name)
            elif container != "function" and _string(statement) is not None:
                if not (first and index == 0):
                    entries.append(["string", depth, _sha(_string(statement)),
                                    prefix or MODULE_OWNER])
            else:
                for nested in _blocks(statement):
                    walk(nested, depth, container, False, prefix)

    docstring = _string(module.body[0]) if module.body else None
    if docstring is not None:
        entries.append(["module", 0, _sha(docstring), MODULE_OWNER])
    walk(module.body, 0, "module", True, "")
    return entries, spans


def _comment_text(token):
    """The normalised text of a comment token, or None for an empty comment or a directive."""
    line = token.start[0]
    if line == 1 and token.start[1] == 0 and token.string.startswith("#!"):
        return None
    if line <= 2 and _CODING.match(token.line):
        return None
    text = token.string.lstrip("#").strip()
    if not text or _DIRECTIVE.match(text):
        return None
    return text


def _comments(source, spans):
    """{owner: sorted comment hashes} for one Python source text."""
    lines = source.count("\n") + 2
    owners = [MODULE_OWNER] * (lines + 1)
    for start, end, name in spans:
        for line in range(start, min(end, lines) + 1):
            owners[line] = name
    found = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            text = _comment_text(token)
            if text is not None:
                found.setdefault(owners[min(token.start[0], lines)], []).append(_sha(text))
    return {owner: sorted(hashes) for owner, hashes in sorted(found.items())}


def documentation_record(source, comments):
    """``{"entries": [[kind, depth, sha256, owner]...], "comments": {owner: [sha256...]}}`` of one
    Python source text; ``comments`` is empty unless `comments` is true."""
    entries, spans = _walk(ast.parse(source))
    return {"entries": entries, "comments": _comments(source, spans) if comments else {}}


def module_record(path, comments):
    """The record of the Python file at `path`, or None when it is missing or unreadable."""
    try:
        if not _readable(path):
            return None
        return documentation_record(path.read_text(encoding="utf-8"), comments)
    except _UNREADABLE:
        return None


def page_digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if _readable(path) else None
    except OSError:
        return None


def baseline_module(delivered, reference):
    """The baseline of one Python file from its delivered and reference-repair records."""
    shape = [entry[:3] for entry in delivered["entries"]]
    if [entry[:3] for entry in reference["entries"]] != shape:
        raise ValueError("the reference repair changes the file's documentation entries")
    entries = [entry[:3] + [sorted({entry[3], other[3]})]
               for entry, other in zip(delivered["entries"], reference["entries"])]
    comments = {}
    for owner, hashes in delivered["comments"].items():
        kept = Counter(hashes) & Counter(reference["comments"].get(owner, ()))
        if kept:
            comments[owner] = sorted(kept.elements())
    return {"entries": entries, "comments": comments}


def documentation_inventory(tree, pages, modules, *, reference=None, comments=None):
    """The sealed baseline of the delivered `tree` for the given page and Python-file paths
    (tree-relative), with owners and comments paired against the `reference` tree (the delivered
    tree with the reference repair applied; the delivered tree itself when the task has no
    repair). `comments` is True or False. Raises ValueError for a file whose record the reference
    repair changes or that cannot be read; build baselines with ``doc-check.py``, not by hand."""
    if reference is None or comments not in (True, False):
        raise TypeError("documentation_inventory needs reference= and comments=; regenerate the "
                        "baseline with skills/_shared/scripts/doc-check.py regenerate TASK")
    tree, reference = Path(tree), Path(reference)
    records = {}
    for name in sorted(modules):
        delivered, repaired = module_record(tree / name, comments), module_record(reference / name, comments)
        if delivered is None or repaired is None:
            raise ValueError(f"unreadable or unparsable Python file: {name}")
        try:
            records[name] = baseline_module(delivered, repaired)
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from None
    return {
        "format": FORMAT,
        "comments": "on" if comments else "off",
        "pages": {page: page_digest(tree / page) for page in sorted(pages)},
        "modules": records,
    }


def _module_intact(current, baseline):
    if len(current["entries"]) != len(baseline["entries"]):
        return False
    for entry, expected in zip(current["entries"], baseline["entries"]):
        if entry[:3] != expected[:3] or entry[3] not in expected[3]:
            return False
    for owner, hashes in baseline["comments"].items():
        if Counter(hashes) - Counter(current["comments"].get(owner, ())):
            return False
    return True


def documentation_preserved(tree, delivered):
    """'intact' when every baseline page is byte-identical and every baseline Python file keeps its
    documentation entries in order, each under an accepted owner, and (comments on) every
    baseline comment under its owner; otherwise a count of the changed pages and files."""
    if not isinstance(delivered, dict) or delivered.get("format") != FORMAT:
        raise ValueError("documentation baseline has an unknown format")
    comments = delivered.get("comments") == "on"
    tree = Path(tree)
    changed_pages = sum(1 for page, digest in delivered["pages"].items()
                        if digest is None or page_digest(tree / page) != digest)
    changed_modules = 0
    for name, baseline in delivered["modules"].items():
        current = module_record(tree / name, comments)
        if baseline is None:
            changed_modules += 1
        elif current is None:
            # A missing file carried no documentation only if the baseline recorded none.
            changed_modules += bool(baseline["entries"] or baseline["comments"])
        elif not _module_intact(current, baseline):
            changed_modules += 1
    if not changed_pages and not changed_modules:
        return "intact"
    return f"changed: {changed_pages} pages, {changed_modules} modules"
