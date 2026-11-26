"""Feat loop batch 3, lane b3-arcane (2026-11-26): the arcane class-feature hooks a playable
character can use, and the spell-hook and metamagic leftovers, proved through the engine.

Before this lane, measured on master 8258614b (0.5.2): none of the lane's 91 feats had a
document. Eldritch Heritage could not even be taken — its "Skill Focus with the class skill
of bloodline selected" was unparsed, so `feats.meets` answered "unknown" for everyone — and
a fighter holding it would have had no bloodline power to use: the granted-powers reader
asked only the class's own choice.
"""
from __future__ import annotations

import pytest

from rules import class_abilities, classbuilder, feats, grantedpowers
from tests.test_class_active_abilities import _fight, _pc, _use

HERITAGE = ["Skill Focus (perception)", "Eldritch Heritage (draconic red)"]


def test_the_lane_file_validates():
    import json
    from pathlib import Path

    doc = json.loads(Path("content/feats/mechanics/b3-arcane.json").read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


# --- Eldritch Heritage ------------------------------------------------------------------

def test_eldritch_heritage_can_be_taken_with_the_skill_focus_it_asks():
    """Measured 0.5.2: `meets` returned ok False, unknown ["Skill Focus with the class skill
    of bloodline selected for this feat (see below)"] for every character, so the feat and
    the two after it were untakeable."""
    pc = _pc("fighter", 3, feats=["Skill Focus (perception)"])
    pc.abilities["cha"] = 13
    assert feats.meets(pc, "eldritch-heritage")["ok"]
    bare = _pc("fighter", 3, feats=[])
    bare.abilities["cha"] = 13
    assert not feats.meets(bare, "eldritch-heritage")["ok"]


def test_a_fighter_with_eldritch_heritage_has_the_first_power_at_level_minus_two():
    """UM: the bloodline's 1st-level power, "using your character level - 2 as your
    effective sorcerer level". A 7th-level fighter with aberrant heritage spits Acidic
    Ray at sorcerer level 5: 1d6 + floor(5/2) = 1d6+2, never 1d6+3."""
    pc = _pc("fighter", 7, feats=["Skill Focus (knowledge (dungeoneering))",
                                  "Eldritch Heritage (aberrant)"])
    rows = grantedpowers.had(pc)
    assert [(r["power"]["key"], r["level"]) for r in rows] == [("acidic ray", 5)]
    ray = next(d for d in class_abilities._docs_for(pc) if d.get("key") == "acidic ray")
    assert ray["roll"]["bonus"] == "floor((level - 2) / 2)"


def test_no_power_without_the_bloodlines_own_skill_focus():
    """The pick's skill is asked when the power is read: Skill Focus (perception) is the
    draconic bloodline's, not the aberrant's."""
    pc = _pc("fighter", 7, feats=["Skill Focus (perception)", "Eldritch Heritage (aberrant)"])
    assert grantedpowers.had(pc) == []


def test_improved_heritage_breathes_at_character_level_minus_two_through_the_engine():
    """Improved Eldritch Heritage (breath weapon) on an 11th-level fighter, Cha 16: the
    draconic breath at sorcerer level 9 — 9d6 fire, Reflex DC 10 + 4 + 3 = 17 — spent
    from its own once-a-day pool and stamped with the bloodline power's origin."""
    pc = _pc("fighter", 11, feats=HERITAGE + ["Improved Eldritch Heritage (breath weapon)"])
    pc.abilities["cha"] = 16
    _scene, e = _fight(pc, "thug")
    out = _use(e, "Breath Weapon", to="c1")
    save = next(f for f in out.effects if f.get("kind") == "save")
    assert save["dc"] == 17
    assert "9d6" in out.tell
    spent = next(f for f in out.effects if f.get("kind") == "resource")
    assert (spent["pool"], spent["left"]) == ("breath weapon", 0)


def test_greater_heritage_lifts_every_heritage_power_to_character_level():
    """Greater: "treat your character level as your sorcerer level for all your sorcerer
    bloodline powers granted by this feat, Eldritch Heritage, and Improved"."""
    pc = _pc("fighter", 17, feats=HERITAGE + ["Improved Eldritch Heritage (breath weapon)",
                                              "Greater Eldritch Heritage (wings)"])
    got = {r["power"]["key"]: r["level"] for r in grantedpowers.had(pc)}
    assert got == {"claws": 17, "breath weapon": 17, "wings": 17}


def test_a_sorcerer_cannot_take_her_own_bloodline_again():
    """"Select one sorcerer bloodline. ... a bloodline you do not already have" — a
    draconic sorcerer naming draconic gets nothing twice."""
    pc = _pc("sorcerer", 5, feats=HERITAGE,
             class_choices={"bloodline": {"picks": [{"pick": "draconic", "variant": "red"}]}})
    assert [r["label"] for r in grantedpowers.had(pc)
            if "Eldritch" in r["label"]] == []


# --- documents on the existing grammar ----------------------------------------------------

from rules import casting, spells  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.grid import Grid  # noqa: E402
from rules.sheet import from_dict, situated  # noqa: E402


def _wren(feats=(), level=6, **extra):
    data = {"name": "Wren", "kind": "pc", "class": "wizard", "level": level,
            "abilities": {"str": 10, "dex": 14, "con": 12, "int": 16, "wis": 12, "cha": 12},
            "hp": 40, "weapons": ["dagger"], "equipped": "dagger",
            "feats": list(feats), "ranks": {"spellcraft": 2, "knowledge (arcana)": 2}}

    data.update(extra)
    return from_dict(data)


def _sum(mods, name=None) -> int:
    return sum(m.value for m in mods if name is None or m.source == name)


def test_tapestry_traveler_casts_teleportation_two_levels_higher():
    """PSP: "You cast spells of the teleportation subschool as though your caster level
    were 2 higher". Dimension door at a 9th-level wizard's CL 11; fireball stays at 9."""
    pc = _wren(["Tapestry Traveler"], level=9)
    assert casting.spell_caster_level(pc, spells.get("dimension-door")) == 11
    assert casting.spell_caster_level(pc, spells.get("fireball")) == 9


def test_mage_of_the_wild_is_two_better_in_its_own_terrain_only():
    """ARG: "+2 bonus on caster level checks, concentration checks, and Knowledge (arcana)
    and Spellcraft checks" in the terrain picked. Measured before: no document, +0 in the
    forest; and a feat's `bearer.terrain` could not name its own parenthetical."""
    pc = _wren(["Attuned to the Wild (forest)", "Mage of the Wild (forest)"])
    pc.at = "oldwood~forest"
    assert _sum(pc.concentration_modifiers({}), "Mage of the Wild") == 2
    assert _sum(pc.caster_level_check_modifiers({}), "Mage of the Wild") == 2
    assert _sum(pc.skill_modifiers("spellcraft"), "Mage of the Wild") == 2
    assert _sum(pc.skill_modifiers("knowledge (arcana)"), "Mage of the Wild") == 2
    pc.at = "town~urban"
    assert _sum(pc.concentration_modifiers({}), "Mage of the Wild") == 0
    assert _sum(pc.skill_modifiers("spellcraft"), "Mage of the Wild") == 0


def test_a_dispels_caster_level_check_now_reads_the_casters_terms():
    """Measured 0.5.2: the dispel's caster level check was a bare `Modifier(caster_level)`
    outside the funnel, so no feat on caster level checks reached it. Same seed, same die:
    the elf in her forest totals 2 more."""
    def total(feats):
        pc = _wren(feats)
        s = Scene()
        s.at = "oldwood~forest"
        s.add(pc)


        e = Engine(s, Dice(seed=4))
        fx, _ = e._spell_operation({"operation": "dispel", "check_dc": "30", "target": "x"},
                                   {"caster": pc.ref, "caster_level": 6})
        return next(f["total"] for f in fx if f["kind"] == "caster_level_check")
    assert total(["Mage of the Wild (forest)"]) == total([]) + 2


def _line(a, b, foe):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    for x in (a, b, foe):
        s.add(x)
    s.sides = {"us": [a.ref, b.ref], "them": [foe.ref]}
    s.positions.update({a.ref: (5, 5), b.ref: (5, 6), foe.ref: (9, 5)})
    return s


def test_shieldwall_phalanx_counts_the_adjacent_allies_who_hold_it():
    """Champions of Purity: a sacred bonus to AC against evil creatures' attacks and to
    saves against their spells "equal to the number of adjacent allies who also have this
    feat". One such ally: +1; the ally steps away: +0."""
    a = _wren(["Shieldwall Phalanx"])
    b = _wren(["Shieldwall Phalanx"], name="Bryn")
    foe = _wren([], name="Foe")
    s = _line(a, b, foe)
    with situated(s):
        assert _sum(a.ac_modifiers(attacker=foe), "Shieldwall Phalanx") == 1
        assert _sum(a.save_modifiers("will", {"attacker_actor": foe}),
                    "Shieldwall Phalanx") == 1
        s.positions[b.ref] = (15, 15)
        assert _sum(a.ac_modifiers(attacker=foe), "Shieldwall Phalanx") == 0


def test_duck_and_cover_takes_cover_behind_an_allys_shield_from_arrows_only():
    """APG: "+2 cover bonus to your AC against ranged attacks as long as your ally is
    wielding a shield" — the ally adjacent and holding the feat. No shield, no cover; a
    sword swing gets none."""
    a = _wren(["Duck and Cover"])
    b = _wren(["Duck and Cover"], name="Bryn", shield="heavy wooden shield")
    foe = _wren([], name="Foe")
    s = _line(a, b, foe)
    with situated(s):
        assert a.ac(against="ranged", attacker=foe) == a.ac(against="melee",
                                                            attacker=foe) + 2
        b.shield = "none"
        assert a.ac(against="ranged", attacker=foe) == a.ac(against="melee", attacker=foe)


# --- Vermin Heart, Exile's Path -----------------------------------------------------------

from rules import animals  # noqa: E402
from rules.bestiary import instantiate  # noqa: E402
from tests.test_feats_batch1_modifiers import Loaded  # noqa: E402


def _cast_at(caster, foe, spell, dice):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster)
    s.add(foe)
    s.initiative = [(caster.ref, 20), (foe.ref, 10)]
    s.sides = {"us": [caster.ref], "them": [foe.ref]}
    s.round, s.turn = 1, 0
    e = Engine(s, dice)

    raw = {"op": "cast", "actor": caster.ref, "target": foe.ref, "because": "test",
           "visibility": "hidden", "params": {"spell": spell}}
    res = e.run(e.validate([raw]))
    res.outcomes[0].said = " ".join(o.tell for o in res.outcomes)
    return res.outcomes[0]


