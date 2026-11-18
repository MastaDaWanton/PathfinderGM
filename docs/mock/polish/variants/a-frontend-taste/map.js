// Variant a-frontend-taste: renderMap from 03-offers-and-map.js (0.2.29), reworked for
// legibility and previews. mapPaint and the board's click handler below are unchanged.
// The data rules are the game's: reachable squares, areas and tokens come from the payload;
// the previews come from pvRead (preview.js), which reads only what the engine sent.

let MAP_LEVEL = 0;
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
  const pv = PV_NOW = pvRead(s);
  const reach = new Map((g.reachable || []).map(([c, r, cost]) => [`${c},${r}`, cost]));
  const parts = [];

  const levels = (g.levels && g.levels.length > 1) ? g.levels : [0];
  if (!levels.includes(MAP_LEVEL)) MAP_LEVEL = levels[0];
  const ground = new Map((g.floor || []).map(([c, r, v]) => [`${c},${r}`, v]));
  const at = (c, r) => ground.get(`${c},${r}`) || 0;
  const blocked = new Set((g.blocked || []).map(([c, r]) => `${c},${r}`));
  const inside = (c, r) => c >= 0 && r >= 0 && c < g.width && r < g.height;

  for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
  for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
  for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
  for (const [c, r, v] of (g.floor || []))
    parts.push(cell(c, r, `up${Math.min(3, v)}`,
      `<title>${v * 5} ft above the floor</title>`));

  // Raised ground reads as raised: the lamp is high and to the north-west (the 3D view's
  // LIGHT), so a platform's north and west lips catch it and it casts a short shadow on
  // the lower ground south and east of it. Only where the neighbour really is lower.
  for (const [c, r, v] of (g.floor || [])) {
    const x = c * CELL, y = r * CELL;
    if (at(c, r - 1) < v) parts.push(`<line class="lip" x1="${x}" y1="${y + .6}" x2="${x + CELL}" y2="${y + .6}"/>`);
    if (at(c - 1, r) < v) parts.push(`<line class="lip" x1="${x + .6}" y1="${y}" x2="${x + .6}" y2="${y + CELL}"/>`);
    const fall = Math.min(5, 2 * v);
    if (inside(c, r + 1) && at(c, r + 1) < v)
      parts.push(`<rect class="dropshade" x="${x}" y="${y + CELL}" width="${CELL}" height="${fall}"/>`);
    if (inside(c + 1, r) && at(c + 1, r) < v)
      parts.push(`<rect class="dropshade" x="${x + CELL}" y="${y}" width="${fall}" height="${CELL}"/>`);
  }

  // Rails as one continuous line along the way the run goes, as the 3D view already
  // draws them. Per-square horizontal ticks along a north-south rail read as rungs.
  const rails = new Map((g.parapet || []).map(([c, r, v]) => [`${c},${r}`, v]));
  for (const [c, r, v] of (g.parapet || [])) {
    const alongX = rails.has(`${c - 1},${r}`) || rails.has(`${c + 1},${r}`);
    const [x1, y1, x2, y2] = alongX
      ? [c * CELL, (r + .5) * CELL, (c + 1) * CELL, (r + .5) * CELL]
      : [(c + .5) * CELL, r * CELL, (c + .5) * CELL, (r + 1) * CELL];
    parts.push(`<line class="rail" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"><title>a rail, ${
      v * 5} ft up</title></line>`);
  }

  for (const [key, cost] of reach) {
    const [c, r] = key.split(",").map(Number);
    const lvl = at(c, r);
    parts.push(cell(c, r, "reach", `<title>${cost} ft${
        lvl ? `, ${lvl * 5} ft up` : ""}</title>`)
      .replace('class="reach"', `class="reach" data-sq="${c},${r}${
        lvl ? "," + lvl : ""}"`));
  }

  // The edge of how far you can go, drawn once round the whole region rather than as a
  // wash alone: the wash at 12% was nearly invisible on the dark stone. Squares inside the
  // region that are not destinations (people standing there) count as inside, so the edge
  // does not box each token; so does a gap the region surrounds on three sides.
  const occupied = new Set((s.scene.actors || []).filter(a => a.at)
    .map(a => `${a.at[0]},${a.at[1]}`));
  const inReach = (c, r) => reach.has(`${c},${r}`) || occupied.has(`${c},${r}`);
  const filled = (c, r) => {
    if (!inside(c, r)) return false;
    if (inReach(c, r)) return true;
    if (blocked.has(`${c},${r}`)) return false;
    return [[0, -1], [0, 1], [-1, 0], [1, 0]].filter(([dc, dr]) => inReach(c + dc, r + dr)).length >= 3;
  };
  if (reach.size) parts.push(`<path class="reachedge" d="${edgePath(filled)}"/>`);

  // Previews (brief item 2). Hatched: leaving your square for this one provokes. A red
  // inner edge: a foe you can locate threatens it. pointer-events none, so the lit
  // square underneath still takes the click.
  for (const k of Object.keys(pv.provokes)) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="provoke" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);
  }
  for (const k of pv.safe) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="safe" x="${c * CELL + 2.2}" y="${r * CELL + 2.2}" width="${
      CELL - 4.4}" height="${CELL - 4.4}" rx="1"/>`);
  }
  for (const k of pv.threat) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="threat" x="${c * CELL + 1.2}" y="${r * CELL + 1.2}" width="${
      CELL - 2.4}" height="${CELL - 2.4}" rx="1"/>`);
  }
  // Out of sight (brief item 3): the engine's line of sight from the PC, as a darker veil.
  // Foundry lets a GM choose how dark fog is; this is dark enough to read as "not seen"
  // and light enough that the stone underneath still says what it is.
  for (const k of pv.unseen) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="unseen" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"><title>out of your sight</title></rect>`);
  }

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
    for (const { c, r, here, spell } of shown.values()) {
      const name = String(spell || "a spell").replace(/-/g, " ");
      parts.push(`<rect class="spellarea${here ? "" : " offlevel"}" x="${c * CELL}" y="${
        r * CELL}" width="${CELL}" height="${CELL}" fill="#e0701e" fill-opacity="${
        here ? 0.3 : 0}" stroke="#f0a050" stroke-opacity="${here ? 0.25 : 0.8}"
        stroke-width="${here ? 0.5 : 1.2}"${here ? "" : ` stroke-dasharray="3 2"`}
        pointer-events="none"><title>${esc(name)}${here ? "" : ", above or below this floor"
        }</title></rect>`);
    }
    // The template's own outline, so the cone reads as one shape and not twelve squares.
    const hereSet = new Set([...shown.values()].filter(v => v.here).map(v => `${v.c},${v.r}`));
    if (hereSet.size) parts.push(`<path class="spelledge" d="${edgePath((c, r) => hereSet.has(`${c},${r}`))}"/>`);
  }

  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);

  // The lamp (brief item 4): the hour's colour multiplied over the ground and under the
  // tokens, so the tokens keep their own colours at night.
  if (pv.lamp.wash > 0.01)
    parts.push(`<rect class="lampwash" x="0" y="0" width="${g.width * CELL}" height="${
      g.height * CELL}" fill="${pv.lamp.hex}" opacity="${pv.lamp.wash.toFixed(2)}"/>`);

  // A hunch (brief item 3) is a ring of its notice range round the PC, never a square: the
  // engine sends a count and a distance, and the ring says exactly that much.
  if (pv.pc && pv.pc.at)
    for (const h of pv.hunches)
      parts.push(`<circle class="hunch" cx="${(pv.pc.at[0] + .5) * CELL}" cy="${
        (pv.pc.at[1] + .5) * CELL}" r="${(h.within_ft / 5 + .5) * CELL}"><title>someone you cannot see, within ${
        h.within_ft} ft</title></circle>`);

  for (const b of (s.scene.pools || [])) {
    if (!b.at) continue;
    parts.push(`<circle class="bloodpool" cx="${(b.at[0] + .5) * CELL}" cy="${
      (b.at[1] + .5) * CELL}" r="${CELL * .38}">
      <title>blood pool, ${esc(b.source || b.owner)}</title></circle>`);
  }

  // Tokens are discs, terrain is squares: a creature can no longer be mistaken for a
  // coloured floor tile. Whose turn it is gets a static candle ring. A pulse was weighed
  // and refused: the brief forbids looping motion on controls and a token is a control
  // (it takes focus and the pointer), and a still ring in the brightest colour on the
  // board is already the first thing the eye lands on.
  for (const a of s.scene.actors) {
    if (!a.at) continue;
    const [c, r] = a.at;
    const n = a.squares || 1;
    const down = a.hp <= 0;
    const side = a.stance ? ` ${a.stance}` : (s.scene.in_encounter ? " bystander" : "");
    const az = a.at.length > 2 ? a.at[2] : 0;
    const mine = az === MAP_LEVEL;
    const ghost = mine ? "" : " offlevel";
    const unit = a.members != null;
    const cx = (c + n / 2) * CELL, cy = (r + n / 2) * CELL, rad = n * CELL / 2 - 2;
    const tip = `<title>${esc(a.name)}, ${a.hp}/${a.hp_max}${
      unit ? `, ${a.members} of ${a.members_max} still standing` : ""}${
      az ? `, ${az * 5} ft up` : ""}</title>`;
    const label = `${esc(a.name)}${a.ref === pv.turn ? ", whose turn it is" : ""}`;
    const cls = `token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}`;
    if (a.ref === pv.turn)
      parts.push(`<circle class="turnring" cx="${cx}" cy="${cy}" r="${rad + 2.6}"/>`);
    if (pv.caught.has(a.ref))
      parts.push(`<circle class="caughtring" cx="${cx}" cy="${cy}" r="${rad + (a.ref === pv.turn ? 4.6 : 2.6)}"/>`);
    parts.push(unit
      ? `<rect class="${cls}" data-ref="${esc(a.ref)}" tabindex="0" aria-label="${label}" x="${c * CELL + 2}" y="${r * CELL + 2}"
          width="${n * CELL - 4}" height="${n * CELL - 4}" rx="3">${tip}</rect>`
      : `<circle class="${cls}" data-ref="${esc(a.ref)}" tabindex="0" aria-label="${label}"
          cx="${cx}" cy="${cy}" r="${rad}">${tip}</circle>`);
    parts.push(`<text class="tok${a.ref === pv.turn ? " turn" : ""}${ghost}" x="${cx}" y="${cy + 3.3}">${unit ? a.members
        : esc(a.name.slice(0, 1).toUpperCase())}</text>`);
    if (down) parts.push(`<line class="downmark" x1="${cx - rad * .7}" y1="${cy + rad * .7}" x2="${
      cx + rad * .7}" y2="${cy - rad * .7}"/>`);
    // Somebody on another floor says which, beside the disc, rather than only fading.
    if (!mine) parts.push(`<text class="lvltag" x="${(c + n) * CELL - .5}" y="${r * CELL + 4.6}">${
      az > MAP_LEVEL ? "+" : "-"}${Math.abs(az - MAP_LEVEL) * 5}</text>`);
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
                       reach: !!(STATE.scene && STATE.scene.in_encounter), pv })
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
         ${PV_HATCH}
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
  const legend = `${pvKey(pv, g, reach.size)}${
      pools ? `<p class="sub maplegend">${pools} pool${
        pools === 1 ? "" : "s"} of blood on the ground</p>` : ""}`;
  $("#boardframe").dataset.ground = g.place ? `The ground · ${g.place}` : "The ground";
  $("#boardframe").dataset.phase = pv.lamp.phase;
  $("#groundctl").innerHTML = view + picker;
  // The read-out keeps a fixed height whatever it says, so pointing at things never moves
  // the board under the pointer.
  $("#mapwrap").innerHTML = `<div class="boardview">${svg}</div>
    <div class="boardfoot">${g.about ? `<p class="sub maplegend">${esc(g.about)}</p>` : ""}${
      legend}<p class="boardread" id="boardread" aria-live="polite">${pvIdle(pv)}</p></div>`;
  if (typeof mapPaint === "function") mapPaint();

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
  // The outline of a set of squares: every side whose neighbour is outside the set.
  function edgePath(has) {
    const d = [];
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
      if (!has(c, r)) continue;
      const x = c * CELL, y = r * CELL;
      if (!has(c, r - 1)) d.push(`M${x} ${y}h${CELL}`);
      if (!has(c, r + 1)) d.push(`M${x} ${y + CELL}h${CELL}`);
      if (!has(c - 1, r)) d.push(`M${x} ${y}v${CELL}`);
      if (!has(c + 1, r)) d.push(`M${x + CELL} ${y}v${CELL}`);
    }
    return d.join("");
  }
}

// The provoke hatch, shared by both views' <defs>: --alarm, the theme's own warning red.
// Quiet on purpose. Walking off a goblin provokes on almost every square of this board,
// and at .6 the hatch buried the board under it (measured: 80 of 86 lit squares hatched);
// the six that do not provoke get their own gold edge instead, because those are what the
// eye should find.
const PV_HATCH = `<pattern id="pv-provoke" width="4.5" height="4.5" patternUnits="userSpaceOnUse"
    patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4.5" stroke="#b0483c"
    stroke-width=".8" stroke-opacity=".38"></line></pattern>`;

// --- play/static/js/table/16-tab-map.js, lines 38-80 (MAPV, mapShowingPlaces, mapPaint), unchanged ---
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

// --- play/static/js/table/04-combat-and-turns.js, lines 636-642, unchanged ---
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
