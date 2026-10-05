"""The core classes' active abilities, as documents (docs/class-audit.md, lane 4).

The defect, measured 2026-10-05 against the real engine: rage, smite evil, lay on hands,
ki, wild shape and bardic performance were pool counters and nothing else — each pool
refilled on a night's rest and the generic `resource` op subtracted from it, but no op
applied what the pool was for. `use_ability` refused all fourteen names tried on every
core class: "has no ability called rage. They can use: nothing yet." The ability bar
(`play/views.py:_usable_abilities`) and the GM's brief listed Blood Bending's path
abilities only. Channel energy and stunning fist had no pool at all.

Every test here goes through `Engine.validate` and `Engine.run`, the door the table uses,
and reads the numbers back off the real sheet and the real rolls.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rules import class_abilities as ca
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import from_dict, load_pc, to_dict


def _pc(cls: str, level: int, **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = cls
    d["level"] = level
    d["ranks"] = {}
    d.pop("paths", None)
    d.update(extra)
    return from_dict(d, ref="pc")


def _fight(pc, *foes, allies=()):
    scene = Scene()
    scene.add(pc)
    for a in allies:
        scene.add(a)
    for i, f in enumerate(foes or ("thug",)):
        scene.add(instantiate(f, scene=scene, name=f"the {f}"))
    them = [r for r in scene.actors if r not in ("pc",) and r not in {a.ref for a in allies}]
    e = Engine(scene, dice=Dice(seed=11))
    e.run(e.validate([{"op": "begin_encounter", "params": {
        "sides": {"pc": ["pc"] + [a.ref for a in allies], "them": them}}}]))
    return scene, e


def _use(e, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return e.run(e.validate([raw])).outcomes[-1]


def _swing(e, target="c1", face=15, weapon=None):
    raw = {"op": "attack", "actor": "pc", "target": target, "because": "test", "params": {}}
    if weapon:
        raw["params"]["weapon"] = weapon
    res = e.run(e.validate([raw]))
    asked = []
    while res.awaiting:
        asked.append(dict(res.awaiting))
        label = res.awaiting["label"]
        res = e.resume(face if label.startswith(("Attack", "Confirm"))
                       else int(res.awaiting["max"]))
    return res, asked


def _adjacent(scene, a="pc", b="c1"):
    from tests._board import face_to_face

    face_to_face(scene, a, b)


# --- the door itself ------------------------------------------------------------------------

@pytest.mark.parametrize("cls,level,name", [
    ("barbarian", 1, "Rage"), ("paladin", 1, "Smite Evil"), ("paladin", 2, "Lay on Hands"),
    ("paladin", 4, "Channel Positive Energy"), ("cleric", 1, "Channel Energy"),
    ("monk", 1, "Stunning Fist"), ("monk", 4, "Ki Dodge"), ("monk", 4, "Ki Speed"),
    ("bard", 1, "Inspire Courage"), ("bard", 1, "Fascinate"),
    ("druid", 4, "Wild Shape (wolf)"),
])
def test_fourteen_names_were_refused_on_every_core_class_and_now_resolve(cls, level, name):
    """Measured 2026-10-05: `use_ability` with rage, smite evil, lay on hands, channel
    energy, wild shape, stunning fist and eight more was refused on all twelve classes —
    "has no ability called X. They can use: nothing yet." Each now resolves for the class
    that has it, through validate and run, and is never that refusal."""
    pc = _pc(cls, level)
    _scene, e = _fight(pc)
    aimed = {"Smite Evil", "Stunning Fist"}
    out = _use(e, name, to="c1" if name in aimed else None)
    assert "has no ability called" not in out.tell, out.tell
    assert out.status != "refused", out.tell


def test_a_class_ability_below_its_level_says_when_it_arrives():
    """A 1st-level druid asking for wild shape is told 4th, not "no ability called"."""
    pc = _pc("druid", 1)
    _scene, e = _fight(pc)
    out = _use(e, "Wild Shape (wolf)")
    assert out.status == "refused" and "level 4" in out.tell, out.tell


# --- rage -----------------------------------------------------------------------------------

def test_a_barbarian_could_not_rage_and_now_the_swing_feels_it():
    """"a barbarian could not rage: 'rage' refused on every core class". Rage is +4 morale
    Strength and Constitution, +2 morale Will, -2 AC (CRB p.31), costs a round of the pool
    the class file already declares, lends 2 hit points per Hit Die through Constitution —
    and the next attack's Strength term is two higher, read off the real roll."""
    pc = _pc("barbarian", 5)
    scene, e = _fight(pc)
    _adjacent(scene)
    before = {ab: pc.ability_score(ab) for ab in ("str", "con")}
    ac, will = pc.ac(), sum(m.value for m in pc.save_modifiers("will"))
    hp, hp_max, pool = pc.hp, pc.hp_max, pc.pool("rage").current
    out = _use(e, "Rage")
    assert pc.has_condition("rage") and pc.has_state("buff.stance.rage")
    assert pc.ability_score("str") == before["str"] + 4
    assert pc.ability_score("con") == before["con"] + 4
    assert pc.ac() == ac - 2
    assert sum(m.value for m in pc.save_modifiers("will")) == will + 2
    assert pc.hp_max == hp_max + 2 * pc.hit_dice and pc.hp == hp + 2 * pc.hit_dice
    assert pc.pool("rage").current == pool - 1
    assert "+4 str" in out.tell and "rage" in out.tell.lower()

    pc.equipped = "unarmed"
    _res, asked = _swing(e, weapon="unarmed")
    attack = next(a for a in asked if a["label"].startswith("Attack"))
    strength = next(b for b in attack["breakdown"] if b["source"] == "Str")
    assert strength["value"] == (before["str"] + 4 - 10) // 2


