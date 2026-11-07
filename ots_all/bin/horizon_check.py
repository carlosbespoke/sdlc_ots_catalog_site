# Compare the report's runs (ro/) with live Horizon, task by task, at each task's report version and every newer version.
# For every run in ro/: does it still exist, with the same model, version, score, passed and errored values?
# For every run on Horizon at those versions that ro/ lacks: is it from after LATE_CUTOFF (expected) or before (a gap)?
# Runs of models the report does not know (not in MM) are listed apart.
# Also: task name and whether the report version is still the task's current version.
#     python bin/horizon_check.py  ->  audit/horizon_check.json
import sys, os, json, time, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f'{H}/bin')
from common import TASKS, DROPPED, MM
SNAP = open(f'{H}/LATE_CUTOFF').read().strip()
c = client.Client()
def get(path, params=None, tries=12):
    for a in range(tries):
        try: return c.get(path, params)
        except Exception as e: err = e; time.sleep(1 + a % 4)
    return {'_error': str(err)}
F = ('model', 'task_version_number', 'extracted_score', 'passed', 'is_errored')
def one(t):
    r = json.load(open(f"{H}/ro/{t['id']}.json")); v = r['version']; out = {'task': t['name'], 'id': t['id'], 'version': v, 'issues': []}
    meta = get(f"api/tasks/{t['id']}")
    if '_error' in meta: out['issues'].append(('task fetch failed', meta['_error'])); return out
    if meta.get('name') != t['name']: out['issues'].append(('name differs', meta.get('name')))
    out['current_version'] = meta.get('current_version'); out['status'] = meta.get('status')
    d = get(f"api/tasks/{t['id']}/rollouts", {})  # every version
    if '_error' in d: out['issues'].append(('rollout fetch failed', d['_error'])); return out
    live = {x['id']: x for x in d.get('rollouts') or [] if (x.get('task_version_number') or 0) >= v}; camp = set(r.get('campaign_rollouts', []))
    for q in r['rollouts']:
        x = live.get(q['id'])
        if x is None: out['issues'].append(('snapshot run missing on Horizon', q['id'], q['model'])); continue
        diff = {k: (q.get(k), x.get(k)) for k in F if q.get(k) != x.get(k)}
        if diff: out['issues'].append(('run changed', q['id'], q['model'], diff))
    have = {q['id'] for q in r['rollouts']}
    for i, x in live.items():
        if i in have or x['model'] in DROPPED: continue
        if x['model'] not in MM: out.setdefault('unknown_model', []).append((i, x['model'])); continue
        late = (x.get('created_at') or '')[:16] > SNAP[:16]
        out.setdefault('extra_after' if late else 'extra_before', []).append((i, x['model'], x.get('passed'), x.get('is_errored')))
    return out
with cf.ThreadPoolExecutor(8) as ex: R = list(ex.map(one, TASKS))
json.dump(R, open(f'{H}/audit/horizon_check.json', 'w'), indent=1)
k = collections.Counter(i[0] for o in R for i in o['issues'])
print('tasks', len(R), 'issues by kind', dict(k))
print('tasks with kept-model runs before LATE_CUTOFF but missing from ro/:', sum(1 for o in R if o.get('extra_before')), 'runs', sum(len(o.get('extra_before', [])) for o in R))
print('tasks with kept-model runs after LATE_CUTOFF (left out by design):', sum(1 for o in R if o.get('extra_after')), 'runs', sum(len(o.get('extra_after', [])) for o in R))
print('runs of models the report does not know:', sum(len(o.get('unknown_model', [])) for o in R))
print('report version is not the current version:', sum(1 for o in R if o.get('current_version') not in (None, o['version'])))
print('status', collections.Counter(o.get('status') for o in R))
