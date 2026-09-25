// The play table, part 04 of 6 (combat and turns). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// --- the combat turn builder ---------------------------------------------------------
// One turn, built then committed: the server runs the ops in order through the same
// engine path as a spoken turn, and the NPCs answer through the machinery that already
// existed. Buttons for the mechanical; the say box for everything else.
const COMBAT = { target: null, move: null, standard: null, swift: null, frees: [] };

function actionKind(text) {
  const m = /^\s*(?:as an?|an?)?\s*(swift|free|immediate|move|standard|full[- ]round)\b/i
    .exec(text || "");
  return m ? m[1].toLowerCase().replace("full ", "full-") : "standard";
}

function renderCombat(s) {
  const bar = $("#combatbar");
  if (!bar) return;
  const on = s.scene && s.scene.in_encounter;
  bar.hidden = !on;
  if (!on) { COMBAT.target = COMBAT.move = COMBAT.standard = COMBAT.swift = null;
             COMBAT.frees = []; return; }

  $("#cb-round").textContent = `Round ${s.scene.round || 1}`;
  const up = s.scene.turn_ref === (s.pc && s.pc.ref || "pc");
  $("#cb-turn").textContent = up ? "your turn" :
    `waiting on ${(s.scene.initiative.find(i => i.up) || {}).name || "…"}`;

  const foes = (s.scene.actors || []).filter(a => !a.is_pc && a.hp > 0);
  if (COMBAT.target && !foes.some(f => f.ref === COMBAT.target)) COMBAT.target = null;
  if (!COMBAT.target && foes.length === 1) COMBAT.target = foes[0].ref;
  $("#cb-targets").innerHTML = foes.map(f =>
    `<span class="cb-target ${COMBAT.target === f.ref ? "on" : ""}" data-target="${
      esc(f.ref)}">${esc(f.name)}<small>${
      (f.conditions || []).join(", ") || (f.hp < f.hp_max ? "wounded" : "unhurt")
    }</small></span>`).join("")
    || `<span class="sub">Nobody left standing against you.</span>`;

  renderPlan();
}

function renderPlan() {
  const bits = [];
  if (COMBAT.move) bits.push(`<span class="cb-step" data-unplan="move"
    title="Remove">Move to ${COMBAT.move.join(",")}</span>`);
  if (COMBAT.standard) bits.push(`<span class="cb-step" data-unplan="standard"
    title="Remove">${esc(COMBAT.standard.label)}</span>`);
  if (COMBAT.swift) bits.push(`<span class="cb-step" data-unplan="swift"
    title="Remove">Swift: ${esc(COMBAT.swift)}</span>`);
  COMBAT.frees.forEach((f, i) => bits.push(`<span class="cb-step" data-unplan="free:${i}"
    title="Remove">Free: ${esc(f)}</span>`));
  $("#cb-plan").innerHTML = bits.join("");
}

function targetName() {
  const f = (STATE.scene.actors || []).find(a => a.ref === COMBAT.target);
  return f ? f.name : "the enemy";
}

function combatMenu(html) {
  const m = $("#cb-menu");
  m.hidden = !html;
  m.innerHTML = html || "";
}

async function commitTurn(endOnly) {
  const actions = [];
  const said = [];
  if (COMBAT.move) {
    actions.push({ op: "move", params: { zone: "near", square: COMBAT.move } });
    said.push(`move to (${COMBAT.move.join(",")})`);
  }
  if (COMBAT.standard) {
    actions.push(...COMBAT.standard.actions);
    said.push(COMBAT.standard.label.toLowerCase());
  }
  if (COMBAT.swift) {
    actions.push({ op: "use_ability",
                   params: { ability: COMBAT.swift }, target: COMBAT.target });
    said.push(`swift: ${COMBAT.swift}`);
  }
  for (const f of COMBAT.frees) {
    actions.push({ op: "use_ability", params: { ability: f }, target: COMBAT.target });
    said.push(`free: ${f}`);
  }
  busy(true);
  try {
    const d = await post("/api/combat/act", {
      actions: endOnly ? [] : actions,
      end_turn: true,
      label: endOnly ? "" : said.join("; ") || "",
    });
    COMBAT.move = COMBAT.standard = COMBAT.swift = null; COMBAT.frees = [];
    combatMenu("");
    render(d);
  } catch (e) { $("#err").textContent = e.message; }
  busy(false);
}

