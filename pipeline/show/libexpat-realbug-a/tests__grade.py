#!/usr/bin/env python3
"""Grade a real-bug C diagnosis task.

Two halves, neither of which needs a model.

  repair   per bug: its upstream regression test files go into the tree, the tree is
           built and the whole CTest suite runs; the bug is repaired when its own
           fail-to-pass tests pass and no other test in the suite fails. The half is the
           fraction of bugs repaired.
  report   /app/rca.json names the function holding each bug. A site counts when it is
           named and its bug was repaired; precision divides by every entry written.

Threat model, for whoever reviews this grader. The agent never sees this file. The task is
dual-container: this grader runs in its own verifier container, built from tests/Dockerfile,
and /tests - this file, the answer key, the hidden test files and the suite archive - exists
only in that image, root-owned. What reaches this container from the agent is the collected
/logs/artifacts and nothing else: worktree.tgz, out of which adopt_agent_worktree takes only
C source files under the declared source roots and never a test path, and rca.json, read
before any of that source runs. The repository's suite and every bug's hidden test files are
root-owned in the tree and written by root; every build and suite run drops to the agent
account; every process of that account is killed before root touches the tree again. Agent
source runs inside the test programs, so: a run whose report does not carry the planted
/bin/sh canaries as failures is not believed, a run whose stdout and report disagree is not
believed, and agent C source that adds a process-control call, a pre-main hook or a
test-context probe the shipped and fixed trees did not have voids every bug's repair.
"""

from __future__ import annotations

import errno
import json
import os
import pwd
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import hashlib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from types import ModuleType

# See build_task.GRADER: a trusted PATH before any subprocess starts.
os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin"

