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
import random
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
NOT_NAMES = {"device_name", "virtual_name", "metric_name"}  # /dev/sdf, ephemeral0, CPUUtilization: not resource names


def name_fields(rtype, legacy_args=()):
    """Name attributes of a resource: the known ones for its type plus every name-shaped argument that the trusted
    legacy configuration sets for it (so dropping an argument cannot hide a stale name)."""
    return set(NAME_ATTRS.get(rtype, [])) | {k for k in legacy_args if GENERIC_NAME.match(k) and not ID_KEY.search(k)
                                             and k not in NOT_NAMES}


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
RESOURCE_REF = re.compile(r"\b(?:module|data)\.|\b[a-z0-9]+_[a-z0-9_]+\.[A-Za-z_][A-Za-z0-9_-]*[.\[]")  # type.name. / type.name[
AWS_OWNED_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:aws:")


def token_pattern(tokens):
    """one regex for standalone occurrences of any of the tokens (not inside a longer run of letters and digits)"""
    if not tokens:
        return None
    return re.compile(r"(?<![0-9A-Za-z])(?:" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
                      + r")(?![0-9A-Za-z])")


KEY_PROBES = ("key_add", "key_remove", "key_update")
AZ_KEY = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d+[a-z]$")


def fresh_key(key, existing, salt):
    """A key no configuration can list in advance, shaped like the probe's own add key (so it is a valid name wherever
    that one is): after the prefix every key of the dimension shares, characters are redrawn from the task's hidden salt
    - lowercase for lowercase, uppercase for uppercase, digit for digit, separators kept - and the new key sorts among
    today's keys where the add key does (a task may make the first or last key the primary one, and the reference's plan
    under the fresh key must stay comparable). An availability zone keeps its region and gets an unused zone letter."""
    if not isinstance(key, str) or not salt:
        return None
    keys = [k for k in existing if isinstance(k, str)]
    taken = set(keys) | {key}
    rank = sum(1 for k in keys if k < key)
    prefix = os.path.commonprefix(keys + [key]) if keys else ""
    tail = key[len(prefix):] or key
    head = key[:len(key) - len(tail)]
    rnd = random.Random(int(hashlib.sha256(f"{salt}|{key}".encode()).hexdigest(), 16))

    def ranked(new):
        return new not in taken and sum(1 for k in keys if k < new) == rank

    def redraw(text):
        return "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") if c.islower() else
                       rnd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") if c.isupper() else
                       rnd.choice("0123456789") if c.isdigit() else c for c in text)
    if AZ_KEY.match(key) and len(tail) == 1 and tail.islower():
        for pool in ("abcdef", "ghijklmnopqrstuvwxyz"):
            letters = [c for c in pool if ranked(head + c)]
            if letters:
                return head + rnd.choice(letters)
        return None
    for keep in range(len(tail)):  # keep as little of the add key as the sort position needs
        for _ in range(80):
            new = head + tail[:keep] + redraw(tail[keep:])
            if ranked(new):
                return new
    return None


PATH_ARGS = {"filename", "source", "source_file", "source_dir", "path", "template"}
FILE_DATA = ("local_file", "local_sensitive_file", "template_file")


def expression_segments(text):
    """the HCL expressions inside a parsed string (hcl2json keeps them as "${...}", nested ones included); the plain
    text around them - a description, a tag value - is data, not code (r1006-103819)"""
    out, i = [], 0
    while True:
        start = text.find("${", i)
        if start < 0:
            return out
        depth, j = 0, start + 1
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(text[start + 2:j])
        i = j + 1


ARTIFACT_PART = re.compile(r"^\.terraform($|\.)|\.tfstate($|\.)|\.tfplan($|\.)")


def artifact_path(path):
    """a path naming a Terraform state or plan file (terraform.tfstate, *.tfstate.backup, terraform.tfstate.d, *.tfplan)
    or entering .terraform, judged by path component: a template called tfstate-policy.tpl or a directory named after a
    state bucket is just a name (r1006-081336)"""
    return any(ARTIFACT_PART.search(part) for part in re.split(r"[/\\]", str(path)))


def path_args(value):
    """string values of path-like arguments (filename, source, source_file, ...) anywhere in a parsed document"""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in PATH_ARGS and isinstance(v, str):
                yield v
            else:
                yield from path_args(v)
    elif isinstance(value, list):
        for v in value:
            yield from path_args(v)


