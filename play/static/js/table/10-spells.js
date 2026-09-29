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

const SPELLS = { anchor: null, sheet: null, chips: [], armed: false, chose: false,
                 downOpen: false };
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
function currentAttachments() { return SPELLS.chips.map(c => ({ ...c })); }

function drawAttachments() {
  const box = document.getElementById("attachments");
  const input = document.getElementById("input");
  if (!box) return;
  const c = SPELLS.chips[0];
  if (!c) {
    box.innerHTML = "";
    box.hidden = true;
    if (input) input.placeholder = INPUT_PLACEHOLDER;
    return;
  }
  // The remove button names what it removes ("Remove Burning Hands"), and its name is not
  // part of the chip's own: Gutenberg #82042 fixed chips that read "Burning Hands Remove".
  box.innerHTML = `<span class="chip att${SPELLS.armed ? " armed" : ""}" role="group"
      data-kind="spell" data-id="${esc(c.id)}" aria-label="Spell: ${esc(c.name)}"><span
      class="chip-kind" aria-hidden="true">Spell</span><span class="chip-label"
      aria-hidden="true">${esc(c.name)}</span><button type="button" class="chip-x"
      aria-label="Remove ${esc(c.name)}" title="Remove ${esc(c.name)}">✕</button></span>`;
  box.hidden = false;
  // Short enough to be read whole in the phone's box; "or just press Say" is in the
  // sentence the status region speaks when the chip is attached.
  if (input) input.placeholder = `What do you do with ${c.name}?`;
}

function attachSpell(spell) {
  if (!spell || !spell.id) return;
  const was = SPELLS.chips[0];
  SPELLS.chips = [{ kind: "spell", id: String(spell.id), name: String(spell.name || spell.id) }];
  SPELLS.armed = false;
  drawAttachments();
  const name = SPELLS.chips[0].name;
  spellSay(was && was.id !== spell.id
    ? `${name} attached in place of ${was.name}. Write what you do with it, or press Say.`
    : `${name} attached. Write what you do with it, or press Say.`);
}

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
    if (SPELLS.armed && !["Shift", "Control", "Alt", "Meta"].includes(e.key)) {
      SPELLS.armed = false;
      drawAttachments();
    }
    return;
  }
  if (e.target.closest && e.target.closest("#attachments .chip-x")
      && (e.key === "Delete" || e.key === "Backspace")) {
    e.preventDefault();
    removeAttachment();
    $("#input").focus();
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
      // counted below the list rather than printed as forty greyed rows.
      if (!k.prepared) { unprepared++; continue; }
    } else if (k.level > 0 && (!slot || slot.left <= 0)) {
      why = `no slot left at level ${k.level}`;
    }
    rows.push({ id: k.id, name: k.name, level: k.level, line: k.line || "", why });
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
    const pips = lvl > 0 && slot ? `<span class="sp-pips" aria-hidden="true">${
      Array.from({ length: slot.max }, (_, i) => `<i${i < slot.left ? ` class="on"` : ""}></i>`)
        .join("")}</span><span class="sp-left">${slot.left} of ${slot.max} left</span>` : "";
    return `<div class="sp-level" data-level="${lvl}">
      <div class="sp-levelhead"><span>${lvl === 0 ? "Cantrips" : `Level ${lvl}`}</span>${pips}</div>
      ${rows.filter(r => r.level === lvl).map(r => `<button type="button" class="sp-spell"
          data-spell="${esc(r.id)}" data-name="${esc(r.name)}"${r.why ? " disabled" : ""}${
          r.line ? ` title="${esc(r.line)}"` : ""}><span class="sp-name">${esc(r.name)}</span>${
          r.why ? `<span class="sp-why">${esc(r.why)}</span>` : ""}</button>`).join("")}
    </div>`;
  }).join("");
  const rest = unprepared ? `<p class="sp-note">${unprepared} more in your book ${
    unprepared === 1 ? "is" : "are"} not prepared today.</p>${openTab}` : "";
  return `${head}${find}${body}${rest}`;
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
    if (SPELLS.anchor && document.contains(SPELLS.anchor)) SPELLS.anchor.focus({ preventScroll: true });
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
    if (wasOpen) closeSpellPicker(); else openSpellPicker(opener);
    return;
  }
  const pick = t.closest("#spellpop .sp-spell");
  if (pick && !pick.disabled) {
    SPELLS.chose = true;
    attachSpell({ id: pick.dataset.spell, name: pick.dataset.name });
    closeSpellPicker();
    $("#input").focus();
    return;
  }
  if (t.closest("#spellpop [data-spells-tab]")) {
    SPELLS.chose = true;
    closeSpellPicker();
    SHEET_TAB = "spells";
    openSheet();
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
  const q = find.value.trim().toLowerCase();
  // Hidden in place rather than redrawn, so the caret and the focus stay in the box.
  spellPop().querySelectorAll(".sp-level").forEach(level => {
    let any = false;
    level.querySelectorAll(".sp-spell").forEach(b => {
      const hit = !q || b.dataset.name.toLowerCase().includes(q);
      b.hidden = !hit;
      any = any || hit;
    });
    level.hidden = !any;
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
    if (SPELLS.chips.length) clearAttachments();
  }
});