ctest = ModuleType("ctest")
sys.modules["ctest"] = ctest
exec("\nimport re\nimport shlex\nfrom dataclasses import dataclass, field\n\n#: How to rebuild a configured tree, per `environment.build_system` in the artifact.\n#: Only the two that drive CTest. The pool's `make` (205) and `autotools` (132)\n#: repositories overwhelmingly run their suites through `make check` rather than CTest,\n#: so they need their own runner rather than a rebuild spelling bolted on here.\n_REBUILD = {\n    \"cmake\": \"cmake --build {dir} -j 8\",\n    \"meson\": \"meson compile -C {dir}\",\n}\n_TEST_DIR = re.compile(r\"--test-dir[= ]+(\\S+)\")\n#: A trailing re-raise the pool records on some commands: `; rc=$?; (exit $rc)`. It only\n#: hands the suite's own exit code back, so dropping it changes nothing a run observes \u2014\n#: and dropping it is what lets a command that is otherwise a bare `ctest` clear the\n#: metacharacter guard.\n_RC_WRAPPER = re.compile(r\"\\s*;\\s*rc=\\$\\?\\s*;\\s*\\(\\s*exit \\$rc\\s*\\)\\s*$\")\n#: `cd <dir> && ctest ...`: a build dir the command steps into before running the suite.\n#: The dir is a safe path token ONLY -- word chars, `.`, `/`, `-` -- so a target carrying\n#: anything a shell would act on (`$(...)`, spaces, quotes) never matches and is left for\n#: `vet_decision` to refuse. Traversal is refused separately, on the matched dir. `ctest`\n#: must be a whole token (whitespace or end after it): `\\b` also matched `ctest-foo` and\n#: `ctest.sh`, which are DIFFERENT commands, and would have been corrupted into a ctest call.\n_CD_CTEST = re.compile(r\"^cd\\s+(?P<dir>[\\w./-]+)\\s+&&\\s+(?P<ctest>ctest(?:\\s+.*)?)$\", re.S)\n_OUTPUT_JUNIT = re.compile(r\"\\s*--output-junit[= ]+\\S+\")\n#: A CTest test name cannot contain a newline, so no registered test can match this.\n#: `-R` with it is how a run is asked to execute nothing at all.\nSELECT_NOTHING = \"^$a^\"\n#: `100% tests passed, 0 tests failed out of 22` \u2014 CTest prints it on every completed\n#: run, passing or failing, and never when the build died first.\n_SUMMARY = re.compile(r\"(\\d+)% tests passed, (\\d+) tests failed out of (\\d+)\")\n#: The heading over the block CTest prints after a failing run, and the shape of one of\n#: its lines: \"\\t  1 - cjson_add (Failed)\".\n#:\n#: THE HEADING IS PART OF THE READER, not decoration. CTest prints a SECOND block with\n#: identical line shapes -- \"The following tests did not run:\", holding the skipped and\n#: disabled ones -- and it prints it first, so a match over the whole output reads every\n#: skipped test as a failure. That is not a small error where this is used: the grader\n#: compares what a run SAID failed with what its report accounts for, so one honestly\n#: skipped test would have it declare the runner a liar and score a correct repair zero.\n#: Scoping also keeps a failing test's own stdout out of the answer, which\n#: `--output-on-failure` dumps into the same stream.\n_FAILED_HEADING = \"The following tests FAILED:\"\n#: The NAME runs to the final parenthesised status, not to the first space. A CTest\n#: name may contain them -- `add_test(NAME \"json round trip\" ...)` is legal CMake and\n#: CTest prints it verbatim here. Matching a single non-space run did not truncate such\n#: a name, it dropped the line outright, because the pattern then wanted `(` where the\n#: rest of the name stood, and the fault's break vanished with it.\n_FAILED_LINE = re.compile(r\"^\\s*\\d+\\s*-\\s*(.+?)\\s*\\([^()]*\\)\\s*$\", re.M)\n#: Where CTest looks when the command names no `--test-dir`: the directory it is run in,\n#: which for these commands is the repository root. An in-source build is common enough\n#: to be the reason this is not `build` -- akheron/jansson at 851a2145 configures with\n#: `cmake .` and records `ctest --output-junit ... -j 8`, and in its own pool image\n#: `cmake --build build` answers \"Error: /workspace/repo/build is not a directory\".\nDEFAULT_BUILD_DIR = \".\"\n\n\ndef build_dir(cmd: str) -> str:\n    \"\"\"The tree CTest reads, which is the tree that must be rebuilt.\n\n    `--test-dir` when the command names one, and otherwise the directory the command runs\n    in, because that is where CTest looks for CTestTestfile.cmake. Guessing `build` for\n    the second case compiled nothing at all on an in-source build, and a command that\n    compiles nothing mines faults that are all dropped for breaking nothing.\n\n    The fallback is only ever right because of what the command is allowed to BE. A\n    recorded command has to start with `ctest` (`lang.LANGS[\"c\"].cmd_prefix`, enforced by\n    `prebuild.vet_decision` before this is called), so it runs in the working directory\n    the stage sets, which is the repository root. A command shaped `cd build && ctest ...`\n    would resolve here to the root and be wrong - and it does not reach this function in\n    that shape, because `normalize` has already folded its `cd build` into `--test-dir\n    build` (or, failing that, `vet_decision` refused it for not starting with `ctest`).\n    Downstream, a build directory resolved wrongly\n    anyway is caught before a task ships: the canary is planted into the CTestTestfile.cmake\n    at this path, and `canary_was_planted` refuses a grading run that found none.\n    \"\"\"\n    m = _TEST_DIR.search(cmd)\n    return m.group(1) if m else DEFAULT_BUILD_DIR\n\n\ndef normalize(cmd: str) -> str:\n    \"\"\"Canonicalize the two benign non-bare-`ctest` shapes the pool records into the bare\n    `ctest [--test-dir <dir>] ...` form `vet_decision` accepts, and leave everything else\n    verbatim.\n\n    Two transforms, no others: strip a trailing `; rc=$?; (exit $rc)` re-raise, and fold a\n    leading `cd <safe-dir> &&` into `--test-dir <dir>` (a directory CTest reads the same\n    way it reads the working directory it would have been `cd`'d into). Anything that is\n    not exactly one of these -- an awk pipeline, a redirect, a `cd` into an unsafe or\n    traversing target -- is returned unchanged, so the metacharacter guard downstream\n    still refuses it. This never launders an injection: the `cd` target must be a bare\n    relative path with no `..` and no shell metacharacters, or the rewrite does not fire.\n    \"\"\"\n    s = _RC_WRAPPER.sub(\"\", cmd.strip()).strip()\n    m = _CD_CTEST.match(s)\n    if m:\n        d, rest = m.group(\"dir\"), m.group(\"ctest\")\n        # Fold only a repo-relative dir into a command that names no --test-dir of its own.\n        # An absolute dir (would point --test-dir outside the tree), a traversal, or a\n        # command that already carries --test-dir (dropping the cd would change which tree\n        # CTest reads) is left verbatim, so vet_decision refuses the `cd ...` form.\n        if (not d.startswith(\"/\") and \"..\" not in d.split(\"/\")\n                and not _TEST_DIR.search(rest)):\n            s = rest.replace(\"ctest\", f\"ctest --test-dir {d}\", 1)\n    return s\n\n\ndef with_build(cmd: str, build_system: str | None) -> str | None:\n    \"\"\"`cmd` with its tree rebuilt first, or None when there is no known rebuild.\n\n    None is a refusal, not a fallback. Returning `cmd` unwrapped would mine a repository\n    whose faults never compile, and every one of them would be dropped for breaking\n    nothing only after a full suite run has been paid for.\n    \"\"\"\n    spelling = _REBUILD.get((build_system or \"\").strip().lower())\n    if spelling is None:\n        return None\n    build = spelling.format(dir=build_dir(cmd))\n    # Config authoring can run twice on a resumed repository. Building twice would be\n    # merely wasteful; changing the command would move the hash the task is built\n    # against, which is not.\n    return cmd if cmd.startswith(build + \" &&\") else f\"{build} && {cmd}\"\n\n\n@dataclass\nclass Run:\n    \"\"\"One CTest run, as the mining and grading paths need to read it.\"\"\"\n    ran: bool = False           # the summary line was printed, so the suite completed\n    build_failed: bool = False  # it was not, so compilation died before CTest started\n    failed: set[str] = field(default_factory=set)\n    total: int = 0\n\n\ndef parse_output(text: str) -> Run:\n    \"\"\"Read one run's stdout. `ran` and `failed` are deliberately separate: a build\n    failure has no failing tests and is not a green suite.\"\"\"\n    m = _SUMMARY.search(text)\n    if m is None:\n        return Run(ran=False, build_failed=True)\n    _, heading, block = text.partition(_FAILED_HEADING)\n    failed = set(_FAILED_LINE.findall(block)) if heading else set()\n    return Run(ran=True, build_failed=False, failed=failed, total=int(m.group(3)))\n\n\ndef with_report(cmd: str, path: str) -> str:\n    \"\"\"`cmd` writing its JUnit report to `path`.\n\n    The recorded command writes into the worktree, which the agent can reach; the grader\n    reads from a directory made after the run exited. The existing flag is REPLACED\n    rather than joined by a second one, because CTest takes the last `--output-junit` it\n    is given and a stale first one would leave a readable report at the agent's path.\n    \"\"\"\n    stripped = _OUTPUT_JUNIT.sub(\"\", cmd)\n    return f\"{stripped} --output-junit {path}\"\n\n\ndef select(cmd: str, names: list[str] | tuple[str, ...]) -> str:\n    \"\"\"`cmd` restricted to exactly `names`, or to nothing when `names` is empty.\n\n    `-R` is a regex over test names, so the names are escaped and anchored: unanchored,\n    `parse_value` would drag in `parse_value_extra` and the site would be scored on a\n    test it never named.\n    \"\"\"\n    pattern = (f\"^({'|'.join(re.escape(n) for n in names)})$\" if names\n               else SELECT_NOTHING)\n    return f\"{cmd} -R {shlex.quote(pattern)}\"\n\n\n_IDENT_END = re.compile(r\"[A-Za-z_]\\w*$\")\n#: Keywords that take a parenthesised head and a braced body but are not functions.\n_NOT_A_FUNCTION = frozenset({\"if\", \"for\", \"while\", \"switch\", \"catch\", \"return\",\n                             \"sizeof\", \"do\", \"else\"})\n\n\ndef _blanked(src: str) -> str:\n    \"\"\"`src` with comment, string and char-literal CONTENTS replaced by spaces.\n\n    Length and line structure are preserved, so every offset still lines up with the\n    original. Without this a lone brace inside a string -- cJSON.c prints `{` -- opens a\n    body that never closes, and every function after it gets the wrong span.\n    \"\"\"\n    out = list(src)\n    i, n = 0, len(src)\n    while i < n:\n        two = src[i:i + 2]\n        if two == \"/*\":\n            j = src.find(\"*/\", i + 2)\n            j = n if j < 0 else j + 2\n            for k in range(i, j):\n                if out[k] != \"\\n\":\n                    out[k] = \" \"\n            i = j\n        elif two == \"//\":\n            j = src.find(\"\\n\", i)\n            j = n if j < 0 else j\n            for k in range(i, j):\n                out[k] = \" \"\n            i = j\n        elif src[i] in \"\\\"'\":\n            quote, j = src[i], i + 1\n            while j < n and src[j] != quote:\n                j += 2 if src[j] == \"\\\\\" else 1\n            for k in range(i + 1, min(j, n)):\n                if out[k] != \"\\n\":\n                    out[k] = \" \"\n            i = min(j + 1, n)\n        else:\n            i += 1\n    return \"\".join(out)\n\n\ndef _preprocessor_lines(src: str) -> set[int]:\n    \"\"\"0-based indices of lines belonging to a preprocessor directive, continuations\n    included. `#define NOISY(x) do { ... } while (0)` has a name, a parameter list and\n    braces, and is not a function.\"\"\"\n    out: set[int] = set()\n    carry = False\n    for i, line in enumerate(src.splitlines()):\n        if carry or line.lstrip().startswith(\"#\"):\n            out.add(i)\n        carry = line.rstrip().endswith(\"\\\\\")\n    return out\n\n\ndef _name_before(blank: str, brace: int) -> tuple[int, int] | None:\n    \"\"\"(start, end) of the function name whose body opens at `brace`, or None.\n\n    Read BACKWARDS from the brace, which is the only way to read it accurately. Scanning\n    forward for something shaped like a signature is ambiguous: a parameter list may not\n    contain `;{}` but it may contain anything else, so a forward match happily spans from\n    an earlier `while (` across newlines to the real signature's closing paren and reports\n    `while`. Backwards there is no choice to make -- the `)` before the brace closes the\n    parameter list, and the identifier before its `(` is the name. It also reads through\n    a decorating macro: `CJSON_PUBLIC(cJSON *) cJSON_Parse(const char *value) {` gives\n    `cJSON_Parse`, where a forward scan gives `CJSON_PUBLIC`.\n    \"\"\"\n    def back_over_parens(k: int) -> int:\n        \"\"\"Index of the `(` matching the `)` at k, or -1.\"\"\"\n        depth = 0\n        while k >= 0:\n            if blank[k] == \")\":\n                depth += 1\n            elif blank[k] == \"(\":\n                depth -= 1\n                if depth == 0:\n                    return k\n            k -= 1\n        return -1\n\n    j = brace - 1\n    while j >= 0 and blank[j].isspace():\n        j -= 1\n    if j < 0 or blank[j] != \")\":\n        return None                      # a struct body, an initialiser, a bare block\n    j = back_over_parens(j)\n    if j < 0:\n        return None\n    head = blank[:j].rstrip()\n    m = _IDENT_END.search(head)\n    if m is not None:\n        return m.start(), m.end()\n    # No identifier before the parameter list means a SECOND list sits there: the name\n    # is wrapped in a macro, as `H3Error H3_EXPORT(cellToVertex)(H3Index cell, ...)`.\n    # uber/h3 writes nearly every public function this way, and reading only the outer\n    # list found no name at all, so the grader could not locate the function and the\n    # build was refused. Step back over the macro's own parentheses and take what is\n    # inside them, which is the real name.\n    if head.endswith(\")\"):\n        k = back_over_parens(len(head) - 1)\n        if k >= 0:\n            inner = head[k + 1:len(head) - 1].strip()\n            if inner and _IDENT_END.fullmatch(inner):\n                start = head.rfind(inner, k, len(head) - 1)\n                return start, start + len(inner)\n    return None\n\n\ndef c_functions(src: str) -> list[tuple[str, int, int]]:\n    \"\"\"(name, first line, last line) for every function DEFINITION, 1-based inclusive.\n\n    A brace scanner rather than a parser: the grader runs inside the agent's image,\n    which has python3 and no tree-sitter, so this has to hold up on its own. It reads\n    definitions only -- a declaration ends in `;` and a struct body has no parameter\n    list -- and it ignores braces inside comments, strings, chars and macros.\n    \"\"\"\n    blank = _blanked(src)\n    skip = _preprocessor_lines(src)\n    starts = [0]\n    for line in src.split(\"\\n\")[:-1]:\n        starts.append(starts[-1] + len(line) + 1)\n\n    def line_of(offset: int) -> int:\n        lo, hi = 0, len(starts) - 1\n        while lo < hi:\n            mid = (lo + hi + 1) // 2\n            if starts[mid] <= offset:\n                lo = mid\n            else:\n                hi = mid - 1\n        return lo\n\n    out: list[tuple[str, int, int]] = []\n    depth, i, n = 0, 0, len(blank)\n    while i < n:\n        ch = blank[i]\n        if ch == \"}\":\n            depth = max(0, depth - 1)\n            i += 1\n            continue\n        if ch != \"{\":\n            i += 1\n            continue\n        if depth > 0 or line_of(i) in skip:\n            depth += 1\n            i += 1\n            continue\n        named = _name_before(blank, i)\n        # The name is taken from the ORIGINAL text: the head was only blanked to keep\n        # offsets aligned, and an identifier is never inside a string or comment here.\n        if named is None:\n            depth += 1\n            i += 1\n            continue\n        at, end = named\n        name = src[at:end]\n        if name in _NOT_A_FUNCTION:\n            depth += 1\n            i += 1\n            continue\n        start = line_of(at)\n        j, inner = i, 0\n        while j < n:\n            if blank[j] == \"{\":\n                inner += 1\n            elif blank[j] == \"}\":\n                inner -= 1\n                if inner == 0:\n                    break\n            j += 1\n        out.append((name, start + 1, line_of(min(j, n - 1)) + 1))\n        i = j + 1\n    return out\n\n\ndef function_text(src: str, name: str) -> str | None:\n    \"\"\"One function's source, whitespace-normalised, or None when it is not there.\n\n    Normalised because the grader compares a repaired function with the original and\n    the comparison must not turn on indentation the agent happened to reflow.\n    \"\"\"\n    span = next(((a, b) for fn, a, b in c_functions(src) if fn == name), None)\n    if span is None:\n        return None\n    body = \"\\n\".join(src.splitlines()[span[0] - 1:span[1]])\n    return \" \".join(body.split())\n\n\n#: The file CMake generates in a configured build tree listing that directory's tests.\n#: CTest reads it at run time, so appending to it registers a test without touching\n#: CMakeLists or re-running cmake -- and the entry survives `cmake --build`.\nTEST_LIST = \"CTestTestfile.cmake\"\n_PLAIN_NAME = re.compile(r\"^[A-Za-z_]\\w*$\")\n\n\ndef canary_plant(passing: list[str] | tuple[str, ...],\n                 failing: list[str] | tuple[str, ...] = ()) -> str:\n    \"\"\"Lines to append to a build tree's generated test list, planting the grader's own\n    tests among the repository's.\n\n    The canary is what makes a report's silence meaningful: a run that reports no\n    failures has either passed the suite or never run it, and a planted test that must\n    appear tells the two apart. On Go it is a `_test.go` per breaking package; here it\n    is two shell commands CTest runs like any other test, reported in the JUnit output\n    under their own names.\n\n    Names must be plain identifiers, because this is appended to a cmake file as code.\n    \"\"\"\n    for name in (*passing, *failing):\n        if not _PLAIN_NAME.match(name):\n            raise ValueError(f\"canary name is not a plain identifier: {name!r}\")\n    lines = [f'add_test({name} \"/bin/sh\" \"-c\" \"exit 0\")' for name in passing]\n    lines += [f'add_test({name} \"/bin/sh\" \"-c\" \"exit 1\")' for name in failing]\n    return \"\".join(line + \"\\n\" for line in lines)\n", ctest.__dict__)

