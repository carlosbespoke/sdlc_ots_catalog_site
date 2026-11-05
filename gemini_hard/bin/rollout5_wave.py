# Adaptive Argon rollout, run in waves from our side (Horizon's own adaptive mode is off globally and needs binary grading).
#   python bin/rollout5_wave.py --collect            read every submitted evaluation's status and runs into rollout_plan/results.json
#   python bin/rollout5_wave.py --submit [--tasks id,id] [--limit N] [--dry]
#        submits 1 Gemini 4 Argon run for each plan task that still needs one: no passed run yet (a run that scores 1 stops the task),
#        fewer than 3 graded runs, nothing pending, and at most 2 errored attempts. Logged to rollout_plan/waves.json.
# A task is "done" once it has a pass, 3 graded runs, or 3 errored attempts. Paid action: --submit starts real runs.
import csv, json, os, sys, time, datetime, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
MAX_GRADED, MAX_ERRORED = 3, 3
R = {r['task_id']: r for r in csv.DictReader(open(f'{OUT}/runs.csv'))}
W_P, RES_P = f'{OUT}/waves.json', f'{OUT}/results.json'
W = json.load(open(W_P)) if os.path.exists(W_P) else []
RES = json.load(open(RES_P)) if os.path.exists(RES_P) else {}
c = client.Client()
TERM = ('completed', 'failed', 'cancelled', 'errored', 'error')
def get(p, q=None):
    for a in range(8):
        try: return c.get(p, q)
        except Exception: time.sleep(2 + a)
def collect():
    for w in W:
        e = w.get('evaluation_id')
        if not e or RES.get(e, {}).get('final'): continue
        st = (get(f'api/evaluations/{e}') or {}).get('status') or 'poll-error'
        runs = []
        for s in get(f'api/evaluations/{e}/rollouts', {}) or []:
            for r in get(f"api/evaluations/{e}/tasks/{s['local_task_id']}/rollouts", {}) or []:
                d = get(f"api/rollouts/{r['id']}") or {}; d = d.get('rollout', d)
                runs.append({k: d.get(k) for k in ('id', 'evaluation_status', 'turn_count', 'task_version_number', 'passed', 'is_errored', 'extracted_score', 'total_cost', 'stop_reason')})
        RES[e] = {'task_id': w['task_id'], 'status': st, 'final': st in TERM, 'runs': runs}
    json.dump(RES, open(RES_P, 'w'), indent=1)
def state(tid):
    ev = [w for w in W if w['task_id'] == tid and w.get('evaluation_id')]
    runs = [r for w in ev for r in RES.get(w['evaluation_id'], {}).get('runs', [])]
    pending = any(not RES.get(w['evaluation_id'], {}).get('final') for w in ev)
    graded = [r for r in runs if not r['is_errored'] and (r['passed'] is not None or r['extracted_score'] is not None)]
    passed = any(r['passed'] or (r['extracted_score'] or 0) >= 0.999 for r in graded)
    errored = sum(1 for r in runs if r['is_errored']) + sum(1 for w in ev if RES.get(w['evaluation_id'], {}).get('final') and not RES[w['evaluation_id']]['runs'])
    return {'graded': len(graded), 'passed': passed, 'errored': errored, 'pending': pending, 'cost': sum(r['total_cost'] or 0 for r in runs)}
def needs(tid):
    s = state(tid); return not s['passed'] and not s['pending'] and s['graded'] < MAX_GRADED and s['errored'] < MAX_ERRORED
if '--collect' in sys.argv:
    collect(); S = {t: state(t) for t in R}
    print('tasks', len(S), 'passed', sum(s['passed'] for s in S.values()), 'pending', sum(s['pending'] for s in S.values()),
          'graded runs', sum(s['graded'] for s in S.values()), 'errored', sum(s['errored'] for s in S.values()),
          'still need runs', sum(needs(t) for t in R), 'cost $%.2f' % sum(s['cost'] for s in S.values()))
if '--submit' in sys.argv:
    from horizon import HorizonClient
    h = HorizonClient(); DRY = '--dry' in sys.argv
    only = next((a.split('=', 1)[1].split(',') for a in sys.argv if a.startswith('--tasks=')), None)
    lim = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--limit=')), None)
    todo = sorted([t for t in R if (only is None or t in only) and needs(t)], key=lambda t: int(R[t]['priority']))[:lim]
    wave = 1 + max([w['wave'] for w in W] or [0])
    for tid in todo:
        r = R[tid]
        act = (get(f'api/tasks/{tid}') or {}).get('current_version')
        rec = {'wave': wave, 'task_id': tid, 'task': r['task'], 'catalog': r['catalog'], 'set': r['set'], 'version': r['version'], 'active_version': act, 'machine_type': r['machine_type']}
        if r['version'] and str(act) != r['version']: rec['skipped'] = 'active version changed'; W.append(rec); print('SKIP', r['task']); continue
        if DRY: print('DRY', wave, r['set'], r['catalog'], r['task'], r['machine_type']); continue
        try:
            ev = h.evaluations.trigger(task_id=tid, model=r['codename'], runs=1, max_turns=int(r['max_turns']), max_tokens=int(r['max_tokens']),
                                       agent_type=r['agent_type'], effort_tier=int(r['effort_tier']), machine_type=r['machine_type'], sandbox_backend=r['sandbox_backend'])
            rec['evaluation_id'] = getattr(ev, 'evaluation_id', None) or getattr(ev, 'id', None)
        except Exception as e: rec['error'] = str(e)[:400]
        rec['submitted'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'); W.append(rec)
        json.dump(W, open(W_P, 'w'), indent=1); print(rec.get('evaluation_id') or rec.get('error'), r['set'], r['task'])
    print('wave', wave, 'submitted', sum(1 for w in W if w['wave'] == wave and w.get('evaluation_id')), 'of', len(todo))
