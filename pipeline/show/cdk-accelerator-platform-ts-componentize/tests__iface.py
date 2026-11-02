#!/usr/bin/env python3
"""Interface checks of the CDK componentization family, generated from the spec (no task-specific code).

TypeScript: `generate_ts(spec, project_dir)` returns the source of grade/interface-check.ts and a map from line numbers to
component classes. The file is type-checked, never executed: for every component one function constructs it with an
object literal holding exactly the stated props (each typed as stated, so a missing member, an unknown member or an
incompatible member type is a type error), checks the declared type of each stated prop (the constructor's third
parameter, member by member): not `any`, and no wider than the stated type (with the literal above: the same type, up
to `readonly` on arrays and optionality), reads every stated public property into a variable of the stated type
(declared no wider than stated) that must not be `any`, and assigns each one to itself under `// @ts-expect-error` (an
error unless the property is readonly).

Stacks that declare public properties (spec.stacks[].properties) get the same check without the constructor: one
function per stack takes an instance, reads every stated property into a variable of the stated type and assigns it
to itself under `// @ts-expect-error`.

Python components and stacks are checked at run time by the harness (constructor keyword parameters, isinstance of
the public properties); `type_problems(spec)` validates the type expressions of either language for iacctl lint.
"""
import json
import os
import re
import sys

# Conventional import aliases of aws-cdk-lib submodules (TypeScript module path; Python: aws_cdk.<module>)
DEFAULT_ALIASES = {
    "cdk": "", "apigateway": "aws-apigateway", "apigw": "aws-apigateway", "apigatewayv2": "aws-apigatewayv2",
    "apigwv2": "aws-apigatewayv2", "appscaling": "aws-applicationautoscaling", "autoscaling": "aws-autoscaling",
    "backup": "aws-backup", "certificatemanager": "aws-certificatemanager", "acm": "aws-certificatemanager",
    "cloudfront": "aws-cloudfront", "cloudtrail": "aws-cloudtrail", "cloudwatch": "aws-cloudwatch",
    "cw": "aws-cloudwatch", "cwActions": "aws-cloudwatch-actions", "cw_actions": "aws-cloudwatch-actions",
    "codebuild": "aws-codebuild", "cognito": "aws-cognito", "dynamodb": "aws-dynamodb", "ec2": "aws-ec2",
    "ecr": "aws-ecr", "ecs": "aws-ecs", "efs": "aws-efs", "eks": "aws-eks", "elasticache": "aws-elasticache",
    "elbv2": "aws-elasticloadbalancingv2", "events": "aws-events", "targets": "aws-events-targets",
    "events_targets": "aws-events-targets", "firehose": "aws-kinesisfirehose", "glue": "aws-glue", "iam": "aws-iam",
    "kinesis": "aws-kinesis", "kms": "aws-kms", "lambda": "aws-lambda", "lambda_": "aws-lambda",
    "lambdaEventSources": "aws-lambda-event-sources", "lambda_event_sources": "aws-lambda-event-sources",
    "logs": "aws-logs", "opensearch": "aws-opensearchservice", "rds": "aws-rds", "route53": "aws-route53",
    "s3": "aws-s3", "s3n": "aws-s3-notifications", "secretsmanager": "aws-secretsmanager", "ses": "aws-ses",
    "servicediscovery": "aws-servicediscovery", "sns": "aws-sns", "subs": "aws-sns-subscriptions",
    "sns_subscriptions": "aws-sns-subscriptions", "sqs": "aws-sqs", "ssm": "aws-ssm", "sfn": "aws-stepfunctions",
    "stepfunctions": "aws-stepfunctions", "tasks": "aws-stepfunctions-tasks", "sfn_tasks": "aws-stepfunctions-tasks",
    "wafv2": "aws-wafv2", "xray": "aws-xray", "athena": "aws-athena", "kinesisfirehose": "aws-kinesisfirehose",
    "msk": "aws-msk", "redshift": "aws-redshift", "scheduler": "aws-scheduler", "pipes": "aws-pipes",
    "synthetics": "aws-synthetics", "guardduty": "aws-guardduty", "config": "aws-config", "budgets": "aws-budgets",
    "sam": "aws-sam", "batch": "aws-batch", "emr": "aws-emr", "appsync": "aws-appsync", "codepipeline": "aws-codepipeline",
}
TS_BUILTINS = {"string", "number", "boolean", "any", "unknown", "undefined", "null", "void", "never", "object",
               "readonly", "Record", "Partial", "Readonly", "ReadonlyArray", "Array", "Map", "Set", "ReadonlyMap",
               "ReadonlySet", "Promise", "true", "false", "keyof", "typeof", "Required", "Pick", "Omit"}
PY_BUILTINS = {"str", "int", "float", "bool", "None", "Optional", "Mapping", "Dict", "dict", "Sequence", "List", "list",
               "tuple", "Tuple", "Any", "typing", "Union", "object", "bytes", "Literal", "Iterable", "Callable", "Set",
               "set", "FrozenSet", "frozenset", "MutableMapping", "MutableSequence"}


