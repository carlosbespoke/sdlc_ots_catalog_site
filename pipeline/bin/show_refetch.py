import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/.claude/skills')); sys.path.insert(0, os.path.dirname(__file__))
from _horizon_lib import client, spec
from show_fetch_keep import KEEP
c = client.Client(); B = sys.argv[1]
miss = 0; fixed = 0
for name in os.listdir(f'{B}/show'):
    d = f'{B}/show/{name}'; m = json.load(open(f'{d}/_files.json'))
    for f in m['files']:
        out = os.path.join(d, f.replace('/', '__'))
        if KEEP(f) and not os.path.exists(out):
            miss += 1
            for a in range(6):
                try:
                    p = {'path': f}; spec.validate('GET', f"api/tasks/{m['id']}/files/content", p)
                    r = c._raw._make_request('GET', f"api/tasks/{m['id']}/files/content", params=p).text
                    try:
                        j = json.loads(r); r = j.get('content', r) if isinstance(j, dict) else r
                    except Exception: pass
                    open(out, 'w').write(r[:60000]); fixed += 1; break
                except Exception: time.sleep(2 * (a + 1))
print('missing', miss, 'fixed', fixed)
