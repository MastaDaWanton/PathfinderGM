"""Feat loop batch 7, lane fixes: negative energy's one family, Power Attack's stance and
the b6-rules leftovers (content/feats/mechanics/b7-fixes.json)."""
from __future__ import annotations

from rules import states
from rules.bestiary import instantiate
from rules.engine import Scene


# --- 1. negative energy heals: one tag family (owner ruling 2026-11-09) -------------------

def test_inflict_mends_a_deaths_embrace_cleric_and_a_cure_does_not_hurt_her():
    """Owner ruling 2026-11-09: "Inflict spells heal creatures with a negative energy
    affinity: channel.negative.heals, not only type.undead." Measured before b7: a Death's
    Embrace cleric at 3 hp cast inflict light wounds on herself and went DOWN — the cast loop
    asked `type.undead` and Necromantic Affinity's `energy.negative.affinity`, and never the
    channel's tag. Death's Embrace says nothing of cure spells, so a cure still heals her."""
    from tests.test_audit_magic import _cleric, records, run, said, scene_with

    pc = _cleric(level=8)
    pc.domains = ["Death", "War"]
    assert pc.has_state(states.NEGATIVE_HEALS_CHANNEL)
    s, e = scene_with(pc)
    pc.hp = 3
    res = run(e, "cast", spell="inflict-light-wounds", at="pc")
    assert pc.hp > 3, said(res)
    assert records(res, "heal")
    assert "answers to negative energy" in said(res)
    before = pc.hp
    run(e, "cast", spell="cure-light-wounds", at="pc")
    assert pc.hp >= before


def test_the_undead_hold_the_family_by_their_type():
    """One vocabulary: the cast loop asks `energy.negative.heals`, never `type.undead`
    beside a second tag, so the undead must answer it by their type (`states.type_tags`)."""
    z = instantiate("zombie", scene=Scene(location_id="5bbd0c40345f"))
    assert z.has_state(states.NEGATIVE_HEALS)
    assert z.has_state(states.NEGATIVE_HEALS_SPELLS)
    assert not z.has_state(states.NEGATIVE_HEALS_CHANNEL)
    wolf = instantiate("wolf", scene=Scene(location_id="5bbd0c40345f"))
    assert not wolf.has_state(states.NEGATIVE_HEALS)