TESTS = Path("/tests")
ARTIFACTS = Path("/logs/artifacts")
OUT = Path("/logs/verifier")

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testdata"}
COLLECTION_CONFIG_NAMES = {
    "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini",
    "pytest.cfg", ".pytest.ini", "sitecustomize.py", "usercustomize.py",
}
IMPORT_SHADOW_NAMES = {
    "pytest.py", "py.py", "_pytest.py", "pluggy.py", "coverage.py",
    "unittest.py", "os.py", "sys.py", "json.py", "subprocess.py", "re.py",
}
TEST_FILE_RE = re.compile(
    r"(?:^test_.+|.+_test|.+\.(?:test|spec)|conftest|tests?)"
    r"\.(?:py|js|jsx|ts|tsx|mjs|cjs|go|rs|rb|java|kt|kts|c|cc|cpp|cxx|h|hh|hpp)$",
    re.IGNORECASE,
)
C_TEST_FILE_RE = re.compile(r"test[A-Z0-9_-][^/]*\.(?:c|cc|cpp|cxx|h|hh|hpp)")

RAW_KEY = (TESTS / "answer_key.json").read_bytes()
key = json.loads(RAW_KEY)
if key.get("mode") != "realbug":
    raise SystemExit("this grader grades real-bug tasks only; the answer key says "
                     f"mode={key.get('mode')!r}")
