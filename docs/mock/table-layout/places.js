// Places: the town as a chart of its places joined by their ways, under a fog of war.
//
// The drawing is the other mock's (mock/table-free, docs/mock/table-free/views.js, "Map:
// the place graph the exits walk"), which the owner picked as their favourite piece: the
// layout (a small spring model over the exits alone, since the world export has no
// coordinates), solid lines for next door, dashed for the ways outside the walls, the
// current place filled, a pressed place giving the way there, its time, and Walk there.
// What is new here is only what the owner asked for (2026-09-29): "the fog of war only
// being able to see places conected to where you have been before", and a count of the
// places found instead of the places the rules know.
//
// The fog, by the owner's ruling: a place is on the chart if you have been there this
// session, or if it is one way from anywhere you have been; nothing else is drawn, no node,
// no line, no name. A way out of a place you have only seen, not visited, is drawn as a
// short stub fading into the paper: the way is there, where it goes is not known yet.
//
// The layout is worked out once over the whole town, so a place never moves when more of
// the chart is found; the chart's frame fits what is found (never less than half the
// town's width, so the names stay at one size).
"use strict";

window.Places = (function () {
  const KEY = "tablelayout.visited";
  const MINUTES = { "a few minutes' walk": 5, "a quarter of an hour": 15, "about five days on foot": 7200 };
  const walkWords = w => String(w || "").replace(/(?:'s|') walk$/, "");

  // --- The visited set: in memory, and in sessionStorage so a reload keeps it ------------
  let visited = new Set([D.start]);
  try {
    const kept = JSON.parse(sessionStorage.getItem(KEY) || "null");
    if (Array.isArray(kept) && kept.length) visited = new Set(kept.filter(id => D.places[id]));
    if (!visited.size) visited = new Set([D.start]);
  } catch (e) { /* storage refused (a private window): memory only */ }
  function keep() {
    try { sessionStorage.setItem(KEY, JSON.stringify([...visited])); } catch (e) { /* memory only */ }
  }

  // --- The layout: the other mock's spring model, unchanged -------------------------------
  let LAYOUT = null;
  function layout() {
    if (LAYOUT) return LAYOUT;
    const ids = Object.keys(D.places);
    const edges = [];
    const seen = new Set();
    ids.forEach(a => D.places[a].exits.forEach(x => {
      const b = x[0];
      if (!D.places[b]) return;
      const k = [a, b].sort().join("|");
      if (!seen.has(k)) { seen.add(k); edges.push([a, b, x[2] === "o" || x[2] === "r"]); }
    }));
    // Rings by distance from the great square: a stable start the springs only tidy.
    const hub = ids.find(i => /great-square/.test(i)) || ids[0];
    const depth = { [hub]: 0 }, q = [hub];
    while (q.length) {
      const a = q.shift();
      D.places[a].exits.forEach(x => { if (D.places[x[0]] && depth[x[0]] === undefined) { depth[x[0]] = depth[a] + 1; q.push(x[0]); } });
    }
    const rings = {};
    ids.forEach(i => { const d = depth[i] ?? 6; (rings[d] = rings[d] || []).push(i); });
    const P = {};
    Object.entries(rings).forEach(([d, list]) => list.forEach((id, k) => {
      const a = (k / list.length) * Math.PI * 2 + d * .7;
      P[id] = [Math.cos(a) * (d * 95 + 10), Math.sin(a) * (d * 70 + 8)];
    }));
    for (let it = 0; it < 420; it++) {
      const F2 = Object.fromEntries(ids.map(i => [i, [0, 0]]));
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const a = P[ids[i]], b = P[ids[j]];
        const dx = a[0] - b[0], dy = a[1] - b[1]; const d2 = dx * dx + dy * dy + .01, d = Math.sqrt(d2);
        const rep = 5200 / d2;
        F2[ids[i]][0] += dx / d * rep; F2[ids[i]][1] += dy / d * rep;
        F2[ids[j]][0] -= dx / d * rep; F2[ids[j]][1] -= dy / d * rep;
      }
      edges.forEach(([a, b]) => {
        const pa = P[a], pb = P[b]; const dx = pb[0] - pa[0], dy = pb[1] - pa[1];
        const d = Math.sqrt(dx * dx + dy * dy) + .01, f = (d - 78) * .045;
        F2[a][0] += dx / d * f; F2[a][1] += dy / d * f; F2[b][0] -= dx / d * f; F2[b][1] -= dy / d * f;
      });
      ids.forEach(i => { P[i][0] += Math.max(-8, Math.min(8, F2[i][0])); P[i][1] += Math.max(-8, Math.min(8, F2[i][1])) * .8; });
    }
    // Squash to a landscape frame: the springs settle tall.
    let xs = ids.map(i => P[i][0]), ys = ids.map(i => P[i][1]);
    const wide = Math.max(...xs) - Math.min(...xs), tall = Math.max(...ys) - Math.min(...ys);
    if (tall / wide > .62) ids.forEach(i => { P[i][1] *= .62 * wide / tall; });
    xs = ids.map(i => P[i][0]); ys = ids.map(i => P[i][1]);
    const x0 = Math.min(...xs) - 70, y0 = Math.min(...ys) - 30;
    LAYOUT = { P, edges, ids, box: [x0, y0, Math.max(...xs) - x0 + 70, Math.max(...ys) - y0 + 30] };
    return LAYOUT;
  }

  // --- What is known --------------------------------------------------------------------
  const ways = id => D.places[id].exits.filter(x => D.places[x[0]]);
  function known() {
    const seen = new Set(visited);
    visited.forEach(id => ways(id).forEach(x => seen.add(x[0])));
    return seen;
  }
  // A way is known when it leaves a place you have been. Walks go by known ways only, and
  // under Wanted, never through one the watch holds (the table's own exits say which).
  const exitsOf = id => (S.wanted ? D.places[id].wanted : D.places[id].exits);
  function route(to) {
    const prev = { [S.place]: null }, q = [S.place];
    while (q.length) {
      const a = q.shift();
      if (a === to) break;
      if (!visited.has(a)) continue;
      exitsOf(a).forEach(x => {
        if (x[4] >= 0 || x[5] || !D.places[x[0]] || x[0] in prev) return;
        prev[x[0]] = [a, x]; q.push(x[0]);
      });
    }
    if (!(to in prev)) return null;
    const legs = []; let k = to;
    while (prev[k]) { legs.unshift(prev[k][1]); k = prev[k][0]; }
    return legs;
  }

  let sel = null, said = "";

  // --- Drawing ---------------------------------------------------------------------------
  // The chart's scale changes with what is found (the frame fits it), so the ink is sized
  // in screen pixels: k is the drawing's units per pixel, measured on the drawn chart, and
  // every radius, stroke, gap and letter is multiplied by it. Measured on the first
  // drawing: at a fixed size in the drawing's own units the names came out at 8.5px on
  // the opening chart at 1440, too small to read.
  let k = 1;
  // A name's width on screen, in the chart's own face (mock.css .chart .node text).
  const ruler = document.createElement("canvas").getContext("2d");
  const face = getComputedStyle(document.documentElement).getPropertyValue("--body") || "Georgia, serif";
  function textWidth(s, italic) {
    ruler.font = `${italic ? "italic 400" : "600"} 13.5px ${face}`;
    return ruler.measureText(s).width;
  }
  function render() {
    // The frame's margins are themselves in ink sizes, so k and the frame settle together:
    // a few rounds, each within a percent of the last by the third.
    for (let round = 0; round < 5; round++) {
      draw();
      const svgEl = $("#boardview .chart svg");
      if (!svgEl) return;
      const vb = svgEl.viewBox.baseVal, r = svgEl.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const next = Math.max(vb.width / r.width, vb.height / r.height);
      if (Math.abs(next - k) / next < .01) return;
      k = next;
    }
  }
  function draw() {
    const L = layout(), P = L.P;
    const seen = known();
    const near = new Set(exitsOf(S.place).filter(x => D.places[x[0]]).map(x => x[0]));
    const shutFrom = new Map();   // "a|b" -> the place whose way to the other is shut
    if (S.wanted) visited.forEach(a => D.places[a].wanted.forEach(x => {
      if (x[4] >= 0 && D.places[x[0]]) shutFrom.set([a, x[0]].sort().join("|"), a);
    }));
    const lines = [], stubs = [], defs = [];
    L.edges.forEach(([a, b, road], i) => {
      const va = visited.has(a), vb = visited.has(b);
      const pair = [a, b].sort().join("|");
      if (va || vb) {
        const shut = shutFrom.get(pair);
        lines.push(`<line class="edge${road ? " road" : ""}${shut ? " shut" : ""}" x1="${P[a][0]}" y1="${
          P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}"/>`);
        if (shut) {
          // A bar across the way, a third of the way out from the place it is shut from.
          const o = shut === a ? b : a, [sx, sy] = P[shut], [ox, oy] = P[o];
          const mx = sx + (ox - sx) / 3, my = sy + (oy - sy) / 3, d = Math.hypot(ox - sx, oy - sy) || 1;
          const nx = -(oy - sy) / d * 6 * k, ny = (ox - sx) / d * 6 * k;
          lines.push(`<line class="bar" x1="${mx - nx}" y1="${my - ny}" x2="${mx + nx}" y2="${my + ny}"/>`);
        }
        return;
      }
      // Neither end visited: from each end that is on the chart, a stub into the fog.
      [[a, b], [b, a]].forEach(([from, to]) => {
        if (!seen.has(from)) return;
        const [fx, fy] = P[from], [tx, ty] = P[to], d = Math.hypot(tx - fx, ty - fy) || 1;
        const len = Math.min(32 * k, d * .42), ex = fx + (tx - fx) / d * len, ey = fy + (ty - fy) / d * len;
        const id = `fog${i}${from === a ? "a" : "b"}`;
        defs.push(`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${fx}" y1="${fy}" x2="${ex}" y2="${ey}">
          <stop offset="0" stop-color="#3c2e20" stop-opacity=".9"/><stop offset="1" stop-color="#3c2e20" stop-opacity="0"/></linearGradient>`);
        stubs.push(`<line class="stub${road ? " road" : ""}" stroke="url(#${id})" x1="${fx}" y1="${fy}" x2="${ex}" y2="${ey}"/>`);
      });
    });
    // Names: to the right of their place as the other mock draws them, unless that would
    // run into another place or name; then left, above, below. Placed you-first, then the
    // places you have been, then the rest. Measured on the first drawings at 1024 and on a
    // phone, where the chart is 225px tall: "north crossing" ran over the warrens' ring.
    const order = L.ids.filter(id => seen.has(id)).sort((a, b) =>
      (b === S.place) - (a === S.place) || visited.has(b) - visited.has(a));
    const boxes = order.map(id => [P[id][0] - 9 * k, P[id][1] - 9 * k, P[id][0] + 9 * k, P[id][1] + 9 * k]);
    const hit = (b, list) => list.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    const placed = [], label = {};
    order.forEach((id, i) => {
      const [x, y] = P[id], name = D.places[id].name.replace(/^the /, "");
      const w = textWidth(name, !visited.has(id)) * k, h = 13 * k;
      const tries = [[10, 4.5, "start"], [-10, 4.5, "end"], [0, -12, "middle"], [0, 21, "middle"],
                     [8, -8, "start"], [8, 17, "start"], [-8, -8, "end"], [-8, 17, "end"]];
      let pick = tries[0];
      for (const t of tries) {
        const lx = x + t[0] * k, ly = y + t[1] * k;
        const bx = t[2] === "start" ? lx : t[2] === "end" ? lx - w : lx - w / 2;
        const box = [bx, ly - h * .8, bx + w, ly + h * .25];
        if (!hit(box, placed) && !hit(box, boxes.filter((_, j) => j !== i))) { pick = t; break; }
      }
      const lx = x + pick[0] * k, ly = y + pick[1] * k;
      const bx = pick[2] === "start" ? lx : pick[2] === "end" ? lx - w : lx - w / 2;
      placed.push([bx, ly - h * .8, bx + w, ly + h * .25]);
      label[id] = [lx, ly, pick[2]];
    });
    const nodes = L.ids.filter(id => seen.has(id)).map(id => {
      const p = D.places[id], [x, y] = P[id];
      const here = id === S.place, been = visited.has(id);
      const cls = (here ? " here" : "") + (been ? " been" : " seen") + (near.has(id) ? " near" : "")
        + (p.setting === "outside" ? " out" : "") + (sel === id ? " sel" : "");
      const [lx, ly, anchor] = label[id];
      return `<g class="node${cls}" data-node="${esc(id)}" tabindex="0" role="button"
        aria-label="${esc(p.name)}${here ? ", you are here" : been ? ", visited" : ", seen, not yet visited"}"><circle cx="${x}" cy="${y}" r="${(here ? 8 : 6) * k}"/>
        <text x="${lx}" y="${ly}" text-anchor="${anchor}">${esc(p.name.replace(/^the /, ""))}</text></g>`;
    }).join("");

    // The frame fits what is found, its names included, never smaller than a fifth of the
    // town, so a first chart of the gate and its doors is not blown up to fill the sheet.
    const pts = [...seen].map(id => P[id]);
    let x0 = Math.min(...pts.map(p => p[0] - 12 * k), ...placed.map(b => b[0])) - 8 * k;
    let x1 = Math.max(...pts.map(p => p[0] + 12 * k), ...placed.map(b => b[2])) + 8 * k;
    let y0 = Math.min(...pts.map(p => p[1] - 12 * k), ...placed.map(b => b[1])) - 10 * k;
    let y1 = Math.max(...pts.map(p => p[1] + 12 * k), ...placed.map(b => b[3])) + 10 * k;
    const [, , fw, fh] = L.box;
    const mw = fw * .2, mh = fh * .2;
    if (x1 - x0 < mw) { const c = (x0 + x1) / 2; x0 = c - mw / 2; x1 = c + mw / 2; }
    if (y1 - y0 < mh) { const c = (y0 + y1) / 2; y0 = c - mh / 2; y1 = c + mh / 2; }

    const town = D.places[S.place].setting === "outside" ? "Near Zhilvarnia" : "Zhilvarnia";
    let side = `<div class="mapnote"><h3>${esc(cap(D.places[S.place].name))} <small>you are here</small></h3>
      <p>Press a place for the way there. The drawing comes from the exits alone; the world gives no coordinates, so distance on it means nothing.</p></div>`;
    if (sel && sel !== S.place && D.places[sel]) {
      const legs = route(sel);
      const mins = legs ? legs.reduce((n, x) => n + (MINUTES[x[3]] || 5), 0) : 0;
      side = `<div class="mapnote picked"><h3>${esc(cap(D.places[sel].name))}${
        visited.has(sel) ? "" : " <small>not yet visited</small>"}</h3>
        ${legs ? `<ol class="route">${legs.map(x => `<li>${esc(cap(x[1]))}<span>${esc(walkWords(x[3]))}</span></li>`).join("")}</ol>
          <p>About ${mins} minutes on foot, by the way above.</p>
          <button type="button" class="go" data-walkto="${esc(sel)}">Walk there</button>`
        : `<p class="shutwhy">No open way there from ${esc(D.places[S.place].name)}${
          S.wanted ? ": the watch holds the ways you would need" : " by the ways you know"}.</p>`}</div>` + side;
    }
    if (said) side = `<div class="mapnote said" aria-live="polite"><p>${esc(said)}</p></div>` + side;
    $("#board-name").textContent = town;
    $("#boardview").innerHTML = `<div class="placemap"><div class="chart"><svg viewBox="${x0} ${y0} ${
      x1 - x0} ${y1 - y0}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="The places you have found"
      style="--k: ${k.toFixed(4)}">
      <defs>${defs.join("")}</defs>${stubs.join("")}${lines.join("")}${nodes}</svg></div>
      <div class="maprail">${side}</div></div>`;
    const v = visited.size, f = seen.size;
    $("#board-about").textContent = `${f} ${f === 1 ? "place" : "places"} found, ${
      v === f ? "all" : v} of them visited. Solid lines are next door; dashed lead outside the walls.`;
    $("#board-key").innerHTML = `<span class="pk here"></span>You are here <span class="pk been"></span>Visited
      <span class="pk seen"></span>Seen, not yet visited <span class="pk fog"></span>A way not yet known`;
    $("#board-say").innerHTML = "";
  }

  // --- Walking by the chart ------------------------------------------------------------
  function walkTo(id) {
    const legs = route(id);
    if (!legs) return;
    Turn.take(() => {
      const from = D.places[S.place].name;
      const mins = legs.reduce((k, x) => k + (MINUTES[x[3]] || 5), 0);
      legs.forEach(x => { visit(x[0]); S.walked.push(x[1]); });
      S.place = id; S.confirm = null; S.why = ""; S.person = null; sel = null;
      const by = legs.slice(0, -1).map(x => x[1]).join(", ");
      said = `Mock. The engine walks each leg in turn, ${mins} minutes in all, and would stop the walk if anything happened on the way. You are at ${D.places[id].name}.`;
      say(`I walk to ${D.places[id].name}${by ? `, by ${by}` : ""}.`, `Mock. The engine moves you from ${from} to ${
        D.places[id].name} by ${legs.length} ${legs.length > 1 ? "legs" : "leg"}, about ${mins} minutes on foot.`);
      renderScene();
      if (S.board.view === "places") render();
    });
  }
  function visit(id) { if (D.places[id] && !visited.has(id)) { visited.add(id); keep(); } }

  document.addEventListener("click", e => {
    const n = e.target.closest && e.target.closest("[data-node]");
    if (n) { sel = n.dataset.node === sel ? null : n.dataset.node; said = ""; render();
      const again = document.querySelector(`[data-node="${CSS.escape(n.dataset.node)}"]`); if (again) again.focus(); return; }
    const w = e.target.closest && e.target.closest("[data-walkto]");
    if (w) walkTo(w.dataset.walkto);
  });
  document.addEventListener("keydown", e => {
    const n = e.target.closest && e.target.closest("[data-node]");
    if (n && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); n.dispatchEvent(new MouseEvent("click", { bubbles: true })); }
  });

  return {
    render, visit,
    reset() { visited = new Set([D.start]); sel = null; said = ""; keep(); },
    visited: () => [...visited], known: () => [...known()],
  };
})();

// Opened straight at the chart (#mode=map&view=places): mock.js drew the board before this
// file loaded, so it is drawn again now.
if (S.mode === "map" && S.board.view === "places") renderBoard();
