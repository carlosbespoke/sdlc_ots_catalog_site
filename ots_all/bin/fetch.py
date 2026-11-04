# Fill the gaps in the 2 Nov snapshot copied from ../gemini_hard/ro3 (ro/): runs of the Optimization tasks, which that pull left out,
# and the turn count of every completed run of every model (turns/), reusing counts already fetched for the same run ids.
import sys, os, json, re, time, collections, concurrent.futures as cf
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; G = '/Users/carlos/code/sdlc_final_samples/gemini_hard'
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
import openpyxl
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = client.Client(); os.makedirs(f'{H}/turns', exist_ok=True)
def get(path, params=None, tries=25):
    for a in range(tries):  # the rollout endpoint returns intermittent 404s
        try: return c.get(path, params)
        except Exception: time.sleep(1 + a % 4)
# 1. Optimization runs, at the 2 Nov sheet's selected version (else the full catalogue's, else the task's current version)
FC = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Full catalogue'].iter_rows(values_only=True))
hd = list(FC[5]); NOV = {}
for x in FC[6:]:
    o = dict(zip(hd, x))
    if o.get('Task') and re.match(r'^\d+(\.0)?$', str(o.get('Selected task version') or '')): NOV[o['Task']] = int(float(o['Selected task version']))
F = {o['name']: o for o in json.load(open(f'{P}/fullcat/full.json'))}
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
U = json.load(open(f'{G}/universe.json'))['tasks']
for t in U:
    out = f"{H}/ro/{t['id']}.json"
    if os.path.exists(out): continue
    v = NOV.get(t['name']) or (int(F[t['name']]['ver']) if F.get(t['name'], {}).get('ver') else get(f"api/tasks/{t['id']}", tries=6)['current_version'])
    d = get(f"api/tasks/{t['id']}/rollouts", {'task_version': str(v)}, tries=6) or {}
    rs = d.get('rollouts') or []
    json.dump({'id': t['id'], 'name': t['name'], 'version': v, 'grouped': d.get('groupedStats') or [], 'n_rollouts': len(rs),
               'rollouts': [{k: x.get(k) for k in KEEP} for x in rs]}, open(out, 'w'))
    print('runs', t['name'], 'v', v, len(rs))
# 2. turn counts
cache = {}
for d in [f'{P}/{x}' for x in ('turns_all', 'turns', 'turns_s', 'turns_x')] + [f'{G}/turns', f'{H}/turns']:
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.startswith('_'): continue
        for q in json.load(open(f'{d}/{f}')).get('runs', []):
            if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
runs = {t['id']: [q for q in json.load(open(f"{H}/ro/{t['id']}.json"))['rollouts'] if not q.get('is_errored')] for t in U}
need = [q['id'] for v in runs.values() for q in v if q['id'] not in cache]
with cf.ThreadPoolExecutor(6) as ex: got = dict(zip(need, ex.map(lambda i: get(f'api/rollouts/{i}'), need)))
miss = collections.Counter()
for tid, v in runs.items():
    out = []
    for q in v:
        x = cache.get(q['id']) or got.get(q['id']) or {}
        if not isinstance(x.get('turn_count'), (int, float)): miss[q['model']] += 1; continue
        out.append({'id': q['id'], 'model': q['model'], 'turn_count': x['turn_count'], 'max_turns': x.get('max_turns'), 'passed': q.get('passed')})
    json.dump({'id': tid, 'runs': out}, open(f'{H}/turns/{tid}.json', 'w'))
print('tasks', len(U), 'completed runs', sum(map(len, runs.values())), 'fetched', len(need), 'without turn count', dict(miss))
