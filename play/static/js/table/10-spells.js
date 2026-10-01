// The play table, part 10 of 10 (spells). Classic script, sharing one global scope with
// 01-09.
//
// A spell is attached to a turn, not sent (playtest items 11 and 21.1; docs/design-f-ui.md
// §4.4). The Spells button beside Trade, the combat bar's Cast… (owner Q47) and the
// Spells tab's Cast button all open or feed one thing: a chip before the input. The
// player writes what they do with it ("into the tree tops"), or nothing and presses Say,
// and `/api/say` carries `attachments: [{kind: "spell", id}]`. No target picker (owner
// Q46): the player says where it goes, in words.
//
// - The picker is a popover (Esc and a click outside close it, Baseline since 2025), with
//   a class-toggle fallback for a browser that predates it. Its list is `GET /api/sheet`'s
//   own `spells` block, the Spells tab's source, so the two cannot disagree: cantrips
//   first, then each level with its slot pips and the count in words, and a spell that
//   cannot be cast greyed with the reason as visible text — a tooltip does not exist on a
//   touch screen.
// - One spell a turn: a new one replaces the old and says so. Backspace at the start of
//   the box takes two presses, the first selecting the chip: Vuetify #3069's chips were
//   eaten by the Backspace meant for a typed letter.
// - A refusal the player can fix (HTTP 422, docs/fix-interfaces.md §2.6) keeps the words
//   and the chip, says why in the engine's own sentence, and offers the fix as a button.
// - Shown by `spellcasting.kind` (owner Q49), never by `pc.castable`, which offers a
//   prepared caster's whole book when nothing is prepared (fix-interfaces §1.7 F1).

const SPELLS = { anchor: null, returnTo: null, sheet: null, chips: [], armed: false,
                 chose: false, downOpen: false };
const HAS_POPOVER = typeof HTMLElement !== "undefined"
  && typeof HTMLElement.prototype.showPopover === "function";
const INPUT_PLACEHOLDER = ($("#input") && $("#input").placeholder) || "What do you do?";

const spellPop = () => document.getElementById("spellpop");

function spellSay(text) {
  const status = document.getElementById("saystatus");
  if (!status) return;
  // Emptied first, so the same sentence twice is still spoken twice.
  status.textContent = "";
  setTimeout(() => { status.textContent = text; }, 30);
}

// --- the chip ------------------------------------------------------------------------------
// The aim grammar, the server's own (`rules/areas.AIM_PATTERN`, §2.7), held here only so a
// chip never carries an aim the door would 400 on. Where a spell goes is normally the
// player's words in the box — "into the tree tops", "above my head", "at the man" — sent
// as the turn's text beside the chip and grounded by the server against the scene
// (`areas.aim_from_words`: the people present first, then the things here, then the
// directions). That reader lives once, on the server; a second copy here would drift.
// A chip carries an `aim` of its own only when a caller already holds one in the grammar
// (`attachSpellChip(id, name, aim)`).
const AIM_RE = /^(ref:[A-Za-z0-9_-]+|self|dir:(n|ne|e|se|s|sw|w|nw|up|down)|point:\d+,\d+(,\d+)?|object:[^\n]{1,60})$/;

// The chip slot is one thing whatever rides in it: a spell (Lane F) or, since
// 2026-09-29, a place from the "From here" row (11-exits.js). The owner: "when you click
// a next door button it should attach like a spell does and then apply when you send".
// So the remove button, the two-press Backspace, Esc, the status sentences and the 422
// that keeps words and chip are the spell chip's own, not a copy of them. A chip is
// `{kind, id, name}`, plus `aim` for a spell and `label`, `note` and `journey` for a
// place: its kind word ("Go", "Journey", "Withdraw") and the line held under it.
function chipKind(c) {
  return c.kind === "spell" ? "Spell" : (c.label || "Go");
}

