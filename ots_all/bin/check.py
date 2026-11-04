# Recompute every number on the pages and in the CSVs straight from the snapshot (ro/ runs, turns/ turn counts), check each sample
# (field table, prompt, diagram, overview row, samples.csv), and check the writing rules. Exits 1 on any mismatch.
import csv, hashlib, html, statistics
from common import *
C = f'{H}/catalog'; errors, checked = [], collections.Counter()
NEWC = json.load(open(f'{H}/cat/new_task_classes.json')); SID = json.load(open(f'{H}/cat/sample_ids.json'))
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
def eq(what, got, want):
    checked[what.split(':')[0]] += 1
    if str(got) != str(want): errors.append(f'{what}: page says {got!r}, snapshot gives {want!r}')
def section(md, title):
    m = re.search(rf'^## {re.escape(title)}\n(.*?)(?=^## |\Z)', md, re.S | re.M); return m.group(1) if m else ''
def rows(block, first=''):
    return [[c.strip() for c in l.strip().strip('|').split('|')] for l in block.splitlines() if l.startswith(f'| {first}') and not l.startswith('|---')]
def kpis(md): return dict((b, html.unescape(a)) for a, b in re.findall(r'kpi-value">([^<]+)</div><div class="kpi-label">([^<]+)<', md))
def per_model(tasks):
    """model -> [graded, passed, per-task rates, rollouts]"""
    out = collections.defaultdict(lambda: [0, 0, [], 0])
    for t in tasks:
        for q in RO[t['id']]['rollouts']:
            if q['model'] not in DROPPED: out[MM[q['model']]][3] += 1
        for m, v in runs(t['id']).items():
            o = out[m]; o[0] += len(v); o[1] += sum(x for x, _ in v); o[2].append(sum(x for x, _ in v) / len(v))
    return out
Q = lambda a, b: f"{100 * a / b:.0f}%"
total = len(TASKS)
for slug, cat in CATS:
    md = open(f'{C}/{slug}.md').read(); T = [t for t in TASKS if t['catalog'] == cat]; PM = per_model(T)
    K = kpis(section(md, 'Executive summary'))
    eq(f'tasks card: {slug}', K.get('Tasks'), f'{len(T):,}')
    eq(f'graded card: {slug}', K.get('Tasks with graded runs'), f"{sum(1 for t in T if runs(t['id'])):,}")
    topm = max((m for m in PM if PM[m][0]), key=lambda m: PM[m][3])
    eq(f'headline: {slug}', K.get(f'{topm} pass rate'), pct(PM[topm][1] / PM[topm][0]))
    tab = {r[0]: r for r in rows(section(md, 'Model pass rates across the catalog')) if r[0] != 'Model'}
    for m, (g, p, per, _) in PM.items():
        if len(per) >= 5:
            eq(f'model table: {slug} {m}', tab.get(m, [None])[1:], [f'{len(per):,}', f'{g:,}', pct(p / g), Q(sum(v == 0 for v in per), len(per)), Q(sum(0.2 <= v <= 0.8 for v in per), len(per)), Q(sum(v == 1 for v in per), len(per))])
        else: eq(f'model table: {slug} {m} absent', m in tab, False)
    # turn counts over every model's completed runs
    tm = [statistics.mean(r['turn_count'] for r in TURNS[t['id']]) for t in T if TURNS[t['id']]]
    M = {r[0]: r[1] for r in rows(section(md, 'Turn counts and long-horizon tasks')) if len(r) == 2}
    eq(f'turns: {slug} average', M.get('Average turn count'), f'{statistics.mean(tm):.1f}')
    eq(f'turns: {slug} median', M.get('Median turn count'), f'{statistics.median(tm):.1f}')
    eq(f'turns: {slug} long horizon', M.get('Long-horizon tasks (200+ turns)'), f'{100 * sum(x >= 200 for x in tm) / len(tm):.0f}% of tasks')
    # samples
    blocks = re.split(r'^### Example ', md, flags=re.M)[1:]
    want = sorted([t for t in TASKS if t.get('sample') in ('main', 'attached') and t['catalog'] == cat], key=lambda t: (t['sample'] != 'main', t['sample_order']))
    eq(f'sample count: {slug}', len(blocks), len(want))
    for i, (blk, t) in enumerate(zip(blocks, want), 1):
        sid = SID[t['name']]
        F = dict(re.findall(r'^\| (Task id|Final category|Domain|Sub-domain|Language|Seniority) \| (.*?) \|$', blk, re.M))
        r = ROWS.get(t['id']); c = NEWC.get(t['name'], {})
        eq(f'field table: {slug} {i}', (F.get('Task id', '').split('`')[1:2], F.get('Sub-domain'), F.get('Language')), ([sid], r['cat'] if r else c['cat'], r['lang'] if r else c['lang']))
        pr = {x[0]: x[1:] for x in rows(blk.split('#### Pass rates')[1].split('####')[0]) if x[0] != 'Model'}
        eq(f'sample pass rates: {slug} {i}', sorted(pr.items()), sorted((m, [str(len(v)), pct(sum(x for x, _ in v) / len(v))]) for m, v in runs(t['id']).items()))
        tl = re.search(r'^\| Turn count \| (.*) \|$', blk, re.M).group(1); bt = collections.defaultdict(list)
        for q in TURNS[t['id']]: bt[MM[q['model']]].append(q['turn_count'])
        eq(f'sample turns: {slug} {i}', sorted(tl.split(', ')), sorted(f'{statistics.mean(x):.0f} ({m})' for m, x in bt.items()) if bt else ['no completed run'])
        pm = re.search(r'<div class="prompt-md">\n\n(.*?)\n\n</div>', blk, re.S).group(1)
        src = next(open(p).read() for p in (f"{G}/audit/instr/{t['id']}.md", f"{G}/samples/{t['sample']}/{sid}/instruction.md") if os.path.exists(p) and os.path.getsize(p))
        words = lambda z: re.findall(r'[A-Za-z0-9]{3,}', z)
        eq(f'prompt: {slug} {i}', words(pm)[:80] == words(src)[:80] and abs(len(words(pm)) - len(words(src))) <= 3, True)
        img = re.search(r'!\[How the task works\]\(assets/([^)]+)\)', blk)
        d = f'{G}/diagrams/{sid}/diagram.svg'
        if not os.path.exists(d): errors.append(f'diagram: {slug} {i} {sid} not drawn yet'); continue
        eq(f'diagram: {slug} {i}', img and hashlib.md5(open(f'{C}/assets/{img.group(1)}', 'rb').read()).digest() == hashlib.md5(open(d, 'rb').read()).digest(), True)