def core_failures(spec, checks):
    """Failed core checks: a key probe (adding, removing or changing a key of a dimension) or a module's ownership. They
    are the refactor itself (it generalizes to keys and puts each resource in its module), so failing one scores 0
    like a gate (user decision 10-04: reviewers rejected ~0.9 for solutions that do not generalize)."""
    kinds = {p["name"]: p.get("kind") for p in spec.get("probes", [])}
    kinds.update({f"{p['name']}_fresh": "key_add" for p in spec.get("probes", []) if p.get("kind") == "key_add"})
    kinds.update({f"{p['name']}_fresh": "rename" for p in spec.get("probes", []) if p.get("kind") == "rename"})
    # also the structure of the refactor itself: the module layout, keying by the dimension, no count (Argus Lite on
    # five tasks after the first rule: a solution ignoring the required layout still kept ~0.9), and the rename probes
    # (project and environment flow through every name; user decision 10-06)
    # a set or tags probe the spec marks core (an explicit requirement of the statement: Argus Lite fails a task whose
    # solution keeps partial credit while hard-coding such variables, 10-06)
    marked = {p["name"] for p in spec.get("probes", []) if p.get("core") is True}
    marked |= {f"{name}_alt" for name in marked} | {f"{name}_fresh" for name in marked}  # its variants are core too
    return sorted(name for name, c in checks.items() if not c.get("ok")
                  and (name.startswith(("ownership_", "keys_")) or name in ("layout", "no_count")
                       or kinds.get(name) in KEY_PROBES or kinds.get(name) == "rename" or name in marked))


def fitting_strings(value):
    """the strings of a parsed configuration that can carry a key into an expression: expression text (hcl2json keeps
    "${...}"), list elements and map keys. A plain scalar value (a variable's default, a description, a tag value) cannot,
    so a hidden key spelled there, in an unrelated default say, is not a fitted allowlist (r1004-170315)."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from fitting_strings(v)
    elif isinstance(value, list):
        for v in value:
            if isinstance(v, str):
                yield v
            else:
                yield from fitting_strings(v)
    elif isinstance(value, str) and "${" in value:
        yield value


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


PAREN_TRAVERSAL = re.compile(rf"(?<![\w.\]])\(\s*({CHAIN_BODY})\s*\)")  # also iterator-indexed: (aws_subnet.x[k].id)


def unparen(text):
    """drop parentheses around a bare traversal - (v).id, (v.id), ((v)), (module.network).vpc_id - which Terraform
    reads as the same reference (judst r1002-091617, inside a for expression's key or value); a function call's
    parentheses (preceded by its name) and any group holding an operator, literal or call are left alone"""
    while True:
        new = PAREN_TRAVERSAL.sub(lambda m: m.group(1), text)
        if new == text:
            return text
        text = new


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


def adds_only(today, want):
    """want holds every part of today's at least as often as today does: the reference only adds parts (counted, so a
    new part equal to an existing one, a second 1 in [1, 2, 1], is an addition too)"""
    have = {}
    for p in want:
        have[p] = have.get(p, 0) + 1
    for p in today:
        if have.get(p, 0) == 0:
            return False
        have[p] -= 1
    return True


def subsequence(part, whole):
    """part's elements appear in whole in part's order (others may sit between them)"""
    it = iter(whole)
    return all(any(w == p for w in it) for p in part)


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
            if sorted(g) == sorted(w) and g != w and g != kept and not (
                    adds_only(now, [key(e) for e in want]) and subsequence(now, [key(e) for e in got])):
                # (a value-equal new part, a new desired count of 1 in [1, 2, 1], may sit anywhere too: r1006-162040)
                return path or "the list"
        if len(got) == len(want):
            t = today if isinstance(today, list) and len(today) == len(got) else [None] * len(got)
            for i, (a, b) in enumerate(zip(got, want)):
                p = order_problem(a, b, t[i], f"{path}[{i}]")
                if p:
                    return p
    return None


def replace_deep(value, old, new):
    """value with every leaf equal to old replaced by new, and old spelled as a token inside a string swapped for new"""
    if value == old:
        return new
    if isinstance(value, dict):
        return {k: replace_deep(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_deep(v, old, new) for v in value]
    if isinstance(value, str) and isinstance(old, (str, int, float)) and not isinstance(old, bool):
        return swap(value, str(old), str(new))
    return value


def fresh_text(text, rnd):
    """text with every letter and digit redrawn (same case, digit for digit), separators kept"""
    return "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") if c.islower() else
                   rnd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") if c.isupper() else
                   rnd.choice("0123456789") if c.isdigit() else c for c in str(text))


def replace_text(value, old, new):
    """value with old replaced by new inside every string (a joined name: fraudprod -> caseprod)"""
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, dict):
        return {k: replace_text(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_text(v, old, new) for v in value]
    return value


def leaf_pairs(old, new, out=None):
    """(old leaf, new leaf) wherever two values of the same shape differ (an entry's cidr, its port)"""
    out = [] if out is None else out
    if isinstance(old, dict) and isinstance(new, dict):
        for k in old:
            if k in new:
                leaf_pairs(old[k], new[k], out)
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for a, b in zip(old, new):
            leaf_pairs(a, b, out)
    elif old != new and not isinstance(old, (dict, list)):
        out.append((old, new))
    return out


def derive_expect(expect, base_vars, alt_vars):
    """a set probe's expect entries for one of its alternates: each of the probe's own values, wherever it appears in an
    entry's value or contains parts (a list of CIDRs, a "retention=14" string), becomes the alternate's"""
    out = []
    for e in expect:
        e = dict(e)
        for k, bv in base_vars.items():
            if k in alt_vars:
                for field in ("value", "contains"):
                    if field in e:
                        e[field] = replace_deep(e[field], bv, alt_vars[k])
        out.append(e)
    return out


def json_fragment(part):
    """a contains part written as JSON object members ('"name":"DB_NAME","value":"dbt"') or as a JSON object or array,
    parsed; None for plain text"""
    text = str(part).strip()
    for candidate in (text, "{" + text + "}"):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, (dict, list)):
            return value
    return None


