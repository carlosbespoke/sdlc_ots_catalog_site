#!/usr/bin/env python3
"""Family grader: Terraform policy remediation (separate verifier container, offline). Stdlib only.

The solver gets a production Terraform stack, its recorded production state and the team's CI policy pack (OPA/Rego,
evaluated by conftest on the plan JSON). The stack violates the pack; the solver must make every policy pass by
updating existing resources in place and adding only the resource types the task allows, keeping the plan otherwise
minimal and the fixes general. One grader serves every task of the family; each task ships /tests/spec.json.

Nothing the solver ran or saved decides the grade. The artifact (spec artifact_dir, default /workspace/infra) is copied
to a scratch directory without state files, plan files, .terraform, .git, symlinks or the lock file; terraform runs
offline (dead proxy), as an unprivileged user, with the verifier's own lock file, against the verifier's own pristine
state (passed with -state, outside the configuration directory). conftest runs from a clean directory with the
verifier's own copy of the policy pack, every namespace, no configuration file.

Gates (any failure -> reward 0):
  static     protected files and the policy pack are byte-identical to the originals; no banned files (conftest
             configuration), no override or .tf.json files, no lifecycle ignore_changes/replace_triggered_by, no
             provisioners, no backend/cloud, provider (outside providers.tf), import, removed or moved blocks, no
             banned data sources
  terraform  offline init + validate + `plan -refresh=false` against the pristine state
  safety     every instance in the pristine state is still managed at its address and planned as no-op or update
             (no delete, replace, forget or move)
  creates    every planned create has a type the task allows
  minimal    every update changes only the arguments the task allows for its type (tags only for the allowed tag
             keys); the declared variables keep their values
  policies   the verifier's copy of the policy pack passes on the plan (conftest, zero failures)
Checks (spec "probes"): each probe re-plans with a -var-file against a probe state (default: the pristine state) and
must pass safety, creates, minimal (variables excepted) and policies again, plus its own expectations. A probe that
removes collection keys lists in `allowed_destroys` the recorded instances today's configuration destroys for that
change: exactly those must be destroyed, nothing else. `allowed_changes` ({address: [arguments]}) are the in-place
updates today's configuration itself makes for the probe's change; they are allowed in that probe on top of the
table. With scoring.partial_credit false (the default) every check is required: reward 1 only when all gates and
checks pass.
Input space (spec "input_space"): one input is planned at every value of its declared valid space (each family with
its sizes; a migrated family maps to its target family), a few plans at a time, with only the resource it drives
targeted (plus what that resource depends on). Each plan must succeed, keep that resource in place (no replace,
delete, forget or move anywhere in the plan), change only the allowed arguments, give the resource the expected value
at `path` and pass the pack's rules on it (spec namespaces). One check covers every value: any value the configuration
maps wrongly fails it, so no table short of the rule itself passes.
Fresh-key probes (spec "generated_collection_probes"): a shipped collection_add probe with its added key renamed, in
the var file and everywhere in the pre-deployed state, to a key no shipped probe or default uses, picked by a digest
of the submitted .tf files (the same submission always gets the same key), and the entry's values redrawn; graded
like that probe, with its expectations, for every key.

Outputs in /logs/verifier: reward.txt (the number), metrics.json ({"gates", "checks", "passed_checks",
"total_checks", ...}), grading.json (everything, for people). Never a reward.json: Horizon reads it as numbers only.
"""
import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TESTS = Path(os.environ.get("TESTS_DIR", "/tests"))
VERIFIER = Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
RUN_AS = os.environ.get("GRADER_RUN_AS", "nobody")
TF_CLI_CONFIG = os.environ.get("TF_CLI_CONFIG_FILE", "/etc/terraformrc")
PROXY = os.environ.get("GRADER_PROXY", "http://127.0.0.1:9")
# authoring only (iacctl verify): stop at the first failed gate instead of grading every probe
FAST = os.environ.get("GRADER_STOP_AFTER_FAILED_GATE") == "1"

SKIP_DIRS = {".terraform", ".git", "terraform.tfstate.d"}
SKIP_FILE = re.compile(r"(\.tfstate(\..*)?|\.tfplan|^\.terraform\.lock\.hcl|^\.terraform\.tfstate\.lock\.info)$")
OVERRIDE = re.compile(r"^(.+_)?override\.tf(\.json)?$")
BANNED_LIFECYCLE = ("ignore_changes", "replace_triggered_by")
BANNED_DATA = {"external", "terraform_remote_state", "http"}
BANNED_TOP = ("import", "removed", "moved")
GATES = ("static", "terraform", "safety", "creates", "minimal", "policies")
RULE_ID = re.compile(r"^([A-Z][A-Z0-9]*-[0-9]{3})\b")
LETTERS = "abcdefghijklmnopqrstuvwxyz"
SLUG_CHARS = LETTERS + "0123456789"
BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}")


def log(msg):
    print(f"[grade] {printable(msg)}", flush=True)


def printable(text):
    """text that prints and is stored as JSON in any locale: a lone surrogate (how Python reads a byte of an artifact
    file name that is not UTF-8) becomes its escape"""
    return str(text).encode("utf-8", "backslashreplace").decode("utf-8")


def tail(text, lines=25):
    return "\n".join((text or "").strip().splitlines()[-lines:])


def run(argv, cwd=None, timeout=900, as_user=RUN_AS, home="/nonexistent"):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": home, "LANG": "C.UTF-8", "TF_CLI_CONFIG_FILE": TF_CLI_CONFIG,
           "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1", "TF_INPUT": "0", "AWS_EC2_METADATA_DISABLED": "true"}
    if PROXY:
        env.update(HTTPS_PROXY=PROXY, HTTP_PROXY=PROXY, https_proxy=PROXY, http_proxy=PROXY)
    prefix = ["runuser", "-u", as_user, "--"] if as_user else []
    cmd = [*prefix, "env", "-i", *[f"{k}={v}" for k, v in env.items()], *argv]
    try:  # the tools echo artifact file names and contents: bytes that are not UTF-8 are replaced, never fatal
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(argv[:3])}"
    return p.returncode, p.stdout, p.stderr


# ---- value comparison -------------------------------------------------------------------------------------------
PROTOCOL_NUMBERS = {"tcp": "6", "udp": "17", "icmp": "1", "icmpv6": "58", "all": "-1"}


