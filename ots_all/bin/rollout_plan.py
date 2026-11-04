# Rollout plan: bring every kept model to the larger of 5% of a catalog's tasks or 5 tasks (the row threshold), with 4 graded
# runs per task, under the new run settings. Writes rollout_plan/plan.csv (one row per task and model) and rollout_plan/summary.json.
#
# Task choice, per catalog and model, among report tasks the model has no graded run on:
#   1. the catalog's sample tasks first (their sample pages get more runs);
#   2. then domains in proportion to the catalog's domain mix (largest remainder);
#   3. inside a domain, tasks graded by more of the other kept models first (paired comparison), then healthy tasks
#      (lowest error share across all their runs), then a seeded shuffle, keeping languages varied.
# Horizon runs a task at its active version (the submit call takes no version), so only tasks whose active version is the
# version the report uses are eligible; the new runs then join the existing ones. Active versions: rollout_plan/active_versions.json.
#
# Cost: dollars per turn for the model in the catalog (Horizon cost ledger / mean turns of that model there), times the
# expected turns under the new 1,200-turn limit (runs that hit the old limit are assumed to run to 1,200).
import math, random, csv, statistics
from common import *
random.seed(20261104)
OUT = f'{H}/rollout_plan'; os.makedirs(OUT, exist_ok=True)
GRADED, CAP = 4, 1200
SETTINGS = {'max_turns': CAP, 'effort': 'max', 'agent_type': 'typhoon (Terminus V2)', 'max_tokens': 32000, 'agent_timeout_sec': 43200}
CODE = {'z-ai/glm-5.3-flash': 'steppe', 'google/gemini-3.8-flash': 'kittiwake', 'google/gemini-4-argon': 'umbra'}
NAME = {'z-ai/glm-5.3-flash': 'GLM 5.3 Flash', 'google/gemini-3.8-flash': 'Gemini 3.8 Flash', 'google/gemini-4-argon': 'Gemini 4 Argon'}
NEWC = json.load(open(f'{H}/cat/new_task_classes.json')); SID = json.load(open(f'{H}/cat/sample_ids.json'))
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
def meta(t):
    r = ROWS.get(t['id']); c = NEWC.get(t['name'], {})
    return (r['sg'] if r else c.get('sg', '?')), (r['lang'] if r else c.get('lang', '?'))
# measured dollars per run (Horizon cost ledger, versions run by one model only); Argon from the 64-run Argon proposal basis
C = json.load(open('/private/tmp/claude-502/-Users-carlos-code-sdlc-final-samples/c9ff029e-97d0-441d-8596-74b78a8141ec/scratchpad/cost.json'))
ARGON = json.load(open(f'{P}/argon_costs.json'))
def turns(m, cat=None):
    return [(r['turn_count'], r.get('max_turns')) for t in TASKS if cat in (None, t['catalog']) for r in TURNS[t['id']] if MM[r['model']] == m]
def per_turn(m, cat):
    if m == 'google/gemini-4-argon':
        return sum(x['total_cost'] for x in ARGON) / sum(x['turn_count'] for x in ARGON), 'Argon proposal runs (64)'
    k = f'{cat}|{NAME[m]}'
    tv = turns(m, cat)
    if k in C and tv: return statistics.mean(a for a, _ in C[k]) / statistics.mean(x for x, _ in tv), 'measured in this catalog'
    pairs = [(statistics.mean(a for a, _ in v), statistics.mean(x for x, _ in turns(m, kk.split('|')[0]))) for kk, v in C.items() if kk.endswith('|' + NAME[m]) and turns(m, kk.split('|')[0])]
    return sum(a for a, _ in pairs) / sum(b for _, b in pairs), 'model average over other catalogs'
def exp_turns(m, cat):
    # this model in this catalog; else the other kept models in this catalog; else this model everywhere
    tv = turns(m, cat) or [x for mm in CODE for x in turns(mm, cat)] or turns(m)
    return statistics.mean(CAP if (mt and tc >= 0.98 * mt) else min(tc, CAP) for tc, mt in tv), len(tv)