def doc_nodes(value):
    yield value
    if isinstance(value, dict):
        for v in value.values():
            yield from doc_nodes(v)
    elif isinstance(value, list):
        for v in value:
            yield from doc_nodes(v)


def doc_contains(doc, fragment):
    """some object in the document holds every member of the fragment (in any order, however serialized), or some
    node equals the fragment"""
    if isinstance(fragment, dict):
        return any(isinstance(n, dict) and all(k in n and canon(n[k]) == canon(v) for k, v in fragment.items())
                   for n in doc_nodes(doc))
    return any(canon(n) == canon(fragment) for n in doc_nodes(doc))


def same_doc(a, b, attr="", owner=None):
    """equal as AWS reads them (doc_form); IAM policy documents also ignore statement and element order"""
    if policy_doc(a) is not None and policy_doc(b) is not None:
        return canon(a) == canon(b)
    return doc_form(a, attr, owner) == doc_form(b, attr, owner)


def expect_problem(got, want, owner=None):
    """None when a planned value meets a probe's expect entry, else what is wrong (from the attribute on): "value" must
    be equal as AWS reads it (doc_form), "contains" must appear in the planned string (one part or a list of parts); in
    a JSON document a part written as JSON (members of an object) is found by structure, whatever the member order or
    spacing (r1004-172130, r1005-075328)."""
    attr = want["attr"]
    if "contains" in want:
        parts = want["contains"] if isinstance(want["contains"], list) else [want["contains"]]
        doc = jsonish(got) if isinstance(got, str) else got
        structured = isinstance(doc, (dict, list))
        if (isinstance(got, str) or structured) and all(
                (isinstance(got, str) and str(p) in got)
                or (structured and json_fragment(p) is not None and doc_contains(doc, json_fragment(p))) for p in parts):
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


def list_head(values, sep):
    """fixed text a list is glued to before its first part ("myapp/prod/services=worker,web,admin"): the longest prefix
    all the values share, cut after its last '=' or ':', unless today's later parts start with it too (a list of ARNs
    shares "arn:aws:sqs:...:" in every part: that belongs to each part, not to text before the list)"""
    today = values[0]
    first = today.find(sep)
    if first < 0:
        return ""
    prefix = os.path.commonprefix(values)[:first]
    cut = max(prefix.rfind(c) for c in "=:|/;")  # KEY=, path:, a|b|<list> (r1005-135803, r1006-044650)
    if cut < 0:
        return ""
    head = prefix[:cut + 1]
    if all(part.startswith(head) for part in today[len(head):].split(sep)[1:]):
        return ""
    return head


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
        if not head:  # KEY=value fields first (pools=a,b;queues=x,y): each field's list is judged on its own
            raw = [s[:len(s) - len(tail)] if tail else s for s in (today, want, got)]
            fields = field_match(raw[2].split(sep), raw[1].split(sep), raw[0].split(sep)) if sep.strip() else None
            if fields is not None:  # (r1006-085230: the list prefix below would cut into the first field)
                return fields
        if not head:  # a list glued to a fixed KEY= or path: prefix (a new first part would change the first token)
            head = list_head([today, want, got], sep)
        if head and sep.strip():  # "...; available=a,b,c": a KEY= prefix glued to the first part after the sentence
            inner = list_head([s[len(head):len(s) - len(tail) if tail else len(s)] for s in (today, want, got)], sep)
            head += inner  # (r1006-054710)
        if not tail and sep.strip():  # the punctuation closing a sentence that ends with the list ("... us-east-1b.")
            closing = re.search(r"""[.!?;:)\]'"]+$""", today)
            if closing and all(s.endswith(closing.group(0)) for s in (got, want)):
                tail = closing.group(0)
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
        if adds_only(before, after):  # the reference only adds parts, counted (a new part may equal an existing one:
            applies = True  # "1,2,1" -> "1,2,1,1", r1006-162040): today's parts in today's order, the new ones anywhere
            if sorted(mine) != sorted(after):
                continue
            return subsequence(before, mine)
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


