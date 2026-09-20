"""Group 11 of the 2026-09-19 fix pass: a map at all times, and who a place holds.

Reported (docs/playtest-2026-09-18.md item 28): *"A map should be displayed at all times
and Enemy/NPC spawns should not be random but based on the situation and narration should
match it."*

**The map.** The grid existed only inside a fight by construction — laid by
`_lay_battlefield` from the two doors a fight comes in by, cleared by `end_encounter`, and
gated again in the view and in the browser, which printed "No ground is mapped. A grid is
laid out when a fight starts." Nothing was missing to derive one: `floorplan.for_place` is
a pure function of the place id, its terrain and the world's authored shape, and its
scatter is a SHA-seeded LCG rather than `random`. What was absent was positions.

**The spawns.** There is no randomness in the spawn path at all. Who appeared was decided
by three regexes over the player's own sentence falling through to a literal `"thug"`, and
the model was offered four hand-written templates while 7,133 stat blocks sat loaded. The
situational material — `places.STAFFED`'s 25 rows, `category_of`, `npcs.choose`'s CR band,
the world's residents — was written and unread.
"""
from __future__ import annotations

import inspect

import pytest

from rules import roster, troops
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"
GUILDHALL = f"{TOWN}~urban:the-guildhall"


@pytest.fixture
def table():
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene, Engine(scene, Dice(seed=3), world=WORLD)


# --- the map ----------------------------------------------------------------------------

def test_the_ground_is_laid_when_the_party_arrives_not_when_a_fight_starts(table):
    scene, engine = table
    assert scene.grid is None, "nowhere yet"
    engine.place_party(MARKET)
    assert scene.grid is not None and scene.grid.width > 0
    assert "pc" in scene.positions, "and the player is standing on it"


def test_the_ground_belongs_to_the_place_and_is_replaced_when_the_party_moves(table):
    scene, engine = table
    engine.place_party(MARKET)
    market = scene.grid
    engine.place_party(GUILDHALL)
    assert scene.grid is not market, "a different room is different ground"
    # And the same place twice is the SAME ground: this path runs on every load, and
    # re-deriving there threw away everything laid ON the map — measured by the suite
    # within the hour, a fog cloud survived a restart and its squares did not.
    same = scene.grid
    engine.place_party(GUILDHALL)
    assert scene.grid is same


