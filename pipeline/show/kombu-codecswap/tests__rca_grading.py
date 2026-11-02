"""Deterministic validation and scoring of the agent's /workdir/rca.json (stdlib only).

Copy to tests/rca_grading.py beside reward_writer.py; tests/grade.py imports it:

    from rca_grading import (load_answer, answer_checks, reproducer_path, reproducer_fixes,
                             reproducer_checks, reproducer_missing)
    answer, problems = load_answer(Path("/workdir/rca.json"))
    checks += answer_checks(answer, problems, meta, root=PRISTINE)   # L rows; root = buggy tree
    repro = reproducer_path(Path("/workdir/rca.json"), meta)   # the test R runs (None -> R = 0)
    if repro is None:
        checks += reproducer_missing("no usable reproducer")
    else:
        on_buggy = run_repro(buggy_tree)                       # "fail" | "pass" | "error" | "crashed"
        on_fixes = [(label, run_repro(buggy_tree + patch))     # gold first, then each alt fix
                    for label, patch in reproducer_fixes(meta, Path("/tests"))]
        checks += reproducer_checks(on_buggy, on_fixes, meta)  # the R rows

rca.json (templates/rca.schema.json):

    {"root_causes": [{"file": "<repo-relative path>", "function": "<name>"}, ...],
     "reproducer": "<repo-relative path of the agent's regression test>"}

The legacy `"root_cause": {"file", "function"}` object is still accepted as a one-element
`root_causes` list (`root_causes` wins when both are present).

Rules (docs/task-contract.md):
- A missing or invalid rca.json scores L = 0, and R falls back to meta.json `default_reproducer`
  (R = 0 when that is absent too). Unknown top-level keys are ignored.
- Paths are repo-relative; a leading `/workdir/` or `./` is stripped, `\\` becomes `/`, and
  absolute paths or `..` segments make the answer invalid. File comparison is exact.
- Function names are normalized to dotted components: Go `(*Recv).Method` / `(Recv).Method`,
  Rust/C++ `Type::method`, `module::function`, `<Type as Trait>::method` and generic arguments
  (`Vec<T>::push`) all become `Recv.Method` / `Type.method` / `module.function`, and a trailing
  parameter list (`()`, C++ `(int) const`) is removed. Two names match when the shorter one's components are the tail of the longer
  one's: `method` matches `Class.method`, `crate::de::Parser::parse` matches `Parser::parse`, but
  `Other.method` never matches `Class.method`. A named Go receiver `(m *Recv).Method` or
  `(m *Recv) Method` normalizes like `(*Recv).Method`.
- Bare names (grade.py passes `root=` the pristine buggy tree to answer_checks): a bare answer
  name (one component) matches a gold name with a receiver/class/module component only when that
  name is unambiguous in the answer's file of the buggy tree (one Go owner, one Python qualname,
  one Rust `fn`). Defined more than once there -> no match (the name must be qualified, as the
  instruction asks). An unreadable file, an unknown language or a scan that finds no definition is
  inconclusive: the entry matches as before and the cause row's detail carries a note. Without
  `root` (older graders, rca check) matching is the plain tail rule. An accept-list entry that is
  itself a bare name always matches the bare answer.
- L (multi-cause): meta.json `root_causes` = [{"accept": [{file, function}, ...]}, ...], one entry per
  gold cause, each with its own accept-list (legacy `root_cause` = one accept-list = one cause).
  L = 1 iff a bipartite matching assigns every gold cause its own answer entry (each entry matches
  that cause's accept-list and counts for at most one cause, so a bare `toRaw` that tail-matches
  two causes covers only one, and identical entries after normalisation count once) AND the answer lists at most len(gold causes) entries (anti-shotgun,
  no slack). Rows: `locate:cause_N` per gold cause and
  `locate:entries`; a missing or invalid rca.json gives the single row `L`. No gold values leak.
- meta.json: `root_causes` (or legacy `root_cause`) as above; `default_reproducer` an
  optional safe path; `fix_tests` the 2-4 hidden fix tests (gold reproducer + 1-3 variants);
  `p2p` the existing-suite selection ({"command": ..., "selection"?: ..., "excluded"?: [{"id": test
  id, "why": justification}]}, see p2p_excluded); `alt_fixes` 1-2 alternative correct patches
  under tests/ (optional for backward compatibility; `rca check` warns without it).
- R (multi-fix): the reproducer must fail on the clean buggy tree AND pass on buggy + gold.patch AND
  pass on buggy + each meta.json `alt_fixes` patch. A reproducer that inspects source text, or
  pins the internals of the gold implementation, fails at least one of the correct fixes.
- A reproducer process killed by a signal (negative return code, or exit 128+N under a shell; not
  the grader's own timeout kill) is the outcome "crashed" (crash_outcome): its row still fails
  (R = 0 for that tree, as an "error" would), but it carries `"crashed": "<SIGNAME>"` and reads
  `crashed: <SIGNAME>` in eval.json, metrics.json and rewards.txt, so a nondeterministic crash path
  is visible (cvxpy-paramcache v2: a cvxcore segfault read as "no test report").
"""
from __future__ import annotations

import json
import re
import signal as _signal
import sys
from pathlib import Path, PurePosixPath

MAX_BYTES = 64 * 1024
MIN_FIX_TESTS, MAX_FIX_TESTS = 2, 4   # the gold reproducer plus 1-3 variant tests
MIN_ALT_FIXES, MAX_ALT_FIXES = 1, 2   # alternative correct patches the reproducer must also pass
GOLD_FIX = "gold.patch"
MIN_JUSTIFICATION = 10                # characters in a p2p.excluded justification
EXTRA_ANSWER_SLACK = 0                # answer entries allowed beyond the gold causes (anti-shotgun: none)
REPRO_OUTCOMES = {"fail", "pass", "error", "crashed"}
MAX_SIGNAL = 64                       # exit 128+N under a shell names signal N only for N <= this
MAX_NESTING = 64                      # containers deep: deeper candidate-influenced JSON/TOML is rejected


# --- candidate-influenced structured input: parse or fail closed ----------------------------------
# Every parse of data the candidate can shape (rca.json, an edited pyproject.toml, a probe's or the
# suite's output lines) goes through safe_parse. A malformed, oversized or deeply nested input must
# score its part 0, never crash the grader: a parser's RecursionError (or MemoryError) on input
# nested thousands of levels deep escapes every `except ValueError`, the run is then recorded as a
# verifier error instead of a grade, and a failing run escapes scoring (mashumaro-pagerules v2 and
# gitcliff-sortorder argus-main).

