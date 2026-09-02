"""Foraging that costs time, and a body that notices.

Time was free before this. A character could forage for thirty hours, cross a continent
and sit up three nights running, and nothing on the sheet knew — the clock moved and the
body did not. That is fine while every action is a single swing and stops being fine the
moment the player can say "I forage for eighteen hours".

Two things changed together. Foraging is hours now, one Survival check each, and the
degree of success runs the whole way from a plant torn out of the ground and wrecked to a
garden's worth of perfect specimens. And the hours are spent for real: thirst, hunger and
sleep on 1e's own schedules, all three of which a class or a ruleset can exempt a
character from.

Staying awake is a **Will save**, rising an hour at a time, which is the project owner's
decision rather than 1e's — the book uses a Constitution check for a forced march. It is
recorded here because a rule that departs from the book on purpose has to be findable.
"""
from __future__ import annotations

import collections

import pytest

from rules import foraging, survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


@pytest.fixture
def forager():
    # A 6th-level forager, because `validate` caps ranks at character level and holds a
    # 1st-level rogue to a single rank in anything. Set through `from_dict` so the sheet
    # is legal on every round trip rather than only until one happens.
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["level"] = 6
    d["ranks"] = {"survival": 6}
    d["abilities"]["wis"] = 16
    return from_dict(d, ref="pc")


@pytest.fixture
def wood(forager):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "forest")
    s.add(forager)
    return s, Engine(s, Dice(seed=5))


def forage(engine, hours=1, face=11):
    """Run a forage to completion, answering the Survival popup with `face` — the
    suspend is the contract now, and this file's business is the clock either side
    of it."""
    resolution = engine.run(engine.validate([
        {"op": "forage", "actor": "pc", "because": "she works the treeline",
         "params": {"hours": hours}}]))
    if resolution.awaiting is None:
        return resolution
    return engine.resume(face)


# --- an hour is an hour ------------------------------------------------------------------

def test_foraging_moves_the_clock(wood):
    scene, engine = wood
    forage(engine, hours=8)
    assert scene.clock_minutes == 8 * 60


def test_a_session_is_at_least_an_hour(wood):
    scene, engine = wood
    forage(engine, hours=0)
    assert scene.clock_minutes == 60


def test_every_hour_is_its_own_check(forager):
    """One roll for the stretch would make an eighteen-hour day either trivial or
    impossible with nothing in between."""
    got = foraging.forage("forest", 3, 3, Dice(seed=5), hours=6, actor=forager)
    assert len(got["hourly"]) == 6
    assert len({h["roll"] for h in got["hourly"]}) > 1


# --- the spectrum, from a wrecked leaf to a garden ------------------------------------------

def test_the_bands_run_the_whole_way():
    assert foraging.band_for(25)[0] == "a garden's worth"
    assert foraging.band_for(16)[0] == "an excellent hour"
    assert foraging.band_for(0)[0] == "a meagre hour"
    assert foraging.band_for(-2)[0] == "nothing worth carrying"
    assert foraging.band_for(-20)[0] == "a ruined handful"


def test_a_botched_hour_names_what_was_destroyed():
    """The brief's "single destroyed leaf". Nothing is carried either way, but being told
    you tore the roots off a Woundwart is a different fact from being told the wood was
    bare — and only one of them is worth reading."""
    seen = ""
    for seed in range(400):
        # A forest rather than a desert: the desert table is empty at this ceiling, so
        # there is nothing there to wreck and the first version of this test proved only
        # that an empty wood stays empty.
        hour = foraging.forage_hour("forest", 0, 1, Dice(seed=seed))
        if hour["ruined"]:
            seen = hour["wrecked"]
            break
    assert seen, "no hour in 400 came out ruined"


def test_a_skilled_forager_reaches_the_top_and_a_novice_does_not():
    """Measured over 400 hours each in the same wood, with legal sheets — ranks are
    capped at character level, so the "master" is a 5th-level Herbalist 5 with five ranks
    rather than the impossible fifteen the first version of this test gave her.

    The novice never reaches the top band and never brings back a pristine specimen. The
    master reaches it in about one hour in seven and comes back with something perfect
    about half the time. The gap is the point; the exact numbers are recorded so a change
    in the bands shows up here rather than in play."""
    def spread(ranks, wis, level):
        d = to_dict(load_pc("fixtures/pc-kesst.json"))
        d["level"] = max(1, level)
        d["ranks"] = dict(ranks)
        d["abilities"]["wis"] = wis
        pc = from_dict(d, ref="pc")
        bands = collections.Counter()
        pristine = 0
        for seed in range(400):
            hour = foraging.forage_hour("forest", level, min(5, level), Dice(seed=seed),
                                        actor=pc)
            bands[hour["band"]] += 1
            pristine += bool(hour["pristine"])
        return bands, pristine

    novice, novice_pristine = spread({}, 12, 1)
    master, master_pristine = spread({"survival": 5}, 18, 5)

    assert novice["a garden's worth"] == 0
    assert novice_pristine == 0
    assert master["a garden's worth"] > 30
    assert master_pristine > 3 * max(1, novice_pristine)
    assert master_pristine > 150