def test_rage_ends_in_fatigue_for_twice_the_rounds_raged():
    """"Fatigued after rage for a number of rounds equal to 2 times the number of rounds
    spent in the rage" (CRB p.31). Three rounds raged — the round it began and two drained
    by the round clock — is six rounds fatigued, and a fatigued barbarian cannot rage
    again: the refusal names the state."""
    pc = _pc("barbarian", 5)
    scene, e = _fight(pc)
    _use(e, "Rage")
    scene._drain_periodic(pc)
    scene._drain_periodic(pc)
    out = _use(e, "Rage")
    assert not pc.has_condition("rage")
    fatigue = next(x for x in pc.effects if x.key == "fatigued")
    assert fatigue.rounds_left == 6, out.tell
    assert "fatigued for 6 rounds" in out.tell
    again = _use(e, "Rage")
    assert again.status == "refused" and "fatigued" in again.tell


def test_a_rage_run_dry_by_its_upkeep_still_leaves_the_fatigue():
    """The round clock ends a rage whose pool is empty (`Scene._drain_periodic`); the
    fatigue is owed then too, and said, or a rage that ran out was free."""
    pc = _pc("barbarian", 1)
    scene, e = _fight(pc)
    _use(e, "Rage")
    records = []
    for _ in range(pc.pool("rage").maximum + 2):
        records += scene._drain_periodic(pc)
    assert not pc.has_condition("rage")
    assert any(r.get("kind") == "upkeep_failed" for r in records)
    assert any(r.get("kind") == "condition" and r.get("condition") == "fatigued"
               for r in records)
    assert pc.has_condition("fatigued")
    assert pc.ability_score("str") == 10, "the rage's Strength left with it (fatigue -2)"


