# Turn count of every completed Gemini run on the selected tasks (turns/), reusing the catalog pipeline's cached counts.
import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
MM = json.load(open(f'{P}/ro_models.json')); GEM = {k for k, v in MM.items() if 'gemini' in v and v != 'google/gemini-3.7-flash'}
c = client.Client(); os.makedirs(f'{H}/turns', exist_ok=True)
cache = {}  # no reuse: every turn count is fetched fresh for this snapshot
for d in ():
    for f in os.listdir(f'{P}/{d}') if os.path.isdir(f'{P}/{d}') else []:
        if f.startswith('_'): continue
        for q in json.load(open(f'{P}/{d}/{f}')).get('runs', []):
            if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
U = [t for t in json.load(open(f'{H}/universe.json'))['tasks'] if t.get('tier')]
runs = {t['id']: [q for q in json.load(open(f"{H}/ro3/{t['id']}.json"))['rollouts'] if q['model'] in GEM and not q.get('is_errored')] for t in U}
need = [q['id'] for v in runs.values() for q in v if q['id'] not in cache]
def get(i):
    for a in range(25):  # this endpoint returns intermittent 404s
        try: return i, c.get(f'api/rollouts/{i}')
        except Exception: time.sleep(1 + a % 4)
    return i, None
with cf.ThreadPoolExecutor(6) as ex: got = dict(ex.map(get, need))
miss = 0
for tid, v in runs.items():
    out = []
    for q in v:
        x = cache.get(q['id']) or got.get(q['id']) or {}
        if not isinstance(x.get('turn_count'), (int, float)): miss += 1; continue
        out.append({'id': q['id'], 'model': q['model'], 'turn_count': x['turn_count'], 'max_turns': x.get('max_turns'), 'passed': q.get('passed')})
    json.dump({'id': tid, 'runs': out}, open(f'{H}/turns/{tid}.json', 'w'))
print('tasks', len(U), 'gemini runs', sum(map(len, runs.values())), 'fetched', len(need), 'without turn count', miss)