def test_the_ground_stays_when_the_fight_ends(table):
    """This is the reversal. `end_encounter` cleared the grid and the panel's own words
    were "there is no grid outside a fight"; the ground belongs to the place now, and what
    ends with the fight is the tactical layer above it."""
    scene, engine = table
    engine.place_party(MARKET)
    foe = instantiate("thug", scene=scene, name="the thug")
    scene.add(foe, zone="near")
    engine.run(engine.validate([{"op": "begin_encounter", "because": "a brawl",
                                 "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    scene.end_encounter()
    assert scene.grid is not None and "pc" in scene.positions
    assert scene.initiative == [] and scene.sides == {} and not scene.in_encounter
    src = inspect.getsource(Scene.end_encounter)
    assert "self.grid = None" not in src


def test_a_fight_still_lays_out_its_own_combatants(table):
    """The geometry that is load-bearing. A zone word and a stated distance are claims
    about the FIGHT — "I loose an arrow at him from 200 feet" — and an idle position from
    standing about in the room is not. Measured the hour the map became permanent: with
    everyone pre-placed on arrival the bowshot opened at forty feet, because the layout
    skips anybody who already has a square."""
    scene, engine = table
    engine.place_party(MARKET)
    foe = instantiate("watchman", scene=scene, name="the watchman")
    scene.add(foe, zone="far")
    # As the real arrivals do: `promote_cast` and `Engine._bring_in` place a newcomer by
    # their zone when there is ground, which there now always is.
    scene.place_by_zone([foe.ref])
    assert scene.positions.get(foe.ref) is not None, "standing somewhere before the fight"
    engine.run(engine.validate([{"op": "begin_encounter", "because": "the arrow",
                                 "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    assert scene.distance_between("pc", foe.ref) == 40, "far is far, and the fight says so"
    src = inspect.getsource(Engine._lay_battlefield)
    assert "self.scene.positions.pop(ref, None)" in src


def test_a_bystander_keeps_where_they_were_standing(table):
    """The other half of the same rule: the fight lays out the fight, and the room keeps
    the rest of the room."""
    scene, engine = table
    engine.place_party(MARKET)
    watcher = instantiate("guildhand", scene=scene, name="the merchant")
    scene.add(watcher, zone="near")
    scene.place_by_zone([watcher.ref])
    stood = scene.positions[watcher.ref]
    foe = instantiate("thug", scene=scene, name="the thug")
    scene.add(foe, zone="near")
    engine.run(engine.validate([{"op": "begin_encounter", "because": "a brawl",
                                 "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    assert scene.positions[watcher.ref] == stood


def test_a_fight_nowhere_in_particular_still_has_ground():
    """A scene with no place is one that has not been put anywhere yet — the map tray says
    so rather than drawing a blank field — but a brawl still happens on ground."""
    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=5))
    assert engine.lay_the_ground() is False, "nowhere is not a room"
    foe = instantiate("thug", scene=scene, name="the thug")
    scene.add(foe, zone="near")
    engine.run(engine.validate([{"op": "begin_encounter", "because": "a brawl",
                                 "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    assert scene.grid is not None


def test_the_browser_no_longer_promises_a_grid_only_in_a_fight():
    html = open("play/templates/play/table.html", encoding="utf-8").read()
    assert "A grid is laid out when a fight\n       starts" not in html
    assert "as soon as they are standing somewhere" in html


# --- who this place would hold ------------------------------------------------------------

def test_the_place_says_who_is_in_it(table):
    """`places.STAFFED` has held 25 rows of who is at each kind of place since it was
    written, and its only caller in the repo was a tooling script."""
    scene, engine = table
    engine.place_party(MARKET)
    who = roster.who_would_be_here(scene, WORLD, level=1)
    assert who, "the market holds somebody"
    words = [r["who"].lower() for r in who]
    assert "stallholder" in words and "merchant" in words
    assert all(r["template"] for r in who), "every one of them has a stat block"
    assert who[0]["why"].startswith("the market"), "the most specific source comes first"

    engine.place_party(GUILDHALL)
    guild = [r["who"].lower() for r in roster.who_would_be_here(scene, WORLD, level=1)]
    assert "clerk" in guild and "stallholder" not in guild


def test_a_place_with_no_row_falls_through_to_its_kind_then_to_people(table):
    scene, engine = table
    engine.place_party(f"{TOWN}~urban:the-gate")
    who = [r["who"].lower() for r in roster.who_would_be_here(scene, WORLD, level=1)]
    assert who, "somewhere with no staffing row still holds people"
    assert roster.words_for("", "a place nobody wrote a row for") == roster.BYSTANDERS
    # Deliberately not "thug": the old fallback made every unnamed arrival an assailant.
    assert "thug" not in roster.BYSTANDERS


def test_residents_come_by_name_and_never_by_their_prose(table):
    """The measurement that changed the design mid-build. In the shipped Pangrella export
    a resident's `Role` fact is prose — "Innovative developer and expert in magnetic shift
    adaptation", "High King's Representative" — and handing that to `npcs.choose` returned
    a Drummond-and-Neville and an Initiate of Flame. Aurvantis writes clean roles; neither
    export can be relied on, so neither is."""
    scene, engine = table
    engine.place_party(MARKET)
    who = roster.who_would_be_here(scene, WORLD, level=1)
    named = [r for r in who if r["why"].startswith("lives in")]
    assert named, "the world's own people are in the roster"
    assert all(len(r["who"].split()) <= 4 for r in named), "by name, not by paragraph"
    assert len(named) <= 2, "a roster swamped by names is one nothing can choose from"


def test_the_brief_offers_the_roster_instead_of_four_templates(table):
    from gm import prompts
    from rules import engine as engine_mod

    scene, engine = table
    engine.place_party(MARKET)
    brief = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [],
                                here=engine.here(), known=engine.places())
    assert "WHO THIS PLACE WOULD HOLD" in brief
    assert "stallholder" in brief
    # The hint no longer presents four templates as the whole world.
    assert "the templates are" not in engine_mod._SPAWN_HINT
    assert "WHO THIS PLACE WOULD HOLD above" in engine_mod._SPAWN_HINT


def test_the_roster_is_a_list_of_who_could_be_here_not_who_is(table):
    """Item 29's rule is untouched: the engine still has to be told to create anybody, and
    whose word they exist on is still the test."""
    scene, engine = table
    engine.place_party(MARKET)
    line = roster.brief_line(roster.who_would_be_here(scene, WORLD, level=1))
    assert "if somebody new appears" in line
    assert roster.brief_line([]) == ""
