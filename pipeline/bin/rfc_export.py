# Export per-task rows for the explorer artifact, reusing rfc_agg's classification logic.
import sys, json, re
B = sys.argv[1]
src = open(f'{B}/bin/rfc_agg.py').read().split('N = len(rows)')[0]
src = src.replace("batch=t['batch']))", "batch=t['batch'], name=t['name'], recipe=t.get('recipe','')))")
g = {'__name__': 'x'}; sys.argv = ['x', B]; exec(src, g)
rows = g['rows']
def cust(b):
    l = b.lower()
    if 'xai' in l: return 'xAI'
    if 'cohere' in l: return 'Cohere'
    if 'gemini' in l: return 'Gemini'
    return 'Internal / unassigned'
def fam(b):
    l = b.lower()
    if 'cohere' in l: return 'Cohere (all batches)'
    if 'diagnosis' in l: return 'Diagnosis (all batches)'
    if 'programbench' in l and 'upgrade' in l: return 'ProgramBench repo upgrade (all batches)'
    if 'drift' in l: return 'Spec drift (all batches)'
    if l.startswith('migration'): return 'Migration (all batches)'
    if 'optimization' in l: return 'Optimization (all batches)'
    if l in ('rca-xai-ots', 'sre-xai-ots'): return 'RCA + SRE (xAI)'
    if 'deepswe' in l or 'featureimplementation' in l or 'feature-implementation' in l or b in ('alpharecon-blueprint-tasks', 'alpharecon-gemini-binary'):
        return 'Feature implementation / DeepSWE (all batches)'
    return b
strip = lambda s: s.replace('NEW: ', '') if s else s
keys = ['final','fstat','batch','fam','cust','recipe','sg','cat','shapec','shape','role','sen','sdlc','lang']
import os, glob
FT = {}
for f in glob.glob(f'{B}/ft_out/*.jsonl'):
    for line in open(f):
        if line.strip(): o = json.loads(line); FT[o['name']] = o['label']
FTMAP = {'SYSTEM_DESIGN': 'System design', 'FAULT_TOLERANCE': 'Fault tolerance', 'FEATURE': 'Feature implementation'}
DBG = 'Diagnosis, Debugging, and Bug Fixing'
def final(r):
    b, f, sc = r['batch'], r['fam'], r['shapec']
    if f.startswith('ProgramBench repo upgrade'): return 'ProgramBench repo upgrade', 'Batch rule'
    if b == 'programbench-reimplementation-ots': return 'ProgramBench reimplementation', 'Batch rule'
    if f.startswith('Spec drift'): return DBG, 'Spec drift folded into Diagnosis'
    if b == 'IaC-ots' or sc == 'Infrastructure as code': return 'Infrastructure as code', 'Batch rule'
    if f.startswith('Diagnosis') or b == 'rca-xai-ots': return DBG, 'Batch rule'
    if b == 'system-design-harsh-xai': return 'System design', 'Batch rule'
    if b == 'data-processing-xai-ots': return 'Data engineering', 'Batch rule'
    if f.startswith('Migration'): return 'Migration', 'Batch rule'
    if f.startswith('Optimization'): return 'Optimization', 'Batch rule'
    if b == 'SRE-xai-ots': return 'SRE (parked)', 'Parked'
    if b == 'featureimplementation-deepswe-cohere' or sc.startswith('Fault'):
        lab = FT.get(r['name'])
        return (FTMAP[lab], 'Instruction review (classifier + manual check)') if lab else ('Fault tolerance', 'Instruction review pending')
    return 'Feature implementation', 'Batch rule'
for r in rows:
    r['fam'] = fam(r['batch']); r['cust'] = cust(r['batch'])
    r['final'], r['fstat'] = final(r)
    r['shape'] = strip(r['shape'])
    r['newcat'] = r['cat'].startswith('NEW: ')
    r['cat'] = strip(r['cat'])
dicts = {k: sorted({r[k] for r in rows}) for k in keys}
idx = {k: {v: i for i, v in enumerate(dicts[k])} for k in keys}
out = {'dicts': dicts, 'newcats': sorted({r['cat'] for r in rows if r['newcat']}),
       'rows': [[idx[k][r[k]] for k in keys] + [r['name']] for r in rows], 'keys': keys}
json.dump(out, open(f'{B}/rfc/explorer.json', 'w'), separators=(',', ':'))
print(len(rows), {k: len(v) for k, v in dicts.items()})
