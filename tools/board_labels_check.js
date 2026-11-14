// Every coordinate label on the flat board names the squares it sits beside, in reading
// order, and is on screen. Run in the page (the preview tools' javascript_exec or a
// console) with the flat board showing, at Fit and zoomed.
//
// Why (2026-11-13): a long board is drawn transposed to fill its box (flatTurned in
// 03-offers-and-map.js). The first try turned it a quarter instead: the letters ran F..A
// up the side, and zoomed, the labels scrolled off with the squares instead of staying
// pinned (24-map-zoom.js pin). A player types the name the board shows ("I go to C5",
// rules/fixtures.py square_said), so a label beside the wrong squares sends them there.
//
// Returns {labels, wrong, backwards, offscreen}; all three lists empty is the pass.
//   wrong      a label more than half a square off the line of squares it names
//   backwards  a pair of neighbouring labels not left-to-right or top-to-bottom
//   offscreen  a label, while zoomed, outside the board's own box
(() => {
  const svg = document.querySelector("#mapwrap .boardview svg#map");
  if (!svg) return {error: "no flat board showing"};
  const CELL = 18;
  const box = svg.getBoundingClientRect();
  const colOf = (s) => [...s].reduce((n, ch) => n * 26 + ch.charCodeAt(0) - 64, 0) - 1;
  const out = {labels: 0, wrong: [], backwards: [], offscreen: []};
  const seen = {col: [], row: []};
  for (const t of svg.querySelectorAll("text.coord")) {
    out.labels++;
    const col = t.classList.contains("col");
    const i = col ? colOf(t.textContent.trim()) : Number(t.textContent) - 1;
    // The squares' own sums: the label's group draws them, so its matrix is the board's.
    const m = t.parentNode.getScreenCTM();
    const at = (x, y) => new DOMPoint(x, y).matrixTransform(m);
    const a = col ? at((i + .5) * CELL, 0) : at(0, (i + .5) * CELL);
    const b = col ? at((i + 1.5) * CELL, 0) : at(0, (i + 1.5) * CELL);
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
    const r = t.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    // Along the line of names, the label's middle and its squares' middles agree.
    const off = ((cx - a.x) * dx + (cy - a.y) * dy) / len;
    if (Math.abs(off) > len / 2) out.wrong.push({label: t.textContent, off: Math.round(off)});
    seen[col ? "col" : "row"].push({i, cx, cy, name: t.textContent});
    // Zoomed: a label whose squares are in view is pinned in view (one whose squares are
    // scrolled off goes with them, by design).
    const inside = (x, y) => x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;
    const along = Math.abs(dx) > Math.abs(dy) ? inside(a.x, box.top + 1) : inside(box.left + 1, a.y);
    if (svg.closest(".is-zoomed") && along && !inside(cx, cy)) out.offscreen.push(t.textContent);
  }
  for (const list of Object.values(seen)) {
    list.sort((p, q) => p.i - q.i);
    for (let k = 1; k < list.length; k++) {
      const p = list[k - 1], q = list[k];
      if (q.cx < p.cx - 1 || q.cy < p.cy - 1) out.backwards.push(`${p.name} then ${q.name}`);
    }
  }
  return out;
})();
