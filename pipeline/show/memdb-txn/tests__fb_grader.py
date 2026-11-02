#!/usr/bin/env python3
"""FeatureBench Go grader: runs in the SEPARATE verifier container.

    fb_grader.py <app_dir> <spec_dir> <manifest.json> [model.patch]

reward = 1.0 only if EVERY required test (all F2P + all P2P) passes, else 0.0.

Design carried over from the migration core grader (core/grader_tests.py), adapted to a
real multi-package repo instead of one flat package:
  * reward 0.0 is written before anything else; a SIGTERM/SIGINT flushes the result so
    far (the final reward is still binary: a partial run is never 1.0);
  * a FIXED whitelist of test ids from the manifest; a test is graded by the EXIT CODE of
    its own run (`<pkg>.test -test.run '^Name$'`); an id the compiled binary does not
    list fails (phantom guard, fail-closed);
  * runtime test-read isolation: each test binary is root-owned and execute-only (0711)
    and EVERY execution of it (`-test.list` too) runs as uid 65534 from a fresh run dir holding only the package's data files,
    with the build tree and the spec unreadable, so the solution linked into the binary
    cannot read the test sources or the compiled-in expected values.
FeatureBench additions:
  * the patch is applied to a fresh copy of the pristine tree, then the WHOLE test
    surface (every *_test.go and testdata/ file) is restored from the spec, so the agent
    cannot edit, add or delete tests;
  * a patch-scope check (reward 0) closes what a separate container does not: the
    solution is compiled into the test binary, so an init(), os.Exit or forged test
    output could fake results. Test files, testdata, go.mod/go.sum/go.work, vendor and
    assembly/C files are reset to the pristine tree (not punished), so only non-test
    Go code the patch changes has any effect.
    The regex pass over the diff is only a cheap pre-filter (evadable: `os . Exit(0)`
    in a package-level var initializer earned 1.0, Argus Lite 2026-10-17). The
    authoritative check (GUARD_GO) parses every changed Go file with go/parser and
    rejects, on any line the patch added, a process-exit / process-control call under
    any import alias or dot import, a banned import path, an init() function, or a
    go:linkname / go:embed directive, or a way to learn who called it (stack and
    caller introspection, os.Args): the hidden tests assert through package code the
    agent may edit (cty's Value.RawEquals), and a comparator that returns true only
    when runtime.Caller names a _test.go file turned a broken implementation into 1.0
    (Reward Hack 2026-10-17, cty v2). Which files and lines changed is worked out by
    comparing the patched tree with the pristine tree, never from the patch text: the
    agent controls how git formats its diff, and a `*.go binary` attribute or a quoted
    `diff --git` header hid a forged file from a diff parser (Reward Hack 2026-10-17,
    sqlbuilder v2: 1.0 with Interpolate unimplemented). A binary or non-standard-header
    diff of a Go file, or a new symbolic link, is a violation;
  * a test passes only on positive proof: exit 0 AND its own `--- PASS: <Name> (` line
    from `-test.v`, so a process that ends before the test runs is a failure.
"""
import difflib
import json
import os
import posixpath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

APP = Path(sys.argv[1]).resolve()
SPEC = Path(sys.argv[2]).resolve()
MAN = json.loads(Path(sys.argv[3]).read_text())
PATCH = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("/logs/artifacts/model.patch")
VDIR = Path(os.environ.get("FB_VERIFIER_DIR", "/logs/verifier"))
VDIR.mkdir(parents=True, exist_ok=True)
REQUIRED = list(dict.fromkeys(MAN["required_tests"]))
F2P = set(MAN.get("f2p") or [])
SANDBOX_UID = int(os.environ.get("FB_SANDBOX_UID", "65534"))
TEST_TIMEOUT = int(os.environ.get("FB_TEST_TIMEOUT", "300"))
JOBS = int(os.environ.get("FB_JOBS", "4"))
STATE = {"passed": set(), "done": False, "final": None, "lock": threading.Lock(), "markers": set()}
MARKER = re.compile(r"^FBATTACK [a-z_]+: (?:denied|readable[^\n]*)$", re.M)   # self-test probes surface here


