// The play table, part 03 of 6 (offers and map). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// --- what the GM offered -----------------------------------------------------------
//
// Suggestions, not a menu. Clicking one puts the words in the box rather than sending
// them, so the player can change their mind or add to it — a chip that fired the turn
// straight off would quietly turn a nudge into the only three things you can do.
function renderGmView(s) {
  const box = $("#gmview");
  if (!box) { return; }
  const running = s.schemes;
  if (!running) { box.innerHTML = ""; return; }
  if (!running.length) {
    box.innerHTML = `<h2>Behind the screen</h2><div class="sub">No scheme is running.</div>`;
    return;
  }
  box.innerHTML = `<h2>Behind the screen</h2>` + running.map(x => {
    const slots = Object.entries(x.slots || {})
      .map(([k, v]) => `<div class="sub">${esc(k)}: ${esc(v || "unfilled")}</div>`).join("");
    const fired = Object.keys(x.fired || {});
    return `<div class="scheme">
      <div><b>${esc(x.title || x.scheme)}</b></div>
      ${slots}
      ${fired.length ? `<div class="sub">fired: ${esc(fired.join(", "))}</div>` : ""}
      ${(x.skipped || []).length
        ? `<div class="sub">skipped: ${esc((x.skipped || []).join("; "))}</div>` : ""}
      ${x.outcome ? `<div class="sub">outcome: ${esc(x.outcome)}</div>` : ""}
      ${(x.news || []).length ? `<div class="sub">news on its way: ${(x.news || []).length}</div>` : ""}
    </div>`;
  }).join("");
}

function renderSuggestions(s) {
  const box = $("#suggestions");
  const offered = (s.suggestions || []);
  // Hidden entirely while a roll is pending: the only thing to do then is answer it.
  if (!offered.length || s.awaiting) { box.innerHTML = ""; return; }
  box.innerHTML = offered.map(t =>
    `<button type="button" class="sugg v2-btn">${esc(t)}</button>`).join("");
}

document.addEventListener("click", e => {
  const chip = e.target.closest(".sugg");
  if (!chip) return;
  const input = $("#input");
  input.value = chip.textContent;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
});

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

// Which symbol draws each fixture kind (content/rules/fixtures.json), and the symbols:
// shapes and flat procedural texture that ARE the object, in the table's own palette —
// wood from the leather and brass browns (#6b4a3a, #7d6845, #4a3326, #2e261e), stone from
// the board's greys, the ember (rgb 255,176,84) for a fire. Each is an 18-unit square with
// its front to the south (renderMap turns it). No image files, no icons, and no
// gradient: url(#id) resolves to the first copy in the page, which may sit in a hidden
// board, and Chrome then paints nothing.
const FX_SYMBOL = { barrel: "barrel", crate: "crate", table: "table", counter: "counter",
  stall: "stall",
  bookshelf: "shelf", rack: "rack", hearth: "hearth", cart: "cart", stair: "stair",
  gallery: "planks", water: "water", rubble: "rubble", chandelier: "chandelier",
  door: "door", window: "window", crane: "crane",
  mast: "mast", rigging: "rigging", rope: "rope", hatch: "hatch", helm: "helm",
  capstan: "capstan", anchor: "anchor", bench: "bench", boat: "boat", rail: "gunwale",
  sea: "sea", bollard: "bollard" };