APP = Path(key["workdir"])
RUN_AS = key.get("run_tests_as") or "agent"
weights = key["weights"]

# The C process-control and test-context scan, from build_task.CSNIFF_SRC, widened for
# real-bug tasks by REALBUG_SNIFF_SRC (the build records its baseline with the same code).


# THE C TEST-CONTEXT / PROCESS-CONTROL CHECK. A C fault site is compiled into the test
# programs that exercise it, so agent source linked into those programs runs inside the
# test process and can end it before its assertions, or branch on whether a test is
# running. A global constructor that exits, an exit() in an init function every test
# calls, or `if (getenv("CTEST...")) return;` all make the suite report passes the repair
# did not earn, and the /bin/sh canary (which runs no repository code) does not notice. So
# the agent's own C changes are read for calls and attributes a repair has no reason to
# add, the same way SNIFF_SRC reads Python and the Go scanner reads Go: a hit voids the
# runner route for every site, as a caught probe does.
#
# ONE SOURCE FOR BOTH SIDES, spliced into tests/grade.py and executed by the build, which
# records what the shipped tree already holds (`c_sniff_baseline` in the answer key) so a
# repository that legitimately registers a constructor or calls exit() in its own code is
# not charged for it: only occurrences the shipped copy did not have count. Counted, not
# set-compared, so a call copied into a new function is caught even when an identical line
# exists elsewhere.
#
# WHAT IT DOES NOT CHASE. A payload written to evade a scanner it knows is there - a
# backslash-newline split through a token, a `#define BYE exit` alias, `(exit)(0)`, a call
# through a function pointer, an inline-asm syscall - is deliberate obfuscation, which only
# makes sense once you know this exists, and the Reward Hack Post-Eval review is the
# backstop for it. This catches the calls and attributes a solver writes in the natural
# way; the robust out-of-process answer is the C behavioural probes, a separate follow-up.

