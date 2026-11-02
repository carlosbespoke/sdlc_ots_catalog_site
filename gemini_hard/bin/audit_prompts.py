# instruction.md of every selected task at the version its runs are counted on; compare with the local copies the pages use, and look for shared prompts.
import sys, os, json, time, hashlib, collections, re, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from common import *
from _horizon_lib import client, spec
c = client.Client(); D = f'{H}/audit/instr'; os.makedirs(D, exist_ok=True)
U = [t for t in json.load(open(f'{H}/universe.json'))['tasks'] if t.get('tier')]
def fetch(t):
    out = f"{D}/{t['id']}.md"
    if os.path.exists(out) and os.path.getsize(out): return 'cached'
    p = {'path': 'instruction.md', 'version': str(RO[t['id']]['version'])}; spec.validate('GET', f"api/tasks/{t['id']}/files/content", p)
    for a in range(25):
        try:
            r = c._raw._make_request('GET', f"api/tasks/{t['id']}/files/content", params=p).text; break
        except Exception: time.sleep(1 + a % 4)
    else: return 'fail'
    try:
        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
    except Exception: pass
    if not r.strip(): return 'empty'
    open(out, 'w').write(r); return 'ok'
with cf.ThreadPoolExecutor(8) as ex: print(collections.Counter(ex.map(fetch, U)))
# metadata retry for tasks whose first pull came back empty
for t in U:
    a = json.load(open(f"{H}/audit/{t['id']}.json"))
    if a['meta'].get('current_version') is None:
        for k in range(25):
            try: m = c.get(f"api/tasks/{t['id']}"); break
            except Exception: time.sleep(1 + k % 4)
        print('meta retry', t['name'], m.get('current_version'), m.get('status'), m.get('archived'))
norm = lambda s: re.sub(r'\s+', ' ', s).strip()
H2 = collections.defaultdict(list)
for t in U:
    p = f"{D}/{t['id']}.md"
    if os.path.exists(p): H2[hashlib.md5(norm(open(p).read()).encode()).hexdigest()].append(t['name'])
print('identical prompts', [v for v in H2.values() if len(v) > 1])
# near-duplicates: shared opening (first 300 normalized chars)
O = collections.defaultdict(list)
for t in U:
    p = f"{D}/{t['id']}.md"
    if os.path.exists(p): O[norm(open(p).read())[:300]].append(t['name'])
print('same opening', [v for v in O.values() if len(v) > 1])
# local copies used on the pages vs the counted version
for t in U:
    if not t.get('sample'): continue
    loc = next((q for q in (f"{P}/show/{t['name']}/instruction.md", f"{H}/show/{t['name']}/instruction.md") if os.path.exists(q) and os.path.getsize(q)), None)
    cur = open(f"{D}/{t['id']}.md").read() if os.path.exists(f"{D}/{t['id']}.md") else None
    print(f"{t['name'][:50]:50} local {'match' if loc and cur and norm(open(loc).read()) == norm(cur) else 'DIFFERS' if loc else 'missing'}  ({loc and loc.split('/')[-3]})")
