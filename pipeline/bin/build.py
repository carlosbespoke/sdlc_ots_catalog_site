import sys, os, csv, collections
B = sys.argv[1]; sys.path.insert(0, f'{B}/bin')
from taxo_data import T, BATCH, SRE
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
sheet = {r[0]: r for r in csv.reader(open(f'{B}/sheet.csv')) if len(r) > 6 and 'horizon' in r[6]}
look = {l.split('\t')[0]: l.split('\t') for l in open(f'{B}/lookup.tsv').read().splitlines()}
def cust(b):
    return 'xAI' if 'xai' in b.lower() else 'Cohere' if 'cohere' in b.lower() else 'Internal (alpharecon)'
H = ["Task","Horizon","Batch","Main taxonomy (sheet)","Primary language","Other languages","SDLC phase","Change type","Domain","Tech stack","Upstream project","Benchmark family","Grading approach","Environment shape","Customer hint (from batch name)"]
rows = []
for name, r in sheet.items():
    b = look[name][2]; t = T[name]
    if b == 'SRE-xai-ots':
        k = 'db' if name.startswith('db-migration') else 'live' if name.startswith(('qfn-','livesvc-')) else 'iac'
        fam = SRE[k]
    else:
        fam = BATCH[b]
    rows.append([name, r[6], b, r[1].replace('\n',' / ').strip(), *t[:6], t[6] or '(synthetic / not identified)', *fam, cust(b)])
rows.sort(key=lambda x: (x[2], x[0]))
missing = set(sheet) - set(T); assert not missing, missing
with open(f'{B}/task_taxonomies.csv','w',newline='') as f:
    w = csv.writer(f); w.writerow(H); w.writerows(rows)
wb = Workbook(); ws = wb.active; ws.title = 'Taxonomies'
ws.append(H)
for x in rows: ws.append(x)
hdr = PatternFill('solid', fgColor='1F3864')
for c in ws[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = hdr; c.alignment = Alignment(wrap_text=True, vertical='top')
widths = [42,20,34,26,24,20,20,30,36,48,28,36,48,36,18]
for i,wd in enumerate(widths): ws.column_dimensions[chr(65+i)].width = wd
for row in ws.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    row[1].hyperlink = row[1].value; row[1].value = row[1].value.rsplit('/',1)[-1][:8]; row[1].font = Font(color='0563C1', underline='single')
ws.freeze_panes = 'B2'; ws.auto_filter.ref = ws.dimensions
s = wb.create_sheet('Summary')
for col in ["Primary language","SDLC phase","Change type","Benchmark family","Domain","Customer hint (from batch name)"]:
    i = H.index(col); cnt = collections.Counter(x[i] for x in rows)
    s.append([col, 'Tasks']); s[s.max_row][0].font = Font(bold=True); s[s.max_row][1].font = Font(bold=True)
    for k, v in cnt.most_common(): s.append([k, v])
    s.append([])
s.column_dimensions['A'].width = 60
d = wb.create_sheet('Definitions')
for line in [
 ("Primary language","Language the agent writes. Migrations show the target; the source is under Other languages. ProgramBench reimplementation lets the agent choose its language (the reference tool's language is shown)."),
 ("SDLC phase","Design · Implementation · Maintenance (evolving/fixing to spec) · Debugging (root cause analysis) · Refactoring · Migration · Performance · Deployment & operations"),
 ("Change type","The concrete deliverable: bug fix, feature, refactor, port, reimplementation, optimization, DB migration, policy remediation, incident recovery."),
 ("Domain","Application or problem area of the codebase."),
 ("Tech stack","Main frameworks, runtimes, databases and tools in the environment (from Dockerfile, task.toml tags and instructions)."),
 ("Benchmark family","Task family, from the batch, with the public benchmark it resembles where there is one."),
 ("Grading approach","How the verifier scores the task (from batch conventions and the sheet notes)."),
 ("Environment shape","What the agent is given: a single repo, a reference binary, an offline IaC plan or a live multi-service stack."),
 ("Customer hint","Inferred only from the batch name (xai / cohere). Not confirmed against Horizon project metadata."),
 ("Sources","Horizon API (api/tasks/{id}, task files: instruction.md, task.toml, Dockerfile, file listing) plus the 'Task purpose' column of the sheet. pdk-parquetdb-schema, pdk-buildbot-cluster-wide-locks and livesvc-medlink-vault-postgres-access-model have no files in their active version, so they are classified from the sheet text only.")]:
    d.append(list(line))
d.column_dimensions['A'].width = 22; d.column_dimensions['B'].width = 120
for row in d.iter_rows():
    row[0].font = Font(bold=True)
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
wb.save(f'{B}/task_taxonomies.xlsx')
for col in ["Primary language","SDLC phase","Change type","Benchmark family"]:
    i = H.index(col); print(col, dict(collections.Counter(x[i] for x in rows).most_common()))
print(len(rows))
