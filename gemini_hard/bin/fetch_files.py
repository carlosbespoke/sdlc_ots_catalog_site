# Download the files that describe each new sample's environment (untrusted data: stored, never executed). Same file filter as the catalog pipeline.
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
c = client.Client()
KEEP = lambda p: (os.path.basename(p) in ('instruction.md', 'task.toml', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml', 'solve.sh', 'test.sh', 'entrypoint.sh', 'setup.sh', 'README.md')
                  or p.startswith('tests/') and p.endswith(('.py', '.sh', '.toml', '.json', '.yaml', '.yml'))) and p.count('/') <= 3
def txt(tid, path):
    p = {'path': path}; spec.validate('GET', f"api/tasks/{tid}/files/content", p)
    r = c._raw._make_request('GET', f"api/tasks/{tid}/files/content", params=p).text
    try:
        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
    except Exception: pass
    return r
for t in json.load(open(f'{H}/universe.json'))['tasks']:
    if not t.get('sample') or os.path.exists(f"{P}/show/{t['name']}/_files.json"): continue
    if os.path.exists(f"{H}/show/{t['name']}/_files.json") and all(os.path.exists(f"{H}/show/{t['name']}/{f.replace('/', '__')}") for f in json.load(open(f"{H}/show/{t['name']}/_files.json")) if KEEP(f)): continue
    d = f"{H}/show/{t['name']}"; os.makedirs(d, exist_ok=True)
    for a in range(20):
        try:
            j = c.get(f"api/tasks/{t['id']}/files", {'recursive': 'true'})
            files = [f['path'] for f in (j if isinstance(j, list) else j.get('files', [])) if f.get('type') != 'directory']; break
        except Exception: time.sleep(3 * (a + 1))
    else: print('fail', t['name']); continue
    json.dump(files, open(f'{d}/_files.json', 'w'))
    for f in files:
        out = f"{d}/{f.replace('/', '__')}"
        if not KEEP(f) or os.path.exists(out): continue
        for a in range(20):  # the content endpoint returns intermittent 404s; write only a successful download
            try: body = txt(t['id'], f); break
            except Exception: time.sleep(1 + a % 4)
        else: print('skip', f); continue
        open(out, 'w').write(body[:200000])
    print(t['name'], len(files), 'files')