def _druid(feats):
    d = _wren(feats, **{"class": "druid", "spellbook": ["hold-animal"],
                        "prepared": {"hold-animal": 2}})
    d.abilities["wis"] = 18
    return d


def test_vermin_heart_lets_wild_empathy_and_animal_spells_reach_vermin():
    """APG: "You may target vermin with spells and special abilities that only affect
    animals ... You may use wild empathy to influence vermin as easily as you influence
    animals." Measured before: a giant spider was "no animal" to hold animal and wild
    empathy refused it, feat or not."""
    spider = instantiate("giant-spider", name="the spider")
    assert animals.empathy_reaches(spider, _druid([])) is None
    assert animals.empathy_reaches(spider, _druid(["Vermin Heart"])) == 0
    held = spells.spared_by(spells.get("hold-animal"), spider, 4, _druid(["Vermin Heart"]))
    assert held == ""
    assert spells.spared_by(spells.get("hold-animal"), spider, 4, _druid([])) == "is no animal"


def test_vermin_heart_hold_animal_takes_hold_of_a_spider_through_the_cast():
    """The cast's own spare (`_rider_saves`) asks with the caster: without the feat the
    spider is told spared and makes no save; with it, it saves against the spell."""
    plain = _cast_at(_druid([]), instantiate("giant-spider", name="the spider"),
                     "hold-animal", Dice(seed=2))
    assert "no hold on" in plain.tell
    heart = _cast_at(_druid(["Vermin Heart"]), instantiate("giant-spider", name="the spider"),
                     "hold-animal", Dice(seed=2))
    assert "no hold on" not in heart.tell and "Will save" in heart.tell


