# Turn count of every completed Gemini 4 Argon, Gemini 3.8 Flash and GLM-5.3 Flash run at the selected version of each
# 5 Nov selected task (cat/sel5.json), into turns5/<task id>.json. Counts already cached anywhere locally are reused by run id.
import sys, os, json, time, glob, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
MM = json.load(open(f'{P}/ro_models.json')); SHOWN = {'google/gemini-4-argon', 'google/gemini-3.8-flash', 'z-ai/glm-5.3-flash'}
os.makedirs(f'{H}/turns5', exist_ok=True)
cache = {}
for f in glob.glob(f'{P}/turns_*/*.json') + glob.glob(f'{P}/turns/*.json') + glob.glob(f'{H}/turns/*.json') + glob.glob(f'{H}/turns_glm/*.json'):
    try: runs = json.load(open(f)).get('runs', [])
    except Exception: continue
    for q in runs:
        if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
S = [t for t in json.load(open(f'{H}/cat/sel5.json')) if not os.path.exists(f"{H}/turns5/{t['id']}.json")]
runs = {}
for t in S:
    rs = json.load(open(f"{H}/ro5/{t['id']}.json"))['rollouts']
    runs[t['id']] = [q for q in rs if MM.get(q['model']) in SHOWN and not q.get('is_errored') and (t['version'] is None or q.get('task_version_number') == t['version'])]
need = [q['id'] for v in runs.values() for q in v if q['id'] not in cache]
got = {}
if need:
    from _horizon_lib import client
    c = client.Client()
    def get(i):
        for a in range(25):  # this endpoint returns intermittent 404s
            try: return i, c.get(f'api/rollouts/{i}')
            except Exception: time.sleep(1 + a % 4)
        return i, None
    with cf.ThreadPoolExecutor(8) as ex: got = dict(ex.map(get, need))
miss = 0
for tid, v in runs.items():
    out = []
    for q in v:
        x = cache.get(q['id']) or got.get(q['id']) or {}
        if not isinstance(x.get('turn_count'), (int, float)): miss += 1; continue
        out.append({'id': q['id'], 'model': MM[q['model']], 'turn_count': x['turn_count'], 'max_turns': x.get('max_turns'), 'passed': q.get('passed')})
    json.dump({'id': tid, 'runs': out}, open(f'{H}/turns5/{tid}.json', 'w'))
print('tasks', len(S), 'runs', sum(map(len, runs.values())), 'cached', sum(map(len, runs.values())) - len(need), 'fetched', len(need), 'without turn count', miss)
