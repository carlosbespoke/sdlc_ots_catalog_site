#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TESTS_DIR = Path(os.environ.get("TESTS_DIR", "/tests"))
VERIFIER_DIR = Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "/logs/artifacts"))
BASE_PIN_DIR = Path(os.environ.get("BASE_PIN_DIR", "/opt/dp-base"))
RANK = {"passed": 0, "skipped": 1, "failed": 2}

COLLECTION_CONFIG_NAMES = ("conftest.py", "pytest.ini", ".pytest.ini",
                           "sitecustomize.py", "usercustomize.py")

IMPORT_SHADOW_NAMES = ("pytest", "_pytest", "pluggy", "py", "iniconfig",
                       "packaging", "tomli", "exceptiongroup", "pygments")

SHARED_CONFIG_NAMES = ("pyproject.toml", "setup.cfg", "tox.ini")

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", ".tox", "__pycache__",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", "target", "vendor"}

CANARY_ID = "dp_canary.expected_failure"

REWARD_CHANNEL = ("reward.txt", "reward.json", "metrics.json", "ctrf.json", "partial_rewards.txt")

def log(msg):
    print(f"[verifier] {msg}", flush=True)


def load_config():
    return json.loads((TESTS_DIR / "config.json").read_text())



def patch_paths(text):
    seen, out = set(), []
    for line in text.splitlines():
        path = None
        m = re.match(r'^diff --git (?:"?a/(.*?)"?) (?:"?b/(.*?)"?)$', line)
        if m:
            path = m.group(2)
        elif line.startswith('+++ b/'):
            path = line[6:]
        elif line.startswith('--- a/'):
            path = line[6:]
        if path and path != '/dev/null' and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def read_patch(path):
    p = Path(path)
    return p.read_text(errors="replace") if p.exists() else ""


# The repository's own suites (P2P) run the submission's code in their own process. A runtime
# source file the submission changed can therefore hijack the test machinery and forge an all-pass
# report, hiding a regression. A data processing task's runtime code never touches the test
# framework or the grader's report files, so an added line in a NON-test source file that does is
# tampering, and grading fails closed (reward 0). The hidden suite runs the code as a black box in a
# separate process, so these patterns never appear in a fair solution.
# Each pattern is deliberately high-signal: a data processing change's runtime code never does any
# of these, while forging the report needs at least one. The guard is a tripwire, not a complete
# proof; the hidden suite re-asserting the load-bearing behaviours (a separate black-box process) is
# the real backstop for a cleverer forge.
# Two families. FRAMEWORK: touching pytest at all (a data library's runtime code normally never
# does, but a pytest plugin or a pkg/testing.py helper legitimately does). REPORT: forging the result
# itself, which no legitimate code does. A file that already uses the framework at base may keep
# using it; report forging is flagged whenever it is new.
FRAMEWORK, REPORT = "framework", "report"
TAMPER_PATTERNS = (
    (FRAMEWORK, re.compile(r"(?:^|[^\w.])(?:import|from)\s+(?:pytest|_pytest|pluggy)\b"),
     "imports the test framework"),
    (FRAMEWORK, re.compile(r"\bimport_module\(\s*['\"](?:_?pytest|pluggy)"),
     "imports the test framework dynamically"),
    (FRAMEWORK, re.compile(r"\b_pytest\.\w|\bpytest\.(?:hookimpl|fixture|mark|main|skip|exit|PytestPlugin)"),
     "uses pytest internals"),
    # Hooks that decide or rewrite a test's outcome, or drop tests, forge the result directly.
    (REPORT, re.compile(r"\bdef\s+pytest_(?:runtest_makereport|runtest_logreport|runtest_protocol"
                        r"|runtest_call|runtest_setup|runtest_teardown|report_teststatus"
                        r"|collection_modifyitems|deselected|sessionfinish|terminal_summary)\b"),
     "defines a pytest hook that decides test outcomes"),
    (FRAMEWORK, re.compile(r"(?m)^\+?\s*def\s+pytest_\w+"), "defines a pytest hook"),
    (FRAMEWORK, re.compile(r"\bsys\.modules\b.*['\"]_?pytest|['\"]_?pytest['\"]\s*(?:not\s+)?in\s+sys\.modules"),
     "inspects or replaces the pytest module"),
    (FRAMEWORK, re.compile(r"\bPYTEST_CURRENT_TEST\b"), "branches on the pytest environment"),
    (REPORT, re.compile(r"\b(?:junitxml|LogXML|junit_family)\b"), "writes JUnit reports"),
    (REPORT, re.compile(r"JUNIT_REPORT|/logs/verifier|/var/lib/dp-grading|/opt/dp-base|/dp-base\b"),
     "references the grader's report files or directories"),
)

