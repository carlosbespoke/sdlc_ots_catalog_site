#!/usr/bin/env python3
"""Spec-driven grader for "componentize a CDK app without touching production" tasks (separate verifier container).

Shared by every task of the family, TypeScript and Python. Each task ships /tests/spec.json, the expected (reference)
templates per configuration in /tests/expected/<config>/, the configurations in /tests/configs/, the trusted copies of
the files the agent must not change in /tests/trusted/, and the family's entry points (harness.ts, harness_py.py),
code rules (rules.js, rules_py.py), interface-check generator (iface.py) and comparer (cfn_equal.py).

Nothing the agent ran or saved decides the grade. The submission is copied to a scratch directory without
node_modules, cdk.out, .git, virtual environments, caches and symlinks; the trusted files (the entry module, the
configuration schema, cdk.json, the Lambda assets, deployed/, tools/, scripts/ ...) are restored over it; the grader
adds its own entry point (grade/) and synthesizes every configuration itself, as an unprivileged user, with no network.
The entry point calls the build function of the trusted entry module, exactly as the repository's own entry does, so a
forged cdk.out or tree.json in the repository is never read. Its structure report is written through functions captured
before any submission code runs, carries a per-run nonce, and is cross-checked against the synthesized templates.

Gates (any failure -> reward 0):
  integrity    every file the agent must not change (spec "owned", trusted copies in /tests/trusted) is in the
               submission exactly as shipped: not changed, deleted, replaced by a directory or a symbolic link, and
               nothing added inside a protected directory except new configuration files `config/<name>.json` and new
               `deployed/<name>/` directories (the statement invites both, to try other configurations); file modes
               are not compared. The trusted copies are restored afterwards either way, so grading runs on them.
  build        TypeScript: tsc over the code directory, the trusted entry module and the grader entry point;
               Python: every .py file of the repository compiles
  rules        the static code rules (rules.js / rules_py.py)
  synth        every visible configuration synthesizes through the grader entry point; the report is genuine and clean
  provenance   in every visible configuration, each resource is created by the same L1 class, directly inside an
               instance of the reference's parent construct class or of a subclass of it (aws-cdk-lib's or the
               solver's own), with the same number of raw overrides as in the reference, and the report and the
               templates list the same resources
  templates    the templates of every visible configuration equal the reference templates (cfn_equal.py), with two
               allowances that only the tagging decides: a REST API deployment compares by content whatever its
               logical ID (spec normalize_api_deployments: tagging the API changes that ID), and the component tag is
               not compared inside tag specifications nor in an Auto Scaling group's PropagateAtLaunch flag
Checks (all core: a failure scores 0):
  layout_<Component>   every instance of the component exists at its path as an instance of the exported class, its
                       stated construct paths exist with the stated aws-cdk-lib classes, and it contains exactly the
                       resources the reference places in it (visible configurations)
  probe_<name>         a hidden configuration: synth, template equality, provenance and layout/ownership of every
                       component. Besides the author's hidden configurations the spec carries, for each of them, a
                       variant built when the task was made (spec configs[...].variant_of): its new entries and new
                       stage renamed to names drawn from a per-task salt (shaped like the originals, appearing nowhere
                       in the task) and some of their numbers replaced by other valid values; its expected templates
                       are the reference's for that configuration, which equal the current app's apart from the
                       allowed changes
  interface_<Component>  props and public property types (TypeScript: tsc over the generated interface check, which
                         also rejects `any` and props or properties whose declared type is not the stated one; Python:
                         keyword-only constructor parameters annotated with the stated types, isinstance of the public
                         properties) and the public properties refer to the stated constructs (visible configurations)
  interface_<Stack>      for each stack whose public properties the spec states (spec.stacks[].properties): the
                         properties exist with the stated types (TypeScript: read-only, not `any`) and refer to the
                         stated constructs (visible configurations)
reward = passed checks / all checks when every gate and every check passes (1.0), else 0.
Outputs: /logs/verifier/reward.txt (the number), reward.json ({"reward": x}), metrics.json (gates, checks, details).

Task type "regression-repair" (spec task_type): the same gates (the expected templates are the reference's: production's
templates plus the stated feature), no layout, interface or tag checks, and instead of them:
  regression_<id>   a regression the task's feature commit introduced: the resources and template entries it changes
                    (spec regressions[].keys, per configuration, recorded when the task was built) equal the expected
                    ones in every configuration, visible and hidden
  feature           the resources and entries the feature adds or changes (spec feature_keys) equal the expected ones
  probe_<name>      a hidden configuration: synth, template equality and provenance
"""
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
import traceback
from pathlib import Path

