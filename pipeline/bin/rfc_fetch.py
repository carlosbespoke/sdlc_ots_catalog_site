import sys, os, json, re, time, collections, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
c = client.Client(); B = sys.argv[1]
tasks = json.load(open(f'{B}/rfc/tasks.json'))
EXT = {'.py':'Python','.go':'Go','.rs':'Rust','.java':'Java','.kt':'Kotlin','.ts':'TypeScript','.tsx':'TypeScript','.js':'JavaScript','.c':'C','.h':'C','.cc':'C++','.cpp':'C++','.hpp':'C++','.tf':'HCL (Terraform)','.rb':'Ruby','.cs':'C#','.php':'PHP','.scala':'Scala','.swift':'Swift','.ex':'Elixir','.hs':'Haskell','.lua':'Lua','.zig':'Zig','.sql':'SQL','.v':'Verilog','.sv':'Verilog','.lean':'Lean','.ml':'OCaml','.dart':'Dart'}
os.makedirs(f'{B}/rfc/t', exist_ok=True)
def one(t):
    out = f"{B}/rfc/t/{t['id']}.json"
    if os.path.exists(out) and json.load(open(out)).get('nfiles'): return
    rec = {'id': t['id'], 'name': t['name'], 'batch': t.get('batch_name'), 'recipe': t.get('recipe_name'), 'spec': t.get('spec_name')}
    files, err = [], ''
    for a in range(5):
        try:
            j = c.get(f"api/tasks/{t['id']}/files", {'recursive': 'true'})
            files = [f['path'] for f in (j if isinstance(j, list) else j.get('files', [])) if f.get('type') != 'directory']; err = ''; break
        except Exception as e:
            err = str(e)[:200]; time.sleep(2 * (a + 1))
    rec['err'] = err
    rec['ext'] = dict(collections.Counter(EXT[os.path.splitext(f)[1]] for f in files if os.path.splitext(f)[1] in EXT).most_common(5))
    rec['nfiles'] = len(files)
    def txt(path):
        try:
            p = {'path': path}; spec.validate('GET', f"api/tasks/{t['id']}/files/content", p)
            r = c._raw._make_request('GET', f"api/tasks/{t['id']}/files/content", params=p).text
            try:
                jj = json.loads(r); r = jj.get('content', r) if isinstance(jj, dict) else r
            except Exception: pass
            return r
        except Exception: return ''
    ins = next((f for f in files if os.path.basename(f) in ('instruction.md', 'prompt.md') and f.count('/') == 0), None) or next((f for f in files if os.path.basename(f) == 'instruction.md'), None)
    rec['instr'] = txt(ins)[:1500] if ins else ''
    tm = next((f for f in files if f == 'task.toml'), None)
    rec['toml'] = ' '.join(re.findall(r'^(?:category|tags)\s*=.*', txt(tm), re.M)) if tm else ''
    df = next((f for f in files if os.path.basename(f) == 'Dockerfile'), None)
    rec['from'] = ','.join(re.findall(r'^FROM\s+(\S+)', txt(df), re.M))[:200] if df else ''
    json.dump(rec, open(out, 'w'))
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(one, tasks))
print(len(os.listdir(f'{B}/rfc/t')))
