# Hand-placed system design diagrams for the sample tasks: boxes, stores, zones, routed arrows and
# sequence lanes, drawn as SVG in the Bespoke Labs palette with an embedded Inter subset.
# Each task's diagram is a Python file next to this one that builds a Diagram and calls save().
import base64, html, io, os, re, subprocess
from PIL import ImageFont
from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = '/Users/carlos/code/sdlc_final_samples/catalogs/site/fonts'
ICONS = '/Users/carlos/code/sdlc_final_samples/pipeline/d2/icons'
REG, BOLD = f'{FONTS}/Inter-Regular.ttf', f'{FONTS}/Inter-SemiBold.ttf'
TEAL, MINT, TAN, INK, RED, LIME, BLUE, GREY = '#0F484D', '#D4E8E3', '#F8F3E6', '#231F20', '#F44029', '#DAF767', '#B9C8DD', '#625f5d'
KIND = {  # fill, stroke, text, dash
    'svc': ('#ffffff', TEAL, TEAL, None),
    'new': (LIME, TEAL, TEAL, None),
    'client': (MINT, '#1f6f6a', TEAL, None),
    'fault': ('#fdecea', RED, '#c83220', None),
    'dark': (TEAL, TEAL, '#ffffff', None),
    'muted': ('#f4f2ee', '#b9b4ab', GREY, None),
    'file': ('#ffffff', '#9d988f', INK, None),
}
ZONE = {
    'app': ('#fbf9f4', TEAL, TEAL, None),
    'side': ('#f3f6f9', '#7f97b5', '#3a4f6b', '4 4'),
    'grader': ('#fff6f4', RED, '#c83220', '4 4'),
    'client': ('#f2f8f6', '#1f6f6a', TEAL, None),
    'plain': ('#ffffff', '#cfcac2', GREY, None),
}
EDGE = {'flow': (TEAL, None), 'fault': (RED, '5 4'), 'new': ('#5b7d12', None), 'muted': ('#9d988f', '3 3'), 'ok': ('#1f6f6a', None)}
_fc = {}
def font(size, bold=False):
    k = (size, bold)
    if k not in _fc: _fc[k] = ImageFont.truetype(BOLD if bold else REG, size)
    return _fc[k]
def tw(s, size, bold=False): return font(size, bold).getlength(s)
def wrap(s, width, size, bold=False):
    out = []
    for para in str(s).split('\n'):
        line = ''
        for w in para.split(' '):
            t = (line + ' ' + w).strip()
            if line and tw(t, size, bold) > width: out.append(line); line = w
            else: line = t
        out.append(line)
    return out
def esc(s): return html.escape(str(s), quote=True)