# Only code files can forge an in-process report. Prose, data and config cannot, and scanning them
# is pure false-positive risk (a README that says "from pytest import", a CSV column "base.xml").
_CODE_SUFFIXES = (".py", ".pyx", ".pxd")


def tamper_hits(model_patch_text, ref=None):
    """(path, reason) for every added line in a code file of the submission's patch that touches the
    test framework or the grader's reports. Only added lines ('+') in Python files are read. Files
    that grading restores to base first (test files, collection config, and anything under a
    test-named directory) are skipped, since a change there has no effect when the suites run."""
    base_test_dirs = base_test_surface(ref)[0] if ref is not None else []
    hits, path, skip = [], None, True
    for line in model_patch_text.splitlines():
        m = re.match(r'^diff --git (?:"?a/(.*?)"?) (?:"?b/(.*?)"?)$', line)
        if m:
            path = m.group(2)
            name = path.rsplit("/", 1)[-1] if path else ""
            # Skip only files grading restores to base: test files, collection config
            # (conftest.py, pytest.ini, sitecustomize ...), files under a base test directory, and
            # non-code files. A NEW file under a NEW test-named directory is removed by
            # restore_test_surface before the suites run, so it is skipped here too.
            restored_test_dir = (test_dir_of(path) is not None)
            skip = (path is None or path == "/dev/null" or not path.endswith(_CODE_SUFFIXES)
                    or is_test_file(path) or name in COLLECTION_CONFIG_NAMES or restored_test_dir
                    or any(path == d or path.startswith(d + "/") for d in base_test_dirs))
            continue
        if skip or not line.startswith("+") or line.startswith("+++"):
            continue
        added = _code_part(line[1:])
        if not added.strip():
            continue
        for family, reason in _matches(added):
            hits.append((path, family, reason))
    hits = list(dict.fromkeys(hits))
    # Only what the submission newly introduces counts for the FRAMEWORK family. A repository may
    # legitimately use pytest in non-test source (a pytest plugin, a pkg/testing.py helper), so
    # editing such a file is not tampering: a FRAMEWORK hit is dropped when the base version of the
    # file already uses the framework. A REPORT hit is never dropped: no legitimate change forges a
    # test result or writes the grader's report, and the base mentioning the same thing (in prose, a
    # docstring) is no licence to start doing it.
    base = {}
    out = []
    for path, family, reason in hits:
        if family == FRAMEWORK and ref is not None:
            if path not in base:
                base[path] = _matches_in(_base_text(ref, path))[0]
            if FRAMEWORK in base[path]:
                continue
        out.append((path, reason))
    return list(dict.fromkeys(out))


