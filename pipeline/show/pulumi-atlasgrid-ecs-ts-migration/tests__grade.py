#!/usr/bin/env python3
"""Family grader: "migrate a Terraform stack to Pulumi" (tf2pulumi) tasks, Python or TypeScript programs.

Driven entirely by tests/spec.json (+ tests/expected.json.gz, tests/state/*.json). Nothing here is task specific.

Grading model
  The solver's Pulumi project is previewed (never deployed) against the grader's own copy of the production Pulumi
  stack, fully offline, once per *case*:
    base            the production configuration against the production state             (gate)
    remapped_state  the production state with every cloud-generated ID/ARN/IP swapped     (gate)
    <probes>        other configuration values and/or a drifted state                     (checks, some core)
  For every case the grader collects, from `pulumi preview --json` and the engine's gRPC debug log:
    ops      the planned operation per URN (same/create/update/replace/delete/read/import)
    planned  the provider's planned state of every created/updated/replaced resource
    outputs  the stack outputs the program registered
    calls    every resource registration with its options, every invoke/read/call
  Gates (reward 0 when one fails): the submission stages (entry point present, size caps, every verifier-owned
  file it contains identical to the original, no file containing an identifier production generated);
  TypeScript programs
  type-check with the verifier-owned tsconfig.json; base and remapped_state plan nothing but `same` over exactly the
  stack's URNs, register no banned option and make no invoke/read/call, and export the expected outputs.
  A probe passes when ops, planned state and outputs equal the reference program's recording for that probe
  (`grade.py record` at build time), compared semantically (JSON documents parsed, IAM policies order-free, secrets
  unwrapped, unknowns handled directionally). reward = 0 if a gate or a core probe fails, else 1 only when every probe passes (binary).

Isolation
  The program is real code. It runs as `nobody` (setpriv, no new privileges, no capabilities, rlimits) with the
  passphrase, backend URL and debug-log path removed from its environment. Backends, logs, /tests and the submission
  copy are root-only (0700); the program sees only its own read-only project copy. No emulator, no network: provider
  calls go to a dead endpoint.

Outputs (in GRADER_LOGS, default /logs/verifier): reward.txt (the number), metrics.json ({"gates": {name: {ok,
detail, skipped}}, "checks": {name: {ok, detail}}, "passed_checks", "total_checks", ...}), grading.json (every
problem, numeric-free details).

Usage
  grade.py                       grade the submission (verifier entrypoint)
  grade.py record SRC_DIR        run the reference project through every case and write the expected recordings
  grade.py case SRC_DIR NAME     run one case and print its problems (debugging)

Build-time environment overrides: GRADER_TESTS (/tests), GRADER_WORK (/grade), GRADER_LOGS (/logs/verifier),
GRADER_EXPECTED_OUT (record: where expected.json.gz goes), GRADER_RECORD_DETAILS (record: a JSON file with the base
registrations), GRADER_PULUMI_HOME (overrides spec.pulumi_home), GRADER_SANDBOX=0 (no privilege drop: only for a
non-root build container, where the sandbox cannot be applied), GRADER_PARALLEL, GRADER_SUBMISSION.
"""
import concurrent.futures
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(os.environ.get("GRADER_TESTS", "/tests"))
WORK = Path(os.environ.get("GRADER_WORK", "/grade"))
LOGS = Path(os.environ.get("GRADER_LOGS", "/logs/verifier"))
SANDBOX = os.environ.get("GRADER_SANDBOX", "1") != "0"
UNKNOWN = "04da6b54-80e4-46f7-96ec-b56ff0331ba9"   # Pulumi's unknown-value sentinel (CLI 3.267.0)
SECRET_SIG = "4dabf18193072939515e22adb298388d"   # Pulumi's special-value signature key
SECRET_VAL = "1b47061264138c4ac30d75fd1eb44270"
UNK = "<unknown>"
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pulumi"}
MAX_FILES, MAX_BYTES = 2000, 20 * 1024 * 1024
NOBODY = 65534
T0 = time.time()
BANNED_OPTIONS = {          # RegisterResource request field -> statement wording (python, typescript)
    "protect": ("protect", "protect"), "ignoreChanges": ("ignore_changes", "ignoreChanges"),
    "retainOnDelete": ("retain_on_delete", "retainOnDelete"), "deletedWith": ("deleted_with", "deletedWith"),
    "importId": ("import_", "import"), "aliases": ("aliases", "aliases"), "aliasURNs": ("aliases", "aliases"),
    "replaceOnChanges": ("replace_on_changes", "replaceOnChanges"),
    "customTimeouts": ("custom_timeouts", "customTimeouts"), "transforms": ("transforms", "transforms"),
    "hooks": ("hooks", "hooks"), "remote": ("remote components", "remote components"),
    "providers": ("providers", "providers"), "provider": ("provider", "provider"),
    "replaceWith": ("replace_with", "replaceWith"),
}
BANNED_METHODS = {"Invoke": "provider functions (invokes)", "StreamInvoke": "provider functions (invokes)",
                  "Call": "component method calls", "ReadResource": "resource lookups (.get()) and stack references",
                  "RegisterStackTransform": "stack transforms", "RegisterStackInvokeTransform": "invoke transforms",
                  "RegisterResourceHook": "resource hooks", "RegisterPackage": "parameterized packages"}


