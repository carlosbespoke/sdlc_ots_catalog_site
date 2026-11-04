import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('xmltodict: opt-in nulls and preserved whitespace for a partner XML feed',
        'A partner feed now marks missing values with xsi:nil and protects padded text with xml:space. The agent extends xmltodict\'s parse and unparse in /app with two opt-in options, xsi_nil and xml_space, and leaves every default behaviour exactly as it was.')
top, bot = 104, 474
D.zone(20, top, 250, bot - top, 'Sample data: /data', 'side', 'copied into the image, outside /app')
D.box('feed', 36, top + 50, 218, 'partner-feed.xml', '3 entries; nil marked as true and as 1, under two different prefixes; padded codes', 'file', 'file-code')
D.box('ns', 36, top + 154, 218, 'xml:space', 'preserve on the feed root, default on one nested element', 'file', None)
D.box('env', 36, top + 238, 218, 'Environment', 'Python 3.12, project dependencies installed in /opt/venv, no network', 'muted', 'python')
D.zone(290, top, 500, bot - top, 'xmltodict in /app (the agent edits this)', 'app', 'martinblech/xmltodict at a pinned commit')
D.box('parse', 306, top + 54, 220, 'parse()', 'Expat events to dicts; namespaces on or off; streaming callbacks at item_depth, also from byte chunks', 'svc', 'python')
D.box('unparse', 554, top + 54, 220, 'unparse()', 'dicts back to XML; nested elements and list entries', 'svc', 'python')
D.box('o1', 306, top + 172, 220, 'xsi_nil=True', 'nil="true" or "1" under any prefix becomes None; unparse writes None as an explicit nil with a valid namespace binding', 'new', tag='NEW')
D.box('o2', 554, top + 172, 220, 'xml_space=True', 'preserve keeps text and comment whitespace exactly; descendants inherit it until default', 'new', tag='NEW')
D.note(306, top + 300, 468, 'Without the new options, parsing and writing stay exactly as before. Malformed XML and invalid UTF-8 still raise Expat errors, and entity declarations still raise ValueError by default.', 11.5, GREY)
D.arrow([(254, top + 90), (306, top + 90)], 'read')
D.zone(810, top, 270, bot - top, 'Hidden grader', 'grader', 'runs the code as an unprivileged user')
D.box('hn', 826, top + 50, 238, '8 new tests', 'fail on the delivered code, must pass after the change', 'fault', 'test-pipe')
y = top + 152
for name, n in [('nil on parse', 2), ('xml:space', 2), ('nil on unparse', 2), ('both together', 2)]:
    D._t(840, y + 4, name, 12, False, INK); D._t(1050, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="960" y="{y - 6}" width="{n / 2 * 70:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 19
D.box('p2', 826, y + 10, 238, '137 must keep passing', "134 of the repository's own tests and 3 checks of the default behaviour", 'dark')
D.note(826, y + 104, 238, 'Reward 1 only when every one of the 145 tests passes.', 11.5, '#c83220', True)
D.arrow([(790, top + 90), (826, top + 90)], 'patch', loff=(0, -8))
# bottom: the first feed entry, parsed today and with the two options
y0 = bot + 28
H = 410
D.zone(20, y0, 1060, H, 'One feed entry, before and after', 'plain', 'the first entry of partner-feed.xml, and what parse returns for it; values follow the instruction\'s rules')
cx, cy, cw = 36, y0 + 60, 380
lines = [('<feed xmlns:vendor="...XMLSchema-instance"', None), ('      xml:space="preserve">', 'sp'), ('<entry>', None), ('  <code> 401 </code>', 'pad'),
         ('  <missing vendor:nil="true"/>', 'nil'), ('  <empty/>', None), ('  <revised xml:space="default">  0  </revised>', 'def'), ('</entry>', None)]
lh = 26
D.el.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{len(lines) * lh + 14}" rx="5" fill="#1c2b2d"/>')
for i, (txt, k) in enumerate(lines):
    yy = cy + 24 + i * lh
    if k: D.el.append(f'<rect x="{cx + 4}" y="{yy - 16}" width="{cw - 8}" height="22" rx="3" fill="none" stroke="{LIME if k != "nil" else RED}" stroke-width="1.3"/>')
    D._t(cx + 12, yy, txt.replace(' ', '\u00a0'), 11, False, '#e8f0ee', mono=True)
D.note(cx, cy + len(lines) * lh + 34, cw, 'The nil attribute is matched by its namespace, not its prefix: the third entry uses instance:nil="1".', 11.5, GREY)
def card(x, y, w, head, kind, rows):
    f, s, c, _ = KIND[kind]
    D.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{36 + len(rows) * 30}" rx="5" fill="#ffffff" stroke="{s}" stroke-width="1.4"/>')
    D.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="5" fill="{f}" stroke="{s}" stroke-width="1.4"/>')
    D._t(x + 12, y + 19, head, 11.5, True, c, mono=False)
    for i, (k, v, hl) in enumerate(rows):
        yy = y + 52 + i * 30
        D._t(x + 12, yy, k, 11, False, GREY, mono=True); D._t(x + 104, yy, v, 11, True, '#c83220' if hl == 'x' else TEAL, mono=True)
        if hl == 'ok': D.check(x + w - 16, yy - 4, 6)
        if hl == 'x': D.cross(x + w - 13, yy - 4, 5)
ax, bx, cwid = 446, 786, 286
card(ax, cy, cwid, 'parse(feed): today', 'muted', [('code', "'401'", 'x'), ('missing', "{'@vendor:nil':'true'}", 'x'), ('empty', 'None', ''), ('revised', "'0'", '')])
card(bx, cy, cwid, 'parse(feed, xsi_nil=True, xml_space=True)', 'new', [('code', "' 401 '", 'ok'), ('missing', 'None', 'ok'), ('empty', 'None', ''), ('revised', "'0'", '')])
D.arrow([(cx + cw + 4, cy + 4 * lh), (ax - 4, cy + 4 * lh)], width=1.2)
D.arrow([(ax + cwid + 4, cy + 142), (bx - 4, cy + 142)], 'opt in', kind='new', loff=(0, -8))
ny = cy + 36 + 4 * 30 + 26
for i, t in enumerate(['padding inside preserve is kept exactly', 'nil becomes None; empty stays an ordinary empty element', 'xml:space="default" restores normal stripping below it']):
    D.badge(ax + 10, ny + i * 26, i + 1, TEAL); D.note(ax + 28, ny + i * 26 + 4, 600, t, 11.5, TEAL)
ry = ny + 3 * 26 + 6
D.box('rt', ax, ry, bx + cwid - ax, 'And back: unparse(..., xsi_nil=True)', 'every None, nested or in a list, is written with an explicit nil attribute and its namespace binding, so parse, write and parse again keep each null where it was', 'client', 'refresh')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
