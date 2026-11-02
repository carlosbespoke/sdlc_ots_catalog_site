import sys, os, json, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
c = client.Client(); B = sys.argv[1]
lines = [l.split('\t') for l in open(f'{B}/v2/tasks.tsv').read().splitlines() if l.strip()]
def one(x):
    name, tid = x[0], x[1]
    files = json.load(open(f'{B}/tasks/{name}/files.json'))
    path = 'instruction.md' if 'instruction.md' in files else next((f for f in files if f.endswith('instruction.md')), None)
    if not path: return name, None
    p = {'path': path}; spec.validate('GET', f'api/tasks/{tid}/files/content', p)
    for a in range(4):
        try:
            t = c._raw._make_request('GET', f'api/tasks/{tid}/files/content', params=p).text
            try:
                j = json.loads(t); t = j.get('content', t) if isinstance(j, dict) else t
            except Exception: pass
            return name, {'chars': len(t), 'words': len(t.split()), 'lines': t.count('\n') + 1}
        except Exception: pass
    return name, None
with cf.ThreadPoolExecutor(3) as ex: res = dict(ex.map(one, lines))
json.dump(res, open(f'{B}/v2/instr_len.json', 'w'))
print(sum(1 for v in res.values() if v), 'of', len(res), 'measured; missing:', [k for k, v in res.items() if not v])
