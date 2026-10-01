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
    sheetInto("journal");
  },
  leave() { sheetOutOf("journal"); },
});
