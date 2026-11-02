import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
c = client.Client(); B = sys.argv[1]
d = json.load(open(f'{B}/rfc/explorer.json')); K = d['keys']; D = d['dicts']; I = {k: i for i, k in enumerate(K)}
g = lambda r, k: D[k][r[I[k]]]
T = {json.load(open(f'{B}/rfc/t/{f}'))['name'] + '|' + json.load(open(f'{B}/rfc/t/{f}'))['batch']: json.load(open(f'{B}/rfc/t/{f}')) for f in os.listdir(f'{B}/rfc/t')}
sel = []
for r in d['rows']:
    b, fam, sc = g(r, 'batch'), g(r, 'fam'), g(r, 'shapec')
    if b == 'system-design-harsh-xai' or b == 'featureimplementation-deepswe-cohere' or (fam in ('Cohere (all batches)', 'Feature implementation / DeepSWE (all batches)') and sc.startswith('Fault')):
        t = T[r[-1] + '|' + b]; sel.append({'id': t['id'], 'name': t['name'], 'batch': b, 'ref': b == 'system-design-harsh-xai'})
def one(s):
    out = f"{B}/ft/{s['id']}.json"
    if os.path.exists(out): return
    p = {'path': 'instruction.md'}
    for a in range(5):
        try:
            spec.validate('GET', f"api/tasks/{s['id']}/files/content", p)
            r = c._raw._make_request('GET', f"api/tasks/{s['id']}/files/content", params=p).text
            try:
                jj = json.loads(r); r = jj.get('content', r) if isinstance(jj, dict) else r
            except Exception: pass
            s['instr'] = r; json.dump(s, open(out, 'w')); return
        except Exception as e: time.sleep(2 * (a + 1))
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(one, sel))
print(len(sel), len(os.listdir(f'{B}/ft')))
