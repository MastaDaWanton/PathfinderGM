// The play table, part 19 (the Spells tab). Classic script, sharing one global scope.
//
// A caster gets the Spells tab and the Spells button beside Say; a non-caster gets
// neither, with no empty tab and no disabled button (the mock README, point 3; Foundry's
// PF1 sheet removes the spells tab for an actor with no spellcasting profile). Shown by
// `spellcasting.kind`, the rule 10-spells.js already keeps for the button (owner Q49),
// never by `pc.castable`, which offers a prepared caster's whole book when nothing is
// prepared.
//
// Stage 1 carries today's Spells page (05's `tabSpells`: the slots as gem sockets,
// prepared today as cards, the grimoire index) into the tab as it is.

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