#: The largest C file the scan reads. A larger one is not parsed (two passes over every
#: character is linear but not free); the grader charges it unless it is byte for byte the
#: file the image shipped, the way the Go scan treats a file over GO_SNIFF_LIMIT.
CSNIFF_C_LIMIT = 2_000_000

#: Process-control and non-local-jump calls a one-line behaviour repair never needs to
#: add, with the __builtin_ spelling of each folded in. Matched case-sensitively as a
#: call: the token (optionally __builtin_-prefixed), then `(`, not preceded by an
#: identifier character. The exec* family and syscall end or replace the process too.
CSNIFF_CALLS = ("exit", "_exit", "_Exit", "quick_exit", "abort", "atexit",
                "at_quick_exit", "pthread_exit", "thrd_exit", "signal", "sigaction",
                "raise", "kill", "pthread_kill", "tgkill", "setjmp", "_setjmp",
                "sigsetjmp", "longjmp", "_longjmp", "siglongjmp", "syscall",
                "execl", "execlp", "execle", "execv", "execvp", "execvpe", "execve",
                "__builtin_trap")
CSNIFF_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:__builtin_)?(?:" + "|".join(sorted(CSNIFF_CALLS,
                                                             key=len, reverse=True))
    + r")\s*\(")
#: A pre-main hook: the GNU __attribute__((constructor/destructor)) in either spelling, and
#: the C23 [[gnu::constructor]] form. Case-sensitive; the attribute context is required so
#: an ordinary identifier called `constructor` is not a hit.
CSNIFF_ATTR_RE = re.compile(
    r"(?:attribute__\s*\(\((?:[^()]|\([^()]*\))*?(?<![A-Za-z0-9_])_*(?:constructor|destructor)"
    r"_*(?![A-Za-z0-9_])|\[\[[^]]*(?:constructor|destructor))")
