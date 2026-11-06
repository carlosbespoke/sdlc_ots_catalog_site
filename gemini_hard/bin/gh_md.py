# Assemble the Gemini-hard catalog pages (same structure as the OTS catalog pages) from cat/stats.json and the catalog write-ups.
import json, os, re, shutil, sys
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; sys.path.insert(0, f'{P}/bin')
from codeify import codeify as _cf
from noname import strip_names
codeify = lambda x: _cf(strip_names(x))
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/catalog'
S = json.loads(open(f'{H}/cat/stats.json').read().replace(r'Mid–Senior', 'Mid-Senior').replace('Mid–Senior', 'Mid-Senior'))
U = json.load(open(f'{H}/universe.json'))
def pct(v): return 'n/a' if v is None else '<1%' if 0 < v < 0.005 else f'{100 * v:.0f}%'
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
# a page that holds more tasks than its estimate shows the tasks it holds (Feature implementation, 108; reviewer decision, 5 Nov)
for k in NUM: NUM[k] = S[k]['tasks'] if os.path.exists(f'{H}/cat/sel5.json') else max(NUM[k], S[k]['tasks'])  # 5 Nov selection: the tasks each page holds
total = sum(NUM.values())
SUM = json.load(open(f'{H}/cat/summary_text.json'))
WHY = json.load(open(f'{H}/cat/why_text.json'))  # written for the merged catalogs, from the selected tasks' prompts and files
NUMW = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten', 11: 'eleven', 12: 'twelve'}
def kpi(value, label): return f'<div class="kpi"><div class="kpi-value">{value.replace("<", "&lt;")}</div><div class="kpi-label">{label}</div></div>'
# interactive charts, the same code as the all-models report (../ots_all/bin/charts.js), here with pass rates (bin/charts.js)
nob = lambda x: '\n'.join(l for l in x.splitlines() if l.strip())  # raw HTML blocks must not contain blank lines
CX_CSS, CX_JS = open(f'{H}/bin/charts.css').read(), open(f'{H}/bin/charts.js').read()
def chart(kind, title, extra=''):
    return nob(f'<div class="cx" data-chart="{kind}"{extra}>\n<div class="fig-head"><span class="lab">Interactive figure</span><h4>{title}</h4></div>\n<div class="fig-box" data-body></div>\n</div>') + '\n'
def runtime(data):
    return nob('<div data-chart-runtime>\n<style>' + CX_CSS + '</style>\n<script type="application/json" data-chart-data>' + json.dumps(data, separators=(',', ':'))
               + '</script>\n<script>' + CX_JS + '</script>\n</div>') + '\n'
