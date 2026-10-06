// The play table, part 21 (the Journal tab). Classic script, sharing one global scope.
//
// The approved design's Journal: the matters in play (the quest cards the engine keeps,
// their objectives and what has happened), what people said (the conversation log, read
// a person at a time; answering is Talk's), the places walked, and the character's
// history (2026-10-01, `/api/history`). Drawn by 05-sheet.js's `pageJournal`.

Shell.tab("journal", {
  enter() {
    // Read afresh each visit: what was said, and what happened, move on every turn.
    JOURNAL_LOG = null;
    JOURNAL_HISTORY = null;
    HERBARIUM = null;
    sheetInto("journal");
  },
  leave() { sheetOutOf("journal"); },
});

// --- The herbarium (docs/herbalism-ui-plan.md §6.6) ------------------------------------
// Every herb the character has met, read from `/api/herbarium`: what is known of each,
// how it was learned, and a dash for the rest. The server sends only what the character
// knows — an unknown property's text never reaches the page (rules/herbknowledge.py) —
// so nothing here can show a secret by mistake.
//
// Drawn beside History as its own card. 05-sheet.js's `pageJournal` draws the journal's
// cards and this file does not own it, so the card is added after each draw of the
// journal (an observer on the sheet body), the way `historyRead` fills its log after the
// draw. The list's id is "jr-herbarium-list", never "jr-herbarium": that is the card's
// heading id (`sheetCard` puts it on the h2), and the history card's first cut replaced
// its own heading by sharing one.
let HERBARIUM = null;              // the entries last read, or null while reading
let HERB_OPEN = "";                // the herb whose card is open
const HERB_CARDS = {};             // id -> the card last read
let HERB_UNKNOWN_FIRST = false;

function journalHerbarium() {
  return `<div class="jr-herb-tools">
      <button type="button" class="v2-btn is-small" data-herbsort
        aria-pressed="${HERB_UNKNOWN_FIRST}">Unknowns first</button>
    </div>
    <div id="jr-herbarium-list" role="list" aria-label="Herbs you have met">${herbariumRows()}</div>`;
}

function herbKnownLine(e) {
  return `${e.known} of ${e.total} known`;
}

function herbariumRows() {
  if (HERBARIUM === null) return `<p class="why">Reading the herbarium.</p>`;
  const rows = (HERBARIUM.entries || []).slice();
  if (!rows.length) return `<p class="why">No herbs yet. Forage or buy one and it appears here.</p>`;
  if (HERB_UNKNOWN_FIRST) {
    rows.sort((a, b) => ((b.total - b.known) - (a.total - a.known))
      || String(a.name).localeCompare(String(b.name)));
  }
  // A disclosure per herb: the heading holds the button (a heading inside a button is
  // not allowed), and the button takes the heading's own look.
  return `<ul class="plain matters twocol jr-herbs">${rows.map(e => `<li class="matter" role="listitem">
      <h3><button type="button" class="jr-herb-row" data-herb="${esc(e.id)}"
        aria-expanded="${HERB_OPEN === e.id}" aria-controls="jr-herb-card-${esc(e.id)}"
        style="all: unset; cursor: pointer; display: inline-flex; gap: 10px; align-items: center;">
        <span class="jr-herb-icon" data-part="${esc(e.part || "")}" aria-hidden="true"></span>${esc(e.name)}</button></h3>
      <p class="why">${esc([e.kind, herbKnownLine(e), (e.biomes || []).join(", "),
        e.carried ? `${e.carried} carried` : ""].filter(Boolean).join(" · "))}</p>
      <div id="jr-herb-card-${esc(e.id)}"${HERB_OPEN === e.id ? "" : " hidden"}>${
        HERB_OPEN === e.id ? herbCardBody(e.id) : ""}</div>
    </li>`).join("")}</ul>`;
}

