"""Group 9 of the 2026-09-19 fix pass: a crowd as one thing.

Asked for in as many words (docs/playtest-2026-09-18.md item 33): *"A crowd of people
should be spawned as a single unit with the combined hp of all its members, it should take
up however many squares the people would take up, find a way to display this and allow for
them to be killed giving xp, run away and scatter."*

It is a design REVERSAL, not a gap. `bestiary.split_collective_name` turns "a pair of
guards" into two actors and its docstring records why: a single 11-hp actor called "pair of
guards" meant the player "fought half as many people as the fiction described". That was
right for two guards and wrong for a crowd, so the line between them is the member count
(`troops.UNIT_FROM`) and the old ruling still holds below it.

Three traditions, each supplying what the others lack — the Pathfinder troop subtype for
the shape, 13th Age's mooks for the shared pool and the attrition, Basic D&D's morale for
running away — and what was actually missing from this app was the rule set: `xp.worth`
paid one all-or-nothing award per fallen actor and nothing at all for a rout.
"""
from __future__ import annotations

import inspect

import pytest

from gm import judgement
from rules import troops, xp
from rules.bestiary import instantiate, split_collective_name
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.guards import Packet
from rules.sheet import from_dict, load_pc, to_dict
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def table():
    scene = Scene(location_id=VORMOOR)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene, Engine(scene, Dice(seed=5), world=WORLD)


def _hit(engine, unit, amount, traits=()):
    return engine._land(Packet(amount=amount, dtype="slashing", traits=tuple(traits),
                               lethality="lethal", target=unit.ref))


# --- the shape ---------------------------------------------------------------------------

def test_a_crowd_is_one_actor_with_the_combined_hit_points_of_its_members(table):
    """13th Age's mob: "a collective HP pool equal to the sum of the HP of the mooks in the
    mob". Twelve raiders at 29 each is 348, and the bestiary's Raider has shipped at 29 hp
    all along — it was reachable by `spawn` and by nothing else."""
    scene, _ = table
    unit = troops.form("raider", 12, scene=scene)
    assert unit.troop is not None
    assert unit.troop.members == 12 and unit.troop.member_hp == 29
    assert unit.hp == unit.hp_max == 348
    assert unit.name == "twelve raiders"
    # And it fights like a raider, because it is built out of one: the block's numbers
    # stand for the whole, which is how Pathfinder's own troops are put together.
    assert unit.from_template == "raider"


def test_the_unit_takes_up_as_many_squares_as_the_people_would(table):
    """The player's ruling in place of the troop subtype's fixed 20-by-20 square: "it should
    take up however many squares the people would take up". Pathfinder gives every troop a
    Gargantuan footprint whatever its numbers, and a band of three filling one would be the
    opposite of what was asked."""
    scene, _ = table
    assert troops.size_for(1) == "medium"
    assert troops.size_for(4) == "large"
    assert troops.size_for(9) == "huge"
    assert troops.size_for(12) == "gargantuan"      # 4x4, four squares to spare
    assert troops.size_for(30) == "colossal"
    unit = troops.form("raider", 12, scene=scene)
    assert unit.size == "gargantuan"
    from rules import grid

    assert len(grid.footprint((0, 0), unit.size)) == 16


def test_a_handful_still_arrives_as_people(table):
    """The reversal has a line and this is it. Below five they arrive as themselves, because
    the earlier ruling was right there: one 11-hp actor called "pair of guards" meant the
    player fought half as many people as the fiction described."""
    scene, engine = table
    engine.run(engine.validate([{"op": "spawn", "because": "two of them",
                                 "params": {"template": "thug", "count": 2}}]))
    bodies = [a for a in scene.actors.values() if not a.is_pc]
    assert len(bodies) == 2
    assert all(a.troop is None for a in bodies)
    assert troops.UNIT_FROM == 5


