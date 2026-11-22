"""Spell buffs as timed, typed ActiveEffects (audit 2026-11-22, lane A).

`Engine._EXECUTES` had no entry for ability_mod, save_mod, skill_mod, non-AC combat_mod,
speed, temp_hp, resistance, damage_reduction, fast_healing or remove_condition, so bless,
aid, heroism, the six animal buffs, enlarge person and every other buff spell spent its
slot and was only TOLD: "+4 Strength." printed for the GM, Strength unchanged. The potion
of the same spell landed it, through `consumables._spec_to_intents`. These tests cast the
spell through the engine and read the sheet.
"""
from __future__ import annotations

from rules.sheet import from_dict, load_pc, to_dict
from test_casting_executes import cast, table


def caster(cls, level, *book):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    for ab in ("int", "wis", "cha"):
        d["abilities"][ab] = 18
    d["spellbook"] = list(book)
    d["prepared"] = {b: 2 for b in book}
    return from_dict(d, ref="pc")


def attack(actor):
    return sum(m.value for m in actor.attack_modifiers())


def save(actor, which, ctx=None):
    return sum(m.value for m in actor.save_modifiers(which, ctx))


def test_bulls_strength_lands_for_its_rounds_and_wears_off_with_a_record():
    """Audit 2026-11-22: bull's strength at caster level 5 left Strength 12 and printed
    "+4 Strength." Now 16 for 50 rounds (minutes/level), and when the minutes pass the
    scene's one ticker ends it and records the ending for the narrator."""
    s, e = table(caster("cleric", 5, "bull-s-strength"))
    pc = s.actors["pc"]
    out = cast(e, "bull-s-strength", at="pc").outcomes[0]
    assert pc.ability_score("str") == 16
    assert "+4 Strength for 5 minute(s) (Bull's Strength)" in out.tell
    held = next(x for x in pc.effects if x.source == "Bull's Strength")
    assert held.rounds_left == 50 and held.origin == "spell:bull-s-strength"
    advanced = s.advance(minutes=6)
    assert pc.ability_score("str") == 12
    assert any("Bull's Strength" in line for line in advanced["ended"])


def test_two_morale_bonuses_take_the_best_and_luck_adds_to_them():
    """Same type takes the best (CRB, Combining Magical Effects): heroism's +2 morale and
    bless's +1 morale give +2 to hit, not +3; prayer's +1 luck is another type and adds."""
    s, e = table(caster("cleric", 7, "bless", "prayer"))
    pc = s.actors["pc"]
    base = attack(pc)
    pc.add_buff("combat_mod", "attack", 2, source="Heroism", rounds=50,
                bonus_type="morale", origin="spell:heroism")
    cast(e, "bless", at="pc")
    assert attack(pc) == base + 2
    cast(e, "prayer", at="pc")
    assert attack(pc) == base + 3


def test_casting_the_same_buff_twice_refreshes_it_rather_than_stacking():
    """Spells "usually do not stack with themselves" (CRB, Magic): a second bless is the
    same source and resets the clock, never +2."""
    s, e = table(caster("cleric", 5, "bless"))
    pc = s.actors["pc"]
    base = attack(pc)
    cast(e, "bless", at="pc")
    cast(e, "bless", at="pc")
    assert attack(pc) == base + 1
    assert len([x for x in pc.effects if x.source == "Bless"]) == 1


def test_prayer_blesses_the_casters_side_and_hinders_the_other():
    """Prayer: allies +1 luck, foes -1 (CRB). The foes' half was a narrative line; in an
    area a bonus lands on the caster's side and a penalty on the other (`_cast_buff`)."""
    s, e = table(caster("cleric", 5, "prayer"))
    pc, thug = s.actors["pc"], s.actors["c1"]
    pc_will, thug_will = save(pc, "will"), save(thug, "will")
    cast(e, "prayer", at="pc")
    assert save(pc, "will") == pc_will + 1
    assert save(thug, "will") == thug_will - 1


def test_divine_favor_scales_with_caster_level_to_its_cap():
    """Audit 2026-11-22: divine favor's document was a flat +1 with "+1 per three caster
    levels, minimum +1, maximum +3" in a note nothing read. CRB: +1 at 1st, +2 at 6th, +3
    at 9th and never more."""
    for level, want in ((1, 1), (6, 2), (9, 3), (15, 3)):
        s, e = table(caster("cleric", level, "divine-favor"))
        pc = s.actors["pc"]
        base = attack(pc)
        cast(e, "divine-favor", at="pc")
        assert attack(pc) == base + want, level


def test_aid_rolls_its_temporary_hit_points_once_and_its_fear_bonus_waits_for_fear():
    """Aid: 1d8 + caster level (maximum +10) temporary hit points, +1 morale on attacks and
    on saves against fear (CRB). The temp HP rolled at cast and lasting the spell; the
    save bonus scoped by `when: {"against": "fear"}`, so an ordinary Will save is unmoved
    and a fear spell's save (`Engine._cast_save`: against spell AND fear) gets it."""
    s, e = table(caster("cleric", 5, "aid"))
    pc = s.actors["pc"]
    will = save(pc, "will")
    cast(e, "aid", at="pc")
    assert 6 <= pc.temp_hp <= 13
    pool = next(x for x in pc.effects if x.kind == "temp_hp")
    assert pool.rounds_left == 50
    assert save(pc, "will") == will
    assert save(pc, "will", {"against": ("spell", "fear")}) == will + 1