function herbCardBody(id) {
  const card = HERB_CARDS[id];
  if (!card) return `<p class="why">Reading what you know.</p>`;
  if (card.error) return `<p class="why">${esc(card.error)}</p>`;
  const props = (card.properties || []).map(p => p.known
    ? `<li>${esc(p.text)}${p.drawback ? ` <span class="chip">harmful</span>` : ""}${
        p.how ? `<br><span class="why">${esc(p.how)}</span>` : ""}</li>`
    : `<li><span aria-hidden="true">–</span> <span class="why">unknown</span></li>`).join("");
  return `${card.danger_known ? `<p class="why">You know this is dangerous: ${esc(card.danger_known)}.</p>` : ""}
    <ul class="plain objectives">${props || `<li class="why">Nothing to know.</li>`}</ul>`;
}

// The engraved icon, when the bench's registry is loaded (lane D's `BenchIcons`); a herb
// with no icon simply has none, and the row reads the same.
function herbIcons(root) {
  if (!window.BenchIcons || typeof window.BenchIcons.el !== "function") return;
  for (const slot of root.querySelectorAll(".jr-herb-icon:empty")) {
    try {
      const el = window.BenchIcons.el(slot.dataset.part || "leaf");
      if (el) slot.appendChild(el);
    } catch (err) { /* an icon is decoration; a failure draws none */ }
  }
}

function herbariumDraw() {
  const box = document.getElementById("jr-herbarium-list");
  if (!box) return;
  box.innerHTML = herbariumRows();
  herbIcons(box);
}

async function herbariumRead() {
  try {
    HERBARIUM = await readJSON(await fetch("/api/herbarium", { cache: "no-store" }));
  } catch (err) {
    HERBARIUM = { entries: [] };
  }
  herbariumDraw();
}

async function herbCardRead(id) {
  try {
    HERB_CARDS[id] = await readJSON(await fetch(`/api/herb/${encodeURIComponent(id)}`,
                                                { cache: "no-store" }));
  } catch (err) {
    HERB_CARDS[id] = { error: err.message || String(err) };
  }
  if (HERB_OPEN === id) herbariumDraw();
}

// Two columns on a desktop and one when narrow (UI plan §6.6). `.twocol` alone fits as
// many 300px columns as it can — three at the journal's 1180px, measured in the running
// page — so the count is pinned here. Layout only: every colour is the journal's own.
function herbariumStyle() {
  if (document.getElementById("jr-herbarium-style")) return;
  const style = document.createElement("style");
  style.id = "jr-herbarium-style";
  style.textContent = `
    #jr-herbarium-list .jr-herbs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    @media (max-width: 900px) {
      #jr-herbarium-list .jr-herbs { grid-template-columns: minmax(0, 1fr); }
    }
    .jr-herb-tools { margin: 0 0 8px; }
    .jr-herb-icon:empty { display: none; }`;
  document.head.appendChild(style);
}

// Added after each draw of the journal, beside History, full width.
function herbariumMount() {
  herbariumStyle();
  const body = document.getElementById("sheetbody");
  const journal = body && body.querySelector(".journal");
  if (!journal || document.getElementById("jr-herbarium")) return;
  const host = document.createElement("div");
  host.innerHTML = sheetCard("jr-herbarium", "Herbarium", journalHerbarium(), "jr-herbarium");
  const card = host.firstElementChild;
  // Full width in the journal's grid, which names areas for its own cards only.
  card.style.gridColumn = "1 / -1";
  const history = document.getElementById("jr-history");
  const after = history && history.closest("section");
  if (after && after.parentElement === journal) after.insertAdjacentElement("beforebegin", card);
  else journal.appendChild(card);
  if (HERBARIUM === null) herbariumRead(); else herbariumDraw();
}

