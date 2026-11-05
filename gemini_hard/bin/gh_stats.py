# Catalog statistics for the Gemini-hard selection, in the same shape as the catalog pipeline's cat/stats.json, Gemini models only.
from common import *
U = json.load(open(f'{H}/universe.json')); EST = {e['catalog']: e for e in U['estimate']}
SEL = [t for t in U['tasks'] if t.get('tier')]
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
GEM = {k: v for k, v in MM.items() if 'gemini' in v and v != DROPPED}  # 3.7 Flash is left out of the report
CANON = {k: next(c for c, w in GEM.items() if w == v) for k, v in GEM.items()}
LONG = 200
MIN_TASKS = 5  # a model gets a row in a page's pass-rate table once it has graded runs on this many tasks
AFFINITY = {'Distributed systems & coordination': 'Applications & business domains', 'Observability & reliability': 'Cloud infrastructure & IaC',
            'Security': 'Systems, hardware & accelerators', 'Build, release & supply chain': 'Languages & developer tooling',
            'Cloud infrastructure & IaC': 'Languages & developer tooling', 'Data engineering & databases': 'Scientific & ML software',
            'Scientific & ML software': 'Data engineering & databases', 'Applications & business domains': 'Languages & developer tooling',
            'Languages & developer tooling': 'Applications & business domains', 'Systems, hardware & accelerators': 'Languages & developer tooling'}
NEW = 'Not yet classified'
NEWC = json.load(open(f'{H}/cat/new_task_classes.json'))
SID = json.load(open(f'{H}/cat/sample_ids.json'))  # client-facing task ids of the samples
URL = {k: f'https://drive.google.com/file/d/{v[0]}/view' for k, v in json.load(open(f'{H}/cat/sample_urls.json')).items() if not k.startswith('_')}  # Drive copies of the sample zips
# smaller task groups are presented inside a larger catalog, as one domain of its domain breakdown
MERGE = {'Migration': 'ProgramBench', 'Infrastructure as code': 'System design', 'Data engineering': 'Feature implementation'}
GROUP_DOMAIN = {'Migration': 'Cross-language migration', 'Infrastructure as code': 'State-preserving infrastructure changes', 'Data engineering': 'Data pipelines'}
dest = lambda c: MERGE.get(c, c)
DISPLAY = {'ProgramBench': 'ProgramBench and Migration', 'System design': 'System design & IaC'}  # catalog names once the groups are merged
LANG_NEW = {'pdk-harbor-scan-ephemeral-credentials': 'Go', 'pdk-bagetter-fenced-package-writes': 'C#', 'pdk-dittofeed-user-deletion-in-flight': 'TypeScript'}  # from each task's base image
def meta(t):
    r = ROWS.get(t['id'])
    if r: return {'sg': r['sg'], 'cat': r['cat'], 'lang': r['lang'], 'sen': r['sen'].replace('\u2013', '-'), 'role': r['role'], 'final': r['final']}
    c = NEWC.get(t['name'])
    if c: return {'sg': c['sg'], 'cat': c['cat'], 'lang': c['lang'], 'sen': c['sen'], 'role': c['role'], 'final': t['catalog']}
    return {'sg': NEW, 'cat': t['category'].split(' / ')[-1], 'lang': LANG_NEW.get(t['name'], NEW), 'sen': NEW, 'role': NEW, 'final': t['catalog']}
TURNS = {f[:-5]: [r for r in json.load(open(f'{H}/turns/{f}'))['runs'] if r['model'] in GEM] for f in os.listdir(f'{H}/turns')}
def turn_stats(tid):
    runs = TURNS.get(tid) or []
    if not runs: return None
    v = [r['turn_count'] for r in runs]; by = collections.defaultdict(list)
    for r in runs: by[CANON[r['model']]].append(r['turn_count'])
    return {'runs': len(v), 'mean': sum(v) / len(v), 'min': min(v), 'max': max(v), 'by_model': {m: sum(x) / len(x) for m, x in by.items()}}
def median(v):
    v = sorted(v); n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)
