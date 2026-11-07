# Assemble the catalog pages (catalog/*.md), the overview (catalog/README.md) and the CSVs from cat/stats.json and cat/text.json.
import csv, shutil, unicodedata
from common import *
from codeify import codeify as _cf
from noname import strip_names
codeify = lambda x: _cf(strip_names(x))
OUT = f'{H}/catalog'
S = json.load(open(f'{H}/cat/stats.json')); TXT = json.load(open(f'{H}/cat/text.json'))
NUMW = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten'}
def table(head, rows, left=False, text_cols=1, align=None):
    """align: optional string of l/r per column; otherwise the first text_cols columns are left-aligned."""
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join({'l': '---', 'c': ':---:'}.get(align[i], '---:') if align else ('---' if i < text_cols or left else '---:') for i in range(len(head))) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)
def kpi(value, label): return f'<div class="kpi"><div class="kpi-value">{value.replace("<", "&lt;")}</div><div class="kpi-label">{label}</div></div>'
def instruction(t):
    """The sample's instruction.md: the copy checked against the selected version, else the shipped sample's own."""
    for p in (f"{H}/super/tasks/{t['task_id']}/instruction.md" if t.get('earlier') == 'super' else '', f"{G}/audit/instr/{t['id']}.md", f"{P}/show/{t['name']}/instruction.md", f"{G}/show/{t['name']}/instruction.md",
              f"{G}/samples/main/{t['task_id']}/instruction.md", f"{G}/samples/attached/{t['task_id']}/instruction.md"):
        if p and os.path.exists(p) and os.path.getsize(p): return open(p).read().strip()
def prompt_md(src):
    """Render an instruction as Markdown inside the page: demote its headings below the page's own, escape stray HTML."""
    out, fence = [], None
    for line in src.splitlines():
        m = re.match(r'^\s*(`{3,}|~{3,})', line)
        if m:
            if fence is None: fence = m.group(1)[0] * len(m.group(1))
            elif line.strip().startswith(fence): fence = None
            out.append(line); continue
        if fence is not None: out.append(line); continue
        h = re.match(r'^(#{1,6})\s+(.*)$', line)
        if h:
            out.append('#' * min(6, len(h.group(1)) + 4) + ' ' + h.group(2) if len(h.group(1)) <= 2 else f'**{h.group(2).strip()}**'); continue
        parts = re.split(r'(`[^`]*`)', line)
        out.append(''.join(p if i % 2 else p.replace('<', '&lt;').replace('>', '&gt;') for i, p in enumerate(parts)))
    if fence is not None: out.append(fence)
    return '\n'.join(out).strip()
def anchor(title):
    """The heading id build_site.py gives a heading with this text (same rule)."""
    slug = re.sub(r'[^\w\s-]', '', unicodedata.normalize('NFKC', title).lower())
    return re.sub(r'[-\s]+', '-', slug).strip('-') or 'section'
ex_title = lambda i, t: f"Example {i}: {t['category']} ({t['language'].replace('HCL (Terraform)', 'Terraform')})"
def top(s):
    """The model with the most runs in the catalog: the one the headline average reward is about."""
    return next((m for m in s['models'] if m['graded']), None)
def langs(s):
    L_ = s['language'][:3]
    choice = next((x for x in L_ if x['value'] == "Agent's choice"), None); rest = [x for x in L_ if x is not choice]
    named = ', '.join(f"{x['value']} ({x['pct']:.0f}%)" for x in rest[:-1]) + (' and ' if len(rest) > 1 else '') + (f"{rest[-1]['value']} ({rest[-1]['pct']:.0f}%)" if rest else '')
    if choice: return f"In {choice['pct']:.0f}% of tasks the agent chooses the language; the most common fixed languages are {named}."
    return f"The language is {named}." if len(rest) == 1 else f"The main languages are {named}."
nob = lambda x: '\n'.join(l for l in x.splitlines() if l.strip())  # raw HTML blocks must not contain blank lines
CX_CSS, CX_JS = open(f'{H}/bin/charts.css').read(), open(f'{H}/bin/charts.js').read()
def chart(kind, title, extra=''):
    return nob(f'<div class="cx" data-chart="{kind}"{extra}>\n<div class="fig-head"><span class="lab">Interactive figure</span><h4>{title}</h4></div>\n<div class="fig-box" data-body></div>\n</div>') + '\n'
