# Catalog statistics for all 1,356 tasks and every model (cat/stats.json): domains, languages, seniority, per-model average reward (average@k),
# turn counts and the samples of each catalog.
from common import *
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
NEWC = json.load(open(f'{H}/cat/new_task_classes.json'))
SID = json.load(open(f'{H}/cat/sample_ids.json'))  # client-facing task ids of the samples
URL = {k: f'https://drive.google.com/file/d/{v[0]}/view' for k, v in json.load(open(f'{H}/cat/sample_urls.json')).items() if not k.startswith('_')}
LONG, MIN_TASKS = 200, 5  # long-horizon threshold; a model gets a row in a catalog's tables once it has graded runs on this many tasks
AFFINITY = {'Distributed systems & coordination': 'Applications & business domains', 'Observability & reliability': 'Cloud infrastructure & IaC',
            'Security': 'Systems, hardware & accelerators', 'Build, release & supply chain': 'Languages & developer tooling',
            'Cloud infrastructure & IaC': 'Languages & developer tooling', 'Data engineering & databases': 'Scientific & ML software',
            'Scientific & ML software': 'Data engineering & databases', 'Applications & business domains': 'Languages & developer tooling',
            'Languages & developer tooling': 'Applications & business domains', 'Systems, hardware & accelerators': 'Languages & developer tooling'}
def meta(t):
    r = ROWS.get(t['id'])
    if r: return {'sg': r['sg'], 'cat': r['cat'], 'lang': r['lang'], 'sen': r['sen'].replace('–', '-'), 'role': r['role'], 'final': r['final']}
    c = NEWC[t['name']]
    return {'sg': c['sg'], 'cat': c['cat'], 'lang': c['lang'], 'sen': c['sen'], 'role': c['role'], 'final': t['catalog']}
def turn_stats(tid):
    v = TURNS[tid]
    if not v: return None
    by = collections.defaultdict(list)
    for r in v: by[MM[r['model']]].append(r['turn_count'])
    return {'runs': len(v), 'mean': sum(r['turn_count'] for r in v) / len(v), 'by_model': {m: sum(x) / len(x) for m, x in sorted(by.items(), key=lambda kv: -len(kv[1]))}}
def median(v):
    v = sorted(v); n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)
def model_rows(tid):
    out = collections.defaultdict(lambda: dict(rollouts=0, graded=0, passed=0, errors=0, score_sum=0.0))
    for q in RO[tid]['rollouts']:
        if q['model'] in DROPPED: continue
        o = out[MM[q['model']]]; o['rollouts'] += 1
        if q.get('is_errored'): o['errors'] += 1; continue
        if q.get('passed') is None: continue
        o['graded'] += 1; o['passed'] += bool(q['passed']); o['score_sum'] += q.get('extracted_score') or 0
    return dict(out)