#: Init-array / constructor sections, named directly. No `section(` is required: a
#: `.init_array` reference in agent-added C is a pre-main hook however it is spelled.
CSNIFF_SECTIONS = (".init_array", ".preinit_array", ".ctors")
#: Bare identifiers (no call) whose presence is itself the signal: the running program's
#: own name, which test-context code reads to recognise a test binary. Matched as a whole
#: identifier, so a longer name that merely contains one (program_invocation_name_extra) is
#: not a hit.
CSNIFF_NAMES = ("program_invocation_name", "program_invocation_short_name", "__progname")
#: Words that, beside a getenv call or argv[0] in the same statement, say the code is looking
#: for a test harness rather than doing the repository's own work. Matched in the
#: lower-cased statement text, literals included.
CSNIFF_TEST_WORDS = ("ctest", "pytest", "unittest", "gtest", "_test", "test_",
                     "testing", "/proc/self")
CSNIFF_GETENV = ("getenv", "secure_getenv", "getenv_s")


def _c_strip_comments(text):
    """Two strings the same length as `text`: `code`, with every /* */ and // comment and
    every string and char literal's CONTENT blanked to spaces (the quotes kept), and
    `full`, the same but with the literal content kept. Equal length so one set of split
    offsets slices both, and a ; { } or newline inside a comment or a string becomes a
    space in `code` and so never splits a statement.

    A string or char literal ENDS AT A NEWLINE as well as at its closing quote. A C literal
    does not cross a raw newline, so an unbalanced quote - a stray `'` in dead code, an
    apostrophe in a comment the scan has already removed - can blank at most the rest of
    its own line rather than the rest of the file."""
    code, full, i, n = [], [], 0, len(text)
    in_block = in_line = in_str = in_chr = esc = False
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if in_block:
            keep = c if c == "\n" else " "
            code.append(keep); full.append(keep)
            if two == "*/":
                code.append(" "); full.append(" "); i += 2; in_block = False; continue
            i += 1; continue
        if in_line:
            keep = c if c == "\n" else " "
            code.append(keep); full.append(keep)
            if c == "\n":
                in_line = False
            i += 1; continue
        if in_str or in_chr:
            if c == "\n" and not esc:
                # A literal does not cross a raw newline; close it here so an unbalanced
                # quote cannot blank the rest of the file.
                code.append("\n"); full.append("\n"); in_str = in_chr = esc = False
                i += 1; continue
            q = '"' if in_str else "'"
            if esc:
                code.append(" "); full.append(c); esc = False; i += 1; continue
            if c == "\\":
                code.append(" "); full.append(c); esc = True; i += 1; continue
            if c == q:
                code.append(q); full.append(q); in_str = in_chr = False; i += 1; continue
            code.append(" "); full.append(c); i += 1; continue
        if two == "/*":
            code.append("  "); full.append("  "); i += 2; in_block = True; continue
        if two == "//":
            code.append("  "); full.append("  "); i += 2; in_line = True; continue
        if c == '"':
            in_str = True; code.append('"'); full.append('"'); i += 1; continue
        if c == "'":
            in_chr = True; code.append("'"); full.append("'"); i += 1; continue
        code.append(c); full.append(c); i += 1
    return "".join(code), "".join(full)


def _c_statements(text):
    """(code, full) pairs, one per C statement. A statement ends at ; { } or a newline, so
    a preprocessor directive is its own piece and a flagged token stays on one piece; the
    two strings are sliced by the same offsets, which `_c_strip_comments` keeps aligned."""
    code, full = _c_strip_comments(text)
    out, start = [], 0
    for m in re.finditer(r"[;{}\n]", code):
        out.append((code[start:m.start()], full[start:m.start()])); start = m.end()
    out.append((code[start:], full[start:]))
    return out


