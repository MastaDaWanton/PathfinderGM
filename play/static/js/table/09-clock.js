// The play table, part 09 of 10 (clock). A stub shipped by the Phase-1 panel shell (S6) so
// the page loads every script it names and the packaged build has no 404s at G1.
// Lane F fills it in Phase 2: the time-skip face in #clockpop and its sentence in #clocksay
// (docs/design-f-ui.md §4.3), armed by the `table:posted` event that `post()` dispatches
// on `document`, and fired from a render hook, never on the first draw (`prev === null`).
onRender(function clockFace(s, prev) { /* Lane F, Phase 2 */ });