def _code_part(line):
    """The line without a trailing comment: cut at the first '#' that is outside a string literal."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and line[i - 1:i] != "\\":
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def _matches(line):
    """Every (family, reason) a single line matches (all patterns, not the first)."""
    return [(family, reason) for family, pattern, reason in TAMPER_PATTERNS if pattern.search(line)]


def _matches_in(text):
    """(families, reasons) that any non-comment line of `text` matches."""
    families, reasons = set(), set()
    for line in text.splitlines():
        line = _code_part(line)
        if not line.strip():
            continue
        for family, reason in _matches(line):
            families.add(family)
            reasons.add(reason)
    return families, reasons


def _base_text(ref, path):
    """The file's text at the base commit, or "" when the submission created it or the base cannot be
    read. An empty base flags more, which is the safe direction (fail closed)."""
    try:
        r = git("show", f"{ref}:{path}", capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout if r.returncode == 0 else ""



def git(*args, **kw):
    return subprocess.run(["git", *args], cwd=APP_DIR, **kw)


def inside_repo(path):
    """True for a relative path that stays inside the repository. Paths come from model.patch,
    which the submission writes, so a '../' path must never reach a root rm -rf."""
    if not path or os.path.isabs(path) or ".." in path.split("/"):
        return False
    root = os.path.realpath(APP_DIR)
    # The parent must resolve inside the repository; the last part may itself be a link, which
    # rm -rf then removes (never its target).
    parent = os.path.realpath(os.path.dirname(os.path.join(root, path)))
    return parent == root or parent.startswith(root + os.sep)


def reset_paths(paths, ref):
    for f in paths:
        if not inside_repo(f):
            if f:
                log(f"NOTE: ignoring path outside the repository: {f!r}")
            continue
        rc = git("checkout", "-q", ref, "--", f,
                 stderr=subprocess.DEVNULL).returncode
        if rc != 0 and (APP_DIR / f).exists():
            subprocess.run(["rm", "-rf", "--", f], cwd=APP_DIR)


def tracked_config_paths(ref):
    r = git("ls-tree", "-r", "-z", "--name-only", ref, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.split("\0")
            if p and p.rsplit("/", 1)[-1] in COLLECTION_CONFIG_NAMES]


def live_config_paths():
    out = []
    root = str(APP_DIR)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if dirpath != root and ".git" in (set(dirnames) | set(filenames)):
            dirnames[:] = []
            continue
        for name in filenames:
            if name in COLLECTION_CONFIG_NAMES:
                out.append(os.path.relpath(os.path.join(dirpath, name), root))
    return out


_MODULE_FILE = r"(\.py|\.pyc|(\.[A-Za-z0-9_-]+)?\.(so|pyd))"


def shadow_stems():
    """Repository paths (no suffix) where a module would be imported in place of the test framework
    or a pinned pytest plugin: the framework's modules at the root, plus base-pytest.shadow (written
    at image build for python tasks: each pinned plugin's top-level module in each import folder)."""
    stems = list(IMPORT_SHADOW_NAMES)
    try:
        extra = (BASE_PIN_DIR / "base-pytest.shadow").read_text().splitlines()
    except OSError:
        extra = []
    return stems + [line.strip() for line in extra if line.strip()]


def import_shadow_paths():
    out = []
    for stem in shadow_stems():
        parent, _, name = stem.rpartition("/")
        folder = APP_DIR / parent if parent else APP_DIR
        module = re.compile(re.escape(name) + _MODULE_FILE + r"\Z")
        init = re.compile(r"__init__" + _MODULE_FILE + r"\Z")
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for entry in entries:
            rel = f"{parent}/{entry}" if parent else entry
            path = folder / entry
            if entry == name and os.path.islink(path):
                out.append(rel)                     # a linked package: the link itself is removed
            elif module.match(entry) and not os.path.isdir(path):
                out.append(rel)
            elif entry == name and os.path.isdir(path):
                # Its __init__ would make it a regular package that wins the import. Without one it is
                # only a namespace portion, which an installed module beats; a plugin inside an
                # installed namespace package has its own stem (foo/bar) in base-pytest.shadow.
                out += [f"{rel}/{f}" for f in os.listdir(path) if init.match(f)]
    return out


