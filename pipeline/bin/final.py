import sys, json, os, collections
sys.path.insert(0, sys.argv[1] + '/bin')
from hier import P, R, CAT, DOM
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
SRC = '/Users/carlos/code/sdlc_final_samples/task_taxonomies_v3.xlsx'
OUT = '/Users/carlos/code/sdlc_final_samples/task_taxonomies_final.xlsx'
src = load_workbook(SRC)
ws = src['Taxonomies']; H = [c.value for c in ws[1]]
data = [dict(zip(H, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
links = {ws.cell(r, 2).value: ws.cell(r, 3).hyperlink.target for r in range(2, ws.max_row + 1)}
IL = json.load(open(sys.argv[1] + '/v2/instr_len.json'))
LEN = ["Instruction length (words)","Instruction length (characters)","Instruction length (lines)"]
for d in data:
    v = IL.get(d['Task'])
    for k, f in zip(LEN, ('words','chars','lines')): d[k] = v[f] if v else 'no instruction.md'
H = H + LEN
# Final category (signed off 27 Oct 2026), taken from the ready-for-client export by task name
EX = json.load(open(sys.argv[1] + '/rfc/explorer.json')); EI = {k: i for i, k in enumerate(EX['keys'])}
FIN = {r[-1]: (EX['dicts']['final'][r[EI['final']]], EX['dicts']['fstat'][r[EI['fstat']]], EX['dicts']['fam'][r[EI['fam']]]) for r in EX['rows']}
for d in data: d['Final category'], d['Final category basis'], d['Batch group'] = FIN[d['Task']]
H = H + ['Final category', 'Final category basis', 'Batch group']
# Revised shape categories: RCA is debugging; SRE and live operations merge; Reliability renamed
for d in data:
    sh, c = d.get('Task shape (SDLC Task shapes sheet)') or '', d.get('Task shape category')
    if sh.startswith('On-call root cause'): d['Task shape category'] = 'Debugging'
    elif c in ('SRE / incident response', 'Operations / migration'): d['Task shape category'] = 'SRE & live operations'
    elif c == 'Reliability': d['Task shape category'] = 'Fault tolerance / distributed systems'
GROUPS = [
 ("Identity", "1F3864", ["Rank","Task","Horizon","Batch","Status vs. previous list"]),
 ("Final classification", "0B6E4F", ["Final category","Final category basis","Batch group"]),
 ("Sheet taxonomy", "404040", ["Main taxonomy (sheet)","Capability (sheet)"]),
 ("Domain hierarchy", "375623", ["Domain super-group (revised)","Domain category (50+3)","Domain","Upstream project","Domain super-group (previous)"]),
 ("Task shape", "833C0B", ["Task shape category","Task shape (SDLC Task shapes sheet)","Task shape match","SDLC phase","Change type"]),
 ("Role", "7F6000", ["Primary role","Secondary role","Seniority"]),
 ("Prompt", "C55A11", ["Instruction length (words)","Instruction length (characters)","Instruction length (lines)"]),
 ("Technology", "1F4E78", ["Primary language","Other languages","Tech stack"]),
 ("Evaluation", "3F3151", ["Benchmark family","Grading approach","Environment shape","Customer hint (from batch name)"]),
]
cols = [c for _, _, cs in GROUPS for c in cs]
assert set(cols) == set(H), set(H) ^ set(cols)
W = {"Final category":30,"Final category basis":30,"Batch group":30,"Rank":6,"Task":40,"Horizon":10,"Batch":28,"Status vs. previous list":10,"Main taxonomy (sheet)":32,"Capability (sheet)":28,"Domain super-group (revised)":28,
     "Domain category (50+3)":30,"Domain":32,"Upstream project":24,"Domain super-group (previous)":26,"Task shape category":22,"Task shape (SDLC Task shapes sheet)":36,
     "Task shape match":40,"SDLC phase":18,"Change type":28,"Primary role":28,"Secondary role":24,"Seniority":11,"Primary language":22,"Other languages":18,"Tech stack":44,
     "Benchmark family":32,"Grading approach":44,"Environment shape":32,"Customer hint (from batch name)":16,"Instruction length (words)":12,"Instruction length (characters)":13,"Instruction length (lines)":11}
wb = Workbook(); t = wb.active; t.title = 'Taxonomies'
t.append([g for g, _, cs in GROUPS for _ in cs]); t.append(cols)
col = 1
for g, colr, cs in GROUPS:
    t.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(cs) - 1)
    for j in range(len(cs)):
        for r in (1, 2):
            c = t.cell(r, col + j); c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor=colr); c.alignment = Alignment(wrap_text=True, vertical='top', horizontal='center' if r == 1 else 'left')
        t.column_dimensions[t.cell(2, col + j).column_letter].width = W[cs[j]]
    col += len(cs)
for d in data:
    t.append([d[c] for c in cols])
    r = t.max_row; h = t.cell(r, 3); h.hyperlink = links[d['Task']]; h.font = Font(color='0563C1', underline='single')
    for c in t[r]: c.alignment = Alignment(wrap_text=True, vertical='top')
t.freeze_panes = 'C3'; t.auto_filter.ref = f"A2:{t.cell(2, len(cols)).column_letter}{t.max_row}"
# Taxonomy reference tab: the hierarchy itself
ref = wb.create_sheet('Taxonomy reference')
ref.append(['Level','Value','Parent','Shortlist tasks']); 
for c in ref[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
cnt = lambda k, v: sum(1 for d in data if d[k] == v)
for gk in R:
    ref.append(['Domain super-group', R[gk], '', cnt('Domain super-group (revised)', R[gk])])
    for k in sorted(c for c in CAT if CAT[c][2] == gk):
        ref.append(['  Domain category', CAT[k][0], R[gk], cnt('Domain category (50+3)', CAT[k][0])])
ref.append([])
shapes = collections.OrderedDict()
for d in sorted(data, key=lambda d: d['Task shape category']): shapes.setdefault(d['Task shape category'], set()).add(d['Task shape (SDLC Task shapes sheet)'])
for sc, ss in shapes.items():
    ref.append(['Task shape category', sc, '', cnt('Task shape category', sc)])
    for s in sorted(ss): ref.append(['  Task shape', s, sc, cnt('Task shape (SDLC Task shapes sheet)', s)])
ref.append([])
nums = sorted(d['Instruction length (words)'] for d in data if isinstance(d['Instruction length (words)'], int))
if nums:
    q = lambda f: nums[min(len(nums) - 1, int(f * len(nums)))]
    ref.append(['Instruction length (words)', f'min {nums[0]} · median {q(0.5)} · p90 {q(0.9)} · max {nums[-1]}', f'{len(nums)} of {len(data)} tasks measured', ''])
    ref.append([])
for rl in sorted({d['Primary role'] for d in data}): ref.append(['Primary role', rl, '', cnt('Primary role', rl)])
ref.append([])
for s in ['Staff+','Senior','Mid–Senior']: ref.append(['Seniority', s, '', cnt('Seniority', s)])
for i, w in enumerate([22,52,30,14]): ref.column_dimensions[chr(65+i)].width = w
for row in ref.iter_rows(min_row=2):
    if row[0].value and not str(row[0].value).startswith('  '): row[1].font = Font(bold=True)
# copy the analysis tabs from v3
for name in ['Domain hierarchy','Task shape coverage','Roles','Summary','Dropped from list','Definitions']:
    s = src[name]; n = wb.create_sheet(name)
    for row in s.iter_rows(values_only=True): n.append(list(row))
    for k, dim in s.column_dimensions.items(): n.column_dimensions[k].width = dim.width
    for r in n.iter_rows():
        for c in r: c.alignment = Alignment(wrap_text=True, vertical='top')
    for c in n[1]: c.font = Font(bold=True)
df = wb['Definitions']
for row in [("Final category", "Client-facing classification signed off on 27 Oct 2026: ProgramBench repo upgrade · ProgramBench reimplementation · Feature implementation · Fault tolerance · System design · Diagnosis, Debugging, and Bug Fixing · Infrastructure as code · Data engineering · Migration · Optimization · SRE (parked)."),
            ("Final category basis", "Batch rule: follows the task's batch group. Spec drift folded into Diagnosis: documentation-drift tasks are blind bug finding with the docs as the reference. Instruction review: DeepSWE and Cohere durability and system-design tasks, split by reading each instruction (System design = several instances, workers or nodes must coordinate; Fault tolerance = one component must survive or recover from failure; Feature implementation = failure handling is incidental). Parked: the 5 SRE live-operations tasks."),
            ("Batch group", "Batches merged for reporting: all Cohere batches; all Diagnosis batches; Feature implementation / DeepSWE; the two ProgramBench upgrade batches; the three spec-drift batches; the two migration batches; the two optimization batches; RCA + SRE (xAI).")]:
    df.append(list(row))
    for c in df[df.max_row]: c.alignment = Alignment(wrap_text=True, vertical='top')
# optional: ready-for-client portfolio summary
rf = sys.argv[2] if len(sys.argv) > 2 else None
if rf and os.path.exists(rf):
    S = json.load(open(rf)); s = wb.create_sheet('Ready-for-client (alpharecon)', 1)
    s.append([S['title']]); s[1][0].font = Font(bold=True, size=13)
    for line in S['notes']: s.append([line])
    for dim, rows in S['dims'].items():
        s.append([]); s.append([dim, 'Tasks', '% of total']); 
        for c in s[s.max_row]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864')
        for k, v in rows: s.append([k, v, round(100 * v / S['total'], 1)])
    if S.get('xtab'):
        X = S['xtab']; s.append([]); s.append([X['title']]); s[s.max_row][0].font = Font(bold=True, size=12)
        s.append([X['rows_label'] + ' \\ ' + X['cols_label']] + X['cols'] + ['Total'])
        for c in s[s.max_row]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='0B6E4F'); c.alignment = Alignment(wrap_text=True, vertical='top')
        for rname, vals in X['rows']: s.append([rname] + [v or None for v in vals] + [sum(vals)])
        s.append(['Total'] + [sum(v[i] for _, v in X['rows']) for i in range(len(X['cols']))] + [S['total']])
        for c in s[s.max_row]: c.font = Font(bold=True)
        for i in range(len(X['cols']) + 1): s.column_dimensions[s.cell(1, i + 2).column_letter].width = max(10, s.column_dimensions[s.cell(1, i + 2).column_letter].width or 0)
    s.column_dimensions['A'].width = 60; s.column_dimensions['B'].width = 10; s.column_dimensions['C'].width = 11
wb.save(OUT); print('saved', OUT, len(data), 'rows')
