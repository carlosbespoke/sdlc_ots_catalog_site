# Capability-regression rollout (6 Nov): the tasks where Gemini 3.8 Flash's pass rate is above Gemini 4 Argon's (both ran;
# gemini_hard_universe.csv). Each task gets 5 runs of each model under each of two agents, all at maximum effort (tier 3, the
# highest both models offer): typhoon (Terminus V2) and apogee (Antigravity CLI). Same task version (the selected one, which must
# be the active version), same VM, turn and token limits for every arm, all submitted together.
#   regress_plan.py            write regression_plan/{plan.csv,task_infra.json,runs.csv}
#   regress_plan.py --submit   launch every arm not yet launched (paid), recorded in regression_plan/waves.json
#   regress_plan.py --collect  fetch run results into regression_plan/results.json and print a summary
import sys, os, csv, json, time, tomllib, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/regression_plan'; os.makedirs(f'{OUT}/toml', exist_ok=True)
MODELS = [('umbra', 'Gemini 4 Argon'), ('kittiwake', 'Gemini 3.8 Flash')]
AGENTS = [('typhoon', 'Terminus V2'), ('apogee', 'Antigravity CLI')]
RUNS, MAX_TURNS, MAX_TOKENS, EFFORT_TIER = 5, 1200, 32000, 3
MACHINES = [(2, 4096), (4, 8192), (8, 16384), (16, 32768)]
c = client.Client()
def num(x): return int(x) if x else 0
S = {t['id']: t for t in json.load(open(f'{H}/cat/sel5.json'))}
def plan():
    out = []
    for r in csv.DictReader(open(f'{H}/gemini_hard_universe.csv')):
        ag, ap, fg, fp = (num(r[k]) for k in ('Argon runs graded', 'Argon passes', 'Gemini 3.8 Flash runs graded', 'Gemini 3.8 Flash passes'))
        if ag and fg and fp / fg > ap / ag:
            tid = r['Horizon task id']
            out.append({'task_id': tid, 'task': r['Task'], 'catalog': r['Catalog'], 'sample': r['Sample'], 'version': S[tid]['version'],
                        'argon_before': f'{ap}/{ag}', 'flash_before': f'{fp}/{fg}'})
    return out
def infra(r):
    f = f"{OUT}/toml/{r['task_id']}.toml"
    if not os.path.exists(f):
        p = {'path': 'task.toml', 'version': r['version']}; spec.validate('GET', f"api/tasks/{r['task_id']}/files/content", p)
        t = c._raw._make_request('GET', f"api/tasks/{r['task_id']}/files/content", params=p).text
        try:
            j = json.loads(t); t = j.get('content', t) if isinstance(j, dict) else t
        except Exception: pass
        open(f, 'w').write(t)
    d = tomllib.loads(open(f).read())  # task.toml is untrusted data: parsed, never executed
    env, ag, ve = d.get('environment', {}), d.get('agent', {}), d.get('verifier', {}); venv = ve.get('environment', {}) or {}
    return {'cpus': env.get('cpus', 1), 'memory_mb': env.get('memory_mb', 2048), 'verifier_mode': ve.get('environment_mode', 'shared'),
            'verifier_cpus': venv.get('cpus'), 'verifier_memory_mb': venv.get('memory_mb'), 'agent_timeout_sec': ag.get('timeout_sec', 3600)}
def machine(o):
    sep = o['verifier_mode'] == 'separate'
    cpu = max(o['cpus'], (o['verifier_cpus'] or o['cpus']) if sep else 0); mem = o['memory_mb'] + ((o['verifier_memory_mb'] or o['memory_mb']) if sep else 0)
    cc, m = next((cc, m) for cc, m in MACHINES if cc >= cpu and m >= mem); return f'e2-custom-{cc}-{m}'
def active(tid):
    vs = c.get(f'api/tasks/{tid}/versions'); vs = vs.get('versions') if isinstance(vs, dict) else vs
    return next(v['version_number'] for v in vs if v['is_active'])
