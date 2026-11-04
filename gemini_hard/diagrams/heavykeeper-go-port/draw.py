import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('heavykeeper-rs: port a top-k sketch library from Rust to Go',
        'The agent gets the Rust crate and a Go package whose functions are stubs with their final signatures. It fills in every body so the Go code returns exactly what the Rust code returns, then the crate\'s own tests, ported to Go and kept hidden, score the port.')
top, bot = 104, 470
D.zone(20, top, 330, bot - top, 'Reference: /app/rust_reference', 'side', 'pmcgleenon/heavykeeper-rs, 7 files, 2,952 lines')
D.box('hk', 36, top + 52, 298, 'TopK', 'the HeavyKeeper sketch: depth rows of width buckets, probabilistic decay, a top-k queue', 'svc', 'rust')
D.box('bk', 36, top + 144, 298, 'BucketedTopK and CuckooTopK', 'two variants: one bucket of depth cells, or a decaying lobby plus cuckoo-hashed heavy slots', 'svc', 'rust')
D.box('ser', 36, top + 236, 298, 'Serialization, hashing, priority queue', 'byte layout with header checks, seeded hash composition, ordered top-k queue', 'svc', 'rust')
D.zone(390, top, 330, bot - top, 'Agent edits: /app/port', 'app', 'Go 1.21 package, offline')
D.box('sk', 406, top + 52, 298, 'Skeleton: 107 stubs', 'every exported type and function with its final signature; bodies are panic("not implemented")', 'svc', 'go', tag='FILL IN')
D.box('mc', 406, top + 162, 298, 'mig-check (on the PATH)', 'diffs signatures against the stubs, runs go build and go vet, flags name clashes with test helpers', 'new')
D.box('rules', 406, top + 262, 298, 'Constraints', 'no os, net, syscall, runtime, embed or cgo; RE2 regular expressions only; 2 vCPUs, 60 s and 2 GB per test', 'muted')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs after the session')
D.box('sp', 776, top + 52, 288, "Crate's tests ported to Go", '201 required tests in 8 files', 'fault', 'test-pipe')
y = top + 132
for name, n in [('TopK', 57), ('bucketed', 56), ('cuckoo', 45), ('serialization', 15), ('accuracy', 12), ('queue', 11), ('other', 5)]:
    D._t(790, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="{900}" y="{y - 6}" width="{n / 57 * 120:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 22
D.box('sc', 776, y + 6, 288, 'Score', 'weighted share of tests passed; a test that panics or times out scores 0', 'dark')
D.arrow([(334, top + 190), (370, top + 190), (370, top + 100), (406, top + 100)], 'port', lpos=.5, loff=(16, 4))
D.arrow([(555, top + 140), (555, top + 162)], kind='new', both=True)
D._t(566, top + 155, 'run often', 11, False, '#5b7d12')
D.arrow([(704, top + 92), (776, top + 76)], 'patch', lpos=.5, loff=(0, -8))
# bottom: what one add() does in the TopK sketch, as the Rust code implements it
y0 = bot + 28
H = 440
D.zone(20, y0, 1060, H, 'What the Go code must reproduce: one add(item, n) on the TopK sketch', 'plain', 'illustrative sketch with depth 3 and width 6; fingerprints and counts are made-up values, the rules come from heavykeeper.rs')
gx, gy, cw, ch, RS = 210, y0 + 84, 62, 44, 76
D._t(36, gy - 18, 'item "x" hashes to one bucket per row', 11.5, True, TEAL)
rows = [
    [('a', 4), ('', 0), ('x', 7), ('c', 2), ('', 0), ('d', 9)],
    [('', 0), ('e', 5), ('', 0), ('f', 1), ('', 0), ('g', 3)],
    [('h', 6), ('i', 2), ('', 0), ('j', 1), ('k', 12), ('', 0)],
]
hit = {0: 2, 1: 2, 2: 4}
kinds = {0: 'new', 1: 'client', 2: 'fault'}
for r, cells in enumerate(rows):
    yy = gy + r * RS
    D._t(gx - 14, yy + ch / 2 + 4, f'row {r + 1}', 11, False, GREY, 'end')
    for c, (fp, n) in enumerate(cells):
        x = gx + c * (cw + 6)
        k = kinds[r] if hit[r] == c else 'muted' if not fp else 'svc'
        f, s, col, _ = KIND[k]
        D.el.append(f'<rect x="{x}" y="{yy}" width="{cw}" height="{ch}" rx="4" fill="{f}" stroke="{s}" stroke-width="{1.6 if hit[r] == c else 1}"/>')
        D._t(x + cw / 2, yy + 18, f'fp {fp}' if fp else 'empty', 10.5, True, col, 'middle')
        D._t(x + cw / 2, yy + 34, f'count {n}', 10.5, False, col if k != 'svc' else GREY, 'middle')
D.el.append(f'<rect x="36" y="{gy + RS + 4}" width="66" height="36" rx="5" fill="{LIME}" stroke="{TEAL}" stroke-width="1.6"/>')
D._t(69, gy + RS + 27, 'add x, n', 11, True, TEAL, 'middle')
for r in range(3):
    ty = gy + r * RS + ch / 2
    D.arrow([(102, gy + RS + 22), (118, gy + RS + 22), (118, ty), (gx - 66, ty)], kind='muted', width=1)
# three outcomes, one per row
ox = gx + 6 * (cw + 6) + 30
outs = [('new', 'Same fingerprint: count += n', 'row 1 already holds x, so its count grows'),
        ('client', 'Empty bucket: claim it', 'row 2 is empty, so x takes it with count n'),
        ('fault', 'Another item: decay it', 'row 3 holds k; each unit of n lowers k by one with probability decay^count, and x takes over if k reaches 0')]
oy = gy - 4
for r, (k, t, b) in enumerate(outs):
    yy = gy + r * RS
    D.arrow([(gx + 6 * (cw + 6) - 2, yy + ch / 2), (ox - 4, yy + ch / 2)], kind={'new': 'new', 'client': 'ok', 'fault': 'fault'}[k], width=1.2)
    D.box(f'o{r}', ox, yy + ch / 2 - (31 if r < 2 else 38), 1064 - ox, t, b, k, h=62 if r < 2 else 76)
# the top-k queue
qx = 36; qy = gy + 3 * RS + 20
D._t(qx, qy, 'then the top-k queue', 11.5, True, TEAL)
D.note(qx, qy + 20, 540, 'x\'s estimate is the largest count among its rows. If x is already tracked its count is updated; otherwise it enters only when the queue has room or the estimate beats the current minimum, which is evicted.', 11.5, GREY)
lx = 620
items = [('k', 12), ('d', 9), ('x', 7), ('h', 6)]
D._t(lx, qy, 'list(): illustrative', 11, True, TEAL)
for i, (it, n) in enumerate(items):
    x = lx + i * 112
    D.box(f'q{i}', x, qy + 10, 100, f'{it}: {n}', None, 'new' if it == 'x' else 'svc', h=34)
D.note(lx, qy + 66, 444, 'Ties, ordering, decay thresholds and the serialized bytes must all match the Rust crate exactly.', 11.5, TEAL, True)
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