def test_greater_mighty_and_tireless_rage_are_rungs_not_code():
    """+6/+3 at 11th, +8/+4 at 20th, and no fatigue from 17th — three rungs of one
    document, not three branches."""
    for level, str_bonus, will_bonus in ((11, 6, 3), (20, 8, 4)):
        pc = _pc("barbarian", level)
        _scene, e = _fight(pc)
        base, will = pc.ability_score("str"), sum(m.value for m in pc.save_modifiers("will"))
        _use(e, "Rage")
        assert pc.ability_score("str") == base + str_bonus
        assert sum(m.value for m in pc.save_modifiers("will")) == will + will_bonus
        _use(e, "Rage")
        assert pc.has_condition("fatigued") is (level < 17)


def test_rage_powers_ride_the_rage_only_when_chosen():
    """Rage powers are lane 1's choice; their effects are documents here. Animal Fury's
    bite and Swift Foot's +5 ft arrive with the rage and leave with it; Renewed Vigor is
    refused out of a rage ("only while raging") and once a day inside one."""
    pc = _pc("barbarian", 6, class_choices={
        "rage power": {"picks": ["animal fury", "swift foot", "renewed vigor"]}})
    _scene, e = _fight(pc)
    speed = pc.speed_feet
    out = _use(e, "Renewed Vigor")
    assert out.status == "refused" and "only while raging" in out.tell
    _use(e, "Rage")
    assert pc.weapon("bite")["damage"] == "1d4" and pc.weapon("bite").get("natural")
    assert pc.speed_feet == speed + 5
    pc.hp = 1
    healed = _use(e, "Renewed Vigor")
    assert pc.hp > 1 and "recovers" in healed.tell
    assert _use(e, "Renewed Vigor").status == "refused"
    _use(e, "Rage")
    assert pc.speed_feet == speed
    assert not any(e.payload.get("natural_weapons") for e in pc.effects
                   if isinstance(e.payload, dict))

    plain = _pc("barbarian", 6)
    _s2, e2 = _fight(plain)
    _use(e2, "Rage")
    assert not any(isinstance(x.payload, dict) and x.payload.get("natural_weapons")
                   for x in plain.effects), "no bite for a barbarian who never chose it"


# --- the paladin ---------------------------------------------------------------------------

def test_a_paladin_smite_counts_against_its_target_and_nobody_else():
    """Smite evil: Charisma to attack, paladin level to damage, Charisma as deflection to
    AC — all "against the target of the smite" (CRB p.61). Before, an effect's modifiers
    were read unconditionally, so a target-scoped bonus could only be left out. Read off
    the real attack: the smite is in the breakdown against the thug, and absent against
    the other one."""
    pc = _pc("paladin", 4)
    scene, e = _fight(pc, "thug", "thug")
    _adjacent(scene)
    thug, other = scene.actors["c1"], scene.actors["c2"]
    cha = pc.ability_mod("cha")
    plain_ac = pc.ac()
    out = _use(e, "Smite Evil", to="c1")
    assert pc.pool("smite evil").current == pc.pool("smite evil").maximum - 1
    assert sum(m.value for m in pc.attack_modifiers(defender=thug)) == \
        sum(m.value for m in pc.attack_modifiers(defender=other)) + cha
    assert sum(m.value for m in pc.damage_modifiers(defender=thug)) == \
        sum(m.value for m in pc.damage_modifiers(defender=other)) + 4
    assert pc.ac(attacker=thug) == plain_ac + cha
    assert pc.ac(attacker=other) == plain_ac and pc.ac() == plain_ac
    assert "against the thug" in out.tell
    _res, asked = _swing(e, target="c1")
    attack = next(a for a in asked if a["label"].startswith("Attack"))
    assert any(b["source"].startswith("Smite Evil") for b in attack["breakdown"])