def test_a_spawn_of_five_or_more_arrives_as_one_unit(table):
    scene, engine = table
    engine.run(engine.validate([{"op": "spawn", "because": "the band",
                                 "params": {"template": "raider", "count": 8}}]))
    bodies = [a for a in scene.actors.values() if not a.is_pc]
    assert len(bodies) == 1
    assert bodies[0].troop.members == 8
    assert bodies[0].hp == 8 * 29


# --- the attrition ----------------------------------------------------------------------

def test_every_members_worth_of_damage_takes_one_of_them_off_their_feet(table):
    """13th Age: "every time the mob takes one mook's worth of damage, one mook dies", with
    the excess cascading. That is what makes the unit visibly shrink, and the shrinking is
    the "scatter" the request asks to see."""
    scene, engine = table
    unit = troops.form("raider", 12, scene=scene)
    scene.add(unit)
    eff = _hit(engine, unit, 29)
    assert eff["fell"] == 1 and eff["members"] == 11
    assert unit.size == "gargantuan"
    # Excess cascades: 87 is three raiders' worth.
    eff = _hit(engine, unit, 87)
    assert eff["fell"] == 3 and eff["members"] == 8
    assert unit.size == "huge", "eight fit in a 3x3; the footprint shrinks with them"
    assert "3 raiders go down" in eff["unit_note"]
    assert "8 of twelve raiders still stand" in eff["unit_note"]


def test_one_hit_point_left_is_still_somebody_standing(table):
    scene, _ = table
    unit = troops.form("guard", 4, scene=scene)
    assert troops.members_left(1, unit.troop.member_hp) == 1, "rounded up: they still swing"
    assert troops.members_left(0, unit.troop.member_hp) == 0
    assert troops.members_left(-9, unit.troop.member_hp) == 0


def test_attrition_is_written_in_exactly_one_place():
    """The law about one applicator, kept for a number that is not an effect: attrition
    applied anywhere but the one place hit points leave an actor could double-count a blow
    or miss one."""
    src = inspect.getsource(from_dict.__globals__["Actor"].take_damage)
    assert "_troops.settle" in src
    assert inspect.getsource(troops.settle).count("troop.members = now") == 1


# --- the morale -------------------------------------------------------------------------

def test_the_two_moments_a_crowd_checks_its_nerve(table):
    """Basic D&D, and the Old School Essentials SRD keeps the durable version: 2d6 against
    a morale score of 2-12, checked "when the first combatant on the monster's side has been
    killed, or when half of the monster's group have been killed", higher than the score and
    they run. A 12 never checks; two passes and they fight to the death."""
    scene, _ = table
    unit = troops.form("raider", 12, scene=scene)
    t = unit.troop
    assert t.morale == troops.MORALE_DEFAULT == 8
    assert troops.owes_a_check(t, 0) == "", "nobody fell; nothing to check"
    assert troops.owes_a_check(t, 1) == "first blood"
    assert troops.morale_holds(t, 5, "first blood") is True
    assert t.checks_passed == 1
    # Not again until half are down.
    t.members = 9
    assert troops.owes_a_check(t, 1) == ""
    t.members = 6
    assert troops.owes_a_check(t, 1) == "half of them down"
    # Higher than the score and they break.
    assert troops.morale_holds(t, 11, "half of them down") is False
    assert t.routed is True
    # A fearless unit never checks at all, and two passes ends the checking.
    brave = troops.form("raider", 12, scene=scene).troop
    brave.morale = troops.MORALE_FEARLESS
    assert troops.owes_a_check(brave, 3) == ""
    steady = troops.form("raider", 12, scene=scene).troop
    steady.checks_passed = troops.CHECKS_BEFORE_RESOLVE
    assert troops.owes_a_check(steady, 3) == ""