class UntrustedInputError(ValueError):
    """A candidate-influenced input that is malformed, oversized or nested too deeply; `reason`
    is a short phrase for a feedback line."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def nesting_exceeds(value, limit=MAX_NESTING):
    """True when lists/tuples/dicts in `value` nest more than `limit` deep (iterative, so the
    check itself cannot recurse)."""
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, dict):
            children = item.values()
        elif isinstance(item, (list, tuple)):
            children = item
        else:
            continue
        if depth >= limit:
            return True
        stack.extend((child, depth + 1) for child in children)
    return False


def safe_parse(parse, text, *, max_bytes=None, max_depth=MAX_NESTING, errors=(ValueError,)):
    """parse(text) for candidate-influenced text, failing closed. Raises UntrustedInputError (a
    ValueError) with a short reason when `text` is longer than `max_bytes`, when the parser raises
    one of `errors` or gives up on the input (RecursionError, MemoryError), or when the result nests
    containers more than `max_depth` deep. Never lets anything else from the parser escape."""
    if max_bytes is not None and len(text) > max_bytes:
        raise UntrustedInputError(f"larger than {max_bytes} bytes")
    try:
        value = parse(text)
    except (RecursionError, MemoryError):
        raise UntrustedInputError("nested too deeply or too large to parse") from None
    except errors as error:
        raise UntrustedInputError(f"does not parse ({str(error)[:200]})") from None
    if max_depth is not None and nesting_exceeds(value, max_depth):
        raise UntrustedInputError(f"nested more than {max_depth} levels deep")
    return value


def safe_json(text, *, max_bytes=None, max_depth=MAX_NESTING, finite=False):
    """json.loads through safe_parse (str or bytes). finite=True rejects NaN/Infinity."""
    if finite:
        return safe_parse(lambda t: json.loads(t, parse_constant=_reject_non_finite), text,
                          max_bytes=max_bytes, max_depth=max_depth)
    return safe_parse(json.loads, text, max_bytes=max_bytes, max_depth=max_depth)


def _reject_non_finite(name):
    raise ValueError(f"non-finite number {name}")


def normalize_path(value):
    """Repo-relative POSIX path, or None when the value is not a safe relative path."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("\\", "/")
    for prefix in ("/workdir/", "./"):
        while text.startswith(prefix):
            text = text[len(prefix):]
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) == ".":
        return None
    return str(path)


# Go receivers: (*Recv).M, (Recv).M, (r *Recv).M, (r *Recv) M, (s *Set[T]).M -> Recv.M
GO_RECEIVER = re.compile(r"\(\s*(?:[A-Za-z_]\w*\s+)?\*?\s*([A-Za-z_]\w*)\s*(?:\[[^\[\]()]*\])?\s*\)"
                         r"(?:\s*\.|\s+(?=[A-Za-z_]))")
GO_FUNC_KEYWORD = re.compile(r"^func\s+(?=\()")       # `func (m *Recv) Method` as copied from source
QUALIFIED_SELF = re.compile(r"<\s*([A-Za-z_][\w:]*)\s+as\s+[^<>]*>")   # Rust <Type as Trait>
GENERIC_ARGS = re.compile(r"<[^<>]*>")
TRAILING_PARAMS = re.compile(r"\s*\([^()]*\)\s*(const)?\s*$")   # f(), C++ f(int) const
NAME = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")


def normalize_function(value):
    """Canonical dotted name, or None when it is not a function name."""
    if not isinstance(value, str):
        return None
    text = TRAILING_PARAMS.sub("", value.strip())
    text = GO_RECEIVER.sub(lambda m: m.group(1) + ".", GO_FUNC_KEYWORD.sub("", text))
    for _ in range(6):  # innermost first: <Foo<T> as Bar>::baz, Map<K, Vec<V>>::get
        stripped = GENERIC_ARGS.sub("", QUALIFIED_SELF.sub(lambda m: m.group(1), text))
        if stripped == text:
            break
        text = stripped
    text = re.sub(r"\s*(::|\.)\s*", ".", text)
    text = text.lstrip(".")  # C++ global scope `::f`
    return text if NAME.match(text) else None


def function_matches(answer, gold):
    """True when one normalized name's components are the tail of the other's."""
    answer, gold = normalize_function(answer), normalize_function(gold)
    if answer is None or gold is None:
        return False
    a, g = answer.split("."), gold.split(".")
    shorter, longer = (a, g) if len(a) <= len(g) else (g, a)
    return longer[len(longer) - len(shorter):] == shorter


MAX_SCAN_BYTES = 8 * 1024 * 1024     # larger source files are not scanned (inconclusive)
GO_FUNC = re.compile(r"^[ \t]*func[ \t]*(?:\(([^)]*)\)[ \t]*)?([A-Za-z_]\w*)[ \t]*[\[(]", re.M)
GO_RECV_TYPE = re.compile(r"^\s*(?:[A-Za-z_]\w*\s+)?\*?\s*([A-Za-z_]\w*)")
RUST_FN = re.compile(r"^[ \t]*(?:pub(?:[ \t]*\([^)]*\))?[ \t]+)?(?:(?:default|const|async|unsafe|extern"
                     r"(?:[ \t]+\"[^\"]*\")?)[ \t]+)*fn[ \t]+(r#)?([A-Za-z_]\w*)[ \t]*[<(]", re.M)


def _python_owners(text, name):
    """Distinct qualified names (outer scopes dotted, `<locals>` dropped) of every def `name`;
    None when the file does not parse."""
    import ast
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):   # too deep: inconclusive
        return None
    found = set()
    stack = [(tree, [])]                       # iterative: a deep tree cannot recurse the grader
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not isinstance(child, ast.ClassDef) and child.name == name:
                    found.add(".".join(scope + [name]))
                stack.append((child, scope + [child.name]))
            else:
                stack.append((child, scope))
    return found


def definition_count(root, file, name):
    """(count, reason) for how many distinct functions/methods called `name` the file `file` of
    the tree `root` defines: Go by owner (receiver type, or none), Python by qualified name (so a
    property setter or @overload of the same method counts once), Rust by `fn name` occurrences.
    count None means inconclusive (reason says why); the caller then keeps the plain tail rule."""
    rel = normalize_path(file)
    if rel is None:
        return None, "unusable file path"
    path = Path(root) / rel
    try:
        if not path.is_file():
            return None, "file not found in the buggy tree"
        if path.stat().st_size > MAX_SCAN_BYTES:
            return None, "file too large to scan"
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, "file unreadable"
    suffix = PurePosixPath(rel).suffix.lower()
    if suffix == ".go":
        owners = set()
        for match in GO_FUNC.finditer(text):
            if match.group(2) == name:
                recv = GO_RECV_TYPE.match(match.group(1)) if match.group(1) is not None else None
                owners.add(recv.group(1) if recv else None)
        count = len(owners)
    elif suffix in (".py", ".pyi"):
        owners = _python_owners(text, name)
        if owners is None:
            return None, "file does not parse"
        count = len(owners)
    elif suffix == ".rs":
        count = sum(match.group(2) == name for match in RUST_FN.finditer(text))
    else:
        return None, f"no definition scan for {suffix or 'extensionless'} files"
    if count == 0:
        return None, "no definition found by the scan"
    return count, None


