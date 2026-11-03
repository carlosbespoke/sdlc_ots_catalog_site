import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('TorchIO 2: fix every place the library drifted from its documentation',
        'TorchIO loads, augments and patch-samples 3D medical images for PyTorch. Its code no longer does what its own pages and docstrings say. The agent finds each disagreement and changes the code, never the documentation.')
top = 104
def stack(items, x, w, y, gap=12):
    for id, t, b, k, ic in items:
        y += D.box(id, x, y, w, t, b, k, ic) + gap
    return y
y1 = stack([('c', 'concepts/, get-started/: 5 pages', 'data model, lazy loading, transforms, per-instance augmentation, quickstart', 'file', 'book'),
            ('t', 'tutorials/, how-to/: 11 pages', 'first pipeline, large volumes, annotations, data loaders, patch training and inference, TTA', 'file', 'book'),
            ('r', 'reference/: 52 pages', 'image, subject, points, bounding boxes, affine, backends, patches, random parameters, and 41 transform pages', 'file', 'book'),
            ('ds', 'Docstrings', 'module, class and function docstrings of the 66 in-scope modules, examples included', 'file', 'python')], 36, 298, top + 52)
y2 = stack([('code', '66 in-scope modules', '45 under transforms/, 15 under data/, plus io, loader, types and others; datasets, CLI and adapters are out of scope', 'svc', 'python'),
            ('cm', 'Code comments', 'supporting evidence only; when a comment contradicts the documentation, follow the documentation', 'muted', None),
            ('api', 'Public API stays stable', 'behaviour that already matches its documentation must work exactly as before', 'muted', None)], 406, 298, top + 52, 16)
y3 = stack([('ob', '162 observations', '161 small TorchIO programs compared with sealed expected values, plus one unedited-documentation check', 'fault', 'test-pipe'),
            ('f2p', '40 drift groups, 40 observations', 'fail on the delivered code, pass after the reference repair', 'fault', None),
            ('p2p', '36 guard groups, 122 observations', 'already pass and must keep passing', 'client', None),
            ('sc', 'Score', 'mean of drift groups fixed, times mean of guard groups kept', 'dark', None)], 776, 288, top + 52)
D.tag(704 - 8, top + 52 - 8, 'FIX')
bot = max(y1, y2, y3) + 6
D.zone(20, top, 330, bot - top, 'Documentation: the authority', 'side', '68 pages plus docstrings, read only')
D.zone(390, top, 330, bot - top, 'Agent edits: /workdir/src/torchio', 'app', 'Python 3.12, PyTorch CPU, SimpleITK, offline')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs as user nobody after the session')
D.arrow([(334, D.pt('t', 'r')[1]), (370, D.pt('t', 'r')[1]), (370, top + 90), (406, top + 90)], 'compare', lpos=.5, loff=(-22, 0))
D.arrow([(704, top + 90), (776, top + 90)], 'patch', lpos=.5, loff=(0, -8))
# bottom: the library pipeline, and the rule for each disagreement
y0 = bot + 26
py = y0 + 62
stages = [('Images and subject', 'scalar images, label maps, affines, points, boxes; lazy backends'),
          ('Transforms', 'spatial, intensity and label; compose, random parameters'),
          ('History and inverse', 'each applied transform recorded and invertible'),
          ('Patch sampling', 'samplers and the queue feed the data loader'),
          ('Aggregation', 'patch predictions stitched back into a volume')]
bw, gap = 186, 23
for i, (t, b) in enumerate(stages):
    x = 36 + i * (bw + gap)
    D.box(f's{i}', x, py, bw, t, b, 'svc', h=86)
    if i: D.arrow([(x - gap + 2, py + 43), (x - 2, py + 43)])
ry = py + 116
D.box('doc', 36, ry, 240, 'The documentation says', 'a default, a parameter range, an output shape, an error', 'file', 'book', h=76)
D.box('run', 36, ry + 116, 240, 'The code does', 'what TorchIO returns or raises at runtime', 'svc', 'python', h=76)
cx, cy = 356, ry + 96
D.el.append(f'<circle cx="{cx}" cy="{cy}" r="38" fill="#ffffff" stroke="{TEAL}" stroke-width="1.4"/>')
D._t(cx, cy - 3, 'same', 11.5, True, TEAL, 'middle'); D._t(cx, cy + 12, 'behaviour?', 11.5, True, TEAL, 'middle')
D.arrow([(276, ry + 38), (300, ry + 38), (300, cy - 14), (318, cy - 14)])
D.arrow([(276, ry + 154), (300, ry + 154), (300, cy + 14), (318, cy + 14)])
D.box('keep', 470, ry - 4, 290, 'Yes: leave it exactly as it is', 'checked by the 122 guard observations', 'client', h=60)
D.box('fix', 470, ry + 66, 290, 'No: change the code to match', 'checked by the 40 drift observations', 'new', h=60)
D.box('no', 470, ry + 136, 290, 'Never: edit or delete the documentation', 'one guard observation checks every page and docstring is unedited', 'fault', h=76)
D.arrow([(cx + 30, cy - 24), (430, cy - 24), (430, ry + 26), (470, ry + 26)], kind='ok')
D.arrow([(cx + 38, cy), (470, cy)], kind='new')
D.arrow([(cx + 30, cy + 24), (430, cy + 24), (430, ry + 166), (470, ry + 166)], kind='fault')
D.cross(744, ry + 150, 8)
D.note(790, ry + 10, 274, 'The prompt names the scope and the rule, not the drifts. The agent finds them by reading 68 pages and the docstrings against the code.', 12.5, TEAL, True)
H = ry + 212 + 22 - y0
D.zone(20, y0, 1060, H, 'Where a drift can sit, and what to do with it', 'plain', 'the whole data, transform and patch pipeline is in scope; each documented behaviour is checked against what the code does')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