def scan_markers(text):
    for m in MARKER.findall(text or "")[:50]:
        STATE["markers"].add(m.strip())

# FB_PATH / FB_GOTOOLCHAIN exist for running the grader on a dev host; the verifier image
# uses the defaults (its own pinned Go, no toolchain switching).
GO_ENV = {"PATH": os.environ.get("FB_PATH", "/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"),
          "GOFLAGS": "-mod=mod", "GOPROXY": "off",
          "GOTOOLCHAIN": os.environ.get("FB_GOTOOLCHAIN", "local"), "CGO_ENABLED": "0",
          "GOTELEMETRY": "off", "HOME": "/tmp/fbhome"}

# ---- patch scope -----------------------------------------------------------------
# Paths outside the solution's scope. They are NOT punished (an honest agent may add a
# test of its own or run `go mod tidy`; the participle fairness review 2026-10-17 flagged
# a zero for that as an undisclosed rule): prepare() resets every one of them to the
# pristine tree (tests from the spec), so whatever the patch did there has no effect.
# Only a path escaping the tree is a violation.
# A directory whose name starts with "_" is ignored by the go tool (no package code lives there) and holds test data
# like testdata/ (tablewriter pkg/twwarp/_data golden files, Argus Main 2026-10-19).
GRADER_OWNED = re.compile(r"(^|/)(testdata|vendor)/|(^|/)_[^/]+/|_test\.go$|(^|/)go\.(mod|sum|work)$"
                          r"|\.(s|S|c|cc|cpp|h|hpp|syso|so|a)$")
BANNED_PATH = re.compile(r"(^|/)\.\.(/|$)|^/")
BANNED_ADDED = [
    (re.compile(r"^\s*func\s+init\s*\("), "adds an init() function"),
    (re.compile(r"\b(os|syscall)\.Exit\s*\(|\bruntime\.Goexit\s*\("), "exits the process"),
    (re.compile(r'^\s*(import\s+)?([\w.]+\s+)?"(testing|flag)"\s*\)?\s*$'), "imports testing/flag in non-test code"),
    (re.compile(r"//go:embed|^\s*import\s+\"C\""), "embeds files or uses cgo"),
    (re.compile(r"--- (PASS|FAIL|SKIP)|=== (RUN|PAUSE|CONT)|\\x16|\x16"), "writes test-framework output"),
    (re.compile(r"//go:linkname"), "uses go:linkname"),
    (re.compile(r"(^|\s)//line\s|/\*line\s"), "adds a //line directive"),   # relabels positions (gift 2026-10-19)
    (re.compile(r"/proc/self|os\.Executable\s*\("), "inspects its own process image"),
]


def solution_go(path):
    return path.endswith(".go") and not GRADER_OWNED.search(path)


def go_lines(text):
    """Lines as Go's tokenizer counts them: split on "\n" only. str.splitlines() also splits on
    U+0085, U+2028/2029, \v, \f and \x1c-\x1e, so its line numbers drift from Go's and a header
    line can be cut short (participle v4 Reward Hack / v6 Argus Main, Hardik 2026-10-18)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def patch_scope(text):
    """List of violations (empty = allowed). An honest `git diff` of Go source always has a
    plain `diff --git a/<p> b/<p>` header and text hunks; anything else hides the code."""
    bad, cur = [], None
    for line in go_lines(text):
        if line.startswith("diff --git "):
            m = re.match(r"^diff --git a/(\S+) b/(\S+)$", line)
            cur = m.group(2) if m else None
            if not m:
                if ".go" in line and "_test.go" not in line:
                    bad.append(f"non-standard diff header for a Go file: {line[:160]}")
                continue
            for p in {m.group(1), m.group(2)}:
                if BANNED_PATH.search(p):
                    bad.append(f"{p}: path outside the repository")
            continue
        if line.startswith("GIT binary patch") and cur and solution_go(cur):
            bad.append(f"{cur}: binary diff of a Go file")
            continue
        if (line.startswith("+++") or not line.startswith("+") or not cur or not cur.endswith(".go")
                or GRADER_OWNED.search(cur)):
            continue
        for rx, why in BANNED_ADDED:
            if rx.search(line[1:]):
                bad.append(f"{cur}: {why}: {line[1:].strip()[:120]}")
    return bad


# ---- syntax-aware guard (authoritative) ------------------------------------------
# Built from source at grading time with the verifier's own Go (stdlib only). Input on
# stdin: [{"path": <file in the patched tree>, "added": [new-file line numbers]}], where
# the added lines come from comparing the patched tree with the pristine one.
# Output: one violation per line. A parse error on a changed file is a violation
# (fail closed). Only constructs on ADDED lines count, so an upstream file that already
# calls os.Exit (a CLI main) can still be edited.
GUARD_GO = r"""package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strconv"
	"strings"
)

