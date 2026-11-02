#!/usr/bin/env python3
"""Grade a fault chain task.

Two halves, neither of which needs a model.

  repair   the target test passes and nothing else broke
  report   /app/rca.json names each edited file and function, and each site it names
           shows evidence that the behaviour that edit took away has come back

The answer key is written when the task is built, from the record of what was injected,
so grading is a comparison rather than a judgment.
"""

from __future__ import annotations

import ast
import copy
import json
import shutil
import tarfile
import math
import os
import hashlib
import pwd
import random
import re
import secrets
import shlex
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# The grader runs as root, and environment/Dockerfile puts the agent-owned /opt/venv/bin
# first on PATH. Every bare binary this process resolves - setpriv (which run() uses to
# DROP to the agent, so it is located while still root), git, tar, rm - would otherwise
# come from a directory the agent owns and could have planted a binary in, and would run as
# root before any privilege drop. Pin a trusted PATH of the base image's real tools, which
# are never chowned to the agent, before any subprocess starts. The repository's own suite
# still gets the venv: run() executes it through `bash -lc`, a login shell that re-sources
# the root-owned /etc/profile.d and re-prepends /opt/venv/bin for the agent command.
os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin"

# The Go-suite helpers, spliced in from pipeline/gotest.py so the verifier needs nothing
# beyond the standard library: node ids, `go test -json` events, function spans.

import json
import re
import shlex
from dataclasses import dataclass, field

#: The store's node id for a package whose test binary never built or set up.
PACKAGE_SENTINEL = "<package>"

_COUNT1 = re.compile(r"(?<!\S)-count=\d+(?!\S)")


def base(node_id: str) -> str:
    """The top-level test name of a node id: the unit `go test -skip` can address.
    `pkg::TestErrors/String/empty` -> `TestErrors`, the way `b.split("[")[0]` reduces a
    parametrised pytest id to the function that owns it. A bare `TestX/sub` (no `::`)
    is taken as the test part. The cut is the FIRST `::`: an import path holds no
    colon, and a subtest's name (t.Run) may."""
    name = node_id.split("::", 1)[-1]
    return name.split("/", 1)[0]


def top(node: str) -> str:
    """The top-level test's own node id: `pkg::TestErrors/String` -> `pkg::TestErrors`.
    A run's size is counted in these rather than in bare names, so a TestSame in two
    packages is two tests and a package that stopped reporting it is missed."""
    package, sep, _ = node.partition("::")
    return (package + sep if sep else "") + base(node)


def ensure_count1(cmd: str) -> str:
    """`go test` with `-count=1` right after the verb, so go's result cache never answers
    for a tree that differs by one line. A command that already sets -count (any N,
    all of which bypass the cache) and any non-`go test` command return unchanged."""
    if not is_go_test(cmd) or _COUNT1.search(cmd):
        return cmd
    return "go test -count=1" + cmd[len("go test"):]


def is_go_test(cmd: str) -> bool:
    """Is this a `go test` invocation (the verb, not a prefix of another word)?"""
    return cmd == "go test" or cmd.startswith("go test ")


#: What makes a Go tree ungradable, as `go test` prints it without -json: a package
#: whose test binary never built or never set up, or a test binary that panicked (which
#: kills every remaining test in that package). Plain `--- FAIL` lines are failures,
#: and failures are what faults are for. A `panic: ` line counts only when the
#: runtime's goroutine trace follows it: a test that merely logs the word is not a
#: crash.
BUILD_FAILED = re.compile(r"^FAIL\s+\S+\s+\[(?:build|setup) failed\]", re.M)
#: Anywhere on its line: testing prints the panic it recovered once more, INDENTED,
#: before the trace, and a test that printed without a newline leaves its text in front
#: (pterm: "bpanic: ..."). What makes it a crash is the trace on the lines after it,
#: not the column; a log line that merely says "panic:" has no trace.
PANIC = re.compile(r"panic: ")
TRACE = re.compile(r"^goroutine \d+ \[running\]:")
#: How many lines before a trace the panic line that names it can sit: the runtime
#: prints the panic, a blank line, the trace; a recovered-and-rethrown one indents the
#: panic once more in between.
TRACE_CONTEXT = 3
#: The build failures and the trace lines as POSIX grep -E spells them, for grepping a
#: suite log INSIDE a container (GNU grep has no `(?:` and no `\s`; the python regex
#: above would be an error there, and a grep that errors finds nothing — the check would
#: be blind). The panic line is not matched: it arrives as context before its trace
#: (ERROR_GREP's -B, a GNU and BusyBox option), so a log line that says "panic:"
#: elsewhere never lands beside a stack dump in the excerpt, and a chatty recover-path
#: suite cannot fill the excerpt's cap before its real crash.
ERROR_LINE_ERE = (r"^FAIL[[:space:]]+[^[:space:]]+[[:space:]]+\[(build|setup) failed\]"
                  r"|^goroutine [0-9]+ \[running\]:")
ERROR_GREP = f"grep -E -B{TRACE_CONTEXT} {shlex.quote(ERROR_LINE_ERE)}"


def errors(output: str) -> int:
    """The count of error lines in `go test` output — the analog of pytest's
    `N errors` summary count that collectcheck disqualifies a composed tree on."""
    lines = output.splitlines()
    # The crash is the trace; the panic line within the few lines before it is what
    # names it. Counting traces reads the recovered-and-rethrown pair (two panic lines,
    # one trace) as one crash, and a run of log lines that say "panic:" as none.
    crashes = sum(1 for i, line in enumerate(lines)
                  if TRACE.match(line)
                  and any(PANIC.search(l) for l in lines[max(0, i - TRACE_CONTEXT):i]))
    return len(BUILD_FAILED.findall(output)) + crashes


def node_id(package: str, test: str) -> str:
    """`<import path>::<TestName>/<subtest>` — the artifact store's own spelling."""
    return f"{package}::{test}"


_NODE_ID = re.compile(r"^[^:\s]+::\S+$")


def is_node_id(text: str) -> bool:
    """Does this look like a Go node id (an import path, `::`, a test path)? A pytest
    id has a `.py` file before its `::`; a bare `TestX` has no `::` at all."""
    return bool(_NODE_ID.match(text)) and not text.split("::", 1)[0].endswith(".py")


