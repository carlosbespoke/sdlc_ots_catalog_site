# Render task-environment diagrams with D2 from structured specs, Bespoke Labs palette, grid layout.
import json, os, subprocess, sys, re, textwrap
B = sys.argv[1]; OUT = '/Users/carlos/code/sdlc_final_samples/catalogs/assets'
ICONS = f'{B}/d2/icons'; FONTS = '/Users/carlos/code/sdlc_final_samples/catalogs/site/fonts'
def icon(key):
    if not key: return None
    for p in (f'{ICONS}/si-{key}.svg', f'{ICONS}/tb-{key}.svg'):
        if os.path.exists(p): return p
    return None
def q(s): return '"' + str(s).replace('\\', '\\\\').replace('"', "'").replace('\n', '\\n') + '"'
def wrap(s, w):
    return '\n'.join(line for part in str(s).split('\n') for line in (textwrap.wrap(part, w) or ['']))
def nid(s): return re.sub(r'\W', '_', s)
STYLE = '''vars: {d2-config: {layout-engine: elk; pad: 16}}
classes: {
  band: {style: {fill: "#fbf9f4"; stroke: "#11484e"; stroke-width: 1; font-color: "#446b6e"; border-radius: 0; font-size: 13; bold: true}}
  card: {width: 260; height: 70; style: {fill: "#ffffff"; stroke: "#cfcac2"; font-color: "#11484e"; border-radius: 2; font-size: 13; bold: false}}
  svc: {width: 220; height: 66; style: {fill: "#ffffff"; stroke: "#11484e"; font-color: "#11484e"; border-radius: 2; font-size: 13; bold: false}}
  step: {width: 190; height: 70; style: {fill: "#ffffff"; stroke: "#11484e"; font-color: "#11484e"; border-radius: 14; font-size: 13; bold: false}}
  goal: {width: 300; height: 66; style: {fill: "#11484e"; stroke: "#11484e"; font-color: "#ffffff"; border-radius: 2; font-size: 13; bold: true}}
  check: {width: 260; height: 70; style: {fill: "#d4e8e3"; stroke: "#1f6f6a"; font-color: "#11484e"; border-radius: 2; font-size: 13; bold: false}}
  problem: {width: 760; height: 70; style: {fill: "#fdecea"; stroke: "#f44029"; font-color: "#c83220"; border-radius: 2; font-size: 14; stroke-dash: 3; bold: false}}
}
(** -> **)[*].style: {stroke: "#11484e"; font-color: "#625f5d"; font-size: 12; stroke-width: 1}
'''
def card(i, label, cls, ic):
    p = icon(ic)
    s = f'{i}: {q(wrap(label, 24 if p else 30))} {{class: {cls}'
    if p: s += f'; icon: {p}; icon.near: center-left'
    return s + '}'
def render(spec, path):
    L = [STYLE, 'grid-columns: 1', 'grid-gap: 18']
    L.append(f'problem: {q(wrap(spec["problem"], 90))} {{class: problem; icon: {icon("alert-triangle")}; icon.near: center-left}}')
    n = len(spec['receives'])
    L.append(f'gets: "WHAT THE AGENT RECEIVES" {{class: band; grid-columns: {n}; grid-gap: 14')
    for i, r in enumerate(spec['receives']): L.append('  ' + card(f'r{i}', r['label'], 'card', r.get('icon')))
    L.append('}')
    sysz = spec.get('system')
    if sysz and sysz.get('nodes'):
        L.append(f'sys: {q((sysz.get("label") or "The running system").upper())} {{class: band; direction: right')
        for nd in sysz['nodes']: L.append('  ' + card(nid(nd['id']), nd['label'], 'svc', nd.get('icon')))
        for a, b, *lab in sysz.get('edges', []):
            L.append(f'  {nid(a)} -> {nid(b)}' + (f': {q(lab[0])}' if lab and lab[0] else ''))
        L.append('}')
    L.append('job: "THE AGENT\'S JOB" {class: band; direction: right')
    for i, st in enumerate(spec['job']):
        L.append(f'  j{i}: {q(wrap(f"{i + 1}. {st}", 22))} {{class: step}}')
        if i: L.append(f'  j{i - 1} -> j{i}')
    L.append('}')
    L.append(f'out: "DELIVERABLE" {{class: band; grid-columns: {len(spec["deliver"])}; grid-gap: 14')
    for i, d in enumerate(spec['deliver']): L.append('  ' + f'd{i}: {q(wrap(d["label"], 34))} {{class: goal}}')
    L.append('}')
    L.append(f'verify: "HOW IT IS CHECKED" {{class: band; grid-columns: {len(spec["check"])}; grid-gap: 14')
    for i, c in enumerate(spec['check']): L.append('  ' + card(f'c{i}', c['label'], 'check', c.get('icon')))
    L.append('}')
    src = '\n'.join(L)
    d2p = path[:-4] + '.d2'; open(d2p, 'w').write(src)
    args = ['d2', '--theme=0', f'--font-regular={FONTS}/Inter-Regular.ttf', f'--font-bold={FONTS}/Inter-SemiBold.ttf', f'--font-italic={FONTS}/Inter-Regular.ttf']
    r = subprocess.run(args + [d2p, path], capture_output=True, text=True)
    if r.returncode: print('FAIL', path, r.stderr[-500:])
    return r.returncode == 0
if __name__ == '__main__':
    specs = json.load(open(f'{B}/cat/diagrams.json'))
    ok = sum(render(s, f"{OUT}/env-{s['slug']}-{s['key']}.svg") for s in specs)
    print('rendered', ok, 'of', len(specs))