def test_a_good_hour_reaches_rarer_ground_but_never_past_the_track():
    """Luck finds better things; it does not teach the character to handle them."""
    hour = foraging.forage_hour("forest", 5, 2, Dice(seed=5))
    assert hour["ceiling"] <= 4


def test_perfect_specimens_are_carried_as_such(wood):
    scene, engine = wood
    forage(engine, hours=4)
    pc = scene.pc()
    for iid, n in pc.pristine.items():
        assert n <= pc.inventory[iid], f"more pristine {iid} than {iid}"


# --- the body ---------------------------------------------------------------------------------

def test_a_short_day_costs_nothing(wood):
    scene, engine = wood
    forage(engine, hours=8)
    pc = scene.pc()
    assert pc.nonlethal == 0
    assert not pc.conditions


def test_past_a_day_awake_it_starts_asking(wood):
    scene, engine = wood
    forage(engine, hours=30)
    pc = scene.pc()
    assert pc.awake_minutes // 60 > survival.AWAKE_GRACE_HOURS
    assert pc.nonlethal > 0 or pc.has_condition("fatigued")


def test_the_forager_stops_at_the_hour_they_fell_over(wood):
    """Rather than at the end of the stretch they meant to work. The player needs to be
    told when it went wrong, not just that it did."""
    scene, engine = wood
    res = forage(engine, hours=40)
    effect = res.outcomes[0].effects[0]
    assert effect["hours"] < effect["asked_for"]
    assert scene.clock_minutes == effect["hours"] * 60


def test_the_will_save_gets_harder_every_hour():
    """The project owner's choice over 1e's Constitution check, and the rise is what makes
    a long night a decision rather than one gamble: hour 25 is trivial, hour 40 is not."""
    assert survival.awake_dc(24) == 0
    assert survival.awake_dc(25) == 11
    assert survival.awake_dc(40) == 26


def test_hard_ground_makes_it_worse():
    assert survival.awake_dc(30, "desert") > survival.awake_dc(30, "forest")


def test_the_check_is_a_will_save_and_not_a_constitution_check(wood):
    scene, engine = wood
    forage(engine, hours=30)
    effect = res_checks(engine, scene)
    assert any(c["save"] == "will" for c in effect if c["kind"] == "Exhaustion")


def res_checks(engine, scene):
    last = scene.log[-1] if scene.log else {}
    for e in last.get("effects", []):
        if e.get("kind") == "forage":
            return e.get("toll", {}).get("checks", [])
    return []


def test_thirst_waits_a_day_plus_your_constitution(forager):
    forager.abilities["con"] = 14
    assert survival.hours_until_thirsty(forager) == 24 + 14


def test_hunger_waits_three_days(forager):
    assert survival.hours_until_hungry(forager) == 72


def test_the_dcs_rise_per_check_made_not_per_hour():
    """1e: "+1 for each previous check". A character who passed twice faces DC 12, not
    DC 10 plus however many hours have elapsed."""
    assert survival.thirst_dc(0) == 10
    assert survival.thirst_dc(5) == 15


def test_a_night_resets_the_clock(forager):
    forager.awake_minutes = 30 * 60
    forager.rest("night")
    assert forager.awake_minutes == 0


def test_eating_and_drinking_reset_theirs(forager):
    forager.fed_minutes = 100 * 60
    forager.watered_minutes = 50 * 60
    survival.eat(forager)
    survival.drink(forager)
    assert forager.fed_minutes == 0 and forager.watered_minutes == 0


# --- things that do not eat, drink or sleep ------------------------------------------------------

def test_a_creature_can_be_exempted_from_each_need(forager):
    """A construct does not drink and something stranger might not sleep."""
    for rule in (survival.NO_SLEEP, survival.NO_FOOD, survival.NO_WATER):
        forager.overrides[rule] = True
    forager.awake_minutes = 200 * 60
    forager.watered_minutes = 200 * 60
    toll = survival.pass_hours(forager, 10, Dice(seed=1), biome="desert")
    assert toll.checks == []
    assert toll.nonlethal == 0


def test_the_exemptions_are_declared_rules_not_free_text():
    """The same reason `ACTOR_RULES` is a list at all: a misspelled exemption would be a
    character silently made immortal."""
    from rules.sheet import ACTOR_RULES

    for rule in (survival.NO_SLEEP, survival.NO_FOOD, survival.NO_WATER):
        assert rule in ACTOR_RULES


def test_an_unexempted_character_is_not_accidentally_exempt(forager):
    assert not survival.exempt(forager, survival.NO_SLEEP)


