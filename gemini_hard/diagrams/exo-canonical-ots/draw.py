import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('Exo: fix every place the compiler drifted from its documentation',
        'Exo is a Python-embedded language and compiler for high-performance kernels. Its code no longer does what its own pages and docstrings say. The agent finds each disagreement and changes the code, never the documentation.')
top = 104
def stack(items, x, w, y, gap=12):
    for id, t, b, k, ic in items:
        y += D.box(id, x, y, w, t, b, k, ic) + gap
    return y
y1 = stack([('rd', 'README.md', 'what Exo is and how to use it', 'file', 'markdown'),
            ('dc', 'docs/, 12 pages', 'cursors, procedures, memories, instructions, externs, inspection, object code', 'file', 'book'),
            ('pr', 'docs/primitives/, 6 pages', 'loop, buffer, config, sub-procedure, backend and other scheduling operations', 'file', 'book'),
            ('ds', 'Docstrings', 'module, class and function docstrings of the 42 in-scope modules, examples included', 'file', 'python')], 36, 298, top + 52)
y2 = stack([('code', '42 in-scope modules', 'frontend, core, rewrite, backend, stdlib and API; src/exo/platforms/ is out of scope', 'svc', 'python'),
            ('cm', 'Code comments', 'supporting evidence only; when a comment contradicts the documentation, follow the documentation', 'muted', None),
            ('api', 'Public API stays stable', 'behaviour that already matches its documentation must work exactly as before', 'muted', None)], 406, 298, top + 52, 16)
y3 = stack([('ob', '124 observations', '123 small Exo programs compared with sealed expected values, plus one unedited-documentation check', 'fault', 'test-pipe'),
            ('f2p', '11 drift groups, 30 observations', 'fail on the delivered code, pass after the reference repair', 'fault', None),
            ('p2p', '44 guard groups, 94 observations', 'already pass and must keep passing', 'client', None),
            ('sc', 'Score', 'mean of drift groups fixed, times mean of guard groups kept', 'dark', None)], 776, 288, top + 52)
D.tag(704 - 8, top + 52 - 8, 'FIX')
bot = max(y1, y2, y3) + 6
D.zone(20, top, 330, bot - top, 'Documentation: the authority', 'side', 'read only; editing it to hide a drift does not count')
D.zone(390, top, 330, bot - top, 'Agent edits: /workdir/src/exo', 'app', 'Python 3.12, PySMT, z3-solver, offline')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs as user nobody after the session')
D.arrow([(334, D.pt('dc', 'r')[1]), (370, D.pt('dc', 'r')[1]), (370, top + 90), (406, top + 90)], 'compare', lpos=.5, loff=(-22, 0))
D.arrow([(704, top + 90), (776, top + 90)], 'patch', lpos=.5, loff=(0, -8))
# bottom: the compiler pipeline, and the rule for each disagreement
y0 = bot + 26
py = y0 + 62
stages = [('@proc, @instr, @config', 'object code in Python'), ('parse and type-check', 'pyparser, typecheck'), ('bounds-check', 'boundscheck'),
          ('schedule', 'primitives through cursors and patterns'), ('compile to C', 'exocc, compile_procs, c_code_str')]
bw, gap = 186, 23
for i, (t, b) in enumerate(stages):
    x = 36 + i * (bw + gap)
    D.box(f's{i}', x, py, bw, t, b, 'svc', h=70)
    if i: D.arrow([(x - gap + 2, py + 35), (x - 2, py + 35)])
ry = py + 100
D.box('doc', 36, ry, 240, 'The documentation says', 'a signature, a default, an allowed range, an output form', 'file', 'book', h=76)
D.box('run', 36, ry + 116, 240, 'The code does', 'what Exo prints, returns or raises at runtime', 'svc', 'python', h=76)
cx, cy = 356, ry + 96
D.el.append(f'<circle cx="{cx}" cy="{cy}" r="38" fill="#ffffff" stroke="{TEAL}" stroke-width="1.4"/>')
D._t(cx, cy - 3, 'same', 11.5, True, TEAL, 'middle'); D._t(cx, cy + 12, 'behaviour?', 11.5, True, TEAL, 'middle')
D.arrow([(276, ry + 38), (300, ry + 38), (300, cy - 14), (318, cy - 14)])
D.arrow([(276, ry + 154), (300, ry + 154), (300, cy + 14), (318, cy + 14)])
D.box('keep', 470, ry - 4, 290, 'Yes: leave it exactly as it is', 'checked by the 94 guard observations', 'client', h=60)
D.box('fix', 470, ry + 66, 290, 'No: change the code to match', 'checked by the 30 drift observations', 'new', h=60)
D.box('no', 470, ry + 136, 290, 'Never: edit or delete the documentation', 'one guard observation checks every page and docstring is unedited', 'fault', h=76)
D.arrow([(cx + 30, cy - 24), (430, cy - 24), (430, ry + 26), (470, ry + 26)], kind='ok')
D.arrow([(cx + 38, cy), (470, cy)], kind='new')
D.arrow([(cx + 30, cy + 24), (430, cy + 24), (430, ry + 166), (470, ry + 166)], kind='fault')
D.cross(744, ry + 150, 8)
D.note(790, ry + 10, 274, 'The prompt names the scope and the rule, not the drifts. The agent finds them by reading the documentation against the code, stage by stage.', 12.5, TEAL, True)
H = ry + 212 + 22 - y0
D.zone(20, y0, 1060, H, 'Where a drift can sit, and what to do with it', 'plain', 'every compiler stage is in scope; each documented behaviour is checked against what the code actually does')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
