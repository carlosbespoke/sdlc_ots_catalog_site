# Gemini-hard universe: tasks where Gemini 4 Argon's pass rate is (or is predicted to be) under 80%.
from common import *
import math, random, hashlib
CUT = 0.8
SL_OLD = shortlist()
rows = dedupe([r for r in green(load_rows()) if r['catalog']], SL_OLD)
SEL = selection(); SELN = {s['name']: s for s in SEL}; SELI = {s['id']: s for s in SEL}
FC = {o['Task']: o for o in full_catalogue()}
NEWC = json.load(open(f'{H}/cat/new_task_classes.json'))  # hand classification of tasks new in the 2 Nov sheet
names = {r['name'] for r in rows}; ids = {r['id'] for r in rows}
TASKS = []
for r in rows:
    TASKS.append({'id': r['id'], 'name': r['name'], 'catalog': r['catalog'], 'domain': r['sg'], 'category': r['cat'], 'language': r['lang'],
                  'batch': r['batch'], 'in_catalog': True, 'shortlist_no': (SELN.get(r['name']) or SELI.get(r['id']) or {}).get('no'), 'old_shortlist': SL_OLD.get(r['name'])})
# shortlisted tasks that are not in the 1,342-task catalog yet: keep them only if Argon has graded runs (their sheet pipeline gives the catalog)
for s in SEL:
    if s['id'] in ids or s['name'] in names: continue
    if ARGON not in mstats(s['id']): continue
    pipe = (FC.get(s['name']) or {}).get('Original pipeline') or ''
    nc = NEWC.get(s['name'], {})
    TASKS.append({'id': s['id'], 'name': s['name'], 'catalog': 'System design' if pipe.lower() == 'system design' else None, 'domain': nc.get('sg', s['taxonomy']),
                  'category': nc.get('cat', s['taxonomy']), 'language': nc.get('lang'), 'batch': None, 'in_catalog': False, 'shortlist_no': s['no'], 'old_shortlist': None})
TASKS = [t for t in TASKS if t['catalog']]
for t in TASKS:
    t['models'] = mstats(t['id'])
    a = t['models'].get(ARGON); t['argon'] = a and {'graded': a[0], 'passed': a[1], 'rate': a[1] / a[0], 'score': a[2]}
def bucket(m, key):
    v = m.get(key)
    if not v: return 'none'
    r = v[1] / v[0]
    return '0' if r == 0 else '<.5' if r < .5 else '>=.5'
# naive-Bayes odds from the tasks Argon has run: catalog prior x GLM-5.3 Flash evidence x Gemini 3.8 Flash evidence
RUN = [t for t in TASKS if t['argon']]
hard = lambda t: t['argon']['rate'] < CUT
def lr(key):
    c = collections.Counter((bucket(t['models'], key), hard(t)) for t in RUN)
    nh = sum(hard(t) for t in RUN); ne = len(RUN) - nh; B4 = ('0', '<.5', '>=.5', 'none')
    return {b: ((c[(b, True)] + 1) / (nh + 4)) / ((c[(b, False)] + 1) / (ne + 4)) for b in B4}
LR = {k: lr(k) for k in (GLMF, FLASH)}
PRIOR = {}
for slug, cat in CATS:
    R = [t for t in RUN if t['catalog'] == cat]
    if R: PRIOR[cat] = (sum(hard(t) for t in R) + 1) / (len(R) + 2)
for t in TASKS:
    p = PRIOR.get(t['catalog'])
    if p is None: t['p_hard'] = None; continue
    o = p / (1 - p) * LR[GLMF][bucket(t['models'], GLMF)] * LR[FLASH][bucket(t['models'], FLASH)]
    t['p_hard'] = o / (1 + o)
    t['evidence'] = sum(v[0] for v in t['models'].values())
# portfolio estimate: each catalog's Argon share under 80% applied to its size (catalog tasks only)
def wilson(k, n, z=1.96):
    if not n: return (0, 1)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)
EST = []
for slug, cat in CATS:
    C = [t for t in TASKS if t['catalog'] == cat and t['in_catalog']]
    if not C: continue
    R = [t for t in C if t['argon']]; k = sum(hard(t) for t in R); n = len(R)
    lo, hi = wilson(k, n)
    EST.append({'slug': slug, 'catalog': cat, 'tasks': len(C), 'argon_tasks': n, 'argon_hard': k, 'share': k / n if n else None,
                'estimate': len(C) * k / n if n else None, 'lo': len(C) * lo, 'hi': len(C) * hi,
                'model_estimate': sum(1 if (t['argon'] and hard(t)) else 0 if t['argon'] else t['p_hard'] for t in C)})
