#!/usr/bin/env python3
"""livesvc verifier: grade a submitted platform repository against live services.

Flow (spec-driven; nothing task-specific):
  1. static gates over the submitted files (allowed resource/data types, no provisioners, no override or extra tfvars
     files, no provider/backend blocks of its own, local modules only, no symlinks);
  2. the verifier-owned files (spec.verifier_owned) are restored from the pristine copies;
  3. for the reference solution (tests/gold, trusted) and then the submission (as an unprivileged user): fresh services
     from the task snapshot + the pristine production state -> terraform init/apply -> a second plan must be clean ->
     coverage (every object the reference manages is managed) -> checkpoint -> behavioural observation;
  4. every probe (spec.probes: inventory changes) is applied on top of each side's own result, then observed;
  5. observations are compared check by check (base), and per probe on the checks the probe changes for the
     reference plus "nothing else changed".
Writes /logs/verifier/reward.txt (the score), metrics.json (gates + checks), grading.json (details).
Score: 0 when a gate or a core check fails, else passed checks / all checks.
"""
import argparse
import json
import os
import pwd
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livesvc as L  # noqa: E402

ROOT = os.geteuid() == 0
DEFAULT_RESOURCES = {
    "vault": ["vault_mount", "vault_auth_backend", "vault_audit", "vault_policy", "vault_approle_auth_backend_role",
              "vault_database_secret_backend_connection", "vault_database_secret_backend_role",
              "vault_database_secrets_mount", "vault_identity_group", "vault_identity_group_policies",
              "vault_identity_group_member_entity_ids", "vault_identity_group_member_group_ids",
              "vault_kv_secret_backend_v2", "vault_audit_request_header", "vault_auth_backend_tune"],
    "postgres": ["postgresql_role", "postgresql_grant", "postgresql_grant_role", "postgresql_default_privileges",
                 "postgresql_schema", "postgresql_extension", "postgresql_database"],
    "grafana": ["grafana_data_source", "grafana_folder", "grafana_folder_permission", "grafana_folder_permission_item",
                "grafana_team", "grafana_dashboard", "grafana_dashboard_permission", "grafana_dashboard_permission_item",
                "grafana_contact_point", "grafana_mute_timing", "grafana_message_template",
                "grafana_notification_policy", "grafana_rule_group", "grafana_library_panel"],
}
DATA_PREFIXES = {"vault": "vault_", "postgres": "postgresql_", "grafana": "grafana_"}
TF_EXCLUDE = {".terraform", ".git"}
COVER = {
    "vault_policy": lambda v: [f"vault.policy:{v.get('name')}"],
    "vault_approle_auth_backend_role": lambda v: [f"vault.approle:{v.get('role_name')}"],
    "vault_database_secret_backend_connection": lambda v: [f"vault.dbconn:{v.get('name')}"],
    "vault_database_secrets_mount": lambda v: [f"vault.mount:{(v.get('path') or '').strip('/')}"] + [
        f"vault.dbconn:{c.get('name')}" for k, cs in v.items() if isinstance(cs, list) for c in cs
        if isinstance(c, dict) and c.get("name") and "connection_url" in c],
    "vault_database_secret_backend_role": lambda v: [f"vault.dbrole:{v.get('name')}"],
    "vault_identity_group": lambda v: [f"vault.group:{v.get('name')}"],
    "vault_identity_group_policies": lambda v: [f"vault.group:{v.get('group_name')}"],
    "vault_identity_group_member_entity_ids": lambda v: [f"vault.group:{v.get('group_name')}"],
    "vault_mount": lambda v: [f"vault.mount:{(v.get('path') or '').strip('/')}"],
    "vault_auth_backend": lambda v: [f"vault.auth:{(v.get('path') or v.get('type') or '').strip('/')}"],
    "vault_audit": lambda v: [f"vault.audit:{(v.get('path') or '').strip('/')}"],
    "vault_kv_secret_backend_v2": lambda v: [f"vault.kvconfig:{(v.get('mount') or '').strip('/')}"],
    "postgresql_role": lambda v: [f"pg.role:{v.get('name')}"],
    "postgresql_schema": lambda v: [f"pg.schema:{v.get('database')}.{v.get('name')}"],
    "postgresql_extension": lambda v: [f"pg.extension:{v.get('database')}.{v.get('name')}"],
    "postgresql_database": lambda v: [f"pg.database:{v.get('name')}"],
    "grafana_data_source": lambda v: [f"grafana.datasource:{v.get('uid')}"],
    "grafana_folder": lambda v: [f"grafana.folder:{v.get('uid')}"],
    "grafana_folder_permission": lambda v: [f"grafana.folderperms:{v.get('folder_uid')}"],
    "grafana_team": lambda v: [f"grafana.team:{v.get('name')}"],
    "grafana_dashboard": lambda v: [f"grafana.dashboard:{v.get('uid')}"],
    "grafana_contact_point": lambda v: [f"grafana.contactpoint:{v.get('name')}"],
    "grafana_mute_timing": lambda v: [f"grafana.mute:{v.get('name')}"],
    "grafana_message_template": lambda v: [f"grafana.template:{v.get('name')}"],
    "grafana_notification_policy": lambda v: ["grafana.policy"],
    "grafana_rule_group": lambda v: [f"grafana.rulegroup:{v.get('folder_uid')}/{v.get('name')}"],
}


