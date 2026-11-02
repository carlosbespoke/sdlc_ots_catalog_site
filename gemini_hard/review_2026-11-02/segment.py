#!/usr/bin/env python3
"""Split a markdown/plain-text file into a recursive idea tree with stable IDs.
Usage: segment.py input.md > tree.json
Nodes: doc > section (by heading level) > paragraph > sentence | list > item | block (table/code/figure)."""
import json, re, sys
Z = chr(0)

ABBR = r"\b(e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|Prof|Fig|Eq|Sec|No|al|approx|cf|Inc|Ltd|Jr|Sr|St|U\.S|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\."
def sentences(text):
    t = re.sub(ABBR, lambda m: m.group(0).replace(".", Z), text)
    t = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + Z + m.group(2), t)
    parts = re.split(r"(?<=[.!?])[\"”')\]]*\s+(?=[\"“(\[]?[A-Z0-9])", t)
    return [p.replace(Z, ".").strip() for p in parts if p.strip()]

def blocks(lines):
    """Yield (kind, payload) blocks: heading, para, list, block."""
    buf, kind, fence = [], None, False
    def flush():
        nonlocal buf, kind
        if buf: yield (kind, buf)
        buf, kind = [], None
    for ln in lines:
        s = ln.rstrip("\n")
        if s.strip().startswith("```"):
            if fence: buf.append(s); fence = False; yield from flush(); continue
            yield from flush(); fence = True; kind = "block"; buf = [s]; continue
        if fence: buf.append(s); continue
        if not s.strip(): yield from flush(); continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m: yield from flush(); yield ("heading", (len(m.group(1)), m.group(2).strip())); continue
        k = "list" if re.match(r"^\s*([-*+]|\d+[.)])\s+", s) else "block" if s.lstrip().startswith(("|", "![", ">")) and not s.lstrip().startswith("> ") else "para"
        if s.lstrip().startswith("> "): k, s = "para", s.lstrip()[2:]
        if kind and k != kind and not (kind == "list" and k == "para" and s.startswith("  ")): yield from flush()
        kind = kind or k; buf.append(s)
    yield from flush()

def build(path):
    lines = open(path, encoding="utf-8").readlines()
    doc = {"id": "D", "type": "doc", "title": None, "children": []}
    stack = [(0, doc)]; counters = {}
    def nid(parent, prefix):
        key = (parent["id"], prefix); counters[key] = counters.get(key, 0) + 1
        return f"{parent['id']}.{prefix}{counters[key]}"
    last_para = None
    for kind, payload in blocks(lines):
        parent = stack[-1][1]
        if kind == "heading":
            lvl, title = payload
            if lvl == 1 and doc["title"] is None and not doc["children"]:
                doc["title"] = title; continue
            while stack[-1][0] >= lvl: stack.pop()
            parent = stack[-1][1]
            sec = {"id": nid(parent, "S"), "type": "section", "title": title, "level": lvl, "children": []}
            parent["children"].append(sec); stack.append((lvl, sec)); last_para = None; continue
        if kind == "para":
            text = " ".join(x.strip() for x in payload)
            p = {"id": nid(parent, "P"), "type": "paragraph", "children": []}
            for s in sentences(text):
                p["children"].append({"id": nid(p, "s"), "type": "sentence", "text": s})
            parent["children"].append(p); last_para = p; continue
        host = last_para if last_para is not None and last_para in parent["children"] else parent
        if kind == "list":
            L = {"id": nid(host, "L"), "type": "list", "children": []}
            items, cur = [], ""
            for x in payload:
                if re.match(r"^\s*([-*+]|\d+[.)])\s+", x):
                    if cur: items.append(cur)
                    cur = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", x)
                else: cur += " " + x.strip()
            if cur: items.append(cur)
            for it in items: L["children"].append({"id": nid(L, "i"), "type": "item", "text": it.strip()})
            host["children"].append(L)
        else:
            host["children"].append({"id": nid(host, "B"), "type": "block", "text": "\n".join(payload)[:200]})
    return doc

def walk(n):
    yield n
    for c in n.get("children", []): yield from walk(c)

if __name__ == "__main__":
    tree = build(sys.argv[1])
    counts = {}
    for n in walk(tree): counts[n["type"]] = counts.get(n["type"], 0) + 1
    tree["counts"] = counts
    json.dump(tree, sys.stdout, indent=1, ensure_ascii=False)
