import sys, os, json, re, time, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
c = client.Client(); B = sys.argv[1]; d = f'{B}/rfc/t'
R = [json.load(open(f'{d}/{f}')) for f in os.listdir(d)]
X = [r for r in R if r['name'].startswith('pdk-drift-repository')]
def txt(tid, path):
    p = {'path': path}; spec.validate('GET', f'api/tasks/{tid}/files/content', p)
    for a in range(3):
        try:
            t = c._raw._make_request('GET', f'api/tasks/{tid}/files/content', params=p).text
            try:
                j = json.loads(t); t = j.get('content', t) if isinstance(j, dict) else t
            except Exception: pass
            return t
        except Exception: time.sleep(2)
    return ''
def one(r):
    j = []
    for a in range(5):
        try: j = c.get(f"api/tasks/{r['id']}/files", {'recursive': 'true'}); break
        except Exception: time.sleep(3 * (a + 1))
    files = [f['path'] for f in (j if isinstance(j, list) else j.get('files', [])) if f.get('type') != 'directory']
    pick = sorted([f for f in files if os.path.basename(f) in ('pyproject.toml','package.json','Cargo.toml','setup.cfg','setup.py','go.mod','README.md','README.rst')], key=lambda f: (f.count('/'), f))[:3]
    info = []
    for f in pick:
        t = txt(r['id'], f)
        m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)', t, re.M) or re.search(r'"name"\s*:\s*"([^"]+)"', t) or re.search(r'^module\s+(\S+)', t, re.M)
        desc = re.search(r'^\s*description\s*=\s*["\']([^"\']+)', t, re.M) or re.search(r'"description"\s*:\s*"([^"]+)"', t)
        if m: info.append(f"{os.path.basename(f)} name={m.group(1)}" + (f" desc={desc.group(1)[:120]}" if desc else ''))
        elif f.lower().startswith('readme') or 'README' in f: info.append('README: ' + re.sub(r'\s+', ' ', t[:200]))
    top = sorted({f.split('/')[2] for f in files if f.count('/') >= 3 and f.startswith('environment/')})[:8]
    return {'id': r['id'], 'name': r['name'], 'ext': r['ext'], 'manifest': info, 'top_dirs': top}
with cf.ThreadPoolExecutor(4) as ex: out = list(ex.map(one, X))
json.dump(out, open(f'{B}/rfc/drift_ids.json', 'w'), indent=1)
for o in out: print(o['name'][-12:], '|', '; '.join(o['manifest'])[:230], '|', o['top_dirs'][:5])
