#!/usr/bin/env python3
"""cfn_equal.py EXPECTED_DIR ACTUAL_DIR [--ignore-tag KEY] [--normalize-api-deployments] [--feature FILE] [--json FILE]
                [--show N]

Template equality the way the CDK componentization tasks define it. EXPECTED_DIR and ACTUAL_DIR are cloud assemblies
(cdk.out directories with manifest.json) or plain directories of <stack>.template.json files.

Per stack and logical ID: Type, Properties, DependsOn (as a set), Condition, DeletionPolicy, UpdateReplacePolicy,
UpdatePolicy and CreationPolicy must be equal; so must the Outputs, Parameters, Conditions, Mappings and Rules sections.
JSON key order and resource order do not matter; array order does. Resource Metadata, AWS::CDK::Metadata resources
and the CDKMetadataAvailable condition are ignored. --ignore-tag KEY removes tags with that key from ACTUAL before
comparing, wherever CloudFormation renders tags: `Tags` and the other `...Tags` properties (HostedZoneTags,
UserPoolTags, ...) in both shapes ([{"Key","Value"}] lists and {key: value} maps), and the Tags of TagSpecifications
(also inside a launch template's LaunchTemplateData). --normalize-api-deployments renames
every AWS::ApiGateway::Deployment in both templates to "Deployment:<its RestApiId>" (and every reference to it), so a
deployment compares by content whatever its logical ID (tagging the API changes that ID). --soft-tag KEY does not
compare what only the rendering of tag KEY decides beyond a resource's own tags: its entries in tag specifications and
its PropagateAtLaunch flag (both sides). --feature FILE (a JSON file {"added": [regex, ...], "modified": {regex: [path,
...]}}; regexes match "<stack>/<logical ID>" or "<stack>/#Outputs/<output ID>") does not count what a stated feature
changes: resources and outputs ACTUAL adds whose names match an "added" regex, and, in a resource whose name matches a
"modified" regex, differences at or below the listed paths (such as /Properties/AlarmRule). Whatever else differs,
inside the feature's resources or not, still counts; a missing resource always counts.
Exit status 0 when every stack is equal, 1 otherwise.
"""
import json
import os
import re
import sys

RES_ATTRS = ["Type", "Properties", "DependsOn", "Condition", "DeletionPolicy", "UpdateReplacePolicy",
             "UpdatePolicy", "CreationPolicy"]
SECTIONS = ["Outputs", "Parameters", "Conditions", "Mappings", "Rules"]
TAG_PROPS = ("Tags", "BackupVaultTags", "BackupPlanTags", "TagSpecifications")


def load_templates(path):
    man = os.path.join(path, "manifest.json")
    out = {}
    if os.path.exists(man):
        m = json.load(open(man))
        for name, art in m.get("artifacts", {}).items():
            if art.get("type") == "aws:cloudformation:stack":
                out[art.get("displayName", name)] = json.load(open(os.path.join(path, art["properties"]["templateFile"])))
    else:
        for f in sorted(os.listdir(path)):
            if f.endswith(".template.json"):
                out[f[:-len(".template.json")]] = json.load(open(os.path.join(path, f)))
    return out


def strip_tag(props, key):
    """Remove the tag `key` wherever CloudFormation renders a resource's tags: `Tags` and every other `...Tags`
    property (HostedZoneTags, UserPoolTags, BackupVaultTags, ...) as a [{"Key", "Value"}] list or a {key: value} map,
    and the `Tags` of `TagSpecifications` entries (also inside a launch template's LaunchTemplateData). Collections
    left empty are dropped."""
    for name in list(props):
        v = props[name]
        if name.endswith("Tags") and isinstance(v, list) and all(isinstance(t, dict) and "Key" in t for t in v):
            v = [t for t in v if t.get("Key") != key]
        elif name.endswith("Tags") and isinstance(v, dict):
            v = {k: x for k, x in v.items() if k != key}
        elif name == "TagSpecifications" and isinstance(v, list):
            specs = []
            for spec in v:
                if isinstance(spec, dict) and isinstance(spec.get("Tags"), list):
                    spec = dict(spec, Tags=[t for t in spec["Tags"] if not (isinstance(t, dict) and t.get("Key") == key)])
                    if not spec["Tags"]:
                        continue
                specs.append(spec)
            v = specs
        elif name == "LaunchTemplateData" and isinstance(v, dict):
            v = dict(v)
            strip_tag(v, key)
            props[name] = v
            continue
        else:
            continue
        if v:
            props[name] = v
        else:
            del props[name]