def runtime(data):
    return nob('<div data-chart-runtime>\n<style>' + CX_CSS + '</style>\n<script type="application/json" data-chart-data>' + json.dumps(data, separators=(',', ':'))
               + '</script>\n<script>' + CX_JS + '</script>\n</div>') + '\n'
def page_data(s):
    """Per-task rows for a catalog page: domain, sub-domain, language, seniority, scores and turns per model."""
    tr = s['task_rows']; models = [m['model'] for m in s['models']]
    for r in tr:
        for m in list(r['scores']) + list(r['turns']):
            if m not in models: models.append(m)
    dims = {k: sorted({r[f] for r in tr}) for k, f in (('g', 'sg'), ('c', 'cat'), ('l', 'lang'), ('s', 'sen'))}
    rows = [[dims['g'].index(r['sg']), dims['c'].index(r['cat']), dims['l'].index(r['lang']), dims['s'].index(r['sen']),
             {models.index(m): v for m, v in r['scores'].items() if v}, {models.index(m): v for m, v in r['turns'].items()}] for r in tr]
    return {'cross': True, 'models': models, 'dims': dims, 'tasks': rows, 'minTasks': s['min_tasks'], 'sat': 0.8, 'bin': 50, 'xmax': 1000, 'threshold': s['turns']['threshold']}
_g = collections.Counter()
for s_ in S.values():
    for m_ in s_['models']: _g[m_['model']] += m_['graded']
