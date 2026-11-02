import subprocess, json, sys, os, collections, concurrent.futures as cf
P=os.path.expanduser('~/code/horizon_env/bin/python3'); S=os.path.expanduser('~/.claude/skills/horizon-api/scripts/api.py')
base=sys.argv[1]
def get(*a):
    r=subprocess.run([P,S,'--get',*a],capture_output=True,text=True)
    return r.stdout if r.returncode==0 else None
def one(line):
    name,tid,_=line.split('\t')
    out=os.path.join(base,'tasks',name); os.makedirs(out,exist_ok=True)
    lst=get(f'api/tasks/{tid}/files','recursive=true')
    files=[]
    try:
        j=json.loads(lst); files=[f['path'] for f in (j if isinstance(j,list) else j.get('files',[])) if f.get('type')!='directory']
    except Exception: pass
    json.dump(files,open(f'{out}/files.json','w'))
    want=[f for f in files if os.path.basename(f) in ('instruction.md','task.toml','task.yaml','Dockerfile','docker-compose.yaml','docker-compose.yml','prompt.md')][:8]
    for f in want:
        c=get(f'api/tasks/{tid}/files/content',f'path={f}')
        if c:
            try:
                j=json.loads(c); c=j.get('content',c) if isinstance(j,dict) else c
            except Exception: pass
            open(os.path.join(out,f.replace('/','__')),'w').write(c if isinstance(c,str) else json.dumps(c))
    return name,len(files),len(want)
lines=[l for l in open(os.path.join(base,'tasks.tsv')).read().splitlines() if l.strip()]
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one,lines): print(*r)