def reset_collection_config(ref):
    paths = sorted(set(tracked_config_paths(ref)) | set(live_config_paths())
                   | set(import_shadow_paths()))
    if paths:
        shown = ", ".join(paths[:10]) + (" ..." if len(paths) > 10 else "")
        log(f"Resetting {len(paths)} collection/reporting config file(s) "
            f"to base: {shown}")
        reset_paths(paths, ref)
    return paths


def restore_package_metadata():
    """Puts the package metadata folders (name.dist-info, name.egg-info) in the repository's import
    folders back to the copy pin-base took at image build, and removes any other. importlib.metadata
    finds one in any import folder, and the pinned `-p NAME` loads a pytest11 entry point named NAME
    from it before any module, even with plugin autoload off, so a submission could swap in its own."""
    try:
        dirs = (BASE_PIN_DIR / "base-pytest.importdirs").read_text().splitlines()
    except OSError:
        return []                                    # no pin (dbt tasks)
    snapshot = BASE_PIN_DIR / "base-pytest.metadata"
    added = []
    for d in dirs:
        # The snapshot nests deeper import folders under the root's (src/ under .), so only metadata
        # names count.
        base = {e for e in (os.listdir(snapshot / d) if (snapshot / d).is_dir() else [])
                if e.lower().endswith((".dist-info", ".egg-info"))}
        try:
            entries = os.listdir(APP_DIR / d)
        except OSError:
            continue
        for entry in entries:
            rel = entry if d == "." else f"{d}/{entry}"
            if entry.lower().endswith((".dist-info", ".egg-info")) and inside_repo(rel):
                subprocess.run(["rm", "-rf", "--", rel], cwd=APP_DIR)
                if entry not in base:
                    added.append(rel)
        for entry in sorted(base):
            rel = entry if d == "." else f"{d}/{entry}"
            src = snapshot / d / entry
            if not inside_repo(rel):
                continue
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, APP_DIR / rel, symlinks=True)
            else:
                shutil.copy2(src, APP_DIR / rel, follow_symlinks=False)
    if added:
        log(f"Removed {len(added)} package metadata folder(s) the base did not have: {', '.join(added[:10])}")
    return added


def warn_shared_config(paths):
    named = sorted({p for p in paths
                    if p.rsplit("/", 1)[-1] in SHARED_CONFIG_NAMES})
    for p in named:
        log(f"NOTE: model.patch edits {p}, which can also carry pytest settings "
            f"(addopts, plugins). Left in place - the file has non-test uses.")


def clear_reward_channel():
    removed = []
    for name in REWARD_CHANNEL:
        path = VERIFIER_DIR / name
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed.append(name)
        except OSError:
            pass
    if removed:
        log(f"Cleared reward-channel file(s) this run did not write: "
            f"{', '.join(removed)}")


def report_paths():
    out = []
    try:
        reports = load_config().get("grade", {}).get("reports", []) or []
    except (OSError, ValueError):
        return out
    for entry in reports:
        text = str(entry).strip()
        if text:
            out.append(Path(text) if os.path.isabs(text) else APP_DIR / text)
    return out


def clear_reports():
    removed = []
    for path in report_paths():
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed.append(str(path))
        except OSError:
            pass
    if removed:
        log(f"Cleared stale report(s) this run did not write: "
            f"{', '.join(removed)}")


TEST_DIR_SEGMENTS = ("test", "tests", "testing", "__tests__",
                     "testdata", "test_data")

TEST_FILE_SUFFIXES = ("_test.go", "_test.py", "_test.rb", "_test.exs",
                      ".test.js", ".test.jsx", ".test.ts", ".test.tsx",
                      ".test.mjs", ".test.cjs", ".spec.js", ".spec.jsx",
                      ".spec.ts", ".spec.tsx", "_spec.rb", "Test.java",
                      "Tests.cs")
TEST_FILE_PREFIXES = ("test_",)

RUNNER_CONFIG_PREFIXES = ("jest.config.", "jest.setup.", "vitest.config.",
                          "vitest.setup.", "setupTests.", "karma.conf.",
                          ".mocharc.")


