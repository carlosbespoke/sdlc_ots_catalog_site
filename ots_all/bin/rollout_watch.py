# Poll every evaluation in rollout_plan/launch.json until all are terminal; then write each run's result to
# rollout_plan/launch_results.json and print graded/errored counts per task and model.
import json, time, sys, os, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib.client import Client
c = Client(); OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rollout_plan')
E = [e for e in json.load(open(f'{OUT}/launch.json')) if e.get('evaluation_id')]
TERM = ('completed', 'failed', 'cancelled', 'errored', 'error')
def get(p, q=None):
    for a in range(8):
        try: return c.get(p, q)
        except Exception: time.sleep(2 + a)
def runs_of(e):
    out = []
    for s in get(f"api/evaluations/{e['evaluation_id']}/rollouts", {}) or []:
        for r in get(f"api/evaluations/{e['evaluation_id']}/tasks/{s['local_task_id']}/rollouts", {}) or []:
            d = get(f"api/rollouts/{r['id']}") or {}; d = d.get('rollout', d)
            out.append({k: d.get(k) for k in ('id', 'evaluation_status', 'turn_count', 'task_version_number', 'passed', 'is_errored', 'extracted_score', 'total_cost', 'stop_reason')})
    return out
last = None
while True:
    st = [((get(f"api/evaluations/{e['evaluation_id']}") or {}).get('status') or 'poll-error') for e in E]
    cnt = dict(collections.Counter(st))
    if cnt != last: print(time.strftime('%H:%M'), cnt, flush=True); last = cnt
    if all(s in TERM for s in st): break
    time.sleep(600)
res = [{**e, 'status': s, 'rollouts': runs_of(e)} for e, s in zip(E, st)]
json.dump(res, open(f'{OUT}/launch_results.json', 'w'), indent=1)
for x in res:
    rs = x['rollouts']; g = [r for r in rs if not r['is_errored'] and r['extracted_score'] is not None]
    print(f"{x['codename']:9} {x['task'][:45]:45} {x['status']:9} runs {len(rs)} graded {len(g)} errored {sum(bool(r['is_errored']) for r in rs)} cost ${sum(r['total_cost'] or 0 for r in rs):.2f}", flush=True)
print('ALL DONE', flush=True)