class GraderError(Exception):
    """An infrastructure or reference failure: never a graded result."""


def run(cmd, cwd=None, env=None, user=None, timeout=900):
    pre = []
    if user and ROOT:
        pre = ["runuser", "-u", user, "--"]
    p = subprocess.run(pre + [str(c) for c in cmd], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout + p.stderr


def ensure_user(name):
    if not ROOT:
        try:
            return pwd.getpwuid(os.geteuid()).pw_name
        except KeyError:
            return os.environ.get("USER", str(os.geteuid()))
    try:
        pwd.getpwnam(name)
    except KeyError:
        subprocess.run(["useradd", "-r", "-M", "-s", "/usr/sbin/nologin", name], check=True)
    return name


def chown_tree(path, user):
    if ROOT:
        subprocess.run(["chown", "-R", f"{user}:", str(path)], check=True)


# ======================================================================================================================
# Static gates
# ======================================================================================================================
def static_gates(repo, spec):
    """Problems with the submitted files (a list of strings; empty = ok)."""
    problems = []
    owned = set(spec["verifier_owned"])
    allowed = set(spec.get("allowed_resources") or sum((DEFAULT_RESOURCES[b] for b in spec["backends"]
                                                        if b in DEFAULT_RESOURCES), []))
    prefixes = tuple(DATA_PREFIXES[b] for b in spec["backends"] if b in DATA_PREFIXES)
    inventory = spec["inventory_file"]
    for p in sorted(repo.rglob("*")):
        rel = p.relative_to(repo)
        if rel.parts and rel.parts[0] in TF_EXCLUDE:
            continue
        if p.is_symlink():
            problems.append(f"{rel}: symbolic links are not allowed")
            continue
        name = p.name
        if p.is_file() and (name.endswith(".tf.json") or name == "override.tf" or name.endswith("_override.tf")):
            problems.append(f"{rel}: JSON configuration and override files are not allowed")
        if p.is_file() and (name.endswith(".tfvars") or name.endswith(".tfvars.json")) and str(rel) != inventory:
            problems.append(f"{rel}: variable files other than {inventory} are not allowed (the inventory is "
                            "verifier-owned)")
        if p.is_file() and name in (".terraformrc", "terraform.rc"):
            problems.append(f"{rel}: CLI configuration files are not allowed")
    for tf in sorted(repo.rglob("*.tf")):
        rel = tf.relative_to(repo)
        if rel.parts[0] in TF_EXCLUDE or str(rel) in owned:
            continue
        code, out = run(["hcl2json", str(tf)], timeout=60)
        if code != 0:
            problems.append(f"{rel}: not valid HCL ({out.strip()[:200]})")
            continue
        doc = json.loads(out)
        for rtype, objs in (doc.get("resource") or {}).items():
            if rtype not in allowed:
                problems.append(f"{rel}: resource type {rtype} is not allowed")
            for rname, bodies in objs.items():
                for b in bodies:
                    if "provisioner" in b or "connection" in b:
                        problems.append(f"{rel}: {rtype}.{rname} has a provisioner")
        for dtype in (doc.get("data") or {}):
            if not dtype.startswith(prefixes):
                problems.append(f"{rel}: data source {dtype} is not allowed")
        for b in doc.get("removed") or []:
            if "provisioner" in b:
                problems.append(f"{rel}: removed block with a provisioner")
        if doc.get("provider"):
            problems.append(f"{rel}: provider blocks belong to the verifier-owned providers.tf")
        for t in doc.get("terraform") or []:
            if "backend" in t or "cloud" in t:
                problems.append(f"{rel}: backend/cloud configuration belongs to the verifier-owned backend.tf")
            for rp in t.get("required_providers") or []:
                for name, req in rp.items():
                    src = req.get("source", name) if isinstance(req, dict) else name
                    if not any(src.endswith(x) for x in spec.get("providers", ["hashicorp/vault", "cyrilgdn/postgresql"])):
                        problems.append(f"{rel}: provider {src} is not available")
        for mname, bodies in (doc.get("module") or {}).items():
            for b in bodies:
                src = str(b.get("source", ""))
                if not (src.startswith("./") or src.startswith("../")):
                    problems.append(f"{rel}: module {mname} must use a local source (found {src!r})")
    return problems


# ======================================================================================================================
# Services and Terraform
# ======================================================================================================================
class Platform:
    def __init__(self, tests, work, spec):
        self.tests, self.work, self.spec = tests, work, spec
        self.root = work / "platform"
        self.svc = ensure_user("svc")
        # /tests is root-only; the services run as svc and restore from their own copy of the snapshot
        self.snapshot = work / "snapshot"
        shutil.copytree(tests / "snapshot", self.snapshot)
        chown_tree(self.snapshot, self.svc)
        os.chmod(self.snapshot, 0o700)
        self.pc = ["python3", str(tests / "platformctl.py"), "--backends", ",".join(spec["backends"])]

    def _pc(self, *args, timeout=300):
        code, out = run(self.pc + list(args), timeout=timeout)
        if code != 0:
            raise GraderError(f"platformctl {args[0]} failed: {out[-800:]}")
        return out

    def fresh(self):
        self.down()
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        chown_tree(self.root, self.svc)
        self._pc("up", "--root", self.root, "--snapshot", self.snapshot, "--user", self.svc)

    def down(self):
        if self.root.exists():
            run(self.pc + ["down", "--root", self.root], timeout=120)

    def checkpoint(self, name):
        self.down()
        dst = self.work / "ckpt" / name
        shutil.rmtree(dst, ignore_errors=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(dst.parent, 0o700)
        shutil.copytree(self.root, dst, symlinks=True)
        self._pc("up", "--root", self.root, "--snapshot", self.snapshot, "--user", self.svc)

    def rollback(self, name):
        self.down()
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.copytree(self.work / "ckpt" / name, self.root, symlinks=True)
        chown_tree(self.root, self.svc)
        self._pc("up", "--root", self.root, "--snapshot", self.snapshot, "--user", self.svc)

    def secrets(self):
        files = {"vault": "vault-root.token", "postgres": "postgres.password", "grafana": "grafana-admin.password"}
        return {b: (self.snapshot / f).read_text().strip() for b, f in files.items() if b in self.spec["backends"]}


class Side:
    """One configuration (reference or submission) in its own working copy, with its own state file."""

    def __init__(self, name, src, tests, work, spec, user, trusted):
        self.name, self.spec, self.user, self.trusted = name, spec, user, trusted
        self.dir = work / name
        self.repo = self.dir / "repo"
        self.state = self.dir / "state" / "terraform.tfstate"
        self.home = self.dir / "home"
        shutil.rmtree(self.dir, ignore_errors=True)
        self.repo.mkdir(parents=True)
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src)
            if rel.parts[0] in TF_EXCLUDE or p.is_symlink() or p.name.endswith((".tfstate", ".tfstate.backup", ".tfplan")):
                continue
            if p.is_dir():
                (self.repo / rel).mkdir(parents=True, exist_ok=True)
            elif p.is_file():
                (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, self.repo / rel)
        for f in spec["verifier_owned"]:
            shutil.copyfile(tests / "pristine" / f, self.repo / f)
        shutil.copyfile(tests / "pristine" / "terraform.lock.hcl", self.repo / ".terraform.lock.hcl")
        (self.repo / spec.get("backend_file", "backend.tf")).write_text(
            f'terraform {{\n  backend "local" {{\n    path = "{self.state}"\n  }}\n}}\n')
        self.state.parent.mkdir(parents=True)
        self.home.mkdir()
        os.chmod(self.dir, 0o700)
        chown_tree(self.dir, user)

    def env(self, sec):
        token, pgpw, gpw = sec.get("vault"), sec.get("postgres"), sec.get("grafana")
        e = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/lib/postgresql/17/bin",
             "HOME": str(self.home), "TF_IN_AUTOMATION": "1", "CHECKPOINT_DISABLE": "1",
             "TF_CLI_CONFIG_FILE": os.environ.get("TF_CLI_CONFIG_FILE", "/etc/terraformrc"),
             "LANG": "C.UTF-8"}
        if token:
            e.update({"VAULT_ADDR": L.VAULT, "VAULT_TOKEN": token})
        if pgpw:
            e.update({"PGHOST": L.PG_HOST, "PGPORT": str(L.PG_PORT), "PGUSER": "postgres", "PGPASSWORD": pgpw,
                      "PGDATABASE": "postgres", "PGSSLMODE": "disable"})
        if gpw:
            e.update({"GRAFANA_URL": L.GRAFANA, "GRAFANA_AUTH": f"admin:{gpw}"})
        return e

    def set_state(self, src):
        shutil.copyfile(src, self.state)
        chown_tree(self.state.parent, self.user)

    def set_inventory(self, inv):
        (self.repo / self.spec["inventory_file"]).write_text(json.dumps(inv, indent=2) + "\n")
        chown_tree(self.repo, self.user)

    def tf(self, args, env, timeout):
        return run(["terraform", *args], cwd=self.repo, env=env, user=None if self.trusted else self.user, timeout=timeout)