def _c_squeeze(s):
    """`s` with whitespace and quotes removed, CASE KEPT: C is case-sensitive, so `exit`
    and an enum `EXIT` are different, and `_Exit` is a real spelling."""
    for ch in " \t\r\n\\\"'`":
        s = s.replace(ch, "")
    return s


def c_sniff_statements(text):
    """Normalised C statements that end or redirect the process, register a pre-main hook,
    or look at whether a test is running, one entry per occurrence. The returned form is
    case-folded so two spellings of one statement compare equal across the baseline."""
    found = []
    for cseg, fseg in _c_statements(text):
        code = _c_squeeze(cseg)                 # case-sensitive: names, getenv
        if not code:
            continue
        # Calls and attributes are matched on whitespace COLLAPSED, not removed, so the
        # identifier boundary survives `else exit(0)` and `return raise(SIGTERM)`.
        spaced = re.sub(r"\s+", " ", cseg)
        low = code.lower()                      # case-insensitive: section/getenv/name text
        fll = _c_squeeze(fseg).lower()          # literal text, for getenv args and paths
        hit = (bool(CSNIFF_CALL_RE.search(spaced))
               or bool(CSNIFF_ATTR_RE.search(spaced))
               or any(sec in low or sec in fll for sec in CSNIFF_SECTIONS)
               or any(re.search(r"(?<![A-Za-z0-9_])" + n + r"(?![A-Za-z0-9_])", spaced)
                      for n in CSNIFF_NAMES)
               or "/proc/self" in fll
               or (any(g + "(" in code for g in CSNIFF_GETENV)
                   and any(w in fll for w in CSNIFF_TEST_WORDS))
               or ("argv[0]" in low and any(w in fll for w in CSNIFF_TEST_WORDS)))
        if hit:
            found.append(low)
    return found


def c_sniff_file(rel):
    """Whether `rel` is non-test C source the scan reads: a .c/.h/.cc/... that `c_test_path`
    does not call test material. A test file comes back pristine from the archive, not from
    the agent, so a change in one is not the agent's, and its own exit()/main is not charged.
    `c_test_path` is the same rule the build hid the suite with (test_grader_c pins that)."""
    return bool(re.search(r"\.(c|cc|cpp|cxx|h|hh|hpp)$", rel)) and not c_test_path(rel)


def c_sniff_tree(root, rels):
    """{relative path: [normalised statements]} over the non-test C files in `rels`, each
    read once. A file over CSNIFF_C_LIMIT is not parsed here; the caller charges it."""
    import os as _os
    out = {}
    for rel in rels:
        if not c_sniff_file(rel):
            continue
        path = _os.path.join(root, rel)
        try:
            if _os.path.getsize(path) > CSNIFF_C_LIMIT:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                hits = c_sniff_statements(fh.read())
        except OSError:
            continue
        if hits:
            out[rel] = hits
    return out


REALBUG_EXTRA_CALLS = ("fexecve", "execveat", "posix_spawn", "posix_spawnp", "system",
                       "popen", "fork", "vfork", "clone", "clone3", "daemon", "setsid",
                       "on_exit", "dlopen", "dlsym", "dlvsym", "ptrace", "prctl",
                       # Reading a value the verifier hid from the agent (for example the
                       # per-run completion nonce) needs one of these; agent library source
                       # under a source root has no reason to open a file, read the
                       # environment or drop to a raw syscall, so each counts against the
                       # per-file baseline the shipped and gold trees set.
                       "open", "openat", "openat2", "open64", "creat", "fopen", "fopen64",
                       "freopen", "freopen64", "fdopen", "opendir", "fdopendir",
                       "getenv", "secure_getenv", "mmap", "mmap64", "readlink",
                       "readlinkat", "pread", "pread64", "asm", "__asm__")
REALBUG_EXTRA_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:__builtin_)?(?:"
    + "|".join(sorted(REALBUG_EXTRA_CALLS, key=len, reverse=True)) + r")\s*\(")


def realbug_sniff_statements(text):
    found = list(c_sniff_statements(text))
    already = Counter(found)
    for cseg, _ in _c_statements(text):
        if not REALBUG_EXTRA_RE.search(re.sub(r"\s+", " ", cseg)):
            continue
        low = _c_squeeze(cseg).lower()
        if already[low] > 0:
            already[low] -= 1
        else:
            found.append(low)
    return found


def realbug_sniff_tree(root, rels):
    import os as _os
    out = {}
    for rel in rels:
        if not c_sniff_file(rel):
            continue
        path = _os.path.join(root, rel)
        try:
            if _os.path.getsize(path) > CSNIFF_C_LIMIT:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                hits = realbug_sniff_statements(fh.read())
        except OSError:
            continue
        if hits:
            out[rel] = hits
    return out


