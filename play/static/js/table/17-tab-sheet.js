// The play table, part 17 (the Sheet tab, and the sheet panel the other tabs borrow).
// Classic script, sharing one global scope.
//
// The table rebuild, stage 2 (docs/table-rebuild-inventory.md): the Sheet, Equipment,
// Spells and Journal tabs are each one page of the sheet, drawn by 05-sheet.js into one
// element, #sheetpanel, which is carried into whichever of those tabs is open. The Sheet
// tab's page is the approved design's column of framed cards, Combat first, in the centre
// column between the two sides; Equipment, Spells and Journal take the whole page.
//
// One element carried rather than four copies, because everything that acts on the sheet
// (Prepare and its kept scroll, a spell's details, the drink button, taking a level, the
// gender prompt) finds it by `#sheetbody`, and four bodies would be four places for the
// next fix to miss one.

// Where the panel goes while each tab is open.
const SHEET_HOMES = { sheet: "sheetmore", equipment: "mode-equipment",
                      spells: "mode-spells", journal: "mode-journal" };

function sheetInto(tab) {
  const panel = document.getElementById("sheetpanel");
  const home = document.getElementById(SHEET_HOMES[tab]);
  if (panel && home && panel.parentElement !== home) home.appendChild(panel);
  SHEET_TAB = tab;
  // The page opens at its top: on a phone the Sheet tab is one scroll, who first, as the
  // design lays it out, and a stage left scrolled from the last visit opened mid-sheet.
  // The panel's "?" shows the open tab's tips (js/tutorials.js).
  const help = document.querySelector('#sheetnote [data-tut-help]');
  if (help) help.dataset.tutHelp = "tab." + tab;
  Promise.resolve(openSheet()).then(() => {
    const stage = document.getElementById("stage");
    if (tab === "sheet" && stage && window.matchMedia("(max-width: 760px)").matches) stage.scrollTop = 0;
    // The tab's first-time card, once its page is drawn; and on the Sheet, the level's own
    // card when one is ready to take or its choices are owed.
    if (!window.Tutorials || SHEET_TAB !== tab) return;
    Tutorials.arrive("tab." + tab, { entered: true });
    const xp = STATE && STATE.pc && STATE.pc.xp;
    if (tab === "sheet" && ((xp && xp.ready) || document.getElementById("lvpicks"))) {
      Tutorials.arrive("tab.levelup", { entered: true });
    }
  });
}
if (window.Tutorials) {
  ["sheet", "equipment", "spells", "journal"].forEach(t => Tutorials.reach("tab." + t, () => Shell.show(t)));
  Tutorials.reach("tab.levelup", () => Shell.show("sheet"));
}

function sheetOutOf() {
  sheetAway();
}

Shell.tab("sheet", {
  enter() {
    sheetInto("sheet");
    magicRead();
  },
  leave() { sheetOutOf("sheet"); },
});

// --- Magic carried (docs/enchanting-ui-plan.md §6.6, lane U5) ------------------------------
// The Sheet tab's card for the things in the pack with a magic layer: each one's section
// as the Equipment tab draws it (49-enchant-ledger.js `itemSection`, one renderer) with its
// Identify button in it. Added after each draw of the Sheet's cards, after Defence, the way
// 21 adds the herbarium, because 05-sheet.js draws the page and this file does not own it;
// a pack with no magic, or a page without 49, adds no card at all. The cards and the
// Identify handler are 18-tab-equipment.js's (`EQ_MAGIC`, `magicIdentify`), so the two
// tabs cannot disagree about an item.
function magicCardHtml() {
  const L = window.EnchantLedger;
  const list = Object.values(EQ_MAGIC || {}).sort((a, b) => String(a.name).localeCompare(String(b.name)));
  if (!L || !list.length) return "";
  return sheetCard("sh-magic", "Magic carried", `<ul class="el-magic-list">${list.map(it => `<li>
      <b>${esc(it.name)}</b>${L.itemSection(it.card, { key: it.key, name: it.name, button: true,
        busy: !!EQ_MAGIC_BUSY, msg: EQ_MAGIC_SAY[it.key] || "" })}</li>`).join("")}</ul>`, "sh-magic");
}

function magicCardDraw() {
  if (SHEET_TAB !== "sheet") return;
  const cards = document.querySelector("#sheetbody .sheetcards");
  if (!cards) return;
  const old = document.getElementById("sh-magic");
  const html = magicCardHtml();
  const was = old && old.closest("section");
  if (!html) { if (was) was.remove(); return; }
  const host = document.createElement("div");
  host.innerHTML = html;
  const card = host.firstElementChild;
  if (was) { was.replaceWith(card); return; }
  const defence = cards.children[1];
  if (defence) defence.insertAdjacentElement("afterend", card);
  else cards.appendChild(card);
}

async function magicRead() {
  if (!window.EnchantLedger) return;
  EQ_MAGIC = await window.EnchantLedger.items();
  magicCardDraw();
}

(function watchTheSheet() {
  const body = document.getElementById("sheetbody");
  if (!body || typeof MutationObserver !== "function") return;
  new MutationObserver(() => { if (!document.getElementById("sh-magic")) magicCardDraw(); })
    .observe(body, { childList: true });
})();
