import json, os
B = os.environ.get('B') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATS = [('programbench', 'ProgramBench'), ('system-design', 'System design'), ('debugging', 'Diagnosis, Debugging, and Bug Fixing'),
        ('feature-implementation', 'Feature implementation'), ('infrastructure-as-code', 'Infrastructure as code'),
        ('data-engineering', 'Data engineering'), ('migration', 'Migration')]
def catalog_of(final):
    if final.startswith('ProgramBench'): return 'ProgramBench'
    if final in ('System design', 'Fault tolerance'): return 'System design'
    if final == 'SRE (parked)': return None
    return final
def load_rows():
    X = json.load(open(f'{B}/rfc/explorer.json')); I = {k: i for i, k in enumerate(X['keys'])}
    T = {}
    for f in os.listdir(f'{B}/rfc/t'):
        t = json.load(open(f'{B}/rfc/t/{f}')); T[(t['name'], t['batch'])] = t
    rows = []
    for r in X['rows']:
        d = {k: X['dicts'][k][r[I[k]]] for k in X['keys']}; d['name'] = r[-1]
        t = T[(d['name'], d['batch'])]; d['id'] = t['id']; d['instr'] = t['instr']; d['toml'] = t['toml']
        d['catalog'] = catalog_of(d['final']); rows.append(d)
    return rows
def shortlist():
    from openpyxl import load_workbook
    wb = load_workbook('/Users/carlos/code/sdlc_final_samples/task_taxonomies_final.xlsx'); t = wb['Taxonomies']; H = [c.value for c in t[2]]
    return {t.cell(r, H.index('Task') + 1).value: t.cell(r, H.index('Rank') + 1).value for r in range(3, t.max_row + 1)}

import re, collections
def base_name(n):
    n = re.sub(r'^tests-(half-alt|half|quarter|50pct|75pct|25pct)-(go-|python-)?', '', n)
    return re.sub(r'(-ots|-shared)$', '', n)
def dedupe(rows, SL=None):
    """One task per base name: drop renamed or re-published copies of the same task.
    Keep the shortlist copy, else the copy with most graded runs on its current version, else the first by name."""
    SL = SL or {}
    def graded(r):
        p = f"{B}/ro/{r['id']}.json"
        if not os.path.exists(p): return 0
        return sum(g.get('graded_count') or 0 for g in json.load(open(p))['grouped'])
    g = collections.defaultdict(list)
    for r in rows: g[base_name(r['name'])].append(r)
    keep = []
    for k, v in g.items():
        v.sort(key=lambda r: (r['name'] not in SL, -graded(r), r['name'], r['batch']))
        v[0]['copies'] = len(v); keep.append(v[0])
    return keep

def green(rows):
    """Keep only tasks whose client presentation status is Green in the 'Full catalogue' tab (fullcat/full.json).
    Match by the Horizon task id in the sheet's link, else by task name."""
    F = json.load(open(f'{B}/fullcat/full.json'))
    G = [o for o in F if (o['status'] or '').startswith('Green')]
    ids = {re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}', o['url'] or '').group(0) for o in G if o['url']}
    names = {o['name'] for o in G}
    have = {r['id'] for r in rows}
    # same-name tasks whose sheet link points at a different Horizon task: keep our classification, use the sheet's id (its runs are in ro/)
    loose = {o['name']: re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}', o['url']).group(0) for o in G
             if not any(i in have for i in re.findall(r'[0-9a-f]{8}-[0-9a-f-]{27}', o['url'] or ''))}
    out, done = [], set()
    for r in rows:
        if r['id'] in ids: out.append(r)
        elif r['name'] in loose and r['name'] not in done: out.append({**r, 'id': loose[r['name']]}); done.add(r['name'])
    return out