document.addEventListener("click", async e => {
  const t = e.target;
  const chip = t.closest(".cb-target");
  if (chip) { COMBAT.target = chip.dataset.target; renderCombat(STATE); return; }
  const un = t.closest("[data-unplan]");
  if (un) {
    const what = un.dataset.unplan;
    if (what === "move") COMBAT.move = null;
    else if (what === "standard") COMBAT.standard = null;
    else if (what === "swift") COMBAT.swift = null;
    else if (what.startsWith("free:")) COMBAT.frees.splice(Number(what.slice(5)), 1);
    renderPlan(); return;
  }
  const lvl = t.closest("[data-maplevel]");
  if (lvl) { MAP_LEVEL = Number(lvl.dataset.maplevel); renderMap(STATE); return; }
  const vw = t.closest("[data-mapview]");
  if (vw) { MAP_3D = vw.dataset.mapview === "3d"; renderMap(STATE); return; }
  const trn = t.closest("[data-mapturn]");
  if (trn) { MAP_TURN = (MAP_TURN + Number(trn.dataset.mapturn) + 4) % 4;
             renderMap(STATE); return; }
  const sq = t.closest("[data-sq]");
  if (sq && STATE.scene && STATE.scene.in_encounter) {
    COMBAT.move = sq.dataset.sq.split(",").map(Number);
    renderPlan(); return;
  }

  if (t.closest("#cb-strike")) {
    if (!COMBAT.target) { $("#err").textContent = "Pick a target first."; return; }
    // More than one weapon only while a toggle grants one (the armed punch, while
    // the armament is formed) — then the strike has to ask which.
    const arms = (STATE.attacks || {}).weapons || [];
    if (arms.length > 1) {
      combatMenu(arms.map(w => `<button data-strikeweapon="${esc(w)}">${esc(w)}
        </button>`).join("") + `<span class="cb-note">Which weapon?</span>`);
      return;
    }
    COMBAT.standard = { label: `Strike ${targetName()}`,
      actions: [{ op: "attack", target: COMBAT.target, params: {} }] };
    combatMenu(""); renderPlan(); return;
  }
  const sw = t.closest("[data-strikeweapon]");
  if (sw) {
    const w = sw.dataset.strikeweapon;
    COMBAT.standard = { label: `Strike ${targetName()} (${w})`,
      actions: [{ op: "attack", target: COMBAT.target, params: { weapon: w } }] };
    combatMenu(""); renderPlan(); return;
  }

  if (t.closest("#cb-fullatk")) {
    if (!COMBAT.target) { $("#err").textContent = "Pick a target first."; return; }
    const seq = (STATE.attacks || {}).sequence || [0];
    // A toggle is a free action whatever its text says — the armament and Blood Rage
    // sat in this list as "attacks", and picking one wasted a swing on something the
    // chips row below gives away for nothing.
    const abil = (STATE.abilities || []).filter(a =>
      !a.toggle && !["swift", "free", "immediate"].includes(actionKind(a.text)));
    const arms = (STATE.attacks || {}).weapons || [];
    const options = (i) => `<option value="">weapon (${seq[i] >= 0 ? "+" : ""}${
      seq[i]})</option>` + (arms.length > 1 ? arms.slice(1).map(w =>
      `<option value="w:${esc(w)}">${esc(w)} (${seq[i] >= 0 ? "+" : ""}${
      seq[i]})</option>`).join("") : "") + ((STATE.attacks || {}).replaceable ? abil.map(a =>
      `<option value="${esc(a.name)}">${esc(a.name)}</option>`).join("") : "");
    combatMenu(seq.map((p, i) =>
      `<div class="cb-slot"><label>attack ${i + 1}</label>
       <select data-slot="${i}">${options(i)}</select></div>`).join("") +
      `<button id="cb-fullok">Set full attack</button>
       <span class="cb-note">Blood Bond: any swing can be an ability instead —
       the weapon swings keep their own iterative penalties.</span>`);
    return;
  }
  if (t.closest("#cb-fullok")) {
    const slots = [...$("#cb-menu").querySelectorAll("select")].map(s => s.value);
    const actions = slots.map((v, i) => {
      if (!v) return { op: "attack", target: COMBAT.target, params: { iteration: i } };
      if (v.startsWith("w:")) return { op: "attack", target: COMBAT.target,
        params: { iteration: i, weapon: v.slice(2) } };
      return { op: "use_ability", params: { ability: v }, target: COMBAT.target };
    });
    const label = "Full attack: " + slots.map(v =>
      v ? (v.startsWith("w:") ? v.slice(2) : v) : "weapon").join(", ") +
      ` on ${targetName()}`;
    COMBAT.standard = { label, actions };
    combatMenu(""); renderPlan(); return;
  }

  const menuFor = (kinds, slot) => {
    // Toggles count as free here too, so the armament reaches the free menu and
    // stays out of the standard one.
    const list = (STATE.abilities || []).filter(a =>
      kinds.includes(a.toggle ? "free" : actionKind(a.text)));
    if (!list.length) { combatMenu(`<span class="cb-note">Nothing ${
      kinds[0]} to use.</span>`); return; }
    combatMenu(list.map(a => `<button data-pick="${slot}:${esc(a.name)}"
      title="${esc((a.text || "").slice(0, 200))}">${esc(a.name)}</button>`).join(""));
  };
  // Casting is a standard action like any other, and it was the one a spellcaster
  // could not reach: `cast` was missing from the panel's op list, so a wizard's whole
  // turn had to be typed and routed through the narrator. The spells offered are the
  // ones actually prepared, because a spell in the book and a spell in the head are
  // different things and the engine refuses the second question anyway.
  if (t.closest("#cb-cast")) {
    const spells = (STATE.pc && STATE.pc.castable) || [];
    if (!spells.length) { combatMenu(`<span class="cb-note">Nothing prepared.</span>`);
      return; }
    combatMenu(spells.map(sp => `<button data-pick="cast:${esc(sp.id || sp.name)}"
      title="${esc(sp.summary || sp.name || "")}">${esc(sp.name || sp.id)}${
        sp.left != null ? ` (${sp.left})` : ""}</button>`).join(""));
    return;
  }
  if (t.closest("#cb-ability")) { menuFor(["standard", "full-round", "move"], "standard"); return; }
  if (t.closest("#cb-swift")) { menuFor(["swift", "immediate"], "swift"); return; }
  if (t.closest("#cb-free")) { menuFor(["free"], "free"); return; }

  const pick = t.closest("[data-pick]");
  if (pick) {
    const [slot, ...rest] = pick.dataset.pick.split(":");
    const name = rest.join(":");
    if (slot === "cast") COMBAT.standard = { label: `Cast ${name}`,
      actions: [{ op: "cast", params: { spell: name }, target: COMBAT.target }] };
    else if (slot === "standard") COMBAT.standard = { label: `Use ${name}`,
      actions: [{ op: "use_ability", params: { ability: name },
                  target: COMBAT.target }] };
    else if (slot === "swift") COMBAT.swift = name;
    else COMBAT.frees.push(name);
    combatMenu(""); renderPlan(); return;
  }

  if (t.closest("#cb-clear")) {
    COMBAT.move = COMBAT.standard = COMBAT.swift = null; COMBAT.frees = [];
    combatMenu(""); renderPlan(); return;
  }
  if (t.closest("#cb-commit")) { commitTurn(false); return; }
  if (t.closest("#cb-end")) { commitTurn(true); return; }
});

