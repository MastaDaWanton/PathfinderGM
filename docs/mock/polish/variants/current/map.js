// VERBATIM copies of what draws the board in the game (release 0.2.29, 7f63ab60).
// Do not edit: this is the Current baseline. Each block names its source lines.

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
    // A blank board reads as broken, so the Map tab says why (its `.boardempty` line,
    // shown while this is empty). Since 2026-09-19 the ground is laid when the party
    // ARRIVES somewhere rather than when a fight starts (item 28), so this is now the
    // rare case: a scene with nowhere in it yet, between worlds or before the party has
    // been placed.
    $("#mapwrap").innerHTML = "";
    $("#groundctl").innerHTML = "";
    $("#boardframe").dataset.ground = "The ground";
    if (typeof mapPaint === "function") mapPaint();
    return;
  }

  const CELL = 18;
  const reach = new Map((g.reachable || []).map(([c, r, cost]) => [`${c},${r}`, cost]));
  const parts = [];

  // Which floor is being looked at. A room with only one is not asked about — a level
  // picker over a flat market is a control that does nothing, and the first thing a
  // player learns from it is that it does not matter.
  const levels = (g.levels && g.levels.length > 1) ? g.levels : [0];
  if (!levels.includes(MAP_LEVEL)) MAP_LEVEL = levels[0];
  const ground = new Map((g.floor || []).map(([c, r, v]) => [`${c},${r}`, v]));
  const at = (c, r) => ground.get(`${c},${r}`) || 0;

  for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
  for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
  for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
  // Raised ground, lighter the higher it stands, drawn under everything else so a token
  // on a dais still reads as a token on a dais.
  for (const [c, r, v] of (g.floor || []))
    parts.push(cell(c, r, `up${Math.min(3, v)}`,
      `<title>${v * 5} ft above the floor</title>`));
  // Rails as edges, not fills. A parapet is a thing to shoot over; a filled square
  // would read as a wall, which is the very mistake the engine was making.
  for (const [c, r, v] of (g.parapet || []))
    parts.push(`<line class="rail" x1="${c * CELL + 2}" y1="${(r + .5) * CELL}" x2="${
      (c + 1) * CELL - 2}" y2="${(r + .5) * CELL}"><title>a rail, ${
      v * 5} ft up</title></line>`);
  for (const [key, cost] of reach) {
    const [c, r] = key.split(",").map(Number);
    // data-sq is what makes the square a *destination* — the combat builder queues a
    // move op from it. Present whether or not the panel is open, harmless when idle.
    // data-sq is what makes the square a destination for the combat builder. The
    // first cut replaced on 'class="cell reach"', which cell() never writes — the
    // legend counted 35 lit squares while zero of them were clickable.
    // A destination carries the level it lands you on, so the combat builder queues a
    // move to a CELL and not merely a square. Walking onto a dais is walking up onto it.
    const lvl = at(c, r);
    parts.push(cell(c, r, "reach", `<title>${cost} ft${
        lvl ? ` · ${lvl * 5} ft up` : ""}</title>`)
      .replace('class="reach"', `class="reach" data-sq="${c},${r}${
        lvl ? "," + lvl : ""}"`));
  }

  // The latest turn's spell areas (`scene.grid.areas`, §2.10): the engine's ruling on
  // where the cone or burst fell, drawn so the player can see it and dispute it the way a
  // table would (rules/areas.py: "the cells go to the map"). Measured 2026-09-28: Burning
  // Hands caught nobody, the prose burned a man, and nothing on the page showed where the
  // cone had actually gone. Drawn as each cell's square on the floor; a cell on the level
  // being looked at is filled, one above or below it (a cone into the canopy) outlined,
  // so a spell aimed up reads as up. The 3D view reads the same `g.areas` by the same
  // rule in scene3d.js, so these are only the flat board's squares.
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
        here ? 0.32 : 0}" stroke="#f0a050" stroke-opacity="${here ? 0.55 : 0.8}"
        stroke-width="${here ? 0.8 : 1.2}"${here ? "" : ` stroke-dasharray="3 2"`}
        pointer-events="none"><title>${esc(name)}${here ? "" : ", above or below this floor"
        }</title></rect>`);
    }
  }

  // Grid lines last of the terrain, so they sit over the fills and under the tokens.
  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);

  // Blood before bodies, so a token stands in its own pool rather than under it.
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
    // The server's `stance`, read off the attitude track — the same reader the panel's
    // "· Hostile" and the narrator's brief use (`attitude.stance`). This used to be
    // worked out here from the fight's side NAME, so an hour after the robbers won (the
    // sides gone with the fight) neither was painted a foe while the panel called one of
    // them Hostile; and a side named "party" painted the player's own companions red.
    const side = a.stance ? ` ${a.stance}` : (s.scene.in_encounter ? " bystander" : "");
    // Somebody on another floor of the same room is faded, not hidden. Hiding them is
    // how a player is surprised by an archer who was on the map the whole time; this is
    // the level selector saying "not who you are looking at" rather than "not there".
    const mine = (a.at.length > 2 ? a.at[2] : 0) === MAP_LEVEL;
    const ghost = mine ? "" : " offlevel";
    // A crowd is many people, and a plain filled block of nine squares reads as one big
    // creature (item 33). The unit gets a hatched fill and its count on the glyph, so a
    // 3x3 of townsfolk cannot be mistaken for a giant.
    const unit = a.members != null;
    parts.push(`<rect class="token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}"
      x="${c * CELL + 2}" y="${r * CELL + 2}"
      width="${n * CELL - 4}" height="${n * CELL - 4}" rx="3">
      <title>${esc(a.name)} — ${a.hp}/${a.hp_max}${
        unit ? ` · ${a.members} of ${a.members_max} still standing` : ""}${
        a.at.length > 2 && a.at[2] ? ` · ${a.at[2] * 5} ft up` : ""}</title></rect>`);
    parts.push(`<text class="tok" x="${(c + n / 2) * CELL}" y="${
      (r + n / 2) * CELL + 4}">${unit ? a.members
        : esc(a.name.slice(0, 1).toUpperCase())}</text>`);
  }

  // A flask being aimed at a square (04's Throw…, CRB "Throw Splash Weapon": a grid
  // intersection at AC 5): while it is, every square of the board is a target, drawn over
  // the tokens so a corner beside somebody can be clicked too. The engine refuses one out
  // of reach in its own words; nothing here decides which squares may be aimed at.
  if (typeof COMBAT !== "undefined" && COMBAT.aim && !MAP_3D) {
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++)
      parts.push(`<rect class="aimsq" data-aimsq="${c},${r}" x="${c * CELL}" y="${r * CELL}"
        width="${CELL}" height="${CELL}" fill="transparent"><title>the north-west corner of ${
        c},${r}</title></rect>`);
  }

  // The same board, drawn two ways. Both read the one geometry payload and both write
  // `data-sq`, so the combat builder cannot tell them apart — which is the whole reason
  // the flat one was built first.
  const svg = MAP_3D
    ? Scene3D.render(g, s.scene.actors || [],
                     { turn: MAP_TURN, level: MAP_LEVEL,
                       reach: !!(STATE.scene && STATE.scene.in_encounter) })
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
       </defs>${parts.join("")}</svg>`;
  const pools = (s.scene.pools || []).length;
  // The controls sit in the board's head as the approved design lays them out (the mock's
  // Map mode): Flat and 3D as one recessed pair, the turn beside them while it is in 3D,
  // and the floors, each pressed in when it is the one being looked at. The same
  // `data-mapview`, `data-mapturn` and `data-maplevel` the tray used, read by 04. They go
  // into `#groundctl`, the head row's room for the ground's own controls, right of the
  // Places button (16-tab-map.js), which is a different map and is not drawn here.
  // Flat and 3D are pressed only while the ground is what is shown.
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
  const legend = `${g.speed ? `<p class="sub maplegend">${
      reach.size} squares within ${g.speed} ft</p>` : ""}${
      pools ? `<p class="sub maplegend">${pools} pool${
        pools === 1 ? "" : "s"} of blood on the ground</p>` : ""}`;
  // The place is named, not just drawn. A correct map of the well, while the prose is
  // describing a gate, is indistinguishable from a broken map unless the board says which
  // place it is (reported 2026-09-21). `about` is the shape's own line about what that
  // kind of place is made of, which is also what the plan was built from.
  // The heading is the board's own `#board-name`; 16-tab-map.js writes this into it while
  // the ground is shown and the town's name while Places is.
  $("#boardframe").dataset.ground = g.place ? `The ground · ${g.place}` : "The ground";
  $("#groundctl").innerHTML = view + picker;
  $("#mapwrap").innerHTML = `<div class="boardview">${svg}</div>
    <div class="boardfoot">${g.about ? `<p class="sub maplegend">${esc(g.about)}</p>` : ""}${
      legend}</div>`;
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

// The head row and which of the two boards is shown. Called by 03 after every drawing of
// the ground and here after every change of view.
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
    // Out of use while hidden: the keyboard cannot reach what the eye cannot see.
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

// --- play/static/js/table/04-combat-and-turns.js, lines 636-642, the board's own
// controls. In the game they sit inside 04's one big click handler; here they are
// the only lines of it, in a listener of their own (the t = e.target is 04's too). ---
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
