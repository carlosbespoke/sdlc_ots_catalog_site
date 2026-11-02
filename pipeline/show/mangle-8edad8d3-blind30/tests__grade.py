#!/usr/bin/env python3
"""Grade a fault chain task.

Two halves, neither of which needs a model.

  repair   the target test passes and nothing else broke
  report   /app/rca.json names each edited file and function, and each site it names
           shows evidence that the behaviour that edit took away has come back

The answer key is written when the task is built, from the record of what was injected,
so grading is a comparison rather than a judgment.

Threat model, for whoever reviews this grader. The agent never sees this file: /tests is
a root-owned mount that is not in the agent's tree during its phase, and the suite it
grades with is restored from there at grade time. So the attacks that count are the ones
an agent can mount WITHOUT reading this file. A forgery that has to know which tests are
the planted canaries, or which failures to keep, needs this file or a process of the
agent's left alive into grading; a shim without that knowledge turns the canaries green,
and the canary check refuses the run. The classes that rules out are settled at triage,
not here.
"""

from __future__ import annotations

import ast
import copy
import errno
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
import stat
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# The grader runs as root, and environment/Dockerfile puts the agent-owned /opt/venv/bin
# first on PATH. Every bare binary this process resolves - setpriv (which run() uses to
# DROP to the agent, so it is located while still root), git, tar, rm - would otherwise
# come from a directory the agent owns and could have planted a binary in, and would run as
# root before any privilege drop. Pin a trusted PATH of the base image's real tools, which
# are never chowned to the agent, before any subprocess starts. The repository's own suite
# still gets the venv: run() executes it through a non-login, non-rc shell whose prelude
# sources only the root-owned /etc/profile.d, which re-prepends /opt/venv/bin.
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
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(h|m|s)")


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


def _words(cmd: str) -> list[str] | None:
    """The command as shell words, a `# comment` dropped the way the shell drops it, or
    None when shlex cannot parse it (a stray quote): the callers leave such a command
    alone rather than raise on it.

    bash starts a comment only at the start of a word; shlex at any unquoted `#`. Go's
    auto-numbered subtests put one mid-word (`-run TestFoo/#01`), so a `#` that follows
    a non-blank is masked before the split and restored after."""
    masked = re.sub(r"(?<=\S)#", "\0", cmd)
    try:
        return [word.replace("\0", "#") for word in shlex.split(masked, comments=True)]
    except ValueError:
        return None


def _own_timeout(words: list[str]) -> str | None:
    """The duration a `go test` command's own -timeout flag sets (`-timeout 2h`,
    `-timeout=2h`, either dash count), read off shell words so a `-timeout` inside a
    quoted -run pattern is not one."""
    for i, word in enumerate(words):
        flag, eq, value = word.partition("=")
        if flag.lstrip("-") != "timeout" or not flag.startswith("-"):
            continue
        if eq:
            return value
        if i + 1 < len(words):
            return words[i + 1]
    return None


def ensure_timeout(cmd: str, timeout: str) -> str:
    """`go test` with `-timeout <duration>` right after the verb, unless the command sets
    its own. Suites that outrun go's 10-minute default at the task's 2 CPUs need the
    longer timeout in the ONE command every stage shares (baseline, composition, gate,
    grader), or the stages measure different suites. Shell words in and out, so a quoted
    argument keeps its spaces. Any non-`go test` command returns unchanged."""
    words = _words(cmd) if is_go_test(cmd) else None
    if words is None or _own_timeout(words):
        return cmd
    head = 2 + (1 if len(words) > 2 and _COUNT1.fullmatch(words[2]) else 0)
    return shlex.join(words[:head] + ["-timeout", timeout] + words[head:])


def timeout_seconds(cmd: str) -> int | None:
    """The seconds a `go test` command's own -timeout allows (`2h`, `90m`, `1h30m`), or
    None when it sets none or is not `go test`: what a stage's own cap has to exceed."""
    words = _words(cmd) if is_go_test(cmd) else None
    duration = _own_timeout(words) if words else None
    if not duration:
        return None
    total = 0.0
    for number, unit in _DURATION.findall(duration):
        total += float(number) * {"h": 3600, "m": 60, "s": 1}[unit]
    return int(total) or None