CARD_ORDER = [m for m, _ in _g.most_common()]  # the overview's order: most graded runs first
for slug, s in S.items():
    W = TXT[slug]; n = s['tasks']; MIN = s['min_tasks']; tm = top(s); L = []
    L.append(f"# {s['name']}\n")
    L.append('## Executive summary\n')
    L.append('<div class="kpis">' + kpi(f"{n:,}", 'Tasks') + ''.join(kpi(pct(m['reward']), f"{m['model']} average reward" + (f" ({m['tasks_graded']} tasks)" if m['tasks_graded'] < MIN else ''))
             for m in sorted((m for m in s['models'] if m['tasks_graded']), key=lambda m: CARD_ORDER.index(m['model']))) + '</div>\n')
    L.append(W['work'] + ' ' + langs(s) + '\n')
    cov = (f"Every task has graded runs." if s['tasks_graded'] == n else f"{s['tasks_graded']:,} of the {n:,} tasks have graded runs from at least one model.")
    if tm:
        fails = f" and scores 0 on every run of {pct(tm['tasks_0'] / tm['tasks_graded'])} of the {tm['tasks_graded']:,} tasks it ran" if tm['tasks_0'] else f" on the {tm['tasks_graded']:,} tasks it ran"
        L.append(f"{cov} The model with the most runs here, {tm['model']}, has an average reward of {pct(tm['reward'])} over {tm['graded']:,} graded runs{fails}.\n")
    L.append('## Why this catalog\n')
    L.append('### Problems engineers face\n'); L.append(W['problems'] + '\n')
    L.append('### How the tasks reproduce them\n'); L.append(W['how'] + '\n')
    L.append('### Typical prompts\n'); L.append('\n'.join(f'- {p}' for p in W['prompts']) + '\n')
    L.append('## Domain breakdown\n')
    d0 = s['domain'][0]
    L.append(f"The tasks span {NUMW.get(len(s['domain']), len(s['domain']))} domain{'s' if len(s['domain']) > 1 else ''}."
             + (f" The largest, {d0['super_group']}, makes up {d0['pct']:.0f}% of the catalog.\n" if len(s['domain']) > 1 else '\n'))
    L.append(chart('bars', 'Share of tasks by domain', ' data-dims="g>c=Domain" data-hint="Click a domain to filter the charts on this page; use the arrow to see its sub-domains."'))
    L.append('## Language and seniority\n')
    L.append(chart('bars', 'Primary language and seniority', ' data-dims="l:8=Primary language,s=Seniority"'))
    for key, title in [('language', 'Primary language'), ('seniority', 'Seniority')]:
        L.append(f'### {title}\n'); L.append(table([title, '% of catalog'], [[x['value'], f"{100 * x['tasks'] / n:.1f}%"] for x in s[key]]) + '\n')
    L.append('## Model average reward across the catalog\n')
    M = [m for m in s['models'] if m['tasks_graded'] >= MIN]; few = [m for m in s['models'] if 0 < m['tasks_graded'] < MIN]
    L.append(f"A model's average reward is average@k: on each task, the mean grader score over its graded runs, with partial credit counted as scored; then the mean over the tasks it ran. Runs that errored are left out. Models are listed by number of runs, and a model needs graded runs on {NUMW[MIN]} or more tasks for a row.\n")
    if M:
        Q = lambda a, b: 'n/a' if not b else f"{100 * a / b:.0f}%"
        L.append(table(['Model', 'Tasks run', 'Graded runs', 'Average reward', 'Tasks at 0%', 'Tasks at 20-80%', 'Tasks at 100%'],
            [[m['model'], f"{m['tasks_graded']:,}", f"{m['graded']:,}", pct(m['reward']), Q(m['tasks_0'], m['tasks_graded']), Q(m['tasks_20_80'], m['tasks_graded']), Q(m['tasks_100'], m['tasks_graded'])] for m in M]) + '\n')
        sat = [m['model'] for m in M if m['tasks_100'] / m['tasks_graded'] >= 0.8]
        L.append(chart('reward', 'Per-task average reward by model'))
        if sat: L.append(f"The chart starts with {' and '.join(sat)} hidden, because {'it scores' if len(sat) == 1 else 'they score'} full marks on every run of 80% or more of {'its' if len(sat) == 1 else 'their'} tasks. Click {'its' if len(sat) == 1 else 'their'} button to show {'it' if len(sat) == 1 else 'them'}.\n")
    if few: L.append(f"Also run on fewer than {NUMW[MIN]} tasks: " + ', '.join(f"{m['model']} ({m['tasks_graded']} task{'s' if m['tasks_graded'] > 1 else ''}, {pct(m['reward'])} average reward over {m['graded']} runs)" for m in few) + '.\n')
    TT = s['turns']
    L.append('## Turn counts and long-horizon tasks\n')
    if TT['tasks_with_turns']:
        k = TT['tasks_with_turns']
        L.append(f"A task's turn count is the average over its completed runs, from every model. A task is long horizon when that average is {TT['threshold']} or more turns. {k:,} of the {n:,} tasks have a completed run.\n")
        L.append(table(['Measure', 'Value'], [['Average turn count', f"{TT['mean_of_task_means']:.1f}"], ['Median turn count', f"{TT['median_of_task_means']:.1f}"],
            ['Range', f"{TT['min_task_mean']:.0f} to {TT['max_task_mean']:.0f}"], [f"Long-horizon tasks ({TT['threshold']}+ turns)", f"{100 * TT['long_horizon_tasks'] / k:.0f}% of tasks"]]) + '\n')
        L.append(chart('turns', 'Turns per task', ' data-group="Domain"'))
        L.append(table(['Model', '% of tasks', 'Mean turns', f"% of runs with {TT['threshold']}+ turns"],
            [[m['model'], (f"{100 * m['tasks'] / k:.0f}%" if 100 * m['tasks'] / k >= 0.5 else '<1%'), f"{m['mean']:.1f}", f"{100 * m['runs_200_plus'] / m['runs']:.0f}%"] for m in TT['by_model']]) + '\n')
    L.append('## Sample tasks\n')
    if not s['showcase']: L.append('This catalog has no sample task yet.\n')
    for i, t in enumerate(s['showcase'], 1):
        L.append(f"### {ex_title(i, t)}\n")
        L.append(table(['Field', 'Value'], [
            ['Task id', f"[`{t['task_id']}`]({t['url']})" if t.get('url') else f"`{t['task_id']}`"], ['Final category', t['final']], ['Domain', t['super_group']], ['Sub-domain', t['category']],
            ['Language', t['language']], ['Seniority', t['seniority']],
            ['Turn count', (', '.join(f"{v:.0f} ({m})" for m, v in t['turns']['by_model'].items()) if t['turns'] else 'no completed run')],
            ['Long horizon', ('yes' if t['turns']['mean'] >= 200 else 'no') if t['turns'] else 'n/a']], left=True) + '\n')
        ins = instruction(t)
        L.append('#### Prompt\n')
        L.append('<details open><summary>Full instruction given to the agent (instruction.md)</summary>\n<div class="prompt-md">\n\n' + (prompt_md(ins) if ins else '`instruction.md` not found in the selected version.') + '\n\n</div>\n</details>\n')
        L.append('#### Average reward\n')
        g = [m for m in t['models'] if m['graded']]
        L.append(table(['Model', 'Graded runs', 'Average reward'], [[m['model'], m['graded'], pct(m['reward'])] for m in g]) + '\n' if g else 'No graded runs on the selected version.\n')
        L.append('#### Environment\n')
        src = next((p for p in (f"{H}/super/diagrams/{t['task_id']}/diagram.svg", f"{G}/diagrams/{t['task_id']}/diagram.svg") if os.path.exists(p)), '')
        if os.path.exists(src):
            shutil.copyfile(src, f"{OUT}/assets/env-{t['task_id']}.svg"); L.append(f"![How the task works](assets/env-{t['task_id']}.svg)\n")
        else: L.append('_Diagram pending._\n')
    L.append(runtime(page_data(s)))
    open(f'{OUT}/{slug}.md', 'w').write('\n'.join(L))
    print(slug, n, 'tasks', len(s['showcase']), 'samples')