def jsonish(value):
    """a string holding a JSON object or array, parsed (policy documents compare by meaning, not by layout)"""
    if isinstance(value, str) and value[:1] in "{[":
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def unset(value):
    """null, "", [] and {} all mean "not set", so provider normalization is not a change"""
    if isinstance(value, dict):
        value = {k: v for k, v in ((k, unset(v)) for k, v in value.items()) if v is not None}
        return value or None
    if isinstance(value, list):
        value = [v for v in (unset(v) for v in value) if v is not None]
        return value or None
    return None if value == "" else value


POLICY_LISTS = ("Action", "NotAction", "Resource", "NotResource")


def policy_document(value):
    """an IAM-style document with its scalar-or-list fields as lists ("Action": "x" means ["x"])"""
    statements = value.get("Statement")
    statements = statements if isinstance(statements, list) else [statements] if statements is not None else []
    out = []
    for st in statements:
        if not isinstance(st, dict):
            out.append(st)
            continue
        st = dict(st)
        for k in POLICY_LISTS:
            if k in st and not isinstance(st[k], list):
                st[k] = [st[k]]
        for k in ("Principal", "NotPrincipal"):
            if isinstance(st.get(k), dict):
                st[k] = {p: v if isinstance(v, list) else [v] for p, v in st[k].items()}
        if isinstance(st.get("Condition"), dict):
            st["Condition"] = {op: ({c: v if isinstance(v, list) else [v] for c, v in conds.items()}
                                    if isinstance(conds, dict) else conds) for op, conds in st["Condition"].items()}
        out.append(st)
    return dict(value, Statement=out)


def canon(value):
    """comparable form: JSON strings parsed, unset parts dropped, protocol names as numbers, lists of maps and of
    scalars compared as multisets (the plan lists set-typed blocks in no particular order), policy documents with
    their scalar-or-list fields as lists"""
    value = jsonish(value)
    if isinstance(value, dict) and "Statement" in value:
        value = policy_document(value)
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in ("protocol", "ip_protocol") and isinstance(v, str):
                v = PROTOCOL_NUMBERS.get(v.lower(), v)
            if k in ("icmp_code", "icmp_type") and v == 0:  # the provider writes 0 or null for non-ICMP entries
                v = None
            out[k] = canon(v)
        return unset(out)
    if isinstance(value, list):
        items = [canon(v) for v in value]
        items = [v for v in items if v is not None]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True)) or None
    return unset(value)


def has_unknown(value):
    if isinstance(value, dict):
        return any(has_unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(has_unknown(v) for v in value)
    return value is True


def expr_text(value):
    """an HCL expression as hcl2json prints it, without the ${...} wrapper, comments, whitespace and commas (layout
    and formatting are not a change)"""
    if value is None:
        return None
    s = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    if s.startswith("${") and s.endswith("}"):
        s = s[2:-1]
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"(#|//)[^\n]*", "", s)
    return re.sub(r"[\s,]+", "", s)