type in struct {
	Path  string `json:"path"`
	Added []int  `json:"added"`
}

// Banned: what could end the process with status 0 or read the test binary (with these
// gone, exit 0 plus the test's own PASS line is the test's real result), and what tells
// code who called it or that it runs under a test (stack/caller introspection, os.Args):
// the tests assert through package code, so a helper that answers differently when a
// _test.go file calls it would fake every assertion that goes through it.
var bannedImport = map[string]bool{
	"syscall": true, "golang.org/x/sys/unix": true, "golang.org/x/sys/windows": true,
	"os/exec": true, "os/signal": true, "plugin": true, "testing": true, "flag": true,
	"embed": true, "C": true, "runtime/cgo": true, "runtime/pprof": true, "runtime/trace": true,
}

var bannedSel = map[string]map[string]bool{
	"os": {"Exit": true, "FindProcess": true, "StartProcess": true, "Executable": true, "Args": true},
	"runtime": {"Goexit": true, "Caller": true, "Callers": true, "CallersFrames": true,
		"FuncForPC": true, "Stack": true},
	"runtime/debug": {"Stack": true, "PrintStack": true, "ReadBuildInfo": true},
	"log":           {"Lshortfile": true, "Llongfile": true},
}

func main() {
	var files []in
	if err := json.NewDecoder(os.Stdin).Decode(&files); err != nil {
		fmt.Println("guard: bad input:", err)
		return
	}
	for _, f := range files {
		added := map[int]bool{}
		for _, l := range f.Added {
			added[l] = true
		}
		fs := token.NewFileSet()
		file, err := parser.ParseFile(fs, f.Path, nil, parser.ParseComments)
		if err != nil {
			fmt.Printf("%s: does not parse: %v\n", f.Path, err)
			continue
		}
		// positions as written, never as a //line directive relabels them (gift-transform Argus Lite 2026-10-19:
		// a directive moved an added init() onto "unchanged" lines and the guard skipped it)
		at := func(p token.Pos) int { return fs.PositionFor(p, false).Line }
		touched := func(n ast.Node) bool {
			a, b := at(n.Pos()), at(n.End())
			for l := a; l <= b; l++ {
				if added[l] {
					return true
				}
			}
			return false
		}
		report := func(n ast.Node, why string) {
			fmt.Printf("%s:%d: %s\n", f.Path, at(n.Pos()), why)
		}
		alias := map[string]string{} // local name -> import path
		for _, im := range file.Imports {
			path, _ := strconv.Unquote(im.Path.Value)
			name := path
			if i := strings.LastIndex(path, "/"); i >= 0 {
				name = path[i+1:]
			}
			if im.Name != nil {
				name = im.Name.Name
			}
			if touched(im) {
				if bannedImport[path] {
					report(im, "imports "+path)
				}
				if name == "." && bannedSel[path] != nil {
					report(im, "dot-imports "+path)
				}
			}
			alias[name] = path
		}
		for _, cg := range file.Comments {
			for _, c := range cg.List {
				if touched(c) && (strings.Contains(c.Text, "go:linkname") || strings.Contains(c.Text, "go:embed")) {
					report(c, "compiler directive "+strings.TrimSpace(c.Text))
				}
				if touched(c) && (strings.HasPrefix(c.Text, "//line ") || strings.HasPrefix(c.Text, "/*line ")) {
					report(c, "line directive "+strings.TrimSpace(c.Text))
				}
			}
		}
		ast.Inspect(file, func(n ast.Node) bool {
			switch x := n.(type) {
			case *ast.FuncDecl:
				if x.Recv == nil && x.Name.Name == "init" && touched(x.Name) {
					report(x, "adds an init() function")
				}
			case *ast.SelectorExpr:
				if id, ok := x.X.(*ast.Ident); ok && touched(x) {
					if p, ok := alias[id.Name]; ok && bannedSel[p][x.Sel.Name] {
						report(x, "uses "+p+"."+x.Sel.Name)
					}
				}
				if x.Sel.Name == "AddSource" && touched(x) {
					report(x, "records the caller's source position (AddSource)")
				}
			case *ast.KeyValueExpr:
				if id, ok := x.Key.(*ast.Ident); ok && id.Name == "AddSource" && touched(x) {
					report(x, "records the caller's source position (AddSource)")
				}
			}
			return true
		})
	}
}
"""


def changed_go(work):
    """({path: [added line numbers]}, [new symlinks]) from the patched tree itself.

    Every non-test Go file that differs from the pristine tree is listed: a new file with
    all its lines, a changed one with the lines difflib finds inserted or replaced. A
    symlink the pristine tree does not have is reported (it could point a Go path at
    content no check reads)."""
    files, links = {}, []
    for dirpath, dirnames, filenames in os.walk(work):     # does not follow dir symlinks
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                rel = p.relative_to(work).as_posix()
                o = APP / rel
                if not (o.is_symlink() and os.readlink(o) == os.readlink(p)):
                    links.append(rel)
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(work).as_posix()
            if p.is_symlink() or not solution_go(rel):
                continue
            new = go_lines(p.read_text(errors="replace"))
            o = APP / rel
            if o.is_file() and not o.is_symlink():
                old = go_lines(o.read_text(errors="replace"))
                if old == new:
                    continue
                ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
                added = [j + 1 for tag, _, _, j1, j2 in ops if tag in ("replace", "insert")
                         for j in range(j1, j2)]
            else:
                added = list(range(1, len(new) + 1))
            if added:
                files[rel] = added
    return files, sorted(links)


def syntax_guard(work, env, root):
    """Violations from GUARD_GO over the changed Go files; fail closed on a tool error."""
    changed, links = changed_go(work)
    if links:
        return [f"{l}: adds a symbolic link" for l in links]
    files = [{"path": str(work / p), "added": ls} for p, ls in changed.items()]
    if not files:
        return []
    src = root / "guard"
    src.mkdir()
    (src / "go.mod").write_text("module fbguard\n\ngo 1.21\n")
    (src / "main.go").write_text(GUARD_GO)
    exe = root / "fbguard"
    # a timeout fails closed with a reason instead of crashing the grader (phonenumbers v2 Argus, 2026-10-19)
    try:
        b = subprocess.run(["go", "build", "-o", str(exe), "."], cwd=src, capture_output=True, text=True, errors="replace",
                           env={**env, "GOFLAGS": "-mod=mod"}, timeout=600)
    except subprocess.TimeoutExpired:
        return ["guard build timed out"]
    if b.returncode:
        return [f"guard build failed: {(b.stdout + b.stderr)[-300:]}"]
    try:
        r = subprocess.run([str(exe)], input=json.dumps(files), capture_output=True, text=True, errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return ["guard timed out"]
    if r.returncode:
        return [f"guard failed: {(r.stdout + r.stderr)[-300:]}"]
    return [l.replace(str(work) + "/", "") for l in go_lines(r.stdout) if l.strip()]


# ---- reward ----------------------------------------------------------------------
def lock_verifier_dir():
    """The reward files are written by root; the sandbox user must not be able to write them."""
    if os.geteuid() == 0:
        try:
            os.chown(VDIR, 0, 0)
            os.chmod(VDIR, 0o755)
        except OSError:
            pass


def emit(reward, extra):
    (VDIR / "reward.txt").write_text(f"{reward}\n")
    (VDIR / "reward.json").write_text(json.dumps({"reward": reward}))
    (VDIR / "reward_debug.json").write_text(json.dumps(extra, indent=1, sort_keys=True))


def result(reason=None):
    passed = STATE["passed"]
    ok_all = all(t in passed for t in REQUIRED) and bool(REQUIRED) and not reason
    extra = {"passed": len(passed & set(REQUIRED)), "required": len(REQUIRED),
             "f2p_passed": len(passed & F2P), "f2p": len(F2P),
             "p2p_passed": len(passed & (set(REQUIRED) - F2P)), "p2p": len(set(REQUIRED) - F2P),
             "failed": sorted(set(REQUIRED) - passed)[:200], "reason": reason}
    return (1.0 if ok_all else 0.0), extra


def on_signal(signum, frame):
    if STATE["final"] is not None:     # the final result is staged: a late signal re-writes it, never a 0
        emit(*STATE["final"])
    elif not STATE["done"]:
        with STATE["lock"]:
            reward, extra = result(f"signal {signum} before grading finished")
        emit(0.0, extra)
    os._exit(0)


# ---- tree --------------------------------------------------------------------------
def is_test_surface(rel):
    return rel.endswith("_test.go") or "testdata" in rel.split("/")[:-1]


def support_dirs():
    """Directories with graded tests whose files the reference solution does not touch (manifest "solution_dirs",
    written at bundle time; None for a bundle built before it): test-support packages. Their non-test code is part
    of the test surface (tablewriter tests/fn.go holds visualCheck, the comparator every snapshot test asserts
    through: a neutered copy plus a stub renderer scored 1.0 on 184/184, Argus Main 2026-10-19), so prepare()
    restores every file there from the pristine tree; an honest solution has nothing to write in them."""
    # plus "support_dirs": module packages the tests import that the solution does not reach (gotoml internal/assert:
    # a neutered Equal and a broken float encoder scored 1.0, prereview 2026-10-19), computed at bundle time
    # (authoritative when present: it leaves out packages the solution's own code imports, which a solution may edit)
    if isinstance(MAN.get("support_dirs"), list):
        return {d for d in MAN["support_dirs"] if isinstance(d, str)}
    sol = MAN.get("solution_dirs")
    if sol is None:
        return set()
    tested = {posixpath.dirname(f.relative_to(SPEC).as_posix()) for f in SPEC.rglob("*_test.go") if f.is_file()}
    return tested - set(sol)


# Grader-owned, added to every graded package: the test to run arrives on stdin (fd 0, read directly), never on the
# command line. A solution read /proc/self/cmdline through a split literal ("/proc"+"/self/"+"cmdline"), learned the
# running hidden test's name from -test.run and answered per test: 1.0 on 436/436 with the behaviour broken
# (mangle-temporal Argus Main 2026-10-19). Package code that reads fd 0 first consumes the name: nothing runs, the
# test fails.
RUNSEL_FILE = "zz_fbgrader_runsel_test.go"
RUNSEL = """package {pkg}

