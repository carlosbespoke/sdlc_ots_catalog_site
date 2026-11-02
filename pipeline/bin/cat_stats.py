# Deterministic catalog statistics: domain tables, metadata, per-model pass rates, showcase selection.
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from cat_common import *
SL = shortlist()
ALLROWS = [r for r in green(load_rows()) if r['catalog']]
rows = dedupe(ALLROWS, SL)
REMOVED = collections.Counter(r['catalog'] for r in ALLROWS); REMOVED.subtract(collections.Counter(r['catalog'] for r in rows))
MM = json.load(open(f'{B}/ro_models.json'))
# several codenames can resolve to one model; merge them under the first codename seen for that model
CANON = {}
for k, v in MM.items(): CANON[k] = next(c for c, w in MM.items() if w == v)
canon = lambda m: CANON.get(m, m)
RO = {}
for d in ('ro', 'ro2'):  # ro2: refreshed runs at the sheet's selected version; overrides ro
    for f in os.listdir(f'{B}/{d}'):
        x = json.load(open(f'{B}/{d}/{f}')); RO[x['id']] = x
LONG = 200
PIN = {k: [t['name'] for t in v['showcase'][:3]] for k, v in json.load(open(f'{B}/backups/backup_pre_green/stats.json')).items()}
AFFINITY = {'Distributed systems & coordination': 'Applications & business domains', 'Observability & reliability': 'Cloud infrastructure & IaC',
            'Security': 'Systems, hardware & accelerators', 'Build, release & supply chain': 'Languages & developer tooling',
            'Cloud infrastructure & IaC': 'Languages & developer tooling', 'Data engineering & databases': 'Scientific & ML software',
            'Scientific & ML software': 'Data engineering & databases', 'Applications & business domains': 'Languages & developer tooling',
            'Languages & developer tooling': 'Applications & business domains', 'Systems, hardware & accelerators': 'Languages & developer tooling'}
TURNS = {}
TDIR = f'{B}/turns_all'  # turn_count of every completed run
for f in os.listdir(TDIR) if os.path.isdir(TDIR) else []:
    if f.startswith('_'): continue
    x = json.load(open(f'{TDIR}/{f}'))
    TURNS[x['id']] = [r for r in x['runs'] if not r.get('is_errored') and isinstance(r.get('turn_count'), (int, float))]
XTURNS = {}
for f in os.listdir(f'{B}/turns_x') if os.path.isdir(f'{B}/turns_x') else []:
    x = json.load(open(f'{B}/turns_x/{f}'))
    XTURNS[x['id']] = [r for r in x['runs'] if isinstance(r.get('turn_count'), (int, float))]
def turn_stats(tid, extra=False):
    runs = TURNS.get(tid) or (XTURNS.get(tid) if extra else None) or []
    if not runs: return None
    v = [r['turn_count'] for r in runs]; by = collections.defaultdict(list)
    for r in runs: by[canon(r['model'])].append(r['turn_count'])
    return {'runs': len(v), 'mean': sum(v) / len(v), 'min': min(v), 'max': max(v), 'by_model': {m: sum(x) / len(x) for m, x in by.items()}}
def median(v):
    v = sorted(v); n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)
def model_rows(tid):
    out = collections.defaultdict(lambda: dict(rollouts=0, graded=0, passed=0, errors=0, score_sum=0.0))
    for g in RO.get(tid, {}).get('grouped', []):
        o = out[canon(g['model'])]; o['rollouts'] += g['total_rollouts'] or 0; o['graded'] += g['graded_count'] or 0
        o['passed'] += g['pass_count'] or 0; o['errors'] += g['error_count'] or 0; o['score_sum'] += (g['avg_score'] or 0) * (g['total_rollouts'] or 0)
    return dict(out)
def rate(a, b): return None if not b else a / b
def dist(R, key):
    c = collections.Counter(r[key] for r in R); n = len(R)
    return [{'value': k, 'tasks': v, 'pct': round(100 * v / n, 1), 'shortlist': sum(1 for r in R if r[key] == k and r['name'] in SL)} for k, v in c.most_common()]
