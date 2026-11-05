import os, sys; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/Users/carlos/code/sdlc_final_samples/gemini_hard/diagrams')
from sd import *
D = Diagram(1100, 900)
D.title('Gazelle: rebuild a Bazel BUILD file generator from its behavior',
        'The agent can run the original Gazelle but cannot read it. From its documentation and what it does, it writes a new program from scratch that gives the same exit codes, output and BUILD file changes, and the grader replays 196 recorded cases against it.')
top, bot = 104, 470
D.zone(20, top, 330, bot - top, 'What the agent receives', 'side', 'offline container; runs and reads these')
D.box('ref', 36, top + 52, 298, 'Original program', '/opt/reference/executable: execute-only for the agent user, so it can be run but not read or copied', 'svc', 'lock')
D.box('doc', 36, top + 150, 298, 'Upstream documentation', 'README, how Gazelle works, command and flag reference, Go and proto language references: 1,164 lines in /workspace/docs', 'svc', 'book')
D.box('tc', 36, top + 264, 298, 'Offline toolchains', 'Go 1.25, Rust 1.92, C and C++ with cmake, Python 3; no internet and no package registries', 'muted', 'terminal-2')
D.zone(390, top, 330, bot - top, 'Agent writes: /workspace', 'app', 'any language, any design')
D.box('src', 406, top + 52, 298, 'Source project', 'update, fix and update-repos; Go and proto rule generation; directives; merging into existing BUILD files; import resolution', 'svc', 'file-code', tag='WRITE')
D.box('cs', 406, top + 182, 298, './compile.sh', 'builds ./executable from a fresh checkout, offline', 'new')
D.box('ex', 406, top + 260, 298, './executable', 'must behave like the original for the same arguments, input and files', 'dark')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', '196 recorded cases in 19 branches')
y = top + 58
groups = [('layout and output', 39), ('proto rules', 35), ('update-repos', 29), ('transforms', 29), ('directives', 19),
          ('index and resolve', 19), ('Go rules', 14), ('merge and # keep', 9), ('help and errors', 3)]
for name, n in groups:
    D._t(776, y + 4, name, 11.5, False, INK); D._t(1062, y + 4, str(n), 11.5, True, '#c83220', 'end')
    D.el.append(f'<rect x="{930}" y="{y - 6}" width="{n / 39 * 100:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 21
D.box('sc', 776, y + 8, 288, 'Score', 'share of cases where exit code, stdout, stderr and file changes all match', 'dark')
D.arrow([(334, top + 80), (406, top + 80)])
D.arrow([(334, top + 186), (370, top + 186), (370, top + 98), (406, top + 98)])
D.arrow([(555, top + 160), (555, top + 182)])
D.arrow([(555, top + 238), (555, top + 260)])
D.arrow([(704, top + 290), (760, top + 290)], 'fresh build', lpos=.5, loff=(0, -8))
# one comparison: the same command on the same tree, run by the original and by the rebuild
y0 = bot + 28
ZI = len(D.bg)
D.zone(20, y0, 1060, 420, 'One comparison: same arguments, same files, byte-for-byte result', 'plain', 'illustrative example; the file names and the BUILD rule are made up for this picture')
cy = y0 + 62
# input tree
D._t(36, cy, 'INPUT TREE (ILLUSTRATIVE)', 10.5, True, GREY)
def mono(x, y, lines, color=INK, size=10.5):
    for i, l in enumerate(lines):
        D._t(x, y + i * 14.5, l, size, False, color, mono=True); D.el[-1] = D.el[-1].replace('<text ', '<text xml:space="preserve" ', 1)
f, s, c, _ = KIND['client']
D.el.append(f'<rect x="36" y="{cy + 10}" width="230" height="128" rx="5" fill="{f}" stroke="{s}"/>')
mono(48, cy + 30, ['repo/', '  WORKSPACE', '  go.mod', '  hello/', '    hello.go', '    hello_test.go'], TEAL)
D._t(36, cy + 164, 'COMMAND', 10.5, True, GREY)
D.el.append(f'<rect x="36" y="{cy + 174}" width="230" height="30" rx="5" fill="{f}" stroke="{s}"/>')
mono(48, cy + 194, ['$ <program> update'], TEAL)
D.note(36, cy + 226, 230, 'run once with the original and once with ./executable, each on its own fresh copy of the tree', 11, GREY)
# two runs
lx, lw = 320, 420
for k, (lab, kind, yy) in enumerate([('/opt/reference/executable', 'svc', cy + 10), ('./executable', 'dark', cy + 182)]):
    ff, ss, cc, _ = KIND[kind]
    D.el.append(f'<rect x="{lx}" y="{yy}" width="{lw}" height="160" rx="5" fill="{ff}" stroke="{ss}" stroke-width="1.2"/>')
    D._t(lx + 12, yy + 20, lab, 12.5, True, cc)
    D._t(lx + 12, yy + 40, 'writes hello/BUILD.bazel:', 11, False, cc if kind == 'dark' else GREY)
    D.el.append(f'<rect x="{lx + 12}" y="{yy + 48}" width="{lw - 24}" height="102" rx="4" fill="#1d2b2c" stroke="{TEAL}"/>')
    mono(lx + 22, yy + 64, ['load("@rules_go//go:def.bzl", "go_library", "go_test")', '', 'go_library(', '    name = "hello",', '    srcs = ["hello.go"],', '    ...'], '#e8efe9', 10)
D.arrow([(266, cy + 80), (320, cy + 80)])
D.arrow([(266, cy + 189), (293, cy + 189), (293, cy + 262), (320, cy + 262)])
# comparison column
cx0 = 790
D._t(cx0, cy, 'COMPARED, BYTE FOR BYTE', 10.5, True, GREY)
items = [('exit code', 'same number'), ('standard output', 'same bytes'), ('standard error', 'same bytes, messages included'), ('file changes', 'every file written, edited or left alone')]
yy = cy + 24
for name, sub in items:
    D.el.append(f'<rect x="{cx0}" y="{yy}" width="274" height="50" rx="5" fill="#ffffff" stroke="#cfcac2"/>')
    D.check(cx0 + 20, yy + 25)
    D._t(cx0 + 40, yy + 22, name, 12.5, True, TEAL); D._t(cx0 + 40, yy + 39, sub, 11, False, GREY)
    yy += 60
for k in range(2):
    sy = cy + 90 + k * 172
    D.arrow([(lx + lw, sy), (cx0 - 14, sy), (cx0 - 14, cy + 174), (cx0, cy + 174)], head=(k == 1), kind='ok')
D.note(cx0, yy + 8, 274, 'Any difference, such as one extra space in a BUILD file, fails the case.', 11.5, '#c83220')
D.h = y0 + 420 + 20
D.save(HERE + '/diagram.svg')
