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
RANK = {"passed": 0, "skipped": 1, "failed": 2}

COLLECTION_CONFIG_NAMES = ("conftest.py", "pytest.ini", ".pytest.ini",
                           "sitecustomize.py", "usercustomize.py")

IMPORT_SHADOW_NAMES = ("pytest", "_pytest", "pluggy", "py", "iniconfig",
                       "packaging", "tomli", "exceptiongroup", "pygments")

SHARED_CONFIG_NAMES = ("pyproject.toml", "setup.cfg", "tox.ini")

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", ".tox", "__pycache__",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", "target", "vendor"}

REWARD_CHANNEL = ("reward.txt", "reward.json", "metrics.json", "ctrf.json",
                  "partial_rewards.txt")

BUILD_DEFINITION_NAMES = ("pyproject.toml", "setup.py")

ENTRY_POINT_MARKERS = ("entry_points", "[project.entry-points",
                       "[project.scripts")


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



def git(*args, **kw):
    return subprocess.run(["git", *args], cwd=APP_DIR, **kw)


def reset_paths(paths, ref):
    for f in paths:
        if not f:
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


def import_shadow_paths():
    out = []
    for name in IMPORT_SHADOW_NAMES:
        for rel in ("%s.py" % name, "%s/__init__.py" % name):
            if (APP_DIR / rel).is_file():
                out.append(rel)
    return out


def reset_collection_config(ref):
    paths = sorted(set(tracked_config_paths(ref)) | set(live_config_paths())
                   | set(import_shadow_paths())
                   | set(pythonpath_shadow_paths(ref)))
    if paths:
        shown = ", ".join(paths[:10]) + (" ..." if len(paths) > 10 else "")
        log(f"Resetting {len(paths)} collection/reporting config file(s) "
            f"to base: {shown}")
        reset_paths(paths, ref)
    return paths


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


def added_test_dirs(dirs):
    out = []
    for path in patch_paths(read_patch(TESTS_DIR / "test.patch")):
        top = test_dir_of(path)
        if top and top not in dirs and top not in out:
            out.append(top)
    return out


def suite_package_dirs(ref):
    r = git("ls-tree", "-r", "-z", "--name-only", ref,
            capture_output=True, text=True)
    if r.returncode != 0:
        return []
    base_dirs = set()
    for path in r.stdout.split("\0"):
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            base_dirs.add(path)
    out = []
    for path in patch_paths(read_patch(TESTS_DIR / "test.patch")):
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/".join(parts[:i])
            if d in base_dirs:
                continue
            if d not in out:
                out.append(d)
            break
    return sorted(out)


def suite_dir_intruders(ref):
    ours = set(patch_paths(read_patch(TESTS_DIR / "test.patch")))
    out = []
    for d in suite_package_dirs(ref):
        for dirpath, dirnames, filenames in os.walk(APP_DIR / d):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), str(APP_DIR))
                if rel not in ours:
                    out.append(rel)
    return sorted(out)


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


def restore_test_surface(ref):
    dirs, loose = base_test_surface(ref)
    dirs = sorted(set(dirs) | set(added_test_dirs(dirs)))
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

    outside = sorted(set(loose) | set(live_test_files(dirs)))
    intruders = [p for p in suite_dir_intruders(ref) if p not in outside]
    for path in intruders:
        log(f"TAMPER: {path} sits in a directory test.patch creates for the "
            "graded suite and test.patch does not write it; dropping it")
    if outside or intruders:
        reset_paths(sorted(set(outside) | set(intruders)), ref)
    if dirs or outside or intruders:
        shown = ", ".join(dirs[:8]) + (" ..." if len(dirs) > 8 else "")
        log(f"Restored the test surface to base: {len(dirs)} directory(ies) "
            f"[{shown}], {len(outside)} loose test file(s) and "
            f"{len(intruders)} file(s) left in a suite directory")


def canary_name(argv):
    for index, arg in enumerate(argv):
        if arg == "--canary" and index + 1 < len(argv):
            return str(argv[index + 1]).strip()
        if arg.startswith("--canary="):
            return arg.split("=", 1)[1].strip()
    return ""


