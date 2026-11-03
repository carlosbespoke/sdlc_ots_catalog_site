import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('dagre-rs: port a graph layout library from Rust to Go',
        'The agent gets the Rust crate and a Go package whose functions are stubs with their final signatures. It fills in every body so the Go code returns exactly what the Rust code returns, then the crate\'s own tests, ported to Go and kept hidden, score the port.')
top, bot = 104, 470
D.zone(20, top, 330, bot - top, 'Reference: /app/rust_reference', 'side', 'kookyleo/dagre-rs, 30 files, 6,785 lines')
D.box('g', 36, top + 52, 298, 'graph', 'graph store, algorithms (Dijkstra, Tarjan, topological sort), JSON', 'svc', 'rust')
D.box('l', 36, top + 132, 298, 'layout', 'acyclic, rank (network simplex), normalize, order (barycenter, crossing count), position (Brandes-Köpf), intersect', 'svc', 'rust')
D.box('t', 36, top + 244, 298, 'types and util', 'node and edge labels, rank direction, coordinate system', 'svc', 'rust')
D.zone(390, top, 330, bot - top, 'Agent edits: /app/port', 'app', 'Go 1.21 package, offline')
D.box('sk', 406, top + 52, 298, 'Skeleton: 143 stubs', 'every exported type and function with its final signature; bodies are panic("not implemented")', 'svc', 'go', tag='FILL IN')
D.box('mc', 406, top + 162, 298, 'mig-check (on the PATH)', 'diffs signatures against the stubs, runs go build and go vet, flags name clashes with test helpers', 'new')
D.box('rules', 406, top + 262, 298, 'Constraints', 'no os, net, unsafe, syscall, cgo or embed; RE2 regular expressions only; 2 vCPUs, 60 s and 2 GB per test', 'muted')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs after the session')
D.box('sp', 776, top + 52, 288, "Crate's tests ported to Go", '528 required tests in 7 files', 'fault', 'test-pipe')
y = top + 132
for name, n in [('graph', 255), ('layout', 74), ('layout phases', 59), ('order', 50), ('position', 48), ('rank', 34), ('intersect', 8)]:
    D._t(790, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="{900}" y="{y - 6}" width="{n / 255 * 120:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 22
D.box('sc', 776, y + 6, 288, 'Score', 'weighted share of tests passed; a test that panics or times out scores 0', 'dark')
D.arrow([(334, top + 190), (370, top + 190), (370, top + 100), (406, top + 100)], 'port', lpos=.5, loff=(16, 4))
D.arrow([(555, top + 140), (555, top + 162)], kind='new', both=True)
D._t(566, top + 155, 'run often', 11, False, '#5b7d12')
D.arrow([(704, top + 92), (776, top + 76)], 'patch', lpos=.5, loff=(0, -8))
# the pipeline the port must reproduce
y0 = bot + 28
D.zone(20, y0, 1060, 336, 'What the Go code must reproduce, stage by stage', 'plain', 'dagre lays out a directed graph in layers; each stage must give the same output as the Rust code, down to node order and float coordinates')
pw, gap, py = 160, 16, y0 + 70
NW, NH = 26, 22
def NODE(x, y, s, kind='svc'):
    D.el.append(f'<rect x="{x - NW / 2}" y="{y - NH / 2}" width="{NW}" height="{NH}" rx="4" fill="{KIND[kind][0]}" stroke="{KIND[kind][1]}" stroke-width="1.2"/>'); D._t(x, y + 4, s, 11, True, KIND[kind][2], 'middle')
def DUMMY(x, y): D.el.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#ffffff" stroke="{TEAL}" stroke-width="1.2" stroke-dasharray="2 2"/>')
def clip(p, q, dummy=False):
    dx, dy = q[0] - p[0], q[1] - p[1]
    if dummy: r = 6 / (dx * dx + dy * dy) ** .5
    else: r = min((NW / 2 + 2) / abs(dx) if dx else 9, (NH / 2 + 2) / abs(dy) if dy else 9)
    return (q[0] - dx * r, q[1] - dy * r)
def E(p, q, kind='flow', pd=False, qd=False, head=True):
    D.arrow([clip(q, p, pd), clip(p, q, qd)], kind=kind, width=1.2, head=head)
def CURVE(p, q, kind, bend):
    c = (p[0] + q[0]) / 2 + bend, (p[1] + q[1]) / 2
    a, b = clip(c, p), clip(c, q); col = EDGE[kind][0]
    D.el.append(f'<path d="M{a[0]:.1f},{a[1]:.1f} Q{c[0]:.1f},{c[1]:.1f} {b[0]:.1f},{b[1]:.1f}" fill="none" stroke="{col}" stroke-width="1.4" stroke-dasharray="{EDGE[kind][1] or ""}" marker-end="url(#a-{kind})"/>')
stages = ['1  Input graph', '2  Break cycles', '3  Assign ranks', '4  Split long edges', '5  Order each rank', '6  Coordinates']
notes = ['5 nodes; e → a closes a cycle', 'reverse e → a, so it becomes a → e', 'network simplex puts each node in a layer', 'a → e skips a layer, so it gets a dummy node', 'barycenter sweeps move the dummy and remove the crossing', 'Brandes-Köpf x, rank y; edge ends clipped to node borders']
BASE = [('a', 'b'), ('a', 'c'), ('b', 'd'), ('c', 'd'), ('c', 'e')]
for i, (st, n) in enumerate(zip(stages, notes)):
    x = 36 + i * (pw + gap); cx = x + pw / 2
    D.el.append(f'<rect x="{x}" y="{py}" width="{pw}" height="200" rx="6" fill="#fbf9f4" stroke="#cfcac2"/>')
    D._t(x + 10, py + 20, st, 12, True, TEAL)
    D.note(x + 4, py + 222, pw - 6, n, 11, GREY)
    if i <= 1:
        P = {'a': (cx - 35, py + 58), 'b': (cx + 45, py + 75), 'c': (cx - 40, py + 120), 'd': (cx + 35, py + 165), 'e': (cx - 45, py + 175)}
    else:
        P = {'a': (cx - 10, py + 55), 'b': (cx - 50, py + 110), 'c': (cx + 5, py + 110), 'd': (cx - 25, py + 165), 'e': (cx + 45, py + 165)}
    if i == 2: [D.el.append(f'<line x1="{x + 6}" y1="{yy}" x2="{x + pw - 6}" y2="{yy}" stroke="#b9dcd3" stroke-width="1" stroke-dasharray="4 3"/>') for yy in (py + 55, py + 110, py + 165)]
    for u, v in BASE: E(P[u], P[v])
    if i == 0: CURVE(P['e'], P['a'], 'fault', -38)
    elif i == 1: CURVE(P['a'], P['e'], 'new', -38)
    elif i == 2: E(P['a'], P['e'], 'new')
    else:
        dm = (cx - 22, py + 110) if i == 3 else (cx + 50, py + 110)
        E(P['a'], dm, qd=True); E(dm, P['e'], pd=True); DUMMY(*dm)
        if i == 3: D.el.append(f'<circle cx="{cx - 13}" cy="{py + 138}" r="9" fill="none" stroke="{RED}" stroke-width="1.4"/>')
    for k, p in P.items(): NODE(*p, k, 'new' if (i in (1, 2) and k in 'ae') else 'svc')
    if i == 5:
        D._t(P['a'][0] + 18, P['a'][1] + 4, 'x 65, y 30', 9.5, False, GREY)
        for k, lab in (('d', 'x 40, y 130'), ('e', 'x 110, y 130')): D._t(P[k][0], P[k][1] + 25, lab, 9.5, False, GREY, 'middle')
    if i < 5: D.arrow([(x + pw + 2, py + 100), (x + pw + gap - 2, py + 100)], width=1.2)
D.h = y0 + 336 + 20
D.save(HERE + '/diagram.svg')