def rename_refs(v, renames):
    if isinstance(v, dict):
        if len(v) == 1 and "Ref" in v and v["Ref"] in renames:
            return {"Ref": renames[v["Ref"]]}
        if len(v) == 1 and "Fn::GetAtt" in v and isinstance(v["Fn::GetAtt"], list) and v["Fn::GetAtt"][0] in renames:
            return {"Fn::GetAtt": [renames[v["Fn::GetAtt"][0]]] + v["Fn::GetAtt"][1:]}
        return {k: rename_refs(x, renames) for k, x in v.items()}
    if isinstance(v, list):
        return [rename_refs(x, renames) for x in v]
    return v


def normalize_api_deployments(t):
    res = t.get("Resources") or {}
    renames = {lid: "Deployment:" + json.dumps((r.get("Properties") or {}).get("RestApiId"), sort_keys=True)
               for lid, r in res.items() if r.get("Type") == "AWS::ApiGateway::Deployment"}
    if not renames:
        return t
    out = dict(t)
    new_res = {}
    for lid, r in res.items():
        r = rename_refs(r, renames)
        if "DependsOn" in r:
            d = r["DependsOn"]
            r["DependsOn"] = [renames.get(x, x) for x in ([d] if isinstance(d, str) else d)]
        new_res[renames.get(lid, lid)] = r
    out["Resources"] = new_res
    for sec in ("Outputs", "Conditions"):
        if sec in t:
            out[sec] = rename_refs(t[sec], renames)
    return out


def norm(t, ignore_tags=()):
    res = {}
    for lid, r in (t.get("Resources") or {}).items():
        if r.get("Type") == "AWS::CDK::Metadata":
            continue
        n = {}
        for k in RES_ATTRS:
            if k in r:
                v = r[k]
                if k == "DependsOn":
                    v = sorted([v] if isinstance(v, str) else v)
                n[k] = json.loads(json.dumps(v))
        for key in ignore_tags:
            if isinstance(n.get("Properties"), dict):
                strip_tag(n["Properties"], key)
        res[lid] = n
    out = {"Resources": res}
    for sec in SECTIONS:
        v = dict(t.get(sec) or {})
        if sec == "Conditions":
            v.pop("CDKMetadataAvailable", None)
        out[sec] = v
    return out


