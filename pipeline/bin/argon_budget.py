# Budgeted Gemini 4 Argon selection: per-catalog task quota, 2 runs per task, shortlist first within a domain-proportional allocation.
# Cost per task = runs x (task's mean turns across existing runs, else catalog mean) x Argon's observed cost per turn.
import sys, os, json, csv, random, collections, statistics as st
B = sys.argv[1]; os.environ['B'] = B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cat_common import load_rows, green, dedupe, shortlist, CATS
SL = shortlist(); MM = json.load(open(f'{B}/ro_models.json')); S = json.load(open(f'{B}/cat/stats.json'))
R = [r for r in dedupe([r for r in green(load_rows()) if r['catalog']], SL) if r['catalog'] != 'Optimization']
AC = json.load(open(f'{B}/argon_costs.json')); PER_TURN = sum(x['total_cost'] for x in AC) / sum(x['turn_count'] for x in AC)
RUNS = 2
QUOTA = {'ProgramBench': 10, 'System design': 0, 'Diagnosis, Debugging, and Bug Fixing': 15, 'Feature implementation': 10,
         'Infrastructure as code': 20, 'Data engineering': 17, 'Migration': 12}
PB_FINAL = 'ProgramBench reimplementation'  # repo-upgrade tasks have never been run; left out of this budget
rng = random.Random(20261028)
ro = lambda r: json.load(open(f"{B}/ro2/{r['id']}.json"))
graded_by = lambda r: {g['model']: g.get('graded_count') or 0 for g in ro(r)['grouped'] if g.get('graded_count')}
def turns(r):
    p = f"{B}/turns_all/{r['id']}.json"
    v = [q['turn_count'] for q in json.load(open(p))['runs']] if os.path.exists(p) else []
    return st.mean(v) if v else None
rows, summary = [], []
for slug, cat in CATS:
    X = [r for r in R if r['catalog'] == cat and (cat != 'ProgramBench' or r['final'] == PB_FINAL)]
    fold = S[slug]['folded']; dom = lambda r: fold.get(r['sg'], r['sg'])
    cmean = S[slug]['turns']['mean_of_task_means']
    argon = [r for r in R if r['catalog'] == cat and 'umbra' in graded_by(r)]
    q = min(QUOTA[cat], len(X))
    size = collections.Counter(dom(r) for r in X)
    # largest-remainder allocation of q over domains
    raw = {d: q * k / len(X) for d, k in size.items()}; alloc = {d: int(v) for d, v in raw.items()}
    for d in sorted(raw, key=lambda d: -(raw[d] - alloc[d]))[:q - sum(alloc.values())]: alloc[d] += 1
    pick = []
    for d, k in alloc.items():
        pool = [r for r in X if dom(r) == d]; rng.shuffle(pool)
        pool.sort(key=lambda r: (r['name'] not in SL, not (set(graded_by(r)) - {'umbra'})))  # shortlist first, then paired
        pick += pool[:k]
    for r in pick:
        t = turns(r) or cmean
        rows.append({'catalog': cat, 'task_name': r['name'], 'task_id': r['id'], 'task_version': ro(r)['version'], 'batch': r['batch'],
                     'final_category': r['final'], 'domain': dom(r), 'sub_domain': r['cat'], 'language': r['lang'],
                     'reason': 'shortlist' if r['name'] in SL else 'stratified sample', 'argon_runs': RUNS,
                     'est_turns_per_run': round(t), 'est_cost_usd': round(RUNS * t * PER_TURN, 2),
                     'other_models_graded': '; '.join(f"{MM.get(m, m)} x{n}" for m, n in sorted(graded_by(r).items(), key=lambda x: -x[1]) if m != 'umbra')})
    sel = [x for x in rows if x['catalog'] == cat]
    summary.append({'catalog': cat, 'tasks': len([r for r in R if r['catalog'] == cat]), 'argon_now': len(argon), 'new': len(sel),
                    'shortlist': sum(1 for x in sel if x['reason'] == 'shortlist'), 'runs': RUNS * len(sel),
                    'cost': sum(x['est_cost_usd'] for x in sel), 'after': len(argon) + len(sel)})
out = '/Users/carlos/code/sdlc_final_samples/argon_proposal'
with open(f'{out}/argon_task_selection_1000usd.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f'cost per turn {PER_TURN:.4f}')
for s in summary: print(s)
tot = sum(s['cost'] for s in summary); print('runs', sum(s['runs'] for s in summary), 'est cost', round(tot), 'reserve', round(1000 - tot))
