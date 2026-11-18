// Style 2, the isometric diorama: Townscaper / Dorfromantik's little world on tiles, in
// plain canvas 2D. The same model and rules as the chart (shared/); this file only draws.
// The town is turned 45° into isometric, so north is up and to the left (the rose says so).
const DioramaRenderer = (() => {
  const M = MapModel, C = Math.SQRT1_2;
  let stage, api, cv, cx, tags, V = null, s = .8, ox = 0, oy = 0, dpr = 1, raf = 0, t0 = performance.now();
  let staticLayer = null, staticKey = "", hits = [], walkers = [], token = null, lift = [], drops = [];
  const WARD = { north: "#c98f4b", east: "#6f9a5e", south: "#b9645a", west: "#5f7fa6", square: "#c9a64f" };

  // --- Projection -------------------------------------------------------------------------
  const iso = (x, y, z = 0) => [((x - y) * C) * s + ox, ((x + y) * C * .5) * s - z * s + oy];

  function init(el, a) {
    stage = el; api = a;
    stage.innerHTML = `<canvas class="surface" aria-hidden="true"></canvas><div class="tags"></div>`;
    cv = stage.querySelector("canvas"); cx = cv.getContext("2d"); tags = stage.querySelector(".tags");
    let down = null, moved = false;
    cv.addEventListener("pointerdown", ev => { down = [ev.clientX, ev.clientY, ox, oy]; moved = false; cv.setPointerCapture(ev.pointerId); });
    cv.addEventListener("pointermove", ev => { if (!down) { hover(ev); return; }
      const dx = ev.clientX - down[0], dy = ev.clientY - down[1];
      if (Math.hypot(dx, dy) > 4) moved = true;
      if (moved) { ox = down[2] + dx; oy = down[3] + dy; staticKey = ""; } });
    cv.addEventListener("pointerup", ev => { if (down && !moved) click(ev); down = null; });
    cv.addEventListener("wheel", ev => { ev.preventDefault();
      const r = cv.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top, f = Math.exp(-ev.deltaY * .0012);
      const ns = Math.min(Math.max(s * f, .3), 2.4), k = ns / s;
      ox = mx - (mx - ox) * k; oy = my - (my - oy) * k; s = ns; staticKey = ""; }, { passive: false });
    new ResizeObserver(() => { size(); staticKey = ""; }).observe(stage);
    size(); loop();
  }
  function size() {
    const r = stage.getBoundingClientRect(); dpr = Math.min(devicePixelRatio || 1, 2);
    cv.width = Math.max(1, r.width * dpr); cv.height = Math.max(1, r.height * dpr);
    cv.style.width = r.width + "px"; cv.style.height = r.height + "px";
  }
  function click(ev) {
    const r = cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    let best = null, bd = 30;
    hits.forEach(h => { const d = Math.hypot(h.x - x, h.y - y); if (d < bd) { bd = d; best = h; } });
    if (best) api.pick(best.id);
  }
  function hover(ev) {
    const r = cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    cv.style.cursor = hits.some(h => Math.hypot(h.x - x, h.y - y) < 30) ? "pointer" : "grab";
  }

  // --- The scene of each map: tiles, things on them, names --------------------------------
  let lastLevel = "";
  function draw(v) {
    const fresh = v.level === "town" ? [...v.fresh] : [];
    V = v; staticKey = "";
    if (fresh.length && !v.reduced) lift = fresh.map(i => { const p = M.anchor(v.L, i); return { p: p && [p[0] * Q, p[1] * Q], t: performance.now() }; });
    const key = v.level + (v.site ? v.site.key : "");
    if (key !== lastLevel) { lastLevel = key; frame(); }
  }
  function scene(v) {
    if (v.level === "town") return townScene(v);
    if (v.level === "region") return regionScene(v);
    return siteScene(v);
  }
  // Fit what is found into the stage.
  function frame() {
    const sc = scene(V), r = stage.getBoundingClientRect();
    if (!sc.focus.length || !r.width) return;
    const pts = sc.focus.map(([x, y]) => [(x - y) * C, (x + y) * C * .5]);
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const w = Math.max(...xs) - Math.min(...xs) + 160, h = Math.max(...ys) - Math.min(...ys) + 200;
    s = Math.min(r.width / w, r.height / h, 1.6);
    ox = r.width / 2 - (Math.max(...xs) + Math.min(...xs)) / 2 * s;
    oy = r.height / 2 - (Math.max(...ys) + Math.min(...ys)) / 2 * s + 20;
  }

  const kindOf = name => { const n = String(name);
    return /cathedral|temple|chapel/.test(n) ? "steeple" : /keep|tower/.test(n) ? "keep" : /smith/.test(n) ? "smithy"
      : /inn|tavern/.test(n) ? "inn" : /market|row/.test(n) ? "market" : /well|cistern/.test(n) ? "well"
      : /grave/.test(n) ? "grave" : /green/.test(n) ? "green" : /gate/.test(n) ? "gate" : /square/.test(n) ? "plaza"
      : /crossing/.test(n) ? "cross" : /arena/.test(n) ? "arena" : /warren/.test(n) ? "huts" : "house"; };

  const Q = .62;  // the chart's seats are spaced for names; a diorama's houses sit closer
  function townScene(v) {
    const { T } = v, F = v.F, L0 = v.L, items = [], focus = [], paths = [];
    const q = p => p && [p[0] * Q, p[1] * Q];
    const L = { ...L0, pos: Object.fromEntries(Object.entries(L0.pos).map(([k, p]) => [k, q(p)])) };
    const P = i => q(M.anchor(L0, i));
    const ward = i => { if (i === L.square) return "square"; const c = L.kind[i] === "crossing" ? i : L.street[i];
      const m = /(north|east|south|west)-crossing/.exec(c || ""); return m ? m[1] : "square"; };
    const found = [...F.found].filter(i => L.pos[i]);
    found.forEach(i => { if (F.visited.has(i)) focus.push(L.pos[i]); });  // open on what you have walked
    // Streets as cobbled paths, where a found place stands at either end.
    Object.values(L.crossings).forEach(c => { if (F.found.has(c)) paths.push({ a: [0, 0], b: L.pos[c], w: 22, kind: "cobble" }); });
    if (L.gate && F.found.has(L.gate)) paths.push({ a: L.pos[L.street[L.gate]], b: L.pos[L.gate], w: 18, kind: "cobble" });
    found.forEach(i => { const st = L.street[i]; if (!st || ["crossing", "gate"].includes(L.kind[i])) return;
      const [x, y] = L.pos[i], [sx, sy] = L.pos[st];
      const foot = sx === 0 && st !== L.square ? [0, y] : sy === 0 && st !== L.square ? [x, 0] : [sx, sy];
      paths.push({ a: foot, b: [x, y], w: 9, kind: F.visited.has(i) ? "cobble" : "dirt" }); });
    const cr = found.find(i => /crossroads$/.test(i)) || found.find(i => /outskirts$/.test(i));
    if (L.gate && cr) paths.push({ a: L.pos[L.gate], b: L.pos[cr], w: 12, kind: "dirt" });
    found.filter(i => ["roadhead", "sign"].includes(L.kind[i]) && cr).forEach(i => paths.push({ a: L.pos[cr], b: L.pos[i], w: 8, kind: "dirt" }));
    // Things.
    found.forEach(i => {
      const [x, y] = L.pos[i], storeys = (L.floors[i] || []).filter(f => M.floorOf(f) > 0).length + 1;
      const k = L.kind[i] === "roadhead" ? "road" : L.kind[i] === "sign" ? (/desert/.test(i) ? "dunes" : "trees") : L.kind[i] === "apron" ? "post" : kindOf(T.names[i]);
      items.push({ id: i, x, y, k, storeys, been: F.visited.has(i), here: M.baseOf(v.here) === i, sel: v.sel === i, colour: WARD[ward(i)],
                   down: !!MapUI.siteFor(i), name: M.bare(T.names[i]),
                   road: L.kind[i] === "roadhead" ? ((T.ways[i] || []).find(w => w.journey) || {}).time_words : "" });
    });
    // The town wall, on the tiles it crosses.
    const gp = L.gate ? L.pos[L.gate] : [0, -240], wr = L0.wall ? L0.wall * Q : Math.hypot(...gp);
    const revealed = (x, y) => found.some(i => { const [px, py] = L.pos[i]; return Math.hypot(px - x, py - y) < 62; })
      || paths.some(p => segDist([x, y], p.a, p.b) < 28);
    return { items, paths, focus, revealed, ground: (x, y) => (Math.hypot(x, y) < wr ? "town" : "field"),
             wall: wr, extent: 480, cell: 26, route: v.route ? v.route.map(P).filter(Boolean) : null };
  }
  function regionScene(v) {
    const { G } = v, items = [], focus = [], paths = [];
    G.shown.forEach(i => { focus.push(G.pos[i]); items.push({ id: i, x: G.pos[i][0], y: G.pos[i][1], k: "town", been: v.visited.has(i),
      here: i === v.here, sel: v.sel === i, name: G.towns[i].name, colour: "#c98f4b", storeys: 1 }); });
    G.wild.forEach(w => { if (!v.wildFound.has(w.id)) return; focus.push(w.pos);
      items.push({ id: w.id, x: w.pos[0], y: w.pos[1], k: w.kind === "woods" ? "trees" : w.kind === "desert" ? "dunes" : "cave",
        been: v.wildVisited.has(w.id), here: false, sel: v.sel === w.id, name: M.bare(w.name), colour: "#6f9a5e", down: w.kind === "cave", storeys: 1 }); });
    G.roads.forEach(r => paths.push({ a: G.pos[r.a], b: G.pos[r.b], w: r.by === "river" ? 12 : 9, kind: r.by === "river" ? "river" : "dirt", days: r.days }));
    G.wild.forEach(w => { if (v.wildFound.has(w.id)) paths.push({ a: G.pos[v.R.here], b: w.pos, w: 6, kind: "dirt" }); });
    const sea = G.harbours.map(h => G.pos[h.id]);
    const revealed = (x, y) => focus.some(([px, py]) => Math.hypot(px - x, py - y) < 110) || paths.some(p => segDist([x, y], p.a, p.b) < 46);
    // No coastline in the export: a harbour gets a little water off its docks, nothing more.
    const ground = (x, y) => sea.some(([sx, sy]) => Math.hypot(x - sx - 80, y - sy) < 60) && !paths.some(p => segDist([x, y], p.a, p.b) < 20) ? "sea"
      : G.wild.some(w => w.kind === "desert" && Math.hypot(w.pos[0] - x, w.pos[1] - y) < 60) ? "sand" : "field";
    const P = i => G.pos[i] || (G.wild.find(w => w.id === i) || {}).pos;
    return { items, paths, focus, revealed, ground, extent: 640, route: v.route ? v.route.map(P).filter(Boolean) : null, cell: 44 };
  }
  const sitePos = (v, id) => [v.S.col[id] * 165, v.S.row[id] * 150];
  function siteScene(v) {
    const { S, site: st } = v, items = [], focus = [], paths = [];
    const seen = new Set(); st.been.forEach(i => (S.adj[i] || []).forEach(n => { if (!st.been.has(n)) seen.add(n); }));
    Object.keys(S.col).forEach(i => { const [x, y] = sitePos(v, i); focus.push([x, y]);
      if (!st.been.has(i) && !seen.has(i)) return;
      const r = st.rooms.find(q => q.id === i);
      items.push({ id: i, x, y, k: "room", been: st.been.has(i), here: i === v.here, sel: v.sel === i, name: M.bare(r.name), climax: r.role === "climax", door: r.door, storeys: 1 }); });
    S.passages.forEach(([a, b]) => { if (st.been.has(a) || st.been.has(b)) { const p = sitePos(v, a), q = sitePos(v, b);
      const mid = [ (p[0] + q[0]) / 2, p[1] ]; paths.push({ a: p, b: [mid[0], p[1]], w: 16, kind: "stone" }, { a: [mid[0], p[1]], b: [mid[0], q[1]], w: 16, kind: "stone" }, { a: [mid[0], q[1]], b: q, w: 16, kind: "stone" }); } });
    const revealed = () => false;  // underground: rock everywhere but rooms and passages
    return { items, paths, focus, revealed, ground: () => "rock", extent: 0, site: true,
             route: v.route ? v.route.map(i => sitePos(v, i)) : null };
  }
  function segDist(p, a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2));
    return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
  }

  // --- Painting -----------------------------------------------------------------------------
  const shade = (hex, f) => { const n = parseInt(hex.slice(1), 16); const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.max(0, Math.min(255, Math.round(v * f))));
    return `rgb(${c[0]},${c[1]},${c[2]})`; };
  function poly(pts, fill, stroke) {
    cx.beginPath(); pts.forEach(([x, y], n) => (n ? cx.lineTo(x, y) : cx.moveTo(x, y))); cx.closePath();
    if (fill) { cx.fillStyle = fill; cx.fill(); } if (stroke) { cx.strokeStyle = stroke; cx.lineWidth = 1; cx.stroke(); }
  }
  // A box standing on the ground: the two faces you can see and its top.
  function box(x, y, w, d, h, col, z = 0, ghost = false) {
    const a = iso(x - w, y + d, z), b = iso(x + w, y + d, z), c = iso(x + w, y - d, z);
    const at = iso(x - w, y + d, z + h), bt = iso(x + w, y + d, z + h), ct = iso(x + w, y - d, z + h), dt = iso(x - w, y - d, z + h);
    if (ghost) { cx.setLineDash([3, 3]); poly([a, b, bt, at], "rgba(235,240,250,.18)", "rgba(40,60,90,.55)"); poly([b, c, ct, bt], "rgba(235,240,250,.12)", "rgba(40,60,90,.55)"); poly([at, bt, ct, dt], "rgba(235,240,250,.25)", "rgba(40,60,90,.55)"); cx.setLineDash([]); return; }
    poly([a, b, bt, at], shade(col, .78), "rgba(40,28,18,.35)");
    poly([b, c, ct, bt], shade(col, .62), "rgba(40,28,18,.35)");
    poly([at, bt, ct, dt], shade(col, 1.05), "rgba(40,28,18,.25)");
  }
  function roof(x, y, w, d, h, r, col, ghost) {
    const L = iso(x - w, y, h + r), R = iso(x + w, y, h + r);
    const fl = iso(x - w, y + d, h), fr = iso(x + w, y + d, h), br = iso(x + w, y - d, h);
    if (ghost) { cx.setLineDash([3, 3]); poly([fl, fr, R, L], "rgba(235,240,250,.2)", "rgba(40,60,90,.55)"); cx.setLineDash([]); return; }
    poly([iso(x - w, y - d, h), br, R, L], shade(col, .55));
    poly([fl, fr, R, L], shade(col, 1));
    poly([fr, br, R], shade(col, .7), "rgba(40,28,18,.3)");
  }
  function windows(x, y, w, d, h, lit) {
    if (!lit) return;
    cx.fillStyle = "rgba(255,200,110,.95)";
    for (let z = 6; z < h - 4; z += 11) for (let t = -.5; t <= .5; t += 1) {
      const [px, py] = iso(x + t * w, y + d, z); cx.fillRect(px - 1.6 * s, py - 3 * s, 3.2 * s, 4 * s);
      const [qx, qy] = iso(x + w, y + t * d, z); cx.fillRect(qx - 1.4 * s, qy - 3 * s, 2.8 * s, 4 * s);
    }
  }
  function tree(x, y, sc = 1, ghost) {
    const [bx, by] = iso(x, y, 0), [tx, ty] = iso(x, y, 16 * sc);
    cx.strokeStyle = "#5a4028"; cx.lineWidth = 2 * s; cx.beginPath(); cx.moveTo(bx, by); cx.lineTo(tx, ty); cx.stroke();
    cx.fillStyle = ghost ? "rgba(200,220,200,.35)" : "#4f7a3c"; cx.beginPath(); cx.arc(tx, ty - 4 * s * sc, 9 * s * sc, 0, 7); cx.fill();
    if (!ghost) { cx.fillStyle = "#6f9a52"; cx.beginPath(); cx.arc(tx - 2.5 * s, ty - 7 * s * sc, 5 * s * sc, 0, 7); cx.fill(); }
  }
  function building(it, night) {
    const g = !it.been, col = it.colour || "#b8a07a", x = it.x, y = it.y, h = 14 + (it.storeys - 1) * 10;
    switch (it.k) {
      case "plaza": { const p = [iso(x - 30, y - 30), iso(x + 30, y - 30), iso(x + 30, y + 30), iso(x - 30, y + 30)]; poly(p, "#cdbf9f", "rgba(60,50,40,.3)");
        box(x, y, 6, 6, 4, "#9aa3ad", 0, g); const [fx, fy] = iso(x, y, 10); cx.fillStyle = "rgba(120,170,220,.85)"; cx.beginPath(); cx.arc(fx, fy, 3.5 * s, 0, 7); cx.fill(); break; }
      case "cross": { const [px, py] = iso(x, y, 0), [tx, ty] = iso(x, y, 20); cx.strokeStyle = "#3a2c1c"; cx.lineWidth = 2 * s; cx.beginPath(); cx.moveTo(px, py); cx.lineTo(tx, ty); cx.stroke();
        cx.fillStyle = "#e8dcc0"; cx.fillRect(tx - 1 * s, ty, 12 * s, 4 * s); cx.fillRect(tx - 11 * s, ty + 6 * s, 10 * s, 4 * s); break; }
      case "steeple": box(x, y, 14, 9, h, col, 0, g); roof(x, y, 14, 9, h, 8, "#6a4a3a", g); box(x + 10, y + 4, 5, 5, h + 22, "#d9cbb0", 0, g);
        if (!g) { const t = iso(x + 10, y + 4, h + 22), sp = iso(x + 10, y + 4, h + 40); poly([iso(x + 5, y + 9, h + 22), iso(x + 15, y + 9, h + 22), iso(x + 15, y - 1, h + 22), sp], "#4a5a6a"); void t; }
        windows(x, y, 14, 9, h, night && !g); break;
      case "keep": box(x, y, 13, 13, h + 18, "#a8a090", 0, g); if (!g) for (let i = -1; i <= 1; i += 2) for (let j = -1; j <= 1; j += 2) box(x + i * 10, y + j * 10, 3, 3, 6, "#a8a090", h + 18);
        windows(x, y, 13, 13, h + 18, night && !g); break;
      case "gate": box(x - 14, y, 7, 7, 30, "#a8a090", 0, g); box(x + 14, y, 7, 7, 30, "#a8a090", 0, g); box(x, y, 8, 5, 10, "#a8a090", 18, g); break;
      case "well": { const [px, py] = iso(x, y, 0); cx.fillStyle = g ? "rgba(235,240,250,.25)" : "#8a8a8a"; cx.beginPath(); cx.ellipse(px, py - 3 * s, 9 * s, 5 * s, 0, 0, 7); cx.fill();
        cx.fillStyle = "#2a3a4a"; cx.beginPath(); cx.ellipse(px, py - 5 * s, 6 * s, 3 * s, 0, 0, 7); cx.fill(); roof(x, y, 9, 6, 14, 6, "#7a4a30", g); break; }
      case "grave": for (let i = -2; i <= 2; i++) for (let j = -1; j <= 1; j++) box(x + i * 8, y + j * 10, 2, 1.2, 6, "#b0aca4", 0, g); tree(x + 18, y - 14, .8, g); break;
      case "green": tree(x - 10, y - 6, 1, g); tree(x + 9, y + 4, 1.1, g); tree(x - 2, y + 14, .9, g); break;
      case "trees": for (let i = 0; i < 7; i++) tree(x + Math.cos(i * 2.4) * 22 * (i % 3 ? 1 : .4), y + Math.sin(i * 2.4) * 18 * (i % 3 ? 1 : .4), .9 + (i % 2) * .3, g); break;
      case "dunes": for (let i = 0; i < 3; i++) { const [px, py] = iso(x + i * 14 - 14, y - i * 6, 0); cx.fillStyle = g ? "rgba(240,220,170,.4)" : "#dcbc80"; cx.beginPath(); cx.ellipse(px, py, 16 * s, 6 * s, -.2, Math.PI, 0); cx.fill(); } break;
      case "cave": { const [px, py] = iso(x, y, 0); cx.fillStyle = g ? "rgba(200,200,200,.4)" : "#8a7d6a"; cx.beginPath(); cx.ellipse(px, py - 6 * s, 22 * s, 16 * s, 0, Math.PI, 0); cx.fill();
        cx.fillStyle = "#1a140e"; cx.beginPath(); cx.ellipse(px, py - 2 * s, 8 * s, 9 * s, 0, Math.PI, 0); cx.fill(); break; }
      case "road": { const [px, py] = iso(x, y, 0), [tx, ty] = iso(x, y, 18); cx.strokeStyle = "#5a4028"; cx.lineWidth = 2 * s; cx.beginPath(); cx.moveTo(px, py); cx.lineTo(tx, ty); cx.stroke();
        cx.fillStyle = g ? "rgba(240,230,210,.6)" : "#e8d6a8"; cx.beginPath(); cx.moveTo(tx - 10 * s, ty); cx.lineTo(tx + 8 * s, ty); cx.lineTo(tx + 13 * s, ty + 3 * s); cx.lineTo(tx + 8 * s, ty + 6 * s); cx.lineTo(tx - 10 * s, ty + 6 * s); cx.fill(); break; }
      case "post": { const [px, py] = iso(x, y, 0), [tx, ty] = iso(x, y, 16); cx.strokeStyle = "#5a4028"; cx.lineWidth = 2 * s; cx.beginPath(); cx.moveTo(px, py); cx.lineTo(tx, ty); cx.stroke(); break; }
      case "town": { for (let i = 0; i < 5; i++) { const a = i * 1.26, r = i ? 13 : 0; box(x + Math.cos(a) * r, y + Math.sin(a) * r, 5, 4, 7 + (i % 2) * 4, "#e0cfa8", 0, g); roof(x + Math.cos(a) * r, y + Math.sin(a) * r, 5, 4, 7 + (i % 2) * 4, 4, "#b9645a", g); }
        if (!g) { cx.strokeStyle = "rgba(90,80,70,.7)"; cx.lineWidth = 2.2 * s; cx.beginPath(); const [px, py] = iso(x, y, 0); cx.ellipse(px, py, 32 * s * C * 1.4, 16 * s * C * 1.4, 0, 0, 7); cx.stroke(); }
        windows(x, y, 5, 4, 8, night && !g); break; }
      case "huts": for (let i = 0; i < 4; i++) { const xx = x + (i % 2) * 14 - 7, yy = y + Math.floor(i / 2) * 12 - 6; box(xx, yy, 5, 4, 7, "#b8a07a", 0, g); roof(xx, yy, 5, 4, 7, 4, "#7a5a3a", g); } break;
      case "arena": { const [px, py] = iso(x, y, 0); cx.strokeStyle = g ? "rgba(40,60,90,.5)" : "#a89878"; cx.lineWidth = 7 * s; cx.beginPath(); cx.ellipse(px, py - 4 * s, 22 * s, 11 * s, 0, 0, 7); cx.stroke(); break; }
      case "market": box(x - 8, y, 6, 6, 8, "#d8c8a0", 0, g); box(x + 8, y, 6, 6, 8, "#d8c8a0", 0, g);
        if (!g) { poly([iso(x - 15, y + 7, 12), iso(x + 15, y + 7, 12), iso(x + 15, y - 7, 14), iso(x - 15, y - 7, 14)], "#c0504a"); poly([iso(x - 5, y + 7, 12.1), iso(x + 5, y + 7, 12.1), iso(x + 5, y - 7, 14.1), iso(x - 5, y - 7, 14.1)], "#f0e0c0"); } break;
      case "room": break;
      default: box(x, y, 12, 9, h, col === "#c9a64f" ? "#e0cfa8" : "#e6d6b4", 0, g); roof(x, y, 12, 9, h, 8, col, g); windows(x, y, 12, 9, h, night && !g);
        if (it.k === "smithy" && !g) { const [px, py] = iso(x + 12, y + 3, 6); cx.fillStyle = "rgba(255,140,60,.9)"; cx.fillRect(px - 2 * s, py - 4 * s, 4 * s, 5 * s); }
        if (it.k === "inn" && !g) { const [px, py] = iso(x + 14, y + 9, 12); cx.fillStyle = "#7a4a2a"; cx.fillRect(px, py, 7 * s, 5 * s); }
    }
  }
  function room(it, v, t) {
    const x = it.x, y = it.y, w = 52, d = 36, wallH = 34;
    const floor = [iso(x - w, y - d), iso(x + w, y - d), iso(x + w, y + d), iso(x - w, y + d)];
    if (!it.been) { cx.setLineDash([5, 4]); poly(floor, "rgba(90,80,70,.35)", "rgba(220,200,160,.6)"); cx.setLineDash([]); return; }
    poly(floor, it.here ? "#7a6a52" : "#655845", "rgba(20,14,8,.6)");
    // Flagstones.
    cx.strokeStyle = "rgba(30,22,14,.35)"; cx.lineWidth = 1;
    for (let i = -w + 13; i < w; i += 13) { const a = iso(x + i, y - d), b = iso(x + i, y + d); cx.beginPath(); cx.moveTo(...a); cx.lineTo(...b); cx.stroke(); }
    for (let j = -d + 12; j < d; j += 12) { const a = iso(x - w, y + j), b = iso(x + w, y + j); cx.beginPath(); cx.moveTo(...a); cx.lineTo(...b); cx.stroke(); }
    // The cutaway: back walls only, so you see in.
    poly([iso(x - w, y - d), iso(x + w, y - d), iso(x + w, y - d, wallH), iso(x - w, y - d, wallH)], "#4d4234", "rgba(20,14,8,.6)");
    poly([iso(x - w, y - d), iso(x - w, y + d), iso(x - w, y + d, wallH), iso(x - w, y - d, wallH)], "#5a4d3c", "rgba(20,14,8,.6)");
    if (it.climax) box(x + 20, y - 18, 10, 8, 14, "#6a3030");
    if (it.here) { const [tx, ty] = iso(x - w + 4, y - 4, 26), fl = .8 + .2 * Math.sin(t * 9) * Math.sin(t * 5.3);
      const g = cx.createRadialGradient(tx, ty, 0, tx, ty, 90 * s); g.addColorStop(0, `rgba(255,190,90,${.55 * fl})`); g.addColorStop(1, "rgba(255,190,90,0)");
      cx.fillStyle = g; cx.beginPath(); cx.arc(tx, ty, 90 * s, 0, 7); cx.fill(); cx.fillStyle = "#ffd070"; cx.beginPath(); cx.arc(tx, ty, 2.5 * s, 0, 7); cx.fill(); }
  }

  function paintStatic(sc, v) {
    const W = cv.width / dpr, H = cv.height / dpr;
    cx.save();
    cx.fillStyle = sc.site ? "#16110c" : "#c9ccd6"; cx.fillRect(0, 0, W, H);  // the sky under the clouds
    const cell = sc.cell || 36, ext = sc.extent || 0;
    // Ground tiles under a cloud, except where you know the land.
    if (!sc.site) for (let gx = -ext; gx <= ext; gx += cell) for (let gy = -ext; gy <= ext; gy += cell) {
      const c = [iso(gx, gy), iso(gx + cell, gy), iso(gx + cell, gy + cell), iso(gx, gy + cell)];
      if (c.every(([x, y]) => x < -60 || x > W + 60 || y < -60 || y > H + 60)) continue;
      const mx = gx + cell / 2, my = gy + cell / 2, kind = sc.ground(mx, my);
      const odd = ((gx + gy) / cell) & 1;
      const col = kind === "sea" ? (odd ? "#4d7ea0" : "#4a7899") : kind === "sand" ? (odd ? "#d9bd85" : "#d4b67c") : kind === "town" ? (odd ? "#8fae6a" : "#89a865") : (odd ? "#7fa45a" : "#79a055");
      poly(c, col, "rgba(30,40,20,.12)");
      // Tile thickness at the board's front edges: a diorama, not a plane.
    }
    if (!sc.site && sc.wall) { cx.strokeStyle = "rgba(150,140,120,.9)"; cx.lineWidth = 5 * s; cx.beginPath();
      for (let a = 0; a <= 64; a++) { const [x, y] = iso(Math.cos(a / 64 * 6.283) * sc.wall, Math.sin(a / 64 * 6.283) * sc.wall); a ? cx.lineTo(x, y) : cx.moveTo(x, y); } cx.stroke(); }
    // Paths.
    sc.paths.forEach(p => { const a = iso(...p.a), b = iso(...p.b);
      cx.lineCap = "round"; cx.strokeStyle = p.kind === "cobble" ? "#b5ab98" : p.kind === "river" ? "#4f86b0" : p.kind === "stone" ? "#4a3f32" : "#b79b6d";
      cx.lineWidth = p.w * s * .9; cx.beginPath(); cx.moveTo(...a); cx.lineTo(...b); cx.stroke();
      if (p.kind === "cobble") { cx.setLineDash([2 * s, 4 * s]); cx.strokeStyle = "rgba(90,80,64,.5)"; cx.lineWidth = p.w * s * .5; cx.stroke(); cx.setLineDash([]); }
      if (p.days > 1) for (let d = 1; d < p.days; d++) { const t = d / p.days; cx.fillStyle = "rgba(255,245,220,.9)"; cx.beginPath(); cx.arc(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 2.6 * s, 0, 7); cx.fill(); } });
    // Things, back to front.
    sc.items.slice().sort((p, q) => (p.x + p.y) - (q.x + q.y)).forEach(it => it.k === "room" ? room(it, v, 0) : building(it, v.light.night));
    // Cloud over every tile you have not found: puffs, so the edge of the known is soft.
    if (!sc.site) for (let gx = -ext; gx <= ext; gx += cell) for (let gy = -ext; gy <= ext; gy += cell) {
      const mx = gx + cell / 2, my = gy + cell / 2;
      if (sc.revealed(mx, my)) continue;
      const seed = Math.sin(gx * 12.9 + gy * 78.2) * 43758.5 % 1, seed2 = Math.sin(gx * 39.3 + gy * 11.7) * 24634.6 % 1;
      const [x0, y0] = iso(mx, my, 6 + Math.abs(seed2) * 10), x = x0 + seed * 7 * s, y = y0 + seed2 * 4 * s;
      if (x < -80 || x > W + 80 || y < -80 || y > H + 80) continue;
      const r = cell * s * (.5 + Math.abs(seed) * .35);
      cx.fillStyle = "rgba(170,180,200,.55)"; cx.beginPath(); cx.ellipse(x, y + r * .5, r * 1.3, r * .42, 0, 0, 7); cx.fill();
      cx.fillStyle = "rgba(232,234,242,.94)";
      cx.beginPath(); cx.arc(x, y, r, 0, 7); cx.arc(x + r * .7, y - r * .25 + seed * 4, r * .75, 0, 7); cx.arc(x - r * .6, y - r * .1, r * .7, 0, 7); cx.fill();
      cx.fillStyle = "rgba(255,255,255,.7)"; cx.beginPath(); cx.arc(x - r * .2, y - r * .35, r * .5, 0, 7); cx.fill();
    }
    cx.restore();
  }

  // --- Each frame: the static board, then what moves ------------------------------------------
  function loop() {
    cancelAnimationFrame(raf);
    const tick = now => { raf = requestAnimationFrame(tick); frameDraw(now); };
    raf = requestAnimationFrame(tick);
  }
  window.__dioramaFrame = () => frameDraw(performance.now());
  function frameDraw(now) {
    if (!V) return;
    const t = (now - t0) / 1000, still = api.reduced();
    const W = cv.width / dpr, H = cv.height / dpr;
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const sc = scene(V);
    const key = `${V.level}|${s}|${ox}|${oy}|${W}|${H}|${V.light.night}|${V.sel}|${V.here}|${(V.F ? V.F.found.size : 0)}|${V.site ? V.site.been.size + V.site.key : ""}`;
    if (key !== staticKey || !staticLayer) {
      paintStatic(sc, V);
      staticLayer = staticLayer || document.createElement("canvas");
      staticLayer.width = cv.width; staticLayer.height = cv.height;
      staticLayer.getContext("2d").drawImage(cv, 0, 0);
      staticKey = key; walkers = makeWalkers(sc);
    } else { cx.setTransform(1, 0, 0, 1, 0, 0); cx.drawImage(staticLayer, 0, 0); cx.setTransform(dpr, 0, 0, dpr, 0, 0); }
    // Clouds lifting off tiles found on this walk.
    lift = lift.filter(l => now - l.t < 1600);
    lift.forEach(l => { if (!l.p) return; const u = (now - l.t) / 1600, [x, y] = iso(l.p[0], l.p[1], 6 + u * 40);
      cx.fillStyle = `rgba(244,244,250,${(1 - u) * .95})`; cx.beginPath(); cx.arc(x, y, 50 * s * (1 + u), 0, 7); cx.fill(); });
    // People on the streets you know (fewer at night, carrying lanterns).
    if (!still) walkers.forEach((w, n) => { if (V.light.night && n % 3) return;
      const u = (Math.sin(t * w.sp + w.ph) + 1) / 2, x = w.a[0] + (w.b[0] - w.a[0]) * u, y = w.a[1] + (w.b[1] - w.a[1]) * u;
      const [px, py] = iso(x + w.off, y - w.off, Math.abs(Math.sin(t * 8 + n)) * 1.2);
      cx.fillStyle = "rgba(0,0,0,.25)"; cx.beginPath(); cx.ellipse(px, py + 1 * s, 3 * s, 1.5 * s, 0, 0, 7); cx.fill();
      cx.fillStyle = w.c; cx.fillRect(px - 1.5 * s, py - 7 * s, 3 * s, 6 * s); cx.beginPath(); cx.arc(px, py - 8.5 * s, 1.8 * s, 0, 7); cx.fillStyle = "#f0d0b0"; cx.fill();
      if (V.light.night) { const g = cx.createRadialGradient(px, py - 5 * s, 0, px, py - 5 * s, 18 * s); g.addColorStop(0, "rgba(255,200,110,.6)"); g.addColorStop(1, "rgba(255,200,110,0)"); cx.fillStyle = g; cx.beginPath(); cx.arc(px, py - 5 * s, 18 * s, 0, 7); cx.fill(); } });
    // Chimney smoke from houses you know.
    if (!still && V.level === "town") sc.items.forEach((it, n) => { if (!it.been || !["house", "inn", "smithy"].includes(it.k)) return;
      const h = 14 + (it.storeys - 1) * 10 + 10;
      for (let p = 0; p < 3; p++) { const a = (t * .4 + p / 3 + n * .17) % 1, [px, py] = iso(it.x + 6, it.y - 4, h + a * 30);
        cx.fillStyle = `rgba(230,230,235,${.5 * (1 - a)})`; cx.beginPath(); cx.arc(px + Math.sin(a * 5 + n) * 3 * s, py, (2 + a * 5) * s, 0, 7); cx.fill(); } });
    // The sea's glitter.
    if (!still && V.level === "region") V.G.harbours.forEach(h => { const [hx, hy] = V.G.pos[h.id];
      for (let i = 0; i < 14; i++) { const x = hx + 50 + (i * 37) % 60, y = hy - 40 + ((i * 53) % 80), [px, py] = iso(x, y, 0);
        cx.fillStyle = `rgba(255,255,255,${(.5 + .5 * Math.sin(t * 2 + i * 1.7)) * .7})`; cx.fillRect(px, py, 5 * s, 1.2 * s); } });
    // The route, and you.
    if (sc.route) { cx.strokeStyle = "rgba(39,64,110,.9)"; cx.lineWidth = 3.4; cx.setLineDash([8, 6]); cx.lineDashOffset = still ? 0 : -t * 24;
      cx.beginPath(); sc.route.forEach((p, n) => { const [x, y] = iso(p[0], p[1], 2); n ? cx.lineTo(x, y) : cx.moveTo(x, y); }); cx.stroke(); cx.setLineDash([]); }
    sc.items.forEach(it => { if (V.level === "site" && it.here) room(it, V, t); });  // the torch, lit each frame
    const here = token ? token.pos(now) : hereAt(sc);
    if (here) pawn(here[0], here[1], here[2] || 0, t);
    // Light: the hour multiplies over everything; at night windows and lamps glow through it.
    const L = V.light;
    cx.globalCompositeOperation = "multiply"; cx.fillStyle = `rgba(${L.r},${L.g},${L.b},${L.a * 1.3})`; cx.fillRect(0, 0, W, H);
    cx.globalCompositeOperation = "lighter";
    if (L.night && V.level !== "site") sc.items.forEach(it => { if (!it.been) return; const [px, py] = iso(it.x, it.y, 12);
      const g = cx.createRadialGradient(px, py, 0, px, py, 34 * s); g.addColorStop(0, "rgba(255,170,70,.35)"); g.addColorStop(1, "rgba(255,170,70,0)"); cx.fillStyle = g; cx.beginPath(); cx.arc(px, py, 34 * s, 0, 7); cx.fill(); });
    if (here && V.level !== "site") { const [px, py] = iso(here[0], here[1], 10), g = cx.createRadialGradient(px, py, 0, px, py, 46 * s);
      g.addColorStop(0, `rgba(255,200,110,${.35 + .1 * Math.sin(t * 3)})`); g.addColorStop(1, "rgba(255,200,110,0)"); cx.fillStyle = g; cx.beginPath(); cx.arc(px, py, 46 * s, 0, 7); cx.fill(); }
    cx.globalCompositeOperation = "source-over";
    // Rain.
    if (V.rain) { cx.fillStyle = "rgba(40,50,70,.15)"; cx.fillRect(0, 0, W, H);
      if (drops.length < 300) drops = Array.from({ length: 300 }, () => [Math.random() * W, Math.random() * H, .6 + Math.random() * .8]);
      cx.strokeStyle = "rgba(200,215,235,.45)"; cx.lineWidth = 1; cx.beginPath();
      drops.forEach(d => { if (!still) { d[1] += 13 * d[2]; d[0] -= 2.5 * d[2]; if (d[1] > H) { d[1] = -10; d[0] = Math.random() * W * 1.1; } } cx.moveTo(d[0], d[1]); cx.lineTo(d[0] + 2.5 * d[2], d[1] - 11 * d[2]); });
      cx.stroke(); }
    names(sc);
    rose(W, H);
  }
  function hereAt(sc) { const it = sc.items.find(i => i.here); return it ? [it.x + (V.level === "site" ? 0 : 16), it.y + (V.level === "site" ? 0 : 16), 0] : null; }
  function pawn(x, y, z, t) {
    const [px, py] = iso(x, y, 0), [qx, qy] = iso(x, y, z);
    cx.fillStyle = "rgba(0,0,0,.3)"; cx.beginPath(); cx.ellipse(px, py, 7 * s, 3.5 * s, 0, 0, 7); cx.fill();
    cx.fillStyle = "#27406e"; cx.beginPath(); cx.moveTo(qx - 6 * s, qy); cx.lineTo(qx + 6 * s, qy); cx.lineTo(qx + 3 * s, qy - 14 * s); cx.lineTo(qx - 3 * s, qy - 14 * s); cx.fill();
    cx.beginPath(); cx.arc(qx, qy - 17 * s, 4.5 * s, 0, 7); cx.fill();
    cx.strokeStyle = "#f3ead6"; cx.lineWidth = 1.2; cx.stroke();
  }
  function makeWalkers(sc) {
    const cols = ["#7a3b2e", "#3e5a3a", "#5a4a7a", "#8a6a2a", "#2e4a6a"];
    const segs = sc.paths.filter(p => p.kind === "cobble" || (V.level === "region" && p.kind === "dirt"));
    return segs.flatMap((p, n) => [0, 1].map(j => ({ a: p.a, b: p.b, sp: .15 + ((n * 7 + j * 3) % 5) * .05, ph: n * 1.3 + j * 2.1, off: (j ? 4 : -4), c: cols[(n + j) % cols.length] })));
  }

  // Names: plates over the board, nudged up when they would sit on one already placed.
  function names(sc) {
    hits = [];
    const placed = [];
    cx.font = `600 13px Palatino Linotype, Palatino, Georgia, serif`;
    sc.items.slice().sort((a, b) => (b.here - a.here) || (b.been - a.been) || (b.sel - a.sel)).forEach(it => {
      const [px, py] = iso(it.x, it.y, it.k === "room" ? 0 : 30 + (it.storeys - 1) * 10);
      hits.push({ id: it.id, x: px, y: py + 10 });
      cx.font = `${it.been ? "600" : "italic 400"} 13px Palatino Linotype, Palatino, Georgia, serif`;
      const text = it.been || V.level !== "site" ? it.name : "?";
      const w = cx.measureText(text).width + 12, h = 19;
      let y = py - 6;
      for (let n = 0; n < 6 && placed.some(b => px - w / 2 < b[2] && px + w / 2 > b[0] && y - h < b[3] && y > b[1]); n++) y -= h + 2;
      placed.push([px - w / 2, y - h, px + w / 2, y]);
      cx.fillStyle = it.sel ? "#8e2317" : it.here ? "#27406e" : it.been ? "rgba(243,234,214,.92)" : "rgba(243,234,214,.62)";
      cx.beginPath(); cx.roundRect(px - w / 2, y - h, w, h, 9); cx.fill();
      cx.fillStyle = it.sel || it.here ? "#f3ead6" : "#2a2019"; cx.textAlign = "center"; cx.textBaseline = "middle";
      cx.fillText(text, px, y - h / 2 + 1);
      let bx = px + w / 2 + 2;
      if (it.storeys > 1) { cx.fillStyle = "#f3ead6"; cx.beginPath(); cx.arc(bx + 7, y - h / 2, 8, 0, 7); cx.fill(); cx.fillStyle = "#2a2019"; cx.font = "600 11px Palatino Linotype, Georgia, serif"; cx.fillText(String(it.storeys), bx + 7, y - h / 2 + 1); bx += 18; }
      if (it.down) { cx.fillStyle = "#27406e"; cx.beginPath(); cx.arc(bx + 7, y - h / 2, 8, 0, 7); cx.fill(); cx.fillStyle = "#f3ead6"; cx.font = "700 12px Georgia, serif"; cx.fillText("↓", bx + 7, y - h / 2 + 1); }
      if (it.road) { cx.font = "italic 12px Palatino Linotype, Georgia, serif"; cx.fillStyle = "rgba(243,234,214,.95)"; cx.fillText(it.road.replace(/^about /, "").replace(/ on foot$/, ""), px, y + 9); }
    });
  }
  function rose(W, H) {
    const x = W - 46, y = H - 46;
    cx.save(); cx.translate(x, y); cx.fillStyle = "rgba(243,234,214,.85)"; cx.beginPath(); cx.arc(0, 0, 26, 0, 7); cx.fill();
    // North on the board is up and left: the projection turns the town 45°.
    const [nx, ny] = [(0 - -1) * C, (0 + -1) * C * .5], L = Math.hypot(nx, ny);
    cx.rotate(Math.atan2(ny / L, nx / L) + Math.PI / 2);
    cx.fillStyle = "#8e2317"; cx.beginPath(); cx.moveTo(0, -20); cx.lineTo(5, 0); cx.lineTo(-5, 0); cx.fill();
    cx.fillStyle = "#2a2019"; cx.beginPath(); cx.moveTo(0, 20); cx.lineTo(5, 0); cx.lineTo(-5, 0); cx.fill();
    cx.rotate(-(Math.atan2(ny / L, nx / L) + Math.PI / 2)); cx.fillStyle = "#2a2019"; cx.font = "600 11px Cinzel, Georgia, serif"; cx.textAlign = "center";
    cx.fillText("N", -16, -14); cx.restore();
  }

  // --- The walk: the token hops square to square along the route -------------------------------
  function walk(ids, done) {
    const sc = scene(V), pts = sc.route;
    if (!pts || pts.length < 2 || api.reduced()) { done(); return; }
    const seg = [], tot = pts.slice(1).reduce((a, p, n) => { const d = Math.hypot(p[0] - pts[n][0], p[1] - pts[n][1]); seg.push(d); return a + d; }, 0);
    const dur = Math.min(3200, 600 + tot * 3), start = performance.now(), hop = 26;
    token = { pos: now => { const u = Math.min(1, (now - start) / dur); let d = u * tot, n = 0;
      while (n < seg.length - 1 && d > seg[n]) { d -= seg[n]; n++; }
      const a = pts[n], b = pts[n + 1], f = seg[n] ? d / seg[n] : 1, z = Math.abs(Math.sin((u * tot / hop) * Math.PI)) * 9;
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, z]; } };
    let over = false;
    const finish = () => { if (over) return; over = true; token = null; done(); };
    setTimeout(finish, dur + 100);  // ends on time even when a hidden window gets no frames
  }

  return { init, draw, walk };
})();
