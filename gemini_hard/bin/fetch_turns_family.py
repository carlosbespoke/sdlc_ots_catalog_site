# Turn counts of the Gemini 3.8 Flash runs borrowed from each family candidate's original task (cat/family_candidates.json, top N),
# into turns5/<task id>.json (model google/gemini-3.8-flash). Cached counts are reused by run id; the rest are fetched read-only.
import sys, os, json, time, glob, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 160
C = [t for t in json.load(open(f'{H}/cat/family_candidates.json'))[:N] if not os.path.exists(f"{H}/turns5/{t['id']}.json")]
cache = {}
for f in glob.glob(f'{P}/turns_*/*.json') + glob.glob(f'{P}/turns/*.json'):
    try:
        for q in json.load(open(f)).get('runs', []):
            if q.get('id') and isinstance(q.get('turn_count'), (int, float)): cache[q['id']] = q
    except Exception: pass
need = [r['id'] for t in C for r in t['flash_runs'] if r['id'] not in cache]
got = {}
if need:
    from _horizon_lib import client
    c = client.Client()
    def get(i):
        for a in range(25):
            try: d = c.get(f'api/rollouts/{i}'); return i, d.get('rollout', d)
            except Exception: time.sleep(1 + a % 4)
        return i, None
    with cf.ThreadPoolExecutor(8) as ex: got = dict(ex.map(get, need))
miss = 0
for t in C:
    out = []
    for r in t['flash_runs']:
        x = cache.get(r['id']) or got.get(r['id']) or {}
        if not isinstance(x.get('turn_count'), (int, float)): miss += 1; continue
        out.append({'id': r['id'], 'model': 'google/gemini-3.8-flash', 'turn_count': x['turn_count'], 'max_turns': x.get('max_turns'), 'passed': r['passed'], 'borrowed_from': r['from']})
    json.dump({'id': t['id'], 'runs': out}, open(f"{H}/turns5/{t['id']}.json", 'w'))
print('tasks', len(C), 'runs', sum(len(t['flash_runs']) for t in C), 'fetched', len(need), 'without turn count', miss)
