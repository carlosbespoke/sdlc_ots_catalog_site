# Extend the turn data to every Green task with current-version runs: one random completed run per task (same method as turns_sample.py).
import sys, os, json, time, random, concurrent.futures as cf
B = sys.argv[1]; os.environ['B'] = B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from cat_common import load_rows, green
from _horizon_lib import client
c = client.Client()
T = {t['id']: t for t in json.load(open(f'{B}/rfc/tasks.json'))}
def has_runs(i):
    p = f"{B}/ro/{i}.json"
    return os.path.exists(p) and any((g['total_rollouts'] or 0) - (g['error_count'] or 0) > 0 for g in json.load(open(p))['grouped'])
todo = sorted({r['id'] for r in green(load_rows()) if r['catalog'] and has_runs(r['id']) and not os.path.exists(f"{B}/turns_s/{r['id']}.json")})
print('to fetch', len(todo), flush=True)
def get(path, params=None):
    for a in range(6):
        try: return c.get(path, params)
        except Exception: time.sleep(2 * (a + 1))
    return None
def one(i):
    t = T[i]; out = f"{B}/turns_s/{i}.json"; r = random.Random(i)
    d = get(f"api/tasks/{i}/rollouts", {'task_version': str(t['current_version'])})
    if d is None: return 'fail'
    ok = [x for x in d.get('rollouts') or [] if not x.get('is_errored')]
    if not ok:
        json.dump({'id': i, 'batch': t['batch_name'], 'runs': []}, open(out, 'w')); return 'none'
    pick = r.choice(sorted(ok, key=lambda x: x['id']))
    x = get(f"api/rollouts/{pick['id']}")
    if x is None: return 'fail'
    json.dump({'id': i, 'batch': t['batch_name'], 'runs': [{'id': pick['id'], 'model': pick.get('model'), 'turn_count': x.get('turn_count'),
               'max_turns': x.get('max_turns'), 'is_errored': False, 'passed': pick.get('passed')}], 'source': 'api-green'}, open(out, 'w'))
    return 'ok'
import collections
with cf.ThreadPoolExecutor(6) as ex: print(collections.Counter(ex.map(one, todo)))
