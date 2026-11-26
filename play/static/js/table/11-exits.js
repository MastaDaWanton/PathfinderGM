// The play table, part 11 (the ways on, I6). A classic script like the rest, loaded
// after 10-spells.js and sharing the one global scope.
//
// The owner, 2026-09-29: "give the choices based on entrances, what areas are connected
// to where i am." The row above the input lists `scene.exits`, which the server rebuilds
// from the engine's own place graph every state (play/exits.py): next door, the ground
// outside from a way out, and the roads from their heads. Nothing here decides where a
// place is or whether it can be reached; the page only draws what the engine said.
//
// A click ATTACHES the place, as a spell is attached, and Say sends it (the owner, the
// same day: "when you click a next door button it should attach like a spell does and
// then apply when you send"). Until then a click sent "I go to <name>." at once, and a
// journey or any way out of a fight opened a confirm line under the row that a second
// click answered. The chip is that confirmation now: attaching is the first step and Say
// the second, so the confirm line went, and what it told the player stays visible as the
// line held under the chip (10-spells.js `drawAttachments`): a journey's days, and what
// a withdraw costs. The chip lives in 10-spells.js's one slot, so a place replaces a
// spell and a spell a place, and the chip's ✕, the two-press Backspace and Esc are the
// spell chip's own. Words written beside it say how, and what else is done before or
// after the move; the server reads the order (gm/sequence.py).
//
// A way the rules would refuse stays in the row, shut, with the rules' own sentence shown
// while it is pointed at or focused, because hiding the gate is how a wanted player
// learns the watch is there by walking into it.
//
// In a fight (G3 leftovers, 2026-09-29) the row stays, because running is a choice a
// player is entitled to, but it stops looking like a stroll. Every open way is marked
// "withdraw", and its chip is a Withdraw chip whose line says what that costs. Leaving
// mid-fight is PF1e's withdraw (CRB p.188), and the engine rolls it
// (`reactions.provoked_by_withdraw`): a foe you can see who threatens only the square you
// start in gets no swing, while one whose reach covers your way out, or one you cannot
// see, still strikes. The page reads `scene.in_encounter` and says so; it does not work
// out who threatens whom, because a page that answered it would be a second rulebook.
//
// The owner's motion rule: nothing here animates, and nothing opens in the row any more:
// the reason line opens BELOW the buttons, and the chip is drawn in the say form under
// the row, so nothing moves under the pointer that pressed it.

const EXIT_GROUPS = [["next_door", "Next door"], ["outside", "Outside"], ["road", "Roads"]];

// What leaving the fight costs. The strike comes first and the exemption last, because on
// a wide desktop the chip's line sits beside the pen's actions and shows two lines of it
// (table.html, the motion rule; the whole sentence is its title): cut there, it still
// says the thing that hurts.
const WITHDRAW_LINE = "Leaving the fight is a withdraw: a foe whose reach covers your way "
  + "out still strikes, and so does one you cannot see; one beside you that you can see "
  + "gets no swing.";

// "a few minutes' walk" reads as "a few minutes" in a row that is all walking.
function exitTime(words) {
  return String(words || "").replace(/(?:'s|') walk$/, "");
}