def _charmer():
    pc = _wren([], level=5, **{"class": "sorcerer", "spellbook": ["charm-person"]})
    pc.abilities["cha"] = 18
    return pc



def _half_elf(feats):
    return from_dict({"name": "Ilse", "kind": "npc", "class": "fighter", "level": 3,
                      "abilities": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10,
                                    "cha": 10}, "hp": 25, "feats": list(feats)})


def test_exiles_path_rerolls_a_failed_will_save_against_an_enchantment():
    """ARG: "Once per day, when you fail a Will save against an enchantment spell or
    effect, you may reroll that saving throw, but must take the reroll result". Charm
    person (enchantment): the 2 fails, the reroll 19 stands. Before b3 a cast's saves
    carried no luck at all, so no reroll feat reached a spell's save."""
    out = _cast_at(_charmer(), _half_elf(["Exile's Path"]), "charm-person", Loaded(2, 19))
    assert "rolls again (Exile's Path): 2, then 19" in out.said
    assert "Ilse makes the Will save" in out.tell
    plain = _cast_at(_charmer(), _half_elf([]), "charm-person", Loaded(2, 19))
    assert "Ilse fails the Will save" in plain.tell



def test_exiles_path_is_not_offered_against_a_will_save_that_is_no_enchantment():
    """The same failed die against a will save from no enchantment: no reroll."""
    from rules import luck

    doc = {"id": "exile-s-path", "name": "Exile's Path"}
    entry = {"reroll": "any", "rolls": ["save.will"], "against": ["enchantment"]}
    assert luck.covers(entry, "save.will", ("spell", "enchantment", "charm"))
    assert not luck.covers(entry, "save.will", ("spell", "evocation"))
    assert not luck.covers(entry, "save.fort", ("spell", "enchantment"))
    assert doc