const FX_DEFS = `
  <symbol id="fx-barrel" viewBox="0 0 18 18">
    <circle cx="9" cy="9" r="7.3" fill="#6b4a3a" stroke="#2e261e" stroke-width="1.5"/>
    <circle cx="9" cy="9" r="6.1" fill="none" stroke="#4a3326" stroke-width="2.2"
            stroke-dasharray=".55 2.6"/>
    <circle cx="9" cy="9" r="4.7" fill="#7d6845" stroke="#2e261e" stroke-width=".9"/>
    <path d="M6.6 5v8M9 4.3v9.4M11.4 5v8" stroke="#5c4a35" stroke-width=".5"/>
    <circle cx="9" cy="9" r=".8" fill="#2e261e"/></symbol>
  <symbol id="fx-crate" viewBox="0 0 18 18">
    <rect x="2" y="2" width="14" height="14" fill="#6b4a3a" stroke="#241d15" stroke-width=".8"/>
    <path d="M2 6.7h14M2 11.3h14" stroke="#4a3326" stroke-width=".6"/>
    <path d="M3.2 3.2L14.8 14.8M14.8 3.2L3.2 14.8" stroke="#7d6845" stroke-width="1.2"/>
    <rect x="2.7" y="2.7" width="12.6" height="12.6" fill="none" stroke="#7d6845"
          stroke-width="1.1"/></symbol>
  <symbol id="fx-table" viewBox="0 0 18 18">
    <rect x="0" y="3.5" width="18" height="11" fill="#7d6845" stroke="#4a3326"
          stroke-width="1"/>
    <path d="M0 7.2h18M0 10.8h18" stroke="#5c4a35" stroke-width=".45"/></symbol>
  <symbol id="fx-counter" viewBox="0 0 18 18">
    <rect x="0" y="2" width="18" height="10" fill="#7d6845" stroke="#4a3326"
          stroke-width=".8"/>
    <path d="M0 5.3h18M0 8.6h18" stroke="#5c4a35" stroke-width=".45"/>
    <rect x="0" y="12" width="18" height="4.6" fill="#4a3326" stroke="#241d15"
          stroke-width=".6"/>
    <path d="M6 12.6v3.4M12 12.6v3.4" stroke="#6b4a3a" stroke-width=".8"/></symbol>
  <symbol id="fx-stall" viewBox="0 0 18 18">
    <rect x="0" y="9" width="18" height="7.5" fill="#7d6845" stroke="#4a3326"
          stroke-width=".8"/>
    <path d="M0 12.6h18" stroke="#5c4a35" stroke-width=".45"/>
    <rect x="0" y="1" width="18" height="7" fill="#7d1a14" stroke="#241d15"
          stroke-width=".6"/>
    <path d="M3 1v7M9 1v7M15 1v7" stroke="#7d6845" stroke-width="2.2"/></symbol>
  <symbol id="fx-shelf" viewBox="0 0 18 18">
    <rect x="0" y=".5" width="18" height="15.5" fill="#4a3326" stroke="#241d15"
          stroke-width=".8"/>
    <path d="M0 4h18M0 7.5h18" stroke="#2e261e" stroke-width=".5"/>
    <rect x=".8" y="9.6" width="16.4" height="5.6" fill="#241d15"/>
    <rect x="1.1" y="10" width="1.8" height="5" fill="#7d1a14"/>
    <rect x="3.1" y="10.6" width="1.5" height="4.4" fill="#1f4a26"/>
    <rect x="4.8" y="10" width="2" height="5" fill="#7d6845"/>
    <rect x="7" y="10.8" width="1.4" height="4.2" fill="#3a4048"/>
    <rect x="8.6" y="10.2" width="1.9" height="4.8" fill="#7a6f5a"/>
    <rect x="10.7" y="10" width="1.6" height="5" fill="#5a0c08"/>
    <rect x="12.5" y="10.5" width="2" height="4.5" fill="#1f4a26"/>
    <rect x="14.7" y="10.1" width="1.4" height="4.9" fill="#7d6845"/>
    <path d="M0 15.6h18" stroke="#7d6845" stroke-width="1"/></symbol>
  <symbol id="fx-rack" viewBox="0 0 18 18">
    <rect x="0" y=".5" width="18" height="15.5" fill="#4a3326" stroke="#241d15"
          stroke-width=".8"/>
    <rect x=".8" y="9.6" width="16.4" height="5.6" fill="#241d15"/>
    <path d="M2.5 10v5.4M6 10v5.4M9.5 10v5.4M13 10v5.4M16 10v5.4" stroke="#6a6f76"
          stroke-width=".9"/>
    <path d="M1.5 11.4h2M5 11.4h2M8.5 11.4h2M12 11.4h2" stroke="#7d6845"
          stroke-width=".7"/>
    <path d="M0 15.6h18" stroke="#7d6845" stroke-width="1"/></symbol>
  <symbol id="fx-hearth" viewBox="0 0 18 18">
    <rect x="0" y="1" width="18" height="15.6" fill="#4d4a45" stroke="#241d15"
          stroke-width=".8"/>
    <path d="M0 5h18M0 9h18M0 13h18M5 1v4M12 1v4M8.5 5v4M15 5v4M2.5 9v4M15.5 9v4"
          stroke="#3a3128" stroke-width=".6"/>
    <rect x="4" y="9.4" width="10" height="7.2" rx="1" fill="#2e1a0e" stroke="#241d15"
          stroke-width=".6"/>
    <rect x="5.2" y="11.2" width="7.6" height="4.6" rx="1.4" fill="rgb(255,176,84)"
          opacity=".8"/>
    <rect x="7" y="12.8" width="4" height="2.6" rx="1" fill="#f0c070"/></symbol>
  <symbol id="fx-cart" viewBox="0 0 18 18">
    <rect x="0" y="3.6" width="18" height="10.8" fill="#6b4a3a" stroke="#241d15"
          stroke-width=".8"/>
    <path d="M0 7.2h18M0 10.8h18" stroke="#4a3326" stroke-width=".55"/>
    <rect x="4.5" y=".6" width="9" height="2.7" rx="1.2" fill="#2e261e" stroke="#7d6845"
          stroke-width=".55"/>
    <rect x="4.5" y="14.7" width="9" height="2.7" rx="1.2" fill="#2e261e" stroke="#7d6845"
          stroke-width=".55"/></symbol>
  <symbol id="fx-stair" viewBox="0 0 18 18">
    <rect x="1" y="13.4" width="16" height="4.2" fill="#4a3326"/>
    <rect x="1" y="9.1" width="16" height="4.3" fill="#5c4a35"/>
    <rect x="1" y="4.8" width="16" height="4.3" fill="#7d6845"/>
    <rect x="1" y=".5" width="16" height="4.3" fill="#9a8458"/>
    <path d="M1 13.4h16M1 9.1h16M1 4.8h16" stroke="#241d15" stroke-width="1"/>
    <path d="M1 .5v17M17 .5v17" stroke="#241d15" stroke-width=".9"/></symbol>
  <symbol id="fx-planks" viewBox="0 0 18 18">
    <path d="M0 4.5h18M0 9h18M0 13.5h18M6 0v4.5M13 4.5v4.5M4 9v4.5M11 13.5v4.5"
          stroke="#2e261e" stroke-width=".55" opacity=".75"/></symbol>
  <symbol id="fx-water" viewBox="0 0 18 18">
    <rect width="18" height="18" fill="#2e3c46" opacity=".6"/>
    <path d="M2 5q2-1.6 4 0t4 0t4 0M4 10.5q2-1.6 4 0t4 0t4 0M1 15.5q2-1.4 4 0t4 0"
          fill="none" stroke="#6a7a86" stroke-width=".7" opacity=".85"/></symbol>
  <symbol id="fx-rubble" viewBox="0 0 18 18">
    <g fill="#4d4a45" stroke="#241d15" stroke-width=".5">
      <path d="M3 4l3-1 1.5 2.5-2 2-2.8-.8z"/><path d="M10 3.5l3.2.6.4 2.6-2.6 1-1.6-1.8z"/>
      <path d="M6 10l2.6-.6 1.4 2.4-1.8 2-2.6-1.2z"/>
      <path d="M12.5 11.5l2.8.2.6 2.8-2.4 1.2-1.8-2z"/></g>
    <circle cx="15" cy="7.5" r=".9" fill="#5c574f"/>
    <circle cx="3.5" cy="14" r="1" fill="#5c574f"/></symbol>
  <symbol id="fx-chandelier" viewBox="0 0 18 18">
    <circle cx="9" cy="9" r="6" fill="none" stroke="#7a6a44" stroke-width=".8"
            stroke-dasharray="1.5 1.2" opacity=".45"/>
    <circle cx="9" cy="9" r="1.2" fill="#7a6a44" opacity=".45"/></symbol>
  <symbol id="fx-door" viewBox="0 0 18 18">
    <rect x="2" y="0" width="14" height="3.4" fill="#6b4a3a" stroke="#241d15"
          stroke-width=".7"/>
    <path d="M2 0v5M16 0v5" stroke="#7d6845" stroke-width="1.3"/></symbol>
  <symbol id="fx-crane" viewBox="0 0 18 18">
    <rect x="2" y="2" width="14" height="14" fill="none" stroke="#6b4a3a" stroke-width="2"/>
    <path d="M2 16L16 2" stroke="#7d6845" stroke-width="1.6"/>
    <circle cx="16" cy="2" r="1.4" fill="#2e261e" stroke="#7d6845" stroke-width=".6"/></symbol>
  <symbol id="fx-mast" viewBox="0 0 18 18">
    <rect x="0" y="7.6" width="18" height="2.8" rx="1.2" fill="#4a3326" stroke="#241d15"
          stroke-width=".6"/>
    <path d="M1 9h16" stroke="#7d6845" stroke-width=".5"/>
    <circle cx="9" cy="9" r="4.4" fill="#6b4a3a" stroke="#241d15" stroke-width="1"/>
    <circle cx="9" cy="9" r="2.6" fill="none" stroke="#4a3326" stroke-width=".7"/>
    <circle cx="9" cy="9" r=".9" fill="#2e261e"/></symbol>
  <symbol id="fx-rigging" viewBox="0 0 18 18">
    <path d="M2 17L7 1M9 17V1M16 17L11 1" stroke="#9a8458" stroke-width=".9"
          fill="none"/>
    <path d="M2.6 14h12.8M3.6 11h10.8M4.5 8h9M5.4 5h7.2M6.3 2.4h5.4" stroke="#7d6845"
          stroke-width=".6"/></symbol>
  <symbol id="fx-rope" viewBox="0 0 18 18">
    <circle cx="9" cy="9" r="6.4" fill="#5c4a35" stroke="#241d15" stroke-width=".6"/>
    <circle cx="9" cy="9" r="5.4" fill="none" stroke="#9a8458" stroke-width="1.3"/>
    <circle cx="9" cy="9" r="3.6" fill="none" stroke="#9a8458" stroke-width="1.3"/>
    <circle cx="9" cy="9" r="1.8" fill="#2e261e" stroke="#9a8458" stroke-width="1"/>
    <path d="M14.4 9.5q2 2.5 3.4 3" stroke="#9a8458" stroke-width="1.2" fill="none"/></symbol>
  <symbol id="fx-hatch" viewBox="0 0 18 18">
    <rect x="1.5" y="1.5" width="15" height="15" fill="#241d15" stroke="#4a3326"
          stroke-width="2.2"/>
    <path d="M5 2.6v12.8M9 2.6v12.8M13 2.6v12.8M2.6 5h12.8M2.6 9h12.8M2.6 13h12.8"
          stroke="#6b4a3a" stroke-width="1.1"/></symbol>
  <symbol id="fx-helm" viewBox="0 0 18 18">
    <rect x="7" y="11" width="4" height="6" fill="#4a3326" stroke="#241d15" stroke-width=".6"/>
    <circle cx="9" cy="8" r="5.6" fill="none" stroke="#6b4a3a" stroke-width="1.6"/>
    <path d="M9 .6v14.8M1.6 8h14.8M3.8 2.8l10.4 10.4M14.2 2.8L3.8 13.2" stroke="#7d6845"
          stroke-width=".8"/>
    <circle cx="9" cy="8" r="1.5" fill="#2e261e" stroke="#7d6845" stroke-width=".6"/></symbol>
  <symbol id="fx-capstan" viewBox="0 0 18 18">
    <path d="M1 9h16M9 1v16" stroke="#4a3326" stroke-width="1.8"/>
    <circle cx="9" cy="9" r="4.6" fill="#6b4a3a" stroke="#241d15" stroke-width=".9"/>
    <circle cx="9" cy="9" r="3" fill="#7d6845" stroke="#4a3326" stroke-width=".6"/>
    <path d="M6.5 6.5l5 5M11.5 6.5l-5 5" stroke="#4a3326" stroke-width=".5"/></symbol>
  <symbol id="fx-anchor" viewBox="0 0 18 18">
    <path d="M9 3.5v11.5M3.5 10.5q1 4.5 5.5 4.5t5.5-4.5" fill="none" stroke="#6a6f76"
          stroke-width="1.6" stroke-linecap="round"/>
    <path d="M5 5.2h8" stroke="#6b4a3a" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="9" cy="2.2" r="1.3" fill="none" stroke="#6a6f76" stroke-width=".9"/>
    <path d="M2.6 11.6l.9-1.6 1.2 1.4M15.4 11.6l-.9-1.6-1.2 1.4" fill="none"
          stroke="#6a6f76" stroke-width=".9"/></symbol>
  <symbol id="fx-bench" viewBox="0 0 18 18">
    <rect x="0" y="6" width="18" height="6" fill="#7d6845" stroke="#4a3326" stroke-width=".8"/>
    <path d="M0 9h18" stroke="#5c4a35" stroke-width=".45"/>
    <path d="M13 12l4 5.5" stroke="#9a8458" stroke-width="1.6" stroke-linecap="round"/></symbol>
  <symbol id="fx-boat" viewBox="0 0 18 18">
    <path d="M0 3h18v12H0z" fill="#6b4a3a" stroke="#241d15" stroke-width=".8"/>
    <path d="M0 4.5h18M0 13.5h18" stroke="#4a3326" stroke-width=".9"/>
    <rect x="7.7" y="4.5" width="2.6" height="9" fill="#7d6845" stroke="#4a3326"
          stroke-width=".5"/></symbol>
  <symbol id="fx-sea" viewBox="0 0 18 18">
    <rect width="18" height="18" fill="#2e3c46"/>
    <path d="M2 5q2-1.6 4 0t4 0t4 0M4 10.5q2-1.6 4 0t4 0t4 0M1 15.5q2-1.4 4 0t4 0"
          fill="none" stroke="#6a7a86" stroke-width=".7" opacity=".85"/></symbol>
  <symbol id="fx-gunwale" viewBox="0 0 18 18">
    <rect width="18" height="18" fill="#2e3c46"/>
    <path d="M2 4q2-1.6 4 0t4 0t4 0M3 9q2-1.6 4 0t4 0" fill="none" stroke="#6a7a86"
          stroke-width=".7" opacity=".85"/>
    <rect x="0" y="12.4" width="18" height="5.6" fill="#4a3326" stroke="#241d15"
          stroke-width=".6"/>
    <rect x="0" y="12.4" width="18" height="2.2" fill="#7d6845"/></symbol>
  <symbol id="fx-bollard" viewBox="0 0 18 18">
    <circle cx="9" cy="9" r="4.6" fill="#4a3326" stroke="#241d15" stroke-width=".9"/>
    <circle cx="9" cy="9" r="3.2" fill="#6b4a3a" stroke="#2e261e" stroke-width=".6"/>
    <path d="M4 12.5q5 3 10 0" fill="none" stroke="#9a8458" stroke-width="1"/></symbol>
  <symbol id="fx-window" viewBox="0 0 18 18">
    <rect x="3" y="0" width="12" height="2.4" fill="#6a7a86" opacity=".7" stroke="#6b4a3a"
          stroke-width=".9"/></symbol>`;