def _site_match(answer, accepted, root=None):
    """(matched, note, ambiguous) for one answer entry against one accept-list.

    Without `root` this is the plain tail rule. With `root` (the pristine buggy tree), a bare
    answer name matching a qualified gold name needs the name to be unambiguous in the file;
    an inconclusive scan matches and returns a note; `ambiguous` says a tail match was refused."""
    if not isinstance(answer, dict):
        return False, None, False
    file = normalize_path(answer.get("file"))
    if file is None:
        return False, None, False
    name = normalize_function(answer.get("function"))
    ambiguous, note = False, None
    for gold in accepted or []:
        if not (isinstance(gold, dict) and file == normalize_path(gold.get("file"))
                and function_matches(answer.get("function"), gold.get("function"))):
            continue
        gold_name = normalize_function(gold.get("function"))
        if root is None or "." in name or "." not in gold_name:
            return True, None, False
        count, reason = definition_count(root, file, name)
        if count is None:
            note = (f"note: receiver-less name {name!r} accepted without an ambiguity check "
                    f"({reason})")
            continue                           # a later entry may match without a note
        if count == 1:
            return True, None, False
        ambiguous = True
    if note is not None:
        return True, note, False
    return False, None, ambiguous


def site_matches(answer, accepted, root=None):
    """True when {file, function} matches any entry of a meta.json accept-list. With `root` (the
    pristine buggy tree) a bare name must be unambiguous in its file to match a qualified gold
    name (_site_match); without it, the plain tail rule (backward compatible)."""
    return _site_match(answer, accepted, root)[0]


def _site_problems(site, label):
    if not isinstance(site, dict):
        return [f"{label} must be an object with file and function"]
    problems = []
    if normalize_path(site.get("file")) is None:
        problems.append(f"{label}.file must be a repo-relative path")
    if normalize_function(site.get("function")) is None:
        problems.append(f"{label}.function must be a function name")
    return problems


def validate(data):
    """Problems with a parsed rca.json (empty list = valid). Mirrors templates/rca.schema.json."""
    if not isinstance(data, dict):
        return ["rca.json must be a JSON object"]
    problems = []
    if "root_causes" in data:
        sites = data["root_causes"]
        if not isinstance(sites, list) or not sites:
            problems.append("root_causes must be a nonempty list of {file, function} objects")
        else:
            for index, site in enumerate(sites):
                problems += _site_problems(site, f"root_causes[{index}]")
    elif "root_cause" in data:                       # legacy single-cause answer
        problems += _site_problems(data["root_cause"], "root_cause")
    else:
        problems.append("root_causes must be a nonempty list of {file, function} objects")
    if normalize_path(data.get("reproducer")) is None:
        problems.append("reproducer must be a repo-relative path")
    return problems


def load_answer(path):
    """(answer dict or None, problems). None means missing or invalid: L = 0."""
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file():
            return None, ["rca.json is missing"]
        if path.stat().st_size > MAX_BYTES:
            return None, ["rca.json is larger than 64 KiB"]
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return None, ["rca.json is not readable UTF-8 JSON"]
    try:
        data = safe_json(text)
    except UntrustedInputError as error:
        if error.reason.startswith("does not parse"):
            return None, ["rca.json is not readable UTF-8 JSON"]
        return None, [f"rca.json is not usable: {error.reason}"]
    problems = validate(data)
    return (None if problems else data), problems


def answer_sites(answer):
    """The {file, function} entries of a valid rca.json: `root_causes`, or the legacy
    `root_cause` object as a one-element list; [] when neither is present."""
    if not isinstance(answer, dict):
        return []
    if "root_causes" in answer:
        sites = answer["root_causes"]
        return list(sites) if isinstance(sites, list) else []
    return [answer["root_cause"]] if isinstance(answer.get("root_cause"), dict) else []


def gold_causes(meta):
    """meta.json gold causes as a list of accept-lists: `root_causes` [{"accept": [...]}, ...], or
    the legacy `root_cause` accept-list as a single cause; [] when neither is usable."""
    meta = meta if isinstance(meta, dict) else {}
    if "root_causes" in meta:
        causes = meta["root_causes"]
        if not isinstance(causes, list):
            return []
        return [list(c["accept"]) for c in causes if isinstance(c, dict) and isinstance(c.get("accept"), list)]
    legacy = meta.get("root_cause")
    return [list(legacy)] if isinstance(legacy, list) and legacy else []


def gold_sites(meta):
    """Every accepted {file, function} across all gold causes (for leak checks)."""
    return [site for accept in gold_causes(meta) for site in accept if isinstance(site, dict)]


def max_answer_entries(causes):
    """Most rca.json root_causes entries L tolerates for this many gold causes (anti-shotgun)."""
    return causes + EXTRA_ANSWER_SLACK


def _site_key(site):
    """(normalized file, normalized function) of an answer entry, or None when it is unusable."""
    if not isinstance(site, dict):
        return None
    file, function = normalize_path(site.get("file")), normalize_function(site.get("function"))
    return None if file is None or function is None else (file, function)


def cause_matches(sites, causes, root=None):
    """[(cause index, assigned answer entry index or None)] for each gold cause.

    A maximum bipartite matching between gold causes and answer entries: each answer entry is
    assigned to at most one cause, so one bare entry (e.g. a method name that tail-matches the
    accept-lists of two causes) can never cover two causes. Deterministic: causes are tried in
    order, entries in index order (Kuhn's augmenting paths). Entries identical after normalisation
    (same file, same function) are deduplicated first: only the first copy can be assigned, so
    [toRaw, toRaw] still covers one cause (the entry-count limit still counts every raw entry)."""
    distinct, seen_keys = [], set()
    for index, site in enumerate(sites):
        key = _site_key(site)
        if key is None or key not in seen_keys:
            distinct.append(index)
        if key is not None:
            seen_keys.add(key)
    edges = [[i for i in distinct if site_matches(sites[i], accept, root)] for accept in causes]
    owner = {}                                   # answer entry index -> cause index

    def augment(cause, seen):
        for entry in edges[cause]:
            if entry in seen:
                continue
            seen.add(entry)
            if entry not in owner or augment(owner[entry], seen):
                owner[entry] = cause
                return True
        return False

    for cause in range(len(causes)):
        augment(cause, set())
    assigned = {cause: entry for entry, cause in owner.items()}
    return [(number, assigned.get(number)) for number in range(len(causes))]


def _cause_detail(hit, candidates, note=None, ambiguous=False):
    if hit is not None:
        return f"assigned root_causes[{hit}]" + (f"; {note}" if note else "")
    if candidates:
        return ("unmatched: every root_causes entry that matches it is assigned to another cause "
                "(one entry counts for at most one cause; identical entries count once)")
    if ambiguous:
        return ("unmatched: no root_causes entry matches (a bare function name that its file "
                "defines more than once needs its receiver/class/type)")
    return "unmatched: no root_causes entry matches"


