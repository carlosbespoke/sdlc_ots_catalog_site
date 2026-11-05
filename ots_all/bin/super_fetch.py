# Super-samples: pull each pinned task from Horizon, rename it to its client-facing id, zip it, and fetch its runs and turn counts.
# Task files are untrusted data: stored and zipped, never run. Usage: super_fetch.py [--bump] (--bump moves each pin to the current version).
import sys, os, json, re, time, shutil, subprocess, zipfile, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); S = f'{H}/super'
CLI = os.path.expanduser('~/code/horizon_env/bin/horizon')
c = client.Client()
def get(path, params=None, tries=8):
    for a in range(tries):  # the API returns intermittent 404s
        try: return c.get(path, params)
        except Exception: time.sleep(1 + a % 4)
    raise SystemExit(f'failed: {path}')
cfg = json.load(open(f'{S}/super.json'))
for s in cfg['samples']:
    cur = get(f"api/tasks/{s['horizon_id']}")
    if '--bump' in sys.argv and cur['current_version'] != s['version']:
        print(f"{s['client_id']}: pin {s['version']} -> {cur['current_version']}"); s['version'] = cur['current_version']
    elif cur['current_version'] != s['version']:
        print(f"{s['client_id']}: pinned to v{s['version']}, the copy is now at v{cur['current_version']} ({cur['status']})")
    s['status'] = cur['status']
    # 1. task files at the pinned version, renamed to the client-facing id
    d = f"{S}/tasks/{s['client_id']}"; stamp = f'{d}/.horizon/pinned_version'
    if not (os.path.exists(stamp) and open(stamp).read().strip() == str(s['version'])):
        if os.path.isdir(d): shutil.rmtree(d)
        p = subprocess.run([CLI, 'tasks', 'pull', s['horizon_id'], '--version', str(s['version']), '--output-dir', d], capture_output=True, text=True, cwd=S)
        if p.returncode: raise SystemExit(p.stderr[-500:])
        os.makedirs(f'{d}/.horizon', exist_ok=True); open(stamp, 'w').write(str(s['version']))
    t = f'{d}/task.toml'; txt = open(t).read()
    txt = re.sub(r'(?m)^name = ".*"$', f'name = "{s["client_id"]}"', txt, count=1)
    txt = re.sub(r'(?m)^task_id = ".*"$', f'task_id = "{s["client_id"]}"', txt, count=1)
    open(t, 'w').write(txt)
    # 2. zip, as the other samples: one top folder named by the client id, without .horizon/ and .DS_Store
    z = f"{S}/zips/{s['client_id']}.zip"
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for a, dirs, fs in os.walk(d):
            dirs[:] = [x for x in dirs if x != '.horizon']
            for f in fs:
                if f != '.DS_Store': zf.write(os.path.join(a, f), os.path.relpath(os.path.join(a, f), f'{S}/tasks'))
    # 3. runs at the pinned version, with each completed run's turn count
    rr = [q for q in get(f"api/tasks/{s['horizon_id']}/rollouts").get('rollouts', []) if q['task_version_number'] == s['version']]
    old = {q['id']: q for q in json.load(open(f"{S}/data/{s['client_id']}.json"))['rollouts']} if os.path.exists(f"{S}/data/{s['client_id']}.json") else {}
    out = []
    for q in rr:
        x = {k: q.get(k) for k in ('id', 'model', 'agent_type', 'effort', 'extracted_score', 'passed', 'is_errored', 'grader_ok', 'task_version_number', 'created_at')}
        if not q.get('is_errored'):
            tc = old.get(q['id'], {}).get('turn_count')
            x['turn_count'] = tc if tc is not None else get(f"api/rollouts/{q['id']}").get('turn_count')
        out.append(x)
    json.dump({'client_id': s['client_id'], 'horizon_id': s['horizon_id'], 'version': s['version'], 'status': s['status'], 'fetched': time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()), 'rollouts': out},
              open(f"{S}/data/{s['client_id']}.json", 'w'), indent=1)
    by = collections.Counter((q['model'], 'err' if q.get('is_errored') else q.get('passed')) for q in out)
    print(s['client_id'], 'v', s['version'], s['status'], 'zip', os.path.getsize(z), 'runs', dict(by))
json.dump(cfg, open(f'{S}/super.json', 'w'), indent=1)
