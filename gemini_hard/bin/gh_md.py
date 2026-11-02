# Assemble the Gemini-hard catalog pages (same structure as the OTS catalog pages) from cat/stats.json and the catalog write-ups.
import json, os, re, shutil, sys
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; sys.path.insert(0, f'{P}/bin')
from codeify import codeify as _cf
from noname import strip_names
codeify = lambda x: _cf(strip_names(x))
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/catalog'
S = json.loads(open(f'{H}/cat/stats.json').read().replace(r'Mid–Senior', 'Mid-Senior').replace('Mid–Senior', 'Mid-Senior'))
U = json.load(open(f'{H}/universe.json'))
def pct(v): return 'n/a' if v is None else f'{100 * v:.0f}%'
def table(head, rows, left=False, text_cols=1, align=None):
    """align: optional string of l/r per column; otherwise the first text_cols columns are left-aligned."""
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(('---' if align[i] == 'l' else '---:') if align else ('---' if i < text_cols or left else '---:') for i in range(len(head))) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)
def instruction(name):
    for p in (f'{P}/show/{name}/instruction.md', f'{H}/show/{name}/instruction.md'):
        if os.path.exists(p) and os.path.getsize(p): return open(p).read().strip()
def prompt_md(src):
    """Render an instruction as Markdown inside the page: demote its headings below the page's own, escape stray HTML and quote markers."""
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
            lvl = min(6, len(h.group(1)) + 4)
            out.append('#' * lvl + ' ' + h.group(2) if len(h.group(1)) <= 2 else f'**{h.group(2).strip()}**'); continue
        parts = re.split(r'(`[^`]*`)', line)
        line = ''.join(p if i % 2 else p.replace('<', '&lt;').replace('>', '&gt;') for i, p in enumerate(parts))
        out.append(line)
    if fence is not None: out.append(fence)
    return '\n'.join(out).strip()
def load_text(path):
    if not os.path.exists(path): return {'motivation': {}, 'tasks': []}
    raw = open(path).read()
    for a, b in [('showcase tasks', 'example tasks'), ('showcase task', 'example task'), ('showcase set', 'example set'), ('Showcase', 'Example'), ('showcase', 'example')]: raw = raw.replace(a, b)
    d = json.loads(raw); m = d.get('motivation', {})
    for k in ('problems', 'how_tasks_exemplify'):
        if k in m: m[k] = codeify(m[k])
    for k in ('prompt_patterns',): m[k] = [codeify(x) for x in m.get(k, [])]
    for t in d.get('tasks', []):
        for k in ('workflow', 'prompt_pattern'): t[k] = codeify(t.get(k))
    return d
EXTRA = {t['name']: t for t in load_text(f'{H}/cat/samples_text.json').get('tasks', [])}
# environment diagrams already drawn for the OTS catalog examples
OLD = json.load(open(f'{P}/cat/stats.json'))
ENV = {t['name']: f'/Users/carlos/code/sdlc_final_samples/catalogs/assets/env-{slug}-ex{i}.svg' for slug, s in OLD.items() for i, t in enumerate(s['showcase'][:3], 1)}
SLUG = {'ProgramBench': 'programbench', 'System design': 'system-design', 'Diagnosis, Debugging, and Bug Fixing': 'debugging', 'Feature implementation': 'feature-implementation',
        'Infrastructure as code': 'infrastructure-as-code', 'Data engineering': 'data-engineering', 'Migration': 'migration'}
