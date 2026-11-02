# Audit the selection: duplicates (name, sheet family, shared prompt) and versions (sheet-selected vs active vs Argon's runs per version).
import sys, os, json, re, time, collections, hashlib, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from common import *
from cat_common import base_name
from _horizon_lib import client
c = client.Client(); os.makedirs(f'{H}/audit', exist_ok=True)
U = [t for t in json.load(open(f'{H}/universe.json'))['tasks'] if t.get('tier')]
def get(path, params=None):
    for a in range(20):
        try: return c.get(path, params)
        except Exception: time.sleep(1 + a % 4)
def pull(t):
    out = f"{H}/audit/{t['id']}.json"
    if os.path.exists(out): return json.load(open(out))
    meta = get(f"api/tasks/{t['id']}") or {}
    ro = get(f"api/tasks/{t['id']}/rollouts") or {}
    d = {'meta': {k: v for k, v in meta.items() if not isinstance(v, (dict, list)) or k in ('versions',)},
         'rollouts': [{k: x.get(k) for k in ('id', 'model', 'passed', 'is_errored', 'task_version_number', 'extracted_score')} for x in ro.get('rollouts') or []]}
    json.dump(d, open(out, 'w')); return d
with cf.ThreadPoolExecutor(8) as ex: A = dict(zip([t['id'] for t in U], ex.map(pull, U)))
print('meta keys', sorted(next(iter(A.values()))['meta'].keys()))
# --- versions
FC = full_catalogue(); SELV = {s['name']: s for s in selection()}
import openpyxl
U2 = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Updated selection 120'].iter_rows(values_only=True))
SV = {x[1]: int(float(x[11])) for x in U2[6:] if len(x) > 11 and x[1] and x[11]}
FV = {o['Task']: int(float(o['Selected task version'])) for o in FC if o.get('Selected task version') not in (None, '', 'Not captured')
      and re.match(r'^\d+(\.0)?$', str(o['Selected task version']))}
ARG = {k for k, v in MM.items() if v == ARGON}
rep = []
for t in U:
    a = A[t['id']]; cur = a['meta'].get('current_version'); used = RO[t['id']]['version']
    sheet = SV.get(t['name']) or FV.get(t['name'])
    pv = collections.defaultdict(lambda: [0, 0])
    for q in a['rollouts']:
        if q['model'] in ARG and not q.get('is_errored') and q.get('passed') is not None:
            pv[q['task_version_number']][0] += 1; pv[q['task_version_number']][1] += bool(q['passed'])
    rep.append({'name': t['name'], 'id': t['id'], 'catalog': t['catalog'], 'tier': t['tier'], 'sample': t.get('sample'), 'used': used, 'sheet_nov02': sheet,
                'active': cur, 'versions': a['meta'].get('total_versions'), 'archived': a['meta'].get('archived'), 'status': a['meta'].get('status'),
                'argon_by_version': {str(k): v for k, v in sorted(pv.items())}})
json.dump(rep, open(f'{H}/audit/report.json', 'w'), indent=1)
C = collections.Counter()
for r in rep:
    C['used==sheet' if r['used'] == r['sheet_nov02'] else 'used!=sheet' if r['sheet_nov02'] else 'not in sheet'] += 1
    C['used==active' if r['used'] == r['active'] else 'used<active' if r['active'] and r['used'] < r['active'] else 'used>active'] += 1
    if len(r['argon_by_version']) > 1: C['argon on several versions'] += 1
    if r['archived']: C['archived'] += 1
print(C); print('status', collections.Counter(r['status'] for r in rep))
for r in rep:
    if r['sample'] or len(r['argon_by_version']) > 1 or (r['sheet_nov02'] and r['used'] != r['sheet_nov02']):
        print(f"{(r['sample'] or '-'):8} {r['tier']:6} {r['catalog'][:12]:12} {r['name'][:46]:46} used v{r['used']} sheet v{r['sheet_nov02']} active v{r['active']} argon {r['argon_by_version']}")
# --- duplicates
names = [t['name'] for t in U]
bn = collections.Counter(base_name(n) for n in names); print('base-name dupes', [k for k, v in bn.items() if v > 1])
stem = collections.defaultdict(list)
for n in names: stem[re.sub(r'(-[0-9a-f]{4}|-ots|-shared|-xai|-pdk|-canonical|-blind\d+|-[0-9a-f]{8})+$', '', n)].append(n)
print('same stem', {k: v for k, v in stem.items() if len(v) > 1})
fam = {}
for o in FC:
    ids = set(re.findall(r'[0-9a-f]{8}-[0-9a-f-]{27}', str(o.get('Other task IDs in this family') or '')))
    for i in ids: fam.setdefault(i, set()).add(o['Task'])
ourids = {t['id']: t['name'] for t in U}
hits = [(ourids[i], sorted(fam[i])) for i in ourids if i in fam and any(x in names and x != ourids[i] for x in fam[i])]
print('same sheet family', hits)
print('family members of ours listed under another family row', [(ourids[i], sorted(fam[i])) for i in ourids if i in fam][:20])
