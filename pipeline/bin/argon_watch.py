# Poll the Argon evaluations; exit (waking Claude) when all are terminal, spend hits the alert line,
# the spend per finished run projects past budget, or errored runs pile up.
import json, sys, time
from horizon import HorizonClient
L = json.load(open(sys.argv[1])); BUDGET = L['budget_usd']; ALERT = float(sys.argv[2]) if len(sys.argv) > 2 else 850; STOP = float(sys.argv[3]) if len(sys.argv) > 3 else None; TOTAL = sum(e['runs'] for e in L['evaluations'])
c = HorizonClient()
OPEN = {'running', 'pending', 'scheduled', 'queued', 'starting', None}
def snap():
    spend = 0.0; done = err = term = 0; rows = []
    for e in L['evaluations']:
        eid = e['evaluation_id']
        try: usd = c.evaluations.cost(eid).cost_usd or 0.0
        except Exception: usd = 0.0
        try:
            s = c.evaluations.batch_status(eid); st = s.state; t = s.is_terminal
            stat = [x.get('status') for x in s.rollout_statuses or []]
            fin = sum(1 for x in stat if x not in OPEN); er = sum(1 for x in stat if x == 'errored')
        except Exception: fin = er = 0; t = False; st = '?'
        spend += usd; done += fin; err += er; term += bool(t)
        rows.append(f"{e['catalog'][:14]}={st}:{fin}/{e['runs']}(err {er}):${usd:.0f}")
    return spend, done, err, term, rows
while True:
    spend, done, err, term, rows = snap()
    line = f"{time.strftime('%H:%M')} spend=${spend:.2f} finished={done}/{TOTAL} errored={err} terminal_evals={term}/{len(L['evaluations'])} | " + ' '.join(rows)
    print(line, flush=True)
    if term == len(L['evaluations']): print('DONE', line); break
    if not STOP and spend >= ALERT: print('ALERT spend reached', spend); break
    if STOP and spend >= STOP:
        for e in L['evaluations']:
            try:
                if not c.evaluations.batch_status(e['evaluation_id']).is_terminal: c.evaluations.cancel(e['evaluation_id']); print('CANCELLED', e['catalog'], e['evaluation_id'])
            except Exception as x: print('cancel failed', e['evaluation_id'], x)
        print('STOPPED at budget', spend); break
    if done >= 10 and err / done > 0.2: print('ALERT errored runs', err, 'of', done); break
    time.sleep(600)
