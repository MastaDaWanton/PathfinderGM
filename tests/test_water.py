"""Water, and what it does to a body (`rules/water.py`, docs/water.md).

The defect, and this app said it out loud about itself for weeks: **the engine had no
water.** Fourteen terrains and not one of them was wet — `aquatic`, `underwater`, `river`
and `lake` all resolved to `coast` — so the sea was the sand beside it, 468 creatures
including every shark and kraken in the bestiary lived on a beach, and
`docs/race-cues.json` shipped "a swim speed: the engine has no water" as the published
reason a race trait World Bible can write could never work. It was reported to the
supplier in those words on 2026-09-16, a few hours before this was built.

Two terrains, not one, because the Core Rulebook treats them as two situations: a surface
you can breathe on and have cover from the shore, and below it, where the only clock is
the breath you brought.

Every number here is the book's — Table 13-7, the Swim DCs, twice Constitution in rounds,
DC 10 rising by one — and the tests are written against the four rows of that table
because the rows are the whole design: **the water does not ask what you are doing, it
asks what you have.**
"""
from __future__ import annotations

import pytest

from rules import biomes, floorplan, places, water
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
DRY = f"{TOWN}~urban:the-market"
SURFACE = f"{TOWN}~water:the-channel"
DEEP = f"{TOWN}~underwater:the-sunken-hold"


def _table(at: str = DRY, seed: int = 7):
    scene = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=seed), world=WORLD)
    engine.place_party(DRY)
    scene.at = at
    pc.at = at
    return scene, engine, pc


# --- there is water now -------------------------------------------------------------------

def test_the_engine_has_water_and_it_is_not_a_beach():
    """The measurement, as an assertion. `coast` is a shore — sand, rocks, a tide line —
    and it is not somewhere you can drown."""
    assert "water" in biomes.BIOMES and "underwater" in biomes.BIOMES
    assert biomes.canonical("ocean") == "water"
    assert biomes.detect("any oceans") == ["water"]
    assert biomes.canonical("underwater") == "underwater"
    assert biomes.canonical("shore") == "coast", "the shore is still the shore"


def test_a_place_in_the_water_reads_as_water():
    """The ground is inside the place id, which is why a sheet with no world can still
    tell it is in the sea."""
    assert places.terrain_of(SURFACE) == "water"
    assert places.terrain_of(DEEP) == "underwater"
    assert water.is_wet("water") and water.is_wet("underwater")
    assert water.is_under("underwater") and not water.is_under("water")
    assert not water.is_wet("coast")


def test_open_water_has_nothing_to_hide_behind():
    """A shape for both, and the honest one: no walls, no rubble, no ledge. The
    verticality of water is depth, and depth is the other place."""
    for terrain in ("water", "underwater"):
        shape = floorplan.BY_TERRAIN[terrain]
        assert shape.vertical == "none", terrain
        assert shape.rough == 0, terrain
    assert floorplan.BY_TERRAIN["water"].clumps == 0
    assert floorplan.shape_for(SURFACE, "water").about


# --- the four rows of the table -------------------------------------------------------------

def test_the_table_is_the_one_in_the_book():
    """Table 13-7, worst case to best. Slashing and bludgeoning suffer at every rung
    below freedom of movement; piercing only suffers when you are floundering."""
    assert water.attack_penalty(water.FREE, "slashing") == 0
    for row in (water.SWIMMER, water.SWIMMING, water.FOOTING, water.OFF_BALANCE):
        assert water.attack_penalty(row, "slashing") == -2, row
        assert water.damage_halved(row, "bludgeoning") is True, row
    for row in (water.SWIMMER, water.SWIMMING, water.FOOTING):
        assert water.attack_penalty(row, "piercing") == 0, row
        assert water.damage_halved(row, "piercing") is False, row
    assert water.attack_penalty(water.OFF_BALANCE, "piercing") == -2


def test_a_weapon_that_can_do_either_uses_the_half_that_works():
    """A longsword is "slashing", a rapier "piercing", and a few are "slashing or
    piercing". The honest reading of a weapon that can do either is that the wielder uses
    the end the water does not spoil."""
    assert water.damage_halved(water.SWIMMING, "slashing or piercing") is False
    assert water.damage_halved(water.SWIMMING, "slashing") is True


