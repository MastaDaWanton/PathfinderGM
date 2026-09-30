// The play table, part 15 (the book's head). Classic script, sharing one global scope
// with 01-14 and 16-21.
//
// Where you are, in words, across the top of the page (the approved design's head row):
// the place's name, the line under it, and who is here. The line is the old side
// column's biome line, moved (docs/table-rebuild-inventory.md, B7): geography's words
// (`where_label`, `where_detail`, docs/fix-interfaces.md §2.10) when the server sends
// them, today's location, scale and biome otherwise, then the clock and the part of the
// day. The title attribute keeps what the old line kept in its own: what kind of place
// this is.
//
// Who is here is the scene's actors the player can see. The design opens a line about
// the person pressed; the state sends no face for them (the engine has
// `names.appearance_for`, and the actor payload would have to carry it), so the line says
// how they stand, hurt or not and any condition on them, from the same fields the old
// "In the scene" list showed. It never guesses a face.

let BOOK_PERSON = null;

function bookWhere(s) {
  const sc = (s && s.scene) || {};
  const town = sc.where_label || sc.location || "";
  // The place you stand in, when the ground is laid ("the gate", "the market"): the
  // design's head names it, with the settlement on the line under it. Measured live: a
  // walk from the market to the gate left the head reading "Torvathys · town" throughout.
  const local = (sc.grid && sc.grid.place) || "";
  const place = local || town;
  const parts = [];
  if (local && town) parts.push(town);
  if (sc.where_label) {
    if (sc.where_detail) parts.push(sc.where_detail);
  } else {
    const kind = [sc.scale, sc.biome].filter(Boolean).join(", ");
    if (kind) parts.push(kind);
  }
  if (typeof fmtClock === "function") parts.push(fmtClock(sc.clock_minutes));
  if (sc.day_part) parts.push(sc.day_part);
  return { place, line: parts.map(sidesUp).join(". ") + (parts.length ? "." : ""),
           about: sc.what_it_is || sc.biome_describe || "" };
}

function bookStanding(a) {
  const hurt = a.hp < a.hp_max ? (a.hp <= 0 ? "down" : "wounded") : "unhurt";
  const conds = (a.conditions || []).filter(Boolean);
  return `${sidesUp(a.name)}: ${hurt}${conds.length ? `, ${conds.join(", ")}` : ""}.`;
}

function renderBookHead(s) {
  const head = document.getElementById("place-name");
  if (!head) return;
  const w = bookWhere(s);
  head.textContent = w.place || "Nowhere yet";
  const line = $("#where-line");
  line.textContent = w.line;
  line.title = w.about;

  const people = ((s && s.scene && s.scene.actors) || []).filter(a => !a.is_pc);
  if (BOOK_PERSON && !people.some(a => a.ref === BOOK_PERSON)) BOOK_PERSON = null;
  $("#here").hidden = !people.length;
  $("#here-list").innerHTML = people.map(a => `<button type="button" class="v2-btn"
      data-person="${esc(a.ref)}" aria-expanded="${BOOK_PERSON === a.ref}"
      aria-controls="face">${esc(a.name)}</button>`).join("");
  const who = people.find(a => a.ref === BOOK_PERSON);
  $("#face").hidden = !who;
  $("#face").textContent = who ? bookStanding(who) : "";
}

onRender(function bookHead(s, prev) {
  renderBookHead(s);
  // On a phone the book's whole inside scrolls, head and all (the design's phone: a
  // fixed head left the story 190px), so 02's `#story` scroll to the newest beat moves
  // nothing there; the leaf is what goes to the foot. Only when the story grew, so a
  // resync that changed nothing leaves the reader where they are.
  const leaf = document.getElementById("bookin");
  const grew = !prev || ((s && s.transcript) || []).length !== ((prev.transcript) || []).length;
  if (leaf && grew && leaf.scrollHeight > leaf.clientHeight + 1) leaf.scrollTop = leaf.scrollHeight;
});

document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest("#here-list [data-person]");
  if (!b) return;
  BOOK_PERSON = BOOK_PERSON === b.dataset.person ? null : b.dataset.person;
  renderBookHead(STATE);
  const again = document.querySelector(`#here-list [data-person="${CSS.escape(b.dataset.person)}"]`);
  if (again) again.focus({ preventScroll: true });
});