if '--submit' not in sys.argv and '--collect' not in sys.argv:
    P = plan(); INF = {}; rows = []
    for r in P:
        o = infra(r); INF[r['task_id']] = o; act = active(r['task_id'])
        assert act == r['version'], f"{r['task']}: selected version {r['version']} is not the active version {act}"
        for cn, mname in MODELS:
            for at, aname in AGENTS:
                rows.append({**r, 'arm': f'{cn}/{at}', 'model': mname, 'codename': cn, 'agent': aname, 'agent_type': at, 'runs': RUNS,
                             'max_turns': MAX_TURNS, 'max_tokens': MAX_TOKENS, 'effort_tier': EFFORT_TIER, 'sandbox_backend': 'cloud_batch',
                             'machine_type': machine(o), 'agent_timeout_sec': o['agent_timeout_sec']})
    for name, data in (('plan.csv', P), ('runs.csv', rows)):
        with open(f'{OUT}/{name}', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    json.dump(INF, open(f'{OUT}/task_infra.json', 'w'), indent=1)
    print(len(P), 'tasks,', len(rows), 'arms,', sum(r['runs'] for r in rows), 'runs', dict(collections.Counter(r['machine_type'] for r in rows)))
    for r in P: print(' ', r['catalog'][:24], r['task'][:48], 'v' + str(r['version']), 'Flash', r['flash_before'], 'Argon', r['argon_before'], r['sample'])
W = json.load(open(f'{OUT}/waves.json')) if os.path.exists(f'{OUT}/waves.json') else []
if '--submit' in sys.argv:
    import horizon; h = horizon.HorizonClient(); done = {(w['task_id'], w['arm']) for w in W if w.get('evaluation_id')}
    for r in csv.DictReader(open(f'{OUT}/runs.csv')):
        if (r['task_id'], r['arm']) in done: continue
        for a in range(4):
            try:
                ev = h.evaluations.trigger(task_id=r['task_id'], model=r['codename'], runs=int(r['runs']), max_turns=int(r['max_turns']),
                                           max_tokens=int(r['max_tokens']), agent_type=r['agent_type'], effort_tier=int(r['effort_tier']),
                                           machine_type=r['machine_type'], sandbox_backend=r['sandbox_backend'])
                eid = getattr(ev, 'id', None) or getattr(ev, 'evaluation_id', None) or (ev.get('id') if isinstance(ev, dict) else None); break
            except Exception as e: err = str(e)[:300]; time.sleep(5 * (a + 1)); eid = None
        W.append({'task_id': r['task_id'], 'task': r['task'], 'arm': r['arm'], 'runs': int(r['runs']), 'machine_type': r['machine_type'],
                  'evaluation_id': eid, 'error': None if eid else err, 'submitted': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        json.dump(W, open(f'{OUT}/waves.json', 'w'), indent=1); print('submitted' if eid else 'FAILED', r['arm'], r['task'][:40], eid or err)
if '--collect' in sys.argv:
    R = {}; DONE = ('completed', 'failed', 'errored', 'cancelled', 'error')
    for w in W:
        if not w.get('evaluation_id'): continue
        d = c.get(f"api/tasks/{w['task_id']}/rollouts"); rs = [q for q in d.get('rollouts') or [] if q.get('evaluation_id') == w['evaluation_id']]
        R[w['evaluation_id']] = {'task_id': w['task_id'], 'task': w['task'], 'arm': w['arm'], 'runs': [{k: q.get(k) for k in (
            'id', 'evaluation_status', 'passed', 'is_errored', 'extracted_score', 'total_cost', 'total_output_tokens', 'created_at', 'completed_at')} for q in rs]}
    json.dump(R, open(f'{OUT}/results.json', 'w'), indent=1)
    tab = collections.defaultdict(lambda: [0, 0, 0, 0]); cost = 0
    for v in R.values():
        for q in v['runs']:
            t = tab[(v['task'], v['arm'])]; cost += q.get('total_cost') or 0
            if q['evaluation_status'] not in DONE: t[3] += 1
            elif q.get('is_errored') or q['evaluation_status'] != 'completed': t[2] += 1
            else: t[0] += 1; t[1] += bool(q['passed'])
    arms = [f'{cn}/{at}' for cn, _ in MODELS for at, _ in AGENTS]
    print('task'.ljust(46), *[a.ljust(18) for a in arms]); print(' ' * 46, *['passed/graded err run'.ljust(18) for _ in arms])
    for task in sorted({k[0] for k in tab}):
        print(task[:45].ljust(46), *[(f"{tab[(task, a)][1]}/{tab[(task, a)][0]} {tab[(task, a)][2]} {tab[(task, a)][3]}").ljust(18) for a in arms])
    print('pending runs', sum(t[3] for t in tab.values()), 'cost so far $', round(cost, 2))