def model_rows(tid):
    out = collections.defaultdict(lambda: dict(rollouts=0, graded=0, passed=0, errors=0, score_sum=0.0))
    for q in RO.get(tid, {}).get('rollouts', []):
        if q['model'] not in GEM: continue
        o = out[CANON[q['model']]]; o['rollouts'] += 1
        if q.get('is_errored'): o['errors'] += 1; continue
        if q.get('passed') is None: continue
        o['graded'] += 1; o['passed'] += bool(q['passed']); o['score_sum'] += q.get('extracted_score') or 0
    return {m: o for m, o in out.items() if o['rollouts']}
def rate(a, b): return None if not b else a / b
out = {}
import math
def combine(parts):
    """Estimate for a catalog made of task groups: each group's Argon share scales that group; 95% interval from the summed variances (finite-population corrected)."""
    N = sum(e['tasks'] for e in parts); n = sum(e['argon_tasks'] for e in parts); k = sum(e['argon_hard'] for e in parts)
    est = sum(e['estimate'] for e in parts); var = 0
    for e in parts:
        p_ = e['argon_hard'] / e['argon_tasks']
        if e['tasks'] > 1: var += e['tasks'] ** 2 * p_ * (1 - p_) / e['argon_tasks'] * (e['tasks'] - e['argon_tasks']) / (e['tasks'] - 1)
    h = 1.96 * math.sqrt(var)
    return {'tasks': N, 'argon_tasks': n, 'argon_hard': k, 'share': k / n, 'estimate': est, 'lo': max(k, est - h), 'hi': min(N - (n - k), est + h),
            'groups': [e['catalog'] for e in parts]}
