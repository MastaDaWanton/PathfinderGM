"""Stage 4 of docs/states-effects-tells.md: the aggregator's reward.

Three defects, measured before this existed. The sheet page's own admission — "a ring
of protection here will not move your AC until magic items are modelled" — while the
catalogue carried the ring's deflection spec the whole time. Bonus types were carried
on specs and read by nothing, so two deflection bonuses added where 1e takes the
better one, and Bracers of Armor were authored `untyped` with a note saying "armour
bonus" because nothing would have collided them anyway. And Blood Bending's class file
promised "50% resistance to physical damage while in Blood Rage" with no way for any
effect to say a percentage.
"""
from __future__ import annotations

from rules.dice import Modifier, stack
from rules.sheet import from_dict, load_pc, to_dict


def _pc():
    return load_pc("fixtures/pc-kesst.json")


# --- 1e's stacking channels ---------------------------------------------------------


def test_same_typed_bonuses_take_the_best_not_the_sum():
    """1e: two deflection bonuses are the better one. Before typed channels every
    list summed blindly, so +1 and +2 deflection made +3."""
    mods = stack([Modifier(10, "base"), Modifier(1, "ring +1", "deflection"),
                  Modifier(2, "ring +2", "deflection")])
    assert sum(m.value for m in mods) == 12
    assert [m.source for m in mods] == ["base", "ring +2"]


def test_dodge_stacks_and_penalties_always_stack():
    """The two rules GAS's additive-then-multiplicative order gets differently, and
    the reason the doc records for not taking it: dodge stacks with itself, and a
    penalty stacks whatever its type says."""
    mods = stack([Modifier(1, "Dodge feat", "dodge"), Modifier(1, "fighting defensively", "dodge"),
                  Modifier(-2, "cursed", "deflection"), Modifier(-1, "also cursed", "deflection")])
    assert sum(m.value for m in mods) == -1


def test_worn_armour_and_an_armour_bonus_item_do_not_stack():
    """Bracers of Armor were authored `untyped` with a *note* saying "armour bonus";
    the note was read by nobody and the bracers would have stacked with a
    breastplate. The channel is the type, not the note."""
    pc = _pc()
    before = pc.ac()
    pc.slot_list("wrists")[0] = "Bracers of Armor +1"
    # Kesst wears leather (+2 armour); +1 bracers lose to it and move nothing.
    assert pc.ac() == before
    pc.slot_list("wrists")[0] = "Bracers of Armor +4"
    # +4 beats the leather: the better one applies, the leather drops out.
    assert pc.ac() == before + 2


# --- magic items are infinite effects granted by worn slots -------------------------


def test_the_ring_of_protection_finally_moves_the_ac():
    """The sheet page's own admission, closed — and the popup names the ring."""
    pc = _pc()
    before = pc.ac()
    pc.slot_list("ring")[0] = "Ring of Protection +1"
    assert pc.ac() == before + 1
    assert any(m.source == "Ring of Protection +1" and m.type == "deflection"
               for m in pc.ac_modifiers())


def test_a_third_ring_is_worn_not_working():
    """1e allows two rings. The slot past the rules limit records the ring and
    grants nothing."""
    pc = _pc()
    before = pc.ac()
    rings = pc.slot_list("ring")
    while len(rings) < 3:
        pc.add_slot("ring")
        rings = pc.slot_list("ring")
    rings[2] = "Ring of Protection +3"
    assert pc.ac() == before


def test_the_belt_and_the_cloak_reach_every_derived_number():
    """A belt of giant strength is an ability enhancement, so it must move melee
    attack and damage through the Str modifier, not just the score."""
    pc = _pc()
    atk_before = sum(m.value for m in pc.attack_modifiers("dagger"))
    will_before = sum(m.value for m in pc.save_modifiers("will"))
    pc.slot_list("belt")[0] = "Belt of Giant Strength +2"
    pc.slot_list("shoulders")[0] = "Cloak of Resistance +1"
    # The catalogue authors ability_mod as a modifier bump (+2), riding the same
    # convention every buff has used; Kesst's Str 12 base modifier +1 becomes +3.
    assert pc.ability_mod("str") == 3
    assert sum(m.value for m in pc.save_modifiers("will")) == will_before + 1
    assert sum(m.value for m in pc.attack_modifiers("dagger")) >= atk_before
    assert any(m.source == "Cloak of Resistance +1" for m in pc.save_modifiers("will"))


def test_worn_magic_survives_a_save():
    pc = _pc()
    pc.slot_list("ring")[0] = "Ring of Protection +1"
    back = from_dict(to_dict(pc), ref="pc")
    assert back.ac() == pc.ac()
    assert any(m.source == "Ring of Protection +1" for m in back.ac_modifiers())


def test_an_unknown_name_in_a_slot_stays_inert():
    """A guessed effect would be worse than an inert string — the same rule as
    goods.py: honest about what the engine has no rules for."""
    pc = _pc()
    before = pc.ac()
    pc.slot_list("ring")[0] = "the signet of an unremembered house"
    assert pc.ac() == before


# --- percent resistance as a document -----------------------------------------------


def _raging_bender(level=9):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["battle blood"]
    return from_dict(d, ref="pc")


def test_blood_rage_armor_halves_physical_damage_as_a_document():
    """"Gain 50% resistance to physical damage while in Blood Rage" — promised by
    the class text, undeliverable until an effect could carry a percentage. It is a
    by_tier rung on Blood Rage's own document, so it arrives at Control Blood 3 with
    zero engine code naming the class."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    scene = Scene()
    pc = _raging_bender()
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    e.run(e.validate([{"op": "use_ability", "actor": "pc",
                       "params": {"ability": "Blood Rage"}, "because": "test"}]))
    pc.clear_temp_hp()                       # isolate the resistance from the ward
    hp = pc.hp
    got = pc.take_damage(9, "slashing")
    # Rounded in the defender's favour: 50% of 9 shrugs off 5, and 4 lands.
    assert got["factored"] == 5 and got["factored_by"] == "Blood Rage"
    assert pc.hp == hp - 4
    # Energy is not physical, and the armor says physical.
    assert pc.take_damage(8, "fire")["factored"] == 0


def test_the_armor_waits_for_its_tier():
    """At Control Blood 1 the rage carries no rung, so nothing is halved — the
    upgrade arrives when the tier does, through the same resolve_effect as every
    tiered number."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    scene = Scene()
    pc = _raging_bender(level=1)
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    e.run(e.validate([{"op": "use_ability", "actor": "pc",
                       "params": {"ability": "Blood Rage"}, "because": "test"}]))
    pc.clear_temp_hp()
    assert pc.take_damage(9, "slashing")["factored"] == 0