function currentAttachments() {
  return SPELLS.chips.map(c => {
    const out = { kind: c.kind, id: c.id, name: c.name };
    if (c.aim && AIM_RE.test(c.aim)) out.aim = c.aim;
    if (c.kind === "place" && c.journey) out.confirmed = true;
    return out;
  });
}

// The body a turn's attachments go in: kind, id, and the aim when the chip has one. The
// name is the server's to look up (it refuses a spell the character lacks). A journey
// chip carries `confirmed`: attaching it and pressing Say is the confirmation the server
// asks of days on the road, where the row used to ask with a line of its own.
function attachmentsForSay() {
  return currentAttachments().map(a => {
    const out = { kind: a.kind, id: a.id };
    if (a.aim) out.aim = a.aim;
    if (a.confirmed) out.confirmed = true;
    return out;
  });
}

function drawAttachments() {
  const box = document.getElementById("attachments");
  const input = document.getElementById("input");
  if (!box) return;
  const c = SPELLS.chips[0];
  if (typeof reflectExitChip === "function") reflectExitChip();
  if (!c) {
    box.innerHTML = "";
    box.hidden = true;
    if (input) input.placeholder = INPUT_PLACEHOLDER;
    return;
  }
  const kind = chipKind(c);
  // The remove button names what it removes ("Remove Burning Hands"), and its name is not
  // part of the chip's own: Gutenberg #82042 fixed chips that read "Burning Hands Remove".
  // A place's line (the days a journey spends, what a withdraw costs) is held visibly
  // under the chip: it was the row's confirm line, and a sentence a player must weigh
  // before pressing Say cannot live only in a screen reader's ear.
  box.innerHTML = `<span class="chip att${SPELLS.armed ? " armed" : ""}${
      c.kind === "place" && c.label === "Withdraw" ? " risky" : ""}" role="group"
      data-kind="${esc(c.kind)}" data-id="${esc(c.id)}" aria-label="${esc(kind)}: ${
      esc(c.name)}"${c.note ? ` aria-describedby="att-note"` : ""}><span
      class="chip-kind" aria-hidden="true">${esc(kind)}</span><span class="chip-label"
      aria-hidden="true">${esc(c.name)}</span><button type="button" class="chip-x"
      aria-label="Remove ${esc(c.name)}" title="Remove ${esc(c.name)}">✕</button></span>${
      c.note ? `<span class="att-note" id="att-note">${esc(c.note)}</span>` : ""}`;
  box.hidden = false;
  // Short enough to be read whole in the phone's box; "or just press Say" is in the
  // sentence the status region speaks when the chip is attached.
  if (input) {
    input.placeholder = c.kind === "place" ? `How do you go to ${c.name}? Or just press Say.`
                                           : `What do you do with ${c.name}?`;
  }
}

// One attachment a turn: a new chip of either kind replaces the old one and says so.
function attachChip(chip, sentence) {
  if (!chip || !chip.id) return;
  const was = SPELLS.chips[0];
  SPELLS.chips = [chip];
  SPELLS.armed = false;
  drawAttachments();
  const replaced = was && !(was.kind === chip.kind && was.id === chip.id);
  spellSay(replaced ? `${chip.name} attached in place of ${was.name}. ${sentence.again}`
                    : `${chip.name} attached. ${sentence.first}`);
}

function attachSpell(spell) {
  if (!spell || !spell.id) return;
  const chip = { kind: "spell", id: String(spell.id), name: String(spell.name || spell.id) };
  if (spell.aim && AIM_RE.test(String(spell.aim))) chip.aim = String(spell.aim);
  // Where it goes is said in words (owner Q46: no target picker), so the sentence says
  // so: "into the tree tops" was the line that could not be aimed (item 21.2).
  attachChip(chip, { again: "Write where it goes, or press Say.",
                     first: "Write where it goes, at whom or at what, or press Say." });
}