for slug, cat in CATS:
    if cat in MERGE: continue
    groups = [c for _, c in CATS if dest(c) == cat]
    R = [{**t, **meta(t), 'group': t['catalog']} for t in SEL if dest(t['catalog']) == cat]
    for r in R:
        if r['group'] != cat: r['sg'] = GROUP_DOMAIN[r['group']]
    if not R: continue
    n = len(R)
    dist = lambda key: [{'value': k, 'tasks': v, 'pct': round(100 * v / n, 1)} for k, v in collections.Counter(r[key] for r in R).most_common()]
    size = collections.Counter(r['sg'] for r in R); big = size.most_common(1)[0][0]; fold = {}
    for sg, k in size.items():
        if 100 * k / n < 1 and sg not in GROUP_DOMAIN.values():
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
            if o['graded']: p['per_task'].append(o['passed'] / o['graded'])
    models = []
    for m, p in sorted(pm.items(), key=lambda x: (MM[x[0]] != 'google/gemini-4-argon', -x[1]['rollouts'])):
        pt = p['per_task']
        models.append({'codename': m, 'model': MM[m], 'tasks': p['tasks'], 'rollouts': p['rollouts'], 'graded': p['graded'], 'passed': p['passed'],
                       'pass_rate': rate(p['passed'], p['graded']), 'error_rate': rate(p['errors'], p['rollouts']), 'tasks_graded': len(pt),
                       'tasks_0': sum(1 for v in pt if v == 0), 'tasks_100': sum(1 for v in pt if v == 1), 'tasks_20_80': sum(1 for v in pt if 0.2 <= v <= 0.8), 'per_task_rates': pt})
    order = {'super': 0, 'attached': 1}
    show = []
    for r in sorted([r for r in R if r.get('sample') == 'main'], key=lambda r: r['sample_order']):
        mr = model_rows(r['id'])
        show.append({'url': URL[SID[r['name']]], 'task_id': SID[r['name']], 'turns': turn_stats(r['id']), 'name': r['name'], 'group': r['group'], 'id': r['id'], 'rank': r['shortlist_no'], 'sample': r['sample'], 'tier': r['tier'],
                     'final': r['final'], 'super_group': r['sg'], 'category': r['cat'], 'language': r['lang'], 'role': r['role'], 'seniority': r['sen'],
                     'solved_by_other': r['solved_by_other'], 'in_catalog': r['in_catalog'],
                     'models': [{'codename': m, 'model': MM[m], **o, 'pass_rate': rate(o['passed'], o['graded']), 'error_rate': rate(o['errors'], o['rollouts']),
                                 'avg_score': (o['score_sum'] / o['graded']) if o['graded'] else None} for m, o in sorted(mr.items(), key=lambda x: MM[x[0]] != 'google/gemini-4-argon')]})
    TS = [(r, turn_stats(r['id'])) for r in R]; TS = [(r, t) for r, t in TS if t]
    means = [t['mean'] for _, t in TS]
    tm = collections.defaultdict(lambda: [0, 0.0, 0, set()])
    for r in R:
        for x in TURNS.get(r['id']) or []:
            v = tm[CANON[x['model']]]; v[0] += 1; v[1] += x['turn_count']; v[2] += x['turn_count'] >= LONG; v[3].add(r['id'])
    turns = {'tasks_with_turns': len(TS), 'runs': sum(t['runs'] for _, t in TS), 'mean_of_task_means': (sum(means) / len(means)) if means else None,
             'median_of_task_means': median(means), 'long_horizon_tasks': sum(1 for m in means if m >= LONG), 'threshold': LONG, 'task_means': means,
             'max_task_mean': max(means) if means else None, 'min_task_mean': min(means) if means else None,
             'by_model': [{'codename': m, 'model': MM[m], 'runs': v[0], 'tasks': len(v[3]), 'mean': v[1] / v[0], 'runs_200_plus': v[2]} for m, v in sorted(tm.items(), key=lambda x: -x[1][0])]}
    # one row per task for the interactive charts (bin/charts.js): folded domain, sub-domain, language, seniority,
    # each Gemini model's graded runs as 1 (passed) or 0, and its turn total and count over completed runs
    trows = []
    for r in R:
        sc = collections.defaultdict(list)
        for q in RO.get(r['id'], {}).get('rollouts', []):
            if q['model'] not in GEM or q.get('is_errored') or q.get('passed') is None: continue
            sc[MM[q['model']]].append(int(bool(q['passed'])))
        tu = collections.defaultdict(lambda: [0, 0])
        for x in TURNS.get(r['id']) or []: v = tu[MM[x['model']]]; v[0] += x['turn_count']; v[1] += 1
        trows.append({'sg': dg(r), 'cat': r['cat'], 'lang': r['lang'], 'sen': r['sen'], 'scores': dict(sc), 'turns': dict(tu)})
    e = combine([EST[g] for g in groups])
    argon_all = [t['argon']['rate'] for t in U['tasks'] if dest(t['catalog']) == cat and t['in_catalog'] and t['argon']]
    # attached samples for this page (any task on the shortlist, selected or not): shown only in the overview's samples table
    attached = []
    for t in sorted([t for t in U['tasks'] if t.get('sample') == 'attached' and dest(t['catalog']) == cat], key=lambda t: t['sample_order']):
        m = meta(t); mr = model_rows(t['id'])
        attached.append({'url': URL[SID[t['name']]], 'task_id': SID[t['name']], 'name': t['name'], 'id': t['id'], 'group': t['catalog'], 'category': m['cat'], 'language': m['lang'], 'in_selection': bool(t.get('tier')),
                         'models': {MM[k]: {'graded': o['graded'], 'passed': o['passed'], 'pass_rate': rate(o['passed'], o['graded'])} for k, o in mr.items()}})
    out[slug] = {'attached': attached, 'title': cat, 'name': DISPLAY.get(cat, cat), 'tasks': n, 'groups': {g: sum(1 for r in R if r['group'] == g) for g in groups}, 'group_domain': {g: GROUP_DOMAIN[g] for g in groups if g in GROUP_DOMAIN}, 'tiers': dict(collections.Counter(r['tier'] for r in R)), 'not_in_catalog': sum(1 for r in R if not r['in_catalog']),
                 'estimate': e, 'argon_catalog_rates': argon_all, 'turns': turns, 'super_groups': len(dom), 'folded': fold, 'domain': dom,
                 'language': dist('lang'), 'role': dist('role'), 'seniority': dist('sen'), 'models': models, 'showcase': show, 'min_tasks': MIN_TASKS, 'task_rows': trows}
    print(slug, n, out[slug]['tiers'], 'models', [(m['model'], m['tasks_graded']) for m in models], 'turn tasks', len(TS), 'samples', len(show))
json.dump(out, open(f'{H}/cat/stats.json', 'w'), indent=1)