@dataclass
class GoRun:
    """One `go test -json` run, sorted into node id sets. `package_failed` holds the
    `pkg::<package>` sentinel for every package that failed without a single test
    verdict — a build or setup failure, not a failing test."""
    passed: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    skipped: set[str] = field(default_factory=set)
    package_failed: set[str] = field(default_factory=set)
    #: Every test that answered, parents included. `failed` keeps only leaves (a parent
    #: red through a subtest is the same failure), so the SIZE of a run is read here:
    #: the pristine baseline counts a passing parent, and a faulted run must count the
    #: same parent when it fails through a child, or it reads as smaller than the
    #: baseline (miniflux: 7 such parents, 2046 of 2053, every Go task refused).
    reported: set[str] = field(default_factory=set)


def size(run: GoRun) -> int:
    """How many tests a run is: its top-level `func Test`s with a verdict. A subtest
    count is the code under test's to change — btcd: one fault stopped TestRBF before
    its table, and the faulted tree reported 502 of the baseline's 510 — so it cannot
    be what the baseline is compared against. Parents count whatever their children did
    (miniflux: 7 parents red only via subtests), and each package's own."""
    return len({top(node) for node in run.reported})


def parse_events(text: str) -> GoRun:
    """Sort a `go test -json` event stream into node id sets. Lines that are not JSON
    events (compiler output, a truncated tail) are ignored; an empty stream is an empty
    run, never an error — the caller decides what an empty run means."""
    run = GoRun()
    verdicts_in: set[str] = set()   # packages that reported at least one test verdict
    failed_packages: set[str] = set()
    panicked: set[str] = set()      # the test binary died: every sibling verdict is lost
    panic_seen: set[str] = set()    # a `panic: ` line, waiting for the runtime's trace
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        action, package, test = event.get("Action"), event.get("Package"), event.get("Test")
        if not package:
            continue
        if action == "output":
            text = str(event.get("Output", ""))
            if PANIC.search(text):
                panic_seen.add(package)
            elif TRACE.match(text) and package in panic_seen:
                panicked.add(package)        # the real thing: the runtime's trace follows
            elif text.strip():
                panic_seen.discard(package)  # anything else in between: just a log line
        elif test:
            bucket = {"pass": run.passed, "fail": run.failed, "skip": run.skipped}.get(action)
            if bucket is not None:
                bucket.add(node_id(package, test))
                run.reported.add(node_id(package, test))
                verdicts_in.add(package)
        elif action == "fail":
            failed_packages.add(package)
    # A parent that fails only because a subtest did is the same break, not a second
    # one: keep the leaves, the way pytest reports parametrisations.
    run.failed = set(leaves(run.failed))
    run.package_failed = {node_id(p, PACKAGE_SENTINEL)
                          for p in (failed_packages - verdicts_in) | panicked}
    return run


def skip_regex(node_ids: list[str] | set[str]) -> str:
    """The `go test -skip` regex hiding these tests: their top-level names, escaped,
    sorted, anchored. `-skip` splits its pattern on `/` per subtest level, so one
    alternation of parents is the only shape that cannot under-match; the price is
    that a hidden subtest hides its whole parent, and a name hidden in one package is
    hidden in every package the run covers (safe_deselect keeps fault breaks out)."""
    return _alternation({base(n) for n in node_ids})


def _alternation(names: set[str]) -> str:
    """`^(A|B)$` over sorted, escaped names — the shape -run and -skip take; empty for none."""
    if not names:
        return ""
    return "^(" + "|".join(re.escape(n) for n in sorted(names)) + ")$"


_MODULE = re.compile(r"^module\s+(\S+)\s*$", re.M)


def module_path(go_mod_text: str) -> str | None:
    """The `module` directive of a go.mod: the import-path prefix every coverprofile and
    node id carries in front of the repo-relative path."""
    m = _MODULE.search(go_mod_text)
    return m.group(1) if m else None


_BLOCK = re.compile(r"^(\S+?):(\d+)\.\d+,(\d+)\.\d+ (\d+) (\d+)$")