def test_dir_of(path):
    parts = path.split("/")
    for i, seg in enumerate(parts[:-1]):
        if seg in TEST_DIR_SEGMENTS:
            return "/".join(parts[:i + 1])
    return None


def is_test_file(path):
    name = path.rsplit("/", 1)[-1]
    return (name.startswith(TEST_FILE_PREFIXES)
            or name.endswith(TEST_FILE_SUFFIXES)
            or name.startswith(RUNNER_CONFIG_PREFIXES))


def base_test_surface(ref):
    r = git("ls-tree", "-r", "-z", "--name-only", ref,
            capture_output=True, text=True)
    if r.returncode != 0:
        return [], []
    dirs, files = set(), set()
    for path in r.stdout.split("\0"):
        if not path:
            continue
        top = test_dir_of(path)
        if top:
            dirs.add(top)
        elif is_test_file(path):
            files.add(path)
    return sorted(dirs), sorted(files)


def live_test_files(dirs):
    out = []
    root = str(APP_DIR)
    prefixes = tuple(d + "/" for d in dirs)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if dirpath != root and ".git" in (set(dirnames) | set(filenames)):
            dirnames[:] = []
            continue
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            if rel in dirs or rel.startswith(prefixes):
                continue
            if is_test_file(rel):
                out.append(rel)
    return out


def new_test_dir_files(ref):
    """Files the SUBMISSION wrote (paths in model.patch) under a test-named directory segment that are
    not tracked at base, e.g. a new pkg/testing/forge.py the runtime code imports. Read from the
    submission's own patch rather than by walking the tree, so vendored files that were never part
    of the submission (a dbt package's own tests/ under dbt_packages/) are left alone, while a forge
    planted anywhere, dbt_packages/ included, is removed."""
    r = git("ls-tree", "-r", "-z", "--name-only", ref, capture_output=True, text=True)
    base_tracked = set(p for p in r.stdout.split("\0") if p) if r.returncode == 0 else set()
    written = patch_paths(read_patch(ARTIFACTS_DIR / "model.patch"))
    return sorted(p for p in written
                  if p and test_dir_of(p) is not None and p not in base_tracked and (APP_DIR / p).exists())


def restore_test_surface(ref):
    dirs, loose = base_test_surface(ref)
    named = set(patch_paths(read_patch(ARTIFACTS_DIR / "model.patch")))
    tampered = sorted(p for p in named
                      if test_dir_of(p) in dirs or p in loose or is_test_file(p))
    for path in tampered:
        log(f"TAMPER: model.patch writes test material {path}; restoring to base")

    for d in dirs:
        rc = git("checkout", "-q", ref, "--", d,
                 stderr=subprocess.DEVNULL).returncode
        if rc != 0:
            log(f"NOTE: {d} does not exist at base; dropping it whole")
        git("clean", "-qfd", "--", d, stderr=subprocess.DEVNULL)

    # Files the submission ADDED under a test-named directory that does not exist at base (e.g. a new
    # pkg/testing/forge.py the runtime code imports). They are not covered by the base dirs above, so
    # the repository's suites would import them; remove them so a forge cannot hide there.
    new_in_test_dirs = sorted(p for p in new_test_dir_files(ref) if p not in loose)
    outside = sorted(set(loose) | set(live_test_files(dirs)) | set(new_in_test_dirs))
    if outside:
        reset_paths(outside, ref)
    if dirs or outside:
        shown = ", ".join(dirs[:8]) + (" ..." if len(dirs) > 8 else "")
        log(f"Restored the test surface to base: {len(dirs)} directory(ies) "
            f"[{shown}] and {len(outside)} loose test file(s)")



