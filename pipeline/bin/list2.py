import sys, os, json, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
c = client.Client(); base = sys.argv[1]
def one(line):
    name, tid, _ = line.split('\t')
    out = os.path.join(base, 'tasks', name); os.makedirs(out, exist_ok=True)
    try:
        j = c.get(f'api/tasks/{tid}/files', {'recursive': 'true'})
        files = [f['path'] for f in (j if isinstance(j, list) else j.get('files', [])) if f.get('type') != 'directory']
    except Exception as e: files = []
    json.dump(files, open(f'{out}/files.json', 'w')); return name, len(files)
lines = [l for l in open(sys.argv[2]).read().splitlines() if l.strip()]
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one, lines): 
        if r[1] == 0: print('NOFILES', r[0])