def answer_checks(answer, problems, meta, root=None):
    """The L check rows for reward_writer.write_rewards. Never reveals gold values.

    `root`: the pristine buggy tree (grade.py passes PRISTINE). With it, a bare answer name only
    matches a qualified gold name when the name is unambiguous in its file (_site_match); an
    inconclusive scan matches and the cause row's detail carries a note. None = plain tail rule.

    Missing/invalid rca.json: the single row `L`. Otherwise one `locate:cause_N` row per gold
    cause (passed when the bipartite matching of cause_matches assigns it an answer entry that
    matches its accept-list; each entry is assigned to at most one cause) and `locate:entries`
    (passed when the answer lists at most len(gold causes) entries). L = 1 iff all pass."""
    if answer is None:
        detail = "; ".join(problems)[:300] or "rca.json missing or invalid"
        return [{"id": "L", "component": "L", "status": "missing" if "missing" in detail else "failed",
                 "detail": detail}]
    sites, causes = answer_sites(answer), gold_causes(meta)
    if not causes:
        return [{"id": "L", "component": "L", "status": "error", "detail": "meta.json has no usable root causes"}]
    rows = []
    for number, hit in cause_matches(sites, causes, root):
        if hit is not None:
            note, candidates, ambiguous = _site_match(sites[hit], causes[number], root)[1], False, False
        else:
            found = [_site_match(site, causes[number], root) for site in sites]
            note, candidates, ambiguous = None, any(m[0] for m in found), any(m[2] for m in found)
        rows.append({"id": f"locate:cause_{number + 1}", "component": "L",
                     "status": "passed" if hit is not None else "failed",
                     "detail": _cause_detail(hit, candidates, note, ambiguous)})
    within = len(sites) <= max_answer_entries(len(causes))
    rows.append({"id": "locate:entries", "component": "L", "status": "passed" if within else "failed",
                 "detail": (f"{len(sites)} entries listed" + ("" if within else
                            "; extra entries beyond the defects that exist cost the locate part"))})
    return rows


def reproducer_path(rca_file, meta):
    """Repo-relative path of the test R runs: rca.json's `reproducer` when rca.json is valid,
    else meta.json's `default_reproducer`. None means R cannot run, so R = 0."""
    answer, _ = load_answer(rca_file)
    if answer is not None:
        return normalize_path(answer["reproducer"])
    return normalize_path((meta or {}).get("default_reproducer"))


def meta_problems(meta):
    """Problems with a task's meta.json (used by `rca check`)."""
    if not isinstance(meta, dict):
        return ["meta.json must be an object"]
    problems = root_cause_problems(meta)
    if "default_reproducer" in meta and normalize_path(meta["default_reproducer"]) is None:
        problems.append("meta.json default_reproducer must be a repo-relative path")
    tests = meta.get("fix_tests")
    if (not isinstance(tests, list) or not MIN_FIX_TESTS <= len(tests) <= MAX_FIX_TESTS
            or any(not isinstance(t, str) or not t.strip() for t in tests) or len(set(tests)) != len(tests)):
        problems.append(f"meta.json fix_tests must list {MIN_FIX_TESTS}-{MAX_FIX_TESTS} distinct hidden "
                        "tests: the gold reproducer plus 1-3 variants")
    p2p = meta.get("p2p")
    if not isinstance(p2p, dict) or not isinstance(p2p.get("command"), str) or not p2p["command"].strip():
        problems.append('meta.json p2p must be {"command": "<existing-suite command>", "selection"?: ...}')
    elif "excluded" in p2p and p2p_excluded(meta) is None:
        problems.append('meta.json p2p.excluded must give every excluded existing test a justification: '
                        '[{"id": "<test id>", "why": "<why it may fail on a correct fix>"}] '
                        '(or {"<test id>": "<why>"})')
    if "alt_fixes" in meta:
        fixes = meta["alt_fixes"]
        paths = [_alt_fix_path(f) for f in fixes] if isinstance(fixes, list) else None
        if (paths is None or not MIN_ALT_FIXES <= len(paths) <= MAX_ALT_FIXES or None in paths
                or len(set(paths)) != len(paths) or GOLD_FIX in paths
                or any(not p.endswith(".patch") for p in paths)):
            problems.append(f"meta.json alt_fixes must list {MIN_ALT_FIXES}-{MAX_ALT_FIXES} distinct .patch files "
                            "under tests/ (e.g. \"alt_fix_1.patch\"), other than gold.patch")
    if "runtime_fix" in meta:
        problems += runtime_fix_problems(meta)
    for stale in ("symptom_site", "trigger_kind"):
        if stale in meta:
            problems.append(f"meta.json {stale} is no longer part of the contract; remove it")
    return problems


def _accept_list_problems(entries, label):
    if not isinstance(entries, list) or not entries:
        return [f"meta.json {label} must be a nonempty list of {{file, function}}"]
    return [f"meta.json {label} entry {entry!r} needs a relative file and a function name"
            for entry in entries
            if (not isinstance(entry, dict) or normalize_path(entry.get("file")) is None
                or normalize_function(entry.get("function")) is None)]


def root_cause_problems(meta):
    """Problems with meta.json's gold causes: `root_causes` [{"accept": [{file, function}, ...]}, ...]
    or the legacy `root_cause` accept-list (exactly one of the two)."""
    if "root_causes" in meta and "root_cause" in meta:
        return ["meta.json has both root_causes and the legacy root_cause; keep only root_causes"]
    if "root_causes" not in meta:
        return _accept_list_problems(meta.get("root_cause"), "root_cause")
    causes = meta["root_causes"]
    if not isinstance(causes, list) or not causes:
        return ['meta.json root_causes must be a nonempty list of {"accept": [{file, function}, ...]}, '
                "one per gold cause"]
    problems = []
    for number, cause in enumerate(causes, 1):
        if not isinstance(cause, dict) or "accept" not in cause:
            problems.append(f'meta.json root_causes[{number - 1}] must be {{"accept": [{{file, function}}, ...]}}')
            continue
        problems += _accept_list_problems(cause["accept"], f"root_causes[{number - 1}].accept")
    if not problems:
        for a in range(len(causes)):
            for b in range(a + 1, len(causes)):
                if any(site_matches(site, causes[b]["accept"]) for site in causes[a]["accept"]):
                    problems.append(f"meta.json root_causes[{a}] and root_causes[{b}] accept the same "
                                    "function; one answer entry would match two causes")
    return problems


def p2p_excluded(meta):
    """meta.json `p2p.excluded` as {test id: justification}; {} when absent; None when malformed.

    Existing tests that pin the buggy behaviour (they fail on gold) may be left out of the P2P gate,
    each with a justification of at least MIN_JUSTIFICATION characters. Two spellings:
    [{"id": "TestOctRing", "why": "asserts the open ring the fix closes"}] or {"TestOctRing": "..."}."""
    p2p = (meta or {}).get("p2p")
    excluded = p2p.get("excluded", []) if isinstance(p2p, dict) else []
    if isinstance(excluded, dict):
        pairs = list(excluded.items())
    elif isinstance(excluded, list) and all(isinstance(e, dict) for e in excluded):
        pairs = [(e.get("id"), e.get("why")) for e in excluded]
    else:
        return None
    if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str)
           or len(v.strip()) < MIN_JUSTIFICATION for k, v in pairs) or len({k for k, _ in pairs}) != len(pairs):
        return None
    return {k.strip(): v.strip() for k, v in pairs}


