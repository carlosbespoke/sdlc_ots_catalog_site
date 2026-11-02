# turn_count for every rollout on each ready-for-client task's current version (detail endpoint; the listings return null).
import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
c = client.Client(); B = sys.argv[1]; CAP = 3
tasks = json.load(open(f'{B}/rfc/tasks.json'))
def get(path, params=None):
    for a in range(6):
        try: return c.get(path, params)
        except Exception: time.sleep(2 * (a + 1))
    return None
def one(t):
    out = f"{B}/turns/{t['id']}.json"
    if os.path.exists(out): return
    ro = json.load(open(f"{B}/ro/{t['id']}.json"))
    if not ro['grouped']:
        json.dump({'id': t['id'], 'runs': []}, open(out, 'w')); return
    d = get(f"api/tasks/{t['id']}/rollouts", {'task_version': str(t['current_version'])})
    if d is None: return
    # sample: up to 3 non-errored runs per model (first by run order), fetched in parallel
    per, sel = {}, []
    for r in sorted(d.get('rollouts') or [], key=lambda r: (r.get('created_at') or '', r.get('run_number') or 0)):
        if r.get('is_errored'): continue
        k = r.get('model'); per[k] = per.get(k, 0) + 1
        if per[k] <= CAP: sel.append(r)
    def det(r):
        x = get(f"api/rollouts/{r['id']}") or {}
        return {'id': r['id'], 'model': r.get('model'), 'turn_count': x.get('turn_count'), 'max_turns': x.get('max_turns'),
                'is_errored': r.get('is_errored'), 'passed': r.get('passed'), 'stop_reason': x.get('stop_reason')}
    with cf.ThreadPoolExecutor(3) as ex2: runs = list(ex2.map(det, sel))
    json.dump({'id': t['id'], 'runs': runs, 'sampled_per_model': CAP, 'non_errored_runs': sum(per.values())}, open(out, 'w'))
with cf.ThreadPoolExecutor(6) as ex: list(ex.map(one, tasks))
print(len(os.listdir(f'{B}/turns')), 'of', len(tasks))