def log(msg):
    print(msg, flush=True)


def elapsed():
    return time.time() - T0


# ---------------------------------------------------------------------------------------------------------- spec
def load_spec():
    spec = json.loads((TESTS / "spec.json").read_text())
    exp_path = TESTS / spec.get("expected_file", "expected.json.gz")
    expected = json.loads(gzip.decompress(exp_path.read_bytes())) if exp_path.exists() else {}
    return spec, expected


def is_ts(spec):
    return spec.get("language") == "typescript"


def word(spec, field):
    return BANNED_OPTIONS[field][1 if is_ts(spec) else 0]


# ------------------------------------------------------------------------------------------------- submission copy
def pasted_regex(spec):
    """The production stack's generated identifiers (spec.pasted_tokens: the hex part of every prefixed ID, UUIDs, ARN
    suffixes, IAM unique IDs, the account ID, IPs, ELB DNS names), matched as whole tokens: not inside a longer run of
    letters or digits. AWS-published constants (arn:aws:iam::aws:policy/..., service principals) contain none."""
    tokens = sorted({t for t in spec.get("pasted_tokens") or [] if t}, key=len, reverse=True)
    if not tokens:
        return None
    return re.compile(r"(?<![0-9A-Za-z])(?:" + "|".join(re.escape(t) for t in tokens) + r")(?![0-9A-Za-z])")


def stage_submission(spec, src: Path, dest: Path):
    """Copy the solver's project (regular files only, size-capped), then overlay every verifier-owned file. The
    statement requires the verifier-owned files unchanged: a submitted copy that differs from the original fails the
    submission gate (a missing one is simply supplied)."""
    problems = []
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    owned = spec["owned_files"]
    pasted = pasted_regex(spec)
    count = size = 0
    if src.is_dir():
        for root, dirs, files in os.walk(src, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(root, d)))
            rel_root = os.path.relpath(root, src)
            for f in sorted(files):
                p = os.path.join(root, f)
                st = os.lstat(p)
                if not stat.S_ISREG(st.st_mode):
                    continue                      # symlinks, sockets, devices: dropped (the statement says so)
                rel = os.path.normpath(os.path.join(rel_root, f))
                if rel in owned:
                    with open(p, "rb") as fh:
                        if fh.read() != owned[rel].encode("utf-8"):
                            problems.append(f"{rel} differs from the original: the verifier-owned files must stay "
                                            "unchanged, byte for byte")
                    continue
                if "/" not in rel and rel.startswith("Pulumi.") and rel.endswith((".yaml", ".yml")):
                    continue                      # other stacks' configuration files: not part of the program
                count += 1
                size += st.st_size
                if count > MAX_FILES or size > MAX_BYTES:
                    problems.append(f"the project exceeds {MAX_FILES} files or {MAX_BYTES} bytes")
                    break
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, out)
                if pasted is not None:
                    hit = pasted.search(out.read_bytes().decode("utf-8", errors="ignore"))
                    if hit:
                        problems.append(f"{rel} contains {hit.group(0)!r}, an identifier production generated: the "
                                        "statement forbids pasting resource IDs, ARNs, the account ID, IP addresses "
                                        "or DNS names of existing resources, in whole or in part")
            if problems:
                break
    for rel, content in spec["owned_files"].items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content)
    entry = spec.get("entry_point", "__main__.py")
    if not (dest / entry).is_file():
        problems.append(f"the project has no {entry}")
    os.chmod(dest, 0o700)                         # staging copy: root only (each run gets its own readable copy)
    return problems


def world_readable(path: Path):
    for root, dirs, files in os.walk(path):
        os.chmod(root, 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)


# -------------------------------------------------------------------------------------------------------- running
STRIP = ("PULUMI_CONFIG_PASSPHRASE", "PULUMI_CONFIG_PASSPHRASE_FILE", "PULUMI_BACKEND_URL", "PULUMI_ACCESS_TOKEN",
         "PULUMI_DEBUG_GRPC", "PULUMI_HOME", "GRADER_TESTS", "GRADER_WORK", "GRADER_LOGS", "GRADER_PULUMI_HOME",
         "GRADER_EXPECTED_OUT", "GRADER_RECORD_DETAILS", "GRADER_SUBMISSION")


