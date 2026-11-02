# Pull current runs (at the selected task version) for every catalog task and every task in the sheet's "Updated selection 120" tab, into ro3/.
import sys, os, json, re, time, collections, concurrent.futures as cf
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; os.environ['B'] = P
sys.path.insert(0, f'{P}/bin'); sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from cat_common import load_rows, green, dedupe, shortlist
from _horizon_lib import client
import openpyxl
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = client.Client(); os.makedirs(f'{H}/ro3', exist_ok=True)
F = {o['name']: o for o in json.load(open(f'{P}/fullcat/full.json')) if o['status'].startswith('Green')}
T = {t['id']: t for t in json.load(open(f'{P}/rfc/tasks.json'))}
R = [r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist()) if r['catalog'] != 'Optimization']
import re as _re
_FC = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Full catalogue'].iter_rows(values_only=True))
_hd = list(_FC[5]); NOV = {}
for x in _FC[6:]:
    o = dict(zip(_hd, x))
    if o.get('Task') and _re.match(r'^\d+(\.0)?$', str(o.get('Selected task version') or '')): NOV[o['Task']] = int(float(o['Selected task version']))
def version(r):
    if r['name'] in NOV: return NOV[r['name']]  # the 2 Nov sheet's selected version, the same source as the shortlist
    v = F.get(r['name'], {}).get('ver')
    return int(v) if v else (T[r['id']]['current_version'] if r['id'] in T else json.load(open(f"{P}/ro/{r['id']}.json"))['version'])
jobs = [(r['id'], r['name'], version(r)) for r in R]
have = {r['id'] for r in R} | {r['name'] for r in R}
U = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Updated selection 120'].iter_rows(values_only=True))
for x in U[6:]:
    if len(x) < 12 or not x[1]: continue
    tid = re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}', x[10] or '').group(0)
    if tid not in have and x[1] not in have: jobs.append((tid, x[1], int(float(x[11]))))
def get(path, params=None):
    for a in range(6):
        try: return c.get(path, params)
        except Exception: time.sleep(2 * (a + 1))
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
def pull(j):
    tid, name, v = j; out = f'{H}/ro3/{tid}.json'
    if os.path.exists(out): return 'cached'
    d = get(f'api/tasks/{tid}/rollouts', {'task_version': str(v)})
    if d is None: return 'fail'
    rs = d.get('rollouts') or []
    json.dump({'id': tid, 'name': name, 'version': v, 'grouped': d.get('groupedStats') or [], 'n_rollouts': len(rs),
               'rollouts': [{k: x.get(k) for k in KEEP} for x in rs]}, open(out, 'w'))
    return 'ok'
with cf.ThreadPoolExecutor(8) as ex: print(len(jobs), collections.Counter(ex.map(pull, jobs)))