# --- Arcane Vendetta ----------------------------------------------------------------------

def test_arcane_vendetta_marks_an_arcane_caster_the_pc_identified():
    """ISWG: "+2 damage with weapon attacks made against any target you have witnessed
    casting an arcane spell ... in the last 5 rounds. You must have successfully identified
    the spell with a Spellcraft check". The hedge wizard's magic missile, identified on a
    20: he is marked for 5 rounds, told, and the PC's blows at him deal 2 more; missed on a
    1, nothing."""
    from tests.test_skill_uses_mind import _here, _wizard

    def cast(face):
        scene, engine, pc = _here(faces={"Spellcraft": face}, rest=10)
        pc.ranks["spellcraft"] = 1
        pc.feats = list(pc.feats) + ["Arcane Vendetta"]
        pc.hp = pc.hp_max = 500
        wiz = _wizard(scene)
        res = engine.run(engine.validate([{"op": "cast", "actor": "c2", "target": "pc",
                                           "params": {"spell": "magic-missile"},
                                           "visibility": "hidden"}]))
        return pc, wiz, next(o for o in res.outcomes if o.op == "cast")

    pc, wiz, out = cast(20)
    assert "marks the hedge wizard for Arcane Vendetta" in out.tell
    mark = next(e for e in wiz.effects if "mark.arcane-vendetta" in e.tags)
    assert mark.rounds_left == 5 and mark.origin == "feat:arcane-vendetta"
    assert _sum(pc._buff_mods("combat_mod", "damage", {"target_actor": wiz}),
                "Arcane Vendetta") == 2
    pc, wiz, out = cast(1)
    assert not wiz.has_state("mark.arcane-vendetta")
    assert _sum(pc._buff_mods("combat_mod", "damage", {"target_actor": wiz}),
                "Arcane Vendetta") == 0


# --- Sorcerous Bloodstrike ------------------------------------------------------------------

def _red_sorcerer(feats, level=2):
    pc = _wren(feats, level=level, **{"class": "sorcerer", "spellbook": ["magic-missile"],
                                  "class_choices": {"bloodline": {"picks": [
                                      {"pick": "draconic", "variant": "red"}]}}})
    pc.abilities["cha"] = 18
    return pc


def test_sorcerous_bloodstrike_gives_a_spent_claw_back_for_a_kill_by_spell():
    """UM: "upon reducing a creature to 0 or fewer hit points with one of your sorcerer
    spells, you can regain one usage of a sorcerer bloodline power that has a limited
    number of uses per day", once a day, for a creature of at least half the sorcerer's
    level in Hit Dice. A 2nd-level red-dragon sorcerer who has spent one round of claws
    kills a 1-HD thug with magic missile: the round comes back, and only once; at 4th
    level the thug has too few Hit Dice."""
    pc = _red_sorcerer(["Sorcerous Bloodstrike"])
    claws = pc.pool("claws")
    claws.current = claws.maximum - 1
    thug = instantiate("thug", name="the thug")
    thug.hp = 1

    out = _cast_at(pc, thug, "magic-missile", Dice(seed=3))
    assert "Sorcerous Bloodstrike" in out.tell
    assert claws.current == claws.maximum
    assert pc.pool("sorcerous-bloodstrike").current == 0


