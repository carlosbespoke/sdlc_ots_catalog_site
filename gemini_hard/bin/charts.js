// Interactive charts for the Gemini-hard catalog site, ported from ../ots_all/bin/charts.js with pass rate in place of average reward:
// bar counts are of the selected tasks (the pages' headline task counts are estimates); each run is 1 (passed) or 0, a task's value is its share of passed runs, and a model's rate pools runs across tasks, as in the tables.
// Interactive charts for the catalog site. Each page carries one JSON data block; charts on a page share a store,
// so a click in one chart can filter the others. No element ids are used (the single-file build prefixes them),
// everything is found through data attributes inside the page's own view.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var fmt = function (n) { return Math.round(n).toLocaleString('en-US'); };
  var half = function (r) { var f = Math.floor(r), d = r - f; return Math.abs(d - 0.5) < 1e-9 ? (f % 2 ? f + 1 : f) : Math.round(r); };  // round half to even, like the tables
  var pc = function (v) { return v === null || isNaN(v) ? 'n/a' : (v > 0 && v < 0.005 ? '<1%' : half(100 * v) + '%'); };
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, parent, html) {
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  function pool(pts) { var p = 0, n = 0; pts.forEach(function (x) { x.runs.forEach(function (v) { p += v; n++; }); }); return n ? p / n : NaN; }
  function passes(s) { var p = s.filter(function (v) { return v >= 1; }).length; return p + ' of ' + s.length + ' run' + (s.length > 1 ? 's' : '') + ' passed'; }
  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : NaN; }
  function quant(s, q) { if (!s.length) return NaN; var p = (s.length - 1) * q, lo = Math.floor(p), hi = Math.ceil(p); return s[lo] + (s[hi] - s[lo]) * (p - lo); }
  function svgX(svg, clientX) { var p = svg.createSVGPoint(); p.x = clientX; p.y = 0; return p.matrixTransform(svg.getScreenCTM().inverse()).x; }
  function jitter(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x) - 0.5; }
  function chips(parent, items, onToggle) {  // items: [{label, note, on}]
    var wrap = h('div', 'cx-chips', parent);
    items.forEach(function (it, i) {
      var b = h('button', 'cx-chip', wrap, '<span class="cx-dot"></span>' + esc(it.label) + (it.note ? ' <span class="cx-n">' + esc(it.note) + '</span>' : ''));
      b.type = 'button'; b.setAttribute('aria-pressed', String(it.on));
      b.addEventListener('click', function () { if (onToggle(i)) b.setAttribute('aria-pressed', String(items[i].on)); });
    });
    return wrap;
  }
  function tip(box) {
    var t = h('div', 'cx-tip', box); t.hidden = true;
    return {
      show: function (html, ev) {
        t.innerHTML = html; t.hidden = false;
        var r = box.getBoundingClientRect(), x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
        if (x + t.offsetWidth > r.width) x = Math.max(0, ev.clientX - r.left - t.offsetWidth - 10);
        t.style.left = x + 'px'; t.style.top = y + 'px';
      },
      hide: function () { t.hidden = true; }
    };
  }
  // ---- store: tasks, cross-filters and subscribers, one per page ----
  function makeStore(D) {
    var S = { D: D, tasks: D.tasks, filters: {}, order: [], subs: [] };
    S.visible = function (except) {
      var keys = S.order.filter(function (k) { return S.filters[k] && (except || []).indexOf(k) < 0; }), out = [];
      for (var i = 0; i < S.tasks.length; i++) {
        var ok = true;
        for (var j = 0; j < keys.length && ok; j++) ok = S.filters[keys[j]].test(i);
        if (ok) out.push(i);
      }
      return out;
    };
    S.set = function (key, f) {
      if (f) { S.filters[key] = f; if (S.order.indexOf(key) < 0) S.order.push(key); }
      else { delete S.filters[key]; S.order = S.order.filter(function (k) { return k !== key; }); }
      S.subs.forEach(function (fn) { fn(); });
    };
    S.strip = function (parent) {  // the active filters, shown at the top of every chart on the page
      var s = h('div', 'cx-strip', parent);
      S.subs.push(function () {
        clear(s); var keys = S.order.filter(function (k) { return S.filters[k]; }); s.hidden = !keys.length;
        if (!keys.length) return;
        h('span', 'cx-strip-lab', s, 'Showing');
        keys.forEach(function (k) {
          var b = h('button', 'cx-filter', s, esc(S.filters[k].label) + ' <span aria-hidden="true">&times;</span>'); b.type = 'button';
          b.title = 'Remove this filter'; b.addEventListener('click', function () { S.set(k, null); });
        });
        if (keys.length > 1) { var a = h('button', 'cx-clearall', s, 'Clear all'); a.type = 'button'; a.addEventListener('click', function () { S.order.slice().forEach(function (k) { delete S.filters[k]; }); S.order = []; S.subs.forEach(function (fn) { fn(); }); }); }
      });
      return s;
    };
    return S;
  }
  // ---- bar panels (domain with sub-domains; language; seniority) ----
  function bars(fig, S) {
    var box = fig.querySelector('[data-body]'), specs = fig.dataset.dims.split(','), mode = 'pct', open = {};
    if (S.D.cross) S.strip(box);
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    [['pct', '% of tasks'], ['n', 'Tasks']].forEach(function (m) {
      var b = h('button', '', seg, m[1]); b.type = 'button'; b.setAttribute('aria-pressed', String(mode === m[0]));
      b.addEventListener('click', function () { mode = m[0]; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); });
    });
    h('span', 'cx-hint-inline', bar, fig.dataset.hint || 'Click a bar to filter the charts on this page.');
    var panels = h('div', 'cx-panels', box);
    var P = specs.map(function (sp) {
      var m = sp.match(/^(\w)(?:>(\w))?(?::(\d+))?(?:=(.*))?$/);
      var p = { key: m[1], child: m[2], top: m[3] ? +m[3] : 0, title: m[4] || '', el: h('div', 'cx-panel', panels) };
      var all = {}; S.tasks.forEach(function (t) { all[t[p.key]] = (all[t[p.key]] || 0) + 1; });
      p.order = Object.keys(all).map(Number).sort(function (a, b) { return all[b] - all[a]; });
      if (p.top && p.order.length > p.top + 1) { p.rest = p.order.slice(p.top); p.order = p.order.slice(0, p.top).concat(['rest']); }
      return p;
    });
    function row(parent, p, label, n, tot, max, active, onClick, cls, toggle) {
      var r = h('div', 'cx-bar' + (active ? ' is-on' : '') + (cls ? ' ' + cls : ''), parent), v = mode === 'pct' ? (tot ? n / tot : 0) : n;
      var lab = h('span', 'cx-bar-lab', r);
      if (toggle) { var t = h('button', 'cx-expand', lab, toggle.open ? '&#9662;' : '&#9656;'); t.type = 'button'; t.title = toggle.open ? 'Hide sub-domains' : 'Show sub-domains'; t.addEventListener('click', function (e) { e.stopPropagation(); toggle.fn(); }); }
      h('span', '', lab, esc(label));
      var tr = h('span', 'cx-bar-track', r); h('span', 'cx-bar-fill', tr).style.width = (max ? 100 * v / max : 0) + '%';
      h('span', 'cx-bar-val', r, mode === 'pct' ? (tot ? (100 * n / tot).toFixed(n && 100 * n / tot < 10 ? 1 : 0) + '%' : 'n/a') : fmt(n));
      r.tabIndex = 0; r.setAttribute('role', 'button'); r.setAttribute('aria-pressed', String(!!active));
      r.addEventListener('click', onClick); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } });
      return v;
    }
    function draw() {
      P.forEach(function (p) {
        clear(p.el); if (p.title) h('div', 'cx-panel-title', p.el, esc(p.title));
        var V = S.visible([p.key, p.child].filter(Boolean)), cnt = {}, sub = {};
        V.forEach(function (i) { var t = S.tasks[i]; cnt[t[p.key]] = (cnt[t[p.key]] || 0) + 1; if (p.child) { var k = t[p.key] + ':' + t[p.child]; sub[k] = (sub[k] || 0) + 1; } });
        var val = function (k) { return k === 'rest' ? p.rest.reduce(function (a, r) { return a + (cnt[r] || 0); }, 0) : (cnt[k] || 0); };
        var tot = V.length, max = 0;
        p.order.forEach(function (k) { var n = val(k); max = Math.max(max, mode === 'pct' ? (tot ? n / tot : 0) : n); });
        var names = S.D.dims[p.key], F = S.filters[p.key];
        p.order.forEach(function (k) {
          var label = k === 'rest' ? 'Other (' + p.rest.length + ' languages)' : names[k], active = F && F.v === String(k);
          var click = function () {
            if (active) { S.set(p.key, null); return; }
            if (p.child) S.set(p.child, null);
            S.set(p.key, { v: String(k), label: (p.title || 'Domain') + ': ' + label, test: k === 'rest' ? function (i) { return p.rest.indexOf(S.tasks[i][p.key]) >= 0; } : function (i) { return S.tasks[i][p.key] === k; } });
          };
          row(p.el, p, label, val(k), tot, max, active, click, '', p.child ? { open: !!open[k], fn: function () { open[k] = !open[k]; draw(); } } : null);
          if (p.child && open[k]) {
            var kids = Object.keys(sub).filter(function (s) { return s.split(':')[0] === String(k); }).map(function (s) { return +s.split(':')[1]; })
              .sort(function (a, b) { return sub[k + ':' + b] - sub[k + ':' + a]; });
            kids.forEach(function (c) {
              var CF = S.filters[p.child], on = CF && CF.v === String(c);
              row(p.el, p, S.D.dims[p.child][c], sub[k + ':' + c], tot, max, on, function () {
                if (on) { S.set(p.child, null); return; }
                S.set(p.child, { v: String(c), label: 'Sub-domain: ' + S.D.dims[p.child][c], test: function (i) { return S.tasks[i][p.child] === c; } });
              }, 'is-child');
            });
          }
        });
        h('div', 'cx-panel-foot', p.el, fmt(tot) + ' selected tasks' + (tot < S.tasks.length ? ' after filters' : ''));
      });
    }
    S.subs.push(draw);
  }
  // ---- turns per task histogram ----
  function turns(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, H = 330, L = 52, R = 18, T = 34, B = 44, BIN = D.bin, XMAX = D.xmax;
    var models = D.models.map(function (m, i) { var n = 0; S.tasks.forEach(function (t) { if (t.t[i]) n++; }); return { label: m, note: fmt(n) + ' tasks', on: n > 0, n: n }; }).filter(function (m) { return m.n; });
    var sel = function (name) { return models.some(function (m) { return m.on && m.label === name; }); };
    var thr = D.threshold, pick = null, gname = fig.dataset.group || 'Domain';
    if (D.cross) S.strip(box);
    chips(box, models, function (i) { if (models[i].on && models.filter(function (m) { return m.on; }).length === 1) return false; models[i].on = !models[i].on; pick = null; if (S.filters.turns) S.set('turns', null); else draw(); return true; });
    var sum = h('p', 'cx-summary', box), svg = el('svg', { 'class': 'cx-svg', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Histogram of average turns per task' }, box);
    h('p', 'cx-hint', box, 'Toggle models to recompute each task from their runs only. Drag the red line to move the long-horizon threshold. Click a bar to break it down by ' + gname.toLowerCase() + (D.cross ? ' and filter the other charts' : '') + '.');
    var panel = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v / XMAX; };
    var gS = el('g', {}, svg), gGrid = el('g', {}, svg), gBars = el('g', {}, svg), gL = el('g', {}, svg);
    var wash = el('rect', { y: T, height: H - T - B, fill: 'var(--red)', 'fill-opacity': 0.07 }, gS);
    for (var v = 0; v <= XMAX; v += 100) el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gS, fmt(v));
    el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: 'var(--ink)' }, gS);
    el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gS, 'Average turns per task');
    el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', 'class': 'cx-axis', transform: 'rotate(-90 14 ' + (T + H - B) / 2 + ')' }, gS, 'Tasks');
    var mLine = el('line', { y1: T, y2: H - B, stroke: 'var(--ink)', 'stroke-width': 1.2, 'stroke-dasharray': '4 4' }, gL), mText = el('text', { y: T + 14, 'class': 'cx-mean' }, gL);
    var hg = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': 'Long-horizon threshold in turns', 'aria-valuemin': 0, 'aria-valuemax': XMAX }, gL);
    var hHit = el('rect', { y: T - 20, height: H - B - T + 20, width: 24, fill: 'transparent' }, hg), hLine = el('line', { y1: T - 6, y2: H - B, stroke: 'var(--red)', 'stroke-width': 2 }, hg);
    var hKnob = el('circle', { cy: T - 6, r: 7, fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 2 }, hg), hText = el('text', { y: T - 18, 'class': 'cx-thr' }, hg);
    function means(V) {
      var out = [];
      V.forEach(function (i) { var tk = S.tasks[i], s = 0, n = 0; for (var m in tk.t) if (sel(D.models[m])) { s += tk.t[m][0]; n += tk.t[m][1]; } if (n) out.push([i, s / n]); });
      return out;
    }
    function draw() {
      var M = means(S.visible(['turns'])), nb = Math.ceil(XMAX / BIN), bins = [];
      for (var i = 0; i < nb; i++) bins.push([]);
      M.forEach(function (m) { bins[Math.min(nb - 1, Math.floor(m[1] / BIN))].push(m[0]); });
      var top = Math.max.apply(null, bins.map(function (b) { return b.length; })) || 1, step = top > 200 ? 50 : top > 80 ? 20 : top > 30 ? 10 : top > 12 ? 5 : top > 5 ? 2 : 1;
      top = Math.ceil(top / step) * step;
      var y = function (n) { return H - B - (H - B - T) * n / top; };
      clear(gGrid); clear(gBars);
      for (var g = 0; g <= top; g += step) { el('line', { x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: 'var(--line-2)' }, gGrid); el('text', { x: L - 8, y: y(g) + 4, 'text-anchor': 'end', 'class': 'cx-tick' }, gGrid, fmt(g)); }
      var F = S.filters.turns; if (D.cross && !F) pick = null;
      bins.forEach(function (b, i) {
        var lo = i * BIN, on = pick === i, r = el('rect', { x: x(lo) + 1, width: x(lo + BIN) - x(lo) - 2, y: y(b.length), height: Math.max(0, H - B - y(b.length)), 'class': 'cx-col' + (on ? ' is-on' : ''), tabindex: b.length ? 0 : -1, role: 'button' }, gBars);
        var go = function () {
          if (!b.length) return; pick = on ? null : i;
          if (D.cross) { var set = {}; b.forEach(function (k) { set[k] = 1; }); S.set('turns', pick === null ? null : { label: 'Turns: ' + fmt(lo) + '-' + fmt(lo + BIN - 1), test: function (k) { return !!set[k]; } }); } else draw();
        };
        r.addEventListener('click', go); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
        r.addEventListener('mousemove', function (e) { t.show('<b>' + fmt(lo) + '-' + fmt(lo + BIN - 1) + ' turns</b><br>' + fmt(b.length) + ' tasks (' + pc(M.length ? b.length / M.length : 0) + ')', e); });
        r.addEventListener('mouseleave', t.hide);
      });
      var mu = mean(M.map(function (m) { return m[1]; })) || 0, tx = x(thr);
      mLine.setAttribute('x1', x(mu)); mLine.setAttribute('x2', x(mu));
      var left = x(mu) > tx - 90 && x(mu) < tx; mText.setAttribute('x', left ? x(mu) - 6 : x(mu) + 6); mText.setAttribute('text-anchor', left ? 'end' : 'start'); mText.textContent = 'mean ' + fmt(mu);
      wash.setAttribute('x', tx); wash.setAttribute('width', Math.max(0, W - R - tx));
      hHit.setAttribute('x', tx - 12); hLine.setAttribute('x1', tx); hLine.setAttribute('x2', tx); hKnob.setAttribute('cx', tx);
      var flip = tx > W - R - 190; hText.setAttribute('x', flip ? tx - 12 : tx + 12); hText.setAttribute('text-anchor', flip ? 'end' : 'start'); hText.textContent = 'long horizon, ' + fmt(thr) + '+ turns';
      hg.setAttribute('aria-valuenow', thr);
      var long = M.filter(function (m) { return m[1] >= thr; });
      sum.innerHTML = '<strong>' + fmt(long.length) + '</strong> of ' + fmt(M.length) + ' tasks (' + pc(M.length ? long.length / M.length : 0) + ') average ' + fmt(thr) + ' turns or more. Mean ' + fmt(mu) + ' turns per task.';
      // breakdown table: long-horizon tasks by group, or the picked bar's tasks by group
      var names = D.dims.g, rows, cap, head;
      var byG = function (list) { var c = {}; list.forEach(function (k) { var gg = S.tasks[k].g; c[gg] = (c[gg] || 0) + 1; }); return c; };
      var allC = byG(M.map(function (m) { return m[0]; }));
      var order = Object.keys(allC).map(Number).sort(function (a, b) { return allC[b] - allC[a]; });
      if (pick === null) {
        cap = 'Long-horizon tasks (' + fmt(thr) + '+ turns) by ' + gname.toLowerCase(); head = [gname, 'Long-horizon tasks', 'Tasks with runs', 'Share'];
        var lc = byG(long.map(function (m) { return m[0]; }));
        rows = order.map(function (gg) { return [names[gg], lc[gg] || 0, allC[gg], (lc[gg] || 0) / allC[gg]]; });
      } else {
        var bc = byG(bins[pick]); cap = 'Tasks averaging ' + fmt(pick * BIN) + '-' + fmt(pick * BIN + BIN - 1) + ' turns, by ' + gname.toLowerCase(); head = [gname, 'Tasks in this bar', 'Tasks with runs', 'Share of bar'];
        rows = order.map(function (gg) { return [names[gg], bc[gg] || 0, allC[gg], bins[pick].length ? (bc[gg] || 0) / bins[pick].length : 0]; });
      }
      clear(panel); grid(panel, cap + (pick === null ? '. Click a bar to break it down.' : '.'), head, rows, pick === null ? null : function () { pick = null; if (D.cross) S.set('turns', null); else draw(); });
    }
    var drag = false;
    hg.addEventListener('pointerdown', function (e) { drag = true; hg.setPointerCapture(e.pointerId); e.preventDefault(); });
    hg.addEventListener('pointermove', function (e) { if (!drag) return; var v = Math.max(0, Math.min(XMAX, Math.round((svgX(svg, e.clientX) - L) / (W - L - R) * XMAX / 10) * 10)); if (v !== thr) { thr = v; draw(); } });
    hg.addEventListener('pointerup', function () { drag = false; });
    hg.addEventListener('keydown', function (e) { var d = { ArrowLeft: -10, ArrowDown: -10, ArrowRight: 10, ArrowUp: 10, PageDown: -100, PageUp: 100 }[e.key]; if (d) { e.preventDefault(); thr = Math.max(0, Math.min(XMAX, thr + d)); draw(); } });
    S.subs.push(draw);
  }
  function grid(parent, cap, head, rows, back) {  // a small table drawn with divs, with a share meter in the last column
    var c = h('p', 'cx-cap', parent, esc(cap));
    if (back) { var b = h('button', 'cx-link', c, 'Back to the long-horizon view'); b.type = 'button'; b.addEventListener('click', back); }
    var g = h('div', 'cx-grid', parent); g.setAttribute('role', 'table');
    var hr = h('div', 'cx-row cx-head', g); hr.setAttribute('role', 'row'); head.forEach(function (x) { h('span', '', hr, esc(x)).setAttribute('role', 'columnheader'); });
    rows.forEach(function (r) {
      var rr = h('div', 'cx-row', g); rr.setAttribute('role', 'row');
      h('span', '', rr, esc(r[0])); h('span', '', rr, fmt(r[1])); h('span', '', rr, fmt(r[2]));
      h('span', '', rr, '<span class="cx-meter"><span style="width:' + (100 * r[3]).toFixed(1) + '%"></span></span>' + Math.round(100 * r[3]) + '%');
      rr.querySelectorAll(':scope > span').forEach(function (s) { s.setAttribute('role', 'cell'); });
    });
  }
  // ---- per-task pass rate by model: box plot with one dot per task ----
  function reward(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, L = 210, R = 24, T = 40, B = 44, ROW = 58;
    var lo = 0.2, hi = 0.8, same = false, focus = null;
    var stats = D.models.map(function (m, k) {
      var pt = []; S.tasks.forEach(function (t) { var s = t.r[k]; if (s && s.length) pt.push(mean(s)); });
      return { k: k, n: pt.length, full: pt.filter(function (v) { return v >= 1; }).length };
    }).filter(function (s) { return s.n; });
    var items = stats.map(function (s) {
      var sat = s.full / s.n >= D.sat, few = s.n < D.minTasks;
      return { k: s.k, label: D.models[s.k], note: fmt(s.n) + ' tasks' + (sat ? ', saturated' : few ? ', few tasks' : ''), on: !sat && !few };
    });
    if (!items.some(function (i) { return i.on; }) && items.length) items[0].on = true;
    if (D.cross) S.strip(box);
    chips(box, items, function (i) { if (items[i].on && items.filter(function (x) { return x.on; }).length === 1) return false; items[i].on = !items[i].on; draw(); return true; });
    var opts = h('label', 'cx-check', box, '<input type="checkbox"> Same tasks only: keep the tasks every selected model ran');
    opts.querySelector('input').addEventListener('change', function (e) { same = e.target.checked; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Per-task pass rate by model' }, box);
    h('p', 'cx-hint', box, 'Each dot is one task: the share of a model\'s graded runs on it that passed. Boxes span the middle half of tasks, the line is the median and the diamond the model\'s pass rate over all its runs. Drag the edges of the shaded band to change it. Hover a dot for its runs; click it for the task.');
    var detail = h('div', 'cx-detail', box), summary = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v; };
    var gBand = el('rect', { y: T - 10, fill: 'var(--teal)', 'fill-opacity': 0.09 }, svg), gC = el('g', {}, svg), lastH = T + ROW + B, H0;
    var hd = ['lo', 'hi'].map(function (which) {
      var g = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': which === 'lo' ? 'Lower edge of the band' : 'Upper edge of the band' }, svg);
      var o = { which: which, g: g, hit: el('rect', { y: T - 26, width: 20, fill: 'transparent' }, g), line: el('line', { y1: T - 16, stroke: 'var(--teal)', 'stroke-width': 2 }, g),
        knob: el('circle', { cy: T - 16, r: 6.5, fill: 'var(--teal)', stroke: 'var(--paper)', 'stroke-width': 2 }, g), lab: el('text', { y: T - 27, 'text-anchor': 'middle', 'class': 'cx-band' }, g) };
      var setv = function (v) { v = Math.round(v * 20) / 20; if (which === 'lo') lo = Math.max(0, Math.min(v, hi - 0.05)); else hi = Math.min(1, Math.max(v, lo + 0.05)); };
      var dragging = false;
      g.addEventListener('pointerdown', function (ev) { dragging = true; g.setPointerCapture(ev.pointerId); ev.preventDefault(); });
      g.addEventListener('pointermove', function (ev) { if (!dragging) return; var old = lo + ':' + hi; setv((svgX(svg, ev.clientX) - L) / (W - L - R)); if (old !== lo + ':' + hi) { place(); tally(); } });
      g.addEventListener('pointerup', function () { dragging = false; });
      g.addEventListener('keydown', function (ev) { var d = { ArrowLeft: -0.05, ArrowDown: -0.05, ArrowRight: 0.05, ArrowUp: 0.05 }[ev.key]; if (d) { ev.preventDefault(); setv((which === 'lo' ? lo : hi) + d); place(); tally(); } });
      return o;
    });
    function place() {  // band and handles follow lo, hi and the chart height
      gBand.setAttribute('x', x(lo)); gBand.setAttribute('width', x(hi) - x(lo)); gBand.setAttribute('height', lastH - T - B + 10);
      hd.forEach(function (o) {
        var v = o.which === 'lo' ? lo : hi;
        o.hit.setAttribute('x', x(v) - 10); o.hit.setAttribute('height', lastH - B - T + 26);
        o.line.setAttribute('x1', x(v)); o.line.setAttribute('x2', x(v)); o.line.setAttribute('y2', lastH - B); o.knob.setAttribute('cx', x(v));
        o.lab.setAttribute('x', x(v)); o.lab.textContent = Math.round(100 * v) + '%'; o.g.setAttribute('aria-valuenow', Math.round(100 * v));
      });
    }
    var lastRows = [];
    function draw() {
      var V = S.visible([]), on = items.filter(function (i) { return i.on; });
      if (same) V = V.filter(function (i) { return on.every(function (m) { var s = S.tasks[i].r[m.k]; return s && s.length; }); });
      var rows = on.map(function (m) {
        var pts = []; V.forEach(function (i) { var s = S.tasks[i].r[m.k]; if (s && s.length) pts.push({ i: i, v: mean(s), runs: s }); });
        var vs = pts.map(function (p) { return p.v; }).sort(function (a, b) { return a - b; });
        return { m: m, pts: pts, vs: vs, q1: quant(vs, 0.25), q2: quant(vs, 0.5), q3: quant(vs, 0.75), mu: pool(pts) };
      }).filter(function (r) { return r.pts.length; });
      rows.sort(function (a, b) { return (b.q3 - a.q3) || (b.q2 - a.q2) || (b.mu - a.mu); });
      var H = T + Math.max(1, rows.length) * ROW + B; svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(gC); lastH = H; place();
      for (var v = 0; v <= 1.0001; v += 0.1) { el('line', { x1: x(v), x2: x(v), y1: T - 10, y2: H - B, stroke: 'var(--line-2)' }, gC); el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gC, Math.round(100 * v) + '%'); }
      el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'Per-task pass rate');
      if (!rows.length) el('text', { x: (L + W - R) / 2, y: T + 30, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'No graded runs for the selected models and filters');
      rows.forEach(function (r, j) {
        var cy = T + j * ROW + ROW / 2, g = el('g', {}, gC);
        el('text', { x: L - 14, y: cy - 2, 'text-anchor': 'end', 'class': 'cx-rowlab' }, g, r.m.label);
        el('text', { x: L - 14, y: cy + 14, 'text-anchor': 'end', 'class': 'cx-tick' }, g, fmt(r.pts.length) + ' tasks, pass rate ' + pc(r.mu));
        var iqr = r.q3 - r.q1, wl = Math.max(r.vs[0], r.q1 - 1.5 * iqr), wh = Math.min(r.vs[r.vs.length - 1], r.q3 + 1.5 * iqr);
        el('line', { x1: x(wl), x2: x(r.q1), y1: cy, y2: cy, stroke: 'var(--ink)' }, g); el('line', { x1: x(r.q3), x2: x(wh), y1: cy, y2: cy, stroke: 'var(--ink)' }, g);
        el('rect', { x: x(r.q1), width: Math.max(1, x(r.q3) - x(r.q1)), y: cy - 14, height: 28, fill: 'var(--card)', stroke: 'var(--ink)' }, g);
        el('line', { x1: x(r.q2), x2: x(r.q2), y1: cy - 14, y2: cy + 14, stroke: 'var(--ink)', 'stroke-width': 2 }, g);
        r.pts.forEach(function (p) {
          var c = el('circle', { cx: x(p.v), cy: cy + jitter(p.i * 7 + r.m.k) * 26, r: focus === p.i ? 5 : 3.2, 'class': 'cx-pt' + (focus === p.i ? ' is-on' : '') }, g);
          c.addEventListener('mousemove', function (e) { t.show('<b>' + esc(r.m.label) + '</b><br>' + passes(p.runs) + '<br>Task pass rate ' + pc(p.v), e); });
          c.addEventListener('mouseleave', t.hide);
          c.addEventListener('click', function () { focus = focus === p.i ? null : p.i; draw(); });
        });
        el('path', { d: 'M' + x(r.mu) + ' ' + (cy - 7) + 'l6 7l-6 7l-6 -7z', fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 1.5 }, g);
      });
      lastRows = rows; tally();
      clear(detail); detail.hidden = focus === null;
      if (focus !== null) {
        var tk = S.tasks[focus], tu = 0, tn = 0; for (var m in tk.t) { tu += tk.t[m][0]; tn += tk.t[m][1]; }
        var parts = ['<b>Selected task</b>', 'Domain: ' + esc(D.dims.g[tk.g]), 'Sub-domain: ' + esc(D.dims.c[tk.c]), 'Language: ' + esc(D.dims.l[tk.l]), 'Seniority: ' + esc(D.dims.s[tk.s]), tn ? 'Average turns: ' + fmt(tu / tn) + ' over ' + tn + ' completed runs' : 'No completed runs with a turn count'];
        D.models.forEach(function (name, k) { var s = tk.r[k]; if (s && s.length) parts.push(esc(name) + ': ' + passes(s) + ' (' + pc(mean(s)) + ')'); });
        detail.innerHTML = parts.join('<br>');
        var x0 = h('button', 'cx-link', detail, 'Close'); x0.type = 'button'; x0.addEventListener('click', function () { focus = null; draw(); });
      }
    }
    function tally() {  // the table under the chart, recomputed for the band
      var rows = lastRows; clear(summary);
      var cap = h('p', 'cx-cap', summary, 'Tasks by per-task pass rate, with the band at ' + Math.round(100 * lo) + '-' + Math.round(100 * hi) + '%');
      var gtab = h('div', 'cx-grid cx-grid5', summary); gtab.setAttribute('role', 'table');
      var hr = h('div', 'cx-row cx-head', gtab); ['Model', 'Tasks', 'Pass rate', 'Tasks at 0%', 'In the band', 'Tasks at 100%'].forEach(function (s) { h('span', '', hr, s); });
      rows.forEach(function (r) {
        var n = r.vs.length, z = r.vs.filter(function (v) { return v === 0; }).length, f = r.vs.filter(function (v) { return v >= 1; }).length, b = r.vs.filter(function (v) { return v >= lo - 1e-9 && v <= hi + 1e-9; }).length;
        var rr = h('div', 'cx-row', gtab); h('span', '', rr, esc(r.m.label)); h('span', '', rr, fmt(n)); h('span', '', rr, pc(r.mu)); h('span', '', rr, pc(z / n)); h('span', '', rr, pc(b / n)); h('span', '', rr, pc(f / n));
      });
    }
    S.subs.push(draw);
  }
  // ---- overview heatmap: models by catalogs ----
  function heat(fig, S) {
    var D = S.D.heat, box = fig.querySelector('[data-body]'), metric = 'reward', minT = D.minTasks, pick = null;
    var M = {
      reward: { label: 'Pass rate', f: function (c) { return c.passed / c.graded; }, txt: pc },
      t0: { label: 'Tasks at 0%', f: function (c) { return c.pt.filter(function (v) { return v === 0; }).length / c.pt.length; }, txt: pc },
      band: { label: 'Tasks at 20-80%', f: function (c) { return c.pt.filter(function (v) { return v >= 0.2 && v <= 0.8; }).length / c.pt.length; }, txt: pc },
      t100: { label: 'Tasks at 100%', f: function (c) { return c.pt.filter(function (v) { return v >= 1; }).length / c.pt.length; }, txt: pc },
      runs: { label: 'Graded runs', f: function (c) { return c.graded; }, txt: fmt }
    };
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    Object.keys(M).forEach(function (k) { var b = h('button', '', seg, M[k].label); b.type = 'button'; b.setAttribute('aria-pressed', String(k === metric)); b.addEventListener('click', function () { metric = k; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); }); });
    var sl = h('label', 'cx-slider', bar, 'Hide cells with fewer than <input type="range" min="1" max="20" value="' + minT + '"> <b>' + minT + '</b> tasks');
    sl.querySelector('input').addEventListener('input', function (e) { minT = +e.target.value; sl.querySelector('b').textContent = minT; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Heatmap of models by catalog' }, box);
    h('p', 'cx-hint', box, 'Hover a cell for its numbers; click it for the spread of per-task pass rates.');
    var detail = h('div', 'cx-detail', box), t = tip(box); detail.hidden = true;
    var links = fig.querySelectorAll('[data-links] a');
    var C = {}; D.cells.forEach(function (c) { C[c[0] + ':' + c[1]] = { graded: c[2], pt: c[3], passed: c[4] }; });
    function color(v) {  // paper -> sage -> ink
      var s = [[251, 249, 244], [127, 179, 170], [17, 72, 78]], a = v < 0.5 ? s[0] : s[1], b = v < 0.5 ? s[1] : s[2], u = v < 0.5 ? v * 2 : (v - 0.5) * 2;
      return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * u); }).join(',') + ')';
    }
    function draw() {
      var W = 940, L = 200, T = 70, CW = (W - L - 10) / D.catalogs.length, CH = 54, H = T + D.models.length * CH + 10, m = M[metric];
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(svg);
      var vmax = 1; if (metric === 'runs') { vmax = 1; D.cells.forEach(function (c) { if (c[3].length >= minT) vmax = Math.max(vmax, c[2]); }); }
      D.catalogs.forEach(function (name, j) {
        var words = name.split(' '), lines = [], cur = '';
        words.forEach(function (w) { if ((cur + ' ' + w).trim().length > 16) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w; }); lines.push(cur.trim());
        lines.slice(0, 3).forEach(function (ln, k) { el('text', { x: L + j * CW + CW / 2, y: T - 12 - (Math.min(lines.length, 3) - 1 - k) * 14, 'text-anchor': 'middle', 'class': 'cx-collab' }, svg, ln); });
      });
      D.models.forEach(function (mname, i) {
        el('text', { x: L - 12, y: T + i * CH + CH / 2 + 4, 'text-anchor': 'end', 'class': 'cx-rowlab' }, svg, mname);
        D.catalogs.forEach(function (cn, j) {
          var c = C[j + ':' + i], ok = c && c.pt.length >= minT, gx = L + j * CW, gy = T + i * CH;
          var r = el('rect', { x: gx + 2, y: gy + 2, width: CW - 4, height: CH - 4, fill: ok ? color(metric === 'runs' ? c.graded / vmax : m.f(c)) : 'var(--paper)', stroke: pick === j + ':' + i ? 'var(--red)' : 'var(--line-2)', 'stroke-width': pick === j + ':' + i ? 2.5 : 1, 'class': ok ? 'cx-cell' : '' }, svg);
          if (!ok) { if (c) el('text', { x: gx + CW / 2, y: gy + CH / 2 + 4, 'text-anchor': 'middle', 'class': 'cx-tick' }, svg, c.pt.length + ' task' + (c.pt.length > 1 ? 's' : '')); return; }
          var v = metric === 'runs' ? c.graded / vmax : m.f(c), ink = v > 0.55 ? '#fff' : 'var(--ink)';
          el('text', { x: gx + CW / 2, y: gy + CH / 2 - 1, 'text-anchor': 'middle', 'class': 'cx-cellv', fill: ink }, svg, m.txt(m.f(c)));
          el('text', { x: gx + CW / 2, y: gy + CH / 2 + 15, 'text-anchor': 'middle', 'class': 'cx-cells', fill: ink }, svg, c.pt.length + ' tasks');
          r.addEventListener('mousemove', function (e) {
            var s = c.pt.slice().sort(function (a, b) { return a - b; });
            t.show('<b>' + esc(mname) + '</b><br>' + esc(cn) + '<br>' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs<br>Pass rate ' + pc(c.passed / c.graded) + '<br>Middle half of tasks: ' + pc(quant(s, 0.25)) + ' to ' + pc(quant(s, 0.75)), e);
          });
          r.addEventListener('mouseleave', t.hide);
          r.addEventListener('click', function () { pick = pick === j + ':' + i ? null : j + ':' + i; draw(); });
        });
      });
      clear(detail); detail.hidden = pick === null;
      if (pick !== null) {
        var jj = +pick.split(':')[0], ii = +pick.split(':')[1], c = C[pick], bins = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        c.pt.forEach(function (v) { bins[Math.min(9, Math.floor(v * 10))]++; });
        var mx = Math.max.apply(null, bins);
        h('p', 'cx-cap', detail, esc(D.models[ii]) + ' in ' + esc(D.catalogs[jj]) + ': ' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs, pass rate ' + pc(c.passed / c.graded));
        var hist = h('div', 'cx-mini', detail);
        bins.forEach(function (n, k) { var col = h('div', 'cx-mini-col', hist); var b = h('div', 'cx-mini-bar', col); b.style.height = (mx ? 100 * n / mx : 0) + '%'; b.title = n + ' tasks'; h('div', 'cx-mini-n', col, String(n)); h('div', 'cx-mini-lab', col, (k * 10) + '-' + (k === 9 ? 100 : k * 10 + 9) + '%'); });
        var foot = h('p', 'cx-hint', detail, 'Tasks by per-task pass rate. ');
        if (links[jj]) { var a = links[jj].cloneNode(true); a.textContent = 'Open the ' + D.catalogs[jj] + ' page'; foot.appendChild(a); }
      }
    }
    draw();
  }
  // ---- wiring ----
  function init(scope) {
    var dataEl = scope.querySelector('script[data-chart-data]');
    if (!dataEl || dataEl.dataset.ready) return; dataEl.dataset.ready = '1';
    var D = JSON.parse(dataEl.textContent), S = makeStore(D);
    S.tasks = D.tasks.map(function (r) { return { g: r[0], c: r[1], l: r[2], s: r[3], r: r[4] || {}, t: r[5] || {} }; });
    scope.querySelectorAll('[data-chart]').forEach(function (fig) {
      var kind = fig.dataset.chart;
      if (kind === 'bars') bars(fig, S); else if (kind === 'turns') turns(fig, S); else if (kind === 'reward') reward(fig, S); else if (kind === 'heat') heat(fig, S);
    });
    S.subs.forEach(function (fn) { fn(); });
  }
  var me = document.currentScript, scope = (me && me.closest('.view')) || document;
  init(scope);
})();