TXT = {g: load_text(f'{P}/cat/{sl}_text.json') for g, sl in SLUG.items()}
TX = {t['name']: t for d in TXT.values() for t in d.get('tasks', [])}; TX.update(EXTRA)
EN = {slug: s['estimate']['estimate'] for slug, s in S.items()}; total = round(sum(EN.values()))
NUM = {k: int(v) for k, v in EN.items()}
for k in sorted(EN, key=lambda k: -(EN[k] - int(EN[k])))[:total - sum(NUM.values())]: NUM[k] += 1
SUM = json.load(open(f'{H}/cat/summary_text.json'))
WHY = json.load(open(f'{H}/cat/why_text.json'))  # written for the merged catalogs, from the selected tasks' prompts and files
def kpi(value, label): return f'<div class="kpi"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>'
index = []
for slug, s in S.items():
    T = TXT[s['title']]; tx = TX; mo = T.get('motivation', {})
    moved = [g for g in s['groups'] if g != s['title']]
    n = s['tasks']; e = s['estimate']; tiers = s['tiers']; L = []
    L.append(f"# {s['name']}\n")
    L.append('## Executive summary\n')
    G = {m['model']: m for m in s['models'] if m['tasks_graded'] >= 5}
    am, fm = G.get('google/gemini-4-argon'), G.get('google/gemini-3.8-flash')
    cards = [kpi(f"{NUM[slug]:,}", 'Tasks')] + [kpi(pct(m['pass_rate']), f"{nm} pass rate") for m, nm in ((am, 'Gemini 4 Argon'), (fm, 'Gemini 3.8 Flash')) if m]
    L.append('<div class="kpis">' + ''.join(cards) + '</div>\n')
    L.append(SUM[slug]['work'] + '\n')
    langs = [x for x in s['language'] if x['value'] != 'Not yet classified'][:3]
    fails = lambda m: f", and it fails every run on {pct(m['tasks_0'] / m['tasks_graded'])} of the tasks" if m['tasks_0'] else ''
    L.append(' '.join([f"Gemini 4 Argon passes {pct(am['pass_rate'])} of its runs on these tasks{fails(am)}." if am else '',
                       f"Gemini 3.8 Flash passes {pct(fm['pass_rate'])}{fails(fm)}." if fm else '',
                       'The main languages are ' + ', '.join(f"{x['value']} ({x['pct']:.0f}%)" for x in langs[:-1]) + (' and ' if len(langs) > 1 else '') + f"{langs[-1]['value']} ({langs[-1]['pct']:.0f}%)."]).strip() + '\n')
    L.append(table(['Domain', 'What the tasks do', '% of catalog'],
                   [[g['super_group'], SUM[slug]['domains'].get(g['super_group'], ''), f"{g['pct']:.0f}%"] for g in s['domain']], text_cols=2) + '\n')
    L.append('## Why this catalog\n')
    W = WHY[slug]
    L.append('### Problems engineers face\n'); L.append(W['problems'] + '\n')
    L.append('### How the tasks reproduce them\n'); L.append(W['how'] + '\n')
    L.append('### Typical prompts\n'); L.append('\n'.join(f'- {p}' for p in W['prompts']) + '\n')
    L.append('## Domain breakdown\n')
    L.append(f'![Share of tasks by domain](assets/{slug}_domain.svg)\n')
    Pc = lambda k: 100 * k / n
    L.append('## Language and seniority\n')
    L.append(f'![Primary language and seniority](assets/{slug}_metadata.svg)\n')
    for key, title in [('language', 'Primary language'), ('seniority', 'Seniority')]:
        L.append(f'### {title}\n'); L.append(table([title, '% of catalog'], [[x['value'], f"{Pc(x['tasks']):.1f}%"] for x in s[key]]) + '\n')
    L.append('## Gemini pass rates across the catalog\n')
    M = [m for m in s['models'] if m['tasks_graded'] >= 5]
    if M:
        Q = lambda a, b: 'n/a' if not b else f"{100 * a / b:.0f}%"
        L.append(table(['Model', 'Pass rate', 'Tasks at 0%', 'Tasks at 20-80%', 'Tasks at 100%'],
            [[m['model'], pct(m['pass_rate']), Q(m['tasks_0'], m['tasks_graded']), Q(m['tasks_20_80'], m['tasks_graded']), Q(m['tasks_100'], m['tasks_graded'])] for m in M]) + '\n')
        if os.path.exists(f'{OUT}/assets/{slug}_per_task.svg'): L.append(f'![Per-task pass rate by Gemini model](assets/{slug}_per_task.svg)\n')
    else: L.append('No Gemini model has graded runs on five or more of the selected tasks.\n')
    TT = s.get('turns') or {}
    L.append('## Turn counts and long-horizon tasks\n')
    if TT.get('tasks_with_turns'):
        k = TT['tasks_with_turns']; lh = TT['long_horizon_tasks']
        L.append(f"A task's turn count is the average over its Gemini runs. A task is long horizon when that average is {TT['threshold']} or more turns.\n")
        L.append(table(['Measure', 'Value'], [['Average turn count', f"{TT['mean_of_task_means']:.1f}"], ['Median turn count', f"{TT['median_of_task_means']:.1f}"],
            ['Range', f"{TT['min_task_mean']:.0f} to {TT['max_task_mean']:.0f}"], [f"Long-horizon tasks ({TT['threshold']}+ turns)", f"{100 * lh / k:.0f}% of tasks"]]) + '\n')
        L.append(f'![Turns per task](assets/{slug}_turns.svg)\n')
        L.append(table(['Model', '% of tasks', 'Mean turns', f"% with {TT['threshold']}+ turns"],
            [[m['model'], (f"{100 * m['tasks'] / k:.0f}%" if 100 * m['tasks'] / k >= 0.5 else '<1%'), f"{m['mean']:.1f}", f"{100 * m['runs_200_plus'] / m['runs']:.0f}%"] for m in TT['by_model']]) + '\n')
    else: L.append('No Gemini turn data for the selected tasks.\n')
    L.append('## Example tasks from the shortlist\n')
    if not s['showcase']:
        L.append("None of this catalog's shortlisted tasks are in the Gemini-hard selection, so this page has no example.\n")
    else:
        main = sum(1 for t in s['showcase'] if t['sample'] == 'super')
        L.append(('The first example is a main sample for the catalog; the others are attached samples.' if main else 'These examples are attached samples.')
                 + ' All of them come from the shortlist and have Gemini runs that pass at most half the time.\n')
    for i, t in enumerate(s['showcase'], 1):
        x = tx.get(t['name'], {})
        L.append(f"### Example {i}: {t['category']} ({t['language']})\n")
        gem = [m for m in t['models'] if m['graded']]
        L.append(table(['Field', 'Value'], [
            ['Sample', 'Main sample for the catalog' if t['sample'] == 'super' else 'Attached sample'],
            ['Final category', t['final']], ['Domain', t['super_group']], ['Sub-domain', t['category']],
            ['Language', t['language']], ['Seniority', t['seniority']],
            ['Turn count', (', '.join(f"{v:.0f} ({json.load(open(f'{P}/ro_models.json')).get(m, m)})" for m, v in t['turns']['by_model'].items()) if t.get('turns') else 'no completed run')],
            ['Long horizon', ('yes' if t.get('turns') and t['turns']['mean'] >= 200 else 'no' if t.get('turns') else 'n/a')]], left=True) + '\n')
        if x.get('prompt_pattern'): L.append(f"Prompt shape: {x['prompt_pattern']}\n")
        ins = instruction(t['name'])
        L.append('#### Prompt\n')
        L.append('<details open><summary>Full instruction given to the agent (instruction.md)</summary>\n<div class="prompt-md">\n\n' + (prompt_md(ins) if ins else '`instruction.md` not found in the current version.') + '\n\n</div>\n</details>\n')
        L.append('#### Pass rates\n')
        if gem:
            L.append(table(['Model', 'Pass rate', 'Mean score'],
                [[m['model'], pct(m['pass_rate']), 'n/a' if m['avg_score'] is None else f"{m['avg_score']:.2f}"] for m in gem]) + '\n')
        else: L.append('No graded Gemini runs on the current version.\n')
        L.append('#### Environment\n')
        envsvg = f'env-{slug}-ex{i}.svg'
        if os.path.exists(f"{OUT}/assets/env-{t['name']}.svg"):
            L.append(f"![How the task works](assets/env-{t['name']}.svg)\n")
        elif t['name'] in ENV and os.path.exists(ENV[t['name']]):
            shutil.copyfile(ENV[t['name']], f'{OUT}/assets/{envsvg}'); L.append(f'![How the task works](assets/{envsvg})\n')
        elif x.get('environment_mermaid'):
            L.append('```mermaid\n' + x['environment_mermaid'].strip() + '\n```\n')
        else: L.append('_Pending._\n')
        L.append('#### How it maps to the work\n')
        L.append((x.get('workflow') or '_Pending._') + '\n')
    md = '\n'.join(L)
    open(f'{OUT}/{slug}.md', 'w').write(md)
    index.append((slug, s))
    print(slug, len(md), 'chars', len(s['showcase']), 'examples')