TESTS = Path(os.environ.get("TESTS_DIR", "/tests"))
VERIFIER = Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
WORK = Path(os.environ.get("GRADER_WORK", "/tmp/cdk-grade"))
RUN_AS = os.environ.get("GRADER_RUN_AS", "nobody")
NODE_MODULES = Path(os.environ.get("GRADER_NODE_MODULES", "/opt/cdk-node/node_modules"))
LINT_NODE_MODULES = os.environ.get("GRADER_LINT_NODE_MODULES", "/opt/lint-node/node_modules")
PY = os.environ.get("GRADER_PYTHON", "/opt/cdk-py/bin/python3")
SYNTH_TIMEOUT = int(os.environ.get("GRADER_SYNTH_TIMEOUT", "600"))
PROXY = "http://127.0.0.1:9"
DROP_ALWAYS = {"node_modules", "cdk.out", ".git", "grade", ".venv", "venv", "__pycache__", ".pytest_cache",
               ".mypy_cache", ".jest-cache"}

sys.path.insert(0, str(TESTS))
from cfn_equal import compare, load_templates  # noqa: E402
from iface import harness_spec, names  # noqa: E402

LOG_LINES = []


def log(msg):
    line = f"[grade] {msg}"
    LOG_LINES.append(line)
    print(line, flush=True)


RUNUSER = shutil.which("runuser") or "/usr/sbin/runuser"


def cdk_bin():
    for c in (os.environ.get("GRADER_CDK"), str(NODE_MODULES / ".bin" / "cdk"), "/opt/cdk-cli/node_modules/.bin/cdk"):
        if c and Path(c).exists():
            return c
    return "cdk"


def as_user_prefix():
    # -m keeps the environment the grader sets (HOME, TMPDIR, PATH ...): runuser would otherwise set HOME to the
    # user's home (/nonexistent for nobody), where jsii cannot create its package cache
    if RUN_AS and os.geteuid() == 0:
        return [RUNUSER, "-m", "-u", RUN_AS, "--"]
    return []


def base_env():
    path = f"{NODE_MODULES / '.bin'}:/opt/cdk-cli/node_modules/.bin:/usr/local/bin:/usr/bin:/bin"
    return {
        "PATH": path,
        "HOME": str(WORK / "home"),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "CDK_DISABLE_VERSION_CHECK": "true",
        "CDK_DISABLE_CLI_TELEMETRY": "true",
        "AWS_EC2_METADATA_DISABLED": "true",
        "JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION": "1",
        "JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "HTTPS_PROXY": PROXY, "HTTP_PROXY": PROXY, "https_proxy": PROXY, "http_proxy": PROXY,
        "TMPDIR": str(WORK / "tmp"),
    }


def run(cmd, cwd, env=None, timeout=600, user=True):
    t0 = time.time()
    try:
        p = subprocess.run((as_user_prefix() if user else []) + cmd, cwd=str(cwd), env=env or base_env(),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        out = p.stdout.decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") + f"\n[grader] timed out after {timeout}s"
        rc = 124
    return rc, out, round(time.time() - t0, 1)


def tail(text, n=12):
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(l[:400] for l in lines[-n:])


# ---------------------------------------------------------------------------------------------- preparation
def copy_submission(spec):
    artifact = Path(os.environ.get("ARTIFACT_DIR") or spec["project"])
    src = WORK / "src"
    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "out").mkdir(parents=True)
    (WORK / "home").mkdir()
    (WORK / "tmp").mkdir()
    drop = set(spec.get("drop", [])) | DROP_ALWAYS
    dropped_links = []
    if artifact.is_dir():
        def ignore(dirpath, names):
            out = set()
            for n in names:
                p = Path(dirpath) / n
                if p.is_symlink():
                    dropped_links.append(str(p.relative_to(artifact)))
                    out.add(n)
                elif n in drop and (Path(dirpath) == artifact or n in ("__pycache__", "node_modules", ".pytest_cache")):
                    out.add(n)
                elif n.endswith((".pyc", ".pyo")):
                    out.add(n)
            return out
        shutil.copytree(artifact, src, ignore=ignore, symlinks=True)
    else:
        log(f"no {artifact} artifact was collected; grading an empty submission")
        src.mkdir()
    if dropped_links:
        log(f"ignored {len(dropped_links)} symlink(s) in the submission, e.g. {dropped_links[:3]}")
    # trusted files the agent must not change: compare first (the integrity gate), then restore them either way
    trusted = TESTS / "trusted"
    INTEGRITY[:] = integrity_problems(spec, src, trusted, dropped_links) if artifact.is_dir() else \
        ["no submission was collected"]
    for rel in spec.get("owned", []):
        t = trusted / rel
        d = src / rel
        if d.is_dir() and not d.is_symlink():
            shutil.rmtree(d)
        elif d.exists() or d.is_symlink():
            d.unlink()
        if t.is_dir():
            shutil.copytree(t, d)
        elif t.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(t, d)
    # the grader's own entry point
    g = src / "grade"
    g.mkdir()
    for name, source in spec["grade_files"].items():
        shutil.copy2(TESTS / source, g / name)
    if spec["language"] == "typescript":
        (src / "node_modules").symlink_to(NODE_MODULES)
        write_ts_projects(spec, src)
    # source tree: root-owned, world-readable; outputs, HOME and TMPDIR writable by the unprivileged user
    for root, dirs, files in os.walk(src):
        for n in dirs + files:
            p = Path(root) / n
            if not p.is_symlink():
                p.chmod(p.stat().st_mode | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                        | (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH if p.is_dir() else 0))
    if os.geteuid() == 0 and RUN_AS:
        for d in ("out", "home", "tmp"):
            subprocess.run(["chown", "-R", f"{RUN_AS}", str(WORK / d)], check=True)
    WORK.chmod(0o755)
    return src


