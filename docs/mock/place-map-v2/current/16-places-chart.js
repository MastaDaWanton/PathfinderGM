// The play table, part 16 (the Places chart's drawing). Classic script, sharing one
// global scope with the rest; 16-tab-map.js puts it on the Map tab and walks by it.
//
// The town as a chart of its places joined by their ways, under a fog of war: the owner's
// favourite piece of the approved design ("this is amazing its my favorite piece you
// made"), `docs/mock/table-layout/places.js`, which carried it from the other mock
// (mock/table-free, views.js). Its drawing is kept as it was: the small spring model over
// the exits alone (the world export has no coordinates), solid lines for next door and
// dashed for the ways outside the walls, your place filled, the places one way from you
// ringed, a place seen but not visited in italic with a paler ring, a way not yet known
// a short stroke fading into the paper, a way the watch holds in rubric with a bar
// across it, and names that keep 13.5px and step aside rather than overlap.
//
// What changed from the mock is only where the facts come from. The mock held the visited
// set in sessionStorage and read a frozen data.js; here everything is the engine's own
// `scene.places_found` (play/places_found.py, on /api/state), and this file decides
// nothing about what is known:
//
//   * the nodes are the places found and nothing else, by name; a place under the fog
//     crosses to the page only as an index in `layout.links`, so there is nothing of it
//     here to leak into the DOM;
//   * the lines are `edges` (ways out of places stood in), the strokes into the paper
//     are `stubs` (ways out of places only seen, pointed by `toward`), and a shut way's
//     reason is the rules' own sentence (`shut`);
//   * the header counts places FOUND (`found`, `visited`). `layout.size` is the number
//     the rules know, and the owner ruled it is never shown: it is read here only to lay
//     the chart out.
//
// The layout is worked out once over the WHOLE graph (`layout`, which names nothing), so
// a place never moves when more of the chart is found; the chart's frame closes in on
// what is found. Measured 2026-09-30 on all three fixture worlds, 25 random walks each:
// `layout` was byte-identical from the first state to the last. It changes only when the
// town itself does (a place founded), and then the chart is laid out again.
//
// Pure: `svg`, `slip`, `header` and `key` return strings and touch no element, so node
// can run them (tests/test_table_places.py) and 16-tab-map.js writes them where they go.

