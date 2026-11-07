# Add two kinds of runs to the snapshot in ro/, both up to the time in LATE_CUTOFF (decided 7 Nov):
#   1. runs at the task's report version made after SNAPSHOT (until then only our own campaigns' runs were added);
#   2. runs at any newer version of the task, whenever they were made. Both versions of the task then count.
# Only models the report knows (in MM, not in DROPPED) are added; runs of other models are counted and left out.
# Added ids go in 'late_rollouts', the newer versions in 'extra_versions'. Safe to rerun. Run bin/fetch.py afterwards for turn counts.
import sys, os, json, time, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f'{H}/bin')
from common import TASKS, MM, DROPPED
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
CUT = open(f'{H}/LATE_CUTOFF').read().strip()
c = client.Client()
def get(path, params=None, tries=12):
    for a in range(tries):
        try: return c.get(path, params)
        except Exception: time.sleep(1 + a % 4)
    raise SystemExit(f'failed: {path}')
skipped = collections.Counter(); added = collections.Counter()
def one(t):
    f = f"{H}/ro/{t['id']}.json"; r = json.load(open(f)); v = r['version']; have = {q['id'] for q in r['rollouts']}
    new = []
    for x in get(f"api/tasks/{t['id']}/rollouts", {}).get('rollouts') or []:  # every version
        if x['id'] in have or (x.get('created_at') or '')[:16] > CUT[:16]: continue
        if x.get('task_version_number') is None: skipped['no version'] += 1; continue
        if x['task_version_number'] < v: continue
        if x['model'] in DROPPED: continue
        if x['model'] not in MM: skipped[x['model']] += 1; continue
        new.append({k: x.get(k) for k in KEEP})
    if not new: return
    r['rollouts'] += new; r['n_rollouts'] = len(r['rollouts'])
    r['late_rollouts'] = r.get('late_rollouts', []) + [q['id'] for q in new]
    ev = sorted({q['task_version_number'] for q in r['rollouts']} - {v})
    if ev: r['extra_versions'] = ev
    json.dump(r, open(f, 'w'))
    for q in new: added[(MM[q['model']], 'same version' if q['task_version_number'] == v else 'newer version')] += 1
with cf.ThreadPoolExecutor(8) as ex: list(ex.map(one, TASKS))
for k, n in sorted(added.items()): print(f'{k[0]:32} {k[1]:14} {n}')
print('runs added', sum(added.values()), 'left out (model not in the report)', dict(skipped))