def sandbox_prefix():
    """The command prefix every solver process starts behind: no grader secrets in its environment, capped file sizes
    and descriptors, uid/gid nobody without capabilities. (No RLIMIT_NPROC: the kernel counts every nobody process on
    the host, so a cap fails at random on a busy machine; the verifier timeout bounds runaway programs.)"""
    strip = " ".join(f"-u {v}" for v in STRIP)
    lines = [f"exec env {strip} HOME=/nonexistent PYTHONDONTWRITEBYTECODE=1 \\",
             "  prlimit --fsize=67108864 --nofile=4096 --core=0 -- \\"]
    if SANDBOX:
        lines.append(f"  setpriv --reuid={NOBODY} --regid={NOBODY} --clear-groups --no-new-privs --inh-caps=-all "
                     "--bounding-set=-all \\")
    return "\n".join(lines)


def make_wrappers(spec):
    """Python: PULUMI_PYTHON_CMD points at a wrapper (the language host runs it as root; it drops to nobody before
    python starts). TypeScript: the nodejs language host runs `node` from PATH, so a root-owned directory holding a
    `node` wrapper goes first on the CLI's PATH."""
    bindir = WORK / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    os.chmod(bindir, 0o755)
    if is_ts(spec):
        target, name = spec.get("node", "/opt/node/bin/node"), "node"
    else:
        target, name = spec.get("python", "/usr/local/bin/python3"), "py-sandboxed"
    wrapper = bindir / name
    wrapper.write_text("#!/bin/sh\n# run the solver's program unprivileged (see grade.py: sandbox_prefix)\n"
                       f"{sandbox_prefix()}\n  {target} \"$@\"\n")
    os.chmod(wrapper, 0o755)
    return wrapper


def pulumi_home(spec):
    return os.environ.get("GRADER_PULUMI_HOME") or spec.get("pulumi_home", "/root/.pulumi")


def cli_env(spec, backend: Path, grpc_log: Path, wrapper: Path):
    path = "/opt/pulumi:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    env = {
        "PATH": path,
        "HOME": str(WORK / "home"),
        "USER": os.environ.get("USER") or "grader", "LOGNAME": os.environ.get("USER") or "grader",
        "PULUMI_HOME": pulumi_home(spec),
        "PULUMI_BACKEND_URL": f"file://{backend}",
        "PULUMI_CONFIG_PASSPHRASE": spec["passphrase"],
        "PULUMI_SKIP_UPDATE_CHECK": "true",
        "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
        "PULUMI_IGNORE_AMBIENT_PLUGINS": "true",
        "PULUMI_DEBUG_GRPC": str(grpc_log),
        "AWS_ENDPOINT_URL": "http://127.0.0.1:9",
        "AWS_ACCESS_KEY_ID": "offline", "AWS_SECRET_ACCESS_KEY": "offline", "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost", "no_grpc_proxy": "127.0.0.1,localhost",
        "LANG": "C.UTF-8",
    }
    if is_ts(spec):
        env["PATH"] = f"{wrapper.parent}:{path}"
        env["PULUMI_NODEJS_TRANSPILE_ONLY"] = "true"
    else:
        env["PULUMI_PYTHON_CMD"] = str(wrapper)
    return env


def stack_config_text(spec, overrides):
    """The verifier-owned stack config plus the case's values (project namespace), as JSON (valid YAML)."""
    cfg = dict(spec["stack_config"])
    for key, value in (overrides or {}).items():
        cfg[f"{spec['config_namespace']}:{key}"] = value
    doc = {"config": cfg}
    if spec.get("encryption_salt"):
        doc["encryptionsalt"] = spec["encryption_salt"]
    return json.dumps(doc, indent=1, sort_keys=False) + "\n"


def run(cmd, cwd, env, timeout):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=max(5, timeout))
        return p.returncode, p.stdout, p.stderr, time.time() - t
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return 124, out, err + f"\n[grader] timed out after {timeout:.0f}s", time.time() - t


def link_node_modules(spec, project: Path):
    if is_ts(spec):
        link = project / "node_modules"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(spec.get("node_modules", "/opt/pulumi-node/node_modules"))


import threading
_STATE_LOCK = threading.Lock()


def state_path(name):
    """tests/state/<name>, or its gzip (the assembled task ships the verifier's states compressed), unpacked once
    into the root-only work directory."""
    plain = TESTS / "state" / name
    if plain.exists():
        return plain
    packed = TESTS / "state" / (name + ".gz")
    out = WORK / "state" / name
    with _STATE_LOCK:
        if not out.exists() and packed.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(out.parent, 0o700)
            tmp = out.with_suffix(".tmp")
            tmp.write_bytes(gzip.decompress(packed.read_bytes()))
            tmp.replace(out)
    return out


def budget_left(spec):
    return spec.get("time_budget", 2700) - elapsed()


