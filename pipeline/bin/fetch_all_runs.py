# Refresh every catalog task's runs at the sheet's selected version (ro2/), then fetch turn_count for every completed run (turns_all/).
import sys, os, json, re, time, collections, concurrent.futures as cf
B = sys.argv[1]; os.environ['B'] = B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from cat_common import load_rows, green, dedupe, shortlist
from _horizon_lib import client
c = client.Client()
os.makedirs(f'{B}/ro2', exist_ok=True); os.makedirs(f'{B}/turns_all', exist_ok=True)
F = {o['name']: o for o in json.load(open(f'{B}/fullcat/full.json')) if o['status'].startswith('Green')}
T = {t['id']: t for t in json.load(open(f'{B}/rfc/tasks.json'))}
R = [r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist()) if r['catalog'] != 'Optimization']
def version(r):
    v = F.get(r['name'], {}).get('ver')
    return int(v) if v else (T[r['id']]['current_version'] if r['id'] in T else json.load(open(f"{B}/ro/{r['id']}.json"))['version'])
def get(path, params=None):
    for a in range(6):
        try: return c.get(path, params)
        except Exception: time.sleep(2 * (a + 1))
    return None
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
def runs_of(r):
    out = f"{B}/ro2/{r['id']}.json"
    if os.path.exists(out): return 'cached'
    v = version(r); d = get(f"api/tasks/{r['id']}/rollouts", {'task_version': str(v)})
    if d is None: return 'fail'
    rs = d.get('rollouts') or []
    json.dump({'id': r['id'], 'name': r['name'], 'version': v, 'grouped': d.get('groupedStats') or [], 'n_rollouts': len(rs),
               'rollouts': [{k: x.get(k) for k in KEEP} for x in rs]}, open(out, 'w'))
    return 'ok'
with cf.ThreadPoolExecutor(6) as ex: print('runs', collections.Counter(ex.map(runs_of, R)), flush=True)
# cached turn counts by run id
cache = {}
for d in ('turns', 'turns_s', 'turns_x', 'turns_all'):
    for f in os.listdir(f'{B}/{d}') if os.path.isdir(f'{B}/{d}') else []:
        if f.startswith('_'): continue
        x = json.load(open(f'{B}/{d}/{f}'))
        for q in x.get('runs', []):
            if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
jobs = []
for r in R:
    p = f"{B}/ro2/{r['id']}.json"
    if not os.path.exists(p): continue
    for q in json.load(open(p))['rollouts']:
        if not q.get('is_errored') and q['id'] not in cache: jobs.append(q['id'])
print('turn lookups needed', len(jobs), 'cached', len(cache), flush=True)
done = [0]
def det(i):
    x = get(f'api/rollouts/{i}')
    done[0] += 1
    if done[0] % 250 == 0: print('  turns', done[0], '/', len(jobs), flush=True)
    if x is None: return i, None
    return i, {'turn_count': x.get('turn_count'), 'max_turns': x.get('max_turns'), 'stop_reason': x.get('stop_reason')}
with cf.ThreadPoolExecutor(6) as ex: got = dict(ex.map(det, jobs))
miss = 0
for r in R:
    p = f"{B}/ro2/{r['id']}.json"
    if not os.path.exists(p): continue
    runs = []
    for q in json.load(open(p))['rollouts']:
        if q.get('is_errored'): continue
        t = cache.get(q['id']) or got.get(q['id'])
        if not t or not isinstance(t.get('turn_count'), (int, float)): miss += 1; continue
        runs.append({'id': q['id'], 'model': q.get('model'), 'turn_count': t['turn_count'], 'max_turns': t.get('max_turns'), 'passed': q.get('passed'), 'is_errored': False})
    json.dump({'id': r['id'], 'runs': runs}, open(f"{B}/turns_all/{r['id']}.json", 'w'))
print('done; completed runs without a turn count', miss)
