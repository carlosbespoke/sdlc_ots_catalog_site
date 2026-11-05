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
    if (!button) return;
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
