// The play table, part 16 (the place map's world model). Classic script, sharing one global
// scope with the rest; one global, `PlacesWorld`, read by js/places-board.js (the tabletop)
// and 16-tab-map.js (the slips and the breadcrumb).
//
// Phase 3 of docs/place-map-v2-build-plan.md: the Region, Continent and World maps. Ported
// from the chosen mock (docs/mock/place-map-v2/shared/model.js and tabletop.js, branch
// mock/place-map-v2). What the world IS comes from `/api/atlas` (play/atlas.py: every
// settlement, nation, continent and the engine's own journeys); what the player KNOWS comes
// from `scene.known_places`. This file only lays them out; it decides nothing about what is
// known beyond the one rule the mock's region already used (a road out of a town stood in is
// signed for where it goes).
//
// Pure but for `placesAtlas` at the end, which reads the atlas: no element is touched, so node
// runs it (tests/test_places_world.py) on all three worlds. One rule for land, `landAt`, is used by every board and by the World's nations and
// names, so the maps cannot disagree about where the sea is: in the mock the World painted
// its land from canvas blots and the boards asked `landAt`, two readings of one shape.

const PlacesWorld = (function () {
  // --- The world, laid out once -----------------------------------------------------------
  // No coordinates in the export (World Bible ask 1), so by rule: each continent its own
  // quadrant with sea between, and inside it a fixed, seeded spring pass over the land and
  // river roads, so towns a road joins sit near each other, and each town drawn to its own
  // nation's middle so a nation is one block of land (without it the owner could not tell the
  // nations apart). Placed over EVERY city, known or not, so learning of a city never moves
  // another. Deterministic: same world, same map, every time.
  const LAID = new WeakMap();
  function worldLayout(W) {
    if (LAID.has(W)) return LAID.get(W);
    // The campaign's own stored layout (rules/hexes.py, 2026-11-19): the engine's hexes are
    // laid on it, so the board draws the towns exactly where the engine stands them, and a
    // world re-exported under the campaign moves nothing. The pass below is the same rule,
    // kept for a page with no layout sent (the tests, an older server).
    if (W.layout && W.layout.pos) { const got = { pos: W.layout.pos, centre: W.layout.centre, half: W.layout.half }; LAID.set(W, got); return got; }
    const conts = Object.keys(W.continents).sort();
    const centre = {}, R = 300;
    conts.forEach((c, k) => {
      // Four quadrants; a fifth continent and on go round a wider ring.
      const ring = Math.floor(k / 4), q = k % 4;
      centre[c] = [(q % 2 ? 1 : -1) * 380 * (1 + ring), (q < 2 ? -1 : 1) * 330 * (1 + ring)];
    });
    const byCont = {};
    W.cities.forEach(c => (byCont[c.continent] = byCont[c.continent] || []).push(c));
    const pos = {}, land = W.routes.filter(r => r.by !== "sea");
    Object.entries(byCont).forEach(([cont, list]) => {
      list.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
      const nations = [...new Set(list.map(c => c.nation))].sort();
      const [cx, cy] = centre[cont] || [0, 0], P = {};
      list.forEach((c, k) => {
        const n = nations.indexOf(c.nation), a = (n + .5) / nations.length * Math.PI * 2 + (k % 5) * .18;
        const r = R * (.35 + .12 * (k % 4));
        P[c.id] = [Math.cos(a) * r, Math.sin(a) * r];
      });
      const ids = list.map(c => c.id), here = new Set(ids);
      const byId = Object.fromEntries(list.map(c => [c.id, c]));
      const springs = land.filter(r => here.has(r.a) && here.has(r.b));
      for (let it = 0; it < 300; it++) {
        const F = Object.fromEntries(ids.map(i => [i, [0, 0]]));
        for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
          const a = P[ids[i]], b = P[ids[j]], dx = a[0] - b[0], dy = a[1] - b[1], d2 = dx * dx + dy * dy + .01, d = Math.sqrt(d2);
          const f = 2600 / d2; F[ids[i]][0] += dx / d * f; F[ids[i]][1] += dy / d * f; F[ids[j]][0] -= dx / d * f; F[ids[j]][1] -= dy / d * f;
        }
        springs.forEach(r => { const a = P[r.a], b = P[r.b], dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) + .01;
          const f = (d - 70) * .03; F[r.a][0] += dx / d * f; F[r.a][1] += dy / d * f; F[r.b][0] -= dx / d * f; F[r.b][1] -= dy / d * f; });
        const mid = {};
        ids.forEach(i => { const n = byId[i].nation, m = (mid[n] = mid[n] || [0, 0, 0]); m[0] += P[i][0]; m[1] += P[i][1]; m[2]++; });
        ids.forEach(i => { const m = mid[byId[i].nation]; F[i][0] += (m[0] / m[2] - P[i][0]) * .06; F[i][1] += (m[1] / m[2] - P[i][1]) * .06; });
        ids.forEach(i => { const p = P[i], d = Math.hypot(p[0], p[1]);
          if (d > R) { F[i][0] -= p[0] / d * (d - R) * .2; F[i][1] -= p[1] / d * (d - R) * .2; }
          p[0] += Math.max(-6, Math.min(6, F[i][0])); p[1] += Math.max(-6, Math.min(6, F[i][1])); });
      }
      ids.forEach(i => { pos[i] = [cx + P[i][0], cy + P[i][1] * .8]; });
    });
    const half = Math.max(...Object.values(pos).map(p => Math.max(Math.abs(p[0]), Math.abs(p[1])))) + 160;
    const out = { pos, centre, half };
    LAID.set(W, out);
    return out;
  }

  // --- What the player knows ---------------------------------------------------------------
  // How each city is known: stood in; a road out of a town stood in is signed for it; named by
  // someone in talk (`known.heard`, phase 5); or read on a bought map (`known.maps`, nation ids).
  function worldKnown(W, known) {
    const been = (known && known.been) || [], maps = (known && known.maps) || [], heard = (known && known.heard) || {};
    const how = {}, city = Object.fromEntries(W.cities.map(c => [c.id, c]));
    been.forEach(id => { if (city[id]) how[id] = { by: "been" }; });
    W.routes.filter(r => r.by !== "sea").forEach(r => {
      if (how[r.a] && how[r.a].by === "been" && !how[r.b] && city[r.b]) how[r.b] = { by: "road", from: r.a };
      if (how[r.b] && how[r.b].by === "been" && !how[r.a] && city[r.a]) how[r.a] = { by: "road", from: r.b };
    });
    Object.entries(heard).forEach(([id, h]) => { if (city[id] && !how[id]) how[id] = { by: "heard", who: h.who || "", line: h.line || "" }; });
    maps.forEach(n => W.cities.filter(c => c.nation === n).forEach(c => { if (!how[c.id]) how[c.id] = { by: "map", nation: n }; }));
    // A road is drawn when both ends are known; a sea passage only from a port stood in.
    const roads = W.routes.filter(r => how[r.a] && how[r.b] && (r.by !== "sea" || how[r.a].by === "been" || how[r.b].by === "been"));
    return { how, roads };
  }

  // The journey between two known cities by known roads: fewest legs, miles summed.
  function worldRoute(K, from, to) {
    const adj = {};
    K.roads.forEach(r => { (adj[r.a] = adj[r.a] || []).push([r.b, r]); (adj[r.b] = adj[r.b] || []).push([r.a, r]); });
    const came = new Map([[from, null]]), q = [from];
    while (q.length) { const c = q.shift(); if (c === to) break; (adj[c] || []).forEach(([n, r]) => { if (!came.has(n)) { came.set(n, [c, r]); q.push(n); } }); }
    if (!came.has(to) || from === to) return null;
    const legs = []; let k = to;
    while (came.get(k)) { const [c, r] = came.get(k); legs.unshift({ from: c, to: k, by: r.by, miles: r.miles }); k = c; }
    return legs;
  }

  // --- Land: one rule for every map --------------------------------------------------------
  // A blot round every city, five discs each (the mock's World paper); everything else is sea.
  function landAt(W, WL, x, y) {
    return W.cities.some((city, n) => { const p = WL.pos[city.id]; if (!p) return false;
      for (let k = 0; k < 5; k++) { const a = n * 1.7 + k * 1.26, r = 70 + (n * 37 + k * 13) % 40;
        if (Math.hypot(x - p[0] - Math.cos(a) * 30, y - p[1] - Math.sin(a) * 30) < r) return true; }
      return false; });
  }
  function nearestCity(list, WL, x, y) {
    let best = 1e18, c = null;
    list.forEach(ci => { const p = WL.pos[ci.id], d = (p[0] - x) ** 2 + (p[1] - y) ** 2; if (d < best) { best = d; c = ci; } });
    return c;
  }
  function segD(p, a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2));
    return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
  }

  // --- Nations' territory -------------------------------------------------------------------
  // Every bit of land belongs to its nearest city's nation (a Voronoi partition over the
  // cities, as Azgaar's generator partitions its cells), on an N by N grid over the World
  // sheet. Remembered per world: the world never changes in play.
  const GRIDS = new WeakMap();
  function ownerGrid(W, N = 512) {
    const held = GRIDS.get(W);
    if (held && held.N === N) return held;
    const WL = worldLayout(W), half = WL.half, cell = half * 2 / N;
    const nations = Object.keys(W.nations).sort(), owner = new Int16Array(N * N).fill(-1);
    const cities = W.cities.map(c => [WL.pos[c.id][0], WL.pos[c.id][1], nations.indexOf(c.nation)]);
    // The land, disc by disc onto the grid: the same discs as `landAt`, each marking only the
    // cells under it (testing every cell against every disc was 84 million steps on Aurvantis).
    const land = new Uint8Array(N * N);
    W.cities.forEach((city, n) => { const p = WL.pos[city.id];
      for (let k = 0; k < 5; k++) { const a = n * 1.7 + k * 1.26, r = 70 + (n * 37 + k * 13) % 40;
        const cx = p[0] + Math.cos(a) * 30, cy = p[1] + Math.sin(a) * 30;
        const i0 = Math.max(0, Math.floor((cx - r + half) / cell)), i1 = Math.min(N - 1, Math.ceil((cx + r + half) / cell));
        const j0 = Math.max(0, Math.floor((cy - r + half) / cell)), j1 = Math.min(N - 1, Math.ceil((cy + r + half) / cell));
        for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
          if (Math.hypot((i + .5) * cell - half - cx, (j + .5) * cell - half - cy) < r) land[j * N + i] = 1; } } });
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const x = (i + .5) * cell - half, y = (j + .5) * cell - half;
      if (!land[j * N + i]) continue;
      let best = 1e18, who = -1;
      for (const [cx, cy, n] of cities) { const d = (cx - x) ** 2 + (cy - y) ** 2; if (d < best) { best = d; who = n; } }
      owner[j * N + i] = who;
    }
    const got = { N, owner, nations, half, cell };
    GRIDS.set(W, got);
    return got;
  }

  // Map colouring: each nation takes the first wash none of its neighbours has (most-joined
  // first, Welsh-Powell), so two nations that touch never share a colour. Neighbours are
  // nations joined by a land or river road, or whose territories meet on the grid. Green last:
  // on the region's green hexes a green nation did not show (Sandmere Shire, in the mock).
  const NATION_WASH = ["#c98a4b", "#b8606a", "#5f86bd", "#9a7cc2", "#cfa93e", "#3f9a96", "#a8704a", "#6f9f58"];
  const COLOURS = new WeakMap();
  function neighbours(W) {
    const G = ownerGrid(W), city = Object.fromEntries(W.cities.map(c => [c.id, c]));
    const adj = Object.fromEntries(G.nations.map(n => [n, new Set()]));
    const link = (a, b) => { if (a && b && a !== b && adj[a] && adj[b]) { adj[a].add(b); adj[b].add(a); } };
    W.routes.forEach(r => { if (r.by !== "sea" && city[r.a] && city[r.b]) link(city[r.a].nation, city[r.b].nation); });
    const N = G.N, o = G.owner;
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const a = o[j * N + i]; if (a < 0) continue;
      if (i + 1 < N && o[j * N + i + 1] >= 0) link(G.nations[a], G.nations[o[j * N + i + 1]]);
      if (j + 1 < N && o[(j + 1) * N + i] >= 0) link(G.nations[a], G.nations[o[(j + 1) * N + i]]);
    }
    return adj;
  }
  function nationColours(W) {
    if (COLOURS.has(W)) return COLOURS.get(W);
    const adj = neighbours(W), ids = Object.keys(adj), k = {};
    ids.slice().sort((a, b) => adj[b].size - adj[a].size || (a < b ? -1 : 1)).forEach(i => {
      const used = new Set([...adj[i]].map(n => k[n]).filter(x => x !== undefined)); let c = 0; while (used.has(c)) c++; k[i] = c; });
    const out = Object.fromEntries(ids.map(i => [i, NATION_WASH[k[i] % NATION_WASH.length]]));
    COLOURS.set(W, out);
    return out;
  }
  const darken = (hex, f) => { const n = parseInt(hex.slice(1), 16);
    return "#" + [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * f).toString(16).padStart(2, "0")).join(""); };

  // --- Names inside their own borders -------------------------------------------------------
  // Each known nation's name goes where the whole of it lies on that nation's land (the
  // owner's rule, 2026-11-18): the deepest spots first, the "pole of inaccessibility"
  // Mapbox's polylabel finds, from a chamfer distance over the owner grid; a size smaller if
  // none fits, then the name over two lines (Undertide Warrens' wedge held no single line even
  // at the smallest size), down to a floor. Clear of every known town's pin and of the
  // continent names. `measure(text, px, spacingPx)` is the text's width in sheet pixels (a
  // canvas in the page; an estimate in the tests). A name that finds no room is reported in
  // `missed`, never lost quietly.
  function placeNames(W, K, measure, sheet = 2048) {
    const G = ownerGrid(W), WL = worldLayout(W), N = G.N, owner = G.owner, cell = sheet / N, S = sheet / (G.half * 2);
    const P = ([x, y]) => [(x + G.half) * S, (y + G.half) * S];
    const dist = new Float32Array(N * N);
    for (let k = 0; k < N * N; k++) {
      const i = k % N, j = (k / N) | 0, o = owner[k];
      dist[k] = o < 0 || i === 0 || j === 0 || i === N - 1 || j === N - 1 || owner[k - 1] !== o || owner[k + 1] !== o
        || owner[k - N] !== o || owner[k + N] !== o ? 0 : 1e9;
    }
    for (let j = 1; j < N; j++) for (let i = 1; i < N - 1; i++) { const k = j * N + i; if (dist[k]) dist[k] = Math.min(dist[k], dist[k - 1] + 1, dist[k - N] + 1, dist[k - N - 1] + 1.41, dist[k - N + 1] + 1.41); }
    for (let j = N - 2; j >= 0; j--) for (let i = N - 2; i > 0; i--) { const k = j * N + i; if (dist[k]) dist[k] = Math.min(dist[k], dist[k + 1] + 1, dist[k + N] + 1, dist[k + N + 1] + 1.41, dist[k + N - 1] + 1.41); }
    const city = Object.fromEntries(W.cities.map(c => [c.id, c]));
    const knownIds = Object.keys(K.how).filter(id => city[id]);
    const taken = knownIds.map(id => { const [x, y] = P(WL.pos[id]); return [x - 18 * S, y - 18 * S, x + 18 * S, y + 18 * S]; });
    const continents = [];
    const contSeen = new Set(knownIds.map(id => city[id].continent));
    Object.entries(WL.centre).forEach(([cid, [x, y]]) => { if (!contSeen.has(cid)) return;
      const [px, py] = P([x, y - 250]), fs = Math.round(16 * S * 3), cw = measure(W.continents[cid] || "", fs, 0);
      continents.push({ id: cid, name: W.continents[cid] || "", x: px, y: py, size: fs });
      taken.push([px - cw / 2, py - fs, px + cw / 2, py + fs * .4]); });
    const knownNations = [...new Set(knownIds.map(id => city[id].nation))].filter(n => W.nations[n]).sort();
    const placed = {}, missed = [];
    knownNations.forEach(n => {
      const me = G.nations.indexOf(n), text = String(W.nations[n].name || "").toUpperCase();
      const spots = [];
      for (let k = 0; k < N * N; k++) if (owner[k] === me && dist[k] > 1) spots.push(k);
      spots.sort((x, y) => dist[y] - dist[x]);
      const words = text.split(" "), cut = Math.ceil(words.length / 2);
      const tries = [9, 7.5, 6.2, 5, 4].map(size => [size, [text]])
        .concat(words.length > 1 ? [7.5, 6.2, 5, 4].map(size => [size, [words.slice(0, cut).join(" "), words.slice(cut).join(" ")]]) : []);
      for (const [size, lines] of tries) {
        const fs = Math.round(size * S * 3), sp = Math.round(size * .45 * S);
        const w = Math.max(...lines.map(x => measure(x, fs, sp))) + 8, h = fs * 1.15 * lines.length;
        const hw = Math.ceil(w / 2 / cell), hh = Math.ceil(h / 2 / cell);
        const inside = (ci, cj) => { for (let dj = -hh; dj <= hh; dj++) for (let di = -hw; di <= hw; di++) {
          const ii = ci + di, jj = cj + dj; if (ii < 0 || jj < 0 || ii >= N || jj >= N || owner[jj * N + ii] !== me) return false; } return true; };
        const free = (x, y) => !taken.some(b => x - w / 2 < b[2] && x + w / 2 > b[0] && y - h / 2 < b[3] && y + h / 2 > b[1]);
        const k = spots.find(k => dist[k] >= hh && inside(k % N, (k / N) | 0) && free(((k % N) + .5) * cell, (((k / N) | 0) + .5) * cell));
        if (k === undefined) continue;
        const px = ((k % N) + .5) * cell, py = (((k / N) | 0) + .5) * cell;
        taken.push([px - w / 2, py - h / 2, px + w / 2, py + h / 2]);
        placed[n] = { x: px, y: py, size: fs, spacing: sp, lines, w, h };
        return;
      }
      missed.push(n);
    });
    return { placed, missed, continents };
  }

  return { worldLayout, worldKnown, worldRoute, landAt, nearestCity, segD, ownerGrid, nationColours,
           neighbours, darken, placeNames };
})();