def ts_module_of(alias, aliases):
    sub = aliases.get(alias)
    if sub is None:
        return None
    return "aws-cdk-lib" if sub == "" else f"aws-cdk-lib/{sub}"


def py_module_of(alias, aliases):
    sub = aliases.get(alias)
    if sub is None:
        return None
    return "aws_cdk" if sub == "" else "aws_cdk." + sub.replace("-", "_")


def aliases_of(spec):
    out = dict(DEFAULT_ALIASES)
    out.update(spec.get("type_aliases") or {})
    return out


def identifiers(expr, language):
    """(qualified alias.Name pairs, bare names) used in a type expression."""
    text = re.sub(r"\[\s*[A-Za-z_]\w*\s*:", "[", expr)            # index signature parameter names
    text = re.sub(r"[A-Za-z_]\w*\s*\??\s*:", "", text)               # member names in object type literals
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "", text)                   # string literal types
    qualified, bare = set(), set()
    for m in re.finditer(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", text):
        tok = m.group(0)
        if "." in tok:
            head, tail = tok.split(".", 1)
            if language == "python" and head == "typing":
                continue
            qualified.add((head, tail))
        else:
            bare.add(tok)
    builtins = TS_BUILTINS if language == "typescript" else PY_BUILTINS
    return qualified, {b for b in bare if b not in builtins}


def exported_names(path, language):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return set()
    if language == "typescript":
        return set(re.findall(r"^export\s+(?:declare\s+)?(?:abstract\s+)?(?:interface|type|class|enum|const|function)\s+([A-Za-z_]\w*)",
                              text, re.M))
    return set(re.findall(r"^(?:class|def)\s+([A-Za-z_]\w*)", text, re.M)) | \
        set(re.findall(r"^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=", text, re.M))


def strip_opt(name):
    return name[:-1] if name.endswith("?") else name


def names(members):
    """Member names of a {name: type} dict (a trailing ? marks an optional member)."""
    return [strip_opt(k) for k in (members or {})]


def harness_spec(spec):
    """What the grader entry point (harness.ts / harness_py.py) needs to know: the entry module and function, the
    component classes with their public properties (and, for Python, the props and property types it checks)."""
    aliases = aliases_of(spec)
    py = spec.get("language") == "python"
    return {"entry": spec["entry"], "code_dir": spec["code_dir"],
            "config_module": spec.get("config_module") if py else None,
            "type_modules": {a: py_module_of(a, aliases) for a in aliases} if py else {},
            "allowed_imports": spec.get("allowed_imports", []),
            "components": [{"class": c["class"], "module": c["module"], "properties": names(c.get("properties")),
                            "props": names(c.get("props")),
                            "property_types": {strip_opt(k): v for k, v in (c.get("properties") or {}).items()} if py else {},
                            "prop_types": {strip_opt(k): v for k, v in (c.get("props") or {}).items()} if py else {}}
                           for c in spec["components"]],
            "stacks": [{"class": s["class"], "module": s["module"], "properties": names(s.get("properties")),
                        "property_types": {strip_opt(k): v for k, v in (s.get("properties") or {}).items()} if py else {}}
                       for s in interface_stacks(spec)]}


def interface_stacks(spec):
    """The stacks whose public properties the statement states (spec.stacks[].properties)."""
    return [s for s in spec.get("stacks") or [] if s.get("properties")]


def type_problems(spec, project_dir):
    """Unknown type names in the props and public property types of every component."""
    language = spec.get("language", "typescript")
    aliases = aliases_of(spec)
    classes = {c["class"] for c in spec["components"]} | {s["class"] for s in spec.get("stacks") or []}
    exports = {e for c in spec["components"] for e in c.get("exports", [])}
    config_names = exported_names(os.path.join(project_dir, spec["config_module"]), language)
    out = []
    for c in list(spec["components"]) + interface_stacks(spec):
        for kind in ("props", "properties"):
            for name, expr in (c.get(kind) or {}).items():
                q, bare = identifiers(expr, language)
                for alias, _ in q:
                    if alias not in aliases:
                        out.append(f"{c['class']}.{kind}.{strip_opt(name)}: unknown module alias {alias!r} in {expr!r} "
                                   f"(add it to spec.type_aliases)")
                for b in bare:
                    if b not in classes and b not in exports and b not in config_names and b != "Construct":
                        out.append(f"{c['class']}.{kind}.{strip_opt(name)}: unknown type {b!r} in {expr!r} (a component "
                                   f"or stack class, a type the config module exports, or a name in a component's "
                                   f"`exports`)")
    return out


def generate_ts(spec):
    """(source text of grade/interface-check.ts, {line number: component class or '*'})"""
    aliases = aliases_of(spec)
    comps = spec["components"]
    by_class = {c["class"]: c for c in comps}
    by_class.update({st["class"]: st for st in interface_stacks(spec) if st["class"] not in by_class})
    export_owner = {e: c for c in comps for e in c.get("exports", [])}
    used_aliases, used_config, imports_by_module = set(), set(), {}

    def need(expr, owner):
        q, bare = identifiers(expr, "typescript")
        for alias, _ in q:
            used_aliases.add(alias)
        for b in bare:
            if b == "Construct":
                continue
            if b in by_class:
                imports_by_module.setdefault(by_class[b]["module"], set()).add(b)
            elif b in export_owner:
                imports_by_module.setdefault(export_owner[b]["module"], set()).add(b)
            else:
                used_config.add(b)

    for c in comps:
        imports_by_module.setdefault(c["module"], set()).add(c["class"])
        for expr in list((c.get("props") or {}).values()) + list((c.get("properties") or {}).values()):
            need(expr, c)
    stacks = interface_stacks(spec)
    for st in stacks:
        imports_by_module.setdefault(st["module"], set()).add(st["class"])
        for expr in (st.get("properties") or {}).values():
            need(expr, st)

    def rel(module):
        mod = re.sub(r"\.ts$", "", module)
        return "../" + mod

    lines, owner = [], {}
    lines.append("// Interface check (generated by the grader from the task spec; type-checked, never executed): every")
    lines.append("// component accepts exactly the stated props and exposes the stated public properties, read-only, with")
    lines.append("// those types. A type error inside a function fails that component's interface check only.")
    lines.append("import { Construct } from 'constructs';")
    for alias in sorted(used_aliases):
        lines.append(f"import * as {alias} from '{ts_module_of(alias, aliases)}';")
    if used_config:
        lines.append(f"import {{ {', '.join(sorted(used_config))} }} from '{rel(spec['config_module'])}';")
        owner[len(lines)] = "*"
    module_class = {c["module"]: c["class"] for c in list(comps) + stacks}
    for module, names in imports_by_module.items():
        lines.append(f"import {{ {', '.join(sorted(names))} }} from '{rel(module)}';")
        owner[len(lines)] = module_class.get(module, "*")
    lines.append("")
    lines.append("declare const scope: Construct;")
    owner[len(lines)] = "*"
    for helper in ("type IsAny<T> = 0 extends (1 & T) ? true : false;",
                   "type NotAny<T> = IsAny<T> extends true ? false : true;",
                   "type Unro<T> = T extends readonly (infer U)[] ? U[] : T;",
                   "type Within<D, S> = IsAny<D> extends true ? false : [Unro<NonNullable<D>>] extends [NonNullable<S>] ? true : false;"):
        lines.append(helper)
        owner[len(lines)] = "*"
    for c in comps:
        props = c.get("props") or {}
        params = ", ".join(f"p{i}: {expr}{' | undefined' if name.endswith('?') else ''}"
                           for i, (name, expr) in enumerate(props.items()))
        start = len(lines) + 1
        lines.append("")
        lines.append(f"export function check{c['class']}({params}): unknown[] {{")
        members = ", ".join(f"{json.dumps(strip_opt(name))}: p{i}" for i, name in enumerate(props))
        lines.append(f"  const c = new {c['class']}(scope, 'InterfaceCheck', {{ {members} }});")
        reads = []
        if props:
            # the declared type of every stated prop: not `any`, no wider than stated
            lines.append(f"  type Props = NonNullable<ConstructorParameters<typeof {c['class']}>[2]>;")
            for i, (name, expr) in enumerate(props.items()):
                lines.append(f"  const t{i}: [NotAny<Props[{json.dumps(strip_opt(name))}]>, "
                             f"Within<Props[{json.dumps(strip_opt(name))}], {expr}>] = [true, true];")
                reads.append(f"t{i}")
        for j, (name, expr) in enumerate((c.get("properties") or {}).items()):
            prop = strip_opt(name)
            t = f"{expr} | undefined" if name.endswith("?") else expr
            lines.append(f"  const v{j}: {t} = c.{prop};")
            lines.append(f"  const n{j}: NotAny<{c['class']}[{json.dumps(prop)}]> = true;")
            lines.append(f"  // @ts-expect-error {prop} is readonly")
            lines.append(f"  c.{prop} = c.{prop};")
            reads += [f"v{j}", f"n{j}"]
        lines.append(f"  return [c{''.join(', ' + r for r in reads)}];")
        lines.append("}")
        for ln in range(start, len(lines) + 1):
            owner[ln] = c["class"]
    for st in stacks:
        start = len(lines) + 1
        lines.append("")
        lines.append(f"export function check{st['class']}(s: {st['class']}): unknown[] {{")
        reads = []
        for j, (name, expr) in enumerate((st.get("properties") or {}).items()):
            prop = strip_opt(name)
            t = f"{expr} | undefined" if name.endswith("?") else expr
            lines.append(f"  const v{j}: {t} = s.{prop};")
            lines.append(f"  const n{j}: NotAny<{st['class']}[{json.dumps(prop)}]> = true;")
            lines.append(f"  // @ts-expect-error {prop} is readonly")
            lines.append(f"  s.{prop} = s.{prop};")
            reads += [f"v{j}", f"n{j}"]
        lines.append(f"  return [s{''.join(', ' + r for r in reads)}];")
        lines.append("}")
        for ln in range(start, len(lines) + 1):
            owner[ln] = st["class"]
    return "\n".join(lines) + "\n", owner


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    text, _ = generate_ts(spec)
    sys.stdout.write(text)
