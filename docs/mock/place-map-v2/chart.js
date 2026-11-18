// Style 1, the living illustrated chart: ink on the game's own chart paper, drawn in SVG
// with no library. Look-only references: Watabou's Medieval Fantasy City Generator (pen
// streets, wards in washes; no code taken, it is GPL), 80 Days and Sunless Sea (a chart
// that is alive and lit). Every rule comes from shared/ui.js and model.js; this file draws.
const ChartRenderer = (() => {
  const M = MapModel, NS = "http://www.w3.org/2000/svg";
  const e = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let stage, api, svg, live, rainCv, V = null, vb = null, k = 1, raf = 0, t0 = performance.now();

  // Wards in watercolour, by the crossing their street leaves from (the square is gold).
  const WASH = { north: "#c49a52", east: "#7f9a6a", south: "#b77a6a", west: "#6d86a3", square: "#d2b46a" };
  const INK = "#2a2019", PENCIL = "#7d6b55", LAPIS = "#27406e", RUBRIC = "#8e2317";

  // --- The building icons, by what the place is called. ~30 units, centred, pen strokes.
  function icon(name) {
    const n = String(name);
    const P = {
      steeple: "M-9 12V-2L0-10 9-2V12ZM0-10V-22M-4-17H4M-3 12V5H3V12",
      tower: "M-8 12V-12H-5V-9H-2V-12H2V-9H5V-12H8V12ZM-2 12V5H2V12M-3-3H3",
      anvil: "M-11-4H9Q9 1 4 2L3 7H6V10H-6V7H-3L-4 2Q-11 1-11-4ZM9-4L13-6",
      sign: "M-8 12V-12H8M2-12V-9M-1-9H7V-1H-1Z M-12 12H4",
      tankard: "M-6-8H5V9H-6ZM5-5Q11-5 11 1Q11 6 5 6M-6-8Q-6-12 0-11Q5-12 5-8",
      stall: "M-12-3L-9-11H9L12-3ZM-12-3Q-9 1-6-3Q-3 1 0-3Q3 1 6-3Q9 1 12-3M-10-1V10M10-1V10M-12 10H12",
      well: "M-9 3H9V11H-9ZM-9 3Q0 0 9 3M-7 3V-9M7 3V-9M-10-9H10L0-14Z",
      grave: "M-5 12V-2Q-5-8 0-8Q5-8 5-2V12ZM0-6V3M-3-2H3M-12 12H12",
      shield: "M-8-10H8V0Q8 8 0 12Q-8 8-8 0ZM0-10V12M-8-2H8",
      flask: "M-3-12H3M-2-12V-4L-9 9Q-10 12-6 12H6Q10 12 9 9L2-4V-12M-6 5H6",
      barn: "M-11 12V-2L0-11 11-2V12ZM-5 12V3H5V12M-5 3L5 12M5 3L-5 12",
      shoe: "M-7 10Q-11-2-5-9Q0-13 5-9Q11-2 7 10M-4 9Q-7 0-2-5M4 9Q7 0 2-5",
      wheel: "M0-11A11 11 0 1 1 0 11A11 11 0 1 1 0-11ZM0-11V11M-11 0H11M-8-8L8 8M8-8L-8 8",
      tree: "M0 12V2M0 2Q-12 2-9-6Q-11-13-3-12Q0-17 4-12Q12-12 9-5Q12 2 0 2",
      huts: "M-12 12V3L-7-2-2 3V12ZM-2 12V-1L4-7 10-1V12ZM-9 12V8H-5V12M2 12V7H6V12",
      hall: "M-12-4L0-12 12-4ZM-10-4V9M-5-4V9M0-4V9M5-4V9M10-4V9M-12 9H12V12H-12Z",
      oval: "M0-9A13 9 0 1 1 0 9A13 9 0 1 1 0-9ZM0-5A7 5 0 1 1 0 5A7 5 0 1 1 0-5Z",
      row: "M-13 12V-1L-9-6-5-1V12M-5 12V-3L-1-8 3-3V12M3 12V0L7-5 11 0V12M-13 12H11",
      gate: "M-13 12V-12H-6V12M6 12V-12H13V12M-6-4H6M-13-12V-15H-10V-12M10-12V-15H13V-12M-3 12V3Q0 0 3 3V12",
      house: "M-9 12V-1L0-10 9-1V12ZM-3 12V5H3V12M3-6V-11H6V-3",
      fountain: "M-10 6Q0 12 10 6M-10 6Q0 0 10 6M0 3V-8M0-8Q-6-8-7-3M0-8Q6-8 7-3",
      cross: "M0-9V9M-9 0H9",
      sign2: "M0 12V-12M0-10H11L13-7 11-4H0M0-2H-11L-13 1-11 4H0",
      dunes: "M-13 6Q-6-2 0 6Q6-4 13 6M-9 12Q-3 6 3 12",
      road: "M0 12L0-12M-5-6L0-12 5-6",
      cave: "M-12 10Q-12-8 0-9Q12-8 12 10ZM-5 10Q-5-1 0-1Q5-1 5 10",
      walled: "M0-13A13 13 0 1 1 0 13A13 13 0 1 1 0-13ZM-6 2V-4L-2-7 2-4V2ZM2 6V0L6-3 9 0V6M-9 7V2L-6 0-3 2V7",
    };
    const pick = [[/cathedral|temple|chapel|shrine/, "steeple"], [/keep|castle|tower/, "tower"], [/smith|forge/, "anvil"],
      [/inn\b/, "sign"], [/tavern|alehouse/, "tankard"], [/market|bazaar/, "stall"], [/well|cistern/, "well"],
      [/grave|cemetery|crypt/, "grave"], [/barrack|guard|watch/, "shield"], [/laborator|alchem/, "flask"],
      [/granar|barn/, "barn"], [/stable/, "shoe"], [/carter|wheel/, "wheel"], [/green|park|garden|woods/, "tree"],
      [/warren|slum/, "huts"], [/guild|hall/, "hall"], [/arena/, "oval"], [/row|street/, "row"], [/gate/, "gate"],
      [/square/, "fountain"], [/crossing/, "cross"], [/crossroads|outskirts/, "sign2"], [/desert/, "dunes"],
      [/road to/, "road"], [/cave|mouth|throat/, "cave"]];
    if (P[n]) return P[n];
    const hit = pick.find(([re]) => re.test(n));
    return P[hit ? hit[1] : "house"];
  }
  const smokes = /inn|tavern|smith|forge|bakery|house|warren|barrack|guard/;

  function init(el, a) {
    stage = el; api = a;
    stage.innerHTML = `<div class="surface paper"></div><svg class="surface" xmlns="${NS}" role="group"></svg><svg class="surface live" xmlns="${NS}" aria-hidden="true"></svg><canvas class="surface rain" aria-hidden="true"></canvas>`;
    svg = stage.querySelector("svg"); live = stage.querySelector("svg.live"); rainCv = stage.querySelector("canvas");
    panZoom();
    svg.addEventListener("click", ev => { if (dragged) return; const g = ev.target.closest("[data-id]"); if (g) api.pick(g.dataset.id); });
    svg.addEventListener("keydown", ev => { if ((ev.key === "Enter" || ev.key === " ") && ev.target.dataset.id) { ev.preventDefault(); api.pick(ev.target.dataset.id); } });
    new ResizeObserver(() => { if (V) { measure(); render(); } }).observe(stage);
    loop();
  }

  // --- Pan and zoom: the wheel zooms about the pointer, a drag pans. -----------------------
  let dragged = false;
  function panZoom() {
    let down = null;
    svg.addEventListener("pointerdown", ev => { down = [ev.clientX, ev.clientY, vb.slice()]; dragged = false; });
    addEventListener("pointermove", ev => {
      if (!down) return;
      const dx = ev.clientX - down[0], dy = ev.clientY - down[1];
      if (Math.hypot(dx, dy) > 4) dragged = true;
      if (dragged) { vb = [down[2][0] - dx * k, down[2][1] - dy * k, down[2][2], down[2][3]]; setVB(); }
    });
    addEventListener("pointerup", () => { down = null; setTimeout(() => { dragged = false; }, 0); });
    svg.addEventListener("wheel", ev => {
      ev.preventDefault();
      const r = svg.getBoundingClientRect(), f = Math.exp(ev.deltaY * .0012);
      const px = vb[0] + (ev.clientX - r.left) * k, py = vb[1] + (ev.clientY - r.top) * k;
      const w = Math.min(Math.max(vb[2] * f, 300), 2600), s = w / vb[2];
      vb = [px - (px - vb[0]) * s, py - (py - vb[1]) * s, w, vb[3] * s]; measure(); render();
    }, { passive: false });
  }
  function fit(box) {
    const r = stage.getBoundingClientRect(), [x0, y0, x1, y1] = box;
    const w = x1 - x0, h = y1 - y0, s = Math.max(w / r.width, h / r.height);
    vb = [(x0 + x1) / 2 - r.width * s / 2, (y0 + y1) / 2 - r.height * s / 2, r.width * s, r.height * s];
    measure();
  }
  function measure() {
    const r = stage.getBoundingClientRect();
    if (!r.width) return;
    // Keep the box the stage's shape, so a unit is the same on both axes.
    vb[3] = vb[2] * r.height / r.width; k = vb[2] / r.width; setVB();
    rainCv.width = r.width; rainCv.height = r.height;
  }
  const setVB = () => { const b = vb.map(n => n.toFixed(1)).join(" "); svg.setAttribute("viewBox", b); live.setAttribute("viewBox", b); };

  // --- Drawing ------------------------------------------------------------------------------
  let lastKey = "";
  function draw(v) {
    const key = v.level + (v.site ? v.site.key : "");
    V = v;
    if (key !== lastKey) { lastKey = key; fit(bounds(v)); }
    render();
  }
  function bounds(v) {
    const pts = [];
    if (v.level === "town") v.F.found.forEach(i => { const p = M.anchor(v.L, i); if (p) pts.push(p); });
    else if (v.level === "region") { v.G.shown.forEach(i => pts.push(v.G.pos[i])); v.G.wild.forEach(w => pts.push(w.pos)); }
    else Object.keys(v.S.col).forEach(i => pts.push(sitePos(v, i)));
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const pad = v.level === "town" ? 110 : v.level === "region" ? 90 : 80;
    let b = [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad];
    // Never blow a small map up: a three-room cave is drawn at the scale of a big one.
    const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2, w = Math.max(b[2] - b[0], 760), h = Math.max(b[3] - b[1], 480);
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
  }

  function defs() {
    return `<defs>
      <filter id="ink" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3"/>
        <feDisplacementMap in="SourceGraphic" scale="${(1.6 * k).toFixed(2)}"/></filter>
      <filter id="wash" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="3" seed="8" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="70" result="d"/><feGaussianBlur in="d" stdDeviation="5" result="b"/>
        <feComposite in="b" in2="n" operator="arithmetic" k1="0" k2="1" k3="-.25" k4="0"/></filter>
      <pattern id="clouds" width="900" height="900" patternUnits="userSpaceOnUse"><image href="${cloudTex()}" width="900" height="900"/></pattern>
      <radialGradient id="lantern"><stop offset="0" stop-color="#ffd27a" stop-opacity=".95"/><stop offset=".35" stop-color="#f0a040" stop-opacity=".45"/><stop offset="1" stop-color="#f0a040" stop-opacity="0"/></radialGradient>
      <radialGradient id="lamp"><stop offset="0" stop-color="#ffe2a0" stop-opacity=".9"/><stop offset="1" stop-color="#ffb050" stop-opacity="0"/></radialGradient>
      <radialGradient id="clear"><stop offset=".3" stop-color="#000"/><stop offset="1" stop-color="#fff"/></radialGradient>
      <pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M34 0H0V34" fill="none" stroke="#4a6a8a" stroke-opacity=".32" stroke-width="1.2"/></pattern>
    </defs>`;
  }

  let CLOUD = "", cloudImg = null, fogHoles = null;
  function cloudTex() {
    if (CLOUD) return CLOUD;
    const N = 256, c = document.createElement("canvas"); c.width = c.height = N;
    const g = c.getContext("2d"), img = g.createImageData(N, N);
    const grid = (n, seed) => { const a = []; let x = seed; for (let i = 0; i < n * n; i++) { x = (x * 16807) % 2147483647; a.push(x / 2147483647); } return a; };
    const oct = [[4, .5, 7], [8, .25, 11], [16, .15, 13], [32, .1, 17]].map(([n, w, sd]) => [n, w, grid(n, sd)]);
    const sm = t => t * t * (3 - 2 * t);
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      let v = 0;
      oct.forEach(([n, w, G]) => { const fx = x / N * n, fy = y / N * n, ix = Math.floor(fx), iy = Math.floor(fy), tx = sm(fx - ix), ty = sm(fy - iy);
        const at = (i, j) => G[((j % n) * n) + (i % n)];
        v += w * ((at(ix, iy) * (1 - tx) + at(ix + 1, iy) * tx) * (1 - ty) + (at(ix, iy + 1) * (1 - tx) + at(ix + 1, iy + 1) * tx) * ty); });
      const a = Math.max(0, Math.min(1, (v - .42) * 3.2)), o = (y * N + x) * 4;
      img.data[o] = 250; img.data[o + 1] = 246; img.data[o + 2] = 236; img.data[o + 3] = a * 235;
    }
    g.putImageData(img, 0, 0);
    return (CLOUD = c.toDataURL());
  }
  // The fog: paper left unpainted, a drift of cloud over everything except round what is
  // found. One mask for the whole sheet, so the fog says nothing about how much is under it.
  function fogLayer(found, r, box) {
    const [x0, y0, x1, y1] = box;
    fogHoles = { pts: found, r };
    const holes = found.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="url(#clear)"/>`).join("");
    const sheet = `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="#fff"/>`;
    // The paper's fog is drawn once; only the drifting cloud above it moves, on the live layer,
    // so a frame never re-rasterises the filtered sheet (it cost 42 fps when it did).
    return `<mask id="fogm">${sheet}${holes}</mask>
      <g mask="url(#fogm)" class="fog"><rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="#ece2ca" opacity=".72"/>
      <rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="url(#clouds)" opacity=".55"/></g>
`;
  }

  function label(x, y, text, side, cls, w) {
    const fs = 13.5 * k, off = 20 * k;
    const [dx, dy, anchor] = { right: [off, fs * .35, "start"], left: [-off, fs * .35, "end"], above: [0, -off - 2 * k, "middle"],
                               below: [0, off + fs * .8, "middle"] }[side] || [off, 0, "start"];
    return `<text class="lbl ${cls}" x="${x + dx}" y="${y + dy}" text-anchor="${anchor}" style="font-size:${fs}px;stroke-width:${3.2 * k}px">${e(text)}</text>`;
  }
  // A name's box, to push it to its next side when it would sit on another name.
  const ruler = document.createElement("canvas").getContext("2d");
  function boxOf(x, y, text, side, italic) {
    ruler.font = `${italic ? "italic " : "600 "}13.5px Palatino Linotype, Palatino, Georgia, serif`;
    const w = ruler.measureText(text).width * k, h = 14 * k, off = 20 * k;
    if (side === "right") return [x + off, y - h * .6, x + off + w, y + h * .5];
    if (side === "left") return [x - off - w, y - h * .6, x - off, y + h * .5];
    if (side === "above") return [x - w / 2, y - off - h, x + w / 2, y - off];
    return [x - w / 2, y + off, x + w / 2, y + off + h];
  }
  function sides(pref) {
    return [pref, ...{ right: ["left", "below", "above"], left: ["right", "below", "above"], above: ["below", "right", "left"], below: ["above", "right", "left"] }[pref]];
  }
  function placeNames(items) {
    // items: [x, y, text, pref, italic]; first come first served, you and visited first.
    const taken = items.map(([x, y, , , , tall]) => [x - 14 * k, y - (tall ? 36 : 14) * k, x + 14 * k, y + 14 * k]);  // a banner makes it taller
    const g = 7 * k, hit = (b, list) => list.some(o => b[0] - g < o[2] && b[2] + g > o[0] && b[1] < o[3] && b[3] > o[1]);
    const placed = [];
    return items.map(([x, y, t, pref, it, tall], i) => {
      const others = taken.filter((_, j) => j !== i);
      const s = sides(pref).filter(sd => !(tall && sd === "above")).find(sd => { const b = boxOf(x, y, t, sd, it); return !hit(b, placed) && !hit(b, others); }) || pref;
      placed.push(boxOf(x, y, t, s, it));
      return s;
    });
  }

  function glyph(id, x, y, name, { visited, current, sel, fresh, wash, badge, down }) {
    const s = 1.05 * k, d = icon(name);
    const fill = visited ? wash : "none";
    return `<g class="place${visited ? " been" : " seen"}${current ? " here" : ""}${sel ? " sel" : ""}${fresh ? " fresh" : ""}"
        data-id="${e(id)}" tabindex="0" role="button" aria-label="${e(name)}${current ? ", you are here" : visited ? ", visited" : ", seen, not yet visited"}"
        transform="translate(${x} ${y})">
      <circle r="${17 * k}" class="hitpad" fill="transparent"/>
      ${current ? `<!--LIVE--><circle class="glow" cx="${x}" cy="${y}" r="${62 * k}" fill="url(#lantern)"/><circle class="glow" cx="${x}" cy="${y}" r="${30 * k}" fill="url(#lantern)"/><!--/LIVE-->` : ""}
      ${sel ? `<circle r="${19 * k}" fill="none" stroke="${RUBRIC}" stroke-width="${2.4 * k}"/>` : ""}
      <g transform="scale(${s})" filter="url(#ink)"><path d="${d}" fill="${fill}" fill-opacity=".55" stroke="${visited ? INK : PENCIL}"
        stroke-width="${visited ? 1.5 : 1.1}" stroke-linejoin="round" stroke-linecap="round" ${visited ? "" : 'stroke-dasharray="2.5 2"'} pathLength="100"/></g>
      ${badge ? `<g transform="translate(${13 * k} ${-13 * k})"><circle r="${7 * k}" fill="#f3ead6" stroke="${INK}" stroke-width="${k}"/>
        <text y="${3.6 * k}" text-anchor="middle" style="font:600 ${10 * k}px var(--body)" fill="${INK}">${badge}</text></g>` : ""}
      ${down ? `<g class="down" transform="translate(${-14 * k} ${12 * k})"><circle r="${7.5 * k}" fill="${LAPIS}"/>
        <text y="${4 * k}" text-anchor="middle" style="font:700 ${11 * k}px var(--body)" fill="#f3ead6">↓</text></g>` : ""}
    </g>`;
  }

  function render() {
    if (!V || !vb) return;
    const v = V;
    let body = "";
    if (v.level === "town") body = town(v);
    else if (v.level === "region") body = region(v);
    else body = site(v);
    const L = v.light;
    // The hour: one wash of the clock's colour over the sheet, multiplied into the paper.
    const tint = `<rect class="tint" x="${vb[0] - 3000}" y="${vb[1] - 3000}" width="${vb[2] + 6000}" height="${vb[3] + 6000}"
      fill="rgb(${L.r},${L.g},${L.b})" opacity="${L.a}" style="mix-blend-mode:multiply" pointer-events="none"/>`;
    if (V.level === "site") fogHoles = null;
    const moving = [];
    const still = body.replace(/<!--LIVE-->([\s\S]*?)<!--\/LIVE-->/g, (_, m) => { moving.push(m); return ""; });
    svg.innerHTML = defs() + still.replace("<!--TINT-->", tint);
    live.innerHTML = moving.join("");
    svg.setAttribute("aria-label", v.level === "town" ? "Featherperch, the places you have found" : v.level === "region" ? "The region" : v.site.name);
  }

  // --- Town -------------------------------------------------------------------------------
  function town(v) {
    const { T, L, F } = v, out = [];
    const P = i => M.anchor(L, i);
    const dirOf = i => { if (i === L.square) return "square"; const c = L.kind[i] === "crossing" ? i : L.street[i];
      const m = /(north|east|south|west)-crossing/.exec(c || ""); return m ? m[1] : "square"; };
    const found = [...F.found].filter(i => P(i));
    const box = [-900, -1000, 900, 700];
    // Washes: a wet blot of the ward's colour under every place found; they run together.
    out.push(`<g filter="url(#wash)" opacity=".5">${found.filter(i => v.T.settings[i] === "in").map(i => { const [x, y] = P(i);
      return `<circle cx="${x}" cy="${y}" r="${F.visited.has(i) ? 62 : 46}" fill="${WASH[dirOf(i)]}"/>`; }).join("")}</g>`);
    // The wall: a pen ring with the gate in it, and the ditch outside it.
    const gp = L.gate ? L.pos[L.gate] : [0, -405];
    const wr = Math.hypot(gp[0], gp[1]);
    out.push(`<g filter="url(#ink)" fill="none" stroke="${INK}" stroke-opacity=".55">
      <circle r="${wr}" stroke-width="${2.6 * k}" stroke-dasharray="${wr * .08} ${wr * .0001}"/>
      <circle r="${wr + 9}" stroke-width="${.8 * k}" stroke-dasharray="${3 * k} ${4 * k}"/></g>`);
    // Streets: double pen strokes from the square to each crossing found and on to the gate.
    const street = (a, b, w, dashed) => `<path d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}" stroke="${INK}" stroke-width="${w}" stroke-linecap="round"${dashed ? ` stroke-dasharray="${6 * k} ${5 * k}"` : ""}/>
      <path d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}" stroke="#efe4c8" stroke-width="${w - 3.2 * k}" stroke-linecap="round"/>`;
    const lines = [];
    Object.values(L.crossings).forEach(c => { if (F.found.has(c)) lines.push(street([0, 0], L.pos[c], 13 * k)); });
    if (L.gate && F.found.has(L.gate)) lines.push(street(L.pos[L.street[L.gate]], L.pos[L.gate], 11 * k));
    found.forEach(i => {
      const s = L.street[i]; if (!s || L.kind[i] === "crossing" || L.kind[i] === "gate") return;
      const [x, y] = P(i), [sx, sy] = L.pos[s];
      // A lane meets its street square-on, at the point level with the place.
      const foot = sx === 0 && s !== L.square ? [0, y] : sy === 0 && s !== L.square ? [x, 0] : [sx, sy];
      lines.push(`<path d="M${foot[0]} ${foot[1]}L${x} ${y}" stroke="${F.visited.has(i) ? INK : PENCIL}" stroke-width="${1.4 * k}" stroke-opacity=".8"${F.visited.has(i) ? "" : ` stroke-dasharray="${3 * k} ${3 * k}"`}/>`);
    });
    // Outside the gate: the apron, then the roads leaving as labelled arrows.
    const outside = found.filter(i => ["apron", "roadhead", "sign"].includes(L.kind[i]));
    if (L.gate && outside.length) {
      const crossroads = found.find(i => /crossroads$/.test(i)) || found.find(i => /outskirts$/.test(i));
      const cr = crossroads ? L.pos[crossroads] : gp;
      lines.push(`<path d="M${gp[0]} ${gp[1]}L${cr[0]} ${cr[1]}" stroke="${INK}" stroke-width="${2 * k}" stroke-dasharray="${7 * k} ${5 * k}" fill="none"/>`);
      outside.filter(i => L.kind[i] !== "apron").forEach(i => {
        const [x, y] = L.pos[i];
        lines.push(`<path d="M${cr[0]} ${cr[1]}Q${(cr[0] + x) / 2} ${cr[1] - 20} ${x} ${y}" stroke="${F.visited.has(i) ? INK : PENCIL}" stroke-width="${1.6 * k}" stroke-dasharray="${6 * k} ${5 * k}" fill="none"/>`);
      });
    }
    out.push(`<g filter="url(#ink)">${lines.join("")}</g>`);
    out.push(fogLayer(found.map(P), 125, box));
    // Stubs: a way out of a place only seen, a short stroke into the paper toward its seat.
    out.push(`<g class="stubs">${F.stubs.map(s => { const a = P(s.from), b = s.to && P(s.to); if (!a || !b) return "";
      const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1, len = Math.min(34, d * .4);
      return `<path d="M${a[0]} ${a[1]}l${dx / d * len} ${dy / d * len}" stroke="${PENCIL}" stroke-width="${1.5 * k}" stroke-linecap="round" opacity=".55"/>`; }).join("")}</g>`);
    // The route: lapis, marching toward where it goes.
    if (v.route) {
      const pts = v.route.map(P).filter(Boolean);
      out.push(`<!--LIVE--><path class="route" d="M${pts.map(p => p.join(" ")).join("L")}" fill="none" stroke="${LAPIS}" stroke-width="${3.4 * k}"
        stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="${9 * k} ${7 * k}"/><!--/LIVE-->`);
    }
    // Roads out: arrows past the board's edge with where they go and how long.
    const roads = [];
    found.filter(i => L.kind[i] === "roadhead").forEach(i => {
      const [x, y] = L.pos[i], j = (T.ways[i] || []).find(w => w.journey);
      const to = String(T.names[i]).replace(/^the road to /, "");
      const days = j ? j.time_words.replace(/^about /, "").replace(/ on foot$/, "") : "";
      roads.push(`<g class="roadout" data-id="${e(i)}" tabindex="0" role="button" aria-label="${e(T.names[i])}${days ? ", " + days : ""}">
        <path d="M${x} ${y}V${y - 46}M${x - 6 * k} ${y - 40 + 0}L${x} ${y - 50}L${x + 6 * k} ${y - 40}" stroke="${F.visited.has(i) ? INK : PENCIL}" stroke-width="${2 * k}" fill="none" filter="url(#ink)"/>
        <rect x="${x - 50}" y="${y - 50}" width="100" height="60" fill="transparent"/>
        <text x="${x}" y="${y - 58 - 14 * k}" text-anchor="middle" class="lbl roadlbl${F.visited.has(i) ? "" : " seen"}" style="font-size:${13.5 * k}px;stroke-width:${3.2 * k}px">${e(to)}</text>
        <text x="${x}" y="${y - 58}" text-anchor="middle" class="lbl days" style="font-size:${12 * k}px;stroke-width:${3 * k}px">${days ? e(days) : "unwalked"}</text></g>`);
    });
    out.push(roads.join(""));
    // Places.
    const order = found.filter(i => L.kind[i] !== "roadhead" && L.pos[i])
      .sort((a, b) => (b === v.here) - (a === v.here) || F.visited.has(b) - F.visited.has(a) || a.localeCompare(b));
    const sideOf = placeNames(order.map(i => [...L.pos[i], M.bare(T.names[i]), L.label[i] || "right", !F.visited.has(i), /keep|gate$/.test(i)]));
    const glyphs = [], names = [];
    order.forEach((i, n) => {
      const [x, y] = L.pos[i], fl = (L.floors[i] || []).map(M.floorOf);
      const storeys = fl.filter(f => f > 0).length;
      const site = MapUI.siteFor(i) || (fl.some(f => f < 0) ? "" : "");
      const hereHere = M.baseOf(v.here) === i;
      glyphs.push(glyph(i, x, y, T.names[i], { visited: F.visited.has(i), current: hereHere, sel: v.sel === i,
        fresh: v.fresh.has(i), wash: WASH[dirOf(i)], badge: storeys ? storeys + 1 : "", down: !!site }));
      names.push(label(x, y, M.bare(T.names[i]), sideOf[n], F.visited.has(i) ? (hereHere ? "here" : "") : "seen"));
    });
    out.push(glyphs.join(""), `<g class="names">${names.join("")}</g>`);
    // Lamps come on at night along the streets of places you know.
    if (v.light.night) out.push(`<!--LIVE--><g class="lamps">${found.filter(i => F.visited.has(i) && L.pos[i]).map(i => { const [x, y] = L.pos[i];
      return `<circle cx="${x + 9 * k}" cy="${y - 10 * k}" r="${16 * k}" fill="url(#lamp)" class="lamp"/>`; }).join("")}</g><!--/LIVE-->`);
    // Living things: smoke from chimneys you know, a banner on the keep and the gate.
    out.push(`<!--LIVE--><g class="smoke" pointer-events="none">${found.filter(i => F.visited.has(i) && smokes.test(T.names[i]) && L.pos[i])
      .map((i, n) => { const [x, y] = L.pos[i]; return `<g data-x="${x + 5 * k}" data-y="${y - 14 * k}" data-n="${n}"></g>`; }).join("")}</g><!--/LIVE-->`);
    out.push(`<!--LIVE--><g class="banners" pointer-events="none">${found.filter(i => /keep|gate$/.test(i) && L.pos[i]).map(i => { const [x, y] = L.pos[i];
      return `<g transform="translate(${x + (i === L.gate ? -10 : 2) * k} ${y - 16 * k}) scale(${k})"><path d="M0 0V-16" stroke="${INK}" stroke-width="1.2"/><path class="flag" d="M0-16H12L9-12.5 12-9H0" fill="${RUBRIC}"/></g>`; }).join("")}</g><!--/LIVE-->`);
    out.push("<!--TINT-->");
    out.push(cartouche("Featherperch", "a town of the Sunkeep Reaches"), compass());
    return out.join("");
  }

  // The cartouche and the compass rose sit in the sheet's corners, in screen units.
  function cartouche(title, sub) {
    const x = vb[0] + 18 * k, y = vb[1] + vb[3] - 78 * k, w = Math.max(title.length * 15, sub.length * 7.4) * k + 40 * k;
    return `<g class="cartouche" pointer-events="none" transform="translate(${x} ${y})">
      <path d="M0 6Q0 0 6 0H${w - 6}Q${w} 0 ${w} 6V${54 * k}Q${w} ${60 * k} ${w - 6} ${60 * k}H6Q0 ${60 * k} 0 ${54 * k}Z" fill="#f3ead6" fill-opacity=".85" stroke="${INK}" stroke-width="${1.4 * k}"/>
      <path d="M${6 * k} ${6 * k}H${w - 6 * k}V${54 * k}H${6 * k}Z" fill="none" stroke="${INK}" stroke-width="${.6 * k}"/>
      <text x="${w / 2}" y="${30 * k}" text-anchor="middle" style="font:600 ${21 * k}px var(--display);letter-spacing:.06em" fill="${INK}">${e(title)}</text>
      <text x="${w / 2}" y="${47 * k}" text-anchor="middle" style="font:italic ${12 * k}px var(--body)" fill="#4a3a2a">${e(sub)}</text></g>`;
  }
  function compass() {
    const x = vb[0] + vb[2] - 52 * k, y = vb[1] + vb[3] - 56 * k, s = k;
    return `<g class="compass" pointer-events="none" transform="translate(${x} ${y}) scale(${s})" filter="url(#ink)">
      <circle r="30" fill="none" stroke="${INK}" stroke-width=".8"/><circle r="24" fill="none" stroke="${INK}" stroke-width=".5"/>
      <path d="M0-38L6-6 38 0 6 6 0 38-6 6-38 0-6-6Z" fill="#f3ead6" stroke="${INK}" stroke-width="1"/>
      <path d="M0-38L6-6 0 0ZM38 0L6 6 0 0ZM0 38L-6 6 0 0ZM-38 0L-6-6 0 0Z" fill="${INK}"/>
      <text y="-42" text-anchor="middle" style="font:600 12px var(--display)" fill="${RUBRIC}">N</text></g>`;
  }

  // --- Region -----------------------------------------------------------------------------
  function region(v) {
    const { G } = v, out = [], P = i => G.pos[i];
    const shown = [...G.shown];
    // The sea off Ledgernook's docks, its waves shimmering.
    G.harbours.forEach(h => { const [x, y] = P(h.id);
      // No coastline in the export: the harbour gets a little water off its docks, nothing more.
      out.push(`<g class="sea" pointer-events="none"><ellipse cx="${x + 80}" cy="${y + 10}" rx="62" ry="52" fill="#8fb0c8" opacity=".45" filter="url(#wash)"/>
        <!--LIVE-->${[0, 1, 2, 3].map(n => `<path class="wave" data-n="${n}" d="M${x + 58 + (n % 2) * 22} ${y - 18 + n * 14}q6-5 12 0t12 0" stroke="#3d6a8a" stroke-width="${1.3 * k}" fill="none"/>`).join("")}<!--/LIVE-->
        <text x="${x + 80}" y="${y + 74}" text-anchor="middle" class="lbl seen" style="font-size:${12 * k}px;stroke-width:${3 * k}px">docks: ${h.ports.length} ports by sea</text></g>`); });
    // Roads and rivers, with a notch for every day: where journey events will be pinned.
    out.push(`<g filter="url(#ink)">${G.roads.map(r => { const a = P(r.a), b = P(r.b), river = r.by === "river";
      const known = v.visited.has(r.a) && v.visited.has(r.b);
      const ticks = []; for (let d = 1; d < r.days; d++) { const t = d / r.days, x = a[0] + (b[0] - a[0]) * t, y = a[1] + (b[1] - a[1]) * t;
        const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / L * 5 * k, ny = (b[0] - a[0]) / L * 5 * k;
        ticks.push(`<path d="M${x - nx} ${y - ny}L${x + nx} ${y + ny}" stroke="${INK}" stroke-width="${1.2 * k}"/>`); }
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      return `<path d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}" stroke="${river ? "#3d6a8a" : known ? INK : PENCIL}" stroke-width="${(river ? 2.4 : 1.8) * k}" fill="none"${known || river ? "" : ` stroke-dasharray="${6 * k} ${5 * k}"`}/>${ticks.join("")}
        <text x="${mx}" y="${my - 6 * k}" text-anchor="middle" class="lbl days" style="font-size:${11.5 * k}px;stroke-width:${3 * k}px">${r.days} days${river ? " by river" : ""}</text>`; }).join("")}</g>`);
    out.push(fogLayer([...shown.map(P), ...G.wild.map(w => w.pos)], 150, [-1400, -1200, 1600, 1300]));
    if (v.route) { const [a, b] = v.route.map(i => P(i) || (G.wild.find(w => w.id === i) || {}).pos).filter(Boolean).length === 2 ? v.route.map(i => P(i) || G.wild.find(w => w.id === i).pos) : [null, null];
      if (a) out.push(`<!--LIVE--><path class="route" d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}" stroke="${LAPIS}" stroke-width="${3.4 * k}" stroke-dasharray="${9 * k} ${7 * k}" stroke-linecap="round"/><!--/LIVE-->`); }
    const items = [], gl = [];
    shown.forEach(i => { const [x, y] = P(i), t = G.towns[i];
      gl.push(glyph(i, x, y, "walled", { visited: v.visited.has(i), current: i === v.here, sel: v.sel === i, wash: v.visited.has(i) ? "#c49a52" : "", badge: "", down: false }).replace(/aria-label="walled/, `aria-label="${e(t.name)}`));
      items.push([x, y, t.name, "below", !v.visited.has(i)]); });
    G.wild.forEach(w => { if (!v.wildFound.has(w.id)) return; const [x, y] = w.pos, vis = v.wildVisited.has(w.id);
      gl.push(glyph(w.id, x, y, w.name, { visited: vis, current: false, sel: v.sel === w.id, wash: w.kind === "desert" ? "#d8b878" : "#7f9a6a", badge: "", down: !!MapUI.siteFor(w.id) || w.kind === "cave" }));
      items.push([x, y, M.bare(w.name), "above", !vis]); });
    const sideOf = placeNames(items);
    out.push(gl.join(""), `<g class="names">${items.map((it, n) => label(it[0], it[1], it[2], sideOf[n], it[4] ? "seen" : (G.towns[shown[n]] && shown[n] === v.here ? "here" : ""))).join("")}</g>`);
    out.push("<!--TINT-->", cartouche("The Sunkeep Reaches", "towns a journey apart, as far as you know them"), compass());
    return out.join("");
  }

  // --- Site ---------------------------------------------------------------------------------
  // A room's name in its box: two lines when long, as large as the zoom allows.
  function roomName(x, y, name, been) {
    const fs = Math.min(13.5 * k, 21), words = name.split(" ");
    let lines = [name];
    if (name.length > 10 && words.length > 1) { let best = 1, gap = 1e9;
      for (let i = 1; i < words.length; i++) { const d = Math.abs(words.slice(0, i).join(" ").length - words.slice(i).join(" ").length); if (d < gap) { gap = d; best = i; } }
      lines = [words.slice(0, best).join(" "), words.slice(best).join(" ")]; }
    const y0 = y + fs * .35 - (lines.length - 1) * fs * .55;
    return `<text text-anchor="middle" class="lbl${been ? "" : " seen"}" style="font-size:${fs}px;stroke-width:0">${lines.map((l, i) =>
      `<tspan x="${x}" y="${y0 + i * fs * 1.1}">${e(l)}</tspan>`).join("")}</text>`;
  }
  const sitePos = (v, id) => [v.S.col[id] * 160, v.S.row[id] * 100];
  function site(v) {
    const { S, site: s } = v, out = [], seen = new Set();
    s.been.forEach(i => (S.adj[i] || []).forEach(n => { if (!s.been.has(n)) seen.add(n); }));
    const ids = Object.keys(S.col), xs = ids.map(i => sitePos(v, i)[0]), ys = ids.map(i => sitePos(v, i)[1]);
    out.push(`<rect x="${Math.min(...xs) - 400}" y="${Math.min(...ys) - 300}" width="${Math.max(...xs) - Math.min(...xs) + 800}" height="${Math.max(...ys) - Math.min(...ys) + 600}" fill="url(#grid)"/>`);
    // Passages: drawn where either end has been entered.
    out.push(`<g filter="url(#ink)">${S.passages.map(([a, b, kind]) => { if (!s.been.has(a) && !s.been.has(b)) return "";
      const p = sitePos(v, a), q = sitePos(v, b), mid = (p[0] + q[0]) / 2;
      const d = `M${p[0]} ${p[1]}H${mid}V${q[1]}H${q[0]}`;
      return `<path d="${d}" stroke="${INK}" stroke-width="${14}" fill="none" stroke-linejoin="round"/><path d="${d}" stroke="#efe4c8" stroke-width="${11}" fill="none" stroke-linejoin="round"/>
        ${kind === "side" ? `<path d="${d}" stroke="${PENCIL}" stroke-width="1" stroke-dasharray="3 3" fill="none"/>` : ""}`; }).join("")}</g>`);
    if (v.route) out.push(`<!--LIVE--><path class="route" d="M${sitePos(v, v.route[0]).join(" ")}${v.route.slice(1).map((i, n) => {
      const p = sitePos(v, v.route[n]), q = sitePos(v, i), mid = (p[0] + q[0]) / 2; return `H${mid}V${q[1]}H${q[0]}`; }).join("")}" stroke="${LAPIS}" stroke-width="${3.4 * k}" stroke-dasharray="${9 * k} ${7 * k}" fill="none" stroke-linecap="round"/><!--/LIVE-->`);
    ids.forEach(i => {
      const [x, y] = sitePos(v, i), r = s.rooms.find(q => q.id === i);
      const been = s.been.has(i), known = been || seen.has(i);
      if (!known) return;  // unexplored: blank paper
      const here = i === v.here, w = 128, h = 70;
      out.push(`<g class="place room${been ? " been" : " seen"}${here ? " here" : ""}${v.sel === i ? " sel" : ""}" data-id="${e(i)}" tabindex="0" role="button" aria-label="${e(r.name)}${here ? ", you are here" : been ? ", entered" : ", seen, not yet entered"}">
        ${here ? `<!--LIVE--><circle cx="${x}" cy="${y}" r="90" fill="url(#lantern)" class="glow"/><!--/LIVE-->` : ""}
        <rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="3" fill="${been ? "#efe4c8" : "rgba(239,228,200,.4)"}" stroke="${v.sel === i ? RUBRIC : been ? INK : PENCIL}"
          stroke-width="${v.sel === i ? 3 : 1.8}" ${been ? "" : 'stroke-dasharray="6 4"'} filter="url(#ink)"/>
        ${been && r.door ? `<rect x="${x - w / 2 - 5}" y="${y - 6}" width="8" height="12" fill="#7a5a34" stroke="${INK}"/>` : ""}
        ${r.role === "climax" && been ? `<path d="M${x + w / 2 - 20} ${y - h / 2 + 6}l6 10 6-10" fill="${RUBRIC}"/>` : ""}
        ${roomName(x, y, been ? M.bare(r.name) : "?", been)}</g>`);
    });
    out.push("<!--TINT-->", cartouche(M.upper(s.name), s.from), compass());
    return out.join("");
  }

  // --- The live bits: lantern breath, smoke, banners, waves, the route's march, rain. ------
  function loop() {
    cancelAnimationFrame(raf);
    const tick = now => {
      raf = requestAnimationFrame(tick);
      const t = (now - t0) / 1000, still = api.reduced();
      if (still) { rain(t, true); return; }
      live.querySelectorAll(".glow").forEach(g => g.setAttribute("opacity", (.78 + .22 * Math.sin(t * 2.1) * Math.sin(t * 3.7 + 1)).toFixed(3)));
      live.querySelectorAll(".lamp").forEach((g, n) => g.setAttribute("opacity", (.75 + .25 * Math.sin(t * 5 + n * 1.7)).toFixed(3)));
      const r = live.querySelector(".route"); if (r) r.setAttribute("stroke-dashoffset", (-t * 22 * k).toFixed(1));
      live.querySelectorAll(".flag").forEach((f, n) => { const w = Math.sin(t * 4 + n) * 1.6;
        f.setAttribute("d", `M0-16Q6 ${-17 + w} 12 ${-16 - w * .5}L${9 + w * .3}-12.5 12 ${-9 + w * .5}Q6 ${-8 - w} 0-9`); });
      live.querySelectorAll(".wave").forEach((w, n) => w.setAttribute("transform", `translate(${(Math.sin(t * .9 + n) * 6).toFixed(1)} 0)`));
      live.querySelectorAll(".wave").forEach((w, n) => w.setAttribute("opacity", (.4 + .4 * Math.sin(t * 1.6 + n * 1.3)).toFixed(2)));
      live.querySelectorAll(".smoke > g").forEach(g => {
        const x = +g.dataset.x, y = +g.dataset.y, n = +g.dataset.n;
        let html = "";
        for (let p = 0; p < 4; p++) { const a = ((t * .35 + p / 4 + n * .13) % 1);
          html += `<circle cx="${(x + Math.sin(a * 6 + n) * 4 * k + a * 10 * k).toFixed(1)}" cy="${(y - a * 34 * k).toFixed(1)}" r="${((2 + a * 6) * k).toFixed(1)}" fill="#6a5d4e" opacity="${(.32 * (1 - a)).toFixed(2)}"/>`; }
        g.innerHTML = html; });
      rain(t, false);
    };
    raf = requestAnimationFrame(tick);
  }
  let drops = [];
  // The drifting cloud over the fog: a 2D canvas, the cloud texture slid across it, with a soft
  // hole cut round every place found. In SVG this was a masked layer re-rasterised every frame.
  function drift(c, t) {
    if (!fogHoles || !vb) return;
    if (!cloudImg) { cloudImg = new Image(); cloudImg.src = cloudTex(); }
    if (!cloudImg.complete) return;
    const W = rainCv.width, H = rainCv.height, sz = 900 / k;
    const pat = c.createPattern(cloudImg, "repeat");
    pat.setTransform(new DOMMatrix().translateSelf((-vb[0] / k) % sz + Math.sin(t * .05) * 140 / k, (-vb[1] / k) % sz + Math.cos(t * .04) * 20 / k).scaleSelf(sz / 256));
    c.save(); c.globalAlpha = .55; c.fillStyle = pat; c.fillRect(0, 0, W, H); c.restore();
    c.save(); c.globalCompositeOperation = "destination-out";
    fogHoles.pts.forEach(([x, y]) => { const sx = (x - vb[0]) / k, sy = (y - vb[1]) / k, r = fogHoles.r / k;
      if (sx < -r || sy < -r || sx > W + r || sy > H + r) return;
      const g = c.createRadialGradient(sx, sy, r * .3, sx, sy, r); g.addColorStop(0, "#000"); g.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = g; c.fillRect(sx - r, sy - r, r * 2, r * 2); });
    c.restore();
  }
  function rain(t, still) {
    const c = rainCv.getContext("2d"), W = rainCv.width, H = rainCv.height;
    c.clearRect(0, 0, W, H);
    drift(c, still ? 0 : t);
    if (!V || !V.rain) return;
    c.fillStyle = "rgba(60,70,90,.12)"; c.fillRect(0, 0, W, H);
    if (drops.length < 260) drops = Array.from({ length: 260 }, () => [Math.random() * W, Math.random() * H, .6 + Math.random() * .8]);
    c.strokeStyle = "rgba(50,62,84,.38)"; c.lineWidth = 1; c.beginPath();
    drops.forEach(d => { if (!still) { d[1] += 14 * d[2]; d[0] -= 3 * d[2]; if (d[1] > H) { d[1] = -10; d[0] = Math.random() * W * 1.1; } }
      c.moveTo(d[0], d[1]); c.lineTo(d[0] + 3 * d[2], d[1] - 12 * d[2]); });
    c.stroke();
  }

  // --- Walking: the lantern carried along the route, then the new ink. -------------------
  function walk(ids, done) {
    const v = V;
    const P = i => v.level === "town" ? M.anchor(v.L, i) : v.level === "region" ? (v.G.pos[i] || v.G.wild.find(w => w.id === i).pos) : sitePos(v, i);
    const pts = ids.map(P).filter(Boolean);
    if (api.reduced() || pts.length < 2) { done(); return; }
    const seg = [], tot = pts.slice(1).reduce((s, p, n) => { const d = Math.hypot(p[0] - pts[n][0], p[1] - pts[n][1]); seg.push(d); return s + d; }, 0);
    const g = document.createElementNS(NS, "g");
    g.innerHTML = `<circle r="${40 * k}" fill="url(#lantern)"/><circle r="${6 * k}" fill="${LAPIS}" stroke="#f3ead6" stroke-width="${2 * k}"/>`;
    live.appendChild(g);
    const dur = Math.min(2600, 500 + tot * 2.2), start = performance.now();
    // A hidden window gets no animation frames; the walk still ends on time.
    let over = false; const finish = () => { if (over) return; over = true; g.remove(); done(); };
    setTimeout(finish, dur + 400);
    const step = now => {
      if (over) return;
      const u = Math.min(1, (now - start) / dur), ease = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      let d = ease * tot, n = 0; while (n < seg.length - 1 && d > seg[n]) { d -= seg[n]; n++; }
      const a = pts[n], b = pts[n + 1], f = seg[n] ? d / seg[n] : 1;
      g.setAttribute("transform", `translate(${a[0] + (b[0] - a[0]) * f} ${a[1] + (b[1] - a[1]) * f})`);
      if (u < 1) requestAnimationFrame(step); else finish();
    };
    requestAnimationFrame(step);
  }

  return { init, draw, walk };
})();