def restore_declared_paths(ref):
    """Paths the task declares as fixed input (config.json "restore_paths", e.g. a dbt project's
    seeds/): reset to base, and anything the submission added under them removed, so the
    repository's own checks always run on the original data."""
    paths = [str(p).strip().strip("/") for p in (load_config().get("restore_paths") or [])]
    for path in [p for p in paths if inside_repo(p)]:
        rc = git("checkout", "-q", ref, "--", path, stderr=subprocess.DEVNULL).returncode
        if rc != 0:
            subprocess.run(["rm", "-rf", "--", path], cwd=APP_DIR)
        git("clean", "-qfdx", "--", path, stderr=subprocess.DEVNULL)
        log(f"Restored {path} to base (declared fixed input)")


def clear_suite_dirs(paths, ref):
    """The hidden suite must be exactly test.patch's files. Every folder test.patch writes into that
    does not exist at base is removed before test.patch is applied, so nothing the submission placed
    there (a non-test source file, a build file) is staged, built and run with the suite."""
    roots = set()
    for path in paths:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            if git("cat-file", "-e", f"{ref}:{prefix}", stderr=subprocess.DEVNULL).returncode != 0:
                roots.add(prefix)
                break
        else:
            if parts and not test_dir_of(path):
                log(f"NOTE: test.patch writes {path} into a folder that exists at base; "
                    "keep the hidden suite in a folder of its own")
    for root in sorted(roots):
        target = APP_DIR / root
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        log(f"Cleared {root} (not in base) before applying test.patch")



def cmd_prepare(argv):
    if not APP_DIR.is_dir():
        VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
        sys.exit(6)
    os.chdir(APP_DIR)
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    clear_reward_channel()
    clear_reports()
    subprocess.run(["git", "config", "--global", "--add", "safe.directory",
                    str(APP_DIR)], stderr=subprocess.DEVNULL)
    base = load_config()["base_commit"]
    model_patch = ARTIFACTS_DIR / "model.patch"
    if model_patch.exists() and model_patch.stat().st_size > 0:
        submitted = patch_paths(read_patch(model_patch))
        reset_paths(submitted, base)
        rc = git("apply", "--whitespace=nowarn", str(model_patch)).returncode
        if rc != 0:
            log("ERROR: submitted model.patch failed to apply")
            cmd_grade(["--apply-failed"])
            sys.exit(0)
        log(f"model.patch applied ({model_patch.stat().st_size} bytes)")
        warn_shared_config(submitted)
        hits = tamper_hits(read_patch(model_patch), base)
        if hits:
            for path, reason in hits:
                log(f"TAMPER: {path} {reason}; the repository's suites run the submission's code in "
                    "their own process, so this could forge the P2P report")
            cmd_grade(["--tampered", "; ".join(f"{p} {r}" for p, r in hits)])
            sys.exit(0)
    else:
        log("no model.patch submitted — grading pristine base state")

    # The package is never reinstalled here: an install runs the submission's build backend
    # (setup.py, setup.cfg attr: versions, pyproject hooks) as root. The image's editable install
    # already resolves the package from /app, so source changes apply without it.
    reset_collection_config(base)
    restore_package_metadata()
    restore_declared_paths(base)
    clear_reward_channel()

    restore_test_surface(base)
    test_patch = TESTS_DIR / "test.patch"
    clear_suite_dirs(patch_paths(read_patch(test_patch)), base)
    log("Resetting files touched by test.patch")
    reset_paths(patch_paths(read_patch(test_patch)), base)
    log("Applying test.patch")
    r = git("apply", "--whitespace=nowarn", "--allow-empty", str(test_patch),
            capture_output=True, text=True)
    if r.returncode != 0:
        log("ERROR: test.patch failed to apply")
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit(r.returncode)
    try:
        inner = APP_DIR / "test.sh"
        inner.chmod(inner.stat().st_mode | 0o111)
    except OSError:
        pass



def norm_status(raw):
    raw = str(raw or "").strip().lower()
    if raw == "passed":
        return "passed"
    if raw in ("skipped", "pending", "other"):
        return "skipped"
    return "failed"