def test_no_bloodstrike_without_the_feat_or_with_nothing_spent():
    pc = _red_sorcerer([])
    claws = pc.pool("claws")
    claws.current = claws.maximum - 1
    thug = instantiate("thug", name="the thug")
    thug.hp = 1
    _cast_at(pc, thug, "magic-missile", Dice(seed=3))
    assert claws.current == claws.maximum - 1
    full = _red_sorcerer(["Sorcerous Bloodstrike"])
    thug = instantiate("thug", name="the thug")
    thug.hp = 1
    out = _cast_at(full, thug, "magic-missile", Dice(seed=3))
    assert "Bloodstrike" not in out.tell
    high = _red_sorcerer(["Sorcerous Bloodstrike"], level=4)
    high.pool("claws").current -= 1
    thug = instantiate("thug", name="the thug")
    thug.hp = 1
    out = _cast_at(high, thug, "magic-missile", Dice(seed=3))
    assert "Bloodstrike" not in out.tell


# --- Echoing Spell ----------------------------------------------------------------------------

def test_echoing_spell_casts_once_more_today_without_a_slot():
    """UM: "you can cast it one additional time during that day ... this second casting
    does not require you to prepare it in another spell slot", in a slot three levels
    higher. A 9th-level wizard prepares one echoing magic missile (a 4th-level slot): it
    is cast, the echo stays, the second missile is cast with no slot and no copy, and the
    third is refused. A night's sleep clears an unused echo."""
    pc = _wren(["Echoing Spell"], level=9, spellbook=["magic-missile"],
               prepared={"magic-missile+echoing-spell": 1})
    assert casting.prepared_count(pc, casting.metamagic_key("magic-missile",
                                                            ["echoing-spell"])) == 1
    thug = instantiate("thug", name="the thug")
    thug.hp_max = thug.hp = 500
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(thug)
    s.initiative = [(pc.ref, 20), (thug.ref, 10)]
    s.sides = {"us": [pc.ref], "them": [thug.ref]}
    s.round, s.turn = 1, 0
    e = Engine(s, Dice(seed=1))

    def cast(**params):
        raw = {"op": "cast", "actor": pc.ref, "target": thug.ref, "because": "test",
               "visibility": "hidden", "params": {"spell": "magic-missile", **params}}
        return e.run(e.validate([raw])).outcomes[0]

    slots = pc.pool(casting.slot_pool(4)).current
    first = cast(metamagic=["echoing-spell"])
    assert "echoes in Wren's memory" in first.tell
    assert pc.has_state(casting.echo_tag("magic-missile"))
    assert pc.pool(casting.slot_pool(4)).current == slots - 1
    left1 = pc.pool(casting.slot_pool(1)).current
    second = cast()
    assert second.status == "resolved"
    assert not pc.has_state(casting.echo_tag("magic-missile"))
    assert pc.pool(casting.slot_pool(1)).current == left1
    with pytest.raises(Exception):
        cast()
    # An unused echo is gone in the morning.
    e._echo_left(
type("I", (), {"actor": pc.ref, "params": {"metamagic": ["echoing-spell"]}})(),
                 type("O", (), {"effects": [{"kind": "cast", "spell": "magic-missile"}],
                                "tell": ""})())
    assert pc.has_state(casting.echo_tag("magic-missile"))
    pc.clear_states("recovery.rest")
    assert not pc.has_state(casting.echo_tag("magic-missile"))



# --- Tenebrous Spell --------------------------------------------------------------------------

def _night_cast(minute, meta=(), seed=5):
    pc = _wren(["Tenebrous Spell"], level=7, spellbook=["burning-hands"],
               prepared={"burning-hands": 1, "burning-hands+tenebrous-spell": 1})
    thug = instantiate("thug", name="the thug")
    thug.hp_max = thug.hp = 500
    s = Scene()
    s.at = "oldwood~forest"
    s.clock_minutes = minute
    s.add(pc)
    s.add(thug)
    s.initiative = [(pc.ref, 20), (thug.ref, 10)]
    s.sides = {"us": [pc.ref], "them": [thug.ref]}
    s.round, s.turn = 1, 0
    e = Engine(s, Dice(seed=seed))
    raw = {"op": "cast", "actor": pc.ref, "target": thug.ref, "because": "test",
           "visibility": "hidden",
           "params": {"spell": "burning-hands", "metamagic": list(meta)}}
    return e, e.run(e.validate([raw])).outcomes[0]