// The exits row's door into the slot (11-exits.js). `place` is `{id, name, label, note,
// journey}`, built there from the engine's own `scene.exits`.
function attachPlace(place) {
  if (!place || !place.id) return;
  const chip = { kind: "place", id: String(place.id), name: String(place.name || place.id),
                 label: place.label || "Go", note: place.note || "",
                 journey: !!place.journey };
  attachChip(chip, { again: "Write how you go and what else you do, or press Say.",
                     first: "Write how you go and what else you do, or press Say." });
}

// A stable door for other parts of the table (the Spells tab's cards, I5) to attach a
// spell as a chip without knowing this file's internals. `aim` is optional and must be in
// the server's grammar; anything else is dropped rather than sent to be refused.
window.attachSpellChip = function attachSpellChip(id, name, aim, range) {
  return chooseSpell({ id, name, aim, range });
};

// Every door that chooses a spell comes through here: the picker's rows, the Spells
// tab's Cast (02-state.js) and `attachSpellChip`. In a fight the spell is a step of the
// combat panel's turn (04's `stageCastInTurn`), committed with the move by Commit turn;
// out of one it is the chip for Say, as before. Measured 2026-10-01, the owner in a
// fight: both buttons attached the chip, the cast left through /api/say as a turn of its
// own, "so i cannot move and cast in the same turn". Returns "turn" or "chip", so the
// caller knows where the player's attention goes next.
function inAFight() {
  return !!(typeof STATE !== "undefined" && STATE && STATE.scene && STATE.scene.in_encounter);
}

function chooseSpell(spell) {
  if (!spell || !spell.id) return "";
  if (inAFight() && typeof stageCastInTurn === "function" && stageCastInTurn(spell)) {
    // A chip attached before the fight began is not this turn's spell any more: the one
    // just chosen is, and two spells in two places is the split this undoes.
    if (SPELLS.chips.some(c => c.kind === "spell")) clearAttachments();
    spellSay(`${spell.name || spell.id} is in this turn. Press Commit turn to cast it.`);
    return "turn";
  }
  attachSpell(spell);
  return "chip";
}

// Where focus goes once a spell is chosen: to Commit turn when it went into the turn,
// to the box when it went to Say.
function focusAfterChoosing(where) {
  const to = where === "turn" ? document.getElementById("cb-commit") : $("#input");
  if (to) to.focus();
}

function attachedChip() { return SPELLS.chips[0] || null; }

function removeAttachment({ announce = true } = {}) {
  const was = SPELLS.chips[0];
  SPELLS.chips = [];
  SPELLS.armed = false;
  drawAttachments();
  if (was && announce) spellSay(`${was.name} removed.`);
}

// Called by 04's `takeTurn` once a turn was taken, and only then: a refusal, a stale
// screen or a busy table keep both the words and the chip.
function clearAttachments() { removeAttachment({ announce: false }); }

// A turn that did some of the words and not the rest (play/views.py `_unfinished`): the
// rest is back in the pen, prefilled by 04, and the line says where the player is and
// what is not yet done, visibly and to a screen reader. The chain stopped the way a
// parser's does when a command in it fails (gm/sequence.py); nothing was dropped.
function showUnfinished(u) {
  if (!u || !u.line) return;
  const err = document.getElementById("err");
  if (err) {
    err.className = "hint";
    err.textContent = u.why ? `${u.line} ${u.why}` : u.line;
  }
  spellSay(u.line);
}