def meta_warnings(meta):
    """Non-blocking notes on a task's meta.json (used by `rca check`)."""
    warnings = []
    if isinstance(meta, dict) and not meta.get("alt_fixes"):
        warnings.append("tests/meta.json has no `alt_fixes`: R only compares buggy with gold, so a reproducer "
                        "that reads source text or pins gold internals earns R (argus-lite fails this); add "
                        "1-2 alternative correct fixes (docs/task-contract.md)")
    if isinstance(meta, dict) and "root_cause" in meta and "root_causes" not in meta:
        warnings.append('tests/meta.json uses the legacy `root_cause` accept-list (read as one cause); on the '
                        'next version write `"root_causes": [{"accept": [...]}]` (docs/task-contract.md)')
    return warnings


# --- R: the reproducer across several correct fixes ---------------------------------------------

def _alt_fix_path(value):
    """An alt_fixes entry as a path relative to tests/ (a leading `tests/` is dropped), or None."""
    path = normalize_path(value)
    if path is not None and path.startswith("tests/"):
        path = normalize_path(path[len("tests/"):])
    return path


def alt_fix_paths(meta):
    """meta.json `alt_fixes` as paths relative to tests/; [] when absent (legacy tasks)."""
    fixes = (meta or {}).get("alt_fixes") or []
    return [p for p in (_alt_fix_path(f) for f in fixes) if p is not None]


def reproducer_fixes(meta, tests_dir):
    """[(label, patch path)] of the correct fixes R runs the reproducer against: ("gold",
    tests/gold.patch) first, then ("alt_fix_1", ...), ("alt_fix_2", ...) in meta.json order. The
    labels are neutral: they appear in rollout feedback and must not describe the fix."""
    tests_dir = Path(tests_dir)
    fixes = [("gold", tests_dir / GOLD_FIX)]
    fixes += [(f"alt_fix_{i}", tests_dir / rel) for i, rel in enumerate(alt_fix_paths(meta), 1)]
    return fixes


RUNTIME_FIX_KINDS = ("pythonpath", "go-overlay", "none")
RUNTIME_FIX_LABEL = "runtime_fix"


def runtime_fix_spec(meta):
    """meta.json `runtime_fix` as {"kind", "path"} when it declares an active runtime fix; None when
    absent or `"kind": "none"` (legacy tasks, or a language without a runtime route)."""
    spec = (meta or {}).get("runtime_fix")
    if not isinstance(spec, dict) or spec.get("kind") in (None, "none"):
        return None
    return {"kind": spec.get("kind"), "path": normalize_path(spec.get("path"))}


def runtime_fix_problems(meta):
    """Problems with meta.json `runtime_fix` (absent is fine for legacy tasks)."""
    spec = (meta or {}).get("runtime_fix")
    if spec is None:
        return []
    if not isinstance(spec, dict) or spec.get("kind") not in RUNTIME_FIX_KINDS:
        return [f'meta.json runtime_fix must be {{"kind": one of {list(RUNTIME_FIX_KINDS)}, "path": "runtime_fix"}}']
    if spec["kind"] == "none":
        why = spec.get("why")
        return ([] if isinstance(why, str) and len(why.strip()) >= MIN_JUSTIFICATION else
                ['meta.json runtime_fix {"kind": "none"} needs a "why" explaining the missing runtime route'])
    path = normalize_path(spec.get("path"))
    if path is None or path.startswith("tests/"):
        return ['meta.json runtime_fix.path must be a directory relative to tests/, e.g. "runtime_fix"']
    return []


def reproducer_trees(meta, tests_dir):
    """[(label, kind, path)] of every correct-fix tree R runs the reproducer on, in order: the
    reproducer_fixes() patches (kind "patch"), then the runtime fix (kind "runtime", label
    "runtime_fix", path = its directory under tests/) when meta.json declares an active one."""
    trees = [(label, "patch", path) for label, path in reproducer_fixes(meta, tests_dir)]
    spec = runtime_fix_spec(meta)
    if spec is not None:
        trees.append((RUNTIME_FIX_LABEL, "runtime", Path(tests_dir) / (spec["path"] or "runtime_fix")))
    return trees


def crash_signal(code):
    """The signal name (e.g. "SIGSEGV") when a return code says the process was killed by a signal:
    a negative code (subprocess) or 128+N (a shell reporting its child's death); else None."""
    if type(code) is not int:
        return None
    number = -code if code < 0 else (code - 128 if 128 < code <= 128 + MAX_SIGNAL else 0)
    if number <= 0:
        return None
    try:
        return _signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


def crash_outcome(outcome, code, timed_out=False, signal_name=None):
    """`outcome` ({"outcome", "detail"}) re-labelled for a reproducer process killed by a signal
    (from its return code, or `signal_name` when a wrapper such as test2json reported it).

    Only an "error" becomes "crashed" (with "signal"), so the score never changes: a crashed tree
    fails its R row exactly as an error does. A "fail"/"pass" keeps its outcome and gains a note.
    The grader's own timeout kill is not a crash (timed_out=True)."""
    name = None if timed_out else (signal_name or crash_signal(code))
    if name is None:
        return outcome
    detail = str(outcome.get("detail") or "")
    if outcome.get("outcome") == "error":
        return {"outcome": "crashed", "signal": name,
                "detail": f"crashed: {name} (exit {code})" + (f"; {detail}" if detail else "")}
    return {**outcome, "detail": (f"{detail}; " if detail else "") + f"process then killed by {name}"}


def _outcome(value):
    """(outcome, detail, signal) from "fail" | "pass" | "error" | "crashed" | None or
    {"outcome", "detail"?, "signal"?}."""
    detail, name = "", None
    if isinstance(value, dict):
        value, detail, name = value.get("outcome"), str(value.get("detail") or ""), value.get("signal")
    if value is None:
        return None, detail, None
    if value not in REPRO_OUTCOMES:
        raise ValueError(f"reproducer outcome must be one of {sorted(REPRO_OUTCOMES)}, not {value!r}")
    if value == "crashed":
        name = str(name or "unknown signal")
    return value, detail, name if value == "crashed" else None


def _repro_row(row_id, expected, where, value):
    outcome, detail, name = _outcome(value)
    row = {"id": row_id, "component": "R",
           "status": "missing" if outcome is None else ("passed" if outcome == expected else "failed")}
    shown = f"crashed: {name}" if name else (outcome or "not run")
    row["detail"] = f"{where}: " + (detail if name and detail.startswith(shown)    # crash_outcome's own detail
                                    else shown + (f"; {detail}" if detail else ""))
    if name:
        row["crashed"] = name
    return row