def canary_verdict(argv, seen):
    name = canary_name(argv)
    if not name:
        return "", True, ""
    hits = [nid for nid in seen
            if nid == name or nid.rsplit(".", 1)[-1] == name]
    if not hits:
        return name, False, (
            f"FORGED REPORT: the canary {name} planted in this run is absent "
            "from every report, so nothing the runner wrote is in them. "
            "Reward forced to 0.")
    passed = sorted(nid for nid in hits if seen[nid][0] == "passed")
    if passed:
        return name, False, (
            f"FORGED REPORT: the canary {name} is reported PASSED ({passed}), "
            "and it fails by construction in every run. Reward forced to 0.")
    return name, True, (
        f"canary {name} reported failed by the run, as it must be; the report "
        "is the runner's")


def seal_dir(argv):
    for index, arg in enumerate(argv):
        if arg == "--seal" and index + 1 < len(argv):
            return str(argv[index + 1]).strip()
        if arg.startswith("--seal="):
            return arg.split("=", 1)[1].strip()
    return ""


def sealed_reports(argv, reports):
    root = seal_dir(argv)
    if not root:
        return list(reports), ""
    graded, unsealed = [], []
    for rep in reports:
        copy = Path(root) / Path(str(rep)).name
        if copy.is_file():
            graded.append(str(copy))
        else:
            unsealed.append(str(rep))
    detail = f"grading {len(graded)} sealed report(s) out of {root}"
    if unsealed:
        detail += (
            "; UNSEALED REPORT(S) IGNORED: " + ", ".join(unsealed)
            + " - the frame took a seal and these are not in it, so nothing "
            "says the bytes at those paths are the ones the runner wrote")
    return graded, detail


def ignored_paths(paths):
    wanted = [p for p in paths if p]
    if not wanted:
        return set()
    r = git("check-ignore", "-z", "--stdin", input="\0".join(wanted) + "\0",
            capture_output=True, text=True)
    if r.returncode not in (0, 1):
        return set()
    return {p for p in r.stdout.split("\0") if p}


def path_dirs_in_app():
    out = []
    root = str(APP_DIR).rstrip("/")
    for entry in (os.environ.get("PATH") or "").split(os.pathsep):
        entry = entry.rstrip("/")
        if entry.startswith(root + "/"):
            out.append(entry[len(root) + 1:])
    return out


def pythonpath_dirs_in_app():
    out = []
    root = str(APP_DIR).rstrip("/")
    for entry in (os.environ.get("PYTHONPATH") or "").split(os.pathsep):
        entry = entry.rstrip("/")
        if entry.startswith(root + "/"):
            out.append(entry[len(root) + 1:])
    return out


def shadow_candidates():
    out, seen = [], set()
    for base_dir in ["", *pythonpath_dirs_in_app()]:
        prefix = (base_dir + "/") if base_dir else ""
        for name in IMPORT_SHADOW_NAMES:
            for rel in (prefix + name + ".py", prefix + name + "/__init__.py"):
                if rel not in seen:
                    seen.add(rel)
                    out.append(rel)
    return out


def pythonpath_shadow_paths(ref):
    return [rel for rel in shadow_candidates()
            if (APP_DIR / rel).is_file() and show(ref, rel) is None]


def refused_paths(paths, ref):
    out = {}
    on_path = path_dirs_in_app()
    for rel in paths:
        for d in on_path:
            if rel == d or rel.startswith(d + "/"):
                out[rel] = ("it is inside " + d + ", which is on the verifier's "
                            "PATH, so a file there is a program the verifier "
                            "would run as itself")
                break
    shadows = set(shadow_candidates())
    for rel in paths:
        if rel not in out and rel in shadows and show(ref, rel) is None:
            out[rel] = ("it is a module the runner imports for ITSELF, sitting "
                        "in a directory the verifier's PYTHONPATH names, and "
                        "base has no such file - so it shadows the runner "
                        "rather than being any part of this repository")
    ours = set(patch_paths(read_patch(TESTS_DIR / "test.patch")))
    suite_dirs = suite_package_dirs(ref)
    for rel in paths:
        if rel in out or rel in ours:
            continue
        for d in suite_dirs:
            if rel.startswith(d + "/"):
                out[rel] = ("it is inside " + d + ", which base does not have "
                            "and test.patch creates for the graded suite, and "
                            "test.patch does not write this file - so it is "
                            "code the suite's own binary would run rather than "
                            "any part of this repository")
                break
    for rel in ignored_paths([p for p in paths if p not in out]):
        out[rel] = ("this repository's own ignore rules say it is not source, "
                    "so it is build output the image made rather than anything "
                    "a solution writes")
    return out


