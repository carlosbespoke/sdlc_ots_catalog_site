import sys, os, json, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
c = client.Client()
base = sys.argv[1]
KEEP = ('instruction.md','task.toml','task.yaml','Dockerfile','docker-compose.yaml','docker-compose.yml')
def one(line):
    name, tid, _ = line.split('\t')
    out = os.path.join(base, 'tasks', name)
    files = json.load(open(f'{out}/files.json'))
    want = [f for f in files if os.path.basename(f) in KEEP and f.count('/') <= 2][:6]
    n = 0
    for f in want:
        p = {'path': f}
        spec.validate('GET', f'api/tasks/{tid}/files/content', p)
        try:
            t = c._raw._make_request('GET', f'api/tasks/{tid}/files/content', params=p).text
        except Exception:
            continue
        try:
            j = json.loads(t)
            if isinstance(j, dict) and 'content' in j: t = j['content']
        except Exception: pass
        open(os.path.join(out, f.replace('/', '__')), 'w').write(t[:6000]); n += 1
    return name, len(files), n
lines = [l for l in open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, 'tasks.tsv')).read().splitlines() if l.strip()]
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one, lines): print(*r)
