# Recompute every number on the catalog pages and in the CSV straight from the snapshot (ro3/ runs, turns/ turn counts,
# universe.json for which tasks are selected) and compare with what the pages print. Exits 1 on any mismatch.
import csv, html, json, os, re, statistics, sys, collections
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); C = f'{H}/catalog'
MM = json.load(open('/Users/carlos/code/sdlc_final_samples/pipeline/ro_models.json'))
GEM = {k: v for k, v in MM.items() if 'gemini' in v and v != 'google/gemini-3.7-flash'}  # 3.7 Flash is left out of the report
RO = {f[:-5]: json.load(open(f'{H}/ro3/{f}')) for f in os.listdir(f'{H}/ro3')}
RO.update({f[:-5]: json.load(open(f'{H}/ro3_refresh/{f}')) for f in os.listdir(f'{H}/ro3_refresh')})  # runs refreshed after the snapshot
TU = {f[:-5]: [r for r in json.load(open(f'{H}/turns/{f}'))['runs'] if r['model'] in GEM] for f in os.listdir(f'{H}/turns')}
U = json.load(open(f'{H}/universe.json'))
SEL = [t for t in U['tasks'] if t.get('tier')]
# GLM-5.3 Flash: each selected task's runs as recorded in universe.json, each one checked against the raw run files
# (ro3/ for the task's own runs, origins/ for runs borrowed from the copied-from or reimplementation task)
GLMF = 'z-ai/glm-5.3-flash'
def _raw(tid, src):
    if src == 'own': return {q['id']: q for q in RO[tid]['rollouts']}
    return {q['id']: q for o in json.load(open(f'{H}/origins/{tid}.json'))['origins'] for q in o['rollouts']}
GLM, FLB = {}, {}
FLASHM = 'google/gemini-3.8-flash'
for t in SEL:
    for key, model, store in (('glm', GLMF, GLM), ('flash_borrowed', FLASHM, FLB)):
        if not t.get(key): continue
        raw = _raw(t['id'], t[key]['source'])
        for q in t[key]['runs']:
            x = raw.get(q['id'])
            if not x or MM.get(x['model']) != model or x.get('is_errored') or bool(x.get('passed')) != q['passed']: print('borrowed run not in raw files:', t['name'], q['id']); sys.exit(1)
        store[t['id']] = [q['passed'] for q in t[key]['runs']]
for f in os.listdir(f'{H}/turns_glm'):
    if f[:-5] in GLM or f[:-5] in FLB: TU.setdefault(f[:-5], []); TU[f[:-5]] = TU[f[:-5]] + json.load(open(f'{H}/turns_glm/{f}'))['runs']
NAME = {**GEM, **{k: v for k, v in MM.items() if v == GLMF}, GLMF: GLMF, FLASHM: FLASHM}
MERGE = {'Migration': 'ProgramBench', 'Infrastructure as code': 'System design', 'Data engineering': 'Feature implementation'}
PAGE = {'ProgramBench': 'programbench', 'System design': 'system-design', 'Diagnosis, Debugging, and Bug Fixing': 'debugging', 'Feature implementation': 'feature-implementation'}
page_of = lambda t: PAGE[MERGE.get(t['catalog'], t['catalog'])]
pct = lambda v: '<1%' if 0 < v < 0.005 else f'{100 * v:.0f}%'
errors, checked = [], collections.Counter()
def eq(what, got, want):
    checked[what.split(':')[0]] += 1
    if str(got) != str(want): errors.append(f'{what}: page says {got!r}, snapshot gives {want!r}')
def runs(tid, glm=True):
    """Model -> list of (passed, score) over graded runs: Gemini models from the raw run file, GLM-5.3 Flash from the checked runs above."""
    out = collections.defaultdict(list)
    if glm and tid in GLM: out[GLMF] = [(p, 0) for p in GLM[tid]]
    if glm and tid in FLB: out[FLASHM] = [(p, 0) for p in FLB[tid]]
    for q in RO[tid]['rollouts']:
        if q['model'] in GEM and not q.get('is_errored') and q.get('passed') is not None:
            out[GEM[q['model']]].append((bool(q['passed']), q.get('extracted_score') or 0))
    return out
def pooled(tasks, model):
    g = p = 0; per = []
    for t in tasks:
        r = runs(t['id']).get(model)
        if r: g += len(r); p += sum(x for x, _ in r); per.append(sum(x for x, _ in r) / len(r))
    return g, p, per