# universe: every task proven hard, plus every task with run evidence whose predicted chance of being hard is at least even
FAIR = 0.5
proven = [t for t in TASKS if t['argon'] and hard(t)]
for t in TASKS: t['status'] = 'proven' if t in proven else 'cleared' if t['argon'] else None
predicted = [t for t in TASKS if not t['argon'] and t.get('evidence') and t['p_hard'] is not None and t['p_hard'] >= FAIR]
for t in predicted: t['status'] = 'predicted'
UNI = proven + predicted
TARGET = len(UNI); tot = sum(e['estimate'] for e in EST)
pool = {e['catalog']: [t for t in TASKS if t['catalog'] == e['catalog'] and not t['argon'] and t.get('evidence')] for e in EST}
for e in EST:
    e['universe'] = sum(1 for t in UNI if t['catalog'] == e['catalog']); e['proven'] = sum(1 for t in proven if t['catalog'] == e['catalog'])
    e['predicted'] = e['universe'] - e['proven']
extra = [t for t in proven if not t['in_catalog']]
json.dump({'cut': CUT, 'target': TARGET, 'lr': LR, 'prior': PRIOR, 'estimate': EST, 'extra_proven': len(extra),
           'tasks': [{k: v for k, v in t.items()} for t in TASKS]}, open(f'{H}/universe.json', 'w'), indent=1, default=str)
print('argon-run tasks', len(RUN), 'hard', sum(map(hard, RUN)), 'proven', len(proven), 'extra (not in catalog)', len(extra))
print('LR', {k: {b: round(v, 2) for b, v in d.items()} for k, d in LR.items()})
print('prior', {k: round(v, 2) for k, v in PRIOR.items()})
for e in EST: print(f"{e['catalog'][:22]:22} N={e['tasks']:4} argon {e['argon_hard']}/{e['argon_tasks']} est {e['estimate']:.0f} [{e['lo']:.0f}-{e['hi']:.0f}] model {e['model_estimate']:.0f} | universe {e['universe']} = {e['proven']} proven + {e['predicted']} predicted (pool {len(pool[e['catalog']])})")
print('total est', round(tot), 'model', round(sum(e['model_estimate'] for e in EST)), 'universe', len(UNI))
print('predicted p_hard range', min(t['p_hard'] for t in predicted), max(t['p_hard'] for t in predicted))
print('unrun tasks without any runs', collections.Counter(t['catalog'] for t in TASKS if not t['argon'] and not t.get('evidence')))
# samples, shortlisted universe tasks only ("Updated selection 120" tab)
def gem(t):
    g = sum(t['models'].get(m, [0, 0])[0] for m in (ARGON, FLASH)); p = sum(t['models'].get(m, [0, 0])[1] for m in (ARGON, FLASH))
    return g, p
def solved(t): return any(v[1] for m, v in t['models'].items() if m not in (ARGON, FLASH))
for t in TASKS:
    g, p = gem(t); t['gemini_graded'], t['gemini_passed'] = g, p; t['gemini_rate'] = p / g if g else None; t['solved_by_other'] = solved(t)
# tasks kept out of the samples by reviewer decision (they stay in the selection)
NOT_SAMPLE = {'mangle-8edad8d3-blind30': 'prompt judged unsuitable as a sample (2 Nov review)'}
SHORT = [t for t in UNI if t['shortlist_no'] and t['name'] not in NOT_SAMPLE]
# super samples: in the catalog, run by Argon, Gemini pooled pass rate 25% or less over 4+ Gemini runs; one per catalog
sup, seen = [], set()
for t in sorted([t for t in SHORT if t['in_catalog'] and t['argon'] and t['gemini_graded'] >= 4 and t['gemini_rate'] <= 0.25],
                key=lambda t: (t['gemini_rate'], -t['gemini_graded'])):
    if t['catalog'] not in seen and len(sup) < 3: sup.append(t); seen.add(t['catalog'])
# samples on each catalog page: up to 3, at least one per task group, all run by Argon and in the selection.
# The strongest sample above anchors its page; each task group without a sample gets its lowest-pass-rate candidate
# (shortlisted, or from the original catalog's shortlist when the group has no shortlisted task); remaining slots go to
# shortlisted tasks at 50% or less, lowest Gemini pass rate first.
PAGE = {'Migration': 'ProgramBench', 'Infrastructure as code': 'System design', 'Data engineering': 'Feature implementation'}
page = lambda c: PAGE.get(c, c)
rank = lambda t: (t['gemini_rate'], -t['gemini_graded'], not t['in_catalog'], t['shortlist_no'] or t['old_shortlist'] or 999)
def cand(g):
    c = [t for t in SHORT if t['catalog'] == g and t['argon']]
    return c or [t for t in UNI if t['catalog'] == g and t['argon'] and t['old_shortlist'] and t['name'] not in NOT_SAMPLE]
# per-page override of the one-per-task-group rule (reviewer decision): System design & IaC samples come from System design only
SAMPLE_GROUPS = {'System design': ['System design']}
chosen = {}
for slug, cat in CATS:
    if cat in PAGE: continue
    groups = SAMPLE_GROUPS.get(cat) or [c for _, c in CATS if page(c) == cat]
    pick = [t for t in sup if page(t['catalog']) == cat]
    for g in groups:
        if not any(t['catalog'] == g for t in pick) and cand(g): pick.append(min(cand(g), key=rank))
    for t in sorted([t for g in groups for t in SHORT if t['catalog'] == g and t['argon'] and t['gemini_rate'] <= 0.5 and t not in pick], key=rank):
        if len(pick) >= 3: break
        pick.append(t)
    for i, t in enumerate(pick[:3]): chosen[t['id']] = i
