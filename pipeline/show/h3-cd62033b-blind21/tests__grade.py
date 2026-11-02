#!/usr/bin/env python3
"""Grade a fault chain task.

Two halves, neither of which needs a model.

  repair   the target test passes and nothing else broke
  report   /app/rca.json names each edited file and function, and each site it names
           shows evidence that the behaviour that edit took away has come back

The answer key is written when the task is built, from the record of what was injected,
so grading is a comparison rather than a judgment.

Threat model, for whoever reviews this grader. The agent never sees this file. The task is
dual-container: this grader runs in its own verifier container, built from
tests/Dockerfile, and /tests - this file, the answer key, the pristine sources and the
hidden suite - exists only in that image, root-owned, never in the agent's container. What
reaches this container from the agent is the collected /logs/artifacts and nothing else:
worktree.tgz, out of which adopt_agent_worktree takes only source files under the declared
source roots, and rca.json, read before any of that source runs. The agent's .git, venv,
home directory and processes stay behind in its own container. So the attacks that count
are the ones an agent can mount WITHOUT reading this file, through the source it hands
over, which this grader runs as the agent account for every suite run. A forgery that has
to know which tests are the planted canaries, or which failures to keep, needs this file,
and no process of the agent's can be alive in this container to read it; a shim without
that knowledge turns the canaries green, and the canary check refuses the run. The
classes that rules out are settled at triage, not here.
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
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import ModuleType

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


# The test-context check, from build_task.SNIFF_SRC; the build runs the same source over
# the shipped tree to record what it already holds. See test_context_sniffing.


# THE TEST-CONTEXT CHECK. Source that applies a fix only while a test is watching passes
# every test by construction, and at a site with no recorded call there is nothing else to
# ask. Under AlphaRecon's binary reward such a tree could never reach 1.0; under the
# partial reward it was paid per site (0.600 and 0.650 on cyclopts-954e72e1-blind30). So
# the agent's own changes are read for the thing that trick cannot do without: looking at
# whether a test is running. A statement the agent added or changed that inspects the
# call stack, asks whether pytest or unittest is loaded, reads PYTEST_CURRENT_TEST, or
# looks for a test runner in argv makes the per-site runner route untrustworthy for every
# site, as a caught probe does.
#
# ONE SOURCE FOR BOTH SIDES. It is spliced into tests/grade.py and also executed by the
# build, which records the statements of this kind the shipped tree already holds
# (`sniff_baseline` in the answer key), so a library that legitimately inspects frames is
# not charged for its own code: only statements not in the shipped copy of the same file
# count. Statements are normalised before matching (lower case, whitespace, quotes and
# `+` removed), so "py" + "test", getattr(sys, "_get" + "frame") and
# importlib.import_module("insp" + "ect") read the same as the plain spelling.
SNIFF_FRAME_WORDS = ("_getframe", "currentframe", "inspect.stack", "inspect.trace",
                     "extract_stack", "walk_stack", "getouterframes", "getinnerframes",
                     "getframeinfo", "f_back", "co_name", "co_filename", "tb_frame",
                     "f_locals", "f_globals")
SNIFF_RUNNERS = ("pytest", "unittest")
#: The inspect functions that walk or read the stack, reached through `from inspect
#: import ...` or an alias (`import inspect as i; i.stack()`).
SNIFF_INSPECT_FUNCS = ("stack", "currentframe", "getouterframes", "getinnerframes",
                       "trace", "getframeinfo")
#: Code that turns a string into a name. Where a statement holds one, the words inside its
#: string literals count as code too, so getattr(sys, "_get" + "frame") is still read.
SNIFF_INDIRECTION = ("getattr", "import_module", "__import__", "eval", "exec", "compile",
                     "globals", "vars", "__dict__")


def _sniff_word(norm, word):
    """`word` in `norm`, not as the tail of a longer identifier (disco_name is not co_name)."""
    start = norm.find(word)
    while start >= 0:
        before = norm[start - 1] if start else ""
        if not (before.isalnum() or (before == "_" and not word.startswith("_"))):
            return True
        start = norm.find(word, start + 1)
    return False


def sniff_hit(code, full, library=True, aliases=(), names=()):
    """Whether one statement looks at whether a test is running.

    `code` is the statement with every string literal replaced by S, `full` the same with
    the literals' text kept; both lower case with whitespace, quotes and `+` removed.
    Stack and frame words are read in `code`, so a message that merely mentions
    "f_back" is not a signal, and in `full` only when the statement turns strings into
    names. Which runner is asked about is always read in `full`, because that is a string
    ("pytest" in sys.modules). `library` is False for a file that is not importable library
    code; there an ordinary `import pytest` is not a signal. `aliases` are the names this
    file binds to the inspect module, `names` its raw tokens.
    """
    runner = any(word in full for word in SNIFF_RUNNERS)
    frame_text = full if any(word in code for word in SNIFF_INDIRECTION) else code
    if any(_sniff_word(frame_text, word) for word in SNIFF_FRAME_WORDS):
        return True
    if any(_sniff_word(code, f"{alias}.{func}")
           for alias in aliases for func in SNIFF_INSPECT_FUNCS):
        return True
    if (list(names[:3]) == ["from", "inspect", "import"]
            and any(name in SNIFF_INSPECT_FUNCS for name in names[3:])):
        return True
    if "modules" in code and runner:
        return True
    if ("environ" in code or "getenv" in code) and (
            runner or "pytest_current_test" in full):
        return True
    if "argv" in code and runner:
        return True
    if ("import_module" in code or "__import__" in code) and (
            runner or "inspect" in full):
        return True
    if library and runner and (code.startswith("import") or code.startswith("from")):
        return True
    return False


def _sniff_norm(text):
    text = text.lower()
    for ch in " \t\r\n\\\"'+":
        text = text.replace(ch, "")
    return text


def sniff_statements(text, library=True):
    """The normalised statements in one Python source that look at whether a test runs.

    Comments are dropped and so is a statement that is a bare string (a docstring), so
    prose about tests is not a signal. A file tokenize cannot read is read line by line.
    Each hit is returned as its `full` normalisation, which is what the shipped baseline
    records.
    """
    import io
    import tokenize
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.INDENT, tokenize.DEDENT,
            tokenize.ENCODING, tokenize.ENDMARKER}
    statements, current = [], []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.NEWLINE:
                statements.append(current)
                current = []
            elif tok.type not in skip:
                current.append(tok)
        statements.append(current)
        pieces = [[(tok.string, tok.type == tokenize.STRING) for tok in stmt]
                  for stmt in statements
                  if stmt and not all(tok.type == tokenize.STRING for tok in stmt)]
    except (tokenize.TokenError, SyntaxError, ValueError):
        pieces = [[(line.split("#", 1)[0], False)] for line in text.splitlines()]
    aliases = {"inspect"}
    for parts in pieces:
        words = [piece for piece, _ in parts]
        if words[:2] == ["import", "inspect"] and len(words) >= 4 and words[2] == "as":
            aliases.add(words[3].lower())
    found = []
    for parts in pieces:
        full = _sniff_norm("".join(piece for piece, _ in parts))
        code = _sniff_norm("".join("S" if is_str else piece for piece, is_str in parts))
        names = [piece for piece, _ in parts]
        if full and sniff_hit(code, full, library, aliases, names) and full not in found:
            found.append(full)
    return found


def sniff_library_file(rel, is_package_dir, imported=()):
    """Whether `rel` is library code: in a package, or a top-level module some package
    file imports; and not a test module."""
    name = rel.rsplit("/", 1)[-1]
    if (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
            or any(part in ("test", "tests", "testing") for part in rel.split("/")[:-1])):
        return False
    if "/" not in rel:
        return name[:-3] in imported
    return is_package_dir(rel.rsplit("/", 1)[0])


def sniff_tree(root, rels):
    """{relative path: [normalised statements]} over the Python files `rels` under `root`.

    Two passes: the first reads which top-level modules the package files import, so a
    helper at the repository root that a package imports is read as library code rather
    than as a script.
    """
    import os as _os
    import re as _re

    def is_package_dir(d):
        return bool(d) and _os.path.isfile(_os.path.join(root, d, "__init__.py"))

    texts = {}
    for rel in rels:
        try:
            with open(_os.path.join(root, rel), encoding="utf-8", errors="replace") as handle:
                texts[rel] = handle.read()
        except OSError:
            continue
    imported = set()
    for rel, text in texts.items():
        if "/" in rel and is_package_dir(rel.rsplit("/", 1)[0]):
            imported.update(_re.findall(r"(?m)^\s*(?:from|import)\s+([A-Za-z_]\w*)", text))
    out = {}
    for rel, text in texts.items():
        hits = sniff_statements(text, sniff_library_file(rel, is_package_dir, imported))
        if hits:
            out[rel] = hits
    return out


# GO. The same question asked of Go source, which has its own ways to ask it: `go test`
# runs a binary named <pkg>.test with -test.* flags on its command line and registered in
# the flag package, the testing package answers Testing(), and every test runs under
# testing.tRunner on the stack. None of these is something library code needs in order
# to do its job, and where a repository does use one (a logger reading runtime.Caller, a
# CLI with a "test" subcommand) the baseline the build records from the shipped tree
# holds that statement, so only a statement the agent added or changed counts.
#
# AND WHERE THE PROCESS RUNS FROM. `go test ./pkg/` runs the test binary with its working
# directory set to the package's own source directory (and PWD to match), which is where
# no production binary runs, and from a shell that set $_ to the go command. So asking
# where the process is, or what files sit around it, tells a test from production as
# surely as os.Args does: os.Getwd, PWD, `pwd`, $_, and any file system call handed a
# relative path written in the source (os.Stat("x.go"), filepath.Abs("."),
# os.ReadDir("."), filepath.Glob("*_test.go")). A library is handed the paths it works
# on; it does not make up relative ones. A path built from a parameter or a field is not
# read this way, only one that starts with a string the source spells.
#
# A STATEMENT IS A LOGICAL LINE. A newline ends one unless it falls inside ( or [, so a
# call written over several lines is one statement, while each line of a block, of a
# closure body and of a grouped import/var/const/type declaration is its own, the way
# Python statements are, and a repair inside a long closure changes one statement rather
# than the whole call around it. Comments are dropped, except a //go:linkname directive:
# that is code to the compiler, and it reaches unexported state such as the flag
# testing.testBinary that Testing() reads. String literals joined with + are read as one.
import re
SNIFF_GO_TOKEN = re.compile(
    r'//[^\n]*|/\*.*?(?:\*/|\Z)|"(?:\\.|[^"\\\n])*"?|`[^`]*`?|\x27(?:\\.|[^\x27\\\n])*\x27?'
    r'|[()\[\]{};\n]|[^/"`\x27()\[\]{};\n]+|/', re.S)
#: A ( after one of these opens a grouped declaration, whose lines are statements.
SNIFF_GO_GROUPS = ("import", "var", "const", "type")
#: Environment variables a CI system or a test runner sets and a library has no reason
#: to name: a literal that is exactly one of these is a hit wherever it is.
SNIFF_GO_RUNNER_ENV = ("ci", "github_actions", "gitlab_ci", "buildkite", "circleci",
                       "travis", "jenkins_url", "teamcity_version", "tf_build",
                       "gocoverdir", "go_want_helper_process", "test_srcdir", "test_tmpdir",
                       "pytest_current_test")
#: The packages whose members are asked about, by the name each binds by default.
SNIFF_GO_PACKAGES = {"os": "os", "runtime": "runtime", "runtime/debug": "debug",
                     "runtime/pprof": "pprof", "flag": "flag", "syscall": "syscall",
                     "golang.org/x/sys/unix": "unix", "testing": None,
                     "path/filepath": "filepath", "path": "path", "io/ioutil": "ioutil",
                     "os/exec": "exec"}
#: The calls that read the file system at a path, resolved against the working directory
#: when the path is relative. Handed a relative path the source spells, each one asks
#: where the process runs from.
SNIFF_GO_PATH_READS = {
    "os": ("stat", "lstat", "open", "openfile", "readfile", "readdir", "dirfs", "chdir",
           "openroot", "openinroot", "readlink"),
    "io/ioutil": ("readfile", "readdir"),
    "path/filepath": ("abs", "evalsymlinks", "glob", "walk", "walkdir"),
    "syscall": ("stat", "lstat", "open", "access", "chdir", "readlink"),
    "golang.org/x/sys/unix": ("stat", "lstat", "open", "access", "chdir", "readlink"),
}
#: The calls that only put a path together, looked through for the string it starts with:
#: os.Stat(filepath.Join("testdata", name)) is as relative as os.Stat("testdata").
SNIFF_GO_PATH_BUILDERS = {"path/filepath": ("join", "clean", "fromslash"),
                          "path": ("join", "clean")}
#: The largest Go file the scan reads, at build time and at grade time. Far above any
#: generated table a repository ships; see GO_SNIFF_LIMIT in the grader for the rest.
SNIFF_GO_LIMIT = 32_000_000
#: An import spec: `import "p"`, `import x "p"`, or one line of a group, `x "p"`.
SNIFF_GO_SPEC = re.compile(r"^(?:import ?\(? ?)?(?:([\w.]+) ?)?\$ ?\)?$")
#: A literal that names a test, from where a runner word starts: "test.v", ".test",
#: "go_test", "gotest", "pytest_current_test", but not "latest" or "contest".
SNIFF_GO_TESTY = re.compile(r"(?:^|[^a-z]|go|py)test")
#: An environment variable name with TEST in it ("GO_TEST", "TESTING", "UNIT_TEST"),
#: read in the literal's own case: upper case with underscores is how Go code names one.
SNIFF_GO_TEST_ENV = re.compile(r"^[A-Z0-9_]*TEST[A-Z0-9_]*$")


def _go_word(code, word, prefix=False):
    """`word` in `code` as a whole name: not the tail of an identifier or a selector
    (myos.args is not os.args), and, unless `prefix`, not the head of a longer one."""
    start = code.find(word)
    while start >= 0:
        before = code[start - 1] if start else ""
        end = start + len(word)
        after = code[end] if end < len(code) else ""
        if (not (before.isalnum() or before in "_.")
                and (prefix or not (after.isalnum() or after == "_"))):
            return True
        start = code.find(word, start + 1)
    return False


def _go_ref(code, names, members):
    """Whether `code` reaches one of `members` of a package bound to `names`."""
    for name in names:
        if name == ".":
            if any(_go_word(code, m) for m in members):
                return True
        elif name != "_" and any(_go_word(code, f"{name}.{m}") for m in members):
            return True
    return False


def sniff_go_signals(code, lits, names):
    """(direct, asks_env, says_test) for one Go statement.

    `direct` is a statement that looks at whether a test is running on its own. The
    environment is the one question library code also asks for ordinary reasons
    (configuration), so it counts only beside a test-like literal: `asks_env` and
    `says_test` are the two halves, matched across one top-level declaration by
    sniff_go_statements. `code` is the statement lower-cased with every string literal
    replaced by $ and whitespace collapsed (none around a dot); `lits` its string
    literals as written, with + concatenations joined; `names` maps each package in
    SNIFF_GO_PACKAGES to the names this file binds it to.
    """
    low = [lit.lower() for lit in lits]
    direct = (
        # The flags go test passes and registers: -test.v, -test.run, -test.timeout.
        any(re.search(r"(?:^|-)test\.", lit) for lit in low)
        # The binary go test builds is <pkg>.test (.test.exe on Windows), also readable
        # from /proc/self/exe or /proc/<pid>/cmdline.
        or any(lit.endswith((".test", ".test.exe")) for lit in low)
        or any(re.search(r"/proc/(?:self|thread-self|\d|%|.*(?:exe|cmdline))", lit)
               for lit in low)
        # A stack frame or a file name that only a test has: testing.tRunner,
        # testing.(*T).Run, testing/testing.go, a _test.go file.
        or any(re.search(r"trunner|testing\.\(\*|(?:testing|_test)\.go(?!\w)", lit)
               for lit in low)
        # An environment variable only a runner or CI sets, or one named for tests.
        or any(lit in SNIFF_GO_RUNNER_ENV for lit in low)
        or any(SNIFF_GO_TEST_ENV.match(lit) for lit in lits)
        # The program's own name, arguments and process id (the way into /proc), the
        # flag set they were parsed into (go test parses it before any test runs), and
        # the build record (a test binary's path ends in .test). A library is handed its
        # inputs; it does not read the command line. A CLI or a logger that does is
        # shipped code, in the baseline.
        or _go_ref(code, names["os"], ("args", "executable", "readlink", "getpid",
                                       "getppid"))
        or _go_ref(code, names["syscall"], ("readlink", "getpid", "getppid"))
        or _go_ref(code, names["golang.org/x/sys/unix"], ("readlink", "getpid", "getppid"))
        # The working directory, which go test sets to the package's source directory:
        # asked for, or run as the shell command that prints it, or expanded from $PWD
        # (os.ExpandEnv; os.Expand takes the caller's own mapping, not the environment).
        or _go_ref(code, names["os"], ("getwd",))
        or _go_ref(code, names["syscall"], ("getwd", "getcwd"))
        or _go_ref(code, names["golang.org/x/sys/unix"], ("getwd", "getcwd"))
        or ((_go_ref(code, names["os/exec"], ("command", "commandcontext"))
             or _go_ref(code, names["os"], ("expandenv",)))
            and any(re.search(r"(?:^|[/\s;&|(])pwd(?:$|[\s;&|)])|\$\{?(?:OLD)?PWD\b", lit)
                    for lit in lits))
        or _go_ref(code, names["flag"], ("lookup", "visit", "visitall", "commandline",
                                         "parsed", "args", "arg", "narg", "nflag"))
        or _go_ref(code, names["runtime/debug"], ("readbuildinfo",))
        # Reading the stack at all, this goroutine's or every goroutine's.
        or _go_ref(code, names["runtime"], ("caller", "callers", "callersframes", "stack",
                                            "funcforpc", "goroutineprofile"))
        or _go_ref(code, names["runtime/debug"], ("stack", "printstack"))
        or _go_ref(code, names["runtime/pprof"], ("lookup", "profiles"))
        # The testing package itself, under whatever name the file gave it.
        or any(_go_word(code, name + ".", prefix=True)
               for name in names["testing"] if name not in (".", "_")))
    asks_env = (_go_ref(code, names["os"], ("getenv", "lookupenv", "environ"))
                or _go_ref(code, names["syscall"], ("getenv", "environ")))
    # PWD (and OLDPWD), which go test sets to the package directory, reads like a test
    # word beside an environment read; alone it is a password key as often as not. So
    # does "_=", the $_ entry of os.Environ() (see _go_token_signals).
    says_test = (any(SNIFF_GO_TESTY.search(lit) for lit in low)
                 or any(re.fullmatch(r"(?:OLD)?PWD=?|_=", lit) for lit in lits))
    return direct, asks_env, says_test


def _go_callee(tokens, k, names, table):
    """The index of the ( that opens a call at token k to one of `table` ({package:
    (function, ...)}) under the names this file binds it to, else None."""
    if tokens[k][0] or (k and tokens[k - 1] == (False, ".")):
        return None
    word = tokens[k][1].lower()
    for pkg, funcs in table.items():
        bound = names.get(pkg) or set()
        if (k + 3 < len(tokens) and tokens[k + 1] == (False, ".")
                and tokens[k + 3] == (False, "(") and word in bound - {".", "_"}
                and tokens[k + 2][1].lower() in funcs):
            return k + 3
        if ("." in bound and k + 1 < len(tokens) and tokens[k + 1] == (False, "(")
                and word in funcs):
            return k + 1
    return None


def _go_relative_at(tokens, j, starts, names, local_paths, depth=0):
    """Whether the expression at token j starts with a relative path the source spells:
    a string (or a constant folded to one, `starts`) that does not start with "/", a
    local of the same declaration that was given one (`local_paths`), or a call that only
    joins paths (SNIFF_GO_PATH_BUILDERS) whose first non-empty argument is one of those.
    Join drops an empty element, so filepath.Join("", "x.go") is "x.go" and
    filepath.Join("", p) is p; a call whose every argument is empty (Clean("") is ".")
    is relative too."""
    if j >= len(tokens):
        return False
    if j in starts:
        return any(not v.startswith("/") for v in starts[j])
    if (not tokens[j][0] and tokens[j][1] in local_paths
            and tokens[j + 1:j + 2] not in ([(False, "(")], [(False, ".")], [(False, "[")])):
        return True
    inner = _go_callee(tokens, j, names, SNIFF_GO_PATH_BUILDERS) if depth < 4 else None
    if inner is None:
        return False
    # Each argument, split on the commas at the call's own level.
    args, level = [inner + 1], 0
    for k in range(inner + 1, len(tokens)):
        tok = tokens[k]
        if tok in ((False, "("), (False, "["), (False, "{")):
            level += 1
        elif tok in ((False, ")"), (False, "]"), (False, "}")):
            if level == 0:
                break
            level -= 1
        elif tok == (False, ",") and level == 0:
            args.append(k + 1)
    for a in args:
        if tokens[a:a + 1] == [(True, "")] and tokens[a + 1:a + 2] in (
                [(False, ",")], [(False, ")")]):
            continue
        return _go_relative_at(tokens, a, starts, names, local_paths, depth + 1)
    return True


#: The environment reads, and what the shell puts in $_: the program it started, which
#: under go test is the go command.
SNIFF_GO_ENV_READS = {"os": ("getenv", "lookupenv"), "syscall": ("getenv",)}


def _go_local_paths(statements, known, names):
    """The names one top-level declaration gives a relative path (`p := "x.go"`,
    `var marker = filepath.Join("testdata", n)`), each statement as _go_tokens gives it.
    Locals are folded here only, inside their own declaration: across functions two
    same-named locals would be merged (see sniff_go_statements)."""
    found = set()
    for _ in range(2):
        for tokens in statements:
            declared = tokens[:1] in ([(False, "var")], [(False, "const")])
            toks = tokens[1:] if declared else tokens
            if len(toks) < 3 or toks[0][0] or not re.fullmatch(r"[A-Za-z_]\w*", toks[0][1]):
                continue
            # A definition, `name := v` or `var name [T] = v`. Not a later `name = v`: a
            # default put in one branch (`if f == "" { f = "config.yaml" }`) is how a
            # command line program names its file, and not what a gate looks like. And
            # never the comparison in `name == v`, whose operator arrives as two tokens.
            k = 2 if (declared and not toks[1][0]
                      and re.fullmatch(r"[A-Za-z_]\w*", toks[1][1])) else 1
            if (k + 1 < len(toks) and toks[k + 1] != (False, "=")
                    and toks[k] == ((False, "=") if declared else (False, ":="))):
                starts = {s: v for s, _, v, _ in _go_chains(toks, known)}
                if _go_relative_at(toks, k + 1, starts, names, found):
                    found.add(toks[0][1])
    return found


def _go_token_signals(tokens, known, names, local_paths):
    """Whether one statement, read token by token, looks at where the process runs from:

    - it hands a file system call (SNIFF_GO_PATH_READS) a relative path the source spells
      (_go_relative_at), so os.Stat("x.go"), filepath.Abs("."), os.ReadDir(".") and
      os.Lstat(filepath.Join("testdata", n)) all count, and os.ReadFile(path) does not;
    - or it reads $_ from the environment, os.Getenv("_") with "_" the whole argument,
      since "_" is a separator in every other environment name a program builds."""
    chains = _go_chains(tokens, known)
    starts = {start: vals for start, _, vals, _ in chains}
    ends = {start: end for start, end, _, _ in chains}
    for i in range(len(tokens)):
        k = _go_callee(tokens, i, names, SNIFF_GO_PATH_READS)
        if k is not None and _go_relative_at(tokens, k + 1, starts, names, local_paths):
