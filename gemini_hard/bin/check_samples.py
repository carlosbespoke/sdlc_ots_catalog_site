# Check every sample on the catalog pages against its own task: heading, field table, prompt, write-up, diagram,
# overview row and CSV row; and that no page still refers to a task that is no longer a sample. Exits 1 on any mismatch.
import csv, hashlib, json, os, re, sys, collections
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); C = f'{H}/catalog'; P = '/Users/carlos/code/sdlc_final_samples/pipeline'
sys.path.insert(0, f'{H}/bin')
from common import load_rows, green, dedupe, shortlist
U = json.load(open(f'{H}/universe.json')); T = {t['id']: t for t in U['tasks']}
S = json.load(open(f'{H}/cat/stats.json'))
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
TXT = {}
for f in os.listdir(f'{P}/cat'):
    if f.endswith('_text.json'):
        for t in json.load(open(f'{P}/cat/{f}')).get('tasks', []): TXT[t['name']] = t
for t in json.load(open(f'{H}/cat/samples_text.json'))['tasks']: TXT[t['name']] = t
OLD = json.load(open(f'{P}/cat/stats.json'))
ORIG_ENV = {t['name']: f'/Users/carlos/code/sdlc_final_samples/catalogs/assets/env-{slug}-ex{i}.svg' for slug, s in OLD.items() for i, t in enumerate(s['showcase'][:3], 1)}
CSV = {r['Horizon task id']: r for r in csv.DictReader(open(f'{H}/gemini_hard_universe.csv'))}
SIDS = {k: v for k, v in json.load(open(f'{H}/cat/sample_ids.json')).items() if not k.startswith('_')}
URLS = {k: f'https://drive.google.com/file/d/{v[0]}/view' for k, v in json.load(open(f'{H}/cat/sample_urls.json')).items() if not k.startswith('_')}
errors, ok = [], collections.Counter()
def eq(what, got, want):
    ok[what.split(':')[0]] += 1
    if got != want: errors.append(f'{what}: page has {got!r}, expected {want!r}')
norm = lambda x: re.sub(r'\s+', ' ', x).strip()
def prompt_source(t):
    for p in (f"{H}/audit/instr/{t['id']}.md", f"{P}/show/{t['name']}/instruction.md", f"{H}/show/{t['name']}/instruction.md"):
        if os.path.exists(p) and os.path.getsize(p): return open(p).read()
samples = sorted([t for t in U['tasks'] if t.get('sample') == 'main'], key=lambda t: t['sample_order'])
ok['samples in selection'] = len(samples)
names = {t['name'] for t in samples}
readme = open(f'{C}/README.md').read()
for slug, s in S.items():
    md = open(f'{C}/{slug}.md').read()
    blocks = re.split(r'^### Example ', md, flags=re.M)[1:]
    eq(f'examples per page: {slug}', [x['name'] for x in s['showcase']], [t['name'] for t in sorted([t for t in samples if t['id'] in {x['id'] for x in s['showcase']}], key=lambda t: t['sample_order'])])
    eq(f'example count: {slug}', len(blocks), len(s['showcase']))
    for i, (blk, x) in enumerate(zip(blocks, s['showcase']), 1):
        t = T[x['id']]; r = ROWS.get(t['id'])
        cat = r['cat'] if r else t['category'].split(' / ')[-1]
        lang = x['language']
        eq(f'heading: {slug} {i}', blk.split('\n', 1)[0], f'{i}: {cat} ({lang})')
        F = dict(re.findall(r'^\| (Final category|Domain|Sub-domain|Language|Seniority) \| (.*?) \|$', blk, re.M))
        # tasks from a moved group show that group's domain, as in the domain breakdown
        GD = {'Migration': 'Cross-language migration', 'Infrastructure as code': 'State-preserving infrastructure changes', 'Data engineering': 'Data pipelines'}
        NC = json.load(open(f'{H}/cat/new_task_classes.json'))
        if not r and t['name'] in NC:
            c = NC[t['name']]; eq(f'field table: {slug} {i}', F, {'Final category': t['catalog'], 'Domain': c['sg'], 'Sub-domain': c['cat'], 'Language': c['lang'], 'Seniority': c['sen']})
        if r: eq(f'field table: {slug} {i}', F, {'Final category': r['final'], 'Domain': GD.get(t['catalog'], r['sg']), 'Sub-domain': r['cat'], 'Language': r['lang'], 'Seniority': r['sen'].replace('–', '-')})
        # prompt: identical to the task's instruction.md at the counted version
        pm = re.search(r'<div class="prompt-md">\n\n(.*?)\n\n</div>', blk, re.S).group(1)
        src = prompt_source(t)
        words = lambda z: re.findall(r'[A-Za-z0-9]{3,}', z)
        eq(f'prompt: {slug} {i}', words(pm)[:60] == words(src)[:60] and abs(len(words(pm)) - len(words(src))) <= 3, True)
        # diagram: the file shown is this task's own diagram
        img = re.search(r'!\[How the task works\]\(assets/([^)]+)\)', blk).group(1)
        f = f'{C}/assets/{img}'
        if img == f"env-{t['name']}.svg": eq(f'diagram: {slug} {i}', os.path.exists(f), True)
        else: eq(f'diagram: {slug} {i}', t['name'] in ORIG_ENV and hashlib.md5(open(f, 'rb').read()).digest() == hashlib.md5(open(ORIG_ENV[t['name']], 'rb').read()).digest(), True)
        # overview row and CSV row point at this example
        row = re.search(rf'^\| Main \| {re.escape(s["name"])} \| \[Example {i}: (.*?)\]\({slug}\.md#(.*?)\) \| \[`(.*?)`\]\((.*?)\) \|', readme, re.M)
        sid = SIDS[t['name']]
        eq(f'task id: {slug} {i}', (re.search(r'^\| Task id \| \[`(.*?)`\]\((.*?)\) \|$', blk, re.M).groups(), row and row.group(3, 4)), ((sid, URLS[sid]), (sid, URLS[sid])))
        site = open(f'{C}/site/{slug}.html').read()
        eq(f'example link target: {slug} {i}', bool(row) and re.search(rf'<h3 id="{re.escape(row.group(2))}"[^>]*>Example {i}:', site) is not None, True)
        eq(f'overview row: {slug} {i}', row and row.group(1), f'{cat} ({lang})')
        c = CSV[t['id']]; eq(f'csv: {slug} {i}', (c['Sample'], c['Catalog example']), ('main', f"{s['name']}, Example {i}"))