class Diagram:
    def __init__(self, w, h):
        self.w, self.h, self.el, self.bg, self.anchors, self.text = w, h, [], [], {}, set()
    def _t(self, x, y, s, size=12, bold=False, color=INK, anchor='start', mono=False):
        self.text.update(s)
        fam = "'MD IO','IBM Plex Mono',Menlo,monospace" if mono else "Inter,Helvetica,Arial,sans-serif"
        self.el.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" font-weight="{600 if bold else 400}" fill="{color}" text-anchor="{anchor}">{esc(s)}</text>')
    def lines(self, x, y, lines, size=12, bold=False, color=INK, anchor='start', lh=None):
        lh = lh or size * 1.35
        for i, l in enumerate(lines): self._t(x, y + i * lh, l, size, bold, color, anchor)
        return y + len(lines) * lh
    def title(self, t, sub=None, x=28, y=40):
        self._t(x, y, t, 22, True, TEAL)
        if sub: self.lines(x, y + 24, wrap(sub, self.w - 2 * x, 13), 13, color=GREY)
    def icon(self, name, x, y, size=18, color=TEAL):
        for p in (f'{ICONS}/si-{name}.svg', f'{ICONS}/tb-{name}.svg'):
            if os.path.exists(p):
                s = open(p).read()
                vb = re.search(r'viewBox="([^"]+)"', s).group(1)
                inner = re.sub(r'^.*?<svg[^>]*>|</svg>\s*$', '', s, flags=re.S)
                stroke = 'tb-' in p
                attrs = f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"' if stroke else f'fill="{color}"'
                inner = inner.replace('currentColor', color)
                self.el.append(f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{vb}" {attrs}>{inner}</svg>')
                return
        raise KeyError(name)
    def zone(self, x, y, w, h, label, kind='app', sub=None):
        f, s, c, d = ZONE[kind]
        self.bg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{f}" stroke="{s}" stroke-width="1.2"' + (f' stroke-dasharray="{d}"' if d else '') + '/>')
        self._t(x + 14, y + 20, label.upper(), 11, True, c)
        if sub: self._t(x + 14, y + 35, sub, 11, False, GREY)
    def _anchor(self, id, x, y, w, h):
        self.anchors[id] = (x, y, w, h)
    def box(self, id, x, y, w, title, body=None, kind='svc', icon=None, h=None, tag=None, code=False):
        f, s, c, d = KIND[kind]
        tx = x + 12 + (26 if icon else 0)
        tl = wrap(title, w - (tx - x) - 10, 13, True)
        bl = wrap(body, w - 24, 11.5) if body else []
        need = 14 + len(tl) * 17 + (6 + len(bl) * 15.5 if bl else 0) + 8
        h = h or max(44, need)
        self.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{f}" stroke="{s}" stroke-width="{1.8 if kind == "new" else 1.2}"' + (f' stroke-dasharray="{d}"' if d else '') + '/>')
        if icon: self.icon(icon, x + 11, y + 11, 18, c if kind != 'dark' else '#ffffff')
        yy = self.lines(tx, y + 24, tl, 13, True, c, lh=17)
        if bl: self.lines(x + 12, yy + 4, bl, 11.5, color=c if kind in ('dark', 'fault') else GREY, lh=15.5)
        if tag: self.tag(x + w - 8, y - 8, tag, 'new' if tag == 'NEW' else kind)
        self._anchor(id, x, y, w, h)
        return h
    def store(self, id, x, y, w, title, body=None, icon=None, h=None, kind='svc'):
        f, s, c, d = KIND[kind]
        e = 9
        bl = wrap(body, w - 24, 11.5) if body else []
        tl = wrap(title, w - 24 - (26 if icon else 0), 13, True)
        h = h or 20 + e + len(tl) * 17 + len(bl) * 15.5 + 14
        self.el.append(f'<path d="M{x},{y + e} a{w / 2},{e} 0 0,0 {w},0 a{w / 2},{e} 0 0,0 {-w},0 v{h - 2 * e} a{w / 2},{e} 0 0,0 {w},0 v{-(h - 2 * e)}" fill="{f}" stroke="{s}" stroke-width="1.2"/>')
        tx = x + 12 + (26 if icon else 0)
        if icon: self.icon(icon, x + 11, y + 2 * e + 4, 18, c)
        yy = self.lines(tx, y + 2 * e + 18, tl, 13, True, c, lh=17)
        if bl: self.lines(x + 12, yy + 2, bl, 11.5, color=GREY, lh=15.5)
        self._anchor(id, x, y, w, h)
        return h
    def tag(self, xr, y, label, kind='new'):
        f, s, c, _ = KIND.get(kind, KIND['new'])
        w = tw(label, 10, True) + 14
        self.el.append(f'<rect x="{xr - w}" y="{y}" width="{w}" height="17" rx="8.5" fill="{f}" stroke="{s}" stroke-width="1"/>')
        self._t(xr - w / 2, y + 12.3, label, 10, True, c, 'middle')
    def badge(self, x, y, n, color=TEAL):
        self.el.append(f'<circle cx="{x}" cy="{y}" r="10" fill="{color}"/>')
        self._t(x, y + 4, str(n), 11, True, '#ffffff', 'middle')
    def pt(self, id, side, f=0.5):
        x, y, w, h = self.anchors[id]
        return {'l': (x, y + h * f), 'r': (x + w, y + h * f), 't': (x + w * f, y), 'b': (x + w * f, y + h)}[side]
    def arrow(self, pts, label=None, kind='flow', lpos=0.5, loff=(0, -6), both=False, lanchor='middle', badge=None, head=True, width=1.4):
        col, dash = EDGE[kind]
        pts = [p for p in pts]
        d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        mid = f'm{abs(hash((col, kind))) % 10000}'
        self.el.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{width}"' + (f' stroke-dasharray="{dash}"' if dash else '') + (f' marker-end="url(#a-{kind})"' if head else '') + (f' marker-start="url(#s-{kind})"' if both else '') + '/>')
        if label or badge:
            # label at fraction lpos along the polyline length
            segs = list(zip(pts, pts[1:])); L = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** .5 for a, b in segs]
            t = sum(L) * lpos
            for (a, b), l in zip(segs, L):
                if t <= l or (a, b) == segs[-1]:
                    r = t / l if l else 0; mx, my = a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r; break
                t -= l
            if label:
                ls = label.split('\n'); wmax = max(tw(s, 11) for s in ls)
                lx, ly = mx + loff[0], my + loff[1] - (len(ls) - 1) * 14
                bx = lx - wmax / 2 if lanchor == 'middle' else lx if lanchor == 'start' else lx - wmax
                self.el.append(f'<rect x="{bx - 4:.1f}" y="{ly - 11:.1f}" width="{wmax + 8:.1f}" height="{len(ls) * 14 - 1:.1f}" fill="#ffffff" fill-opacity="0.92" rx="3"/>')
                self.lines(lx, ly, ls, 11, color=col if kind != 'flow' else '#446b6e', anchor=lanchor, lh=14)
            if badge: self.badge(mx + (badge[1] if isinstance(badge, tuple) else 0), my, badge[0] if isinstance(badge, tuple) else badge)
    def link(self, a, sa, b, sb, via=(), fa=0.5, fb=0.5, **k):
        p, q = self.pt(a, sa, fa), self.pt(b, sb, fb)
        self.arrow([p, *via, q], **k)
    def note(self, x, y, w, text, size=11.5, color=GREY, bold=False):
        return self.lines(x, y, wrap(text, w, size, bold), size, bold, color, lh=size * 1.4)
    def cross(self, x, y, r=7):
        self.el.append(f'<path d="M{x - r},{y - r} L{x + r},{y + r} M{x + r},{y - r} L{x - r},{y + r}" stroke="{RED}" stroke-width="2.4" stroke-linecap="round"/>')
    def check(self, x, y, r=7):
        self.el.append(f'<path d="M{x - r},{y} L{x - r / 3},{y + r * .7} L{x + r},{y - r * .7}" fill="none" stroke="#1f6f6a" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
    def bolt(self, x, y, s=1.0):
        self.el.append(f'<path transform="translate({x},{y}) scale({s})" d="M3,-11 L-6,2 L0,2 L-3,11 L6,-2 L0,-2 Z" fill="{RED}"/>')
    def rule(self, x, y, w, n, text):
        """A numbered requirement line: badge plus wrapped text. Returns the next y."""
        self.badge(x + 10, y + 1, n)
        return self.note(x + 28, y + 5, w - 28, text, 12, INK) + 6
    def seq(self, x, y, w, lanes, steps, row=34, head=46, title=None):
        """Sequence lanes. lanes: [(key, label, kind)]. steps: dicts with a, b (lane keys), label, kind,
        mark ('x' | 'ok' | 'bolt'), gap (extra rows), note (text at the right edge, for a = b)."""
        n = len(lanes); col = w / n; X = {k: x + col * (i + .5) for i, (k, _, _) in enumerate(lanes)}
        if title: self._t(x, y - 10, title.upper(), 11, True, TEAL)
        bw = min(col - 16, 150)
        total = sum(1 + s.get('gap', 0) for s in steps)
        y1 = y + head + total * row + 8
        for k, label, kind in lanes:
            self.el.append(f'<line x1="{X[k]}" y1="{y + 36}" x2="{X[k]}" y2="{y1}" stroke="#cfcac2" stroke-width="1.2" stroke-dasharray="3 3"/>')
            f, s, c, _ = KIND[kind]
            ls = wrap(label, bw - 12, 12, True)
            self.el.append(f'<rect x="{X[k] - bw / 2}" y="{y}" width="{bw}" height="36" rx="5" fill="{f}" stroke="{s}" stroke-width="1.2"/>')
            self.lines(X[k], y + (22 if len(ls) == 1 else 15), ls, 12, True, c, 'middle', lh=14)
        yy = y + head + row * .6
        for s in steps:
            yy += s.get('gap', 0) * row
            a, b = X[s['a']], X[s.get('b', s['a'])]
            kind = s.get('kind', 'flow')
            if a == b:
                self.note(a + 12, yy + 4, col * 1.6, s['label'], 11, EDGE[kind][0] if kind != 'flow' else GREY, kind == 'fault')
                if s.get('mark') == 'bolt': self.bolt(a, yy)
            else:
                d = 1 if b > a else -1
                end = b - (22 if s.get('mark') == 'x' else 4) * d
                self.arrow([(a + 4 * d, yy), (end, yy)], s.get('label'), kind, loff=(0, -6))
                if s.get('mark') == 'x': self.cross(b - 8 * d, yy)
                if s.get('mark') == 'ok': self.check(b - d * 20, yy - 12)
                if s.get('mark') == 'bolt': self.bolt((a + b) / 2, yy)
            yy += row
        return y1
    def save(self, path):
        chars = ''.join(sorted(self.text | set(' 0123456789')))
        css = ''
        for fam_w, ttf in ((400, REG), (600, BOLD)):
            f = TTFont(ttf); sub = subset.Subsetter(subset.Options()); sub.populate(text=chars); sub.subset(f)
            f.flavor = 'woff2'; buf = io.BytesIO(); f.save(buf)
            css += f"@font-face{{font-family:Inter;font-weight:{fam_w};src:url(data:font/woff2;base64,{base64.b64encode(buf.getvalue()).decode()}) format('woff2')}}"
        marks = ''.join(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9 Z" fill="{c}"/></marker>'
                        f'<marker id="s-{k}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M10,1 L1,5 L10,9 Z" fill="{c}"/></marker>' for k, (c, _) in EDGE.items())
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">'
               f'<defs><style>{css}</style>{marks}</defs><rect width="{self.w}" height="{self.h}" fill="#ffffff"/>' + ''.join(self.bg + self.el) + '</svg>')
        open(path, 'w').write(svg)
        png = path[:-4] + '.png'
        subprocess.run(['rsvg-convert', '-w', str(self.w * 2), path, '-o', png], check=True)
        return path
