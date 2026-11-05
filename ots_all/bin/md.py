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
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(('---' if align[i] == 'l' else '---:') if align else ('---' if i < text_cols or left else '---:') for i in range(len(head))) + '|']
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
    """The model with the most runs in the catalog: the one the headline pass rate is about."""
    return next((m for m in s['models'] if m['graded']), None)
def langs(s):
    L_ = s['language'][:3]
    choice = next((x for x in L_ if x['value'] == "Agent's choice"), None); rest = [x for x in L_ if x is not choice]
    named = ', '.join(f"{x['value']} ({x['pct']:.0f}%)" for x in rest[:-1]) + (' and ' if len(rest) > 1 else '') + (f"{rest[-1]['value']} ({rest[-1]['pct']:.0f}%)" if rest else '')
    if choice: return f"In {choice['pct']:.0f}% of tasks the agent chooses the language; the most common fixed languages are {named}."
    return f"The language is {named}." if len(rest) == 1 else f"The main languages are {named}."
for slug, s in S.items():
    W = TXT[slug]; n = s['tasks']; MIN = s['min_tasks']; tm = top(s); L = []
    L.append(f"# {s['name']}\n")
    L.append('## Executive summary\n')
    L.append('<div class="kpis">' + kpi(f"{n:,}", 'Tasks') + kpi(f"{s['tasks_graded']:,}", 'Tasks with graded runs')
             + (kpi(pct(tm['pass_rate']), f"{tm['model']} pass rate") if tm else '') + '</div>\n')
    L.append(W['work'] + ' ' + langs(s) + '\n')
    cov = (f"Every task has graded runs." if s['tasks_graded'] == n else f"{s['tasks_graded']:,} of the {n:,} tasks have graded runs from at least one model.")
    if tm:
        fails = f" and fails every run on {pct(tm['tasks_0'] / tm['tasks_graded'])} of the {tm['tasks_graded']:,} tasks it ran" if tm['tasks_0'] else f" on the {tm['tasks_graded']:,} tasks it ran"
        L.append(f"{cov} The model with the most runs here, {tm['model']}, passes {pct(tm['pass_rate'])} of its {tm['graded']:,} graded runs{fails}.\n")
    L.append('## Why this catalog\n')
    L.append('### Problems engineers face\n'); L.append(W['problems'] + '\n')
    L.append('### How the tasks reproduce them\n'); L.append(W['how'] + '\n')
    L.append('### Typical prompts\n'); L.append('\n'.join(f'- {p}' for p in W['prompts']) + '\n')
    L.append('## Domain breakdown\n')
    d0 = s['domain'][0]
    L.append(f"The tasks span {NUMW.get(len(s['domain']), len(s['domain']))} domain{'s' if len(s['domain']) > 1 else ''}."
             + (f" The largest, {d0['super_group']}, makes up {d0['pct']:.0f}% of the catalog.\n" if len(s['domain']) > 1 else '\n'))
    L.append(f'![Share of tasks by domain](assets/{slug}_domain.svg)\n')
    L.append('## Language and seniority\n')
    L.append(f'![Primary language and seniority](assets/{slug}_metadata.svg)\n')
    for key, title in [('language', 'Primary language'), ('seniority', 'Seniority')]:
        L.append(f'### {title}\n'); L.append(table([title, '% of catalog'], [[x['value'], f"{100 * x['tasks'] / n:.1f}%"] for x in s[key]]) + '\n')
    L.append('## Model pass rates across the catalog\n')
    M = [m for m in s['models'] if m['tasks_graded'] >= MIN]; few = [m for m in s['models'] if 0 < m['tasks_graded'] < MIN]
    L.append(f"A model's pass rate is its passed runs over its graded runs, pooled across the tasks it ran; runs that errored are left out. Models are listed by number of runs, and a model needs graded runs on {NUMW[MIN]} or more tasks for a row.\n")
    if M:
        Q = lambda a, b: 'n/a' if not b else f"{100 * a / b:.0f}%"
        L.append(table(['Model', 'Tasks run', 'Graded runs', 'Pass rate', 'Tasks at 0%', 'Tasks at 20-80%', 'Tasks at 100%'],
            [[m['model'], f"{m['tasks_graded']:,}", f"{m['graded']:,}", pct(m['pass_rate']), Q(m['tasks_0'], m['tasks_graded']), Q(m['tasks_20_80'], m['tasks_graded']), Q(m['tasks_100'], m['tasks_graded'])] for m in M]) + '\n')
        if os.path.exists(f'{OUT}/assets/{slug}_per_task.svg'):
            sat = [m['model'] for m in M if m['tasks_100'] / m['tasks_graded'] >= 0.8]
            L.append('![Per-task pass rate by model](assets/' + slug + '_per_task.svg)\n')
            if sat: L.append(f"The chart leaves out {' and '.join(sat)}, which pass{'es' if len(sat) == 1 else ''} every run on 80% or more of {'its' if len(sat) == 1 else 'their'} tasks.\n")
    if few: L.append(f"Also run on fewer than {NUMW[MIN]} tasks: " + ', '.join(f"{m['model']} ({m['tasks_graded']} task{'s' if m['tasks_graded'] > 1 else ''}, {pct(m['pass_rate'])} of {m['graded']} runs)" for m in few) + '.\n')
    TT = s['turns']
    L.append('## Turn counts and long-horizon tasks\n')
    if TT['tasks_with_turns']:
        k = TT['tasks_with_turns']
        L.append(f"A task's turn count is the average over its completed runs, from every model. A task is long horizon when that average is {TT['threshold']} or more turns. {k:,} of the {n:,} tasks have a completed run.\n")
        L.append(table(['Measure', 'Value'], [['Average turn count', f"{TT['mean_of_task_means']:.1f}"], ['Median turn count', f"{TT['median_of_task_means']:.1f}"],
            ['Range', f"{TT['min_task_mean']:.0f} to {TT['max_task_mean']:.0f}"], [f"Long-horizon tasks ({TT['threshold']}+ turns)", f"{100 * TT['long_horizon_tasks'] / k:.0f}% of tasks"]]) + '\n')
        L.append(f'![Turns per task](assets/{slug}_turns.svg)\n')
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
        L.append('#### Pass rates\n')
        g = [m for m in t['models'] if m['graded']]
        L.append(table(['Model', 'Graded runs', 'Pass rate'], [[m['model'], m['graded'], pct(m['pass_rate'])] for m in g]) + '\n' if g else 'No graded runs on the selected version.\n')
        L.append('#### Environment\n')
        src = next((p for p in (f"{H}/super/diagrams/{t['task_id']}/diagram.svg", f"{G}/diagrams/{t['task_id']}/diagram.svg") if os.path.exists(p)), '')
        if os.path.exists(src):
            shutil.copyfile(src, f"{OUT}/assets/env-{t['task_id']}.svg"); L.append(f"![How the task works](assets/env-{t['task_id']}.svg)\n")
        else: L.append('_Diagram pending._\n')
    open(f'{OUT}/{slug}.md', 'w').write('\n'.join(L))
    print(slug, n, 'tasks', len(s['showcase']), 'samples')