# overview
TOT = sum(s['tasks'] for _, s in index); EST = sum(s['estimate']['estimate'] for _, s in index)
def tt(s):
    T = s.get('turns') or {}
    return f"{T['mean_of_task_means']:.0f}" if T.get('tasks_with_turns') else 'n/a'
proven = sum(s['tiers'].get('Proven', 0) for _, s in index); likely = TOT - proven
argon = [t for t in U['tasks'] if t['argon']]; argon_g = sum(t['argon']['graded'] for t in argon); argon_p = sum(t['argon']['passed'] for t in argon)
cat_n = sum(s['estimate']['tasks'] for _, s in index)
expected = round(proven + sum(t['p_hard'] for t in U['tasks'] if t.get('tier') == 'Likely'))
ONE = {'programbench': 'Rebuild or upgrade programs to match a reference exactly, or port libraries to another language.',
       'system-design': 'Keep running services and live infrastructure correct through failures and refactors.',
       'debugging': 'Find and fix faults in real codebases from symptoms or documentation.',
       'feature-implementation': 'Add capabilities to existing libraries and services without breaking current behaviour.'}
allm = {}
for _, s in index:
    for m in s['models']:
        a = allm.setdefault(m['model'], [0, 0]); a[0] += m['graded']; a[1] += m['passed']
