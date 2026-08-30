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
    # 1e: a belt of giant strength raises your STRENGTH. Kesst's Str 12 becomes 14 and
    # the modifier follows it from +1 to +2.
    #
    # This assertion read `== 3` with a comment calling the +2 "a modifier bump, riding
    # the same convention every buff has used" — which is what the code did and not what
    # the rules say. Applied to the modifier, a +2 belt was worth +2 where raising 12 to
    # 14 gives +1, and a +6 belt was worth +6 where it should be +3: every belt and
    # headband in the shipped catalogue was worth double. The convention was the bug, and
    # a test written to match it protected the bug.
    assert pc.ability_score("str") == 14
    assert pc.ability_mod("str") == 2
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


# --- the score is the funnel point ----------------------------------------------------


def _con(level=4, con=14, hp=40):
    return from_dict({"name": "x", "kind": "npc", "level": level, "hp": hp,
                      "hp_max": hp,
                      "abilities": {"str": 10, "dex": 10, "con": con,
                                    "int": 10, "wis": 10, "cha": 10}})


def test_an_ability_bonus_raises_the_score_and_the_modifier_follows():
    """1e: a belt of giant strength raises your STRENGTH. Applied to the modifier
    instead — the convention the code used and a test of mine was written to match —
    a +2 belt was worth +2 where raising 12 to 14 gives +1, and a +6 belt was worth
    +6 where it should be +3. Every belt and headband in the catalogue was double."""
    a = _con()
    a.abilities["str"] = 12
    a.add_buff("ability_mod", "str", 4, source="belt", bonus_type="enhancement")
    assert a.ability_score("str") == 16
    assert a.ability_mod("str") == 3          # not 1 + 4


def test_two_enhancement_belts_take_the_better_one():
    """The second funnel skipped `stack()` entirely, so two enhancement bonuses to one
    score added. Routing the bonus through the score puts it through the channels."""
    a = _con()
    a.abilities["str"] = 12
    a.add_buff("ability_mod", "str", 2, source="lesser belt", bonus_type="enhancement")
    a.add_buff("ability_mod", "str", 6, source="greater belt", bonus_type="enhancement")
    assert a.ability_score("str") == 18       # 12 + 6, not 12 + 8


def test_a_constitution_buff_cannot_mint_hit_points():
    """The sequence the rules review found, and the reason `hp_max` had to become
    derived in the same change that let ability bonuses reach the score.

    `hp_max` was a stored number mutated in three places and reconciled in one. Buff
    Constitution (nothing recomputed), take Con damage (a delta measured against the
    buffed modifier), let the buff expire (nothing recomputed), heal the damage (a
    delta measured against the unbuffed one) — and the character keeps hit points
    nobody granted. That is 'added and hopefully subtracted', which law 2 exists to
    forbid, and it would have been created BY the fix to the ability funnel."""
    a = _con()
    start = a.hp_max
    a.add_buff("ability_mod", "con", 4, source="bear's endurance",
               bonus_type="enhancement")
    assert a.hp_max == start + 2 * a.hit_dice, "a +4 Con is +2 per Hit Die"
    a.damage_ability("con", 4)
    a.remove_effects(source="bear's endurance")
    a.heal_ability("con", 4)
    assert a.hp_max == start, f"hit points were minted: {start} -> {a.hp_max}"


def test_a_wounded_character_keeps_the_wound_when_the_maximum_moves():
    a = _con(hp=40)
    a.hp = 12
    a.damage_ability("con", 4)                # -2 modifier over 4 Hit Dice
    assert a.hp_max == 32 and a.hp == 4