# overview
TOT = sum(s['tasks'] for s in S.values())
allm = collections.defaultdict(lambda: [0, 0, set()])
for slug, s in S.items():
    for t in TASKS:
        if t['catalog'] != s['title']: continue
        for m, v in runs(t['id']).items(): a = allm[m]; a[0] += len(v); a[1] += sum(x for x, _ in v); a[2].add(t['id'])
graded = sum(v[0] for v in allm.values())
L = ['# Coding OTS RL Envs\n']
L.append('<div class="kpis">' + kpi(f"{TOT:,}", 'Tasks') + ''.join(kpi(pct(v[1] / v[0]), f'{m} pass rate') for m, v in sorted(allm.items(), key=lambda kv: -kv[1][0])) + '</div>\n')
LANG = collections.Counter(); SEN = collections.Counter()
for s_ in S.values():
    for x in s_['language']: LANG[x['value']] += x['tasks']
    for x in s_['seniority']: SEN[x['value']] += x['tasks']
AC = "Agent's choice"
lp = lambda *ks: f"{100 * sum(LANG[k] for k in ks) / TOT:.0f}%"
allt0 = [m for s_ in S.values() for m in s_['turns']['task_means']]
T_ = {k: s_['tasks'] for k, s_ in S.items()}; TM = {k: s_['turns']['mean_of_task_means'] for k, s_ in S.items()}
PR = {m: v[1] / v[0] for m, v in allm.items()}; lo, hi = min(PR, key=PR.get), max(PR, key=PR.get)
big3 = T_['programbench'] + T_['debugging'] + T_['infrastructure-as-code']
NM = {'z-ai/glm-5.3-flash': 'GLM 5.3 Flash', 'google/gemini-3.8-flash': 'Gemini 3.8 Flash', 'google/gemini-4-argon': 'Gemini 4 Argon'}
nm = lambda m: NM.get(m, m)
L.append('## Executive summary\n')
L.append(f"These {TOT:,} tasks train and test AI coding agents on long, senior-level software work: rebuilding whole programs, fixing faults in real codebases and changing live systems without breaking them. "
         f"Pass rates vary widely by model, from {pct(PR[lo])} for {nm(lo)} over {len(allm[lo][2]):,} tasks to {pct(PR[hi])} for {nm(hi)} over the {len(allm[hi][2]):,} tasks it ran.\n")
