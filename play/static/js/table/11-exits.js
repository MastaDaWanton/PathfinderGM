// The play table, part 11 (the ways on, I6). A classic script like the rest, loaded
// after 10-spells.js and sharing the one global scope.
//
// The owner, 2026-09-29: "give the choices based on entrances, what areas are connected
// to where i am." The row above the input lists `scene.exits`, which the server rebuilds
// from the engine's own place graph every state (play/exits.py): next door, the ground
// outside from a way out, and the roads from their heads. Nothing here decides where a
// place is or whether it can be reached; the page only draws what the engine said.
//
// A click sends "I go to <name>." with a place attachment, and the engine moves the party
// there directly (play/views.py `_take_the_exit`). A journey spends days, so the first
// click only asks: a confirm line opens under the row, and "Set out" (or the same button
// again) sends it. A way the rules would refuse stays in the row, shut, with the rules'
// own sentence shown while it is pointed at or focused, because hiding the gate is how a
// wanted player learns the watch is there by walking into it.
//
// The owner's motion rule: nothing here animates. The reason line and the confirm line
// open BELOW the buttons, so nothing moves under the pointer that opened them.

const EXIT_GROUPS = [["next_door", "Next door"], ["outside", "Outside"], ["road", "Roads"]];
let EXIT_CONFIRM = null;          // the journey waiting for its second click, by id

// "a few minutes' walk" reads as "a few minutes" in a row that is all walking.
function exitTime(words) {
  return String(words || "").replace(/(?:'s|') walk$/, "");
}

function exitNorm(text) {
  return String(text || "").toLowerCase().replace(/[.!]+$/, "")
    .replace(/^the\s+/, "").replace(/\s+/g, " ").trim();
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

function renderExits(s) {
  const box = document.getElementById("exits");
  if (!box) return;
  const scene = (s && s.scene) || {};
  const exits = scene.exits || [];
  dropDuplicateSuggestions(exits);
  if (!exits.length || s.awaiting || s.ended) {
    box.hidden = true; box.innerHTML = ""; EXIT_CONFIRM = null;
    return;
  }
  if (EXIT_CONFIRM && !exits.some(e => e.id === EXIT_CONFIRM && e.journey && !e.blocked)) {
    EXIT_CONFIRM = null;
  }
  const groups = EXIT_GROUPS.map(([key, label]) => {
    const mine = exits.filter(e => e.group === key);
    if (!mine.length) return "";
    return `<div class="ex-group" role="group" aria-labelledby="ex-g-${key}">
      <span class="ex-label" id="ex-g-${key}">${label}</span><div class="ex-list">${mine.map(e => {
        const shut = !!e.blocked;
        const time = exitTime(e.time_words);
        return `<button type="button" class="exitbtn${shut ? " shut" : ""}${
          EXIT_CONFIRM === e.id ? " asking" : ""}" data-exit="${esc(e.id)}"${
          shut ? ` aria-disabled="true" data-why="${esc(e.blocked)}"` : ""}${
          e.journey ? ` aria-expanded="${EXIT_CONFIRM === e.id}" aria-controls="exits-confirm"` : ""
        }><span class="ex-name">${esc(e.name)}</span>${
          time ? `<span class="ex-time"><span class="ex-sep" aria-hidden="true"> · </span>${
            esc(time)}</span>` : ""}${
          shut ? `<span class="vh"> (shut)</span>` : ""}</button>`;
      }).join("")}</div></div>`;
  }).join("");
  const asking = exits.find(e => e.id === EXIT_CONFIRM);
  box.innerHTML = groups
    + `<div class="ex-why" id="exits-why" aria-live="polite"></div>`
    + (asking ? `<div class="ex-confirm" id="exits-confirm" role="group"
          aria-label="Confirm the journey">
        <span>${esc(asking.name)}: ${esc(asking.time_words)}. The days pass on the
        road.</span>
        <button type="button" class="exitgo" data-exitgo="${esc(asking.id)}">Set out</button>
        <button type="button" class="exitgo quiet" data-exitcancel>Not now</button>
      </div>` : "");
  box.hidden = false;
}

function exitWhy(btn) {
  const line = document.getElementById("exits-why");
  if (line) line.textContent = btn && btn.dataset.why ? btn.dataset.why : "";
}

function goToExit(id, confirmed) {
  const e = ((STATE && STATE.scene && STATE.scene.exits) || []).find(x => x.id === id);
  if (!e || e.blocked) return;
  const place = { kind: "place", id: e.id };
  if (confirmed) place.confirmed = true;
  EXIT_CONFIRM = null;
  // The input and any spell chip are left as they are: the move is its own turn.
  takeTurn({ text: `I go to ${e.name}.`, attachments: [place] }, false);
}

document.addEventListener("click", e => {
  const btn = e.target.closest && e.target.closest("#exits .exitbtn");
  if (btn) {
    const id = btn.dataset.exit;
    if (btn.getAttribute("aria-disabled") === "true") { exitWhy(btn); return; }
    const x = ((STATE.scene || {}).exits || []).find(v => v.id === id);
    if (x && x.journey && EXIT_CONFIRM !== id) {
      EXIT_CONFIRM = id;
      renderExits(STATE);
      const go = document.querySelector("#exits [data-exitgo]");
      if (go) go.focus();
      return;
    }
    goToExit(id, !!(x && x.journey));
    return;
  }
  const go = e.target.closest && e.target.closest("#exits [data-exitgo]");
  if (go) { goToExit(go.dataset.exitgo, true); return; }
  if (e.target.closest && e.target.closest("#exits [data-exitcancel]")) {
    const was = EXIT_CONFIRM;
    EXIT_CONFIRM = null;
    renderExits(STATE);
    const back = was && document.querySelector(`#exits [data-exit="${CSS.escape(was)}"]`);
    if (back) back.focus();
  }
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
document.addEventListener("keydown", e => {
  if (e.key !== "Escape" || !EXIT_CONFIRM) return;
  if (!(e.target.closest && e.target.closest("#exits"))) return;
  const was = EXIT_CONFIRM;
  EXIT_CONFIRM = null;
  renderExits(STATE);
  const back = document.querySelector(`#exits [data-exit="${CSS.escape(was)}"]`);
  if (back) back.focus();
});

onRender(s => renderExits(s));