function upFirst(text) {
  const t = String(text || "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function exitNorm(text) {
  return String(text || "").toLowerCase().replace(/[.!]+$/, "")
    .replace(/^the\s+/, "").replace(/\s+/g, " ").trim();
}

// The chip a way makes: its kind word and the line held under it.
function exitChip(e, fighting) {
  // A passage's words are the engine's own (play/exits.py `_days_aboard`): its days pass
  // aboard, never "on the road" (measured live 2026-11-13 on a sea crossing's chip).
  // Inland, the road to the harbour comes first ("... on foot to Scrapden, then ...").
  const aboard = /\b(?:at sea|on the river)\b/.test(String(e.time_words || ""));
  const road = /\b(?:on foot|riding) to\b/.test(String(e.time_words || ""));
  const where = aboard && road ? "on the road, then aboard" : aboard ? "aboard" : "on the road";
  const days = e.journey ? `${upFirst(e.time_words)}; the days pass ${where}.` : "";
  if (fighting) {
    return { id: e.id, name: e.name, journey: !!e.journey, label: "Withdraw",
             note: days ? `${WITHDRAW_LINE} ${days}` : WITHDRAW_LINE };
  }
  return { id: e.id, name: e.name, journey: !!e.journey,
           label: e.journey ? "Journey" : "Go", note: days };
}

function attachedExitId() {
  const c = typeof attachedChip === "function" ? attachedChip() : null;
  return c && c.kind === "place" ? c.id : null;
}

// A suggestion that is nothing but a move to one of the exits is the row's job now, so
// it is dropped rather than offered twice. Only a BARE move: "Walk to the market and ask
// after the smith" is more than a move and stays.
const BARE_MOVE = /^(?:i\s+)?(?:go|walk|head|return|wander|stroll|step|travel|make\s+(?:my|your)\s+way|set\s+out)\s+(?:back\s+)?(?:(?:over|down|up|out|across|on)\s+)?(?:to|into|toward|towards|for)\s+(.+?)\s*[.!]?$/i;

function dropDuplicateSuggestions(exits) {
  const box = document.getElementById("suggestions");
  if (!box || !exits.length) return;
  const names = new Set(exits.map(e => exitNorm(e.name)));
  box.querySelectorAll(".sugg").forEach(chip => {
    const m = BARE_MOVE.exec(chip.textContent.trim());
    if (m && names.has(exitNorm(m[1]))) chip.remove();
  });
  // `:empty` hides the row only when nothing at all is left in it.
  if (!box.querySelector(".sugg")) box.innerHTML = "";
}

// A far place (item 9, 2026-09-30): not a way on from here, but one the chart walks to
// through places you have been (`scene.places_found`, the node's `walk`), whose first
// leg is an open way on. Map's Walk there attaches it as ONE chip and the engine walks
// every hop in one turn (play/views.py `_read_place` takes it by the same rule,
// `places_found.walk_to`). Returned as a way the chip can be made from, or null.
function farWay(s, id) {
  const scene = (s && s.scene) || {};
  const pf = scene.places_found;
  const node = pf && Array.isArray(pf.nodes) ? pf.nodes.find(n => n.id === id) : null;
  const legs = node && node.walk && node.walk.legs;
  if (!legs || !legs.length) return null;
  const first = (scene.exits || []).find(x => x.id === legs[0].to);
  if (!first || first.blocked) return null;
  return { id: node.id, name: node.name, journey: false, time_words: "", legs: legs.length };
}

// A place chip follows the state it was attached in: a fight that began makes it a
// Withdraw chip, one that ended makes it a walk again, and a way that shut or is no
// longer a way from here takes the chip off with a sentence saying so. Only while the
// row is shown: a roll owed hides the row and says nothing about the ways.
function refreshPlaceChip(exits, fighting, s) {
  const c = typeof attachedChip === "function" ? attachedChip() : null;
  if (!c || c.kind !== "place") return;
  const e = exits.find(x => x.id === c.id) || (s ? farWay(s, c.id) : null);
  if (!e || e.blocked) {
    removeAttachment({ announce: false });
    spellSay(e ? `${c.name} is shut: ${e.blocked}` : `${c.name} is no longer a way on from here.`);
    return;
  }
  const fresh = exitChip(e, fighting);
  if (fresh.label !== c.label || fresh.note !== c.note) {
    Object.assign(c, fresh);
    drawAttachments();
  }
}

function renderExits(s) {
  const box = document.getElementById("exits");
  if (!box) return;
  const scene = (s && s.scene) || {};
  const exits = scene.exits || [];
  const fighting = !!scene.in_encounter;
  dropDuplicateSuggestions(exits);
  if (!exits.length || s.awaiting || s.ended) {
    box.hidden = true; box.innerHTML = "";
    return;
  }
  refreshPlaceChip(exits, fighting, s);
  const pressed = attachedExitId();
  box.classList.toggle("fighting", fighting);
  const groups = EXIT_GROUPS.map(([key, label]) => {
    const mine = exits.filter(e => e.group === key);
    if (!mine.length) return "";
    return `<div class="ex-group" role="group" aria-labelledby="ex-g-${key}">
      <span class="ex-label" id="ex-g-${key}">${label}</span><div class="ex-list">${mine.map(e => {
        const shut = !!e.blocked;
        const time = exitTime(e.time_words);
        const risky = fighting && !shut;
        const on = !shut && pressed === e.id;
        return `<button type="button" class="exitbtn v2-btn${shut ? " shut" : ""}${
          risky ? " risky" : ""}${on ? " asking" : ""}" data-exit="${esc(e.id)}"${
          shut ? ` aria-disabled="true" data-why="${esc(e.blocked)}"`
               : ` aria-pressed="${on}"`}><span class="ex-name">${esc(e.name)}</span>${
          time ? `<span class="ex-time"><span class="ex-sep" aria-hidden="true"> · </span>${
            esc(time)}</span>` : ""}${
          risky ? `<span class="ex-risk" aria-hidden="true">withdraw</span><span class="vh">
            (leaving the fight is a withdraw: foes whose reach covers the way out still
            strike)</span>` : ""}${
          shut ? `<span class="vh"> (shut)</span>` : ""}</button>`;
      }).join("")}</div></div>`;
  }).join("");
  box.innerHTML = groups + `<div class="ex-why" id="exits-why" aria-live="polite"></div>`;
  box.hidden = false;
}