L.append(f"The tasks fall into {NUMW[len(S)]} catalogs, and three of them hold {100 * big3 / TOT:.0f}%. In ProgramBench ({T_['programbench']} tasks) the agent rebuilds a program from how it behaves. "
         f"In Debugging ({T_['debugging']}) it finds and fixes faults, and in Infrastructure as code ({T_['infrastructure-as-code']}) it restructures deployed Terraform without changing what runs. "
         f"Feature implementation ({T_['feature-implementation']}) adds capabilities to existing libraries, System design ({T_['system-design']}) keeps running services correct through crashes and retries, and Data engineering ({T_['data-engineering']}) and Migration ({T_['migration']}) cover data pipelines and ports to another language.\n")
L.append(f"Almost all tasks are senior engineering work in a few languages. Senior engineers are the target for {100 * SEN['Senior'] / TOT:.0f}% of tasks and staff engineers for {100 * SEN['Staff+'] / TOT:.0f}%. "
         f"Go, Terraform and Python account for {lp('Go', 'HCL (Terraform)', 'Python')} of tasks, and Rust, C and C++ for another {lp('Rust', 'C', 'C++')}.\n")
L.append(f"The tasks are long. An agent averages {sum(allt0) / len(allt0):.0f} turns (one model reply plus its tool calls) on a task, and {100 * sum(m >= 200 for m in allt0) / len(allt0):.0f}% of tasks average 200 turns or more. "
         f"ProgramBench and System design run longest, at about {round((TM['programbench'] + TM['system-design']) / 2, -1):.0f} turns. Infrastructure as code tasks are the shortest, at {TM['infrastructure-as-code']:.0f} turns.\n")
L.append(TXT['_summary_bench'] + '\n')
L.append('## Catalogs\n')
tt = lambda s: f"{s['turns']['mean_of_task_means']:.0f}" if s['turns']['tasks_with_turns'] else 'n/a'
L.append(table(['Catalog', 'Tasks', 'What the tasks do', '% of all tasks', 'Tasks with graded runs', 'Average turn count'],
    [[f"[{s['name']}]({slug}.md)", f"{s['tasks']:,}", TXT[slug]['one'], f"{100 * s['tasks'] / TOT:.1f}%", f"{s['tasks_graded']:,}", tt(s)] for slug, s in S.items()]
    + [['**Total**', f"**{TOT:,}**", '', '**100%**', f"**{sum(s['tasks_graded'] for s in S.values()):,}**", '']], align='lrlrrr') + '\n')
L.append('## How the catalogs compare with public benchmarks\n')
L.append(TXT['_bench_intro'] + '\n')
L.append(table(['Catalog', 'Closest public benchmarks', 'What ours add'], [[s_['name'], TXT[k]['bench'], TXT[k]['adds']] for k, s_ in S.items()], left=True) + '\n')
L.append('## Model pass rates\n')
L.append(f"Pass rates and turn counts come from Horizon runs up to {SNAPSHOT[:10]}. Each cell is a model's pass rate in one catalog: passed runs over graded runs, pooled across the tasks it ran there. A cell is blank when the model has graded runs on fewer than {NUMW[S['programbench']['min_tasks']]} tasks in that catalog.\n")
L.append('![Pass rate by model and catalog](assets/overview_models.svg)\n')
L.append(table(['Model', 'Tasks run', 'Graded runs', 'Pass rate'], [[m, f"{len(v[2]):,}", f"{v[0]:,}", pct(v[1] / v[0])] for m, v in sorted(allm.items(), key=lambda kv: -kv[1][0])]) + '\n')
L.append('## Samples\n')
L.append("Each sample is a full task, downloadable from its task id. The pass rate is that of the model with the most graded runs on the task.\n")
smp = [(slug, s, i, t) for slug, s in S.items() for i, t in enumerate(s['showcase'], 1)]
def best(t):
    g = [m for m in t['models'] if m['graded']]  # the model with the most graded runs; a tie goes to the one with more runs
    return max(g, key=lambda m: m['graded']) if g else None
