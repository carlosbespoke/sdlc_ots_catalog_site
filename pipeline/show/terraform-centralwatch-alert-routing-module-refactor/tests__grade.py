#!/usr/bin/env python3
"""Spec-driven grader for Terraform migrate/refactor tasks (separate verifier container).

Shared by every task the IaC pipeline builds. Each task ships /tests/spec.json describing its target (modules,
ownership, key dimensions, variables, probes, outputs); everything that keeps grading honest is fixed here.

The agent's /workspace/infra arrives as an artifact. Nothing the agent ran or saved decides the grade: state files,
plan files, the lock file and .terraform are discarded, and terraform runs offline, as an unprivileged user, in a
scratch copy, against the verifier's own pristine state, which lives outside the configuration directory and reaches
terraform only through -state.

Gates (any failure -> reward 0):
  terraform      offline init + validate + `plan -refresh=false` against the pristine state
  static         no ignore_changes/prevent_destroy, provisioners, removed/import blocks, backends, external or
                 terraform_remote_state data sources, file functions with computed or out-of-module paths, state or plan
                 references, extra or changed provider configuration (providers.tf byte for byte), override files or
                 .tf.json files in any loaded module
  moves_only     every resource in the pristine state is still managed; no create/update/replace/destroy/forget
  policies       the repository's CI guardrail policies (verifier-owned copy) pass on that plan
  no_pasted_ids  no ID, ARN, IP address or DNS name of an existing resource, nor the random part of one (an ALB's
                 arn_suffix), is written into the configuration, and with every resource forced to be replaced no known
                 value still holds a cloud-assigned one or a random part of one
  remapped_state planned against a copy of the state whose cloud-assigned IDs and their random parts are all
                 consistently swapped wherever they appear, the configuration still plans as moves only and no original
                 ID or random part survives anywhere
  outputs        every required root output exists with the expected value, as a plain reference to an output of its
                 owning module (so leaving outputs out cannot keep most of the reward)
Checks (reward = passed / total once every gate passes, so 1.0 only when all pass), from spec.json:
  layout, ownership_<module>..., keys_<dimension>..., no_count, one check per probe
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

TESTS = Path(os.environ.get("TESTS_DIR", "/tests"))
ARTIFACT = Path(os.environ.get("ARTIFACT_DIR", "/workspace/infra"))
VERIFIER = Path(os.environ.get("VERIFIER_DIR", "/logs/verifier"))
RUN_AS = os.environ.get("GRADER_RUN_AS", "nobody")
TF_CLI_CONFIG = os.environ.get("TF_CLI_CONFIG_FILE", "/etc/terraformrc")
# Provider traffic goes to a dead loopback proxy: still offline, but an API call a plan makes (for example an EC2 instance
# whose AMI changes) fails at once instead of waiting out DNS failures and SDK retries past the plan timeout.
PROXY = os.environ.get("GRADER_PROXY", "http://127.0.0.1:9")
RECORD = os.environ.get("GRADER_RECORD")  # iacctl: where the reference solution's run records its key-probe updates

NAME_ATTRS = {  # resource names and identifiers (rename probes expect these to follow the renamed variable)
    "aws_cloudwatch_log_group": ["name"], "aws_iam_role": ["name"], "aws_iam_role_policy": ["name"],
    "aws_iam_policy": ["name"], "aws_iam_instance_profile": ["name"], "aws_iam_user": ["name"],
    "aws_iam_group": ["name"], "aws_security_group": ["name"], "aws_lb": ["name"], "aws_lb_target_group": ["name"],
    "aws_launch_template": ["name"], "aws_autoscaling_group": ["name"], "aws_s3_bucket": ["bucket"],
    "aws_kms_alias": ["name"], "aws_dynamodb_table": ["name"], "aws_db_subnet_group": ["name"],
    "aws_db_parameter_group": ["name"], "aws_db_instance": ["identifier", "final_snapshot_identifier"],
    "aws_sqs_queue": ["name"], "aws_sns_topic": ["name"], "aws_lambda_function": ["function_name"],
    "aws_ecs_cluster": ["name"], "aws_ecs_service": ["name"], "aws_ecr_repository": ["name"],
    "aws_secretsmanager_secret": ["name"], "aws_ssm_parameter": ["name"], "aws_cloudwatch_metric_alarm": ["alarm_name"],
    "aws_elasticache_subnet_group": ["name"], "aws_elasticache_cluster": ["cluster_id"],
    "aws_api_gateway_rest_api": ["name"], "aws_apigatewayv2_api": ["name"], "aws_cognito_user_pool": ["name"],
    "aws_sfn_state_machine": ["name"], "aws_kinesis_stream": ["name"], "aws_efs_file_system": ["creation_token"],
    "aws_ecs_task_definition": ["family"], "aws_elasticache_replication_group": ["replication_group_id"],
    "aws_cognito_user_pool_domain": ["domain"],
}
GENERIC_NAME = re.compile(r"^(name|.+_name|(.+_)?identifier)$")  # name-shaped arguments the legacy stack configures


def name_fields(rtype, legacy_args=()):
    """Name attributes of a resource: the known ones for its type plus every name-shaped argument that the trusted
    legacy configuration sets for it (so dropping an argument cannot hide a stale name)."""
    return set(NAME_ATTRS.get(rtype, [])) | {k for k in legacy_args if GENERIC_NAME.match(k) and not ID_KEY.search(k)}


FILE_FUNCS = ("templatefile", "filebase64sha256", "filebase64sha512", "filebase64", "fileexists", "filemd5",
              "filesha1", "filesha256", "filesha512", "fileset", "file")
FILE_CALL = re.compile(r"(?<![\w.:])(" + "|".join(FILE_FUNCS) + r")\s*\(")
# an optional leading "./" is the same place ("./${path.module}/x" is "modules/m/x" read from the root directory)
LITERAL_PATH = re.compile(r'"(?:\./)?(?:\$\{path\.(?:module|root)\}/)?(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*"\s*[,)]')
# a child module resolves bare paths and path.root from the root directory, so only path.module stays inside it
CHILD_PATH = re.compile(r'"(?:\./)?\$\{path\.module\}/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*"\s*[,)]')
# random parts of cloud-assigned values: IPv4 (dotted or dashed), hex runs, upper/lower alphanumeric runs with a digit
TOKEN = re.compile(r"(?<![0-9A-Za-z])\d{1,3}([.-])\d{1,3}\1\d{1,3}\1\d{1,3}(?![0-9])|[0-9a-f]{6,}|(?=[0-9A-Z]*\d)[0-9A-Z]{8,}|[A-Z]{16,}"
                   r"|(?=[0-9a-z]*\d)(?=[0-9a-z]*[g-z])[0-9a-z]{12,}"
                   # the random suffix AWS appends to a Secrets Manager secret's ARN (...:secret:name-kfSVUB): six
                   # letters and digits after the last dash, mixing upper and lower case
                   r"|(?<=-)(?=[0-9a-z]*[A-Z])(?=[0-9A-Z]*[a-z])[0-9A-Za-z]{6}$")
IPV4 = re.compile(r"\d{1,3}([.-])\d{1,3}\1\d{1,3}\1\d{1,3}")
ENDPOINT_KEY = re.compile(r"(^|_)(dns|dns_name|endpoint|address)$")
ID_KEY = re.compile(r"(^|_)(id|ids|arn|arns|ip|ips|dns|dns_name|endpoint|address)$")
# an ARN AWS itself owns (account field "aws", e.g. arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess) is a published
# constant every account shares, not an identifier assigned to this stack: writing it out is no pasted ID
AWS_OWNED_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:aws:")


def token_pattern(tokens):
    """one regex for standalone occurrences of any of the tokens (not inside a longer run of letters and digits)"""
    if not tokens:
        return None
    return re.compile(r"(?<![0-9A-Za-z])(?:" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
                      + r")(?![0-9A-Za-z])")


def strings_in(value):
    """every string in a JSON value, map keys included"""
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)
    elif isinstance(value, str):
        yield value
GATES = ["terraform", "static", "moves_only", "policies", "no_pasted_ids", "remapped_state", "outputs"]
SKIP_DIRS = {".terraform", ".git", "terraform.tfstate.d"}
SKIP_FILE = re.compile(r"(\.tfstate(\..*)?|\.tfplan|^\.terraform\.lock\.hcl|^\.terraform\.tfstate\.lock\.info)$")
KEY_RE = re.compile(r'\[("(?:[^"\\]|\\.)*"|\d+)\]')
INSTANCE_KEY = r'\[(?:"(?:[^"\\]|\\.)*"|\d+)\]'
CHAIN_IDENT = r"[A-Za-z_][A-Za-z0-9_-]*"
# an index is a literal key or a key held in a local or variable (aws_s3_bucket.data[local.certs_bucket]), or an element
# of one (aws_lambda_function.op[local.order[0]], the same key a local holding var.order[0] would give): either way the
# value is still read from the resource, and the output's value is checked separately
CHAIN_INDEX = (r'\[\s*(?:"(?:[^"\\]|\\.)*"|\d+|(?:local|var)\.[A-Za-z_][A-Za-z0-9_-]*'
               r'(?:\.[A-Za-z_][A-Za-z0-9_-]*|\[\s*(?:\d+|"(?:[^"\\]|\\.)*")\s*\])*)\s*\]')
CHAIN_TRAVERSAL = rf"{CHAIN_IDENT}(?:\s*\.\s*{CHAIN_IDENT}|\s*{CHAIN_INDEX})*"
# a for expression's key and value may also index by a bare identifier (an iteration variable, e.g. aws_subnet.x[az])
CHAIN_BODY = rf"{CHAIN_IDENT}(?:\s*\.\s*{CHAIN_IDENT}|\s*{CHAIN_INDEX}|\s*\[\s*{CHAIN_IDENT}\s*\])*"


TYPE_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[A-Za-z_][A-Za-z0-9_-]*|-?\d+(?:\.\d+)?|[(){}\[\],=:]')


def canonical_type(expr):
    """Canonical text of an HCL type constraint (object attributes sorted, layout ignored); None when absent."""
    if not isinstance(expr, str):
        return None
    text = expr.strip()
    m = re.fullmatch(r"\$\{(.*)\}", text, re.S)
    text = m.group(1) if m else text
    toks, pos = TYPE_TOKEN.findall(text), [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take(want=None):
        tok = peek()
        pos[0] += 1
        if tok is None or (want is not None and tok != want):
            raise ValueError(f"expected {want}, got {tok}")
        return tok

    def typ():
        name = take()
        if name in ("string", "number", "bool", "any"):
            return name
        if name in ("list", "set", "map"):
            take("(")
            inner = typ()
            take(")")
            return f"{name}({inner})"
        if name == "optional":
            take("(")
            inner, default, depth = typ(), [], 0
            if peek() == ",":
                take(",")
                while not (peek() == ")" and depth == 0):
                    tok = take()
                    depth += (tok in ("(", "[", "{")) - (tok in (")", "]", "}"))
                    default.append(tok)
            take(")")
            return f"optional({inner}{',' + ' '.join(default) if default else ''})"
        if name == "object":
            take("(")
            take("{")
            attrs = []
            while peek() != "}":
                key = take()
                take("=" if peek() == "=" else ":")
                attrs.append(f"{key}={typ()}")
                if peek() == ",":
                    take(",")
            take("}")
            take(")")
            return "object({" + ",".join(sorted(attrs)) + "})"
        if name == "tuple":
            take("(")
            take("[")
            items = []
            while peek() != "]":
                items.append(typ())
                if peek() == ",":
                    take(",")
            take("]")
            take(")")
            return "tuple([" + ",".join(items) + "])"
        raise ValueError(f"unknown type {name}")

    try:
        out = typ()
        if pos[0] != len(toks):
            raise ValueError("trailing tokens")
        return out
    except ValueError:
        return " ".join(text.split())


def log(msg):
    print(f"[grade] {msg}", flush=True)


def tail(text, lines=25):
    return "\n".join((text or "").strip().splitlines()[-lines:])


def run(argv, cwd=None, timeout=900, as_user=RUN_AS, home="/nonexistent"):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": home, "LANG": "C.UTF-8",
           "TF_CLI_CONFIG_FILE": TF_CLI_CONFIG, "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1",
           "TF_INPUT": "0", "AWS_EC2_METADATA_DISABLED": "true"}
    if PROXY:
        env.update(HTTPS_PROXY=PROXY, HTTP_PROXY=PROXY, https_proxy=PROXY, http_proxy=PROXY)
    prefix = ["runuser", "-u", as_user, "--"] if as_user else []
    cmd = [*prefix, "env", "-i", *[f"{k}={v}" for k, v in env.items()], *argv]
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(argv[:3])}"
    return p.returncode, p.stdout, p.stderr


def hcl2json(path, as_user=RUN_AS):
    rc, out, err = run(["hcl2json", str(path)], timeout=60, as_user=as_user)
    return (json.loads(out), None) if rc == 0 else (None, tail(err or out, 5))


# ---- small helpers ---------------------------------------------------------------------------------------------
def managed_changes(plan):
    return {rc["address"]: rc for rc in plan.get("resource_changes", []) if rc.get("mode") == "managed"}


def keys_of(address):
    return [json.loads(k) for k in KEY_RE.findall(address)]


def base_of(address):
    """aws_x.y[0] -> aws_x.y (legacy root addresses only)."""
    return re.sub(rf"{INSTANCE_KEY}$", "", address)


def is_unknown(value):
    if isinstance(value, dict):
        return any(is_unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(is_unknown(v) for v in value)
    return value is True


def unset(value):
    """A value with null, "", [] and {} all meaning "not set", so provider normalization is not a change."""
    if isinstance(value, dict):
        value = {k: v for k, v in ((k, unset(v)) for k, v in value.items()) if v is not None}
        return value or None
    if isinstance(value, list):
        value = [v for v in (unset(v) for v in value) if v is not None]
        return value or None
    return None if value == "" else value


def blank(value):
    """unset() that also treats false and 0 as unset: an attribute left at its zero default."""
    value = unset(value)
    if isinstance(value, dict):
        value = {k: v for k, v in ((k, blank(v)) for k, v in value.items()) if v is not None}
        return value or None
    if isinstance(value, list):
        value = [v for v in (blank(v) for v in value) if v is not None]
        return value or None
    return None if value is False or value == 0 else value


PROTOCOL_NUMBERS = {"tcp": "6", "udp": "17", "icmp": "1", "icmpv6": "58", "all": "-1"}
RULE_STATES = {"ENABLED": True, "DISABLED": False, "ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS": True}


def provider_forms(value):
    """value with spellings AWS treats as one written one way: a protocol by name or by number (tcp and 6), and an
    EventBridge rule's enabled state, which the stored state holds as both `state` and `is_enabled` while a plan can
    set only one of them (they conflict) and leaves the other null; configuration and state may differ there without
    any change"""
    if isinstance(value, dict):
        out = {k: (PROTOCOL_NUMBERS.get(v.lower(), v) if k in ("protocol", "ip_protocol") and isinstance(v, str)
                   else provider_forms(v)) for k, v in value.items()}
        if "state" in out and "is_enabled" in out:
            if out["is_enabled"] is None and out["state"] in RULE_STATES:
                out["is_enabled"] = RULE_STATES[out["state"]]
            elif out["state"] is None and isinstance(out["is_enabled"], bool):
                out["state"] = "ENABLED" if out["is_enabled"] else "DISABLED"
            elif out["state"] is None and out["is_enabled"] is None and (
                    "schedule_expression" in out or "event_pattern" in out):
                out["state"], out["is_enabled"] = "ENABLED", True  # neither set: AWS creates the rule enabled
        return out
    if isinstance(value, list):
        return [provider_forms(v) for v in value]
    return value


def ecs_containers(value, awsvpc=False):
    """An ECS task definition's container definitions (parsed) the way the AWS provider compares them
    (containerDefinitionsAreEquivalent): containers, environment variables and secrets in name order, essential true
    unless set, a tcp port mapping without its protocol, a zero host port unset and, under awsvpc networking, an unset
    host port equal to the container port. Empty lists are already unset by doc_form."""
    if isinstance(value, dict):  # canon() reads a one-container list as the container itself
        value = [value]
    if not isinstance(value, list):
        return value
    by_name = lambda e: str(e.get("name")) if isinstance(e, dict) else json.dumps(e, sort_keys=True)
    out = []
    for c in value:
        if isinstance(c, dict):
            c = dict(c)
            if c.get("essential") is None:
                c["essential"] = True
            for k in ("environment", "secrets"):
                if isinstance(c.get(k), list):
                    c[k] = sorted(c[k], key=by_name)
            if isinstance(c.get("portMappings"), list):
                mappings = []
                for pm in c["portMappings"]:
                    if isinstance(pm, dict):
                        pm = dict(pm)
                        if str(pm.get("protocol", "")).lower() in ("tcp", "6"):
                            pm.pop("protocol")
                        if pm.get("hostPort") in (0, None):
                            pm.pop("hostPort", None)
                        if awsvpc and "hostPort" not in pm and "containerPort" in pm:
                            pm["hostPort"] = pm["containerPort"]
                    mappings.append(pm)
                c["portMappings"] = mappings
        out.append(c)
    return sorted(out, key=by_name)


def doc_form(value, attr="", owner=None):
    """A value as AWS reads it, for comparing one setting with another: JSON documents parsed (member order is not
    meaning), null, "", [] and {} parts unset, the provider's alternative spellings unified (provider_forms), and an
    ECS task definition's container definitions normalized the way the provider compares them (owner, the resource's
    attributes, tells whether it uses awsvpc networking). The plan shows a configuration's own text for a resource it
    creates or replaces, so text that differs only where the provider sees no difference is not a different value."""
    value = provider_forms(unset(jsonish(value)))
    if str(attr).split(".")[-1] == "container_definitions" and value is not None:
        value = ecs_containers(value, isinstance(owner, dict) and owner.get("network_mode") == "awsvpc")
    return value


def changed_attrs(rc):
    """Attributes an update really changes (null/empty normalization and re-computed unset attributes excluded)."""
    change = rc["change"]
    before, after, unknown = change.get("before") or {}, change.get("after") or {}, change.get("after_unknown") or {}
    before, after = provider_forms(before), provider_forms(after)
    changed = {}
    for k in set(before) | set(after) | set(unknown):
        if is_unknown(unknown.get(k)):
            if unset(before.get(k)) is not None:
                changed[k] = f"{before.get(k)!r} -> (known after apply)"
        elif doc_form(before.get(k), k, before) != doc_form(after.get(k), k, after):
            changed[k] = f"{before.get(k)!r} -> {after.get(k)!r}"
    return changed


def swap(text, old, new):
    return re.sub(rf"(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])", new, text)


def swap_deep(value, old, new):
    if isinstance(value, dict):
        return {k: swap_deep(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [swap_deep(v, old, new) for v in value]
    return swap(value, old, new) if isinstance(value, str) else value


def same_value(a, b):
    """Equal defaults: maps and lists exactly, scalars by value (2 and "2" are the same number)."""
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return a == b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def same_name(got, want):
    """equal, or one is the ARN that ends in the other: AWS stores some name arguments (an event source mapping's
    function_name) as the ARN even when the configuration passes the bare name"""
    if got == want:
        return True
    if isinstance(got, str) and isinstance(want, str):
        return any(a.startswith("arn:") and re.split(r"[:/]", a)[-1] == b for a, b in ((got, want), (want, got)))
    return False


def swap_problems(before, after, unknown, old, new, path=""):
    """For a value that must follow a rename: (paths whose known text keeps the old token or lost some of it, paths this
    plan does not know yet). Maps are compared key by key, so a known leaf is checked even when a sibling is unknown;
    anything else is compared as text: no old token may remain, and at least as many new tokens must appear as there
    were old ones (normalization-proof, unlike comparing documents)."""
    word = lambda tok: re.compile(rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])")
    where = path or "the value"
    if unknown is True:
        return [], [where]
    if isinstance(before, dict) and isinstance(after, dict):
        bad, later = [], []
        for k in before:
            b, l = swap_problems(before[k], after.get(k), unknown.get(k) if isinstance(unknown, dict) else None, old, new,
                                 f"{path}.{k}" if path else k)
            bad, later = bad + b, later + l
        return bad, later
    text_before = before if isinstance(before, str) else json.dumps(before)
    text_after = after if isinstance(after, str) else json.dumps(after)
    if word(old).search(text_after):  # unknown leaves are null in the plan, so this reads the known parts only
        return [where], []
    if is_unknown(unknown):  # a list with unknown elements: the count needs the whole value
        return [], [where]
    if len(word(new).findall(text_after)) < len(word(old).findall(text_before)):
        return [where], []
    return [], []


def jsonish(value):
    """value with JSON-document strings parsed, so that object member order does not count as a difference"""
    if isinstance(value, str) and value.strip()[:1] in ("{", "["):
        try:
            return jsonish(json.loads(value))
        except ValueError:
            return value
    if isinstance(value, dict):
        return {k: jsonish(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonish(v) for v in value]
    return value


def canon(value):
    """A value as a document: JSON strings parsed, key order and list order ignored, a one-element list the same as its
    element, and unset parts (null, "", [], {}) dropped."""
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("{", "["):
            try:
                return canon(json.loads(text))
            except ValueError:
                pass
        return value
    if isinstance(value, dict):
        return {k: c for k, c in ((k, canon(v)) for k, v in value.items()) if c not in (None, "", [], {})}
    if isinstance(value, list):
        items = sorted((canon(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
        return items[0] if len(items) == 1 else items
    return value


def known_part(value, unknown):
    """value without the parts the plan does not know (None when none of it is known)"""
    if unknown is True:
        return None
    if isinstance(value, dict):
        u = unknown if isinstance(unknown, dict) else {}
        return {k: known_part(v, u.get(k)) for k, v in value.items() if u.get(k) is not True}
    if isinstance(value, list):
        u = unknown if isinstance(unknown, list) else []
        return [known_part(v, u[i] if i < len(u) else None) for i, v in enumerate(value) if not (i < len(u) and u[i] is True)]
    return value


def covers(got, want):
    """every part of want (a canon() document) appears in got"""
    if isinstance(want, dict):
        return isinstance(got, dict) and all(k in got and covers(got[k], v) for k, v in want.items())
    if isinstance(want, list):
        pool = list(got) if isinstance(got, list) else [got]
        for w in want:
            hit = next((i for i, g in enumerate(pool) if covers(g, w)), None)
            if hit is None:
                return False
            pool.pop(hit)
        return True
    if isinstance(got, list):
        return any(covers(g, want) for g in got)
    return got == want


def order_problem(got, want, today, path=""):
    """Where got's lists lose the order of today's parts: in every list of the (parsed) documents, the elements that
    exist today must keep today's order or come in the order the reference puts them in (a priority probe reorders
    them; a reference may also rebuild a list in key order where AWS does not care); a new element may sit anywhere.
    The path of the first list out of order, else None. canon() ignores list order, so a collector rebuilt in some
    other order (sorted, say) would otherwise match."""
    if isinstance(got, dict) and isinstance(want, dict):
        today = today if isinstance(today, dict) else {}
        for k in sorted(set(got) & set(want)):
            p = order_problem(got[k], want[k], today.get(k), f"{path}.{k}" if path else k)
            if p:
                return p
        return None
    if isinstance(got, list) and isinstance(want, list):
        if isinstance(today, list) and today:
            key = lambda e: json.dumps(canon(e), sort_keys=True)
            now = [key(e) for e in today]
            if [key(e) for e in want] == now:
                # the reference leaves this list exactly as it is today, so it collects nothing here: the document's own
                # semantics apply (an IAM statement's Action list may come in any order), and where order is meaning to
                # the provider (a string attribute) the moves-only plan has already pinned today's order
                return None
            g, w = [key(e) for e in got if key(e) in now], [key(e) for e in want if key(e) in now]
            kept = [k for k in now if k in g]  # today's order of the parts got keeps
            if sorted(g) == sorted(w) and g != w and g != kept:
                return path or "the list"
        if len(got) == len(want):
            t = today if isinstance(today, list) and len(today) == len(got) else [None] * len(got)
            for i, (a, b) in enumerate(zip(got, want)):
                p = order_problem(a, b, t[i], f"{path}[{i}]")
                if p:
                    return p
    return None


def expect_problem(got, want, owner=None):
    """None when a planned value meets a probe's expect entry, else what is wrong (from the attribute on): "value" must
    be equal as AWS reads it (doc_form), "contains" must appear in the planned string (one part or a list of parts)."""
    attr = want["attr"]
    if "contains" in want:
        parts = want["contains"] if isinstance(want["contains"], list) else [want["contains"]]
        if isinstance(got, str) and all(str(p) in got for p in parts):
            return None
        return f"{attr} = {got!r}, expected it to contain {', '.join(repr(str(p)) for p in parts)}"
    if doc_form(got, attr, owner) == doc_form(want.get("value"), attr, owner):
        return None
    return f"{attr} = {got!r}, expected {want.get('value')!r}"


def short(value, n=180):
    text = value if isinstance(value, str) else json.dumps(value)
    return repr(text[:n] + ("..." if len(text) > n else ""))


def list_affixes(today, sep):
    """The text around today's list when the list sits inside a sentence ("valid: /a/*, /b/* paths."): what comes
    before its first part and after its last one, cut at whitespace. Empty for a string that is only the list, and for
    a list that is itself separated by whitespace."""
    if not sep.strip():
        return "", ""
    first, last = today.find(sep), today.rfind(sep)
    if first < 0:
        return "", ""
    head_end = max(today.rfind(" ", 0, first), today.rfind("\n", 0, first)) + 1
    starts = [i for i in (today.find(" ", last + len(sep)), today.find("\n", last + len(sep))) if i >= 0]
    return today[:head_end], (today[min(starts):] if starts else "")


def field_match(mine, after, before):
    """For KEY=value fields (a ';'-separated configuration string): True when every field holds want's value, a field
    that collects parts (scheduled_jobs=a,b,c) compared as a delimited list; None when the parts are not aligned
    KEY=value fields."""
    if not (len(mine) == len(after) == len(before)) or len(after) < 2:
        return None
    rows = [(m.partition("="), a.partition("="), b.partition("=")) for m, a, b in zip(mine, after, before)]
    if not all(m[1] and a[1] and b[1] and m[0].strip() == a[0].strip() == b[0].strip() for m, a, b in rows):
        return None
    return all(m[2] == a[2] or delimited_match(m[2], a[2], b[2]) is True for m, a, b in rows)


def delimited_match(got, want, today):
    """For a delimited string that collects one part per key (a comma-joined list of services, say): None if the
    separator does not apply, else whether got holds exactly want's parts, with today's surviving parts in today's
    order. The statement fixes what is taken in or dropped and that the rest stays as it is, but not where a new part
    goes, so an added part may sit anywhere: also first in a ", "-separated list, inside a sentence whose text before
    and after the list stays put, in a '|'-separated list, and in a list inside one KEY=value field of a string."""
    if not all(isinstance(v, str) for v in (got, want, today)):
        return None
    applies = False
    for sep in (", ", ",", "; ", ";", " | ", "|", " ", "\n"):
        head, tail = list_affixes(today, sep)
        if not all(s.startswith(head) and s.endswith(tail) and len(s) >= len(head) + len(tail) for s in (got, want)):
            head, tail = "", ""
        core = lambda s: s[len(head):len(s) - len(tail)]
        cores = [core(today), core(want), core(got)]
        for q in ('"', "'"):  # a quote every value opens or closes the list with is text around it, not part of a part
            if all(c.endswith(q) for c in cores):
                cores = [c[:-1] for c in cores]
            if all(c.startswith(q) for c in cores):
                cores = [c[1:] for c in cores]
        before, after, mine = (c.split(sep) for c in cores)
        fields = field_match(mine, after, before)
        if fields is not None:
            return fields
        if len(before) < 2:
            continue
        if sorted(before) == sorted(after):
            if after == before:
                continue  # want keeps today's list as it is: nothing for this rule to judge
            # want only reorders today's parts (a priority probe, a list rebuilt in key order): today's order or the
            # reference's, as order_problem allows for lists in documents, never a third order (eks-q-business v2:
            # the reference re-sorted a comma-joined collector by an undisclosed priority, a kept order failed)
            applies = True
            if sorted(mine) != sorted(after):
                continue
            return mine in (before, after)
        added = [p for p in after if p not in before]
        dropped = [p for p in before if p not in after]
        if not added and not dropped:
            continue
        if sorted(p for p in after if p not in added) != sorted(p for p in before if p not in dropped):
            continue  # want is not today with parts added or dropped: not this separator
        applies = True
        if sorted(mine) != sorted(after):
            continue  # other parts here: perhaps a list nested in fields that another separator splits
        kept = [p for p in before if p not in dropped]
        return [p for p in mine if p in kept] == kept  # the right parts: today's must keep today's order
    return False if applies else None


def nested_delimited_match(got, want, today):
    """delimited_match applied inside documents: True when got and want have the same shape and every leaf where
    they differ is a delimited string that delimited_match accepts against today's leaf there (a comma-joined list
    of buckets inside a Lambda's environment variables, say); None when that rule does not apply."""
    if isinstance(got, dict) and isinstance(want, dict):
        if set(got) != set(want):
            return None
        today = today if isinstance(today, dict) else {}
        results = [nested_delimited_match(got[k], want[k], today.get(k)) for k in got]
    elif isinstance(got, list) and isinstance(want, list):
        if len(got) != len(want):
            return None
        today = today if isinstance(today, list) else []
        results = [nested_delimited_match(g, w, today[i] if i < len(today) else None)
                   for i, (g, w) in enumerate(zip(got, want))]
    else:
        return True if got == want else delimited_match(got, want, today)
    if any(r is False for r in results):
        return False
    return True if all(r is True for r in results) else None