def test_floundering_is_the_whole_difference_between_water_and_a_blue_room():
    """The bottom row is what happens to an armoured character who goes over the side,
    and it is why a fight in water is a different fight: you are not harder to hit, you
    are easier, and there is nothing behind the blow."""
    assert water.bonus_against(water.OFF_BALANCE) == 2
    assert water.loses_dex_to_ac(water.OFF_BALANCE) is True
    for row in (water.FREE, water.SWIMMER, water.SWIMMING, water.FOOTING):
        assert water.bonus_against(row) == 0, row
        assert water.loses_dex_to_ac(row) is False, row


def test_a_swimmer_swims_and_everybody_else_is_slow():
    assert water.speed_factor(water.SWIMMER) == 1.0
    assert water.speed_factor(water.SWIMMING) == 0.25
    assert water.speed_factor(water.FOOTING) == 0.5


def test_which_row_you_are_in_is_a_fact_about_you():
    """Asked of the creature, never of the narrator — it is what your body can do and
    what you are wearing, which is exactly the kind of thing this app will not let a
    model assert."""
    scene, _engine, pc = _table(SURFACE)
    assert water.row_for(pc) == water.OFF_BALANCE          # nobody asked, no armour
    assert water.row_for(pc, made_swim_check=True) == water.SWIMMING
    assert water.row_for(pc, made_swim_check=False) == water.OFF_BALANCE
    shark = scene.add(instantiate("guildhand", scene=scene, name="Fishy"))
    shark.tags = list(getattr(shark, "tags", []) or []) + ["move.swim.30"]
    assert water.swim_speed(shark) == 30
    assert water.row_for(shark) == water.SWIMMER


# --- and it reaches the swing ----------------------------------------------------------------

def test_the_water_takes_two_off_a_sword_and_nothing_off_a_spear():
    """Through the one funnel, so it is itemised beside every other modifier and the
    player can see why the number is the number."""
    _scene, _engine, pc = _table(SURFACE)
    assert pc.water_row() == water.OFF_BALANCE
    sources = [m.source for m in pc.attack_modifiers()]
    assert "the water" in sources, sources
    # Treading water, her dagger is unpenalised: only slashing and bludgeoning suffer
    # until you are floundering.
    pc.swim_check_made = True
    assert pc.water_row() == water.SWIMMING
    assert "the water" not in [m.source for m in pc.attack_modifiers()]


def test_on_dry_land_nothing_changes():
    """The whole thing is additive: a place that is not wet is the game as it was."""
    _scene, _engine, pc = _table(DRY)
    assert pc.water_row() == ""
    assert "the water" not in [m.source for m in pc.attack_modifiers()]


# --- drowning ---------------------------------------------------------------------------------

def test_a_held_breath_is_twice_your_constitution():
    _scene, _engine, pc = _table(DEEP)
    assert water.breath_rounds(pc) == pc.ability_score("con") * 2


def test_the_clock_runs_and_it_ends_where_the_book_ends_it():
    """Twice Constitution in rounds, then a Constitution check each round at DC 10 going
    up by one, then unconscious, dying, dead — three rounds, no save. Drowning is the one
    death in the game that arrives on a schedule, so every rung of it tells."""
    scene, engine, pc = _table(DEEP)
    limit = water.breath_rounds(pc)
    said: list[str] = []
    for _ in range(limit + 12):
        scene.advance(rounds=1, minutes=0)
        said.extend(engine.breathe())
        if pc.has_state("state.down.dead"):
            break
    assert pc.has_state("state.down.dead"), said
    assert pc.held_breath_rounds > limit
    assert any("breathes water" in s for s in said), said
    assert any("dying" in s for s in said), said
    assert any("drowned" in s for s in said), said


def test_the_clock_does_not_run_on_the_surface():
    """You can breathe up there. The counter is the difference between the two terrains,
    and it is why they are two terrains."""
    scene, engine, pc = _table(SURFACE)
    for _ in range(60):
        scene.advance(rounds=1, minutes=0)
        engine.breathe()
    assert pc.held_breath_rounds == 0
    assert pc.drown_failures == 0