def run_case(spec, src: Path, case, wrapper):
    """Fresh backend + stack import of the case's state + one offline preview; returns the parsed result."""
    name = case["name"]
    root = WORK / "runs" / name
    res = {"name": name, "errors": []}
    left = budget_left(spec)
    if left < 60:
        res["errors"].append("not run: the grading time budget is used up (the program previews too slowly)")
        return res
    if root.exists():
        shutil.rmtree(root)
    project, backend, logs = root / "project", root / "backend", root / "logs"
    shutil.copytree(src, project, symlinks=False)
    (project / f"Pulumi.{spec['stack']}.yaml").write_text(stack_config_text(spec, case.get("config")))
    world_readable(project)
    link_node_modules(spec, project)
    for d in (backend, logs):
        d.mkdir(parents=True)
        os.chmod(d, 0o700)
    os.chmod(root, 0o711)
    grpc_log = logs / "grpc.jsonl"
    env = cli_env(spec, backend, grpc_log, wrapper)
    stack = spec["stack"]
    state_file = state_path(case.get("state", spec["state_file"]))
    quiet = dict(env)
    quiet.pop("PULUMI_DEBUG_GRPC")
    rc, out, err, _ = run(["pulumi", "stack", "init", stack, "--non-interactive"], project, quiet, 120)
    if rc != 0:
        res["errors"].append(f"stack init failed: {err.strip()[-400:]}")
        return res
    rc, out, err, _ = run(["pulumi", "stack", "import", "-s", stack, "--file", str(state_file)], project, quiet, 300)
    if rc != 0:
        res["errors"].append(f"stack import failed: {err.strip()[-400:]}")
        return res
    if grpc_log.exists():
        grpc_log.unlink()
    timeout = min(spec.get("preview_timeout", 900), budget_left(spec) - 30)
    rc, out, err, dt = run(["pulumi", "preview", "--json", "--show-sames", "--refresh=false", "--non-interactive",
                            "--suppress-progress", "-s", stack], project, env, timeout)
    res["seconds"] = round(dt, 1)
    (logs / "preview.json").write_text(out)
    (logs / "preview.err").write_text(err)
    try:
        doc = json.loads(out)
    except ValueError:
        res["errors"].append(f"preview produced no JSON (rc={rc}): {(err or out).strip()[-1500:]}")
        return res
    diags = [d for d in doc.get("diagnostics", []) if d.get("severity") == "error"]
    if rc != 0 or diags:
        msgs = " | ".join(clip(d.get("message", "").strip()) for d in diags[:4])
        res["errors"].append(f"preview failed (rc={rc}): {msgs or err.strip()[-800:]}")
    res.update(parse_preview(doc))
    res.update(parse_grpc(spec, grpc_log))
    return res