def page_data(s):
    """Per-task rows for a catalog page: domain, sub-domain, language, seniority, each Gemini model's runs (1 passed, 0 not) and turns."""
    tr = s['task_rows']; models = [m['model'] for m in s['models']]
    for r in tr:
        for m in list(r['scores']) + list(r['turns']):
            if m not in models: models.append(m)
    dims = {k: sorted({r[f] for r in tr}) for k, f in (('g', 'sg'), ('c', 'cat'), ('l', 'lang'), ('s', 'sen'))}
    rows = [[dims['g'].index(r['sg']), dims['c'].index(r['cat']), dims['l'].index(r['lang']), dims['s'].index(r['sen']),
             {models.index(m): v for m, v in r['scores'].items() if v}, {models.index(m): v for m, v in r['turns'].items()}] for r in tr]
    return {'cross': True, 'models': models, 'dims': dims, 'tasks': rows, 'minTasks': s['min_tasks'], 'sat': 0.8, 'bin': 50, 'xmax': 1000, 'threshold': s['turns']['threshold']}
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
    # paragraph 1: what the tasks are, including their languages
    _ls = [x for x in s['language'] if x['value'] != 'Not yet classified']; langs = [x for x in _ls if x['tasks'] >= _ls[min(2, len(_ls) - 1)]['tasks']]  # top 3, plus any tied with the third
    choice = next((x for x in langs if x['value'] == "Agent's choice"), None); rest = [x for x in langs if x is not choice]
    named = ', '.join(f"{x['value']} ({x['pct']:.0f}%)" for x in rest[:-1]) + (' and ' if len(rest) > 1 else '') + f"{rest[-1]['value']} ({rest[-1]['pct']:.0f}%)"
    lang_s = (f"In {choice['pct']:.0f}% of tasks the agent chooses the language; the most common fixed languages are {named}." if choice
              else f"The main languages are {named}.")
    L.append(SUM[slug]['work'] + ' ' + lang_s + '\n')
    # paragraph 2: results, point first, each rate bounded to the tasks that model has run
    fails = lambda m: f" and fails every run on {pct(m['tasks_0'] / m['tasks_graded'])} of the tasks it has run" if m['tasks_0'] else ''
    L.append(' '.join([f"Gemini 4 Argon passes {pct(am['pass_rate'])} of its runs{fails(am)}." if am else '',
                       f"Gemini 3.8 Flash passes {pct(fm['pass_rate'])} of its runs{fails(fm)}." if fm else '']).strip() + '\n')
    L.append('## Why this catalog\n')
    W = WHY[slug]
    L.append('### Problems engineers face\n'); L.append(W['problems'] + '\n')
    L.append('### How the tasks reproduce them\n'); L.append(W['how'] + '\n')
    L.append('### Typical prompts\n'); L.append('\n'.join(f'- {p}' for p in W['prompts']) + '\n')
    L.append('## Domain breakdown\n')
    top = s['domain'][0]
    L.append(f"The tasks span {NUMW.get(len(s['domain']), len(s['domain']))} domains. The largest, {top['super_group']}, makes up {top['pct']:.0f}% of the catalog.\n")
    L.append(chart('bars', 'Share of tasks by domain', ' data-dims="g>c=Domain" data-hint="Click a domain to filter the charts on this page; use the arrow to see its sub-domains."'))
    Pc = lambda k: 100 * k / n
    L.append('## Language and seniority\n')
    L.append(chart('bars', 'Primary language and seniority', ' data-dims="l:8=Primary language,s=Seniority"'))
    for key, title in [('language', 'Primary language'), ('seniority', 'Seniority')]:
        L.append(f'### {title}\n'); L.append(table([title, '% of catalog'], [[x['value'], f"{Pc(x['tasks']):.1f}%"] for x in s[key]]) + '\n')
    L.append('## Pass rates across the catalog\n')
    M = [m for m in s['models'] if m['tasks_graded'] >= 5]
    if M:
        Q = lambda a, b: 'n/a' if not b else f"{100 * a / b:.0f}%"
        L.append(table(['Model', 'Pass rate', 'Tasks at 0%', 'Tasks at 20-80%', 'Tasks at 100%'],
            [[m['model'], pct(m['pass_rate']), Q(m['tasks_0'], m['tasks_graded']), Q(m['tasks_20_80'], m['tasks_graded']), Q(m['tasks_100'], m['tasks_graded'])] for m in M]) + '\n')
        L.append("Tasks with pass rates between 0% and 20%, or between 80% and 100%, fall outside these three columns.\n")
        L.append(chart('reward', 'Per-task pass rate by model'))
        rf = [r for r in s.get('refreshed', [])]
        if rf: L.append(f"Runs on {NUMW.get(len(rf), len(rf))} tasks were refreshed on 5 Nov, after the 2 Nov snapshot, at the same task version. Their Gemini 4 Argon results set their place in the catalog.\n")
        if s.get('glm_borrowed') or s.get('flash_borrowed'):  # pages where some results come from a related task (see README)
            assert all(r['scores'] for r in s['task_rows']), f'{slug}: a task has no results'
            L.append("Every task in the catalog has results from at least one model shown.\n")
        hid = [m['model'] for m in M if m['tasks_100'] / m['tasks_graded'] >= 0.8]
        if hid: L.append(f"The chart starts with {' and '.join(hid)} hidden, because {'it passes' if len(hid) == 1 else 'they pass'} every run on 80% or more of {'its' if len(hid) == 1 else 'their'} tasks. Click {'its' if len(hid) == 1 else 'their'} button to show {'it' if len(hid) == 1 else 'them'}.\n")
    else: L.append('No model has graded runs on five or more of the selected tasks.\n')
    TT = s.get('turns') or {}
    L.append('## Turn counts and long-horizon tasks\n')
    if TT.get('tasks_with_turns'):
        k = TT['tasks_with_turns']; lh = TT['long_horizon_tasks']
        L.append(f"A task's turn count is the average over its runs by Gemini 4 Argon and Gemini 3.8 Flash. A task is long horizon when that average is {TT['threshold']} or more turns.\n")
        L.append(table(['Measure', 'Value'], [['Average turn count', f"{TT['mean_of_task_means']:.1f}"], ['Median turn count', f"{TT['median_of_task_means']:.1f}"],
            ['Range', f"{TT['min_task_mean']:.0f} to {TT['max_task_mean']:.0f}"], [f"Long-horizon tasks ({TT['threshold']}+ turns)", f"{100 * lh / k:.0f}% of tasks"]]) + '\n')
        L.append(chart('turns', 'Turns per task', ' data-group="Domain"'))
        L.append(table(['Model', '% of tasks run', 'Mean turns per task', f"% of its tasks at {TT['threshold']}+ turns"],
            [[m['model'], (f"{100 * m['tasks'] / k:.0f}%" if 100 * m['tasks'] / k >= 0.5 else '<1%'), f"{m['mean']:.1f}", f"{100 * m['tasks_200_plus'] / m['tasks']:.0f}%"] for m in TT['by_model']]) + '\n')
    else: L.append('No Gemini turn data for the selected tasks.\n')
    L.append('## Sample tasks\n')
    if not s['showcase']:
        L.append("This catalog has no example yet.\n")
    for i, t in enumerate(s['showcase'], 1):
        x = tx.get(t['name'], {})
        L.append(f"### Example {i}: {t['category']} ({t['language']})\n")
        gem = [m for m in t['models'] if m['graded']]
        L.append(table(['Field', 'Value'], [
            ['Task id', f"[`{t['task_id']}`]({t['url']})"], ['Final category', t['final']], ['Domain', t['super_group']], ['Sub-domain', t['category']],
            ['Language', t['language']], ['Seniority', t['seniority']],
            ['Turn count', (', '.join(f"{v:.0f} ({json.load(open(f'{P}/ro_models.json')).get(m, m)})" for m, v in t['turns']['by_model'].items()) if t.get('turns') else 'no completed run')],
            ['Long horizon', ('yes' if t.get('turns') and t['turns']['mean'] >= 200 else 'no' if t.get('turns') else 'n/a')]], left=True) + '\n')
        ins = instruction(t['name'])
        L.append('#### Prompt\n')
        L.append('<details open><summary>Full instruction given to the agent (instruction.md)</summary>\n<div class="prompt-md">\n\n' + (prompt_md(ins) if ins else '`instruction.md` not found in the current version.') + '\n\n</div>\n</details>\n')
        L.append('#### Pass rates\n')
        if gem:
            L.append(table(['Model', 'Pass rate'], [[m['model'], pct(m['pass_rate'])] for m in gem]) + '\n')
        else: L.append('No graded Gemini runs on the current version.\n')
        L.append('#### Environment\n')
        envsvg = f'env-{slug}-ex{i}.svg'
        # hand-drawn system design diagram for the sample (diagrams/<task id>/draw.py), else the older ones
        if os.path.exists(f"{H}/diagrams/{t['task_id']}/diagram.svg"):
            shutil.copyfile(f"{H}/diagrams/{t['task_id']}/diagram.svg", f"{OUT}/assets/env-{t['task_id']}.svg")
            L.append(f"![How the task works](assets/env-{t['task_id']}.svg)\n")
        elif os.path.exists(f"{OUT}/assets/env-{t['name']}.svg"):
            L.append(f"![How the task works](assets/env-{t['name']}.svg)\n")
        elif t['name'] in ENV and os.path.exists(ENV[t['name']]):
            shutil.copyfile(ENV[t['name']], f'{OUT}/assets/{envsvg}'); L.append(f'![How the task works](assets/{envsvg})\n')
        elif x.get('environment_mermaid'):
            L.append('```mermaid\n' + x['environment_mermaid'].strip() + '\n```\n')
        else: L.append('_Pending._\n')
    L.append(runtime(page_data(s)))
    md = '\n'.join(L)
    open(f'{OUT}/{slug}.md', 'w').write(md)
    index.append((slug, s))
    print(slug, len(md), 'chars', len(s['showcase']), 'examples')