def test_a_unit_whose_morale_breaks_leaves_the_board_and_scatters(table):
    scene, engine = table
    unit = troops.form("raider", 12, scene=scene)
    scene.add(unit)
    engine.run(engine.validate([{"op": "begin_encounter", "because": "the road",
                                 "params": {"sides": {"pc": ["pc"], "them": [unit.ref]}}}]))
    ref = unit.ref
    for _ in range(12):
        if ref not in scene.actors:
            break
        _hit(engine, unit, 40)
    assert ref not in scene.actors, "they ran; they are not a body lying here"
    assert not any(ref in refs for refs in (scene.sides or {}).values())
    assert all(r != ref for r, _ in scene.initiative)
    assert scene.said.get("routed_xp"), "the debt outlives them"


# --- the experience ----------------------------------------------------------------------

def test_the_fallen_are_paid_for_even_when_the_rest_run(table):
    """`xp.award_for_fallen` pays one all-or-nothing award per fallen actor and nothing at
    all for a rout, deliberately, so that mercy is not taxed. A unit is the case that breaks
    it: eight raiders dead and four fled is not mercy, and paying nothing would be the
    answer the player would notice first."""
    scene, engine = table
    unit = troops.form("raider", 12, scene=scene)
    scene.add(unit)
    engine.run(engine.validate([{"op": "begin_encounter", "because": "the road",
                                 "params": {"sides": {"pc": ["pc"], "them": [unit.ref]}}}]))
    unit.troop.morale = troops.MORALE_FEARLESS      # no rout: measure the standing case
    _hit(engine, unit, 87)
    assert unit.troop.fallen == 3
    assert troops.xp_owed(unit.troop) == 3 * 600
    total, names = xp.award_for_fallen(scene, scene.pc())
    assert total == 1800
    assert any("3 of" in n for n in names)


def test_a_routed_units_debt_is_settled_once(table):
    scene, engine = table
    unit = troops.form("raider", 6, scene=scene)
    scene.add(unit)
    engine.run(engine.validate([{"op": "begin_encounter", "because": "the road",
                                 "params": {"sides": {"pc": ["pc"], "them": [unit.ref]}}}]))
    unit.troop.morale = 2                            # they break at the first death
    _hit(engine, unit, 29)
    assert unit.ref not in scene.actors
    total, _ = xp.award_for_fallen(scene, scene.pc())
    assert total == 600, "one raider fell and the other five ran"
    # And paid ONCE: a second fight in the same room must not pay for the first one's dead.
    src = inspect.getsource(Engine._settle_xp) if hasattr(Engine, "_settle_xp") else ""
    assert 'scene.said.pop("routed_xp"' in inspect.getsource(Engine) or \
        'said.pop("routed_xp", None)' in inspect.getsource(Engine)


# --- the troop rules that are not about hit points ---------------------------------------

def test_an_area_effect_hurts_a_crowd_half_again_as_much(table):
    """"A troop takes half again as much damage (+50%) from spells or effects that affect an
    area." The rule that makes a fireball feel right against a crowd, and the reason a caster
    has something better to do than pick members off one at a time."""
    scene, engine = table
    unit = troops.form("raider", 12, scene=scene)
    scene.add(unit)
    eff = _hit(engine, unit, 20, traits=("area",))
    assert eff["amount"] == 30
    assert troops.damage_multiplier(unit.troop, ("area",)) == 1.5
    assert troops.damage_multiplier(unit.troop, ()) == 1.0
    assert troops.damage_multiplier(None, ("area",)) == 1.0


def test_a_spell_that_picks_out_single_creatures_finds_no_target_in_a_crowd():
    """"A troop is immune to any spell or effect that targets a specific number of
    creatures (including single-target spells such as disintegrate and multiple-target
    spells such as haste)." The corpus can tell them apart on its own: fireball's area is
    "20-foot-radius spread" and magic missile's target is "creatures (up to 5)"."""
    from rules import spells

    all_spells = spells.all_spells()
    fireball = all_spells["fireball"]
    missile = all_spells["magic-missile"]
    assert spells.casting_plan(fireball, 5)["area"] is True
    assert spells.casting_plan(fireball, 5)["targets_counted"] is False
    assert spells.casting_plan(missile, 5)["targets_counted"] is True
    src = inspect.getsource(Engine._op_cast)
    assert 'plan.get("targets_counted")' in src, "the cast path reads it"
    assert "is a " in src and "crowd" in src, "and says so: a wasted slot must say why"
    assert 'traits=("area",) if plan.get("area") else ()' in src


