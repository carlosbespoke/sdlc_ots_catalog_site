import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('ETLPlus: CSV exports must behave exactly like JSON',
        'The nightly order export switched from JSON to CSV, and the team\'s etlplus pipeline now fails validation and computes wrong totals. The agent fixes etlplus in /app so that a job reading CSV gives the same result it gives on the same records as JSON.')
top, bot = 104, 470
D.zone(20, top, 250, bot - top, 'Sample data: /data/orders', 'side', 'copied into the image, outside /app')
D.box('j4', 36, top + 50, 218, 'orders-2026-10-04.json', 'last JSON night: 340 orders with typed values', 'file', 'json')
D.box('c4', 36, top + 126, 218, 'orders-2026-10-04.csv', 'the same 340 orders as CSV: 24 chunks, 364 lines', 'file', 'file-text')
D.box('c5', 36, top + 202, 218, 'orders-2026-10-05.csv', 'next night, CSV only: 355 orders in 24 chunks', 'file', 'file-text')
D.box('py', 36, top + 278, 218, 'pipeline.yml', 'two jobs, 11 validation rules, 9 aggregates', 'file', 'yaml')
D.zone(290, top, 500, bot - top, 'etlplus in /app (the agent edits this)', 'app', 'Python 3.13, environment in /opt/venv, no network')
D._t(304, top + 62, 'job clean_orders', 11, True, TEAL)
D._t(430, top + 198, 'job order_summary, runs after clean_orders', 11, True, TEAL)
G = 12
r1 = [('e1', 'extract', 'orders_export, CSV', 'new', 106), ('v1', 'validate', 'orders_basic, 11 rules', 'svc', 110), ('t1', 'transform', 'filter, rename, select, sort', 'svc', 116), ('l1', 'load', 'orders_clean.csv', 'svc', 110)]
r2 = [('e2', 'extract', 'orders_clean.csv, CSV', 'new', 106), ('t2', 'transform', 'summarize: 9 aggregates', 'svc', 116), ('l2', 'load', 'orders_summary.json', 'svc', 140)]
for row, y in ((r1, top + 74), (r2, top + 210)):
    x = 304
    for i, (k, t, b, kind, w) in enumerate(row):
        if i: D.arrow([(x - G, y + 39), (x, y + 39)])
        D.box(k, x, y, w, t, b, kind, h=78); x += w + G