def typecheck(spec, src: Path, wrapper):
    """TypeScript: `tsc --noEmit -p .` with the verifier-owned tsconfig.json, run like the program (unprivileged)."""
    if not is_ts(spec):
        return []
    root = WORK / "runs" / "_typecheck"
    if root.exists():
        shutil.rmtree(root)
    project = root / "project"
    shutil.copytree(src, project, symlinks=False)
    world_readable(project)
    link_node_modules(spec, project)
    os.chmod(root, 0o711)
    tsc = spec.get("tsc", "/opt/pulumi-node/node_modules/typescript/bin/tsc")
    env = {"PATH": f"{wrapper.parent}:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
    rc, out, err, _ = run([str(wrapper), tsc, "--noEmit", "-p", "."], project, env,
                          min(600, max(60, budget_left(spec) - 600)))
    if rc == 0:
        return []
    lines = [l for l in (out + err).splitlines() if l.strip()]
    errs = [l for l in lines if "error TS" in l] or lines
    return [f"tsc --noEmit reports {len([l for l in lines if 'error TS' in l]) or 'errors'}: "
            + " | ".join(l.strip()[:220] for l in errs[:6])]


def clip(msg, head=400, tail=900):
    """An error message's head and tail (a Python traceback ends with the exception, a Node error starts with it)."""
    return msg if len(msg) <= head + tail else msg[:head] + " [...] " + msg[-tail:]


def normalize_op(op):
    return {"create-replacement": "replace", "delete-replaced": "replace", "replace": "replace",
            "discard": "delete", "discard-replaced": "replace"}.get(op, op)


def parse_preview(doc):
    ops = {}
    for s in doc.get("steps", []):
        urn = s.get("urn") or (s.get("oldState") or {}).get("urn")
        op = normalize_op(s.get("op"))
        if urn in ops and ops[urn] == "replace":
            continue
        ops[urn] = op
    return {"ops": ops}


def parse_grpc(spec, path: Path):
    """Completed gRPC calls: registrations (+ options), banned calls, planned states, stack outputs."""
    regs, banned, planned, outputs = [], [], {}, None
    stack_urn_suffix = f"pulumi:pulumi:Stack::{spec['project']}-{spec['stack']}"
    if not path.exists():
        return {"registrations": regs, "banned_calls": ["no gRPC log was written"], "planned": planned,
                "outputs": outputs}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if "response" not in entry and "errors" not in entry:
                continue                                  # call-start entry; the completed one follows
            service = entry.get("method", "")
            method = service.rsplit("/", 1)[-1]
            req = entry.get("request") or {}
            if "ResourceMonitor" in service:
                if method == "RegisterResource":
                    regs.append({**req, "_urn": (entry.get("response") or {}).get("urn")})
                elif method in BANNED_METHODS:
                    what = req.get("tok") or req.get("type") or req.get("name") or ""
                    banned.append(f"{BANNED_METHODS[method]}: {method} {what}".strip())
                elif method == "RegisterResourceOutputs" and str(req.get("urn", "")).endswith(stack_urn_suffix):
                    outputs = req.get("outputs") or {}
            elif "ResourceProvider" in service and method in ("Create", "Update") and req.get("preview"):
                planned[req.get("urn")] = (entry.get("response") or {}).get("properties")
    return {"registrations": regs, "banned_calls": banned, "planned": planned, "outputs": outputs}


# ------------------------------------------------------------------------------------------------- normalization
def iam_canon(doc):
    def listify(v):
        if isinstance(v, list):
            return sorted(json.dumps(x, sort_keys=True) if not isinstance(x, str) else x for x in v)
        return [v] if not isinstance(v, dict) else v

    stmts = doc.get("Statement")
    stmts = stmts if isinstance(stmts, list) else [stmts]
    out = []
    for s in stmts:
        if not isinstance(s, dict):
            out.append(s)
            continue
        c = {}
        for k, v in s.items():
            if k in ("Action", "NotAction", "Resource", "NotResource"):
                c[k] = listify(v)
            elif k in ("Principal", "NotPrincipal") and isinstance(v, dict):
                c[k] = {pk: listify(pv) for pk, pv in v.items()}
            elif k == "Condition" and isinstance(v, dict):
                c[k] = {op: {ck: listify(cv) for ck, cv in (body or {}).items()} for op, body in v.items()}
            else:
                c[k] = v
        out.append(c)
    canon_doc = {k: v for k, v in doc.items() if k != "Statement"}
    canon_doc["Statement"] = sorted(out, key=lambda x: json.dumps(x, sort_keys=True))
    return {"<iam-policy>": canon_doc}


def canon(v):
    """Semantic normal form used on both sides of every comparison."""
    if isinstance(v, dict):
        if v.get(SECRET_SIG) == SECRET_VAL and "value" in v:
            return canon(v["value"])
        if v.get(SECRET_SIG) == SECRET_VAL and "plaintext" in v:    # a state export made with --show-secrets
            try:
                return canon(json.loads(v["plaintext"]))
            except ValueError:
                return canon(v["plaintext"])
        if SECRET_SIG in v:                               # assets/archives/resource refs: keep a stable digest
            return {"<special>": hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:16]}
        return {k: canon(x) for k, x in sorted(v.items()) if k not in ("__meta", "__defaults")}
    if isinstance(v, list):
        return [canon(x) for x in v]
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        if v == UNKNOWN:
            return UNK
        s = v.strip()
        if s[:1] in ("{", "[") and s[-1:] in ("}", "]"):
            try:
                doc = json.loads(s)
            except ValueError:
                return v
            if isinstance(doc, dict) and "Statement" in doc:
                return iam_canon(canon(doc))
            return {"<json>": canon(doc)}
    return v


def has_unknown(v):
    if v == UNK:
        return True
    if isinstance(v, dict):
        return any(has_unknown(x) for x in v.values())
    if isinstance(v, list):
        return any(has_unknown(x) for x in v)
    return False


def is_empty(v):
    return v is None or v == "" or v == [] or v == {}


def diff_values(ref, got, path="", out=None, limit=12):
    """Differences between the reference's value and the solver's. An unknown on one side matches a value that is
    itself (partly) unknown on the other side - two ways of writing the same dependency - but never a known value.
    Empty values (null, "", [], {}) are equivalent: setting an argument to empty is the same as leaving it unset."""
    out = [] if out is None else out
    if len(out) >= limit or (is_empty(ref) and is_empty(got)):
        return out
    if ref == UNK or got == UNK:
        if ref == got or (ref == UNK and has_unknown(got)) or (got == UNK and has_unknown(ref)):
            return out
        out.append((path or ".", ref, got))
        return out
    if isinstance(ref, dict) and isinstance(got, dict):
        for k in sorted(set(ref) | set(got)):
            diff_values(ref.get(k), got.get(k), f"{path}.{k}" if path else k, out, limit)
        return out
    if isinstance(ref, list) and isinstance(got, list) and len(ref) == len(got):
        for i, (a, b) in enumerate(zip(ref, got)):
            diff_values(a, b, f"{path}[{i}]", out, limit)
        return out
    if ref != got:
        out.append((path or ".", ref, got))
    return out


