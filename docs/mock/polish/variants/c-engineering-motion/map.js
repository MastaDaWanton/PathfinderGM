// c-engineering-motion: the game's board code (release 0.2.29, 7f63ab60), changed where
// marked "c-engineering-motion". Readings come from board-read.js, one model for both views.

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
  // c-engineering-motion: one reading of the board for both views.
  const M = BoardRead.model(s), R = BoardRead.readings(M);

  for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
  for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
  for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
  // Raised ground, lighter the higher it stands, drawn under everything else so a token
  // on a dais still reads as a token on a dais.
  for (const [c, r, v] of (g.floor || []))
    parts.push(cell(c, r, `up${Math.min(3, v)}`,
      `<title>${v * 5} ft above the floor</title>`));
  /* c-engineering-motion: relief. Raised ground casts a shadow onto the lower square to
     its south and east and catches light on its north and west lips: the same lamp
     direction scene3d.js lights with (LIGHT, high and to the north-west), so the flat
     board and the 3D one agree which way is up. Before this the wall-walk was a lighter
     brown only, which reads as a different floor, not a higher one. */
  const tall = (c, r) => g.blocked.some(b => b[0] === c && b[1] === r) ? 99 : at(c, r);
  for (const [c, r, v] of (g.floor || []).concat(g.blocked.map(([c, r]) => [c, r, 99]))) {
    if (tall(c + 1, r) < v && c + 1 < g.width)
      parts.push(`<rect class="relief-sh" x="${(c + 1) * CELL}" y="${r * CELL}" width="4" height="${CELL}"/>`);
    if (tall(c, r + 1) < v && r + 1 < g.height)
      parts.push(`<rect class="relief-sh" x="${c * CELL}" y="${(r + 1) * CELL}" width="${CELL}" height="4"/>`);
    if (v === 99) continue;
    if (tall(c - 1, r) < v)
      parts.push(`<line class="relief-hi" x1="${c * CELL + .6}" y1="${r * CELL}" x2="${c * CELL + .6}" y2="${(r + 1) * CELL}"/>`);
    if (tall(c, r - 1) < v)
      parts.push(`<line class="relief-hi" x1="${c * CELL}" y1="${r * CELL + .6}" x2="${(c + 1) * CELL}" y2="${r * CELL + .6}"/>`);
  }
  // The room lamp (board-read.js lamp()), multiplied over the ground and under everything
  // the player reads: lit squares, previews and people keep their colours at night.
  if (M.lamp) parts.push(`<rect class="lamp" width="${g.width * CELL}" height="${g.height * CELL}"/>`);
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
    // c-engineering-motion: no <title>; the inspector card says the cost and more, and a
    // native tooltip would cover it a second later. A square that does not provoke is lit
    // brighter: these are the only squares the board asks you to notice at rest.
    parts.push(cell(c, r, M.safe.has(key) ? "reach safe" : "reach")
      .replace(/class="reach( safe)?"/, m => `${m} data-sq="${c},${r}${
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

  // c-engineering-motion: what the PC cannot see, and each foe's threatened squares
  // (drawn hidden, lit while that foe is inspected). Neither takes a click.
  const flatMark = (m, inner = "") => {
    const n = m.n || 1, x = m.c * CELL, y = m.r * CELL;
    if (m.kind === "fog") return `<rect class="fog" x="${x}" y="${y}" width="${CELL}" height="${CELL}"/>`;
    if (m.kind === "zone") return `<rect class="zone" data-zone="${m.ref}" x="${x}" y="${y}" width="${CELL}" height="${CELL}"/>`;
    return `<rect class="mark-${m.kind}" ${m.ref ? `data-ring="${m.ref}"` : ""} x="${x + .75}" y="${
      y + .75}" width="${n * CELL - 1.5}" height="${n * CELL - 1.5}" rx="${
      m.kind === "active" ? 5 : 2.5}"/>${inner}`;
  };
  for (const m of R.marks) if (m.kind === "fog" || m.kind === "zone") parts.push(flatMark(m));

  // Grid lines last of the terrain, so they sit over the fills and under the tokens.
  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);
  // Outlines on the square's own edge: the ground any foe threatens (Wrath of the
  // Righteous draws a threat range as a red dotted edge), the spell's area, and the
  // reach of a hunch, centred on the PC, so it says how near and never where.
  for (const s of R.strips) {
    const x = s.c * CELL, y = s.r * CELL;
    const [x1, y1, x2, y2] = { n: [x, y, x + CELL, y], s: [x, y + CELL, x + CELL, y + CELL],
                               w: [x, y, x, y + CELL], e: [x + CELL, y, x + CELL, y + CELL] }[s.side];
    parts.push(`<line class="edge-${s.kind}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`);
  }

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
    /* c-engineering-motion: the side is said by shape as well as colour, so it survives
       colour blindness and the night lamp: you and your allies are round, foes square,
       bystanders between. A body at 0 hp is struck through as well as faded. The native
       <title> went: the inspector card carries the name, hit points and height. */
    const rx = unit ? 3 : { pc: n * CELL / 2 - 2, ally: n * CELL / 2 - 2, foe: 1.5 }[a.stance] || 4;
    parts.push(`<rect class="token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}"
      x="${c * CELL + 2}" y="${r * CELL + 2}"
      width="${n * CELL - 4}" height="${n * CELL - 4}" rx="${rx}"></rect>`);
    parts.push(`<text class="tok${ghost}" x="${(c + n / 2) * CELL}" y="${
      (r + n / 2) * CELL + 3.4}">${unit ? a.members
        : esc(a.name.slice(0, 1).toUpperCase())}</text>`);
    if (down) parts.push(`<line class="downmark" x1="${c * CELL + 4}" y1="${(r + n) * CELL - 4}" x2="${
      (c + n) * CELL - 4}" y2="${r * CELL + 4}"/>`);
  }
  // Rings over the tokens: whose turn it is (still, see board.css), who the spell
  // catches, and the provokers, hidden until a square that provokes them is inspected.
  for (const m of R.marks) if (m.kind !== "fog" && m.kind !== "zone") parts.push(flatMark(m));
  // The inspector's square. Moved by board-read.js, never re-drawn, so it costs nothing.
  parts.push(`<rect id="boardcursor" x="0" y="0" width="${CELL}" height="${CELL}" visibility="hidden"/>`);

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
  // c-engineering-motion: the board is one keyboard stop. Arrows walk a cursor over the
  // squares (the roving-focus pattern of the WAI-ARIA grid, without four hundred tab
  // stops), Enter is the click a lit square takes, Home goes back to you.
  const kbd = ` tabindex="0" role="application" aria-roledescription="board" aria-label="${
    esc(g.place || "The ground")}, ${g.width} by ${g.height} squares. Arrow keys inspect a square, Enter moves to a lit one, Home returns to you." aria-describedby="boardsay"`;
  const fogDef = `<pattern id="fogx" width="4" height="4" patternUnits="userSpaceOnUse"
      patternTransform="rotate(45)"><rect width="4" height="4" fill="#0b0908" fill-opacity=".62"/>
      <line x1="0" y1="0" x2="0" y2="4" stroke="#93866e" stroke-opacity=".22" stroke-width="1"/></pattern>`;
  const opts3d = ({
    turn: MAP_TURN, level: MAP_LEVEL, reach: !!(STATE.scene && STATE.scene.in_encounter),
    lamp: M.lamp && M.lamp.mul, safe: M.safe, svgAttrs: kbd, defs: `<defs>${fogDef}</defs>`,
    marks: R.marks.map(m3d), strips: R.strips.map(s => ({ ...s, cls: "edge3 edge-" + s.kind,
      color: { threat: "#c06649", spell: "#f0a050", hunch: "#8fb0c8" }[s.kind] })) });
  BoardTurn.last = { g, actors: s.scene.actors || [], opts: opts3d };
  const svg = MAP_3D
    ? Scene3D.render(g, s.scene.actors || [], opts3d)
    : `<svg id="map" viewBox="0 0 ${g.width * CELL} ${g.height * CELL}"
         preserveAspectRatio="xMidYMid meet"${kbd}><defs>${fogDef}
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
  // c-engineering-motion: the reach count moved into the key line below, beside its swatch.
  const legend = `${
      pools ? `<p class="sub maplegend">${pools} pool${
        pools === 1 ? "" : "s"} of blood on the ground</p>` : ""}`;
  /* c-engineering-motion: a key, one line, only for what this board is drawing. Each
     swatch is the mark itself, so the key cannot drift from the board. */
  const nSafe = M.safe.size, hunchN = M.hunches.length;
  // Two wordings where the long one would wrap a phone's key onto five lines and take the
  // board's height with it.
  const two = (long, short) => `<span class="klong">${long}</span><span class="kshort">${short}</span>`;
  const keyItems = [
    M.threat.size && `<span class="k k-threat"></span>Threatened`,
    g.speed && `<span class="k k-safe"></span>${two(`${reach.size} within ${g.speed} ft, ${
      nSafe} without provoking`, `${nSafe} without provoking`)}`,
    M.blind.size && `<span class="k k-fog"></span>Out of sight`,
    hunchN && `<span class="k k-hunch"></span>${two(`${hunchN === 1 ? "Something" : hunchN + " things"} unseen within ${M.hunchFt} ft`,
      `Unseen within ${M.hunchFt} ft`)}`,
  ].filter(Boolean);
  const boardkey = keyItems.length
    ? `<p class="boardkeyline">${keyItems.map(t => `<span class="ki">${t}</span>`).join("")}</p>` : "";
  // The light shares the place's line, right-aligned: one line of the well's height kept.
  const lampKey = M.lamp ? `<span class="ki lampkey"><span class="k k-lamp"></span>${esc(M.lamp.text)}</span>` : "";
  // The place is named, not just drawn. A correct map of the well, while the prose is
  // describing a gate, is indistinguishable from a broken map unless the board says which
  // place it is (reported 2026-09-21). `about` is the shape's own line about what that
  // kind of place is made of, which is also what the plan was built from.
  // The heading is the board's own `#board-name`; 16-tab-map.js writes this into it while
  // the ground is shown and the town's name while Places is.
  $("#boardframe").dataset.ground = g.place ? `The ground · ${g.place}` : "The ground";
  $("#groundctl").innerHTML = view + picker;
  // c-engineering-motion: the lamp is a registered custom property on the frame, which
  // outlives every re-draw, so a change of hour eases from one light to the next.
  $("#boardframe").style.setProperty("--lamp", M.lamp ? M.lamp.css : "#fff");
  $("#mapwrap").innerHTML = `<div class="boardview">${svg}<div class="boardcard" aria-hidden="true"></div></div>
    <p id="boardsay" class="vh" aria-live="polite"></p>
    <div class="boardfoot">${boardkey}<div class="footrow">${g.about ? `<p class="sub maplegend">${esc(g.about)}</p>` : "<span></span>"}${
      lampKey}</div>${legend}</div>`;
  // A change of view fades the new board in (150 ms, opacity only); re-draws of the same
  // view (a new hour, a level, the harness) do not, so nothing flickers that did not change.
  const viewNow = MAP_3D ? "3d" : "flat", swapped = BoardTurn.view && BoardTurn.view !== viewNow;
  if (swapped) $("#mapwrap .boardview > svg").classList.add("enter");
  BoardTurn.view = viewNow;
  if (MAP_3D) BoardTurn.to(MAP_TURN, !swapped);
  BoardRead.after(M);
  if (typeof mapPaint === "function") mapPaint();

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
}