// A square's name on the board: column letters (A..Z, then AA..), rows from 1 at the top.
// The engine reads the same names back (rules/fixtures.py `square_name`).
function sqCol(c) {
  return c < 26 ? String.fromCharCode(65 + c)
    : String.fromCharCode(64 + Math.floor(c / 26)) + String.fromCharCode(65 + c % 26);
}
function sqName(c, r) { return `${sqCol(c)}${r + 1}`; }

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

  const CELL = 18, MARGIN = 14;   // MARGIN: room for the coordinates, top and left
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
  // Raised ground as relief (variant D, 2026-11-13): a lit lip on the edges that face the
  // room's light (north, west) and a shadow on the two that do not, wherever the ground
  // next door is lower. Four shades of brown alone said "different", not "higher".
  const lip = [], shade = [];
  for (const [c, r, v] of (g.floor || [])) {
    if (at(c, r - 1) < v) lip.push([c, r, c + 1, r]);
    if (at(c - 1, r) < v) lip.push([c, r, c, r + 1]);
    if (at(c, r + 1) < v) shade.push([c, r + 1, c + 1, r + 1]);
    if (at(c + 1, r) < v) shade.push([c + 1, r, c + 1, r + 1]);
  }
  parts.push(edgePath(lip, "lip"), edgePath(shade, "shade"));
  // The fight's own answers for the PC (views._tactics), {} outside one: who threatens
  // which square, which moves provoke and from whom, what the PC cannot see, a hunch's
  // range. Read here, never worked out: one rule, in the engine.
  const T = g.tactics || {};
  const provokes = T.provokes || {};
  // Rails as edges, not fills. A parapet is a thing to shoot over; a filled square
  // would read as a wall, which is the very mistake the engine was making.
  // A gallery's rail is stored on the ground square in front of it and drawn on the
  // gallery's edge (the side meeting floor at the rail's height), as scene3d.js does:
  // through the middle of that square it crossed the stair and whoever stood there.
  const solidSq = new Set((g.blocked || []).map(([c, r]) => `${c},${r}`));
  for (const [c, r, v] of (g.parapet || [])) {
    const d = [[0, -1], [0, 1], [-1, 0], [1, 0]].find(([dx, dy]) =>
      !solidSq.has(`${c + dx},${r + dy}`) && at(c + dx, r + dy) >= v);
    const [x1, y1, x2, y2] = !d ? [c + .1, r + .5, c + .9, r + .5]
      : d[0] ? [c + (d[0] > 0 ? 1 : 0), r + .1, c + (d[0] > 0 ? 1 : 0), r + .9]
      : [c + .1, r + (d[1] > 0 ? 1 : 0), c + .9, r + (d[1] > 0 ? 1 : 0)];
    parts.push(`<line class="rail" x1="${x1 * CELL}" y1="${y1 * CELL}" x2="${
      x2 * CELL}" y2="${y2 * CELL}"><title>a rail, ${v * 5} ft up</title></line>`);
  }
  // The named fixtures (rules/fixtures.py), each drawn as the thing it is: one <symbol>
  // per kind in <defs> (FX_DEFS) and one <use> per square, so a 24x24 board of barrels is
  // 576 small elements at most, never a hand-drawn picture per square. Every symbol is
  // drawn in an 18-unit square with its FRONT to the south; the square's own rotation
  // turns that front to the open floor (a shelf's spines face the room, a stair climbs
  // toward its gallery). Over the terrain fill and deaf to the pointer, so a lit square
  // under a stair still queues the move onto it. The palette is the table's own: wood
  // from the leather and brass browns, stone from the board's greys, the ember for a fire.
  const fixtures = g.fixtures || [];
  const fxRot = { "0,1": 0, "-1,0": 90, "0,-1": 180, "1,0": 270 };
  const openAt = (c, r) => c >= 0 && r >= 0 && c < g.width && r < g.height
    && !solidSq.has(`${c},${r}`);
  const wetSq = new Set(fixtures.filter(f => f.kind === "sea" || f.kind === "rail")
    .flatMap(f => f.squares.map(([c, r]) => `${c},${r}`)));
  for (const f of fixtures) {
    const sq = f.squares || [];
    if (!sq.length) continue;
    // Faded when it stands on another floor; a stair, a gallery's planks and a crate you
    // climb (a raised square, not a solid one) are all reached from this one.
    const off = (f.level || 0) !== MAP_LEVEL && solidSq.has(`${sq[0][0]},${sq[0][1]}`)
      ? " offlevel" : "";
    const tip = `<title>${esc(f.name)}</title>`;
    const xs = sq.map(p => p[0]), ys = sq.map(p => p[1]);
    const runX = Math.max(...xs) - Math.min(...xs) >= Math.max(...ys) - Math.min(...ys);
    for (const [c, r] of sq) {
      let turn = 0;
      if (f.kind === "stair") {
        // Up is toward the highest open neighbour; the symbol climbs north.
        const up = [[0, -1], [0, 1], [-1, 0], [1, 0]].reduce((best, d) =>
          at(c + d[0], r + d[1]) > at(c + best[0], r + best[1]) ? d : best, [0, -1]);
        turn = (fxRot[`${-up[0]},${-up[1]}`] || 0);
      } else if (["bookshelf", "rack", "hearth", "counter", "stall", "door", "window"]
                 .includes(f.kind)) {
        // The front faces the open floor across the run: a shelf against a wall.
        const sides = runX ? [[0, 1], [0, -1]] : [[1, 0], [-1, 0]];
        const front = sides.find(([dx, dy]) => openAt(c + dx, r + dy)) || sides[0];
        turn = fxRot[`${front[0]},${front[1]}`] || 0;
      } else if (["cart", "table", "gallery", "bench", "boat"].includes(f.kind)) {
        turn = runX ? 0 : 90;
      } else if (f.kind === "rail") {
        // The planking faces the deck it closes, whichever side of the hull it is on and
        // whatever stands there (a barrel at the rail is still deck): the side that is
        // not more water. The rail round the bow runs every way at once.
        const front = [[0, 1], [0, -1], [1, 0], [-1, 0]].find(([dx, dy]) =>
          c + dx >= 0 && r + dy >= 0 && c + dx < g.width && r + dy < g.height
          && !wetSq.has(`${c + dx},${r + dy}`)) || [0, 1];
        turn = fxRot[`${front[0]},${front[1]}`] || 0;
      }
      const sym = FX_SYMBOL[f.kind];
      if (!sym) continue;
      parts.push(`<use href="#fx-${sym}" class="fx${off}" pointer-events="none" x="${
        c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"${turn
        ? ` transform="rotate(${turn} ${(c + .5) * CELL} ${(r + .5) * CELL})"` : ""}>${
        tip}</use>`);
    }
  }

  const safe = new Set();
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
    // In a fight the move is split by the engine's own "would this provoke"
    // (`reactions.provoked_by_move`): the safe squares bright inside a candle outline, the
    // provoking ones the old dim gold. Marking the exception is what reads: in the mock's
    // fight 80 of 86 squares provoked, and a red wash on all of them (tried first) turned
    // the whole board red, a notch on each (tried second) was confetti.
    const how = !T.provokes ? "" : provokes[key] ? " risky" : " safe";
    if (how === " safe") safe.add(key);
    parts.push(cell(c, r, `reach${how}`, `<title>${sqName(c, r)} · ${cost} ft${
        lvl ? ` · ${lvl * 5} ft up` : ""}${how === " risky" ? " · provokes" : ""}</title>`)
      .replace(`class="reach${how}"`, `class="reach${how}" data-sq="${c},${r}${
        lvl ? "," + lvl : ""}"`));
  }
  const reachEdges = boardEdges(g, (c, r) => reach.has(`${c},${r}`));
  const safeEdges = safe.size && safe.size < reach.size
    ? boardEdges(g, (c, r) => safe.has(`${c},${r}`)) : [];

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

  // Threatened squares: a hatch in --alarm, not a fill, so the ground and the move wash
  // read through it and it survives colour blindness where a red tint does not.
  for (const k of Object.keys(T.threat || {})) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="threat" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);
  }
  // What the PC cannot see: fog, not a black-out, so remembered walls still read as walls
  // (Foundry ships fog as an opacity for the same reason).
  for (const [c, r] of (T.unseen || []))
    parts.push(`<rect class="fog" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);

  // Grid lines last of the terrain, so they sit over the fills and under the tokens.
  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);

  // Coordinates in the margin, letters across and numbers down, as play-by-post tables
  // name squares ("move to H3"): the owner, 2026-11-12, "display coordinates on the map so
  // that the user can be precise about where he wants to stand even outside of combat".
  // A line naming one ("I go to C5") walks there (rules/fixtures.py `square_said`).
  for (let c = 0; c < g.width; c++)
    parts.push(`<text class="coord col" x="${(c + .5) * CELL}" y="${-4}">${sqCol(c)}</text>`);
  for (let r = 0; r < g.height; r++)
    parts.push(`<text class="coord row" x="${-7}" y="${(r + .5) * CELL + 3}">${r + 1}</text>`);

  // Night (mock, plan item 10): the light the PC sees (views._light_state), as a wash
  // over the ground and under the tokens, so people stay readable; a square a carried
  // light raises is left out of it. One path a level, never a rect a square.
  if (g.light) {
    const lit = {}, wash = { dim: "", dark: "" };
    for (const p of g.light.lit || []) lit[`${p[0]},${p[1]}`] = p[2];
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
      const lv = lit[`${c},${r}`] || g.light.level;
      if (lv in wash) wash[lv] += `M${c * CELL} ${r * CELL}h${CELL}v${CELL}h${-CELL}z`;
    }
    for (const lv in wash) if (wash[lv])
      parts.push(`<path class="night ${lv}" pointer-events="none" d="${wash[lv]}"/>`);
  }

  // The edge of the move, the edge of its safe steps, and the edge of each hunch: a hunch
  // is a range round the PC (the squares views._tactics sends), never a square of the foe.
  // In a fight only, as the 3D board lights the move only then: walking round town, a gold
  // line round thirty feet of street says "this matters" when nothing does.
  if (s.scene.in_encounter)
    parts.push(edgePath(reachEdges, "reachedge"), edgePath(safeEdges, "safeedge"));
  for (const h of (T.hunches || [])) {
    const inside = new Set(h.squares.map(p => `${p[0]},${p[1]}`));
    parts.push(`<path class="hunch" d="${pathOf(boardEdges(g, (c, r) => inside.has(`${c},${r}`)))
      }"><title>you sense ${h.count === 1 ? "a foe" : h.count + " foes"} within ${
      h.within_ft} ft</title></path>`);
  }

  // Blood before bodies, so a token stands in its own pool rather than under it.
  for (const b of (s.scene.pools || [])) {
    if (!b.at) continue;
    parts.push(`<circle class="bloodpool" cx="${(b.at[0] + .5) * CELL}" cy="${
      (b.at[1] + .5) * CELL}" r="${CELL * .38}">
      <title>blood pool — ${esc(b.source || b.owner)}</title></circle>`);
  }

  // Who the latest spell's area caught (the engine's own list, unseen creatures dropped).
  const caught = new Set((g.areas || []).flatMap(a => a.caught || []));
  for (const a of s.scene.actors) {
    if (!a.at) continue;
    // Each body is one group, focusable and named, so the readout answers a tap, a point
    // or a Tab on it alike (variant D: a phone has no hover).
    const tp = [];
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
    // Round, as a miniature's base is (2026-11-11, the owner: "replace the square people
    // with something that will indicate it is a humanoid"). Seen from above: a person is
    // shoulders and a head, a beast (`form`, from the `type.*` tags in play/views.py) a
    // long body with its head to one side, an ooze a spreading ring. The initial sits on
    // the head; a crowd keeps its hatching and its count.
    const up = s.scene.in_encounter && a.ref && a.ref === s.scene.turn_ref ? " up" : "";
    const cx = (c + n / 2) * CELL, cy = (r + n / 2) * CELL, k = n * CELL / 18;
    // Whose turn: a still candle ring round the token. A pulse was refused in the mock: it
    // would be the one thing on the board that never stops moving.
    if (up) tp.push(`<circle class="turnring" cx="${cx}" cy="${cy}" r="${n * CELL / 2 + .6}"/>`);
    tp.push(`<circle class="token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}${
      up}" cx="${cx}" cy="${cy}" r="${n * CELL / 2 - 1.5}">
      <title>${esc(a.name)} — ${a.hp}/${a.hp_max}${
        unit ? ` · ${a.members} of ${a.members_max} still standing` : ""}${
        a.at.length > 2 && a.at[2] ? ` · ${a.at[2] * 5} ft up` : ""}</title></circle>`);
    const form = unit ? "" : a.form || "humanoid";
    // The server's plate letters (views._marks): two when an initial clashes here.
    const mark = a.mark || a.name.slice(0, 1).toUpperCase();
    const glyph = form === "beast"
      ? `<ellipse cx="${cx - 1.2 * k}" cy="${cy}" rx="${4.6 * k}" ry="${2.8 * k}"/>
         <circle class="head" cx="${cx + 3.6 * k}" cy="${cy}" r="${2.2 * k}"/>`
      : form === "ooze"
      ? `<circle cx="${cx}" cy="${cy}" r="${5 * k}"/><circle class="head" cx="${cx}" cy="${
          cy}" r="${2.6 * k}"/>`
      : form ? `<ellipse cx="${cx}" cy="${cy + .4 * k}" rx="${6 * k}" ry="${3 * k}"/>
         <circle class="head" cx="${cx}" cy="${cy}" r="${3.4 * k}"/>` : "";
    if (glyph) tp.push(`<g class="tokbody${down ? " down" : ""}${ghost}">${glyph}</g>`);
    // A keeper's brass coin (mock, plan item 4), the 3D base's own: not a ring, which
    // already means whose turn it is.
    if (a.keeps && !down) tp.push(`<circle class="keepcoin${ghost}" cx="${cx + 5.6 * k}" cy="${
      cy + 5.6 * k}" r="${2 * k}"><title>${esc(a.name)} keeps a counter here</title></circle>`);
    tp.push(`<text class="tok${unit ? "" : " ini"}${ghost}" x="${
      form === "beast" ? cx - 1.2 * k : cx}" y="${
      unit ? cy + 3.2 : cy + 2.1 * k}" style="font-size:${unit ? 9 : (mark.length > 1 ? 4.4 : 6) * k
        }px">${unit ? a.members : esc(mark)}</text>`);
    // The downed are struck through, so "down" reads without telling faded from far away.
    if (down) {
      const d = (n * CELL / 2 - 3) * .7071;
      tp.push(`<path class="strike" d="M${cx - d} ${cy - d}L${cx + d} ${cy + d}M${cx + d} ${
        cy - d}L${cx - d} ${cy + d}"/>`);
    }
    parts.push(`<g class="tokg${ghost}${caught.has(a.ref) ? " caught" : ""}" data-ref="${
      esc(a.ref)}" tabindex="0" role="button" aria-label="${esc(`${a.name}, ${a.hp} of ${
      a.hp_max}${down ? ", down" : ""}${up ? ", their turn" : ""}`)}">${tp.join("")}</g>`);
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

  // A board at least twice as long one way as the other, in a box the other way about, is
  // drawn a quarter-turn round (north to the left) so its long axis runs along the box's.
  // Measured 2026-11-13: a ship's deck (6 x 17 with its sea) drew 15% of the width of a
  // 692 x 272 board box. Text is turned back upright by the stylesheet (#map.turned);
  // MapZoom reads `data-turned` for its board-to-view sums. 3D opens zoomed instead
  // (24-map-zoom.js): a quarter-turn of an isometric board does not change its shape.
  const W = g.width * CELL, H = g.height * CELL;
  const turned = !MAP_3D && flatTurned(g);
  // The same board, drawn two ways. Both read the one geometry payload and both write
  // `data-sq`, so the combat builder cannot tell them apart — which is the whole reason
  // the flat one was built first.
  const svg = MAP_3D
    ? Scene3D.render(g, s.scene.actors || [],
                     { turn: MAP_TURN, level: MAP_LEVEL, tactics: T, caught,
                       hunches: (T.hunches || []).map(h => {
                         const inside = new Set(h.squares.map(p => `${p[0]},${p[1]}`));
                         return boardEdges(g, (c, r) => inside.has(`${c},${r}`));
                       }),
                       fight: !!s.scene.in_encounter,
                       reach: !!(STATE.scene && STATE.scene.in_encounter),
                       up: s.scene.in_encounter ? s.scene.turn_ref : null })
    : `<svg id="map" viewBox="${turned ? `${-MARGIN} 0 ${H + MARGIN} ${W + MARGIN}`
         : `${-MARGIN} ${-MARGIN} ${W + MARGIN} ${H + MARGIN}`}"${
         turned ? ` class="turned" data-turned="${W}"` : ""}
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
         </pattern>${FX_DEFS}${MAP_HATCH}
       </defs>${turned ? `<g transform="matrix(0 -1 1 0 0 ${W})">${parts.join("")}</g>`
         : parts.join("")}</svg>`;
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
                  aria-label="Turn the board left"><span class="long">Turn </span>left</button>
          <button type="button" class="v2-btn" data-mapturn="1"
                  aria-label="Turn the board right"><span class="long">Turn </span>right</button></div>` : ""}`;
  const picker = levels.length > 1
    ? `<div class="v2-recess" role="group" aria-label="Looking at"><span class="seglabel">Looking at</span>${
        levels.map(v => `<button type="button" data-maplevel="${v}" ${pressed(v === MAP_LEVEL)}>${
          v ? (v > 0 ? `+${v * 5} ft` : `${v * 5} ft`) : "the floor"}</button>`).join("")}</div>${
        g.ceiling ? `<span class="seglabel">ceiling ${g.ceiling * 5} ft</span>` : ""}`
    : "";
  // What is on the board, in the words the narrator is given (gm/brief/fixtures_here.py).
  const named = [...new Set(fixtures.map(f => f.name))];
  const legend = `${named.length ? `<p class="sub maplegend">Here: ${
      esc(named.join(", "))}</p>` : ""}${g.speed ? `<p class="sub maplegend">${
      reach.size} squares within ${g.speed} ft</p>` : ""}${
      pools ? `<p class="sub maplegend">${pools} pool${
        pools === 1 ? "" : "s"} of blood on the ground</p>` : ""}`;
  // The key opens OVER the board, never under it (variant D): a key that pushed the foot
  // taller shrank the board while somebody was looking at it. It stays as it was left.
  const sw = (cls, label) => `<span class="mapk"><i class="sw ${cls}" aria-hidden="true"></i>${label}</span>`;
  const key = `<details class="mapkey"${typeof MAPREAD !== "undefined" && MAPREAD.keyOpen ? " open" : ""}><summary>Key</summary>
      <div class="mapkeyrow">${sw("k-pc", "You")}${sw("k-ally", "Ally")}${sw("k-foe", "Foe")}${
      sw("k-by", "Bystander")}${s.scene.in_encounter ? sw("k-turn", "Whose turn") : ""}${
      T.provokes ? sw("k-safe", "Move, safe") + sw("k-risky", "Move, provokes") : ""}${
      T.threat ? sw("k-threat", "Threatened") : ""}${T.unseen ? sw("k-fog", "Out of sight") : ""}${
      (T.hunches || []).length ? sw("k-hunch", "Sensed foe, somewhere inside") : ""}
      ${g.about ? `<p class="sub maplegend">${esc(g.about)}</p>` : ""}${legend}</div></details>`;
  // The place is named, not just drawn. A correct map of the well, while the prose is
  // describing a gate, is indistinguishable from a broken map unless the board says which
  // place it is (reported 2026-09-21). `about` is the shape's own line about what that
  // kind of place is made of, which is also what the plan was built from.
  // The heading is the board's own `#board-name`; 16-tab-map.js writes this into it while
  // the ground is shown and the town's name while Places is.
  $("#boardframe").dataset.ground = g.place ? `The ground · ${g.place}` : "The ground";
  $("#groundctl").innerHTML = view + picker;
  // The readout (25-map-readout.js) is a box of fixed height under the board, so nothing
  // tapped or pointed at changes the board's size.
  $("#mapwrap").innerHTML = `<div class="boardview">${svg}</div>
    <div class="boardfoot"><div id="mapread" class="mapread" aria-live="polite"></div>
      <div class="maprow">${key}${g.about ? `<span class="mapabout" title="${esc(g.about)}">${
        esc(g.about)}</span>` : ""}</div></div>`;
  if (typeof mapReadout === "function") mapReadout(s, T);
  if (typeof mapPaint === "function") mapPaint();
  if (typeof MapZoom !== "undefined") MapZoom.mount(g, s.scene);

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
  function pathOf(edges) {
    return edges.map(([x1, y1, x2, y2]) => `M${x1 * CELL} ${y1 * CELL}L${x2 * CELL} ${y2 * CELL}`).join("");
  }
  function edgePath(edges, cls) {
    return edges.length ? `<path class="${cls}" pointer-events="none" d="${pathOf(edges)}"/>` : "";
  }
}

