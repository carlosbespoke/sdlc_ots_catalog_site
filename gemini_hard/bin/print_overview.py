# Overview page as a PDF (catalog/gemini-hard-overview.pdf): prints catalog/site/index.html with headless Chrome, adding
# print-only styles to a temporary copy (the site itself is unchanged): A4, no sort arrows or interactive-figure hints,
# no repeated table totals, page breaks before "Pass rates by catalog" and "Turn counts", and only the Google Drive
# download links kept (links to the catalog pages would point at local files).
import os, subprocess, tempfile
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); SITE = f'{H}/catalog/site'; OUT = f'{H}/catalog/gemini-hard-overview.pdf'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
CSS = """<style media="print">
@page{size:A4;margin:14mm 13mm}
html,body{background:#fff!important}
.sort-button::after{content:''!important}
.lab,.cx-hint,.cx-hint-inline,.cx-toolbar,.cx-slider,.cx-filter,.cx-clearall,.cx-expand,.back-top,.skip,.page-nav,.catalog-nav,.toc-links,.contents{display:none!important}
.page-footer,.band,footer{display:none!important}
body,.page{min-height:0!important}
tfoot{display:table-row-group}
tr,.kpis,.kpi,.cx,figure,img,svg{break-inside:avoid}
h1,h2,h3,h4,.fig-head{break-after:avoid}
h2.pb{break-before:page}
a.nolink{text-decoration:none!important;border:0!important;box-shadow:none!important;background:none!important;color:inherit!important;pointer-events:none}
table.overview-cat td:nth-child(3){min-width:230px}
table.overview-cat th:nth-child(5),table.overview-cat th:nth-child(6){min-width:90px}
</style>
<script>
window.addEventListener('load',function(){setTimeout(function(){
  document.querySelectorAll('h2').forEach(function(e){if(/^(Pass rates by catalog|Turn counts)/.test(e.textContent.trim()))e.classList.add('pb');});
  document.querySelectorAll('a[href]').forEach(function(a){var u=a.getAttribute('href');if(!/^https?:/.test(u)){a.removeAttribute('href');a.classList.add('nolink');}});
  var t=document.querySelector('table.data'); if(t) t.classList.add('overview-cat');
  var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;
  while((n=w.nextNode())){ if(/Click a bar to break it down\\./.test(n.nodeValue)) n.nodeValue=n.nodeValue.replace(/\\.?\\s*Click a bar to break it down\\./,'.'); }
},1500);});
</script>"""
SAMPLES_OLD = "Click its task id to download it, or a main sample's example to read its prompt and environment diagram on its catalog page."
SAMPLES_NEW = "Click its task id or the download button to download it. Each main sample's prompt and environment diagram are on its catalog page in the full report."
h = open(f'{SITE}/index.html').read()
assert SAMPLES_OLD in h, 'the samples sentence changed; update SAMPLES_OLD'
h = h.replace('<head>', f'<head><base href="file://{SITE}/">', 1).replace('</head>', CSS + '</head>', 1).replace(SAMPLES_OLD, SAMPLES_NEW)
with tempfile.TemporaryDirectory() as d:
    src = f'{d}/overview_print.html'; open(src, 'w').write(h)
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--virtual-time-budget=20000',
                    '--run-all-compositor-stages-before-draw', f'--print-to-pdf={OUT}', f'file://{src}'], check=True, capture_output=True)
print('wrote', OUT, os.path.getsize(OUT), 'bytes')