const PlacesChart = (function () {
  const MINUTE_WORDS = w => String(w || "").replace(/(?:'s|') walk$/, "");
  const upper = t => { t = String(t || ""); return t ? t[0].toUpperCase() + t.slice(1) : t; };
  const bare = name => String(name || "").replace(/^the /i, "");
  const e = s => String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // --- The layout: the mock's spring model, over indices instead of names ---------------
  // The mock started its rings from the great square, found by name. Unfound places have
  // no name here, so the hub is the best-connected place (ties to the lowest index): a
  // choice made from the graph alone, so every state and every reload lays it the same.
  let LAID = null;
  function layoutOf(layout) {
    const size = Math.max(0, Number(layout && layout.size) || 0);
    const links = ((layout && layout.links) || []).filter(l =>
      Array.isArray(l) && l[0] >= 0 && l[1] >= 0 && l[0] < size && l[1] < size && l[0] !== l[1]);
    const sig = size + "|" + links.map(l => l[0] + "-" + l[1]).join(",");
    if (LAID && LAID.sig === sig) return LAID;
    const ids = [...Array(size).keys()];
    const next = ids.map(() => []);
    links.forEach(([a, b]) => { next[a].push(b); next[b].push(a); });
    const hub = ids.reduce((best, i) => (next[i].length > next[best].length ? i : best), 0);
    const depth = { [hub]: 0 }, q = [hub];
    while (q.length) {
      const a = q.shift();
      next[a].forEach(b => { if (depth[b] === undefined) { depth[b] = depth[a] + 1; q.push(b); } });
    }
    const rings = {};
    ids.forEach(i => { const d = depth[i] ?? 6; (rings[d] = rings[d] || []).push(i); });
    const P = {};
    Object.entries(rings).forEach(([d, list]) => list.forEach((id, k) => {
      const a = (k / list.length) * Math.PI * 2 + d * .7;
      P[id] = [Math.cos(a) * (d * 95 + 10), Math.sin(a) * (d * 70 + 8)];
    }));
    for (let it = 0; it < 420; it++) {
      const F = ids.map(() => [0, 0]);
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const a = P[i], b = P[j];
        const dx = a[0] - b[0], dy = a[1] - b[1]; const d2 = dx * dx + dy * dy + .01, d = Math.sqrt(d2);
        const rep = 5200 / d2;
        F[i][0] += dx / d * rep; F[i][1] += dy / d * rep;
        F[j][0] -= dx / d * rep; F[j][1] -= dy / d * rep;
      }
      links.forEach(([a, b]) => {
        const pa = P[a], pb = P[b]; const dx = pb[0] - pa[0], dy = pb[1] - pa[1];
        const d = Math.sqrt(dx * dx + dy * dy) + .01, f = (d - 78) * .045;
        F[a][0] += dx / d * f; F[a][1] += dy / d * f; F[b][0] -= dx / d * f; F[b][1] -= dy / d * f;
      });
      ids.forEach(i => { P[i][0] += Math.max(-8, Math.min(8, F[i][0]));
                         P[i][1] += Math.max(-8, Math.min(8, F[i][1])) * .8; });
    }
    // Squash to a landscape frame: the springs settle tall.
    let xs = ids.map(i => P[i][0]), ys = ids.map(i => P[i][1]);
    if (ids.length) {
      const wide = Math.max(...xs) - Math.min(...xs) || 1, tall = Math.max(...ys) - Math.min(...ys);
      if (tall / wide > .62) ids.forEach(i => { P[i][1] *= .62 * wide / tall; });
      xs = ids.map(i => P[i][0]); ys = ids.map(i => P[i][1]);
    }
    const x0 = (ids.length ? Math.min(...xs) : 0) - 70, y0 = (ids.length ? Math.min(...ys) : 0) - 30;
    const x1 = (ids.length ? Math.max(...xs) : 0) + 70, y1 = (ids.length ? Math.max(...ys) : 0) + 30;
    LAID = { sig, P, box: [x0, y0, x1 - x0, y1 - y0], centre: [(x0 + x1) / 2, (y0 + y1) / 2] };
    return LAID;
  }

  // A name's width on screen, in the chart's own face (the `.chart .node text` rule).
  // Without a canvas (node, in the tests) a fair estimate of Palatino at 13.5px.
  let ruler = null;
  function textWidth(s, italic) {
    try {
      if (!ruler && typeof document !== "undefined" && document.createElement) {
        ruler = document.createElement("canvas").getContext("2d");
      }
    } catch (err) { ruler = null; }
    if (!ruler) return String(s).length * (italic ? 6.6 : 7.3);
    const face = (typeof getComputedStyle === "function"
      && getComputedStyle(document.documentElement).getPropertyValue("--body")) || "Georgia, serif";
    ruler.font = `${italic ? "italic 400" : "600"} 13.5px ${face}`;
    return ruler.measureText(s).width;
  }

  // --- The drawing ---------------------------------------------------------------------
  // `k` is the drawing's units per screen pixel, measured on the drawn chart by the
  // caller (16-tab-map.js), and every radius, stroke, gap and letter is multiplied by it,
  // so the ink keeps its size however far the frame closes in. Measured on the mock's
  // first drawing: at a fixed size in the drawing's own units the names came out at
  // 8.5px on the opening chart at 1440, too small to read.
  function svg(pf, { sel = null, k = 1 } = {}) {
    const L = layoutOf(pf.layout);
    const nodes = (pf.nodes || []).filter(n => L.P[n.i]);
    const at = new Map(nodes.map(n => [n.id, L.P[n.i]]));
    const lines = [], stubs = [], defs = [];

    // One line per pair of places, whichever way it was walked; a bar for each direction
    // the rules shut, a third of the way out from the place it is shut from (the watch
    // stands at the way OUT, so a way can be shut one way only).
    const pairs = new Map();
    (pf.edges || []).forEach(x => {
      if (!at.has(x.from) || !at.has(x.to)) return;
      const key = [x.from, x.to].sort().join("|");
      const p = pairs.get(key) || { a: x.from, b: x.to, dashed: false, shut: [] };
      p.dashed = p.dashed || !!x.dashed;
      if (x.shut) p.shut.push([x.from, x.to, x.shut]);
      pairs.set(key, p);
    });
    pairs.forEach(p => {
      const [ax, ay] = at.get(p.a), [bx, by2] = at.get(p.b);
      const why = p.shut.map(s => s[2]).join(" ");
      lines.push(`<line class="edge${p.dashed ? " road" : ""}${p.shut.length ? " shut" : ""}" x1="${
        ax}" y1="${ay}" x2="${bx}" y2="${by2}">${why ? `<title>${e(why)}</title>` : ""}</line>`);
      p.shut.forEach(([from, to, reason]) => {
        const [sx, sy] = at.get(from), [ox, oy] = at.get(to);
        const mx = sx + (ox - sx) / 3, my = sy + (oy - sy) / 3, d = Math.hypot(ox - sx, oy - sy) || 1;
        const nx = -(oy - sy) / d * 6 * k, ny = (ox - sx) / d * 6 * k;
        lines.push(`<line class="bar" x1="${mx - nx}" y1="${my - ny}" x2="${mx + nx}" y2="${
          my + ny}"><title>${e(reason)}</title></line>`);
      });
    });

    // A way whose far end is not known: a short stroke into the paper. It points at the
    // hidden end's place in the layout (`toward`, an index), or, for a road (a journey
    // out of the town), away from the town's middle.
    const stroke = (from, tx, ty, dashed, n, title) => {
      const [fx, fy] = at.get(from);
      let dx = tx - fx, dy = ty - fy, d = Math.hypot(dx, dy);
      if (!d) { dx = 1; dy = 0; d = 1; }
      const len = Math.min(32 * k, Math.max(d * .42, 18 * k));
      const ex = fx + dx / d * len, ey = fy + dy / d * len;
      const id = `fog${n}`;
      defs.push(`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${fx}" y1="${fy}" x2="${
        ex}" y2="${ey}"><stop offset="0" stop-color="#3c2e20" stop-opacity=".9"/><stop offset="1" stop-color="#3c2e20" stop-opacity="0"/></linearGradient>`);
      stubs.push(`<line class="stub${dashed ? " road" : ""}" stroke="url(#${id})" x1="${fx}" y1="${
        fy}" x2="${ex}" y2="${ey}">${title ? `<title>${e(title)}</title>` : ""}</line>`);
    };
    const outward = from => {
      const [fx, fy] = at.get(from), [cx, cy] = L.centre;
      return fx === cx && fy === cy ? [fx + 1, fy] : [fx + (fx - cx), fy + (fy - cy)];
    };
    (pf.stubs || []).forEach((x, n) => {
      if (!at.has(x.from)) return;
      const to = x.toward != null && L.P[x.toward] ? L.P[x.toward] : outward(x.from);
      stroke(x.from, to[0], to[1], x.dashed, n, "");
    });
    (pf.roads || []).forEach((r, n) => {
      if (!at.has(r.from)) return;
      const to = outward(r.from);
      stroke(r.from, to[0], to[1], true, `r${n}`, `${upper(r.name)}, ${r.time_words}${r.shut ? `. ${r.shut}` : ""}`);
    });

    // Names: to the right of their place, as the other mock draws them, unless that would
    // run into another place or name; then left, above, below. Placed you-first, then the
    // places you have been, then the rest. Measured on the mock at 1024 and on a phone,
    // where the chart is 225px tall: "north crossing" ran over the warrens' ring.
    const order = nodes.slice().sort((a, b) =>
      (b.current - a.current) || (b.visited - a.visited) || (a.i - b.i));
    const rings = order.map(n => { const [x, y] = at.get(n.id); return [x - 9 * k, y - 9 * k, x + 9 * k, y + 9 * k]; });
    const hit = (b, list) => list.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    const placed = [], label = {};
    const xsFound = nodes.map(n => at.get(n.id)[0]);
    const minX = Math.min(...xsFound), spanX = Math.max(...xsFound) - minX;
    order.forEach((n, idx) => {
      const [x, y] = at.get(n.id), name = bare(n.name);
      const w = textWidth(name, !n.visited) * k, h = 13 * k;
      // The mock's eight places for a name, then the same eight a step further out: with
      // fifteen places found on a 1024 or a phone's chart, the first eight left 4 and 28
      // pairs of names over each other (measured 2026-09-30 on Deepshoal).
      const near8 = [[10, 4.5, "start"], [-10, 4.5, "end"], [0, -12, "middle"], [0, 21, "middle"],
                     [8, -8, "start"], [8, 17, "start"], [-8, -8, "end"], [-8, 17, "end"]];
      let tries = near8.concat(near8.map(([dx, dy, a]) =>
        [dx * 1.8, a === "middle" ? (dy < 0 ? dy - 10 : dy + 10) : (dy < 4 ? dy - 9 : dy + 9), a]));
      // A place on the found set's right-hand edge tries its name on the left first, into
      // the chart, not out past it. Every name that hangs outside the places widens the
      // frame, and the frame is fitted to the sheet: at 375 the names hanging out on both
      // sides left the places themselves 100px of a 300px chart.
      if (spanX > 0 && (x - minX) / spanX > .66) {
        tries = tries.filter(t => t[2] === "end").concat(tries.filter(t => t[2] !== "end"));
      }
      const boxOf = t => {
        const lx = x + t[0] * k, ly = y + t[1] * k;
        const bx = t[2] === "start" ? lx : t[2] === "end" ? lx - w : lx - w / 2;
        return [bx, ly - h * .8, bx + w, ly + h * .25];
      };
      const others = rings.filter((_, j) => j !== idx);
      const pick = tries.find(t => !hit(boxOf(t), placed) && !hit(boxOf(t), others)) || tries[0];
      placed.push(boxOf(pick));
      label[n.id] = [x + pick[0] * k, y + pick[1] * k, pick[2]];
    });
    const drawn = order.slice().sort((a, b) => a.i - b.i).map(n => {
      const [x, y] = at.get(n.id);
      const cls = (n.current ? " here" : "") + (n.visited ? " been" : " seen") + (n.near ? " near" : "")
        + (n.setting === "outside" ? " out" : "") + (sel === n.id ? " sel" : "");
      const [lx, ly, anchor] = label[n.id];
      const how = n.current ? ", you are here" : n.visited ? ", visited" : ", seen, not yet visited";
      return `<g class="node${cls}" data-node="${e(n.id)}" tabindex="0" role="button" aria-pressed="${
        sel === n.id}" aria-label="${e(n.name)}${how}"><circle cx="${x}" cy="${y}" r="${
        (n.current ? 8 : 6) * k}"/><text x="${lx}" y="${ly}" text-anchor="${anchor}">${
        e(bare(n.name))}</text></g>`;
    }).join("");

    // The frame fits what is found, its names included, never smaller than a fifth of the
    // town, so a first chart of the gate and its doors is not blown up to fill the sheet.
    const pts = nodes.map(n => at.get(n.id));
    let x0 = Math.min(...pts.map(p => p[0] - 12 * k), ...placed.map(b => b[0])) - 8 * k;
    let x1 = Math.max(...pts.map(p => p[0] + 12 * k), ...placed.map(b => b[2])) + 8 * k;
    let y0 = Math.min(...pts.map(p => p[1] - 12 * k), ...placed.map(b => b[1])) - 10 * k;
    let y1 = Math.max(...pts.map(p => p[1] + 12 * k), ...placed.map(b => b[3])) + 10 * k;
    if (!pts.length) { [x0, y0] = L.box; x1 = x0 + L.box[2]; y1 = y0 + L.box[3]; }
    const mw = L.box[2] * .2, mh = L.box[3] * .2;
    if (x1 - x0 < mw) { const c = (x0 + x1) / 2; x0 = c - mw / 2; x1 = c + mw / 2; }
    if (y1 - y0 < mh) { const c = (y0 + y1) / 2; y0 = c - mh / 2; y1 = c + mh / 2; }

    return `<svg viewBox="${x0} ${y0} ${x1 - x0} ${y1 - y0}" preserveAspectRatio="xMidYMid meet"
      role="group" aria-label="The places you have found" style="--k: ${k.toFixed(4)}"><defs>${
      defs.join("")}</defs>${stubs.join("")}${lines.join("")}${drawn}</svg>`;
  }

  // --- The words around it -----------------------------------------------------------------
  // The header counts what the player has found (the owner: "instead of displaying the
  // number of places the rules know you display the number of places found by the user"),
  // and both numbers, because a player reading "10 found" wants to know how much of it
  // they have walked. Never `layout.size`.
  function header(pf) {
    const f = Number(pf.found) || 0, v = Number(pf.visited) || 0;
    return `${f} ${f === 1 ? "place" : "places"} found, ${v >= f ? "all" : v} of them visited. `
      + "Solid lines are next door; dashed lead outside the walls.";
  }

  function key(pf) {
    const shut = (pf.edges || []).some(x => x.shut);
    return `<span class="pk here"></span>You are here <span class="pk been"></span>Visited
      <span class="pk seen"></span>Seen, not yet visited <span class="pk fog"></span>A way not yet known${
      shut ? ` <span class="pk shut"></span>Shut to you` : ""}`;
  }

  // The slip beside the chart: where you are, or the pressed place with its way there leg
  // by leg, the engine's own minutes ("About N minutes on foot" was a guess from words in
  // the mock; `walk.minutes` is `outskirts.hop_minutes`, what the exits row words), and
  // Walk there. `said` is the line the last Walk there left, above the rest.
  function slip(pf, { sel = null, said = "", walking = null } = {}) {
    const here = (pf.nodes || []).find(n => n.current);
    let out = here ? `<div class="mapnote"><h3>${e(upper(here.name))} <small>you are here</small></h3>
      <p>Press a place for the way there. The drawing comes from the exits alone; the world
      gives no coordinates, so distance on it means nothing.</p></div>` : "";
    const n = sel && (pf.nodes || []).find(x => x.id === sel && !x.current);
    if (n) {
      const legs = (n.walk && n.walk.legs) || [];
      const on = walking && walking === n.id;
      out = `<div class="mapnote picked"><h3>${e(upper(n.name))}${
        n.visited ? "" : " <small>not yet visited</small>"}</h3>${legs.length
        ? `<ol class="route">${legs.map(x => `<li>${e(upper(x.name))}<span>${
            e(MINUTE_WORDS(x.time_words))}</span></li>`).join("")}</ol>
          <p>About ${Number(n.walk.minutes) || 0} ${Number(n.walk.minutes) === 1 ? "minute" : "minutes"} on foot, by the way above.</p>
          <button type="button" class="v2-btn is-go walkthere" data-walkto="${e(n.id)}"${
            on ? ` aria-describedby="walksaid"` : ""}>Walk there</button>`
        : `<p class="shutwhy">${e(n.why || "No way there by the ways you know.")}</p>`}</div>` + out;
    }
    if (said) out = `<div class="mapnote said" id="walksaid"><p>${e(said)}</p></div>` + out;
    return out;
  }

  return { svg, header, key, slip, layoutOf };
})();
