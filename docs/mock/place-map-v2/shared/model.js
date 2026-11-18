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
    const [town, region, site] = await Promise.all([get("town.json"), get("region.json"), get("site.json")]);
    return { town, region, site };
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
  const SLOTS = [[C - 5, -1], [C - 5, 1], [C + 85, -1], [C + 85, 1], [C + 170, -1], [C + 170, 1],
                 [C + 255, -1], [C + 255, 1]];  // [along the street, side]
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
      gates.forEach(g => { pos[g] = [dx * GATE, dy * GATE]; kind[g] = "gate"; street[g] = c; label[g] = "right"; });
      rest.forEach((i, k) => {
        const [a, side] = SLOTS[k % SLOTS.length];
        pos[i] = [dx * a + nx * side * ACROSS, dy * a + ny * side * ACROSS];
        kind[i] = "place"; street[i] = c;
        // A name hangs away from its street: out to the side for a north/south street,
        // above or below for an east/west one, so names on facing slots never meet.
        label[i] = dx === 0 ? (nx * side > 0 ? "right" : "left") : (ny * side > 0 ? "below" : "above");
      });
    });
    bySquare.sort().forEach((i, k) => {
      const a = (45 + 90 * (k % 4) + 28 * Math.floor(k / 4)) * Math.PI / 180, r = 112 + 26 * Math.floor(k / 4);
      pos[i] = [Math.cos(a) * r, Math.sin(a) * r]; kind[i] = "place"; street[i] = square;
      label[i] = Math.cos(a) > 0 ? "right" : "left";
    });
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
    return { pos, kind, street, floors, label, square, crossings, gate, sites, roadsOut };
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

  return { load, fog, route, townLayout, anchor, regionLayout, siteLayout, siteRoute, sites, light,
           clockWords, selfCheck, bare, upper, tail, baseOf, floorOf };
})();
