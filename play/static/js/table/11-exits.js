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

// What leaving the fight costs, in the words the confirm line used to say it.
const WITHDRAW_LINE = "Leaving the fight is a withdraw: a foe beside you that you can see "
  + "gets no swing, but one whose reach covers your way out still strikes, and so does "
  + "one you cannot see.";

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
  const days = e.journey ? `${upFirst(e.time_words)}; the days pass on the road.` : "";
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

// A place chip follows the state it was attached in: a fight that began makes it a
// Withdraw chip, one that ended makes it a walk again, and a way that shut or is no
// longer a way from here takes the chip off with a sentence saying so. Only while the
// row is shown: a roll owed hides the row and says nothing about the ways.
function refreshPlaceChip(exits, fighting) {
  const c = typeof attachedChip === "function" ? attachedChip() : null;
  if (!c || c.kind !== "place") return;
  const e = exits.find(x => x.id === c.id);
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
  refreshPlaceChip(exits, fighting);
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
  toggleExit(btn.dataset.exit);
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

onRender(s => renderExits(s));