// The pressed state follows the chip without redrawing the row (10-spells.js calls this
// whenever the chip changes), so focus stays on the button that was pressed.
function reflectExitChip() {
  const id = attachedExitId();
  document.querySelectorAll("#exits .exitbtn[aria-pressed]").forEach(b => {
    const on = b.dataset.exit === id;
    b.setAttribute("aria-pressed", String(on));
    b.classList.toggle("asking", on);
  });
}

function exitWhy(btn) {
  const line = document.getElementById("exits-why");
  if (line) line.textContent = btn && btn.dataset.why ? btn.dataset.why : "";
}

// A click attaches the way, or takes it back when it is the one attached. Nothing is sent.
function toggleExit(id) {
  const scene = (STATE && STATE.scene) || {};
  const e = (scene.exits || []).find(x => x.id === id);
  if (!e || e.blocked) return;
  if (attachedExitId() === id) { removeAttachment(); return; }
  attachPlace(exitChip(e, !!scene.in_encounter));
}

document.addEventListener("click", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn");
  if (!btn) return;
  if (btn.getAttribute("aria-disabled") === "true") { exitWhy(btn); return; }
  // The door folds first (its focus goes back to Ways on), then the box takes focus,
  // where the player writes how they go or presses Say.
  closePenPop("wayspop");
  toggleExit(btn.dataset.exit);
  const input = document.getElementById("input");
  if (input && input.focus && penOpen("wayspop") === false) input.focus({ preventScroll: true });
});

// The reason for a shut way, as a visible line while it is pointed at or focused.
document.addEventListener("mouseover", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn.shut");
  if (btn) exitWhy(btn);
});
document.addEventListener("mouseout", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn.shut");
  if (btn && !btn.contains(e.relatedTarget) && document.activeElement !== btn) exitWhy(null);
});
document.addEventListener("focusin", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn");
  if (btn) exitWhy(btn.classList.contains("shut") ? btn : null);
});
document.addEventListener("focusout", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn.shut");
  const to = e.relatedTarget;
  if (btn && !(to && to.closest && to.closest("#exits .exitbtn.shut"))) exitWhy(null);
});

// On a desktop the chip's line shares the pen's action line and is held to its height
// (table.html, the motion rule), so a long place line is cut at two lines there. The
// whole sentence stays on it as its title (and in the chip's description for a screen
// reader, 10's `aria-describedby`); 10 draws the chip, so the title is added when it does.
(function titleThePlaceLine() {
  const box = document.getElementById("attachments");
  if (!box || typeof MutationObserver === "undefined") return;
  new MutationObserver(() => {
    const note = document.getElementById("att-note");
    if (note && note.title !== note.textContent) note.title = note.textContent;
  }).observe(box, { childList: true });
})();

