"""Stage 2 of docs/states-effects-tells.md: one store, one applicator, one ticker.

The defect, measured before the port: the sheet maintained five mechanisms for the same
idea — conditions, buffs, temporary hit point pools, weapon coatings, and ability
bonuses — with three separate expiry loops inside `tick_conditions` and two mechanisms
(coatings, ability bonuses) that no loop ticked at all. Blood Rage's own +2/+2/−2 was
authored in the class file and applied by nothing: `_op_use_ability` printed the
numbers into prose and changed no roll. A mechanism added without its own loop was a
mechanism that never wore off.
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect
from rules.sheet import from_dict, to_dict


def _pc():
    return from_dict({
        "name": "Test Subject", "kind": "npc", "hp": 20, "hp_max": 20,
        "abilities": {a: 10 for a in ("str", "dex", "con", "int", "wis", "cha")},
    })


def test_all_five_mechanisms_land_in_the_one_store():
    """Conditions, buffs, temp hp and coatings were four separate lists; now they are
    four kinds in one list, and the list is the only thing a save has to carry."""
    a = _pc()
    a.add_condition("shaken", 3)
    a.add_buff("save_mod", "will", 1, source="acacia tea", rounds=10)
    a.gain_temp_hp(5, "a ward", rounds=20)
    a.coating = {"name": "oil of taggit", "specs": []}
    assert sorted(e.kind for e in a.effects) == [
        "buff", "coating", "condition", "temp_hp"]


def test_one_ticker_expires_everything_timed_in_one_call():
    """The three old loops, one clock. Before the port, `tick_conditions` held one
    expiry loop per mechanism — three copies of the same six lines — and the labels
    each loop reported are preserved verbatim here because transcripts read them."""
    a = _pc()
    a.add_condition("shaken", 2)
    a.add_buff("save_mod", "will", 1, source="acacia tea", rounds=2)
    a.gain_temp_hp(5, "a ward", rounds=2)
    assert a.tick_effects(1) == []
    ended = a.tick_effects(1)
    assert "Shaken" in ended
    assert "acacia tea (+1 will)" in ended
    assert "a ward (5 temp)" in ended
    assert a.effects == []


def test_a_stance_answers_tag_queries_without_being_a_condition():
    """`has_state` reads granted tags off every effect. Before, only condition keys
    answered — an ability's stance had to masquerade as a condition to be seen."""
    a = _pc()
    a.apply_effect(ActiveEffect(name="Blood Rage", kind="ability",
                                source="Blood Rage",
                                tags=("buff.stance.blood-rage",)))
    assert a.has_state("buff.stance")
    assert a.has_state("buff.stance.blood-rage")
    assert not a.has_state("state.down")
    assert not a.has_condition("blood rage")


def test_an_effects_modifiers_flow_through_the_dice_popup():
    """Source-tracked modifiers ride the existing modifier lists, so every number in
    the popup keeps a name. This is the path Blood Rage's +2/+2/−2 takes in stage 3."""
    a = _pc()
    a.apply_effect(ActiveEffect(
        name="Blood Rage", kind="ability", source="Blood Rage",
        modifiers=[{"kind": "combat_mod", "target": "attack", "amount": 2},
                   {"kind": "combat_mod", "target": "ac", "amount": -2}]))
    attack = a.attack_modifiers()
    assert any(m.value == 2 and m.source == "Blood Rage" for m in attack)
    ac = a.ac_modifiers()
    assert any(m.value == -2 and m.source == "Blood Rage" for m in ac)
    # Remove the effect and its contribution evaporates — nothing is subtracted.
    a.remove_effects(name="Blood Rage")
    assert not any(m.source == "Blood Rage" for m in a.attack_modifiers())
    assert not any(m.source == "Blood Rage" for m in a.ac_modifiers())


def test_refresh_stacking_never_grows_a_second_copy():
    a = _pc()
    e = ActiveEffect(name="Blood Rage", kind="ability", source="Blood Rage",
                     duration="rounds", rounds_left=5,
                     modifiers=[{"kind": "combat_mod", "target": "attack", "amount": 2}])
    a.apply_effect(e)
    a.apply_effect(ActiveEffect(name="Blood Rage", kind="ability",
                                source="Blood Rage", duration="rounds", rounds_left=9,
                                modifiers=[{"kind": "combat_mod", "target": "attack",
                                            "amount": 3}]))
    live = [x for x in a.effects if x.name == "Blood Rage"]
    assert len(live) == 1 and live[0].rounds_left == 9
    assert sum(m.value for m in a._buff_mods("combat_mod", "attack")) == 3


def test_an_effect_with_tags_and_modifiers_survives_a_save():
    """The legacy keys cannot say this record: a buff carries no tags and a condition
    carries no modifiers. The `active_effects` key is where it round-trips."""
    a = _pc()
    a.apply_effect(ActiveEffect(
        name="Blood Rage", kind="ability", source="Blood Rage",
        duration="rounds", rounds_left=7, tags=("buff.stance.blood-rage",),
        modifiers=[{"kind": "combat_mod", "target": "attack", "amount": 2}]))
    a.add_condition("shaken", 3)
    a.gain_temp_hp(4, "a ward")
    back = from_dict(to_dict(a))
    assert back.has_state("buff.stance.blood-rage")
    assert back.temp_hp == 4
    assert back.has_condition("shaken")
    assert sum(m.value for m in back._buff_mods("combat_mod", "attack")) == 2


def test_an_older_save_with_only_the_legacy_keys_still_loads():
    a = from_dict({
        "name": "Old Save", "kind": "npc", "hp": 9, "hp_max": 9,
        "abilities": {x: 10 for x in ("str", "dex", "con", "int", "wis", "cha")},
        "conditions": [{"key": "shaken", "rounds_left": 4}],
        "buffs": [{"kind": "save_mod", "target": "will", "amount": 1,
                   "source": "acacia tea", "rounds_left": 10}],
        "temp_hp": 6, "temp_hp_source": "a ward",
        "coating": {"name": "oil of taggit"},
    })
    assert a.has_condition("shaken") and a.conditions[0].rounds_left == 4
    assert a.temp_hp == 6 and a.temp_pools[0].source == "a ward"
    # The tea's +1 is present and named (shaken's −2 sits beside it, not over it).
    assert any(m.value == 1 and m.source == "acacia tea"
               for m in a.save_modifiers("will"))
    assert a.coating.get("name") == "oil of taggit"