// c-engineering-motion: a board-read mark as scene3d.js draws it, a quad on its own ground.
// shortcut: a ring round a creature bigger than one square only rings its first square;
// draw n squares wide if Large creatures reach the board.
function m3d(m) {
  if (m.kind === "fog") return { c: m.c, r: m.r, cls: "fog3", attrs: ' fill="url(#fogx)"' };
  if (m.kind === "zone") return { c: m.c, r: m.r, cls: "zone3", attrs: ` data-zone="${m.ref}" fill="#b0483c"` };
  return { c: m.c, r: m.r, grow: 0.06, cls: "mark-" + m.kind,
           attrs: ` fill="none"${m.ref ? ` data-ring="${m.ref}"` : ""}` };
}

/* c-engineering-motion: the 3D board turns rather than jumping a quarter.
 *
 * A jump puts every square somewhere else at once and the player has to find the room
 * again; seeing it swing says where everything went (spatial consistency, the reason
 * XCOM's 90-degree camera steps are animated). One motion, the board, with everything on
 * it carried: tokens, rings and outlines turn because they are part of the drawing, never
 * timed on their own. The card is hidden while it turns and comes back on the last frame.
 *
 * 300 ms on the strong ease-in-out (cubic-bezier(.77, 0, .175, 1)), the curve for
 * movement on screen; a click mid-turn starts the new turn from where the board is, so
 * fast clicks never queue. Under prefers-reduced-motion it jumps, as it does in the game.
 * Every frame comes from Scene3D.render, and the last one is the ordinary render, so the
 * resting board and its `data-sq` targets are exactly what a jump would have drawn.
 */
