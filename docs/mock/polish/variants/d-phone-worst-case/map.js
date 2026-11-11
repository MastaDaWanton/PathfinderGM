// Variant d-phone-worst-case. Started from the verbatim 0.2.29 copy in variants/current;
// renderMap keeps its structure, its data-sq contract and its controls, and gains what
// polish.js works out (previews, sight, the hunch, the lamp). Comments from the game's
// file are kept where the code they explain is kept.

let MAP_LEVEL = 0;
let MAP_TURN = 0, MAP_3D = false;

// What the readout is showing: a pinned selection (a tap or a click) and a passing one (a
// pointer that can hover). Not part of STATE, for the reason MAP_LEVEL is not.
const PVS = { sel: null, hover: null, F: null, keyOpen: false };

function renderMap(real) {
  // The worst case swaps the scene at the data boundary, the same door the real one
  // comes through; nothing below knows which it is drawing.
  let s = real, sc = window.POLISH_SCENE;
  if (PV.worst) {
    sc = PV.worstScene();
    s = sc.state;
    // The harness's spell toggle, followed: the made-up cone when the real one is shown.
    if (real.scene.grid && (real.scene.grid.areas || []).length)
      s.scene.grid.areas = [sc.extras.spell_area.as_grid_area];
  }
  const g = s.scene.grid;
  if (!g) {
    $("#mapwrap").innerHTML = "";
    $("#groundctl").innerHTML = "";
    $("#boardframe").dataset.ground = "The ground";
    if (typeof mapPaint === "function") mapPaint();
    return;
  }

  const F = PV.facts(s, sc);
  PVS.F = F;
  const CELL = 18;
  const reach = F.reach;
  const parts = [];

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
  // Raised ground as relief: a lit lip on the edges that face the lamp (north, west) and a
  // shadow on the two that do not, wherever the ground next door is lower. Four shades of
  // brown alone said "different", not "higher"; a bevel says higher in every map style
  // from Dyson's to XCOM's.
  const lip = [], shadow = [];
  for (const [c, r, v] of (g.floor || [])) {
    if (at(c, r - 1) < v) lip.push([c, r, c + 1, r]);
    if (at(c - 1, r) < v) lip.push([c, r, c, r + 1]);
    if (at(c, r + 1) < v) shadow.push([c, r + 1, c + 1, r + 1]);
    if (at(c + 1, r) < v) shadow.push([c + 1, r, c + 1, r + 1]);
  }
  parts.push(edgePath(lip, "lip"), edgePath(shadow, "shade"));
  for (const [c, r, v] of (g.parapet || []))
    parts.push(`<line class="rail" x1="${c * CELL + 2}" y1="${(r + .5) * CELL}" x2="${
      (c + 1) * CELL - 2}" y2="${(r + .5) * CELL}"><title>a rail, ${
      v * 5} ft up</title></line>`);

  // The squares the PC can reach, split in two by the engine's own answer to "would this
  // move provoke": bright gold and a candle outline where it is safe, the game's own dim
  // gold where it is not, and the detail (who would swing) on a tap or a point, as Baldur's
  // Gate 3 warns on the path being considered rather than on the whole map.
  // Tried and rejected, both measured on this fight, where 80 of 86 squares provoke: an
  // alarm-red wash turned the board red at every hour (dawn and night looked the same and
  // nothing read as safe), and an alarm notch in each corner was 80 red triangles of
  // confetti. Marking the exception, the few safe squares, is what reads.
  const safe = new Set();
  for (const [k, e] of reach) {
    const [c, r] = k.split(",").map(Number);
    const lvl = at(c, r);
    const risky = (F.provokes[k] || []).length ? " risky" : "";
    parts.push(cell(c, r, `reach${risky}`, `<title>${e[2]} ft${
        lvl ? `, ${lvl * 5} ft up` : ""}${risky ? ", provokes" : ""}</title>`)
      .replace(`class="reach${risky}"`, `class="reach${risky}" data-sq="${c},${r}${
        lvl ? "," + lvl : ""}"`));
    if (!risky) safe.add(k);
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
        here ? 0.32 : 0}" stroke="#f0a050" stroke-opacity="${here ? 0.55 : 0.8}"
        stroke-width="${here ? 0.8 : 1.2}"${here ? "" : ` stroke-dasharray="3 2"`}
        pointer-events="none"><title>${esc(name)}${here ? "" : ", above or below this floor"
        }</title></rect>`);
    }
  }

  // Threatened squares: a hatch, not a fill, so the ground and the move wash still read
  // through it. Hatching is the tabletop convention for "this area is dangerous" and it
  // survives colour blindness where a red tint does not.
  for (const k of F.threat.keys()) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="threat" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);
  }
  // What the PC cannot see, and what is too dark to make out: a fog over the ground, not
  // a black-out. Foundry ships fog as an opacity for this reason; the terrain under it is
  // remembered ground, and walls should still read as walls.
  for (const k of F.unseen) {
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="fog" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);
  }
  for (const k of F.dark) {
    if (F.unseen.has(k)) continue;
    const [c, r] = k.split(",").map(Number);
    parts.push(`<rect class="fog dark" x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}"/>`);
  }

  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);

  // The lamp, laid over the ground and under every token: the hour changes the room, and
  // never the colour of who is standing in it.
  const W = g.width * CELL, H = g.height * CELL;
  if (F.light.hue)
    parts.push(`<rect class="lamp hue" width="${W}" height="${H}" fill="${F.light.hue}" opacity="${F.light.hueAmount}"/>`);
  if (F.light.dim)
    parts.push(`<rect class="lamp" width="${W}" height="${H}" fill="${F.light.dim}"/>`);

  // The edge of the move, the edge of the safe steps, and the edge of the hunch.
  parts.push(edgePath(F.reachEdges, "reachedge"));
  if (safe.size && safe.size < reach.size)
    parts.push(edgePath(PV.edges(g, sq => safe.has(`${sq[0]},${sq[1]}`)), "safeedge"));
  for (const h of F.hunches)
    parts.push(`<path class="hunch" d="${pathOf(h.edges)}"><title>you sense ${h.n === 1
      ? "a foe" : h.n + " foes"} within ${h.ft} ft</title></path>`);

  for (const b of (s.scene.pools || [])) {
    if (!b.at) continue;
    parts.push(`<circle class="bloodpool" cx="${(b.at[0] + .5) * CELL}" cy="${
      (b.at[1] + .5) * CELL}" r="${CELL * .38}">
      <title>blood pool, ${esc(b.source || b.owner)}</title></circle>`);
  }

  // Tokens: the down first, so a standing body covers a fallen one and not the reverse.
  const order = [...F.actors].sort((a, b) => (a.hp > 0) - (b.hp > 0));
  for (const a of order) {
    const [c, r] = a.at;
    const n = a.squares || 1;
    const down = a.hp <= 0;
    const side = a.stance ? ` ${a.stance}` : (s.scene.in_encounter ? " bystander" : "");
    const mine = (a.at.length > 2 ? a.at[2] : 0) === MAP_LEVEL;
    const ghost = mine ? "" : " offlevel";
    const unit = a.members != null;
    // Two or more on one square: each drawn a quarter size in its own corner, so none is
    // hidden under another. Measured on the worst case: a fallen goblin under a standing
    // ally was invisible and untappable.
    const stack = F.stacks.get(a.at.join(",")) || [a.ref];
    const i = stack.indexOf(a.ref), many = n === 1 && stack.length > 1;
    const sz = many ? CELL / 2 - 1 : n * CELL - 3;
    const x = many ? c * CELL + 1 + (i % 2) * CELL / 2 : c * CELL + 1.5;
    const y = many ? r * CELL + 1 + (Math.floor(i / 2) % 2) * CELL / 2 : r * CELL + 1.5;
    const label = F.labels.get(a.ref);
    const fs = many ? 5.5 : n > 1 ? 11 : label.length > 1 ? 7.5 : 9.5;
    const turn = a.ref === F.turn ? " turn" : "";
    const caught = F.caught.has(a.ref) ? " caught" : "";
    const tip = `${a.name}, ${a.hp}/${a.hp_max}${unit ? `, ${a.members} of ${a.members_max} still standing` : ""}${
      a.at.length > 2 && a.at[2] ? `, ${a.at[2] * 5} ft up` : ""}${down ? ", down" : ""}`;
    parts.push(`<g class="tokg${side}${down ? " down" : ""}${ghost}${turn}${caught}" data-ref="${esc(a.ref)}"
      tabindex="0" role="button" aria-label="${esc(tip)}">
      ${turn ? `<rect class="turnring" x="${x - 2}" y="${y - 2}" width="${sz + 4}" height="${sz + 4}" rx="4.5"/>` : ""}
      <rect class="token${side}${down ? " down" : ""}${unit ? " unit" : ""}"
      x="${x}" y="${y}" width="${sz}" height="${sz}" rx="${many ? 2 : 3}"><title>${esc(tip)}</title></rect>
      ${down ? `<path class="strike" d="M${x + 3} ${y + 3}L${x + sz - 3} ${y + sz - 3}M${x + sz - 3} ${y + 3}L${x + 3} ${y + sz - 3}"/>` : ""}
      ${many && i > 3 ? "" : `<text class="tok" x="${x + sz / 2}" y="${y + sz / 2 + fs * .36}" style="font-size:${fs}px">${esc(label)}</text>`}</g>`);
  }

  if (typeof COMBAT !== "undefined" && COMBAT.aim && !MAP_3D) {
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++)
      parts.push(`<rect class="aimsq" data-aimsq="${c},${r}" x="${c * CELL}" y="${r * CELL}"
        width="${CELL}" height="${CELL}" fill="transparent"><title>the north-west corner of ${
        c},${r}</title></rect>`);
  }

  const svg = MAP_3D
    ? Scene3D.render(g, F.actors,
                     { turn: MAP_TURN, level: MAP_LEVEL, F,
                       reach: !!(s.scene && s.scene.in_encounter) })
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

  const places = typeof mapShowingPlaces === "function" && mapShowingPlaces();
  const pressed = on => `class="v2-btn" aria-pressed="${on && !places ? "true" : "false"}"`;
  const view = `<div class="v2-recess" role="group" aria-label="View">
      <button type="button" data-mapview="flat" ${pressed(!MAP_3D)}>Flat</button>
      <button type="button" data-mapview="3d" ${pressed(MAP_3D)}>3D</button></div>${MAP_3D
      ? `<div class="v2-recess" role="group" aria-label="Turn the board">
          <button type="button" class="v2-btn" data-mapturn="-1"
                  aria-label="Turn the board left"><span class="pv-long">Turn </span>left</button>
          <button type="button" class="v2-btn" data-mapturn="1"
                  aria-label="Turn the board right"><span class="pv-long">Turn </span>right</button></div>` : ""}`;
  const picker = levels.length > 1
    ? `<div class="v2-recess" role="group" aria-label="Looking at"><span class="seglabel">Looking at</span>${
        levels.map(v => `<button type="button" data-maplevel="${v}" ${pressed(v === MAP_LEVEL)}>${
          v ? (v > 0 ? `+${v * 5} ft` : `${v * 5} ft`) : "the floor"}</button>`).join("")}</div>${
        g.ceiling ? `<span class="seglabel pv-ceil">ceiling ${g.ceiling * 5} ft</span>` : ""}`
    : "";
  const pools = (s.scene.pools || []).length;
  $("#boardframe").dataset.ground = g.place ? `The ground, ${g.place}` : "The ground";
  $("#groundctl").innerHTML = view + picker;

  // The key opens OVER the board, never under it: a key that pushed the foot taller
  // would shrink the board while somebody was looking at it. Once opened or shut, it
  // stays as it was left across redraws.
  const sw = (cls, label) => `<span class="pv-k"><i class="sw ${cls}" aria-hidden="true"></i>${label}</span>`;
  const key = `<details class="pv-key"${PVS.keyOpen ? " open" : ""}><summary>Key</summary><div class="pv-keyrow">
      ${sw("k-pc", "You")}${sw("k-ally", "Ally")}${sw("k-foe", "Foe")}${sw("k-by", "Bystander")}${sw("k-turn", "Whose turn")}
      ${sw("k-safe", "Move, safe")}${sw("k-risky", "Move, provokes")}${sw("k-threat", "Threatened")}
      ${sw("k-fog", "Out of sight")}${sw("k-hunch", "Sensed foe, somewhere inside")}
      ${pools ? `<span class="pv-k">${pools} pool${pools === 1 ? "" : "s"} of blood</span>` : ""}
      ${g.about ? `<span class="pv-k pv-aboutk">${esc(capFirst(g.about))}</span>` : ""}</div></details>`;
  $("#mapwrap").innerHTML = `<div class="boardview${PV.worst ? " is-worst" : ""}">${
      PV.worst ? `<p class="pv-flag">Worst case (made up)</p>` : ""}${svg}</div>
    <div class="boardfoot">
      <div id="pvread" class="pv-read" aria-live="polite"></div>
      <div class="pv-row">${key}${g.about ? `<span class="pv-about" title="${esc(g.about)}">${esc(capFirst(g.about))}</span>` : ""}
        <button type="button" class="v2-btn is-small pv-worst" data-pvworst
          aria-pressed="${PV.worst}">Worst case (made up)</button></div>
    </div>`;
  // A selection that no longer exists on this board (the worst case toggled off, say)
  // is dropped rather than shown as somebody who is not there.
  if (PVS.sel && PVS.sel.ref && !F.byRef.has(PVS.sel.ref)) PVS.sel = null;
  PVS.hover = null;
  pvPaint();
  if (typeof mapPaint === "function") mapPaint();
  // The heading is clamped to two lines on a phone (a three-line place name cost the
  // board 60px of a 520px screen); the whole name stays a tap or a hover away.
  const hn = $("#board-name");
  if (hn) hn.title = hn.textContent;

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
  function pathOf(edges) {
    return edges.map(([x1, y1, x2, y2]) => `M${x1 * CELL} ${y1 * CELL}L${x2 * CELL} ${y2 * CELL}`).join("");
  }
  function edgePath(edges, cls) {
    return edges.length ? `<path class="${cls}" d="${pathOf(edges)}"/>` : "";
  }
}