# Transient errors of parallel applies, retried like CI does (the retry continues from the recorded state):
# PostgreSQL when parallel resources update the same catalog row (GRANTs on one database), PostgreSQL refusing a
# connection because a CONNECT grant of the same apply has not landed yet (Vault verifies its database connections),
# Grafana answering 412 to concurrent folder/dashboard writes. Authentication failures are NOT transient.
TRANSIENT = re.compile(r"tuple concurrently updated|deadlock detected|could not serialize access|concurrent update|"
                       r"permission denied for database|\(status 412\)")


def apply_and_plan(side, env, label):
    """(ok, detail, state_json)"""
    for attempt in range(3):
        code, out = side.tf(["apply", "-auto-approve", "-input=false", "-no-color", "-lock=false"], env, 1800)
        (side.dir / f"{label}-apply{'' if attempt == 0 else f'-retry{attempt}'}.log").write_text(out)
        if code == 0 or not TRANSIENT.search(out):
            break
        L.log(f"{side.name} {label}: transient error, retrying the apply ({errors(out)[:160]})")
    if code != 0:
        return False, "terraform apply failed: " + errors(out), None
    code, out = side.tf(["plan", "-detailed-exitcode", "-input=false", "-no-color", "-lock=false"], env, 900)
    (side.dir / f"{label}-plan.log").write_text(out)
    if code == 2:
        changes = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("# ")][:8]
        return False, "the second plan is not clean: " + "; ".join(changes), None
    if code != 0:
        return False, "the second plan failed: " + errors(out), None
    code, out = side.tf(["show", "-json"], env, 600)
    try:
        return True, "applied; second plan clean", json.loads(out)
    except ValueError:
        return False, "terraform show -json failed", None