# --- persistence --------------------------------------------------------------------------------

def test_the_clocks_survive_a_save(forager):
    forager.awake_minutes = 300
    forager.watered_minutes = 900
    forager.thirst_checks = 3
    back = from_dict(to_dict(forager))
    assert back.awake_minutes == 300
    assert back.watered_minutes == 900
    assert back.thirst_checks == 3


def test_pristine_material_survives_a_save(forager):
    forager.carry("woundwort", 3, pristine=2)
    back = from_dict(to_dict(forager))
    assert back.inventory["woundwort"] == 3
    assert back.pristine["woundwort"] == 2


def test_a_sheet_written_before_any_of_this_still_loads():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    for key in ("awake_minutes", "fed_minutes", "watered_minutes", "pristine",
                "thirst_checks", "hunger_checks"):
        d.pop(key, None)
    back = from_dict(d)
    assert back.awake_minutes == 0
    assert back.pristine == {}


# --- plants grow in patches -----------------------------------------------------------------

def test_a_find_is_a_patch_not_a_single_flower():
    """Eight finds used to mean eight individual specimens, one of each. That is not what
    an hour in a wood looks like: you come out with an armful of the common stuff and, if
    you were lucky, a couple of the rare."""
    assert foraging.batch_for(1, 0) == 10       # common, best hour
    assert foraging.batch_for(2, 0) == 8        # uncommon
    assert foraging.batch_for(3, 0) == 6        # rare
    assert foraging.batch_for(4, 0) == 4        # exotic
    assert foraging.batch_for(5, 0) == 2        # legendary


def test_the_patch_shrinks_two_a_band():
    assert foraging.batch_for(1, 1) == 8
    assert foraging.batch_for(1, 2) == 6
    assert foraging.batch_for(1, 4) == 2


def test_you_always_hold_at_least_one_of_what_you_found():
    """The floor is what keeps a legendary herb worth stooping for at every band rather
    than rounding away to nothing three bands down."""
    assert foraging.batch_for(5, 4) == 1
    assert foraging.batch_for(1, 99) == 1


def test_a_good_hour_finds_distinct_species(forager):
    """Eight rolls that all landed on Woundwart is one plant found eight times, not the
    eight kinds the band promised."""
    best = None
    for seed in range(200):
        hour = foraging.forage_hour("forest", 5, 5, Dice(seed=seed), actor=forager)
        if hour["band"] == "a garden's worth":
            best = hour
            break
    assert best, "no hour in 200 reached the top band"
    ids = [p["id"] for p in best["picks"] if p["id"]]
    assert len(ids) == len(set(ids))
    assert len(best["found"]) > 1


def test_the_rarer_the_plant_the_smaller_the_patch(forager):
    """Within one hour, so the band is held constant and only the rank varies."""
    for seed in range(200):
        hour = foraging.forage_hour("forest", 5, 5, Dice(seed=seed), actor=forager)
        ranks = {p["rank"]: p["count"] for p in hour["picks"] if p["id"]}
        if len(ranks) > 1:
            ordered = [ranks[r] for r in sorted(ranks)]
            assert ordered == sorted(ordered, reverse=True), ranks
            return
    pytest.skip("no hour in 200 turned up two different ranks")


# --- eating and drinking as ops (playtest, 2026-08-22) --------------------------------------

def test_eating_resets_the_hunger_clock_and_only_that(wood):
    """"I eat from my rations and drink from my waterskin" reached the engine as
    narrate_only in both playtest sessions, so the hunger and thirst clocks could run out
    but never be answered. Now they are ops."""
    s, engine = wood
    pc = s.pc()
    pc.fed_minutes = pc.watered_minutes = pc.awake_minutes = 600

    r = engine.run(engine.validate([{"op": "eat"}]))
    assert pc.fed_minutes == 0
    assert pc.watered_minutes == 600, "a meal is not a drink"
    assert pc.awake_minutes == 600, "a meal is not a nap"
    assert "eats" in r.outcomes[0].tell


def test_drinking_resets_thirst(wood):
    s, engine = wood
    pc = s.pc()
    pc.watered_minutes = 900
    engine.run(engine.validate([{"op": "drink"}]))
    assert pc.watered_minutes == 0


def test_a_nights_rest_still_resets_the_awake_clock_but_not_the_stomach(wood):
    """The reason eat/drink are their own ops rather than flags on rest: sleeping through
    a night hungry leaves you a night hungrier."""
    s, engine = wood
    pc = s.pc()
    pc.awake_minutes = 1200
    pc.fed_minutes = 1200
    before = s.clock_minutes
    engine.run(engine.validate([{"op": "rest", "actor": "pc",
                                     "params": {"kind": "night"}}]))
    assert pc.awake_minutes == 0
    assert pc.fed_minutes == 1200
    assert s.clock_minutes - before == 8 * 60, "a night is eight hours, not twenty minutes"