# overview
TOT = sum(s['tasks'] for _, s in index); EST = sum(s['estimate']['estimate'] for _, s in index)
def tt(s, model=None):
    T = s.get('turns') or {}
    if model: return next((f"{m['mean']:.0f}" for m in T.get('by_model') or [] if m['model'] == model), 'n/a')
    return f"{T['mean_of_task_means']:.0f}" if T.get('tasks_with_turns') else 'n/a'
proven = sum(s['tiers'].get('Proven', 0) for _, s in index); likely = TOT - proven
argon = [t for t in U['tasks'] if t['argon']]; argon_g = sum(t['argon']['graded'] for t in argon); argon_p = sum(t['argon']['passed'] for t in argon)
cat_n = sum(s['estimate']['tasks'] for _, s in index)
expected = round(proven + sum(t['p_hard'] for t in U['tasks'] if t.get('tier') == 'Likely'))
ONE = {'programbench': 'Rebuild or upgrade programs to match a reference exactly, or port libraries to another language.',
       'system-design': 'Keep running services and live infrastructure correct through failures and refactors.',
       'debugging': 'Find and fix faults in real codebases from symptoms or documentation.',
       'feature-implementation': 'Add capabilities to existing libraries and services without breaking current behavior.'}
allm = {}
for _, s in index:
    for m in s['models']:
        a = allm.setdefault(m['model'], [0, 0]); a[0] += m['graded']; a[1] += m['passed']