def errors(out):
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    errs = [ln for i, ln in enumerate(lines) if ln.startswith("Error:")]
    return (" | ".join(errs[:4]) or (lines[-1] if lines else "no output"))[:600]


def coverage(state):
    keys = set()

    def walk(mod):
        for r in mod.get("resources") or []:
            if r.get("mode") == "managed" and r.get("type") in COVER:
                keys.update(COVER[r["type"]](r.get("values") or {}))
        for c in mod.get("child_modules") or []:
            walk(c)

    walk(((state or {}).get("values") or {}).get("root_module") or {})
    return keys


# ======================================================================================================================
# Probes
# ======================================================================================================================
def merge_patch(target, patch):
    if not isinstance(patch, dict):
        return patch
    out = dict(target) if isinstance(target, dict) else {}
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = merge_patch(out.get(k), v)
    return out


WORDS = ["atlas", "beacon", "cascade", "dorado", "ember", "falcon", "glacier", "heron", "iris", "juniper", "kestrel",
         "lumen", "meridian", "nimbus", "osprey", "prism", "quill", "raven", "summit", "tundra", "umber", "vesper",
         "willow", "zephyr"]


def probe_inventory(probe, base_inv, salt):
    patch = probe["patch"]
    if probe.get("tokens"):
        rng = random.Random(f"{salt}:{probe['name']}")
        used = json.dumps(base_inv)
        text = json.dumps(patch)
        for tok, shape in sorted(probe["tokens"].items()):
            words = [w for w in WORDS if w not in used]
            word = rng.choice(words)
            used += word
            value = shape.replace("@WORD@", word)
            text = text.replace(tok, value)
        patch = json.loads(text)
    return merge_patch(base_inv, patch)


