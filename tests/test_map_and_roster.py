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


def test_the_map_tray_names_the_place_it_is_drawing():
    """Reported 2026-09-21: "i am at a gate with wagons passing through and a wagon off to
    the side this map is completely wrong."

    The map was right. The engine held the party at **the well** — a 5x5 place World Bible
    authored, a wellhead and the ground worn round it — and drew exactly that. The prose
    had wandered to a gate that does not exist in that town at all.

    The tray said "The ground" and nothing else, so a correct map of one place beside prose
    about another is indistinguishable from a broken map. It names the place now, and the
    shape's own `about` line says what that kind of place is made of.
    """
    from play.views import _where_the_ground_is

    class _Scene:
        at = "abc~urban:the-well"

    name, about = _where_the_ground_is(_Scene())
    assert name == "the well"
    assert "wellhead" in about, about

    class _Gate:
        at = "abc~urban:the-gate"

    gate_name, gate_about = _where_the_ground_is(_Gate())
    assert gate_name == "the gate" and "gatehouse" in gate_about

    class _Nowhere:
        at = ""

    assert _where_the_ground_is(_Nowhere()) == ("", "")


def test_the_caption_reads_the_same_shape_the_plan_was_drawn_from():
    """One place, one answer: the caption must not be able to describe a different room
    from the one on screen, which is what a second lookup would eventually do."""
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    body = src.split("def _where_the_ground_is(")[1].split("\ndef ")[0]
    assert "floorplan.shape_for(" in body
    assert "places_mod.terrain_of(" in body


# --- every settlement has a way in, and somebody on it ------------------------------------

def test_every_scale_of_settlement_has_a_way_in():
    """Asked for 2026-09-21: "every city/town needs an entrance or two that is watched a
    village still has entry roads that are likely watched as well."

    Measured across the three shipped worlds before it was built: eight of Aurvantis's
    sixteen villages named no entrance of any kind, and a generated village's guaranteed
    set was a single well. Towns and cities were already given a gate; a village was given
    nowhere to arrive at.
    """
    from rules import places

    for scale in ("village", "town", "city"):
        names = {p.name for p in places._settlement_set("abc123def456", scale, None)}
        assert names & set(places.ENTRANCES), (scale, sorted(names))


def test_an_authored_settlement_with_no_entrance_is_given_one():
    """Vormoor's five authored places are a well, a market, a guildhall, a lane and a
    green. The narrator put the player "under the gate" of a town that had none (item 45),
    and the warrant check, which watches the way out, could never fire there.

    A deliberate amendment to this module's "the author has spoken" rule, and the reason
    it is not the same thing: a docks is a flourish, a way in is the difference between a
    town somebody can arrive at and a town that is only ever an interior.
    """
    from rules import places
    from play import library

    world = library.world("aurvantis-campaign")
    settlement = next(s for s in world.play["settlements"] if s["name"] == "Vormoor")
    got = places.home_set(world.get(settlement["id"]))
    names = [p.name for p in got]
    assert "the way in" in names, names
    # The author's own places are untouched and still come first.
    assert names[:5] == ["the well", "the market", "the guildhall", "the lane", "the green"]


def test_a_settlement_that_names_its_own_entrance_gets_nothing_added():
    """The amendment is narrow: any entrance at all and the generator stays out of it."""
    from rules import places
    from play import library

    world = library.world("pangrella-campaign")
    for settlement in world.play["settlements"]:
        got = places.home_set(world.get(settlement["id"]))
        entrances = [p.name for p in got if p.name in places.ENTRANCES]
        assert entrances, settlement["name"]
        assert len([p for p in got if p.name == "the way in"]) <= 1, settlement["name"]


