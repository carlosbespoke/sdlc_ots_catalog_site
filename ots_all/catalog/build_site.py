#!/usr/bin/env python3
"""Build the catalogs without editing their Markdown sources.

Usage: python build_site.py [catalog_directory] [--verify]
Dependency: markdown-it-py (use >=3,<4 on Python 3.9; >=3 on newer Python).
Install into the chosen virtual environment, never globally. No build-time network
requests. Existing site/fonts are preserved; all other site content is generated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit

try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except ImportError:
    raise SystemExit('Install markdown-it-py in your virtual environment: '
                     'python -m pip install "markdown-it-py>=3,<4"')

FILES = ('README.md', 'programbench.md', 'system-design.md', 'debugging.md', 'feature-implementation.md',
         'infrastructure-as-code.md', 'data-engineering.md', 'migration.md', 'optimization.md')
MERMAID_URL = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js'
NUMERIC = re.compile(r'^[+−-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)%?(?:\s*\([\d.,]+%?\))?$')

CSS = r'''
@font-face{font-family:'GT Alpina Light';src:url('fonts/GT-Alpina-Standard-Light.woff2') format('woff2');font-weight:300 400;font-display:swap}
@font-face{font-family:Inter;src:url('fonts/Inter-Regular.ttf') format('truetype');font-weight:400;font-display:swap}
@font-face{font-family:Inter;src:url('fonts/Inter-Light.ttf') format('truetype');font-weight:300;font-display:swap}
@font-face{font-family:Inter;src:url('fonts/Inter-Medium.ttf') format('truetype');font-weight:500;font-display:swap}
@font-face{font-family:Inter;src:url('fonts/Inter-SemiBold.ttf') format('truetype');font-weight:600 900;font-display:swap}
@font-face{font-family:'MD IO';src:url('fonts/MDIO-Regular.woff2') format('woff2');font-display:swap}
:root{color-scheme:light;--paper:#f7f4ed;--card:#fbf9f4;--soft:#f0ece4;--ink:#11484e;--ink-2:#446b6e;--muted:#625f5d;--faint:#9a9590;--line:#cfcac2;--line-2:#e3ded5;--band:#0f484d;--red:#f44029;--red-ink:#c83220;--teal:#1f6f6a;--mint:#d4e8e3;--blue:#b9c8dd;--lime:#daf767;--serif:'GT Alpina Light',Georgia,'Times New Roman',serif;--sans:Inter,Arial,sans-serif;--mono:'MD IO',ui-monospace,monospace}
*{box-sizing:border-box}html{scroll-padding-top:28px}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.7 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--ink);text-decoration-color:rgba(17,72,78,.35);text-underline-offset:3px}a:hover{text-decoration-color:var(--red)}button{font:inherit;color:inherit}button,a,summary{touch-action:manipulation}:focus-visible{outline:2px solid var(--red);outline-offset:3px}::selection{background:var(--mint)}[hidden]{display:none!important}
.skip{position:fixed;left:16px;top:-100px;z-index:10;background:var(--card);padding:12px}.skip:focus{top:12px}
.band{margin:12px;background:var(--band);color:white}.band-in{display:flex;align-items:center;gap:12px;min-height:70px;padding:16px 32px}.brand{flex:none}.brand img{display:block;width:162px;height:auto}.band .div{color:rgba(255,255,255,.3)}.crumb{font-size:13px;font-weight:500;color:rgba(255,255,255,.7);overflow-wrap:anywhere;min-width:0}.crumb a{color:inherit;text-decoration-color:rgba(255,255,255,.35)}.crumb a:hover{text-decoration-color:var(--red)}
.hero{max-width:1228px;margin:0 auto;padding:50px 24px 36px}.hero h1{font:400 clamp(48px,6.3vw,82px)/1.02 var(--serif);letter-spacing:-.045em;margin:0;max-width:1000px;text-wrap:balance}.hero-meta{margin-top:30px;border-top:1px solid var(--line);height:1px}
.page{max-width:1228px;margin:0 auto;padding:0 24px 80px;display:grid;grid-template-columns:190px minmax(0,1fr);gap:50px;align-items:start}.reading,article,main{min-width:0}.reading{max-width:940px}.reading>p,.reading>ul,.reading>ol,.reading>blockquote,.reading>details,.reading>pre,.reading>h2,.reading>h3,.reading>h4,.reading>h5,.reading>h6{max-width:760px}
h1,h2,h3,h4{font-family:var(--serif);font-weight:400;color:var(--ink);overflow-wrap:anywhere}h2{font-size:clamp(38px,4.4vw,52px);line-height:1.05;letter-spacing:-.035em;margin:72px 0 22px}h3{font-size:clamp(25px,2.6vw,29px);line-height:1.15;letter-spacing:-.02em;margin:44px 0 12px}h4{font-size:24px;line-height:1.2;letter-spacing:-.015em;margin:28px 0 12px}h5,h6{font-size:15px;font-weight:600;margin:24px 0 10px}h2,h3,h4{scroll-margin-top:8px}.reading>h2:first-child{margin-top:0}
p{margin:0 0 20px;overflow-wrap:anywhere}ul,ol{padding-left:1.3em;margin:0 0 20px}li{margin-bottom:10px;overflow-wrap:anywhere}li::marker{color:var(--red)}strong{font-weight:600}hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.contents{position:sticky;top:28px;max-height:calc(100vh - 56px);overflow-y:auto;scrollbar-width:thin;align-self:start;background:var(--paper);padding-right:8px}.contents-label{display:block;font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--ink-2);font-weight:600;margin:0 0 14px}.contents a{display:block;border-left:3px solid transparent;color:var(--ink-2);font:500 13px/1.4 var(--sans);padding:6px 0 6px 10px;text-decoration:none;overflow-wrap:anywhere}.contents a:hover,.contents a:focus-visible,.contents a[aria-current]{color:var(--ink);border-left-color:var(--red)}.contents a[aria-current]{font-weight:600}.catalog-nav{padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid var(--line-2)}.catalog-nav a{display:flex;align-items:baseline;justify-content:space-between;gap:8px}.count{font:10px var(--mono);color:var(--muted);white-space:nowrap}.toc-links .level-3{font-size:12px;padding-left:20px;font-weight:400}.toc-empty{font-size:12px;color:var(--muted)}
.table-scroll{max-width:100%;overflow-x:auto;margin:24px 0 30px}table.data{border-collapse:collapse;width:100%;font-size:14px;line-height:1.6;font-variant-numeric:tabular-nums}th,td{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:13px;font-weight:600;border-bottom:1px solid var(--ink)}th:first-child,td:first-child{padding-left:0}td code{white-space:normal;overflow-wrap:anywhere}.numeric,th.numeric{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.group-header td{border-top:1.5px solid var(--ink);color:var(--ink);font-weight:600;padding-top:16px}
.sort-button{display:block;width:100%;padding:0;border:0;background:none;cursor:pointer;text-align:inherit;font:inherit;color:inherit}.sort-button::after{content:' ↕';color:var(--faint);white-space:nowrap}th[aria-sort=ascending] .sort-button::after{content:' ↑';color:var(--ink)}th[aria-sort=descending] .sort-button::after{content:' ↓';color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:6px 0 30px;max-width:820px}.kpi{padding:18px 20px;background:var(--card);border:1px solid var(--line-2);border-top:3px solid var(--red)}.kpi-value{font:400 46px/1 var(--serif);letter-spacing:-.03em;color:var(--ink);white-space:nowrap}.kpi-label{margin-top:8px;font-size:13px;font-weight:600;line-height:1.35;color:var(--ink-2)}
figure.fig{margin:30px 0 36px;max-width:940px;min-width:0}.fig-head{margin-bottom:12px}.fig-head .lab{font:11px/1.4 var(--mono);color:var(--muted);letter-spacing:.06em;text-transform:uppercase}.fig-head h4{margin:6px 0 0;font:400 25px/1.15 var(--serif);letter-spacing:-.02em;text-wrap:balance}.fig-box{border-top:1px solid var(--ink);border-bottom:1px solid var(--line);padding:16px 0 12px;min-width:0}.fig-box img{display:block;width:100%;height:auto;max-width:100%}.diagram-note{display:block;font-size:12px;color:var(--muted);margin:0 0 10px}.diagram-view{min-width:0}.diagram-view svg{display:block;max-width:100%;height:auto;margin:auto}.diagram-view svg text{font-family:var(--sans)}
blockquote{margin:24px 0;padding:16px 20px;background:var(--soft);border-left:2px solid var(--ink);font-size:15px}blockquote p:last-child{margin-bottom:0}.draft-label{display:block;font:11px var(--mono);letter-spacing:.08em;color:var(--red-ink);margin-bottom:9px}
code,pre{font-family:var(--mono);font-size:.85em}code{background:var(--soft);padding:2px 4px;border-radius:0;overflow-wrap:anywhere}pre{max-width:100%;overflow-x:auto;padding:18px;background:var(--soft);border:1px solid var(--line-2);font-size:13px;line-height:1.7;white-space:pre;tab-size:4}pre code{padding:0;background:none;border:0;font:inherit;white-space:inherit;overflow-wrap:normal}
details{margin:18px 0 28px;border:1px solid var(--line-2);border-left:2px solid var(--ink);background:var(--card);min-width:0}summary{cursor:pointer;padding:14px 18px;font-size:13px;font-weight:500;overflow-wrap:anywhere}details[open] summary{border-bottom:1px solid var(--line-2)}details pre{max-width:100%}.prompt-md{padding:6px 20px 18px;font:15px/1.65 var(--sans);min-width:0}.prompt-md h5,.prompt-md h6{font:600 15px/1.4 var(--sans);margin:18px 0 6px}.prompt-md pre{margin:12px 0}.prompt-md p{margin:8px 0}.prompt-md ul,.prompt-md ol{padding-left:22px}.prompt-md .table-scroll{margin:16px 0}
.task-chips{display:flex;flex-wrap:wrap;gap:8px 20px;margin:16px 0 28px;max-width:760px}.task-chips a{font-size:12px;line-height:1.6;overflow-wrap:anywhere;max-width:100%;color:var(--ink-2)}
.page-footer{margin-top:60px;border-top:1px solid var(--ink);padding-top:22px}.page-nav{display:flex;justify-content:space-between;gap:24px;margin-top:25px}.page-nav a{font-size:14px;max-width:48%;overflow-wrap:anywhere}.page-nav a:last-child{margin-left:auto;text-align:right}.page-nav small{display:block;font:10px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}.back-top{font-size:12px}.footer-word{font-size:11px;color:var(--muted);margin-top:40px}
@media(max-width:880px){.page{grid-template-columns:minmax(0,1fr);gap:30px}.contents{position:static;max-height:none;padding:0 0 22px;border-bottom:1px solid var(--line)}.catalog-nav,.toc-links{columns:2;column-gap:24px}.contents a{break-inside:avoid}.catalog-nav{padding-bottom:14px;margin-bottom:14px}.hero{padding-top:36px}.band-in{padding:16px 20px}.reading{width:100%}}
@media(max-width:540px){body{font-size:16.5px}.band{margin:8px}.band-in{flex-wrap:wrap;padding:16px;gap:10px}.brand img{width:162px}.crumb{flex:1 1 100%;font-size:12px}.band .div{display:none}.hero{padding:32px 16px 28px}.hero h1{font-size:48px}.page{padding:0 16px 50px}.catalog-nav,.toc-links{column-gap:12px}.contents a{font-size:12px}.toc-links .level-3{font-size:11px;padding-left:14px}h2{margin-top:50px}.prompt-md{padding:6px 14px 16px}th,td{padding:9px}.page-nav{gap:15px}}
@media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
@media print{.band,.contents,.task-chips,.page-footer,.skip{display:none}.page{display:block;padding:0}.hero{padding:0 0 24px}body{background:white;font-size:10pt}h2,h3{break-after:avoid}pre{white-space:pre-wrap;overflow-wrap:anywhere}.table-scroll{overflow:visible}table.data{font-size:8pt}}
'''

JS = r'''
'use strict';
// Sort only after a reader asks. Domain children always remain with their group.
const numeric = /^[+−-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)%?(?:\s*\([\d.,]+%?\))?$/;
document.querySelectorAll('article table').forEach(table => {
  const body = table.tBodies[0];
  if (!body) return;
  const original = Array.from(body.rows);
  const headers = Array.from(table.tHead.rows[0].cells);
  headers.forEach((header, column) => {
    const button = header.querySelector('button');
    button.addEventListener('click', () => {
      const direction = header.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
      headers.forEach(h => h.setAttribute('aria-sort', 'none'));
      header.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
      const value = row => (row.cells[column]?.textContent || '').trim();
      const compare = (a, b) => {
        const av = value(a), bv = value(b);
        if (!av || !bv) return av === bv ? 0 : av ? -1 : 1;
        const order = numeric.test(av) && numeric.test(bv)
          ? parseFloat(av.replaceAll(',', '').replace('−', '-')) - parseFloat(bv.replaceAll(',', '').replace('−', '-'))
          : av.localeCompare(bv, undefined, {numeric:true, sensitivity:'base'});
        return order * direction;
      };
      const groups = [];
      const loose = [];
      for (const row of original) {
        if (row.classList.contains('group-header')) groups.push({head:row, children:[]});
        else if (groups.length) groups[groups.length - 1].children.push(row);
        else loose.push(row);
      }
      let sorted = loose.slice().sort(compare);
      if (groups.length) {
        groups.sort((a, b) => compare(a.head, b.head));
        for (const group of groups) sorted.push(group.head, ...group.children.slice().sort(compare));
      }
      body.replaceChildren(...sorted);
    });
  });
});

const headings = Array.from(document.querySelectorAll('article h2, article h3'));
const tocLinks = Array.from(document.querySelectorAll('.toc-links a'));
let scheduled = false;
function updateToc() {
  const offset = 40;
  let current = headings[0];
  for (const heading of headings) {
    if (heading.getBoundingClientRect().top <= offset) current = heading;
    else break;
  }
  tocLinks.forEach(link => {
    if (current && link.hash === '#' + current.id) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  scheduled = false;
}
function scheduleToc() { if (!scheduled) { scheduled = true; requestAnimationFrame(updateToc); } }
addEventListener('scroll', scheduleToc, {passive:true});
addEventListener('resize', scheduleToc);
addEventListener('hashchange', scheduleToc);
document.addEventListener('toggle', scheduleToc, true);
updateToc();

// The source stays in the HTML for offline access and per-diagram failure recovery.
const diagrams = Array.from(document.querySelectorAll('[data-mermaid]'));
function diagramFailure(figure, note = 'Diagram could not be rendered. Source shown below.') {
  figure.dataset.state = 'failed';
  figure.querySelector('.diagram-note').textContent = note;
  figure.querySelector('pre').hidden = false;
}
async function renderDiagrams() {
  if (!window.mermaid) { diagrams.forEach(figure => diagramFailure(figure)); return; }
  try {
    mermaid.initialize({startOnLoad:false, securityLevel:'strict', suppressErrorRendering:true,
      theme:'base', themeVariables:{fontFamily:'Inter, Arial, sans-serif', fontSize:'13px',
        primaryColor:'#fbf9f4', primaryTextColor:'#11484e', primaryBorderColor:'#11484e',
        secondaryColor:'#f7f4ed', secondaryTextColor:'#11484e', tertiaryColor:'#f0ece4',
        lineColor:'#11484e', textColor:'#11484e', mainBkg:'#fbf9f4', nodeBorder:'#11484e',
        clusterBkg:'#f7f4ed', clusterBorder:'#11484e', edgeLabelBackground:'#f7f4ed'}});
  } catch (error) { diagrams.forEach(figure => diagramFailure(figure)); return; }
  for (const [index, figure] of diagrams.entries()) {
    const source = figure.querySelector('pre code').textContent;
    const staging = document.createElement('div');
    staging.style.cssText = 'position:absolute;left:-100000px;top:0;width:1000px';
    document.body.append(staging);
    try {
      const result = await mermaid.render('catalog-diagram-' + index, source, staging);
      const view = document.createElement('div');
      view.className = 'diagram-view'; view.innerHTML = result.svg;
      figure.querySelector('.fig-box').append(view);
      result.bindFunctions?.(view);
      figure.querySelector('pre').hidden = true;
      figure.querySelector('.diagram-note').hidden = true;
      figure.dataset.state = 'rendered';
    } catch (error) {
      figure.querySelector('.diagram-view')?.remove();
      diagramFailure(figure);
    } finally { staging.remove(); }
  }
  scheduleToc();
}
if (diagrams.length) {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js';
  script.onload = renderDiagrams;
  script.onerror = () => diagrams.forEach(figure => diagramFailure(figure));
  document.head.append(script);
}
'''


def parser():
    return MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough'])


def inline_text(token):
    return ''.join(t.content for t in (token.children or [])
                   if t.type in ('text', 'code_inline', 'image', 'html_inline'))


def output_name(source):
    return 'index.html' if source == 'README.md' else Path(source).with_suffix('.html').name


def rewrite_link(href):
    parts = urlsplit(href)
    path = parts.path.removeprefix('./')
    if not parts.scheme and not parts.netloc and path in FILES:
        return urlunsplit(('', '', output_name(path), parts.query, parts.fragment))
    return href


def raw_token(html):
    token = Token('html_block', '', 0)
    token.content = html
    return token


def table_rows(tokens, start, end):
    rows = []
    for i in range(start, end):
        if tokens[i].type == 'tr_open':
            rows.append((tokens[i], []))
        elif tokens[i].type in ('th_open', 'td_open'):
            rows[-1][1].append((tokens[i], tokens[i + 1]))
    return rows


def decorate_tables(tokens):
    for start, token in enumerate(tokens):
        if token.type != 'table_open':
            continue
        end = next(i for i in range(start + 1, len(tokens)) if tokens[i].type == 'table_close')
        rows = table_rows(tokens, start, end)
        columns = len(rows[0][1])
        for column in range(columns):
            values = [inline_text(cells[column][1]).strip() for _, cells in rows[1:]]
            nonempty = [v for v in values if v]
            is_numeric = bool(nonempty) and all(NUMERIC.fullmatch(v) for v in nonempty)
            for _, cells in rows:
                cell, content = cells[column]
                # Several source tables mark text columns right-aligned. Infer numbers
                # from the actual data, keeping mixed metadata values readable.
                cell.attrs.pop('style', None)
                if is_numeric or (cell.type == 'td_open' and NUMERIC.fullmatch(inline_text(content).strip())):
                    cell.attrSet('class', 'numeric')
                if cell.type == 'th_open':
                    cell.attrSet('scope', 'col')
                    cell.attrSet('aria-sort', 'none')
        for row, cells in rows[1:]:
            if columns >= 2 and any(t.type == 'strong_open' for t in cells[0][1].children or []) and not inline_text(cells[1][1]).strip():
                row.attrSet('class', 'group-header')


def read_catalogs(readme):
    tokens = parser().parse(readme)
    catalogs = []
    for i, token in enumerate(tokens):
        if token.type != 'tr_open':
            continue
        end = next(j for j in range(i + 1, len(tokens)) if tokens[j].type == 'tr_close')
        cells = [t for t in tokens[i:end] if t.type == 'inline']
        if len(cells) < 2:
            continue
        links = [t.attrGet('href') for t in cells[0].children or [] if t.type == 'link_open']
        if links and links[0] in FILES[1:]:
            catalogs.append({'source': links[0], 'label': inline_text(cells[0]),
                             'count': inline_text(cells[1]), 'href': output_name(links[0])})
    if Counter(c['source'] for c in catalogs) != Counter(FILES[1:]):
        raise ValueError('README must list each of the eight catalogs exactly once.')
    return catalogs


def render_article(source):
    md = parser()
    tokens = md.parse(source)
    seen = set()
    headings = []
    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            title = inline_text(tokens[i + 1])
            slug = re.sub(r'[^\w\s-]', '', unicodedata.normalize('NFKC', title).lower())
            slug = re.sub(r'[-\s]+', '-', slug).strip('-') or 'section'
            anchor, n = slug, 2
            while anchor in seen:
                anchor, n = f'{slug}-{n}', n + 1
            seen.add(anchor)
            token.attrSet('id', anchor)
            headings.append((i, token.tag, title, anchor))
        if token.type == 'inline':
            for child in token.children or []:
                if child.type == 'link_open':
                    child.attrSet('href', rewrite_link(child.attrGet('href') or ''))
    decorate_tables(tokens)
    insertions = {}
    for position, (index, level, title, anchor) in enumerate(headings):
        if level == 'h2' and title.casefold() in ('showcase tasks', 'example tasks from the shortlist', 'sample tasks'):
            tasks = []
            for _, sublevel, subtitle, subanchor in headings[position + 1:]:
                if sublevel in ('h1', 'h2'):
                    break
                if sublevel == 'h3':
                    tasks.append(f'<a href="#{escape(subanchor)}">{escape(subtitle)}</a>')
            if tasks:
                insertions[index + 3] = raw_token('<nav class="task-chips" data-ui aria-label="Example tasks">' + ''.join(tasks) + '</nav>\n')
    for index in sorted(insertions, reverse=True):
        tokens.insert(index, insertions[index])

    def fence(renderer, items, index, options, env):
        token = items[index]
        if token.info.strip().split(' ', 1)[0].lower() == 'mermaid':
            return ('<figure class="fig diagram" data-mermaid data-state="source">'
                    '<div class="fig-head" data-ui><span class="lab">Figure</span><h4>Environment diagram</h4></div>'
                    '<div class="fig-box">'
                    '<small class="diagram-note" data-ui>Diagram source. Rendering requires the Mermaid CDN.</small>'
                    '<pre tabindex="0"><code class="language-mermaid">' + escape(token.content) + '</code></pre></div></figure>\n')
        language = token.info.strip().split(' ', 1)[0]
        return f'<pre tabindex="0"><code class="language-{escape(language, quote=True)}">{escape(token.content)}</code></pre>\n'

    def image(renderer, items, index, options, env):
        token = items[index]
        caption = renderer.renderInlineAsText(token.children or [], options, env)
        return ('<figure class="fig"><div class="fig-head" data-ui>'
                '<span class="lab">Figure</span><h4>' + escape(caption) + '</h4></div>'
                '<div class="fig-box">' + renderer.image(items, index, options, env) + '</div></figure>')

    # Figures are block elements: omit the Markdown paragraph around image runs.
    def paragraph(renderer, items, index, options, env):
        inline = items[index + 1 if items[index].type == 'paragraph_open' else index - 1]
        if any(t.type == 'image' for t in inline.children or []):
            return ''
        return renderer.renderToken(items, index, options, env)

    md.add_render_rule('fence', fence)
    md.add_render_rule('image', image)
    md.add_render_rule('paragraph_open', paragraph)
    md.add_render_rule('paragraph_close', paragraph)
    md.add_render_rule('table_open', lambda r, ts, i, o, e: '<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable data table">\n<table class="data">\n')
    md.add_render_rule('table_close', lambda r, ts, i, o, e: '</table>\n</div>\n')
    md.add_render_rule('th_open', lambda r, ts, i, o, e: r.renderToken(ts, i, o, e) + '<button class="sort-button" type="button" title="Sort this column">')
    md.add_render_rule('th_close', lambda r, ts, i, o, e: '</button>' + r.renderToken(ts, i, o, e))
    return md.renderer.render(tokens, md.options, {}), headings


def render_page(source, filename, catalogs):
    article, headings = render_article(source)
    title = next((h[2] for h in headings if h[1] == 'h1'), Path(filename).stem)
    hero = re.search(r'<h1\b[^>]*>.*?</h1>', article, re.DOTALL)
    hero_html = hero.group(0) if hero else ''
    if hero:
        article = article[:hero.start()] + article[hero.end():]
    crumb = ('Coding OTS RL Envs' if filename == 'README.md' else
             '<a href="index.html">Coding OTS RL Envs</a> / ' + escape(title))
    nav = []
    total = sum(int(c['count'].replace(',', '')) for c in catalogs if c['count'].replace(',', '').isdigit())
    entries = [{'source': 'README.md', 'label': 'Overview', 'count': f'{total:,}' if total else '', 'href': 'index.html'}] + catalogs
    for entry in entries:
        current = ' aria-current="page"' if entry['source'] == filename else ''
        count = f'<span class="count" aria-label="{escape(entry["count"])} tasks">{escape(entry["count"])}</span>' if entry['count'] else ''
        nav.append(f'<a href="{entry["href"]}"{current}><span>{escape(entry["label"])}</span>{count}</a>')
    toc = ''.join(f'<a class="level-{level[1]}" href="#{escape(anchor)}">{escape(text)}</a>'
                  for _, level, text, anchor in headings if level in ('h2', 'h3'))
    if not toc:
        toc = '<p class="toc-empty">Catalog overview</p>'
    position = next(i for i, entry in enumerate(entries) if entry['source'] == filename)
    pager = []
    for offset, label, rel in [(-1, 'Previous', 'prev'), (1, 'Next', 'next')]:
        if 0 <= position + offset < len(entries):
            target = entries[position + offset]
            pager.append(f'<a rel="{rel}" href="{target["href"]}"><small>{label}</small>{escape(target["label"])}</a>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>{escape(title)} | Bespoke Labs</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="site.css"><script src="site.js" defer></script></head>
<body id="top"><a class="skip" href="#content">Skip to content</a>
<header class="band"><div class="band-in"><a class="brand" href="index.html"><img src="assets/bespoke-labs-logo.svg" alt="Bespoke Labs" width="162"></a>
<span class="div" aria-hidden="true">/</span><div class="crumb">{crumb}</div></div></header>
<main id="content" tabindex="-1"><article id="catalog-content">
<header class="hero">{hero_html}<div class="hero-meta" aria-hidden="true"></div></header>
<div class="page"><aside class="contents" aria-label="Contents" data-ui><p class="contents-label">Contents</p>
<nav class="catalog-nav" aria-label="Catalogs">{''.join(nav)}</nav><nav class="toc-links" aria-label="On this page">{toc}</nav></aside>
<div class="reading">{article}
<footer class="page-footer" data-ui><a class="back-top" href="#top">Back to top ↑</a><nav class="page-nav" aria-label="Previous and next catalogs">{''.join(pager)}</nav>
<p class="footer-word">Bespoke Labs · Coding OTS RL Envs</p></footer></div></div></article></main>
</body></html>
'''


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def walk(self, skip_ui=False):
        if skip_ui and 'data-ui' in self.attrs:
            return
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk(skip_ui)

    def text(self, skip_ui=False):
        if skip_ui and 'data-ui' in self.attrs:
            return ''
        return ''.join(child.text(skip_ui) if isinstance(child, Node) else child for child in self.children)


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def verify(root, sources):
    """Compare article contents and structures to an undecorated Markdown render.

    Fences are also checked against source tokens, byte-for-byte after Markdown's
    newline normalization. Generated navigation and figure captions are excluded.
    """
    results = []
    norm = lambda text: re.sub(r'\s+', ' ', text).strip()
    for filename, source in sources.items():
        baseline = Document(parser().render(source)).root
        page = Document((root / 'site' / output_name(filename)).read_text()).root
        article = next(node for node in page.walk() if node.attrs.get('id') == 'catalog-content')
        assert norm(baseline.text()) == norm(article.text(skip_ui=True)), f'{filename}: article text changed'
        expected_h2 = [node.text() for node in baseline.walk() if node.tag == 'h2']
        actual_h2 = [node.text() for node in article.walk() if node.tag == 'h2']
        assert expected_h2 == actual_h2, f'{filename}: h2 headings differ'
        assert [(n.tag, n.text()) for n in baseline.walk() if n.tag in ('h2', 'h3')] == [
            (n.tag, n.text()) for n in article.walk() if n.tag in ('h2', 'h3')
        ], f'{filename}: section headings differ'
        structural_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr', 'th', 'td', 'blockquote', 'li', 'ul', 'ol', 'details', 'summary', 'pre', 'img', 'strong', 'em'}
        expected_structure = [n.tag for n in baseline.walk() if n.tag in structural_tags]
        actual_structure = [n.tag for n in article.walk(skip_ui=True) if n.tag in structural_tags]
        assert expected_structure == actual_structure, f'{filename}: content structure changed'
        expected_code = [n.text() for n in baseline.walk() if n.tag == 'pre']
        actual_code = [n.text() for n in article.walk() if n.tag == 'pre']
        assert expected_code == actual_code, f'{filename}: code source changed'
        tokens = parser().parse(source)
        mermaid = [t.content for t in tokens if t.type == 'fence' and t.info.strip() == 'mermaid']
        rendered_mermaid = [n for n in article.walk() if 'data-mermaid' in n.attrs]
        assert len(mermaid) == len(rendered_mermaid), f'{filename}: Mermaid count differs'
        assert mermaid == [next(x.text() for x in n.walk() if x.tag == 'pre') for n in rendered_mermaid]
        ids = [n.attrs['id'] for n in page.walk() if 'id' in n.attrs]
        assert len(ids) == len(set(ids)), f'{filename}: duplicate anchors'
        images = [n.attrs['src'] for n in article.walk() if n.tag == 'img']
        assert [(n.attrs.get('src'), n.attrs.get('alt')) for n in baseline.walk() if n.tag == 'img'] == [
            (n.attrs.get('src'), n.attrs.get('alt')) for n in article.walk() if n.tag == 'img'
        ], f'{filename}: image sources or alt text changed'
        assert any(n.tag == 'img' and n.attrs.get('src') == 'assets/bespoke-labs-logo.svg'
                   for n in page.walk()), f'{filename}: logo not referenced'
        assert (root / 'site/assets/bespoke-labs-logo.svg').is_file(), 'Missing Bespoke Labs logo'
        assert all('open' in n.attrs for n in article.walk() if n.tag == 'details'), f'{filename}: closed prompt'
        figures = [n for n in article.walk() if n.tag == 'figure']
        assert len(figures) == len(images) + len(mermaid), f'{filename}: missing figure wrappers'
        for figure in figures:
            assert 'fig' in figure.attrs.get('class', '').split(), f'{filename}: unstyled figure'
            assert any(n.attrs.get('class') == 'fig-box' for n in figure.children if isinstance(n, Node))
            assert any(n.attrs.get('class') == 'fig-head' for n in figure.children if isinstance(n, Node))
            image = next((n for n in figure.walk() if n.tag == 'img'), None)
            if image:
                assert next(n.text() for n in figure.walk() if n.tag == 'h4') == image.attrs.get('alt', '')
        for src in images:
            parts = urlsplit(src)
            assert not parts.scheme and (root / 'site' / unquote(parts.path)).is_file(), f'{filename}: missing image {src}'
        for n in page.walk():
            if n.tag != 'a':
                continue
            parts = urlsplit(n.attrs.get('href', ''))
            if parts.scheme or parts.netloc:
                continue
            if parts.path:
                assert (root / 'site' / unquote(parts.path)).is_file(), f'{filename}: missing link {parts.path}'
            elif parts.fragment:
                assert unquote(parts.fragment) in ids, f'{filename}: missing anchor {parts.fragment}'
        counts = Counter(n.tag for n in article.walk())
        result = dict(page=output_name(filename), h2=len(expected_h2), h3=counts['h3'], images=len(images),
                      mermaid=len(mermaid), tables=counts['table'], details=counts['details'],
                      code_blocks=len(actual_code), content='exact text/order and structure match')
        results.append(result)
        print(f'PASS {result["page"]}: {result["h2"]} h2, {result["h3"]} h3, {result["images"]} images, '
              f'{result["mermaid"]} Mermaid, {result["tables"]} tables, {result["details"]} details; content preserved')
    for font in re.findall(r"url\('(fonts/[^']+)'\)", CSS):
        assert (root / 'site' / font).is_file(), f'Missing font: {font}'
    for asset in (root / 'assets').glob('*.svg'):
        assert asset.read_bytes() == (root / 'site' / 'assets' / asset.name).read_bytes(), f'Asset changed: {asset}'
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory', nargs='?', default='.', type=Path)
    cli.add_argument('--verify', action='store_true', help='Verify source text, structure, headings, code, diagrams, assets and links.')
    args = cli.parse_args()
    root = args.directory.resolve()
    sources = {name: (root / name).read_text(encoding='utf-8') for name in FILES}
    catalogs = read_catalogs(sources['README.md'])
    site = root / 'site'
    (site / 'assets').mkdir(parents=True, exist_ok=True)
    for source in sorted((root / 'assets').glob('*.svg')):
        shutil.copyfile(source, site / 'assets' / source.name)
    (site / 'site.css').write_text(CSS.strip() + '\n', encoding='utf-8')
    (site / 'site.js').write_text(JS.strip() + '\n', encoding='utf-8')
    for filename, source in sources.items():
        (site / output_name(filename)).write_text(render_page(source, filename, catalogs), encoding='utf-8')
    print(f'Built {len(sources)} pages in {site}')
    if args.verify:
        verify(root, sources)


if __name__ == '__main__':
    main()