// The hatch both views lay over a threatened square: --alarm (#b0483c), thin, at 45°.
const MAP_HATCH = `<pattern id="maphatch" width="4" height="4" patternUnits="userSpaceOnUse"
  patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="#b0483c"
  stroke-width="1.1" stroke-opacity=".7"></line></pattern>`;

// Whether the flat board is drawn a quarter-turn round (renderMap): long (2 : 1 or more)
// one way, in a box that is long the other way. The box is the board's last one, or the
// map's panel before the first; unmeasured (a hidden tab), it is taken as wide.
function flatTurned(g) {
  const long = Math.max(g.width, g.height), short = Math.min(g.width, g.height);
  if (!short || long < 2 * short) return false;
  const box = document.querySelector("#mapwrap .boardview") || document.getElementById("mapwrap");
  const r = box ? box.getBoundingClientRect() : null;
  const wide = !r || !r.width || !r.height || r.width >= r.height;
  return wide !== (g.width >= g.height);
}

// The outline of a set of squares as unit edges [x1, y1, x2, y2] in squares: the edge of
// the move, of its safe steps, of a hunch's range. Geometry only; the set is the engine's.
function boardEdges(g, inside) {
  const out = [];
  const ok = (x, y) => x >= 0 && y >= 0 && x < g.width && y < g.height && inside(x, y);
  for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
    if (!inside(c, r)) continue;
    if (!ok(c, r - 1)) out.push([c, r, c + 1, r]);
    if (!ok(c, r + 1)) out.push([c, r + 1, c + 1, r + 1]);
    if (!ok(c - 1, r)) out.push([c, r, c, r + 1]);
    if (!ok(c + 1, r)) out.push([c + 1, r, c + 1, r + 1]);
  }
  return out;
}