def add(res, nid, st, msg=""):
    cur = res.get(nid)
    msg = msg or ""
    if cur is None or RANK[st] > RANK[cur[0]]:
        res[nid] = (st, msg if st != "passed" else "")
    elif RANK[st] == RANK[cur[0]] and st != "passed" and not cur[1] and msg:
        res[nid] = (st, msg)


def parse_ctrf(path, cfg):
    res = {}
    try:
        doc = json.loads(Path(path).read_text())
        tests = (doc.get("results") or {}).get("tests") or []
        if not isinstance(tests, list):
            return res
    except Exception:
        return res
    for tc in tests:
        if not isinstance(tc, dict):
            continue
        nm = str(tc.get("name") or "").strip()
        if not nm:
            continue
        su_raw = tc.get("suite")
        if isinstance(su_raw, list) and su_raw:
            su = str(su_raw[0]).strip()
        elif isinstance(su_raw, str):
            su = su_raw.strip()
        else:
            su = ""
        nid = f"{su}.{nm}" if (cfg.get("node_id") == "suite.name" and su) else nm
        st = norm_status(tc.get("status"))
        msg = ""
        if st != "passed":
            msg = str(tc.get("message") or tc.get("trace") or "").strip()
        add(res, nid, st, msg)
    return res


def junit_status_msg(tc):
    st, msg = "passed", ""
    for ch in tc:
        tag = ch.tag.rsplit("}", 1)[-1]
        if tag in ("failure", "error"):
            parts = [(ch.get("message") or "").strip(), (ch.text or "").strip()]
            return "failed", "\n".join(p for p in parts if p).strip()
        if tag == "skipped":
            st = "skipped"
    return st, msg


def parse_junit(path, cfg):
    res = {}
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return res
    failed_suites = {}
    for tc in root.iter("testcase"):
        cn = (tc.attrib.get("classname", "") or "").strip()
        nm = (tc.attrib.get("name", "") or "").strip()
        if not nm:
            continue
        nid = f"{cn}.{nm}" if cn else nm
        st, msg = junit_status_msg(tc)
        add(res, nid, st, msg)
        low = msg.lower()
        if st == "failed" and cn and any(
            marker in low
            for marker in (
                "cannot find module",
                "failed to collect",
                "error during collection",
                "test suite failed to run",
                "failed to load url",
            )
        ):
            failed_suites[cn] = msg
    for nid in list(res):
        for suite, msg in failed_suites.items():
            if nid.startswith(f"{suite}."):
                add(
                    res,
                    nid,
                    "failed",
                    msg or "test file failed before individual tests ran",
                )
                break
    return res


PARSERS = {"ctrf": parse_ctrf, "junit": parse_junit}