_NOT_GIVEN = object()
REBUILT_ROW = "repro:fails_on_buggy_rebuilt"


def reproducer_checks(on_buggy, on_fixes, meta=None, on_rebuilt=_NOT_GIVEN):
    """The R rows for reward_writer.write_rewards.

    on_buggy  the reproducer's outcome on the clean buggy tree
    on_rebuilt  its outcome on the same buggy code rebuilt with a behaviour-neutral change
              (perturb_sources plus the grader's alternative build setting): it must fail there
              too, so a test that only recognises the exact buggy build scores R = 0. Every
              format-1 grader passes it (None: not run, the row reads "missing"); a caller that
              omits it (legacy graders) gets no such row.
    on_fixes  [(label, outcome)] on buggy + each correct fix, labels as reproducer_fixes() gives them
    outcome   "fail"  it ran and at least one of its tests failed (a test failure, not a build error)
              "pass"  it ran, at least one test passed and none failed
              "error" build failure, timeout, or no test ran;  None: not run (counts as missing)
              "crashed" the process was killed by a signal (crash_outcome; scores like "error")
              or {"outcome": ..., "detail": "...", "signal"?: "SIGSEGV"}

    R = 1 iff it fails on buggy (and on the rebuilt buggy code) and passes with every correct fix.
    When meta is given, on_fixes
    must cover exactly reproducer_trees(meta): gold, each alt fix and, when meta.json declares one,
    the verifier-owned runtime fix (label "runtime_fix"). A grader that skips one raises (a missing
    check is never a pass). A crashed row is "failed" with `"crashed": "<SIGNAME>"`."""
    labels = [label for label, _ in on_fixes]
    if meta is not None:
        expected = [label for label, _, _ in reproducer_trees(meta, ".")]
        if labels != expected:
            raise ValueError(f"reproducer outcomes cover {labels}, expected {expected}")
    if not labels or labels[0] != "gold" or len(set(labels)) != len(labels):
        raise ValueError("on_fixes must start with the gold fix and have distinct labels")
    rows = [_repro_row("repro:fails_on_buggy", "fail", "on buggy", on_buggy)]
    if on_rebuilt is not _NOT_GIVEN:
        rows.append(_repro_row(REBUILT_ROW, "fail", "on buggy, rebuilt with a behaviour-neutral change", on_rebuilt))
    rows += [_repro_row(f"repro:passes_with_{label}", "pass", f"with correct fix {label}", value)
             for label, value in on_fixes]
    return rows


def perturb_sources(root, suffixes, comment, skip=lambda rel: False):
    """Append one comment line (`comment`, e.g. "#" or "//") to every regular file under `root`
    whose name ends in one of `suffixes` and that `skip(rel)` does not exclude (the grader skips
    the agent's test files and the test paths). The behaviour of the code is unchanged; every
    file's bytes, size and hash are not. Appending (never prepending) keeps every line number.
    Returns the number of files changed."""
    root, count = Path(root), 0
    tail = ("\n" + comment + "\n").encode()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if not name.endswith(tuple(suffixes)) or path.is_symlink() or not path.is_file() or skip(rel):
                continue
            with open(path, "ab") as stream:
                stream.write(tail)
            count += 1
    return count


def reproducer_missing(detail="no reproducer at the path rca.json names"):
    """The single R row when no reproducer can run (R = 0)."""
    return [{"id": "repro:present", "component": "R", "status": "missing", "detail": str(detail)[:300]}]


# =================================================================================================
# Format-1 verifier toolkit (docs/task-format.md). Stdlib only; used by templates/grade_python.py
# and templates/grade_go.py (copied to tests/grade.py) and by `rca check`/`rca regen`. Nothing
# below imports or executes candidate code in the calling process: candidate code only ever runs
# in a Sandbox child, demoted to the agent's uid.
# =================================================================================================

import hashlib
import math
import os
import shutil
import signal
import subprocess
import tempfile
import time

TREE_ALGORITHM = "spec-drift-tree-v1"
MANIFEST_FORMAT, MANIFEST_VERSION = "rca-task", 1
SHA_HEX = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
# Paths in the agent's /workdir that are never part of a fix: the answer, the git history and the
# task material the agent was given (REPORT.md only exists in legacy tasks; evidence/ is optional).
NOT_A_CHANGE_TOP = {"rca.json", "REPORT.md", "evidence", ".git"}
# The task's own evidence: environment/evidence/ lands at /workdir/<EVIDENCE_DIR>/ in the agent
# image, and `rca regen` mirrors it byte for byte into tests/<EVIDENCE_DIR>/ (root-only in the
# verifier). Reproducer trees get that pristine copy (task_evidence), never the agent's.
EVIDENCE_DIR = "evidence"
# THE build-output definition of trees.solver, shared with `rca regen` (scripts/rca_format.py
# imports is_fingerprint_build_output from this file): exactly what the agent image's normalization
# step deletes (docs/task-format.md "Workspace and normalization"), plus the *.egg-info an editable
# install writes. Cache names go at any depth; build/ and target/ only at the top of the tree
# (toolchain install output). A deeper directory with that name is project content (octodns
# docs/examples/basic/target/) and stays in the solver view, the fingerprint and every graded tree.
CACHE_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".coverage", "htmlcov"})
TOP_LEVEL_BUILD_DIRS = frozenset({"build", "target"})
# Snapshot only: more tool caches the agent may create, ignored unless the pristine tree has the path.
SNAPSHOT_ONLY_PARTS = frozenset({".hypothesis", ".tox", ".nox", ".eggs", ".git"})
BUILD_OUTPUT_SUFFIXES = (".pyc", ".pyo", ".egg-info")


def is_fingerprint_build_output(rel):
    """True for a tree-relative path (file or directory) the solver view excludes as a build output."""
    parts = str(rel).split("/")
    return parts[0] in TOP_LEVEL_BUILD_DIRS or any(p in CACHE_NAMES or p.endswith(".egg-info") for p in parts)


# --- tree fingerprint (spec-drift-tree-v1, adopted verbatim) ------------------------------------