function renderRolls(log) {
  const rolls = [];
  for (const entry of log) {
    for (const o of (entry.outcomes || [])) {
      for (const r of (o.rolls || [])) {
        rolls.push({r, o});
      }
    }
  }
  // Only the player's own rolls ever appear here. The server already strips everyone
  // else's before the state leaves it, so there is nothing to filter and nothing to
  // find in the page source.
  $("#rolls").innerHTML = rolls.slice(-8).reverse().map(({r, o}) => `
    <div class="who" style="display:block">
      <div style="display:flex;justify-content:space-between">
        <span>${esc(r.label || o.op)}</span>
        <span style="color:var(--accent)">${r.total}${
          // Only a d20 is compared against a DC or an AC. Showing the outcome's target
          // beside a damage roll read as "6 vs 10", which looks like a miss.
          o.dc && o.dc.value != null && r.die === "1d20" ? " vs " + o.dc.value : ""}</span>
      </div>
      <small>${r.raw}${
        r.modifiers.map(m => ` ${sign(m.value)} ${esc(m.source)}`).join("")}</small>
    </div>`).join("") || `<div class="sub">Nothing rolled yet.</div>`;
}

function showPopup(p) {
  // The 3D die, asking. `Dice3D.ask` resolves with a number the player rolled on a real
  // die — behind the debug toggle, because a die on the desk is the exception — or null,
  // meaning the table rolls it, which is the default and what the solid is for.
  const lo = p.min != null ? p.min : 1, hi = p.max != null ? p.max : 20;
  const die = p.die || "1d20";
  const terms = p.breakdown.map(m => ({ label: m.source, value: sign(m.value) }));
  // The total row only when there is something to total: with one term the card read
      // "Str x2 +38" over "your modifier +38", the same number twice (2026-09-18, item 3).
      if (p.breakdown.length !== 1) terms.push({ label: "your modifier", value: sign(p.modifier), total: true });
  // `dc_shown` is the engine saying whether this number is a difficulty the
  // player may know or the result of a die already rolled in secret. Absent on
  // a payload from an older save mid-flight, which reads as shown — the same
  // answer it had before the flag existed.
  if (p.dc != null && p.dc_shown !== false) terms.push({ label: "beat", value: p.dc });

  const shown = {
    title: p.label,
    why: p.because || "",
    sides: hi - lo + 1 === 20 ? 20 : (hi - lo + 1),
    lo: lo, hi: hi, die: die,
    terms: terms,
    note: lo === hi ? "" : `${die} (${lo}–${hi})`,
  };
  // `hold` keeps the mat open when the table is doing the rolling, so the die goes
  // straight from the wind-up into its throw. It used to close here and reopen on the
  // far side of the request, which is the blink the player saw as the animation
  // skipping — two throws with a cut between them.
  Dice3D.ask(Object.assign({ hold: true }, shown)).then(face => sendRoll(face, shown));
}