document.addEventListener("keydown", e => {
  if (!SPELLS.chips.length) return;
  const input = e.target.closest && e.target.closest("#input");
  if (input) {
    if (e.key === "Backspace" && input.selectionStart === 0 && input.selectionEnd === 0) {
      e.preventDefault();
      if (!SPELLS.armed) {
        SPELLS.armed = true;
        drawAttachments();
        spellSay(`Press Backspace again to remove ${SPELLS.chips[0].name}.`);
      } else {
        removeAttachment();
      }
      return;
    }
    // Esc takes back a chip the first Backspace selected, and nothing else: in the box
    // it is also the key a player presses to get out of a panel.
    if (SPELLS.armed && e.key === "Escape") {
      e.preventDefault();
      removeAttachment();
      return;
    }
    if (SPELLS.armed && !["Shift", "Control", "Alt", "Meta"].includes(e.key)) {
      SPELLS.armed = false;
      drawAttachments();
    }
    return;
  }
  const onChip = e.target.closest && e.target.closest("#attachments .chip-x");
  if (onChip && (e.key === "Delete" || e.key === "Backspace" || e.key === "Escape")) {
    e.preventDefault();
    removeAttachment();
    $("#input").focus();
    return;
  }
  // Esc from the exits row takes back the place it attached, as it used to close the
  // row's confirm line; focus stays on the way that was pressed.
  if (e.key === "Escape" && SPELLS.chips[0].kind === "place"
      && e.target.closest && e.target.closest("#exits")) {
    e.preventDefault();
    removeAttachment();
  }
});

document.addEventListener("click", e => {
  if (!e.target.closest("#attachments .chip-x")) return;
  removeAttachment();
  $("#input").focus();
});

// --- the picker ----------------------------------------------------------------------------
function spellPickerOpen() {
  const p = spellPop();
  if (!p) return false;
  return p.classList.contains("open") || (HAS_POPOVER && p.matches(":popover-open"));
}

function placeSpellPicker() {
  const p = spellPop(), a = SPELLS.anchor;
  if (!p || !a || !spellPickerOpen()) return;
  const r = a.getBoundingClientRect();
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const w = p.offsetWidth;
  const left = Math.max(12, Math.min(r.right - w, vw - w - 12));
  const above = r.top - 16, below = vh - r.bottom - 16;
  p.style.left = `${Math.round(left)}px`;
  p.style.right = "auto";
  // Above its button, where the eye already is; below only when there is more room there.
  if (above >= 220 || above >= below) {
    p.style.top = "auto";
    p.style.bottom = `${Math.round(vh - r.top + 8)}px`;
    p.style.maxHeight = `${Math.round(Math.max(140, Math.min(520, above)))}px`;
  } else {
    p.style.bottom = "auto";
    p.style.top = `${Math.round(r.bottom + 8)}px`;
    p.style.maxHeight = `${Math.round(Math.max(140, Math.min(520, below)))}px`;
  }
}

function spellNameFor(id) {
  const chip = SPELLS.chips.find(c => c.id === id);
  if (chip) return chip.name;
  const known = (((SPELLS.sheet || {}).spells || {}).known || []).find(k => k.id === id);
  if (known) return known.name;
  return String(id || "").replace(/-/g, " ").replace(/\b\w/g, ch => ch.toUpperCase());
}

// The rows the picker offers, from the sheet's own spells block.
function spellRows(sp) {
  const slots = new Map((sp.slots || []).map(s => [s.level, s]));
  const prepared = sp.kind === "prepared";
  const rows = [];
  let unprepared = 0;
  for (const k of sp.known || []) {
    if (k.missing || k.level === null || k.level === undefined) continue;
    const slot = slots.get(k.level);
    let why = "";
    if (prepared) {
      // A prepared caster casts what is in their head today; the rest of the book is
      // counted below the list rather than printed as forty greyed rows. Cantrips too:
      // a wizard "can prepare a number of cantrips… each day" and casts those at will
      // (AoN, Wizard). Until 2026-09-29 every cantrip in the book was offered here,
      // because the engine skipped the prepared check at level 0; it no longer does.
      if (!k.prepared) { unprepared++; continue; }
    } else if (k.level > 0 && (!slot || slot.left <= 0)) {
      why = `no slot left at level ${k.level}`;
    }
    rows.push({ id: k.id, name: k.name, level: k.level, line: k.line || "", why,
                range: k.range || "" });
  }
  return { rows, unprepared, slots };
}

