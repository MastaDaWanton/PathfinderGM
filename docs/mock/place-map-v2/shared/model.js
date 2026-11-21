// Place map v2 mocks: the shared model. Plain JS, one global (MapModel), no build step.
//
// Everything here is read off data/*.json, which export.py takes from the engine itself
// (play/places_found.chart() and exits.ways_from over a COPY of the owner's jack save,
// stood in Featherperch's inn; frag's founded sewers for the Site map). Nothing invented.
//
// The game asks the engine for the fog on every state. A mock has no engine, so it
// replays the same two rules in the page from the exported exits rows:
//   * fog (places_found.chart): every place stood in, plus one way beyond each of them;
//   * route (places_found.route): breadth-first through places stood in, never by a
//     journey, never by a shut way.
// selfCheck() compares the replay with chart()'s own answer on the first state.
const MapModel = (() => {
  const bare = s => String(s || "").replace(/^the /i, "");
  const upper = s => (s = String(s || "")) ? s[0].toUpperCase() + s.slice(1) : s;
  const tail = id => String(id).split("~")[1] || String(id);
  const baseOf = id => String(id).replace(/\^-?\d+$/, "");
  const floorOf = id => { const m = /\^(-?\d+)$/.exec(id); return m ? +m[1] : 0; };

  async function load(root = "data/") {
    const get = f => fetch(root + f).then(r => { if (!r.ok) throw new Error(f + " " + r.status); return r.json(); });
    const [town, region, site, world] = await Promise.all([get("town.json"), get("region.json"), get("site.json"), get("world.json")]);
    return { town, region, site, world };
  }

  // --- Fog (places_found.chart, replayed) ----------------------------------------------
  function fog(T, been, here) {
    const known = new Set(T.ids);
    const visited = been.filter(p => known.has(p));
    if (!visited.includes(here)) visited.push(here);
    const V = new Set(visited), seen = [];
    visited.forEach(p => (T.ways[p] || []).forEach(r => {
      if (!r.journey && known.has(r.id) && !V.has(r.id) && !seen.includes(r.id)) seen.push(r.id);
    }));
    const S = new Set(seen), roads = [], stubs = [];
    visited.forEach(p => (T.ways[p] || []).forEach(r => { if (r.journey) roads.push({ from: p, ...r }); }));
    seen.forEach(p => (T.ways[p] || []).forEach(r => {
      if (!V.has(r.id)) stubs.push({ from: p, to: r.journey ? null : r.id, dashed: r.group !== "next_door" });
    }));
    return { visited: V, seen: S, found: new Set([...visited, ...seen]), roads, stubs, here };
  }

  // --- Route (places_found.route, replayed) --------------------------------------------
  function route(ways, been, start, to) {
    const search = throughShut => {
      const came = new Map([[start, null]]), q = [start];
      while (q.length) {
        const cur = q.shift();
        if (cur === to) break;
        if (!been.has(cur)) continue;
        for (const r of ways[cur] || []) {
          if (r.journey || came.has(r.id) || (r.blocked && !throughShut)) continue;
          came.set(r.id, [cur, r]); q.push(r.id);
        }
      }
      if (!came.has(to)) return null;
      const legs = []; let k = to;
      while (came.get(k)) { const [cur, r] = came.get(k); legs.push({ from: cur, to: r.id, name: r.name,
        time_words: r.time_words, minutes: r.minutes, blocked: r.blocked }); k = cur; }
      return legs.reverse();
    };
    const open = search(false);
    if (open) return { legs: open, minutes: open.reduce((s, l) => s + l.minutes, 0), why: "" };
    const shut = search(true);
    return { legs: [], minutes: 0, why: shut ? shut.find(l => l.blocked).blocked : "No way there by the ways you know." };
  }

  // --- The town, laid out by rule ------------------------------------------------------
  // Not physics: the great square in the middle, the four crossings at their compass
  // points, each place in a fixed slot on its street (slots are dealt over EVERY place the
  // town has, found or not, sorted by id, so a place never moves when more is found),
  // the gate at the end of its street, floors as badges, the land outside beyond the gate.
  const DIRS = { north: [0, -1], east: [1, 0], south: [0, 1], west: [-1, 0] };
  const C = 190;                               // square to crossing
  // Seats come in pairs, one each side of the street, a row every ROW further out. A street
  // never runs out: a ninth place is a fifth row, not a seat dealt again on top of the first
  // (the worst case caught `k % 8` stacking places 9-16 on 1-8). Places are founded in play,
  // so a street's length is unbounded; only the town changing can lengthen it.
  const ROW = 85, slot = k => [C - 5 + ROW * Math.floor(k / 2), k % 2 ? 1 : -1];
  const ACROSS = 82, GATE = C + 195;
  function townLayout(T) {
    const ids = T.ids, set = new Set(ids), setting = T.settings;
    const urban = ids.filter(i => setting[i] === "in" && !floorOf(i));
    const square = urban.find(i => /great-square$/.test(i)) || urban[0];
    const crossings = {};
    urban.forEach(i => { const m = /(north|east|south|west)-crossing$/.exec(i); if (m) crossings[m[1]] = i; });
    const dirOf = Object.fromEntries(Object.entries(crossings).map(([d, i]) => [i, d]));
    const links = i => (T.ways[i] || []).filter(r => !r.journey && set.has(r.id)).map(r => r.id);
    const pos = {}, kind = {}, street = {}, floors = {}, label = {};
    pos[square] = [0, 0]; kind[square] = "square"; label[square] = "below";
    Object.entries(crossings).forEach(([d, i]) => {
      const [dx, dy] = DIRS[d]; pos[i] = [dx * C, dy * C]; kind[i] = "crossing"; street[i] = square;
      label[i] = d === "north" || d === "south" ? "right" : "above";
    });
    const bySquare = [], byCrossing = {};
    urban.forEach(i => {
      if (pos[i]) return;
      const ls = links(i), cross = ["north", "east", "south", "west"].map(d => crossings[d]).find(c => c && ls.includes(c));
      if (cross) (byCrossing[cross] = byCrossing[cross] || []).push(i);
      else bySquare.push(i);
    });
    Object.entries(byCrossing).forEach(([c, list]) => {
      const [dx, dy] = DIRS[dirOf[c]], nx = -dy, ny = dx;
      const gates = list.filter(i => /gate$/.test(i)), rest = list.filter(i => !gates.includes(i)).sort();
      const end = Math.max(GATE, slot(Math.max(rest.length - 1, 0))[0] + 90);  // the gate past the last row
      gates.forEach(g => { pos[g] = [dx * end, dy * end]; kind[g] = "gate"; street[g] = c; label[g] = "right"; });
      rest.forEach((i, k) => {
        const [a, side] = slot(k);
        pos[i] = [dx * a + nx * side * ACROSS, dy * a + ny * side * ACROSS];
        kind[i] = "place"; street[i] = c;
        // A name hangs away from its street: out to the side for a north/south street,
        // above or below for an east/west one, so names on facing slots never meet.
        label[i] = dx === 0 ? (nx * side > 0 ? "right" : "left") : (ny * side > 0 ? "below" : "above");
      });
    });
    // Round the square: with crossings, only on the diagonals between the four streets, a ring
    // further out for every four; without (48 of Aurvantis's 64 towns have none), eight a ring.
    // Measured 2026-11-18: the old ring (28 degrees round, 26 further out) put a town's tenth
    // place 56 units from a street seat.
    const per = Object.keys(crossings).length ? 4 : 8;
    bySquare.sort().forEach((i, k) => {
      const ring = Math.floor(k / per), a = ((per === 4 ? 45 + 90 * (k % 4) : 22.5 + 45 * (k % 8)) + (ring % 2) * (per === 4 ? 0 : 22.5)) * Math.PI / 180;
      const r = 112 + (per === 4 ? 62 : 72) * ring;
      pos[i] = [Math.cos(a) * r, Math.sin(a) * r]; kind[i] = "place"; street[i] = square;
      label[i] = Math.cos(a) > 0 ? "right" : "left";
    });
    // The wall goes round every seat, however long a street has grown.
    const wall = Math.max(GATE, ...urban.filter(i => pos[i]).map(i => Math.hypot(...pos[i]) + 50));
    ids.filter(floorOf).forEach(i => { const b = baseOf(i); if (pos[b]) (floors[b] = floors[b] || []).push(i); });

    // Outside the walls: beyond the first gate, the outskirts, the crossroads and the roads.
    const gate = Object.keys(kind).find(i => kind[i] === "gate");
    const [gx, gy] = gate ? pos[gate] : [0, -GATE];
    const out = [gx === 0 ? 0 : Math.sign(gx), gy === 0 ? 0 : Math.sign(gy)];
    const at = (d, side = 0) => [gx + out[0] * d - out[1] * side, gy + out[1] * d + out[0] * side];
    const outside = ids.filter(i => setting[i] === "outside");
    const roadsOut = [], signs = [];
    outside.forEach(i => {
      const t = tail(i);
      if (/@the-outskirts$/.test(t)) { pos[i] = at(66); kind[i] = "apron"; label[i] = "right"; }
      else if (/@the-crossroads$/.test(t)) { pos[i] = at(122); kind[i] = "apron"; label[i] = "right"; }
      else if (/@the-road-to-/.test(t)) roadsOut.push(i);
      else if (/^underground:/.test(t)) { kind[i] = "under"; }
      else signs.push(i);
    });
    roadsOut.sort().forEach((i, k, all) => {
      const s = (k - (all.length - 1) / 2) * 150;
      pos[i] = at(196, s); kind[i] = "roadhead"; label[i] = "above";
    });
    signs.sort().forEach((i, k) => { pos[i] = at(96, (k % 2 ? 1 : -1) * (250 + 40 * Math.floor(k / 2))); kind[i] = "sign"; label[i] = "below"; });
    // A dungeon or cave under a place: its rooms are ids beneath it (woods/the-cave/the-mouth).
    const sites = {};
    ids.filter(i => kind[i] === "under").forEach(i => {
      const t = tail(i).replace(/^underground:/, ""), parts = t.split("/");
      if (parts.length === 2) {
        const host = ids.find(h => tail(h).endsWith("@" + parts[0]) || tail(h).endsWith(":" + parts[0]));
        if (host) sites[host] = { id: i, rooms: ids.filter(r => r.startsWith(i)) };
      }
    });
    return { pos, kind, street, floors, label, square, crossings, gate, sites, roadsOut, wall };
  }
  // Where a place is drawn: a floor at its building, a cave room at its host.
  function anchor(L, id) {
    if (L.pos[id]) return L.pos[id];
    if (L.pos[baseOf(id)]) return L.pos[baseOf(id)];
    for (const [host, s] of Object.entries(L.sites)) if (id.startsWith(s.id)) return L.pos[host];
    return null;
  }

  // --- The region: settlements a journey apart, the wild places about Featherperch ------
  // The world gives no coordinates, so this is laid by rule too: the town you are in at
  // the middle, each journey out at a fixed bearing (sorted by id) and a length that
  // grows with its days; one journey beyond a town you have been is the fog's edge.
  function regionLayout(R, T, visitedTowns) {
    const towns = Object.fromEntries(R.towns.map(t => [t.id, t]));
    const adj = {};
    R.roads.forEach(r => { (adj[r.a] = adj[r.a] || []).push(r); (adj[r.b] = adj[r.b] || []).push(r); });
    const other = (r, id) => (r.a === id ? r.b : r.a);
    const isSea = r => r.by === "sea";  // a river passage is drawn: it has a length
    const land = id => (adj[id] || []).filter(r => !isSea(r)), sea = id => (adj[id] || []).filter(isSea);
    const pos = { [R.here]: [0, 0] }, from = {};
    const scale = d => 60 + d * 30;
    // Land journeys at bearings; a sea passage does not draw a line across the board (the
    // export gives it no length worth drawing: `days_apart` 1 is the derived default), so
    // the ports a harbour sails to are listed at the board's edge instead.
    const out = land(R.here).map(r => other(r, R.here)).sort();
    out.forEach((id, k) => {
      const r = land(R.here).find(x => other(x, R.here) === id);
      const a = (-135 + k * (360 / Math.max(out.length, 1))) * Math.PI / 180;
      pos[id] = [Math.cos(a) * scale(r.days), Math.sin(a) * scale(r.days) * .8]; from[id] = R.here;
    });
    const hubs = out.slice().sort((x, y) => visitedTowns.has(y) - visitedTowns.has(x));
    hubs.forEach(hub => {
      const next = land(hub).map(r => other(r, hub)).filter(i => !pos[i]).sort();
      const [hx, hy] = pos[hub], base = Math.atan2(hy, hx), step = Math.min(.55, 2.2 / Math.max(next.length, 1));
      next.forEach((id, k) => {
        const r = land(hub).find(x => other(x, hub) === id);
        const a = base + (k - (next.length - 1) / 2) * step;
        pos[id] = [hx + Math.cos(a) * scale(Math.min(r.days, 6)), hy + Math.sin(a) * scale(Math.min(r.days, 6)) * .8];
        from[id] = hub;
      });
    });
    const shown = new Set(Object.keys(pos).filter(id => visitedTowns.has(id)
      || [...visitedTowns].some(v => land(v).some(r => other(r, v) === id))));
    const roads = R.roads.filter(r => !isSea(r) && shown.has(r.a) && shown.has(r.b));
    const harbours = [...visitedTowns].filter(v => sea(v).length && pos[v])
      .map(v => ({ id: v, ports: sea(v).map(r => other(r, v)).sort((x, y) => towns[x].name.localeCompare(towns[y].name)) }));
    // Featherperch's wild ground, from its exits rows: walked in hours, not days.
    const wild = [];
    const slots = { woods: [0, -80], desert: [104, 0], cave: [0, -146] };  // on the axes: the roads leave on the diagonals
    T.ids.filter(i => T.settings[i] === "outside" && /(@the-woods|@the-desert|the-woods\/the-cave)$/.test(tail(i)))
      .forEach(i => { const k = /cave$/.test(i) ? "cave" : /desert$/.test(i) ? "desert" : "woods";
                      wild.push({ id: i, kind: k, name: T.names[i], pos: slots[k] }); });
    return { towns, pos, from, shown, roads, wild, adj, harbours };
  }

  // --- A site: rooms on a grid, passages between ------------------------------------------
  // Darkest Dungeon's corridor map: a room is a box on a grid, joined by passages. Depth
  // in the room tree is the column, order among siblings the row; unexplored rooms blank.
  function siteLayout(rooms) {
    const byId = Object.fromEntries(rooms.map(r => [r.id, r]));
    const root = rooms.find(r => !byId[r.parent]) || rooms[0];
    const kids = {};
    rooms.forEach(r => { if (byId[r.parent]) (kids[r.parent] = kids[r.parent] || []).push(r.id); });
    const col = {}, row = {}, rowsAt = {};
    let nextRow = 0;
    const place = (id, d) => {
      col[id] = d;
      const ks = (kids[id] || []).slice().sort();
      if (!ks.length) { row[id] = nextRow++; return row[id]; }
      const rs = ks.map(k => place(k, d + 1));
      row[id] = (Math.min(...rs) + Math.max(...rs)) / 2;
      return row[id];
    };
    place(root.id, 0);
    const passages = [];
    rooms.forEach(r => {
      if (byId[r.parent]) passages.push([r.parent, r.id]);
      (r.exits || []).forEach(x => { if (byId[x] && !passages.some(p => p.includes(r.id) && p.includes(x))) passages.push([r.id, x, "side"]); });
    });
    const adj = {};
    passages.forEach(([a, b]) => { (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a); });
    return { root: root.id, col, row, passages, adj, rows: nextRow, cols: Math.max(...Object.values(col)) + 1 };
  }
  function siteRoute(S, been, from, to) {
    const came = new Map([[from, null]]), q = [from];
    while (q.length) { const c = q.shift(); if (c === to) break; if (!been.has(c)) continue;
      (S.adj[c] || []).forEach(n => { if (!came.has(n)) { came.set(n, c); q.push(n); } }); }
    if (!came.has(to)) return null;
    const p = [to]; while (came.get(p[0])) p.unshift(came.get(p[0]));
    return p;
  }
  // The two sites the mocks can open: Featherperch's own cave (real fog: the cave stood in,
  // its mouth and throat only seen) and frag's sewers (a whole founded dungeon).
  function sites(D) {
    const T = D.town, out = {};
    const cave = T.ids.find(i => /the-woods\/the-cave$/.test(i));
    if (cave) {
      const rooms = T.ids.filter(i => i.startsWith(cave)).map(i => ({ id: i, name: T.names[i],
        parent: i === cave ? "" : i.split("/").slice(0, -1).join("/"), exits: [], about: "", role: i === cave ? "entrance" : "room" }));
      out.cave = { key: "cave", name: "the cave", from: "Featherperch's woods (jack's save)", rooms,
                   been: new Set(T.been.filter(i => i.startsWith(cave))), here: null, host: T.ids.find(i => /@the-woods$/.test(i)) };
    }
    const f = D.site.founded.filter(x => x.id.includes("the-sewers"));
    if (f.length) {
      out.sewers = { key: "sewers", name: "the sewers", from: "under the well (frag's save, another town)",
        rooms: f.map(x => ({ id: x.id, name: x.name, parent: x.parent, exits: x.exits, about: x.about,
                              role: (x.dungeon || {}).role || (x.deeper ? "way down" : "passage"),
                              stock: (x.dungeon || {}).stock || "", door: ((x.dungeon || {}).door || {}).state || "" })),
        been: new Set(D.site.been.filter(i => i.includes("the-sewers"))), here: D.site.at,
        concept: (f.find(x => x.deeper) || {}).deeper };
    }
    return out;
  }


  // --- The world ------------------------------------------------------------------------
  // Every city the world has, placed ONCE over the whole road graph so learning of a city
  // never moves another. No coordinates in the export (World Bible ask), so by rule: each
  // continent its own quadrant with sea between ("continents are separated by water"), and
  // inside it a fixed, seeded spring pass over the land and river roads, so towns a road
  // joins sit near each other. Deterministic: same world, same map, every time.
  let WORLD_LAID = null;
  function worldLayout(W) {
    if (WORLD_LAID && WORLD_LAID.W === W) return WORLD_LAID;
    const conts = Object.keys(W.continents).sort();
    const centre = {}, R = 300;
    conts.forEach((c, k) => { centre[c] = [(k % 2 ? 1 : -1) * 380, (k < 2 ? -1 : 1) * 330]; });
    const byCont = {};
    W.cities.forEach(c => (byCont[c.continent] = byCont[c.continent] || []).push(c));
    const pos = {}, land = W.routes.filter(r => r.by !== "sea");
    Object.entries(byCont).forEach(([cont, list]) => {
      list.sort((a, b) => a.id.localeCompare(b.id));
      const nations = [...new Set(list.map(c => c.nation))].sort();
      const [cx, cy] = centre[cont] || [0, 0], P = {};
      list.forEach((c, k) => {   // seed: nation sectors, cities fanned inside them
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
        // Cohesion: each town is drawn to its own nation's middle, so a nation is one block
        // of land. Without it, roads across borders mixed the towns and the territories came
        // out a patchwork (the owner could not tell the nations apart).
        const mid = {};
        ids.forEach(i => { const n = byId[i].nation, m = (mid[n] = mid[n] || [0, 0, 0]); m[0] += P[i][0]; m[1] += P[i][1]; m[2]++; });
        ids.forEach(i => { const m = mid[byId[i].nation]; F[i][0] += (m[0] / m[2] - P[i][0]) * .06; F[i][1] += (m[1] / m[2] - P[i][1]) * .06; });
        ids.forEach(i => { const p = P[i], d = Math.hypot(p[0], p[1]);
          if (d > R) { F[i][0] -= p[0] / d * (d - R) * .2; F[i][1] -= p[1] / d * (d - R) * .2; }   // stay on the continent
          p[0] += Math.max(-6, Math.min(6, F[i][0])); p[1] += Math.max(-6, Math.min(6, F[i][1])); });
      }
      ids.forEach(i => { pos[i] = [cx + P[i][0], cy + P[i][1] * .8]; });
    });
    return (WORLD_LAID = { W, pos, centre });
  }
  // What the PC knows of the world, and how: stood in it; a road sign out of a town stood in
  // (the region's own fog rule); named by someone in conversation; or read on a map.
  // `maps` is a list of nation ids whose map was read (a proposed item: none exists yet).
  function worldKnown(W, been, maps = []) {
    const how = {}, city = Object.fromEntries(W.cities.map(c => [c.id, c]));
    been.forEach(id => { if (city[id]) how[id] = { by: "been" }; });
    W.routes.filter(r => r.by !== "sea").forEach(r => {
      if (how[r.a] && how[r.a].by === "been" && !how[r.b]) how[r.b] = { by: "road", from: r.a };
      if (how[r.b] && how[r.b].by === "been" && !how[r.a]) how[r.a] = { by: "road", from: r.b };
    });
    Object.entries(W.heard || {}).forEach(([id, h]) => { if (!how[id]) how[id] = { by: "heard", who: h.who, line: h.line }; });
    maps.forEach(n => W.cities.filter(c => c.nation === n).forEach(c => { if (!how[c.id]) how[c.id] = { by: "map", nation: n }; }));
    // Roads: drawn when both ends are known; a sea passage only from a port you have been to.
    const roads = W.routes.filter(r => how[r.a] && how[r.b] && (r.by !== "sea" || how[r.a].by === "been" || how[r.b].by === "been"));
    return { how, roads };
  }
  // The journey between two known cities by known roads: fewest legs, miles summed.
  function worldRoute(W, known, from, to) {
    const adj = {};
    known.roads.forEach(r => { (adj[r.a] = adj[r.a] || []).push([r.b, r]); (adj[r.b] = adj[r.b] || []).push([r.a, r]); });
    const came = new Map([[from, null]]), q = [from];
    while (q.length) { const c = q.shift(); if (c === to) break; (adj[c] || []).forEach(([n, r]) => { if (!came.has(n)) { came.set(n, [c, r]); q.push(n); } }); }
    if (!came.has(to)) return null;
    const legs = []; let k = to; while (came.get(k)) { const [c, r] = came.get(k); legs.unshift({ from: c, to: k, by: r.by, miles: r.miles }); k = c; }
    return legs;
  }

  // --- Nation colours ---------------------------------------------------------------------
  // Map colouring: each nation takes the first wash none of its neighbours has, so two nations
  // that touch never share a colour. Neighbours are nations joined by a land or river road,
  // or with towns close together on the same continent (where the world map's territories
  // meet). Same answer on the region and the world, so a nation keeps its colour on both.
  // Green last: on the region's green hexes a green nation did not show (Sandmere Shire).
  const NATION_WASH = ["#c98a4b", "#b8606a", "#5f86bd", "#9a7cc2", "#cfa93e", "#3f9a96", "#a8704a", "#6f9f58"];
  function nationColours(W) {
    if (W._colours) return W._colours;
    const L = worldLayout(W), city = Object.fromEntries(W.cities.map(c => [c.id, c]));
    const ids = Object.keys(W.nations).sort((a, b) => W.nations[a].name.localeCompare(W.nations[b].name));
    const adj = Object.fromEntries(ids.map(i => [i, new Set()]));
    const link = (a, b) => { if (a && b && a !== b && adj[a] && adj[b]) { adj[a].add(b); adj[b].add(a); } };
    W.routes.forEach(r => { if (r.by !== "sea" && city[r.a] && city[r.b]) link(city[r.a].nation, city[r.b].nation); });
    for (let i = 0; i < W.cities.length; i++) for (let j = i + 1; j < W.cities.length; j++) {
      const a = W.cities[i], b = W.cities[j];
      if (a.continent === b.continent && Math.hypot(L.pos[a.id][0] - L.pos[b.id][0], L.pos[a.id][1] - L.pos[b.id][1]) < 140) link(a.nation, b.nation);
    }
    const k = {};
    ids.slice().sort((a, b) => adj[b].size - adj[a].size || a.localeCompare(b)).forEach(i => {   // most-connected first (Welsh-Powell)
      const used = new Set([...adj[i]].map(n => k[n]).filter(x => x !== undefined)); let c = 0; while (used.has(c)) c++; k[i] = c; });
    return (W._colours = Object.fromEntries(ids.map(i => [i, NATION_WASH[k[i] % NATION_WASH.length]])));
  }
  const darken = (hex, f) => { const n = parseInt(hex.slice(1), 16); return "#" + [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * f).toString(16).padStart(2, "0")).join(""); };

  // --- The worst case (made up) -----------------------------------------------------------
  // Invented data shaped exactly like the export, entering at the same door (the loaded data),
  // never by editing the drawing. Every value is one a long campaign could produce: places are
  // founded in play (houses called on, ventures), so a street's length is unbounded; names
  // are the world's own patterns at their longest; a map read can reveal a whole world.
  function worstCase(D) {
    const T = JSON.parse(JSON.stringify(D.town)), W = JSON.parse(JSON.stringify(D.world));
    const pre = T.here.split("~")[0] + "~";
    const north = T.ids.find(i => /north-crossing$/.test(i)), square = T.ids.find(i => /great-square$/.test(i));
    const west = T.ids.find(i => /west-crossing$/.test(i));
    const way = (id, name, minutes = 8, group = "next_door") => ({ id, name, group, time_words: minutes < 10 ? "a few minutes' walk" : "a quarter of an hour", blocked: "", journey: false, minutes });
    const add = (slug, name, on, been, setting = "in") => {
      const id = pre + (setting === "in" ? "urban:" : "forest:@") + slug;
      T.ids.push(id); T.names[id] = name; T.settings[id] = setting;
      T.ways[id] = on ? [way(on, T.names[on])] : [];
      if (on) T.ways[on] = (T.ways[on] || []).concat(way(id, name));
      if (been) T.been.push(id);
      return id;
    };
    // Eleven more off the north crossing (sixteen on one street), some only seen.
    ["the house of Aleksandra Wiśniewska-Kowalczyk", "the counting house of the Honourable Company of Lamplighters and Chandlers",
     "Jo's", "the house of Bartholomew Fitzgerald-Montgomery III", "the chandlery", "the old customs house where the river toll was once taken",
     "the house of Ünsal the Twice-Drowned", "the tannery", "the house of the widow Mæve", "the bathhouse", "the ropewalk"]
      .forEach((n, k) => add("wc-north-" + k, n, north, k % 3 !== 2));
    // Six more round the great square: nine there.
    ["the shrine of the Lantern-Bearer of the Seventh Hour", "the stocks", "the moneychanger's", "the scriveners' hall",
     "the house of Iolanthe Brightwater-Vey", "the cooper's"].forEach((n, k) => add("wc-square-" + k, n, square, k % 2 === 0));
    // A tower of seven storeys and two cellars on the west street.
    const tower = add("wc-tower", "the Tower of the Unquiet Astronomers", west, true);
    for (let f = 1; f <= 6; f++) { const id = tower + "^" + f; T.ids.push(id); T.names[id] = "floor " + f; T.settings[id] = "in"; }
    [-1, -2].forEach(f => { const id = tower + "^" + f; T.ids.push(id); T.names[id] = "cellar"; T.settings[id] = "in"; });
    // Seven more roads out: eleven road heads past the gate.
    const cross = T.ids.find(i => /@the-crossroads$/.test(i));
    ["Saint-Aubin-de-la-Haute-Mer-sur-les-Falaises", "Ys", "Thornwick-under-Hollow", "Greywater Ford", "Kharzun-Deep",
     "the Pilgrim Stair", "Old Vellacourt"].forEach((n, k) => {
      const id = add("the-road-to-wc" + k, "the road to " + n, cross, k < 4, "outside");
      T.ways[id].push({ id: "wc-town-" + k, name: "the road to " + n, group: "road", time_words: "about " + ["nine", "two", "eleven", "four", "twenty", "six", "three"][k] + " days on foot", blocked: "", journey: true, minutes: 0 });
    });
    T.ids.sort();
    T.worst = true;
    // The world: every city known by a map read, two of the names at the export's longest.
    W.cities[3].name = "Saint-Aubin-de-la-Haute-Mer-sur-les-Falaises"; W.cities[9].name = "Ys";
    W.worstMaps = Object.keys(W.nations);
    return { ...D, town: T, world: W, worst: true };
  }

  // --- The game clock -------------------------------------------------------------------
  // 0 at midnight; the light the maps tint by: dawn warm, day clear, dusk amber, night blue.
  function light(h) {
    const k = [[0, [40, 60, 120, .5]], [5, [50, 60, 120, .45]], [6.5, [255, 170, 110, .22]], [8.5, [255, 230, 190, .05]],
               [16, [255, 230, 190, .05]], [18.5, [255, 140, 70, .24]], [20, [60, 60, 130, .42]], [24, [40, 60, 120, .5]]];
    let i = 0; while (i < k.length - 2 && h >= k[i + 1][0]) i++;
    const [h0, a] = k[i], [h1, b] = k[i + 1], t = (h - h0) / (h1 - h0 || 1);
    const c = a.map((v, j) => v + (b[j] - v) * t);
    return { r: c[0] | 0, g: c[1] | 0, b: c[2] | 0, a: c[3], night: h < 6 || h >= 19.5, dark: c[3] };
  }
  const clockWords = m => { const h = Math.floor(m / 60) % 24, mm = m % 60;
    return `${((h + 11) % 12) + 1}:${String(mm).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`; };

  // The replay must agree with the engine's own chart on the first state, or the mock is
  // drawing something the game would not.
  function selfCheck(T) {
    const F = fog(T, T.been, T.here), errs = [];
    if (F.found.size !== T.found) errs.push(`found ${F.found.size} vs chart ${T.found}`);
    if (F.visited.size !== T.visited) errs.push(`visited ${F.visited.size} vs chart ${T.visited}`);
    T.nodes.forEach(n => {
      if (n.current) return;
      const r = route(T.ways, F.visited, T.here, n.id);
      if ((n.walk ? n.walk.minutes : 0) !== r.minutes) errs.push(`${n.name}: ${r.minutes} vs ${n.walk && n.walk.minutes}`);
    });
    if (errs.length) console.warn("MapModel self-check:", errs); else console.info("MapModel self-check: replay matches chart()");
    return errs;
  }

  return { load, fog, route, townLayout, anchor, regionLayout, siteLayout, siteRoute, sites, light, worldLayout, worldKnown, worldRoute, worstCase, nationColours, darken,
           clockWords, selfCheck, bare, upper, tail, baseOf, floorOf };
})();
