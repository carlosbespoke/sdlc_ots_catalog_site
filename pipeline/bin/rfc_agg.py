import sys, os, json, re, collections
B = sys.argv[1]; sys.path.insert(0, f'{B}/bin')
from hier import CAT, R
T = {json.load(open(f'{B}/rfc/t/{f}'))['id']: json.load(open(f'{B}/rfc/t/{f}')) for f in os.listdir(f'{B}/rfc/t')}
C = {}
for f in sorted(os.listdir(f'{B}/rfc/out')):
    for line in open(f'{B}/rfc/out/{f}'):
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except Exception: continue
        C[o['id']] = o
sys.path.insert(0, f'{B}/rfc')
from drift_overrides import O
for k, t in T.items():
    if t['name'].startswith('pdk-drift-repository-') and t['name'].rsplit('-', 1)[-1] in O:
        cat, nc, rl, up = O[t['name'].rsplit('-', 1)[-1]]
        C.setdefault(k, {'id': k}); C[k].update(cat=cat, new_cat=nc, role=rl, lang='Python')
# standardise proposed category names
NEWMAP = {}
def norm(n):
    l = n.lower()
    if 'game' in l or 'puzzle' in l: return 'Games & game engines'
    if 'emulat' in l: return 'Emulators'
    if 'cad' in l or 'cam' in l or 'g-code' in l or 'bim' in l: return 'CAD / CAM'
    if 'font' in l: return 'Fonts & text rendering'
    if 'text' in l or 'nlp' in l or 'markup' in l: return 'Text & NLP processing'
    if 'format' in l or 'lint' in l: return 'Code formatters & linters'
    if 'visuali' in l: return 'Data visualization'
    if 'data structure' in l: return 'Data structures'
    if 'utilit' in l or 'dependency injection' in l: return 'General-purpose utility libraries'
    if 'blockchain' in l: return 'Blockchain'
    if 'spreadsheet' in l: return 'Spreadsheets'
    if 'system information' in l: return 'System information libraries'
    return n.strip() or 'Unspecified'
for o in C.values():
    if o.get('cat') == 0: o['new_cat'] = norm(o.get('new_cat', ''))
missing = [k for k in T if k not in C]
# domain for categories proposed during classification (not in the 53-category taxonomy)
HOME = {'Text & NLP processing': 'Languages & developer tooling', 'General-purpose utility libraries': 'Languages & developer tooling',
        'Code formatters & linters': 'Languages & developer tooling', 'Data structures': 'Languages & developer tooling',
        'Games & game engines': 'Applications & business domains', 'Fonts & text rendering': 'Applications & business domains',
        'Spreadsheets': 'Applications & business domains', 'CAD / CAM': 'Scientific & ML software',
        'Emulators': 'Systems, hardware & accelerators', 'System information libraries': 'Systems, hardware & accelerators',
        'Data visualization': 'Data engineering & databases', 'Blockchain': 'Distributed systems & coordination'}
def shape(t, c):
    b = (t['batch'] or '').lower(); n = t['name'].lower(); tm = t['toml'].lower()
    if ('reimplementation' in b and 'featureimplementation' not in b) or 'reimplementation' in tm: return 'Rebuild a program from its binary','Greenfield / reimplementation','Staff+','Implementation'
    if 'upgrade' in b or 'repository-update' in tm: return 'Evolve a repo from one release to the next','Software evolution','Senior','Maintenance'
    if 'migration' in b and 'db-migration' not in n: return 'Evolve a repo from one release to the next','Software evolution','Senior','Migration'
    if 'diagnosis' in b: return 'NEW: Multi-bug diagnosis & fault localization','Debugging','Senior','Debugging'
    if b.startswith('rca'): return 'On-call root cause analysis','Debugging','Mid–Senior','Debugging'
    if 'spec' in b and 'drift' in b or 'specdrift' in b: return 'NEW: Docs-vs-code drift repair','Software evolution','Senior','Maintenance'
    if b.startswith('sre'):
        if n.startswith('db-migration') or n.startswith('livesvc'): return 'Live system change','SRE & live operations','Staff+','Deployment & operations'
        if n.startswith('qfn') or 'system-administration' in tm: return 'Incident response','SRE & live operations','Staff+','Deployment & operations'
        return 'NEW: State-preserving IaC change','Infrastructure as code','Senior','Refactoring'
    if b.startswith('iac'): return 'NEW: State-preserving IaC change','Infrastructure as code','Senior','Refactoring'
    if 'data-processing' in b: return 'NEW: Data pipeline repair / extension','Data engineering','Mid–Senior','Maintenance'
    if 'system-design' in b: return 'Failure-proofing','Fault tolerance / distributed systems','Staff+','Design'
    if 'optimization' in b: return 'NEW: CPU performance optimization','Performance','Senior','Performance'
    # feature-style batches (deepswe, cohere, blueprint, gemini)
    if c.get('durable'): return 'Failure-proofing','Fault tolerance / distributed systems','Staff+','Implementation'
    return 'Feature development across several PRs','Feature development','Senior','Implementation'