function spellPickerHtml(sheet) {
  const sp = sheet && sheet.spells;
  const head = `<h2 class="sp-title">Spells</h2>`;
  if (!sp) return `${head}<p class="sp-note">${esc((sheet && sheet.identity && sheet.identity.name)
    || "You")} does not cast spells.</p>`;
  const { rows, unprepared, slots } = spellRows(sp);
  const openTab = `<button type="button" class="quiet sp-open" data-spells-tab>Open your
    spells</button>`;
  if (!rows.length) {
    return `${head}<p class="sp-note">${sp.kind === "prepared" ? "Nothing prepared today."
      : "No spells known yet."} Choose them in your spells.</p>${openTab}`;
  }
  const levels = [...new Set(rows.map(r => r.level))].sort((a, b) => a - b);
  const find = rows.length > 12 ? `<input type="search" class="findbox" id="spellpick-find"
      placeholder="Find a spell" aria-label="Find a spell" autocomplete="off">` : "";
  const body = levels.map(lvl => {
    const slot = slots.get(lvl);
    // Cantrips carry no pips: casting one spends nothing, so there is nothing to count.
    const pips = lvl === 0 ? `<span class="sp-left">at will</span>`
      : slot ? `<span class="sp-pips" aria-hidden="true">${
      Array.from({ length: slot.max }, (_, i) => `<i${i < slot.left ? ` class="on"` : ""}></i>`)
        .join("")}</span><span class="sp-left">${slot.left} of ${slot.max} left</span>` : "";
    return `<div class="sp-level" data-level="${lvl}">
      <div class="sp-levelhead"><span>${lvl === 0 ? "Cantrips" : `Level ${lvl}`}</span>${pips}</div>
      ${rows.filter(r => r.level === lvl).map(r => `<button type="button" class="sp-spell"
          data-spell="${esc(r.id)}" data-name="${esc(r.name)}" data-range="${
          esc(r.range)}"${r.why ? " disabled" : ""}${
          r.line ? ` title="${esc(r.line)}"` : ""}><span class="sp-name">${esc(r.name)}</span>${
          r.why ? `<span class="sp-why">${esc(r.why)}</span>` : ""}</button>`).join("")}
    </div>`;
  }).join("");
  const rest = unprepared ? `<p class="sp-note">${unprepared} more in your book ${
    unprepared === 1 ? "is" : "are"} not prepared today.</p>${openTab}` : "";
  // Said before the list, in a fight, so the player knows the press does not cast yet.
  const turn = inAFight() ? `<p class="sp-note">Chosen here, it joins this turn beside your
    move. Commit turn casts it.</p>` : "";
  return `${head}${turn}${find}${body}${rest}`;
}

async function fillSpellPicker() {
  const p = spellPop();
  if (!p) return;
  p.innerHTML = `<h2 class="sp-title">Spells</h2><p class="sp-note">Reading your spells…</p>`;
  placeSpellPicker();
  let sheet;
  try {
    const r = await fetch("/api/sheet", { cache: "no-store" });
    sheet = await readJSON(r);
    if (!r.ok) throw new Error(sheet.error || "Your spells could not be read.");
  } catch (err) {
    p.innerHTML = `<h2 class="sp-title">Spells</h2><p class="sp-note">${esc(err.message)}</p>`;
    placeSpellPicker();
    return;
  }
  SPELLS.sheet = sheet;
  if (!spellPickerOpen()) return;
  p.innerHTML = spellPickerHtml(sheet);
  placeSpellPicker();
  const first = p.querySelector("#spellpick-find") || p.querySelector(".sp-spell:not(:disabled)")
    || p.querySelector("[data-spells-tab]");
  if (first) first.focus({ preventScroll: true });
}

function markSpellAnchors(open) {
  for (const id of ["spellbtn", "cb-cast"]) {
    const b = document.getElementById(id);
    if (b) b.setAttribute("aria-expanded", String(open && SPELLS.anchor === b));
  }
}

function openSpellPicker(anchor) {
  const p = spellPop();
  if (!p) return;
  SPELLS.anchor = anchor || document.getElementById("spellbtn");
  SPELLS.returnTo = null;
  SPELLS.chose = false;
  if (HAS_POPOVER) { if (!p.matches(":popover-open")) p.showPopover(); }
  else p.classList.add("open");
  markSpellAnchors(true);
  fillSpellPicker();
}

