// The play table, part 18 (the Equipment tab). Classic script, sharing one global scope.
//
// Stage 1 carries today's Inventory and Equipment pages of the sheet (05's
// `tabInventory`, `tabEquipment`) into the tab, with exactly the actions they had:
// drink, throw, coat and wear a thing carried; add and take a line in a body slot.
// Take off and drop are not offered, because the engine has neither op (the mock README,
// "What the engine does not know"); the note above the panel says so in words rather
// than leaving the player to look for them (docs/table-rebuild-inventory.md, H9).
//
// Stage 2 replaces this file's body with the approved design's Equipment page (the
// shelves, the list, Worn and wielded).

Shell.tab("equipment", {
  enter() { sheetInto("equipment"); },
  leave() { sheetOutOf("equipment"); },
});
