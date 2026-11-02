import sys, collections
sys.path.insert(0, sys.argv[1] + '/bin')
from hier import CAT
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
ROLE_BY_CAT = {
"AI agents & retrieval":"ML / AI Engineer","Machine learning & MLOps":"ML / AI Engineer","Medical imaging & healthcare":"Research Software Engineer",
"Scientific computing":"Research Software Engineer","Statistics & numerical methods":"Research Software Engineer","Geospatial":"Research Software Engineer",
"Sports analytics":"Data Engineer","Analytics engineering":"Analytics Engineer","Data pipelines & ETL":"Data Engineer","Data validation":"Data Engineer",
"Data formats & serialization":"Library / Backend Engineer","Parser security hardening":"Security Engineer","Compression & data integrity":"Systems Engineer",
"Probabilistic data structures":"Library / Backend Engineer","Graph algorithms":"Library / Backend Engineer","Databases & storage engines":"Database Engineer",
"SQL tooling":"Database Engineer","Compilers & language runtimes":"Compiler / Language Engineer","Logic programming":"Compiler / Language Engineer",
"Memory management":"Systems Engineer","Binary analysis":"Systems Engineer","Build systems":"Build & Release Engineer","CI/CD":"Build & Release Engineer",
"Software supply chain":"Build & Release Engineer","API tooling":"Developer Tools Engineer","CLI tooling":"Developer Tools Engineer",
"Configuration management":"Developer Tools Engineer","Filesystems":"Systems Engineer",
"Cloud infra: containers & self-hosted platforms":"Platform Engineer","Cloud infra: serverless & event-driven":"Platform Engineer","Cloud infra: AWS platform stacks":"Platform Engineer",
"Cloud security & compliance":"Cloud Security Engineer","Secrets & access control":"Cloud Security Engineer","Cryptography & secure protocols":"Security Engineer",
"Secret scanning":"Security Engineer","Monitoring & observability":"Observability Engineer","Messaging & event streaming":"Backend Engineer",
"Job scheduling":"Backend Engineer","Calendaring & recurrence":"Library / Backend Engineer","Rate limiting":"Backend Engineer","Networking & HTTP":"Backend Engineer",
"IoT & smart home":"Embedded / IoT Engineer","Workflow automation":"Backend Engineer","Payments & banking":"Backend Engineer","Web applications":"Backend Engineer",
"Collaborative documents":"Full-stack Engineer","Media processing":"Media Software Engineer","Frontend & UI state":"Frontend Engineer",
"Education tooling":"Full-stack Engineer","Web crawling":"Backend Engineer",
}
SENIORITY = {
"Failure-proofing":"Staff+","Live system change":"Staff+","Incident response":"Staff+","Rebuild a program from its binary":"Staff+",
"NEW: Multi-bug diagnosis & fault localization":"Senior","Evolve a repo from one release to the next":"Senior","NEW: State-preserving IaC change":"Senior",
"NEW: Docs-vs-code drift repair":"Senior","Feature development across several PRs":"Senior","NEW: CPU performance optimization":"Senior",
"Add OpenTelemetry instrumentation":"Senior","On-call root cause analysis":"Mid–Senior","NEW: Data pipeline repair / extension":"Mid–Senior",
}
WHY = {
"Staff+":"Open-ended: designs across services or rebuilds a whole program, and owns correctness under failure, live traffic or no source code.",
"Senior":"Multi-part change in an unfamiliar codebase: several bugs, a full port, a state-preserving refactor or a spec-wide repair.",
"Mid–Senior":"Well-scoped: one root cause or one pipeline behaviour, plus a regression test or note.",
}
def role(name, catname, shape, change):
    base = ROLE_BY_CAT[catname]
    if shape == "Failure-proofing":
        p = "Storage / Systems Engineer" if "diskfs" in name else "Distributed Systems Engineer"
    elif name.startswith("db-migration"): p = "Database Reliability Engineer"
    elif name.startswith("livesvc-"): p = "Platform Engineer"; base = "Cloud Security Engineer"
    elif shape == "Incident response": p = "SRE"
    elif shape == "NEW: State-preserving IaC change":
        p = "Cloud Security Engineer" if change == "Policy remediation" else "Platform Engineer"
    elif shape == "NEW: Data pipeline repair / extension":
        p = "Analytics Engineer" if "-dbt" in name else "Data Engineer"
        if catname in ("Databases & storage engines",): base = "Database Engineer"
        elif catname == "Sports analytics": base = "Data Scientist"
        elif catname in ("Scientific computing","Medical imaging & healthcare"): base = "Research Software Engineer"
    elif shape == "NEW: CPU performance optimization": p = "Performance Engineer"
    else: p = base
    return p, (base if base != p else "")
