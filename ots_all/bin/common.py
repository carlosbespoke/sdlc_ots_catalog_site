import sys, os, json, re, collections
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; os.environ['B'] = P
G = '/Users/carlos/code/sdlc_final_samples/gemini_hard'  # sample files, diagrams and checked prompts are shared with it
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{P}/bin')
from cat_common import load_rows, green, dedupe, shortlist
CATS = [('programbench', 'ProgramBench'), ('system-design', 'System design'), ('debugging', 'Diagnosis, Debugging, and Bug Fixing'),
        ('feature-implementation', 'Feature implementation'), ('infrastructure-as-code', 'Infrastructure as code'),
        ('data-engineering', 'Data engineering'), ('migration', 'Migration')]
# Horizon codename -> model, from ../pipeline/ro_models.json plus the vendored Horizon model map for helm and granola-plus.
# Models left out of every page, plot, turn count and CSV column are listed in common_drop.py.
MM = {**json.load(open(f'{P}/ro_models.json')), 'helm': 'cohere/command-a', 'granola-plus': 'meta/muse-spark-1.3'}
MM = {k: {'claude-opus-5-5': 'anthropic/claude-opus-5-5', 'gpt-6-astra': 'openai/gpt-6-astra'}.get(v, v) for k, v in MM.items()}
from common_drop import DROPPED, EXCLUDED_TASKS
SNAPSHOT = open(f'{H}/SNAPSHOT').read().strip()
ALL_TASKS = json.load(open(f'{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/cat/universe.json'))['tasks']  # 1,356 tasks: the 2 Nov sheet's catalog plus the five new System design tasks, frozen from ../gemini_hard/universe.json at d30db8c (that file keeps changing)
ALL_TASKS += json.load(open(f'{H}/cat/extra_tasks.json'))['tasks']  # 25 more from the 'Updated selection 120' tab
# the 9 Optimization tasks are counted as System design (pages, pass rates, turn counts, CSV)
ALL_TASKS = [{**t, 'catalog': 'System design'} if t['catalog'] == 'Optimization' else t for t in ALL_TASKS]
TASKS = [t for t in ALL_TASKS if t['id'] not in EXCLUDED_TASKS]  # 1,305 in the report
RO = {t['id']: json.load(open(f"{H}/ro/{t['id']}.json")) for t in TASKS}
TURNS = {t['id']: [r for r in json.load(open(f"{H}/turns/{t['id']}.json"))['runs'] if r['model'] not in DROPPED] for t in TASKS}
def runs(tid):
    """model -> list of (score, passed) over graded runs (errored runs excluded). The score is the grader's reward, partial credit included."""
    out = collections.defaultdict(list)
    for q in RO[tid]['rollouts']:
        if q['model'] in DROPPED or q.get('is_errored') or q.get('passed') is None: continue
        out[MM[q['model']]].append((q.get('extracted_score') or 0, bool(q['passed'])))
    return out
def pct(v): return 'n/a' if v is None else '<1%' if 0 < v < 0.005 else f'{100 * v:.0f}%'
