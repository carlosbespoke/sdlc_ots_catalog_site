# Runs of the family members (originals, forks, copies) of ProgramBench tasks that have no Gemini 4 Argon runs of their own and are not
# in the Argon rollout. Family members come from the 5 Nov sheet's "Other task IDs in this family" column; every member's runs are
# pulled read-only, all versions, into family5/<task id>.json. The sheet's "Existing rollout evidence" text is kept alongside.
import sys, os, re, json, csv, time, collections, concurrent.futures as cf, openpyxl
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = '/Users/carlos/code/sdlc_final_samples/pipeline'
MM = json.load(open(f'{P}/ro_models.json')); ARGON = 'google/gemini-4-argon'
PIPE = {'ProgramBench reimplementation', 'ProgramBench · Reimplementation', 'ProgramBench repo upgrade', 'ProgramBench · Repo upgrade', 'Migration'}
U = json.load(open(f'{H}/universe.json')); SEL = {t['id']: t for t in U['tasks'] if t.get('tier')}
PLAN = {r['task_id'] for r in csv.DictReader(open(f'{H}/rollout_plan/runs.csv'))}
wb = openpyxl.load_workbook(f'{H}/nov05/sheet.xlsx', read_only=True)
FC = list(wb['Full catalogue'].iter_rows(values_only=True)); hd = list(FC[5]); rows = [dict(zip(hd, x)) for x in FC[6:] if len(x) > 1 and x[1]]
MAP = {r[0]: r[1] for r in list(wb['Horizon task ID mapping'].iter_rows(values_only=True))[1:] if r and r[0]}
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
def ver(r):
    v = str(r.get('Selected task version') or ''); return int(float(v)) if re.match(r'^\d+(\.0)?$', v) else None
tgt, seen = [], set()
for r in rows:
    tid = MAP[r['Task']]
    if tid in seen: continue
    seen.add(tid)
    if not ((tid in SEL and SEL[tid]['catalog'] in ('ProgramBench', 'Migration')) or (tid not in SEL and r.get('Original pipeline') in PIPE)) or tid in PLAN: continue
    v = ver(r); rs = [q for q in json.load(open(f'{H}/ro5/{tid}.json'))['rollouts'] if v is None or q.get('task_version_number') == v]
    if any(MM.get(q['model']) == ARGON and not q.get('is_errored') and q.get('passed') is not None for q in rs): continue
    fam = [x for x in dict.fromkeys(re.findall(UUID, str(r.get('Other task IDs in this family') or ''))) if x != tid]
    tgt.append({'id': tid, 'name': r['Task'], 'version': v, 'pipeline': r.get('Original pipeline'), 'green': str(r.get('Client presentation status') or '').startswith('Green'),
                'family': fam, 'evidence': r.get('Existing rollout evidence'), 'evidence_evals': re.findall(r'eval (' + UUID + ')', str(r.get('Existing rollout evidence') or ''))})
c = client.Client(); os.makedirs(f'{H}/family5', exist_ok=True)
KEEP = ('id', 'model', 'passed', 'is_errored', 'extracted_score', 'task_version_number', 'evaluation_id', 'created_at')
def get(p):
    for a in range(6):
        try: return c.get(p)
        except Exception: time.sleep(2 * (a + 1))
def pull(t):
    out = f"{H}/family5/{t['id']}.json"
    if os.path.exists(out): return 'cached'
    mem = []
    for f in t['family']:
        d = get(f'api/tasks/{f}/rollouts')
        if d is None: return 'fail'
        info = get(f'api/tasks/{f}') or {}; info = info.get('task', info)
        mem.append({'id': f, 'name': info.get('name'), 'batch': info.get('batch_name'), 'rollouts': [{k: x.get(k) for k in KEEP} for x in d.get('rollouts') or []]})
    json.dump({**t, 'members': mem}, open(out, 'w')); return 'ok'
with cf.ThreadPoolExecutor(8) as ex: print(len(tgt), dict(collections.Counter(ex.map(pull, tgt))))