async function sendRoll(face, shown) {
  $("#veil").classList.remove("on");

  // The number FIRST, on a request of its own.
  //
  // Reported 2026-09-16: "when dice are rolled the last die spins until a reply is sent
  // to the user. I would prefer that the dice land show the number it landed on and
  // then be able to be closed while the user waits." The whole of `/api/roll` used to
  // be awaited before the die could land, and the slow part of it is the narrator — so
  // the die span through the generation, and the LAST die of a turn span longest.
  //
  // `/api/roll/face` decides the face and mutates nothing, so an abandoned one costs
  // nothing. When the player rolled a real die themselves the face is already in hand
  // and there is nothing to ask.
  let landed = face;
  if (landed == null) {
    // A failure here is not worth showing anybody: it costs the early landing and
    // nothing else, because `/api/roll` rolls its own face when sent null — which is
    // exactly what this did before the split.
    try { landed = (await post("/api/roll/face", {})).face; } catch { landed = null; }
  }

  // Not awaited. `land` resolves when the player closes the mat, and the point of this
  // change is that they may close it whenever they like — before the reply, after it,
  // or not at all. Without the landing we keep the old order and land at the end.
  let closing = null;
  if (landed != null) {
    closing = Dice3D.land({
      title: shown.title, why: shown.why, die: shown.die,
      sides: shown.sides, lo: shown.lo, hi: shown.hi,
      result: landed, terms: shown.terms, note: shown.note,
    });
  }

  busy(true);
  let state = null;
  try { state = await post("/api/roll", { face: landed }); }
  catch (e) { $("#err").textContent = e.message; }
  finally { busy(false); }

  // Land the die on what the server rolled. Without this the main roll path asked,
  // played a decorative throw that ended on an arbitrary face, closed the mat, and
  // told the player the number in a table — reported 2026-09-09 as "the dice don't
  // land with the number facing the user", and they never did.
  if (closing == null) {
    if (state && state.rolled != null) {
      await Dice3D.land({
        title: shown.title, why: shown.why, die: shown.die,
        sides: shown.sides, lo: shown.lo, hi: shown.hi,
        result: state.rolled, terms: shown.terms, note: shown.note,
      });
    } else {
      Dice3D.close();
    }
  }
  // Drawn behind the mat rather than after it. The mat is an overlay, so a player who
  // is still reading the terms loses nothing, and one who already closed it is looking
  // at the page when the reply arrives instead of at a closed mat and a spinner.
  //
  // The exception is the next die. A turn can ask for another roll, and opening its
  // popup now would reset the mat the player is still reading — so the page is drawn
  // and that one part waits for them to close it.
  if (state && closing && state.awaiting) {
    render(state, true);
    await closing;
    showPopup(state.awaiting);
  } else if (state) {
    render(state);
  }
}

async function takeTurn(body, clearInput) {
  $("#err").textContent = "";
  $("#err").className = "";
  busy(true);
  try {
    const s = await post("/api/say", body);
    render(s);
    if (clearInput) $("#input").value = "";   // cleared only once the turn was taken
    if (s.ended) showDeath(s);
  }
  catch (err) {
    if (!err.handled) $("#err").textContent = err.message;
    if (err.hint) $("#err").className = "hint";
  }
  finally { busy(false); }
}

$("#sayform").onsubmit = e => {
  e.preventDefault();
  const text = $("#input").value.trim();
  if (text) takeTurn({text}, true);
};

// No `text` at all. The server knows what an empty continue means and writes the
// player's line itself, so nothing has to be typed and nothing invented on their behalf.
$("#carryon").onclick = () => takeTurn({carry_on: true}, false);

/* ---- The full character sheet -------------------------------------------------
   Section names are the Pathfinder Player Character Folio's own, so a player who
   knows the paper sheet knows which tab to reach for. Every number shows the terms
   that produced it — that itemisation is the whole point of the app, so the sheet is
   where it lives in full. */

let SHEET = null, SHEET_TAB = "defense";

