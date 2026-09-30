// The play table, part 21 (the Journal tab). Classic script, sharing one global scope.
//
// The approved design's Journal: the matters in play (the quest cards the engine keeps,
// their objectives and what has happened), what people said (the conversation log, read
// a person at a time; answering is Talk's), and the places walked. Drawn by 05-sheet.js's
// `pageJournal`. The adventure log is not kept yet, and the page says so.

Shell.tab("journal", {
  enter() {
    // Read afresh each visit: what was said moves on every turn.
    JOURNAL_LOG = null;
    sheetInto("journal");
  },
  leave() { sheetOutOf("journal"); },
});
