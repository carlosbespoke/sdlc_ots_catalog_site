#!/usr/bin/env python3
"""check-rules.py PROJECT_DIR [--code-dir DIR] [--hashes FILE] [--json OUT]

Static rules for the app code under PROJECT_DIR/<code dir> (family: componentize a CDK app without touching
production). The same file ships to the agent as tools/check-rules.py; CI and the grader run their own copy. It only
parses the files (Python `ast`); nothing is executed.

  R1 imports      only aws_cdk (and its submodules, except cloudformation_include, assertions, cx_api and pipelines),
                  constructs, jsii (for the @jsii.implements decorator only), the standard modules typing,
                  typing_extensions, dataclasses, enum, abc, functools, itertools, collections, re, math, json,
                  hashlib, string, textwrap, copy and __future__, os for os.path only, and modules of the app's own
                  package
  R2 names        no use of exec, eval, compile, __import__, open, input, breakpoint, globals, locals, vars, getattr,
                  setattr, delattr or memoryview, and no three-argument type()
  R3 raw CFN      no call of a Cfn* class other than CfnOutput and the property types (CfnTag, CfnCreationPolicy,
                  CfnUpdatePolicy, CfnResourceSignal, CfnAutoScaling*, CfnCodeDeployLambdaAliasUpdate, *Props,
                  *Property); no class extending a Cfn* class; no reference to add_override, add_property_override,
                  add_deletion_override or add_property_deletion_override (called or not)
  R4 internals    no dunder attribute other than __init__, no dunder name other than __file__ and __name__, and no
                  name containing "jsii" other than the jsii module and its implements decorator
  R5 patching     no assignment to (or del of) an attribute or item of anything imported from a package (aws_cdk,
                  constructs, jsii, os, ...), directly or through a variable that holds it; no attribute named `node`
                  assigned or defined in a class
  R6 one app      no call of App, Stage, Stack, NestedStack or of a class that extends one of them; no .synth() call
  R7 copied IDs   none of the 8-character hashes that end the deployed templates' logical IDs and generated names
                  ends a word in the code of a file under the code directory (comments are not code). A hash is taken
                  from a logical ID (its last 8 uppercase hex characters, before the 32 lowercase ones of an API
                  deployment), or from a string value where it ends a word and has a letter (never from an all-digit
                  run such as an account number)
"""
import ast
import json
import os
import re
import sys

ALLOWED_MODULES = {"aws_cdk", "constructs", "jsii", "typing", "typing_extensions", "dataclasses", "enum", "abc",
                   "functools", "itertools", "collections", "re", "math", "json", "hashlib", "string", "textwrap",
                   "copy", "__future__", "os"}
BANNED_CDK_SUBMODULES = {"cloudformation_include", "assertions", "cx_api", "pipelines"}
BANNED_NAMES = {"exec", "eval", "compile", "__import__", "open", "input", "breakpoint", "globals", "locals", "vars",
                "getattr", "setattr", "delattr", "memoryview", "__builtins__"}
OVERRIDES = {"add_override", "add_property_override", "add_deletion_override", "add_property_deletion_override"}
APP_CLASSES = {"App", "Stage", "Stack", "NestedStack"}
CFN_STRUCTS = {"CfnOutput", "CfnTag", "CfnCreationPolicy", "CfnUpdatePolicy", "CfnResourceSignal",
               "CfnAutoScalingCreationPolicy", "CfnAutoScalingReplacingUpdate", "CfnAutoScalingRollingUpdate",
               "CfnAutoScalingScheduledAction", "CfnCodeDeployLambdaAliasUpdate", "CfnResourceAutoScalingCreationPolicy",
               "CfnDynamicReferenceProps", "CfnDynamicReference"}
HASH_RE = re.compile(r"[A-Za-z0-9]([0-9A-F]{8})(?=[0-9a-f]{32}(?![0-9A-Za-z])|(?![0-9A-Za-z]))")
ID_HASH_RE = re.compile(r"[A-Za-z0-9]([0-9A-F]{8})(?:[0-9a-f]{32})?$")


def template_hashes(t):
    """The hashes of one template: the last 8 uppercase hex characters of every logical ID (before the 32 lowercase ones
    of an API deployment), and of every word of a string value that ends that way and has a letter (generated names;
    never an all-digit run such as an account number)."""
    out = set()
    for section in ("Resources", "Outputs", "Conditions", "Parameters", "Mappings"):
        for lid in ((t or {}).get(section) or {}):
            m = ID_HASH_RE.search(lid)
            if m:
                out.add(m.group(1))

    def walk(v):
        if isinstance(v, str):
            out.update(m.group(1) for m in HASH_RE.finditer(v) if re.search(r"[A-F]", m.group(1)))
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(t)
    return out


def code_text(text):
    """The source with every comment blanked out (same length and line breaks)."""
    import io
    import tokenize
    chars = list(text)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                start = offsets[tok.start[0] - 1] + tok.start[1]
                end = offsets[tok.end[0] - 1] + tok.end[1]
                for i in range(start, end):
                    if chars[i] != "\n":
                        chars[i] = " "
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "".join(chars)


