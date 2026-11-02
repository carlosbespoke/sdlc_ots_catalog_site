# Assemble one standardized Markdown file per catalog from cat/stats.json and cat/<slug>_text.json.
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from codeify import codeify as _cf
from noname import strip_names
codeify = lambda x: _cf(strip_names(x))
B = sys.argv[1]; OUT = '/Users/carlos/code/sdlc_final_samples/catalogs'
MM = json.load(open(f'{B}/ro_models.json'))
S = json.loads(open(f'{B}/cat/stats.json').read().replace(r'Mid\u2013Senior', 'Mid-Senior').replace('Mid–Senior', 'Mid-Senior'))
PULLED = '27 Oct 2026'
def pct(v): return 'n/a' if v is None else f'{100 * v:.0f}%'
def table(head, rows, left=False, text_cols=1):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' if i < text_cols or left else '---:' for i in range(len(head))) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)
def instruction(name):
    p = f'{B}/show/{name}/instruction.md'
    return open(p).read().strip() if os.path.exists(p) else None
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
def text(slug):
    p = f'{B}/cat/{slug}_text.json'
    if not os.path.exists(p): return {'motivation': {}, 'tasks': []}
    raw = open(p).read()
    for a, b in [('showcase tasks', 'example tasks'), ('showcase task', 'example task'), ('showcase set', 'example set'), ('Showcase', 'Example'), ('showcase', 'example')]: raw = raw.replace(a, b)
    d = json.loads(raw); m = d.get('motivation', {})
    for k in ('problems', 'how_tasks_exemplify'): m[k] = codeify(m.get(k, ''))
    for k in ('prompt_patterns', 'open_questions'): m[k] = [codeify(x) for x in m.get(k, [])]
    for t in d.get('tasks', []):
        for k in ('workflow', 'prompt_pattern'): t[k] = codeify(t.get(k))
        t['environment_facts'] = [codeify(x) for x in t.get('environment_facts', [])]
    return d
