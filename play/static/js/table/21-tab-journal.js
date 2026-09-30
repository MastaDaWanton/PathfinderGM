// The play table, part 21 (the Journal tab). Classic script, sharing one global scope.
//
// Stage 1 carries today's Quests and Adventures pages of the sheet (05's `tabQuests`:
// the tasks taken up, their objectives and what has happened, and the adventure log
// that is still to come) into the tab as they are. What was said is in Talk, per person.

Shell.tab("journal", {
  enter() { sheetInto("journal"); },
  leave() { sheetOutOf("journal"); },
});