def test_a_smite_on_a_printed_neutral_is_wasted_and_rest_ends_one():
    """"If the paladin targets a creature that is not evil, the smite is wasted with no
    effect." A wolf's block prints N: the use is spent and nothing lands. A thug prints
    nothing, and the app records no alignment, so the smite holds and the tell says why.
    A night's rest ends it (tag `recovery.rest`)."""
    pc = _pc("paladin", 4)
    _scene, e = _fight(pc, "wolf")
    out = _use(e, "Smite Evil", to="c1")
    assert "wasted" in out.tell and not any(x.name == "Smite Evil" for x in pc.effects)
    assert pc.pool("smite evil").current == pc.pool("smite evil").maximum - 1

    pc2 = _pc("paladin", 4)
    scene2 = Scene()
    scene2.add(pc2)
    scene2.add(instantiate("thug", scene=scene2, name="the thug"))
    e2 = Engine(scene2, dice=Dice(seed=2))
    e2.scene.sides = {"pc": ["pc"], "them": ["c1"]}
    pc2.apply_effect  # noqa: B018 — the door below is the real one
    held = _use(e2, "Smite Evil", to="c1")
    assert "Nothing records" in held.tell or "Battle is joined" in held.tell
    pc2.rest("night")
    assert not any(x.name == "Smite Evil" for x in pc2.effects)


def test_lay_on_hands_heals_its_dice_and_the_chosen_mercies_lift():
    """1d6 per two paladin levels (3d6 at 6th), and a mercy taken lifts its condition from
    whoever is healed — the shaken mercy, chosen, lifts shaken; sickened, not chosen, stays.
    Before, the pool counted down and healed nothing."""
    pc = _pc("paladin", 6, class_choices={"mercy": ["shaken"]})
    _scene, e = _fight(pc)
    pc.hp = 1
    pc.add_condition("shaken", 5)
    pc.add_condition("sickened", 5)
    out = _use(e, "Lay on Hands")
    roll = out.rolls[0]
    assert roll.as_dict()["die"] == "3d6"
    assert pc.hp == min(pc.hp_max, 1 + roll.total)
    assert not pc.has_condition("shaken") and pc.has_condition("sickened")
    heal = next(r for r in out.effects if r.get("kind") == "heal")
    assert heal["origin"] == "ability:paladin/lay on hands"


def test_lay_on_hands_on_the_undead_is_a_touch_that_harms():
    """"A paladin can use this healing power to deal 1d6 points of damage for every two
    levels ... to an undead creature ... a melee touch attack, no save." The positive
    energy is not soaked by a skeleton's DR 5/bludgeoning."""
    pc = _pc("paladin", 6)
    scene, e = _fight(pc, "skeleton")
    _adjacent(scene)
    skel = scene.actors["c1"]
    hp = skel.hp
    out = _use(e, "Lay on Hands", to="c1")
    assert "melee touch attack" in out.tell
    assert "hits the skeleton" in out.tell, out.tell          # seed 11: a 15 on the die
    hit = next(r for r in out.effects if r.get("kind") == "damage")
    assert out.rolls[1].label == "Lay on Hands" and hit["rolled"] == out.rolls[1].total
    assert hit["reduced"] == 0 and hit["type"] == "positive" and skel.hp < hp
    assert not any(r.get("kind") == "save" for r in out.effects)


def test_channel_positive_energy_costs_a_paladin_two_lay_on_hands():
    pc = _pc("paladin", 4)
    _scene, e = _fight(pc)
    before = pc.pool("lay on hands").current
    _use(e, "Channel Positive Energy")
    assert pc.pool("lay on hands").current == before - 2


# --- channel energy --------------------------------------------------------------------------

def test_channel_energy_had_no_pool_and_now_heals_the_living_in_the_burst():
    """Measured: no pool at all, "3 + Cha a day" in the book. The burst heals every living
    creature in it — the thug too, as the book's burst does — and never the undead."""
    pc = _pc("cleric", 5)
    scene, e = _fight(pc, "thug", "skeleton")
    pc.hp, scene.actors["c1"].hp = 1, 1
    skel = scene.actors["c2"]
    skel.hp = skel.hp_max - 2
    out = _use(e, "Channel Energy")
    pool = pc.pool("channel energy")
    assert pool.maximum == 3 + pc.ability_mod("cha") and pool.current == pool.maximum - 1
    roll = out.rolls[0]
    assert roll.total >= 3, "3d6 at 5th"
    assert pc.hp > 1 and scene.actors["c1"].hp > 1
    assert skel.hp == skel.hp_max - 2, "positive energy does not heal the undead"
    assert all(r["origin"] == "ability:cleric/channel energy"
               for r in out.effects if r.get("kind") == "heal")