// The world for the maps above the town, read once from `/api/atlas` (play/atlas.py: static
// for a campaign, so not on every state; what the party knows of it is on every state, as
// `scene.known_places`). Read again when a town the party knows is not in it: another
// campaign, another world. The one part of this file that touches the network, kept out of
// 16-tab-map.js, whose walk sends nothing (the turn goes out through Say). `then` runs when
// it lands, so the map draws again.
const ATLAS = { data: null, loading: null, failed: false };
// A nation's hexes for the Region map, from `/api/hexes` (play/hex_views.py): the engine's own
// grid and ground, static for a campaign, so read once a nation. `then` draws again on landing.
const HEXES = { by: {}, loading: {}, failed: {} };
function placesHexes(nation, then) {
  if (!nation) return null;
  if (HEXES.by[nation]) return HEXES.by[nation];
  if (!HEXES.loading[nation] && !HEXES.failed[nation]) {
    HEXES.loading[nation] = fetch(`/api/hexes?nation=${encodeURIComponent(nation)}`, { cache: "no-store" })
      .then(r => readJSON(r).then(got => { if (!r.ok) throw new Error(got.error || `HTTP ${r.status}`); HEXES.by[nation] = got; }))
      .catch(err => { HEXES.failed[nation] = true; console.warn("The region's hexes did not load:", err); })
      .finally(() => { HEXES.loading[nation] = null; then(); });
  }
  return null;
}
function placesAtlas(s, then) {
  const kp = (s && s.scene && s.scene.known_places) || {};
  const d = ATLAS.data, has = id => d && Array.isArray(d.cities) && d.cities.some(c => c.id === id);
  if (d && (kp.been || []).every(has)) return d;
  if (!ATLAS.loading && !ATLAS.failed) {
    ATLAS.loading = fetch("/api/atlas", { cache: "no-store" })
      .then(r => readJSON(r).then(got => { if (!r.ok) throw new Error(got.error || `HTTP ${r.status}`); ATLAS.data = got; HEXES.by = {}; HEXES.failed = {}; }))
      .catch(err => { ATLAS.failed = true; console.warn("The atlas did not load; the town map only:", err); })
      .finally(() => { ATLAS.loading = null; then(); });
  }
  return null;
}

