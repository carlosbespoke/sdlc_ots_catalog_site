# Select tasks for a Gemini 4 Argon (umbra) run: all shortlisted Green tasks, plus a domain-stratified sample per catalog.
# Catalogs with <= 40 tasks are covered in full. Larger ones get max(30, shortlist + 10) tasks.
# Random picks prefer tasks that already have graded runs from other models (paired comparison). Seed fixed.
import sys, os, json, csv, random, collections, math
B = sys.argv[1]; os.environ['B'] = B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cat_common import load_rows, green, dedupe, shortlist, CATS
SL = shortlist(); MM = json.load(open(f'{B}/ro_models.json')); S = json.load(open(f'{B}/cat/stats.json'))
R = [r for r in dedupe([r for r in green(load_rows()) if r['catalog']], SL) if r['catalog'] != 'Optimization']
rng = random.Random(20261028)
QUOTA = {'ProgramBench': {'ProgramBench reimplementation': 20, 'ProgramBench repo upgrade': 20}}
def ro(r): return json.load(open(f"{B}/ro2/{r['id']}.json"))
def graded_by(r):
    return {g['model']: g.get('graded_count') or 0 for g in ro(r)['grouped'] if g.get('graded_count')}
rows, summary = [], []
for slug, cat in CATS:
    X = [r for r in R if r['catalog'] == cat]; N = len(X)
    fold = S[slug]['folded']; dom = lambda r: fold.get(r['sg'], r['sg'])
    has_argon = [r for r in X if 'umbra' in graded_by(r)]
    target = N if N <= 40 else min(N, max(30, sum(1 for r in X if r['name'] in SL) + 10))
    # ProgramBench: no model has run the repo-upgrade tasks, so give each half of the catalog its own quota of 20
    parts = [(lambda r, f=f: r['final'] == f, q) for f, q in QUOTA[cat].items()] if cat in QUOTA else [(lambda r: True, target)]
    pick = {}
    for r in X:
        if r['name'] in SL: pick[r['id']] = 'shortlist'
    for r in has_argon:
        pick.setdefault(r['id'], 'already run')
    for inpart, target in parts:
      XP = [r for r in X if inpart(r)]; rest = [r for r in XP if r['id'] not in pick]
      need = max(0, target - sum(1 for r in XP if r['id'] in pick))
      if need and rest:
          # proportional allocation by domain over the whole catalog, minus what the fixed picks already cover
          size = collections.Counter(dom(r) for r in XP); have = collections.Counter(dom(r) for r in XP if r['id'] in pick)
          want = {d: max(0, target * k / len(XP) - have[d]) for d, k in size.items()}
          alloc = {d: 0 for d in size}
          for _ in range(need):
              d = max((d for d in want if sum(1 for r in rest if dom(r) == d) > alloc[d]), key=lambda d: want[d] - alloc[d], default=None)
              if d is None: break
              alloc[d] += 1
          for d, k in alloc.items():
              pool = [r for r in rest if dom(r) == d]; rng.shuffle(pool)
              pool.sort(key=lambda r: not graded_by(r))  # paired first, random within
              for r in pool[:k]: pick[r['id']] = 'stratified sample'
    sel = [r for r in X if r['id'] in pick]
    for r in sel:
        gb = graded_by(r)
        rows.append({'catalog': cat, 'task_name': r['name'], 'task_id': r['id'], 'task_version': ro(r)['version'], 'batch': r['batch'],
                     'final_category': r['final'], 'domain': dom(r), 'sub_domain': r['cat'], 'language': r['lang'], 'reason': pick[r['id']],
                     'argon_runs_needed': 0 if 'umbra' in gb else 5,
                     'other_models_graded': '; '.join(f"{MM.get(m, m)} x{n}" for m, n in sorted(gb.items(), key=lambda x: -x[1]) if m != 'umbra')})
    cnt = collections.Counter(pick.values())
    dcov = collections.Counter(dom(r) for r in sel); dall = collections.Counter(dom(r) for r in X)
    summary.append({'catalog': cat, 'slug': slug, 'tasks': N, 'selected': len(sel), 'shortlist': cnt['shortlist'], 'already': cnt['already run'],
                    'sampled': cnt['stratified sample'], 'new_tasks': sum(1 for r in sel if 'umbra' not in graded_by(r)),
                    'paired': sum(1 for r in sel if set(graded_by(r)) - {'umbra'}),
                    'domains': [(d, dall[d], dcov[d]) for d, _ in dall.most_common()]})
out = '/Users/carlos/code/sdlc_final_samples/argon_proposal'
with open(f'{out}/argon_task_selection.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump(summary, open(f'{B}/argon_summary.json', 'w'), indent=1)
for s in summary:
    print(f"{s['catalog']:38s} N={s['tasks']:4d} sel={s['selected']:3d} SL={s['shortlist']:3d} already={s['already']:2d} sample={s['sampled']:3d} new={s['new_tasks']:3d} paired={s['paired']:3d}")
    for d, a, c in s['domains']: print(f"      {d:40s} {a:4d} -> {c:3d}  ({100*a/s['tasks']:.0f}% vs {100*c/s['selected']:.0f}%)")
print('total selected', len(rows), 'new tasks', sum(1 for r in rows if r['argon_runs_needed']), 'runs', sum(r['argon_runs_needed'] for r in rows))