PLACEMENT = ("x", "y")


def widget_collector_match(got, want, today):
    """a CloudWatch dashboard's widget list collecting one widget per key: today's widgets unchanged and in today's
    order, the new ones as the reference has them apart from where they sit on the grid (x, y), which the statement
    leaves open (r1006-063800); None for any other list"""
    if not (isinstance(today, list) and got and all(isinstance(e, dict) and "type" in e and "properties" in e
                                                    for e in got + want)):
        return None
    kept = [e for e in today if e in want]
    if [e for e in got if e in kept] != kept:
        return False
    loose = lambda e: json.dumps({k: v for k, v in e.items() if k not in PLACEMENT}, sort_keys=True)
    return sorted(loose(e) for e in got if e not in kept) == sorted(loose(e) for e in want if e not in kept)


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
        if not all(r is True for r in results):  # positions differ: a widget list may still collect correctly
            widgets = widget_collector_match(got, want, today)
            if widgets is not None:
                return widgets
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
            ja, jb, jt = jsonish(va), jsonish(vb), jsonish(today_values[ka])  # KEY=[{...},{...}]: a JSON document
            if (isinstance(ja, (dict, list)) and isinstance(jb, (dict, list)) and canon(ja) == canon(jb)
                    and order_problem(ja, jb, jt) is None):  # (r1006-031654)
                continue
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
        gd, wd = jsonish(got.get("after")), jsonish(want.get("after"))
        if isinstance(got.get("after"), str) and isinstance(gd, (dict, list)) and isinstance(wd, (dict, list)):
            # a JSON document held in a string (an SSM parameter's value): the commas between its members are not
            # collector separators, so compare as documents, collectors inside by the order rule (r1004-221024)
            parts = nested_delimited_match(gd, wd, jsonish(today))
        else:
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


def balanced(text):
    """parentheses balance and never close more than they opened (so "(a) + (b)" is not one parenthesized whole)"""
    depth = 0
    for ch in text:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth < 0:
            return False
    return depth == 0


def output_mismatch(got, want, today):
    """None when a root output in a probe's plan agrees with the reference solution's plan there, else why not. Like
    value_mismatch, and a map output must have the same keys and a list output the same length (the new key's entry may
    be unknown in both plans, which value_mismatch alone would not see)."""
    ga, wa, gu, wu = got.get("after"), want.get("after"), got.get("unknown"), want.get("unknown")
    if wu is True:
        return None  # the reference's plan cannot know it either
    if isinstance(wa, dict) or isinstance(wu, dict):
        keys = lambda a, u: (set(a) if isinstance(a, dict) else set()) | (set(u) if isinstance(u, dict) else set())
        if not (isinstance(ga, dict) or isinstance(gu, dict)) or keys(ga, gu) != keys(wa, wu):
            return f"has keys {sorted(keys(ga, gu))[:6]}, expected {sorted(keys(wa, wu))[:6]}"
    if isinstance(wa, list) and (not isinstance(ga, list) or len(ga) != len(wa)):
        return f"= {short(ga)}, expected {len(wa)} entries"
    return value_mismatch(got, want, today, "output")


UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
CLOUD_ID = re.compile(r"\b([a-z]+)-([0-9a-f]{6,})\b")
STANDIN_IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]|/\d)")  # an address, not a CIDR block
HOST_IP = re.compile(r"\b(ip|ec2)-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}\b")  # ip-10-0-1-5.ec2.internal, ec2-3-4-5-6.compute...


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
    # a cloud-assigned address (an EIP's public_ip, an ENI's private_ip) is fresh too: with the counterpart's own, a set
    # collecting one per key (a Route 53 record's records) would merge the new key's into it (r1006-044755)
    ip = f"198.{18 + int(digest[32:34], 16) % 2}.{int(digest[34:36], 16)}.{100 + int(digest[36:38], 16) % 155}"
    out = STANDIN_IP.sub(ip, out)
    return HOST_IP.sub(lambda m: f"{m.group(1)}-{ip.replace('.', '-')}", out)


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
        like = like 