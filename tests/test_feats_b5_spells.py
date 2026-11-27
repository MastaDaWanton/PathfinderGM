"""Feat loop batch 5, lane b5-spells (2026-11-26): spell hooks, metamagic and the situational
modifiers left in the loop's list, proved through the engine.

Before this lane, measured on integrate/feats-b4 e3c9d166: none of the lane's 51 feats had a
document. A threnodic cause fear on a skeleton was refused twice over ("not a living
creature", then immune to mind-affecting effects); circle of death on a zombie read "immune
to undead traits" whatever the caster held; Guardian of the Wild could not even say which
terrain it meant, because the terrain is Attuned to the Wild's parenthetical, not its own.
"""
from __future__ import annotations

import json
from pathlib import Path

from rules import alchemist as al
from rules import classbuilder, effectspec, spell_feats, spells, surprise
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from tests.test_cast_choices import caster
from tests.test_feats_b3_arcane import _sum, _wren

META = ["Threnodic Spell", "Coaxing Spell", "Thanatopic Spell"]


def test_the_lane_file_validates():
    doc = json.loads(Path("content/feats/mechanics/b5-spells.json").read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


# --- Threnodic, Coaxing, Thanatopic --------------------------------------------------------

def _cast(meta, foe_t, spell="cause-fear", seed=3):
    pc = caster(cls="sorcerer", level=17, book=(spell,), feats=META)
    foe = instantiate(foe_t, name="the foe")
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(foe)
    s.initiative = [(pc.ref, 20), (foe.ref, 10)]
    s.sides = {"us": [pc.ref], "them": [foe.ref]}
    s.round, s.turn = 1, 0
    e = Engine(s, Dice(seed=seed))
    raw = {"op": "cast", "actor": pc.ref, "target": foe.ref, "because": "test",
           "visibility": "hidden", "params": {"spell": spell, "metamagic": list(meta)}}
    res = e.run(e.validate([raw]))
    return foe, " ".join(o.tell for o in res.outcomes)


def test_threnodic_cause_fear_frightens_a_skeleton_and_no_living_foe():
    """UM: "affects undead creatures (even mindless undead) as if they weren't immune to
    mind-affecting effects, but has no effect on living creatures." Measured before: the
    plain cast told "the foe is not a living creature" and frightened nobody; the thug,
    the cast's living target, is frightened by the plain spell and untouched by the
    threnodic one."""
    skel, plain = _cast([], "skeleton")
    assert "not a living creature" in plain and not skel.has_state("state.fear")
    skel, told = _cast(["threnodic"], "skeleton")
    assert skel.has_state("state.fear.frightened"), told
    thug, told = _cast(["threnodic"], "thug")
    assert "has no hold on the foe" in told and not thug.has_state("state.fear")


def test_coaxing_reaches_a_mindless_ooze_and_nothing_else():
    """Dungeoneer's Handbook: "affects mindless oozes and vermin as if they weren't
    mindless, but has no effect on other creature types". The gelatinous cube is immune to
    the plain cast (no Int score) and frightened by the coaxing one."""
    cube, plain = _cast([], "gelatinous-cube")
    assert "mindless" in plain and not cube.has_state("state.fear")
    cube, _ = _cast(["coaxing"], "gelatinous-cube")
    assert cube.has_state("state.fear.frightened")
    thug, told = _cast(["coaxing"], "thug")
    assert not thug.has_state("state.fear") and "has no hold" in told


def test_threnodic_and_coaxing_take_only_a_mind_affecting_spell():
    from rules import metamagic

    pc = caster(cls="sorcerer", level=9, book=("fireball",), feats=META)
    why = metamagic.refusal(pc, spells.get("fireball"), ["threnodic-spell"], spontaneous=True)
    assert "not a mind-affecting spell" in why
    assert metamagic.levels(pc, ["threnodic-spell", "coaxing-spell"]) == 4


def test_thanatopic_circle_of_death_slays_an_undead():
    """UM: "pierces defenses and immunities that protect against death effects ... Undead
    are susceptible". Measured before: "the foe is immune to undead traits and is not
    dead" on every circle of death at a skeleton."""
    skel, plain = _cast([], "skeleton", spell="circle-of-death")
    assert "immune to undead traits" in plain and not skel.is_dead
    skel, told = _cast(["thanatopic"], "skeleton", spell="circle-of-death")
    assert skel.is_dead, told


# --- terrain, shield and save modifiers ---------------------------------------------------

def test_guardian_of_the_wild_is_two_dodge_in_the_attuned_terrain_only():
    """ARG: "When you are in a terrain type you have selected the Attuned to the Wild feat
    for, you gain a +2 dodge bonus to Armor Class." Before, no clause could name the
    other feat's terrain."""
    pc = _wren(["Attuned to the Wild (forest)", "Guardian of the Wild"])
    pc.at = "oldwood~forest"
    assert _sum(pc.ac_modifiers(), "Guardian of the Wild") == 2
    pc.at = "town~urban"
    assert _sum(pc.ac_modifiers(), "Guardian of the Wild") == 0


def test_spirit_of_the_wild_sharpens_the_surprise_round():
    """ARG: "+4 bonus on Perception checks made to act in the surprise round ... If you
    act in the surprise round, you gain blindsense out to a range of 30 feet during the
    surprise round", in the attuned terrain. The ambush roll names its use
    (rules/surprise.py) and the sense is laid for the one round."""
    pc = _wren(["Attuned to the Wild (forest)", "Guardian of the Wild", "Spirit of the Wild"])
    pc.at = "oldwood~forest"
    assert _sum(pc.skill_modifiers("perception", ctx={"skill_use": "ambush"}),
                "Spirit of the Wild") == 4
    assert _sum(pc.skill_modifiers("perception"), "Spirit of the Wild") == 0
    surprise._surprise_senses(pc)
    assert pc.has_state("sense.blindsense.30")
    away = _wren(["Attuned to the Wild (forest)", "Spirit of the Wild"])
    away.at = "town~urban"
    surprise._surprise_senses(away)
    assert not away.has_state("sense.blindsense")


def test_covering_shield_adds_the_shield_and_its_feats_to_reflex_against_areas():
    """Dragonslayer's Handbook: "a bonus on Reflex saves against area of effect attacks
    equal to your shield's base bonus to armor class plus any bonuses granted by feats".
    A heavy shield (+2) and Shield Focus (+1) are +3 against a fireball, +0 against a
    ray's save, and nothing with the shield off."""
    f = _wren(["Shield Focus", "Covering Shield"], shield="heavy shield",
              **{"class": "fighter"})
    fireball = effectspec.spell_against(spells.get("fireball"))
    assert "area" in fireball
    assert _sum(f.save_modifiers("ref", {"against": fireball}), "Covering Shield") == 3
    assert _sum(f.save_modifiers("ref", {"against": ("spell",)}), "Covering Shield") == 0
    f.shield = "none"
    assert _sum(f.save_modifiers("ref", {"against": fireball}), "Covering Shield") == 0


def test_schooled_resolve_adds_bravery_against_a_vampires_charm_not_its_fear():
    """Blood of the Night: "add your bravery bonus on Will saves against mind-affecting
    spells and effects from vampires. This does not stack with the normal bravery bonus
    on saves against fear effects." A vampire's charm person is vampire_mind; its cause
    fear is bravery's alone; a thug's charm is neither."""
    vamp = instantiate("vampire", name="the vampire")
    thug = instantiate("thug", name="the thug")
    words = Engine._spell_source_words(vamp, spells.get("charm-person"))
    assert spell_feats.VAMPIRE_MIND in words
    assert spell_feats.VAMPIRE_MIND not in Engine._spell_source_words(
        vamp, spells.get("cause-fear"))
    assert spell_feats.VAMPIRE_MIND not in Engine._spell_source_words(
        thug, spells.get("charm-person"))
    g = _wren(["SchooledResolve"], level=6, **{"class": "fighter"})
    ctx = {"against": effectspec.spell_against(spells.get("charm-person")) + words}
    assert _sum(g.save_modifiers("will", ctx), "SchooledResolve") == 2


def test_divine_deception_reads_the_devices_tradition():
    """Faction Guide: "+5 bonus on Use Magic Device checks to use divine spell-trigger or
    spell completion items". Through the engine: the rogue's UMD at a scroll of cure light
    wounds (divine) carries the +5; at mage armour (arcane) it does not."""
    from rules import spellitems
    from rules.sheet import load_pc

    seen = {}
    for spell in ("cure-light-wounds", "mage-armor"):
        pc = load_pc("fixtures/pc-kesst.json")
        pc.ref, pc.kind = "pc", "pc"
        pc.feats = list(pc.feats) + ["Divine Deception"]
        spare = next(k for k, v in pc.ranks.items() if v)
        pc.ranks[spare] -= 1
        pc.ranks["use magic device"] = 1
        pc.add_stock(spellitems.make("scroll", spell, how="bought"), 1)
        s = Scene(location_id="5bbd0c40345f")
        s.add(pc)
        e = Engine(s, Dice(seed=11))
        name = next(v.name for v in pc.stock.values() if spellitems.kind_of(v))
        res = e.run(e.validate([{"op": "use_item", "actor": "pc",
                                 "params": {"item": name, "power": spell}}]))
        umd = [r for o in res.outcomes for r in o.rolls
               if r.label.startswith("Use Magic Device (")]
        seen[spell] = any(m.source == "Divine Deception" for m in umd[0].modifiers)
    assert seen == {"cure-light-wounds": True, "mage-armor": False}


def test_meditative_concentration_rides_combat_meditation_only():
    """F&P: "For 1 round per character level after you perform combat meditation ... a
    concentration check ... or a Fortitude save to resist a distraction effect (such as
    the distraction ability of a swarm), you gain a +4 bonus". The combat meditation lays
    meditation.combat for those rounds; an hour's meditation (meditation.held alone) does
    not count."""
    from tests.test_class_active_abilities import _fight, _pc, _use

    pc = _pc("monk", 5, feats=["Combat Meditation", "Meditation Master",
                               "Meditative Concentration"])
    pc.abilities["wis"] = 16
    assert _sum(pc.concentration_modifiers({}), "Meditative Concentration") == 0
    _scene, e = _fight(pc, "thug")
    out = _use(e, "Combat Meditation")
    assert pc.has_state("meditation.combat"), out.tell
    assert _sum(pc.concentration_modifiers({}), "Meditative Concentration") == 4
    assert _sum(pc.save_modifiers("fort", {"against": ("distraction",)}),
                "Meditative Concentration") == 4
    assert _sum(pc.save_modifiers("fort", {"against": ("poison",)}),
                "Meditative Concentration") == 0


def test_a_swarms_distraction_save_is_against_distraction():
    """The swarm's Fortitude save names what it resists, so Meditative Concentration's
    clause has a roll to land on (Engine._distraction runs its save as `distraction`)."""
    from rules.intents import Intent

    s = Scene(location_id="5bbd0c40345f")
    pc = _wren(["Meditative Concentration"])
    s.add(pc)
    e = Engine(s, Dice(seed=2))
    seen = {}
    real = pc.save_modifiers

    def spy(save, ctx=None):
        seen["ctx"] = ctx
        return real(save, ctx)
    pc.save_modifiers = spy
    e._run_within(e.validate([{"op": "save", "actor": pc.ref, "visibility": "hidden",
                               "because": "rats", "params": {"save": "fort", "dc": 12}}],
                             origin="creature:rat-swarm", origin_name="distraction"))
    assert "distraction" in seen["ctx"]["against"]
    assert Intent


# --- the alchemy bench --------------------------------------------------------------------

def test_master_alchemist_bottles_a_book_formula_in_a_tenth_of_the_time():
    """APG: "you may create mundane alchemical items much more quickly than normal ... use
    the item's gp value as its sp value": alchemist's fire bottled from a dissolved
    brimstone takes a tenth of the minutes with the feat; the +2 lands on Craft."""
    from tests.test_alchemy_bench import _make, _pc as _alch, _plan

    times = {}
    for held in ([], ["Master Alchemist"]):
        pc = _alch(1, brimstone=1, lamp_oil=1, clay_flask=2)
        pc.feats = list(pc.feats) + held
        _p, landed = _make(pc, "dissolve", {"inputs": ["inv:brimstone"],
                                            "solvent": "inv:lamp-oil"})
        plan = _plan(pc, "bottle", {"inputs": [f"stock:{landed[0]['key']}"],
                                    "vessel": "inv:clay-flask", "formula": "alchemists-fire"})
        times[bool(held)] = plan.minutes
        if held:
            assert _sum(pc.skill_modifiers("craft"), "Master Alchemist") == 2
    assert times[True] == -(-times[False] // 10) and times[True] < times[False]
    assert al.ALCHEMY_MASTER == "craft.alchemy.master"


# --- weapons, devices, lights, the cold -----------------------------------------------------

def test_legacy_of_the_crusade_is_one_sacred_with_a_good_weapon():
    """Champions of Purity: "When using good-aligned weapons ... a +1 sacred bonus on
    damage rolls". A blade that strikes as good carries it; a plain one does not."""
    pc = _wren(["Legacy of the Crusade"], level=6, **{"class": "paladin"})
    plain = pc._roll_context("dagger")
    assert plain["weapon"]["good"] is False
    assert _sum(pc._feat_mods("combat_mod", "damage", plain), "Legacy of the Crusade") == 0
    holy = {**plain, "weapon": {**plain["weapon"], "good": True}}
    assert _sum(pc._feat_mods("combat_mod", "damage", holy), "Legacy of the Crusade") == 1


def test_torch_handling_widens_a_carried_torch_by_ten_feet():
    """Dungeoneer's Handbook: "the radius of normal and increased illumination shed by any
    torch or mundane light source you carry increases by 10 feet": a torch's 20/40 is 30/50
    in the hand of a holder, 20/40 in anyone else's."""
    from rules.activeeffect import ActiveEffect
    from rules.grid import Grid

    for held, want in (([], (20, 40)), (["Torch Handling"], (30, 50))):
        pc = _wren(held)
        s = Scene(location_id="5bbd0c40345f", grid=Grid(10, 10))
        s.add(pc)
        s.positions[pc.ref] = (2, 2)
        pc.apply_effect(ActiveEffect(name="torch", kind="effect", key="light.carried",
                                     source="torch", origin="item:torch", duration="rounds",
                                     rounds_left=600, tags=("light.carried",),
                                     payload={"light": {"radius_ft": 20, "raised_ft": 40}}))
        assert [lit[1:3] for lit in s.lights()] == [want]


def test_cold_celerity_quickens_for_the_round_after_cold_damage():
    """People of the North: "the same bonuses for 1 round after any round in which you take
    cold damage": +2 initiative and +1 attack, laid by the cold that got through, and not
    by fire."""
    pc = _wren(["Endurance", "Cold Celerity"])
    pc.take_damage(3, "fire")
    assert _sum(pc.attack_modifiers(), "Cold Celerity") == 0
    pc.take_damage(3, "cold")
    assert _sum(pc.attack_modifiers(), "Cold Celerity") == 1
    assert _sum(pc.initiative_modifiers(), "Cold Celerity") == 2


def test_smell_fear_finds_the_frightened_by_scent():
    """APG: "+4 bonus on Perception checks to detect creatures with the shaken, frightened,
    or panicked conditions using scent" — against a shaken thug, not a calm one, and only
    with scent (Keen Scent's tag)."""
    pc = _wren(["Keen Scent", "Smell Fear"], race="half-orc")
    thug = instantiate("thug", name="the thug")
    assert _sum(pc.skill_modifiers("perception", ctx={"target_actor": thug}),
                "Smell Fear") == 0
    thug.add_condition("shaken", rounds=3, source="test")
    assert _sum(pc.skill_modifiers("perception", ctx={"target_actor": thug}),
                "Smell Fear") == 4
    pc.feats = ["Smell Fear"]
    assert _sum(pc.skill_modifiers("perception", ctx={"target_actor": thug}),
                "Smell Fear") == 0