ar = allm['google/gemini-4-argon']; fl = allm['google/gemini-3.8-flash']
L = ['# Coding OTS RL Envs\n']
L.append('<div class="kpis">' + kpi(f"{total:,}", 'Tasks') + kpi(pct(ar[1] / ar[0]), 'Gemini 4 Argon pass rate') + kpi(pct(fl[1] / fl[0]), 'Gemini 3.8 Flash pass rate') + '</div>\n')
L.append(f"These are coding environments for reinforcement learning, grouped into {len(index)} catalogs. Each task puts the agent in a real open-source codebase or program, "
         "gives it a written request of the kind an engineer would receive, and grades the result with hidden tests. "
         f"Gemini 4 Argon passes {pct(ar[1] / ar[0])} of its runs on these tasks and Gemini 3.8 Flash passes {pct(fl[1] / fl[0])}. "
         "Every pass rate and plot on these pages covers Gemini models only: Gemini 4 Argon (`google/gemini-4-argon`) and Gemini 3.8 Flash (`google/gemini-3.8-flash`).\n")
L.append(table(['Catalog', 'Tasks', 'What the tasks do', '% of all tasks', 'Average turn count'],
    [[f"[{s['name']}]({slug}.md)", f"{NUM[slug]:,}", ONE[slug], f"{100 * NUM[slug] / total:.1f}%", tt(s)] for slug, s in index]
    + [['**Total**', f"**{total:,}**", '', '**100%**', '']], align='lrlrr') + '\n')
L.append('## Gemini pass rates\n')
L.append('![Gemini pass rates by catalog](assets/overview_gemini.svg)\n')
L.append(table(['Model', 'Pass rate'], [[k, pct(v[1] / v[0]) if v[0] else 'n/a'] for k, v in allm.items()]) + '\n')
L.append('## Samples\n')
smp = [(slug, s, i, t) for slug, s in index for i, t in enumerate(s['showcase'], 1)]
gm = lambda t, name: next((pct(m['pass_rate']) for m in t['models'] if m['model'] == name and m['graded']), '')
L.append(f"{sum(1 for x in smp if x[3]['sample'] == 'super')} main samples go into the catalog and {sum(1 for x in smp if x[3]['sample'] == 'attached')} are attached. "
         "All come from the shortlist. Main samples pass at most 25% of their Gemini runs. "
         "Attached samples pass at most half their Gemini runs. Each example is written up on its catalog page.\n")
L.append(table(['Sample', 'Catalog', 'Example', 'Gemini 4 Argon', 'Gemini 3.8 Flash'],
    [['Main' if t['sample'] == 'super' else 'Attached', s['name'], f"[Example {i}: {t['category']} ({t['language']})]({slug}.md)", gm(t, 'google/gemini-4-argon'), gm(t, 'google/gemini-3.8-flash')]
     for slug, s, i, t in sorted(smp, key=lambda x: x[3]['sample'] != 'super')], text_cols=3) + '\n')
L.append('\n![Turns per task, all catalogs](assets/all_turns.svg)\n')
open(f'{OUT}/README.md', 'w').write('\n'.join(L))
print('README', TOT, 'tasks')
# tie each sample in the CSV to its example on the catalog pages
import csv
ex = {t['name']: f"{s['name']}, Example {i}" for _, s in index for i, t in enumerate(s['showcase'], 1)}
MOVE = {'Migration': 'ProgramBench and Migration', 'Infrastructure as code': 'System design & IaC', 'Data engineering': 'Feature implementation',
        'ProgramBench': 'ProgramBench and Migration', 'System design': 'System design & IaC'}
rows = list(csv.reader(open(f'{H}/gemini_hard_universe.csv')))
if 'Task group' not in rows[0]:
    rows[0].insert(3, 'Task group'); [r.insert(3, r[2]) for r in rows[1:]]
for r in rows[1:]: r[2] = MOVE.get(r[3], r[3])
if 'Catalog example' not in rows[0]: rows[0].insert(7, 'Catalog example'); [r.insert(7, ex.get(r[0], '')) for r in rows[1:]]
else: k = rows[0].index('Catalog example'); [r.__setitem__(k, ex.get(r[0], '')) for r in rows[1:]]
csv.writer(open(f'{H}/gemini_hard_universe.csv', 'w', newline='')).writerows(rows)