# nothing points at former samples
eq('csv sample rows', sum(1 for c in CSV.values() if c['Sample'] == 'main'), len(samples))
# attached samples: overview rows in page order, each with this task's sub-domain, language and Gemini rates; samples.csv lists them
ATT = [a for s in S.values() for a in s['attached']]
rows_ = [(p_, ti, ar, fl) for p_, ti, sid_, u_, ar, fl in re.findall(r'^\| Attached \| (.*?) \| (.*?) \| \[`(.*?)`\]\((.*?)\) \| (.*?) \| (.*?) \|$', readme, re.M)]
ATTIDS = [(a_, u_) for a_, u_ in re.findall(r'^\| Attached \| .*? \| .*? \| \[`(.*?)`\]\((.*?)\) \|', readme, re.M)]
eq('attached rows', len(rows_), len(ATT))
NCn = json.load(open(f'{H}/cat/new_task_classes.json'))
for (pg, title, ar, fl), a in zip(rows_, ATT):
    t = T[a['id']]; r = ROWS.get(t['id']); nc = NCn.get(t['name'])
    want_title = f"{r['cat'] if r else nc['cat']} ({r['lang'] if r else nc['lang']})"
    eq(f"attached row: {t['name']}", (pg, title), (next(s['name'] for s in S.values() if a in s['attached']), want_title))
    g = t['models'].get('google/gemini-4-argon'); f = t['models'].get('google/gemini-3.8-flash')
    pc = lambda v: '<1%' if 0 < v < 0.005 else f'{100 * v:.0f}%'
    eq(f"attached rates: {t['name']}", (ar, fl), (pc(g[1] / g[0]), pc(f[1] / f[0]) if f else ''))
eq('attached task ids', ATTIDS, [(a['task_id'], URLS[a['task_id']]) for a in ATT])
SL = list(csv.DictReader(open(f'{H}/samples.csv')))
# every sample's folder carries its task id, and its task.toml says the same
import tomllib
for r in SL:
    d = f"{H}/samples/{r['Sample']}/{r['Task id']}"
    eq(f"folder: {r['Task id']}", os.path.isdir(d), True)
    if os.path.isdir(d):
        tm = tomllib.loads(open(f'{d}/task.toml').read())
        eq(f"task.toml: {r['Task id']}", (tm.get('metadata', {}).get('task_id'), tm.get('task', {}).get('name', r['Task id']).split('/')[-1]), (r['Task id'], r['Task id']))
eq('task id map', sorted(r['Task id'] for r in SL), sorted(SIDS.values()))
eq('download urls', sorted((r['Task id'], r['Download URL']) for r in SL), sorted(URLS.items()))
for r in SL: eq(f"zip size: {r['Task id']}", os.path.getsize(f"{H}/samples_zip/{r['Sample']}/{r['Task id']}.zip"), json.load(open(f'{H}/cat/sample_urls.json'))[r['Task id']][1])
eq('samples.csv', sorted((r['Sample'], r['Horizon task id']) for r in SL), sorted([('main', t['id']) for t in samples] + [('attached', a['id']) for a in ATT]))
gone = [t['name'] for t in U['tasks'] if not t.get('sample') and t['name'] in TXT]
for f in os.listdir(C):
    if f.endswith('.md'):
        txt = open(f'{C}/{f}').read()
        for n in gone:
            if n in txt: errors.append(f'{f} mentions former sample {n}')
for f in os.listdir(f'{C}/assets'):
    if f.startswith('env-') and not any(f in open(f'{C}/{m}').read() for m in os.listdir(C) if m.endswith('.md')): errors.append(f'unused diagram {f}')
print('checks:', dict(ok))
print('\n'.join(errors) if errors else 'all samples consistent')
sys.exit(1 if errors else 0)