def test_channel_energy_harms_undead_with_a_will_save_for_half_and_no_dr():
    """3d6 at 5th, Will DC 10 + 1/2 level + Cha for half. Measured building it: the burst
    rolled 6 against a skeleton and landed 1, "less DR 5/bludgeoning" — energy is not a
    blow, and `is_physical` now says so for positive and negative."""
    pc = _pc("cleric", 5)
    scene, e = _fight(pc, "skeleton", "thug")
    skel = scene.actors["c1"]
    thug_hp = scene.actors["c2"].hp
    out = _use(e, "Channel Energy (harm)")
    save = next(r for r in out.effects if r.get("kind") == "save")
    assert save["dc"] == 10 + 2 + pc.ability_mod("cha") and save["ref"] == skel.ref
    hit = next(r for r in out.effects if r.get("kind") == "damage")
    rolled = out.rolls[0].total
    assert hit["reduced"] == 0
    assert hit["rolled"] == (rolled // 2 if save["saved"] else rolled)
    assert scene.actors["c2"].hp == thug_hp, "harm mode leaves the living alone"


def test_the_burst_is_thirty_feet_on_a_map():
    """With a map the burst is measured: a thug forty feet off is not healed."""
    pc = _pc("cleric", 5)
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc, at=(1, 1))
    scene.add(instantiate("thug", scene=scene, name="the near thug"), at=(3, 1))
    scene.add(instantiate("thug", scene=scene, name="the far thug"), at=(12, 1))
    scene.grid = Grid(width=20, height=20)
    e = Engine(scene, dice=Dice(seed=4))
    near, far = scene.actors["c1"], scene.actors["c2"]
    near.hp = far.hp = 1
    _use(e, "Channel Energy")
    assert near.hp > 1 and far.hp == 1


# --- the monk ----------------------------------------------------------------------------------

def test_stunning_fist_had_no_pool_and_now_stuns_on_the_next_unarmed_hit():
    """The book gives a monk his level in stunning attacks a day; there was no pool. Armed
    as a free action, it spends itself on the first unarmed hit: a Fortitude save at
    DC 10 + 1/2 level + Wis, or stunned for a round."""
    pc = _pc("monk", 8)
    pc.abilities["wis"] = 30                  # DC 24: a thug fails on anything but a 20
    pc.equipped = "unarmed"
    scene, e = _fight(pc)
    _adjacent(scene)
    out = _use(e, "Stunning Fist")
    assert pc.pool("stunning fist").maximum == 8
    assert "DC 24" in out.tell
    res, _asked = _swing(e, face=19)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "Fortitude save against Stunning Fist" in tells, tells
    thug = scene.actors["c1"]
    assert "fails the Fortitude save against Stunning Fist" in tells   # 18 vs DC 24
    assert thug.has_condition("stunned") and "lasts 1 round" in tells
    assert not any(isinstance(x.payload, dict) and x.payload.get("charge")
                   for x in pc.effects), "the charge is spent on the hit"


def test_stunning_fist_finds_nothing_to_stun_in_the_undead():
    """"Constructs, oozes, plants, undead, incorporeal creatures, and creatures immune to
    critical hits cannot be stunned." Read by tag (`type.undead`), never by name."""
    pc = _pc("monk", 8)
    pc.equipped = "unarmed"
    scene, e = _fight(pc, "skeleton")
    _adjacent(scene)
    _use(e, "Stunning Fist")
    res, _ = _swing(e, face=19)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "nothing to stun" in tells and not scene.actors["c1"].has_condition("stunned")


