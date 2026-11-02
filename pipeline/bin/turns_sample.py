# Turn counts on a sample: half of the tasks with current-version runs in each batch, one random completed run per task.
import sys, os, json, time, random, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
c = client.Client(); B = sys.argv[1]; rng = random.Random(20261027)
tasks = json.load(open(f'{B}/rfc/tasks.json'))
def has_runs(t):
    x = json.load(open(f"{B}/ro/{t['id']}.json"))
    return any((g['total_rollouts'] or 0) - (g['error_count'] or 0) > 0 for g in x['grouped'])
by = collections.defaultdict(list)
for t in sorted(tasks, key=lambda t: t['id']):
    if has_runs(t): by[t['batch_name']].append(t)
sample = []
for b in sorted(by):
    L = by[b]; k = max(1, round(len(L) / 2)); sample += rng.sample(L, k)
json.dump({'seed': 20261027, 'per_batch': {b: [len(by[b]), max(1, round(len(by[b]) / 2))] for b in sorted(by)}, 'ids': [t['id'] for t in sample]}, open(f'{B}/turns_s/_sample.json', 'w'))
def get(path, params=None):
    for a in range(6):
        try: return c.get(path, params)
        except Exception: time.sleep(2 * (a + 1))
    return None
def one(t):
    out = f"{B}/turns_s/{t['id']}.json"
    if os.path.exists(out): return
    r = random.Random(t['id'])
    cached = f"{B}/turns/{t['id']}.json"
    if os.path.exists(cached):
        runs = [x for x in json.load(open(cached))['runs'] if not x.get('is_errored') and x.get('turn_count') is not None]
        if runs:
            json.dump({'id': t['id'], 'batch': t['batch_name'], 'runs': [r.choice(runs)], 'source': 'cache'}, open(out, 'w')); return
    d = get(f"api/tasks/{t['id']}/rollouts", {'task_version': str(t['current_version'])})
    if d is None: return
    ok = [x for x in d.get('rollouts') or [] if not x.get('is_errored')]
    if not ok:
        json.dump({'id': t['id'], 'batch': t['batch_name'], 'runs': []}, open(out, 'w')); return
    pick = r.choice(sorted(ok, key=lambda x: x['id']))
    x = get(f"api/rollouts/{pick['id']}") or {}
    json.dump({'id': t['id'], 'batch': t['batch_name'], 'runs': [{'id': pick['id'], 'model': pick.get('model'), 'turn_count': x.get('turn_count'),
               'max_turns': x.get('max_turns'), 'is_errored': False, 'passed': pick.get('passed')}], 'source': 'api'}, open(out, 'w'))
with cf.ThreadPoolExecutor(6) as ex: list(ex.map(one, sample))
print('sampled', len(sample), 'of', sum(len(v) for v in by.values()), 'tasks with runs; files', len(os.listdir(f'{B}/turns_s')) - 1)
