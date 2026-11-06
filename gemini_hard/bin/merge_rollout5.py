# Finished Gemini 4 Argon runs from the 5-6 Nov rollout (rollout_plan/results.json) as run records, by task, into
# rollout_plan/argon_runs.json. select5.py, common.py, check_consistency.py and fetch_turns5.py add them to each task's 5 Nov runs.
import json, os, csv
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
PLAN = {r['task_id']: r for r in csv.DictReader(open(f'{OUT}/runs.csv'))}
RES = json.load(open(f'{OUT}/results.json'))
DONE = ('completed', 'failed', 'errored', 'cancelled', 'error')
out = {}
for e, v in RES.items():
    for x in v['runs']:
        if x['evaluation_status'] not in DONE: continue
        tid = v['task_id']; ver = PLAN[tid]['version']
        out.setdefault(tid, []).append({'id': x['id'], 'model': 'umbra', 'passed': x['passed'], 'is_errored': x['is_errored'] or x['evaluation_status'] != 'completed', 'extracted_score': x['extracted_score'],
                                        'task_version_number': int(ver) if ver else x.get('task_version_number'), 'turn_count': x['turn_count'], 'evaluation_id': e})
json.dump(out, open(f'{OUT}/argon_runs.json', 'w'), indent=1)
print(len(out), 'tasks,', sum(map(len, out.values())), 'finished Argon runs')