INTEGRITY = []
EXTRA_OK_FILES = {"config": re.compile(r"^[^/]+\.json$")}  # new configuration files config/<name>.json
EXTRA_OK_DIRS = {"deployed"}  # new deployed/<name>/ directories (templates of a configuration being tried)


def file_digest(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def integrity_problems(spec, src, trusted, dropped_links):
    """How the submission's copies of the files the agent must not change differ from the trusted ones."""
    probs = []
    owned = spec.get("owned", [])
    for link in dropped_links:
        if any(link == o or link.startswith(o.rstrip("/") + "/") for o in owned):
            probs.append(f"{link}: replaced by a symbolic link")
    for rel in owned:
        t, d = trusted / rel, src / rel
        if not t.exists():
            continue
        if t.is_file():
            if not d.exists():
                if not any(l == rel for l in dropped_links):
                    probs.append(f"{rel}: deleted")
            elif d.is_dir():
                probs.append(f"{rel}: replaced by a directory")
            elif file_digest(d) != file_digest(t):
                probs.append(f"{rel}: changed")
            continue
        if not d.exists():
            probs.append(f"{rel}/: deleted")
            continue
        if not d.is_dir():
            probs.append(f"{rel}/: replaced by a file")
            continue
        want = {str(p.relative_to(t)): p for p in t.rglob("*")}
        have = {str(p.relative_to(d)): p for p in d.rglob("*")}
        for r, p in sorted(want.items()):
            q = have.get(r)
            where = f"{rel}/{r}"
            if q is None:
                if not any(l == where for l in dropped_links):
                    probs.append(f"{where}: deleted")
            elif p.is_dir() != q.is_dir():
                probs.append(f"{where}: replaced by a {'file' if p.is_dir() else 'directory'}")
            elif p.is_file() and file_digest(p) != file_digest(q):
                probs.append(f"{where}: changed")
        for r, q in sorted(have.items()):
            if r in want:
                continue
            top = r.split("/")[0]
            if rel in EXTRA_OK_FILES and EXTRA_OK_FILES[rel].match(r) and q.is_file():
                continue
            if rel in EXTRA_OK_DIRS and top not in want and (d / top).is_dir():
                continue
            if q.is_dir() and any(k.startswith(r + "/") for k in have if k not in want):
                continue  # reported through the files inside it
            probs.append(f"{rel}/{r}: added")
    # scripts/ci.sh synthesizes every deployed/<stage>/ with config/<stage>.json: a configuration being tried needs both
    dep, trusted_dep = src / "deployed", trusted / "deployed"
    if dep.is_dir() and not dep.is_symlink():
        for p in sorted(dep.iterdir()):
            if p.is_dir() and not (trusted_dep / p.name).exists() and not (src / "config" / f"{p.name}.json").is_file():
                probs.append(f"deployed/{p.name}/: no config/{p.name}.json, so scripts/ci.sh fails")
    return probs


def write_ts_projects(spec, src):
    """grade/tsconfig.grade.json (the build gate), grade/tsconfig.iface.json and the generated interface check."""
    sys.path.insert(0, str(TESTS))
    from iface import generate_ts
    code = spec["code_dir"]
    base = {"extends": "../tsconfig.json", "compilerOptions": {"noEmit": True, "types": ["node"]}}
    (src / "grade" / "tsconfig.grade.json").write_text(json.dumps(
        {**base, "include": [f"../{code}/**/*.ts", f"../{spec['entry']['module']}", "harness.ts"]}, indent=1))
    (src / "grade" / "tsconfig.iface.json").write_text(json.dumps(
        {**base, "include": [f"../{code}/**/*.ts", "interface-check.ts"]}, indent=1))
    text, owner = generate_ts(spec)
    (src / "grade" / "interface-check.ts").write_text(text)
    (WORK / "iface-owner.json").write_text(json.dumps(owner))


# ---------------------------------------------------------------------------------------------- gates
TS_ERROR = re.compile(r"^(?P<file>[^\s(][^(]*)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<msg>.*)$")


def tsc(src, project):
    rc, out, secs = run([str(NODE_MODULES / ".bin" / "tsc"), "-p", project], src, timeout=300)
    errors = []
    for line in out.splitlines():
        m = TS_ERROR.match(line.strip())
        if m:
            errors.append({"file": m["file"], "line": int(m["line"]), "code": m["code"], "msg": m["msg"]})
    return rc, errors, out, secs


def py_compile_all(src, spec):
    """Every .py file of the repository compiles (nothing is executed and nothing is written)."""
    errors = []
    for p in sorted(src.rglob("*.py")):
        rel = p.relative_to(src)
        if rel.parts[0] == "grade":
            continue
        try:
            compile(p.read_bytes(), str(rel), "exec", dont_inherit=True)
        except SyntaxError as exc:
            errors.append({"file": str(rel), "line": exc.lineno or 0, "code": "SyntaxError", "msg": str(exc.msg)})
        except (ValueError, UnicodeDecodeError) as exc:
            errors.append({"file": str(rel), "line": 0, "code": type(exc).__name__, "msg": str(exc)[:200]})
    return (0 if not errors else 1), errors


def rules(src, spec):
    out_json = WORK / "rules.json"
    env = base_env()
    if spec["language"] == "typescript":
        env["NODE_PATH"] = LINT_NODE_MODULES
        cmd = ["node", str(TESTS / "rules.js"), str(src), "--code-dir", spec["code_dir"], "--hashes",
               str(TESTS / "hashes.json"), "--json", str(out_json)]
    else:
        cmd = [sys.executable, str(TESTS / "rules_py.py"), str(src), "--code-dir", spec["code_dir"], "--hashes",
               str(TESTS / "hashes.json"), "--json", str(out_json)]
    rc, out, secs = run(cmd, WORK, env=env, timeout=180, user=False)
    try:
        res = json.loads(out_json.read_text())
    except Exception:
        return None, out
    return res["violations"], out


# ---------------------------------------------------------------------------------------------- synthesis
def synth(src, spec, name):
    cfg = spec["configs"][name]
    out = WORK / "out" / name
    report_path = WORK / "out" / f"{name}.report.json"
    hspec = WORK / "out" / f"{name}.harness.json"
    hspec.write_text(json.dumps(harness_spec(spec)))
    nonce = secrets.token_hex(16)
    # /tests is unreadable for the unprivileged user: hand over a copy of this configuration only
    cfg_copy = WORK / "out" / f"{name}.config.json"
    shutil.copyfile(TESTS / cfg["file"], cfg_copy)
    for f in (cfg_copy, hspec):
        f.chmod(0o644)
    env = base_env()
    env.update({"GRADE_CONFIG": str(cfg_copy), "GRADE_SPEC": str(hspec),
                "GRADE_REPORT": str(report_path), "GRADE_NONCE": nonce})
    if spec["language"] == "typescript":
        app = f"node {spec.get('node_flags', '')} --import tsx grade/harness.ts".replace("  ", " ")
    else:
        app = f"{PY} grade/harness.py"
    cmd = [cdk_bin(), "synth", "--quiet", "--no-version-reporting", "--path-metadata", "false",
           "--asset-metadata", "false", "--no-lookups", "--no-notices", "-a", app, "-o", str(out)]
    rc, text, secs = run(cmd, src, env=env, timeout=SYNTH_TIMEOUT)
    report, problems = None, []
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text())
        except Exception as e:
            problems.append(f"unreadable structure report: {e}")
    if report is not None and report.get("nonce") != nonce:
        problems.append("the structure report does not carry this run's nonce")
        report = None
    if report is not None:
        if report.get("buildError"):
            problems.append("app construction failed: " + report["buildError"].splitlines()[-1][:300])
        problems += [f"harness: {p}" for p in report.get("problems", [])]
    ok = rc == 0 and report is not None and not problems and (out / "manifest.json").exists()
    if rc != 0:
        problems.append(f"cdk synth exited {rc}: {tail(text, 6)}")
    elif report is None and not problems:
        problems.append("no structure report was written")
    return {"ok": ok, "secs": secs, "out": out, "report": report, "problems": problems}