def _blocks(text: str) -> list[tuple[str, int, int, int, int]] | None:
    """(file, start line, end line, statements, count) per coverprofile record, or
    None when the text is not a coverprofile (no `mode:` header)."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("mode: "):
        return None
    out = []
    for line in lines[1:]:
        m = _BLOCK.match(line.strip())
        if m:
            out.append((m.group(1), int(m.group(2)), int(m.group(3)),
                        int(m.group(4)), int(m.group(5))))
    return out


def parse_coverprofile(text: str, module: str) -> dict[str, set[int]] | None:
    """{repo-relative path: the lines a test executed} from `go test -coverprofile`
    output — the shape coverage-guided mining wants (parse_coverage_map's contract).
    Files outside `module`, and files nothing executed, are dropped; a text that is not
    a profile is None so the caller falls back to unguided mining."""
    blocks = _blocks(text)
    if blocks is None:
        return None
    prefix = module.rstrip("/") + "/"
    out: dict[str, set[int]] = {}
    for file, start, end, _stmts, count in blocks:
        if count > 0 and file.startswith(prefix):
            out.setdefault(file[len(prefix):], set()).update(range(start, end + 1))
    return out


def coverprofile_totals(text: str) -> tuple[int, int] | None:
    """(statements executed, statements total), each block counted once even when the
    profile repeats it (atomic mode from several packages covering one file)."""
    blocks = _blocks(text)
    if blocks is None:
        return None
    by_block: dict[tuple[str, int, int], tuple[int, bool]] = {}
    for file, start, end, stmts, count in blocks:
        key = (file, start, end)
        seen_stmts, seen_hit = by_block.get(key, (stmts, False))
        by_block[key] = (seen_stmts, seen_hit or count > 0)
    covered = sum(n for n, hit in by_block.values() if hit)
    return covered, sum(n for n, _ in by_block.values())


def outcomes(text: str) -> dict[str, bool]:
    """Every test one `go test -json` run answered for, and whether it passed — the
    shape the grader's per-site attribution reads (junit_outcomes for pytest). A skip is
    left out rather than called passed, and a parent red only through a child is not a
    verdict of its own."""
    run = parse_events(text)
    return {**{n: True for n in run.passed}, **{n: False for n in run.failed}}


#: Strings first, so a `//` or `/*` inside one is never read as a comment; the
#: comment alternatives are what gets dropped or blanked.
_STRING_OR_COMMENT = re.compile(
    r'("(?:\\.|[^"\\\n])*"|`[^`]*`|\'(?:\\.|[^\'\\\n])*\')|//[^\n]*|/\*.*?\*/', re.S)


def _masked(source: str) -> str:
    """The source with every string literal and comment blanked to spaces, newlines
    kept, so offsets and line numbers still line up: the text a brace count or a
    `func` search can trust."""
    return _STRING_OR_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)


#: A gofmt-formatted top-level function or method header, on masked text: `func` at
#: column 0, an optional `(receiver)`, the name. Type parameters after the name are
#: left to the brace scan; a receiver's own generics sit inside its parentheses.
_FUNC_HEAD = re.compile(r"^func (?:\(([^)]*)\) )?(\w+)")


_TYPE_BRACE = re.compile(r"(?:struct|interface)\s*$")


def _body_brace(masked: str, start: int) -> int:
    """The offset of the brace that opens a function's body, searching from the end
    of its name: past the parameter and result lists (which may span lines and hold
    brackets), and past a `struct{...}`/`interface{...}` in a result type, which is a
    type's brace and not the body's. -1 when the declaration has no body, or the
    signature runs into another top-level declaration."""
    depth = 0
    pos = start
    while pos < len(masked):
        ch = masked[pos]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "{":
            if depth == 0 and not _TYPE_BRACE.search(masked[max(0, pos - 12):pos]):
                return pos
            depth += 1                      # a type's brace: balance it like a bracket
        elif ch == "}":
            depth -= 1
        elif ch == "\n" and depth == 0 and masked.startswith(("func ", "type ", "var ",
                                                                "const ", "import "), pos + 1):
            return -1
        pos += 1
    return -1


#: Comments and raw strings blanked, interpreted strings kept: the text an import
#: declaration can be read from (its path IS an interpreted string).
_COMMENT_OR_RAW = re.compile(r'("(?:\\.|[^"\\\n])*")|`[^`]*`|//[^\n]*|/\*.*?\*/', re.S)
_IMPORT_BLOCK = re.compile(r"^import\s*(\([^)]*\)|[^\n;]*)", re.M)
#: One import spec naming the package, terminated the way Go allows: a newline, the
#: group's `)`, the end, or an explicit `;` (legal, though gofmt never writes one).
_TESTING_SPEC = re.compile(r'(?:^|[\n(;])\s*(?:(\.|\w+)\s+)?"testing"\s*(?=[\n;)]|$)')


def go_testing_identifier(source: str) -> str | None:
    """How this file refers to the testing package: `testing`, an alias, or `.` for a
    dot import; None when it does not import it or imports it blank. Read off the
    import declarations of the comment-and-raw-string-masked source, so a `t "testing"`
    quoted in a comment or a fixture is never taken for the import."""
    masked = _COMMENT_OR_RAW.sub(lambda m: m.group(1) or re.sub(r"[^\n]", " ", m.group(0)),
                                 source)
    for block in _IMPORT_BLOCK.finditer(masked):
        # Every spec, not the first: Go lets a file import one package twice under
        # different names, and a blank import before a bound one hides nothing.
        for m in _TESTING_SPEC.finditer(block.group(1)):
            name = m.group(1) or "testing"
            if name != "_":
                return name
    return None


#: The type name at the end of a receiver, whatever else is spelled around it: an
#: optional type-argument list and a closing parenthesis after it; the variable, the
#: pointer star and the opening parenthesis fall before it.
_RECEIVER_TYPE = re.compile(r"(\w+)\s*(?:\[.*\])?\s*\)?\s*$")


def receiver_type(receiver: str) -> str:
    """`p *Parser[K, V]`, `(p *Parser[T])`, `(*Parser[T])`, `Parser[T]` -> `Parser`: the
    bare type name, the way the answer key seats a method. Read from a declaration's
    receiver and from a report claim's receiver alike."""
    m = _RECEIVER_TYPE.search(receiver)
    return m.group(1) if m else receiver.strip()


def go_functions(source: str) -> list[tuple[str, int, int]]:
    """(qualname, first line, last line) for every top-level function, in file order.
    Found on the masked source, so a `func` or a brace inside a string or a comment is
    text, and the end is where the braces balance rather than the first `}` at column
    0. Qualname is `Recv.Name` (pointer stripped) or `Name`, the spelling mutate_go
    records and the answer key carries."""
    masked = _masked(source)
    lines = masked.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    out: list[tuple[str, int, int]] = []
    for i, line in enumerate(lines):
        m = _FUNC_HEAD.match(line)
        if not m:
            continue
        qual = f"{receiver_type(m.group(1))}.{m.group(2)}" if m.group(1) else m.group(2)
        open_at = _body_brace(masked, starts[i] + m.end())
        if open_at < 0:
            continue                       # a declaration without a body (assembly stub)
        depth = 0
        for pos in range(open_at, len(masked)):
            if masked[pos] == "{":
                depth += 1
            elif masked[pos] == "}":
                depth -= 1
                if depth == 0:
                    out.append((qual, i + 1, masked.count("\n", 0, pos) + 1))
                    break
    return out


def function_text(source: str, qual: str) -> str | None:
    """The function's body with comments stripped and whitespace collapsed: two
    functions that differ only in layout or comments compare equal, the way the Python
    grader's ast.dump equality ignores both. None when the function is not there."""
    span = next(((a, b) for q, a, b in go_functions(source) if q == qual), None)
    if span is None:
        return None
    body = "\n".join(source.splitlines()[span[0] - 1:span[1]])
    stripped = _STRING_OR_COMMENT.sub(lambda m: m.group(1) or " ", body)
    return " ".join(stripped.split())


def suite_paths(tracked: list[str]) -> list[str]:
    """The smallest set of paths covering the repository's tests: every `_test.go`, and
    each `testdata` directory as one path. Go keeps tests beside the code they test, so
    unlike the Python rule nothing about a source root exempts a file."""
    out: set[str] = set()
    for raw in tracked:
        path = raw.strip().strip("/")
        parts = path.split("/")
        if "testdata" in parts[:-1]:
            out.add("/".join(parts[: parts.index("testdata") + 1]))
        elif path.endswith("_test.go"):
            out.add(path)
    return sorted(out)


def run_selection(node_ids: list[str], module: str) -> tuple[list[str], str]:
    """The `go test` arguments that run exactly these tests' top-level functions:
    (package paths relative to the module root, a -run regex over the test names).
    -run splits on `/` like -skip, so the selection is by parent test and a subtest's
    siblings run too; their verdicts are reported per subtest either way."""
    packages: set[str] = set()
    names: set[str] = set()
    prefix = module.rstrip("/")
    for node in node_ids:
        if "::" not in node:
            continue
        import_path, test = node.split("::", 1)
        rel = import_path[len(prefix):].lstrip("/") if import_path.startswith(prefix) else ""
        packages.add("./" + rel if rel else ".")
        names.add(base(test))
    if not names:
        return [], ""
    return sorted(packages), _alternation(names)


def leaves(node_ids: "set[str] | list[str] | tuple[str, ...]") -> list[str]:
    """The ids with no failing descendant in the same set: a parent red only through a
    subtest is the same failure, so every count (a baseline, a run, a break) is taken
    at this level and the counts agree with each other."""
    ids = set(node_ids)
    return sorted(i for i in ids if not any(o.startswith(i + "/") for o in ids))


TESTS = Path("/tests")
ARTIFACTS = Path("/logs/artifacts")
OUT = Path("/logs/verifier")

# Borrowed from the shipped DeepSWE grader. Restoring tests by discovering them from the
# git tree covers every test in the repository, not just the one named in the task, and
# needs no list maintained by hand.
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testdata"}

# Files that decide what the runner collects or how it reports. A planted conftest.py can
# force every test to report as passed without touching the faults, which earns the whole
# repair score. Restoring only the test files does not stop it, because the hijack lives
# beside them rather than inside them.
COLLECTION_CONFIG_NAMES = {
    "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini",
    "pytest.cfg", ".pytest.ini", "sitecustomize.py", "usercustomize.py",
}

# Modules the runner imports by name. A file called pytest.py at the top of the
# repository is imported instead of the real one, because the working directory leads
# sys.path, so the whole suite can be faked without touching a single test. Blocking
# conftest.py alone missed this, which is the same trick under a different filename.
IMPORT_SHADOW_NAMES = {
    "pytest.py", "py.py", "_pytest.py", "pluggy.py", "coverage.py",
    "unittest.py", "os.py", "sys.py", "json.py", "subprocess.py", "re.py",
}
TEST_FILE_RE = re.compile(
    r"(?:^test_.+|.+_test|.+\.(?:test|spec)|conftest|tests?)"
    r"\.(?:py|js|jsx|ts|tsx|mjs|cjs|go|rs|rb|java|kt|kts|c|cc|cpp|h|hpp)$",
    re.IGNORECASE,
)
OUT = Path("/logs/verifier")

RAW_KEY = (TESTS / "answer_key.json").read_bytes()
key = json.loads(RAW_KEY)
APP = Path(key["workdir"])
RUN_AS = key.get("run_tests_as") or "agent"
weights = key["weights"]
# The language the task was built for is key["language"]; a key written before Go support
# has no field and reads as python. The Go branches below read it off key inline, so the
# functions the tests lift out of this template need no extra name.


def _neutralize_git_config(git_dir: Path) -> bool:
    """Take back the CONTENT of .git/config before root git runs in the tree.

    grade.py runs git as root - ls-tree and checkout of paths for restore_repo_tests,
    update-index for canary_plant - and git executes whatever its configuration names:
    core.fsmonitor on an index refresh, a filter.<name>.smudge driver on a checkout,
    core.hooksPath or core.sshCommand elsewhere. On a shared-verifier task the tree's .git
    belonged to the agent for its whole phase, so such a key is already in the file when
    grading starts; re-owning the file (the seal below) stops a later write but keeps what
    is already there, which is the dangerous half - the content, not the owner.

    Whitelist, do not blacklist. Filter driver names are arbitrary, so no list of keys to
    strip can be complete; instead overwrite the file with the small fixed config the
    grader's own git calls need - repository format and nothing that names a command - so a
    key nobody thought of cannot survive. The image's global safe.directory (git config
    --global, root-owned and not agent-writable) is left in place, so root still operates
    on the agent-owned tree; only the repo-local config, the one file the agent could
    write, is replaced. Returns whether it changed anything, for the seal's report.
    """
    config = git_dir / "config"
    if config.is_symlink():
        # A symlink is followed on open, so root git would read the agent's file through
        # it and refusing to write through it would leave that intact. Remove the link
        # itself (never its target, which is not this grader's) and drop a real safe config
        # in its place. The .git directory is root-owned 0755 by the seal above, so the
        # agent cannot put the link back.
        try:
            config.unlink()
        except OSError:
            return False
    elif not config.is_file():
        return False
    safe = ("[core]\n"
            "\trepositoryformatversion = 0\n"
            "\tfilemode = true\n"
            "\tbare = false\n"
            "\tlogallrefupdates = true\n")
    try:
        if config.is_file() and config.read_text(errors="replace") == safe:
            return False
        config.write_text(safe)
    except OSError:
        return False
    return True


def seal_privileged_paths() -> dict:
    """Put the answer key and this grader's own output out of RUN_AS's reach, now.

    Everything the repair half measures comes out of a process running the agent's source
    as RUN_AS. That account must not be able to READ what the right answer is, and must
    not be able to WRITE the number it is being graded to. The task image already says so
    - tests/Dockerfile leaves /tests mode 700 root and answer_key.json mode 600 - but that
    is a promise made at build time by a Dockerfile this grader does not control, and
    /logs/verifier was never covered by it at all.

    /logs is SHARED WITH THE AGENT CONTAINER, which is how worktree.tgz gets here. So
    /logs/verifier can already exist when grading starts, created by the agent phase and
    owned by the agent, with a reward.txt sitting in it. test.sh's `mkdir -p` accepts that
    directory as it finds it. Taking ownership and closing it to 700 root here means the
    reward this run computes is written somewhere the tree under test cannot read back,
    cannot pre-create and cannot rewrite from anything it forks and leaves running. The
    adversarial suite's "write the reward file from the agent container" case is exactly
    this attack from the other side.

    Re-asserting the /tests modes costs one syscall each and removes the assumption. Both
    are done BEFORE the first line of agent source executes, which is why this sits at the
    top of the file rather than beside the code it protects.

    Reported rather than fatal. A verifier where root cannot chmod its own directories is
    already outside anything this can defend, and refusing to grade would turn it into a
    silent -1 with no reason attached.
    """
    notes = {}

    # A SYMLINK IS NOT A DIRECTORY TO SEAL, IT IS A REDIRECTION, and every call below
    # follows one. Measured, because none of it is obvious from the names:
    #   Path.mkdir(parents=True, exist_ok=True) ACCEPTS a symlink that points at a
    #     directory, because exist_ok is decided by is_dir(), which follows;
    #   os.chown and os.chmod then apply to the TARGET, so root re-owns and re-modes
    #     whatever the link names instead of the output directory;
    #   and a symlinked child redirects the grader's own write - reward.txt pointing at
    #     /dev/null swallows the reward and reward.txt pointing anywhere else publishes
    #     it there.
    # This function exists to stop assuming anything about a path the grader does not
    # control, so following a link out of it would give the assumption straight back.
    # Replace rather than refuse: a link is removed and a real directory made in its
    # place, which is what the grader needed to exist anyway.
    if OUT.is_symlink():
        notes[str(OUT)] = "was a symlink to " + os.readlink(OUT) + ", replaced"
        try:
            OUT.unlink()
        except OSError as exc:
            notes[str(OUT)] = f"symlink, and unlink failed: {exc.__class__.__name__}: {exc}"
    OUT.mkdir(parents=True, exist_ok=True)

    # A LINK CANNOT BE FOLLOWED AND USUALLY CANNOT BE REMOVED, SO IT IS REPORTED.
    # Unlike the output directory, none of these is reachable by the agent: tests/Dockerfile
    # COPYs them into the verifier image as real files, .git is built by git init during the
    # image build, and the agent has no shell in this container. If one is a link anyway the
    # image is not what it claims to be, and neither remedy available is the right one.
    # Following it would chmod a path this grader did not choose, which is the attack.
    # Removing it would delete the grader's own inputs: RAW_KEY was read at module load,
    # already through the link if there was one, /tests also holds originals, faulty and
    # probes, all read later, and .git is the history restore_repo_tests checks out of. So
    # say so, loudly, rather than skipping in silence and letting an empty unsealed_paths
    # claim the paths were closed.
    #
    # A LINKED ROOT DISQUALIFIES EVERYTHING UNDER IT. Reporting /tests or .git and then
    # carrying on to their children is worse than not checking at all, because every child
    # path is reached THROUGH the link: `.git/config` under a symlinked `.git` is not itself
    # a link, so it looks ordinary, and chowning it means chowning a file inside the
    # directory the link names. is_dir() and exists() both follow, which is what made that
    # read as safe. Ask about the root first, and stop there if it is a link.
    def seal_group(root: Path, entries: list) -> None:
        if root.is_symlink():
            notes[str(root)] = ("is a symlink to " + os.readlink(root)
                                + ", so neither it nor anything under it is this "
                                "grader's to set")
            return
        for path, mode in entries:
            # exists() follows, so a DANGLING link would be skipped as silently as a live
            # one. Ask about the link itself before asking about its target.
            if not path.is_symlink() and not path.exists():
                continue
            try:
                if path.is_symlink():
                    # Nothing reads the hooks directory except git, looking for something
                    # to execute, so removing the redirection costs nothing and git is
                    # happy with the directory absent. That makes removal the fail-closed
                    # answer for the one path here where removal is safe.
                    if path.name == "hooks":
                        path.unlink()
                        notes[str(path)] = "was a symlink, removed"
                        continue
                    notes[str(path)] = ("is a symlink to " + os.readlink(path)
                                        + ", so its mode is not this grader's to set")
                    continue
                os.chown(path, 0, 0, follow_symlinks=False)
                os.chmod(path, mode)
            except OSError as exc:
                notes[str(path)] = f"{exc.__class__.__name__}: {exc}"

    seal_group(TESTS, [(TESTS, 0o700), (TESTS / "answer_key.json", 0o600)])
    # The output directory is its own root, and any link there was already replaced above.
    seal_group(OUT, [(OUT, 0o700)])

    # Anything the agent phase left lying in the output directory becomes root's too, so a
    # file it pre-created cannot stay writable underneath the directory that now excludes
    # it. The directory mode alone would be enough on Linux; this is belt and braces for a
    # /logs mounted from somewhere with different semantics. The reward itself is not
    # re-owned but removed: test.sh's trap writes -1 only into an EMPTY reward.txt, so a
    # pre-created `1.0000` would stand as the score if this grader refused to grade (a
    # redirected .git, below) before writing its own. test.sh removes it too, before it
    # runs anything; this covers a grader started some other way.
    if not OUT.is_symlink():
        for child in sorted(OUT.iterdir()):
            try:
                if child.is_symlink():
                    # Nothing legitimate puts a link in here, and leaving one means the
                    # next write to that name lands wherever it points.
                    child.unlink()
                    notes[str(child)] = "was a symlink, removed"
                    continue
                if child.name == "reward.txt":
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
                    notes[str(child)] = "a reward left from before grading, removed"
                    continue
                os.chown(child, 0, 0, follow_symlinks=False)
                if child.is_file():
                    os.chmod(child, 0o600)
            except OSError as exc:
                notes[str(child)] = f"{exc.__class__.__name__}: {exc}"

    # GIT RUNS WHAT ITS CONFIGURATION NAMES, AND THIS GRADER RUNS GIT AS ROOT.
    # restore_repo_tests checks the repository's own tests back out of HEAD, and
    # canary_plant hides the planted files from the diff, both with plain `git` in the tree
    # under test. The env Dockerfile creates .git as root and then chowns the whole
    # workdir to the agent, so in this image .git belongs to the account the tests run as.
    # That turns a config key into root execution: core.fsmonitor is spawned when the
    # index is refreshed, and a filter.<name>.smudge driver is spawned by the very
    # checkout that restores the tests - the one command whose output the grader trusts
    # most. No hook file is needed and no `..` path is needed; one line in .git/config
    # does it. Ownership of the directory matters as much as of the file, because a
    # writable .git lets the file be replaced rather than edited.
    #
    # Objects, refs and the index stay where they are. Re-owning and re-moding .git/config
    # only stops the agent WRITING it during grading; on a shared-verifier task it already
    # wrote the file during its own phase, so _neutralize_git_config takes the content back
    # too. Together they close the executable surface and nothing else, so a suite that
    # reads its own repository still reads it.
    git_dir = APP / ".git"
    if git_dir.is_symlink() or (git_dir.exists() and not git_dir.is_dir()):
        # A symlinked or plain-file .git is never what the image builds - git init makes a
        # real directory. It is the agent redirecting the gitdir the grader's root git calls
        # follow (restore_repo_tests, canary_plant), to an agent-owned config or hooks that
        # name programs git runs as root: core.fsmonitor on an index refresh, a filter
        # driver on the checkout that restores the tests. Re-owning does not reach through a
        # link and the content-neutralization below is a directory operation, so neither
        # defence applies. Refuse. This runs at import, before any git call is made, so the
        # redirection never fires and grading fails closed: grade.py exits without writing a
        # reward and test.sh's trap records -1. A legitimate task never has a non-directory
        # .git, so this cannot fire on one.
        raise SystemExit(
            f"{git_dir} is a "
            + ("symlink" if git_dir.is_symlink() else "non-directory")
            + ", not the git directory the image built; refusing to grade a redirected "
              "gitdir whose config or hooks this grader's root git would obey")
    if git_dir.is_dir():
        seal_group(git_dir, [(git_dir, 0o755), (git_dir / "config", 0o644),
                             (git_dir / "hooks", 0o700)])
        config_was_symlink = (git_dir / "config").is_symlink()
        if _neutralize_git_config(git_dir):
            notes[str(git_dir / "config")] = (
                "was a symlink, replaced with a minimal exec-free config"
                if config_was_symlink
                else "rewrote to a minimal exec-free config")
        # Re-owning the hooks directory keeps whatever the agent dropped in it, and a hook
        # like post-index-change runs as root on the index writes checkout and update-index
        # do during grading. The files are the executable surface, so take them back too.
        # git needs no hook for ls-tree, checkout or update-index.
        hooks = git_dir / "hooks"
        if hooks.is_dir() and not hooks.is_symlink():
            for entry in sorted(hooks.iterdir()):
                try:
                    entry.unlink()
                except OSError as exc:
                    notes[str(entry)] = f"{exc.__class__.__name__}: {exc}"
                else:
                    notes[str(entry)] = "removed a git hook left from the agent phase"
        # .git/commondir (a worktree's shape) names ANOTHER git directory whose config,
        # refs and hooks git reads instead of this one's, which moves the config root git
        # obeys out from under the file just neutralized. `git init` never writes one, so
        # one that is here is the agent's, and git is happy without it.
        redirect = git_dir / "commondir"
        if redirect.is_symlink() or redirect.exists():
            try:
                redirect.unlink()
            except OSError as exc:
                notes[str(redirect)] = f"{exc.__class__.__name__}: {exc}"
            else:
                notes[str(redirect)] = "a gitdir redirect left from the agent phase, removed"
    return notes

def stop_agent_processes_under(root: Path, proc: Path = Path("/proc")) -> list[int]:
    """Kill RUN_AS processes whose cwd or exe is inside the tree under test.

    A uid-wide kill cannot be used in shared-verifier mode: Harbor runs this grader via
    `docker exec` into the still-running agent container, and the process that keeps that
    container alive / relays the reward runs as RUN_AS too. It is a SIBLING of the grader,
    not an ancestor, so a uid-wide (or even lineage-sparing) kill takes it down and the
    exec with it - no reward is ever collected. So scope the kill to what the threat
    actually is: a process the agent left running INSIDE its own repo tree, which can
    rename the restored suite out from under the grader after restore and have scoring run
    a forged green suite (Argus proved it survives canary/determinism, reward 1.0 on zero
    repair). Harbor's relay runs from outside APP, so cwd/exe scoping spares it. The stdlib
    reads /proc in the shell's place; self, zombies, and anything unresolvable are skipped.
    Runs before the seal and the restore, so the tree the suite is scored on is the
    grader's from the first write onward."""
    try:
        uid = pwd.getpwnam(RUN_AS).pw_uid
    except KeyError:
        return []
    try:
        root = Path(root).resolve()
    except OSError:
        return []
    killed: list[int] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        m = re.search(r"^Uid:\s+(\d+)", status, re.M)
        if not m or int(m.group(1)) != uid:
            continue
        under = False
        for link in ("cwd", "exe"):
            try:
                target = (entry / link).resolve()
            except OSError:
                continue
            if target == root or root in target.parents:
                under = True
                break
        if not under:
            continue
        try:
            os.kill(int(entry.name), signal.SIGKILL)
        except OSError:
            continue
        killed.append(int(entry.name))
    return sorted(killed)


AGENT_PROCESSES_KILLED = stop_agent_processes_under(APP)
SEALED_PATHS = seal_privileged_paths()

# Where every pytest invocation in this grading run writes, and where the grader reads.
#
# The nonce is still here and it still matters. At version 2 the scoring run was the only
# invocation carrying --junitxml=/tmp/pytest-report.xml, so an atexit handler appended to
# the package __init__ found that exact string in its own argv, rewrote the report and
# called os._exit(0). Argus reproduced it at about reward 1.0 on a tree where nothing was
# repaired. Hiding the path better was never the fix, because the payload reads argv; what
# the nonce takes away is SELECTIVITY. Every invocation has the same shape of path and
# differs only in the random component, so nothing on the command line says which run is
# worth forging. Do not simplify this back to a fixed or a readable path.
#
# What is no longer claimed is that a payload cannot tell which run it is in at all: it
# can pick out the sabotage run, the one invocation carrying -p. The canary is what made
# hiding that unnecessary. See canary_plant.
RUN_ROOT = Path("/tmp") / ("vg-" + secrets.token_hex(8))
RUN_ROOT.mkdir(parents=True, exist_ok=True)
# Traversable but not listable, so the account the tests run as can reach the path it was
# handed on its own command line and cannot enumerate the others.
os.chmod(RUN_ROOT, 0o711)
PLUG_DIR = RUN_ROOT / "p"
PLUG_DIR.mkdir(parents=True, exist_ok=True)
# Readable, unlike the directory above it. Python's path finder lists a sys.path entry
# before it will import anything out of it, so an execute only directory silently hides
# every module in it and the run comes back with "no module named" and no report at all.
# That refused a correct task once and cost a build cycle. The files here are root owned
# in a directory the tree under test cannot write, so it can look and not touch.
os.chmod(PLUG_DIR, 0o755)

# Where the reports the grader actually reads are kept. Root owned and mode 700, so the
# account the tests run as cannot reach anything inside it, and each run's copy lands in a
# directory that did not exist while that run was going. See seal_report.
SEAL_ROOT = Path("/tmp") / ("vs-" + secrets.token_hex(8))
SEAL_ROOT.mkdir(parents=True, exist_ok=True)
os.chmod(SEAL_ROOT, 0o700)

SABOTAGE_SRC = "def pytest_runtest_call(item):\n    \"\"\"Fail every test from outside the repository.\n\n    Nothing may come back passing from a run carrying this, whatever the tree under test\n    has been made to say about itself. The expected answer does not depend on the agent's\n    code, which is why this can never punish a correct repair: the reference solution\n    fails every test under sabotage too.\n    \"\"\"\n    raise AssertionError(\"sabotage\")\n"


def plant_plugin(source: str) -> str:
    """Write a plugin under a name of its own and return the module name."""
    name = "vp" + secrets.token_hex(8)
    path = PLUG_DIR / (name + ".py")
    path.write_text(source)
    os.chmod(path, 0o644)
    return name


SABOTAGE_PLUGIN = plant_plugin(SABOTAGE_SRC)

# The planted tests that cannot pass, by name. Filled in once the repository's own suite
# has been restored and before anything is measured. An empty set is a legitimate value
# and is not an error: it means the grader has no evidence either way about whose report
# it is reading, which is how this graded before the canary existed.
CANARY: set = set()

# How long one pytest invocation may take. It starts at the old fixed ceiling and comes
# down to something derived from the first run that actually finished; see the note at the
# end of run(). The floor is generous, because refusing to pay for a correct repair costs
# more than any bypass and a worker under load is slower than the machine that measured
# this.
#
# Seeded from a real measurement the build took of this repository's own suite, so the
# FIRST run is bounded too. Calibrating from the first completed run is not enough on its
# own: the run that hangs is usually the first one, and then nothing has been measured yet.
RUN_BUDGET = {"seconds": max(300, int(key.get("suite_seconds") or 0) * 8 + 60) or 1800,
              "floor": 300}

# What every pytest invocation in this grading run reported, in the order they were made.
# Read by the checks on the reporting machinery, which is why it is collected rather than
# thrown away with each run.
RUNS: list = []


def adopt_agent_worktree() -> str:
    """Take only the source files the agent was asked to repair, and nothing else.

    Every grading bypass found so far has been the same shape: the agent controls
    something the grader trusts. A conftest that fakes results, a pytest.py that shadows
    the runner, a commit that rewrites the tests the grader restores from, an atexit
    handler that forges the summary, an entry point plugin hidden in egg-info. Each was
    fixed by naming one more thing to ignore, which is a blacklist, and a blacklist loses.

    So this copies in only what a repair legitimately touches: Python files under the
    declared source roots, excluding anything under a test directory. Everything else in
    the graded tree, including the test suite, the packaging metadata, the interpreter and
    every configuration file, is this container's own and never came from the agent.
    """
    tgz = ARTIFACTS / "worktree.tgz"
    if not tgz.exists():
        return "no worktree collected"
    staging = Path("/tmp/agent-worktree")
    subprocess.run(["rm", "-rf", str(staging)], capture_output=True)
    staging.mkdir(parents=True, exist_ok=True)
    # The archive is agent-controlled and this unpacks it as root, so the flags matter.
    # --no-same-owner and --no-same-permissions stop a member from arriving owned by
    # somebody else or carrying a setuid bit; --no-overwrite-dir stops a member from
    # re-moding a directory that is already there.
    r = subprocess.run(["tar", "xzf", str(tgz), "-C", str(staging),
                        "--no-same-owner", "--no-same-permissions", "--no-overwrite-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"extract failed: {r.stderr[:200]}"

    # SYMLINKS IN THE ARCHIVE ARE READ BY ROOT. The copy below opens each source file with
    # this process's privileges, so a member named like ordinary source and pointing
    # outside the staging tree makes the grader fetch a file the agent cannot open for
    # itself. `zhaquirks/quirks/x.py -> /tests/answer_key.json` puts the answer key inside
    # the graded tree, where the scoring run - which does run the agent's code - reads it
    # back. Resolve every candidate and take only what really lives under staging.
    staging_real = str(staging.resolve())
    app_real = str(APP.resolve())
    copied = skipped_escapes = 0
    for root in key["source_roots"]:
        base = staging / root
        if base.is_symlink() or not base.is_dir():
            continue
        for src in base.rglob("*.go" if key.get("language") == "go" else "*.py"):
            rel = src.relative_to(staging)
            if any(part.lower() in TEST_DIR_NAMES for part in rel.parts):
                continue
            if src.name in COLLECTION_CONFIG_NAMES or src.name in IMPORT_SHADOW_NAMES:
                continue
            try:
                real = src.resolve(strict=True)
            except OSError:
                continue          # a dangling link is not source either
            if os.path.commonpath([str(real), staging_real]) != staging_real \
                    or not real.is_file():
                skipped_escapes += 1
                continue
            # THE DESTINATION IS FOLLOWED TOO, AND THIS WRITE IS ROOT'S.
            # Confining the source to staging says nothing about where the write lands. A
            # symlink already sitting at the destination redirects it, and the graded tree
            # is the only place these bytes are supposed to reach: a link at
            # `pkg/mod.py` pointing into /tests/originals would have root overwrite a
            # pristine copy with agent-controlled bytes, and restored_sites credits a site
            # whose function "matches the original". Not reachable from the agent - no
            # agent code has run in this container yet, and adoption writes bytes rather
            # than creating links - so it would take the repository itself to ship one.
            # The pool repositories checked carry no .py symlinks at all, and refusing
            # costs nothing when they do: a repository's `foo.py -> bar.py` is skipped on
            # the source side by the same rule, and bar.py is adopted on its own.
            dst = APP / rel
            parent = dst.parent
            if not parent.is_dir():
                continue          # the agent cannot introduce new packages into grading
            try:
                real_parent = str(parent.resolve(strict=True))
            except OSError:
                continue
            if os.path.commonpath([real_parent, app_real]) != app_real:
                skipped_escapes += 1
                continue          # a linked directory anywhere above the file
            # READ BEFORE OPENING. O_TRUNC empties the destination the moment the
            # descriptor is opened, and the source is read after, so if the two are ever
            # the same file the content is gone before anything reads it and adoption
            # writes an empty file over every source it was asked to copy. The earlier
            # dst.write_bytes(real.read_bytes()) evaluated the read first and could not
            # do this; opening the destination first can, which is what the O_NOFOLLOW
            # change quietly introduced.
            try:
                payload = real.read_bytes()
            except OSError:
                continue
            if key.get("language") == "go" and not adoptable_go(rel.as_posix(), payload.decode(errors="replace")):
                continue
            # And say the invariant out loud rather than relying on the order alone: the
            # graded tree and the staging tree are meant to be different directories.
            if os.path.realpath(dst) == str(real):
                skipped_escapes += 1
                continue
            try:
                # O_NOFOLLOW makes the kernel refuse rather than trusting the is_symlink
                # answer from a moment earlier, so there is no window between the two.
                handle = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                                 | os.O_NOFOLLOW, 0o644)
            except OSError:
                skipped_escapes += 1
                continue          # the destination itself is a link
            with os.fdopen(handle, "wb") as out:
                out.write(payload)
            copied += 1
    note = f"copied {copied} source files"
    if skipped_escapes:
        note += f", refused {skipped_escapes} reaching outside the graded tree"
    return note


def adoptable_go(rel: str, text: str) -> bool:
    """Whether one file from the agent's tree is Go source a repair legitimately touches:
    a non-test .go file outside vendor/ and test directories that does not import
    "testing". Library code never imports it; a file that does can ask
    testing.Testing() and be correct only while a test is watching, which the Python
    grader defends against with recorded calls that Go has no analog of yet."""
    parts = rel.split("/")
    if not rel.endswith(".go") or rel.endswith("_test.go"):
        return False
    if any(p.lower() in TEST_DIR_NAMES or p.lower() == "vendor" for p in parts[:-1]):
        return False
    # The import declarations, read the way the canary reads them: an alias or a dot
    # import counts, a `"testing"` inside a comment or a raw string does not
    # (shell-plugins keeps a test-file template in cmd/contrib/main.go).
    return go_testing_identifier(text) is None


def run(cmd: str, as_user: str | None = None, calibrate: bool = True) -> tuple[int, str]:
    """Run a command in the repository, never as root.

    The working directory is kept off sys.path with the interpreter's -P flag rather than
    with PYTHONSAFEPATH in the environment; see safe_path.

    EVERY COMMAND THIS STARTS DROPS PRIVILEGES. The working directory is the tree under
    test, so anything started here can import the agent's own source, and a command that
    imports agent source as root hands the agent the grader. as_user picks WHICH account,
    and omitting it means RUN_AS rather than root, so there is no spelling of this call
    that runs the repository as root. That is deliberate: the one place that did was
    _diag_collect_count, which called subprocess.run directly and so never came through
    here at all. Argus rated it critical - module level code in a file the agent was asked
    to edit ran as uid 0 inside the verifier, which is enough to read the answer key and
    to overwrite the pristine originals/ copies the repair half credits against. Nothing
    in this grader needs root to run the tree, so the parameter no longer offers it.

    calibrate=False for a command that is not one whole suite run. The budget at the end
    of this function is learned from how long a run took, so a short command teaches it a
    short number and every real run after it is killed on that number. Collecting is not
    running: on a repository whose suite takes ten minutes, collection takes seconds, and
    a probe that calibrated would cut the budget to its floor before the first scoring run
    ever started. The probe is still BOUNDED by the budget, like everything else. It just
    does not get to set it.
    """
    # Plugin autoload used to be disabled here, to stop a setuptools entry point planted in
    # packaging metadata from loading itself into the run. It also switched off the
    # repository's real plugins. On a suite whose tests need pytest-asyncio, every async
    # test quietly turned into a skip, so a fault sitting under one of them could not be
    # seen and the suite passed with it still in place. The entry point attack is already
    # dead for a better reason: only source files are taken from the agent, so packaging
    # metadata never reaches this container at all. adversarial.py keeps proving that.
    env = dict(os.environ)
    as_user = as_user or RUN_AS
    # setpriv changes the user but not the environment, so HOME stayed at root's while
    # the process ran as agent. Any test that writes under HOME then failed with a
    # permission error, and a correct solution lost the whole repair half for a reason
    # that has nothing to do with the repository or the agent. Give the account it runs
    # as the home directory it actually owns.
    try:
        home = pwd.getpwnam(as_user).pw_dir
    except KeyError:
        home = "/home/" + as_user
    env = dict(env, HOME=home, USER=as_user, LOGNAME=as_user,
               XDG_DATA_HOME=home + "/.local/share",
               XDG_CACHE_HOME=home + "/.cache",
               XDG_CONFIG_HOME=home + "/.config")
    # A LOGIN SHELL SOURCES THE AGENT'S OWN ~/.bash_profile (and an interactive rc its
    # ~/.bashrc), and the agent owns those files - so a `go`/`python` shell function or a
    # PATH prepend planted there shadows the very toolchain this grader reads its verdict
    # from. Argus proved it: a forged `go test -json` from a ~/.bash_profile shim scores
    # reward 1.0 on a fully unrepaired tree, canary-blind. Use a NON-login, non-rc shell so
    # neither file is read, and source only the ROOT-OWNED /etc/profile.d - which is what
    # legitimately puts the repository's runtime (the venv, the language toolchain) on PATH
    # and which the agent cannot write. Its own output is discarded so it cannot pollute the
    # stream the grader parses. HOME stays the account's own dir (above) so a test that
    # writes under it still works; only the shell's startup-file sourcing changes.
    prelude = ('{ for _f in /etc/profile.d/*.sh; do [ -r "$_f" ] && . "$_f"; done; } '
               ">/dev/null 2>&1; ")
    argv = ["setpriv", "--reuid", as_user, "--regid", as_user, "--clear-groups",
            "bash", "--noprofile", "--norc", "-c", prelude + cmd]
    # Drained on a thread while the run is going, and waited on with a deadline, rather
    # than handed to subprocess.run.
    #
    # THIS IS NOT TIDINESS. subprocess.run returns when the pipe reaches end of file, and
    # a pipe is only at end of file once EVERY process holding the write end has gone.
    # werkzeug's serving tests spawn a development server as a child process, that child
    # inherits this descriptor, and one grading run sat there until the 1800 second
    # timeout killed it on a suite that takes 27 seconds by itself. The reference solution
    # scored -1 and the build gate refused the task, which is the gate working.
    #
    # What is wanted is the bytes the run produced before it exited, which is exactly what
    # this reads. A grandchild still holding the descriptor afterwards costs a bounded
    # wait and nothing else.
    p = subprocess.Popen(argv, cwd=APP, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env, text=True,
                         start_new_session=True)
    chunks: list = []

    def drain(stream=p.stdout, into=chunks):
        try:
            for block in iter(lambda: stream.read(1 << 16), ""):
                into.append(block)
        except Exception:
            pass

    pump = threading.Thread(target=drain, daemon=True)
    pump.start()
    started = time.time()
    try:
        code = p.wait(timeout=RUN_BUDGET["seconds"])
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, 9)
        except OSError:
            p.kill()
        code = -1
    # The run is over either way. Anything still holding the descriptor is not the run.
    pump.join(20)
    # What one run of this suite costs, learned from the first one that finished, so the
    # rest of this grading run cannot be held up for longer than the verifier has.
    #
    # A FIXED CEILING IS THE WRONG SHAPE HERE. The old one was 1800 seconds against a
    # verifier allowance of 2400, so a single run that hung ate the whole allowance and
    # the rollout came back with NO SCORE rather than a low one - the failure QC.md
    # records as the most expensive kind, because a task that returns nothing looks like
    # somebody else's problem. werkzeug makes it reachable: its serving tests start a
    # development server as a child process, and a tree whose package cannot be imported
    # leaves those tests waiting for a server that will never answer. An agent that
    # leaves an import error behind should score badly, not silently cost the run.
    spent = time.time() - started
    if calibrate and (code == 0 or code == 1):
        RUN_BUDGET["seconds"] = min(RUN_BUDGET["seconds"],
                                    max(RUN_BUDGET["floor"], int(spent * 8) + 60))
    return code, "".join(chunks[:])