# overview
md = open(f'{C}/README.md').read(); K = kpis(md); PM = per_model(TASKS)
eq('overview card: tasks', K.get('Tasks'), f'{total:,}')
eq('overview card: graded runs', K.get('Graded runs'), f"{sum(v[0] for v in PM.values()):,}")
for r in rows(md, '['):
    slug = re.search(r'\(([\w-]+)\.md\)', r[0]).group(1); cat = dict(CATS)[slug]; T = [t for t in TASKS if t['catalog'] == cat]
    tm = [statistics.mean(x['turn_count'] for x in TURNS[t['id']]) for t in T if TURNS[t['id']]]
    eq(f'overview table: {slug}', [r[1], r[3], r[4], r[5]], [f'{len(T):,}', f'{100 * len(T) / total:.1f}%', f"{sum(1 for t in T if runs(t['id'])):,}", f'{statistics.mean(tm):.0f}'])
for r in rows(section(md, 'Model pass rates')):
    if r[0] in PM: eq(f'overview models: {r[0]}', r[3], pct(PM[r[0]][1] / PM[r[0]][0]))
SM = rows(section(md, 'Samples')); SM = [r for r in SM if r[0] != 'Catalog']
eq('overview samples', len(SM), 22)
SL = list(csv.DictReader(open(f'{H}/samples.csv')))
eq('samples.csv', sorted((r['Horizon task id'], r['Task id']) for r in SL), sorted((t['id'], SID[t['name']]) for t in TASKS if t.get('sample') in ('main', 'attached')))
for r in SL: eq(f"samples.csv version: {r['Task id']}", r['Selected version'], RO[r['Horizon task id']]['version'])
# CSV
TC = list(csv.DictReader(open(f'{H}/ots_tasks.csv')))
eq('csv: task set', sorted(r['Horizon task id'] for r in TC), sorted(t['id'] for t in TASKS))
for r in TC:
    rr = runs(r['Horizon task id']); eq(f"csv: {r['Task']}", [r['Graded runs'], r['Passes']], [str(sum(map(len, rr.values()))), str(sum(x for v in rr.values() for x, _ in v))])
# writing rules, on everything but the agents' prompts
names = sorted({t['name'] for t in TASKS if len(t['name']) > 6}, key=len, reverse=True)
for f in sorted(os.listdir(C)):
    if not f.endswith('.md'): continue
    prose = re.sub(r'<div class="prompt-md">.*?</div>', '', open(f'{C}/{f}').read(), flags=re.S)
    prose = re.sub(r'\]\([^)]*\)', ']', re.sub(r'`[^`]*`', '', prose))  # client-facing sample ids are code spans; link targets are not prose
    for bad, why in [('—', 'em dash'), ('–', 'en dash'), ('How it maps', 'maps-to-work paragraph'), ('shortlist', 'shortlist wording')]:
        checked['rules'] += 1
        if bad in prose: errors.append(f'{f}: {why}')
    for k in sorted({MM[c] for c in DROPPED}):
        checked['rules'] += 1
        if k in prose or k.split('/')[-1] in prose: errors.append(f'{f}: dropped model {k}')
    for k in ('helm', 'granola-plus', 'starfall', 'steppe', 'kittiwake', 'umbra', 'astrolabe', 'lumen-pro', 'meridian', 'forge', 'startrail', 'cipher-omni', 'cipher-prime', 'crossbill', 'ecliptic'):
        if re.search(rf'(?<![\w-]){k}(?![\w-])', prose): errors.append(f'{f}: model codename {k}')
    hit = [n for n in names if n in prose]
    if hit: errors.append(f'{f}: task names in prose {hit[:5]}')
print('snapshot', SNAPSHOT, '| checks by kind:', dict(checked))
print('\n'.join(errors[:60]) if errors else 'all numbers match the snapshot; samples and writing rules check out')
sys.exit(1 if errors else 0)