const BoardTurn = (function () {
  const T = { view: null, last: null, angle: null, raf: 0 };
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  // A real cubic-bezier, solved for x by bisection, so the curve is the named one.
  function bezier(x1, y1, x2, y2) {
    const b = (t, a, c) => 3 * a * t * (1 - t) ** 2 + 3 * c * t * t * (1 - t) + t ** 3;
    return x => {
      let lo = 0, hi = 1;
      for (let i = 0; i < 24; i++) { const m = (lo + hi) / 2; if (b(m, x1, x2) < x) lo = m; else hi = m; }
      return b((lo + hi) / 2, y1, y2);
    };
  }
  const ease = bezier(0.77, 0, 0.175, 1), DUR = 300;

  function frame(angle, fit) {
    const old = document.querySelector("#mapwrap #view3d");
    if (!old || !T.last) return;
    const html = Scene3D.render(T.last.g, T.last.actors, { ...T.last.opts, angle, fit });
    old.insertAdjacentHTML("afterend", html);
    old.remove();
  }

  T.to = function (target, mayAnimate) {
    cancelAnimationFrame(T.raf);
    clearTimeout(T.done);
    const endBox = Scene3D.box();
    const from = T.angle;
    T.angle = target;
    // A hidden page gets no animation frames, and a turn left half-drawn would leave the
    // board at the wrong angle: there it jumps, as it does under reduced motion.
    if (!mayAnimate || from == null || reduce.matches || document.hidden) {
      BoardRead.hold(false); return;
    }
    const d = ((((target - from) % 4) + 6) % 4) - 2;   // the short way round, in quarters
    if (Math.abs(d) < 1e-3) { BoardRead.hold(false); return; }
    Scene3D.render(T.last.g, T.last.actors, { ...T.last.opts, angle: from });
    const startBox = Scene3D.box(), t0 = performance.now();
    BoardRead.hold(true);
    T.angle = from;
    frame(from, startBox);               // at once, or the end would flash for a frame first
    const finish = () => {
      cancelAnimationFrame(T.raf); clearTimeout(T.done);
      T.angle = target;
      frame(undefined, null);            // the resting board, drawn exactly as a jump would
      BoardRead.hold(false);
    };
    const step = now => {
      const k = Math.min(1, (now - t0) / DUR), e = ease(k);
      if (k >= 1) return finish();
      T.angle = from + d * e;
      frame(T.angle, [startBox[0] + (endBox[0] - startBox[0]) * e,
                      startBox[1] + (endBox[1] - startBox[1]) * e]);
      T.raf = requestAnimationFrame(step);
    };
    T.raf = requestAnimationFrame(step);
    T.done = setTimeout(finish, DUR + 120);   // frames throttled mid-turn: land it anyway
  };
  return T;
})();

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