def last_name(node):
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def root_name(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def list_py(code_dir):
    out = []
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(files):
            out.append(os.path.join(root, f))
    return out


def check(project_dir, code_dir_rel, hashes):
    code_dir = os.path.join(project_dir, code_dir_rel)
    package = code_dir_rel.replace("/", ".").replace(os.sep, ".")
    violations = []

    def add(path, node, rule, msg):
        violations.append({"rule": rule, "file": os.path.relpath(path, project_dir),
                           "line": getattr(node, "lineno", 0) if node is not None else 0, "message": msg})

    sources = []
    for path in list_py(code_dir):
        if not path.endswith(".py"):
            if not path.endswith(".pyc"):
                add(path, None, "R1", "only .py files belong under the code directory")
            continue
        text = open(path, encoding="utf-8").read()
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError as exc:
            violations.append({"rule": "R0", "file": os.path.relpath(path, project_dir), "line": exc.lineno or 0,
                               "message": f"syntax error: {exc.msg}"})
            continue
        sources.append((path, text, tree))

    # classes that are (or extend) App / Stage / Stack / NestedStack, across all files (fixpoint over names)
    app_like = set(APP_CLASSES)
    heritage = []
    for _, _, tree in sources:
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                for b in n.bases:
                    heritage.append((n.name, last_name(b)))
    changed = True
    while changed:
        changed = False
        for name, base in heritage:
            if base in app_like and name not in app_like:
                app_like.add(name)
                changed = True

    for path, text, tree in sources:
        package_names = set()   # local names bound to imports from packages (anything but the app's own modules)
        jsii_names = set()
        os_names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    top = a.name.split(".")[0]
                    parts = a.name.split(".")
                    bound = a.asname or top
                    if top == package.split(".")[0]:
                        continue
                    if top not in ALLOWED_MODULES:
                        add(path, n, "R1", f"import of {a.name!r} is not allowed")
                    elif top == "aws_cdk" and len(parts) > 1 and parts[1] in BANNED_CDK_SUBMODULES:
                        add(path, n, "R1", f"import of {a.name!r} is not allowed")
                    elif top == "os" and a.name not in ("os", "os.path"):
                        add(path, n, "R1", f"import of {a.name!r} is not allowed (os.path only)")
                    package_names.add(bound)
                    if top == "jsii":
                        jsii_names.add(bound)
                    if top == "os" and not a.asname:
                        os_names.add("os")
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                top = mod.split(".")[0]
                if n.level and n.level > 0:
                    continue
                if top == package.split(".")[0]:
                    continue
                parts = mod.split(".")
                if top not in ALLOWED_MODULES:
                    add(path, n, "R1", f"import from {mod!r} is not allowed")
                    continue
                if top == "aws_cdk" and len(parts) > 1 and parts[1] in BANNED_CDK_SUBMODULES:
                    add(path, n, "R1", f"import from {mod!r} is not allowed")
                if top == "aws_cdk" and len(parts) == 1:
                    for a in n.names:
                        if a.name in BANNED_CDK_SUBMODULES:
                            add(path, n, "R1", f"import of aws_cdk.{a.name} is not allowed")
                if top == "jsii":
                    for a in n.names:
                        if a.name != "implements":
                            add(path, n, "R4", f"jsii.{a.name} is not allowed (only the implements decorator)")
                if top == "os" and mod not in ("os", "os.path"):
                    add(path, n, "R1", f"import from {mod!r} is not allowed (os.path only)")
                if top == "os" and mod == "os":
                    for a in n.names:
                        if a.name != "path":
                            add(path, n, "R1", f"os.{a.name} is not allowed (os.path only)")
                for a in n.names:
                    if a.name == "*":
                        add(path, n, "R1", "star imports are not allowed")
                    package_names.add(a.asname or a.name)

        # names aliasing an imported package member (x = cdk.Names; y = x): they count as the package (R5)
        tainted = set(package_names)
        for _ in range(3):
            for n in ast.walk(tree):
                if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                    root = root_name(n.value)
                    if root in tainted:
                        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                        for t in targets:
                            for x in ast.walk(t):
                                if isinstance(x, ast.Name):
                                    tainted.add(x.id)

        for n in ast.walk(tree):
            # R2 banned builtins
            if isinstance(n, ast.Name) and n.id in BANNED_NAMES:
                add(path, n, "R2", f"{n.id!r} is not allowed")
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "type" and len(n.args) == 3:
                add(path, n, "R2", "three-argument type() is not allowed")
            # R4 dunders and jsii internals
            if isinstance(n, ast.Attribute):
                if n.attr.startswith("__") and n.attr.endswith("__") and n.attr != "__init__":
                    add(path, n, "R4", f"attribute {n.attr!r} is not allowed")
                if "jsii" in n.attr.lower() and not (n.attr == "implements" and root_name(n) in jsii_names):
                    add(path, n, "R4", f"attribute {n.attr!r} is not allowed")
                if root_name(n) in jsii_names and n.attr != "implements":
                    add(path, n, "R4", f"jsii.{n.attr} is not allowed (only the implements decorator)")
                if root_name(n) in os_names and isinstance(n.value, ast.Name) and n.attr != "path":
                    add(path, n, "R1", f"os.{n.attr} is not allowed (os.path only)")
            if isinstance(n, ast.Name) and n.id.startswith("__") and n.id.endswith("__") \
                    and n.id not in ("__name__", "__file__"):
                add(path, n, "R4", f"name {n.id!r} is not allowed")
            if isinstance(n, ast.Name) and "jsii" in n.id.lower() and n.id not in jsii_names:
                add(path, n, "R4", f"name {n.id!r} is not allowed")
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if n.name.startswith("__") and n.name.endswith("__") and n.name != "__init__":
                    add(path, n, "R4", f"method {n.name!r} is not allowed")
            # R3 raw CloudFormation
            if isinstance(n, ast.Call):
                name = last_name(n.func)
                if name and re.match(r"^Cfn[A-Z0-9]", name) and name not in CFN_STRUCTS \
                        and not name.endswith(("Props", "Property")):
                    add(path, n, "R3", f"{name}(...) (raw CloudFormation) is not allowed")
                if isinstance(n.func, ast.Attribute) and n.func.attr == "synth":
                    add(path, n, "R6", ".synth() is not allowed in the app code")
                if name in app_like:
                    add(path, n, "R6", f"{name}(...) is not allowed in the app code")
            if isinstance(n, ast.Attribute) and n.attr in OVERRIDES:
                add(path, n, "R3", f"{n.attr} (a raw CloudFormation override) is not allowed")
            if isinstance(n, ast.Name) and n.id in OVERRIDES:
                add(path, n, "R3", f"{n.id} (a raw CloudFormation override) is not allowed")
            if isinstance(n, ast.ClassDef):
                for b in n.bases:
                    base = last_name(b)
                    if base and re.match(r"^Cfn[A-Z0-9]", base):
                        add(path, n, "R3", f"extending {base} is not allowed")
                for item in n.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "node":
                        add(path, item, "R5", "defining a member named `node` is not allowed")
                    if isinstance(item, (ast.Assign, ast.AnnAssign)):
                        tgts = item.targets if isinstance(item, ast.Assign) else [item.target]
                        if any(isinstance(t, ast.Name) and t.id == "node" for t in tgts):
                            add(path, item, "R5", "defining a member named `node` is not allowed")
            # R5 patching
            targets = []
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                targets = [n.target]
            elif isinstance(n, ast.Delete):
                targets = n.targets
            for t in targets:
                for x in ([t] if not isinstance(t, (ast.Tuple, ast.List)) else list(t.elts)):
                    if isinstance(x, (ast.Attribute, ast.Subscript)):
                        root = root_name(x)
                        if root in tainted:
                            add(path, n, "R5", f"assigning to a member of {root!r} (an imported package) is not allowed")
                        if isinstance(x, ast.Attribute) and x.attr == "node":
                            add(path, n, "R5", "assigning to a member named `node` is not allowed")

        code = code_text(text)
        for h in hashes:
            for m in re.finditer(re.escape(h) + r"(?=[0-9a-f]{32}(?![0-9A-Za-z])|(?![0-9A-Za-z]))", code):
                line = code.count("\n", 0, m.start()) + 1
                violations.append({"rule": "R7", "file": os.path.relpath(path, project_dir), "line": line,
                                   "message": f"{h!r} is a hash from the deployed templates"})
    return {"files": len(sources), "violations": violations}


def deployed_hashes(project_dir):
    found = set()
    root = os.path.join(project_dir, "deployed")
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".template.json"):
                found |= template_hashes(json.load(open(os.path.join(dirpath, f))))
    return sorted(found)


def guess_code_dir(project_dir):
    """The app's package: the directory next to app.py with an __init__.py (when --code-dir is not given)."""
    cands = sorted(d for d in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, d, "__init__.py"))
                   and d not in ("tests", "test", "grade", "tools", "scripts"))
    return cands[0] if cands else "app"


def main(argv):
    args, code_dir, hashes_file, json_out = [], None, None, None
    i = 0
    while i < len(argv):
        if argv[i] == "--code-dir":
            code_dir = argv[i + 1]
            i += 2
        elif argv[i] == "--hashes":
            hashes_file = argv[i + 1]
            i += 2
        elif argv[i] == "--json":
            json_out = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    project = os.path.abspath(args[0] if args else ".")
    code_dir = code_dir or guess_code_dir(project)
    hashes = json.load(open(hashes_file)) if hashes_file else deployed_hashes(project)
    res = check(project, code_dir, hashes)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(res, fh, indent=1)
    for v in res["violations"]:
        print(f"{v['file']}:{v['line']}: {v['rule']} {v['message']}")
    print(f"rules: {len(res['violations'])} violation(s) in {res['files']} file(s)" if res["violations"]
          else f"rules: OK ({res['files']} files)")
    return 1 if res["violations"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
