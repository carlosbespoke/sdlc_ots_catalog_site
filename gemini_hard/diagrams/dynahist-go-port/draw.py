import os, sys, math; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('DynaHist: port a histogram library from Java to Go',
        'The agent gets the Java library and a Go package whose functions are stubs with their final signatures. It fills in every body so the Go code returns exactly what the Java code returns, then the library\'s own tests, ported to Go and kept hidden, score the port.')
top, bot = 104, 470
D.zone(20, top, 330, bot - top, 'Reference: /app/java_reference', 'side', 'dynatrace-oss/dynahist, 30 source files, 7,258 lines')
D.box('h', 36, top + 52, 298, 'Histograms', 'dynamic, static and preprocessed histograms; add, merge, rank and quantile queries', 'svc', 'openjdk')
D.box('l', 36, top + 138, 298, 'Layouts', 'log-linear, log-quadratic, log-optimal, OpenTelemetry exponential and custom bin boundaries', 'svc', 'openjdk')
D.box('s', 36, top + 242, 298, 'Estimators, serialization, util', 'SciPy quantile and value estimators, bit-level I/O and varints, interpolation and search helpers', 'svc', 'openjdk')
D.zone(390, top, 330, bot - top, 'Agent edits: /app/port', 'app', 'Go 1.21 package, offline')
D.box('sk', 406, top + 52, 298, 'Skeleton: 49 stubbed functions', 'plus the Layout and Histogram interfaces with final signatures; bodies panic', 'svc', 'go', tag='FILL IN')
D.box('mc', 406, top + 168, 298, 'mig-check (on the PATH)', 'diffs signatures against the stubs, runs go build and go vet, flags name clashes with test helpers', 'new')
D.box('rules', 406, top + 268, 298, 'Constraints', 'no os, net, unsafe, syscall, cgo or embed; RE2 regular expressions only; 2 vCPUs, 60 s and 2 GB per test', 'muted')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs after the session')
D.box('sp', 776, top + 52, 288, "Library's tests ported to Go", '135 required tests in 5 files', 'fault', 'test-pipe')
y = top + 136
for name, n in [('layout', 56), ('histogram', 38), ('utility', 30), ('serialization', 6), ('value', 5)]:
    D._t(790, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="900" y="{y - 6}" width="{n / 56 * 120:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 24
D.box('sc', 776, y + 14, 288, 'Score', 'weighted share of tests passed; a test that panics or times out scores 0', 'dark')
D.arrow([(334, top + 186), (370, top + 186), (370, top + 100), (406, top + 100)], 'port', lpos=.5, loff=(16, 4))
D.arrow([(555, top + 146), (555, top + 168)], kind='new', both=True)
D._t(566, top + 161, 'run often', 11, False, '#5b7d12')
D.arrow([(704, top + 92), (776, top + 76)], 'patch', lpos=.5, loff=(0, -8))
# what the port must reproduce
y0 = bot + 28
D.zone(20, y0, 1060, 340, 'What the Go code must reproduce, stage by stage', 'plain', 'a value goes into a bin, counts are stored compactly, quantiles are read back and the histogram is written to bytes; each step must match the Java output exactly')
pw, gap, py = 196, 14, y0 + 70
stages = ['1  Record values', '2  Layout picks a bin', '3  Counts array grows', '4  Estimate quantiles', '5  Serialize']
notes = ['addValue(value, count); NaN is rejected, infinities are kept',
         'bin widths stay within an absolute or a relative limit',
         'the index range widens, and counts get 2^mode bits when a count outgrows its width',
         'SciPy estimator (alphap, betap) plus a value policy inside the bin',
         'the bytes must equal what the Java writer produces']
for i, (st, n) in enumerate(zip(stages, notes)):
    x = 32 + i * (pw + gap); cx = x + pw / 2
    D.el.append(f'<rect x="{x}" y="{py}" width="{pw}" height="200" rx="6" fill="#fbf9f4" stroke="#cfcac2"/>')
    D._t(x + 10, py + 20, st, 12, True, TEAL)
    D.note(x + 4, py + 222, pw - 8, n, 11, GREY)
    if i < 4: D.arrow([(x + pw + 1, py + 100), (x + pw + gap - 1, py + 100)], width=1.2)
    if i == 0:
        for j, (lab, k) in enumerate([('add 0.4', 'svc'), ('add 3.7', 'new'), ('add 3.9', 'svc'), ('add 120, count 5', 'svc'), ('add NaN', 'fault')]):
            yy = py + 40 + j * 30; w = tw(lab, 11.5, True) + 20
            f, s, c, _ = KIND[k]
            D.el.append(f'<rect x="{cx - w / 2}" y="{yy}" width="{w}" height="22" rx="11" fill="{f}" stroke="{s}" stroke-width="1.1"/>')
            D._t(cx, yy + 15, lab, 11.5, True, c, 'middle')
        D.cross(cx + 50, py + 171, 5)
    elif i == 1:
        ly = py + 120
        D.el.append(f'<line x1="{x + 12}" y1="{ly}" x2="{x + pw - 12}" y2="{ly}" stroke="{TEAL}" stroke-width="1.4"/>')
        ticks = [x + 14 + k * 9 for k in range(5)]
        t = ticks[-1]; w = 9
        while t + w < x + pw - 14: w *= 1.32; t += w; ticks.append(t)
        for k, tx in enumerate(ticks):
            D.el.append(f'<line x1="{tx:.1f}" y1="{ly - 9}" x2="{tx:.1f}" y2="{ly + 9}" stroke="{TEAL}" stroke-width="1.1"/>')
        hb = 8
        D.el.append(f'<rect x="{ticks[hb]:.1f}" y="{ly - 9}" width="{ticks[hb + 1] - ticks[hb]:.1f}" height="18" fill="{LIME}" stroke="{TEAL}" stroke-width="1.1"/>')
        vx = ticks[hb] + (ticks[hb + 1] - ticks[hb]) * .4
        D.arrow([(vx, py + 62), (vx, ly - 11)], kind='new', width=1.3)
        D._t(vx, py + 55, '3.7', 11.5, True, TEAL, 'middle')
        D._t((ticks[hb] + ticks[hb + 1]) / 2, ly + 26, 'bin index i', 10.5, False, GREY, 'middle')
        D._t(x + 14, ly + 50, 'linear near 0', 10, False, GREY)
        D._t(x + pw - 14, ly + 50, 'logarithmic', 10, False, GREY, 'end')
    elif i == 2:
        cw = 22; rx = x + 16
        for row, (vals, mode, ry) in enumerate([([1, 0, 2, 1], 'mode 1: 2 bits', py + 56), ([1, 0, 2, 1, 0, 0, 5], 'mode 2: 4 bits', py + 128)]):
            for k, v in enumerate(vals):
                new = row == 1 and k >= 4
                D.el.append(f'<rect x="{rx + k * cw}" y="{ry}" width="{cw}" height="24" fill="{LIME if new else "#ffffff"}" stroke="{TEAL}" stroke-width="1.1"' + (' stroke-dasharray="3 2"' if new else '') + '/>')
                D._t(rx + k * cw + cw / 2, ry + 16, str(v), 11, True, TEAL, 'middle')
            D._t(rx, ry + 42, mode, 10.5, False, GREY)
        D.arrow([(cx, py + 104), (cx, py + 124)], 'add 120, count 5', kind='new', lpos=.5, loff=(52, 4), width=1.2)
    elif i == 3:
        hs = [8, 22, 40, 52, 36, 20, 12, 6]
        bx = x + 18; bw = 19; base = py + 160
        for k, hh in enumerate(hs):
            D.el.append(f'<rect x="{bx + k * bw}" y="{base - hh * 1.8}" width="{bw - 3}" height="{hh * 1.8}" fill="{MINT}" stroke="{TEAL}" stroke-width="1"/>')
        mx = bx + 3 * bw + 9
        D.el.append(f'<line x1="{mx}" y1="{py + 46}" x2="{mx}" y2="{base + 4}" stroke="{RED}" stroke-width="1.4" stroke-dasharray="4 3"/>')
        D._t(mx + 6, py + 52, 'median', 11, True, '#c83220')
        D.el.append(f'<line x1="{bx - 4}" y1="{base}" x2="{bx + 8 * bw}" y2="{base}" stroke="{TEAL}" stroke-width="1.1"/>')
    elif i == 4:
        segs = ['serial version', 'info byte', 'min, max (double)', 'under / overflow (varint)', 'first, last bin (varint)', 'bit-packed counts']
        for k, sg in enumerate(segs):
            yy = py + 34 + k * 26
            D.el.append(f'<rect x="{x + 16}" y="{yy}" width="{pw - 32}" height="22" rx="3" fill="{"#ffffff" if k < 5 else LIME}" stroke="{TEAL}" stroke-width="1.1"/>')
            D._t(x + 26, yy + 15, sg, 11, False, TEAL)
D.h = y0 + 340 + 20
D.save(HERE + '/diagram.svg')