def resources_of(templates_dir):
    res = {}
    for stack, t in load_templates(str(templates_dir)).items():
        for lid, r in (t.get("Resources") or {}).items():
            if r.get("Type") != "AWS::CDK::Metadata":
                res[f"{stack}/{lid}"] = r.get("Type")
    return res


def deployment_keys(templates_dir):
    """stack/logicalId -> stack/Deployment:<its RestApiId> for every REST API deployment: tagging the API changes a
    deployment's logical ID (a hash of the API's content), so deployments are matched by the API they deploy"""
    out = {}
    for stack, t in load_templates(str(templates_dir)).items():
        for lid, r in (t.get("Resources") or {}).items():
            if r.get("Type") == "AWS::ApiGateway::Deployment":
                out[f"{stack}/{lid}"] = f"{stack}/Deployment:" + json.dumps((r.get("Properties") or {}).get("RestApiId"),
                                                                           sort_keys=True)
    return out


def rekey(d, canon):
    return {canon.get(k, k): v for k, v in d.items()} if canon else d


def remap_resources(v, canon):
    if not canon:
        return v
    if isinstance(v, dict):
        return {k: (canon.get(x, x) if k == "resource" and isinstance(x, str) else remap_resources(x, canon)) for k, x in v.items()}
    if isinstance(v, list):
        return [remap_resources(x, canon) for x in v]
    return v


