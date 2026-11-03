import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('SVT-AV1-PSY: rebuild an AV1 video encoder from its behavior',
        'The agent can run the reference encoder but cannot read it. From its documentation and what it prints, it writes a new program from scratch that gives the same output, exit codes and files, and the grader replays 453 recorded runs against it.')
top, bot = 104, 456
D.zone(20, top, 330, bot - top, 'What the agent receives', 'side', 'offline container; runs and reads these')
D.box('ref', 36, top + 52, 298, 'Reference executable', '/opt/task-reference/executable: execute-only, so it can be run but not read or copied', 'svc', 'lock')
D.box('doc', 36, top + 150, 298, 'Bundled documentation', 'README, Parameters, user guide and common questions: 1,017 lines in /workspace/docs', 'svc', 'book')
D.box('tc', 36, top + 248, 298, 'Offline toolchains', 'C and C++ with cmake, Go 1.25, Rust 1.92, Python 3; no package registries', 'muted', 'terminal-2')
D.zone(390, top, 330, bot - top, 'Agent writes: /workspace', 'app', 'any language, any design')
D.box('src', 406, top + 52, 298, 'Source project', 'option parsing, Y4M input, encoder, IVF writer, log and summary output', 'svc', 'file-code', tag='WRITE')
D.box('cs', 406, top + 150, 298, './compile.sh', 'builds ./executable from a fresh checkout, offline', 'new')
D.box('ex', 406, top + 228, 298, './executable', 'must behave like the reference for every documented option', 'dark')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', '453 recorded runs in 9 branches')
y = top + 58
groups = [('errors and edge cases', 136), ('command root', 92), ('rate control options', 83), ('flag interaction', 80),
          ('encoder global options', 25), ('options', 17), ('psychovisual options', 9), ('color description', 7), ('help output', 4)]
for name, n in groups:
    D._t(776, y + 4, name, 11.5, False, INK); D._t(1062, y + 4, str(n), 11.5, True, '#c83220', 'end')
    D.el.append(f'<rect x="{940}" y="{y - 6}" width="{n / 136 * 92:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 21
D.box('sc', 776, y + 8, 288, 'Score', 'fraction of runs where exit code, stdout, stderr and written files all match', 'dark')
D.arrow([(334, top + 80), (406, top + 80)])
D.arrow([(334, top + 178), (370, top + 178), (370, top + 98), (406, top + 98)])
D.arrow([(555, top + 128), (555, top + 150)])
D.arrow([(555, top + 206), (555, top + 228)])
D.arrow([(704, top + 258), (760, top + 258)], 'fresh build', lpos=.5, loff=(0, -8))
# two recorded runs
y0 = bot + 28
ZI = len(D.bg)
D.zone(20, y0, 1060, 360, 'Two of the recorded runs the rebuild must match', 'plain', 'each run starts from a fixture such as clip.y4m (64 x 64, 30 fps, 24,637 bytes); 111 of the 453 runs exit 0 and 342 exit 1')
cols = [(36, 250, 'Command'), (300, 70, 'Exit'), (384, 470, 'stderr excerpt, compared byte for byte (timings masked)'), (868, 196, 'File written')]
hy = y0 + 70
for x, w, h in cols: D._t(x, hy, h.upper(), 10.5, True, GREY)
def mono(x, y, lines, color=INK, size=10.5):
    for i, l in enumerate(lines):
        D._t(x, y + i * 14.5, l, size, False, color, mono=True); D.el[-1] = D.el[-1].replace('<text ', '<text xml:space="preserve" ', 1)
rows = [
    (['-i clip.y4m -b movie.ivf', '--lp 1 --preset 12', '--progress 0 --enable-dlf 2'], '0', 'ok',
     ['Svt[info]: SVT [version]: SVT-AV1-PSY Encoder Lib 2.1.0rc2', 'Svt[warn]: Preset M12 is mapped to M13.',      'Svt[info]: SVT [config]: BRC mode / rate factor : CRF / 35.00', 'Total Frames  Frame Rate  Byte Count  Bitrate', '           4   30.00 fps        1903  114.18 kbps'],
     ('movie.ivf', '1,983 bytes, an AV1 stream in an IVF container, compared byte for byte')),
    (['--hierarchical-levels --qm-min', '-i clip.y4m -b movie.ivf', '--lp 1 --preset 12 --progress 0'], '1', 'fault',
     ['Svt[info]: SVT [version]: SVT-AV1-PSY Encoder Lib 2.1.0rc2', '[SVT-Error]: No argument found for token `--hierarchical-levels`', 'Error in configuration, could not begin encoding! ...', 'Run $PROGRAM --help for a list of options'],
     ('movie.ivf', '32 bytes: only the IVF header is written before the error')),
]
ry = hy + 16
for cmd, rc, kind, err, (fn, fdesc) in rows:
    h = 22 + max(len(err), len(cmd)) * 14.5
    f, s, c, _ = KIND['client']
    D.el.append(f'<rect x="36" y="{ry}" width="250" height="{h}" rx="5" fill="{f}" stroke="{s}"/>')
    mono(48, ry + 19, ['$ ./executable \\'] + ['   ' + l + (' \\' if i < len(cmd) - 1 else '') for i, l in enumerate(cmd)], TEAL)
    f, s, c, _ = KIND['dark' if kind == 'ok' else 'fault']
    D.el.append(f'<rect x="300" y="{ry}" width="70" height="{h}" rx="5" fill="{f}" stroke="{s}"/>')
    D._t(335, ry + h / 2 + 8, rc, 24, True, c, 'middle')
    D.el.append(f'<rect x="384" y="{ry}" width="470" height="{h}" rx="5" fill="#1d2b2c" stroke="{TEAL}"/>')
    mono(396, ry + 19, err, '#e8efe9', 10)
    D.el.append(f'<rect x="868" y="{ry}" width="196" height="{h}" rx="5" fill="#ffffff" stroke="#9d988f"/>')
    D.icon('file-text', 880, ry + 12, 18, TEAL)
    D._t(904, ry + 26, fn, 12.5, True, TEAL)
    D.note(880, ry + 50, 172, fdesc, 11, GREY)
    ry += h + 14
D.h = ry + 20
D.bg[ZI] = D.bg[ZI].replace('height="360"', f'height="{ry - y0 + 4}"')
D.save(HERE + '/diagram.svg')
