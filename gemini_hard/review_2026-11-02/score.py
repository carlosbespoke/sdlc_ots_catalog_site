#!/usr/bin/env python3
"""Check ledger coverage against the tree, then compute knockouts K1-K3, hierarchy penalties and information value.
Usage: score.py tree.json ledger.jsonl   (exit 1 if any node is missing from the ledger)"""
import json, sys
tree = json.load(open(sys.argv[1]))
led = {}
for ln in open(sys.argv[2]):
    if ln.strip():
        r = json.loads(ln); led[r["id"]] = r
def walk(n):
    yield n
    for c in n.get("children", []): yield from walk(c)
nodes = [n for n in walk(tree) if n["type"] != "block"]
missing = [n["id"] for n in nodes if n["id"] not in led]
if missing:
    print(json.dumps({"complete": False, "missing": missing[:50], "missing_count": len(missing)}, indent=1)); sys.exit(1)

paras = [n for n in nodes if n["type"] == "paragraph"]
secs = [n for n in nodes if n["type"] == "section"]
sents = [n for n in nodes if n["type"] in ("sentence", "item")]
d = led["D"]
pen, why = 0, []
def para_fail(r, node=None):
    if r.get("exception") in ("transition", "emphasis"): return False
    off = node and any(led[c["id"]].get("supports_parent") is False for c in node["children"] if c["type"] == "sentence")
    return bool(off) or (not r.get("main_idea_sentence")) or not r.get("position_ok", True) or not r.get("one_idea", True) \
        or bool(r.get("offtopic_sentences")) or r.get("ends_on_new_idea", False)
breaks = [p["id"] for p in paras if not led[p["id"]].get("supports_section", True)]
fails = [p["id"] for p in paras if p["id"] not in breaks and para_fail(led[p["id"]], p)]
sec_breaks = [s["id"] for s in secs if not led[s["id"]].get("supports_parent", True)]
for i in breaks: pen += 5; why.append((i, "paragraph-level hierarchy break", -5))
for i in fails: pen += 4; why.append((i, "failed paragraph test", -4))
for n in [d] + [led[s["id"]] for s in secs]:
    if n.get("buried_lead"): pen += 3; why.append((n["id"], "buried lead", -3))
    for _ in range(n.get("sibling_faults", 0)): pen += 2; why.append((n["id"], "sibling fault", -2))
for p in paras:
    if not led[p["id"]].get("link_ok", True): pen += 1; why.append((p["id"], "missing link", -1))
npar = len(paras)
k3_limit = 1 if npar <= 2 else (2 if npar <= 20 else 3)
ko = {
 "K1": bool(d.get("main_idea")) and d.get("stated_first", False),
 "K2": not sec_breaks and len(breaks) < 2,
 "K3": (sum(1 for p in paras if para_fail(led[p["id"]], p) or p["id"] in breaks) < k3_limit),
}
lab = [led[s["id"]].get("label") for s in sents]
counted = [l for l, s in zip(lab, sents) if not led[s["id"]].get("allowed_exception")]
new = sum(1 for l in counted if l == "new")
iv = new / len(counted) if counted else 1.0
iv_level = 4 if iv >= .95 else 3 if iv >= .85 else 2 if iv >= .70 else 1
offparent = [s["id"] for s in sents if led[s["id"]].get("supports_parent") is False]
print(json.dumps({"complete": True, "counts": {"sections": len(secs), "paragraphs": npar, "sentences_and_items": len(sents)},
 "knockouts_structural": {k: ("pass" if v else "KO") for k, v in ko.items()},
 "section_breaks": sec_breaks, "paragraph_breaks": breaks, "failed_paragraphs": fails,
 "sentences_not_supporting_parent": offparent,
 "hierarchy_penalty": -pen, "penalty_items": why,
 "information_value": {"share_new": round(iv, 3), "level": iv_level,
   "labels": {l: lab.count(l) for l in set(lab)}}}, indent=1))
