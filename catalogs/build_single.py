"""Bundle the built catalog site (site/*.html) into one self-contained HTML file.

Each page becomes a view inside one document. Hash routing picks the view (#debugging) or an anchor
inside it (#debugging--domain-breakdown). Fonts, plots and the logo are embedded as data URIs and the
Mermaid library is inlined, so the file works offline.

    python build_single.py [path/to/mermaid.min.js]
"""
import base64
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, 'site')
OUT = os.path.join(HERE, 'ots-catalogs.html')
MERMAID = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'vendor', 'mermaid-10.9.1.min.js')
PAGES = ['index', 'programbench', 'system-design', 'debugging', 'feature-implementation',
         'infrastructure-as-code', 'data-engineering', 'migration']
MIME = {'.woff2': 'font/woff2', '.ttf': 'font/ttf', '.svg': 'image/svg+xml'}


def data_uri(path):
    ext = os.path.splitext(path)[1]
    return f'data:{MIME[ext]};base64,' + base64.b64encode(open(path, 'rb').read()).decode()


def view_name(page):
    return 'overview' if page == 'index' else page


def link(href, view):
    """Rewrite an href from page space into the single document's hash space."""
    if href.startswith(('http://', 'https://', 'mailto:', 'data:')):
        return href
    m = re.match(r'^([\w-]+)\.html(?:#(.*))?$', href)
    if m:
        target = view_name(m.group(1))
        return f'#{target}--{m.group(2)}' if m.group(2) else f'#{target}'
    if href.startswith('#'):
        return f'#{view}--{href[1:]}' if href[1:] not in ('', 'top') else f'#{view}'
    return href


def page_view(page):
    src = open(os.path.join(SITE, f'{page}.html'), encoding='utf-8').read()
    view = view_name(page)
    crumb = re.search(r'<div class="crumb">(.*?)</div>', src, re.S)
    body = re.search(r'<main[^>]*>(.*)</main>', src, re.S).group(1)
    body = re.sub(r'\sid="([^"]+)"', lambda m: f' id="{view}--{m.group(1)}"', body)
    body = re.sub(r'\shref="([^"]+)"', lambda m: f' href="{html.escape(link(html.unescape(m.group(1)), view), quote=True)}"', body)
    body = re.sub(r'\ssrc="(assets/[^"]+)"', lambda m: f' src="{data_uri(os.path.join(SITE, m.group(1)))}"', body)
    crumb_html = re.sub(r'\shref="([^"]+)"', lambda m: f' href="{link(m.group(1), view)}"', crumb.group(1)) if crumb else ''
    title = re.search(r'<title>(.*?)</title>', src, re.S).group(1)
    return (f'<section class="view" data-view="{view}" data-title="{html.escape(title, quote=True)}" '
            f'data-crumb="{html.escape(crumb_html, quote=True)}" hidden>{body}</section>')


def main():
    css = open(os.path.join(SITE, 'site.css'), encoding='utf-8').read()
    css = re.sub(r"url\('fonts/([^']+)'\)", lambda m: f"url('{data_uri(os.path.join(SITE, 'fonts', m.group(1)))}')", css)
    css += '.view[hidden]{display:none!important}'
    js = open(os.path.join(SITE, 'site.js'), encoding='utf-8').read()
    # Scroll-spy must follow the visible view; the router calls refreshToc() after every switch.
    js = js.replace("const headings = Array.from(document.querySelectorAll('article h2, article h3'));\n"
                    "const tocLinks = Array.from(document.querySelectorAll('.toc-links a'));",
                    "let headings = [], tocLinks = [];\n"
                    "function refreshToc() { const v = document.querySelector('.view:not([hidden])');"
                    " headings = v ? Array.from(v.querySelectorAll('article h2, article h3')) : [];"
                    " tocLinks = v ? Array.from(v.querySelectorAll('.toc-links a')) : []; scheduleToc(); }")
    js = js.replace("updateToc();\n", "", 1)
    # Mermaid is inlined, so render directly instead of loading it from the CDN.
    js = re.sub(r"if \(diagrams\.length\) \{\n  const script = .*?\n\}\n?$", "if (diagrams.length) renderDiagrams();\n", js, flags=re.S)
    router = """
function route() {
  const raw = decodeURIComponent(location.hash.slice(1));
  const [name, anchor] = raw.includes('--') ? [raw.split('--')[0], raw] : [raw || 'overview', null];
  const views = Array.from(document.querySelectorAll('.view'));
  const target = views.find(v => v.dataset.view === name) || views[0];
  views.forEach(v => { v.hidden = v !== target; });
  document.title = target.dataset.title;
  document.querySelector('.band .crumb').innerHTML = target.dataset.crumb;
  refreshToc();
  const el = anchor && document.getElementById(anchor);
  if (el) el.scrollIntoView(); else window.scrollTo(0, 0);
}
addEventListener('hashchange', route);
route();
"""
    views = '\n'.join(page_view(p) for p in PAGES)
    needs_mermaid = 'data-mermaid' in views
    mermaid = open(MERMAID, encoding='utf-8').read().replace('</script', '<\\/script') if needs_mermaid else ''
    band = re.search(r'<header class="band">.*?</header>', open(os.path.join(SITE, 'index.html'), encoding='utf-8').read(), re.S).group(0)
    band = band.replace('href="index.html"', 'href="#overview"')
    band = re.sub(r'src="(assets/[^"]+)"', lambda m: f'src="{data_uri(os.path.join(SITE, m.group(1)))}"', band)
    band = re.sub(r'<div class="crumb">.*?</div>', '<div class="crumb"></div>', band, flags=re.S)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>OTS task catalogs | Bespoke Labs</title><link rel="icon" href="data:,">
<style>{css}</style></head>
<body id="top"><a class="skip" href="#overview">Skip to content</a>
{band}
<main id="content" tabindex="-1">
{views}
</main>
{'<script>' + mermaid + '</script>' if mermaid else ''}
<script>{js}
{router}</script>
</body></html>
"""
    open(OUT, 'w', encoding='utf-8').write(doc)
    print(f'wrote {OUT} ({len(doc) / 1e6:.1f} MB, {len(PAGES)} views)')


if __name__ == '__main__':
    main()