const capFirst = t => String(t).charAt(0).toUpperCase() + String(t).slice(1);

// The hatch both views share: --alarm, thin, at 45 degrees.
const PV_HATCH = `<pattern id="pv-hatch" width="4" height="4" patternUnits="userSpaceOnUse"
  patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="#b0483c"
  stroke-width="1.1" stroke-opacity=".7"></line></pattern>`;

// --- the readout and the highlight ---------------------------------------------------
// Both views write data-ref on every part of a body and data-sq on every square that can
// be moved to, so one function lights both. It changes classes and one text box: nothing
// is redrawn, nothing moves, nothing under the pointer shifts.
function pvTarget(el) {
  const t = el && el.closest && el.closest("[data-ref], [data-sq]");
  if (!t || !$("#mapwrap").contains(t)) return null;
  if (t.dataset.ref) return { ref: t.dataset.ref };
  return { sq: t.dataset.sq.split(",").map(Number) };
}
function pvPaint() {
  const F = PVS.F, box = $("#pvread");
  if (!F || !box) return;
  const t = PVS.hover || PVS.sel;
  document.querySelectorAll("#mapwrap .is-sel, #mapwrap .is-warn").forEach(e =>
    e.classList.remove("is-sel", "is-warn"));
  if (!t) { box.innerHTML = PV.idle(F); return; }
  if (t.ref) {
    const a = F.byRef.get(t.ref);
    if (!a) { box.innerHTML = PV.idle(F); return; }
    document.querySelectorAll(`#mapwrap [data-ref="${CSS.escape(t.ref)}"]`).forEach(e => e.classList.add("is-sel"));
    box.innerHTML = PV.forActor(F, a);
    return;
  }
  const k = `${t.sq[0]},${t.sq[1]}`;
  document.querySelectorAll(`#mapwrap [data-sq^="${k}"]`).forEach(e => {
    if (e.dataset.sq.split(",").slice(0, 2).join(",") === k) e.classList.add("is-sel");
  });
  // Ring who would take the swing: the attacker made plain, which is what Into the
  // Breach's outside testers needed and its developers did not.
  for (const ref of (F.provokes[k] || []))
    document.querySelectorAll(`#mapwrap [data-ref="${CSS.escape(ref)}"]`).forEach(e => e.classList.add("is-warn"));
  box.innerHTML = PV.forSquare(F, t.sq);
}