# overview
TOT = sum(s['tasks'] for s in S.values())
allm = collections.defaultdict(lambda: [0, 0, set(), []])  # graded, passed, tasks, per-task rates
for slug, s in S.items():
    for t in TASKS:
        if t['catalog'] != s['title']: continue
        for m, v in runs(t['id']).items(): a = allm[m]; a[0] += len(v); a[1] += sum(x for x, _ in v); a[2].add(t['id']); a[3].append(sum(x for x, _ in v) / len(v))
graded = sum(v[0] for v in allm.values())
L = ['# Coding OTS RL Envs\n']
L.append('<div class="kpis">' + kpi(f"{TOT:,}", 'Tasks') + ''.join(kpi(pct(sum(v[3]) / len(v[3])), f'{m} average reward') for m, v in sorted(allm.items(), key=lambda kv: -kv[1][0])) + '</div>\n')
LANG = collections.Counter(); SEN = collections.Counter()
for s_ in S.values():
    for x in s_['language']: LANG[x['value']] += x['tasks']
    for x in s_['seniority']: SEN[x['value']] += x['tasks']
AC = "Agent's choice"
lp = lambda *ks: f"{100 * sum(LANG[k] for k in ks) / TOT:.0f}%"
allt0 = [m for s_ in S.values() for m in s_['turns']['task_means']]
T_ = {k: s_['tasks'] for k, s_ in S.items()}; TM = {k: s_['turns']['mean_of_task_means'] for k, s_ in S.items()}
L.append('## Executive summary\n')
L.append("This OTS catalog helps AI coding agents develop capabilities on long, senior-level software work: rebuilding whole programs, fixing faults in real codebases and changing live systems without breaking them.\n")
L.append(f"The tasks fall into {NUMW[len(S)]} catalogs. In ProgramBench ({T_['programbench']} tasks) the agent rebuilds a program from how it behaves. "
         f"In Debugging ({T_['debugging']}) it finds and fixes faults, and in Infrastructure as code ({T_['infrastructure-as-code']}) it restructures deployed Terraform without changing what runs. "
         f"Feature implementation ({T_['feature-implementation']}) adds capabilities to existing libraries, and System design ({T_['system-design']}) keeps running services correct through crashes and retries. Data engineering ({T_['data-engineering']}) and Migration ({T_['migration']}) cover data pipelines and ports to another language.\n")