def test_an_entrance_is_not_staffed_like_a_shop():
    """The player asked for "an entrance or two that IS WATCHED", and the first attempt at
    that put a keeper on the gate through `places.STAFFED`. The suite refused it in its
    own words — `test_a_place_that_sells_nothing_gets_nobody`: "A keeper for every room
    would put a person in every empty street. The gate is watched by the guardhouse, not
    manned by a shopkeeper."

    That is the right call and this test holds it. STAFFED is for places that sell
    something or do something for money; watching a way in belongs to the law, which is a
    different system — and the law reaches every entrance now (see below), where before it
    could only ever find one called "gate"."""
    from rules import places

    for entrance in ("the gate", "the way in"):
        assert entrance not in places.STAFFED, (
            f"{entrance} is staffed like a shop; it is watched by the law instead")
    # And a town does have somewhere the watch lives, which is what does the watching.
    assert "the guardhouse" in places.STAFFED
    assert "the guardhouse" in places.ALWAYS_BY_SCALE["town"]
    assert "the guardhouse" in places.ALWAYS_BY_SCALE["city"]


def test_the_law_watches_every_kind_of_entrance():
    """The warrant check compared the place's name with the literal word "gate", so a
    village — which has a road rather than a gate — was somewhere being wanted could never
    be enforced. One list, read by the generator and the law alike."""
    from pathlib import Path

    from rules import places

    src = Path("rules/engine.py").read_text(encoding="utf-8")
    assert "in places_mod.ENTRANCES" in src
    assert 'removeprefix("the ") == "gate"' not in src
    assert "the way in" in places.ENTRANCES and "the gate" in places.ENTRANCES


def test_the_way_in_has_ground_of_its_own():
    """Without a shape it falls through to generic urban, and the map of a road would be
    an anonymous square room."""
    from rules import floorplan

    shape = floorplan.shape_for("abc~urban:the-way-in", "urban")
    assert shape.width > shape.height, "a road is longer than it is wide"
    assert "road" in (shape.about or "")


def test_travelling_between_places_redraws_the_ground():
    """Reported 2026-09-21, with the market's tray open: "the same map and the scale of
    the map is way too small." It was the same map — literally the well's.

    `place_party` has discarded the grid on arrival since group 11 ("New room, new
    ground"), and `_op_travel` never went through it: `Scene.move` changes where everybody
    stands and touches no map. So walking from the well to the market kept the well's 5x5
    empty floor, where the market is 12x12 with nine clumps of stalls — and left the PC
    with no position on it at all, so the panel offered nowhere to move to.
    """
    from play import library
    from rules import places as places_mod
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    world = library.world("aurvantis-campaign")
    vormoor = next(s for s in world.play["settlements"] if s["name"] == "Vormoor")
    scene = Scene(location_id=vormoor["id"])
    pc = instantiate("guildhand", scene=scene, name="Spree")
    pc.kind = "pc"
    scene.add(pc)
    engine = Engine(scene, Dice(seed=1), world=world)
    engine.place_party()
    first = (scene.grid.width, scene.grid.height)

    engine.run(engine.validate(
        [{"op": "travel", "actor": pc.ref, "because": "t",
          "params": {"place": "the market"}}], origin="author:test"))

    assert scene.at.endswith("the-market")
    assert scene.grid is not None
    assert (scene.grid.width, scene.grid.height) != first, "the old room's map stayed"
    assert (scene.grid.width, scene.grid.height) == (12, 12), "not the market's own shape"
    assert scene.grid.blocked, "the market's stalls are missing"
    assert pc.ref in scene.positions, "the party is not standing on the new ground"


def test_arriving_at_a_settlement_puts_the_party_at_its_way_in():
    """Reported 2026-09-21: "why would walking onto town take me to the market it should
    be the streets or the entry square or something like that."

    Unnamed, `place_party` stood the party at `places()[0]` — whatever the world listed
    first, the well in Vormoor — so a character finishing a week of road stepped straight
    into the middle of town. The entrance is the same list the law watches, so the door
    somebody arrives by is the door a warrant is checked at.
    """
    from play import library
    from rules import places as places_mod
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    world = library.world("aurvantis-campaign")
    for name in ("Vormoor", "Halhollow"):
        settlement = next(s for s in world.play["settlements"] if s["name"] == name)
        scene = Scene(location_id=settlement["id"])
        pc = instantiate("guildhand", scene=scene, name="Spree")
        pc.kind = "pc"
        scene.add(pc)
        Engine(scene, Dice(seed=1), world=world).place_party()
        here = places_mod.find(
            places_mod.for_scene(world.get(settlement["id"]), scene.at), scene.at)
        assert here is not None
        assert here.name in places_mod.ENTRANCES, (name, here.name)