def is_a(fqn, chain_of, want):
    """A construct whose class is `fqn` (jsii class chain `chain_of`, most derived first) is an instance of `want` or
    of a subclass of it (aws-cdk-lib's or the solver's own), as the statement allows."""
    return fqn == want or (want is not None and want in (chain_of or []))


def same_ident(have, want):
    """A public property's description (harness describe()) is the reference's: the same resources or construct paths,
    each held by an instance of the reference's class or of a subclass of it; mappings and sequences element-wise."""
    if isinstance(want, dict) and isinstance(have, dict) and "fqn" in want and ("resource" in want or "construct" in want):
        rest = lambda d: {k: v for k, v in d.items() if k not in ("fqn", "fqns")}  # noqa: E731
        return rest(have) == rest(want) and is_a(have.get("fqn"), have.get("fqns"), want.get("fqn"))
    if isinstance(want, dict) and isinstance(have, dict):
        return set(have) == set(want) and all(same_ident(have[k], want[k]) for k in want)
    if isinstance(want, list) and isinstance(have, list):
        return len(have) == len(want) and all(same_ident(h, w) for h, w in zip(have, want))
    return have == want


def provenance(result, exp):
    """Same construct classes and raw-override counts as the reference (the parent may be an instance of a subclass
    of the reference's parent class, as the statement allows), and report == templates."""
    probs = []
    report = result["report"]
    canon, ecanon = result.get("canon") or {}, result.get("exp_canon") or {}
    elements = rekey({f"{e['stack']}/{e['logicalId']}": e for e in report["elements"] if e.get("type")}, canon)
    templ = rekey(resources_of(result["out"]), canon)
    exp_elements = rekey(exp["elements"], ecanon)
    for key, typ in templ.items():
        e = elements.get(key)
        if e is None:
            probs.append(f"{key}: no construct of the app produces this resource")
            continue
        if e["type"] != typ:
            probs.append(f"{key}: construct type {e['type']} but template type {typ}")
        want = exp_elements.get(key)
        if want is not None:
            got = [e["type"], e["fqn"], e.get("parentFqn"), e.get("rawOverrides", 0)]
            if got[:2] != want[:2] or got[3] != want[3] or not is_a(got[2], e.get("parentFqns"), want[2]):
                probs.append(f"{key}: created by {got[1]} under {got[2]} with {got[3]} raw override(s); "
                             f"expected {want[1]} under {want[2]} with {want[3]}")
    for key in elements:
        if key not in templ:
            probs.append(f"{key}: in the construct tree but not in the templates")
    return probs


def owners(report):
    comp = {n["path"]: n["components"] for n in report["nodes"] if n.get("components")}
    out = {}
    for e in report["elements"]:
        if not e.get("type"):
            continue
        parts = e["path"].split("/")
        owner = None
        for i in range(len(parts) - 1, 0, -1):
            p = "/".join(parts[:i])
            if p in comp:
                owner = p
                break
        out[f"{e['stack']}/{e['logicalId']}"] = owner
    return out, comp