function closeSpellPicker() {
  const p = spellPop();
  if (!p) return;
  if (HAS_POPOVER && p.matches(":popover-open")) p.hidePopover();
  if (p.classList.contains("open")) { p.classList.remove("open"); spellPickerClosed(); }
}

function spellPickerClosed() {
  markSpellAnchors(false);
  const p = spellPop();
  // Focus goes back to the button that opened it, unless a spell was chosen (then it is
  // in the box, where the player writes the rest) or the player has already moved on.
  if (!SPELLS.chose && p && (p.contains(document.activeElement)
                             || document.activeElement === document.body)) {
    const back = SPELLS.returnTo || SPELLS.anchor;
    if (back && document.contains(back)) back.focus({ preventScroll: true });
  }
}

(function wireSpellPop() {
  const p = spellPop();
  if (!p) return;
  if (HAS_POPOVER) {
    p.addEventListener("toggle", e => { if (e.newState === "closed") spellPickerClosed(); });
  }
  // The popover's own light dismiss runs on pointerdown, before the click: a press on the
  // button that opened it would shut it and then open it again. Noted here, so the click
  // below reads "it was open" and leaves it shut.
  document.addEventListener("pointerdown", e => {
    SPELLS.downOpen = !!(e.target.closest && e.target.closest("#spellbtn, #cb-cast"))
      && spellPickerOpen();
  }, true);
  window.addEventListener("resize", placeSpellPicker);
})();

document.addEventListener("click", e => {
  const t = e.target;
  const opener = t.closest("#spellbtn");
  if (opener) {
    const wasOpen = SPELLS.downOpen || spellPickerOpen();
    SPELLS.downOpen = false;
    if (wasOpen) { closeSpellPicker(); return; }
    // In a fight the Spells button is the panel's Cast… by another name: the picker
    // opens against the panel, so the spell is seen to land in the turn being built
    // there, and focus still comes back to the button that was pressed.
    const cast = document.getElementById("cb-cast");
    if (inAFight() && cast && cast.offsetParent !== null) {
      openSpellPicker(cast);
      SPELLS.returnTo = opener;
    } else {
      openSpellPicker(opener);
    }
    return;
  }
  const pick = t.closest("#spellpop .sp-spell");
  if (pick && !pick.disabled) {
    SPELLS.chose = true;
    const went = chooseSpell({ id: pick.dataset.spell, name: pick.dataset.name,
                               range: pick.dataset.range || "" });
    closeSpellPicker();
    focusAfterChoosing(went);
    return;
  }
  if (t.closest("#spellpop [data-spells-tab]")) {
    SPELLS.chose = true;
    closeSpellPicker();
    // The Spells tab since the table rebuild; the sheet's Spells page before it.
    if (typeof Shell === "object" && Shell) Shell.show("spells");
    else { SHEET_TAB = "spells"; openSheet(); }
    return;
  }
  // The fallback has no light dismiss of its own.
  if (!HAS_POPOVER && spellPickerOpen() && !t.closest("#spellpop")) closeSpellPicker();
});

// The combat bar's Cast… opens the same picker (owner Q47), not a second list of its own.
// 04 calls this; a press while it is open shuts it.
function castFromCombatBar(button) {
  const wasOpen = SPELLS.downOpen || (spellPickerOpen() && SPELLS.anchor === button);
  SPELLS.downOpen = false;
  if (wasOpen) { closeSpellPicker(); return; }
  if (typeof combatMenu === "function") combatMenu("");
  openSpellPicker(button);
}