def is_go_test(cmd: str) -> bool:
    """Is this a `go test` invocation (the verb, not a prefix of another word)?"""
    return cmd == "go test" or cmd.startswith("go test ")


#: What makes a Go tree ungradable, as `go test` prints it without -json: a package
#: whose test binary never built or never set up, or a test binary that panicked (which
#: kills every remaining test in that package). Plain `--- FAIL` lines are failures,
#: and failures are what faults are for. A `panic: ` line counts only when the
#: runtime's goroutine trace follows it: a test that merely logs the word is not a
#: crash.
#: Captures the import path so a build/setup failure can be attributed to its package and
#: a constraint-excluded one dropped from the count.
BUILD_FAILED = re.compile(r"^FAIL\s+(\S+)\s+\[(?:build|setup) failed\]", re.M)
#: A package go could not build because build constraints exclude ALL its Go files on this
#: platform: a GOOS=js/wasm-only package under a normal `go test ./...` (one importing
#: `syscall/js`, say). go prints it in the same `[build|setup] failed` shape as a real
#: compile error, but it is not the agent's failure and cannot be built or tested here at
#: all - counting it caps every solution on any repo that ships such a package (jd/v2's
#: internal/web/ui). It is the platform's `[no test files]`, not an error.
#: The trailing ` in ` is load-bearing: the go tool's diagnostic ALWAYS names the excluded
#: directory (`... exclude all Go files in <dir>`, with or without an `imports <path>:`
#: prefix), so requiring it matches the compiler's real message and NOT a package that
#: merely prints the bare phrase in its own output and then fails without a verdict - which
#: would otherwise be dropped from package_failed and let a real setup failure pass.
CONSTRAINT_EXCLUDED = "build constraints exclude all Go files in "
#: Anywhere on its line: testing prints the panic it recovered once more, INDENTED,
#: before the trace, and a test that printed without a newline leaves its text in front
#: (pterm: "bpanic: ..."). What makes it a crash is the trace on the lines after it,
#: not the column; a log line that merely says "panic:" has no trace.
PANIC = re.compile(r"panic: ")
TRACE = re.compile(r"^goroutine \d+ \[running\]:")
#: The runtime killing a test binary at -timeout: a crash on its own line. It prints the
#: tests still running BETWEEN this line and the trace, one per line, so the pair can sit
#: any distance apart and the window below cannot be what finds it (sarama on the fire
#: fleet: a fault hung the root package, the other packages' 203 tests were all the gate
#: saw of 654, and the composition check had called the tree clean).
TIMED_OUT = re.compile(r"^panic: test timed out", re.M)
#: The runtime dying on a fatal error - `concurrent map writes`, `all goroutines are
#: asleep - deadlock!` - which it prints as `fatal error:` rather than `panic:`, followed
#: by a dump of EVERY goroutine (whose header lines carry `gp=`/`m=` annotations that the
#: panic trace pattern does not match). A crash on its own line, like the timeout: on the
#: fire fleet a fault that raced a map killed maroto's metrics package in five seconds,
#: composition called the tree clean, and the gate saw 291 of 295 tests.
FATAL = re.compile(r"^fatal error: ", re.M)
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
#: The `# <import path>` header and the constraint message are matched too, so a package
#: the platform's build constraints exclude entirely (CONSTRAINT_EXCLUDED) is recognisable
#: in the excerpt and dropped from the count, however many excluded imports pushed its
#: header above the -B window. Matching them only ADDS lines to the excerpt (they are not
#: error lines errors() counts), so a real failure is never hidden by the addition.
ERROR_LINE_ERE = (r"^FAIL[[:space:]]+[^[:space:]]+[[:space:]]+\[(build|setup) failed\]"
                  r"|^goroutine [0-9]+ \[running\]:|^panic: test timed out|^fatal error: "
                  r"|^# [^[:space:]]|build constraints exclude all Go files in ")
ERROR_GREP = f"grep -E -B{TRACE_CONTEXT} {shlex.quote(ERROR_LINE_ERE)}"