def diff_paths(a, b, path=""):
    if type(a) != type(b):
        return [path or "/"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += [f"{path}/{k}"] if (k not in a or k not in b) else diff_paths(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}[{len(a)} -> {len(b)} items]"]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in diff_paths(x, y, f"{path}[{i}]")]
    return [] if a == b else [path or "/"]


def soften_tag(t, key):
    """The template without what only the rendering of tag `key` decides beyond the resource's own tags: its entries in
    tag specifications (a launch template's, also inside LaunchTemplateData; the tags of what it launches) and its
    PropagateAtLaunch flag on an Auto Scaling group. Whether a resource carries the tag, and its value, still count."""
    out = json.loads(json.dumps(t))
    for r in (out.get("Resources") or {}).values():
        props = r.get("Properties")
        if not isinstance(props, dict):
            continue
        for holder in (props, props.get("LaunchTemplateData") if isinstance(props.get("LaunchTemplateData"), dict) else None):
            specs = (holder or {}).get("TagSpecifications")
            if isinstance(specs, list):
                for spec in specs:
                    if isinstance(spec, dict) and isinstance(spec.get("Tags"), list):
                        spec["Tags"] = [x for x in spec["Tags"] if not (isinstance(x, dict) and x.get("Key") == key)]
        tags = props.get("Tags")
        if isinstance(tags, list):
            for x in tags:
                if isinstance(x, dict) and x.get("Key") == key:
                    x.pop("PropagateAtLaunch", None)
    return out


def compare(expected_dir, actual_dir, ignore_tags=(), normalize_deployments=False, soft_tag=None):
    exp, act = load_templates(expected_dir), load_templates(actual_dir)
    if normalize_deployments:
        exp = {k: normalize_api_deployments(v) for k, v in exp.items()}
        act = {k: normalize_api_deployments(v) for k, v in act.items()}
    if soft_tag:
        exp = {k: soften_tag(v, soft_tag) for k, v in exp.items()}
        act = {k: soften_tag(v, soft_tag) for k, v in act.items()}
    report = {"stacks": {}, "missing_stacks": sorted(set(exp) - set(act)), "extra_stacks": sorted(set(act) - set(exp))}
    equal = not report["missing_stacks"] and not report["extra_stacks"]
    for name in sorted(set(exp) & set(act)):
        e, a = norm(exp[name]), norm(act[name], ignore_tags)
        er, ar = e["Resources"], a["Resources"]
        st = {"resources": len(er), "same": 0, "modified": {}, "missing": sorted(set(er) - set(ar)),
              "added": sorted(set(ar) - set(er)), "sections": {}}
        for lid in er:
            if lid in ar:
                if er[lid] == ar[lid]:
                    st["same"] += 1
                else:
                    st["modified"][lid] = diff_paths(er[lid], ar[lid])
        for sec in SECTIONS:
            d = diff_paths(e[sec], a[sec])
            if d:
                st["sections"][sec] = d
        st["equal"] = not (st["modified"] or st["missing"] or st["added"] or st["sections"])
        equal = equal and st["equal"]
        report["stacks"][name] = st
    report["equal"] = equal
    return report


def apply_feature(report, feature):
    """The report without the differences a stated feature makes (see --feature); recomputes the equal flags."""
    added = [re.compile(x) for x in feature.get("added") or []]
    modified = [(re.compile(k), list(v)) for k, v in (feature.get("modified") or {}).items()]

    def is_added(name):
        return any(rx.search(name) for rx in added)

    def allowed_paths(name):
        return [p for rx, paths in modified if rx.search(name) for p in paths]

    def under(path, prefixes):
        return any(path == q or path.startswith(q + "/") or path.startswith(q + "[") for q in prefixes)

    equal = not report["missing_stacks"] and not [s for s in report["extra_stacks"] if not is_added(f"{s}/*")]
    report["extra_stacks"] = [s for s in report["extra_stacks"] if not is_added(f"{s}/*")]
    for name, st in report["stacks"].items():
        st["added"] = [lid for lid in st["added"] if not is_added(f"{name}/{lid}")]
        for lid in list(st["modified"]):
            prefixes = allowed_paths(f"{name}/{lid}")
            rest = [p for p in st["modified"][lid] if not under(p, prefixes)]
            if rest:
                st["modified"][lid] = rest
            else:
                del st["modified"][lid]
                st["same"] += 1
        for sec in list(st["sections"]):
            rest = [p for p in st["sections"][sec]
                    if not (is_added(f"{name}/#{sec}/{(p.split('/') + ['', ''])[1].split('[')[0]}") and p.count("/") == 1)]
            if rest:
                st["sections"][sec] = rest
            else:
                del st["sections"][sec]
        st["equal"] = not (st["modified"] or st["missing"] or st["added"] or st["sections"])
        equal = equal and st["equal"]
    report["equal"] = equal
    return report


def main():
    args = sys.argv[1:]
    ignore, js, show = [], None, 10
    normalize = "--normalize-api-deployments" in args
    if normalize:
        args.remove("--normalize-api-deployments")
    soft = None
    if "--soft-tag" in args:
        i = args.index("--soft-tag"); soft = args[i + 1]; del args[i:i + 2]
    while "--ignore-tag" in args:
        i = args.index("--ignore-tag"); ignore.append(args[i + 1]); del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json"); js = args[i + 1]; del args[i:i + 2]
    feature = None
    if "--feature" in args:
        i = args.index("--feature"); feature = json.load(open(args[i + 1])); del args[i:i + 2]
    if "--show" in args:
        i = args.index("--show"); show = int(args[i + 1]); del args[i:i + 2]
    if len(args) != 2:
        print(__doc__)
        return 2
    rep = compare(args[0], args[1], ignore, normalize, soft)
    if feature is not None:
        rep = apply_feature(rep, feature)
    if js:
        json.dump(rep, open(js, "w"), indent=1)
    for s in rep["missing_stacks"]:
        print(f"[{s}] MISSING STACK")
    for s in rep["extra_stacks"]:
        print(f"[{s}] EXTRA STACK")
    for name, st in rep["stacks"].items():
        print(f"[{name}] {'EQUAL' if st['equal'] else 'DIFFERENT'}: {st['same']}/{st['resources']} resources equal, "
              f"{len(st['modified'])} modified, {len(st['missing'])} missing, {len(st['added'])} added"
              + (f", sections differ: {', '.join(st['sections'])}" if st["sections"] else ""))
        for lid, paths in list(st["modified"].items())[:show]:
            print(f"    modified {lid}: {', '.join(paths[:4])}{' ...' if len(paths) > 4 else ''}")
        for lid in st["missing"][:show]:
            print(f"    missing  {lid}")
        for lid in st["added"][:show]:
            print(f"    added    {lid}")
        for sec, paths in st["sections"].items():
            print(f"    {sec}: {', '.join(paths[:4])}{' ...' if len(paths) > 4 else ''}")
    print("RESULT:", "EQUAL" if rep["equal"] else "DIFFERENT")
    return 0 if rep["equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