L.append(f"Almost all tasks are senior engineering work in a few languages. Senior engineers are the target for {100 * SEN['Senior'] / TOT:.0f}% of tasks and staff engineers for {100 * SEN['Staff+'] / TOT:.0f}%. "
         f"Go, Terraform and Python account for {lp('Go', 'HCL (Terraform)', 'Python')} of tasks, and Rust, C and C++ for another {lp('Rust', 'C', 'C++')}.\n")
L.append(f"The catalogs include long-horizon coding tasks. An agent averages {sum(allt0) / len(allt0):.0f} turns (one model reply plus its tool calls) on a task, and {100 * sum(m >= 200 for m in allt0) / len(allt0):.0f}% of tasks average 200 turns or more. "
         f"ProgramBench and System design run longest, at about {round((TM['programbench'] + TM['system-design']) / 2, -1):.0f} turns. Infrastructure as code tasks are the shortest, at {TM['infrastructure-as-code']:.0f} turns.\n")
L.append('## Catalogs\n')
tt = lambda s: f"{s['turns']['mean_of_task_means']:.0f}" if s['turns']['tasks_with_turns'] else 'n/a'
L.append(table(['Catalog', 'Tasks', 'What the tasks do', 'Average turn count'],
    [[f"[{s['name']}]({slug}.md)", f"{s['tasks']:,}", TXT[slug]['one'], tt(s)] for slug, s in S.items()]
    + [['**Total**', f"**{TOT:,}**", '', '']], align='lrlr') + '\n')
L.append('## Benchmarks each catalog lifts\n')
L.append(TXT['_bench_intro'] + '\n')
BENCH = TXT['_bench_columns']
L.append(table(['Catalog'] + BENCH, [[s_['name']] + ['✓' if b in TXT[k].get('bench_map', []) else '' for b in BENCH] for k, s_ in S.items() if TXT[k].get('bench_map')],
               align='l' + 'c' * len(BENCH)) + '\n')
L.append('## Model average reward\n')
L.append("Each cell is a model's average reward in one catalog (average@k): on each task, the mean grader score over its graded runs, partial credit included; then the mean over the tasks it ran there.\n")
HM = [m for m, _ in sorted(allm.items(), key=lambda kv: -kv[1][0])]
HEAT = {'models': HM, 'catalogs': [s_['name'] for s_ in S.values()], 'minTasks': S['programbench']['min_tasks'],
        'cells': [[j, HM.index(m['model']), m['graded'], [round(v, 4) for v in m['per_task_rates']]] for j, s_ in enumerate(S.values()) for m in s_['models'] if m['model'] in HM and m['per_task_rates']]}
L.append(chart('heat', 'Average reward by model and catalog', '').replace('<div class="fig-box" data-body></div>',
    '<div class="fig-box" data-body></div>\n<span data-links hidden>' + ''.join(f'<a href="{k}.html">{s_["name"]}</a>' for k, s_ in S.items()) + '</span>'))
L.append(table(['Model', 'Tasks run', 'Graded runs', 'Average reward'], [[m, f"{len(v[2]):,}", f"{v[0]:,}", pct(sum(v[3]) / len(v[3]))] for m, v in sorted(allm.items(), key=lambda kv: -kv[1][0])]) + '\n')
L.append('## Samples\n')
L.append("Each sample is a full task, downloadable from its task id. The average reward is that of the model with the most graded runs on the task.\n")
smp = [(slug, s, i, t) for slug, s in S.items() for i, t in enumerate(s['showcase'], 1)]
def best(t):
    g = [m for m in t['models'] if m['graded']]  # the model with the most graded runs; a tie goes to the one with more runs
    return max(g, key=lambda m: m['graded']) if g else None
L.append(table(['Catalog', 'Example', 'Task id', 'Model with most graded runs', 'Average reward'],
    [[s['name'], f"[{ex_title(i, t)}]({slug}.md#{anchor(ex_title(i, t))})", f"[`{t['task_id']}`]({t['url']})" if t.get('url') else f"`{t['task_id']}`", (best(t) or {}).get('model', ''),
      f"{pct(best(t)['reward'])} of {best(t)['graded']}" if best(t) else ''] for slug, s, i, t in smp], text_cols=4) + '\n')