ar = allm['google/gemini-4-argon']; fl = allm['google/gemini-3.8-flash']
L = ['# Coding OTS RL Envs\n']
L.append('<div class="kpis">' + kpi(f"{total:,}", 'Tasks') + kpi(pct(ar[1] / ar[0]), 'Gemini 4 Argon pass rate') + kpi(pct(fl[1] / fl[0]), 'Gemini 3.8 Flash pass rate') + '</div>\n')
L.append("We selected coding RL Envs that challenge Gemini models and grouped them into four catalogs.\n")
L.append(table(['Catalog', 'Tasks', 'What the tasks do', '% of all tasks', 'Average turns, Gemini 4 Argon', 'Average turns, Gemini 3.8 Flash'],
    [[f"[{s['name']}]({slug}.md)", f"{NUM[slug]:,}", ONE[slug], f"{100 * NUM[slug] / total:.1f}%", tt(s, 'google/gemini-4-argon'), tt(s, 'google/gemini-3.8-flash')] for slug, s in index]
    + [['**Total**', f"**{total:,}**", '', '**100%**', '', '']], align='lrlrrr') + '\n')
smp = [(slug, s, i, t) for slug, s in index for i, t in enumerate(s['showcase'], 1)]
gm = lambda t, name: next((pct(m['pass_rate']) for m in t['models'] if m['model'] == name and m['graded']), '')
import unicodedata, math, html as _html
def anchor(title):
    """The heading id build_site.py gives a heading with this text (same rule)."""
    slug = re.sub(r'[^\w\s-]', '', unicodedata.normalize('NFKC', title).lower())
    return re.sub(r'[-\s]+', '-', slug).strip('-') or 'section'
ex_title = lambda i, t: f"Example {i}: {t['category']} ({t['language']})"
L.append('## Samples\n')
L.append("Each sample is a full task. Click its task id to download it, or a main sample's example to read its prompt and environment diagram on its catalog page. Attached samples are extra tasks shared as downloads only.\n")
L.append(table(['Sample', 'Catalog', 'Example', 'Task id', 'Gemini 4 Argon', 'Gemini 3.8 Flash'],
    [['Main', s['name'], f"[{ex_title(i, t)}]({slug}.md#{anchor(ex_title(i, t))})", f"[`{t['task_id']}`]({t['url']})", gm(t, 'google/gemini-4-argon'), gm(t, 'google/gemini-3.8-flash')]
     for slug, s, i, t in smp]
    + [['Attached', s['name'], f"{a['category']} ({a['language']})", f"[`{a['task_id']}`]({a['url']})", pct(a['models']['google/gemini-4-argon']['pass_rate']),
        pct(a['models']['google/gemini-3.8-flash']['pass_rate']) if a['models'].get('google/gemini-3.8-flash', {}).get('graded') else '']
       for slug, s in index for a in s['attached']], text_cols=4) + '\n')
# Gemini 4 Argon failure modes on the samples (the 4 Nov supplement); its counts must add up to the snapshot's Argon runs on the samples
FM = json.load(open(f'{H}/cat/failure_modes.json'))
AR = [next(((m['graded'], m['passed']) for m in t['models'] if m['model'] == 'google/gemini-4-argon'), (0, 0)) for _, _, _, t in smp] \
   + [(a['models']['google/gemini-4-argon']['graded'], a['models']['google/gemini-4-argon']['passed']) for _, s in index for a in s['attached']]