ACT = json.load(open(f'{OUT}/active_versions.json'))['tasks']
same = lambda t: ACT[t['id']]['active'] == RO[t['id']]['version']
err = {m: (lambda a: sum(bool(q.get('is_errored')) for q in a) / len(a))([q for t in TASKS for q in RO[t['id']]['rollouts'] if MM.get(q['model']) == m]) for m in CODE}
plan, groups = [], []
for slug, cat in CATS:
    T = [t for t in TASKS if t['catalog'] == cat]; N = len(T); t5 = math.ceil(0.05 * N); tgt = max(t5, 5)
    dom = collections.Counter(meta(t)[0] for t in T)
    for m in CODE:
        have = [t for t in T if m in runs(t['id'])]; gap = max(0, tgt - len(have))
        if not gap: continue
        cand = [t for t in T if m not in runs(t['id']) and same(t)]
        def key(t):
            rs = RO[t['id']]['rollouts']; e = sum(bool(q.get('is_errored')) for q in rs) / max(1, len(rs))
            return (-len(set(runs(t['id'])) - {m}), round(e, 1), random.random())
        pick = [t for t in cand if t.get('sample')][:gap]
        left = gap - len(pick)
        if left:
            cd = collections.Counter(meta(t)[0] for t in cand if t not in pick)
            share = {d: left * dom[d] / N for d in cd}
            alloc = {d: min(cd[d], int(share[d])) for d in cd}
            for d in sorted(cd, key=lambda d: -(share[d] - int(share[d]))):
                if sum(alloc.values()) >= left: break
                if alloc[d] < cd[d]: alloc[d] += 1
            while sum(alloc.values()) < left:  # top up from the largest domains with room
                d = max((d for d in cd if alloc[d] < cd[d]), key=lambda d: cd[d] - alloc[d]); alloc[d] += 1
            for d, k in alloc.items():
                pool = sorted([t for t in cand if meta(t)[0] == d and t not in pick], key=key); langs = set(); got = []
                for t in pool:  # prefer a new language while the top tier lasts
                    if len(got) < k and meta(t)[1] not in langs: got.append(t); langs.add(meta(t)[1])
                for t in pool:
                    if len(got) < k and t not in got: got.append(t)
                pick += got
        ppt, src = per_turn(m, cat); et, nt = exp_turns(m, cat)
        launch = math.ceil(len(pick) * GRADED / (1 - err[m]))
        exp_cost, cap_cost = launch * ppt * et, launch * ppt * CAP
        groups.append({'catalog': cat, 'model': NAME[m], 'codename': CODE[m], 'catalog_tasks': N, 'target_5pct': t5, 'target': tgt, 'have': len(have), 'add': len(pick),
                       'runs_to_launch': launch, 'error_rate': round(err[m], 2), 'usd_per_turn': round(ppt, 4), 'cost_basis': src, 'expected_turns': round(et), 'turn_sample': nt,
                       'expected_usd': round(exp_cost), 'ceiling_usd': round(cap_cost)})
        for t in pick:
            d, l = meta(t)
            plan.append({'catalog': cat, 'model': NAME[m], 'codename': CODE[m], 'task_id': t['id'], 'task': t['name'], 'sample_id': SID.get(t['name'], '') if t.get('sample') else '',
                         'version': RO[t['id']]['version'], 'active_version': ACT[t['id']]['active'], 'domain': d, 'language': l, 'graded_runs_wanted': GRADED,
                         'other_models_graded': ', '.join(sorted(NAME.get(x, x) for x in runs(t['id']) if x != m))})
with open(f'{OUT}/plan.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(plan[0])); w.writeheader(); w.writerows(plan)
json.dump({'settings': SETTINGS, 'graded_runs_per_task': GRADED, 'error_rates': {NAME[m]: round(v, 2) for m, v in err.items()}, 'groups': groups,
           'totals': {k: sum(g[k] for g in groups) for k in ('add', 'runs_to_launch', 'expected_usd', 'ceiling_usd')}}, open(f'{OUT}/summary.json', 'w'), indent=1)
for g in groups: print(f"{g['catalog'][:22]:22} {g['model']:16} N{g['catalog_tasks']:4} have {g['have']:3} tgt {g['target']:2} add {g['add']:2} runs {g['runs_to_launch']:3} ${g['usd_per_turn']:.4f}/turn x {g['expected_turns']} turns = ${g['expected_usd']} (ceiling ${g['ceiling_usd']}) [{g['cost_basis']}]")
print('TOTAL', json.load(open(f'{OUT}/summary.json'))['totals'])