// The berths a harbourmaster offers while the player talks with them (play/views.py
// `_passage_offer`). Measured live 2026-11-13: "I ask the master for passage to
// Mirabalos, pay the fare and go aboard" was read as talk and booked nothing. These are
// the exits row's own passage rows, so a click attaches the same journey chip
// (`toggleExit`) and Say books it; the page decides nothing about who sells or for what.
function renderPassageOffer(s) {
  const box = document.getElementById("passage-offer");
  if (!box) return;
  const offer = ((s && s.scene) || {}).passage_offer || {};
  const rows = offer.rows || [];
  if (!rows.length || s.awaiting || s.ended) { box.innerHTML = ""; return; }
  const pressed = attachedExitId();
  box.innerHTML = rows.map(e => `<button type="button" class="passbtn v2-btn" data-tut="sea-way"
      data-passage="${esc(e.id)}" aria-pressed="${pressed === e.id}">Book passage to ${
      esc(e.name)} · ${esc(e.time_words)}</button>`).join("");
  if (window.Tutorials) Tutorials.arrive("map.sea");   // the sea's first card (16-tab-map.js)
}

document.addEventListener("click", e => {
  const btn = e.target.closest && e.target.closest("#passage-offer .passbtn");
  if (!btn) return;
  toggleExit(btn.dataset.passage);
  document.querySelectorAll("#passage-offer .passbtn").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.passage === attachedExitId())));
});

// --- the pen's two doors (2026-11-25) --------------------------------------------------
// The owner: "the bar where we are typing has become very crowded. lets organize and hide
// the locations and other buttons so that it feels clean again." Measured on their dungeon
// save at 1400x950: the desk above the pen held 836px of controls in a 283px box, eleven
// of them ways out. The ways on now sit behind Ways on (n), and Craft action, Spells and
// the abilities behind More, each one labelled click from the box
// (docs/research/2026-11-25-clean-composer.md). The rows inside are the same rows, drawn
// by the same code; only where they live changed.

const penPop = id => document.getElementById(id);
// true / false for a popover door, null where there is none (the node tests' page).
function penOpen(id) {
  const p = penPop(id);
  return p && p.matches ? p.matches(":popover-open") : null;
}
function closePenPop(id) {
  if (penOpen(id)) penPop(id).hidePopover();
}

// A control inside a closed door cannot take focus; its door can. Used wherever focus
// goes back to Craft action or Spells after a panel or a bench closes.
function visibleOr(el) {
  if (!el || !el.getClientRects || el.getClientRects().length) return el;
  const pop = el.closest && el.closest(".penpop");
  const door = pop && document.querySelector(`[popovertarget="${pop.id}"]`);
  return door && door.getClientRects().length ? door : document.getElementById("input");
}

// Above its door, where the eye already is, right edges together; below only when there is
// more room there. Measured before it opens (`beforetoggle`), so it never paints in the
// UA's centre first: the width is the CSS one, given here, not read from the box.
const PEN_POP_WIDTH = { wayspop: 560, morepop: 420, "cb-declpop": 540 };
// Declare opens above its whole row, not its door: the combat bar's actions wrap, and above a
// door on the second line it covered Strike and Full attack (tools/table_hit_test.js at
// 1024x700, 2026-11-26). The row's top is cut to the desk's scroll box it may be scrolled in.
const PEN_POP_ABOVE = { "cb-declpop": ".cb-acts" };
function placePenPop(pop) {
  const door = document.querySelector(`[popovertarget="${pop.id}"]`);
  if (!door) return;
  const r = door.getBoundingClientRect();
  const row = PEN_POP_ABOVE[pop.id] && door.closest(PEN_POP_ABOVE[pop.id]);
  const box = row && row.parentElement && row.parentElement.closest(".choices");
  const top = row ? Math.max(row.getBoundingClientRect().top,
                             box ? box.getBoundingClientRect().top : 0) : r.top;
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const w = Math.min(PEN_POP_WIDTH[pop.id] || 420, vw - 24);
  pop.style.width = `${w}px`;
  pop.style.left = `${Math.round(Math.max(12, Math.min(r.right - w, vw - w - 12)))}px`;
  pop.style.right = "auto";
  const above = top - 16, below = vh - r.bottom - 16;
  if (above >= 220 || above >= below) {
    pop.style.top = "auto";
    pop.style.bottom = `${Math.round(vh - top + 8)}px`;
    pop.style.maxHeight = `${Math.round(Math.max(140, Math.min(480, above)))}px`;
  } else {
    pop.style.bottom = "auto";
    pop.style.top = `${Math.round(r.bottom + 8)}px`;
    pop.style.maxHeight = `${Math.round(Math.max(140, Math.min(480, below)))}px`;
  }
}

