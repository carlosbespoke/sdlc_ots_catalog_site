// Interactive turns-per-task histogram for the overview page. Data comes from the JSON block next to it.
// No element ids (the single-file build prefixes them), so everything is found through data attributes.
(function () {
  document.querySelectorAll('[data-turns-explorer]').forEach(function (root) {
    if (root.dataset.ready) return; root.dataset.ready = '1';
    var D = JSON.parse(root.querySelector('script[type="application/json"]').textContent);
    var NS = 'http://www.w3.org/2000/svg', W = 940, H = 330, L = 52, R = 18, T = 34, B = 44, BIN = D.bin, XMAX = D.xmax;
    var sel = D.models.map(function () { return true; }), thr = D.threshold, pick = null;
    var chips = root.querySelector('[data-chips]'), svg = root.querySelector('svg'), sum = root.querySelector('[data-summary]'), panel = root.querySelector('[data-panel]');
    var fmt = function (n) { return n.toLocaleString('en-US'); };
    var pct = function (a, b) { return b ? Math.round(100 * a / b) + '%' : 'n/a'; };
    var x = function (v) { return L + (W - L - R) * v / XMAX; };
    var el = function (tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
    D.models.forEach(function (m, i) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'tx-chip'; b.setAttribute('aria-pressed', 'true');
      b.innerHTML = '<span class="tx-dot"></span>' + m.name + ' <span class="tx-n">' + fmt(m.tasks) + ' tasks</span>';
      b.addEventListener('click', function () {
        if (sel[i] && sel.filter(Boolean).length === 1) return;  // keep at least one model
        sel[i] = !sel[i]; b.setAttribute('aria-pressed', String(sel[i])); pick = null; draw();
      });
      chips.appendChild(b);
    });
    function means() {  // each task: its average over the completed runs of the selected models
      var out = [];
      D.tasks.forEach(function (t) {
        var s = 0, n = 0;
        t[1].forEach(function (r) { if (sel[r[0]]) { s += r[1]; n += r[2]; } });
        if (n) out.push([t[0], s / n]);
      });
      return out;
    }
    var gStatic = el('g', {}, svg), gBars = el('g', {}, svg), gLines = el('g', {}, svg);
    var wash = el('rect', { y: T, height: H - T - B, fill: 'var(--red)', 'fill-opacity': 0.07 }, gStatic);
    for (var v = 0; v <= XMAX; v += 100) {
      el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'tx-tick' }, gStatic).textContent = fmt(v);
    }
    el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: 'var(--ink)', 'stroke-width': 1 }, gStatic);
    el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'tx-axis' }, gStatic).textContent = 'Average turns per task';
    el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', 'class': 'tx-axis', transform: 'rotate(-90 14 ' + (T + H - B) / 2 + ')' }, gStatic).textContent = 'Tasks';
    var gGrid = el('g', {}, gStatic);
    var meanLine = el('line', { y1: T, y2: H - B, stroke: 'var(--ink)', 'stroke-width': 1.2, 'stroke-dasharray': '4 4' }, gLines);
    var meanText = el('text', { y: T + 14, 'class': 'tx-mean' }, gLines);
    var thrG = el('g', { 'class': 'tx-thr', tabindex: 0, role: 'slider', 'aria-label': 'Long-horizon threshold in turns', 'aria-valuemin': 0, 'aria-valuemax': XMAX }, gLines);
    var thrHit = el('rect', { y: T - 20, height: H - B - T + 20, width: 24, fill: 'transparent' }, thrG);
    var thrLine = el('line', { y1: T - 6, y2: H - B, stroke: 'var(--red)', 'stroke-width': 2 }, thrG);
    var thrKnob = el('circle', { cy: T - 6, r: 7, fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 2 }, thrG);
    var thrText = el('text', { y: T - 18, 'class': 'tx-thr-label' }, thrG);
    function draw() {
      var M = means(), nb = Math.ceil(XMAX / BIN), bins = [];
      for (var i = 0; i < nb; i++) bins.push([]);
      M.forEach(function (t) { bins[Math.min(nb - 1, Math.floor(t[1] / BIN))].push(t[0]); });
      var top = Math.max.apply(null, bins.map(function (b) { return b.length; })) || 1, step = top > 200 ? 50 : top > 80 ? 20 : top > 30 ? 10 : 5;
      top = Math.ceil(top / step) * step;
      var y = function (n) { return H - B - (H - B - T) * n / top; };
      while (gGrid.firstChild) gGrid.removeChild(gGrid.firstChild);
      for (var g = 0; g <= top; g += step) {
        el('line', { x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: 'var(--line-2)', 'stroke-width': 1 }, gGrid);
        el('text', { x: L - 8, y: y(g) + 4, 'text-anchor': 'end', 'class': 'tx-tick' }, gGrid).textContent = fmt(g);
      }
      while (gBars.firstChild) gBars.removeChild(gBars.firstChild);
      bins.forEach(function (b, i) {
        var lo = i * BIN, hi = lo + BIN, bar = el('rect', { x: x(lo) + 1, width: x(hi) - x(lo) - 2, y: y(b.length), height: Math.max(0, H - B - y(b.length)),
          'class': 'tx-bar' + (pick === i ? ' is-picked' : ''), tabindex: b.length ? 0 : -1, role: 'button' }, gBars);
        el('title', {}, bar).textContent = fmt(lo) + '-' + fmt(hi - 1) + ' turns: ' + fmt(b.length) + ' tasks (' + pct(b.length, M.length) + ')';
        var choose = function () { if (!b.length) return; pick = pick === i ? null : i; draw(); };
        bar.addEventListener('click', choose);
        bar.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } });
      });
      var mean = M.reduce(function (a, t) { return a + t[1]; }, 0) / (M.length || 1);
      meanLine.setAttribute('x1', x(mean)); meanLine.setAttribute('x2', x(mean));
      var left = x(mean) > x(thr) - 90 && x(mean) < x(thr); meanText.setAttribute('x', left ? x(mean) - 6 : x(mean) + 6); meanText.setAttribute('text-anchor', left ? 'end' : 'start'); meanText.textContent = 'mean ' + Math.round(mean);
      var tx = x(thr);
      wash.setAttribute('x', tx); wash.setAttribute('width', Math.max(0, W - R - tx));
      thrHit.setAttribute('x', tx - 12); thrLine.setAttribute('x1', tx); thrLine.setAttribute('x2', tx); thrKnob.setAttribute('cx', tx);
      var flip = tx > W - R - 190; thrText.setAttribute('x', flip ? tx - 12 : tx + 12); thrText.setAttribute('text-anchor', flip ? 'end' : 'start'); thrText.textContent = 'long horizon, ' + fmt(thr) + '+ turns';
      thrG.setAttribute('aria-valuenow', thr);
      var long = M.filter(function (t) { return t[1] >= thr; });
      sum.innerHTML = '<strong>' + fmt(long.length) + '</strong> of ' + fmt(M.length) + ' tasks (' + pct(long.length, M.length) + ') average '
        + fmt(thr) + ' turns or more. Mean ' + Math.round(mean) + ' turns per task.';
      table(M, bins);
    }
    function table(M, bins) {
      var rows, head, cap;
      if (pick === null) {
        cap = 'Long-horizon tasks (' + fmt(thr) + '+ turns) by catalog';
        head = ['Catalog', 'Long-horizon tasks', 'Tasks with runs', 'Share'];
        rows = D.catalogs.map(function (c, ci) {
          var all = M.filter(function (t) { return t[0] === ci; }), lg = all.filter(function (t) { return t[1] >= thr; });
          return [c, lg.length, all.length, all.length ? lg.length / all.length : 0];
        });
      } else {
        var b = bins[pick], lo = pick * BIN;
        cap = 'Tasks averaging ' + fmt(lo) + '-' + fmt(lo + BIN - 1) + ' turns, by catalog';
        head = ['Catalog', 'Tasks in this bar', 'Tasks with runs', 'Share of bar'];
        rows = D.catalogs.map(function (c, ci) {
          var n = b.filter(function (v) { return v === ci; }).length;
          return [c, n, M.filter(function (t) { return t[0] === ci; }).length, b.length ? n / b.length : 0];
        });
      }
      var h = '<p class="tx-cap">' + cap + (pick === null ? '. Click a bar to break it down.' : '. <button type="button" class="tx-clear">Back to long-horizon view</button>') + '</p>'
        + '<div class="tx-grid" role="table"><div class="tx-row tx-head" role="row">' + head.map(function (t) { return '<span role="columnheader">' + t + '</span>'; }).join('') + '</div>'
        + rows.map(function (r) {
          return '<div class="tx-row" role="row"><span role="cell">' + r[0] + '</span><span role="cell">' + fmt(r[1]) + '</span><span role="cell">' + fmt(r[2]) + '</span><span role="cell"><span class="tx-meter"><span style="width:'
            + (100 * r[3]).toFixed(1) + '%"></span></span>' + Math.round(100 * r[3]) + '%</span></div>';
        }).join('') + '</div>';
      panel.innerHTML = h;
      var c = panel.querySelector('.tx-clear'); if (c) c.addEventListener('click', function () { pick = null; draw(); });
    }
    function toValue(clientX) {
      var p = svg.createSVGPoint(); p.x = clientX; p.y = 0; var v = p.matrixTransform(svg.getScreenCTM().inverse()).x;
      return Math.max(0, Math.min(XMAX, Math.round((v - L) / (W - L - R) * XMAX / 10) * 10));
    }
    var dragging = false;
    thrG.addEventListener('pointerdown', function (e) { dragging = true; thrG.setPointerCapture(e.pointerId); e.preventDefault(); });
    thrG.addEventListener('pointermove', function (e) { if (dragging) { var v = toValue(e.clientX); if (v !== thr) { thr = v; draw(); } } });
    thrG.addEventListener('pointerup', function () { dragging = false; });
    thrG.addEventListener('keydown', function (e) {
      var d = { ArrowLeft: -10, ArrowDown: -10, ArrowRight: 10, ArrowUp: 10, PageDown: -100, PageUp: 100 }[e.key];
      if (d) { e.preventDefault(); thr = Math.max(0, Math.min(XMAX, thr + d)); draw(); }
    });
    draw();
  });
})();