rate = lambda a, b: None if not b else a / b
# samples: the earlier main samples first, then the promoted ones, each in their earlier order
SUPER = json.load(open(f'{H}/super/super.json'))['samples']; BYID = {t['id']: t for t in ALL_TASKS}
SAMPLES = sorted([t for t in TASKS if t.get('sample') in ('main', 'attached')], key=lambda t: (t['sample'] != 'main', t['sample_order']))
out = {}
for slug, cat in CATS:
    R = [{**t, **meta(t)} for t in TASKS if t['catalog'] == cat]
    n = len(R)
    dist = lambda key: [{'value': k, 'tasks': v, 'pct': round(100 * v / n, 1)} for k, v in collections.Counter(r[key] for r in R).most_common()]
    # domains under 1% of the catalog fold into a related larger one
    size = collections.Counter(r['sg'] for r in R); big = size.most_common(1)[0][0]; fold = {}
    for sg, k in size.items():
        if 100 * k / n < 1:
            t = AFFINITY.get(sg); fold[sg] = t if t in size and 100 * size[t] / n >= 1 else big
    dg = lambda r: fold.get(r['sg'], r['sg'])
    dom = [{'super_group': sg, 'tasks': k, 'pct': round(100 * k / n, 1),
            'categories': [{'category': c, 'tasks': v, 'pct': round(100 * v / n, 1)} for c, v in collections.Counter(r['cat'] for r in R if dg(r) == sg).most_common()]}
           for sg, k in collections.Counter(dg(r) for r in R).most_common()]
    pm = collections.defaultdict(lambda: dict(tasks=0, rollouts=0, graded=0, passed=0, errors=0, per_task=[]))
    for r in R:
        for m, o in model_rows(r['id']).items():
            p = pm[m]; p['tasks'] += 1
            for k in ('rollouts', 'graded', 'passed', 'errors'): p[k] += o[k]
            if o['graded']: p['per_task'].append(o['score_sum'] / o['graded'])
    models = []
    for m, p in sorted(pm.items(), key=lambda x: -x[1]['rollouts']):
        pt = p['per_task']
        models.append({'model': m, 'tasks': p['tasks'], 'rollouts': p['rollouts'], 'graded': p['graded'], 'passed': p['passed'],
                       'reward': (sum(pt) / len(pt)) if pt else None, 'error_rate': rate(p['errors'], p['rollouts']), 'tasks_graded': len(pt),
                       'tasks_0': sum(1 for v in pt if v == 0), 'tasks_100': sum(1 for v in pt if v == 1), 'tasks_20_80': sum(1 for v in pt if 0.2 <= v <= 0.8), 'per_task_rates': pt})
    show = []
    for t in [t for t in SAMPLES if t['catalog'] == cat]:
        r = {**t, **meta(t)}; mr = model_rows(t['id'])
        show.append({'url': URL[SID[t['name']]], 'task_id': SID[t['name']], 'turns': turn_stats(t['id']), 'name': t['name'], 'id': t['id'], 'version': RO[t['id']]['version'],
                     'earlier': t['sample'], 'final': r['final'], 'super_group': r['sg'], 'category': r['cat'], 'language': r['lang'], 'role': r['role'], 'seniority': r['sen'],
                     'models': [{'model': m, **o, 'reward': rate(o['score_sum'], o['graded'])} for m, o in sorted(mr.items(), key=lambda x: -x[1]['rollouts'])]})
    for s in [s for s in SUPER if s['catalog'] == cat]:  # super-samples: the copy's own version and runs, the original's classification
        o = {**BYID[s['original_id']], **meta(BYID[s['original_id']])}; rs = json.load(open(f"{H}/super/data/{s['client_id']}.json"))['rollouts']
        mr = collections.defaultdict(lambda: dict(rollouts=0, graded=0, passed=0, errors=0, score_sum=0.0)); by = collections.defaultdict(list)
        for q in rs:
            if q['model'] in DROPPED: continue
            x = mr[MM[q['model']]]; x['rollouts'] += 1
            if q.get('is_errored'): x['errors'] += 1; continue
            if q.get('turn_count') is not None: by[MM[q['model']]].append(q['turn_count'])
            if q.get('passed') is None: continue
            x['graded'] += 1; x['passed'] += bool(q['passed']); x['score_sum'] += q.get('extracted_score') or 0
        allt = [v for x in by.values() for v in x]
        show.append({'url': URL.get(s['client_id']), 'task_id': s['client_id'], 'name': s['horizon_name'], 'id': s['horizon_id'], 'version': s['version'], 'earlier': 'super',
                     'turns': {'runs': len(allt), 'mean': sum(allt) / len(allt), 'by_model': {m: sum(x) / len(x) for m, x in sorted(by.items(), key=lambda kv: -len(kv[1]))}} if allt else None,
                     'final': o['final'], 'super_group': o['sg'], 'category': o['cat'], 'language': o['lang'], 'role': o['role'], 'seniority': o['sen'],
                     'models': [{'model': m, **x, 'reward': rate(x['score_sum'], x['graded'])} for m, x in sorted(mr.items(), key=lambda kv: -kv[1]['rollouts'])]})
    TS = [x for x in (turn_stats(r['id']) for r in R) if x]
    means = [x['mean'] for x in TS]
    tm = collections.defaultdict(lambda: [0, 0.0, 0, set()])
    for r in R:
        for x in TURNS[r['id']]:
            v = tm[MM[x['model']]]; v[0] += 1; v[1] += x['turn_count']; v[2] += x['turn_count'] >= LONG; v[3].add(r['id'])
    turns = {'tasks_with_turns': len(TS), 'runs': sum(x['runs'] for x in TS), 'mean_of_task_means': (sum(means) / len(means)) if means else None,
             'median_of_task_means': median(means), 'long_horizon_tasks': sum(1 for m in means if m >= LONG), 'threshold': LONG, 'task_means': means,
             'max_task_mean': max(means) if means else None, 'min_task_mean': min(means) if means else None,
             'by_model': [{'model': m, 'runs': v[0], 'tasks': len(v[3]), 'mean': v[1] / v[0], 'runs_200_plus': v[2]} for m, v in sorted(tm.items(), key=lambda x: -x[1][0])]}
    run_any = sum(1 for r in R if any(o['graded'] for o in model_rows(r['id']).values()))
    # one row per task for the interactive charts: folded domain, sub-domain, language, seniority,
    # each model's grader scores (graded runs) and turn totals (completed runs)
    trows = []
    for r in R:
        sc = collections.defaultdict(list)
        for q in RO[r['id']]['rollouts']:
            if q['model'] in DROPPED or q.get('is_errored') or q.get('passed') is None: continue
            sc[MM[q['model']]].append(round(q.get('extracted_score') or 0, 4))
        tu = collections.defaultdict(lambda: [0, 0])
        for x in TURNS[r['id']]: v = tu[MM[x['model']]]; v[0] += x['turn_count']; v[1] += 1
        trows.append({'sg': dg(r), 'cat': r['cat'], 'lang': r['lang'], 'sen': r['sen'], 'scores': dict(sc), 'turns': {m: v for m, v in tu.items()}})
    out[slug] = {'title': cat, 'name': cat, 'tasks': n, 'tasks_graded': run_any, 'min_tasks': MIN_TASKS, 'turns': turns, 'super_groups': len(dom), 'folded': fold, 'domain': dom,
                 'language': dist('lang'), 'role': dist('role'), 'seniority': dist('sen'), 'models': models, 'showcase': show, 'task_rows': trows}
    print(slug, n, 'graded', run_any, 'models', [(m['model'], m['rollouts'], m['tasks_graded']) for m in models][:5], 'turn tasks', len(TS), 'samples', len(show))
json.dump(out, open(f'{H}/cat/stats.json', 'w'), indent=1)
