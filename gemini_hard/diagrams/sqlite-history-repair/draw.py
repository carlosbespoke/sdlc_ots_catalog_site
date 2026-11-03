import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('sqlite-history-json: repair change history after schema drift',
        'Tables tracked with sqlite-history-json were altered: columns added, renamed and dropped, and whole tables renamed. Restore now returns NULLs or fails, yet the upgrade command reports nothing to do. The agent fixes the library so one upgrade run brings every history back in line with the current schema.')

def table(x, y, cols, rows, widths, hl=None, head_kind='dark'):
    """A small grid. hl: {(r, c): kind} highlights a cell ('bad' red, 'good' lime)."""
    hl = hl or {}; rh = 22; xx = x
    for c, (name, w) in enumerate(zip(cols, widths)):
        D.el.append(f'<rect x="{xx}" y="{y}" width="{w}" height="{rh}" fill="{TEAL}" stroke="{TEAL}"/>')
        D._t(xx + 7, y + 15, name, 11, True, '#ffffff'); xx += w
    for r, row in enumerate(rows):
        xx = x; yy = y + rh * (r + 1)
        for c, (v, w) in enumerate(zip(row, widths)):
            k = hl.get((r, c)); fill = {'bad': '#fdecea', 'good': LIME}.get(k, '#ffffff')
            D.el.append(f'<rect x="{xx}" y="{yy}" width="{w}" height="{rh}" fill="{fill}" stroke="#cfcac2"/>')
            D._t(xx + 7, yy + 15, v, 11, k is not None, {'bad': '#c83220'}.get(k, INK)); xx += w
    return y + rh * (len(rows) + 1)

top, bot = 112, 452
D.zone(20, top, 330, bot - top, 'Agent edits: /app', 'app', 'simonw/sqlite-history-json, Python 3.12, offline')
D.box('src', 36, top + 52, 298, 'Library source', 'core.py: enable, disable, history, row-history, restore, row-state-sql; upgrade.py', 'svc', 'python', tag='FIX')
D.box('cli', 36, top + 150, 298, 'python -m sqlite_history_json.upgrade', 'today it reports nothing to upgrade; it must also take --dry-run', 'svc', 'terminal-2')
D.box('rt', 36, top + 248, 298, 'Repository tests in /app/tests', 'must keep passing', 'muted')
D.zone(370, top, 380, bot - top, 'Copy of the database: /data/shop.db', 'side', 'what drift looks like in practice')
D.store('db', 386, top + 52, 348, '12 tables, 13 audit tables', 'each tracked table has triggers writing JSON entries to _history_json_<table>; 15 change groups in _history_json', 'sqlite')
dy = top + 180
for i, (a, b) in enumerate([('columns added', 'parcels.weight added after tracking began'),
                            ('columns renamed', 'parcels.weight became weight_net'),
                            ('tables renamed', 'customers became assets, products became partners'),
                            ('table dropped', 'tickets: its history must stay untouched')]):
    D._t(392, dy + i * 34, a, 12, True, '#3a4f6b'); D.note(392, dy + i * 34 + 15, 340, b, 11, GREY)