def literal(value):
    """a literal default in comparable form (2 and 2.0 alike, maps by key)"""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: literal(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [literal(v) for v in value]
    return value


def flag(body, key, default):
    v = body.get(key, default)
    if isinstance(v, str):
        v = expr_text(v)
        return {"true": True, "false": False}.get(v, v)
    return v


def declaration(body):
    """what the statement protects of a root variable declaration: everything but its description"""
    return {"type": expr_text(body.get("type")),
            "default": json.dumps(literal(body.get("default")), sort_keys=True) if "default" in body else "<none>",
            "validation": sorted(f"{expr_text(v.get('condition'))} | {' '.join(str(v.get('error_message')).split())}"
                                 for v in (body.get("validation") or [])),
            "nullable": flag(body, "nullable", True), "sensitive": flag(body, "sensitive", False),
            "ephemeral": flag(body, "ephemeral", False)}


def changed_attrs(rc):
    """top-level attributes an update really changes: name -> (before, after, unknown)"""
    ch = rc["change"]
    before, after, unknown = ch.get("before") or {}, ch.get("after") or {}, ch.get("after_unknown") or {}
    out = {}
    for k in sorted(set(before) | set(after) | set(unknown)):
        if has_unknown(unknown.get(k)):
            out[k] = (before.get(k), None, True)
        elif canon(before.get(k)) != canon(after.get(k)):
            out[k] = (before.get(k), after.get(k), False)
    return out


def describe(change):
    before, after, unknown = change
    return f"{short(before)} -> {'(known after apply)' if unknown else short(after)}"


def short(value, n=140):
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= n else text[:n] + "..."


def managed(plan):
    return [rc for rc in plan.get("resource_changes", []) if rc.get("mode") == "managed"]


def renamed(value, old, new):
    """a state or var-file document with the collection key `old` renamed to `new` everywhere: index keys, names, ARNs
    and the documents that embed them, base64-encoded ones (a launch template's user_data) included"""
    if isinstance(value, dict):
        return {renamed(k, old, new): renamed(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [renamed(v, old, new) for v in value]
    if not isinstance(value, str):
        return value
    if old in value:
        return value.replace(old, new)
    if len(value) >= 16 and len(value) % 4 == 0 and BASE64.fullmatch(value):
        try:
            text = base64.b64decode(value, validate=True).decode("utf-8")
        except ValueError:  # not base64 of UTF-8 text
            return value
        if old in text:
            return base64.b64encode(text.replace(old, new).encode("utf-8")).decode("ascii")
    return value


def tag_keys_changed(before, after):
    """the tag keys whose value differs between two tag maps (added, removed or changed)"""
    before, after = before or {}, after or {}
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


# ---- workspace ----------------------------------------------------------------------------------------------------
class Workspace:
    """A scratch copy of the artifact owned by the unprivileged grading user; states and var files live beside it."""

    def __init__(self, artifact, lock_file):
        self.artifact = artifact
        self.lock_file = lock_file
        self.root = Path(tempfile.mkdtemp(prefix="grade-"))
        os.chmod(self.root, 0o755)
        self.infra, self.home, self.data = self.root / "infra", self.root / "home", self.root / "data"
        self.home.mkdir()
        self.data.mkdir()
        self.skipped = []

    def populate(self):
        for dirpath, dirnames, filenames in os.walk(self.artifact):
            rel = Path(dirpath).relative_to(self.artifact)
            kept = []
            for name in dirnames:
                if name in SKIP_DIRS or Path(dirpath, name).is_symlink():
                    self.skipped.append(str(rel / name))
                    continue
                kept.append(name)
            dirnames[:] = kept
            (self.infra / rel).mkdir(parents=True, exist_ok=True)
            for name in filenames:
                src = Path(dirpath, name)
                if src.is_symlink() or not src.is_file() or SKIP_FILE.search(name):
                    self.skipped.append(str(rel / name))
                    continue
                shutil.copyfile(src, self.infra / rel / name)
        self.infra.mkdir(exist_ok=True)
        shutil.copyfile(TESTS / self.lock_file, self.infra / ".terraform.lock.hcl")
        self.own(self.root)

    def stage(self, rel):
        """copy a verifier file (state, var file) into the scratch data directory, readable by the grading user"""
        src = TESTS / rel
        dst = self.data / hashlib.sha256(rel.encode()).hexdigest()[:16] / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        self.own(dst.parent)
        return dst

    def write(self, rel, text):
        """a file the grader writes for this run (a generated var file) into the scratch data directory, readable by
        the grading user"""
        dst = self.data / hashlib.sha256(rel.encode()).hexdigest()[:16] / Path(rel).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
        self.own(dst.parent)
        return dst

    def digest(self):
        """a fingerprint of the submitted configuration (every .tf file's path and bytes), taken before terraform
        runs: it seeds the generated probes, so the same submission always gets the same ones"""
        h = hashlib.sha256()
        for p in sorted(self.infra.rglob("*.tf")):
            if p.is_file() and ".terraform" not in p.relative_to(self.infra).parts:
                h.update(os.fsencode(p.relative_to(self.infra)) + b"\0" + p.read_bytes() + b"\0")
        return h.hexdigest()

    def own(self, path):
        if RUN_AS:
            subprocess.run(["chown", "-R", RUN_AS, str(path)], check=True)

    def tf(self, *args, timeout=900):
        return run(["terraform", *args], cwd=self.infra, timeout=timeout, home=str(self.home))

    def plan(self, name, state, var_file=None, target=None):
        args = ["plan", "-refresh=false", "-input=false", "-lock=false", "-no-color", f"-state={state}",
                f"-out={name}.tfplan"]
        if var_file:
            args.append(f"-var-file={var_file}")
        if target:
            args.append(f"-target={target}")
        rc, out, err = self.tf(*args, timeout=1500)
        if rc != 0:
            return None, tail(err or out, 30)
        rc, out, err = self.tf("show", "-json", "-no-color", f"{name}.tfplan", timeout=600)
        if rc != 0:
            return None, tail(err or out)
        return json.loads(out), None


# ---- grader -------------------------------------------------------------------------------------------------------
class Grader:
    def __init__(self, spec):
        self.spec = spec
        self.gates, self.checks, self.metrics = {}, {}, {}
        artifact = Path(os.environ.get("ARTIFACT_DIR") or spec.get("artifact_dir", "/workspace/infra"))
        self.artifact = artifact
        self.ws = Workspace(artifact, spec.get("lock_file", "terraform.lock.hcl"))
        self.pristine = json.loads((TESTS / spec.get("pristine_state", "pristine.tfstate")).read_text())
        self.instances = self.state_instances(self.pristine)
        self.plan = None
        self.state_file = None
        self.seed = None

    @staticmethod
    def state_instances(state):
        out = set()
        for r in state.get("resources", []):
            if r.get("mode") != "managed":
                continue
            base = (r["module"] + "." if r.get("module") else "") + f"{r['type']}.{r['name']}"
            for inst in r.get("instances", []):
                key = inst.get("index_key")
                out.add(base if key is None else f"{base}[{json.dumps(key)}]")
        return out

    def gate(self, name, ok, detail=""):
        detail = printable(detail)
        self.gates[name] = {"ok": bool(ok), "detail": detail, "skipped": False}
        log(f"gate {name}: {'PASS' if ok else 'FAIL ' + detail}")
        return ok

    def skip_gate(self, name, why):
        self.gates[name] = {"ok": False, "detail": f"not evaluated: {why}", "skipped": True}
        log(f"gate {name}: SKIPPED ({why})")

    def check(self, name, ok, detail="", weight=1):
        detail = printable(detail)
        self.checks[name] = {"ok": bool(ok), "detail": detail, "weight": weight}
        log(f"check {name}: {'PASS' if ok else 'FAIL ' + detail}")
        return ok

    # ---- static -----------------------------------------------------------------------------------------------------
    def hcl(self, path):
        rc, out, err = run(["hcl2json", str(path)], timeout=60, as_user="")
        if rc != 0:
            return None, tail(err or out, 5)
        try:
            return json.loads(out), None
        except ValueError:
            return None, f"hcl2json printed no JSON: {tail(out, 3)}"

    @staticmethod
    def tree(top):
        if not top.is_dir() or top.is_symlink():
            return {}
        return {str(p.relative_to(top)): (p.read_bytes() if p.is_file() and not p.is_symlink() else b"<not a file>")
                for p in sorted(top.rglob("*")) if not p.is_dir() or p.is_symlink()}

    def static_gate(self):
        problems, root, declared = [], self.ws.infra, {}
        protected = self.spec.get("protected", {})
        trusted = TESTS / protected.get("trusted_dir", "trusted")
        for rel in protected.get("files", []):
            mine, ref = self.artifact / rel, trusted / rel
            if not mine.is_file() or mine.is_symlink() or mine.read_bytes() != ref.read_bytes():
                problems.append(f"{rel} must stay exactly as it is (missing or changed)")
        for rel in protected.get("trees", []):
            a, b = self.tree(self.artifact / rel), self.tree(TESTS / rel)
            if a != b:
                diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
                problems.append(f"{rel}/ must stay exactly as it is (added, removed or changed: {diff[:5]})")
        banned_names = set(self.spec.get("banned_files", []))
        for p in sorted(self.artifact.rglob("*")):
            if any(part in SKIP_DIRS for part in p.relative_to(self.artifact).parts):
                continue
            if p.name in banned_names:
                problems.append(f"{p.relative_to(self.artifact)}: {p.name} files are not allowed")
        for p in sorted(root.rglob("*")):
            if not p.is_file() or ".terraform" in p.parts:
                continue
            rel = str(p.relative_to(root))
            if p.name.endswith(".tf.json"):
                problems.append(f"{rel}: JSON configuration files are not allowed")
            if OVERRIDE.match(p.name):
                problems.append(f"{rel}: override files are not allowed")
            if p.suffix != ".tf":
                continue
            doc, err = self.hcl(p)
            if doc is None:
                problems.append(f"{rel}: cannot be parsed: {err}")
                continue
            if p.parent == root:
                for vname, bodies in (doc.get("variable") or {}).items():
                    declared.setdefault(vname, []).extend(bodies if isinstance(bodies, list) else [bodies])
            for rtype, named in (doc.get("resource") or {}).items():
                for rname, bodies in named.items():
                    for body in bodies:
                        for lc in body.get("lifecycle") or []:
                            for banned in BANNED_LIFECYCLE:
                                if banned in lc:
                                    problems.append(f"{rel}: {rtype}.{rname} uses lifecycle {banned}")
                        if "provisioner" in body:
                            problems.append(f"{rel}: {rtype}.{rname} has a provisioner")
            for dtype in (doc.get("data") or {}):
                if dtype in BANNED_DATA:
                    problems.append(f"{rel}: data sources of type {dtype} are not allowed")
            for block in BANNED_TOP:
                if block in doc:
                    problems.append(f"{rel}: {block} blocks are not allowed")
            if "provider" in doc and rel != "providers.tf":
                problems.append(f"{rel}: provider blocks are not allowed outside providers.tf")
            for tb in doc.get("terraform") or []:
                if "backend" in tb or "cloud" in tb:
                    problems.append(f"{rel}: backend/cloud configuration is not allowed")
        for vname, want in sorted((self.spec.get("protected_variables") or {}).items()):
            got = declared.get(vname) or []
            if len(got) != 1:
                problems.append(f"root variable {vname} must stay declared, once, in the root module (found {len(got)})")
                continue
            mine, ref = declaration(got[0]), declaration(want)
            diff = [k for k in ref if mine[k] != ref[k]]
            if diff:
                problems.append(f"root variable {vname} must keep its declaration; changed: {', '.join(diff)}")
        if self.ws.skipped:
            log(f"not graded (state/plan/lock files, .terraform, .git, symlinks): {self.ws.skipped[:20]}")
        return self.gate("static", not problems, "; ".join(problems[:15]))

    # ---- terraform --------------------------------------------------------------------------------------------------
    def terraform_gate(self):
        rc, out, err = self.ws.tf("init", "-input=false", "-no-color", timeout=600)
        if rc != 0:
            return self.gate("terraform", False, f"terraform init failed:\n{tail(err or out)}")
        rc, out, err = self.ws.tf("validate", "-json", "-no-color", timeout=600)
        try:
            valid = json.loads(out).get("valid", False)
        except ValueError:
            valid = False
        if rc != 0 or not valid:
            return self.gate("terraform", False, f"terraform validate failed:\n{tail(out or err)}")
        self.state_file = self.ws.stage(self.spec.get("pristine_state", "pristine.tfstate"))
        self.plan, err = self.ws.plan("main", self.state_file)
        if self.plan is None:
            return self.gate("terraform", False, f"terraform plan failed:\n{err}")
        return self.gate("terraform", True)

    # ---- plan checks (shared by the main plan and every probe) -----------------------------------------------------
    def safety_problems(self, plan, instances, destroys=frozenset()):
        """every recorded instance stays at its address as no-op or update, except `destroys` (a probe that removes
        keys): exactly those are destroyed"""
        problems, seen, deleted = [], set(), set()
        for rc in managed(plan):
            addr, actions = rc["address"], rc["change"]["actions"]
            prev = rc.get("previous_address")
            if prev and prev != addr:
                problems.append(f"{addr}: moved from {prev}")
            if actions == ["delete"] and addr in destroys and not prev:
                deleted.add(addr)
                continue
            if any(a in ("delete", "forget") for a in actions):
                problems.append(f"{addr}: {'/'.join(actions)}")
            if actions in (["no-op"], ["update"]) and not prev:
                seen.add(addr)
        missing = sorted(instances - seen - set(destroys))
        if missing:
            problems.append(f"{len(missing)} recorded resource(s) not kept in place: {missing[:6]}")
        kept = sorted(set(destroys) - deleted)
        if kept:
            problems.append(f"{len(kept)} recorded resource(s) of the removed key(s) are not destroyed: {kept[:6]}")
        return problems

    def create_problems(self, plan):
        allowed = set(self.spec.get("allowed_creates", []))
        return [f"{rc['address']}: creating a {rc['type']} is not allowed" for rc in managed(plan)
                if rc["change"]["actions"] == ["create"] and rc["type"] not in allowed]

    def minimal_problems(self, plan, variables=None, probe_changes=None):
        allowed = self.spec.get("allowed_updates", {})
        fallout = self.spec.get("update_fallout", {})
        tag_keys = self.spec.get("allowed_tag_keys")
        probe_changes = probe_changes or {}
        problems = []
        for rc in managed(plan):
            if rc["change"]["actions"] != ["update"]:
                continue
            ok = set(allowed.get(rc["type"], [])) | set(allowed.get("*", [])) | set(fallout.get(rc["type"], [])) \
                | set(probe_changes.get(rc["address"], []))
            bad = {}
            for k, change in changed_attrs(rc).items():
                if k in ok:
                    continue
                if k in ("tags", "tags_all") and tag_keys is not None and not change[2]:
                    extra = tag_keys_changed(change[0], change[1]) - set(tag_keys)
                    if not extra:
                        continue
                    bad[k] = f"{describe(change)}; only the tag keys {sorted(tag_keys)} may change, not {sorted(extra)}"
                    continue
                bad[k] = describe(change)
            if bad:
                problems.append(f"{rc['address']}: changes {', '.join(f'{k} ({v})' for k, v in sorted(bad.items()))}")
        for name, want in (variables or {}).items():
            got = ((plan.get("variables") or {}).get(name) or {}).get("value")
            if canon(got) != canon(want):
                problems.append(f"variable {name} must keep its value {short(want, 80)} (it is {short(got, 80)})")
        return problems

    def policy_dir(self):
        policy_dir = self.ws.data / "policy-pack"
        if not policy_dir.exists():
            shutil.copytree(TESTS / self.spec.get("policies", "policies"), policy_dir)
            self.ws.own(policy_dir)
        return policy_dir

    def conftest_files(self, paths, namespaces):
        """{plan file: (successes, failures)} for the pack's rules in `namespaces` only, every file in one conftest run
        (a file missing from the result was not evaluated)"""
        rc, out, err = run(["conftest", "test", "--no-color", "--output", "json",
                            *[x for n in namespaces for x in ("--namespace", n)], "--policy", str(self.policy_dir()),
                            *map(str, paths)], cwd=str(self.ws.data), timeout=900, home=str(self.ws.home))
        try:
            results = json.loads(out)
        except ValueError:
            raise RuntimeError(f"conftest did not run: {tail(err or out, 8)}") from None
        got = {}
        for r in results:
            successes, failures = got.get(r.get("filename"), (0, []))
            got[r.get("filename")] = (successes + int(r.get("successes") or 0),
                                      failures + [f["msg"] for f in (r.get("failures") or [])])
        return got

    def conftest(self, plan, name):
        path = self.ws.data / f"{name}.plan.json"
        path.write_text(json.dumps(plan))
        self.ws.own(path)
        policy_dir = self.policy_dir()
        ns = self.spec.get("conftest", {}).get("namespaces", "all")
        ns_args = ["--all-namespaces"] if ns == "all" else [x for n in ns for x in ("--namespace", n)]
        rc, out, err = run(["conftest", "test", "--no-color", "--output", "json", *ns_args, "--policy", str(policy_dir),
                            str(path)], cwd=str(self.ws.data), timeout=900, home=str(self.ws.home))
        try:
            results = json.loads(out)
            failures = [f["msg"] for r in results for f in (r.get("failures") or [])]
            successes = sum(int(r.get("successes") or 0) for r in results)
        except (ValueError, TypeError, KeyError):
            return None, [f"conftest did not run: {tail(err or out, 8)}"]
        if rc != 0 and not failures:
            return None, [f"conftest exited {rc}: {tail(err or out, 8)}"]
        return successes, sorted(failures)

    @staticmethod
    def rule_counts(failures):
        counts = {}
        for msg in failures:
            m = RULE_ID.match(msg)
            key = m.group(1) if m else "other"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def policy_detail(self, failures):
        counts = self.rule_counts(failures)
        head = ", ".join(f"{k} x{v}" for k, v in list(counts.items())[:12])
        return f"{len(failures)} policy failure(s) ({head}): " + " | ".join(failures[:6])

    # ---- main plan gates ----------------------------------------------------------------------------------------------
    def plan_gates(self):
        p = self.safety_problems(self.plan, self.instances)
        self.gate("safety", not p, "; ".join(p[:12]))
        p = self.create_problems(self.plan)
        self.gate("creates", not p, "; ".join(p[:12]))
        p = self.minimal_problems(self.plan, self.spec.get("frozen_variables", {}))
        self.gate("minimal", not p, "; ".join(p[:12]))
        successes, failures = self.conftest(self.plan, "main")
        self.metrics["main_policy_failures"] = len(failures)
        self.metrics["main_failing_rules"] = self.rule_counts(failures) if successes is not None else {}
        self.gate("policies", successes is not None and not failures, self.policy_detail(failures))

    # ---- probes -----------------------------------------------------------------------------------------------------
    def probe(self, probe):
        name = probe["name"]
        if "state_doc" in probe:  # a fresh-key probe: the grader writes its state for this submission
            state = self.ws.write(f"generated/{name}.tfstate", json.dumps(probe["state_doc"]))
            instances = self.state_instances(probe["state_doc"])
        else:
            state = self.ws.stage(probe["state"]) if probe.get("state") else self.state_file
            instances = self.state_instances(json.loads((TESTS / probe["state"]).read_text())) \
                if probe.get("state") else self.instances
        if "vars" in probe:  # a generated probe: the grader writes its var file for this submission
            var_file = self.ws.write(f"generated/{name}.tfvars.json", json.dumps(probe["vars"]))
        else:
            var_file = self.ws.stage(probe["var_file"]) if probe.get("var_file") else None
        plan, err = self.ws.plan(f"probe-{name}", state, var_file)
        if plan is None:
            return self.check(f"probe_{name}", False, f"plan failed: {err}", probe.get("weight", 1))
        destroys = frozenset(probe.get("allowed_destroys") or [])
        problems = (self.safety_problems(plan, instances, destroys)
                    + self.create_problems(plan) + self.minimal_problems(plan, probe_changes=probe.get("allowed_changes")))
        successes, failures = self.conftest(plan, f"probe-{name}")
        # the pack's plan-safety rule reports the removed keys' destroys, which this probe requires (allowed_destroys)
        failures = [f for f in failures if not any(f.startswith(f"SAFE-001 {a}: the plan would destroy ") for a in destroys)]
        if successes is None or failures:
            problems.append(self.policy_detail(failures))
        for expect in probe.get("expect", []):
            problems += self.expectation(plan, expect)
        return self.check(f"probe_{name}", not problems, "; ".join(problems[:10]), probe.get("weight", 1))

    def expectation(self, plan, expect):
        kind = expect.get("kind")
        if kind == "ingress_port_sources":
            return self.ingress_port_sources(plan, expect)
        if kind == "attribute":
            return self.attribute(plan, expect)
        if kind == "input_relations":
            return self.input_relations(plan, expect)
        return [f"unknown expectation kind {kind!r}"]

    @staticmethod
    def covers(rule, port):
        lo, hi, proto = rule.get("from_port"), rule.get("to_port"), str(rule.get("protocol", rule.get("ip_protocol", "")))
        if proto in ("-1", "all"):
            return True
        try:
            return proto.lower() in ("tcp", "6") and int(lo) <= port <= int(hi)
        except (TypeError, ValueError):
            return False

    def ingress_port_sources(self, plan, expect):
        """every ingress rule that opens TCP `port` admits exactly the CIDR ranges `cidrs`, and each resource in
        `require` has at least one such rule"""
        port, want = int(expect["port"]), sorted(expect["cidrs"])
        problems, found = [], set()
        for rc in managed(plan):
            after = rc["change"].get("after") or {}
            rules = []
            if rc["type"] == "aws_security_group":
                rules = [(r, sorted(r.get("cidr_blocks") or []), r.get("ipv6_cidr_blocks") or [],
                          (r.get("security_groups") or []) + (r.get("prefix_list_ids") or []) + (["self"] if r.get("self") else []))
                         for r in after.get("ingress") or []]
            elif rc["type"] == "aws_security_group_rule" and after.get("type") == "ingress":
                r = after
                rules = [(r, sorted(r.get("cidr_blocks") or []), r.get("ipv6_cidr_blocks") or [],
                          [x for x in (r.get("source_security_group_id"), r.get("prefix_list_ids")) if x]
                          + (["self"] if r.get("self") else []))]
            elif rc["type"] == "aws_vpc_security_group_ingress_rule":
                r = dict(after, protocol=after.get("ip_protocol"))
                rules = [(r, sorted([after["cidr_ipv4"]] if after.get("cidr_ipv4") else []),
                          [after["cidr_ipv6"]] if after.get("cidr_ipv6") else [],
                          [x for x in (after.get("referenced_security_group_id"), after.get("prefix_list_id")) if x])]
            for r, v4, v6, others in rules:
                if not self.covers(r, port):
                    continue
                if v4 != want or v6 or others:
                    problems.append(f"{rc['address']}: an ingress rule opening port {port} admits {v4 + v6 + others}, "
                                    f"not exactly {want}")
                else:
                    found.add(rc["address"])
        for addr in expect.get("require", []):
            if addr not in found:
                problems.append(f"{addr}: has no ingress rule opening port {port} to exactly {want}")
        return problems

    @staticmethod
    def path_values(value, path):
        """the values at a dotted path with [i] or [*] list steps ("rule[*].status", "metadata_options[0].http_tokens")"""
        values = [value]
        for part in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path):
            nxt = []
            for v in values:
                if part.startswith("["):
                    idx = part[1:-1]
                    if not isinstance(v, list):
                        continue
                    nxt += v if idx == "*" else ([v[int(idx)]] if idx.isdigit() and int(idx) < len(v) else [])
                elif isinstance(v, dict) and part in v:
                    nxt.append(v[part])
            values = nxt
        return values

    def selected(self, plan, select):
        out = []
        for rc in managed(plan):
            after = rc["change"].get("after")
            if not isinstance(after, dict) or rc["type"] != select.get("type"):
                continue
            if select.get("address") and not re.search(select["address"], rc["address"]):
                continue
            where = select.get("where")
            if where:
                got = self.path_values(after, where["path"])
                if not got or not all(isinstance(v, (str, int, float)) and re.search(where["regex"], str(v)) for v in got):
                    continue
            out.append(rc)
        return out

    def attribute(self, plan, expect):
        """every resource the selector picks has `path` equal to `equals` (or containing every item of `contains`);
        at least `min_count` resources are picked"""
        problems, picked = [], self.selected(plan, expect.get("select", {}))
        if len(picked) < int(expect.get("min_count", 1)):
            problems.append(f"expected at least {expect.get('min_count', 1)} {expect['select'].get('type')} resource(s) "
                            f"matching {json.dumps(expect['select'])}, found {len(picked)}")
        for rc in picked:
            after, unknown = rc["change"]["after"], rc["change"].get("after_unknown") or {}
            if self.path_values(unknown, expect["path"].split("[")[0].split(".")[0]) == [True]:
                problems.append(f"{rc['address']}: {expect['path']} is only known after apply")
                continue
            got = self.path_values(after, expect["path"])
            if "equals" in expect:
                want = canon(expect["equals"])
                if not got or any(canon(v) != want for v in got):
                    problems.append(f"{rc['address']}: {expect['path']} is {short(got)}, expected {short(expect['equals'])}")
            if "contains" in expect:
                flat = [x for v in got for x in (v if isinstance(v, list) else [v])]
                missing = [x for x in expect["contains"] if x not in flat]
                if missing:
                    problems.append(f"{rc['address']}: {expect['path']} lacks {short(missing)}")
        return problems

    def input_relations(self, plan, expect):
        """relations to the plan's own input values, for every collection key including the keys a var-file adds: each
        channel's Lambda function and each bucket carry Owner = their entry's owner; network, application and channel
        log groups keep the requested log_retention_days (a channel's own, else the root one), raised to `floor` when
        lower (a log group named .../audit: exactly the request once it reaches `audit_floor`; below that the pack's own
        range applies); each bucket size alarm fires at alarm_gib in bytes; the application launch template runs the
        app_instance_type input (a t2 size as the same t3 size); every CostCenter tag is the root tags value
        upper-cased"""
        var = {k: (v or {}).get("value") for k, v in (plan.get("variables") or {}).items()}
        channels, buckets = var.get("channels") or {}, var.get("buckets") or {}
        root_ret = var.get("log_retention_days")
        cost = str((var.get("tags") or {}).get("CostCenter") or "").upper()
        floor, audit_floor, cap = (int(expect.get("floor", 120)), int(expect.get("audit_floor", 400)),
                                   int(expect.get("cap", 731)))
        live = {rc["address"]: rc for rc in managed(plan) if isinstance(rc["change"].get("after"), dict)}
        problems = []

        def want(addr, path, expected, what):
            rc = live.get(addr)
            if rc is None:
                problems.append(f"{addr}: not in the plan ({what})")
                return
            got = self.path_values(rc["change"]["after"], path)
            if len(got) != 1 or canon(got[0]) != canon(expected):
                problems.append(f"{addr}: {path} is {short(got)}, expected {short(expected)} ({what})")

        def retention(addr, req, what):
            if not isinstance(req, (int, float)) or isinstance(req, bool) or req > cap:
                return
            name = str((live.get(addr) or {}).get("change", {}).get("after", {}).get("name") or "")
            if name.endswith("/audit"):
                if req >= audit_floor:
                    want(addr, "retention_in_days", int(req), what)
                return
            want(addr, "retention_in_days", max(int(req), floor), what)

        for addr in ("module.network.aws_cloudwatch_log_group.flow_logs",
                     "module.application.aws_cloudwatch_log_group.application"):
            retention(addr, root_ret, "the root log_retention_days")
        for key, entry in sorted(channels.items()):
            entry = entry or {}
            want(f'module.messaging.aws_lambda_function.channel["{key}"]', "tags_all.Owner", entry.get("owner"),
                 f"the {key} channel entry's owner")
            own = entry.get("log_retention_days")
            retention(f'module.messaging.aws_cloudwatch_log_group.channel["{key}"]', root_ret if own is None else own,
                      f"the {key} channel's requested retention")
        for key, entry in sorted(buckets.items()):
            entry = entry or {}
            want(f'module.data.aws_s3_bucket.bucket["{key}"]', "tags_all.Owner", entry.get("owner"),
                 f"the {key} bucket entry's owner")
            gib = entry.get("alarm_gib")
            if isinstance(gib, (int, float)) and not isinstance(gib, bool):
                want(f'module.data.aws_cloudwatch_metric_alarm.bucket_size["{key}"]', "threshold", gib * 1073741824,
                     f"the {key} entry's alarm_gib in bytes")
        app = var.get("app_instance_type")
        if isinstance(app, str) and "." in app:
            family, size = app.split(".", 1)
            want("module.application.aws_launch_template.application", "instance_type",
                 f"t3.{size}" if family == "t2" else app, "the app_instance_type input, a t2 size as the same t3 size")
        if cost:
            for addr, rc in sorted(live.items()):
                tags = rc["change"]["after"].get("tags_all")
                if isinstance(tags, dict) and "CostCenter" in tags and tags["CostCenter"] != cost:
                    problems.append(f"{addr}: CostCenter is {short(tags['CostCenter'])}, expected {cost!r} "
                                    "(the root tags value upper-cased)")
        return problems

    # ---- run --------------------------------------------------------------------------------------------------------
    @contextlib.contextmanager
    def guard(self, *names):
        """the grading steps that decide the gates `names`: an exception there (an odd file name, file or tool output)
        fails the gates still undecided, with its reason, instead of crashing the grader"""
        try:
            yield
        except Exception as exc:
            log(f"gate {'/'.join(names)} raised:\n{traceback.format_exc()}")
            for name in names:
                if name not in self.gates:
                    self.gate(name, False, f"could not be evaluated: {type(exc).__name__}: {exc}")

    def run(self):
        if not self.artifact.is_dir() or not any(self.artifact.rglob("*.tf")):
            self.gate("static", False, f"no Terraform configuration in {self.artifact}")
            self.gate("terraform", False, f"no Terraform configuration in {self.artifact}")
            return
        with self.guard("static"):
            self.ws.populate()
            self.seed = self.ws.digest()
            self.static_gate()
        if not self.gates["static"]["ok"] and FAST:
            for gname in GATES[1:]:
                self.skip_gate(gname, "the static gate failed")
            return
        with self.guard("terraform"):
            self.terraform_gate()
        if not self.gates["terraform"]["ok"]:
            for g in GATES[2:]:
                self.skip_gate(g, "the terraform gate failed")
            return
        with self.guard(*GATES[2:]):
            counts = {}
            for rc in managed(self.plan):
                a = "/".join(rc["change"]["actions"])
                counts[a] = counts.get(a, 0) + 1
            self.metrics["main_plan_actions"] = counts
            self.plan_gates()
        if FAST and not all(g["ok"] for g in self.gates.values()):
            return
        probes = list(self.spec.get("probes", []))
        try:
            probes += self.generated_collection_probes()
        except Exception as exc:  # their checks stay expected: finish_checks fails them
            log(f"generated probes could not be made: {type(exc).__name__}: {exc}")
        for probe in probes:
            try:
                self.probe(probe)
            except Exception as exc:  # a crash inside one probe fails only that probe
                self.check(f"probe_{probe.get('name')}", False, f"probe crashed: {type(exc).__name__}: {exc}",
                           probe.get("weight", 1))
        space = self.spec.get("input_space")
        if space:
            try:
                self.input_space(space)
            except Exception as exc:  # fails only this check
                self.check(f"probe_input_space_{space.get('variable')}", False,
                           f"probe crashed: {type(exc).__name__}: {exc}")

    # ---- generated probes -------------------------------------------------------------------------------------------
    def generated_names(self):
        space = self.spec.get("input_space")
        return [c["name"] for c in self.spec.get("generated_collection_probes") or []] + \
            ([f"input_space_{space['variable']}"] if space else [])

    def pick(self, pool, salt):
        """an element of `pool` chosen by this submission's digest and `salt`: the same submission, the same choice"""
        if not self.seed:
            raise ValueError("the submitted configuration has no digest")
        if not pool:
            raise ValueError(f"nothing left to draw for {salt}")
        return pool[int.from_bytes(hashlib.sha256(f"{self.seed}:{salt}".encode()).digest()[:8], "big") % len(pool)]

    def slug(self, salt, length):
        """a lower-case slug of `length` characters (a letter first) drawn by this submission's digest and `salt`"""
        if not self.seed:
            raise ValueError("the submitted configuration has no digest")
        h = hashlib.sha256(f"{self.seed}:{salt}".encode()).digest()
        return LETTERS[h[0] % 26] + "".join(SLUG_CHARS[b % 36] for b in h[1:length])

    def input_space(self, sp):
        """the input-space check (module docstring): every value planned with only `target` targeted, `parallel` plans
        at a time, then one conftest run over all of them for the rules in `namespaces`"""
        var, target, path, migrations = sp["variable"], sp["target"], sp["path"], sp.get("migrations") or {}
        values = [f"{family}.{size}" for family in sorted(migrations) + list(sp["families"])
                  for size in sp["sizes"][family]]

        def expected(value):
            family, size = value.split(".", 1)
            return f"{migrations[family]}.{size}" if family in migrations else value

        def plan_one(value):
            label = "space-" + hashlib.sha256(value.encode()).hexdigest()[:12]
            var_file = self.ws.write(f"space/{label}.tfvars.json", json.dumps({var: value}))
            plan, err = self.ws.plan(label, self.state_file, var_file, target=target)
            if plan is None:
                return [f"plan failed: {err}"], None
            problems = [f"{rc['address']}: {'/'.join(rc['change']['actions'])}" for rc in managed(plan)
                        if rc.get("previous_address") or set(rc["change"]["actions"]) & {"delete", "forget"}]
            mine = [rc for rc in managed(plan) if rc["address"] == target]
            if len(mine) != 1 or mine[0]["change"]["actions"] not in (["update"], ["no-op"]):
                problems.append(f"{target} is not kept in place: {[rc['change']['actions'] for rc in mine]}")
            else:
                change = mine[0]["change"]
                got = None if (change.get("after_unknown") or {}).get(path) else (change.get("after") or {}).get(path)
                if got != expected(value):
                    problems.append(f"{target}: {path} is {short(got)}, expected {short(expected(value))}")
            problems += self.minimal_problems(plan, probe_changes={target: sp.get("allowed_changes") or []})
            plan_file = self.ws.data / f"{label}.plan.json"
            plan_file.write_text(json.dumps(plan))
            self.ws.own(plan_file)
            return problems, plan_file

        with ThreadPoolExecutor(max(1, int(sp.get("parallel", 4)))) as pool:
            results = dict(zip(values, pool.map(plan_one, values)))
        planned = [plan_file for _, plan_file in results.values() if plan_file]
        verdicts = self.conftest_files(planned, sp["namespaces"]) if planned else {}
        bad = {}
        for value, (problems, plan_file) in results.items():
            if plan_file:
                successes, failures = verdicts.get(str(plan_file), (0, []))
                problems = problems + failures + ([] if successes or failures else ["the pack's rules did not run"])
            if problems:
                bad[value] = problems
        log(f"input space {var}: {len(values) - len(bad)} of {len(values)} values pass"
            + "".join(f"\n  {var}={v}: {'; '.join(p[:3])}" for v, p in list(bad.items())[:12]))
        detail = "; ".join(f"{var}={v}: {p[0]}" for v, p in list(bad.items())[:6])
        return self.check(f"probe_input_space_{var}", not bad,
                          f"{len(bad)} of {len(values)} values fail: {detail}" if bad else f"{len(values)} values")

    def generated_collection_probes(self):
        """this submission's fresh-key probes (module docstring). The new key takes the added key's place in the sorted
        key order and is a prefix of no other key, so the sorted lists the state records (topology, user_data) keep
        their shape; `values` redraws entry fields ({"choices": [...]}, {"range": [lo, hi]}, {"slug": prefix});
        `allowed_changes` ("{key}" for the new key) are today's own updates for the redrawn values"""
        out = []
        pristine = (TESTS / self.spec.get("pristine_state", "pristine.tfstate")).read_text()
        for cfg in self.spec.get("generated_collection_probes") or []:
            name, var, old = cfg["name"], cfg["variable"], cfg["key"]
            base = next(p for p in self.spec.get("probes", []) if p["name"] == cfg["from"])
            if old in pristine:
                raise ValueError(f"{old!r} occurs in the pristine state: it cannot be renamed alone")
            doc = json.loads((TESTS / base["var_file"]).read_text())
            others = sorted(k for k in doc[var] if k != old)
            shipped = set((self.spec.get("frozen_variables") or {}).get(var) or {})
            for p in self.spec.get("probes", []):
                if p.get("var_file"):
                    shipped |= set(json.loads((TESTS / p["var_file"]).read_text()).get(var) or {})
            slot, key = sum(k < old for k in others), None
            for attempt in range(1000):
                cand = self.slug(f"{name}/key/{attempt}", 5 + attempt % 4)
                if cand not in shipped and sum(k < cand for k in others) == slot \
                        and not any(k.startswith(cand) or cand.startswith(k) for k in others):
                    key = cand
                    break
            if key is None:
                raise ValueError(f"no fresh {var} key found for {name}")
            entry = doc[var][key] = dict(doc[var].pop(old))
            for field, how in (cfg.get("values") or {}).items():
                salt = f"{name}/{field}"
                if "choices" in how:
                    entry[field] = self.pick(how["choices"], salt)
                elif "range" in how:
                    entry[field] = self.pick(list(range(how["range"][0], how["range"][1] + 1)), salt)
                else:
                    entry[field] = how["slug"] + self.slug(salt, 6)
            changes = renamed(base.get("allowed_changes") or {}, old, key)
            changes.update({a.replace("{key}", key): args for a, args in (cfg.get("allowed_changes") or {}).items()})
            out.append({"name": name, "vars": doc, "allowed_changes": changes,
                        "state_doc": renamed(json.loads((TESTS / base["state"]).read_text()), old, key),
                        "allowed_destroys": renamed(base.get("allowed_destroys") or [], old, key),
                        "expect": list(base.get("expect") or [])})
            log(f"generated probe {name}: {var} key {key} (for {old}) = {json.dumps(entry, sort_keys=True)}")
        return out

    def expected_probes(self):
        """(name, weight) of every probe the reward needs: the shipped ones and this submission's generated ones"""
        return [(p["name"], p.get("weight", 1)) for p in self.spec.get("probes", [])] + \
            [(name, 1) for name in self.generated_names()]

    def finish_checks(self):
        """every expected check has an entry: a probe that never ran failed because a gate failed first (or, for a
        generated probe, because it could not be made)"""
        for pname, weight in self.expected_probes():
            name = f"probe_{pname}"
            if name not in self.checks:
                self.checks[name] = {"ok": False, "detail": "not graded: a gate failed or the probe could not be made",
                                     "weight": weight}

    def reward(self):
        gates_ok = bool(self.gates) and all(g["ok"] for g in self.gates.values())
        expected = {f"probe_{name}" for name, _ in self.expected_probes()}
        checks_ok = expected <= set(self.checks) and all(c["ok"] for c in self.checks.values())
        if not gates_ok:
            return 0.0
        scoring = self.spec.get("scoring", {})
        if not scoring.get("partial_credit", False):
            return 1.0 if checks_ok else 0.0
        main_w = float(scoring.get("main_weight", 1))
        total = main_w + sum(float(weight) for _, weight in self.expected_probes())
        got = main_w + sum(float(c["weight"]) for c in self.checks.values() if c["ok"])
        return round(got / total, 4)


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    VERIFIER.mkdir(parents=True, exist_ok=True)
    spec = json.loads((TESTS / "spec.json").read_text())
    g = Grader(spec)
    try:
        g.run()
    except Exception as exc:  # whatever the guards in run() miss still grades as a failure, not as a crash
        log("grader raised:\n" + traceback.format_exc())
        g.gate("grader", False, f"grading stopped: {type(exc).__name__}: {exc}")
    g.finish_checks()
    reward = g.reward()
    for name in GATES:
        g.gates.setdefault(name, {"ok": False, "detail": "not evaluated", "skipped": True})
    gates = {k: {"ok": v["ok"], "detail": v["detail"][:300], "skipped": v.get("skipped", False)} for k, v in g.gates.items()}
    checks = {k: {"ok": v["ok"], "detail": v["detail"][:300]} for k, v in g.checks.items()}
    metrics = {"reward": reward, "gates": gates, "checks": checks,
               "passed_checks": sum(1 for c in g.checks.values() if c["ok"]), "total_checks": len(g.checks), **g.metrics}
    (VERIFIER / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (VERIFIER / "grading.json").write_text(json.dumps({"reward": reward, "gates": g.gates, "checks": g.checks,
                                                       "metrics": g.metrics}, indent=2))
    (VERIFIER / "reward.txt").write_text(f"{reward}\n")
    log("GATES " + " ".join(f"{k}={'SKIP' if v.get('skipped') else 'PASS' if v['ok'] else 'FAIL'}" for k, v in gates.items()))
    log("CHECKS " + (" ".join(f"{k}={'PASS' if v['ok'] else 'FAIL'}" for k, v in checks.items()) or "(none)"))
    log(f"reward {reward}")
    shutil.rmtree(g.ws.root, ignore_errors=True)


if __name__ == "__main__":
    main()
