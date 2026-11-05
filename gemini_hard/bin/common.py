import sys, os, json, re, collections
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; os.environ['B'] = P
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{P}/bin')
from cat_common import load_rows, green, dedupe, shortlist, CATS
MM = json.load(open(f'{P}/ro_models.json'))
ARGON, FLASH, GLMF = 'google/gemini-4-argon', 'google/gemini-3.8-flash', 'z-ai/glm-5.3-flash'
DROPPED = 'google/gemini-3.7-flash'  # left out of every page, plot and CSV column (its runs still count as evidence in the selection)
RO_SNAP = {f[:-5]: json.load(open(f'{H}/ro3/{f}')) for f in os.listdir(f'{H}/ro3')}  # the 2 Nov snapshot
# runs refreshed after the snapshot (same task version), which replace the snapshot's for those tasks on the pages and in the tiers;
# the estimate and the Likely predictions stay on the snapshot so the headline counts do not move (reviewer decision, 5 Nov)
REFRESH = {f[:-5]: json.load(open(f'{H}/ro3_refresh/{f}')) for f in os.listdir(f'{H}/ro3_refresh')} if os.path.isdir(f'{H}/ro3_refresh') else {}
RO = {**RO_SNAP, **REFRESH}
def mstats(tid, snap=False):
    """model -> [graded, passed, mean score over graded]"""
    out = collections.defaultdict(lambda: [0, 0, 0.0])
    for q in (RO_SNAP if snap else RO).get(tid, {}).get('rollouts', []):
        if q.get('is_errored') or q.get('passed') is None: continue
        o = out[MM.get(q['model'], q['model'])]; o[0] += 1; o[1] += bool(q['passed']); o[2] += q.get('extracted_score') or 0
    return {m: [g, p, s / g] for m, (g, p, s) in out.items() if g}
def selection():
    import openpyxl
    U = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Updated selection 120'].iter_rows(values_only=True))
    out = []
    for x in U[6:]:
        if len(x) < 12 or not x[1]: continue
        out.append({'no': int(float(x[0])), 'name': x[1], 'taxonomy': x[2], 'id': re.search(r'[0-9a-f]{8}-[0-9a-f-]{27}', x[10]).group(0),
                    'purpose': x[4], 'why': x[5], 'creator': x[9]})
    return out
def full_catalogue():
    import openpyxl
    U = list(openpyxl.load_workbook(f'{P}/fullcat/nov02/sheet.xlsx', read_only=True)['Full catalogue'].iter_rows(values_only=True))
    hd = list(U[5]); return [dict(zip(hd, x)) for x in U[6:] if len(x) > 1 and x[1]]
