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
  Promise.resolve(openSheet()).then(() => {
    const stage = document.getElementById("stage");
    if (tab === "sheet" && stage && window.matchMedia("(max-width: 760px)").matches) stage.scrollTop = 0;
  });
}

function sheetOutOf() {
  sheetAway();
}

Shell.tab("sheet", {
  enter() { sheetInto("sheet"); },
  leave() { sheetOutOf("sheet"); },
});
