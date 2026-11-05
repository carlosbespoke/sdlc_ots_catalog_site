# Runs of the original tasks behind catalog tasks that have no runs of their own.
# Many ProgramBench tasks in alpharecon-programbench-upgrade are copies of a same-name task in programbench-repo-upgrade-ots;
# their runs live on the original, at any version. Read-only: one GET per original, all versions, into origins/<catalog task id>.json.
import sys, os, re, json, time, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
ORIGIN_BATCHES = ('programbench-repo-upgrade-ots', 'alpharecon-programbench-upgrade')
norm = lambda n: re.sub(r'[^a-z0-9]', '', re.sub(r'\.[0-9a-f]{7}$', '', n.lower()))
T = json.load(open(f'{P}/rfc/tasks.json')); idx = collections.defaultdict(list)
for t in T: idx[norm(t['name'])].append(t)
U = json.load(open(f'{H}/universe.json'))['tasks']
need = [t for t in U if t['catalog'] in ('ProgramBench', 'Migration') and not t.get('evidence')]
c = client.Client(); os.makedirs(f'{H}/origins', exist_ok=True)
KEEP = ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')
def get(path):
    for a in range(6):
        try: return c.get(path)
        except Exception: time.sleep(2 * (a + 1))
def pull(t):
    out = f'{H}/origins/{t["id"]}.json'
    if os.path.exists(out): return 'cached'
    sib = [s for s in idx[norm(t['name'])] if s['id'] != t['id'] and s['batch_name'] in ORIGIN_BATCHES]
    origins = []
    for s in sib:
        d = get(f'api/tasks/{s["id"]}/rollouts')
        if d is None: return 'fail'
        origins.append({'id': s['id'], 'name': s['name'], 'batch': s['batch_name'],
                        'rollouts': [{k: x.get(k) for k in KEEP} for x in d.get('rollouts') or []]})
    json.dump({'id': t['id'], 'name': t['name'], 'origins': origins}, open(out, 'w'))
    return 'ok' if any(o['rollouts'] for o in origins) else 'no runs' if origins else 'no origin'
with cf.ThreadPoolExecutor(8) as ex: print(len(need), collections.Counter(ex.map(pull, need)))