def c_test_dir(part: str) -> bool:
    return part.lower().startswith("test")


def c_test_path(rel: str) -> bool:
    """Whether a C path is test material by the rules the build hid the suite with."""
    parts = rel.split("/")
    return (any(part.lower() in TEST_DIR_NAMES or c_test_dir(part) for part in parts[:-1])
            or bool(TEST_FILE_RE.fullmatch(parts[-1]) or C_TEST_FILE_RE.fullmatch(parts[-1])))


def _neutralize_git_config(git_dir: Path) -> bool:
    """Take back the CONTENT of .git/config before root git runs in the tree.

    grade.py runs git as root - ls-tree and checkout of paths for restore_repo_tests,
    update-index for canary_plant - and git executes whatever its configuration names:
    core.fsmonitor on an index refresh, a filter.<name>.smudge driver on a checkout,
    core.hooksPath or core.sshCommand elsewhere. In the dual-container format the .git here
    is the verifier image's own, built by `git init` in tests/Dockerfile and never the
    agent's (the collect command tars the tree without it), so this only drops the image's
    own user and pager keys; the seal below still re-owns it, because the image chowns the
    workdir to RUN_AS and every suite run executes the agent's adopted source as that
    account. On a legacy shared-verifier task the tree's .git
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

    In the dual-container format /logs/verifier is Harbor's fresh mount and nothing of the
    agent phase is in it, but the seal still matters there: every suite run executes the
    agent's adopted source as RUN_AS inside this container, and that source must not read
    the key or write the reward. On a legacy shared-verifier task /logs is SHARED WITH THE
    AGENT CONTAINER, so /logs/verifier can already exist when grading starts, created by
    the agent phase and owned by the agent, with a reward.txt sitting in it. test.sh's
    `mkdir -p` accepts that directory as it finds it. Taking ownership and closing it to
    700 root here means the reward this run computes is written somewhere the tree under
    test cannot read back, cannot pre-create and cannot rewrite from anything it forks and
    leaves running. The adversarial suite's "write the reward file from the agent container" case is exactly
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


def open_artifact(name: str) -> tuple[int | None, str]:
    """A read descriptor on /logs/artifacts/<name>, or None and the reason there is none.

    EVERYTHING UNDER /logs/artifacts IS THE AGENT'S, and in the dual-container format it
    arrives here by upload, which keeps a symlink a symlink. Root follows one on open, so
    `rca.json -> /tests/answer_key.json` would hand the answer key back as the agent's own
    report, and a worktree.tgz pointing anywhere would be unpacked from there. So the name
    is opened with O_NOFOLLOW, the directory itself must not be a link, and only a regular
    file is read: O_NONBLOCK keeps a FIFO by that name from hanging grading until the
    verifier is killed. Nothing of the agent's has run in this container yet when this is
    called, so the answer cannot change between the check and the read.
    """
    path = ARTIFACTS / name
    if ARTIFACTS.is_symlink():
        return None, f"{ARTIFACTS} is a symlink"
    if not path.is_symlink() and not path.exists():
        return None, "missing"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return None, (f"{name} could not be opened without following a link: "
                      f"{exc.__class__.__name__}")
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        return None, f"{name} is not a regular file"
    return fd, ""


def read_report() -> object:
    """Read the agent's report before anything it wrote is executed.

    Taking the snapshot first means source that runs during the test cannot rewrite the
    report to match the answer key. A report that is a link or not a regular file reads as
    invalid, which scores the report half zero like any other unreadable report.
    """
    fd, why = open_artifact("rca.json")
    if fd is None:
        return None if why == "missing" else "invalid"
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read()
    try:
        # read_bytes, not read_text. read_text decodes as UTF-8 before json sees anything,
        # so one stray byte raises UnicodeDecodeError, which is not a JSONDecodeError and
        # was not caught. This runs at module top level before either subscore exists, so
        # the grader died and test.sh's crash trap wrote -1 into reward.txt: an agent that
        # repaired everything and wrote a report with one mis-encoded byte scored BELOW
        # the 0.0 a no-op earns. json.loads accepts bytes and handles a byte order mark.
        # The report half already treats malformed JSON as "invalid" and scores that half
        # zero, so this path was inconsistent rather than intended.
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return "invalid"


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
    # The budget is kept on the monotonic clock: a wall-clock step must neither stretch
    # nor cut a run. `started` stays on the wall clock for the elapsed figure below.
    deadline = time.monotonic() + RUN_BUDGET["seconds"]
    timed_out = False
    try:
        # The leader's exit is observed WITHOUT reaping it (WNOWAIT): its pid names the
        # process group, and a reaped pid can be handed to a new process before the group
        # below is killed. A zombie keeps its pid. The reaping wait is in the cleanup,
        # after the kill.
        while os.waitid(os.P_PID, p.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is None:
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.05)
    final