def test_a_creature_that_breathes_water_is_not_drowning_in_it():
    scene, engine, pc = _table(DEEP)
    fish = scene.add(instantiate("guildhand", scene=scene, name="Gill"))
    fish.at = DEEP
    fish.tags = list(getattr(fish, "tags", []) or []) + ["amphibious"]
    assert water.breathes_water(fish)
    for _ in range(80):
        scene.advance(rounds=1, minutes=0)
        engine.breathe()
    assert fish.held_breath_rounds == 0
    assert not fish.has_state("state.down.dead")


def test_surfacing_gives_the_breath_back():
    scene, engine, pc = _table(DEEP)
    for _ in range(5):
        scene.advance(rounds=1, minutes=0)
    assert pc.held_breath_rounds == 5
    pc.at = SURFACE
    scene.at = SURFACE
    scene.advance(rounds=1, minutes=0)
    assert pc.held_breath_rounds == 0


def test_drowning_writes_the_book_s_own_states_and_invents_none():
    """There is no "drowning" condition in Pathfinder, and the first version of this
    invented one. The suite caught it four separate ways — not in Appendix 2, no entry in
    the tag vocabulary, helpless-but-able-to-act, and one literal condition key too many
    in `rules/engine.py` — which is the three laws working as designed.

    What the book has is a schedule that writes unconscious, then dying, then dead. All
    three are states `apply_hp_state` already derives from hit points, so the schedule is
    a counter and the states are the book's."""
    from rules.sheet import CONDITIONS

    assert "drowning" not in CONDITIONS
    scene, engine, pc = _table(DEEP)
    for _ in range(water.breath_rounds(pc) + 12):
        scene.advance(rounds=1, minutes=0)
        engine.breathe()
        if pc.drown_failures == 1:
            assert pc.has_state("state.down"), [c.key for c in pc.conditions]
            break
    assert pc.drown_failures == 1


def test_a_corpse_is_not_also_disabled():
    """Found by drowning somebody. `apply_hp_state` cleared dying, stable and unconscious
    on death and never `disabled`, because most deaths do not stop at exactly 0 hit
    points — and drowning walks a body down the ladder one rung a round."""
    scene, engine, pc = _table(DEEP)
    for _ in range(water.breath_rounds(pc) + 12):
        scene.advance(rounds=1, minutes=0)
        engine.breathe()
        if pc.has_state("state.down.dead"):
            break
    assert pc.has_state("state.down.dead")
    assert not pc.has_condition("disabled"), [c.key for c in pc.conditions]


def test_the_counters_survive_a_save():
    """A reload that forgot how long the breath had been held would hand the diver a
    fresh lungful, which is the cheapest cheat in the game."""
    from rules.sheet import from_dict, to_dict

    _scene, _engine, pc = _table(DEEP)
    pc.held_breath_rounds, pc.drown_failures, pc.swim_check_made = 9, 1, True
    back = from_dict(to_dict(pc))
    assert (back.held_breath_rounds, back.drown_failures, back.swim_check_made) == (9, 1, True)


# --- what the world may now say ----------------------------------------------------------------

def test_the_bestiary_lives_in_the_water_rather_than_on_the_beach():
    """468 creatures moved when the aliases were repointed and the tagger re-run. A
    shark's environment line reads "any ocean" and the only word this app had for an
    ocean was the sand beside it."""
    from rules import bestiary

    every = bestiary.everything()
    in_water = [k for k, c in every.items() if "water" in (c.get("biomes") or [])]
    assert len(in_water) > 300, len(in_water)


def test_the_handoff_offers_both_words():
    """World Bible cannot write a place on ground this app has never published."""
    from pathlib import Path

    from django.conf import settings

    doc = Path(settings.BASE_DIR, "docs",
               "places-and-races-for-world-bible.md").read_text(encoding="utf-8")
    assert "`water`" in doc and "`underwater`" in doc
    assert "sixteen" in doc
