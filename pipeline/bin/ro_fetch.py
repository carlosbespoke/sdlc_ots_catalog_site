# Per-task groupedStats (pinned to each task's current version) for all ready-for-client tasks.
import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
c = client.Client(); B = sys.argv[1]
tasks = json.load(open(f'{B}/rfc/tasks.json'))
def one(t):
    out = f"{B}/ro/{t['id']}.json"
    if os.path.exists(out): return
    for a in range(5):
        try:
            d = c.task_rollouts(t['id'], t.get('current_version'))
            rs = d.get('rollouts') or []
            json.dump({'id': t['id'], 'name': t['name'], 'version': t.get('current_version'), 'grouped': d.get('groupedStats') or [],
                       'n_rollouts': len(rs), 'rollouts': [{k: r.get(k) for k in ('model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')} for r in rs]},
                      open(out, 'w')); return
        except Exception as e:
            time.sleep(3 * (a + 1))
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(one, tasks))
print(len(os.listdir(f'{B}/ro')), 'of', len(tasks))
