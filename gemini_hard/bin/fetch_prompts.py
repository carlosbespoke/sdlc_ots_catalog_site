# Download instruction.md for each sample that has no local copy (untrusted data: stored, never executed).
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
c = client.Client()
for t in json.load(open(f'{H}/universe.json'))['tasks']:
    if not t.get('sample') or os.path.exists(f"{P}/show/{t['name']}/instruction.md") or os.path.exists(f"{H}/show/{t['name']}/instruction.md"): continue
    p = {'path': 'instruction.md'}; spec.validate('GET', f"api/tasks/{t['id']}/files/content", p)
    for a in range(5):
        try:
            r = c._raw._make_request('GET', f"api/tasks/{t['id']}/files/content", params=p).text; break
        except Exception: time.sleep(3 * (a + 1))
    try:
        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
    except Exception: pass
    os.makedirs(f"{H}/show/{t['name']}", exist_ok=True); open(f"{H}/show/{t['name']}/instruction.md", 'w').write(r)
    print(t['name'], len(r))
