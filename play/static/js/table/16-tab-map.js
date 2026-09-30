// The play table, part 16 (the Map tab). Classic script, sharing one global scope.
//
// Stage 1 of the rebuild carries today's map into the tab as it is: 03's `renderMap`
// draws the flat board or the 3D one into #mapwrap, on the board where the book was, with
// its floors and its turn in the board's head; 04 reads a lit square as a move, as it
// always did. `render` redraws it on every state, so opening the tab only redraws it
// once more at the size the tab gives it.
//
// Stage 3 replaces this file's body: the owner's Places chart, the town under a fog of
// war, as a third way of looking beside Flat and 3D, drawn from `scene.places_found`
// (play/places_found.py, already on /api/state) (docs/table-rebuild-inventory.md, M7).

Shell.tab("map", {
  enter() { if (STATE && typeof renderMap === "function") renderMap(STATE); },
});