def turn_means(tasks):
    return {t['id']: statistics.mean(r['turn_count'] for r in TU[t['id']]) for t in tasks if TU.get(t['id'])}
def section(md, title):
    m = re.search(rf'^## {re.escape(title)}\n(.*?)(?=^## |\Z)', md, re.S | re.M); return m.group(1) if m else ''
def rows(block, first):
    return [[c.strip() for c in l.strip().strip('|').split('|')] for l in block.splitlines() if l.startswith(f'| {first}')]
# task counts: whole numbers per catalog from the estimate, adding up to the rounded total
EN = collections.defaultdict(float)
for e in U['estimate']: EN[PAGE[MERGE.get(e['catalog'], e['catalog'])]] += e['estimate']
total = round(sum(EN.values())); NUM = {k: int(v) for k, v in EN.items()}
for k in sorted(EN, key=lambda k: -(EN[k] - int(EN[k])))[:total - sum(NUM.values())]: NUM[k] += 1
for k in NUM: NUM[k] = max(NUM[k], sum(1 for t in SEL if page_of(t) == k))  # a page over its estimate shows the tasks it holds
total = sum(NUM.values())
CSV = list(csv.DictReader(open(f'{H}/gemini_hard_universe.csv')))
EX = {r['Catalog example']: r for r in CSV if r['Catalog example']}
for slug in PAGE.values():
    md = open(f'{C}/{slug}.md').read(); T = [t for t in SEL if page_of(t) == slug]
    ex = section(md, 'Executive summary'); K = dict((b, html.unescape(a)) for a, b in re.findall(r'kpi-value">([^<]+)</div><div class="kpi-label">([^<]+)<', ex))
    eq(f'tasks card: {slug}', K.get('Tasks'), f'{NUM[slug]:,}')
    for model, short in (('google/gemini-4-argon', 'Gemini 4 Argon'), ('google/gemini-3.8-flash', 'Gemini 3.8 Flash')):
        g, p, per = pooled(T, model)
        shown = len(per) >= 5
        eq(f'pass-rate card: {slug} {short}', K.get(f'{short} pass rate'), pct(p / g) if shown else None)
        tab = {r[0]: r for r in rows(section(md, 'Pass rates across the catalog'), 'google/') + rows(section(md, 'Pass rates across the catalog'), 'z-ai/')}
        if shown:
            r = tab.get(model) or [None] * 5
            eq(f'pass-rate table: {slug} {short}', r[1:5], [pct(p / g), pct(sum(v == 0 for v in per) / len(per)), pct(sum(0.2 <= v <= 0.8 for v in per) / len(per)), pct(sum(v == 1 for v in per) / len(per))])
            m = re.search(rf'{short} passes (<?\d+%) of its runs(?: and fails every run on (\d+%) of them)?', ex)
            eq(f'summary sentence: {slug} {short}', m and (m.group(1), m.group(2)), (pct(p / g), pct(sum(v == 0 for v in per) / len(per)) if any(v == 0 for v in per) else None))
        else: eq(f'pass-rate table: {slug} {short} hidden', model in tab, False)
    # turn counts over Gemini runs
    tm = turn_means(T); v = list(tm.values()); ts = section(md, 'Turn counts and long-horizon tasks')
    if v:
        M = {r[0]: r[1] for r in rows(ts, '') if len(r) == 2}
        eq(f'turns: {slug} average', M.get('Average turn count'), f'{statistics.mean(v):.1f}')
        eq(f'turns: {slug} median', M.get('Median turn count'), f'{statistics.median(v):.1f}')
        eq(f'turns: {slug} range', M.get('Range'), f'{min(v):.0f} to {max(v):.0f}')
        eq(f'turns: {slug} long horizon', M.get('Long-horizon tasks (200+ turns)'), f'{100 * sum(x >= 200 for x in v) / len(v):.0f}% of tasks')
        by = collections.defaultdict(list); tasks_by = collections.defaultdict(set)
        for t in T:
            for r in TU.get(t['id']) or []: by[NAME[r['model']]].append(r['turn_count']); tasks_by[NAME[r['model']]].add(t['id'])
        R = {r[0]: r for r in rows(ts, 'google/') + rows(ts, 'z-ai/')}
        for m_, x in by.items():
            k = len(tm); share = 100 * len(tasks_by[m_]) / k
            eq(f'turns: {slug} {m_}', R.get(m_, [None] * 4)[1:4], [f'{share:.0f}%' if share >= 0.5 else '<1%', f'{statistics.mean(x):.1f}', f'{100 * sum(y >= 200 for y in x) / len(x):.0f}%'])
    # examples
    for i, blk in enumerate(re.split(r'^### Example ', md, flags=re.M)[1:], 1):
        r = EX.get(f"{ {'programbench': 'ProgramBench and Migration', 'system-design': 'System design & IaC', 'debugging': 'Diagnosis, Debugging, and Bug Fixing', 'feature-implementation': 'Feature implementation'}[slug] }, Example {i}")
        if not r: errors.append(f'example {slug} {i}: no CSV row'); continue
        tid = r['Horizon task id']; rr = runs(tid, glm=False)
        want = [[m_, pct(sum(x for x, _ in v_) / len(v_))] for m_, v_ in sorted(rr.items(), key=lambda kv: kv[0] != 'google/gemini-4-argon')]
        got = [r_[:2] for r_ in rows(blk, 'google/') if len(r_) == 2]
        eq(f'example pass rates: {slug} {i}', got, want)
        tl = re.search(r'^\| Turn count \| (.*) \|$', blk, re.M).group(1)
        bt = collections.defaultdict(list)
        for q in TU.get(tid) or []:
            if q['model'] in GEM: bt[GEM[q['model']]].append(q['turn_count'])
        eq(f'example turns: {slug} {i}', sorted(tl.split(', ')), sorted(f'{statistics.mean(x):.0f} ({m_})' for m_, x in bt.items()) if bt else ['no completed run'])