L.append(table(['Catalog', 'Example', 'Task id', 'Model with most graded runs', 'Pass rate'],
    [[s['name'], f"[{ex_title(i, t)}]({slug}.md#{anchor(ex_title(i, t))})", f"[`{t['task_id']}`]({t['url']})" if t.get('url') else f"`{t['task_id']}`", (best(t) or {}).get('model', ''),
      f"{pct(best(t)['pass_rate'])} of {best(t)['graded']}" if best(t) else ''] for slug, s, i, t in smp], text_cols=4) + '\n')
allt = [m for s in S.values() for m in s['turns']['task_means']]
L.append('## Turn counts\n')
L.append(f"A task's turn count is the average over its completed runs, from every model. Across all catalogs the average is {sum(allt) / len(allt):.0f} turns, and {100 * sum(m >= 200 for m in allt) / len(allt):.0f}% of tasks average 200 turns or more.\n")
L.append('![Turns per task, all catalogs](assets/all_turns.svg)\n')
open(f'{OUT}/README.md', 'w').write('\n'.join(L))
print('README', TOT, 'tasks,', len(smp), 'samples')
# CSVs: every task with its catalog, metadata and per-model results; and the samples
ROWS = {r['id']: r for r in dedupe([r for r in green(load_rows()) if r['catalog']], shortlist())}
NEWC = json.load(open(f'{H}/cat/new_task_classes.json'))
EX = {t['id']: (s['name'], i, t) for s in S.values() for i, t in enumerate(s['showcase'], 1)}
MODELS = [m for m, _ in sorted(allm.items(), key=lambda kv: -kv[1][0])]
with open(f'{H}/ots_tasks.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Task', 'Horizon task id', 'Task version', 'Catalog', 'Domain', 'Sub-domain', 'Language', 'Seniority', 'Sample', 'Graded runs', 'Passes', 'Pass rate (all models)']
               + [f'{m} (passed/graded)' for m in MODELS])
    for slug, cat in CATS:
        for t in sorted([t for t in TASKS if t['catalog'] == cat], key=lambda t: t['name']):
            r = ROWS.get(t['id']); c = NEWC.get(t['name'], {}); rr = runs(t['id']); g = sum(map(len, rr.values())); p = sum(x for v in rr.values() for x, _ in v)
            meta = (r['sg'], r['cat'], r['lang'], r['sen'].replace('–', '-')) if r else (c['sg'], c['cat'], c['lang'], c['sen'])
            ex = EX.get(t['id'])
            w.writerow([t['name'], t['id'], RO[t['id']]['version'], cat, *meta, f"{ex[0]}, Example {ex[1]}: {ex[2]['task_id']}" if ex else '', g, p, f"{100 * p / g:.0f}%" if g else '']
                       + [f"{sum(x for x, _ in rr[m])}/{len(rr[m])}" if m in rr else '' for m in MODELS])
with open(f'{H}/samples.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Catalog', 'Example', 'Task id', 'Download URL', 'Horizon task name', 'Horizon task id', 'Horizon URL', 'Selected version', 'Earlier role'])
    for slug, s, i, t in smp:
        w.writerow([s['name'], i, t['task_id'], t.get('url') or '', t['name'], t['id'], f"https://horizon.bespokelabs.ai/tasks/{t['id']}", t['version'], {'main': 'main sample', 'attached': 'attached sample', 'super': 'super-sample'}[t['earlier']]])
print('ots_tasks.csv', sum(1 for _ in open(f'{H}/ots_tasks.csv')) - 1, 'rows; samples.csv', len(smp), 'rows')