# ======================================================================================================================
# Grading
# ======================================================================================================================
def observe(spec, platform, creds, dump=None, inventory=None):
    sec = platform.secrets()
    ob = L.Observer(sec.get("vault"), sec.get("postgres"), spec.get("observe"), creds)
    ob.grafana_pw = sec.get("grafana")
    obs = ob.observe(inventory)
    obs["_policy_texts"] = ob.policy_texts
    obs = json.loads(json.dumps(obs))          # one canonical form (tuples -> lists), as cached references have
    if dump:
        fd = os.open(dump, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(obs, f, indent=1, sort_keys=True)
    return obs


def policy_facts(spec, platform, ref, sub, cache):
    """Fill vault.policy:* 'caps' facts on both observations, evaluated in the running Vault."""
    sec = platform.secrets()
    ob = L.Observer(sec.get("vault"), sec.get("postgres"), spec.get("observe"), {})
    extra = (spec.get("observe") or {}).get("extra_paths", [])
    rt, st = ref.get("_policy_texts", {}), sub.get("_policy_texts", {})
    for n in sorted(set(rt) | set(st)):
        key = (L.digest(rt.get(n)), L.digest(st.get(n)))
        if key not in cache:
            paths = set()
            for t in (rt.get(n), st.get(n)):
                for pat in L.policy_patterns(t):
                    paths |= L.instantiate(pat)
            rc = ob.capabilities({n: (rt[n], paths)}, extra)[n] if n in rt else None
            sc = ob.capabilities({n: (st[n], paths)}, extra)[n] if n in st else None
            cache[key] = (rc, sc)
        rc, sc = cache[key]
        if n in rt:
            ref[f"vault.policy:{n}"]["caps"] = rc
        if n in st:
            sub[f"vault.policy:{n}"]["caps"] = sc


def matches(check, patterns):
    return any(check.startswith(p[:-1]) if p.endswith("*") else check == p for p in patterns)


def core_check(check, spec, ref_obs=None):
    """Core: always for spec.core_checks; for spec.core_if_kept only when the reference keeps it working (e.g. the
    credentials of a production client whose role the model keeps)."""
    if matches(check, spec.get("core_checks", [])):
        return True
    if ref_obs is not None and matches(check, spec.get("core_if_kept", [])):
        facts = ref_obs.get(check) or {}
        login = facts.get("login_ok", facts.get("login"))
        return bool(login.get("ok") if isinstance(login, dict) else login)
    return False


PLATFORMS = []


def grade(a):
    try:
        return _grade(a)
    finally:
        for p in PLATFORMS:
            try:
                p.down()
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass


def _grade(a):
    tests, out = Path(a.tests), Path(a.out)
    spec = json.loads((tests / "spec.json").read_text())
    work = Path(a.work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.chmod(work, 0o711)
    creds = json.loads((tests / "credentials.json").read_text()) if (tests / "credentials.json").exists() else {}
    artifact = Path(a.artifact or spec["repo_dir"])
    gates, checks, info = {}, {}, {"probes": {}}

    def gate(name, ok, detail):
        gates[name] = {"ok": bool(ok), "detail": str(detail)[:300], "skipped": False}
        L.log(f"gate {name}: {'ok' if ok else 'FAIL'} - {str(detail)[:300]}")
        return ok

    def finish(score):
        return write_results(out, score, gates, checks, info, spec)

    if not artifact.is_dir() or not any(artifact.glob("*.tf")):
        gate("static", False, f"no Terraform configuration at {artifact}")
        return finish(0.0)
    problems = static_gates(artifact, spec)
    if not gate("static", not problems, "; ".join(problems[:6]) if problems else "allowed constructs only"):
        info["static_problems"] = problems
        return finish(0.0)

    platform = Platform(tests, work, spec)
    PLATFORMS.append(platform)
    tfuser = ensure_user("tfrun")
    gold = Side("gold", tests / "gold", tests, work, spec, "root" if ROOT else tfuser, trusted=True)
    sub = Side("sub", artifact, tests, work, spec, tfuser, trusted=False)
    sec = platform.secrets()
    base_inv = json.loads((tests / "pristine" / spec["inventory_file"]).read_text())
    probes = spec.get("probes", [])
    salt = spec.get("salt", "0")
    obs = {"gold": {}, "sub": {}}

    # ---- the reference -------------------------------------------------------------------------------------------
    cache = Path(a.ref_cache) if a.ref_cache else None
    cached = None
    if cache and (cache / "ref.json").exists():
        cached = json.loads((cache / "ref.json").read_text())
        if cached.get("key") != ref_key(tests, spec):
            cached = None
    if cached:
        obs["gold"], gold_cov = cached["obs"], {k: set(v) for k, v in cached["coverage"].items()}
        L.log("reference observations: cached")
    else:
        gold_cov = {}
        env = gold.env(sec)
        code, outp = gold.tf(["init", "-input=false", "-no-color", "-lockfile=readonly"], env, 900)
        if code != 0:
            raise GraderError("reference init failed: " + errors(outp))
        for label, inv in [("base", base_inv)] + [(p["name"], probe_inventory(p, base_inv, salt)) for p in probes]:
            if label == "base":
                platform.fresh()
                gold.set_state(tests / "snapshot" / "terraform.tfstate")
            else:
                platform.rollback("gold-base")
                gold.set_state(gold.dir / "base.tfstate")
            gold.set_inventory(inv)
            ok, detail, state = apply_and_plan(gold, env, label)
            if not ok:
                raise GraderError(f"the reference failed on {label}: {detail}")
            gold_cov[label] = coverage(state)
            if label == "base":
                done = re.search(r"Apply complete! Resources: (\d+) imported", (gold.dir / "base-apply.log").read_text())
                imports = int(done.group(1)) if done else 0
                shutil.copyfile(gold.state, gold.dir / "base.tfstate")
                platform.checkpoint("gold-base")
            obs["gold"][label] = observe(spec, platform, creds, work / f"obs-gold-{label}.json", inv)
            L.log(f"reference {label}: observed {len(obs['gold'][label])} objects")
        if cache:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / "ref.json").write_text(json.dumps({"key": ref_key(tests, spec), "obs": obs["gold"], "imports": imports,
                                                        "coverage": {k: sorted(v) for k, v in gold_cov.items()}}))

    # ---- the submission ------------------------------------------------------------------------------------------
    env = sub.env(sec)
    code, outp = sub.tf(["init", "-input=false", "-no-color", "-lockfile=readonly"], env, 900)
    if not gate("init", code == 0, "terraform init ok" if code == 0 else errors(outp)):
        return finish(0.0)
    code, outp = sub.tf(["validate", "-no-color"], env, 300)
    if not gate("validate", code == 0, "valid" if code == 0 else errors(outp)):
        return finish(0.0)
    platform.fresh()
    sub.set_state(tests / "snapshot" / "terraform.tfstate")
    sub.set_inventory(base_inv)
    ok, detail, state = apply_and_plan(sub, env, "base")
    if not gate("apply", ok, detail):
        return finish(0.0)
    missing = sorted(gold_cov["base"] - coverage(state))
    if not gate("coverage", not missing, ("not managed by the configuration: " + ", ".join(missing[:12]) +
                                          (f" (+{len(missing) - 12} more)" if len(missing) > 12 else ""))
                if missing else "every object the model defines is managed"):
        info["unmanaged"] = missing
        return finish(0.0)
    shutil.copyfile(sub.state, sub.dir / "base.tfstate")
    platform.checkpoint("sub-base")
    obs["sub"]["base"] = observe(spec, platform, creds, work / "obs-sub-base.json", base_inv)
    pcache = {}
    policy_facts(spec, platform, obs["gold"]["base"], obs["sub"]["base"], pcache)
    base = L.compare(obs["gold"]["base"], obs["sub"]["base"])
    for c, (ok, detail) in base.items():
        checks[c] = {"ok": ok, "detail": detail or "as the model requires",
                     "core": core_check(c, spec, obs["gold"]["base"])}

    for p in probes:
        name = p["name"]
        inv = probe_inventory(p, base_inv, salt)
        platform.rollback("sub-base")
        sub.set_state(sub.dir / "base.tfstate")
        sub.set_inventory(inv)
        ok, detail, state = apply_and_plan(sub, env, name)
        if ok:
            missing = sorted(gold_cov[name] - coverage(state))
            if missing:
                ok, detail = False, "not managed after the change: " + ", ".join(missing[:8])
        gref, gbase = obs["gold"][name], obs["gold"]["base"]
        # the checks this inventory change touches in the reference
        policy_facts(spec, platform, gbase, gref, pcache)
        delta = sorted(c for c, (same, _) in L.compare(gbase, gref).items() if not same)
        info["probes"][name] = {"apply": detail, "changed_checks": len(delta)}
        checks[f"probe.{name}:apply"] = {"ok": ok, "detail": detail, "core": False}
        if not ok:
            for c in delta:
                checks[f"probe.{name}:{c}"] = {"ok": False, "detail": "the inventory change did not apply", "core": False}
            checks[f"probe.{name}:unchanged"] = {"ok": False, "detail": "the inventory change did not apply",
                                                 "core": False}
            continue
        sobs = observe(spec, platform, creds, work / f"obs-sub-{name}.json", inv)
        policy_facts(spec, platform, gref, sobs, pcache)
        res = L.compare(gref, sobs)
        for c in delta:
            okc, det = res.get(c, (True, ""))
            checks[f"probe.{name}:{c}"] = {"ok": okc, "detail": det or "follows the inventory", "core": False}
        policy_facts(spec, platform, obs["sub"]["base"], sobs, pcache)
        others = [c for c, (same, _) in L.compare(obs["sub"]["base"], sobs).items() if not same and c not in delta]
        checks[f"probe.{name}:unchanged"] = {"ok": not others, "core": False,
                                             "detail": ("also changed: " + ", ".join(others[:8])) if others
                                             else "nothing else changed"}
        L.log(f"probe {name}: {len(delta)} changed checks, {sum(1 for c in delta if res.get(c, (True,))[0])} as "
              f"expected, {len(others)} unexpected changes")
    platform.down()

    failed_core = sorted(c for c, v in checks.items() if v["core"] and not v["ok"])
    passed = sum(1 for v in checks.values() if v["ok"])
    score = 0.0 if failed_core else passed / max(1, len(checks))
    info["failed_core"] = failed_core
    # incident tasks: the score is scaled by the share of code defects resolved (a defect is resolved when every check
    # of its signature passes; signatures are measured at build time by re-introducing each defect alone)
    defects = [d for d in spec.get("defects") or [] if d.get("where") == "code" and d.get("signature")]
    resolved = 0
    if defects:
        status = {}
        for d in defects:
            failing = [c for c in checks if not c.startswith("probe.") and matches(c, d["signature"]) and not checks[c]["ok"]]
            status[d["id"]] = {"resolved": not failing, "symptom": d.get("symptom", ""), "failing": failing[:6]}
        resolved = sum(1 for v in status.values() if v["resolved"])
        info["defects"] = status
        L.log(f"defects resolved: {resolved}/{len(defects)}" + "".join(
            f"; {k} ({v['symptom']}) open: {', '.join(v['failing'][:3])}" for k, v in status.items() if not v["resolved"]))
        score *= resolved / len(defects)
    # binary grading (SRE-xai-ots spec): 1 only when no core check failed and EVERY check passed (and, for incident
    # tasks, every defect is resolved); the share is kept as information only
    full = not failed_core and passed == len(checks) and (not defects or resolved == len(defects))
    info["partial_share"] = round(score, 4)
    return finish(1.0 if full else 0.0)


def ref_key(tests, spec):
    spec = {k: v for k, v in spec.items() if k not in ("defects", "mistakes")}
    h = L.digest({"spec": spec, "files": sorted((str(p.relative_to(tests)), p.stat().st_size, L.digest(p.read_bytes().hex()))
                                               for p in sorted((tests / "gold").rglob("*")) if p.is_file()),
                  "snapshot": sorted((f.name, L.digest(f.read_bytes().hex())) for f in (tests / "snapshot").iterdir()
                                     if f.is_file()),
                  "observer": L.digest(Path(L.__file__).read_bytes().hex())})
    return h


def write_results(out, score, gates, checks, info, spec):
    out.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for v in checks.values() if v["ok"])
    metrics = {"gates": gates, "checks": {c: {"ok": v["ok"], "detail": v["detail"][:300]} for c, v in checks.items()},
               "passed_checks": passed, "total_checks": len(checks), "score": score,
               "failed_core": info.get("failed_core", []), "task_type": spec.get("task_type")}
    if info.get("defects"):
        metrics["defects"] = {k: {"resolved": v["resolved"], "symptom": v["symptom"]} for k, v in info["defects"].items()}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True))
    (out / "grading.json").write_text(json.dumps({"score": score, "gates": gates, "checks": checks, "info": info},
                                                 indent=1, sort_keys=True, default=sorted))
    failed = [c for c, v in checks.items() if not v["ok"]]
    gate_line = " ".join(f"{g}={'ok' if v['ok'] else 'FAIL'}" for g, v in gates.items())
    L.log(f"GATES {gate_line}")
    L.log(f"CHECKS {passed}/{len(checks)} passed" + (f"; failed: {', '.join(failed[:10])}" +
                                                    (f" (+{len(failed) - 10} more)" if len(failed) > 10 else "")
                                                    if failed else ""))
    for c in failed[:40]:
        L.log(f"  FAIL {c}: {checks[c]['detail'][:300]}")
    (out / "reward.txt").write_text(f"{score}\n")
    L.log(f"SCORE {score}")
    return score


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tests", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--artifact")
    ap.add_argument("--out", default="/logs/verifier")
    ap.add_argument("--work", default="/tmp/livesvc-grade")
    ap.add_argument("--ref-cache")
    a = ap.parse_args()
    sys.path.insert(0, a.tests)
    try:
        import platformctl
        platformctl.ensure_identity()
    except ImportError:
        pass
    t0 = time.time()
    try:
        grade(a)
    except (GraderError, L.ObserveError) as e:
        L.log(f"GRADER ERROR (not a graded result): {e}")
        sys.exit(3)
    finally:
        L.log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
