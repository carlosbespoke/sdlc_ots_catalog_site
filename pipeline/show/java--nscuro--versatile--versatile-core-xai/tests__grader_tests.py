"""Generalized TEST-ONLY grader. Language comes from the manifest.

  reward = sum(weight of passed required tests) / sum(weight of all required tests)

Weights come from the manifest's optional "test_weights" ({test id: int >= 1},
capped shared credit over the reference's per-test coverage; see qweights.py),
for the languages in WEIGHTED_LANGS (Go) only. They are honoured only when EVERY
required test has an integer weight >= 1; ids outside required_tests are ignored.
Otherwise the grader falls back to the legacy "test_groups" (tests with identical
reference coverage count once: each required test outside a listed group is its
own group and the reward is the mean of the groups' pass fractions), and a
manifest with neither scores |passed| / |required|. No weight is ever 0, so 1.0
always needs every required test; for WEIGHTED_LANGS a partial result is also
never rounded to 1.0 or 0.0. Every other language (C++) scores exactly as before
weights existed: test_groups, else |passed| / |required|, rounded to 4 decimals.

Same load-bearing design as grader_go: a FIXED whitelist of test ids (captured
when the task was built), graded by the EXIT CODE of running each test against
the solver's impl. Absence == failure. Works for any language in langs.LANGS
via its `compile` and `run_one_tmpl`.

Usage: grader_tests.py <agent_impl_dir> <spec_dir> [manifest.json]
  manifest: {"required_tests":[...], "lang":"go|python|typescript|cpp",
             "test_weights":{id: int,...} | "test_groups":[[...],...]}
"""
import json
import atexit
from fractions import Fraction
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langs

AGENT = Path(sys.argv[1]).resolve()
SPEC = Path(sys.argv[2]).resolve()
MAN = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 and Path(sys.argv[3]).is_file() else {}
VDIR = Path(os.environ.get("MIG_VERIFIER_DIR", "/logs/verifier"))
VDIR.mkdir(parents=True, exist_ok=True)

REQUIRED = list(dict.fromkeys(MAN.get("required_tests") or []))
# Languages whose manifests carry "test_weights" (qweights.apply measures Go reference
# coverage only) and whose partial rewards are kept off 1.0 / 0.0. Mirrored by
# qweights.WEIGHTED_LANGS; any other language scores exactly as it did before weights.
WEIGHTED_LANGS = ("go",)
WEIGHTED = MAN.get("lang", "go") in WEIGHTED_LANGS


def _score_weights(required, raw):
    """{test id: int weight} for every required test, or None when "test_weights"
    is absent or unusable: it must be an object giving EVERY required test an
    integer weight >= 1 (bools rejected). Ids outside `required` are ignored."""
    if not isinstance(raw, dict) or not required:
        return None
    weights = {t: raw.get(t) for t in required}
    if not all(type(w) is int and w >= 1 for w in weights.values()):
        return None
    return weights


def _score_groups(required, raw):
    """Partition `required` into legacy scoring groups. Ids outside `required` and
    repeats are dropped, and every required test no group lists becomes its own
    group, so a stale or malformed "test_groups" can only fall back toward the
    unweighted score."""
    req, seen, groups = set(required), set(), []
    for group in raw if isinstance(raw, list) else []:
        members = [t for t in dict.fromkeys(group if isinstance(group, list) else [])
                   if isinstance(t, str) and t in req and t not in seen]
        if members:
            groups.append(members)
            seen.update(members)
    return groups + [[t] for t in required if t not in seen]


def _scoring(required, manifest):
    """(mode, groups, {test id: exact weight}) actually used to score. Groups are
    weights too: a test in a group of n is worth 1/n, so the weighted sum is the
    mean of the groups' pass fractions. test_weights count only for WEIGHTED_LANGS."""
    weights = (_score_weights(required, manifest.get("test_weights"))
               if manifest.get("lang", "go") in WEIGHTED_LANGS else None)
    if weights is not None:
        return "test_weights", None, {t: Fraction(w) for t, w in weights.items()}
    groups = _score_groups(required, manifest.get("test_groups"))
    mode = "test_groups" if any(len(g) > 1 for g in groups) else "uniform"
    return mode, groups, {t: Fraction(1, len(g)) for g in groups for t in g}


SCORING, GROUPS, WEIGHTS = _scoring(REQUIRED, MAN)


def _number(value):
    return int(value) if value.denominator == 1 else round(float(value), 4)


def score(passed_ids):
    """BINARY-GRADING (xAI): 1.0 iff every required test passed, else 0.0. The fractional
    score stays in reward_debug.json as "fractional_reward" for analysis only."""
    fractional, details = _fractional_score(passed_ids)
    ok = bool(REQUIRED) and all(t in passed_ids for t in REQUIRED)
    return (1.0 if ok else 0.0), {**details, "fractional_reward": fractional, "reward_mode": "binary"}


def _fractional_score(passed_ids):
    """(reward, reward_debug fields) for a set of passed test ids. The ONLY place a
    reward is computed (final, in-progress flushes and the signal path), in exact
    Fractions: passing every required test is exactly 1.0, passing none is 0.0, and
    (WEIGHTED_LANGS) 4-decimal rounding never turns a partial result into either end."""
    passed = [t for t in REQUIRED if t in passed_ids]
    got = sum((WEIGHTS[t] for t in passed), Fraction(0))
    total = sum(WEIGHTS.values(), Fraction(0))
    reward = round(float(got / total), 4) if total else 0.0
    if WEIGHTED and 0 < got < total:
        reward = min(max(reward, 0.0001), 0.9999)
    details = {"scoring": SCORING,
               "unweighted_reward": round(len(passed) / len(REQUIRED), 4) if REQUIRED else 0.0,
               "weight_passed": _number(got), "weight_total": _number(total)}
    if GROUPS is not None:
        details["score_groups"] = len(GROUPS)
    return reward, details


LANG = langs.get(MAN.get("lang", "go"))
# STRICT COMPARISON (C++): the task manifest selects the harness's trusted-value
# comparisons (langs._TH_STRICT) by compiling with -DMIG_STRICT_COMPARE=1. The
# manifest is grader-owned, so the solver cannot choose the mode; a macro the solver
# defines or undefines to change it is rejected (cpp_macro_trace_ban).
STRICT = bool(getattr(langs, "strict_compare", lambda m: False)(MAN)) and LANG["name"] == "cpp"
CPP_DEFS = [langs.STRICT_DEFINE] if STRICT else []
if LANG["name"] == "cpp" and "mig_guard.hpp" in LANG["module_files"]:
    CPP_DEFS = ["-include", "mig_guard.hpp"] + CPP_DEFS       # see langs._MIG_GUARD
# GRADER-OWNED SPEC FILES (C++): headers the hidden tests include from the spec dir
# (e.g. value_checks.hpp / signature_contract.hpp with assertion helpers) are
# grader-owned. They used to be overwritten by a solver `.hpp` of the same name,
# which let the solver replace the very helpers that compare its results. A solver
# file with a spec file's path is now ignored (never copied, scanned or compiled);
# crate.hpp stays the solver's even if a spec ships a copy of it.
SPEC_OWNED = ({str(p.relative_to(SPEC)) for p in SPEC.rglob("*") if p.is_file()} - {"crate.hpp"}
              if LANG["name"] == "cpp" and SPEC.is_dir() else set())