def short(v, n=160):
    s = json.dumps(v, sort_keys=True) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "..."


def urn_label(urn):
    head, _, name = str(urn).rpartition("::")
    return f"{head.rsplit('::', 1)[-1].split('$')[-1]}::{name}"


# --------------------------------------------------------------------------------------------------- comparisons
def alias_key(a):
    return json.dumps(a, sort_keys=True)


def sdk_aliases(res):
    """Aliases present on the reference's registrations: the type aliases the aws SDK itself adds for renamed resource
    types (e.g. aws:lb/listener:Listener <- aws:elasticloadbalancingv2/listener:Listener). Anything else is the user's."""
    out = {}
    for r in res.get("registrations", []):
        for field in ("aliases", "aliasURNs"):
            for a in r.get(field) or []:
                out.setdefault(r.get("type"), set()).add(alias_key(a))
    return {t: sorted(v) for t, v in out.items()}


def registration_problems(spec, res, allowed_aliases=None):
    problems = list(res.get("banned_calls", []))
    default_prefix = f"urn:pulumi:{spec['stack']}::{spec['project']}::pulumi:providers:aws::default"
    allowed_aliases = allowed_aliases or {}
    for r in res.get("registrations", []):
        label = f"{r.get('type')}::{r.get('name')}"
        if str(r.get("type", "")).startswith("pulumi:providers:"):
            problems.append(f"explicit provider resource {label}")
        for field in BANNED_OPTIONS:
            v = r.get(field)
            if v in (None, False, "", [], {}, "0", 0):
                continue
            if field == "provider" and str(v).startswith(default_prefix):
                continue
            if field == "providers" and isinstance(v, dict) and all(str(x).startswith(default_prefix)
                                                                    for x in v.values()):
                continue
            if field in ("aliases", "aliasURNs") and isinstance(v, list) and \
                    all(alias_key(a) in allowed_aliases.get(r.get("type"), ()) for a in v):
                continue
            if field == "customTimeouts" and isinstance(v, dict) and not any(v.values()):
                continue
            problems.append(f"{label}: the resource option {word(spec, field)} is not allowed")
    return sorted(set(problems))


def summarize(res):
    keep = {"ops": {u: o for u, o in (res.get("ops") or {}).items() if o != "same"},
            "planned": {u: canon(p) for u, p in (res.get("planned") or {}).items()},
            "outputs": canon(res.get("outputs"))}
    return keep


def compare_case(exp, res):
    """Problems of a solver run against the recorded reference run of the same case (empty list = pass)."""
    problems = []
    got = summarize(res)
    eo, go = exp["ops"], got["ops"]
    for urn in sorted(set(eo) | set(go)):
        if eo.get(urn, "same") != go.get(urn, "same"):
            problems.append(f"{urn_label(urn)}: planned {go.get(urn, 'same')}, expected {eo.get(urn, 'same')}")
    for urn in sorted(set(exp["planned"]) & set(got["planned"])):
        if eo.get(urn) != go.get(urn):
            continue
        for path, a, b in diff_values(exp["planned"][urn], got["planned"][urn], limit=4):
            problems.append(f"{urn_label(urn)}: {path} = {short(b)}, expected {short(a)}")
    for path, a, b in diff_values(exp["outputs"], got["outputs"], limit=8):
        problems.append(f"stack output {path} = {short(b)}, expected {short(a)}")
    return problems


def gate_base(spec, exp, res, label, allowed_aliases=None):
    problems = list(res.get("errors", []))
    if problems:
        return problems
    urns = set(res["ops"])
    want = set(spec["urns"])
    for urn in sorted(want - urns):
        problems.append(f"{urn_label(urn)} is in the stack but the program does not declare it")
    for urn, op in sorted(res["ops"].items()):
        if op != "same":
            problems.append(f"{urn_label(urn)}: planned {op}; {label} must plan no changes")
    problems += registration_problems(spec, res, allowed_aliases)
    for path, a, b in diff_values(exp["outputs"], canon(res.get("outputs")), limit=8):
        problems.append(f"stack output {path} = {short(b)}, expected {short(a)}")
    return problems


# --------------------------------------------------------------------------------------------------------- driver
def prepare():
    WORK.mkdir(parents=True, exist_ok=True)
    os.chmod(WORK, 0o711)
    (WORK / "home").mkdir(exist_ok=True)
    os.chmod(WORK / "home", 0o700)
    (WORK / "runs").mkdir(exist_ok=True)
    os.chmod(WORK / "runs", 0o711)


def all_cases(spec):
    return [{"name": "base", "gate": True}, {"name": "remapped_state", "gate": True, "state": spec["remapped_state"]}] \
        + spec["probes"]


