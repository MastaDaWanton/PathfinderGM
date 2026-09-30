// The play table, part 19 (the Spells tab). Classic script, sharing one global scope.
//
// A caster gets the Spells tab and the Spells button beside Say; a non-caster gets
// neither, with no empty tab and no disabled button (the mock README, point 3; Foundry's
// PF1 sheet removes the spells tab for an actor with no spellcasting profile). Shown by
// `spellcasting.kind`, the rule 10-spells.js already keeps for the button (owner Q49),
// never by `pc.castable`, which offers a prepared caster's whole book when nothing is
// prepared.
//
// The page is the I5 Spells page (05's `tabSpells`), its behaviour kept and restyled onto
// the design's framed cards: the slots as gem sockets by level, lit while unspent and red
// once spent today (the owner, 2026-09-29), prepared spells as cards with Details,
// cantrips at will, and Cast attaching the spell to the pen as a chip. The house rule is
// said on the page: prepare whenever, but a spent slot stays spent until a long rest.

Shell.tab("spells", {
  enter() { sheetInto("spells"); },
  leave() { sheetOutOf("spells"); },
});

onRender(function spellsTab(s) {
  const tab = document.getElementById("tab-spells");
  if (!tab) return;
  const kind = (s && s.spellcasting && s.spellcasting.kind) || "";
  tab.hidden = !kind;
  // Somebody who does not cast is playing now: their page is not left open.
  if (!kind && Shell.mode() === "spells") Shell.show("table");
});