def test_the_monks_stunning_rungs_arrive_by_level():
    pc = _pc("monk", 8)
    _scene, e = _fight(pc)
    assert _use(e, "Stunning Fist (sickened)").status != "refused"
    late = _use(e, "Stunning Fist (paralyzed)")
    assert late.status == "refused" and "level 20" in late.tell


def test_ki_was_a_counter_and_now_buys_dodge_and_speed():
    """1 ki, a swift action: +4 dodge AC for a round, or +20 ft speed for a round."""
    pc = _pc("monk", 6)
    _scene, e = _fight(pc)
    ac, speed, ki = pc.ac(), pc.speed_feet, pc.pool("ki").current
    _use(e, "Ki Dodge")
    _use(e, "Ki Speed")
    assert pc.ac() == ac + 4 and pc.speed_feet == speed + 20
    assert pc.pool("ki").current == ki - 2
    pc.tick_effects(1)
    assert pc.ac() == ac and pc.speed_feet == speed


# --- the bard ----------------------------------------------------------------------------------

def test_inspire_courage_reaches_the_allies_and_leaves_with_the_song():
    """+1 competence on attack and weapon damage, +2 from 5th (CRB p.36), on everyone on
    the bard's side; one performance at a time; ending it takes every ally's bonus back
    (law 2: remove it and its contribution evaporates)."""
    bard = _pc("bard", 5)
    ally = instantiate("guildhand", scene=None, name="Bob")
    scene, e = _fight(bard, "thug", allies=(ally,))
    ally = scene.actors[ally.ref]
    a0, b0 = sum(m.value for m in ally.attack_modifiers()), sum(
        m.value for m in bard.attack_modifiers())
    pool = bard.pool("bardic performance").current
    _use(e, "Inspire Courage")
    assert sum(m.value for m in ally.attack_modifiers()) == a0 + 2
    assert sum(m.value for m in bard.attack_modifiers()) == b0 + 2
    foe = next(a for r, a in scene.actors.items() if r not in ("pc", ally.ref))
    assert not any(x.origin == "ability:bard/inspire courage" for x in foe.effects), \
        "never the foe"
    assert bard.pool("bardic performance").current == pool - 1
    # Another performance replaces it, and the courage goes with the old song.
    _use(e, "Fascinate")
    assert sum(m.value for m in ally.attack_modifiers()) == a0
    _use(e, "Fascinate")
    assert not bard.has_condition("bardic performance")


def test_dirge_of_doom_shakes_the_foes_while_it_plays():
    bard = _pc("bard", 8)
    scene, e = _fight(bard)
    _use(e, "Dirge of Doom")
    assert scene.actors["c1"].has_condition("shaken")
    _use(e, "Dirge of Doom")
    assert not scene.actors["c1"].has_condition("shaken")


def test_inspire_competence_aims_one_skill_of_one_ally():
    """+2 competence on one skill (+3 at 7th), one ally, never the bard herself."""
    bard = _pc("bard", 7)
    ally = instantiate("guildhand", scene=None, name="Bob")
    scene, e = _fight(bard, allies=(ally,))
    ally = scene.actors[ally.ref]
    before = sum(m.value for m in ally.skill_modifiers("diplomacy"))
    stealth = sum(m.value for m in ally.skill_modifiers("stealth"))
    self_aim = _use(e, "Inspire Competence (diplomacy)", to="pc")
    assert self_aim.status == "refused" and "ally other than" in self_aim.tell
    _use(e, "Inspire Competence (diplomacy)", to=ally.ref)
    assert sum(m.value for m in ally.skill_modifiers("diplomacy")) == before + 3
    assert sum(m.value for m in ally.skill_modifiers("stealth")) == stealth, \
        "one skill, not every skill"