D.zone(770, top, 310, bot - top, 'Hidden grader', 'grader', 'pytest on the patched /app')
D.box('nt', 786, top + 52, 278, '18 hidden tests of the upgrade', 'history, row-history, restore and row-state-sql after drift, as the instruction describes', 'fault', 'test-pipe')
y = top + 158
D._t(790, y, '178 tests guard existing behaviour', 11.5, True, '#c83220'); y += 20
for name, n in [('core library', 86), ('CLI', 36), ('upgrade', 36), ('row-state-sql', 18), ('other', 2)]:
    D._t(790, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="900" y="{y - 6}" width="{n / 86 * 120:.1f}" height="10" rx="2" fill="#f7b3a9"/>'); y += 22
D.note(790, y + 10, 270, 'The instruction also asks: a second run changes nothing, --dry-run only lists, and a name clash on a renamed table stops the upgrade.', 11, GREY)
D.arrow([(334, top + 180), (386, top + 100)], 'upgrade', lpos=.5, loff=(-2, -4))
D.arrow([(334, top + 90), (386, top + 80)], 'triggers', lpos=.45, loff=(0, -6))

# bottom: one concrete case from shop.db
y0 = bot + 26
D.zone(20, y0, 1060, 512, 'What goes wrong, using parcels row 1780 from shop.db', 'plain', 'a renamed column whose old name was later reused: history entries still carry the old key')
cx = 36; cy = y0 + 62
steps = [('1', 'track parcels', 'columns year, country, weight'), ('2', 'RENAME weight TO weight_net', 'tracking on; triggers keep the key "weight"'), ('3', 'ADD COLUMN weight integer', 'a new column takes the old name')]
for i, (n, t, b) in enumerate(steps):
    yy = cy if i == 0 else prev + 18
    D.badge(cx + 10, yy + 22, n)
    h = D.box(f's{i}', cx + 26, yy, 250, t, b, 'svc' if i == 0 else 'fault')
    if i: D.arrow([(cx + 151, prev), (cx + 151, yy)], width=1.2)
    prev = yy + h
ex = 340
D._t(ex, cy + 4, 'Audit entry 12 in _history_json_parcels', 12, True, TEAL)
D.el.append(f'<rect x="{ex}" y="{cy + 14}" width="330" height="54" rx="5" fill="#f4f2ee" stroke="#b9b4ab"/>')
D._t(ex + 12, cy + 36, 'update  pk 1780', 11.5, False, GREY)
D._t(ex + 12, cy + 56, '{"weight": 476.85}', 12, True, '#c83220')
D.note(ex, cy + 198, 330, 'The value was recorded from the column now called weight_net, but the key names the new integer column.', 11.5, GREY)
D._t(ex, cy + 112, 'After the upgrade', 12, True, TEAL)
D.el.append(f'<rect x="{ex}" y="{cy + 122}" width="330" height="54" rx="5" fill="#f2fbd4" stroke="#5b7d12"/>')
D._t(ex + 12, cy + 144, 'update  pk 1780  (id, time and group kept)', 11.5, False, GREY)
D._t(ex + 12, cy + 164, '{"weight_net": 476.85}', 12, True, '#3d5a0a')
D.arrow([(ex + 165, cy + 68), (ex + 165, cy + 98)], kind='new')
D._t(ex + 176, cy + 88, 'the upgrade rewrites the key', 11, False, '#5b7d12')
D.arrow([(cx + 276, cy + 30), (ex - 4, cy + 30)], width=1.2)
rx = 700
cols, W = ['', 'year', 'country', 'weight_net', 'weight'], [70, 44, 116, 74, 54]
D._t(rx, cy + 4, 'Restore to the latest entry', 12, True, TEAL)
y = table(rx, cy + 14, cols, [['current', '625', 'amber-russet92', '476.85', '103'],
                               ['today', '625', 'amber-russet92', 'NULL', '476.85'],
                               ['required', '625', 'amber-russet92', '476.85', '103']], W,
          {(1, 3): 'bad', (1, 4): 'bad', (2, 3): 'good', (2, 4): 'good'})
D.note(rx, y + 18, 358, 'The instruction requires restore to the latest entry to give exactly the current rows.', 11.5, GREY)
# renamed tables strip
ry = cy + 282
D.el.append(f'<line x1="36" y1="{ry - 14}" x2="1064" y2="{ry - 14}" stroke="#e4e0d8"/>')
D._t(36, ry + 6, 'Renamed tables: triggers moved with the table, the history did not', 12, True, TEAL)
by = ry + 24
for i, (old, new) in enumerate([('customers', 'assets'), ('products', 'partners')]):
    x = 36 + i * 360
    D.box(f'n{i}', x, by, 110, new, 'live table', 'svc')
    D.box(f'o{i}', x + 140, by, 205, f'_history_json_{old}', 'audit table, old name', 'fault')
    D.arrow([(x + 110, by + 22), (x + 140, by + 22)], width=1.2)
    D.note(x, by + 82, 340, f'history("{new}") fails today. The instruction asks that the history follow the table, so history, restore, enable and disable work under the new name.', 11, GREY)
D.box('tk', 756, by, 308, '_history_json_tickets', 'its table was dropped: the upgrade leaves it exactly as it is', 'muted')
D.h = y0 + 512 + 20
D.save(HERE + '/diagram.svg')