def patch_sections(text):
    sections, current = [], None
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current is not None:
                sections.append("".join(current))
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        sections.append("".join(current))
    return sections


def apply_submission(model_patch, base):
    text = read_patch(model_patch)
    submitted = patch_paths(text)
    refused = refused_paths(submitted, base)
    if not refused:
        reset_paths(submitted, base)
        return git("apply", "--whitespace=nowarn",
                   str(model_patch)).returncode, submitted
    for rel in sorted(refused):
        log(f"REFUSED {rel}: {refused[rel]}.")
    kept = [p for p in submitted if p not in refused]
    sections = patch_sections(text)
    if "".join(sections) != text:
        log("model.patch is not a git-format diff, so the refused paths are "
            "reset after the apply rather than dropped from it")
        reset_paths(kept, base)
        rc = git("apply", "--whitespace=nowarn", str(model_patch)).returncode
        reset_paths(sorted(refused), base)
        return rc, kept
    filtered = "".join(s for s in sections
                       if not set(patch_paths(s)) & set(refused))
    if not filtered.strip():
        log("model.patch names nothing outside build output and the verifier's "
            "PATH; grading the base state")
        return 0, []
    trimmed = VERIFIER_DIR / "model.source.patch"
    trimmed.write_text(filtered)
    reset_paths(kept, base)
    return git("apply", "--whitespace=nowarn", str(trimmed)).returncode, kept



INSTALL_TIMEOUT = 300

BUILD_SYSTEM_TABLE = re.compile(r"^\s*\[\s*build-system\s*\]")
TOP_LEVEL_TABLE = re.compile(r"^\s*\[")
INLINE_BUILD_SYSTEM = re.compile(r"^\s*build-system\s*=")


def declares_entry_points():
    for name in ("setup.cfg", "setup.py", "pyproject.toml"):
        try:
            text = (APP_DIR / name).read_text(errors="replace")
        except OSError:
            continue
        if any(marker in text for marker in ENTRY_POINT_MARKERS):
            return True
    return False


def strip_build_system(text):
    kept, drop, at_top = [], False, True
    for line in text.splitlines(keepends=True):
        if TOP_LEVEL_TABLE.match(line):
            drop = bool(BUILD_SYSTEM_TABLE.match(line))
            at_top = False
        if drop or (at_top and INLINE_BUILD_SYSTEM.match(line)):
            continue
        kept.append(line)
    return "".join(kept)


def build_system_table(text):
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if TOP_LEVEL_TABLE.match(line):
            inside = bool(BUILD_SYSTEM_TABLE.match(line))
        if inside:
            out.append(line)
    return "".join(out)