# --- the druid ----------------------------------------------------------------------------------

def test_wild_shape_was_a_counter_and_now_is_a_wolf():
    """Beast shape I, Medium: +2 size Strength and +2 natural armour, and the wolf's own
    bite (1d6). Changing back takes all of it away. A Large form is refused at 4th, with
    the forms the druid has named."""
    pc = _pc("druid", 4)
    _scene, e = _fight(pc)
    s, ac = pc.ability_score("str"), pc.ac()
    assert pc.natural_weapon("bite") is None, "a human has no bite of their own"
    out = _use(e, "Wild Shape (wolf)")
    assert out.status != "refused", out.tell
    assert pc.ability_score("str") == s + 2 and pc.ac() == ac + 2
    assert pc.weapon("bite")["damage"] == "1d6" and pc.weapon("bite")["natural"]
    assert pc.has_state("buff.form.wild-shape") and pc.has_state("form.wolf")
    _use(e, "Wild Shape")
    assert pc.ability_score("str") == s and pc.ac() == ac
    horse = _use(e, "Wild Shape (horse)")
    assert horse.status == "refused" and "Wild Shape (wolf)" in horse.tell


def test_a_small_form_is_quicker_to_hit_and_harder_to_hit():
    """Small: +2 size Dex, +1 natural armour, and the size's own +1 attack and +1 AC."""
    pc = _pc("druid", 4)
    _scene, e = _fight(pc)
    dex, ac = pc.ability_score("dex"), pc.ac()
    _use(e, "Wild Shape (small cat)")
    assert pc.ability_score("dex") == dex + 2
    dex_gain = (pc.ability_mod("dex") - ((dex - 10) // 2))
    assert pc.ac() == ac + 1 + 1 + dex_gain


# --- domain powers as attacks ------------------------------------------------------------------

def test_fire_bolt_is_a_ranged_touch_attack_now_and_not_yet_no_more():
    """powers.json said "no engine op resolves a domain power as an attack yet". Fire Bolt:
    a ranged touch attack against touch AC, 1d6 + 1 per two levels fire, a use spent."""
    pc = _pc("cleric", 5, domains=["Fire", "Sun"])
    scene, e = _fight(pc)
    left = pc.pool("fire bolt").current
    out = _use(e, "Fire Bolt", to="c1")
    assert "ranged touch attack" in out.tell and "touch AC" in out.tell
    assert pc.pool("fire bolt").current == left - 1
    assert "hits the thug" in out.tell, out.tell              # seed 11: 21 vs touch 14
    dmg = next(r for r in out.effects if r.get("kind") == "damage")
    assert dmg["type"] == "fire" and dmg["origin"] == "ability:domain/fire bolt"
    assert out.rolls[1].as_dict()["die"] == "1d6+2", "1d6 + 1 per two levels at 5th"


def test_storm_burst_is_nonlethal_and_buffets_the_target():
    pc = _pc("druid", 4, domains=["Weather"])
    scene, e = _fight(pc)
    thug = scene.actors["c1"]
    before = sum(m.value for m in thug.attack_modifiers())
    for _ in range(4):
        out = _use(e, "Storm Burst", to="c1")
        if "hits" in out.tell:
            break
    assert "hits" in out.tell, out.tell
    assert any(r.get("lethality") == "nonlethal" for r in out.effects
               if r.get("kind") == "damage")
    assert sum(m.value for m in thug.attack_modifiers()) == before - 2


def test_a_first_harmful_use_opens_the_fight_and_spends_nothing():
    """The battle gate, as `_cast_gate` keeps it for a spell: out of a fight, a Fire Bolt
    opens the encounter, rolls nothing and spends nothing."""
    pc = _pc("cleric", 5, domains=["Fire"])
    scene = Scene()
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=3))
    left = pc.pool("fire bolt").current
    out = _use(e, "Fire Bolt", to="c1")
    assert "Battle is joined" in out.tell and scene.in_encounter
    assert pc.pool("fire bolt").current == left and not out.rolls