def b64_text(value):
    """the text of a base64-encoded script (launch template user data), or None"""
    if not isinstance(value, str) or len(value) < 8:
        return None
    try:
        text = base64.b64decode(value, validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    return text if "=" in text or "\n" in text else None


def b64_json(value):
    """the document in base64-encoded JSON (launch template user data that holds a JSON document), or None"""
    if not isinstance(value, str) or len(value) < 8:
        return None
    try:
        text = base64.b64decode(value, validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    if text.strip()[:1] not in ("{", "["):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def decoded(value):
    """a base64-encoded script (launch template user data) as its text, so a rename can be checked inside it; any
    other value unchanged"""
    text = b64_text(value)
    return value if text is None else text


def script_delimited_match(got, want, today):
    """delimited_match for KEY=a,b,c lines of base64 user data: True when the scripts differ only in such lines and
    each differing line holds want's parts with today's parts in today's order; None when the rule does not apply"""
    g, w, now = b64_text(got), b64_text(want), b64_text(today)
    if g is None or w is None or now is None:
        return None
    got_lines, want_lines = g.splitlines(), w.splitlines()
    if len(got_lines) != len(want_lines):
        return None
    today_values = {}
    for line in now.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            today_values.setdefault(key, value)
    for a, b in zip(got_lines, want_lines):
        if a == b:
            continue
        ka, sa, va = a.partition("=")
        kb, sb, vb = b.partition("=")
        if not (sa and sb and ka == kb and ka in today_values):
            return False
        if delimited_match(va, vb, today_values[ka]) is not True:
            return False
    return True


def value_mismatch(got, want, today, attr="", owner=None, removing=False):
    """None when an attribute's value in this plan (got) agrees with the reference solution's plan (want), else why not.
    Both are {"after", "unknown"} from a plan; today is the attribute's value in the state. ECS container definitions
    known in full are compared the way the provider compares them (owner: the resource's attributes). removing: the
    probe drops a key, so a value may only lose parts of today's."""
    gu, wu = got.get("unknown"), want.get("unknown")
    if str(attr).split(".")[-1] == "container_definitions" and not is_unknown(gu) and not is_unknown(wu):
        got, want = ({**v, "after": doc_form(v.get("after"), attr, owner)} for v in (got, want))
    if wu is True:  # the reference's value reads what the probe creates or deletes, so its plan cannot know it
        if gu is True:
            return None
        g = canon(got.get("after"))
        if g == canon(today):
            return None  # unchanged: whether it has to change is the required-updates rule's business
        if removing:  # a removal (the reference's policy document data source is read at apply, say): known here,
            if covers(canon(today), g):  # it may only drop parts of today's value, the removed key's
                return None
            return f"= {short(got.get('after'))}: removing a key may only drop parts of today's value"
        if covers(g, canon(today)):
            return None  # known here (built without reading the new resources), keeping everything it had
        return f"= {short(got.get('after'))}: it must keep every part of today's value and take in the change"
    if gu is True:
        return None  # the reference knows it, this plan does not: nothing to compare
    gj, wj = b64_json(got.get("after")), b64_json(want.get("after"))
    if gj is not None and wj is not None and not is_unknown(gu) and not is_unknown(wu):
        # base64 user data holding a JSON document: compared as that document (member order free, collector lists by
        # the order rule), not byte for byte; compact JSON has no "=" or newline for the KEY=value script rule
        tj = b64_json(today)
        return value_mismatch({"after": gj, "unknown": gu}, {"after": wj, "unknown": wu}, today if tj is None else tj,
                              attr, owner, removing)
    g, w = canon(known_part(got.get("after"), gu)), canon(known_part(want.get("after"), wu))
    if not is_unknown(gu) and not is_unknown(wu):
        if g == w:
            if policy_doc(got.get("after")) is not None and policy_doc(want.get("after")) is not None:
                return None  # the same statements and elements: their order means nothing in a policy document
            where = order_problem(jsonish(got.get("after")), jsonish(want.get("after")), jsonish(today))
            if where is None:
                return None
            return (f"= {short(got.get('after'))}, expected {short(want.get('after'))} (the same parts, but today's "
                    f"parts must keep their order: {where})")
        parts = delimited_match(got.get("after"), want.get("after"), today)
        if parts is None and isinstance(got.get("after"), (dict, list)):
            parts = nested_delimited_match(jsonish(got.get("after")), jsonish(want.get("after")), jsonish(today))
        if parts is None and isinstance(got.get("after"), str):
            parts = script_delimited_match(got.get("after"), want.get("after"), today)
        if parts is True:
            return None
        return f"= {short(got.get('after'))}, expected {short(want.get('after'))}" + (
            " (the same parts, with today's parts in today's order)" if parts is False else "")
    # the reference has unknown parts: everything it knows must be here; only this plan has some: all it knows must fit
    if covers(g, w) if is_unknown(wu) else covers(w, g):
        return None
    return f"= {short(got.get('after'))}, expected {short(want.get('after'))} (on the parts both plans know)"


UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
CLOUD_ID = re.compile(r"\b([a-z]+)-([0-9a-f]{6,})\b")


def stand_in(like, seed, rename=None):
    """A value for a new resource's attribute the plan cannot know, in the counterpart's shape: derived from the key
    when the counterpart's value carries it (names, named ARNs), a fresh token where it carries a cloud-assigned id
    (subnet-0abc..., a UUID), and otherwise the counterpart's own value (an enum, a default or an empty setting is
    valid for the new resource too, and the provider validates it)."""
    if not isinstance(like, str) or like == "":
        return like
    renamed = rename(like) if rename else like
    if renamed != like:
        return renamed
    digest = hashlib.sha1(seed.encode()).hexdigest()
    out = CLOUD_ID.sub(lambda m: f"{m.group(1)}-{digest[:len(m.group(2))]}", like)
    out = UUID.sub(lambda m: f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}", out)
    return out


def filled(after, unknown, like, seed, standins=None, rename=None):
    """after with every unknown leaf replaced by a stand-in fixed by seed and the leaf's path; standins records each
    invented token (a fresh id) against the counterpart's value there, so filled values can be read back as the
    counterpart's"""
    if unknown is True:
        value = stand_in(like, seed, rename)
        if standins is not None and isinstance(value, str) and isinstance(like, str) and value != like and (
                not rename or value != rename(like)):
            standins[value] = rename(like) if rename else like
        return value
    if isinstance(unknown, dict):
        after = after if isinstance(after, dict) else {}
        like = like if isinstance(like, dict) else {}
        keys = set(after) | {k for k, v in unknown.items() if is_unknown(v)}
        return {k: filled(after.get(k), unknown.get(k), like.get(k), f"{seed}.{k}", standins, rename)
                for k in sorted(keys)}
    if isinstance(unknown, list):
        after = after if isinstance(after, list) else []
        like = like if isinstance(like, list) else []
        return [filled(after[i] if i < len(after) else None, unknown[i] if i < len(unknown) else None,
                       like[i] if i < len(like) else (like[0] if like else None), f"{seed}[{i}]", standins, rename)
                for i in range(max(len(after), len(unknown)))]
    return after


def policy_doc(value):
    """an IAM-grammar policy document (identity, resource, bucket, key, queue or topic policy), parsed, or None: AWS and
    the provider treat its Statement list and the lists inside a statement as unordered, and so does the grader
    (laravel-fargate r1001-211620 and sample-automate r1002-061118: reordered statements, a provider no-op, failed the
    add/remove probes)"""
    value = jsonish(value)
    return value if isinstance(value, dict) and "Statement" in value else None


def scalar_sets(value):
    """lists of plain values in one canonical order: once stand-ins are read back as the counterpart's values, a set's
    elements (subnet IDs, ARNs) need not come out in the order the provider sorted the stand-ins"""
    if isinstance(value, dict):
        return {k: scalar_sets(v) for k, v in value.items()}
    if isinstance(value, list):
        items = [scalar_sets(v) for v in value]
        if all(not isinstance(v, (dict, list)) for v in items):
            return sorted(items, key=json.dumps)
        return items
    return value


def read_path(literal, d, root):
    """the file or directory a literal path argument names ('"${path.module}/x")', a bare root path, a leading ./), or
    None when it would leave the root directory"""
    s = literal.strip().rstrip(",)").strip().strip('"')
    s = s[2:] if s.startswith("./") else s
    base = root
    for prefix, where in (("${path.module}/", d), ("${path.root}/", root)):
        if s.startswith(prefix):
            base, s = where, s[len(prefix):]
    p = (base / s).resolve()
    return p if p == root or root in p.parents else None


def changed_leaves(before, after, unknown, path=""):
    """the leaf paths (".x[0].y") where a nested value changed to something known; an unknown leaf (a consequence of a
    replacement) and blank-for-blank (null, "", [], {}) are not changes"""
    if unknown is True:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for k in sorted(set(before) | set(after)):
            out += changed_leaves(before.get(k), after.get(k), unknown.get(k) if isinstance(unknown, dict) else None,
                                  f"{path}.{k}")
        return out
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        out = []
        for i, (b, a) in enumerate(zip(before, after)):
            out += changed_leaves(b, a, unknown[i] if isinstance(unknown, list) and i < len(unknown) else None,
                                  f"{path}[{i}]")
        return out
    return [] if blank(before) == blank(after) or same_value(before, after) else [path]


def nested_tags(value, path=""):
    """(path, tags) for every tag map in a resource's nested blocks (root_block_device[0].tags, say); the top-level tags,
    the Auto Scaling Group `tag` set and launch-template tag_specifications are checked on their own"""
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "tags" and path:
                if isinstance(v, dict) and v:
                    yield f"{path}.tags", v
            elif k not in ("tags", "tags_all", "tag", "tag_specifications") and isinstance(v, (dict, list)):
                yield from nested_tags(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from nested_tags(v, f"{path}[{i}]")


def at_path(value, path):
    """the value at a nested_tags path in another document of the same shape, or None"""
    for part in re.findall(r"\[\d+\]|[^.\[\]]+", path):
        if part.startswith("["):
            i = int(part[1:-1])
            value = value[i] if isinstance(value, list) and i < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
        if value is None:
            return None
    return value


def user_data_entries(probe):
    """a rename probe's user-data lines: one entry, or a list of them (one per launch template that writes the token)"""
    entries = probe.get("user_data") or []
    return entries if isinstance(entries, list) else [entries]


def translate(value, standins):
    """value with every stand-in replaced by what the counterpart has there"""
    if isinstance(value, str):
        for s, r in standins.items():
            if s in value:
                value = value.replace(s, r if isinstance(r, str) else json.dumps(r))
        return value
    if isinstance(value, dict):
        return {k: translate(v, standins) for k, v in value.items()}
    if isinstance(value, list):
        return [translate(v, standins) for v in value]
    return value


def split_address(address):
    """module.a.module.b.aws_x.y["k"] -> ("module.a.module.b", "aws_x", "y", "k")"""
    m = re.fullmatch(r'(.*)\[("(?:[^"\\]|\\.)*"|\d+)\]', address)
    rest, key = (m.group(1), json.loads(m.group(2))) if m else (address, None)
    parts = rest.split(".")
    return ".".join(parts[:-2]), parts[-2], parts[-1], key


def dig(value, path):
    """value at a dotted path with list indexes, e.g. rule[0].expiration[0].days; None when absent."""
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            i = int(part[1:-1])
            value = value[i] if isinstance(value, list) and i < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
    return value


def tag_set(tags):
    return {(t.get("key"), t.get("value"), t.get("propagate_at_launch")) for t in tags or []}


def spec_tags(specs):
    return {s.get("resource_type"): s.get("tags") or {} for s in specs or []}


def strings_of(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from strings_of(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_of(v)
    elif isinstance(value, str):
        yield value


def walk_config(module):
    for r in module.get("resources", []):
        yield "resource", r.get("address"), r
    for name, call in module.get("module_calls", {}).items():
        yield "module", name, call
        yield from walk_config(call.get("module", {}))


def config_address(address):
    path = tuple(re.findall(rf"(?:^|\.)module\.([A-Za-z0-9_-]+)(?:{INSTANCE_KEY})?(?=\.)", address))
    resource = re.sub(rf"^(?:module\.[A-Za-z0-9_-]+(?:{INSTANCE_KEY})?\.)+", "", address)
    return path, re.sub(rf"{INSTANCE_KEY}$", "", resource)


def configured_fields(plan):
    found = {}

    def walk(module, path):
        for r in module.get("resources", []):
            found[(path, r.get("address"))] = set((r.get("expressions") or {}).keys())
        for name, call in module.get("module_calls", {}).items():
            walk(call.get("module", {}), path + (name,))

    walk(plan.get("configuration", {}).get("root_module", {}), ())
    return found


# ---- workspace -------------------------------------------------------------------------------------------------
class Workspace:
    """A scratch copy of the artifact, owned by the unprivileged grading user; the state lives next to it."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="grade-"))
        os.chmod(self.root, 0o755)
        self.infra, self.home = self.root / "infra", self.root / "home"
        self.state = self.root / "state" / "terraform.tfstate"
        self.home.mkdir()
        self.skipped_links = []

    def populate(self):
        for dirpath, dirnames, filenames in os.walk(ARTIFACT):
            rel = Path(dirpath).relative_to(ARTIFACT)
            kept = []
            for name in dirnames:
                if name in SKIP_DIRS:
                    continue
                if Path(dirpath, name).is_symlink():
                    self.skipped_links.append(str(rel / name))
                    continue
                kept.append(name)
            dirnames[:] = kept
            (self.infra / rel).mkdir(parents=True, exist_ok=True)
            for name in filenames:
                src = Path(dirpath, name)
                if src.is_symlink():
                    self.skipped_links.append(str(rel / name))
                elif src.is_file() and not SKIP_FILE.search(name):
                    shutil.copyfile(src, self.infra / rel / name)
        self.infra.mkdir(exist_ok=True)
        self.state.parent.mkdir()
        shutil.copyfile(TESTS / "pristine.tfstate", self.state)
        shutil.copyfile(TESTS / "terraform.lock.hcl", self.infra / ".terraform.lock.hcl")
        shutil.copytree(TESTS / "policies", self.root / "policies")
        self.own(self.root)

    def own(self, path):
        if RUN_AS:
            subprocess.run(["chown", "-R", RUN_AS, str(path)], check=True)

    def tf(self, *args, timeout=900):
        return run(["terraform", *args], cwd=self.infra, timeout=timeout, home=str(self.home))

    def write(self, name, data):
        path = self.infra / name
        path.write_text(json.dumps(data))
        self.own(path)
        return name

    def plan(self, name, *args, state=None):
        rc, out, err = self.tf("plan", "-refresh=false", "-input=false", "-lock=false", "-no-color",
                               f"-state={state or self.state}", f"-out={name}.tfplan", *args)
        if rc != 0:
            return None, tail(err or out)
        rc, out, err = self.tf("show", "-json", "-no-color", f"{name}.tfplan")
        if rc != 0:
            return None, tail(err or out)
        return json.loads(out), None


def fake_token(match, legacy_text):
    """a stand-in of the same shape for one random part of a cloud-assigned value (the same one every time)"""
    token = match.group(0)
    if token in legacy_text:  # a constant the configuration itself spells out (e.g. the account ID in an ARN)
        return token
    ip = IPV4.fullmatch(token)
    for salt in range(100):
        seed = hashlib.sha256(f"{salt}:{token.replace('-', '.') if ip else token}".encode()).digest()
        if ip:
            fake = ip.group(1).join(str(o) for o in (100 + seed[0] % 100, seed[1], seed[2], 1 + seed[3] % 254))
            if fake != token:
                return fake
            continue
        out = []
        for i, ch in enumerate(token):
            b = seed[i % len(seed)] + i
            out.append(str(b % 10) if ch.isdigit() else "abcdef"[b % 6] if ch in "abcdef"
                       else chr(65 + b % 26) if ch.isupper() else chr(97 + b % 26) if ch.islower() else ch)
        if "".join(out) != token:
            return "".join(out)
    return token


# ---- the pristine state ----------------------------------------------------------------------------------------
class Pristine:
    def __init__(self, path):
        state = self.state = json.loads(path.read_text())
        self.res = {}
        for block in state["resources"]:
            if block.get("mode") != "managed" or block.get("module"):
                continue
            base = f'{block["type"]}.{block["name"]}'
            for inst in block["instances"]:
                key = inst.get("index_key")
                suffix = "" if key is None else f"[{key}]" if isinstance(key, int) else f"[{json.dumps(key)}]"
                self.res[base + suffix] = {"type": block["type"], "base": base, "attrs": inst["attributes"],
                                           "schema_version": inst.get("schema_version", 0), "provider": block.get("provider")}

    def attr(self, legacy, field):
        return self.res[legacy]["attrs"][field]

    def generated_values(self, legacy_text):
        found = set()

        def walk(key, value, names):
            if isinstance(value, dict):
                for k, v in value.items():
                    walk(k, v, names)
            elif isinstance(value, list):
                for v in value:
                    walk(key, v, names)
            elif (isinstance(value, str) and key and ID_KEY.search(key) and key != "availability_zone_id"
                  and len(value) >= 7 and value not in legacy_text and value not in names
                  and not AWS_OWNED_ARN.match(value)):  # arn:aws:iam::aws:policy/...: published, not this stack's
                found.add(value)

        for r in self.res.values():
            names = {v for k, v in r["attrs"].items() if isinstance(v, str) and not ID_KEY.search(k)}
            walk(None, r["attrs"], names)
        return found

    def id_tokens(self, legacy_text):
        """The random parts of today's cloud-assigned values that the configuration does not spell out (the hex of an
        ID or an ARN, an account number), each standing alone between separators. A value holding one carries part of
        an identifier even when it is not a whole one: an ALB's arn_suffix, or an alarm dimension or URL built from it."""
        tokens = set()
        for value in self.generated_values(legacy_text):
            for m in TOKEN.finditer(value):
                token, a, b = m.group(0), m.start(), m.end()
                if (token not in legacy_text and (a == 0 or not value[a - 1].isalnum())
                        and (b == len(value) or not value[b].isalnum())):
                    tokens.add(token)
        return tokens

    def token_fakes(self, legacy_text):
        """random part -> the stand-in random_values gives it inside every whole value"""
        fakes = {}
        for token in self.id_tokens(legacy_text):
            fake = TOKEN.sub(lambda m: fake_token(m, legacy_text), token)
            if fake != token:
                fakes[token] = fake
        return fakes

    def random_values(self, legacy_text):
        endpoint_values = {v for r in self.res.values() for k, v in r["attrs"].items()
                           if isinstance(v, str) and ENDPOINT_KEY.search(k)}

        fakes = {}
        for value in self.generated_values(legacy_text):
            fake = TOKEN.sub(lambda m: fake_token(m, legacy_text), value)
            if fake == value and value in endpoint_values and "." in value:  # a non-random DNS name (moto's ALB DNS)
                head, sep, rest = value.partition(".")
                fake = f"{head}-r{hashlib.sha256(value.encode()).hexdigest()[:6]}{sep}{rest}"
            if fake != value:
                fakes[value] = fake
        return fakes

    def remapped(self, fakes, token_fakes=None):
        """the state with every whole cloud-assigned value swapped for its stand-in, then every remaining standalone
        random part of one (an arn_suffix, a dimension or URL built from it) for the same part's stand-in"""
        token_fakes = token_fakes or {}
        whole = re.compile("|".join(re.escape(v) for v in sorted(fakes, key=len, reverse=True))) if fakes else None
        part = token_pattern(token_fakes)

        def swap_text(text):
            text = whole.sub(lambda m: fakes[m.group(0)], text) if whole else text
            return part.sub(lambda m: token_fakes[m.group(0)], text) if part else text

        def walk(value):
            if isinstance(value, dict):
                return {k: walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [walk(v) for v in value]
            return swap_text(value) if isinstance(value, str) else value

        return walk(self.state)

    def renamed(self, old, new):
        """A copy of the state in which every attribute and output already carries the new token, as if the rename had
        been applied: planning the renamed configuration against it replaces nothing, so values that read renamed
        resources are known."""
        state = json.loads(json.dumps(self.state))
        for block in state.get("resources", []):
            for inst in block.get("instances", []):
                inst["attributes"] = swap_deep(inst.get("attributes") or {}, old, new)
        for out in (state.get("outputs") or {}).values():
            out["value"] = swap_deep(out.get("value"), old, new)
        return state

    def old_names(self, old, legacy_args):
        """Today's names that contain the old token and are distinctive enough to look for elsewhere."""
        found = set()
        for r in self.res.values():
            attrs = r["attrs"]
            values = [attrs.get(f) for f in name_fields(r["type"], legacy_args.get(r["base"], ()))]
            values += [attrs.get("id")] if attrs.get("id") in values else []
            found |= {v for v in values if isinstance(v, str) and swap(v, old, "\0") != v and len(v) >= len(old) + 3}
        return found


# ---- the grader ------------------------------------------------------------------------------------------------
class Grader:
    def __init__(self, spec):
        self.spec = spec
        self.gates, self.checks = {}, {}
        self.ws = Workspace()
        self.pristine = Pristine(TESTS / "pristine.tfstate")
        trusted = sorted(p for p in (TESTS / "trusted").rglob("*") if p.is_file() and p.suffix in (".tf", ".tpl"))
        self.legacy_text = "\n".join(p.read_text() for p in trusted)
        self.legacy_args = {}  # "type.name" -> top-level arguments the trusted legacy configuration sets
        for p in trusted:
            if p.suffix == ".tf":
                doc, err = hcl2json(p, as_user="")
                if doc is None:
                    raise RuntimeError(f"cannot parse the trusted {p.name}: {err}")
                for rtype, named in doc.get("resource", {}).items():
                    for rname, bodies in named.items():
                        self.legacy_args.setdefault(f"{rtype}.{rname}", set()).update(*(set(b) for b in bodies))
        self.plan, self.new_of, self.docs = None, {}, {}
        self.read_files = set()  # files and directories the configuration reads (file functions, archive_file sources)
        self.filled_errors = {}  # key_add probe -> why its plan with the new resources in the state failed
        for name, attrs in spec.get("name_attrs", {}).items():
            NAME_ATTRS[name] = attrs

    def gate(self, name, ok, detail=""):
        self.gates