// Everything that can be gone out and got, here, now — one list from every craft.
// Gathering on open ground — every trade's, foraging included — takes the narrated
// hourly run (`data-gather`); carcasses and stalls keep the plain excursion path.
async function loadCraftActions() {
  try {
    const d = await readJSON(await fetch("/api/craft/actions", { cache: "reload" }));
    $("#cp-biome").textContent = d.biome || "nowhere in particular";
    $("#cp-desc").textContent = d.biome_describe || "";
    const busyWhy = d.blocked || "";
    $("#cp-busy").hidden = !busyWhy;
    $("#cp-busy").textContent = busyWhy;
    $("#cp-biomepick").innerHTML = (d.biomes || []).map(b =>
      `<option value="${esc(b)}" ${b === d.biome ? "selected" : ""}>${esc(b)}</option>`
    ).join("");
    $("#cp-actions").innerHTML = (d.actions || []).map(a => {
      // Every trade's gathering on open ground goes through the narrated endpoint
      // foraging always had (the one gathering door, 2026-10-06): prose, the ground's
      // encounter, the player's own check. Until then only the herbalist's did, and a
      // prospect was one d20 and a tally line. The herbalist's keeps its old id.
      const ground = a.requires === "biome";
      const id = a.key === "herbalist:forage" ? ` id="cp-forage"` : "";
      const attr = ground ? `data-gather="${esc(a.key)}" data-label="${esc(a.label)}"${id}` :
        `data-excursion="${esc(a.key)}" data-label="${esc(a.label)}"` +
        (a.targets && a.targets.length
          ? ` data-creature="${esc(a.targets[0].name)}"` : "");
      const tip = [a.blurb || "", a.requires_note || "",
                   a.available ? "" : a.why].filter(Boolean).join("\n\n");
      return `<button type="button" ${attr} ${a.available ? "" : "disabled"}
        title="${esc(tip)}">${esc(a.label)}<small>${esc(a.track)}${
        a.level ? ` ${a.level}` : ""}</small></button>`;
    }).join("") || `<div class="cp-busy">No craft actions here.</div>`;
  } catch (err) { $("#err").textContent = err.message; }
}

