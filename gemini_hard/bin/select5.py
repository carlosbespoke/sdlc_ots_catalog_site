# 5 Nov selection (reviewer decision, 5 Nov): every task in the 5 Nov sheet's "Full catalogue" whose runs at the selected task version
# include Gemini 4 Argon OR Gemini 3.8 Flash (any pass rate) OR GLM-5.3 Flash at 10% or less, except tasks Argon passes more than 60% of the time (the 22 samples stay). Runs: ro5/ (all versions, pulled 5 Nov).
# Writes cat/sel5.json: one record per selected task, with the catalog group it belongs to (known from the report, or to classify).
import sys, os, json, re, collections, openpyxl
from common import H, P, MM, ARGON, FLASH, GLMF
wb = openpyxl.load_workbook(f'{H}/nov05/sheet.xlsx', read_only=True)
FC = list(wb['Full catalogue'].iter_rows(values_only=True)); hd = list(FC[5])
ROWS = [dict(zip(hd, x)) for x in FC[6:] if len(x) > 1 and x[1]]
MAP = {r[0]: r[1] for r in list(wb['Horizon task ID mapping'].iter_rows(values_only=True))[1:] if r and r[0]}
GLM_MAX = 0.10
ARUNS = json.load(open(f'{H}/rollout_plan/argon_runs.json')) if os.path.exists(f'{H}/rollout_plan/argon_runs.json') else {}  # finished Argon rollout runs (bin/merge_rollout5.py)
ARGON_MAX = 0.60
EASY_MAX = 0.80  # no task any shown model passes more than 80% of the time (samples excepted)
OLD = {t['id']: t for t in json.load(open(f'{H}/universe_nov02.json'))['tasks']}; OLDN = {t['name']: t for t in OLD.values()}
SAMPLES = {t['id'] for t in OLD.values() if t.get('sample')}  # the 22 samples the client has stay in
# catalog group from the sheet's pipeline, for tasks the report did not have
PIPE = {'ProgramBench reimplementation': 'ProgramBench', 'ProgramBench · Reimplementation': 'ProgramBench', 'ProgramBench repo upgrade': 'ProgramBench',
        'ProgramBench · Repo upgrade': 'ProgramBench', 'Migration': 'Migration', 'System Design': 'System design', 'System design': 'System design',
        'Infrastructure as code': 'Infrastructure as code', 'Spec drift': 'Diagnosis, Debugging, and Bug Fixing', 'RCA / Diagnosis': 'Diagnosis, Debugging, and Bug Fixing',
        'DeepSWE': 'Feature implementation', 'Feature Bench': 'Feature implementation', 'Data processing': 'Data engineering'}
REPORT = {'ProgramBench', 'Migration', 'System design', 'Infrastructure as code', 'Diagnosis, Debugging, and Bug Fixing', 'Feature implementation', 'Data engineering'}
def ver(r):
    v = str(r.get('Selected task version') or ''); return int(float(v)) if re.match(r'^\d+(\.0)?$', v) else None
out, seen = [], set()
for r in ROWS:
    tid = MAP[r['Task']]
    if tid in seen: continue
    seen.add(tid); v = ver(r)
    runs = [q for q in json.load(open(f'{H}/ro5/{tid}.json'))['rollouts'] + ARUNS.get(tid, []) if v is None or q.get('task_version_number') == v]
    g = lambda m: [q for q in runs if MM.get(q['model']) == m and not q.get('is_errored') and q.get('passed') is not None]
    a, f, l = g(ARGON), g(FLASH), g(GLMF)
    if not (a or f or (l and sum(bool(q['passed']) for q in l) / len(l) <= GLM_MAX)): continue
    if a and sum(bool(q['passed']) for q in a) / len(a) > ARGON_MAX and tid not in SAMPLES: continue
    if tid not in SAMPLES and any(x and sum(bool(q['passed']) for q in x) / len(x) > EASY_MAX for x in (f, l)): continue  # any model above 80%: left out (reviewer, 6 Nov)  # Argon above 60%: left out, except the client's samples (reviewer decision, 5 Nov)
    old = OLD.get(tid) or OLDN.get(r['Task'])
    cat = old['catalog'] if old and old['catalog'] in REPORT else PIPE.get(r.get('Original pipeline') or '')
    out.append({'id': tid, 'name': r['Task'], 'version': v, 'pipeline': r.get('Original pipeline'), 'catalog': cat, 'known': bool(old),
                'via': 'gemini' if (a or f) else 'glm', 'what': r.get('What it does and what the agent practices'), 'theme': r.get('Client theme and capability')})
json.dump(out, open(f'{H}/cat/sel5.json', 'w'), indent=1)
print(len(out), collections.Counter(t['catalog'] for t in out), 'known', sum(t['known'] for t in out))