def timed_out(text: str) -> bool:
    """Whether the runtime killed a test binary at -timeout, read off a `go test -json`
    stream (the panic sits inside an Output event) or a plain log alike."""
    for line in text.splitlines():
        if line.startswith("{"):
            try:
                line = str(json.loads(line).get("Output", ""))
            except ValueError:
                continue
        if TIMED_OUT.match(line):
            return True
    return False


def constraint_excluded_packages(output: str) -> set[str]:
    """Import paths whose every Go file this platform's build constraints exclude, read
    from plain `go test` output: the package go names in the `# <import path>` header it
    prints above each build message, when that message says the constraints excluded all
    its files. These are not testable here and are not build failures. See CONSTRAINT_EXCLUDED.
    """
    excluded: set[str] = set()
    current: str | None = None
    for line in output.splitlines():
        header = re.match(r"^# (\S+)", line)
        if header:
            current = header.group(1)
        elif current is not None and CONSTRAINT_EXCLUDED in line:
            excluded.add(current)
    return excluded


def errors(output: str) -> int:
    """The count of error lines in `go test` output — the analog of pytest's
    `N errors` summary count that collectcheck disqualifies a composed tree on. A package
    the platform's build constraints exclude entirely is not one of them (CONSTRAINT_EXCLUDED)."""
    lines = output.splitlines()
    excluded = constraint_excluded_packages(output)
    build_failed = sum(1 for line in lines
                       if (m := BUILD_FAILED.match(line)) and m.group(1) not in excluded)
    # The crash is the trace; the panic line within the few lines before it is what
    # names it. Counting traces reads the recovered-and-rethrown pair (two panic lines,
    # one trace) as one crash, and a run of log lines that say "panic:" as none.
    crashes = sum(1 for i, line in enumerate(lines)
                  if TRACE.match(line)
                  and any(PANIC.search(l) for l in lines[max(0, i - TRACE_CONTEXT):i]))
    return (build_failed + crashes + len(TIMED_OUT.findall(output))
            + len(FATAL.findall(output)))


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
    #: Every test the stream says was STARTED, from its `run` action, whether or not it
    #: went on to answer. `go test -json` runs the binary verbose, so test2json emits a
    #: run event for every test it starts and a stream with none started no test. This
    #: is what tells a suite that was asked to run nothing (`-run '^$'`) from one that
    #: ran and passed, which no count taken from the verdicts alone can do, and a
    #: forged stream of bare pass events is missing it. See the_breaks_did_not_run.
    started: set[str] = field(default_factory=set)


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
    excluded: set[str] = set()      # build constraints exclude all the package's Go files
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
            if CONSTRAINT_EXCLUDED in text:
                # A wasm-only package under a normal run: not testable here, not a failure.
                excluded.add(package)
            if TIMED_OUT.match(text) or FATAL.match(text):
                panicked.add(package)        # the runtime killed the binary: -timeout or fatal
            elif PANIC.search(text):
                panic_seen.add(package)
            elif TRACE.match(text) and package in panic_seen:
                panicked.add(package)        # the real thing: the runtime's trace follows
            elif text.strip() and not text.startswith("[signal "):
                # Anything else in between is a log line, except the runtime's own
                # `[signal SIGSEGV: ...]` line, which a nil dereference prints between
                # the panic and the trace (rain: read as a log line, the crash was missed).
                panic_seen.discard(package)
        elif test:
            if action == "run":
                run.started.add(node_id(package, test))
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
    # A package the platform's build constraints exclude entirely reported no verdicts and
    # failed at the package level, but it is not a build/setup failure to charge: drop it.
    # A panicked package is always kept - a package cannot both panic and have no Go files.
    run.package_failed = {node_id(p, PACKAGE_SENTINEL)
                          for p in (failed_packages - verdicts_in - excluded) | panicked}
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


# --- where a test and a fault live, and whether that is the same place ----------------
#
# A fault whose only break test lives in another package is a fault nobody can diagnose
# from the failure: the test exercises different code, and it went red for a reason the
# edit does not explain. comqtt's ebdcf894 was one — a map capacity edit in the broker
# whose sole break was TestServerClose, which never calls the edited function. These three
# serve the miner and the task builder, which is why they live here: gotest is the one
# module both of them already import, and two copies of a locality rule would disagree
# with each other within a release.


