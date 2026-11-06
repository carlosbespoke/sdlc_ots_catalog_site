# instruction.md of the top family candidates (cat/family_candidates.json, hardest first), into prompts5/<task id>.md, for classifying.
# Untrusted data: stored and read, never executed. Read-only GETs at the sheet's selected version.
import sys, os, json, time, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); N = int(sys.argv[1]) if len(sys.argv) > 1 else 160
c = client.Client()
need = [t for t in json.load(open(f'{H}/cat/family_candidates.json'))[:N] if not os.path.exists(f"{H}/prompts5/{t['id']}.md")]
def pull(t):
    p = {'path': 'instruction.md'}
    if t['version']: p['version'] = str(t['version'])
    spec.validate('GET', f"api/tasks/{t['id']}/files/content", p)
    for a in range(5):
        try: r = c._raw._make_request('GET', f"api/tasks/{t['id']}/files/content", params=p).text; break
        except Exception: time.sleep(3 * (a + 1))
    else: return 'fail'
    try:
        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
    except Exception: pass
    open(f"{H}/prompts5/{t['id']}.md", 'w').write(r); return 'ok'
with cf.ThreadPoolExecutor(6) as ex: print(len(need), dict(collections.Counter(ex.map(pull, need))))
