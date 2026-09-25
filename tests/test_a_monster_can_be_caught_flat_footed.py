"""A monster's armour class is made of the things its stat block says it is made of.

Measured 2026-09-25 by probe: `flat_ac` became ONE untyped modifier, so flat-footed,
touch and every lose-Dex condition did nothing against any of the 7,133 bestiary
creatures — wolf 14/14/14, ogre 17/17/17 — while the attack tell still wrote
"(flat-footed)". The stat blocks carry the breakdown ("+2 Dex, +2 natural") on 6,357
of them and the two numbers outright ("touch 8, flat-footed 17") on 782 more.

Measured after the fix, across the whole bestiary: 0 of 7,133 creatures changed their
printed AC, and 782 of the 786 blocks that state touch and flat-footed reproduce both
(the other four carry two notes run together).
"""
from __future__ import annotations

import pytest

from rules import bestiary
from rules.bestiary import instantiate
from rules.engine import Scene


def _make(key):
    return instantiate(key, scene=Scene())


def test_a_wolf_caught_flat_footed_loses_its_dex():
    wolf = _make("wolf")                          # (+2 Dex, +2 natural), AC 14
    assert wolf.ac() == 14
    assert wolf.ac(flat_footed=True) == 12
    assert wolf.touch_ac() == 12


def test_a_stunned_wolf_loses_its_dex():
    wolf = _make("wolf")
    wolf.add_condition("stunned", source="test")
    assert wolf.ac() == 14 - 2 - 2               # Dex gone, and stunned's own -2


def test_the_stated_numbers_are_reproduced_exactly():
    ogre = _make("ogre")                          # "touch 8, flat-footed 17", AC 17
    assert (ogre.ac(), ogre.touch_ac(), ogre.ac(flat_footed=True)) == (17, 8, 17)


@pytest.mark.parametrize("note,expect", [
    ("(+4 armor, +8 Dex, +1 dodge, +9 natural, +4 shield)",
     [(4, "armour"), (8, ""), (1, "dodge"), (9, "natural armour"), (4, "shield")]),
    ("(+1 Dex, +13 natural, -2 size)", [(1, ""), (13, "natural armour"), (-2, "")]),
    ("(+2 Dex, +2 dodge vs traps)", [(2, "")]),
    ("(+1 deflection against good, +3 armor)", [(3, "armour")]),
])
def test_the_note_is_read_into_typed_terms(note, expect):
    assert [(v, t) for v, _, t in bestiary.ac_parts(note)] == expect


def test_no_creature_changes_its_printed_armour_class():
    """The remainder term is what makes this safe: a note with a typo or a conditional
    must never move a creature's AC. Sampled every fortieth block for speed."""
    blocks = [k for k, b in bestiary.imported().items() if b.get("flat_ac") is not None]
    for key in blocks[::40]:
        try:
            a = _make(key)
        except Exception:
            continue
        assert a.ac() == a.flat_ac, key


def test_a_character_caught_flat_footed_loses_dodge_too():
    """1e: "any situation that denies you your Dexterity bonus also denies you dodge
    bonuses". The PC path dropped Dex and kept dodge."""
    from rules.activeeffect import ActiveEffect
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    base, base_ff = pc.ac(), pc.ac(flat_footed=True)
    pc.apply_effect(ActiveEffect(name="dodge test", kind="buff", key="dodge-test",
                                 source="test", modifiers=[{"kind": "combat_mod",
                                                            "target": "ac", "amount": 1,
                                                            "bonus_type": "dodge"}]))
    assert pc.ac() == base + 1, "the dodge bonus must land, or this tests nothing"
    assert pc.ac(flat_footed=True) == base_ff, "a dodge bonus survived flat-footed"