(function () {
  const fine = matchMedia("(hover: hover) and (pointer: fine)");
  const same = (a, b) => a && b && (a.ref ? a.ref === b.ref : !b.ref && a.sq[0] === b.sq[0] && a.sq[1] === b.sq[1]);
  document.addEventListener("pointerover", e => {
    if (!fine.matches || e.pointerType === "touch") return;
    const t = pvTarget(e.target);
    if (same(t, PVS.hover)) return;
    PVS.hover = t; pvPaint();
  });
  document.addEventListener("pointerleave", () => { PVS.hover = null; pvPaint(); });
  document.addEventListener("click", e => {
    if (e.target.closest("[data-pvworst]")) {
      PV.worst = !PV.worst; PVS.sel = null; renderMap(STATE); return;
    }
    if (!e.target.closest("#mapwrap .boardview")) return;
    const t = pvTarget(e.target);
    // A second tap on the same thing lets it go; a tap on bare ground clears.
    PVS.sel = same(t, PVS.sel) ? null : t;
    PVS.hover = null;
    pvPaint();
  });
  document.addEventListener("focusin", e => {
    // Keyboard focus only. A tap focuses the token too, and selecting on that focus made
    // the click that follows read as a second tap and let go at once.
    if (!e.target.matches || !e.target.matches(":focus-visible")) return;
    const t = pvTarget(e.target);
    if (t) { PVS.sel = t; pvPaint(); }
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && PVS.sel) { PVS.sel = null; pvPaint(); }
    if ((e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest("#mapwrap [data-ref]")) {
      e.preventDefault();
    }
  });
  document.addEventListener("toggle", e => {
    if (e.target.classList && e.target.classList.contains("pv-key")) PVS.keyOpen = e.target.open;
  }, true);
})();

// --- play/static/js/table/16-tab-map.js, lines 38-80 (MAPV, mapShowingPlaces, mapPaint) ---
const MAPV = {
  places: false,
  sel: null,
  said: "",
  walk: null,
  k: 1,
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