def role(t, c, sh):
    base = c.get('role', ''); n = t['name'].lower()
    if sh == 'Failure-proofing' and 'system-design' in (t['batch'] or '').lower(): return 'Distributed Systems Engineer'
    if sh == 'Live system change': return 'Database Reliability Engineer' if n.startswith('db-migration') else 'Platform Engineer'
    if sh == 'Incident response': return 'SRE'
    if sh == 'NEW: State-preserving IaC change': return 'Cloud Security Engineer' if ('policy' in n or c.get('cat') == 32) else 'Platform Engineer'
    if sh == 'NEW: Data pipeline repair / extension': return 'Analytics Engineer' if 'dbt' in n else 'Data Engineer'
    if sh == 'NEW: CPU performance optimization': return 'Performance Engineer'
    return base
rows = []
for k, t in T.items():
    c = C.get(k, {})
    sh, shc, sen, sdlc = shape(t, c)
    cat = c.get('cat', -1)
    if cat in CAT: cname, sg = CAT[cat][0], R[CAT[cat][2]]
    elif cat == 0:
        nc = c.get('new_cat') or 'Unspecified'
        cname, sg = 'NEW: ' + nc, HOME.get(nc, 'Languages & developer tooling')
    else: cname, sg = '(not classified)', '(not classified)'
    rows.append(dict(cat=cname, sg=sg, shape=sh, shapec=shc, sen=sen, sdlc=sdlc, role=role(t, c, sh), lang=c.get('lang', '(not classified)'), batch=t['batch']))
N = len(rows)
dims = collections.OrderedDict()
for key, label in [('sg','Domain super-group'),('cat','Domain category'),('shapec','Task shape category'),('shape','Task shape'),('role','Primary role'),('sen','Seniority'),('sdlc','SDLC phase'),('lang','Primary language')]:
    dims[label] = collections.Counter(r[key] for r in rows).most_common()
used = {r['cat'] for r in rows}
known = {v[0] for v in CAT.values()}
summary = {
 'title': f'Ready-for-client tasks in the alpharecon project: {N} tasks',
 'total': N,
 'notes': [
   f'Scope: Horizon project alpharecon, status ready-for-client, {len({r["batch"] for r in rows})} batches. Pulled {__import__("datetime").date.today()}.',
   f'Domain categories used: {len(used & known)} of the 53 in the taxonomy, plus {len(used - known - {"(not classified)"})} proposed new categories for tasks that fit none.',
   f'Unused taxonomy categories: ' + (', '.join(sorted(known - used)) or 'none'),
   'Task shape, seniority and SDLC phase are set from the batch; domain category, language and domain-based role were assigned by a model from each task\'s instruction, files and Dockerfile, then the same role overrides as the shortlist were applied.',
   f'Not classified: {len(missing)} tasks.',
 ],
 'dims': dims,
}
json.dump(summary, open(f'{B}/rfc/summary.json', 'w'), indent=1)
print(N, 'rows; missing', len(missing))
for label, rows_ in dims.items():
    print(f'\n## {label} ({len(rows_)} distinct)')
    for k, v in rows_[:60]: print(f'{v:5d}  {k}')
