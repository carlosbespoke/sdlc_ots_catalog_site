# Build one ledger per page: every node gets a record. Defaults are "passes"; findings are explicit overrides keyed by node id.
import json, re, sys
def walk(n, parent=None):
    yield n, parent
    for c in n.get('children', []): yield from walk(c, n)
JARGON = re.compile(r'\b(main sample|attached sample|shortlist)\b', re.I)
def build(page, O):
    tree = json.load(open(f'{page}.tree.json')); out = []
    for n, parent in walk(tree):
        t = n['type']; o = O.get(n['id'], {})
        if t == 'block': continue
        if t == 'doc':
            r = dict(id='D', type='doc', main_idea=None, stated_first=True, buried_lead=False, sibling_faults=0, mece_complete=True, notes='')
        elif t == 'section':
            r = dict(id=n['id'], type='section', main_idea=n['title'], stated_first=True, supports_parent=True, buried_lead=False, sibling_faults=0, mece_complete=True, notes='')
        elif t == 'paragraph':
            ss = [c for c in n['children'] if c['type'] == 'sentence']
            r = dict(id=n['id'], type='paragraph', main_idea_sentence=ss[0]['id'] if ss else None, position_ok=True, one_idea=True, offtopic_sentences=[],
                     ends_on_new_idea=False, supports_section=True, link_ok=True, exception=None, notes='')
        elif t == 'list':
            r = dict(id=n['id'], type='list', supports_parent=True, parallel=True, notes='')
        else:
            words = len(n['text'].split()); chk = []
            if words > 30: chk.append(7)
            if JARGON.search(n['text']): chk.append(5)
            r = dict(id=n['id'], type=t, label='new', allowed_exception=False, supports_parent=True, checks_failed=chk, claims=[], fix='', words=words)
        for k, v in o.items():
            if k == 'checks_failed': r[k] = sorted(set(r.get(k, []) + v))
            else: r[k] = v
        if t in ('sentence', 'item') and r['checks_failed'] and not r['fix']:
            r['fix'] = ' / '.join(x for x in ['split into two sentences' if 7 in r['checks_failed'] else '',
                                              'replace internal terms (main/attached sample, shortlist) or define them once' if 5 in r['checks_failed'] else ''] if x)
        out.append(r)
    with open(f'{page}.ledger.jsonl', 'w') as f:
        for r in out: f.write(json.dumps(r) + '\n')
    return len(out)

BEH = 'British "behaviour" here, American "behavior" in the example write-ups; pick one'
P2 = lambda lang_s: {'one_idea': False, 'ends_on_new_idea': True, 'notes': 'Pass rates and languages in one paragraph; ends on a new idea (languages); domain table below it is not introduced by any sentence.'}
REPEAT = lambda src, fix: {'label': 'repeat', 'checks_failed': [21], 'fix': fix, 'notes': src}
JARG = {'checks_failed': [5, 13]}

