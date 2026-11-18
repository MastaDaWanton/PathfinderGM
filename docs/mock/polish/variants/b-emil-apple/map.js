// b-emil-apple: the game's board code (release 0.2.29, 7f63ab60), changed where it says
// "b-emil-apple". Everything else is the Current copy, comments included.

// --- play/static/js/table/03-offers-and-map.js, lines 52-281 (the map, renderMap) ---
// --- the map -------------------------------------------------------------------------
//
// Drawn as an SVG rather than a grid of divs: a 20x20 map is 400 elements either way, and
// the SVG version scales to the panel without every square needing its own size in pixels.
//
// The reachable squares are computed by the engine and sent down, never worked out here.
// Two implementations of the alternating diagonal rule would eventually disagree, and the
// one on screen is the one the player would believe.
// Which floor of the room the map is showing. Not part of STATE: it is a way of looking
// at the board, not a fact about it, and putting it in the server's payload would make
// the server responsible for where the player's attention is.
let MAP_LEVEL = 0;
// Which way the board is being looked at, and whether it is being looked at flat. Both
// are ways of looking rather than facts about the scene, so neither belongs in STATE —
// the server is not responsible for where the player's attention is.
let MAP_TURN = 0, MAP_3D = false;

function renderMap(s) {
  const g = s.scene.grid;
  if (!g) {
    $("#mapwrap").innerHTML = "";
    $("#groundctl").innerHTML = "";
    $("#boardframe").dataset.ground = "The ground";
    if (typeof mapPaint === "function") mapPaint();
    return;
  }

  const CELL = 18;
  const reach = new Map((g.reachable || []).map(([c, r, cost]) => [`${c},${r}`, cost]));
  const parts = [];
  // b-emil-apple: the previews, the lamp and the labels, read once for both views.
  const P = Polish.read(s);
  const seg = (e, cls) => `<line class="${cls}" x1="${e[0] * CELL}" y1="${e[1] * CELL}" x2="${
    e[2] * CELL}" y2="${e[3] * CELL}"/>`;

  const levels = (g.levels && g.levels.length > 1) ? g.levels : [0];
  if (!levels.includes(MAP_LEVEL)) MAP_LEVEL = levels[0];
  const ground = new Map((g.floor || []).map(([c, r, v]) => [`${c},${r}`, v]));
  const at = (c, r) => ground.get(`${c},${r}`) || 0;

  for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
  for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
  for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
  for (const [c, r, v] of (g.floor || []))
    parts.push(cell(c, r, `up${Math.min(3, v)}`,
      `<title>${v * 5} ft above the floor</title>`));
  // b-emil-apple: raised ground gets a lip, lit on its north and west edges and shadowed
  // on its south and east (the theme's own --bevel direction, light from the top left),
  // so a wall-walk reads as standing up from the floor rather than as a paler stripe.
  const raisedSet = {};
  for (const [c, r] of (g.floor || [])) raisedSet[`${c},${r}`] = true;
  // b-emil-apple: what the PC cannot see, veiled under the grid so the squares still read.
  for (const k of Object.keys(P.unseen)) {
    const [c, r] = k.split(",").map(Number);
    parts.push(cell(c, r, "unseen", "<title>Out of your sight</title>"));
  }
  for (const [c, r, v] of (g.parapet || []))
    parts.push(`<line class="rail" x1="${c * CELL + 2}" y1="${(r + .5) * CELL}" x2="${
      (c + 1) * CELL - 2}" y2="${(r + .5) * CELL}"><title>a rail, ${
      v * 5} ft up</title></line>`);

  for (const [key, cost] of reach) {
    const [c, r] = key.split(",").map(Number);
    const lvl = at(c, r);
    // b-emil-apple: a square whose move provokes keeps the gold wash and gains the alarm
    // hatch (drawn over it below); the rest are lit brighter as safe. Hatch rather than a
    // red fill: with two goblins beside her nearly every square provokes, and a board
    // washed red tells the player nothing they can act on. The few bright squares that do
    // not provoke are the decision.
    const kind = (P.provokes[key] || []).length ? "prov" : "safe";
    parts.push(cell(c, r, `reach ${kind}`, `<title>${cost} ft${
        lvl ? ` · ${lvl * 5} ft up` : ""}</title>`)
      .replace(`class="reach ${kind}"`, `class="reach ${kind}" data-cost="${cost}" data-sq="${
        c},${r}${lvl ? "," + lvl : ""}"`));
  }
  for (const [key] of reach) if ((P.provokes[key] || []).length) {
    const [c, r] = key.split(",").map(Number);
    parts.push(`<rect class="provhatch" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${
      CELL}" fill="url(#provhatch)" pointer-events="none"/>`);
  }

  // The latest turn's spell areas, as the game draws them; b-emil-apple adds the area's
  // outline, so the template reads as one shape rather than a scatter of orange squares.
  const spellAreas = (g.areas || []).filter(a => a && (a.cells || []).length);
  if (spellAreas.length && !MAP_3D) {
    const shown = new Map();
    for (const a of spellAreas) {
      for (const cellAt of a.cells) {
        const [c, r] = cellAt;
        const z = cellAt.length > 2 ? cellAt[2] : 0;
        const key = `${c},${r}`;
        const here = z - at(c, r) === MAP_LEVEL || z === MAP_LEVEL;
        const was = shown.get(key);
        if (!was || (here && !was.here)) shown.set(key, { c, r, here, spell: a.spell });
      }
    }
    const hereSet = {};
    for (const { c, r, here, spell } of shown.values()) {
      const name = String(spell || "a spell").replace(/-/g, " ");
      if (here) hereSet[`${c},${r}`] = true;
      parts.push(`<rect class="spellarea${here ? "" : " offlevel"}" x="${c * CELL}" y="${
        r * CELL}" width="${CELL}" height="${CELL}" fill="#e0701e" fill-opacity="${
        here ? 0.3 : 0}" stroke="#f0a050" stroke-opacity="${here ? 0.18 : 0.8}"
        stroke-width="${here ? 0.5 : 1.2}"${here ? "" : ` stroke-dasharray="3 2"`}
        pointer-events="none"><title>${esc(name)}${here ? "" : ", above or below this floor"
        }</title></rect>`);
    }
    for (const e of Polish.edges(hereSet)) parts.push(seg(e, "spelledge"));
  }

  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);
  for (const e of Polish.edges(raisedSet))
    parts.push(seg(e, e[4] === "n" || e[4] === "w" ? "lip-lit" : "lip-shade"));

  // b-emil-apple: the room lamp, over the ground and under everyone standing on it. The
  // ground takes the hour's colour and strength; tokens and previews keep full contrast.
  const L = P.lamp;
  const lampRGB = L.tint.map(v => Math.round(255 * Math.min(1, v * L.strength))).join(",");
  if (lampRGB !== "255,255,255")
    parts.push(`<rect class="lamp" x="0" y="0" width="${g.width * CELL}" height="${
      g.height * CELL}" fill="rgb(${lampRGB})" pointer-events="none"/>`);

  // b-emil-apple: the threatened squares, as one outline round all of them: the edge you
  // cross is what matters, and an outline leaves the safe/provokes wash readable inside it.
  for (const e of Polish.edges(P.threat)) parts.push(seg(e, "threatedge"));
  // Each foe's own reach, filled only while that foe is pointed at (`.foehot`).
  for (const ref of Object.keys(P.threatBy)) for (const [c, r] of P.threatBy[ref])
    parts.push(`<rect class="threatfill" data-of="${esc(ref)}" x="${c * CELL}" y="${
      r * CELL}" width="${CELL}" height="${CELL}" pointer-events="none"/>`);

  // b-emil-apple: a hunch is a range, never a square. A dashed ring of the notice range
  // round the PC, and nothing inside it marked.
  if (P.pc && P.pc.at && P.hunches.length) {
    const ft = P.hunches[0].within_ft;
    parts.push(`<circle class="hunch" cx="${(P.pc.at[0] + .5) * CELL}" cy="${
      (P.pc.at[1] + .5) * CELL}" r="${(ft / 5 + .5) * CELL}" pointer-events="none"/>`);
  }

  for (const b of (s.scene.pools || [])) {
    if (!b.at) continue;
    parts.push(`<circle class="bloodpool" cx="${(b.at[0] + .5) * CELL}" cy="${
      (b.at[1] + .5) * CELL}" r="${CELL * .38}">
      <title>blood pool — ${esc(b.source || b.owner)}</title></circle>`);
  }

  for (const a of s.scene.actors) {
    if (!a.at) continue;
    const [c, r] = a.at;
    const n = a.squares || 1;
    const down = a.hp <= 0;
    const side = a.stance ? ` ${a.stance}` : (s.scene.in_encounter ? " bystander" : "");
    const mine = (a.at.length > 2 ? a.at[2] : 0) === MAP_LEVEL;
    const ghost = mine ? "" : " offlevel";
    const unit = a.members != null;
    // b-emil-apple: whose turn it is, as a still ring of candlelight just outside the
    // token. Still on purpose: a pulse is looping motion beside every control on the page,
    // and the ring is found at a glance without it.
    if (P.turn && a.ref === P.turn)
      parts.push(`<rect class="turnring" x="${c * CELL + .5}" y="${r * CELL + .5}" width="${
        n * CELL - 1}" height="${n * CELL - 1}" rx="4.5" pointer-events="none"/>`);
    // b-emil-apple: caught by the spell on the board: an ember ring.
    if (P.caught.includes(a.ref))
      parts.push(`<rect class="caughtring" x="${c * CELL + .5}" y="${r * CELL + .5}" width="${
        n * CELL - 1}" height="${n * CELL - 1}" rx="4.5" pointer-events="none"/>`);
    // b-emil-apple: a foe is a thing you can point at, or reach with the keyboard, to see
    // your own attack against it.
    const foe = a.stance === "foe" && P.preview[a.ref];
    const hook = foe ? ` data-foe="${esc(a.ref)}" tabindex="0" role="button" aria-label="${
      esc(a.name)}, your attack"` : "";
    parts.push(`<rect class="token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}"${hook}
      x="${c * CELL + 2}" y="${r * CELL + 2}"
      width="${n * CELL - 4}" height="${n * CELL - 4}" rx="3">
      <title>${esc(a.name)} — ${a.hp}/${a.hp_max}${
        unit ? ` · ${a.members} of ${a.members_max} still standing` : ""}${
        a.at.length > 2 && a.at[2] ? ` · ${a.at[2] * 5} ft up` : ""}</title></rect>`);
    // b-emil-apple: down is a struck-through token, not only a fainter one.
    if (down)
      parts.push(`<line class="downmark" x1="${c * CELL + 4}" y1="${(r + n) * CELL - 4}" x2="${
        (c + n) * CELL - 4}" y2="${r * CELL + 4}" pointer-events="none"/>`);
    const label = P.labels[a.ref] || (unit ? a.members : a.name.slice(0, 1).toUpperCase());
    parts.push(`<text class="tok${String(label).length > 1 ? " two" : ""}${ghost}" x="${
      (c + n / 2) * CELL}" y="${(r + n / 2) * CELL + (String(label).length > 1 ? 2.6 : 3.2)}">${
      esc(label)}</text>`);
  }

  if (typeof COMBAT !== "undefined" && COMBAT.aim && !MAP_3D) {
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++)
      parts.push(`<rect class="aimsq" data-aimsq="${c},${r}" x="${c * CELL}" y="${r * CELL}"
        width="${CELL}" height="${CELL}" fill="transparent"><title>the north-west corner of ${
        c},${r}</title></rect>`);
  }

  const svg = MAP_3D
    ? Scene3D.render(g, s.scene.actors || [],
                     { turn: MAP_TURN, level: MAP_LEVEL,
                       reach: !!(STATE.scene && STATE.scene.in_encounter), polish: P })
    : `<svg id="map" viewBox="0 0 ${g.width * CELL} ${g.height * CELL}"
         preserveAspectRatio="xMidYMid meet"><defs>
         <pattern id="unithatch-foe" width="6" height="6" patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)">
           <rect width="6" height="6" fill="#7d1a14"></rect>
           <line x1="0" y1="0" x2="0" y2="6" stroke="#e0261e" stroke-width="3"></line>
         </pattern>
         <pattern id="unithatch-quiet" width="6" height="6" patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)">
           <rect width="6" height="6" fill="#d9d2c2"></rect>
           <line x1="0" y1="0" x2="0" y2="6" stroke="#f7f2e6" stroke-width="3"></line>
         </pattern>
         <pattern id="provhatch" width="4.5" height="4.5" patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)">
           <line x1="0" y1="0" x2="0" y2="4.5" class="hatchline"></line>
         </pattern>
       </defs>${parts.join("")}</svg>`;
  const pools = (s.scene.pools || []).length;
  const places = typeof mapShowingPlaces === "function" && mapShowingPlaces();
  const pressed = on => `class="v2-btn" aria-pressed="${on && !places ? "true" : "false"}"`;
  const view = `<div class="v2-recess" role="group" aria-label="View">
      <button type="button" data-mapview="flat" ${pressed(!MAP_3D)}>Flat</button>
      <button type="button" data-mapview="3d" ${pressed(MAP_3D)}>3D</button></div>${MAP_3D
      ? `<div class="v2-recess" role="group" aria-label="Turn the board">
          <button type="button" class="v2-btn" data-mapturn="-1"
                  aria-label="Turn the board left">Turn left</button>
          <button type="button" class="v2-btn" data-mapturn="1"
                  aria-label="Turn the board right">Turn right</button></div>` : ""}`;
  const picker = levels.length > 1
    ? `<div class="v2-recess" role="group" aria-label="Looking at"><span class="seglabel">Looking at</span>${
        levels.map(v => `<button type="button" data-maplevel="${v}" ${pressed(v === MAP_LEVEL)}>${
          v ? (v > 0 ? `+${v * 5} ft` : `${v * 5} ft`) : "the floor"}</button>`).join("")}</div>${
        g.ceiling ? `<span class="seglabel">ceiling ${g.ceiling * 5} ft</span>` : ""}`
    : "";
  // b-emil-apple: the foot is the place's line, then one readout line of fixed height that
  // answers whatever is pointed at (so nothing below it moves), the key, and the notes.
  const has = {
    safe: [...reach.keys()].some(k => !(P.provokes[k] || []).length),
    prov: [...reach.keys()].some(k => (P.provokes[k] || []).length),
    threat: Object.keys(P.threat).length > 0,
    unseen: Object.keys(P.unseen).length > 0,
    spell: !!P.spell,
  };
  const notes = Polish.notes(P);
  // The place's line, the count of squares and the pools join the notes in one paragraph:
  // four italic lines under the board took 60px from the board itself.
  // The notes (light, spell, hunch) lead, because on a phone the paragraph is cut to three
  // lines and those are the ones that change play.
  const lines = [
    ...notes,
    ...(g.speed ? [`${reach.size} squares within ${g.speed} ft`] : []),
    ...(pools ? [`${pools} pool${pools === 1 ? "" : "s"} of blood on the ground`] : []),
    ...(g.about ? [g.about.charAt(0).toUpperCase() + g.about.slice(1)] : []),
  ];
  $("#boardframe").dataset.ground = g.place ? `The ground · ${g.place}` : "The ground";
  $("#groundctl").innerHTML = view + picker;
  $("#mapwrap").innerHTML = `<div class="boardview lamp-${esc(P.lamp.phase || "none")}">${svg}
      <div id="foecard" class="foecard" role="tooltip"></div></div>
    <div class="boardfoot">
      <p id="boardreadout" class="boardreadout" aria-live="polite">${Polish.restLine(P)}</p>
      ${Polish.keyHtml(P, has)}
      ${lines.length ? `<p class="sub maplegend">${
        lines.map(n => esc(/\.$/.test(n) ? n : n + ".")).join(" ")}</p>` : ""}</div>`;
  if (typeof mapPaint === "function") mapPaint();

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
}

