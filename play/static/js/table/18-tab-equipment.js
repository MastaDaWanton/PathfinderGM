// The play table, part 18 (the Equipment tab). Classic script, sharing one global scope.
//
// The approved design's Equipment page (the mock README, "What changed in the second
// pass", points 1 and 2), drawn by 05-sheet.js's `pageEquipment` from the server's one
// list of what is carried (play/views.py `_carried`): the shelves down the side in the
// trade window's scheme, the list A to Z with every name written out, Worn and wielded
// with a slot that filters the list to what fits it. Wield, Wear and Use are answered by
// the engine's own doors. Take off (for armour and a shield) and drop are not offered,
// because the rules have neither; the head of the page says so in words
// (docs/table-rebuild-inventory.md, H9), and "Go to Trade" beside it is where new things
// come from (the owner's ruling: in play you buy at a counter and equip what you carry).

Shell.tab("equipment", {
  enter() {
    // A reply belongs to the act that drew it; a later visit starts with the line empty.
    EQ_SAY = "";
    EQ_SAY_BAD = false;
    EQ_BEFORE = null;
    sheetInto("equipment");
  },
  leave() { sheetOutOf("equipment"); },
});
