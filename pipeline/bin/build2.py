import sys, os, json, csv, collections
B = sys.argv[1]; sys.path.insert(0, f'{B}/bin')
from taxo_data import T, BATCH, SRE
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
new = json.load(open(f'{B}/v2/new.json'))
look = {l.split('\t')[0]: l.split('\t') for l in open(f'{B}/v2/lookup.tsv').read().splitlines() if l}
oldlook = {l.split('\t')[0]: l.split('\t') for l in open(f'{B}/lookup.tsv').read().splitlines() if l}
oldnames = set(oldlook)
for k in new:
    if k in oldlook and oldlook[k][2] != look[k][2]: print('BATCH MOVED', k, oldlook[k][2], '->', look[k][2])
missing = set(new) - set(T); assert not missing, missing
cust = lambda b: 'xAI' if 'xai' in b.lower() else 'Cohere' if 'cohere' in b.lower() else 'Internal (alpharecon)'
H = ["Rank","Task","Horizon","Batch","Main taxonomy (sheet)","Capability (sheet)","Primary language","Other languages","SDLC phase","Change type","Domain","Tech stack","Upstream project","Benchmark family","Grading approach","Environment shape","Customer hint (from batch name)","Status vs. previous list"]
rows = []
for name, r in new.items():
    b = look[name][2]; t = T[name]
    if b == 'SRE-xai-ots':
        k = 'db' if name.startswith('db-migration') else 'live' if name.startswith(('qfn-','livesvc-')) else 'iac'
        fam = SRE[k]
    else: fam = BATCH[b]
    tax = r['Taxonomy'].split('\nCapability:')
    rank = r['Rank'].replace('.0','')
    rows.append([int(rank) if rank.isdigit() else rank, name, r['Horizon'], b, tax[0].strip(), tax[1].strip() if len(tax) > 1 else '', *t[:6], t[6] or '(synthetic / not identified)', *fam, cust(b), 'Kept' if name in oldnames else 'New'])
rows.sort(key=lambda x: (x[0] if isinstance(x[0], int) else 999))
out = f'{B}/task_taxonomies_v2'
with open(out + '.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(H); w.writerows(rows)
wb = Workbook(); ws = wb.active; ws.title = 'Taxonomies'; ws.append(H)
for x in rows: ws.append(x)
for c in ws[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864'); c.alignment = Alignment(wrap_text=True, vertical='top')
for i, wd in enumerate([6,42,12,30,36,30,24,20,20,30,36,48,28,36,48,36,18,12]): ws.column_dimensions[chr(65+i)].width = wd
for row in ws.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    row[2].hyperlink = row[2].value; row[2].value = row[2].value.rsplit('/',1)[-1][:8]; row[2].font = Font(color='0563C1', underline='single')
ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions
s = wb.create_sheet('Summary')
for col in ["Primary language","SDLC phase","Change type","Benchmark family","Capability (sheet)","Domain","Customer hint (from batch name)","Status vs. previous list"]:
    i = H.index(col)
    s.append([col, 'Tasks']); s[s.max_row][0].font = Font(bold=True); s[s.max_row][1].font = Font(bold=True)
    for k, v in collections.Counter(x[i] for x in rows).most_common(): s.append([k, v])
    s.append([])
s.column_dimensions['A'].width = 60
removed = sorted(oldnames - set(new))
rm = wb.create_sheet('Dropped from list'); rm.append(['Task (in previous Candidates list, not in Shortlist 92)', 'Batch']); rm[1][0].font = Font(bold=True)
for k in removed: rm.append([k, oldlook[k][2]])
rm.column_dimensions['A'].width = 60; rm.column_dimensions['B'].width = 36
d = wb.create_sheet('Definitions')
for line in [
 ("Main taxonomy / Capability","Copied from the sheet's Taxonomy column (Shortlist 92 tab), split at 'Capability:'."),
 ("Primary language","Language the agent writes. Migrations show the target; the source is under Other languages. ProgramBench reimplementation lets the agent choose its language (the reference tool's language is shown)."),
 ("SDLC phase","Design · Implementation · Maintenance (evolving/fixing to spec) · Debugging (root cause analysis) · Refactoring · Migration · Performance · Deployment & operations"),
 ("Change type","The concrete deliverable: bug fix, feature, refactor, port, reimplementation, optimization, DB migration, policy remediation, incident recovery."),
 ("Tech stack","Main frameworks, runtimes, databases and tools (from Dockerfile, task.toml tags and instructions)."),
 ("Benchmark family","Task family, from the batch, with the public benchmark it resembles where there is one."),
 ("Grading approach","How the verifier scores the task (from batch conventions, not from reading each grader)."),
 ("Customer hint","Inferred only from the batch name (xai / cohere). Not confirmed against Horizon project metadata."),
 ("Status","Kept = also in the earlier 'Candidates' list; New = added in Shortlist 92."),
 ("Sources","Horizon API (api/tasks/{id}, task files: instruction.md, task.toml, Dockerfile, file listing) plus the sheet text.")]:
    d.append(list(line))
d.column_dimensions['A'].width = 24; d.column_dimensions['B'].width = 120
for row in d.iter_rows():
    row[0].font = Font(bold=True)
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
wb.save(out + '.xlsx')
for col in ["Primary language","SDLC phase","Benchmark family","Customer hint (from batch name)"]:
    i = H.index(col); print(col, dict(collections.Counter(x[i] for x in rows).most_common()))
print(len(rows), 'rows;', len(removed), 'dropped')