// The door shows only when something is behind it, and says how many ways there are, so a
// player knows there is somewhere to go without opening it. In a fight it wears the alarm
// border, because every way behind it is a withdraw.
function renderWaysDoor(s) {
  const door = document.getElementById("waysbtn");
  const box = document.getElementById("exits");
  if (!door || !box || !box.querySelectorAll) return;
  const n = box.hidden ? 0 : box.querySelectorAll(".exitbtn").length;
  door.hidden = !n;
  const count = document.getElementById("ways-n");
  if (count) count.textContent = n ? `(${n})` : "";
  door.classList.toggle("risky", !!(((s && s.scene) || {}).in_encounter) && n > 0);
  if (!n) closePenPop("wayspop");
}

// More is never a one-item menu (Discord's complaint, Stream's rule; the critic pass on the
// research): with no spells and no abilities, Craft action stands in More's place as a
// plain button, and goes back inside when there is something to keep it company.
function fitMore() {
  const more = document.getElementById("morebtn");
  const craft = document.getElementById("craftaction");
  const home = document.getElementById("pp-craft-g");
  if (!more || !craft || !home) return;
  const spells = document.getElementById("spellbtn");
  const magic = document.getElementById("pp-magic-g");
  if (magic && spells) magic.hidden = spells.hidden;
  const abilities = document.getElementById("abilities");
  const company = (spells && !spells.hidden) || !!(abilities && abilities.children.length);
  if (company) {
    if (craft.parentElement !== home) home.append(craft);
    more.hidden = false;
  } else {
    if (craft.parentElement === home) more.before(craft);
    more.hidden = true;
    closePenPop("morepop");
  }
}

// The combat bar's Declare door (2026-11-26) is the same kind of door, drawn by
// 04-combat-and-turns.js `renderDeclDoor`, so it is wired and placed here with the pen's.
const PEN_POPS = ["wayspop", "morepop", "cb-declpop"];

(function wirePenDoors() {
  for (const id of PEN_POPS) {
    const pop = penPop(id);
    if (!pop || !pop.addEventListener) continue;
    if (typeof pop.showPopover !== "function") {
      // No popover in this browser: the rows stand inline as they did, and the doors go.
      pop.removeAttribute("popover");
      pop.classList.add("inline");
      const door = document.querySelector(`[popovertarget="${id}"]`);
      if (door) door.remove();
      // Declare's band goes back under the actions row, where it stood before its door.
      const row = pop.closest && pop.closest(".cb-acts");
      if (row) row.after(pop);
      continue;
    }
    pop.addEventListener("beforetoggle", e => { if (e.newState === "open") placePenPop(pop); });
  }
  // A choice in More acts and the tray folds, before the action's own listener (on the
  // document) runs: the spell picker then opens against More (10-spells.js `visibleOr`).
  const more = penPop("morepop");
  if (more && more.addEventListener) {
    more.addEventListener("click", e => {
      if (e.target.closest && e.target.closest("button")) closePenPop("morepop");
    });
  }
  window.addEventListener("resize", () => {
    for (const id of PEN_POPS) if (penOpen(id)) placePenPop(penPop(id));
  });
})();

onRender(s => renderExits(s));
onRender(s => renderPassageOffer(s));
onRender(s => renderWaysDoor(s));
onRender(() => fitMore());