ENV = {**os.environ,
       "PATH": "/usr/local/go/bin:/usr/local/bin:" + os.environ.get("PATH", "/usr/bin:/bin"),
       "HOME": "/tmp", "GOFLAGS": "-mod=mod", "GOCACHE": "/tmp/gc", "GOPATH": "/tmp/gp",
       "GOPROXY": "off", "CGO_ENABLED": "0"}

# ---- build limits + evidence --------------------------------------------------
# Horizon's verifier has 2 vCPUs and ~8 GB for the whole container, and runs ~2-3x
# slower than the VM. A reference whose test TU needs 12.4 GB to compile
# (karpeleslab--intlrs: a huge constant table) passed local certification and then
# failed hosted validation (the verifier was killed with no grader output). Every
# C++ compiler process the grader starts therefore runs under an address-space cap
# (MIG_COMPILE_MEM_MB, default 6144): such a build now fails locally the way it
# fails hosted. g++/cc1plus reserve little beyond what they use (measured), so an
# honest build is unaffected. Go/TS are not capped: their runtimes reserve virtual
# address space far beyond what they use (see TEST_MEM_KB below).
# Evidence for the next such investigation, recorded in reward_debug.json: wall
# seconds and peak RSS of the build and of every C++ test TU, wall seconds of every
# test, and why each failed test failed (capped). Scoring is unchanged.
COMPILE_MEM_MB = int(os.environ.get("MIG_COMPILE_MEM_MB", "6144"))
CAP_COMPILE = LANG["name"] == "cpp" and COMPILE_MEM_MB > 0
BUILD = {"mem_cap_mb": COMPILE_MEM_MB if CAP_COMPILE else None, "tus": {}}
FAILED_SHOWN = 25                  # failed tests detailed in the printed result
try:
    TEST_WORKERS = max(1, int(os.environ.get("MIG_TEST_WORKERS") or 8))
except ValueError:
    TEST_WORKERS = 8
SLOWEST_SHOWN = 10
# Go: a test that hit its time limit in the parallel pass is run once more ALONE.
# Horizon's verifier runs 8 tests at once on 2 vCPUs: reference tests taking 4-10 s
# alone on the VM hit the 60 s limit there (caldata-rs 8 tests, heavykeeper 3), so
# an honest port lost them. Serial and capped. Deterministic: the first
# GO_TIMEOUT_RETRIES timed-out tests in test-id order each get exactly one retry;
# nothing depends on the clock (a "time left" gate made the score depend on how
# slow the verifier was, which Argus "Grader determinism" blocked on 12 Go tasks,
# 2026-10-05). The SIGALRM budget stays the only backstop.
GO_TIMEOUT_RETRIES = int(os.environ.get("MIG_GO_TIMEOUT_RETRIES", "16"))


def capped_argv(argv):
    """`argv` run under the compile address-space cap (C++)."""
    if not CAP_COMPILE:
        return list(argv)
    return ["/bin/sh", "-c", f'ulimit -v {COMPILE_MEM_MB * 1024} 2>/dev/null; exec "$0" "$@"', *argv]


def capped_shell(cmd):
    """Shell command `cmd` run under the compile address-space cap (C++)."""
    return f"ulimit -v {COMPILE_MEM_MB * 1024} 2>/dev/null; {cmd}" if CAP_COMPILE else cmd


