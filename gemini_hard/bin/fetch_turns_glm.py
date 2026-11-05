# Turn count of every GLM-5.3 Flash run shown for the selected tasks (its own runs, or the borrowed ones recorded in universe.json), into turns_glm/.
# Counts already in the catalog pipeline's cache (pipeline/turns_all) are reused by run id; the rest are fetched read-only.
import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
os.makedirs(f'{H}/turns_glm', exist_ok=True)
U = [t for t in json.load(open(f'{H}/universe.json'))['tasks'] if t.get('tier') and t.get('glm') and not os.path.exists(f"{H}/turns_glm/{t['id']}.json")]
cache = {}
for f in os.listdir(f'{P}/turns_all'):
    if f.endswith('.json'):
        for q in json.load(open(f'{P}/turns_all/{f}')).get('runs', []):
            if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
need = [q['id'] for t in U for q in t['glm']['runs'] if q['id'] not in cache]
got = {}
if need:
    from _horizon_lib import client
    c = client.Client()
    def get(i):
        for a in range(25):  # this endpoint returns intermittent 404s
            try: return i, c.get(f'api/rollouts/{i}')
            except Exception: time.sleep(1 + a % 4)
        return i, None
    with cf.ThreadPoolExecutor(6) as ex: got = dict(ex.map(get, need))
miss = 0
for t in U:
    out = []
    for q in t['glm']['runs']:
        x = cache.get(q['id']) or got.get(q['id']) or {}
        if not isinstance(x.get('turn_count'), (int, float)): miss += 1; continue
        out.append({'id': q['id'], 'model': 'z-ai/glm-5.3-flash', 'turn_count': x['turn_count'], 'max_turns': x.get('max_turns'), 'passed': q['passed']})
    json.dump({'id': t['id'], 'source': t['glm']['source'], 'runs': out}, open(f'{H}/turns_glm/{t["id"]}.json', 'w'))
print('tasks', len(U), 'GLM runs', sum(len(t['glm']['runs']) for t in U), 'from cache', sum(len(t['glm']['runs']) for t in U) - len(need), 'fetched', len(need), 'without turn count', miss)