def tree_manifest(root, skip=None):
    """{posix path: value} for a tree: a regular file's value is its SHA-256 plus ":executable"
    (any execute bit) or ":file"; a symlink's is "link:" + its target text. `.git` (any case, any
    depth) is ignored; directories and other mode bits do not count. `skip(rel)` drops more paths
    (a skipped directory drops everything under it). Special files raise ValueError."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"tree root must be a directory, not a symlink: {root}")
    result = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(root)
        keep_dirs = []
        for name in sorted(dirnames):
            rel = (rel_dir / name).as_posix()
            if name.casefold() == ".git" or (skip and skip(rel)):
                continue
            if (here / name).is_symlink():
                result[rel] = "link:" + os.readlink(here / name)
                continue
            keep_dirs.append(name)
        dirnames[:] = keep_dirs
        for name in sorted(filenames):
            path, rel = here / name, (rel_dir / name).as_posix()
            if skip and skip(rel):
                continue
            st = path.lstat()
            if path.is_symlink():
                result[rel] = "link:" + os.readlink(path)
            elif path.is_file():
                result[rel] = _sha256_file(path) + (":executable" if st.st_mode & 0o111 else ":file")
            else:
                raise ValueError(f"tree contains a special file: {rel}")
    return result


def tree_digest(manifest):
    """SHA-256 of UTF-8 json.dumps(manifest, sort_keys=True)."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def tree_fingerprint(root, skip=None):
    """spec-drift-tree-v1 digest of a tree."""
    return tree_digest(tree_manifest(root, skip))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# --- omit_tests: gitwildmatch globs with literal keep-exceptions ---------------------------------

def _class_end(body, start):
    j = start + 1
    if j < len(body) and body[j] in "!^":
        j += 1
    if j < len(body) and body[j] == "]":
        j += 1
    end = body.find("]", j)
    return None if end < 0 else end


def _glob_regex(pattern):
    """Regex for one gitwildmatch pattern (trailing "/" already removed), the same semantics as
    `rca regen` (scripts/rca_format.py glob_regex): a pattern with a leading or inner "/" is
    anchored at the repository root, otherwise it matches at any depth; `**/`, a trailing `/**`
    cross directories; `*`, `?` and `[...]` never match "/"; `\\x` escapes; no negation."""
    anchored = pattern.startswith("/") or "/" in pattern
    body, out, i = pattern.lstrip("/"), [], 0
    while i < len(body):
        at_start = i == 0 or body[i - 1] == "/"
        if body.startswith("**/", i) and at_start:
            out.append("(?:.*/)?")
            i += 3
            continue
        if body.startswith("**", i) and at_start and i + 2 == len(body):
            out.append(".*")
            i += 2
            continue
        char = body[i]
        if char == "*":
            while i + 1 < len(body) and body[i + 1] == "*":
                i += 1
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[" and _class_end(body, i) is not None:
            end = _class_end(body, i)
            inner = body[i + 1:end]
            if inner[:1] in ("!", "^"):
                inner = "^" + inner[1:]
            out.append("[" + inner.replace("\\", "\\\\") + "]")
            i = end
        elif char == "\\" and i + 1 < len(body):
            out.append(re.escape(body[i + 1]))
            i += 1
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile(("" if anchored else "(?:.*/)?") + "".join(out) + r"\Z")


class OmitRules:
    """The manifest's omit_tests: which repo paths are removed from the agent's view.

    `matches(path)` is the raw glob match (a path matches when it or any ancestor directory
    matches a pattern; a trailing "/" restricts a pattern to directories). `omitted(path)` honours
    the literal `keep` paths (a kept directory keeps everything under it)."""

    def __init__(self, globs=(), keep=()):
        self.patterns = []
        for glob in globs or ():
            if not isinstance(glob, str) or not glob.strip("/"):
                raise ValueError(f"bad omit_tests glob: {glob!r}")
            self.patterns.append((_glob_regex(glob.rstrip("/")), glob.endswith("/")))
        self.keep = [k.strip("/") for k in keep or () if isinstance(k, str) and k.strip("/")]

    @classmethod
    def from_manifest(cls, manifest):
        omit = (manifest or {}).get("omit_tests") or {}
        return cls(omit.get("globs") or (), omit.get("keep") or ())

    def matches(self, path):
        parts = str(path).split("/")
        for regex, dir_only in self.patterns:
            if not dir_only and regex.match("/".join(parts)):
                return True
            if any(regex.match("/".join(parts[:k])) for k in range(1, len(parts))):
                return True
        return False

    def kept(self, path):
        path = str(path)
        return any(path == k or path.startswith(k + "/") for k in self.keep)

    def omitted(self, path):
        return self.matches(path) and not self.kept(path)


def solver_view_skip(rules):
    """skip() for tree_manifest/prune_tree that yields the solver view: the pristine tree minus
    omit_tests (keep honoured) minus the build outputs the agent image's normalization step
    deletes (is_fingerprint_build_output) -- the definition of trees.solver."""
    return lambda rel: is_fingerprint_build_output(rel) or (
        rules.omitted(rel) and not any(k.startswith(rel + "/") for k in rules.keep))


# --- manifest and format-1 meta.json --------------------------------------------------------------

def manifest_problems(manifest):
    """Schema problems with rca-task.json that a grader cannot work around."""
    if not isinstance(manifest, dict):
        return ["rca-task.json must be an object"]
    problems = []
    if manifest.get("format") != MANIFEST_FORMAT or manifest.get("version") != MANIFEST_VERSION:
        problems.append(f'rca-task.json must declare "format": "{MANIFEST_FORMAT}", "version": {MANIFEST_VERSION}')
    source = manifest.get("source") or {}
    if not isinstance(source.get("commit"), str) or not SHA_HEX.match(source["commit"]):
        problems.append("rca-task.json source.commit must be a full 40/64-hex commit")
    trees = manifest.get("trees") or {}
    if trees.get("algorithm") != TREE_ALGORITHM:
        problems.append(f"rca-task.json trees.algorithm must be {TREE_ALGORITHM}")
    for name in ("pristine", "solver"):
        value = trees.get(name)
        if not isinstance(value, str) or not re.match(r"^[0-9a-f]{64}$", value) or set(value) == {"0"}:
            problems.append(f"rca-task.json trees.{name} must be a generated SHA-256 fingerprint")
    try:
        OmitRules.from_manifest(manifest)
    except ValueError as error:
        problems.append(f"rca-task.json omit_tests: {error}")
    return problems


def format_problems(meta, manifest, tests_dir):
    """Problems with the grading inputs of a format-1 task beyond meta_problems(): every fix probe,
    alt fix and runtime fix exists under tests/, and the manifest is usable."""
    tests_dir = Path(tests_dir)
    problems = manifest_problems(manifest)
    for probe in (meta or {}).get("fix_tests") or []:
        path = normalize_path(probe)
        if path is None or not (tests_dir / path).is_file() or (tests_dir / path).is_symlink():
            problems.append(f"meta.json fix_tests entry {probe!r} is not a regular file under tests/")
    for label, kind, path in reproducer_trees(meta, tests_dir):
        ok = path.is_dir() if kind == "runtime" else path.is_file()
        if not ok or path.is_symlink():
            problems.append(f"{label}: {path.relative_to(tests_dir) if path.is_relative_to(tests_dir) else path} is missing")
    if "runtime_fix" not in (meta or {}):
        problems.append('meta.json runtime_fix is required in format 1 ({"kind": "none", "why": ...} when no route exists)')
    declared = isinstance(manifest, dict) and bool((manifest.get("workspace") or {}).get("evidence"))
    mirrored = bool(_evidence_files(tests_dir))
    if declared and not mirrored:
        problems.append(f"rca-task.json workspace.evidence is declared but tests/{EVIDENCE_DIR}/ (the byte mirror of "
                        "environment/evidence/ that reproducer trees get) is missing or empty; run `rca regen`")
    elif mirrored and not declared:
        problems.append(f"tests/{EVIDENCE_DIR}/ exists but rca-task.json declares no workspace.evidence; run `rca regen`")
    return problems


def _evidence_files(tests_dir):
    """{rel: path} of the regular files under tests/<EVIDENCE_DIR>/ (symlinks never count)."""
    base = Path(tests_dir) / EVIDENCE_DIR
    if not base.is_dir() or base.is_symlink():
        return {}
    return {path.relative_to(base).as_posix(): path for path in sorted(base.rglob("*"))
            if path.is_file() and not path.is_symlink()}


def task_evidence(manifest, tests_dir):
    """{workdir rel: source} of the task's own evidence for the reproducer trees: the pristine copy
    the agent was given (tests/<EVIDENCE_DIR>/, the byte mirror of environment/evidence/), at the
    path the agent saw it (/workdir/<workspace.evidence>/...). The ask lets a regression test read
    /workdir/evidence, so every reproducer tree has it; the agent's own copy (possibly edited,
    extended or deleted) never reaches a tree, so it carries no agent-written marker. {} when the
    task ships no evidence."""
    folder = (manifest.get("workspace") or {}).get("evidence") if isinstance(manifest, dict) else None
    if not folder:
        return {}
    folder = str(folder).strip("/")
    return {f"{folder}/{rel}": path for rel, path in _evidence_files(tests_dir).items()}


# --- the agent's /workdir as untrusted data -------------------------------------------------------

def is_build_output(rel):
    """A build output or cache in the agent's snapshot: the solver-view definition plus more tool
    caches and compiled files (classify_changes ignores them unless the pristine tree has the path)."""
    parts = str(rel).split("/")
    return (is_fingerprint_build_output(rel) or any(p in SNAPSHOT_ONLY_PARTS for p in parts)
            or parts[-1].endswith(BUILD_OUTPUT_SUFFIXES))


def snapshot_tree(src, dest, *, max_file=10 * 1024 * 1024, max_total=512 * 1024 * 1024):
    """Copy the regular files of an untrusted tree into `dest` (which must not exist), never
    following symlinks. Returns {"files": {rel: copied path}, "present": set of every rel path seen
    (symlinks, special and oversized files included, so they never read as deletions), "skipped":
    {reason: count}}. Modes are normalised to 0644/0755 (execute bit kept)."""
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True)
    os.chmod(dest, 0o700)
    files, present, skipped, total = {}, set(), {}, 0
    if src.is_symlink() or not src.is_dir():
        return {"files": files, "present": present, "skipped": {"workdir_not_a_directory": 1}}
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(src)
        walk_dirs = []
        for name in sorted(dirnames):
            rel = (rel_dir / name).as_posix()
            if (here / name).is_symlink():
                present.add(rel)
            elif rel != ".git":
                walk_dirs.append(name)
        dirnames[:] = walk_dirs
        for name in sorted(filenames):
            path, rel = here / name, (rel_dir / name).as_posix()
            present.add(rel)
            try:
                st = path.lstat()
            except OSError:
                skipped["unreadable"] = skipped.get("unreadable", 0) + 1
                continue
            if not os.path.isfile(path) or path.is_symlink():
                skipped["not_regular"] = skipped.get("not_regular", 0) + 1
                continue
            if st.st_size > max_file or total + st.st_size > max_total:
                skipped["too_large"] = skipped.get("too_large", 0) + 1
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as stream, open(target, "wb") as out:
                    shutil.copyfileobj(stream, out)
            except OSError:
                skipped["unreadable"] = skipped.get("unreadable", 0) + 1
                continue
            os.chmod(target, 0o755 if st.st_mode & 0o111 else 0o644)
            total += st.st_size
            files[rel] = target
    return {"files": files, "present": present, "skipped": skipped}


