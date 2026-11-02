# For Green tasks whose sheet link names a Horizon id we never fetched: pull metadata, rollouts at the sheet's selected version, and one turn sample.
import sys, os, json, re, random
B = sys.argv[1]; os.environ['B'] = B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from cat_common import load_rows
from _horizon_lib import client
c = client.Client()
have = {r['id'] for r in load_rows()}
F = json.load(open(f'{B}/fullcat/full.json'))
for o in F:
    if not o['status'].startswith('Green'): continue
    i = re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}', o['url']).group(0)
    if i in have: continue
    t = c.get(f'api/tasks/{i}'); t = t.get('task', t)
    v = int(o['ver'] or t.get('current_version'))
    d = c.task_rollouts(i, v); rs = d.get('rollouts') or []
    json.dump({'id': i, 'name': o['name'], 'version': v, 'grouped': d.get('groupedStats') or [], 'n_rollouts': len(rs),
               'rollouts': [{k: r.get(k) for k in ('model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')} for r in rs]},
              open(f'{B}/ro/{i}.json', 'w'))
    ok = [x for x in rs if not x.get('is_errored')]
    runs = []
    if ok:
        pick = random.Random(i).choice(sorted(ok, key=lambda x: x['id'])); x = c.get(f"api/rollouts/{pick['id']}")
        runs = [{'id': pick['id'], 'model': pick.get('model'), 'turn_count': x.get('turn_count'), 'max_turns': x.get('max_turns'), 'is_errored': False, 'passed': pick.get('passed')}]
    json.dump({'id': i, 'batch': t.get('batch_name'), 'runs': runs, 'source': 'api-sheet-id'}, open(f'{B}/turns_s/{i}.json', 'w'))
    print(o['name'], i, 'status', t.get('status'), 'cur', t.get('current_version'), 'sheet v', v, 'batch', t.get('batch_name'), 'rollouts', len(rs), 'turns', [r['turn_count'] for r in runs])