def test_the_derived_maximum_round_trips_through_a_save():
    """The base is stored and the total derived, so the number in the file has to mean
    the same thing on the way back in — including for a class with two Hit Dice per
    level, where computing the base before `classes.apply` measured Constitution
    against one die and read it back against two. Measured on the user's own twelve
    campaigns: five characters gained hit points on load, Thor 23 -> 37."""
    from rules.sheet import load_pc

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": 3, "ranks": {},
              "paths": ["battle blood"], "hp_max": 37, "hp": 37})
    a = from_dict(d, ref="pc")
    assert a.hit_dice == 6, "two Hit Dice per level"
    assert a.hp_max == 37, "the saved total is the loaded total"
    assert from_dict(to_dict(a), ref="pc").hp_max == 37


# --- the last two inert channels ------------------------------------------------------


def _plain(armour="none"):
    return from_dict({"name": "x", "kind": "npc", "hp": 20, "hp_max": 20,
                      "armour": armour,
                      "abilities": {k: 12 for k in
                                    ("str", "dex", "con", "int", "wis", "cha")}})


def test_magical_speed_bonuses_do_not_pile_up():
    """All 69 shipped speed specs are written with no bonus type, and untyped
    self-stacks — so routing them in raw would let haste, longstrider and expeditious
    retreat add to +70 over a base 30 where 1e's enhancement channel gives +30. 1e
    makes magical speed bonuses enhancement bonuses, so an untyped one is read as
    enhancement rather than left to pile up."""
    a = _plain()
    base = a.speed_feet
    a.add_buff("speed", "land", 30, source="haste")
    a.add_buff("speed", "land", 10, source="longstrider")
    a.add_buff("speed", "land", 30, source="expeditious retreat")
    assert a.speed_feet == base + 30


def test_speed_is_still_armoured_and_halved_in_the_book_s_order():
    """The funnel goes between the armour lookup and the halving: boots do not undo a
    breastplate, and being entangled halves what is left including them."""
    a = _plain("full plate")
    a.add_buff("speed", "land", 10, source="boots")
    assert a.speed_feet == 30              # 30 -> 20 by armour, +10 boots
    a.add_condition("entangled")
    assert a.speed_feet == 15


def test_touch_ac_ignores_the_three_channels_a_touch_attack_ignores():
    """This was `ac() - armour[ac] - shield[ac] - natural_armour`: three table lookups
    subtracted from a finished total, so it saw the armour a character WORE and was
    blind to every other source of those same three bonuses. Bracers of armour, mage
    armor and thirteen crafted hides all inflated touch AC."""
    a = _plain("leather")
    before = a.touch_ac()
    a.slot_list("wrists")[0] = "Bracers of Armor +4"
    assert a.ac() > 10, "the bracers reach ordinary AC"
    assert a.touch_ac() == before, "and are ignored by a touch attack"

    b = _plain("leather")
    was = b.touch_ac()
    b.slot_list("ring")[0] = "Ring of Protection +1"
    assert b.touch_ac() == was + 1, "deflection is not ignored"


def test_an_authored_touch_ac_bonus_reaches_touch_ac():
    """It was in the vocabulary, offered by the editor, and read by nothing."""
    a = _plain("leather")
    before = a.touch_ac()
    a.add_buff("combat_mod", "touch_ac", 2, source="a stance")
    assert a.touch_ac() == before + 2


def test_a_crafted_hide_that_says_armour_is_typed_armour():
    """Thirteen leatherworker specs carried notes reading "worked into armour" and a
    potion's note read "as an armour bonus — it does not stack with worn armour", and
    every one of them was typed `untyped`. The note and the type disagreed, and the
    type is what the stacking rule reads."""
    import json
    from pathlib import Path

    raw = Path("content/materials/leatherworker-materials.json").read_text(
        encoding="utf-8")
    specs = [spec for entry in json.loads(raw).get("materials", [])
             for spec in (entry.get("effects") or [])
             if spec.get("type") == "combat_mod" and spec.get("target") == "ac"
             and "armour" in str(spec.get("note") or "").lower()]
    assert specs, "the crafted hides moved; update this test"
    assert all(s.get("bonus_type") == "armour" for s in specs), (
        "a hide worked into armour grants an armour bonus, and armour bonuses do not "
        "stack with the armour it is worked into")
