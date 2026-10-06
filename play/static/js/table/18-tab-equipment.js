// The play table, part 18 (the Equipment tab). Classic script, sharing one global scope.
//
// The approved design's Equipment page (the mock README, "What changed in the second
// pass", points 1 and 2), drawn by 05-sheet.js's `pageEquipment` from the server's one
// list of what is carried (play/views.py `_carried`): the shelves down the side in the
// trade window's scheme, the list A to Z with every name written out, Worn and wielded
// with a slot that filters the list to what fits it. Wield, Put away, Wear, Take off and
// Use are answered by the engine's own doors (Take off and Put away since 2026-09-30, the
// `take_off` op and a wield of the fists); a row the rules cannot act on says why in its
// own note. Drop is not offered, because the rules do not have it yet, and "Go to Trade"
// is where new things come from (the owner's ruling: in play you buy at a counter and
// equip what you carry).

Shell.tab("equipment", {
  enter() {
    // A reply belongs to the act that drew it; a later visit starts with the line empty.
    EQ_SAY = "";
    EQ_SAY_BAD = false;
    EQ_BEFORE = null;
    sheetInto("equipment");
    eqMagicRead();
  },
  leave() { sheetOutOf("equipment"); },
});

// --- The item card's magic section (docs/enchanting-ui-plan.md §6.6, lane U5) -------------
// A carried thing with a magic layer says, under its facts, what is KNOWN of its magic: the
// aura before it is identified, what it was made to do after, its powers' uses left today,
// FLAWED (never which curse) for a flawed binding, and the curse's words only once known.
// And an Identify button beside its other acts, which rolls on the mat and answers in words
// with the DC and the roll (once per item per day, the server's rule).
//
// 05-sheet.js draws the page and this file does not own it, so the section is added after
// each draw, as 21 adds the herbarium (an observer on #sheetbody's children: `eqRedraw`
// replaces them on every act). The cards are the enchanting bench's own (`/api/enchant/
// state`, each shelf vessel's `card`, rules/enchanter.item_card), read when the tab opens
// and after an Identify; 49-enchant-ledger.js renders them, looked up at call time because
// it loads after this file. A page without 49 draws no section and no button.
let EQ_MAGIC = {};          // shelf key -> {key, name, card}
let EQ_MAGIC_SAY = {};      // shelf key -> the last Identify answer, said in the row
let EQ_MAGIC_BUSY = "";

function eqMagicDraw() {
  const L = window.EnchantLedger;
  if (!L || SHEET_TAB !== "equipment") return;
  for (const row of document.querySelectorAll("#sheetbody .eqrow[data-eqid]")) {
    if (row.querySelector(".el-item")) continue;
    const name = (row.querySelector(".eqname b") || {}).textContent || "";
    const it = L.itemFor(EQ_MAGIC, row.dataset.eqid, name);
    if (!it) continue;
    const host = row.querySelector(".eqname");
    if (!host) continue;
    // No answer line in the row: this page writes it once, in the line it keeps (`EQ_SAY`).
    host.insertAdjacentHTML("beforeend", L.itemSection(it.card, { key: it.key, name: it.name }));
    // Identify sits with the row's other acts (Wield, Wear), one label for the intent.
    const acts = row.querySelector(".eqacts");
    if (acts && L.canIdentify(it.card)) {
      acts.insertAdjacentHTML("beforeend", `<button type="button" class="v2-btn is-small"
        data-el-identify="${esc(it.key)}" data-el-name="${esc(it.name)}"${EQ_MAGIC_BUSY ? " disabled" : ""}
        aria-label="Identify ${esc(it.name)}">Identify</button>`);
    }
  }
}

async function eqMagicRead() {
  const L = window.EnchantLedger;
  if (!L) return;
  EQ_MAGIC = await L.items();
  if (SHEET_TAB !== "equipment") return;
  document.querySelectorAll("#sheetbody .el-item").forEach(x => x.remove());
  document.querySelectorAll("#sheetbody .eqacts [data-el-identify]").forEach(x => x.remove());
  eqMagicDraw();
}

(function watchTheEquipment() {
  const body = document.getElementById("sheetbody");
  if (!body || typeof MutationObserver !== "function") return;
  new MutationObserver(() => eqMagicDraw()).observe(body, { childList: true });
})();

// One handler for both tabs' Identify (this one and the Sheet tab's Magic carried card,
// 17-tab-sheet.js): the answer goes in the item's own section and in the page's line.
async function magicIdentify(btn) {
  const L = window.EnchantLedger;
  if (!L || EQ_MAGIC_BUSY) return;
  const key = btn.dataset.elIdentify, name = btn.dataset.elName || "";
  EQ_MAGIC_BUSY = key;
  btn.disabled = true;
  let said = "", bad = false;
  try {
    const r = await L.identify(key, { name });
    said = r.said;
    if (r.card) EQ_MAGIC[key] = { key, name: r.name || name, card: r.card };
    // Time passed (a minute) and the transcript has the line: the table reads its state.
    if (typeof render === "function" && typeof getState === "function") render(await getState());
  } catch (err) {
    said = err.message || String(err);
    bad = true;
  } finally { EQ_MAGIC_BUSY = ""; }
  EQ_MAGIC_SAY[key] = said;
  if (SHEET_TAB === "equipment") {
    EQ_SAY = said;
    EQ_SAY_BAD = bad;
    eqRedraw({ id: btn.closest(".eqrow") ? btn.closest(".eqrow").dataset.eqid : "" });
  } else if (typeof magicCardDraw === "function") {
    magicCardDraw();
  }
}

document.addEventListener("click", e => {
  const b = e.target.closest("#sheetbody [data-el-identify]");
  if (b && !b.disabled) magicIdentify(b);
});