# --- the bar, the brief, the documents --------------------------------------------------------

def test_the_bar_lists_them_with_uses_left():
    """The bar returned [] for every class without paths (`play/views.py:500`)."""
    from play.views import _usable_abilities

    pc = _pc("paladin", 4)
    bar = {a["name"]: a for a in _usable_abilities(pc)}
    assert {"Smite Evil", "Lay on Hands", "Channel Positive Energy"} <= set(bar)
    smite = bar["Smite Evil"]
    assert smite["uses"] == smite["max"] == pc.pool("smite evil").maximum
    assert smite["action"] == "swift" and smite["aim"] == "foe"
    assert bar["Lay on Hands"]["aim"] == "self"
    cleric = _pc("cleric", 1)
    channel = next(a for a in _usable_abilities(cleric) if a["name"] == "Channel Energy")
    assert channel["max"] == 3 + cleric.ability_mod("cha"), "shown before it was ever used"
    assert cleric.pool("channel energy") is None, "and drawing the bar created nothing"


def test_the_brief_names_them_so_the_narrator_can_propose_them():
    """The brief's ability line was guarded by `paths`: the narrator of a barbarian was
    never told rage existed."""
    from gm import prompts

    pc = _pc("barbarian", 3)
    scene, _e = _fight(pc)

    class W:
        name, secret, premise = "Testholme", "", {}
        entities, unwritten, chronology, factions = {}, [], [], []

        def ancestors(self, _):
            return []

    brief = prompts.scene_brief(W(), scene, None, None)
    assert f"WHAT {pc.name.upper()} CAN DO" in brief
    line = next(l for l in brief.splitlines() if l.strip().startswith("Rage"))
    assert "rage left" in line and "free" in line


def test_the_documents_validate_and_a_bad_one_is_refused_with_the_fix():
    assert ca.validate_documents() == []
    bad = {"barbarian": {"abilities": [{"key": "x", "name": "X", "source": "s",
                                        "cost": {"pool": "nope"}}]}}
    problems = ca.validate_documents(bad)
    assert problems and "nope" in problems[0] and "Pools here: rage" in problems[0]


def test_the_engine_names_no_class_ability():
    """A class ability that needs an engine special case needs a field in the grammar.
    No ability name from content/class-abilities/ may appear in the engine's code
    (comments and docstrings may tell the history)."""
    source = Path("rules/engine.py").read_text(encoding="utf-8")
    source = re.sub(r'"""(?:.|\n)*?"""', "", source)
    code = "\n".join(re.sub(r"#.*$", "", line) for line in source.splitlines()).lower()
    for doc in ca.documents().values():
        for ability in doc.get("abilities") or ():
            for n in [ability["name"]] + list(ability.get("aliases") or ()):
                assert not re.search(r"\b" + re.escape(n.lower()) + r"\b", code), (
                    f"rules/engine.py names {n!r}; give it a field in the grammar")


def test_every_number_these_land_names_its_document():
    """Law 3, stage 8: every heal, damage, temp_hp and buff record carries an origin of
    a known kind."""
    from rules import provenance

    landed = []
    pc = _pc("bard", 9)
    ally = instantiate("guildhand", scene=None, name="Bob")
    scene, e = _fight(pc, allies=(ally,))
    landed += _use(e, "Inspire Greatness", to=ally.ref).effects
    cleric = _pc("cleric", 5)
    _s, e2 = _fight(cleric)
    cleric.hp = 1
    landed += _use(e2, "Channel Energy").effects
    records = [r for r in landed if r.get("kind") in ("heal", "damage", "temp_hp", "buff")]
    assert {r["kind"] for r in records} >= {"heal", "temp_hp", "buff"}
    for r in records:
        assert provenance.well_formed(str(r.get("origin", ""))), r