F = '/Users/carlos/code/sdlc_final_samples/task_taxonomies_v3.xlsx'
wb = load_workbook(F); ws = wb['Taxonomies']
H = [c.value for c in ws[1]]
if 'Primary role' in H: raise SystemExit('already added')
iCat, iShape, iChg = H.index('Domain category (50+3)'), H.index('Task shape (SDLC Task shapes sheet)'), H.index('Change type')
at = H.index('Task shape match') + 2
cols = ['Primary role','Secondary role','Seniority']
ws.insert_cols(at, 3)
fill = PatternFill('solid', fgColor='7F6000')
for j, n in enumerate(cols):
    c = ws.cell(1, at + j, n); c.font = Font(bold=True, color='FFFFFF'); c.fill = fill; c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.column_dimensions[c.column_letter].width = [30,28,12][j]
rows = []
for r in range(2, ws.max_row + 1):
    name = ws.cell(r, 2).value; cat = ws.cell(r, iCat+1).value; shape = ws.cell(r, iShape+1).value; chg = ws.cell(r, iChg+1).value
    p, s = role(name, cat, shape, chg); sen = SENIORITY[shape]
    for j, v in enumerate((p, s, sen)):
        c = ws.cell(r, at + j, v); c.alignment = Alignment(wrap_text=True, vertical='top')
    rows.append((name, p, s, sen, shape))
ws.auto_filter.ref = ws.dimensions
if 'Roles' in wb.sheetnames: del wb['Roles']
t = wb.create_sheet('Roles', 3)
hdr = PatternFill('solid', fgColor='1F3864')
t.append(['Primary role','Tasks','Staff+','Senior','Mid–Senior','Also appears as secondary role','Example tasks'])
pc = collections.Counter(x[1] for x in rows); sc = collections.Counter(x[2] for x in rows if x[2])
for role_, n in pc.most_common():
    by = collections.Counter(x[3] for x in rows if x[1] == role_)
    ex = ', '.join([x[0] for x in rows if x[1] == role_][:4])
    t.append([role_, n, by.get('Staff+',0), by.get('Senior',0), by.get('Mid–Senior',0), sc.get(role_, 0), ex])
for role_ in sorted(set(sc) - set(pc)):
    t.append([role_, 0, 0, 0, 0, sc[role_], ', '.join(x[0] for x in rows if x[2] == role_)[:200]])
t.append([]); t.append(['Seniority','Rule'])
t[t.max_row][0].font = Font(bold=True); t[t.max_row][1].font = Font(bold=True)
for k, v in WHY.items(): t.append([k, v])
t.append(['Principal', 'Not assigned. Principal scope means org-wide technical direction and trade-offs across systems and teams; no shortlist task asks for that. The Staff+ tasks are the closest.'])
for c in t[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = hdr
for i, w in enumerate([32,8,8,8,11,16,90]): t.column_dimensions[chr(65+i)].width = w
for row in t.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
d = wb['Definitions']
for line in [("Primary role","The profession of the engineer who would normally own this problem. Mostly set by domain; set by task shape for operations, IaC, data-pipeline, failure-proofing and performance work."),
             ("Secondary role","A second discipline the task clearly needs (usually the domain specialist when the role came from the task shape)."),
             ("Seniority","Level the task demands (Mid–Senior, Senior, Staff+), from the task shape. See the Roles tab for the rules.")]:
    d.append(list(line)); d[d.max_row][0].font = Font(bold=True)
    for c in d[d.max_row]: c.alignment = Alignment(wrap_text=True, vertical='top')
wb.save(F)
print(pc.most_common()); print(collections.Counter(x[3] for x in rows))
