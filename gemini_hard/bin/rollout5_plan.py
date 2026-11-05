# Argon rollout plan (5 Nov): 331 tasks with no Gemini 4 Argon runs, in two sets.
#  - confirm (174): tasks already in the report that every GLM-5.3 Flash / Grok 4.7 run failed and no model ever passed
#    ("zero everywhere"), half of the 348, chosen to favour the catalogs short of their original targets:
#    all ProgramBench (136) and System design (12), then Feature implementation (18), then Debugging (8, most failed GLM runs first).
#  - refill (157): "Green: presentable" tasks in the 5 Nov sheet that are not in the report, in ProgramBench and System design,
#    with GLM-5.3 Flash at 10-50% or only Grok 4.7 runs that almost always fail (<=1 of 8), or no runs at all (ProgramBench).
# Only tasks whose active version is the sheet's selected version (Horizon runs the active version). Writes rollout_plan/plan.csv.
import csv, json, os, collections
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
pool = [t for t in json.load(open(f'{OUT}/candidates_pool.json'))['pool'] if t['runnable']]
green = [t for t in json.load(open(f'{OUT}/candidates_green.json')) if t['runnable']]
def grok_hard(t):
    g = t['others'].get('x-ai/grok-4.7'); return bool(g) and g[0] <= 1 and set(t['others']) <= {'x-ai/grok-4.7', 'helm'}
green = [t for t in green if t['bucket'] in ('GLM 10-30%', 'GLM 30-50%', 'no runs') or (t['bucket'] == 'other models only' and grok_hard(t))]
key = lambda t: (-t['nfail'], t['name'])
by = collections.defaultdict(list)
for t in pool: by[t['page']].append(t)
gid = {t['id'] for t in green}  # a task in both sets stays in refill; Debugging tops the confirm set back up to 174
first = [t for t in sorted(by['ProgramBench'], key=key) + sorted(by['System design'], key=key) + sorted(by['Feature implementation'], key=key) if t['id'] not in gid]
confirm = first + [t for t in sorted(by['Diagnosis, Debugging, and Bug Fixing'], key=key) if t['id'] not in gid][:174 - len(first)]
ORDER = {'ProgramBench': 0, 'System design': 1}; BUCKET = {'GLM 10-30%': 0, 'other models only': 1, 'GLM 30-50%': 2, 'no runs': 3}
refill = sorted(green, key=lambda t: (ORDER[t['page']], BUCKET[t['bucket']], t['name']))
rows = [{'set': 'refill', 'priority': i, 'catalog': t['page'], 'task_id': t['id'], 'task': t['name'], 'version': t['version'], 'evidence': t['bucket']} for i, t in enumerate(refill)]
rows += [{'set': 'confirm', 'priority': len(refill) + i, 'catalog': t['page'], 'task_id': t['id'], 'task': t['name'], 'version': t['version'],
          'evidence': f"GLM/Grok 0 of {t['nfail']}"} for i, t in enumerate(confirm)]
assert len({r['task_id'] for r in rows}) == len(rows), 'a task is in both sets'
with open(f'{OUT}/plan.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), collections.Counter((r['set'], r['catalog']) for r in rows))