import (
\tfbflag "flag"
\tfbio "io"
\tfbos "os"
\tfbstrings "strings"
\tfbtesting "testing"
)

func init() {{
\tfbtesting.Init()
\tb, _ := fbio.ReadAll(fbio.LimitReader(fbos.NewFile(0, "fbrunsel"), 1<<16))
\trun := fbstrings.TrimSpace(string(b))
\tif run == "" {{
\t\trun = "^$"
\t}}
\t_ = fbflag.Set("test.run", run)
}}
"""


def package_name(work: Path, d: str):
    """The package name of directory d (its non-test files', else its tests' without _test); None if none."""
    names = {}
    folder = work if d == "." else work / d
    for f in sorted(folder.glob("*.go")):
        m = re.search(r"(?m)^package\s+(\w+)", f.read_text(errors="replace"))
        if not m:
            continue
        n = m.group(1)
        if f.name.endswith("_test.go"):
            n = n[:-5] if n.endswith("_test") else n
            names.setdefault(("t", n), 0)
            names[("t", n)] += 1
        else:
            names[("s", n)] = names.get(("s", n), 0) + 1
    src = sorted(((c, n) for (k, n), c in names.items() if k == "s"), reverse=True)
    tst = sorted(((c, n) for (k, n), c in names.items() if k == "t"), reverse=True)
    return (src or tst or [(0, None)])[0][1]


def prepare(work: Path):
    shutil.copytree(APP, work, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    if PATCH.is_file() and PATCH.stat().st_size:
        r = subprocess.run(["git", "apply", "--whitespace=nowarn", str(PATCH)], cwd=work,
                           capture_output=True, text=True, errors="replace")
        # git apply only: an honest collected `git diff` always applies, and a `patch -p1`
        # fallback reads headers and hunks differently (Hardik 2026-10-18); a rejected patch
        # is a clean "does not apply" (reward 0), never a crash
        if r.returncode:
            return f"model.patch does not apply: {(r.stdout + r.stderr)[-300:]}"
    for f in list(work.rglob("*")):                    # reset every grader-owned path
        rel = f.relative_to(work).as_posix()
        if (f.is_file() or f.is_symlink()) and (is_test_surface(rel) or GRADER_OWNED.search(rel)):
            f.unlink()
    for f in APP.rglob("*"):                           # module files etc. from the pristine tree
        rel = f.relative_to(APP).as_posix()
        if (f.is_file() and not rel.startswith(".git/") and GRADER_OWNED.search(rel)
                and not is_test_surface(rel)):
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, work / rel)
    support = support_dirs()
    if support:                                        # test-support packages: every file as in the pristine tree
        for f in list(work.rglob("*")):
            rel = f.relative_to(work).as_posix()
            if (f.is_file() or f.is_symlink()) and posixpath.dirname(rel) in support and not is_test_surface(rel):
                f.unlink()
        for f in APP.rglob("*"):
            rel = f.relative_to(APP).as_posix()
            if (f.is_file() or f.is_symlink()) and posixpath.dirname(rel) in support and not is_test_surface(rel) \
                    and not rel.startswith(".git/"):
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, work / rel, follow_symlinks=False)
    for f in SPEC.rglob("*"):                          # the whole test surface from the spec
        rel = f.relative_to(SPEC).as_posix()
        if f.is_file() and is_test_surface(rel):
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, work / rel)
    return None


def can_drop():
    if os.geteuid() != 0 or not shutil.which("setpriv"):
        return False
    r = subprocess.run(wrap("id -u"), shell=True, capture_output=True, text=True, errors="replace")
    return r.returncode == 0 and r.stdout.strip() == str(SANDBOX_UID)


DROP = {"on": False}


def wrap(cmd):
    if not DROP["on"] and not (os.geteuid() == 0 and cmd == "id -u"):
        return cmd
    return ("setpriv --reuid %d --regid %d --clear-groups --inh-caps=-all -- /bin/sh -c %s"
            % (SANDBOX_UID, SANDBOX_UID, shlex.quote(cmd)))


def main():
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    lock_verifier_dir()
    emit(0.0, {"reason": "grading started"})
    patch_text = PATCH.read_text(errors="replace") if PATCH.is_file() else ""
    violations = patch_scope(patch_text)
    if violations:
        STATE["done"] = True
        _, extra = result("patch-scope violation")
        extra["violations"] = violations[:50]
        emit(0.0, extra)
        print(json.dumps({"reward": 0.0, **extra}))
        return
    root = Path(tempfile.mkdtemp(prefix="fbgrade-"))
    work, bins, runs = root / "work", root / "bin", root / "run"
    err = prepare(work)
    if err:
        STATE["done"] = True
        _, extra = result(err)
        emit(0.0, extra)
        print(json.dumps({"reward": 0.0, **extra}))
        return
    bins.mkdir()
    runs.mkdir()
    env = {**GO_ENV, "GOCACHE": str(root / "gocache"), "GOPATH": os.environ.get("GOPATH", "/go")}
    violations = syntax_guard(work, env, root)
    if violations:
        STATE["done"] = True
        _, extra = result("patch-scope violation")
        extra["violations"] = violations[:50]
        emit(0.0, extra)
        print(json.dumps({"reward": 0.0, **extra}))
        shutil.rmtree(root, ignore_errors=True)
        return
    by_dir = {}
    for tid in REQUIRED:
        d, name = tid.rsplit(":", 1)
        by_dir.setdefault(d, []).append(name)
    built, present = {}, {}
    for d in by_dir:                                       # build as root, one binary per package
        exe = bins / (re.sub(r"[^A-Za-z0-9_]", "_", d) + ".test")
        pkg_name = package_name(work, d)
        if pkg_name:
            ((work if d == "." else work / d) / RUNSEL_FILE).write_text(RUNSEL.format(pkg=pkg_name))
        pkg = "." if d == "." else "./" + d
        try:
            b = subprocess.run(["go", "test", "-c", "-vet=off", "-o", str(exe), pkg], cwd=work, env=env,
                               capture_output=True, text=True, errors="replace", timeout=1800)
        except subprocess.TimeoutExpired:
            built[d] = None                                # this package's tests fail; the others still grade
            print(f"[grader] build timed out for {d}")
            continue
        if b.returncode or not exe.is_file():
            built[d] = None
            print(f"[grader] build failed for {d}: {(b.stdout + b.stderr)[-600:]}")
            continue
        # isolation: the run dir holds only the package's data files (no Go sources)
        rd = runs / (re.sub(r"[^A-Za-z0-9_]", "_", d))
        src_dir = work if d == "." else work / d
        shutil.copytree(src_dir, rd, ignore=shutil.ignore_patterns("*.go", ".git"), dirs_exist_ok=True)
        built[d] = (exe, rd)
    # The binaries carry the solution's code, and package initialisation runs on EVERY
    # execution, `-test.list` included. Nothing compiled from the patch may ever run as
    # root (Reward Hack review 2026-10-17, cty v1: a var initializer ran as root during
    # -test.list and forged reward.json). So privileges are dropped before the first
    # execution, and with no way to drop them nothing is executed: reward 0.
    DROP["on"] = can_drop()
    if not DROP["on"] and os.environ.get("FB_ALLOW_UNISOLATED") != "1":
        STATE["done"] = True
        _, extra = result("cannot drop privileges (need root + setpriv): test binaries not run")
        extra["isolation_enforced"] = False
        emit(0.0, extra)
        print(json.dumps({"reward": 0.0, **extra}))
        shutil.rmtree(root, ignore_errors=True)
        return
    if DROP["on"]:
        os.chmod(root, 0o711)
        for p in (work, SPEC):
            os.chmod(p, 0o700)
        # the build cache holds the compiled spec tests (their expected values): root only (migration lesson,
        # GOCACHE answer leak; Hardik 2026-10-18)
        if (root / "gocache").exists():
            os.chmod(root / "gocache", 0o700)
        os.chmod(bins, 0o711)
        for exe in bins.iterdir():
            os.chmod(exe, 0o711)
        Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
        os.chown(env["HOME"], SANDBOX_UID, SANDBOX_UID)
        os.chmod(runs, 0o755)
        # Every data file restored from the spec (the pristine test surface: testdata/ and the rest) stays
        # root's and read-only, so package code the tests run cannot rewrite the golden data it is checked
        # against. Other copied data files come from the solver's own tree (the patch can change them
        # anyway) and stay writable by the sandbox user: honest tests rewrite committed scratch files
        # (goavro fixtures/temp*.avro, Hardik 2026-10-19). Directories are root's with the sticky bit
        # (1777): tests may create new files, nobody can rename or delete a root-owned file.
        for d, v in built.items():
            if not v:
                continue
            rd = v[1]
            for p in [rd, *rd.rglob("*")]:
                if p.is_symlink():                 # a chmod/chown would follow the link off the tree
                    continue
                if p.is_dir():
                    os.chmod(p, 0o1777)
                    continue
                rel = p.relative_to(rd)
                if (SPEC / rel if d == "." else SPEC / d / rel).is_file():
                    os.chmod(p, 0o444)
                else:
                    os.chown(p, SANDBOX_UID, SANDBOX_UID)
                    os.chmod(p, 0o644)
    renv = {k: v for k, v in env.items() if k not in ("GOCACHE", "GOPATH")}
    for d, v in built.items():                             # phantom guard, as the sandbox user
        if not v:
            continue
        exe, rd = v
        try:
            # errors="replace" on every decoded child output: a var initializer writing \xff crashed the strict
            # decode and left an unexplained 0.0 (gojay v4 Argus Main 2026-10-19)
            lst = subprocess.run(wrap(f"{shlex.quote(str(exe))} -test.list '.*'"), shell=True, cwd=rd,
                                 env=renv, input="", capture_output=True, text=True, errors="replace", timeout=120)
            scan_markers(lst.stdout + lst.stderr)      # package init (a self-test probe) runs here too
            present[d] = set(lst.stdout.split())
        except subprocess.TimeoutExpired:
            present[d] = set()

    def one(tid):
        d, name = tid.rsplit(":", 1)
        if not built.get(d) or name not in present.get(d, ()):
            return tid, False
        exe, rd = built[d]
        # the test's name goes to the grader-owned runsel init on stdin: the command line names no test
        cmd = f"{shlex.quote(str(exe))} -test.v -test.count=1 -test.timeout={TEST_TIMEOUT}s"
        try:
            r = subprocess.run(wrap(cmd), shell=True, cwd=rd, env=renv, capture_output=True,
                               input=("^" + re.escape(name) + "$").encode(), timeout=TEST_TIMEOUT + 30)
        except subprocess.TimeoutExpired:
            return tid, False
        out = r.stdout + r.stderr
        scan_markers(out.decode(errors="replace"))     # a self-test probe's init prints its marker here
        # positive proof: the test's own PASS line, not just a zero exit
        proof = re.search(rb"(?m)^--- PASS: " + re.escape(name.encode()) + rb" \(", r.stdout)
        ok = r.returncode == 0 and bool(proof) and b"no tests to run" not in out
        if ok:
            with STATE["lock"]:
                STATE["passed"].add(tid)
        return tid, ok

    # the tests of one package run one after another in its run dir, as `go test` runs them; packages run in
    # parallel. Two tests of a package sharing files raced when run together (gotest.tools golden
    # TestGoldenAssertInDir / _UpdateGolden, Grader determinism review 2026-10-19).
    by_pkg = {}
    for tid in REQUIRED:
        by_pkg.setdefault(tid.rsplit(":", 1)[0], []).append(tid)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        list(pool.map(lambda tids: [one(t) for t in tids], by_pkg.values()))
    reward, extra = result()        # no lock: the workers are done, and on_signal (same thread) takes it
    extra["isolation_enforced"] = DROP["on"]
    extra["build_failed"] = sorted(d for d, v in built.items() if v is None)
    extra["attack_markers"] = sorted(STATE["markers"])   # self-test probe lines (fb_certify asserts on them)
    extra["patch_empty"] = not patch_text.strip()
    extra["test_seconds"] = round(time.monotonic() - t0, 1)
    STATE["final"] = (reward, extra)                     # staged before the write: see on_signal
    emit(reward, extra)
    STATE["done"] = True
    print(json.dumps({"reward": reward, **{k: v for k, v in extra.items() if k != "failed"},
                      "failed_sample": extra["failed"][:20]}))
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