// --- play/static/js/table/16-tab-map.js, lines 38-80 (MAPV, mapShowingPlaces, mapPaint) ---
const MAPV = {
  places: false,  // the chart is shown instead of the ground
  sel: null,      // the place pressed on the chart
  said: "",       // the line the last Walk there left in the slip
  walk: null,     // { to, name, leg: {from, to, name} } while a walk is under way
  k: 1,           // the chart's drawing units per screen pixel (16-places-chart.js)
};

function mapShowingPlaces() { return MAPV.places; }

function mapPlacesData(s) {
  const pf = s && s.scene && s.scene.places_found;
  return pf && Array.isArray(pf.nodes) ? pf : null;
}

function mapPaint() {
  const frame = document.getElementById("boardframe");
  if (!frame) return;
  const places = MAPV.places;
  frame.classList.toggle("places", places);
  frame.classList.toggle("threed", !places && typeof MAP_3D !== "undefined" && MAP_3D);
  const btn = document.getElementById("placesbtn");
  if (btn) btn.setAttribute("aria-pressed", String(places));
  const ground = document.getElementById("groundctl");
  if (ground) {
    ground.style.visibility = places ? "hidden" : "";
    ground.querySelectorAll("[data-mapview]").forEach(b => {
      const on = !places && (b.dataset.mapview === "3d") === !!(typeof MAP_3D !== "undefined" && MAP_3D);
      b.setAttribute("aria-pressed", String(on));
    });
    ground.inert = places;
  }
  const wrap = document.getElementById("placeswrap");
  if (wrap) wrap.hidden = !places;
  const name = document.getElementById("board-name");
  if (name) {
    const pf = mapPlacesData(STATE);
    name.textContent = places ? ((pf && pf.where) || "The town") : (frame.dataset.ground || "The ground");
  }
}

// --- play/static/js/table/04-combat-and-turns.js, lines 636-642, the board's own controls ---
document.addEventListener("click", e => {
  const t = e.target;
  const lvl = t.closest("[data-maplevel]");
  if (lvl) { MAP_LEVEL = Number(lvl.dataset.maplevel); renderMap(STATE); return; }
  const vw = t.closest("[data-mapview]");
  if (vw) { MAP_3D = vw.dataset.mapview === "3d"; renderMap(STATE); return; }
  const trn = t.closest("[data-mapturn]");
  if (trn) { MAP_TURN = (MAP_TURN + Number(trn.dataset.mapturn) + 4) % 4;
             renderMap(STATE); return; }
});