def _same_file(a, b):
    try:
        sa, sb = os.lstat(a), os.lstat(b)
    except OSError:
        return False
    if sa.st_size != sb.st_size or bool(sa.st_mode & 0o111) != bool(sb.st_mode & 0o111):
        return False
    return _sha256_file(a) == _sha256_file(b)


# Runner-control files: they steer the interpreter or the test runner rather than the code under
# test, so a change to one is never part of a fix (mashumaro v1 Reward Hack Post-Eval: a fix could
# add a file Python loads at startup, or a pytest plugin through the runner's config, and rewrite
# the suite's report). Outside the test paths, classify_changes puts an added, changed or deleted
# one in its own "runner" bucket, which no graded tree receives, and the grader reports it.
STARTUP_FILES = frozenset({"sitecustomize.py", "usercustomize.py"})      # plus any *.pth
PYTEST_CONFIG_FILES = frozenset({"pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml"})
# Installed-package metadata: an entry_points.txt under a *.dist-info (or *.egg-info) directory on
# the import path registers a pytest11 plugin that pytest loads (aiogram-nullfield-v2 Argus Main).
PACKAGE_METADATA_SUFFIXES = (".dist-info", ".egg-info")
# Shared config files: only their pytest part is runner control. A changed file whose pytest
# settings differ from the pristine file's is kept pristine as a whole (never spliced).
PYTEST_SECTION_FILES = {"pyproject.toml": "toml", "setup.cfg": "ini", "tox.ini": "ini"}


def _pytest_settings(path, kind):
    """The pytest settings of a pyproject.toml ([tool.pytest] with every subtable) or an ini file
    ([pytest], [tool:pytest]); None when the file or the section is absent. Raises ValueError when
    the file cannot be read or parsed (the caller then treats the file as runner control)."""
    if path is None:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(str(error)) from None
    if kind == "toml":
        try:
            import tomllib
        except ImportError:                       # Python < 3.11: no parser, so no partial credit
            raise ValueError("tomllib unavailable") from None
        # safe_parse: a TOML file nested thousands deep raises RecursionError in tomllib.
        parsed = safe_parse(tomllib.loads, text, errors=(tomllib.TOMLDecodeError,))
        tool = parsed.get("tool") or {}
        if not isinstance(tool, dict):
            raise ValueError("[tool] is not a table")
        return tool.get("pytest")
    import configparser
    parser = configparser.RawConfigParser(strict=False)
    try:
        parser.read_string(text)
    except configparser.Error as error:
        raise ValueError(str(error)) from None
    found = {name: dict(parser.items(name)) for name in ("pytest", "tool:pytest") if parser.has_section(name)}
    return found or None


def runner_control_reason(rel, path=None, pristine_path=None):
    """Why the candidate's version of `rel` (its file at `path`, None when deleted) is runner
    control rather than part of a fix, or None. `pristine_path` is the pristine file (None when the
    candidate added it)."""
    name = str(