def show(ref, path):
    r = git("show", f"{ref}:{path}", stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
    return r.stdout if r.returncode == 0 else None


def put(path, text):
    if text is None:
        try:
            path.unlink()
        except OSError:
            pass
    else:
        path.write_text(text)


def swap_build_definition(ref):
    saved = {}
    for name in BUILD_DEFINITION_NAMES:
        live = APP_DIR / name
        current = live.read_text(errors="replace") if live.is_file() else None
        base = show(ref, name)
        if name == "pyproject.toml":
            if current is None:
                continue
            table = build_system_table(base or "")
            table = (table.rstrip("\n") + "\n\n") if table.strip() else ""
            wanted = table + strip_build_system(current)
        else:
            wanted = base
        if wanted == current:
            continue
        saved[name] = current
        put(live, wanted)
    return saved


PLUGIN_ENTRY_POINT_GROUP = "pytest11"

PLUGIN_DECLARATION_NAMES = ("pyproject.toml", "setup.cfg")

TOML_ESCAPE = re.compile(r"\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})")


def plain(text):
    return TOML_ESCAPE.sub(
        lambda m: chr(int(m.group(1) or m.group(2), 16)), text)


def plugin_declarations(text):
    out, table, key = [], False, False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("["):
            table = PLUGIN_ENTRY_POINT_GROUP in plain(stripped)
            key = False
            if table:
                out.append(stripped)
            continue
        if table:
            out.append(stripped)
            continue
        indented = raw[:1] in (" ", "\t")
        if not indented and "=" in stripped:
            name = plain(stripped.split("=", 1)[0]).strip().strip("\"'")
            key = name == PLUGIN_ENTRY_POINT_GROUP
            if key:
                out.append(stripped)
        elif key and indented:
            out.append(stripped)
    return out


def pin_plugin_entry_points(ref, saved):
    for name in PLUGIN_DECLARATION_NAMES:
        live = APP_DIR / name
        if not live.is_file():
            continue
        current = live.read_text(errors="replace")
        base = show(ref, name)
        if plugin_declarations(current) == plugin_declarations(base or ""):
            continue
        log(f"TAMPER: {name} changes the {PLUGIN_ENTRY_POINT_GROUP} entry-point "
            f"group, which names modules pytest runs as itself; the install "
            f"reads base's {name} instead")
        saved.setdefault(name, current)
        put(live, base)


def refresh_entry_points(ref):
    if not declares_entry_points():
        return
    saved = swap_build_definition(ref)
    pin_plugin_entry_points(ref, saved)
    if saved:
        log("Build definition restored to base for the install: "
            + ", ".join(sorted(saved)))
    python = shutil.which("python") or sys.executable
    try:
        r = subprocess.run(
            [python, "-m", "pip", "install", "-e", ".", "--no-deps",
             "--no-build-isolation", "-q"],
            cwd=str(APP_DIR), capture_output=True, text=True,
            timeout=INSTALL_TIMEOUT)
        log(f"Entry-point refresh: pip install -e . exited {r.returncode}")
    except (OSError, subprocess.SubprocessError) as error:
        log(f"Entry-point refresh did not run: {error}")
    finally:
        for name, text in saved.items():
            put(APP_DIR / name, text)


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
        rc, submitted = apply_submission(model_patch, base)
        if rc != 0:
            log("ERROR: submitted model.patch failed to apply")
            cmd_grade(["--apply-failed"])
            sys.exit(0)
        log(f"model.patch applied ({model_patch.stat().st_size} bytes, "
            f"{len(submitted)} path(s) kept)")
        warn_shared_config(submitted)
    else:
        log("no model.patch submitted — grading pristine base state")

    refresh_entry_points(base)

    reset_collection_config(base)
    clear_reward_channel()

    restore_test_surface(base)
    test_patch = TESTS_DIR / "test.patch"
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
        out = {"reward": 0.0, "partial_reward": 0.0, **stats(0, 0),
               "apply_failed": 1}
        (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
        (VERIFIER_DIR / "reward.txt").write_text("0.0\n")
        (VERIFIER_DIR / "partial_rewards.txt").write_text("0.0\n")
        print(f"[grade] model.patch failed to apply; metrics.json={json.dumps(out)}")
        return
    parse = PARSERS[cfg.get("format", "ctrf")]
    seen = {}
    graded_reports, seal_detail = sealed_reports(argv, cfg["reports"])
    if seal_detail:
        log(seal_detail)
    for rep in graded_reports:
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
    canary, canary_ok, canary_detail = canary_verdict(argv, seen)
    if canary:
        log(canary_detail)
        if not canary_ok:
            reward = 0.0
            partial_reward = 0.0

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

    out = {"reward": reward, "partial_reward": partial_reward, **stats(fp, pp)}
    if canary:
        out["canary_ok"] = int(canary_ok)
    (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
    (VERIFIER_DIR / "reward.txt").write_text(f"{reward}\n")
    (VERIFIER_DIR / "partial_rewards.txt").write_text(f"{partial_reward}\n")

    fails = ([("p2p", t) for t in pr if t["status"] != "passed"]
             + [("f2p", t) for t in fr if t["status"] != "passed"])
    if fails:
        print(f"[verifier] ===== FAILURES ({len(fails)}) =====")
        for b, t in fails:
            print(f"[verifier] ✗ [{b}] {t['name']}")
            for line in (t.get("message") or "(no message)").splitlines():
                print(f"    {line}")
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
