# Main run: submit every row of rollout_plan/runs.csv with its own settings. Runs per task spread each group's runs_to_launch
# (summary.json) evenly over its tasks, minus graded pilot runs already on that task. A task whose active version no longer
# matches the plan version is skipped. Appends to rollout_plan/launch.json. --dry prints without submitting.
import csv, json, os, sys, datetime
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from horizon import HorizonClient
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
DRY = '--dry' in sys.argv
R = list(csv.DictReader(open(f'{OUT}/runs.csv'))); S = json.load(open(f'{OUT}/summary.json'))
PILOT_GRADED = {('9b114dca-e1c7-4f2d-b4f3-9e77b4ee2969', 'umbra'): 1, ('4ebfe45f-42ba-4277-b053-47c9dfca7eb5', 'kittiwake'): 1,
                ('4b5ae5a6-e206-4fa0-9299-ab4e94f3fd93', 'steppe'): 1}
plan = []
for g in S['groups']:
    rs = [r for r in R if r['catalog'] == g['catalog'] and r['model'] == g['model']]
    base, extra = divmod(g['runs_to_launch'], len(rs))
    for i, r in enumerate(rs): plan.append((r, base + (i < extra) - PILOT_GRADED.get((r['task_id'], r['codename']), 0)))
h = HorizonClient(); c = client.Client()
log_p = f'{OUT}/launch.json'; log = json.load(open(log_p)) if os.path.exists(log_p) else []
done = {(x['task_id'], x['codename']) for x in log if x.get('evaluation_id')}
for r, n in plan:
    key = (r['task_id'], r['codename'])
    if key in done or n <= 0: continue
    act = c.get(f"api/tasks/{r['task_id']}").get('current_version')
    rec = {'catalog': r['catalog'], 'model': r['model'], 'codename': r['codename'], 'task': r['task'], 'task_id': r['task_id'],
           'version': int(r['version']), 'active_version': act, 'runs': n, 'machine_type': r['machine_type'], 'effort_tier': 3}
    if str(act) != r['version']: rec['skipped'] = 'active version changed'; print('SKIP', rec); log.append(rec); continue
    if DRY: print('DRY', r['codename'], r['task'], n, r['machine_type']); continue
    try:
        ev = h.evaluations.trigger(task_id=r['task_id'], model=r['codename'], runs=n, max_turns=int(r['max_turns']), max_tokens=int(r['max_tokens']),
                                   agent_type=r['agent_type'], effort_tier=3, machine_type=r['machine_type'], sandbox_backend=r['sandbox_backend'])
        rec['evaluation_id'] = getattr(ev, 'evaluation_id', None) or getattr(ev, 'id', None)
    except Exception as e: rec['error'] = str(e)[:400]
    rec['submitted'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'); log.append(rec)
    json.dump(log, open(log_p, 'w'), indent=1); print(rec.get('evaluation_id') or rec.get('error'), r['codename'], r['task'], n)
print('total runs', sum(n for _, n in plan))