allt = [m for s in S.values() for m in s['turns']['task_means']]
L.append('## Turn counts\n')
L.append(f"A task's turn count is the average over its completed runs, from every model. Across all catalogs the average is {sum(allt) / len(allt):.0f} turns, and {100 * sum(m >= 200 for m in allt) / len(allt):.0f}% of tasks average 200 turns or more.\n")
# the overview's turns chart: per task, its catalog and each model's turn total and run count
TXM = [m for m, _ in sorted(allm.items(), key=lambda kv: -kv[1][0])]; TXC = [s_['title'] for s_ in S.values()]
txt = []
for t in TASKS:
    if not TURNS[t['id']]: continue
    acc = collections.defaultdict(lambda: [0, 0])
    for q in TURNS[t['id']]: a_ = acc[MM[q['model']]]; a_[0] += q['turn_count']; a_[1] += 1
    txt.append([TXC.index(t['catalog']), 0, 0, 0, {}, {TXM.index(m): v for m, v in acc.items()}])
L.append(chart('turns', 'Turns per task, all catalogs', ' data-group="Catalog"'))
L.append(runtime({'cross': False, 'models': TXM, 'dims': {'g': [s_['name'] for s_ in S.values()]}, 'tasks': txt, 'bin': 50, 'xmax': 1000, 'threshold': 200, 'heat': HEAT}))
open(f'{OUT}/README.md', 'w').write('\n'.join(L))
print('README', TOT, 'tasks,', len(smp), 'samples')
# CSVs: every task with its catalog, metadata and per-model results; and the samples
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
NEWC = json.load(open(f'{H}/cat/new_task_classes.json'))
EX = {t['id']: (s['name'], i, t) for s in S.values() for i, t in enumerate(s['showcase'], 1)}
MODELS = [m for m, _ in sorted(allm.items(), key=lambda kv: -kv[1][0])]
with open(f'{H}/ots_tasks.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Task', 'Horizon task id', 'Task version', 'Newer versions included', 'Catalog', 'Domain', 'Sub-domain', 'Language', 'Seniority', 'Sample', 'Graded runs', 'Average reward (all models)']
               + [f'{m} (average reward, graded runs)' for m in MODELS])
    for slug, cat in CATS:
        for t in sorted([t for t in TASKS if t['catalog'] == cat], key=lambda t: t['name']):
            r = ROWS.get(t['id']); c = NEWC.get(t['name'], {}); rr = runs(t['id']); g = sum(map(len, rr.values())); p = sum(x for v in rr.values() for x, _ in v)
            meta = (r['sg'], r['cat'], r['lang'], r['sen'].replace('–', '-')) if r else (c['sg'], c['cat'], c['lang'], c['sen'])
            ex = EX.get(t['id'])
            w.writerow([t['name'], t['id'], RO[t['id']]['version'], ', '.join(map(str, RO[t['id']].get('extra_versions', []))), cat, *meta, f"{ex[0]}, Example {ex[1]}: {ex[2]['task_id']}" if ex else '', g, f"{100 * p / g:.0f}%" if g else '']
                       + [f"{100 * sum(x for x, _ in rr[m]) / len(rr[m]):.0f}%, {len(rr[m])}" if m in rr else '' for m in MODELS])
with open(f'{H}/samples.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Catalog', 'Example', 'Task id', 'Download URL', 'Horizon task name', 'Horizon task id', 'Horizon URL', 'Selected version', 'Earlier role'])
    for slug, s, i, t in smp:
        w.writerow([s['name'], i, t['task_id'], t.get('url') or '', t['name'], t['id'], f"https://horizon.bespokelabs.ai/tasks/{t['id']}", t['version'], {'main': 'main sample', 'attached': 'attached sample', 'super': 'super-sample'}[t['earlier']]])
print('ots_tasks.csv', sum(1 for _ in open(f'{H}/ots_tasks.csv')) - 1, 'rows; samples.csv', len(smp), 'rows')
