import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('SwanLab: diverged runs score 0.0 in the sweep CSV',
        'A sweep logs metrics in local mode with the CSVWriter plugin. Runs whose loss went to NaN show 0.0 in swanlab_runs.csv and sort to the top, while swanlab watch shows NaN. The agent finds where the value is lost, fixes it at the source, adds a regression test and names the root causes.')

def table(x, y, cols, rows, widths, hl=None):
    hl = hl or {}; rh = 22; xx = x
    for name, w in zip(cols, widths):
        D.el.append(f'<rect x="{xx}" y="{y}" width="{w}" height="{rh}" fill="{TEAL}" stroke="{TEAL}"/>')
        D._t(xx + 7, y + 15, name, 11, True, '#ffffff'); xx += w
    for r, row in enumerate(rows):
        xx = x; yy = y + rh * (r + 1)
        for c, (v, w) in enumerate(zip(row, widths)):
            k = hl.get((r, c)); fill = {'bad': '#fdecea', 'good': LIME}.get(k, '#ffffff')
            D.el.append(f'<rect x="{xx}" y="{yy}" width="{w}" height="{rh}" fill="{fill}" stroke="#cfcac2"/>')
            D._t(xx + 7, yy + 15, v, 11, k is not None, {'bad': '#c83220'}.get(k, INK)); xx += w
    return y + rh * (len(rows) + 1)

top, bot = 112, 448
D.zone(20, top, 740, bot - top, 'Agent edits: /workdir', 'app', 'SwanLab checkout (Python), git repository; sweeps run in local mode')
D.box('log', 36, top + 66, 160, 'swanlab.log', 'val/loss goes to NaN in the last epochs', 'client', 'python')
D.box('sdk', 236, top + 66, 200, 'SDK internals', 'somewhere on this path the NaN is lost; the agent has to find where', 'fault', tag='?')
D.box('lc', 486, top + 40, 254, 'swanlab watch', 'local run logs end in NaN, as they should', 'svc')
D.box('out', 486, top + 150, 254, 'CSVWriter plugin: swanlab_runs.csv', 'the same runs show val/loss = 0.0', 'fault')
D.arrow([(196, top + 96), (236, top + 96)])
D.arrow([(436, top + 86), (460, top + 86), (460, top + 70), (486, top + 70)])
D.arrow([(436, top + 106), (460, top + 106), (460, top + 180), (486, top + 180)])
D.el.append(f'<rect x="36" y="{top + 236}" width="704" height="76" rx="5" fill="#ffffff" stroke="{TEAL}" stroke-dasharray="4 3"/>')
D._t(48, top + 258, 'Agent delivers', 12, True, TEAL)
D.note(48, top + 276, 680, 'A fix in the library at the source (not a special case for this input), a regression test such as tests/test_repro.py that fails today and passes after any correct fix, and /workdir/rca.json naming the function(s) where the problem starts.', 11.5, GREY)
D.zone(780, top, 300, bot - top, 'Hidden grader', 'grader', 'reward 1 only if R, L and F all pass')
gy = top + 52
for k, t, b in [('R', 'Reproduce', 'the regression test fails on the current code and passes with correct fixes'),
                ('L', 'Locate', 'rca.json root causes are compared with the known ones; extra entries count against it'),
                ('F', 'Fix', 'hidden tests of the reported behavior pass, and the full existing suite still passes')]:
    D.badge(806, gy + 20, k, RED)
    h = D.box(k, 822, gy, 242, t, b, 'fault'); gy += h + 10
# bottom: what the user sees today
y0 = bot + 26
D.zone(20, y0, 1060, 214, 'The visible discrepancy, on an illustrative sweep', 'plain', 'the same four runs, read from the CSV and from swanlab watch; the winner is picked by sorting the CSV on final val/loss')
cols, W = ['run', 'final val/loss'], [110, 130]
D._t(36, y0 + 70, 'swanlab_runs.csv, sorted', 12, True, '#c83220')
y = table(36, y0 + 80, cols, [['lr-0.3', '0.0'], ['lr-1.0', '0.0'], ['lr-0.01', '0.74'], ['lr-0.001', '0.92']], W, {(0, 1): 'bad', (1, 1): 'bad'})
D.arrow([(300, y0 + 136), (380, y0 + 136)], 'same runs', kind='muted', both=True, loff=(0, -8))
D._t(396, y0 + 70, 'swanlab watch', 12, True, TEAL)
y = table(396, y0 + 80, cols, [['lr-0.3', 'NaN'], ['lr-1.0', 'NaN'], ['lr-0.01', '0.74'], ['lr-0.001', '0.92']], W, {(0, 1): 'good', (1, 1): 'good'})
D.note(680, y0 + 92, 384, 'Two runs blew up near the end. swanlab watch shows NaN, but the CSV records 0.0, so the diverged runs sort to the top and one of them is picked as the best learning rate.', 12, INK)
D.note(680, y0 + 172, 384, 'Values are illustrative; the instruction reports the pattern, not these numbers.', 11, GREY)
D.h = y0 + 214 + 20
D.save(HERE + '/diagram.svg')
