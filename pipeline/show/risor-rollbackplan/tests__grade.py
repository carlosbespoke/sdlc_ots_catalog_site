"""R/L/F grader for a format-1 Go RCA task (docs/task-format.md). Copy to tests/grade.py.

    python3 -I -S -B /tests/grade.py --prepare     # verifier image build (tests/Dockerfile)
    python3 -I -S -B /tests/grade.py /workdir      # grading (tests/test.sh)

Everything task-specific comes from tests/meta.json and tests/rca-task.json; the only code a task
may change is the block between the `rca:hooks` markers (`rca check` compares the rest with this
template).

Trust model: as templates/grade_python.py. The parent runs as root (with -B: no /tests/__pycache__),
imports only the stdlib and the two templates, never runs candidate code; every `go` invocation on
candidate code and every candidate binary is a Sandbox child demoted to the agent's uid, with the
image's own environment (GOMEMLIMIT/GOMAXPROCS declared there), rlimits and a timeout, and the sandbox undoes its writes (including the build cache in the agent's home,
restored from the image's copy, which --prepare warmed from the pristine tree only) between runs.

Source-less runs. The reproducer (`go test -c`) and every probe (`go build`, below) are compiled
as the agent at /workdir, then every .go file under /workdir is deleted and the binary runs: a
test that reads source text at run time sees nothing. Main packages listed in the PREBUILD hook
are `go install`ed (into /go/bin, on PATH) before the sources go, so a reproducer or probe that
runs the project's CLI as a subprocess runs the tree under test (with the runtime fix's overlay
on that tree).

Probes. A hidden fix probe is a Go test file at tests/fix/<package dir>/probe_N_test.go (the path
under fix/ names the package it joins). It declares one or more TestXxx(t *testing.T) functions
that drive a scenario and print ONE JSON object as the last "{"-line on stdout, with no assertion
and no expected value. It is NOT run by `go test`: the grader rewrites it into an ordinary
program under random names (a random directory under the package dir, random file, function,
type and binary names, all rca_grading.neutral_name(): pronounceable, no fixed prefix or shape;
`*testing.T` becomes a small stand-in type, so the binary links no `testing` flags and
testing.Testing() is false), builds it with `go build` into a fresh, neutrally named directory
the agent owns, strips the sources and runs it with no arguments once per rg.PROBE_RUNS setting,
each on a fresh tree (`./<name>` from that directory with a terminal on stdin; the absolute path
from /workdir with stdin /dev/null), always in the user's own environment (the image ENV through
the agent's login shell, no grader variable); the directory is deleted afterwards. A probe passes
only when every run observes the expected values. An external probe
(package x_test) becomes package main; an internal one (package x) stays in its package under a
random file name and a generated main calls it. The stand-in t supports Helper, Log(f), Error(f),
Fail(Now), Failed, Fatal(f), Skip(f/Now), Skipped, Name, TempDir, Cleanup, Setenv, Parallel
(no-op) and Context; not t.Run. The root reads only the observation line: it never trusts a
`go test` report for F.

Nested modules. The P2P suite (p2p.command, a `go test -json` line) runs in each module root of
the GO_MODULES hook (default ["."]: the repository root only, ids `<package>::<Test>`). A repository
with nested modules (jd: the root module and v2/) lists every root, e.g. [".", "v2"]; the command
then runs from each root in turn and the test ids get the module root as a prefix
(`v2:<package>::<Test>`). An entry may also be a (root, command) pair for a module whose suite
needs its own package list. The reproducer and every probe are built from the root of the module
that holds their package (the nearest go.mod above it).

Runtime fix (meta.json runtime_fix kind "go-overlay"): tests/runtime_fix/ holds replacement files
at repository paths; the reproducer is built with `go test -overlay`, so every repository file on
disk stays byte-identical to the buggy tree.

One launcher, one environment. Every build and every candidate run (the reproducer, the
rebuilt-buggy run, each probe, the suite) goes through rca_grading.Sandbox.run as the agent, under
the agent's login shell from the same environment, the same rlimits, and the same non-interactive
stdin: an empty regular file, never /dev/null (a character device) or a tty, so a fix gated on
isatty() or on stdin being a character device is inactive and caught (gosmtp-clientserver-v3).
Only one hidden-probe setting swaps in a tty, so the two probe runs differ in cwd and in every
stat dimension of stdin.

Reproducer trees. The agent's test files go onto every reproducer tree; nothing else the agent
wrote does (no REPORT.md, no edited evidence/, no answer file). When the task ships evidence,
every reproducer tree also gets the task's own pristine copy (tests/evidence/, the byte mirror
of environment/evidence/) at /workdir/evidence, where the ask says a test may read it
(rca_grading.task_evidence). Besides buggy, gold, each alt fix and
the runtime fix, the reproducer also runs on the buggy tree rebuilt without a change in
behaviour: one comment line appended to every non-test .go file (rca_grading.perturb_sources)
and the repository's own packages compiled without optimisation or inlining (REBUILT_GCFLAGS).
It must fail there too (repro:fails_on_buggy_rebuilt).

Accepted limits:
- The existing-suite check (P2P) reads the result of `go test` processes that run the
  candidate's code, so that code can rewrite the suite's report or exit status. This can hide a
  regression of the existing suite: a fix that passes every hidden probe but breaks other tests
  can then score 1, and on an unfixed tree the partial row that reads the suite (fix:suite_catch)
  can rise. It cannot pass a hidden probe without a real fix: the probes' expected values never
  reach a candidate process.
- The rebuilt-buggy run above stops a regression test that recognises the exact buggy build (a
  hash of its own binary or of the compiled code, a marker file) from earning the reproduce
  score. A test that also recognises the rebuilt build needs to know how this grader rebuilds it,
  which only tests/ says. Such a test would gain the reproduce score only: the fix and the
  diagnosis must still be complete.
- A payload that needs facts only this tests/ directory holds (how the grader builds or runs
  each tree, probe names, expected values, the gold location) is out of scope: the solver never
  sees tests/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

TESTS = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # -I ignores PYTHONDONTWRITEBYTECODE: no /tests/__pycache__ (I5)
sys.path.insert(0, str(TESTS))  # -I drops the script directory from sys.path

import rca_grading as rg  # noqa: E402
from rca_grading import (answer_checks, load_answer, reproducer_checks, reproducer_missing,  # noqa: E402
                         reproducer_path, reproducer_trees)
from reward_writer import write_rewards  # noqa: E402

# --- rca:hooks begin (the only task-editable block) ---
CHILD_PATH = ""                                                # "" = the image's PATH; set only to override
# Must equal the image's ENV (the Go environment template declares all of these), or --prepare
# reports them as `child_env_overrides`: a value the agent's processes never saw marks grading.
GO_ENV = {"GOPATH": "/go", "GOMODCACHE": "/go/pkg/mod", "GOFLAGS": "-buildvcs=false -mod=readonly",
          "GOPROXY": "off", "GOSUMDB": "off", "GOTOOLCHAIN": "local", "GOMEMLIMIT": "1GiB",
          "GOMAXPROCS": "4", "CGO_ENABLED": "1"}
EXTRA_ENV: dict[str, str] = {}
RTOL, ATOL = 1e-9, 1e-12                                       # probe comparison tolerances
TIMEOUT = {"build": 300, "repro": 300, "probe": 300, "p2p": 1200}  # seconds per step
BUDGET = 2700                                                  # below [verifier] timeout_sec
MEMORY = 0                                                     # RLIMIT_AS (0: GOMEMLIMIT only)
PREPARE_ALT_P2P = True
WARM_COMMAND = ["go", "test", "-count=1", "-run", "^$", "./..."]   # --prepare: warm the agent's cache
# R runs the reproducer on gold, on each alt_fix patch and on the runtime fix (reproducer_trees).
PREBUILD: list[str] = []                 # main package dirs `go install`ed before each source-less run, e.g. ["cmd/tool"]
WARM_PACKAGES: list[str] = []            # limit the warm to these patterns (replace "./..."), e.g. ["./internal/x/..."]; [] = all
WARM_TIMEOUT = 1200                      # seconds per module root for the --prepare warm (raise for large suites)
MAX_OUTPUT = 4 << 20                     # stdout tail kept per child (diagnostics, probe line); suites stream the whole file
GO_MODULES: list = ["."]                 # module roots the P2P suite (and WARM_COMMAND) runs in, e.g. [".", "v2"]; or (root, command)
# --- rca:hooks end ---

OPT = Path("/opt/rca")
PRISTINE = OPT / "pristine"
EXPECTED = OPT / "fix_expected.json"
BASELINE = OPT / "p2p_baseline.txt"
UNSTABLE = OPT / "p2p_unstable.txt"          # flaky at build: excluded from the baseline
CATCH = OPT / "p2p_catch.txt"                 # suite tests that fail on buggy and pass on gold + every fix
RECEIPT = OPT / "prepare.json"
WORKDIR = Path("/workdir")
OUT = Path("/logs/verifier")
TEST_FUNC = re.compile(r"^func\s+(Test[A-Za-z0-9_]*)\s*\(\s*\w+\s+\*testing\.T\s*\)", re.M)
PACKAGE_CLAUSE = re.compile(r"^package\s+([A-Za-z_]\w*)", re.M)
MODULE_LINE = re.compile(r"^module\s+(\S+)", re.M)


# --- the Go runner --------------------------------------------------------------------------------

def child_env():
    """The sandbox's base environment: the image's own (as the agent's processes saw it), with
    LANG/LC_ALL, GO_ENV and EXTRA_ENV on top. Builds and candidate runs are login runs from the
    image ENV plus EXTRA_ENV (rca_grading.Sandbox.login_env)."""
    env = rg.ordinary_environment()
    env.update({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", **GO_ENV})
    env["PATH"] = CHILD_PATH or env.get("PATH") or "/usr/local/go/bin:/go/bin:/usr/local/bin:/usr/bin:/bin"
    env.update(EXTRA_ENV)
    return env


def child_env_overrides():
    image = rg.ordinary_environment()
    return sorted(k for k, v in child_env().items() if image.get(k) != v)


# A test binary's death by signal, as its output reports it (test2json exits 1 whatever happened):
# the Go runtime's fatal-signal header ("SIGSEGV: segmentation violation", e.g. in cgo), "fatal
# error: unexpected signal", or test2json's own "signal: segmentation fault" when the binary was
# killed. A recovered nil-dereference panic ("[signal SIGSEGV: ...]") is an ordinary test failure.
RUNTIME_SIGNAL = re.compile(r"^(SIG[A-Z]{2,10}): ")
EXIT_SIGNAL = re.compile(r"^signal: ([a-z -]+)$")
EXIT_SIGNAL_NAMES = {"segmentation fault": "SIGSEGV", "killed": "SIGKILL", "aborted": "SIGABRT",
                     "bus error": "SIGBUS", "floating point exception": "SIGFPE",
                     "illegal instruction": "SIGILL", "terminated": "SIGTERM", "trace/breakpoint trap": "SIGTRAP"}


def output_signal(text):
    """The signal name an output line reports the test binary died of, else None."""
    text = str(text or "").strip()
    match = RUNTIME_SIGNAL.match(text)
    if match:
        return match.group(1)
    if text.startswith("fatal error: unexpected signal"):
        return "SIGSEGV" if "SIGSEGV" in text or "segmentation" in text else "unknown signal"
    match = EXIT_SIGNAL.match(text)
    if match:
        return EXIT_SIGNAL_NAMES.get(match.group(1), "unknown signal")
    return None


class GoEvents:
    """Incremental `go test -json` / test2json reader. feed() one line at a time; it keeps only
    test-level and package-level final actions (pass/fail/skip) and a build-failure flag, and
    drops every "output" event, so memory stays bounded however much a suite prints (trickster's
    `go test -json ./...` is ~9 MB, mostly output events: a bounded stdout tail lost the head of
    the record, so --prepare recorded part of the suite and grading saw the cut-off tests as
    regressions)."""

    def __init__(self):
        self.tests, self.packages, self.seen = {}, {}, set()
        self.build_failed, self.malformed, self.overlong = False, 0, 0
        self.crash = None                      # output_signal() of the first fatal-signal line

    def feed(self, line):
        if line is None:                       # rca_grading.iter_lines: an overlong line, skipped
            self.overlong += 1
            return
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        line = line.strip()
        if not line.startswith("{"):
            return
        try:                                   # fail closed: a too-deep line is a malformed event
            event = rg.safe_json(line)
        except ValueError:
            event = None
        if not isinstance(event, dict):
            if '"Action"' in line:             # a cut-off or garbled event line
                self.malformed += 1
            return
        action, package, test = event.get("Action"), event.get("Package"), event.get("Test")
        if action == "build-fail" or (action == "output" and test is None
                                      and "[build failed]" in str(event.get("Output", ""))):
            self.build_failed = True
        if action == "output" and self.crash is None:
            self.crash = output_signal(event.get("Output"))
        if not isinstance(package, str):
            return
        self.seen.add(package)
        if action in ("pass", "fail", "skip"):
            if isinstance(test, str):
                # Fail-sticky, as the Rust and Python suite readers are: once a test has a real
                # "fail", a later "pass"/"skip" for the same id never overrides it. With -count=1
                # each test ends in exactly one event, so an honest run is unaffected; a forged
                # test2json "pass" event (an agent init() spraying `{"Action":"pass",...}` or a
                # `\x16--- PASS:` line, gosmtp/gogeom Reward Hack Post-Eval) cannot hide a real
                # regression or fake a fix:suite_catch pass for a test that actually failed.
                if self.tests.get((package, test)) != "fail":
                    self.tests[(package, test)] = action
            elif test is None:
                self.packages[package] = action

    def incomplete(self):
        """Why the record is not a complete suite run ([] when it is). Every package the go
        command reported must end in a package-level pass/fail/skip: test2json writes one even
        when a test binary panics or hits -timeout (the unfinished test is reported failed or
        missing, and the package fails), so a package without one means the output was cut off."""
        problems = []
        open_packages = sorted(self.seen - set(self.packages))
        if open_packages:
            problems.append(f"{len(open_packages)} packages have no final result (e.g. {open_packages[0]})")
        if self.malformed:
            problems.append(f"{self.malformed} malformed event lines")
        return problems

    def result(self):
        return {"tests": self.tests, "packages": self.packages, "build_failed": self.build_failed,
                "incomplete": self.incomplete(), "overlong_lines": self.overlong, "crash": self.crash}


def parse_events(stdout):
    """`go test -json` / test2json output (bytes or str) -> GoEvents.result(): {"tests":
    {(package, test): final action}, "packages": {package: final action}, "build_failed",
    "incomplete": [reasons], "overlong_lines"}. Lines that are not JSON events are ignored."""
    events = GoEvents()
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    for line in stdout.splitlines():
        events.feed(line)
    return events.result()


def parse_event_file(path):
    """parse_events over a whole stdout file, streamed line by line (Sandbox.run stdout_reader)."""
    events = GoEvents()
    for line in rg.iter_lines(path):
        events.feed(line)
    return events.result()


def test_names(source):
    return sorted(set(TEST_FUNC.findall(source.decode("utf-8", "replace") if isinstance(source, bytes) else source)))


def package_dir(rel):
    parent = PurePosixPath(rel).parent.as_posix()
    return "." if parent in ("", ".") else parent


def overlay(sandbox, spec_dir):
    """(overlay JSON path, its directory) for `go test -overlay`: replacement files from the runtime
    fix at their repository paths under /workdir. Removed before any candidate binary runs."""
    spec_dir, base = Path(spec_dir), sandbox.private_dir()
    replace = {}
    for path in sorted(spec_dir.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rel = path.relative_to(spec_dir).as_posix()
            rg.put_file(base / "r", rel, path)
            replace[str(WORKDIR / rel)] = str(base / "r" / rel)
    (base / "o.json").write_text(json.dumps({"Replace": replace}))
    rg._run(["chown", "-R", f"{sandbox.uid}:{sandbox.gid}", str(base)], timeout=60)
    return base / "o.json", base


def go_build(sandbox, argv, cwd, timeout, label, runtime=None, flags=()):
    """Run a `go build`/`go test -c`/`go install` argv as the agent, with the runtime fix's
    -overlay when given (the overlay files are removed before any candidate binary runs) and any
    extra build `flags` (the rebuilt-buggy run's REBUILT_GCFLAGS)."""
    holder = None
    if flags:
        argv = argv[:2] + list(flags) + argv[2:]
    if runtime is not None:
        json_path, holder = overlay(sandbox, runtime)
        argv = argv[:2] + [f"-overlay={json_path}"] + argv[2:]
    try:
        return sandbox.run(argv, cwd=cwd, timeout=timeout, label=label)
    finally:
        if holder is not None:
            rg._remove(holder)


def built(result, out):
    if result["timed_out"] or result["code"] != 0 or not out.is_file() or out.is_symlink():
        return None, "build failed" + (" (timed out)" if result["timed_out"] else "")
    return out, "built"


def compile_tests(sandbox, pkg, timeout, label, runtime=None, flags=()):
    """`go test -c` of one package (the agent's reproducer) as the agent, from the root of the
    module holding it; (binary or None, detail)."""
    out = sandbox.private_dir() / (PurePosixPath(pkg).name.replace(".", "x") or "main")
    out = out.with_name(out.name + ".test")
    root = module_root(pkg)
    target = relative_to_module(pkg, root)
    result = go_build(sandbox, ["go", "test", "-c", "-o", str(out), "./" + target if target != "." else "."],
                      WORKDIR / root, timeout, label, runtime, flags)
    return built(result, out)


def module_of(pkg):
    """(module root dir relative to /workdir, module path) of the module holding package dir pkg."""
    here = PurePosixPath(pkg)
    while True:
        gomod = PRISTINE / here / "go.mod"
        if gomod.is_file():
            found = MODULE_LINE.search(gomod.read_text(errors="replace"))
            if found:
                return here.as_posix(), found.group(1).strip('"')
        if here.as_posix() in (".", ""):
            raise RuntimeError(f"no go.mod above {pkg}")
        here = here.parent


def module_root(pkg):
    """The root dir of the module holding package dir pkg ("." when no go.mod is found above it,
    e.g. a package the agent added under a new directory of a go.work workspace)."""
    try:
        return module_of(pkg)[0]
    except RuntimeError:
        return "."


def go_modules(command):
    """[(module root, command)] the P2P suite runs: `command` (p2p.command) in each GO_MODULES root,
    or an entry's own command."""
    modules = []
    for entry in GO_MODULES:
        root, own = (entry, None) if isinstance(entry, str) else (entry[0], entry[1])
        modules.append((PurePosixPath(root).as_posix(), own or command))
    return modules


def suite_id(root, package, test):
    """A P2P test id: `<package>::<Test>`, with a `<module root>:` prefix unless the suite runs
    only in the repository root (the default, single-module ids)."""
    base = f"{package}::{test}"
    return base if [r for r, _ in go_modules("")] == ["."] else f"{root}:{base}"


def relative_to_module(rel, root):
    rel, root = PurePosixPath(rel), PurePosixPath(root)
    return rel.as_posix() if root.as_posix() == "." else rel.relative_to(root).as_posix()


def prebuild(sandbox, budget, label, runtime=None, flags=()):
    """`go install` each PREBUILD main package (to $GOPATH/bin, on PATH; the sandbox removes it at
    the next reset). None when all built, else a neutral detail."""
    for pkg in PREBUILD:
        root, _ = module_of(pkg)
        target = relative_to_module(pkg, root)
        result = go_build(sandbox, ["go", "install", "./" + target if target != "." else "."],
                          WORKDIR / root, budget.step(TIMEOUT["build"]), f"{label}:install", runtime, flags)
        if result["timed_out"] or result["code"] != 0:
            return "build failed" + (" (timed out)" if result["timed_out"] else "")
    return None


def fresh_ident(exported=False):
    """A fresh neutral Go identifier / file / directory / binary name (exported: capitalized)."""
    return rg.neutral_name(capitalized=exported, avoid=GO_RESERVED)


GO_RESERVED = frozenset({
    "break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough", "for", "func",
    "go", "goto", "if", "import", "interface", "map", "package", "range", "return", "select", "struct",
    "switch", "type", "var", "main", "init", "any", "bool", "byte", "comparable", "complex", "error",
    "false", "float", "imag", "make", "max", "min", "new", "panic", "print", "real", "recover", "rune",
    "string", "true", "uint", "uintptr", "append", "cap", "clear", "close", "copy", "delete", "len", "nil"})


def stand_in(type_name, package):
    """Go source of the stand-in for *testing.T (a file of `package`). Everything generated into the
    candidate's module stays valid under a `go 1.13` go.mod directive: interface{} (not any), no
    generics, no post-1.13 stdlib API (ioutil.TempDir, not os.MkdirTemp)."""
    t = type_name
    return f"""package {package}

import (
	"context"
	"fmt"
	"io/ioutil"
	"os"
	"runtime"
)

type {t} struct {{
	failed, skipped bool
	cleanups      []func()
}}

func (t *{t}) Helper()                           {{}}
func (t *{t}) Parallel()                         {{}}
func (t *{t}) Name() string                      {{ return "" }}
func (t *{t}) Log(a ...interface{{}})              {{ fmt.Fprintln(os.Stderr, a...) }}
func (t *{t}) Logf(f string, a ...interface{{}})   {{ fmt.Fprintf(os.Stderr, f+"\\n", a...) }}
func (t *{t}) Error(a ...interface{{}})            {{ t.Log(a...); t.failed = true }}
func (t *{t}) Errorf(f string, a ...interface{{}}) {{ t.Logf(f, a...); t.failed = true }}
func (t *{t}) Fail()                             {{ t.failed = true }}
func (t *{t}) Failed() bool                      {{ return t.failed }}
func (t *{t}) FailNow()                          {{ t.failed = true; runtime.Goexit() }}
func (t *{t}) Fatal(a ...interface{{}})            {{ t.Log(a...); t.FailNow() }}
func (t *{t}) Fatalf(f string, a ...interface{{}}) {{ t.Logf(f, a...); t.FailNow() }}
func (t *{t}) SkipNow()                          {{ t.skipped = true; runtime.Goexit() }}
func (t *{t}) Skip(a ...interface{{}})             {{ t.Log(a...); t.SkipNow() }}
func (t *{t}) Skipf(f string, a ...interface{{}})  {{ t.Logf(f, a...); t.SkipNow() }}
func (t *{t}) Skipped() bool                     {{ return t.skipped }}
func (t *{t}) Context() context.Context          {{ return context.Background() }}
func (t *{t}) Cleanup(f func())                  {{ t.cleanups = append(t.cleanups, f) }}
func (t *{t}) Setenv(k, v string) {{
	old, had := os.LookupEnv(k)
	os.Setenv(k, v)
	t.Cleanup(func() {{
		if had {{
			os.Setenv(k, old)
		}} else {{
			os.Unsetenv(k)
		}}
	}})
}}
func (t *{t}) TempDir() string {{
	d, err := ioutil.TempDir("", "")
	if err != nil {{
		t.Fatal(err)
	}}
	t.Cleanup(func() {{ os.RemoveAll(d) }})
	return d
}}
"""


def runner(type_name, run_name, functions):
    """Go source of the function that calls each probe function in turn on a fresh stand-in."""
    calls = ", ".join(functions)
    return f"""
func {run_name}() {{
	for _, f := range []func(*{type_name}){{{calls}}} {{
		t := &{type_name}{{}}
		done := make(chan struct{{}})
		go func() {{
			defer close(done)
			defer func() {{
				for i := len(t.cleanups) - 1; i >= 0; i-- {{
					t.cleanups[i]()
				}}
			}}()
			f(t)
		}}()
		<-done
	}}
}}
"""


def probe_program(probe, workspace):
    """Rewrite a probe test file into an ordinary program under random names. Returns
    ({rel path under /workdir: generated source}, module root, main package dir relative to the
    module root). The generated sources are written under `workspace` (root-only scratch)."""
    pkg = probe_package(probe)
    source = (TESTS / probe).read_text()
    names = test_names(source)
    clause = PACKAGE_CLAUSE.search(source)
    if clause is None or not names:
        raise RuntimeError(f"{probe}: not a Go probe (package clause and TestXxx functions)")
    package = clause.group(1)
    # Every name distinct, and no file or directory of the package dir is shadowed.
    try:
        taken = {entry.name.split(".")[0].lower() for entry in os.scandir(PRISTINE / pkg)}
    except OSError:
        taken = set()

    def ident(exported=False):
        while True:
            name = fresh_ident(exported)
            if name.lower() not in taken:
                taken.add(name.lower())
                return name

    type_name, run_name, directory = ident(), ident(exported=True), ident()
    renamed = {name: ident(exported=True) for name in names}
    body = re.sub(r"\*\s*testing\.T\b", "*" + type_name, source)
    for old_name, new_name in renamed.items():
        body = re.sub(rf"\b{old_name}\b", new_name, body)
    if not re.search(r"\btesting\.", body):        # drop the now unused import: no `testing` linked
        body = re.sub(r'^[ \t]*import[ \t]+"testing"[ \t]*\n', "", body, flags=re.M)
        body = re.sub(r'^[ \t]*"testing"[ \t]*\n', "", body, flags=re.M)
    root, module = module_of(pkg)
    main_dir = (PurePosixPath(pkg) / directory).as_posix() if pkg != "." else directory
    files = {}
    if package.endswith("_test"):                # external probe: the whole program is package main
        body = PACKAGE_CLAUSE.sub("package main", body, count=1)
        files[f"{main_dir}/{ident()}.go"] = body
        files[f"{main_dir}/{ident()}.go"] = (stand_in(type_name, "main") + runner(type_name, run_name, renamed.values())
                                                + f"\nfunc main() {{ {run_name}() }}\n")
    elif package == "main":
        raise RuntimeError(f"{probe}: a probe joining a main package must be external (package main_test)")
    else:                                         # internal probe: stays in its package, random file
        prefix = f"{pkg}/" if pkg != "." else ""
        files[f"{prefix}{ident()}.go"] = body
        files[f"{prefix}{ident()}.go"] = stand_in(type_name, package) + runner(type_name, run_name, renamed.values())
        rel = relative_to_module(pkg, root)
        path = module if rel == "." else f"{module}/{rel}"
        alias = ident()
        files[f"{main_dir}/{ident()}.go"] = f'package main\n\nimport {alias} "{path}"\n\nfunc main() {{ {alias}.{run_name}() }}\n'
    placed = {}
    for rel, text in files.items():
        target = Path(workspace) / ident()
        target.write_text(text)
        placed[rel] = target
    return placed, root, relative_to_module(main_dir, root)


def strip_sources():
    """Delete every .go file under /workdir (source-less run), except the task's evidence/ (data
    the reproducer may read, never compiled into it)."""
    rg.prune_tree(WORKDIR, lambda rel: rel.endswith(".go") and not rel.startswith(rg.EVIDENCE_DIR + "/")
                  and not (WORKDIR / rel).is_dir())


REBUILT_GCFLAGS = "-N -l"      # the rebuilt-buggy run: no optimisation, no inlining (as a debugger build)


def module_paths():
    """The module path of every go.mod in the pristine tree (testdata/ and vendor/ excluded)."""
    found = set()
    for gomod in sorted(PRISTINE.rglob("go.mod")):
        parts = gomod.relative_to(PRISTINE).parts
        if "testdata" in parts or "vendor" in parts or not gomod.is_file():
            continue
        match = MODULE_LINE.search(gomod.read_text(errors="replace"))
        if match:
            found.add(match.group(1).strip('"'))
    return sorted(found)


def rebuilt_flags():
    """Build flags of the rebuilt-buggy run: the repository's own packages (every module of the
    tree; dependencies and the standard library keep their cached builds) compiled with
    REBUILT_GCFLAGS, so every function of the project compiles to different machine code."""
    return [f"-gcflags={path}/...={REBUILT_GCFLAGS}" for path in module_paths()]


def rebuild_buggy(rules, extras):
    """The buggy tree at /workdir, changed without changing behaviour: one comment line appended to
    every non-test .go file (not the agent's test files, the test paths or testdata/)."""
    def skip(rel):
        return (rel in extras or rules.matches(rel) or rel.endswith("_test.go")
                or "testdata" in rel.split("/"))
    return rg.perturb_sources(WORKDIR, (".go",), "//", skip)


def reproducer_outcome(sandbox, rel, names, budget, label, runtime=None, flags=()):
    pkg = package_dir(rel)
    failed = prebuild(sandbox, budget, label, runtime, flags)
    if failed:
        return {"outcome": "error", "detail": failed}
    binary, detail = compile_tests(sandbox, pkg, budget.step(TIMEOUT["build"]), f"{label}:build", runtime, flags)
    if binary is None:
        return {"outcome": "error", "detail": detail}
    strip_sources()
    timeout = budget.step(TIMEOUT["repro"])
    result = sandbox.run(["go", "tool", "test2json", "-p", pkg, str(binary), "-test.v=test2json",
                          "-test.paniconexit0", f"-test.run=^({'|'.join(names)})$",
                          f"-test.timeout={max(timeout - 10, 10)}s"],
                         cwd=WORKDIR / pkg, timeout=timeout, label=label, stdout_reader=parse_event_file)
    events = result["parsed"] or parse_events(b"")    # None when the budget was already spent
    seen = {test: action for (_, test), action in events["tests"].items() if test in names}
    summary = ", ".join(f"{t}: {a}" for t, a in sorted(seen.items()))[:200] or "no test ran"
    if result["timed_out"]:
        return {"outcome": "error", "detail": "timed out"}
    if any(a == "fail" for a in seen.values()):
        outcome = {"outcome": "fail", "detail": summary}
    elif result["code"] == 0 and seen and all(a in ("pass", "skip") for a in seen.values()) and "pass" in seen.values():
        outcome = {"outcome": "pass", "detail": summary}
    else:
        outcome = {"outcome": "error", "detail": f"exit {result['code']}; {summary}"}
    # killed by a signal: "crashed", not a bare error (test2json reports it in the output, not the exit code)
    return rg.crash_outcome(outcome, result["code"], signal_name=events.get("crash"))


def probe_package(probe):
    """The package dir a tests/fix/<pkg>/probe_N_test.go probe joins (its path under fix/)."""
    rel = PurePosixPath(probe)
    rel = rel.relative_to("fix") if rel.parts[0] == "fix" else rel
    return package_dir(rel.as_posix())


def probe_observation(sandbox, rebuild, budget, label, runtime=None, verbose=False):
    """[(observations or None, neutral detail)], one per rg.PROBE_RUNS setting. For each,
    `rebuild()` places a fresh rewrite of the probe (new random names) in a freshly built /workdir
    and returns (module root, main package dir); the program is built with `go build` into a
    randomly named binary in a fresh, neutrally named directory the agent owns, the sources are
    stripped, and the binary runs like any program a user builds and runs: `./<name>` from that
    directory with a terminal on stdin ("own-dir"), or `/home/agent/<dir>/<name>` from /workdir
    with stdin /dev/null ("project"), in the user's own environment (the image ENV through the
    agent's login shell, no grader variable such as GOMEMLIMIT or GOFLAGS: Sandbox.run(login=True)).
    The directory is deleted afterwards. No single setting is the probe's, so a fix gated on cwd,
    isatty() or an environment knob fails one (octodns v5, mp4ff v6)."""
    runs = []
    for setting in rg.PROBE_RUNS:
        root, main_rel = rebuild()
        failed = prebuild(sandbox, budget, f"{label}:build", runtime)
        if failed:
            runs.append((None, f"no observations ({failed})"))
            continue
        where, cwd = rg.probe_layout(sandbox, setting)
        try:
            out = where / fresh_ident()
            result = go_build(sandbox, ["go", "build", "-o", str(out), "./" + main_rel], WORKDIR / root,
                              budget.step(TIMEOUT["build"]), f"{label}:build", runtime)
            binary, detail = built(result, out)
            if binary is None:
                if verbose:
                    detail += f"; stderr: {result['stderr'][-600:]}"
                runs.append((None, f"no observations ({detail})"))
                continue
            strip_sources()
            result = sandbox.run([rg.program_path(binary, cwd)], cwd=cwd, timeout=budget.step(TIMEOUT["probe"]),
                                 stdin=setting["stdin"], label=f"{label}:{setting['name']}", login=True)
        finally:
            rg._remove(where)
        if result["timed_out"]:
            runs.append((None, rg.PROBE_TIMED_OUT))
            continue
        observed = rg.parse_observation(result["stdout"])
        detail = "observations recorded" if observed is not None else f"no observations (exit {result['code']})"
        if verbose and observed is None:       # --prepare only: grading feedback stays neutral
            detail += (f"; stdout: {result['stdout'][-600:].decode('utf-8', 'replace')}; "
                       f"stderr: {result['stderr'][-600:]}")
        runs.append((observed, detail))
    return runs


def suite_run(sandbox, command, timeout, label, runtime=None):
    """(passing ids or None, detail) of `p2p.command` (a `go test -json` line), run in each
    GO_MODULES root (default: /workdir only) within `timeout` seconds in all. The whole stdout file
    is parsed incrementally (never a bounded tail). An incomplete record (a package without its
    final event, a garbled event line, the go command killed or stopped at the file-size limit, a
    module that ran no test) is None, "not recorded": --prepare fails the build on it, and grading
    never reads a test missing from a cut-off record as a regression of the candidate. With
    `runtime` (a runtime-fix spec dir), the suite runs under its `-overlay`, so every repository
    file on disk stays byte-identical to the buggy tree (used at --prepare to confirm the
    fail-on-buggy tests pass under the runtime fix)."""
    modules = go_modules(command)
    single = len(modules) == 1
    deadline = time.monotonic() + timeout
    holder = json_path = None
    if runtime is not None:
        json_path, holder = overlay(sandbox, runtime)
    passed, collected, details, incomplete, total = set(), set(), [], [], 0
    try:
        for root, module_command in modules:
            argv = shlex.split(module_command)
            if json_path is not None:
                argv = argv[:2] + [f"-overlay={json_path}"] + argv[2:]   # after `go test`
            result = sandbox.run(argv, cwd=WORKDIR / root, timeout=max(0, int(deadline - time.monotonic())),
                                 label=label if single else f"{label}:{root}", stdout_reader=parse_event_file)
            where = "" if single else f"module {root}: "
            if result["timed_out"]:
                return None, where + "timed out"
            events = result["parsed"]
            passed |= {suite_id(root, p, t) for (p, t), a in events["tests"].items() if a == "pass"}
            collected |= {suite_id(root, p, t) for (p, t) in events["tests"]}
            total += len(events["tests"])
            failed = sum(a == "fail" for a in events["tests"].values())
            details.append(where + f"exit {result['code']}: {len(events['tests'])} tests in "
                           f"{len(events['packages'])} packages, {failed} failed"
                           + (", build failed" if events["build_failed"] else ""))
            incomplete += [where + reason for reason in events["incomplete"]]
            if result["code"] not in (0, 1):            # go test: 0 all passed, 1 a test or build failed
                incomplete.append(where + f"go exited with code {result['code']}")
            if result["stdout_bytes"] >= sandbox.limits[1]:
                incomplete.append(where + "stdout reached the file-size limit")
            if not single and not events["tests"]:
                incomplete.append(where + "no test ran")
    finally:
        if holder is not None:
            rg._remove(holder)
    detail = "; ".join(details)
    if incomplete:
        return None, f"{detail}; incomplete record: {'; '.join(incomplete)}"
    return (rg.SuiteRecord(passed, collected) if total else None), detail


# --- shared by --prepare and grading ----------------------------------------------------------------

def load_inputs():
    meta = json.loads((TESTS / "meta.json").read_text())
    manifest = json.loads((TESTS / "rca-task.json").read_text())
    return meta, manifest, rg.OmitRules.from_manifest(manifest)


def make_sandbox(scratch):
    return rg.Sandbox(scratch=scratch, env=child_env(), mem_bytes=MEMORY, max_output=MAX_OUTPUT,
                      extra_env=EXTRA_ENV)


def build(sandbox, rules, view, *, patches=(), files=None, deleted=()):
    remove = rg.solver_view_skip(rules) if view == "solver" else None
    sandbox.populate(PRISTINE, patches=patches, files=files, deleted=deleted, remove=remove)


def scratch_dir():
    path = Path(tempfile.mkdtemp(prefix="g"))
    os.chmod(path, 0o700)
    return path


def probe_files(sandbox, probe, files=None):
    """({rel: source} to place in /workdir: `files` plus the probe rewritten as a program under
    fresh random names), (module root, main package dir)) for one probe run."""
    workspace = Path(tempfile.mkdtemp(dir=sandbox.scratch))      # root-only scratch
    generated, root, main_rel = probe_program(probe, workspace)
    placed = dict(files or {})
    placed.update(generated)
    return placed, (root, main_rel)


def clear_workdir():
    for entry in list(os.scandir(WORKDIR)):
        rg._remove(Path(entry.path))


# --- --prepare: verifier image build ---------------------------------------------------------------

def warm_command():
    """WARM_COMMAND, with its `./...` pattern replaced by WARM_PACKAGES when that is set."""
    if not WARM_PACKAGES:
        return list(WARM_COMMAND)
    return [arg for arg in WARM_COMMAND if arg != "./..."] + list(WARM_PACKAGES)


def warm_cache(sandbox, command):
    """--prepare: build (not run) the tests in each GO_MODULES root, WARM_TIMEOUT seconds each."""
    argv = warm_command()
    for root, _ in go_modules(command):
        warm = sandbox.run(argv, cwd=WORKDIR / root, timeout=WARM_TIMEOUT, label="warm-cache")
        if warm["code"] != 0:
            raise SystemExit(f"prepare: warming the build cache failed ({root}): {warm['stderr'][-300:]}")


def prepare():
    shared_before = rg.shared_entries()        # what /tmp, /var/tmp, /dev/shm held before --prepare
    meta, manifest, rules = load_inputs()
    problems = rg.meta_problems(meta) + rg.format_problems(meta, manifest, TESTS)
    command = meta.get("p2p", {}).get("command", "")
    for root, module_command in go_modules(command):
        if "-json" not in shlex.split(module_command):
            problems.append("p2p.command (and every GO_MODULES command) must be a `go test -json ...` command line")
        if not (PRISTINE / root / "go.mod").is_file():
            problems.append(f"GO_MODULES root {root} has no go.mod in the pristine tree")
    for probe in meta.get("fix_tests") or []:
        if not str(probe).endswith("_test.go") or not (TESTS / probe).is_file() or not test_names((TESTS / probe).read_bytes()):
            problems.append(f"{probe}: a Go probe is a *_test.go file under fix/<package dir>/ declaring TestXxx")
            continue
        try:
            with tempfile.TemporaryDirectory() as workspace:
                probe_program(probe, workspace)
        except RuntimeError as error:
            problems.append(str(error))
    if problems:
        raise SystemExit("prepare: " + "; ".join(problems))
    violations = []
    trees = manifest["trees"]
    if rg.tree_fingerprint(PRISTINE) != trees["pristine"]:
        violations.append("pristine tree fingerprint differs from rca-task.json trees.pristine")
    solver_manifest = rg.tree_manifest(PRISTINE, rg.solver_view_skip(rules))
    if rg.tree_digest(solver_manifest) != trees["solver"]:
        violations.append("solver view fingerprint differs from rca-task.json trees.solver")
    if rules.patterns and not any(rules.omitted(rel) for rel in rg.tree_manifest(PRISTINE)):
        violations.append("the pristine tree has no file matching omit_tests (the suite must be here)")
    if violations:
        raise SystemExit("prepare: " + "; ".join(violations))

    scratch = scratch_dir()
    sandbox = make_sandbox(scratch)
    # Warm the agent's build cache from the pristine tree only, then snapshot the agent's home:
    # every later run (here and at grading) starts from exactly this cache, and nothing a gold,
    # alt-fix or probe build adds survives the run.
    build(sandbox, rules, "full")
    warm_cache(sandbox, command)
    sandbox.scan()
    budget = rg.Budget(10 ** 6)
    fixes = reproducer_trees(meta, TESTS)
    probes = list(meta["fix_tests"])

    details = {}
    settings = [setting["name"] for setting in rg.PROBE_RUNS]

    def observe(label, kind, path):
        """{probe: [observations per rg.PROBE_RUNS setting]} on one tree."""
        seen = {}
        for probe in probes:
            def rebuild(probe=probe):
                placed, program = probe_files(sandbox, probe)
                build(sandbox, rules, "solver", patches=[path] if kind == "patch" else [], files=placed)
                return program
            runs = probe_observation(sandbox, rebuild, budget, f"{label}:{probe}",
                                     runtime=path if kind == "runtime" else None, verbose=True)
            seen[probe] = [observed for observed, _ in runs]
            details[(label, probe)] = "; ".join(f"{name}: {detail}" for name, (_, detail) in zip(settings, runs))
        return seen

    def matches(observed, expected):
        return observed is not None and rg.observations_match(observed, expected, RTOL, ATOL)

    gold_path = fixes[0][2]
    buggy = observe("buggy", None, None)
    gold = observe("gold", "patch", gold_path)
    again = observe("gold-repeat", "patch", gold_path)
    for probe in probes:
        problem = next(filter(None, map(rg.observation_problem, gold[probe])), None)
        if problem:
            violations.append(f"{probe}: gold observations unusable ({problem}; {details[('gold', probe)]})")
            continue
        reference = gold[probe][0]
        if any(observed != reference for observed in gold[probe]):
            violations.append(f"{probe}: observations on the gold tree depend on the run setting ({', '.join(settings)}: "
                              "cwd, the binary's directory or stdin); a probe must observe the same values wherever it runs")
        if again[probe] != gold[probe]:
            violations.append(f"{probe}: observations on the gold tree are not deterministic")
        for name, observed in zip(settings, buggy[probe]):
            if matches(observed, reference):
                violations.append(f"{probe}: observes the same values on the buggy tree as on gold in the {name} run "
                                  "(not fail-to-pass)")
    for label, kind, path in fixes[1:]:
        if kind == "runtime":
            build(sandbox, rules, "solver")
            json_path, holder = overlay(sandbox, path)
            replaced = json.loads(json_path.read_text())["Replace"]
            if any(not Path(target).is_file() for target in replaced):
                violations.append("the runtime fix overlay names a file the tree does not have")
            rg._remove(holder)
        seen = observe(label, kind, path)
        for probe in probes:
            if gold[probe][0] is not None and not all(matches(observed, gold[probe][0]) for observed in seen[probe]):
                violations.append(f"{probe}: {label} observes different values than gold ({details[(label, probe)]})")

    # The P2P baseline from two runs on each tree (a flaky test must not kill the build: powercalc).
    def suite_twice(label, patches):
        runs, details = [], []
        for attempt in (1, 2):
            build(sandbox, rules, "full", patches=patches)
            passed, detail = suite_run(sandbox, command, TIMEOUT["p2p"], f"p2p:{label}:{attempt}")
            runs.append(passed)
            details.append(detail)
        return runs, "; ".join(details)

    on_buggy, buggy_detail = suite_twice("buggy", [])
    on_gold, gold_detail = suite_twice("gold", [gold_path])
    excluded = rg.p2p_excluded_ids(meta)
    baseline, unstable, catch, collection = set(), set(), set(), set()
    if None in on_buggy or None in on_gold:
        violations.append(f"the suite cannot be recorded (buggy: {buggy_detail}; gold: {gold_detail})")
    else:
        recorded = rg.p2p_baseline(on_buggy, on_gold, excluded)
        baseline, unstable = recorded["baseline"], recorded["unstable"]
        collection = recorded["collection_unstable"]   # ids drawn at random at collection: never fail the build
        catch = rg.p2p_catch(on_buggy, on_gold, excluded)   # suite tests the defect broke (fail-to-pass)
        pinned = sorted(recorded["pinned"])
        if pinned:
            violations.append(f"{len(pinned)} suite tests pass on buggy but fail on gold and are not in "
                              f"p2p.excluded (e.g. {pinned[0]})")
        if not baseline:
            violations.append("the P2P baseline is empty" + (f" ({len(unstable)} unstable suite tests excluded)"
                                                             if unstable else ""))
        if unstable:
            print(f"prepare: {len(unstable)} unstable suite tests excluded from the baseline "
                  f"(e.g. {sorted(unstable)[0]})")
        if collection:
            print(f"prepare: {len(collection)} of them have ids not collected identically in each run of one "
                  f"tree (drawn at random at collection?), so they are unstable, never regressions "
                  f"(e.g. {sorted(collection)[0]})")
        if catch:
            print(f"prepare: {len(catch)} suite tests fail on buggy and pass on gold (fix:suite_catch)")
    # Each alt fix and the runtime fix must leave the baseline intact; a catch test that fails on
    # one pins gold internals, so it is dropped from the catch set and logged, not counted at grading.
    if PREPARE_ALT_P2P and baseline:
        for label, kind, path in fixes[1:]:
            def fix_suite(attempt, kind=kind, path=path):
                build(sandbox, rules, "full", patches=[path] if kind == "patch" else [])
                return suite_run(sandbox, command, TIMEOUT["p2p"], f"p2p:{label}:{attempt}",
                                 runtime=path if kind == "runtime" else None)

            outcome = rg.p2p_with_rerun(fix_suite, baseline | catch)
            if not outcome["recorded"]:
                violations.append(f"the suite cannot be recorded on {label} ({outcome['detail']})")
                continue
            if outcome["lost"] & baseline:
                regressed = sorted(outcome["lost"] & baseline)
                violations.append(f"{label} regresses the suite ({outcome['detail']}; e.g. {regressed[0]})")
            dropped = outcome["lost"] & catch
            if dropped:
                print(f"prepare: {len(dropped)} fail-on-buggy suite tests fail on {label} and are dropped from "
                      f"fix:suite_catch (they pin gold internals; e.g. {sorted(dropped)[0]})")
                catch -= dropped

    sandbox.reset()           # the agent's home goes back to the warmed snapshot
    clear_workdir()
    shutil.rmtree(scratch, ignore_errors=True)
    removed = rg.remove_new_shared_entries(shared_before)
    if removed:
        print(f"prepare: removed {len(removed)} entries left in shared temporary directories (e.g. {removed[0]})")
    if rg.remove_bytecode_caches(TESTS):
        print("prepare: removed __pycache__ under /tests (run grade.py with -B)")
    overrides = child_env_overrides()
    if overrides:
        print(f"prepare: candidate children get {overrides} with values the image does not declare")
    if violations:
        raise SystemExit("prepare: " + "; ".join(violations))
    expected_text = json.dumps({probe: runs[0] for probe, runs in gold.items()}, indent=1, sort_keys=True) + "\n"
    baseline_text = "".join(f"{i}\n" for i in sorted(baseline))
    unstable_text = "".join(f"{i}\n" for i in sorted(unstable))
    catch_text = "".join(f"{i}\n" for i in sorted(catch))
    EXPECTED.write_text(expected_text)
    BASELINE.write_text(baseline_text)
    UNSTABLE.write_text(unstable_text)
    CATCH.write_text(catch_text)
    RECEIPT.write_text(json.dumps({
        "language": "go", "go_modules": [root for root, _ in go_modules(command)], "probes": len(probes), "probe_runs": settings, "fix_trees": len(fixes),
        "runtime_fix": (meta.get("runtime_fix") or {}).get("kind"), "p2p_baseline": len(baseline),
        "p2p_excluded": len(excluded), "p2p_unstable": len(unstable),
        "p2p_unstable_collection": len(collection), "p2p_catch": len(catch), "p2p_runs_per_tree": 2,
        "shared_tmp_removed": len(removed), "pristine": trees["pristine"], "child_env_overrides": overrides,
        "fix_expected_sha256": hashlib.sha256(expected_text.encode()).hexdigest(),
        "p2p_baseline_sha256": hashlib.sha256(baseline_text.encode()).hexdigest()}, sort_keys=True) + "\n")
    for path in (EXPECTED, BASELINE, UNSTABLE, CATCH, RECEIPT):
        os.chmod(path, 0o600)
    print(f"prepared: {len(probes)} probes, {len(fixes)} fix trees, {len(baseline)} baseline tests, "
          f"{len(catch)} fail-on-buggy tests")


# --- grading ---------------------------------------------------------------------------------------

def sealed(path):
    st = os.lstat(path)
    return st.st_uid == 0 and not st.st_mode & 0o077 and not Path(path).is_symlink()


def read_ids(path):
    """Ids, one per line (they may contain spaces); an absent file (an older image) is empty."""
    try:
        return {line for line in Path(path).read_text().splitlines() if line}
    except FileNotFoundError:
        return set()


def unstable_note(unstable):
    return {"count": len(unstable), "examples": sorted(unstable)[:5],
            "note": "suite tests that passed in only some --prepare runs of the same tree, or whose ids those "
                    "runs did not collect identically (ids drawn at random at collection); excluded from the "
                    "P2P baseline, so they are never counted as regressions"}


def p2p_row(outcome, baseline, run):
    """The P2P check row from rca_grading.p2p_with_rerun's outcome (and its notes in `run`)."""
    lost = sorted(outcome["lost"])
    run["p2p_rerun"] = {"reran": outcome["reran"], "flaky_in_first_run": sorted(outcome["flaky"])[:5],
                        "flaky_count": len(outcome["flaky"])}
    detail = outcome["detail"]
    if not outcome["recorded"]:
        detail += "; no run produced a complete suite record, so no baseline test could be confirmed"
    elif lost:
        detail += (f"; {len(lost)} of {len(baseline)} previously passing tests no longer pass "
                   f"(e.g. {lost[0]})")
    else:
        detail += f"; {len(baseline)} baseline tests pass"
        if outcome["flaky"]:
            detail += f" ({len(outcome['flaky'])} only on the rerun)"
    unstable = run.get("p2p_unstable", {}).get("count")
    if unstable:
        detail += f"; {unstable} unstable suite tests excluded from the baseline"
    return {"id": "P2P:existing-suite", "component": "P2P",
            "status": "passed" if outcome["recorded"] and not lost else "failed", "detail": detail}


def catch_row(outcome, catch, run):
    """The fix:suite_catch F row from the same p2p_with_rerun outcome: the suite's fail-on-buggy
    tests (recorded at --prepare) that the candidate's fix must restore. Passed when every one of
    them passes (with the usual one-rerun); a correct fix restores them, a symptom-site or
    value-specific fix does not."""
    failed = sorted(outcome["lost"] & set(catch))
    run["p2p_catch"] = {"count": len(catch), "failed": failed[:5],
                        "note": "suite tests that fail on the buggy tree and pass on gold and every correct fix; "
                                "a correct fix must make them pass again"}
    if not outcome["recorded"]:
        detail = "no run produced a complete suite record, so the fail-on-buggy tests could not be confirmed"
    elif failed:
        detail = f"{len(failed)} of {len(catch)} tests the reported defect broke still do not pass (e.g. {failed[0]})"
    else:
        detail = f"the {len(catch)} tests the reported defect broke pass again"
    return {"id": "fix:suite_catch", "component": "F",
            "status": "passed" if outcome["recorded"] and not failed else "failed", "detail": detail}


def grade(workdir=WORKDIR):
    meta, manifest, rules = load_inputs()
    expected = json.loads(EXPECTED.read_text())
    baseline = {line for line in BASELINE.read_text().splitlines() if line}
    unstable = read_ids(UNSTABLE)
    catch = read_ids(CATCH)             # suite tests the defect broke; a correct fix restores them (F)
    budget = rg.Budget(BUDGET)
    scratch = scratch_dir()
    snap = rg.snapshot_tree(workdir, scratch / "agent")           # before any candidate code runs
    for path in (TESTS, OPT, EXPECTED):
        if not sealed(path):
            raise RuntimeError(f"{path} is not sealed root-only")
    sandbox = make_sandbox(scratch)
    run = {"grader": "templates/grade_go.py", "sandbox": sandbox.scan(), "snapshot_skipped": snap["skipped"],
           "p2p_unstable": unstable_note(unstable)}
    if not sandbox.unreadable(EXPECTED):
        raise RuntimeError("the candidate user can read the private expectations")
    try:
        run["prepare"] = json.loads(RECEIPT.read_text())
    except (OSError, ValueError):
        run["prepare"] = None
    checks = []

    # L
    agent = scratch / "agent"
    answer, problems = load_answer(agent / "rca.json")
    checks += answer_checks(answer, problems, meta, root=PRISTINE)   # bare names checked on buggy

    # R: source-less, on the solver view of buggy, gold, each alt fix and the runtime fix
    repro = reproducer_path(agent / "rca.json", meta)
    changes = rg.classify_changes(snap, PRISTINE, rules, repro)
    run.update({"reproducer": repro, "source_changes": len(changes["source"]),
                "deleted": len(changes["deleted"]), "test_files": len(changes["tests"]),
                "runner_control_excluded": changes["runner"]})   # never applied: pristine kept
    names = test_names(snap["files"][repro].read_bytes()) if repro in snap["files"] else []
    if repro is None or not repro.endswith("_test.go") or repro not in snap["files"]:
        checks += reproducer_missing("no regular *_test.go regression test at the path rca.json names"
                                     if repro else "no reproducer path")
    elif not names:
        checks += reproducer_missing("the regression test declares no TestXxx(t *testing.T)")
    else:
        extras = dict(changes["tests"])           # the agent's test files (no REPORT.md, no agent evidence/)
        extras[repro] = snap["files"][repro]
        extras.update(rg.task_evidence(manifest, TESTS))   # the task's own pristine evidence, where the agent saw it

        def outcome(label, kind, path, rebuilt=False):
            build(sandbox, rules, "solver", patches=[path] if kind == "patch" else [], files=extras)
            if rebuilt:
                rebuild_buggy(rules, extras)
            return reproducer_outcome(sandbox, repro, names, budget, f"repro:{label}",
                                      runtime=path if kind == "runtime" else None,
                                      flags=rebuilt_flags() if rebuilt else ())

        on_buggy = outcome("buggy", None, None)
        ran = on_buggy["outcome"] == "fail"
        on_rebuilt = outcome("rebuilt", None, None, rebuilt=True) if ran else None
        on_fixes = [(label, outcome(label, kind, path) if ran else None)
                    for label, kind, path in reproducer_trees(meta, TESTS)]
        checks += reproducer_checks(on_buggy, on_fixes, meta, on_rebuilt=on_rebuilt)

    # F: each hidden probe, source-less, on the solver view + the agent's non-test changes, once per
    # run setting (rg.PROBE_RUNS), each on a fresh tree; a probe passes only when every run matches.
    # A failed probe is rerun once in full (rg.probe_with_rerun) and passes only if the rerun passes.
    run["probe_reruns"] = {}
    for index, probe in enumerate(meta["fix_tests"]):
        check_id = "fix:gold" if index == 0 else f"fix:variant{index}"

        def rebuild(probe=probe):
            placed, program = probe_files(sandbox, probe, changes["source"])
            build(sandbox, rules, "solver", files=placed, deleted=changes["deleted"])
            return program
        ok, detail, reran = rg.probe_with_rerun(lambda attempt: probe_observation(
            sandbox, rebuild, budget, check_id if attempt == 1 else f"{check_id}:rerun"),
            expected[probe], RTOL, ATOL)
        if reran:
            run["probe_reruns"][check_id] = "passed on the rerun" if ok else "failed twice"
        checks.append({"id": check_id, "component": "F", "status": "passed" if ok else "failed", "detail": detail})

    # P2P + the suite's fail-on-buggy tests: the full suite on the full pristine tree + the agent's
    # non-test changes; a watched test that fails is rerun once and counts only if it fails in both
    # runs. The baseline must not regress (P2P); the fail-on-buggy tests (catch) must now pass (one
    # F row, fix:suite_catch) -- a correct fix restores the upstream tests the defect broke.
    def candidate_suite(attempt):
        build(sandbox, rules, "full", files=changes["source"], deleted=changes["deleted"])
        return suite_run(sandbox, meta["p2p"]["command"], budget.step(TIMEOUT["p2p"]),
                         "p2p" if attempt == 1 else "p2p:rerun")

    outcome = rg.p2p_with_rerun(candidate_suite, baseline | catch)
    checks.append(p2p_row({**outcome, "lost": outcome["lost"] & baseline,
                           "flaky": outcome["flaky"] & baseline}, baseline, run))
    if catch:
        checks.append(catch_row(outcome, catch, run))

    sandbox.populate(agent)
    run["runs"] = sandbox.runs
    write_rewards(OUT, checks, run=run)
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        prepare()
    else:
        grade(Path(sys.argv[1]) if len(sys.argv) > 1 else WORKDIR)