def layout(result, exp, cls):
    """Problems of component class `cls` in one configuration."""
    probs = []
    report = result["report"]
    nodes = {n["path"]: n for n in report["nodes"]}
    got_owner, comp = owners(report)
    got_owner = rekey(got_owner, result.get("canon") or {})
    exp_owners = rekey(exp["owners"], result.get("exp_canon") or {})
    want_inst = {p for p, c in exp["instances"].items() if c == cls}
    got_inst = {p for p, cs in comp.items() if cls in cs}
    for p in sorted(want_inst - got_inst):
        probs.append(f"{p}: no {cls} instance at this path" + ("" if p in nodes else " (no construct)"))
    for p in sorted(got_inst - want_inst):
        probs.append(f"{p}: unexpected {cls} instance")
    for p, fqn in exp["paths"].items():
        if any(p.startswith(i + "/") for i in want_inst):
            n = nodes.get(p)
            if n is None:
                probs.append(f"{p}: missing (expected a {fqn})")
            elif not is_a(n.get("fqn"), n.get("fqns"), fqn):
                probs.append(f"{p}: is a {n.get('fqn')}, expected a {fqn} (or a subclass)")
    for key, owner in exp_owners.items():
        if owner in want_inst and got_owner.get(key, "<missing>") != owner:
            probs.append(f"{key}: should be inside {owner}, found in {got_owner.get(key)}")
    for key, owner in got_owner.items():
        if owner in got_inst and exp_owners.get(key, "<none>") != owner:
            probs.append(f"{key}: inside {owner}, but it belongs to {exp_owners.get(key)}")
    return probs


def properties(result, exp, spec, cls):
    probs = []
    props = names(next(c.get("properties") for c in spec["components"] if c["class"] == cls))
    nodes = {n["path"]: n for n in result["report"]["nodes"]}
    for p, want in exp["properties"].items():
        if exp["instances"].get(p) != cls:
            continue
        have = (nodes.get(p) or {}).get("properties")
        if have is None or cls not in (nodes.get(p) or {}).get("components", []):
            probs.append(f"{p}: no {cls} instance")
            continue
        have = remap_resources(have, result.get("canon") or {})
        want = remap_resources(want, result.get("exp_canon") or {})
        for prop in props:
            if not same_ident(have.get(prop), want.get(prop)):
                probs.append(f"{p}.{prop}: {json.dumps(have.get(prop))[:160]} != expected {json.dumps(want.get(prop))[:160]}")
    return probs


def stack_properties(result, exp, spec, cls):
    """Problems of the public properties of stack class `cls` in one configuration (identity, as for components)."""
    probs = []
    props = names(next(s.get("properties") for s in spec["stacks"] if s["class"] == cls))
    nodes = {n["path"]: n for n in result["report"]["nodes"]}
    for p, c in (exp.get("stacks") or {}).items():
        if c != cls:
            continue
        node = nodes.get(p) or {}
        have = node.get("stackProperties")
        if have is None or cls not in node.get("stackClasses", []):
            probs.append(f"{p}: no {cls} instance")
            continue
        want = remap_resources((exp.get("stack_properties") or {}).get(p) or {}, result.get("exp_canon") or {})
        have = remap_resources(have, result.get("canon") or {})
        for prop in props:
            if not same_ident(have.get(prop), want.get(prop)):
                probs.append(f"{p}.{prop}: {json.dumps(have.get(prop))[:160]} != expected {json.dumps(want.get(prop))[:160]}")
    return probs


def interface_errors(spec, errors):
    """Map tsc errors in grade/interface-check.ts to the components (by the generator's line map)."""
    try:
        owner_of_line = {int(k): v for k, v in json.loads((WORK / "iface-owner.json").read_text()).items()}
    except (OSError, ValueError):
        owner_of_line = {}
    by_comp = {}
    for e in errors:
        if not e["file"].replace("\\", "/").endswith("interface-check.ts"):
            continue
        comp = owner_of_line.get(e["line"], "*")
        by_comp.setdefault(comp, []).append(f"line {e['line']}: {e['code']} {e['msg'][:200]}")
    return by_comp


def diff_lines(rep):
    out = [f"missing stack {s}" for s in rep["missing_stacks"]] + [f"extra stack {s}" for s in rep["extra_stacks"]]
    for st_name, st in rep["stacks"].items():
        out += [f"{st_name}/{lid}: {', '.join(p[:3])}" for lid, p in list(st["modified"].items())[:8]]
        out += [f"{st_name}/{lid}: missing" for lid in st["missing"][:8]]
        out += [f"{st_name}/{lid}: added" for lid in st["added"][:8]]
        out += [f"{st_name} {sec}: {', '.join(p[:3])}" for sec, p in st["sections"].items()]
    return out


def diff_keys(rep):
    """Every difference as an entry "<key>|<what>": <key> is stack/logicalId (or stack/#<Section>/<id>, or stack/*), and
    <what> is "missing", "added", "stack" or the template path that differs (/Properties/BatchSize ...)."""
    out = {f"{s}/*|stack" for s in rep["missing_stacks"] + rep["extra_stacks"]}
    for st_name, st in rep["stacks"].items():
        out |= {f"{st_name}/{lid}|missing" for lid in st["missing"]}
        out |= {f"{st_name}/{lid}|added" for lid in st["added"]}
        for lid, paths in st["modified"].items():
            out |= {f"{st_name}/{lid}|{p}" for p in paths}
        for sec, paths in st["sections"].items():
            out |= {f"{st_name}/#{sec}/{(p.split('/') + ['', ''])[1].split('[')[0]}|{p}" for p in paths}
    return out