def run_cases(spec, src, cases, wrapper):
    results = {}
    workers = int(os.environ.get("GRADER_PARALLEL") or spec.get("parallel", 3))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(run_case, spec, src, c, wrapper): c["name"] for c in cases}
        for f in concurrent.futures.as_completed(futs):
            results[futs[f]] = f.result()
    return results


def cmd_record(src_dir):
    """Build time: run the reference project through every case; write the expected recordings."""
    spec, _ = load_spec()
    prepare()
    wrapper = make_wrappers(spec)
    src = WORK / "src"
    problems = stage_submission(spec, Path(src_dir), src)
    if problems:
        sys.exit(f"reference project rejected: {problems}")
    bad = typecheck(spec, src, wrapper)
    results = run_cases(spec, src, all_cases(spec), wrapper)
    aliases = sdk_aliases(results["base"])
    expected = {"_meta": {"sdk_aliases": aliases}}
    for c in all_cases(spec):
        r = results[c["name"]]
        if r.get("errors"):
            bad.append(f"{c['name']}: {r['errors']}")
        regs = registration_problems(spec, r, aliases)
        if regs:
            bad.append(f"{c['name']}: {regs[:3]}")
        expected[c["name"]] = summarize(r)
        log(f"recorded {c['name']:<26} {r.get('seconds', '?')}s  {len(expected[c['name']]['ops'])} non-same steps")
    for g in ("base", "remapped_state"):
        if expected[g]["ops"]:
            bad.append(f"{g}: the reference plans changes {list(expected[g]['ops'].items())[:5]}")
    for p in spec["probes"]:
        if not expected[p["name"]]["ops"]:
            bad.append(f"probe {p['name']}: the reference plans no change, so the probe tests nothing")
    if set(results["base"].get("ops") or {}) != set(spec["urns"]):
        missing = sorted(set(spec["urns"]) - set(results["base"].get("ops") or {}))[:5]
        extra = sorted(set(results["base"].get("ops") or {}) - set(spec["urns"]))[:5]
        bad.append(f"the reference's URNs differ from the stack's (missing {missing}, extra {extra})")
    details = os.environ.get("GRADER_RECORD_DETAILS")
    if details:
        changed = {name: {u for u, o in (r.get("ops") or {}).items() if o != "same"} for name, r in results.items()}
        Path(details).write_text(json.dumps({
            "registrations": results["base"].get("registrations", []),
            "outputs": results["base"].get("outputs"),
            "case_inputs": {name: {reg["_urn"]: reg.get("object") for reg in r.get("registrations", [])
                                   if reg.get("_urn") in changed[name] and reg.get("custom")}
                            for name, r in results.items() if name not in ("base", "remapped_state")},
            "seconds": {k: v.get("seconds") for k, v in results.items()}}, sort_keys=True))
    if bad:
        sys.exit("record failed:\n  " + "\n  ".join(str(b)[:1500] for b in bad))
    out = Path(os.environ.get("GRADER_EXPECTED_OUT") or TESTS / spec.get("expected_file", "expected.json.gz"))
    out.write_bytes(gzip.compress(json.dumps(expected, sort_keys=True).encode(), mtime=0))
    log(f"wrote {out} ({out.stat().st_size} bytes)")


def cmd_case(src_dir, name):
    spec, expected = load_spec()
    prepare()
    wrapper = make_wrappers(spec)
    src = WORK / "src"
    stage_submission(spec, Path(src_dir), src)
    case = next(c for c in all_cases(spec) if c["name"] == name)
    r = run_case(spec, src, case, wrapper)
    log(json.dumps({k: r.get(k) for k in ("errors", "seconds", "banned_calls")}, indent=1))
    if name in expected:
        aliases = expected.get("_meta", {}).get("sdk_aliases", {})
        problems = (gate_base(spec, expected[name], r, name, aliases) if name in ("base", "remapped_state")
                    else compare_case(expected[name], r))
        for p in problems[:60]:
            log("  " + p)


def write_results(spec, reward, gates, checks, core_failed, note):
    """reward.txt (number), metrics.json (the shape the pipeline reads), grading.json (every problem)."""
    LOGS.mkdir(parents=True, exist_ok=True)
    total = len(spec["probes"])
    passed = sum(1 for c in checks.values() if c["ok"])
    metrics = {
        "reward": reward,
        "gates": {g: {"ok": v["ok"], "detail": v["detail"][:300], "skipped": v["skipped"]} for g, v in gates.items()},
        "checks": {c: {"ok": v["ok"], "detail": v["detail"][:300], "core": v["core"]} for c, v in checks.items()},
        "passed_checks": passed, "total_checks": total, "core_failed": core_failed,
        "gates_passed": all(v["ok"] for v in gates.values()), "note": note,
        "language": spec.get("language", "python"), "seconds": round(elapsed(), 1),
    }
    grading = {"reward": reward, "note": note, "gates": {g: v["problems"] for g, v in gates.items()},
               "checks": {c: v["problems"] for c, v in checks.items()}, "core_failed": core_failed}
    (LOGS / "grading.json").write_text(json.dumps(grading, indent=1, sort_keys=True))
    (LOGS / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True))
    (LOGS / "reward.txt").write_text(f"{round(float(reward), 4)}\n")
    log(f"[grade] GATES {sum(1 for v in gates.values() if v['ok'])}/{len(gates)} passed"
        + "".join(f" {g}={'ok' if v['ok'] else 'skipped' if v['skipped'] else 'FAIL'}" for g, v in gates.items()))
    log(f"[grade] CHECKS {passed}/{total} passed" + (f"; core failed: {', '.join(core_failed)}" if core_failed else ""))
    log(f"[grade] REWARD {round(float(reward), 4)} ({note})")


