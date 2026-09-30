// The play table, part 17 (the Sheet tab, and the sheet panel the other tabs borrow).
// Classic script, sharing one global scope.
//
// Stage 1 of the rebuild carries today's full sheet (05-sheet.js, unchanged in what it
// draws) into the new frame: one element, #sheetpanel, carried into whichever tab is
// open and scoped to that tab's pages. The Sheet tab shows the character's pages, in the
// centre column between the two sides; Equipment (18), Spells (19) and Journal (21) take
// the whole page and show theirs. Each remembers the page it was on.
//
// Stage 2 replaces the Sheet's and Equipment's bodies with the approved design's own
// (the combat block, the Equipment page): each tab can then stop borrowing the panel
// without touching the others (docs/table-rebuild-inventory.md, "The seams").

// The sheet's pages each tab shows, by 05's TABS keys, in TABS' own order.
const SHEET_PAGES = {
  sheet: ["defense", "offense", "skills", "class", "feats", "companions", "background"],
  equipment: ["inventory", "equipment"],
  spells: ["spells"],
  journal: ["quests", "adventures"],
};
// Where the panel goes while each tab is open.
const SHEET_HOMES = { sheet: "sheetmore", equipment: "mode-equipment",
                      spells: "mode-spells", journal: "mode-journal" };
// 05 reads this when it draws the strip: null is every page.
let SHEET_SCOPE = null;
const SHEET_LAST = {};

function sheetInto(tab) {
  const panel = document.getElementById("sheetpanel");
  const home = document.getElementById(SHEET_HOMES[tab]);
  if (panel && home && panel.parentElement !== home) home.appendChild(panel);
  SHEET_SCOPE = SHEET_PAGES[tab];
  SHEET_TAB = SHEET_LAST[tab] || SHEET_SCOPE[0];
  // 05 brings the chosen page's tab into view once the sheet is read, and on a phone that
  // scrolled the whole Sheet page to its middle, past the character. The page opens at
  // its top: who first, as the design lays it out.
  Promise.resolve(openSheet()).then(() => {
    const stage = document.getElementById("stage");
    if (tab === "sheet" && stage && window.matchMedia("(max-width: 760px)").matches) stage.scrollTop = 0;
  });
}

function sheetOutOf(tab) {
  if (SHEET_SCOPE === SHEET_PAGES[tab]) SHEET_LAST[tab] = SHEET_TAB;
  sheetAway();
}

Shell.tab("sheet", {
  enter() { sheetInto("sheet"); },
  leave() { sheetOutOf("sheet"); },
});
