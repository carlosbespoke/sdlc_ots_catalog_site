# Re-pull every sample's runs and turn counts from Horizon now, recompute the Gemini numbers each sample shows on the
# pages (pass rate, mean score, turns per model, long horizon) and compare with the pages. Read-only against Horizon.
import json, os, re, statistics, sys, time, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); C = f'{H}/catalog'
MM = json.load(open('/Users/carlos/code/sdlc_final_samples/pipeline/ro_models.json')); GEM = {k: v for k, v in MM.items() if 'gemini' in v}
c = client.Client()
def get(path, params=None, ok=lambda d: True):
    for a in range(25):  # the API returns intermittent 404s
        try:
            d = c.get(path, params)
            if ok(d): return d
        except Exception: pass
        time.sleep(1 + a % 4)
    raise SystemExit(f'could not fetch {path}')
U = json.load(open(f'{H}/universe.json')); RO = {}
samples = sorted([t for t in U['tasks'] if t.get('sample') == 'main'], key=lambda t: t['sample_order'])
pct = lambda v: '<1%' if 0 < v < 0.005 else f'{100 * v:.0f}%'
pages = {slug: open(f'{C}/{slug}.md').read() for slug in ('programbench', 'system-design', 'debugging', 'feature-implementation')}
CSVX = {}
import csv
for r in csv.DictReader(open(f'{H}/gemini_hard_universe.csv')):
    if r['Catalog example']: CSVX[r['Horizon task id']] = r['Catalog example']
SLUG = {'ProgramBench and Migration': 'programbench', 'System design & IaC': 'system-design', 'Diagnosis, Debugging, and Bug Fixing': 'debugging', 'Feature implementation': 'feature-implementation'}
errors, report = [], []
for t in samples:
    snap = json.load(open(f"{H}/ro3/{t['id']}.json")); v = snap['version']
    live = get(f"api/tasks/{t['id']}/rollouts", {'task_version': str(v)}, ok=lambda d: d.get('rollouts') is not None)
    rs = [x for x in live['rollouts'] if x['model'] in GEM]
    graded = [x for x in rs if not x.get('is_errored') and x.get('passed') is not None]
    by = collections.defaultdict(list)
    for x in graded: by[GEM[x['model']]].append(x)
    # turn counts straight from each completed run
    turns = collections.defaultdict(list)
    for x in rs:
        if x.get('is_errored'): continue
        d = get(f"api/rollouts/{x['id']}", ok=lambda d: isinstance(d.get('turn_count'), (int, float)))
        turns[GEM[x['model']]].append(d['turn_count'])
    cat, n = CSVX[t['id']].rsplit(', Example ', 1); md = pages[SLUG[cat]]
    blk = re.split(r'^### Example ', md, flags=re.M)[int(n)]
    shown = {r[0]: r[1:] for r in (l.strip('|').split('|') for l in blk.splitlines() if l.startswith('| google/')) if len(r) == 2}
    shown = {k.strip(): [x.strip() for x in v] for k, v in shown.items()}
    want = {m: [pct(sum(bool(x['passed']) for x in xs) / len(xs))] for m, xs in by.items()}
    if shown != want: errors.append(f"{t['name']}: pass rates on page {shown}, Horizon now {want}")
    tl = re.search(r'^\| Turn count \| (.*) \|$', blk, re.M).group(1)
    tw = ', '.join(f'{statistics.mean(v):.0f} ({m})' for m, v in turns.items()) if turns else 'no completed run'
    if sorted(tl.split(', ')) != sorted(tw.split(', ')): errors.append(f"{t['name']}: turn count on page '{tl}', Horizon now '{tw}'")
    lh = re.search(r'^\| Long horizon \| (.*) \|$', blk, re.M).group(1)
    allt = [x for v in turns.values() for x in v]
    lw = ('yes' if statistics.mean(allt) >= 200 else 'no') if allt else 'n/a'
    if lh != lw: errors.append(f"{t['name']}: long horizon on page '{lh}', Horizon now '{lw}'")
    new = len(live['rollouts']) - snap['n_rollouts']
    report.append((cat, n, t['name'], f'v{v}', {m: f"{sum(bool(x['passed']) for x in xs)}/{len(xs)}" for m, xs in by.items()}, tw, f'{new:+d} runs since snapshot' if new else 'no new runs'))
for r in report: print(*r, sep=' | ')
print('\n'.join(errors) if errors else 'ALL SAMPLE PASS RATES AND TURN COUNTS MATCH HORIZON')
sys.exit(1 if errors else 0)