lx = D.pt('l1', 'b')[0]
D.arrow([(lx, top + 152), (lx, top + 176), (357, top + 176), (357, top + 210)], 'the second job reads the CSV the first one wrote', lpos=.45, loff=(0, -6))
D.note(304, top + 318, 472, 'The existing tests in /app/tests and the CI checks (ruff, pydocstyle, pydoclint, mypy) have to keep passing.', 11.5, GREY)
D.arrow([(254, top + 240), (280, top + 240), (280, top + 113), (304, top + 113)])
D.zone(810, top, 270, bot - top, 'Hidden grader', 'grader', 'runs after the session')
D.box('hn', 826, top + 50, 238, '18 new tests', 'generated exports, each run as CSV and as JSON, results compared', 'fault', 'test-pipe')
y = top + 140
for name, n in [('numbers', 5), ('export records', 3), ('missing values', 3), ('true / false flags', 3), ('team pipeline', 3), ('other CSV feeds', 1)]:
    D._t(840, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="960" y="{y - 6}" width="{n / 5 * 70:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 19
D.box('p2', 826, y + 8, 238, '4,727 checks must still pass', '4,722 existing tests, the JSON pipeline test, ruff, pydocstyle, pydoclint, mypy', 'dark')
D.arrow([(790, top + 90), (826, top + 90)])
# bottom: what the CSV contains and what etlplus must read from it
y0 = bot + 28
D.zone(20, y0, 1060, 392, 'Same orders, two formats', 'plain', 'lines 17 to 39 of orders-2026-10-04.csv, and the record etlplus must build from them')
cx, cy, cw = 36, y0 + 58, 600
lines = [
    (None, 'ORD-418246,2026-10-04T00:56:50Z,C-0337,12,paid,142.26,3,,VIP-GOLD,...'),
    ('BOM', 'order_id,placed_at,customer_id,store_id,status,amount,quantity,...'),
    ('hit', 'ORD-418247,2026-10-04T01:02:13Z,C-0031,11,refunded,-117.49,4,,,...'),
    (None, '...'),
    (None, 'ORD-418264,2026-10-04T01:45:32Z,C-0018,7,paid,323.45,6,26.61,,,...'),
    ('BOM', 'placed_at,order_id,customer_id,store_id,quantity,discount,...'),
    (None, '2026-10-04T02:01:23Z,ORD-418265,C-0382,12,3,,,,paid,false,...'),
    (None, '...'),
    ('BOM', 'quantity,order_id,placed_at,customer_id,status,gift_wrap,...'),
    ('BOM', 'order_id,placed_at,customer_id,store_id,status,amount,...'),
]
lh = 24
D.el.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{len(lines) * lh + 16}" rx="5" fill="#1c2b2d"/>')
for i, (kind, txt) in enumerate(lines):
    yy = cy + 22 + i * lh; x = cx + 12
    if kind == 'BOM':
        D.el.append(f'<rect x="{x}" y="{yy - 12}" width="34" height="16" rx="3" fill="{RED}"/>'); D._t(x + 17, yy, 'BOM', 9.5, True, '#ffffff', 'middle'); x += 40
    if kind == 'hit': D.el.append(f'<rect x="{cx + 4}" y="{yy - 15}" width="{cw - 8}" height="21" rx="3" fill="none" stroke="{LIME}" stroke-width="1.4"/>')
    D._t(x, yy, txt, 11, False, '#e8f0ee' if kind != 'BOM' else '#f7b3a9', mono=True)
notes = [(1, 'a new chunk starts: byte-order mark, then a header row again'), (5, 'columns come in a different order in 6 of the 24 chunks'), (8, 'a chunk with no orders: header only (3 of them)')]
for i, t in notes:
    yy = cy + 22 + i * lh - 4
    D.arrow([(cx + cw + 30, yy), (cx + cw - 6, yy)], kind='fault', width=1.2)
    D.note(cx + cw + 36, yy - 4 + (0 if len(wrap(t, 160, 11)) == 1 else -6), 160, t, 11, '#c83220')
fy = cy + len(lines) * lh + 30
D.note(cx, fy + 4, cw, 'Every value is text and an empty cell means missing. The JSON export has the same 340 orders with real numbers, booleans and nulls.', 11.5, GREY)
# record card
kx, ky, kw = 846, y0 + 58, 218
D.el.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="262" rx="5" fill="#ffffff" stroke="{TEAL}" stroke-width="1.4"/>')
D.el.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="28" rx="5" fill="{LIME}" stroke="{TEAL}" stroke-width="1.4"/>')
D._t(kx + 12, ky + 19, 'Record ORD-418247, as in the JSON', 11.5, True, TEAL)
rec = [('store_id', '11', 'integer'), ('status', '"refunded"', 'string'), ('amount', '-117.49', 'number'), ('quantity', '4', 'integer'), ('discount', 'null', 'missing'), ('coupon_code', 'null', 'missing'), ('shipped_at', '"2026-10-04T04:02:13Z"', ''), ('is_test', 'false', 'boolean'), ('gift_wrap', 'false', 'boolean')]
for i, (k, v, t) in enumerate(rec):
    yy = ky + 50 + i * 23
    D._t(kx + 12, yy, k, 11, False, GREY, mono=True); D._t(kx + 98, yy, v if len(v) < 12 else v[:11] + '..."', 11, True, TEAL, mono=True)
    if t: D._t(kx + kw - 10, yy, t, 9.5, False, '#5b7d12', 'end')
hy = cy + 22 + 2 * lh - 4
D.arrow([(cx + cw + 4, hy + 8), (820, hy + 8), (820, ky + 120), (kx, ky + 120)], 'read as', kind='new', lpos=.12, loff=(0, -6))
D.note(kx - 2, ky + 286, kw + 10, 'Same validation outcome, filter result, sort order and aggregate values as the JSON run.', 11.5, TEAL, True)
D.h = y0 + 392 + 20
D.save(HERE + '/diagram.svg')