def cmd_grade(argv):
    full = load_config()
    cfg = full.get("grade", {})
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    clear_reward_channel()

    def load_ids(key):
        ids, seen = [], set()
        for line in full.get(key, []):
            s = str(line).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            ids.append(s)
        return ids

    p2p = load_ids("p2p_node_ids")
    f2p = load_ids("f2p_node_ids")

    def stats(fp, pp):
        total = len(f2p) + len(p2p)
        return {"f2p_total": len(f2p), "f2p_passed": fp,
                "p2p_total": len(p2p), "p2p_passed": pp,
                "f2p": fp / len(f2p) if f2p else 0.0,
                "p2p": pp / len(p2p) if p2p else 1.0,
                "partial": (fp + pp) / total if total else 0.0}

    if "--apply-failed" in argv:
        out = {"reward": 0.0, **stats(0, 0), "apply_failed": 1}
        (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
        (VERIFIER_DIR / "reward.txt").write_text("0.0\n")
        (VERIFIER_DIR / "partial_rewards.txt").write_text("0.0\n")
        print(f"[grade] model.patch failed to apply; metrics.json={json.dumps(out)}")
        return
    if "--tampered" in argv:
        reason = argv[argv.index("--tampered") + 1] if len(argv) > argv.index("--tampered") + 1 else ""
        out = {"reward": 0.0, **stats(0, 0), "tampered": 1}
        (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
        (VERIFIER_DIR / "reward.txt").write_text("0.0\n")
        (VERIFIER_DIR / "partial_rewards.txt").write_text("0.0\n")
        print(f"[grade] submission tampers with the test machinery: {reason}; reward 0")
        return
    parse = PARSERS[cfg.get("format", "ctrf")]
    seen = {}
    for rep in cfg["reports"]:
        for k, (st, msg) in parse(rep, cfg).items():
            add(seen, k, st, msg)

    def bucket(ids):
        p = f = 0
        rows = []
        for nid in ids:
            entry = seen.get(nid)
            if entry is None:
                rows.append({"name": nid, "status": "failed",
                             "message": "missing from report (test did not run "
                                        "or produced no result — see raw output)"})
                f += 1
            elif entry[0] == "passed":
                rows.append({"name": nid, "status": "passed"})
                p += 1
            else:
                rows.append({"name": nid, "status": entry[0], "message": entry[1]})
                f += 1
        return p, f, rows

    pp, pf, pr = bucket(p2p)
    fp, ff, fr = bucket(f2p)
    partial_reward = (fp / len(f2p)) if (pf == 0 and f2p) else 0.0
    reward = 1.0 if (pf == 0 and f2p and ff == 0) else 0.0
    # The runner's canary verdict (test.sh header): a test that always fails came back passed or
    # missing, so something in the run rewrote the results and none of them can be trusted.
    canary = seen.get(CANARY_ID)
    untrusted = bool(full.get("canary")) and (canary is None or canary[0] != "passed")
    if untrusted:
        partial_reward = reward = 0.0

    def ctrf_test(t, b):
        d = {"name": f"[{b}] {t['name']}", "status": t["status"]}
        if t.get("message"):
            d["message"] = t["message"]
        return d

    ctrf = {"reportFormat": "CTRF", "specVersion": "1.0.0", "results": {
        "tool": {"name": cfg.get("tool_label", "unknown")},
        "summary": {"tests": len(p2p)+len(f2p), "passed": pp+fp,
                    "failed": pf+ff, "skipped": 0, "pending": 0, "other": 0},
        "tests": [ctrf_test(t, "p2p") for t in pr]
                + [ctrf_test(t, "f2p") for t in fr]}}
    (VERIFIER_DIR / "ctrf.json").write_text(json.dumps(ctrf, indent=2))

    out = {"reward": reward, **stats(fp, pp), **({"untrusted": 1} if untrusted else {})}
    (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
    (VERIFIER_DIR / "reward.txt").write_text(f"{reward}\n")
    (VERIFIER_DIR / "partial_rewards.txt").write_text(
        f"{partial_reward}\n")

    fails = ([("p2p", t) for t in pr if t["status"] != "passed"]
             + [("f2p", t) for t in fr if t["status"] != "passed"])
    if fails:
        print(f"[verifier] ===== FAILURES ({len(fails)}) =====")
        for b, t in fails:
            print(f"[verifier] ✗ [{b}] {t['name']}")
            for line in (t.get("message") or "(no message)").splitlines():
                print(f"    {line}")
    if untrusted:
        print(f"[verifier] ✗ {CANARY_ID}: {canary[1] if canary else 'missing from the base report'}; "
              "the repository's suite results cannot be trusted, reward 0")
    print(f"P2P {pp}/{len(p2p)} pass {pf} fail; F2P {fp}/{len(f2p)} pass {ff} fail; "
          + f"PARTIAL {out['partial']}; GATED_REWARD {reward}")


def cmd_patch_paths(argv):
    for path in patch_paths(read_patch(argv[0])):
        print(path)


def main():
    cmds = {"prepare": cmd_prepare, "grade": cmd_grade,
            "patch-paths": cmd_patch_paths}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"usage: grader.py {{{'|'.join(cmds)}}} [args]", file=sys.stderr)
        sys.exit(2)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
