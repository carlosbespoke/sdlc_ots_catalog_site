# Add the rollout campaign's runs (rollout_plan/: pilot, retries and main run) to the snapshot in ro/, at each task's report
# version. Only the campaign's own rollouts are added; every other run on these tasks stays as of SNAPSHOT. Errored and
# ungraded runs are added too and left out by the usual rules. Run bin/fetch.py afterwards to fill their turn counts.
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
c = client.Client()
def get(path, params=None, tries=10):
    for a in range(tries):
        try: return c.get(path, params)
        except Exception: time.sleep(1 + a % 4)
    raise SystemExit(f'failed: {path}')
def evals(o):  # every {evaluation_id, task_id} in pilot.json, at any depth
    if isinstance(o, dict):
        if 'evaluation_id' in o: yield o
        for v in o.values(): yield from evals(v)
    elif isinstance(o, list):
        for v in o: yield from evals(v)
E = list(evals(json.load(open(f'{OUT}/pilot.json')))) + json.load(open(f'{OUT}/launch.json'))
ids = {}  # task id -> campaign rollout ids
for e in E:
    for s in get(f"api/evaluations/{e['evaluation_id']}/rollouts", {}) or []:  # one entry per task in the evaluation
        rs = get(f"api/evaluations/{e['evaluation_id']}/tasks/{s['local_task_id']}/rollouts", {}) or []
        ids.setdefault(e['task_id'], set()).update(r['id'] for r in rs)
added = 0
for tid, want in ids.items():
    f = f'{H}/ro/{tid}.json'; r = json.load(open(f)); have = {q['id'] for q in r['rollouts']}
    d = get(f"api/tasks/{tid}/rollouts", {'task_version': str(r['version'])}) or {}
    new = [{k: x.get(k) for k in KEEP} for x in d.get('rollouts') or [] if x['id'] in want and x['id'] not in have]
    missing = want - have - {q['id'] for q in new}
    if missing: print(r['name'], len(missing), 'campaign runs not at version', r['version'], '(left out)')
    r['rollouts'] += new; r['n_rollouts'] = len(r['rollouts']); r.setdefault('campaign_rollouts', []); r['campaign_rollouts'] += [q['id'] for q in new]
    json.dump(r, open(f, 'w')); added += len(new)
    print(f"{r['name'][:45]:45} v{r['version']} +{len(new)}")
print('tasks', len(ids), 'runs added', added)
