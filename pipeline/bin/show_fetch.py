# Download the files that describe each shortlist task's environment (untrusted data; stored, never executed).
import sys, os, json, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
from openpyxl import load_workbook
c = client.Client(); B = sys.argv[1]
wb = load_workbook('/Users/carlos/code/sdlc_final_samples/task_taxonomies_final.xlsx'); t = wb['Taxonomies']; H = [x.value for x in t[2]]
names = {t.cell(r, H.index('Task') + 1).value for r in range(3, t.max_row + 1)}
tasks = [x for x in json.load(open(f'{B}/rfc/tasks.json')) if x['name'] in names]
KEEP = lambda p: (os.path.basename(p) in ('instruction.md', 'task.toml', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml', 'solve.sh', 'test.sh', 'entrypoint.sh', 'setup.sh', 'README.md')
                  or p.startswith('tests/') and p.endswith(('.py', '.sh', '.toml', '.json', '.yaml', '.yml'))) and p.count('/') <= 3
def txt(tid, path):
    p = {'path': path}; spec.validate('GET', f"api/tasks/{tid}/files/content", p)
    r = c._raw._make_request('GET', f"api/tasks/{tid}/files/content", params=p).text
    try:
        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
    except Exception: pass
    return r
def one(x):
    d = f"{B}/show/{x['name']}"
    if os.path.exists(f'{d}/_files.json'): return
    os.makedirs(d, exist_ok=True)
    for a in range(5):
        try:
            j = c.get(f"api/tasks/{x['id']}/files", {'recursive': 'true'})
            files = [f['path'] for f in (j if isinstance(j, list) else j.get('files', [])) if f.get('type') != 'directory']; break
        except Exception: time.sleep(3 * (a + 1))
    else: return
    for f in files:
        if KEEP(f):
            try: s = txt(x['id'], f)
            except Exception: continue
            out = os.path.join(d, f.replace('/', '__'))
            open(out, 'w').write(s[:60000])
    json.dump({'id': x['id'], 'name': x['name'], 'batch': x['batch_name'], 'files': files}, open(f'{d}/_files.json', 'w'))
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(one, tasks))
print(len(tasks), sum(os.path.exists(f"{B}/show/{x['name']}/_files.json") for x in tasks))