O = {}
O['README'] = {
 'D': {'main_idea': 'Coding RL environments in 4 catalogs; Gemini 4 Argon passes 23% and Gemini 3.8 Flash 2%.', 'notes': 'Opening says what the set is, not why it exists: the reason these tasks were chosen (they are hard for Gemini) is never stated.'},
 'D.P1': {'one_idea': False, 'ends_on_new_idea': True, 'notes': 'Description, results and scope note in one paragraph; ends on the scope note.'},
 'D.P1.s1': {'checks_failed': [19], 'fix': 'Spell out "four catalogs"; add the point: "...grouped into four catalogs and chosen because Gemini rarely passes them."'},
 'D.P1.s3': {'checks_failed': [6, 14], 'claims': ['Gemini 4 Argon passes 23% of its runs', 'Gemini 3.8 Flash passes 2%'], 'fix': 'Bound the scope: "On the tasks each model has run, Gemini 4 Argon passes 23% of its runs and Gemini 3.8 Flash 2%."'},
 'D.P1.s4': {'fix': 'Move to a footnote under the table, or open the Gemini pass rates section with it.'},
 'D.S1': {'stated_first': False, 'notes': 'Plot and table with no sentence stating the takeaway; repeats the opening numbers.'},
 'D.S2': {'sibling_faults': 1, 'notes': 'The all-catalog turn-count plot sits inside Samples with no heading or framing sentence.'},
 'D.S2.P1.s1': {'checks_failed': [5, 13, 19], 'claims': ['3 main samples, 12 attached'], 'fix': '"Three samples are written up in full in the catalog pages, and 12 more are attached." (define "attached"; avoid opening with a numeral)'},
 'D.S2.P1.s2': {'fix': 'Name the source the reader knows, or cut: "All come from our curated shortlist of 120 tasks."'},
}
O['programbench'] = {
 'D': {'main_idea': 'Tasks that make software match a reference exactly (reimplement, upgrade, migrate); Gemini rarely passes them.', 'notes': 'No sentence under the title; the Executive summary carries the governing idea.'},
 'D.S1.P2': P2('s3'), 'D.S1.P2.s3': {'checks_failed': [6, 13], 'fix': '"Agent\'s choice" is not a language: "42% of tasks let the agent choose the language; the rest use Go (23%) or C++ (13%)."'},
 'D.S1.P2.s1': {'claims': ['Argon passes 39% of its runs', 'fails every run on 27% of tasks'], 'checks_failed': [14], 'fix': 'Say the rate covers the tasks Argon has run, not all 283.'},
 'D.S1.P2.s2': {'claims': ['Gemini 3.8 Flash passes 1%', 'fails every run on 96%']},
 'D.S2': {'notes': 'No lead sentence saying why the catalog matters; subsections carry it.'},
 'D.S2.S1.P1.s1': {'label': 'unverifiable', 'checks_failed': [7, 21], 'fix': 'Anchor in the tasks rather than a general claim about engineers, and split: "These tasks ask for software that behaves exactly like a version the engineer cannot reuse."'},
 'D.S2.S2.P1': {'position_ok': False, 'main_idea_sentence': 'D.S2.S2.P1.s5', 'notes': 'Main idea (offline, hidden tests compare with the reference) comes last; s1 covers only two of the three task types.'},
 'D.S2.S2.P1.s1': REPEAT('repeats Executive summary s1', 'Cut; open with s5 as the main idea.'),
 'D.S2.S2.P1.s5': {'label': 'repeat', 'checks_failed': [21], 'fix': 'Move to the front as the main idea and cut the repeat in the Executive summary.'},
 'D.S5': {'stated_first': False, 'notes': 'Table and plot with no takeaway sentence; numbers repeat the Executive summary.'},
 'D.S6.P1': {'notes': 'Defines the measure but never states the result (average 420 turns, share long horizon).'},
 'D.S7.P1.s1': JARG, 'D.S7.P1.s2': {'checks_failed': [5], 'claims': ['all examples pass at most half their Gemini runs']},
 'D.S7.S1.S4.P1.s2': {'checks_failed': [19], 'fix': '"floating point" -> "floating-point" (attributive)'},
}
O['system-design'] = {
 'D': {'main_idea': 'Changes to running production systems (multi-process services and live Terraform); Gemini rarely passes them.', 'notes': 'Governing idea carried by the Executive summary.'},
 'D.S1.P2': P2('s3'), 'D.S1.P2.s3': {'checks_failed': [19], 'fix': 'Avoid nested parentheses: "Terraform HCL (33%), Go (31%) and Python (13%)".'},
 'D.S1.P2.s1': {'claims': ['Argon passes 20%', 'fails every run on 44%'], 'checks_failed': [14], 'fix': 'Say the rate covers the tasks Argon has run.'},
 'D.S1.P2.s2': {'claims': ['Flash passes 10%', 'fails every run on 73%']},
 'D.S2.S1.P1.s1': REPEAT('repeats Executive summary s1 almost verbatim', 'Cut, or replace with what makes this hard: "The failures appear only when processes stop, retry or race."'),
 'D.S2.S2.P1': {'main_idea_sentence': None, 'one_idea': False, 'notes': 'Two task types (services, infrastructure) with no sentence that covers both.'},
 'D.S2.S2.P1.s3': REPEAT('repeats Executive summary s2 (hidden tests kill or pause processes)', 'Keep here, cut from the Executive summary.'),
 'D.S5': {'stated_first': False, 'notes': 'No takeaway sentence; repeats Executive summary numbers.'},
 'D.S6.P1': {'notes': 'Defines the measure but never states the result.'},
 'D.S7': {'sibling_faults': 1, 'notes': 'Examples 5 and 6 have identical headings ("Cloud infra: AWS platform stacks (HCL (Terraform))").'},
 'D.S7.P1.s1': JARG, 'D.S7.P1.s2': {'checks_failed': [5]},
 'D.S7.S5.S4.P1.s3': {'checks_failed': [6], 'fix': 'Say what the CI plan checks: "CI accepts the change only when the plan shows moves and no replacements."'},
}
O['debugging'] = {
 'D': {'main_idea': 'Finding and fixing faults in real codebases from symptoms or documentation; Gemini rarely passes them.', 'notes': 'Governing idea carried by the Executive summary.'},
 'D.S1.P2': P2('s3'),
 'D.S1.P2.s1': {'claims': ['Argon passes 25%', 'fails every run on 71%'], 'checks_failed': [14], 'fix': 'Say the rate covers the tasks Argon has run.'},
 'D.S1.P2.s2': {'claims': ['Flash passes 7%', 'fails every run on 67%']},
 'D.S2.S1.P1.s1': {'label': 'unverifiable', 'checks_failed': [21], 'fix': 'Tie to the tasks: "Each task hands the agent code that is wrong in several places and no test suite."'},
 'D.S2.S1.P1.s5': REPEAT('repeats Executive summary s2', 'Cut, or keep here and shorten the Executive summary.'),
 'D.S2.S2.P1.s5': REPEAT('repeats Executive summary s3 almost verbatim', 'Cut.'),
 'D.S5': {'stated_first': False, 'notes': 'No takeaway sentence; repeats Executive summary numbers.'},
 'D.S6.P1': {'notes': 'Defines the measure but never states the result.'},
 'D.S7.P1.s1': JARG, 'D.S7.P1.s2': {'checks_failed': [5]},
 'D.S7.S2.S4.P1.s3': {'label': 'filler', 'checks_failed': [5, 13, 21], 'fix': 'Cut ("family" is internal vocabulary and the prompt-shape line already says this).'},
 'D.S7.S4.S4.P1.s3': {'label': 'repeat', 'checks_failed': [15, 21], 'fix': 'Cut; the prompt-shape line already says it is written as a ticket.'},
 'D.S7.S4.P1.s1': {'checks_failed': [13], 'fix': 'Use the same path as Example 1: `/app/rca.json`; split the sentence.'},
}
O['feature-implementation'] = {
 'D': {'main_idea': 'Adding capabilities to existing libraries and services without breaking current behaviour; Gemini rarely passes them.', 'notes': 'Governing idea carried by the Executive summary.'},
 'D.S1.P1.s1': {'checks_failed': [6], 'fix': '"specified the way a series of pull requests would be" is vague; say what the spec contains (required types and signatures).'},
 'D.S1.P2': P2('s3'),
 'D.S1.P2.s1': {'claims': ['Argon passes 11%', 'fails every run on 85%'], 'checks_failed': [14], 'fix': 'Say the rate covers the tasks Argon has run.'},
 'D.S1.P2.s2': {'claims': ['Flash passes 0%', 'fails every run on 98%'], 'checks_failed': [17], 'fix': '"passes 0%" while it has 2 passes: write "under 1%".'},
 'D.S2.S1.P1': {'offtopic_sentences': ['D.S2.S1.P1.s3'], 'notes': 's3 (data pipelines) is a second problem, not support for s1.'},
 'D.S2.S1.P1.s1': REPEAT('repeats Executive summary s1', 'Replace with what makes it hard, e.g. the number of code paths a change touches.'),
 'D.S2.S1.P1.s3': {'supports_parent': False, 'fix': 'Give the data-pipeline problem its own short paragraph.'},
 'D.S2.S2.P1.s3': REPEAT('repeats Executive summary s3', 'Cut from one of the two places.'),
 'D.S5': {'stated_first': False, 'notes': 'No takeaway sentence; repeats Executive summary numbers.'},
 'D.S6.P1': {'notes': 'Defines the measure but never states the result.'},
 'D.S7': {'mece_complete': False, 'notes': 'All three examples are data-pipeline tasks (5% of the catalog); none shows the core feature work.'},
 'D.S7.P1.s1': JARG, 'D.S7.P1.s2': {'checks_failed': [5]},
}
for p, o in O.items(): print(p, build(p, o), 'records')
