import sys, csv, collections
B = sys.argv[1]; sys.path.insert(0, f'{B}/bin')
from hier import P, R, CAT, DOM, shape
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
SRC = '/Users/carlos/code/sdlc_final_samples/task_taxonomies_v2.xlsx'
wb = load_workbook(SRC); ws = wb['Taxonomies']
H = [c.value for c in ws[1]]
iD, iF, iC = H.index('Domain'), H.index('Benchmark family'), H.index('Change type')
newcols = ['Domain category (50+3)','Domain super-group (revised)','Domain super-group (previous)','Task shape (SDLC Task shapes sheet)','Task shape category','Task shape match']
at = iD + 2  # insert right after Domain
ws.insert_cols(at, len(newcols))
hdr = PatternFill('solid', fgColor='1F3864'); add = PatternFill('solid', fgColor='375623')
for j, n in enumerate(newcols):
    c = ws.cell(1, at + j, n); c.font = Font(bold=True, color='FFFFFF'); c.fill = add; c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.column_dimensions[c.column_letter].width = [30,30,30,40,26,48][j]
rows = []
for r in range(2, ws.max_row + 1):
    dom = ws.cell(r, iD + 1).value; fam = ws.cell(r, iF + 1 + (len(newcols) if iF >= iD + 1 else 0)).value
    name = ws.cell(r, 2).value
    cid = DOM[dom]; cname, prev, rev = CAT[cid]
    sh = shape(name, fam, '')
    assert sh[0] != '?', (name, fam)
    vals = [cname, R[rev], P[prev], *sh]
    for j, v in enumerate(vals):
        c = ws.cell(r, at + j, v); c.alignment = Alignment(wrap_text=True, vertical='top')
    rows.append((name, dom, cid, rev, prev, *sh))
ws.auto_filter.ref = ws.dimensions
# Hierarchy tab
if 'Domain hierarchy' in wb.sheetnames: del wb['Domain hierarchy']
h = wb.create_sheet('Domain hierarchy', 1)
h.append(['Super-group (revised)','Domain category','Tasks','Super-group (previous)','Moved?','Raw domains (as in Domain column)'])
cnt = collections.Counter(x[2] for x in rows)
rawby = collections.defaultdict(list)
for d, c in DOM.items(): rawby[c].append(d)
order = sorted(CAT, key=lambda k: (list(R).index(CAT[k][2]), k))
for k in order:
    n, prev, rev = CAT[k]
    pv = P[prev] if prev else '(new – from task-shapes sheet)'
    moved = 'Added (gap)' if not prev else ('Moved' if pv != R[rev] and not (prev==1 and rev=='A') and not (prev==2 and rev=='D') and not (prev==3 and rev=='E') and not (prev==4 and rev=='F') and not (prev==5 and rev=='G') and not (prev==6 and rev=='H') and not (prev==7 and rev=='I') and not (prev==8 and rev=='J') else '')
    h.append([R[rev], n, cnt.get(k, 0), pv, moved, '; '.join(sorted(rawby.get(k, []))) or '—'])
for c in h[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = hdr
for i, w in enumerate([32,44,8,36,14,90]): h.column_dimensions[chr(65+i)].width = w
for row in h.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    if row[4].value: row[4].font = Font(bold=True, color='C00000')
h.freeze_panes = 'A2'
# Task shape coverage tab
if 'Task shape coverage' in wb.sheetnames: del wb['Task shape coverage']
t = wb.create_sheet('Task shape coverage', 2)
SHEET_SHAPES = [("Rebuild a program from its binary","Greenfield / reimplementation"),("Long-horizon terminal work","Long-horizon engineering"),("Long-horizon CLI projects","Long-horizon engineering"),("Extending your own code over many checkpoints","Maintainability / code quality"),("Evolve a repo from one release to the next","Software evolution"),("Feature development across several PRs","Feature development"),("Feature requests written like vibe-coding prompts","Feature development"),("On-call root cause analysis","SRE / incident response"),("Root cause with a verified causal path","SRE / incident response"),("Incident response","SRE / incident response"),("Failure-proofing","Reliability"),("Fix failing CI builds","CI/CD"),("Add OpenTelemetry instrumentation","Observability"),("Hard terminal tasks (mixed domains)","Mixed SWE / ML / science"),("Long-horizon Android work","Mobile / migration"),("Engineering tasks in scientific codebases","Scientific software"),("Fix concurrency bugs in real code","Debugging / concurrency"),("Write multi-GPU kernels","Performance / GPU"),("Write single-GPU kernels against realistic baselines","Performance / GPU"),("Formally verified code in Lean and Verus","Formal verification"),("Hardware RTL design and verification","Hardware / RTL"),("Live system change","Operations / migration")]
sc = collections.Counter(x[5] for x in rows)
t.append(['Task shape','Category','Source','Tasks in shortlist (exact + near)','Exact','Near'])
ex = collections.Counter(x[5] for x in rows if x[7].startswith('Exact')); nr = collections.Counter(x[5] for x in rows if x[7].startswith('Near'))
for s, c in SHEET_SHAPES: t.append([s, c, 'SDLC Task shapes sheet', sc.get(s, 0), ex.get(s, 0), nr.get(s, 0)])
for s in sorted({x[5] for x in rows if x[5].startswith('NEW')}):
    cat = next(x[6] for x in rows if x[5] == s); t.append([s, cat, 'Proposed (not in sheet)', sc[s], '', ''])
# science note: scientific-codebase tasks by domain
sci = sum(1 for x in rows if CAT[x[2]][2] == 'F')
t.append([]); t.append(['Note', f'"Engineering tasks in scientific codebases" is a domain, not a shape. {sci} shortlist tasks fall in the Scientific & ML software super-group (see the Domain super-group column).'])
for c in t[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = hdr
for i, w in enumerate([52,30,26,16,8,8]): t.column_dimensions[chr(65+i)].width = w
for row in t.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    if row[3].value == 0: row[3].font = Font(bold=True, color='C00000')
d = wb['Definitions']
for line in [("Domain category (50+3)","The 50 merged domain categories, plus 3 added from the task-shapes sheet with no shortlist tasks yet (GPU kernels, Hardware RTL, Mobile apps)."),
             ("Domain super-group","Revised: 10 groups. Previous: the 8-group version. 'Domain hierarchy' tab shows every move."),
             ("Task shape","Second axis: what the agent has to do, using the shapes in the 'SDLC Task shapes' sheet. 'NEW:' marks shapes proposed because the shortlist has tasks no sheet shape covers."),
             ("Task shape match","Exact, Near (with the reason), or New.")]:
    d.append(list(line))
    d[d.max_row][0].font = Font(bold=True)
    for c in d[d.max_row]: c.alignment = Alignment(wrap_text=True, vertical='top')
wb.save('/Users/carlos/code/sdlc_final_samples/task_taxonomies_v3.xlsx')
print(collections.Counter(R[x[3]] for x in rows).most_common())
print(sorted(sc.items(), key=lambda x: -x[1]))