index = []
OPENQ = []
FAMILIES = {'infrastructure-as-code': [('Terraform module refactor', 312), ('CDK componentization', 5), ('Terraform to Pulumi port', 5), ('Terraform policy remediation', 3)]}
EMPTY = {'programbench': 5, 'debugging': 4, 'infrastructure-as-code': 3, 'data-engineering': 2, 'system-design': 2, 'feature-implementation': 2}
NOTES = {
 'programbench': 'The shortlist examples in this catalog are all clean-room reimplementations; repository-upgrade tasks have no example on this page.',
 'migration': 'Every task in this catalog is a cross-language port, although the batch-level task-shape label reads "Evolve a repo from one release to the next". The language column shows the target language.',
 'system-design': 'This catalog includes the tasks classified as Fault tolerance (one component must survive or recover from failure) alongside the System design tasks (several instances, workers or nodes must coordinate).',
 'feature-implementation': 'The shortlist examples in this catalog do not come from alpharecon-deepswe-binary, the batch that holds most of its tasks.',
 'optimization': 'This catalog has a single shortlist example.',
}
for slug, s in S.items():
    T = text(slug); tx = {t['name']: t for t in T.get('tasks', [])}; mo = T.get('motivation', {})
    n = s['tasks']; L = []
    L.append(f"# {s['title']}\n")
    L.append('## Why this catalog\n')
    if mo:
        L.append('### Problems engineers face\n'); L.append(mo.get('problems', '') + '\n')
        L.append('### How the tasks reproduce them\n'); L.append(mo.get('how_tasks_exemplify', '') + '\n')
        L.append('### Typical prompts\n'); L.append('\n'.join(f'- {p}' for p in mo.get('prompt_patterns', [])) + '\n')
    else: L.append('_Pending._\n')
    L.append('## Domain breakdown\n')
    L.append(f'![Share of tasks by domain](assets/{slug}_domain.svg)\n')
    P = lambda k: 100 * k / n
    rows = []
    for g in s['domain']:
        rows.append([f"**{g['super_group']}**", '', f"**{P(g['tasks']):.1f}%**"])
        big = [c for c in g['categories'] if P(c['tasks']) >= 10]; small = [c for c in g['categories'] if P(c['tasks']) < 10]
        for c in big: rows.append(['', c['category'], f"{P(c['tasks']):.1f}%"])
        if small: rows.append(['', ', '.join(c['category'] for c in small), f"{P(sum(c['tasks'] for c in small)):.1f}%"])
    L.append(table(['Domain', 'Sub-domain', '% of catalog'], rows, text_cols=2) + '\n')
    L.append('## Language and seniority\n')
    L.append(f'![Primary language and seniority](assets/{slug}_metadata.svg)\n')
    for key, title in [('language', 'Primary language'), ('seniority', 'Seniority')]:
        L.append(f'### {title}\n'); L.append(table([title, '% of catalog'], [[x['value'], f"{P(x['tasks']):.1f}%"] for x in s[key]]) + '\n')
    L.append('## Model pass rates across the catalog\n')
    M = s['models']
    if M:
        Q = lambda a, b: 'n/a' if not b else f"{100 * a / b:.0f}%"
        L.append(table(['Model', 'Pass rate', 'Tasks at 0%', 'Tasks at 20-80%', 'Tasks at 100%'],
            [[m['model'], pct(m['pass_rate']), Q(m['tasks_0'], m['tasks_graded']), Q(m['tasks_20_80'], m['tasks_graded']), Q(m['tasks_100'], m['tasks_graded'])] for m in M if m['tasks_graded'] >= 5]) + '\n')
        if os.path.exists(f'{OUT}/assets/{slug}_per_task.svg'): L.append(f'![Per-task pass rate by model](assets/{slug}_per_task.svg)\n')
    else: L.append('No task in this catalog has runs on its current version.\n')
    TT = s.get('turns') or {}
    L.append('## Turn counts and long-horizon tasks\n')
    if TT.get('tasks_with_turns'):
        k = TT['tasks_with_turns']; lh = TT['long_horizon_tasks']
        L.append(f"A task's turn count is the average over its runs. A task is long horizon when that average is {TT['threshold']} or more turns.\n")
        L.append(table(['Measure', 'Value'], [['Average turn count', f"{TT['mean_of_task_means']:.1f}"], ['Median turn count', f"{TT['median_of_task_means']:.1f}"],
            ['Range', f"{TT['min_task_mean']:.0f} to {TT['max_task_mean']:.0f}"], [f"Long-horizon tasks ({TT['threshold']}+ turns)", f"{100 * lh / k:.0f}% of tasks"]]) + '\n')
        L.append(f'![Turns per task](assets/{slug}_turns.svg)\n')
        L.append(table(['Model', '% of tasks', 'Mean turns', f"% with {TT['threshold']}+ turns"],
            [[m['model'], (f"{100 * m['tasks'] / k:.0f}%" if 100 * m['tasks'] / k >= 0.5 else '<1%'), f"{m['mean']:.1f}", f"{100 * m['runs_200_plus'] / m['runs']:.0f}%"] for m in TT['by_model']]) + '\n')
    else: L.append('No turn data for this catalog.\n')
    L.append('## Example tasks from the shortlist\n')
    for i, t in enumerate(s['showcase'][:3], 1):
        x = tx.get(t['name'], {})
        L.append(f"### Example {i}: {t['category']} ({t['language']})\n")
        L.append(table(['Field', 'Value'], [['Final category', t['final']], ['Domain', t['super_group']], ['Sub-domain', t['category']],
            ['Language', t['language']], ['Seniority', t['seniority']],
            ['Turn count', (', '.join(f"{v:.0f} ({MM.get(m, 'unknown model')})" for m, v in t['turns']['by_model'].items()) if t.get('turns') else 'no completed run')],
            ['Long horizon', ('yes' if t.get('turns') and t['turns']['mean'] >= 200 else 'no' if t.get('turns') else 'n/a')]], left=True) + '\n')
        if x.get('prompt_pattern'): L.append(f"Prompt shape: {x['prompt_pattern']}\n")
        ins = instruction(t['name'])
        L.append('#### Prompt\n')
        L.append('<details open><summary>Full instruction given to the agent (instruction.md)</summary>\n<div class="prompt-md">\n\n' + (prompt_md(ins) if ins else '`instruction.md` not found in the current version.') + '\n\n</div>\n</details>\n')
        L.append('#### Pass rates\n')
        if t['models']:
            L.append(table(['Model', 'Pass rate', 'Mean score'],
                [[m['model'], pct(m['pass_rate']), 'n/a' if m['avg_score'] is None else f"{m['avg_score']:.2f}"] for m in t['models']]) + '\n')
        else: L.append('No runs on the current version.\n')
        L.append('#### Environment\n')
        envsvg = f'env-{slug}-ex{i}.svg'
        if os.path.exists(f'{OUT}/assets/{envsvg}'):
            L.append(f'![How the task works](assets/{envsvg})\n')
        elif x.get('environment_mermaid'):
            L.append('```mermaid\n' + x['environment_mermaid'].strip() + '\n```\n')
        else: L.append('_Pending._\n')
        L.append('#### How it maps to the work\n')
        L.append((x.get('workflow') or '_Pending._') + '\n')
    if mo.get('open_questions'): OPENQ.append((s['title'], mo['open_questions']))
    md = '\n'.join(L)
    open(f'{OUT}/{slug}.md', 'w').write(md)
    index.append((slug, s))
    print(slug, len(md), 'chars', 'text' if mo else 'no-text')
L = ['# OTS task catalogs\n']
TOT = sum(s['tasks'] for _, s in index)
def tt(s, k):
    T = s.get('turns') or {}
    if not T.get('tasks_with_turns'): return 'n/a'
    return f"{T['mean_of_task_means']:.0f}" if k == 'mean' else f"{100 * T['long_horizon_tasks'] / T['tasks_with_turns']:.0f}%"
L.append(table(['Catalog', 'Tasks', '% of all tasks', 'Average turn count'],
    [[f"[{s['title']}]({slug}.md)", f"{s['tasks']:,}", f"{100 * s['tasks'] / TOT:.1f}%", tt(s, 'mean')] for slug, s in index]
    + [['**Total**', f"**{TOT:,}**", '**100%**', '']]))
ALLM = [m for _, s in index for m in (s.get('turns') or {}).get('task_means') or []]
if ALLM:
    lh = sum(1 for m in ALLM if m >= 200)
    L.append('\n![Turns per task, all catalogs](assets/all_turns.svg)\n')
open(f'{OUT}/README.md', 'w').write('\n'.join(L))
Q = ['# Open questions from the catalog drafts\n', 'Internal working notes; not part of the catalog pages.\n']
for title, qs in OPENQ: Q.append(f'## {title}\n'); Q.append('\n'.join(f'- {q}' for q in qs) + '\n')
open('/Users/carlos/code/sdlc_final_samples/catalog_open_questions.md', 'w').write('\n'.join(Q))