def keyed_problems(spec_keys, results, names):
    """Problems of one regression-repair check: its entries (per configuration, recorded at build: what the regression or
    the feature changes there, as diff_keys entries; a bare key means any difference at that resource) that the
    submission still has. A resource the submission lacks or adds counts against every entry of that resource."""
    probs = []
    for n in names:
        want = set((spec_keys or {}).get(n) or [])
        if not want:
            continue
        r = results[n]
        if not r["ok"]:
            probs.append(f"{n}: did not synthesize")
            continue
        got = r.get("diff_keys", set())
        got_keys = {e.split("|", 1)[0] for e in got}
        structural = {e.split("|", 1)[0] for e in got if e.rsplit("|", 1)[-1] in ("missing", "added", "stack")}
        bad = []
        for w in sorted(want):
            k, sep, _ = w.partition("|")
            if (not sep and k in got_keys) or (sep and (w in got or k in structural)):
                bad.append(w)
        if bad:
            probs.append(f"{n}: " + ", ".join(bad[:6]) + (f" (+{len(bad) - 6})" if len(bad) > 6 else ""))
    return probs


# ---------------------------------------------------------------------------------------------- main flow
def grade():
    spec = json.loads((TESTS / "spec.json").read_text())
    t0 = time.time()
    src = copy_submission(spec)
    gates, checks, details = {}, {}, {}
    visible = [n for n, c in spec["configs"].items() if c.get("visible")]
    hidden = [n for n, c in spec["configs"].items() if not c.get("visible")]
    rr = spec.get("task_type") == "regression-repair"
    classes = [] if rr else [c["class"] for c in spec["components"]]
    stack_classes = [] if rr else [st["class"] for st in spec.get("stacks") or [] if st.get("properties")]
    ts = spec["language"] == "typescript"

    gates["integrity"] = not INTEGRITY
    details["integrity"] = list(INTEGRITY[:25])
    log(f"integrity: {'ok' if gates['integrity'] else 'FAILED'} ({len(INTEGRITY)} protected path(s) differ)")

    if ts:
        rc, errs, out, secs = tsc(src, "grade/tsconfig.grade.json")
    else:
        t1 = time.time()
        rc, errs = py_compile_all(src, spec)
        out, secs = "", round(time.time() - t1, 1)
    gates["build"] = rc == 0
    details["build"] = [f"{e['file']}:{e['line']} {e['code']} {e['msg'][:200]}" for e in errs[:15]] or ([tail(out)] if rc else [])
    log(f"build: {'ok' if gates['build'] else 'FAILED'} ({secs}s)")

    violations, out = rules(src, spec)
    gates["rules"] = violations == []
    details["rules"] = ([f"{v['file']}:{v['line']}: {v['rule']} {v['message']}" for v in violations[:25]]
                        if violations is not None else [f"rules checker failed: {tail(out)}"])
    log(f"rules: {'ok' if gates['rules'] else 'FAILED'} ({len(violations or [])} violations)")

    results = {}
    for name in visible + hidden:
        r = synth(src, spec, name)
        exp = spec["expect"][name]
        r["equal"] = None
        if r["ok"]:
            normalize = bool(spec.get("normalize_api_deployments"))
            if normalize:
                r["canon"] = deployment_keys(r["out"])
                r["exp_canon"] = deployment_keys(TESTS / "expected" / name)
            rep = compare(str(TESTS / "expected" / name), str(r["out"]), normalize_deployments=normalize,
                          soft_tag=spec.get("tag"))
            r["equal"] = rep["equal"]
            r["diff_keys"] = diff_keys(rep)
            r["diff"] = diff_lines(rep)
            r["provenance"] = provenance(r, exp)
            r["layout"] = {cls: layout(r, exp, cls) for cls in classes}
        log(f"synth {name}: {'ok' if r['ok'] else 'FAILED'} ({r['secs']}s)"
            + (f", templates {'equal' if r['equal'] else 'DIFFERENT'}" if r["ok"] else f": {r['problems'][:2]}"))
        results[name] = r

    gates["synth"] = all(results[n]["ok"] for n in visible)
    details["synth"] = [f"{n}: {p}" for n in visible for p in results[n]["problems"][:4]]
    gates["provenance"] = gates["synth"] and all(not results[n]["provenance"] for n in visible)
    details["provenance"] = [f"{n}: {p}" for n in visible if results[n]["ok"] for p in results[n]["provenance"][:10]]
    gates["templates"] = gates["synth"] and all(results[n]["equal"] for n in visible)
    details["templates"] = [f"{n}: {d}" for n in visible if results[n]["ok"] for d in results[n]["diff"][:15]]

    core = {}
    for cls in classes:
        probs = []
        for n in visible:
            if results[n]["ok"]:
                probs += [f"{n}: {p}" for p in results[n]["layout"][cls]]
            else:
                probs.append(f"{n}: did not synthesize")
        core[f"layout_{cls}"] = (not probs, probs)
    if rr:
        # regression-repair: one check per regression the task planted (its resources in every configuration where it
        # shows, visible or hidden) and one for the feature (the resources it adds or changes), besides the probes
        for reg in spec.get("regressions") or []:
            probs = keyed_problems(reg.get("keys"), results, visible + hidden)
            core[f"regression_{reg['id']}"] = (not probs, probs)
        probs = keyed_problems(spec.get("feature_keys"), results, visible + hidden)
        core["feature"] = (not probs, probs)
    for n in hidden:
        r = results[n]
        probs = [] if r["ok"] else [f"did not synthesize: {p}" for p in r["problems"][:3]]
        if r["ok"]:
            probs += [f"template: {d}" for d in r["diff"][:12]] if not r["equal"] else []
            probs += [f"provenance: {p}" for p in r["provenance"][:8]]
            probs += [f"layout {cls}: {p}" for cls in classes for p in r["layout"][cls][:4]]
        core[f"probe_{n}"] = (not probs, probs)

    if ts and not rr:
        rc, errs, out, secs = tsc(src, "grade/tsconfig.iface.json")
        iface_errs = interface_errors(spec, errs)
    elif ts:
        iface_errs = {}
    else:
        iface_errs = {}
        for n in visible:
            rep = results[n]["report"] if results[n]["ok"] else None
            for cls, probs in ((rep or {}).get("interface") or {}).items():
                for p in probs:
                    if p not in iface_errs.setdefault(cls, []):
                        iface_errs[cls].append(p)
    partial = {}
    for cls in classes:
        probs = list(iface_errs.get(cls, [])) + list(iface_errs.get("*", []))
        for n in visible:
            if results[n]["ok"]:
                probs += [f"{n}: {p}" for p in properties(results[n], spec["expect"][n], spec, cls)]
            else:
                probs.append(f"{n}: did not synthesize")
        partial[f"interface_{cls}"] = (not probs, probs)
    for cls in stack_classes:
        probs = list(iface_errs.get(cls, [])) + list(iface_errs.get("*", []))
        for n in visible:
            if results[n]["ok"]:
                probs += [f"{n}: {p}" for p in stack_properties(results[n], spec["expect"][n], spec, cls)]
            else:
                probs.append(f"{n}: did not synthesize")
        partial[f"interface_{cls}"] = (not probs, probs)

    # every interface is required: the interface checks are core like the layouts and the probes
    core.update(partial)
    for name, (ok, probs) in core.items():
        checks[name] = ok
        details[name] = probs[:20]
    passed = sum(1 for v in checks.values() if v)
    all_gates = all(gates.values())
    all_core = all(ok for ok, _ in core.values())
    reward = round(passed / len(checks), 4) if (all_gates and all_core) else 0.0

    log("GATES " + " ".join(f"{k}={'pass' if v else 'FAIL'}" for k, v in gates.items()))
    failed = [k for k, v in checks.items() if not v]
    log(f"CHECKS {passed}/{len(checks)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    for k in list(gates) + list(checks):
        if (k in gates and not gates[k]) or (k in checks and not checks[k]):
            for line in details.get(k, [])[:8]:
                log(f"  {k}: {line}")
    log(f"REWARD {reward} ({round(time.time() - t0, 1)}s)")
    return reward, gates, checks, details, set(core)


def short(lines, limit=300):
    text = "; ".join(str(x) for x in lines)
    return text[:limit - 3] + "..." if len(text) > limit else text


def main():
    VERIFIER.mkdir(parents=True, exist_ok=True)
    try:
        reward, gates, checks, details, core = grade()
    except Exception:
        traceback.print_exc()
        log("grader error: no reward written")
        sys.exit(2)
    metrics = {
        "reward": reward,
        "gates": {g: {"ok": bool(ok), "detail": "" if ok else short(details.get(g, [])), "skipped": False}
                  for g, ok in gates.items()},
        "checks": {c: {"ok": bool(ok), "detail": "" if ok else short(details.get(c, [])),
                       "core": c in core} for c, ok in checks.items()},
        "passed_checks": sum(1 for v in checks.values() if v), "total_checks": len(checks),
        "details": {k: v for k, v in details.items() if v},
    }
    (VERIFIER / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (VERIFIER / "reward.json").write_text(json.dumps({"reward": reward}))
    (VERIFIER / "reward.txt").write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