ag, ap = sum(g for g, _ in AR), sum(p for _, p in AR)
assert sum(m['runs'] for m in FM['modes']) == ag - ap and sum(m['tasks'] for m in FM['modes']) == len(AR), 'failure modes do not add up to the snapshot'
two = [(g, p) for g, p in AR if g >= 2]
p1 = sum(p / g for g, p in AR if g) / sum(1 for g, _ in AR if g); p2 = sum(1 - math.comb(g - p, 2) / math.comb(g, 2) for g, p in two) / len(two)
L.append('## Where Gemini 4 Argon fails\n')
L.append(f"Across the {len(AR)} samples, Gemini 4 Argon did not pass {ag - ap} of its {ag} graded runs and passed the other {ap}. We sorted the failures into five failure modes. Each sample is counted once, under its main failure mode, though single runs can fail in different ways.\n")
L.append('<div class="kpis">' + kpi(f'{ag - ap} of {ag}', 'Argon runs not passed') + kpi(pct(p1), 'Argon pass@1 on samples') + kpi(pct(p2), f'Argon pass@2 on the {len(two)} samples with 2+ runs') + '</div>\n')
e_ = lambda x: _html.escape(x, quote=False)
rows_ = ''.join(f'<tr><td>{e_(m["mode"])}</td><td><span class="fm-sum">{e_(m["summary"])}</span><ul class="fm-ex">' + ''.join(f'<li><b>{e_(k)}:</b> {e_(v)}</li>' for k, v in m['examples'])
                + f'</ul></td><td class="numeric">{m["runs"]}</td><td class="numeric">{m["tasks"]}</td></tr>' for m in FM['modes'])
L.append(nob('<div class="table-scroll"><table class="data fm">\n<thead><tr><th>Failure mode</th><th>Details and examples</th><th class="numeric">Runs not passed</th><th class="numeric">Samples</th></tr></thead>\n<tbody>' + rows_
             + f'</tbody>\n<tfoot><tr><td><b>Total</b></td><td></td><td class="numeric"><b>{ag - ap}</b></td><td class="numeric"><b>{len(AR)}</b></td></tr></tfoot>\n</table></div>\n<style>table.fm td{{vertical-align:top}}table.fm .fm-sum{{display:block;font-weight:600;margin-bottom:6px}}table.fm ul{{margin:0;padding-left:18px}}table.fm li{{margin:0 0 6px}}table.fm tfoot td{{border-top:1px solid var(--ink)}}</style>') + '\n')
L.append('### Headroom for improvement\n')
L.append(f"Across the {sum(1 for g, _ in AR if g)} samples, the chance that one Argon run passes (pass@1) is {pct(p1)}. On the {len(two)} samples with two or more graded Argon runs, the chance that at least one of two runs passes (pass@2) is {pct(p2)}. Each sample is weighted equally. Argon can often reach a working solution but does not get there reliably.\n")
L.append(FM['headroom'] + '\n')
L.append('## Pass rates by catalog\n')
L.append("Each cell is a model's pass rate in one catalog: its passed runs over its graded runs there, with errored runs left out.\n")
HM = list(allm)
HEAT = {'models': HM, 'catalogs': [s_['name'] for _, s_ in index], 'minTasks': 5,
        'cells': [[j, HM.index(m['model']), m['graded'], [round(v, 4) for v in m['per_task_rates']], m['passed']] for j, (_, s_) in enumerate(index) for m in s_['models'] if m['per_task_rates']]}
L.append(chart('heat', 'Pass rate by model and catalog').replace('<div class="fig-box" data-body></div>',
    '<div class="fig-box" data-body></div>\n<span data-links hidden>' + ''.join(f'<a href="{k}.html">{s_["name"]}</a>' for k, s_ in index) + '</span>'))
L.append(table(['Model', 'Pass rate'], [[k, pct(v[1] / v[0]) if v[0] else 'n/a'] for k, v in allm.items()]) + '\n')
allt = [m for _, s_ in index for m in (s_.get('turns') or {}).get('task_means') or []]
L.append('## Turn counts\n')
L.append(f"A task's turn count is the average over its runs by Gemini 4 Argon and Gemini 3.8 Flash. Across all catalogs the average is {sum(allt) / len(allt):.0f} turns, and {100 * sum(m >= 200 for m in allt) / len(allt):.0f}% of tasks average 200 turns or more.\n")
TXM = HM; txt = []
for j, (_, s_) in enumerate(index):
    for r in s_['task_rows']:
        if r['turns']: txt.append([j, 0, 0, 0, {}, {TXM.index(m): v for m, v in r['turns'].items()}])
L.append(chart('turns', 'Turns per task, all catalogs', ' data-group="Catalog"'))
L.append(runtime({'cross': False, 'models': TXM, 'dims': {'g': [s_['name'] for _, s_ in index]}, 'tasks': txt, 'bin': 50, 'xmax': 1000, 'threshold': 200, 'heat': HEAT}))
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