// Hex travel on the Region (rules/hexes.py, play/hex_views.py): the engine's `hex_move` for a
// lit hex pressed on the board or its button in the slip, the Perception die the player's own
// through the same popup an excursion's uses, and the table drawn again from the state the
// move left. `hexEnter` goes into the spotted site underfoot.
const HEXGO = { busy: false };
function hexMove(q, r) { return hexAct("/api/hex/move", { hex: [q, r] }); }
function hexEnter() { return hexAct("/api/hex/enter", {}); }
async function hexAct(url, body) {
  if (HEXGO.busy) return;
  HEXGO.busy = true;
  busy(true);
  try {
    let d = await post(url, body);
    if (d.roll) {
      busy(false);
      const p = d.roll, bd = p.breakdown || [];
      const terms = bd.map(m => ({ label: m.source, value: sign(m.value) }));
      if (bd.length !== 1) terms.push({ label: "your modifier", value: sign(p.modifier), total: true });
      let face = await Dice3D.ask({ hold: true, title: p.label, why: p.because || "", sides: 20, lo: 1, hi: 20, die: "1d20", terms });
      if (face == null) { try { face = (await post("/api/roll/face", {})).face; } catch { face = null; } }
      const landed = face != null ? Dice3D.land({ title: p.label, why: p.because || "", die: "1d20", sides: 20, lo: 1, hi: 20, result: face, terms }) : null;
      busy(true);
      try { d = await post(url, { face: face == null ? "auto" : face }); }
      catch (err) { Dice3D.close(); throw err; }
      finally { busy(false); }
      if (landed) await landed; else Dice3D.close();
    }
    render(await getState());
  } catch (err) {
    const e = document.getElementById("err"); if (e) e.textContent = err.message;
  } finally { busy(false); HEXGO.busy = false; }
}