def test_enlarge_person_on_yourself_lands_with_no_save():
    """"A creature can voluntarily forgo a saving throw and willingly accept a spell's
    result" (CRB, Magic). Audit 2026-11-22: enlarge person on the caster did nothing —
    the gate skipped the caster and its branch held only numbers nothing ran."""
    s, e = table(caster("wizard", 5, "enlarge-person"))
    pc = s.actors["pc"]
    strength = pc.ability_score("str")
    out = cast(e, "enlarge-person", at="pc").outcomes[0]
    assert pc.ability_score("str") == strength + 2
    assert "Fortitude save" not in out.tell
    assert not [r for r in out.rolls if "save" in (r.label or "").lower()]


def test_enlarge_person_on_a_foe_is_saved_against():
    """The same gate on the other side asks for the Fortitude save, and a made save
    leaves the thug as he was."""
    for seed in range(1, 12):
        s, e = table(caster("wizard", 5, "enlarge-person"), seed=seed)
        thug = s.actors["c1"]
        strength = thug.ability_score("str")
        out = cast(e, "enlarge-person", at="c1").outcomes[0]
        assert "Fortitude save" in out.tell
        made = "makes the Fortitude save" in out.tell
        assert thug.ability_score("str") == (strength if made else strength + 2)


def test_a_buff_whose_note_qualifies_it_is_told_and_not_applied():
    """Bless's "+1 Will against fear effects" is a curated spec (lane B's) with the clause
    in a note no reader asks. Applied, it would be +1 to every Will save; told, it is
    honest until the data carries a `when`."""
    s, e = table(caster("cleric", 5, "bless"))
    pc = s.actors["pc"]
    will = save(pc, "will")
    out = cast(e, "bless", at="pc").outcomes[0]
    assert save(pc, "will") == will
    assert "told rather than applied" in out.tell


def test_expeditious_retreat_moves_land_speed():
    s, e = table(caster("wizard", 3, "expeditious-retreat"))
    pc = s.actors["pc"]
    cast(e, "expeditious-retreat", at="pc")
    assert pc.speed_feet == 60


def test_rage_raises_hit_points_with_constitution_and_takes_them_back():
    """A timed Constitution bonus moves current hit points with the maximum, both ways
    (`Actor._follow_con`); the buff op alone moved only the maximum."""
    s, e = table(caster("wizard", 7, "rage"))
    pc = s.actors["pc"]
    hp, top = pc.hp, pc.hp_max
    cast(e, "rage", at="pc")
    assert pc.hp_max == top + 7 and pc.hp == hp + 7
    s.advance(minutes=2)
    assert (pc.hp, pc.hp_max) == (hp, top)


def test_lesser_restoration_ends_fatigue():
    s, e = table(caster("cleric", 3, "restoration-lesser"))
    pc = s.actors["pc"]
    pc.add_condition("fatigued")
    out = cast(e, "restoration-lesser", at="pc").outcomes[0]
    assert not pc.has_condition("fatigued")
    assert "no longer fatigued" in out.tell


def test_a_fear_spells_save_carries_aids_bonus_and_an_ordinary_one_does_not():
    """Measured 2026-11-22: the cast's save context was `{"against": "spell"}` alone, so a
    `when: {"against": "fear"}` term could never hold on any spell save. A fear spell's
    save is now against a spell AND fear (`Engine._cast_save`); cause fear's Will save on
    an aided thug carries Aid's +1 morale."""
    s, e = table(caster("cleric", 5, "aid", "cause-fear"))
    cast(e, "aid", at="c1")
    out = cast(e, "cause-fear", at="c1").outcomes[0]
    will = next(r for r in out.rolls if "Will save" in (r.label or ""))
    assert any(m.source == "Aid" and m.value == 1 for m in will.modifiers)


def test_a_chosen_resistance_lands_through_the_rider_path():
    """Resist energy (lane B's part-21) is a `choose_one` of five `resistance` options, the
    pick the cast's `choose` param, the amount a caster-level formula. `_choose` hands the
    picked option to `_run_one`, which reaches `_cast_buff`: resist fire 20 at caster level
    7, for the spell's rounds — and nothing at all while nobody has chosen."""
    from rules.engine import Engine

    s, e = table(caster("cleric", 7, "bless"))
    pc = s.actors["pc"]
    spec = {"type": "choose_one", "options": [
        {"type": "resistance", "target": t,
         "amount": "min(30, max(10, 10 + 10 * ((caster_level - 3) / 4)))"}
        for t in ("acid", "cold", "electricity", "fire", "sonic")]}
    ctx = {"caster": "pc", "targets": ["pc"], "caster_level": 7, "rounds": 70,
           "source": "Resist Energy", "origin": "spell:resist-energy",
           "vars": {"caster_level": 7}, "chosen": None}
    assert Engine._run_one(e, spec, dict(ctx))[0][0]["kind"] == "choice_pending"
    effects, tells = Engine._run_one(e, spec, {**ctx, "chosen": 4})
    held = [x for x in pc.effects if x.source == "Resist Energy"]
    assert held and held[0].rounds_left == 70
    assert any("resistance 20 to fire" in t for t in tells)