document.addEventListener("input", e => {
  const find = e.target.closest && e.target.closest("#spellpick-find");
  if (!find) return;
  const q = find.value.trim().toLowerCase().replace(/\s+/g, " ");
  // Hidden in place rather than redrawn, so the caret and the focus stay in the box.
  //
  // By `style.display`, not the `hidden` attribute alone. Measured 2026-09-29: "burn"
  // still showed Magic Missile — the match was right and the row stayed on screen,
  // because `#spellpop .sp-spell { display: flex }` outranks the user-agent's
  // `[hidden] { display: none }`. A level with no match hid correctly (its rule sets no
  // display), which is why only rows sharing a level with a hit leaked through.
  //
  // And by the start of a word, so "mis" finds Magic Missile and "and" does not find
  // Burning Hands: a substring anywhere in a name is a loose filter over forty spells.
  const starts = name => q.split(" ").every(part =>
    name.split(/[\s'-]+/).some(w => w.startsWith(part)));
  spellPop().querySelectorAll(".sp-level").forEach(level => {
    let any = false;
    level.querySelectorAll(".sp-spell").forEach(b => {
      const hit = !q || starts(b.dataset.name.toLowerCase());
      b.hidden = !hit;
      b.style.display = hit ? "" : "none";
      any = any || hit;
    });
    level.hidden = !any;
    level.style.display = any ? "" : "none";
  });
});

document.addEventListener("keydown", e => {
  if (!spellPickerOpen()) return;
  const p = spellPop();
  if (!HAS_POPOVER && e.key === "Escape") { closeSpellPicker(); return; }
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  if (!p.contains(document.activeElement)) return;
  const items = [...p.querySelectorAll("#spellpick-find, .sp-spell:not(:disabled), [data-spells-tab]")]
    .filter(el => el.offsetParent !== null);
  const i = items.indexOf(document.activeElement);
  const to = items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length];
  if (to) { e.preventDefault(); to.focus(); }
});

// --- the refusal and its fix --------------------------------------------------------------
// §2.6's 422: `{"error", "refusal": {"text", "code", "fix"}}`. The words in the box and the
// chip stay; the sentence is the engine's; the fix is one press.
function showRefusal(refusal) {
  const err = document.getElementById("err");
  if (!err) return;
  const fix = (refusal && refusal.fix) || null;
  let button = "";
  if (fix && fix.kind === "prepare" && fix.spell) {
    button = `<button type="button" class="quiet errfix" data-fix="prepare"
      data-spell="${esc(fix.spell)}">Prepare ${esc(spellNameFor(fix.spell))}</button>`;
  } else if (fix && fix.kind === "go" && fix.place) {
    button = `<button type="button" class="quiet errfix" data-fix="go"
      data-place="${esc(fix.place)}">Go to ${esc(fix.place)}</button>`;
  }
  err.className = "hint";
  err.innerHTML = `<span class="errtext">${esc((refusal && refusal.text)
    || "That cannot be done as it stands.")}</span>${button}`;
}

document.addEventListener("click", async e => {
  const fix = e.target.closest("#err .errfix");
  if (!fix) return;
  fix.disabled = true;
  if (fix.dataset.fix === "go") {
    // The words and the chip stay in the box for the turn after this one.
    takeTurn({ text: `I go to ${fix.dataset.place}.` }, false);
    return;
  }
  if (fix.dataset.fix === "prepare") {
    const name = spellNameFor(fix.dataset.spell);
    try {
      await post("/api/spells/prepare", { action: "prepare", spell: fix.dataset.spell });
      render(await getState());
      const err = document.getElementById("err");
      err.className = "hint";
      err.textContent = `${name} is prepared. Press Say to cast it.`;
      $("#input").focus();
    } catch (err) {
      flash(err.message || String(err));
    }
  }
});

onRender(function spellsButton(s) {
  const btn = document.getElementById("spellbtn");
  if (!btn) return;
  const kind = (s && s.spellcasting && s.spellcasting.kind) || "";
  btn.hidden = !kind;
  if (!kind) {
    // Somebody who does not cast is playing now: nothing of the last caster's stays.
    if (spellPickerOpen()) closeSpellPicker();
    // A spell only: a place chip is anybody's.
    if (SPELLS.chips.some(c => c.kind === "spell")) clearAttachments();
  }
});