// --- The smith's ledger (docs/blacksmithing-ui-plan.md §6.7) -----------------------------
// Every material met, beside the herbarium: "3 of 7 known", an "Unknowns first" toggle,
// and each material's known lines. 44-forge-ledger.js draws it (`ForgeLedger.journal`,
// contracts §11) from `/api/forge/ledger`, the same renderer as the forge's ledger card,
// so the two cannot drift. 44 loads after this file, so it is looked up at mount time;
// a page without it draws no section rather than an empty card. The list's id is
// "jr-ledger-list", never the heading's "jr-ledger" (the history card's lesson above).
function ledgerMount() {
  const body = document.getElementById("sheetbody");
  const journal = body && body.querySelector(".journal");
  if (!journal || document.getElementById("jr-ledger")) return;
  if (!window.ForgeLedger || typeof window.ForgeLedger.journal !== "function") return;
  const host = document.createElement("div");
  host.innerHTML = sheetCard("jr-ledger", "Smith's ledger", `<div id="jr-ledger-list"></div>`, "jr-ledger");
  const card = host.firstElementChild;
  card.style.gridColumn = "1 / -1";
  const herbs = document.getElementById("jr-herbarium");
  const beside = herbs && herbs.closest("section");
  const history = document.getElementById("jr-history");
  const before = history && history.closest("section");
  if (beside && beside.parentElement === journal) beside.insertAdjacentElement("afterend", card);
  else if (before && before.parentElement === journal) before.insertAdjacentElement("beforebegin", card);
  else journal.appendChild(card);
  window.ForgeLedger.journal(document.getElementById("jr-ledger-list"));
}

// --- Essences and recipes (docs/enchanting-ui-plan.md §6.8) ------------------------------
// Every essence met or carried, what is known of each and how, "still unknown" counts as
// the server sends them, and the recipes known, beside the herbarium and the smith's
// ledger. 49-enchant-ledger.js draws it (`EnchantLedger.journal`, contracts §13) from
// `/api/enchant/ledger`, the same renderer as the bench's essence card. 49 loads after
// this file, so it is looked up at mount time; a page without it draws no section. The
// list's id is "jr-essences-list", never the heading's "jr-essences".
function essencesMount() {
  const body = document.getElementById("sheetbody");
  const journal = body && body.querySelector(".journal");
  if (!journal || document.getElementById("jr-essences")) return;
  if (!window.EnchantLedger || typeof window.EnchantLedger.journal !== "function") return;
  const host = document.createElement("div");
  host.innerHTML = sheetCard("jr-essences", "Essences and recipes", `<div id="jr-essences-list"></div>`, "jr-essences");
  const card = host.firstElementChild;
  card.style.gridColumn = "1 / -1";
  const smith = document.getElementById("jr-ledger");
  const herbs = document.getElementById("jr-herbarium");
  const beside = (smith && smith.closest("section")) || (herbs && herbs.closest("section"));
  const history = document.getElementById("jr-history");
  const before = history && history.closest("section");
  if (beside && beside.parentElement === journal) beside.insertAdjacentElement("afterend", card);
  else if (before && before.parentElement === journal) before.insertAdjacentElement("beforebegin", card);
  else journal.appendChild(card);
  window.EnchantLedger.journal(document.getElementById("jr-essences-list"));
}

(function watchTheJournal() {
  const body = document.getElementById("sheetbody");
  if (!body || typeof MutationObserver !== "function") return;
  new MutationObserver(() => { herbariumMount(); ledgerMount(); essencesMount(); }).observe(body, { childList: true });
})();

document.addEventListener("click", e => {
  const sort = e.target.closest("#sheetbody [data-herbsort]");
  if (sort) {
    HERB_UNKNOWN_FIRST = !HERB_UNKNOWN_FIRST;
    sort.setAttribute("aria-pressed", String(HERB_UNKNOWN_FIRST));
    herbariumDraw();
    return;
  }
  const row = e.target.closest("#sheetbody [data-herb]");
  if (!row) return;
  const id = row.dataset.herb;
  HERB_OPEN = HERB_OPEN === id ? "" : id;
  herbariumDraw();
  if (HERB_OPEN) herbCardRead(id);
});