def measured_run(cmd, *, cwd, timeout, shell=False, env=None):
    """subprocess.run(cmd, capture_output=True) that also returns the wall seconds
    and the peak RSS in MB of the process tree it waited for (wait4's ru_maxrss: the
    largest of the child and its reaped descendants, i.e. cc1plus for a g++ build).
    Raises subprocess.TimeoutExpired after killing the process group."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        start = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=cwd, shell=shell, env=env or ENV, stdout=out,
                                stderr=err, start_new_session=True)
        while True:
            pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - start > timeout:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                os.wait4(proc.pid, 0)
                proc.returncode = -9
                raise subprocess.TimeoutExpired(cmd, timeout)
            time.sleep(0.02)
        proc.returncode = os.waitstatus_to_exitcode(status)
        seconds = time.monotonic() - start
        out.seek(0)
        err.seek(0)
        scale = 1024 * 1024 if sys.platform == "darwin" else 1024     # bytes vs KiB
        return (subprocess.CompletedProcess(cmd, proc.returncode, out.read(), err.read()),
                round(seconds, 2), round(usage.ru_maxrss / scale, 1))


_OOM_TEXT = re.compile(r'virtual memory exhausted|out of memory allocating|Cannot allocate memory'
                       r'|std::bad_alloc|Killed signal terminated program|fatal error: Killed')

# ---- runtime test-read isolation (HELD-OUT hardening) -----------------------
# Under held-out grading the hidden *_test.go live in the build dir NEXT TO the
# solver's impl, and the grader compiles them together and runs the resulting
# binary there, as root. Because the solver's impl is LINKED INTO that binary, it
# can read the co-located test SOURCE at RUNTIME — not by importing a banned pkg,
# but via any std-lib reader whose os/io import lives inside the STD-LIB package
# rather than the impl: `go/parser.ParseDir(".")`, `text/template.ParseFiles`,
# `go/build`, `debug/elf.Open`, `archive/zip.OpenReader`, … — and simply return
# the asserted values. (Proven PoC: a stub crate that reads TestGetBytesWorks's
# `[]byte{..}` literal and returns it scores credit; it even tracks a mutated
# expected value.) Import-path bans cannot close this: the reader packages are
# legitimate for honest ports (false-rejects) and the list is unbounded.
#
# Architectural fix (no token bans, language-general for standalone-binary langs):
# run the compiled test binary from a FRESH run dir that contains ONLY the binary
# plus data fixtures (testdata/), as an unprivileged uid, with the build dir and
# the spec dir made unreadable to that uid. The binary itself is root-owned and
# EXECUTE-ONLY (0711): the expected literals are compiled into it, and an impl
# could otherwise read them back via debug/elf.Open("/proc/self/exe"). Honest
# ports are unaffected (they compute; they never read the tests). Residual: an
# unsafe-pointer walk of the process's own memory is not prevented.
# C++ fits the SAME shape: its test artifact (mig_tb) is a standalone binary, and
# the identical answer-leak was open there — crate.hpp compiled into mig_tb could
# `#include <fstream>` and read the co-located `*_test.cpp` SOURCE (or the absolute
# spec copy, or its own /proc/self/exe) at runtime and return the asserted literals
# (proven PoC: a stub crate scores 1.0 by parsing `CHECK_EQ(Double(2), 4)` out of
# the test file). No token ban closes it (<fstream> is legitimate for honest ports;
# the reader set is unbounded), so cpp joins the structural fix: the test binary
# runs from a clean run dir, as the sandbox uid, with the build dir + spec dir made
# root-only and mig_tb execute-only (0711) so neither the co-located source nor the
# embedded literals are readable. Python/TS keep running in-tree (their runners must
# read the source and rely on the import bans), so isolation stays gated to langs
# whose test artifact is a standalone binary. If dropping privileges is not possible
# (not root, or the verifier lacks CAP_SETUID/CAP_SETGID) the tests still run from
# the clean run dir as the current user and reward_debug records
# isolation_enforced=false; it never turns a failed drop into failed tests. That
# fallback only hides the co-located source: the absolute spec copy and the binary
# stay readable, so a delivered task's rollouts must show isolation_enforced=true.
ISOLATE_LANGS = {"go", "cpp"}                  # langs whose test artifact is a binary
ISOLATE = LANG["name"] in ISOLATE_LANGS
SANDBOX_UID = int(os.environ.get("MIG_SANDBOX_UID", "65534"))   # `nobody`
# Address-space cap per test process: a runaway allocation (e.g. a parser loop
# that appends without advancing) fails that test instead of exhausting the VM,
# which Horizon reports as an errored rollout with no score. The limit is on
# virtual memory: a Go 1.21 test binary reserves ~0.7 GB before running anything
# (0.5 GB will not even start it), so 2 GB leaves an honest test ~1.3 GB of heap.
# A C++ mig_tb reserves almost nothing (a trivial g++ -O0 binary runs under a
# 16 MB -v cap, measured), so the same 2 GB cap is ample headroom for an honest
# port. (node is deliberately NOT isolated/capped: V8 reserves tens of GB of
# virtual address space and aborts under any -v below ~8+ GB — measured — so a
# virtual cap cannot be set safely; TS relies on the container's RSS memory_mb.)
TEST_MEM_KB = int(os.environ.get("MIG_TEST_MEM_KB", str(2 * 1024 * 1024)))
HAVE_SETPRIV = shutil.which("setpriv") is not None
# Decided once by _probe_drop() inside setup_runspace(): True only when a child
# actually ran as SANDBOX_UID.
ISOLATION = {"can_drop": False}
# {cwd, env} the test binary runs in; replaced by setup_runspace() after the build.
RUNSPACE = {"cwd": None, "env": ENV}


def _drop_privs():                             # preexec_fn fallback when no setpriv
    os.setgroups([])
    os.setgid(SANDBOX_UID)
    os.setuid(SANDBOX_UID)


def _wrap(cmd, kw):
    if not (ISOLATE and ISOLATION["can_drop"]):
        return cmd
    if HAVE_SETPRIV:
        return ("setpriv --reuid %d --regid %d --clear-groups --inh-caps=-all -- /bin/sh -c %s"
                % (SANDBOX_UID, SANDBOX_UID, shlex.quote(cmd)))
    kw["preexec_fn"] = _drop_privs
    return cmd


def _probe_drop():
    """True iff a child process really runs as SANDBOX_UID (root with
    CAP_SETUID/CAP_SETGID). Checked, not assumed: a capability-restricted
    verifier must fall back instead of failing every test."""
    if not (hasattr(os, "geteuid") and os.geteuid() == 0):
        return False
    ISOLATION["can_drop"] = True
    kw = dict(shell=True, capture_output=True, timeout=30)
    try:
        r = subprocess.run(_wrap("id -u", kw), **kw)
        ok = r.returncode == 0 and r.stdout.decode(errors="replace").strip() == str(SANDBOX_UID)
    except Exception:
        ok = False
    ISOLATION["can_drop"] = ok
    return ok


def _run_cmd(cmd, timeout):
    """Run one test / list command in the (possibly isolated) run space. When
    isolating AND running as root, drop to SANDBOX_UID via setpriv (preferred:
    clears supplementary groups + inheritable caps, no fork-in-threadpool hook) or
    an os.setuid preexec_fn fallback. When NOT root (local dev) the clean run dir
    has already removed the cwd source-leak and there is no privilege boundary to
    enforce, so we run in place as the current user — honest grading is unchanged
    and nothing regresses."""
    if LANG["name"] in GROUP_KILL_LANGS:
        return _run_test_group(cmd, timeout)
    kw = dict(shell=True, capture_output=True,
              cwd=RUNSPACE["cwd"], env=RUNSPACE["env"], timeout=timeout)
    if ISOLATE:
        cmd = f"ulimit -v {TEST_MEM_KB} 2>/dev/null; {cmd}"
    return subprocess.run(_wrap(cmd, kw), **kw)


# Languages whose test process runs in its own session and dies with its whole
# process group on timeout (a timed-out shell otherwise leaves the test running).
GROUP_KILL_LANGS = ("cpp", "go")
# Process groups of the test processes running now (killed on a budget signal).
LIVE_GROUPS = set()


def _kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def _run_test_group(cmd, timeout):
    """_run_cmd for C++: the shell execs the test binary (so the binary is the shell's
    process, not a child of it) in a session of its own, and a timeout kills that
    whole process group. subprocess.run(shell=True, timeout=) killed only the shell,
    and a looping ./mig_tb outlived the grader at 100% CPU (cydhra--vers: four
    EliasFano*NearMaximum tests ran 10 h as orphans in a deleted run dir)."""
    kw = {}
    cmd = (f"ulimit -v {TEST_MEM_KB} 2>/dev/null; " if ISOLATE else "") + "exec " + cmd
    cmd = _wrap(cmd, kw)
    proc = subprocess.Popen(cmd, shell=True, cwd=RUNSPACE["cwd"], env=RUNSPACE["env"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, **kw)
    LIVE_GROUPS.add(proc.pid)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)                # leader not reaped yet: the pgid is still ours
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                # a process that left the group (setsid) still holds the pipes open:
                # stop reading rather than block until the verifier deadline
                for f in (proc.stdout, proc.stderr):
                    try:
                        f.close()
                    except OSError:
                        pass
                proc.wait()
                out, err = b"", b""
            raise subprocess.TimeoutExpired(cmd, timeout, output=out, stderr=err)
        except BaseException:
            _kill_group(proc.pid)
            proc.wait()
            raise
    finally:
        LIVE_GROUPS.discard(proc.pid)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _restore_mode(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:                              # e.g. the temp build dir is gone
        pass


def setup_runspace(work):
    """Return (cwd, env) for executing the compiled test binary.

    Non-isolated langs (python/typescript) -> the build dir unchanged (their
    runners must read the source tree; they rely on the import bans). Isolated
    langs (go, cpp) -> a fresh dir holding ONLY the built binary + non-source
    fixtures (testdata/*), with the build dir and spec dir made root-only so the
    sandbox uid cannot reach the hidden tests even via the binary's embedded
    absolute source paths. The source-file skip below is language-general: it
    drops every file whose name ends in the lang's test_suffix (go `_test.go` /
    cpp `*_test.cpp`), is a module file, or is an impl source (the lang ext,
    `.go`/`.hpp`) outside testdata — so for cpp only mig_tb and data fixtures
    reach the run dir, never crate.hpp or the `*_test.cpp` answer source.
    HOME/TMPDIR/GOCACHE/GOPATH point inside the run dir so the test binary's
    t.TempDir()/caches work for the dropped uid."""
    if not ISOLATE:
        return str(work), ENV
    run = Path(tempfile.mkdtemp(prefix="mig_run_"))
    skip = set(MODFILES) | {"go.sum"}
    for f in work.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(work)
        name = f.name
        if name == "mig_tb":                         # the test binary itself
            dst = run / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            dst.chmod(0o755)
            continue
        in_testdata = "testdata" in rel.parts[:-1]
        if (name.endswith(LANG["test_suffix"]) or name in skip or name.endswith((".o", ".a"))
                or (name.endswith(LANG["ext"]) and not in_testdata)):
            continue                                 # NEVER copy test source / impl source / modules
        dst = run / rel                              # keep data fixtures (testdata/*)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
    for d in (".home", ".tmp", ".cache", ".gopath"):
        (run / d).mkdir(exist_ok=True)
    env = {**ENV, "HOME": str(run / ".home"), "TMPDIR": str(run / ".tmp"),
           "GOCACHE": str(run / ".cache"), "GOPATH": str(run / ".gopath")}
    if _probe_drop():
        # build + spec dirs: root-only (0700). mkdtemp already makes `work` 0700,
        # but a child package dir may be 0755; 0700 on the ROOT blocks traversal
        # regardless, so the sandbox uid can open neither the co-located nor the
        # original spec copy of any *_test.go.
        for d in (work, SPEC):
            try:
                mode = d.stat().st_mode & 0o7777
                os.chmod(d, 0o700)
                # The spec dir may be a bundle on disk (pipeline-side grading):
                # give it its permissions back when the grader exits.
                atexit.register(_restore_mode, d, mode)
            except Exception:
                pass
        # run dir: root-owned with the sticky bit, so the sandbox uid may create
        # files there but cannot rename or replace the root-owned binary or the
        # fixtures; only its HOME/TMPDIR/cache dirs belong to it.
        for d in (".home", ".tmp", ".cache", ".gopath"):
            os.chown(run / d, SANDBOX_UID, SANDBOX_UID)
        run.chmod(0o1777)
        # Root-owned, execute-only: the sandbox uid can run it but not read the
        # expected values compiled into it (e.g. via /proc/self/exe).
        for tb in run.rglob("mig_tb"):
            os.chown(tb, 0, 0)
            tb.chmod(0o711)
    return str(run), env

# light per-language anti-cheat: the impl must not redefine tests or hard-exit.
# Patterns are matched on a COMMENT-STRIPPED copy (see static_reject) so words
# in doc comments (e.g. Rust's `unsafe`) don't false-reject an honest impl.
# Exit primitives are banned comprehensively: a `func init(){ syscall.Exit(0) }`
# (or os.Exit/runtime.Goexit) forces `go test` to print `ok` before any
# assertion runs — a grading bypass (argus, dusk-plonk v2). syscall.* is never
# needed by a from-scratch algorithm port. `unsafe.` (usage) is banned; the bare
# word is not (it appears in comments).
# Exit-code grading is only faithful if the impl CANNOT force the process to
# exit 0. A regex over calls (os.Exit) is evadable by import alias / dot-import
# (argus, dusk-plonk v3: `import oo "os"; oo.Exit(0)` -> 1.0). So we ban the
# IMPORT-PATH STRING of every package that provides a process exit / process
# control — the path literal is present regardless of alias (`import . "os"`
# still contains `"os"`). A from-scratch algorithm port never needs these; with
# them gone the process exit code reflects the real test results.
# Anti-cheat bans, in THREE categories (red-team audit, dusk-plonk):
#   import: banned import PATHS (exit/process/net/embed). Matched on comment-
#           stripped-but-STRING-PRESERVED text with a line-anchored regex that
#           swallows `import` + any number of alias/`_`/`.` tokens — so it
#           catches `import oo "os"`, `import . "os"`, `import _ "unsafe"`,
#           `import _ "embed"`, grouped, and plain forms, but NOT a `"os"` in a
#           map key / struct tag / normal string.
#   code:   patterns matched on comment-AND-string-stripped text (so a string
#           literal like "run testing.Main" can't false-reject). Test-function
#           bans require the *testing.T signature (a `func TestVectorParse(s
#           string)` helper is fine).
#   raw:    compiler directives (`//go:linkname`) — these are `//` COMMENTS, so
#           they must be scanned on the ORIGINAL text before comment-stripping.
# `embed` closes the go:embed answer-leak (impl embeds the co-located test file);
# exit-path bans make the process exit code faithful (impl can't force exit 0).
# Go banned import PATHS. Rather than a fragile line-anchored regex (evadable by
# aliased / dot / blank / single-line-parenthesized / semicolon import forms,
# argus v3..v7), we EXTRACT every imported path with go_banned_import() and check
# membership here — form-independent. A from-scratch algorithm port needs none of
# these; with them gone the process cannot force exit 0 (so exit-code grading is
# faithful) and cannot embed/read the co-located test file or offload over net.
# Only LOAD-BEARING paths are banned (argus dusk-plonk v9: an undisclosed ban on
# a path an honest impl might legitimately use — and that `go test` accepts — is a
# false-reject bug). Each entry here is necessary for exit-code grading soundness
# AND is DISCLOSED to the solver in instruction.md:
#   os/os/exec/syscall/runtime/plugin/C  -> could force an early exit 0 (process
#                                           control), defeating exit-code grading
#   io/ioutil/embed                      -> could read/embed the co-located answer
#                                           (the immutable test file)
#   net/net/http/net/rpc                 -> could offload the answer over the wire
#   flag                                 -> process control without `os`: a FlagSet with
#                                           ExitOnError parsing "-h" from package init
#                                           exits the test binary 0 before any test runs
#                                           (reproduced: reward 1.0 with no implementation)
#   testing, testing/...                 -> the test runner's own package; impl code that
#                                           reaches it can take over the binary's flags.
#                                           Previously only a token regex (evadable);
#                                           now enforced by the toolchain check too.
# `reflect` stays allowed. `unsafe` is banned again (2026-10-05): Argus found Go
# ports reading the hidden tests' compiled-in expected values from process memory
# with an unsafe stack walk and passing tests with no implementation (json-five-rs;
# Java task commons-codec, >=36% of the weight, with filesystem isolation on). The
# answer is in the test binary's own memory, so isolation cannot stop it. Banning
# the import also closes //go:linkname, which needs it.
GO_BANNED_PATHS = {"os", "os/exec", "syscall", "runtime", "plugin",
                   "io/ioutil", "net", "net/http", "net/rpc", "embed", "C",
                   "flag", "testing", "unsafe"}
GO_BANNED_PREFIXES = ("testing/",)


def go_path_banned(path):
    return path in GO_BANNED_PATHS or path.startswith(GO_BANNED_PREFIXES)
# Process-exit / process-abort primitives an agent could use to force exit 0 for a
# failing test under EXIT-CODE cpp grading. err/errx/verr/verrx (from <err.h>) and
# abort internally terminate the process. Reused by the static pre-filter AND the
# authoritative g++ -E preprocessed scan (cpp_exit_preprocessed_ban).
# EXIT-0 primitives only (things that terminate the process with a chosen 0 code).
# Excludes abort/__builtin_trap (they raise a signal -> NON-zero exit, can't force a
# PASS) and bare err/verr (too collision-prone with honest `.err()`/`error()`
# accessors; <err.h> is import-banned and errx/verrx are matched). All are matched
# ONLY as CALLS WITH AN ARGUMENT `name(<something>)`, so a no-arg `exit()` member
# method and bare identifiers are not false-rejected.
# NB: bare err/verr are NOT here — they collide with the ubiquitous `int16_t& err`
# out-param / `err(x)` helper idiom (false-reject). The <err.h> family is handled
# by the import ban + a narrow 2+-arg-signature ban (ERRH_CALL) that matches the
# libc err(int,fmt,...) shape but not a 1-arg honest `err(x)`.
EXITPRIMS = (r'(?:exit|_exit|_Exit|quick_exit|pthread_exit|thrd_exit|'
             r'__builtin_exit|__builtin__Exit|exit_group|_exit_group)')
# <err.h> exiting funcs. errx/verrx/errc are Unix-only fatal funcs an honest
# ALGORITHM port never calls -> ban their CALLS outright. err/verr collide with
# honest `err` out-params/helpers -> match only the libc VARARGS DECLARATION the
# forge must write (import ban blocks <err.h>). So an honest non-varargs
# `err(const char*,const char*)` helper (toml_datetime) is NOT matched.
# NB: `errc` is NOT banned — it collides with C++17 `std::errc` (false-reject,
# csv-core). Only errx/verrx (Unix-only fatal) are call-banned.
ERRH_CALL = (r'(?:\b(?:errx|verrx)\s*\('
             r'|\b(?:err|verr)\s*\([^;{)]*\.\.\.\s*\))')
# Runtime symbol resolution defeats ALL source-token bans: dlsym(RTLD_DEFAULT,
# "_exit") resolves an exit primitive by a (char-array) name at runtime. Ban the
# mechanism itself (load-bearing under exit-code grading).
DLSYM_BAN = [r'\bdl(?:sym|open|vsym|mopen)\b', r'\bRTLD_\w+\b', r'\b__libc_dlsym\b']
# OBJECT-LEVEL forge defense (the authoritative cpp anti-cheat — see
# cpp_object_symbol_ban). Source/preprocessed token scans provably do NOT converge:
# a forge `err(0,"x")` (libc err->exit) is STATICALLY indistinguishable from an
# honest helper `err("date","month")` — the difference is only LINK-TIME symbol
# resolution, invisible to any source token. At the OBJECT level that resolution is
# visible: an honest helper is a DEFINED symbol in the agent TU; a libc forge is an
# UNDEFINED symbol that will resolve to libc. So we scan the compiled agent object
# for UNDEFINED references to the finite set of exit-0-CAPABLE libc entry points.
# This is immune to every source obfuscation (macro/token-paste/line-splice/#line
# spoof/pointer-decay/alias/weakref/template) because it inspects what the COMPILER
# EMITTED, not what the source spelled — and it needs NO call-graph analysis: a
# banned symbol referenced ANYWHERE in the TU (even transitively via a helper) is an
# UND entry regardless of who calls it. Set = only symbols that can terminate with a
# chosen 0 exit code (abort/error excluded: they can't force exit 0). Raw inline-asm
# exit (`mov $60,%rax; syscall`) emits no symbol -> caught by the .text syscall scan.
BANNED_SYMS = re.compile(
    r'^(?:exit|_exit|_Exit|quick_exit|pthread_exit|thrd_exit|__builtin_exit|'
    r'__builtin__Exit|exit_group|_exit_group|err|errx|verr|verrx|'
    r'execl|execlp|execle|execv|execvp|execvpe|execve|fexecve|'
    r'system|posix_spawn|posix_spawnp|dlsym|dlopen|dlvsym|dlmopen|__libc_dlsym|'
    r'longjmp|siglongjmp|_longjmp|__longjmp_chk|'
    # W^X / code-injection primitives (argus const-oid v20 bypass: a global ctor
    # mmap()s an RWX page, memcpy's exit_group(0) shellcode, and calls it — the
    # syscall opcode is .rodata DATA (not a .text instruction) and the only UND
    # symbols are mmap/memcpy, so the token/UND/.text scans all miss it). Executing
    # injected data REQUIRES a writable+executable page: mmap(PROT_EXEC) or mprotect
    # adding PROT_EXEC. Banning the W^X syscalls closes the whole code-injection
    # class (an honest data-crate port never maps or reprotects memory) — a class
    # cut, not a token. memcpy stays allowed (ubiquitous); without an exec page it
    # is harmless.
    r'mmap|mmap64|__mmap|mprotect|__mprotect|pkey_mprotect|mremap|'
    r'memfd_create|shmat|shmdt|remap_file_pages|__libc_dlopen_mode)$')
# Macro names a solver may never #define/#undef (fast source-level pre-filter; the
# authoritative rule is cpp_macro_trace_ban): C++ keywords (`#define static_assert(...)`
# neutered a spec header's type pin), the harness macros, assert/NDEBUG (a test's
# <cassert> checks) and the grader's own MIG_* switches.
_CPP_KEYWORDS = (
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char char8_t "
    "char16_t char32_t class compl concept const consteval constexpr constinit const_cast "
    "continue co_await co_return co_yield decltype default delete do double dynamic_cast "
    "else enum explicit export extern false float for friend goto if inline int long "
    "mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected "
    "public register reinterpret_cast requires return short signed sizeof static "
    "static_assert static_cast struct switch template this thread_local throw true try "
    "typedef typeid typename union unsigned using virtual void volatile wchar_t while xor "
    "xor_eq final override import module").split()
_CPP_HARNESS_MACROS = ["CHECK", "CHECK_EQ", "CHECK_NEAR", "CHECK_THROWS", "TEST", "assert",
                       "NDEBUG", "defined", "__VA_ARGS__", "__VA_OPT__", "_Pragma",
                       "__has_include", "__has_cpp_attribute"]
CPP_PROTECTED_MACRO = (r'(?:MIG_\w*|' + "|".join(re.escape(k) for k in sorted(
    _CPP_KEYWORDS + _CPP_HARNESS_MACROS, key=len, reverse=True)) + r')')
# Every way solver code can NAME the harness namespaces (langs._TH_HPP): `th::x` /
# `::th::x` / `using th::x`, reopening `namespace th`, an alias (`namespace hh = th;`
# / `= ::th;`, which `\bth\s*::` never saw: `template<> void hh::check_eq<int,int>(...)
# {}` and `template<> struct hh::cmp::i128<Box> : std::true_type {}` forged every
# comparison, strict mode included), a using-directive, and the reserved namespace
# that holds the comparison machinery. Scanned on comment/string-stripped source and
# on the g++ -E text of agent files (macro-pasted spellings).
CPP_HARNESS_REFS = [r'\bth\s*::', r'\bnamespace\s+th\b',
                    r'\bnamespace\s+[A-Za-z_]\w*\s*=\s*(?:::\s*)?th\b',
                    r'\busing\s+namespace\s+(?:::\s*)?th\b',
                    r'\b__mig_th\b']


def _match_brace(text, i):
    """Index of the `}` closing the `{` at text[i] (or len(text) when unbalanced)."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return len(text)


def _match_angle(text, i):
    """Index just past the `>` closing the `<` at text[i] (or -1). Angle brackets
    inside parentheses (`(N > 3)`) do not count."""
    depth = paren = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "(":
            paren += 1
        elif c == ")":
            paren -= 1
            if paren < 0:
                return -1
        elif paren:
            continue
        elif c == "<":
            depth += 1
        elif c == ">":
            depth -= 1
            if depth == 0:
                return j + 1
        elif c in ";{}":
            return -1
    return -1


_STD_NS = r'(?:std|__gnu_cxx|__cxx11|__detail|__gnu_debug)'
_STD_ROOTS = frozenset(("std", "__gnu_cxx", "__cxx11", "__detail", "__gnu_debug"))
_QN_START = re.compile(r'(?<![\w$])(::\s*)?([A-Za-z_]\w*)')
_QN_NEXT = re.compile(r'\s*(~?[A-Za-z_]\w*)')
_NAME_STOP = frozenset(_CPP_KEYWORDS) - {"operator", "template"}
# One item of the only `namespace std { ... }` content allowed: a full or partial
# specialization of std::hash (`template<> struct hash<T>` / `template<class T>
# struct hash<Box<T>>`), declared or defined.
_HASH_HEAD = re.compile(r'\s*template\s*<')
_HASH_CLASS = re.compile(r'\s*(?:struct|class)\s+(?:\[\[[^\]]*\]\]\s*)*(?:hash|less|equal_to)\s*<')
# What may follow `hash<...>` before its body: `final`, then a base clause
# (`: hash<std::uint32_t>`, `: public std::hash<int>`).
_HASH_FINAL = re.compile(r'final\b')


def _skip_ws(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _qualified_names(text):
    """[(start, end, components)] of every (possibly qualified) name in `text`, left
    to right. Template argument lists are skipped as a whole (balanced), so
    `std::vector<int>::size` is ONE name [std, vector, size] and the `Fmt<Foo>` of
    `std::string Fmt<Foo>::operator()` is a separate name from `std::string`. A name
    ends at `operator` (what follows is the operator symbol)."""
    out, pos = [], 0
    while True:
        m = _QN_START.search(text, pos)
        if not m:
            return out
        comps, end = [m.group(2)], m.end()
        # (a keyword is never a name component: `struct ::std::less` is `struct` and
        # the global-qualified `::std::less`)
        while comps[-1] != "operator" and comps[-1] not in _NAME_STOP:
            j = _skip_ws(text, end)
            if j < len(text) and text[j] == "<":
                close = _match_angle(text, j)
                if close < 0:
                    break
                end = close
                j = _skip_ws(text, end)
            if not text.startswith("::", j):
                break
            nxt = _QN_NEXT.match(text, j + 2)
            if not nxt:
                break
            comps.append(nxt.group(1))
            end = nxt.end()
        out.append((m.start(), end, comps))
        pos = max(end, m.end())


def _std_rooted(comps):
    return comps[0] in _STD_ROOTS


def _declarator_region(head):
    """`head` up to the parameter list of the declared function: the first `(` that
    does not belong to an `operator()` name or to a name's template arguments
    (`std::function<void()>::operator bool`), the whole head for a variable."""
    spans = [(a, b) for a, b, _ in _qualified_names(head)]
    i = 0
    while True:
        p = head.find("(", i)
        if p < 0:
            return head
        inside = next((b for a, b in spans if a <= p < b), None)
        if inside is not None:
            i = inside
            continue
        if re.search(r'\boperator\s*$', head[:p]):
            close = head.find(")", p)
            i = p + 1 if close < 0 else close + 1
            continue
        return head[:p]


def _match_paren(text, i):
    """Index just past the `)` closing the `(` at text[i] (or len(text))."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(text)


def _match_bracket(text, i):
    """Index just past the `]` closing the `[` at text[i] (or len(text)). Nested
    brackets count, so the `[[...]]` of `[[gnu::aligned(al[idx[0]])]]` ends at its own
    `]]`, not at the first `]]` inside it."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(text)


_CLASS_HEAD_ATTR = re.compile(r'(?:alignas|__attribute__|__attribute|__declspec)\s*\(')


def _skip_attributes(text, i):
    """Index of the first character at or after text[i] that is not whitespace or an
    attribute (`[[...]]` by bracket depth, `alignas(...)`, `__attribute__((...))`,
    `__declspec(...)`)."""
    while True:
        i = _skip_ws(text, i)
        if text.startswith("[[", i):
            i = _match_bracket(text, i)
            continue
        m = _CLASS_HEAD_ATTR.match(text, i)
        if not m:
            return i
        i = _match_paren(text, m.end() - 1)


def _class_name_start(head, i):
    """Where the class-head name starts in `head` after its class-key (at i): past
    attributes (`[[...]]`, `alignas(...)`, `__attribute__((...))`), which may sit
    between the class-key and the name (`template<> struct [[deprecated]] std::less<K>`).
    `head` is cpp_code_only() text, so a digraph `<:<:...:>:>` reads as `[[...]]`."""
    return _skip_attributes(head, i)


def _declarator_comps(head):
    """Components of the name the declaration `head` declares (text after a template
    parameter list up to its body / `;` / initializer): the class-head name of a
    class, else the operator name or the last name before the parameter list. None
    when there is none."""
    cls = re.match(r'\s*(?:friend\s+)?(?:struct|class|union)\b', head)
    if cls:
        start = _class_name_start(head, cls.end())
        return next((c for a, _, c in _qualified_names(head) if a == start), None)
    names = _qualified_names(_declarator_region(head))
    for _, _, comps in names:
        if comps[-1] == "operator":
            return comps
    return names[-1][2] if names else None


def _hash_member(comps, explicit):
    """True when `comps` names a member of a std::hash specialization (`hash<K>::
    operator()`, `std::hash<Box<T>>::operator()`) in a declaration that is not itself
    an explicit specialization (`template<>`): the out-of-line definition of a member
    of the solver's own std::hash specialization."""
    return (not explicit and len(comps) >= 2 and comps[-2] in ("hash", "less", "equal_to")
            and all(c in _STD_ROOTS for c in comps[:-2]))


def _parenthesized_declarator(head):
    """The components of a PARENTHESIZED declarator-id in the non-class declaration
    `head`, i.e. a `( <name> )` group that wraps the declared name and is immediately
    followed by the parameter list `(` — `unsigned long (std::vector<int>::size)()`
    hides the std member that `std::vector<int>::size` names from a plain scan. None
    when the head has no such group (an ordinary `f(params)` call, a `decltype(...)`
    or an `operator()` are not parenthesized declarators)."""
    i = 0
    while True:
        p = head.find("(", i)
        if p < 0:
            return None
        close = _match_paren(head, p)
        if _skip_ws(head, close) < len(head) and head[_skip_ws(head, close)] == "(":
            inner = head[p + 1:close - 1]
            if "{" in inner or ";" in inner:               # not a declarator-id
                i = close
                continue
            names = _qualified_names(inner)
            if names:
                return names[-1][2]
        i = close                        # never inside a parameter list / nested group


_STD_OWN_SPECS = frozenset(("hash", "less", "equal_to"))
_LEAD_ID = re.compile(r'\s*(?:(?:const|volatile|typename|struct|class|enum)\s+)*(?:::\s*)?([A-Za-z_]\w*)')
_OWN_DEF = re.compile(r'\b(?:struct|class|union)\s+(?:(?:\[\[[^\]]*\]\]|alignas\s*\([^)]*\))\s*)*'
                      r'([A-Za-z_]\w*)\s*(?:final\s*)?(?:\{|:(?!:))'
                      r'|\benum\s+(?:class\s+|struct\s+)?([A-Za-z_]\w*)\s*(?::[^;{]*)?\{')


def _own_defined(code):
    """Class/struct/union/enum names `code` DEFINES with a body (not a forward decl)."""
    return frozenset(a or b for a, b in _OWN_DEF.findall(code)) - _STD_ROOTS


def _own_type_arg(spec, own):
    """Whether the first template argument of the template-id `spec` (`std::less<Key>`)
    is led by a type the solver defines (`Key`)."""
    i = spec.find("<")
    if i < 0:
        return False
    m = _LEAD_ID.match(spec, i + 1)
    return bool(m) and m.group(1) in own


def _template_decl_problem(head, explicit=False, std_leading=lambda comps: False, own=frozenset()):
    """Why the declaration `head` (the text after a `template<...>` parameter list, up
    to its body / `;` / initializer) specializes or redefines a std entity, else ''.
    Allowed: a (full or partial) specialization of the std::hash class template, and
    the out-of-line definition of a member of a partial one (`template<class T>
    size_t std::hash<Box<T>>::operator()(...) const`). `explicit`: the parameter list
    is empty (`template<>`). `std_leading(comps)`: whether the name `comps` begins with
    a namespace/class that resolves to std — directly `std::`, through a solver alias
    (`using V = std::vector<int>`) or a std using-declaration / `using namespace std`
    (so `V::size`, `(std::vector<int>::size)` and, after `using namespace std`,
    `vector<int>::size` are all caught), while a member of the solver's own type is
    not. A std entity other than a std::hash specialization is rejected."""
    cls = re.match(r'\s*(?:friend\s+)?(?:struct|class|union)\b', head)
    if cls:
        comps = _declarator_comps(head)
        start = _class_name_start(head, cls.end())
        span = next(((a, b) for a, b, _ in _qualified_names(head) if a == start), None)
        if span is None or not head[span[0]:span[1]].rstrip().endswith(">"):
            return ""                     # a primary template: never a specialization
        if comps and std_leading(comps):
            if comps[-1] == "hash":
                return ""                 # a bad hash only collides; it cannot forge equality
            if comps[-1] in _STD_OWN_SPECS and _own_type_arg(head[span[0]:span[1]], own):
                return ""                 # std::less/equal_to for a type the solver defines
            if comps[-1] in _STD_OWN_SPECS:
                return f"specializes std::{comps[-1]} for a type the solver does not define"
            return "specializes a std template"
        return ""
    paren = _parenthesized_declarator(head)
    if paren is not None:
        # A parenthesized declarator-id in a template declaration is rejected: it is
        # never needed by an honest member definition and it hides the declared name
        # (`template<> unsigned long (std::vector<int>::size)() const`) from the scan.
        if std_leading(paren) and not _hash_member(paren, explicit):
            return "specializes a std function or member (parenthesized declarator)"
        return "parenthesized declarator in a template declaration"
    region = _declarator_region(head)
    names = _qualified_names(region)
    for _, _, comps in names:
        if comps[-1] == "operator":
            # The declarator is this operator name; what follows it is the operator
            # symbol or a conversion type (`Wrapper<T>::operator std::string()`,
            # `operator std::vector<U>()`), never a declarator of its own.
            return ("specializes a std operator"
                    if std_leading(comps) and not _hash_member(comps, explicit) else "")
    if (names and std_leading(names[-1][2]) and len(names[-1][2]) > 1
            and not _hash_member(names[-1][2], explicit)):
        # The declarator itself is std-qualified (directly or through an alias /
        # using-directive): std::swap(...), std::vector<int>::size(),
        # V::size() after `using V = std::vector<int>`, vector<int>::size() after
        # `using namespace std`, or a variable template / static member.
        return "specializes a std function, member or variable"
    return ""


def _decl_end(text, i):
    """Index of the first `{`, `;` or `}` at parenthesis depth 0 from text[i] (the end
    of a declaration's head), or len(text)."""
    depth = 0
    for k in range(i, len(text)):
        ch = text[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth <= 0 and ch in "{;}":
            return k
    return len(text)


def _hash_member_end(body, i, explicit):
    """End (index past it) of the item at body[i] inside `namespace std { ... }` when
    it is an out-of-line definition or declaration of a member function of a std::hash
    specialization (`inline size_t hash<Key>::operator()(const Key& k) const noexcept
    { ... }`), else -1."""
    k = _decl_end(body, i)
    if k >= len(body) or body[k] == "}":
        return -1
    head = body[i:k]
    if _declarator_region(head) == head:
        return -1                                   # no parameter list: not a function
    comps = _declarator_comps(head)
    if not comps or not _hash_member(comps, explicit):
        return -1
    if body[k] == ";":
        return k + 1
    end = _match_brace(body, k)
    return -1 if end >= len(body) else end + 1


def cpp_std_tamper(code):
    """Reject solver code that redefines what a standard type does (C++ strict
    comparisons trust std containers / strings / optional, so a solver must not be
    able to change them): opening `namespace std` for anything but a std::hash
    specialization, aliasing std, or specializing (fully or partially) a std
    template other than std::hash, or a std function / member / variable template /
    operator, e.g. `template<> std::size_t std::vector<int>::size() const`,
    `template<class T> struct std::less<Box<T>>`, `template<> constexpr bool
    std::is_arithmetic_v<Fake> = true` or `template<> bool std::operator==(...)`.
    The `namespace std { ... }` and the qualified `std::hash` forms are treated alike.
    `code` is cpp_code_only() text (comments removed, literals emptied). Measured: no C++ reference or
    skeleton on the factory does any of these (0/53)."""
    own_types = _own_defined(code)
    for m in re.finditer(r'\bnamespace\s+' + _STD_NS + r'\b(\s*::)?', code):
        if re.search(r'\busing\s*$', code[:m.start()]):
            continue                                  # `using namespace std;` is fine
        if m.group(1):
            return "`namespace std::...` (nested std namespace)"
        k = _skip_ws(code, m.end())
        if k >= len(code) or code[k] != "{":
            return f"`{' '.join(code[m.start():k + 1].split())[:60]}`"
        end = _match_brace(code, k)
        body, pos = code[k + 1:end], 0
        while True:
            while pos < len(body) and (body[pos].isspace() or body[pos] == ";"):
                pos += 1                              # (an empty declaration is nothing)
            if pos >= len(body):
                break
            h = _HASH_HEAD.match(body, pos)
            params_end = _match_angle(body, h.end() - 1) if h else -1
            c = _HASH_CLASS.match(body, params_end) if params_end >= 0 else None
            args_end = _match_angle(body, c.end() - 1) if c else -1
            if args_end < 0 and not (h and params_end < 0):
                # The out-of-line definition of a member of a std::hash specialization
                # declared in this block (`inline size_t hash<Key>::operator()(const
                # Key&) const noexcept { ... }`; with `template<class T>` for a partial
                # one) is part of that specialization. Not under `template<>`: that
                # would specialize a member of some other hash<...> (hash<T*>).
                explicit = bool(h) and not body[h.end():params_end - 1].strip()
                member_end = _hash_member_end(body, params_end if h else pos, explicit)
                if member_end >= 0:
                    pos = member_end
                    continue
            if args_end < 0:
                return "`namespace std { ... }` other than a std::hash specialization"
            kind = c.group(0).rsplit(None, 1)[-1].rstrip("<").strip()
            if kind in ("less", "equal_to") and not _own_type_arg(body[c.start():args_end], own_types):
                return f"`namespace std {{ ... }}` std::{kind} for a type the solver does not define"
            j = _skip_ws(body, args_end)
            final = _HASH_FINAL.match(body, j)
            if final:
                j = _skip_ws(body, final.end())
            if body.startswith(":", j) and not body.startswith("::", j):
                # a base clause runs to the class body (it holds no `{`, `}` or `;`)
                k = body.find("{", j)
                if k < 0 or re.search(r'[;}]', body[j:k]):
                    return "`namespace std { ... }` other than a std::hash specialization"
                j = k
            if body.startswith("{", j):
                j = _skip_ws(body, _match_brace(body, j) + 1)
            if not body.startswith(";", j):
                return "`namespace std { ... }` other than a std::hash specialization"
            pos = j + 1
    m = re.search(r'\bnamespace\s+\w+\s*=\s*(?:::\s*)?' + _STD_NS + r'\s*;', code)
    if m:
        return f"`{' '.join(m.group(0).split())}` (alias of namespace std)"
    std_scopes = _std_alias_scopes(code)
    using_std = bool(re.search(r'\busing\s+namespace\s+(?:::\s*)?' + _STD_NS + r'\b(?!\s*::)', code))
    own = _own_scopes(code) if (std_scopes or using_std) else frozenset()

    def _std_leading(comps):
        """Whether `comps` begins with a scope that resolves to std: directly std-rooted,
        a solver alias/using-declaration of a std name, or — after `using namespace std`
        — any qualified name whose leading scope the solver did not declare itself."""
        if _std_rooted(comps):
            return True
        if comps[0] in std_scopes and comps[0] not in own:
            return True                  # (a solver class/namespace of that name is its own)
        return using_std and len(comps) > 1 and comps[0] not in own

    for m in re.finditer(r'\btemplate\s*<', code):
        params_end = _match_angle(code, m.end() - 1)
        if params_end < 0:
            continue
        stop = min([x for x in (code.find("{", params_end), code.find(";", params_end),
                                code.find("=", params_end)) if x >= 0] or [len(code)])
        head = code[params_end:stop]
        why = _template_decl_problem(head, not code[m.end():params_end - 1].strip(), _std_leading, own_types)
        if why:
            shown = ' '.join((code[m.start():params_end] + head).split())[:80]
            return f"`{shown}` ({why})"
    return ""


# Names the solver binds to a std entity, so a `template<>`/partial specialization of a
# member through one of them is still a std specialization: a type alias
# (`using V = std::vector<int>;`, `typedef std::vector<int> V;`) or a std using-
# declaration (`using std::vector;`). `using namespace std;` is handled separately (it
# makes every std name reachable unqualified, so any non-own qualified id counts).
_STD_ALIAS_USING = re.compile(
    r'\busing\s+([A-Za-z_]\w*)\s*=\s*(?:typename\s+)?(?:::\s*)?' + _STD_NS + r'\s*(?:::|<)')
_STD_ALIAS_TYPEDEF = re.compile(
    r'\btypedef\b[^;{}]*?\b' + _STD_NS + r'\s*::[^;{}]*?\b([A-Za-z_]\w*)\s*;')
_STD_USING_DECL = re.compile(r'\busing\s+(?:::\s*)?' + _STD_NS + r'\s*::\s*([A-Za-z_]\w*)\s*;')


def _std_alias_scopes(code):
    return frozenset(_STD_ALIAS_USING.findall(code)
                     + _STD_ALIAS_TYPEDEF.findall(code)
                     + _STD_USING_DECL.findall(code))


# The C++ harness's templates (langs._TH_HPP): its check functions, and every name of
# its strict comparison machinery (`cmp`, in the reserved namespace __mig_th).
_HARNESS_CHECKS = frozenset(("check_true", "check_eq", "check_near", "check_throws", "check_throws_as"))
_HARNESS_NAMESPACES = frozenset(("th", "__mig_th"))
_HARNESS_CMP_NAMES = (frozenset(re.findall(r'[A-Za-z_]\w*', re.sub(
    r'"(?:[^"\\\n]|\\.)*"|//[^\n]*', ' ', getattr(langs, "_TH_STRICT", ""))))
                      - frozenset(_CPP_KEYWORDS) - _STD_ROOTS)


_OWN_NAMESPACE = re.compile(r'\bnamespace\s+((?:[A-Za-z_]\w*\s*::\s*)*[A-Za-z_]\w*)\s*\{')
_OWN_CLASS = re.compile(r'\b(?:struct|class|union)\s+(?:\[\[[^\]]*\]\]\s*)*([A-Za-z_]\w*)\s*'
                        r'(?:final\s*)?(?:[{;<]|:(?!:))')


def _own_scopes(code):
    """Names of the namespaces and classes `code` itself declares (`namespace a::b {`,
    `struct Box {`); an alias (`namespace hh = th;`) is none of them."""
    names = {c.strip() for m in _OWN_NAMESPACE.finditer(code) for c in m.group(1).split("::")}
    return frozenset(names | set(_OWN_CLASS.findall(code))) - _HARNESS_NAMESPACES


def _harness_decl_problem(head, explicit, own=frozenset()):
    """Why the template declaration `head` specializes or defines a test-harness
    template, else ''. Decided on the declared name, whatever qualifier spells the
    harness namespace (an alias, a using-directive in a test, `::`); a name qualified
    only by namespaces / classes the solver's code declares itself (`own`: its own
    `mylib::cmp::eq`) is its own."""
    comps = _declarator_comps(head)
    if not comps:
        return ""
    qualifier = comps[:-1]
    if any(c in _HARNESS_NAMESPACES for c in qualifier):
        return "specializes a test-harness template"
    if qualifier and all(c in own for c in qualifier):
        return ""
    if comps[-1] in _HARNESS_CHECKS and (explicit or qualifier or re.search(
            r'\b' + comps[-1] + r'\s*<', _declarator_region(head))):
        return "specializes a test-harness check function"
    if any(a == "cmp" and b in _HARNESS_CMP_NAMES for a, b in zip(comps, comps[1:])):
        return "specializes a test-harness comparison template"
    return ""


def cpp_harness_tamper(code):
    """Reject solver code that explicitly specializes (or partially specializes, or
    defines a member of) a template of the test harness: th::/__mig_th:: check_eq,
    check_near, check_true, check_throws, check_throws_as under any qualifier, and
    anything under `cmp::` (i128, text, seq, eq, Lhs, ...). Such a specialization
    changes what a comparison does without any operator (`template<> inline void
    hh::check_eq<int,int>(...) {}` after `namespace hh = th;` passed every int
    comparison; `template<> struct hh::cmp::i128<Box> : std::true_type {}` made a
    crate type a trusted number compared with its own operator==). The source rules
    already reject every spelling of the namespace (CPP_HARNESS_REFS) and the
    machinery the CHECK macros use lives in the reserved __mig_th; this rule holds
    whatever qualifier spells it. `code` is cpp_code_only() text."""
    own = _own_scopes(code)
    for m in re.finditer(r'\btemplate\s*<', code):
        params_end = _match_angle(code, m.end() - 1)
        if params_end < 0:
            continue
        stop = min([x for x in (code.find("{", params_end), code.find(";", params_end),
                                code.find("=", params_end)) if x >= 0] or [len(code)])
        head = code[params_end