def gate_entry(problems, skipped=False):
    if skipped:
        return {"ok": False, "skipped": True, "detail": "not run: an earlier gate failed", "problems": []}
    return {"ok": not problems, "skipped": False, "detail": "; ".join(problems)[:300], "problems": problems[:40]}


def cmd_grade():
    spec, expected = load_spec()
    prepare()
    wrapper = make_wrappers(spec)
    src = WORK / "src"
    gate_names = ["submission"] + (["typecheck"] if is_ts(spec) else []) + ["base", "remapped_state"]
    gates = {}
    checks = {p["name"]: {"ok": False, "core": bool(p.get("core")), "detail": "not graded: a gate failed",
                          "problems": []} for p in spec["probes"]}

    def stop(failed, note):
        for g in gate_names:
            if g not in gates:
                gates[g] = gate_entry([], skipped=True)
        log(f"reward 0.0 ({note})")
        write_results(spec, 0.0, {g: gates[g] for g in gate_names}, checks, [], note)

    def report(g, title, problems, seconds=None):
        gates[g] = gate_entry(problems)
        log(f"GATE {g} ({title}): {'PASS' if not problems else 'FAIL'}" + (f" [{seconds}s]" if seconds else ""))
        for p in problems[:25]:
            log("  " + p)
        return not problems

    sub = Path(os.environ.get("GRADER_SUBMISSION") or spec["submission_dir"])
    if not report("submission", "the project stages", stage_submission(spec, sub, src)):
        return stop("submission", "a gate failed: submission")
    if is_ts(spec) and not report("typecheck", "tsc --noEmit with the owned tsconfig.json", typecheck(spec, src, wrapper)):
        return stop("typecheck", "a gate failed: typecheck")
    aliases = expected.get("_meta", {}).get("sdk_aliases", {})
    base = run_case(spec, src, {"name": "base"}, wrapper)
    if not report("base", "no changes against production, structure, options, outputs",
                  gate_base(spec, expected["base"], base, "the production configuration", aliases),
                  base.get("seconds")):
        return stop("base", "a gate failed: base")
    cases = [c for c in all_cases(spec) if c["name"] != "base"]
    results = run_cases(spec, src, cases, wrapper)
    remap = results.pop("remapped_state")
    remap_ok = report("remapped_state", "every generated ID/ARN/IP swapped",
                      gate_base(spec, expected["remapped_state"], remap, "the remapped production state", aliases),
                      remap.get("seconds"))
    core_failed = []
    for probe in spec["probes"]:
        r = results[probe["name"]]
        probs = list(r.get("errors", [])) + registration_problems(spec, r, aliases)
        if not probs:
            probs = compare_case(expected[probe["name"]], r)
        ok = not probs
        checks[probe["name"]] = {"ok": ok, "core": bool(probe.get("core")), "detail": "; ".join(probs)[:300],
                                 "problems": probs[:40]}
        if not ok and probe.get("core"):
            core_failed.append(probe["name"])
        log(f"CHECK {probe['name']:<26} {'PASS' if ok else 'FAIL'}{' (core)' if probe.get('core') else ''}"
            f" [{r.get('seconds', '?')}s]  {probe.get('title', '')}")
        for p in probs[:12]:
            log("    " + p)
    passed = sum(1 for c in checks.values() if c["ok"])
    if not remap_ok:
        reward, note = 0.0, "a gate failed: remapped_state"
    elif core_failed:
        reward, note = 0.0, f"core checks failed: {', '.join(core_failed)}"
    else:
        reward, note = (1.0 if passed == len(spec["probes"]) else 0.0), f"{passed}/{len(spec['probes'])} checks (binary: every check must pass)"
    log(f"reward {round(reward, 4)} ({note})")
    write_results(spec, reward, {g: gates[g] for g in gate_names}, checks, core_failed, note)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        cmd_record(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "case":
        cmd_case(sys.argv[2], sys.argv[3])
    else:
        cmd_grade()


if __name__ == "__main__":
    main()