def source_package(path: str) -> str:
    """The package a source file belongs to: its directory, or "." at the repository
    root. Both languages, because both are read from the repository-relative path."""
    head = path.rsplit("/", 1)[0] if "/" in path else ""
    return head or "."


def test_package(node: str, module: str | None = None, go: bool = True) -> str:
    """The package a test node id's file belongs to, spelled the way `source_package`
    spells it. "" when the id cannot be placed in this repository at all, which for Go
    means an import path that is not under this module.

    A Go node id names an import path, not a file, so the module prefix comes off and
    what is left is the directory. A pytest node id names the file itself."""
    head = node.split("::", 1)[0]
    if not go:
        return source_package(head)
    if not module:
        return ""
    if head == module:
        return "."
    return head[len(module) + 1:] if head.startswith(module + "/") else ""


def _unaffixed(part: str) -> str:
    """A path component with pytest's `test_` prefix or `_test` suffix taken off."""
    return part[5:] if part.startswith("test_") else part.removesuffix("_test")


def break_is_local(node: str, fault_path: str, module: str | None = None,
                   go: bool = True) -> bool:
    """Could this break test be in the same package as the edit at `fault_path`?

    Given the module, the Go answer is exact: the two directories match or they do not.
    WITHOUT the module — the miner's case, which never reads go.mod — the import path is
    still enough for a sufficient test, because an import path ends with the directory it
    names. A fault in the repository root cannot be placed that way at all, so it answers
    True: this predicate is read to REFUSE a fault, and refusing on an undecidable answer
    would refuse honest work.

    Python is a different question wearing the same clothes. A pytest suite lives in its
    own `tests/` tree, so comparing directories would call nearly every Python fault
    non-local and refuse the language; the module name is what relates the two. A test
    file whose stem, less a `test_` or `_test` affix, names any directory or module on the
    fault's path is local, and so is a test path that spells the faulted module's own
    name. Anything else has no visible relationship to the edit.
    """
    head = node.split("::", 1)[0]
    if go:
        here = source_package(fault_path)
        if module:
            return bool(there := test_package(node, module)) and there == here
        if here == ".":
            return True
        return head == here or head.endswith("/" + here)
    if source_package(head) == source_package(fault_path):
        return True
    # WHOLE COMPONENTS ON BOTH SIDES, never a substring. `foo` occurs inside
    # `test_foobar.py` and the two have nothing to do with each other, so a substring
    # match quietly calls an unrelated test local and the advisory finding never fires.
    # Each component of the test's path gives up its `test_` or `_test` affix first, so
    # `tests/arrow/test_shift.py` offers `tests`, `arrow` and `shift`.
    names = {part for part in fault_path.removesuffix(".py").split("/") if part}
    parts = {_unaffixed(part) for part in head.removesuffix(".py").split("/") if part}
    return bool(names & (parts - {""}))


def nonlocal_breaks(breaks: "list[str] | set[str]", fault_path: str,
                    module: str | None = None, go: bool = True) -> list[str]:
    """The break tests that cannot be in the fault's own package, sorted."""
    return sorted(t for t in breaks if not break_is_local(t, fault_path, module, go))


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
# has been restored and before anything is measured. On PYTHON an empty set is a
# legitimate value and is not an error: it means the grader has no evidence either way
# about whose report it is reading, which is how this graded before the canary existed.
# ON GO IT IS A REFUSAL, because the Go verdict has nothing else holding it up; see
# canary_was_planted.
CANARY: set = set()

# What the Go plant did, for the refusal above to be able to say which step came back
# empty: how many packages own a break, how many of them had a file the canary could be
# appended to, what was planted, and which of those the probe run reported back.
CANARY_GO: dict = {"packages": 0, "hosts": 0, "tagged_only": 0, "unsafe": 0,
                   "planted": [], "reported": []}

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

    So this copies in only what a repair legitimately touches: Python files under t