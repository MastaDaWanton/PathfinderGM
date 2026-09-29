"""A prepared caster starts the campaign with spells prepared (playtest item 21.4).

Measured 2026-09-28: Bobby, a wizard 1 with fifty spells in the book, began with
`prepared: {}`; "I cast burning hands into the tree tops" was refused seven times across
two models and the prose made the refusal a bluff. The G2 live queue measured it again the
same day: the `cast-area` script's five casts were all "Burning Hands is not prepared",
because nothing prepared the first morning. `new_campaign` now calls
`casting.ensure_prepared(pc, reason="start")`, which fills the empty slots from the book
in 1e's order and leaves a list caster empty with the sheet's warning (register Q39).
"""
from __future__ import annotations

from play import campaign as cm
from rules import casting
from rules.sheet import load_pc


def test_a_wizard_begins_with_his_slots_filled_from_the_book():
    pc = load_pc("fixtures/pc-caster.json")
    assert not pc.prepared, "the fixture starts empty, as Bobby did"
    c = cm.new_campaign("first-morning-wizard", seed=7, character=pc)
    me = c.scene.pc()
    assert me.prepared, "a wizard's first morning left every slot empty"
    assert casting.prepared_count(me, "burning-hands") >= 1
    assert not any(casting.empty_slots(me).values()), casting.empty_slots(me)


def test_a_non_caster_is_untouched():
    c = cm.new_campaign("first-morning-rogue", seed=7,
                        character=load_pc("fixtures/pc-kesst.json"))
    assert not c.scene.pc().prepared