def test_a_crowd_makes_no_attack_roll(table):
    """"They deal automatic damage to any creature within reach or whose space they occupy
    at the end of their move, with no attack roll needed." It also solves a real engine
    problem: twelve raiders would otherwise be twelve NPC turns and twelve rolls a round."""
    src = inspect.getsource(Engine._op_attack)
    assert 'getattr(actor, "troop", None) is not None' in src
    assert "no roll to make" in src


def test_a_crowd_at_zero_breaks_up_and_does_not_bleed_out(table):
    """Measured live 2026-09-19: the last beat of a twelve-raider fight read "raiders is
    bleeding out." Pathfinder: "reducing a troop to 0 hit points or fewer causes it to break
    up, effectively destroying the troop" — no dying, no stabilising, no round-by-round
    loss, because what has been reduced is a formation and not a body."""
    scene, engine = table
    unit = troops.form("raider", 3, scene=scene)
    scene.add(unit)
    _hit(engine, unit, 500)
    assert unit.troop.members == 0
    # The same call every damage site makes through `_hp_state_effects`.
    assert unit.apply_hp_state() == ["dead"]
    assert unit.has_condition("dead")
    assert not unit.has_condition("dying") and not unit.has_condition("unconscious")
    assert unit.ref not in [b.owner for b in (scene.bleeding or [])] if scene.bleeding else True


def test_saves_are_thrown_once_because_it_is_one_actor(table):
    """"A troop attempts saving throws as a single creature" — which is the troop rule with
    nothing added, since a unit IS one actor. Recorded so nobody builds a second mechanism
    for it."""
    scene, _ = table
    unit = troops.form("raider", 12, scene=scene)
    one = instantiate("raider", scene=scene)
    assert unit.save_modifiers("fort") == one.save_modifiers("fort")


# --- the readout and the save ------------------------------------------------------------

def test_the_unit_survives_a_save_and_comes_back_whole(table):
    scene, _ = table
    unit = troops.form("raider", 12, scene=scene)
    unit.take_damage(60)
    back = from_dict(to_dict(unit), ref=unit.ref)
    assert back.troop is not None
    assert back.troop.members == unit.troop.members
    assert back.troop.fallen == unit.troop.fallen
    assert back.troop.member_xp == 600
    assert to_dict(load_pc("fixtures/pc-kesst.json"))["troop"] is None


def test_the_map_is_told_how_many_are_standing():
    from play import views

    src = inspect.getsource(views._state)
    assert '"members": int(a.troop.members)' in src
    html = open("play/templates/play/table.html", encoding="utf-8").read()
    assert "still standing" in html, "the tooltip says how many of how many"
    assert "token.unit" in html, "a crowd is hatched, not a solid block"
    assert "unithatch-foe" in html


# --- and the prose door ------------------------------------------------------------------

def test_a_band_the_prose_booked_arrives_as_a_unit(table):
    """This is what settles item 30's cap: "a band of twelve raiders" was four actors named
    "twelve soldier" at best and nothing at all at worst. It is one unit of twelve."""
    scene, _ = table
    beat = "A band of twelve raiders comes up the road, steel already out."
    added = judgement.note_cast(scene, beat, turn=1)
    made = judgement.promote_cast(scene, added, beat=beat, world=WORLD)
    bodies = [a for a in scene.actors.values() if not a.is_pc]
    assert made == ["raider"]
    assert len(bodies) == 1
    assert bodies[0].troop.members == 12
    assert bodies[0].hp == 348
    assert bodies[0].has_state("role.bystander"), "in the room, not in the order"
    assert split_collective_name("a band of twelve raiders") == (12, "raider")