for t in TASKS: t['sample'] = 'main' if t['id'] in chosen else ''; t['sample_order'] = chosen.get(t['id'])
# attached samples (sent alongside, not written up on the pages): 10 tasks from the shortlist with Argon runs that are not
# main samples, Gemini-hard tasks first, then lowest Argon pass rate, more Argon runs, shortlist order
import csv
ATT_N = 10
att_pool = [t for t in TASKS if t['shortlist_no'] and t['argon'] and not t['sample'] and t['name'] not in NOT_SAMPLE]
for i, t in enumerate(sorted(att_pool, key=lambda t: (t not in UNI, t['argon']['rate'], -t['argon']['graded'], t['shortlist_no']))[:ATT_N]):
    t['sample'] = 'attached'; t['sample_order'] = i
att = [t for t in TASKS if t['sample']]
# every sample, main and attached, with what is needed to send it
with open(f'{H}/samples.csv', 'w', newline='') as f:
    w = csv.writer(f)
    SID = {k: v for k, v in json.load(open(f'{H}/cat/sample_ids.json')).items() if not k.startswith('_')}
    URLS = {k: f'https://drive.google.com/file/d/{v[0]}/view' for k, v in json.load(open(f'{H}/cat/sample_urls.json')).items() if not k.startswith('_')}
    w.writerow(['Sample', 'Task id', 'Download URL', 'Horizon task name', 'Horizon task id', 'Selected version', 'Catalog page', 'Task group', 'In Gemini-hard selection', 'Shortlist no.',
                'Argon runs graded', 'Argon passes', 'Argon pass rate', 'Gemini 3.8 Flash runs graded', 'Gemini 3.8 Flash passes'])
    PAGES = [c for _, c in CATS if c not in PAGE]
    for t in sorted(att, key=lambda t: (t['sample'] != 'main', PAGES.index(page(t['catalog'])), t['sample_order'])):
        a_ = t['argon']; fl = t['models'].get(FLASH) or [None, None]
        w.writerow([t['sample'], SID[t['name']], URLS[SID[t['name']]], t['name'], t['id'], RO[t['id']]['version'], {'ProgramBench': 'ProgramBench and Migration', 'System design': 'System design & IaC'}.get(page(t['catalog']), page(t['catalog'])), t['catalog'], 'yes' if t in UNI else 'no (Argon at 80%)',
                    t['shortlist_no'] or f"original catalog shortlist {t['old_shortlist']}", a_['graded'], a_['passed'], f"{a_['rate']:.0%}", fl[0] or '', fl[1] if fl[0] else ''])
def tier(t):
    return 'Proven' if t['status'] == 'proven' else 'Likely'
import csv
with open(f'{H}/gemini_hard_universe.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Task', 'Horizon task id', 'Catalog', 'Domain', 'Category', 'Tier', 'Sample', 'Shortlist no.', 'In 1,342 catalog',
                'Argon runs graded', 'Argon passes', 'Argon pass rate', 'Gemini 3.8 Flash runs graded', 'Gemini 3.8 Flash passes',
                'Predicted P(Argon < 80%)', 'Other models (passed/graded)'])
    order = {'main': 0, 'attached': 1, '': 2}; tord = {'Proven': 0, 'Likely': 1, 'Possible': 2}
    for t in sorted(UNI, key=lambda t: ([c for _, c in CATS].index(t['catalog']), order[t['sample']], tord[tier(t)], -(t['p_hard'] or 0), t['name'])):
        a = t['argon'] or {}; fl = t['models'].get(FLASH) or [None, None]
        w.writerow([t['name'], t['id'], t['catalog'], t['domain'], t['category'], tier(t), t['sample'], t['shortlist_no'] or '', 'yes' if t['in_catalog'] else 'no',
                    a.get('graded', ''), a.get('passed', ''), f"{a['rate']:.0%}" if a else '', fl[0] or '', fl[1] if fl[0] else '',
                    '' if t['status'] == 'proven' else f"{t['p_hard']:.2f}",
                    '; '.join(f'{m}: {v[1]}/{v[0]}' for m, v in sorted(t['models'].items()) if m not in (ARGON, FLASH, DROPPED))])
for t in TASKS: t['tier'] = tier(t) if t in UNI else ''
json.dump({'cut': CUT, 'target': TARGET, 'lr': LR, 'prior': PRIOR, 'estimate': EST, 'extra_proven': len(extra),
           'tasks': TASKS}, open(f'{H}/universe.json', 'w'), indent=1, default=str)
print('samples', sorted((page(t['catalog']), t['sample_order'], t['name'], t['catalog'], f"{t['gemini_passed']}/{t['gemini_graded']}") for t in att))
print('tiers', collections.Counter(tier(t) for t in UNI), 'expected hard', round(len(proven) + sum(t['p_hard'] for t in predicted)))
