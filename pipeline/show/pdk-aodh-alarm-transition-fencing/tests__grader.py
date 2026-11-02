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

REWARD_CHANNEL = ("reward.txt", "reward.json", "metrics.json", "ctrf.json")


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
                   | set(import_shadow_paths()))
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
    if outside:
        reset_paths(outside, ref)
    if dirs or outside:
        shown = ", ".join(dirs[:8]) + (" ..." if len(dirs) > 8 else "")
        log(f"Restored the test surface to base: {len(dirs)} directory(ies) "
            f"[{shown}] and {len(outside)} loose test file(s)")



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
    git("reset", "--hard", base)
    git("clean", "-fd", "aodh")
    for leftover in (APP_DIR / "test.sh",):
        if leftover.exists() and not git("ls-files", "--error-unmatch", str(leftover), capture_output=True).returncode == 0:
            leftover.unlink()
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
    else:
        log("no model.patch submitted — grading pristine base state")

    reset_collection_config(base)
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
    # gated_p2p_node_ids lists hidden guard tests (black-box, run out of process, so they cannot be
    # forged). With p2p_gating "guards" (the default) they gate the reward together with F2P, and the
    # repository's own suites (which load the submission's code in-process, so their reports can be
    # forged) are reported but advisory; "all" also gates every P2P test of those suites. Without
    # gated_p2p_node_ids every P2P test gates, as before.
    gated_mode = "gated_p2p_node_ids" in full
    gated = load_ids("gated_p2p_node_ids") if gated_mode else p2p
    p2p_gates = (not gated_mode) or full.get("p2p_gating", "guards") != "guards"

    def stats(fp, pp, gp=None):
        total = len(f2p) + len(p2p)
        out = {"f2p_total": len(f2p), "f2p_passed": fp,
               "p2p_total": len(p2p), "p2p_passed": pp,
               "f2p": fp / len(f2p) if f2p else 0.0,
               "p2p": pp / len(p2p) if p2p else 1.0,
               "partial": (fp + pp) / total if total else 0.0}
        if gated_mode:
            out.update(gated_p2p_total=len(gated), gated_p2p_passed=gp or 0, p2p_advisory=not p2p_gates)
        return out

    if "--apply-failed" in argv:
        out = {"reward": 0.0, **stats(0, 0), "apply_failed": 1}
        (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
        (VERIFIER_DIR / "reward.txt").write_text("0.0\n")
        (VERIFIER_DIR / "partial_rewards.txt").write_text("0.0\n")
        print(f"[grade] model.patch failed to apply; metrics.json={json.dumps(out)}")
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
    gp, gf, gr = bucket(gated) if gated_mode else (pp, pf, pr)
    regression = gf > 0 or (p2p_gates and pf > 0)
    partial_reward = (fp / len(f2p)) if (not regression and f2p) else 0.0
    reward = 1.0 if (not regression and f2p and ff == 0) else 0.0

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
                + [ctrf_test(t, "f2p") for t in fr]
                + ([ctrf_test(t, "p2p-gated") for t in gr] if gated_mode else [])}}
    (VERIFIER_DIR / "ctrf.json").write_text(json.dumps(ctrf, indent=2))

    out = {"reward": reward, **stats(fp, pp, gp)}
    (VERIFIER_DIR / "metrics.json").write_text(json.dumps(out))
    (VERIFIER_DIR / "reward.txt").write_text(f"{reward}\n")
    (VERIFIER_DIR / "partial_rewards.txt").write_text(
        f"{partial_reward}\n")

    fails = ([("p2p" + ("" if p2p_gates else " (advisory)"), t) for t in pr if t["status"] != "passed"]
             + [("f2p", t) for t in fr if t["status"] != "passed"]
             + ([("p2p-gated", t) for t in gr if t["status"] != "passed"] if gated_mode else []))
    if fails:
        print(f"[verifier] ===== FAILURES ({len(fails)}) =====")
        for b, t in fails:
            print(f"[verifier] ✗ [{b}] {t['name']}")
            for line in (t.get("message") or "(no message)").splitlines():
                print(f"    {line}")
    gated_note = f"GATED P2P {gp}/{len(gated)} pass {gf} fail; " if gated_mode else ""
    print(f"P2P {pp}/{len(p2p)} pass {pf} fail{'' if p2p_gates else ' (advisory)'}; {gated_note}"
          + f"F2P {fp}/{len(f2p)} pass {ff} fail; PARTIAL {out['partial']}; GATED_REWARD {reward}")


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