out = {}
for slug, cat in CATS:
    R = [r for r in rows if r['catalog'] == cat]
    # domain table; a domain under 1% of the catalog folds into its closest related domain (or the largest one)
    size = collections.Counter(r['sg'] for r in R); big = size.most_common(1)[0][0]
    fold = {}
    for sg, k in size.items():
        if 100 * k / len(R) < 1:
            t = AFFINITY.get(sg)
            fold[sg] = t if t in size and 100 * size[t] / len(R) >= 1 else big
    dg = lambda r: fold.get(r['sg'], r['sg'])
    dom = []
    for sg, n in collections.Counter(dg(r) for r in R).most_common():
        cats = collections.Counter(r['cat'] for r in R if dg(r) == sg).most_common()
        dom.append({'super_group': sg, 'tasks': n, 'pct': round(100 * n / len(R), 1), 'shortlist': sum(1 for r in R if dg(r) == sg and r['name'] in SL),
                    'categories': [{'category': k, 'tasks': v, 'pct': round(100 * v / len(R), 1), 'shortlist': sum(1 for r in R if r['cat'] == k and dg(r) == sg and r['name'] in SL)} for k, v in cats]})
    folded = fold
    # pass rates per model across catalog
    pm = collections.defaultdict(lambda: dict(tasks=0, rollouts=0, graded=0, passed=0, errors=0, per_task=[]))
    evaluated = 0
    for r in R:
        mr = model_rows(r['id'])
        if mr: evaluated += 1
        for m, o in mr.items():
            p = pm[m]; p['tasks'] += 1
            for k in ('rollouts', 'graded', 'passed', 'errors'): p[k] += o[k]
            if o['graded']: p['per_task'].append(o['passed'] / o['graded'])
    models = []
    for m, p in sorted(pm.items(), key=lambda x: -x[1]['rollouts']):
        pt = p['per_task']
        models.append({'codename': m, 'model': MM.get(m, '??'), 'tasks': p['tasks'], 'rollouts': p['rollouts'], 'graded': p['graded'], 'passed': p['passed'],
                       'pass_rate': rate(p['passed'], p['graded']), 'error_rate': rate(p['errors'], p['rollouts']),
                       'tasks_graded': len(pt), 'tasks_0': sum(1 for v in pt if v == 0), 'tasks_100': sum(1 for v in pt if v == 1),
                       'tasks_20_80': sum(1 for v in pt if 0.2 <= v <= 0.8), 'per_task_rates': pt})
    # showcase: shortlist only, up to 10, domain spread, prefer tasks with graded rollouts
    cand = [r for r in R if r['name'] in SL]
    def graded(r): return sum(o['graded'] for o in model_rows(r['id']).values())
    cand.sort(key=lambda r: (graded(r) == 0, SL[r['name']]))
    # the 3 shortlisted tasks with the shortest instruction.md (words, then characters)
    def plen(r):
        p = f"{B}/show/{r['name']}/instruction.md"
        if not os.path.exists(p): return (10**9, 10**9)
        t = open(p).read(); return (len(t.split()), len(t))
    # one task per task family (shortest prompt in that family), families taken in order of their shortest prompt; fill up to 3 by prompt length
    def family(r):
        n = r['name']
        if cat == 'Infrastructure as code':
            return ('CDK componentization' if n.startswith('cdk-') else 'Terraform to Pulumi port' if n.startswith('pulumi-')
                    else 'Policy remediation' if 'policy' in n else 'Terraform module refactor')
        return (r['final'], r['fam'])
    ranked = sorted(cand, key=lambda r: (plen(r), r['name']))
    fsize = collections.Counter(family(r) for r in R)
    best = {}
    for r in ranked: best.setdefault(family(r), r)
    order = sorted(best, key=lambda f: (-fsize[f], plen(best[f])))
    pick = [best[f] for f in order[:3]]
    # keep the examples already written up (prompts, diagrams, workflow text) when they are still in the catalog
    if PIN.get(slug) and all(any(r['name'] == n for r in R) for n in PIN[slug]):
        pick = [next(r for r in R if r['name'] == n) for n in PIN[slug]]
    for r in ranked:
        if len(pick) < 3 and r not in pick: pick.append(r)
    show = []
    for r in pick:
        mr = model_rows(r['id'])
        ts = turn_stats(r['id'], extra=True)
        show.append({'turns': ts, 'name': r['name'], 'id': r['id'], 'rank': SL[r['name']], 'batch': r['batch'], 'final': r['final'], 'super_group': r['sg'], 'category': r['cat'],
                     'language': r['lang'], 'role': r['role'], 'seniority': r['sen'], 'shape': r['shape'],
                     'models': [{'codename': m, 'model': MM.get(m, '??'), **o, 'pass_rate': rate(o['passed'], o['graded']), 'error_rate': rate(o['errors'], o['rollouts']),
                                 'avg_score': (o['score_sum'] / o['rollouts']) if o['rollouts'] else None} for m, o in sorted(mr.items(), key=lambda x: -x[1]['rollouts'])]})
    TS = [(r, turn_stats(r['id'])) for r in R]; TS = [(r, t) for r, t in TS if t]
    means = [t['mean'] for _, t in TS]
    tm = collections.defaultdict(lambda: [0, 0.0, 0, set()])
    for r in R:
        for x in TURNS.get(r['id']) or []:
            v = tm[canon(x['model'])]; v[0] += 1; v[1] += x['turn_count']; v[2] += x['turn_count'] >= LONG; v[3].add(r['id'])
    capped = sum(1 for r in R for x in TURNS.get(r['id']) or [] if x.get('max_turns') and x['turn_count'] >= x['max_turns'])
    turns = {'capped': capped, 'tasks_with_turns': len(TS), 'runs': sum(t['runs'] for _, t in TS), 'mean_of_task_means': (sum(means) / len(means)) if means else None,
             'median_of_task_means': median(means), 'long_horizon_tasks': sum(1 for m in means if m >= LONG), 'threshold': LONG,
             'task_means': means, 'max_task_mean': max(means) if means else None, 'min_task_mean': min(means) if means else None,
             'by_model': [{'codename': m, 'model': MM.get(m, '??'), 'runs': v[0], 'tasks': len(v[3]), 'mean': v[1] / v[0], 'runs_200_plus': v[2]} for m, v in sorted(tm.items(), key=lambda x: -x[1][0])]}
    out[slug] = {'copies_removed': REMOVED[cat], 'turns': turns, 'title': cat, 'tasks': len(R), 'shortlist': sum(1 for r in R if r['name'] in SL), 'batches': collections.Counter(r['batch'] for r in R).most_common(),
                 'final_parts': collections.Counter(r['final'] for r in R).most_common(), 'evaluated_tasks': evaluated,
                 'super_groups': len(dom), 'folded': folded, 'categories': len({r['cat'] for r in R}),
                 'domain': dom, 'language': dist(R, 'lang'), 'role': dist(R, 'role'), 'seniority': dist(R, 'sen'), 'models': models, 'showcase': show}
    print(slug, 'turn tasks', len(TS), 'mean', turns['mean_of_task_means'], 'long', turns['long_horizon_tasks'])
    print(slug, len(R), 'evaluated', evaluated, 'models', len(models), 'showcase', [s['name'] for s in show])
json.dump(out, open(f'{B}/cat/stats.json', 'w'), indent=1)