// The craft-action excursion. The server narrates the setting-out, rolls the same
// forage op the bench uses, narrates the finding and hands back three suggestions;
// this only sequences what the player sees — opening first, the die landing on a real
// d100 from the run, then the full turn with the tally and the question.
document.addEventListener("click", async e => {
  if (e.target.closest("#craftaction")) {
    const panel = $("#craftpanel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) await loadCraftActions();
    return;
  }

  // The debug teleport, on the hub rather than the bench.
  if (e.target.closest("#cp-debug")) {
    const pick = $("#cp-biomepick");
    pick.hidden = !pick.hidden;
    return;
  }

  // Everything that is not foraging: one excursion, one check, a haul into the pack.
  const go = e.target.closest("[data-excursion]");
  if (go) {
    const hours = Math.max(1, Math.min(12, Number($("#cp-h").value) || 1));
    $("#craftpanel").hidden = true;
    busy(true);
    try {
      const d = await post("/api/craft/excursion",
        { action: go.dataset.excursion, hours, creature: go.dataset.creature || "" });
      busy(false);
      await Dice3D.land({
        title: go.dataset.label || "Excursion",
        why: `DC ${d.dc}${d.bonus ? ` · your bonus +${d.bonus}` : ""}`,
        sides: 20, result: d.roll,
        note: d.found && d.found.length
          ? d.found.map(h => `${h.name} ×${h.count}`).join(" · ")
          : "Nothing worth carrying.",
      });
      render(await getState());
    } catch (err) { busy(false); $("#err").textContent = err.message; }
    return;
  }

  const gather = e.target.closest("[data-gather]");
  if (!gather) return;
  const what = gather.dataset.label || "Foraging";

  const hours = Math.max(1, Math.min(48, Number($("#cp-h").value) || 1));
  $("#craftpanel").hidden = true;
  busy(true);
  try {
    let d = await post("/api/craftaction", { action: gather.dataset.gather || "forage", hours });
    busy(false);
    // The opening lands in the book at once, so the die falls inside the fiction
    // rather than in front of it.
    $("#story").insertAdjacentHTML("beforeend",
      `<p class="beat fresh">${esc(d.opening)}</p>`);
    // Counted as seen, or the full render a moment later re-runs its entrance.
    window._beatsSeen = (window._beatsSeen || 0) + 1;
    $("#story").scrollTop = $("#story").scrollHeight;
    if (d.roll) {
      // The Survival check is the player's own now — same solid, same terms as every
      // awaiting popup, but the face goes back to the excursion rather than /api/roll
      // so the tally and the closing beat still happen.
      const p = d.roll;
      const terms = p.breakdown.map(m => ({ label: m.source, value: sign(m.value) }));
      // The total row only when there is something to total: with one term the card read
      // "Str x2 +38" over "your modifier +38", the same number twice (2026-09-18, item 3).
      if (p.breakdown.length !== 1) terms.push({ label: "your modifier", value: sign(p.modifier), total: true });
      // `dc_shown` is the engine saying whether this number is a difficulty the
  // player may know or the result of a die already rolled in secret. Absent on
  // a payload from an older save mid-flight, which reads as shown — the same
  // answer it had before the flag existed.
  if (p.dc != null && p.dc_shown !== false) terms.push({ label: "beat", value: p.dc });
      // Held open, and then landed on its number before the turn is posted — the same
      // shape the table's own roll uses, and for the same reason.
      //
      // Two things were wrong here until 2026-09-17. The ask took no `hold`, so the mat
      // shut the instant the player threw and the Survival die NEVER LANDED: they wound
      // up, the die went, and the mat vanished with no number on it. That is the defect
      // reported on 2026-09-09 for the main path, still living on this one. And the
      // closing narration — a second model call, the slow half of a forage — ran before
      // anything came back, so the player watched nothing at all for the length of it.
      let face = await Dice3D.ask({
        hold: true,
        title: p.label, why: p.because || "", sides: 20, lo: 1, hi: 20, die: "1d20",
        terms,
      });
      // `null` means "the table rolls it". Ask what it shows before asking what it did:
      // the excursion's prompt is a pending roll like any other, so the same endpoint
      // answers, and it still changes nothing by answering.
      if (face == null) {
        try { face = (await post("/api/roll/face", {})).face; } catch { face = null; }
      }
      let survival = null;
      if (face != null) {
        survival = Dice3D.land({
          title: p.label, why: p.because || "", die: "1d20",
          sides: 20, lo: 1, hi: 20, result: face, terms,
        });
      }
      busy(true);
      try {
        d = await post("/api/craftaction", { face: face == null ? "auto" : face });
      } catch (err) {
        // A held mat over a dead request is a die spinning on a page that has stopped.
        Dice3D.close();
        throw err;
      } finally {
        busy(false);
      }
      // The haul is a second die, and it may not open on top of the first. The player
      // closes the Survival check when they have read it; the d100 follows.
      if (survival) await survival; else Dice3D.close();
    }
    if (d.rolls && d.rolls.length) {
      await Dice3D.land({
        title: what, why: `${d.hours} hour${d.hours === 1 ? "" : "s"} on the ground`,
        sides: 100, lo: 1, hi: 100, result: d.rolls[0],
        note: d.rolls.length > 1
          ? `The first of ${d.rolls.length} sweeps — the log has the rest.` : "",
      });
    } else if (d.checks && d.checks.length) {
      // A barren day found nothing to pick, so there is no d100 — but the Survival
      // checks were real dice, and the first of them is what lands.
      await Dice3D.land({
        title: what, why: `Survival check, DC ${d.checks[0].dc}`,
        sides: 20, result: Math.min(20, Math.max(1, d.checks[0].roll)),
        note: d.checks.length > 1
          ? `The first of ${d.checks.length} hours — none of them found a thing.` : "",
      });
    }
    render(await getState());
  } catch (err) {
    busy(false);
    $("#err").textContent = err.message;
  }
});
// The debug teleport itself. `travel` is the real op — the ground moves, and the
// scene's own clock and biome move with it.
document.addEventListener("change", async e => {
  if (!e.target.closest("#cp-biomepick")) return;
  busy(true);
  try {
    await post("/api/travel", { biome: e.target.value });
    await loadCraftActions();
    render(await getState());
  } catch (err) { $("#err").textContent = err.message; }
  finally { busy(false); }
});

document.addEventListener("input", e => {
  if (e.target.closest("#cp-h")) $("#cp-hn").textContent = e.target.value;
});

// The glossary: any named feature on the sheet answers a click with what it does.
// "there is nowhere the user can look to see what any of the blood bender abilities
// actually do" — the text was in the class data the whole time; this is the door to it.
function glossFor(name) {
  const g = (SHEET && SHEET.glossary) || {};
  let key = String(name || "").toLowerCase().replace(/\s+/g, " ").trim();
  while (key) {
    if (g[key]) return g[key];
    // The sheet's own computed feat lines answer too ("+1 AC" for Dodge).
    const feat = (SHEET.feats || []).find(f => f.name.toLowerCase() === key);
    if (feat && feat.effect) return { name: feat.name, text: feat.effect,
      source: feat.source || "feat" };
    const parts = key.split(" ");
    if (parts.length > 1 && /\d/.test(parts[parts.length - 1])) {
      key = parts.slice(0, -1).join(" ");
    } else break;
  }
  return null;
}

function glossify(name) {
  // A span the click handler recognises; names with no entry stay plain text, so a
  // dotted underline is a promise the click will be answered.
  return glossFor(name)
    ? `<span class="gloss" data-gloss="${esc(name)}">${esc(name)}</span>`
    : esc(name);
}

document.addEventListener("click", e => {
  const hit = e.target.closest("[data-gloss]");
  let card = document.getElementById("glosscard");
  if (!card) {
    card = document.createElement("div");
    card.id = "glosscard";
    document.body.appendChild(card);
  }
  if (!hit) { card.classList.remove("on"); return; }
  const entry = glossFor(hit.dataset.gloss);
  if (!entry) { card.classList.remove("on"); return; }
  card.innerHTML = `<h4>${esc(entry.name)}</h4>
    <div class="src">${esc(entry.source || "")}</div>
    <p>${esc(entry.text)}</p>`;
  card.classList.add("on");
  // Beside the click, kept on screen.
  const r = hit.getBoundingClientRect();
  card.style.left = Math.min(innerWidth - 440, Math.max(8, r.left)) + "px";
  card.style.top = Math.min(innerHeight - 160, r.bottom + 8) + "px";
});