# overview
md = open(f'{C}/README.md').read()
K = dict((b, html.unescape(a)) for a, b in re.findall(r'kpi-value">([^<]+)</div><div class="kpi-label">([^<]+)<', md))
eq('overview card: tasks', K.get('Tasks'), f'{total:,}')
for model, short in (('google/gemini-4-argon', 'Gemini 4 Argon'), ('google/gemini-3.8-flash', 'Gemini 3.8 Flash')):
    g, p, _ = pooled(SEL, model); eq(f'overview card: {short}', K.get(f'{short} pass rate'), pct(p / g))
for r in rows(md, '['):
    slug = re.search(r'\(([\w-]+)\.md\)', r[0]).group(1); T = [t for t in SEL if page_of(t) == slug]; tm = turn_means(T)
    eq(f'overview table: {slug}', [r[1], r[3], r[4]], [f'{NUM[slug]:,}', f'{100 * NUM[slug] / total:.1f}%', f'{statistics.mean(tm.values()):.0f}' if tm else 'n/a'])
for r in rows(section(md, 'Pass rates by catalog'), 'google/') + rows(section(md, 'Pass rates by catalog'), 'z-ai/'):
    g, p, _ = pooled(SEL, r[0]); eq(f'overview pass table: {r[0]}', r[1], pct(p / g) if g else 'n/a')
for r in rows(section(md, 'Samples'), 'Main'):
    n = int(re.search(r'Example (\d+)', r[2]).group(1)); row = EX[f'{r[1]}, Example {n}']; rr = runs(row['Horizon task id'], glm=False)
    eq(f'overview samples: {r[1]} {n}', r[4:6], [pct(sum(x for x, _ in rr[m]) / len(rr[m])) if rr.get(m) else '' for m in ('google/gemini-4-argon', 'google/gemini-3.8-flash')])
# CSV
ids = {t['id'] for t in SEL}
eq('csv: task set', sorted(r['Horizon task id'] for r in CSV), sorted(ids))
for r in CSV:
    rr = runs(r['Horizon task id'], glm=False); a = rr.get('google/gemini-4-argon'); f = rr.get('google/gemini-3.8-flash')
    eq(f"csv: {r['Task']} argon", [r['Argon runs graded'], r['Argon passes']], [str(len(a)), str(sum(x for x, _ in a))] if a else ['', ''])
    eq(f"csv: {r['Task']} flash", [r['Gemini 3.8 Flash runs graded'], r['Gemini 3.8 Flash passes']], [str(len(f)), str(sum(x for x, _ in f))] if f else ['', ''])
print('snapshot', open(f'{H}/SNAPSHOT').read().strip(), '| checks by kind:', dict(checked))
print('\n'.join(errors[:40]) if errors else 'all numbers match the snapshot')
sys.exit(1 if errors else 0)