def test_tenebrous_spell_is_a_level_stronger_in_the_dark_only():
    """ISM: "When you cast a tenebrous spell in darkness or dim light, the spell's
    effective caster level and any associated save DCs are increased by 1". A forest at
    night is dim: burning hands at DC 14 (Int 16) and caster level 7 becomes DC 15 at
    caster level 8; the same spell plain stays DC 14."""
    e, plain = _night_cast(23 * 60)
    assert e._caster_light(e.scene.actors["wren"]) == "dim"
    assert "DC 14" in plain.tell and "caster level 7" in plain.tell
    _, dark = _night_cast(23 * 60, ["tenebrous-spell"])
    assert "DC 15" in dark.tell and "caster level 8" in dark.tell


def test_tenebrous_spell_in_bright_light_needs_concentration():
    """ISM: "Casting a tenebrous spell in bright light is difficult, and requires a
    concentration check (DC 15 + twice the tenebrous spell's effective spell level)":
    burning hands in a 2nd-level slot at noon is DC 19, rolled, and no light bonus."""
    e, noon = _night_cast(12 * 60, ["tenebrous-spell"])
    assert e._caster_light(e.scene.actors["wren"]) == "bright"
    assert "DC 19" in noon.tell and "bright light" in noon.tell
    assert "DC 15;" not in noon.tell



def test_tenebrous_cannot_take_a_light_spell_and_costs_nothing_on_darkness():
    """"You cannot use this feat on spells with the light descriptor"; a darkness spell
    pays no extra slot level."""
    from rules import metamagic

    pc = _wren(["Tenebrous Spell"], level=7)
    assert "light descriptor" in metamagic.refusal(pc, spells.get("light"),
                                                   ["tenebrous-spell"], spontaneous=False)
    assert metamagic.levels(pc, ["tenebrous-spell"], spells.get("darkness")) == 0
    assert metamagic.levels(pc, ["tenebrous-spell"], spells.get("burning-hands")) == 1


# --- Blood Ties -------------------------------------------------------------------------------

def test_blood_ties_lets_a_draconic_gnome_bluff_where_she_would_plead_with_a_dragon():
    """GoG: "When attempting a Diplomacy check to influence a creature with a plausible
    connection to your sorcerous bloodline, you may instead make a Bluff check ... a gnome
    sorcerer with the draconic bloodline may use this feat against dragons and their kin,
    but no other creatures." Bluff +9 against Diplomacy +1: the pseudodragon is talked to
    with the Bluff; the thug is not."""
    pc = _red_sorcerer(["Blood Ties"], level=4)
    pc.ranks = {"bluff": 4}
    pc.abilities["cha"] = 18
    e = Engine(Scene(), Dice(seed=1))
    plain = list(pc.skill_modifiers("diplomacy"))
    kin = e._blood_ties(pc, instantiate("pseudodragon", name="the pseudodragon"), plain)
    assert sum(m.value for m in kin) == sum(m.value for m in pc.skill_modifiers("bluff"))
    assert all("Blood Ties" in m.source for m in kin)
    assert e._blood_ties(pc, instantiate("thug", name="the thug"), plain) == plain
    assert e._blood_ties(_red_sorcerer([], level=4),
                         instantiate("pseudodragon", name="p"), plain) == plain


def test_blood_ties_reaches_the_roll_of_a_real_influence_check():
    """Through the check op the table sends: the Diplomacy roll at the pseudodragon is
    made of the Bluff's terms, each labelled for the popup."""
    pc = _red_sorcerer(["Blood Ties"], level=4)
    pc.ranks = {"bluff": 4}
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    d = s.add(instantiate("pseudodragon", scene=s, name="the pseudodragon"))
    e = Engine(s, Dice(seed=2))
    res = e.run(e.validate([{"op": "check", "actor": pc.ref, "target": d.ref,
                             "visibility": "hidden", "because": "test",
                             "params": {"skill": "diplomacy"}}], origin="author:test"))
    terms = [m.source for o in res.outcomes for r in o.rolls for m in r.modifiers]
    assert terms and all("(Bluff, Blood Ties)" in t for t in terms)
