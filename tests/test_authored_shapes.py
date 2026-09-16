"""The room is the size the world says it is.

World Bible has written four things about every place it ships since schema 1.3 —
`size_ft`, `clutter`, `footing` and `vertical` — and for two releases nothing read one of
them. Measured 2026-09-16 across both shipped fixtures: **456 authored places, all four
fields on every one, and not a single reader.** Every fight in an authored room was fought
on a shape this app invented from the room's NAME: Ashwatch's market is written 75 by 70
feet and was laid out as the table's generic 16 by 16, and a room whose name the table did
not know got the twenty-by-twenty blank field that the whole of stages 1 to 7 existed to
remove.

That is the same defect this project keeps finding and it is worth naming again: a feature
described and not delivered. `docs/campaign-format.md` asked for these fields, World Bible
built them, the loader carried them as far as a dict, and `rules/places._authored` dropped
them on the floor.

The reader is `floorplan.from_world`, and the arrangement around it is the one the module
already had: the shape is derived where nothing authored it, handed DOWN from the `Place`
where something did, and never looked up — `floorplan` has no world and must not acquire
one.

What changed in play, measured over the 456: the median room goes from 160 squares to 99,
because real rooms are smaller than the generous ones a table invents. A quarter of them
land on the six-square floor. That is the world being honoured rather than a regression,
and the floor is what stops a fifteen-foot closet from being a scene with nowhere to stand.
"""
from __future__ import annotations

import statistics

from rules import floorplan, places
from world import loader

AURVANTIS = loader.load_cached("fixtures/aurvantis-campaign.json")
PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
ASHWATCH = "44ee0af3c2fd"


def _places(world):
    for s in world.play["settlements"]:
        for p in places.home_set(world.get(s["id"])):
            yield p


def _market():
    return next(p for p in places.home_set(AURVANTIS.get(ASHWATCH))
                if p.name == "the market")


# --- the world's dimensions reach the ground ---------------------------------------------

def test_the_market_is_the_size_the_export_wrote():
    """The measurement, as an assertion. 75 by 70 feet is 15 by 14 squares, and the table
    would have said 16 by 16 — close enough to look right and not what the world said."""
    shape = _market().shape
    assert shape is not None, "the authored shape was dropped again"
    assert (shape.width, shape.height) == (15, 14), shape
    assert shape.width * floorplan.FEET_PER_SQUARE == 75


def test_every_authored_place_carries_its_own_shape():
    """All 456 of them, in both fixtures. One that comes back None is one whose four
    fields went back to being decoration."""
    got = [p for p in list(_places(AURVANTIS)) + list(_places(PANGRELLA))]
    assert len(got) == 456, len(got)
    assert all(p.shape is not None for p in got), [
        p.id for p in got if p.shape is None][:5]


def test_a_generated_place_still_derives_its_shape():
    """Nothing else changes — the promise `_authored` was written under. A world that
    ships no rooms, which is every export at 1.2 or below, lays out exactly as before."""
    class Loc:
        id = "aaaabbbbcccc"; name = "Testville"; kind = "CITY"; scale = "town"
        facts = {}; prose = ""; places = []

    for p in places.home_set(Loc()):
        assert p.shape is None
        assert floorplan.shape_for(p.id, p.terrain) is floorplan.BY_SPOT.get(
            p.id.rsplit(":", 1)[-1], floorplan.shape_for(p.id, p.terrain))


def test_the_ground_keeps_the_phrase_the_tell_is_built_from():
    """The export's `about` for the market is "A merchant oligarchy that outspends the
    nobility" — a line about the settlement's politics, which said of a floor is nonsense.
    The dimensions are the world's and the phrase stays the table's."""
    shape = _market().shape
    assert shape.about == floorplan.BY_SPOT["the-market"].about
    assert "stalls" in shape.about


# --- what the four words mean underfoot ---------------------------------------------------

def test_clutter_puts_things_in_the_way_and_bare_does_not():
    """Four words, and they have to differ on the board or they are decoration."""
    raw = {"size_ft": {"width": 70, "depth": 70, "height": None}, "footing": "firm",
           "vertical": "none"}
    counts = {word: floorplan.from_world(dict(raw, clutter=word)).clumps
              for word in ("bare", "some", "cluttered", "dense")}
    assert counts["bare"] < counts["some"] < counts["cluttered"] < counts["dense"], counts
    # Calibrated against the shapes written by hand: "some" in a room this size is about
    # what the tavern and the market were already given.
    assert 4 <= counts["some"] <= 9, counts


def test_footing_is_bad_going_and_firm_is_nearly_none():
    raw = {"size_ft": {"width": 70, "depth": 70, "height": None}, "clutter": "some",
           "vertical": "none"}
    rough = {word: floorplan.from_world(dict(raw, footing=word)).rough
             for word in ("firm", "broken", "bad")}
    assert rough["firm"] < rough["broken"] < rough["bad"], rough
    assert rough["firm"] <= 6, rough


def test_the_vertical_kind_is_the_one_the_world_wrote():
    raw = {"size_ft": {"width": 70, "depth": 70, "height": None}, "clutter": "some",
           "footing": "firm"}
    for kind in floorplan.VERTICAL_KINDS:
        assert floorplan.from_world(dict(raw, vertical=kind)).vertical == kind


def test_a_height_of_null_is_a_place_with_no_roof():
    """241 of the 456 are written that way and they are the yards, the greens and the
    streets. Empty is not absent: a place that wrote a size with no height has SAID there
    is no roof, and only a place that wrote no size at all keeps the table's ceiling."""
    open_air = floorplan.from_world(
        {"size_ft": {"width": 70, "depth": 70, "height": None}, "clutter": "some",
         "footing": "firm", "vertical": "none"},
        floorplan.BY_SPOT["the-tavern"])
    assert open_air.ceiling is None, "the table's roof was kept over an open yard"
    roofed = floorplan.from_world(
        {"size_ft": {"width": 70, "depth": 70, "height": 20}, "clutter": "some",
         "footing": "firm", "vertical": "none"})
    assert roofed.ceiling == 4, roofed


def test_the_roof_the_world_wrote_is_the_one_the_stairs_read():
    """One source, or a tavern is indoors for the purposes of stairs and outdoors for the
    purposes of flying over it — which is the trap `is_indoors` was written to avoid and
    which an authored ceiling could have reopened."""
    market = _market()
    assert not places.is_indoors(market.id, market.terrain, market.shape)
    assert places.storeys(market.id, market.terrain, market.shape) == (0,)
    tavern = next(p for p in places.home_set(AURVANTIS.get(ASHWATCH))
                  if p.name == "the tavern")
    assert places.is_indoors(tavern.id, tavern.terrain, tavern.shape)


def test_a_ten_foot_lane_is_still_ten_feet():
    """The floor was thirty feet and it was wrong. The supplier argued it better than it
    had been argued for: **"a lane ten feet across is an alley; the same lane at thirty
    feet is a street."** Two real consequences followed — "walls close on both sides" is
    this app's own stated reason for keeping lanes flat, and a thirty-foot floor removes
    the geometry that reason depends on; and their generator's narrow-room rule fired on
    anything three squares or less, which a floor of six made unreachable for ever.

    Two squares now: ten feet, the width two Medium creatures can pass in."""
    narrow = floorplan.from_world({"size_ft": {"width": 10, "depth": 60, "height": None},
                                   "clutter": "some", "footing": "firm",
                                   "vertical": "none"})
    assert narrow.width == 2, narrow
    assert floorplan.MIN_SQUARES * floorplan.FEET_PER_SQUARE == 10


def test_a_fight_in_the_narrowest_room_the_world_ships_puts_nobody_off_the_board():
    """The half of the alley fix which is not the floor.

    The party was placed at column 4 of the grid, which was safe while every room was at
    least twelve squares wide and stopped being safe the moment a ten-foot lane became
    authorable. Driven on the narrowest room in either shipped world — a five-square well
    — because a synthetic room proves the arithmetic and a real one proves the path.
    """
    narrow = "b8a937672991"
    room = next(p for p in places.home_set(AURVANTIS.get(narrow)) if p.name == "the well")
    assert room.shape.width <= 6, room.shape
    scene, _foe = _fight(room, location_id=narrow)
    assert scene.grid.width == room.shape.width
    for ref, spot in scene.positions.items():
        assert 0 <= spot[0] < scene.grid.width, (ref, spot, scene.grid.width)
        assert 0 <= spot[1] < scene.grid.height, (ref, spot, scene.grid.height)


def test_nothing_comes_out_smaller_than_a_scene_or_bigger_than_a_map():
    """A five-foot crack is not a room; a 125-foot square is a real square and 25 squares
    is more map than anybody reads. Both ends are clamped, and the clamp is published as
    a field rather than left in a sentence for somebody to parse."""
    every = [p.shape for p in list(_places(AURVANTIS)) + list(_places(PANGRELLA))]
    assert min(min(s.width, s.height) for s in every) >= floorplan.MIN_SQUARES
    assert max(max(s.width, s.height) for s in every) <= floorplan.MAX_SQUARES


def test_the_rooms_are_smaller_than_the_ones_this_app_invented():
    """The headline consequence, stated so nobody has to rediscover it: real rooms are
    smaller than generous ones. If this ever inverts, the reader has stopped reading."""
    mine = [p.shape.width * p.shape.height for p in _places(AURVANTIS)]
    table = [floorplan.shape_for(p.id, p.terrain).width
             * floorplan.shape_for(p.id, p.terrain).height for p in _places(AURVANTIS)]
    assert statistics.median(mine) < statistics.median(table), (
        statistics.median(mine), statistics.median(table))


# --- the floors above it ------------------------------------------------------------------

def test_an_upstairs_room_is_a_floor_of_the_building_the_world_measured():
    """`floorplan._upstairs` derives a floor from the shape below it — "the same
    footprint, divided up more". Handed nothing, it would have derived the upper rooms of
    a world-measured tavern from the generic tavern in the table: Ashwatch's tavern is 8
    by 6 and the table's is 12 by 10, so the bedrooms would have been bigger than the
    taproom under them."""
    known = places.for_scene(AURVANTIS.get(ASHWATCH), f"{ASHWATCH}~urban:the-tavern")
    tavern = next(p for p in known if p.name == "the tavern")
    upstairs = [p for p in known if p.parent == tavern.id]
    assert upstairs, "the tavern has no floors"
    for floor in upstairs:
        assert floor.shape is tavern.shape, f"{floor.name} lost the building it is in"
        shape = floorplan.shape_for(floor.id, floor.terrain, floor.shape)
        assert shape.width <= tavern.shape.width, (floor.name, shape)


def test_a_building_has_the_floors_the_world_counted():
    """The fifth unread field, found while wiring the other four: the export writes
    `storeys: {"up": n, "down": n}` on 177 of the 456 places and this app rolled its own
    number off a seed. Ashwatch's tavern is authored one floor up and none down; the
    generator gave it an undercroft, an upper floor AND a top floor — a two-room village
    pub with four levels in it."""
    known = places.for_scene(AURVANTIS.get(ASHWATCH), f"{ASHWATCH}~urban:the-tavern")
    tavern = next(p for p in known if p.name == "the tavern")
    assert tavern.floors == (0, 1), tavern.floors
    floors = [p for p in known if p.parent == tavern.id]
    assert len(floors) == 1, [p.name for p in floors]
    assert "upper floor" in floors[0].name
    keep = next(p for p in known if p.name == "the keep")
    assert keep.floors == (-1, 0, 1, 2), keep.floors


def test_a_building_the_world_did_not_count_still_counts_itself():
    """Every export at 1.2 and below, and the 207 places that write `storeys: null`.
    Deriving is not a fallback here — it is what a floor count was before there was one to
    read, and it has to keep working exactly as it did."""
    assert places.storeys(f"{ASHWATCH}~urban:the-tavern", "urban",
                          floorplan.BY_SPOT["the-tavern"]) == places.storeys(
        f"{ASHWATCH}~urban:the-tavern", "urban", floorplan.BY_SPOT["the-tavern"], ())


def test_open_sky_beats_a_claim_of_storeys():
    """The handoff tells an author that no place may claim storeys and open sky at once.
    This is what happens to one that does: the roof decides, because a market with an
    upstairs is a market with a staircase into the air."""
    assert places.storeys("x~urban:the-market", "urban",
                          floorplan.BY_SPOT["the-market"], (0, 1, 2)) == (0,)


def test_giving_a_room_its_floors_does_not_drop_anything_else_about_it():
    """A defect this field found rather than caused. `with_storeys` rebuilt the ground
    floor by typing out its fields, so every field nobody remembered to list was lost —
    `within` has been dropped here since districts arrived, which took a roofed room in a
    city quarter and handed it back hanging off nothing. It copies the place now."""
    class City:
        id = "ccccddddeeee"; name = "Bigtown"; kind = "CITY"; scale = "city"
        facts = {}; prose = ""; places = []

    known = places.for_scene(City(), "")
    within = [p for p in known if p.within]
    assert within, "a generated city has no quarters to lose"
    with_floors = [p for p in within if any(q.parent == p.id for q in known)]
    assert with_floors, "no roofed room in a quarter; the case cannot reproduce"
    for p in with_floors:
        assert p.within, f"{p.name} came out of with_storeys hanging off nothing"


# --- and it reaches the fight -------------------------------------------------------------

def _fight(place, spawn_far=False, location_id=ASHWATCH):
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene(location_id=location_id)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=AURVANTIS)
    engine.place_party(place.id)
    foe = scene.add(instantiate("thug", scene=scene, name="Thug"),
                    zone="far" if spawn_far else "near")
    engine.run(engine.validate(
        [{"op": "begin_encounter", "because": "a fight",
          "params": {"sides": {"party": ["pc"], "them": [foe.ref]}}}],
        origin="author:test"))
    return scene, foe


def test_the_fight_is_laid_out_on_the_room_the_world_measured():
    """The whole point of the reader. `_lay_battlefield` had never heard of the export."""
    market = _market()
    scene, _foe = _fight(market)
    assert (scene.grid.width, scene.grid.height) == (market.shape.width,
                                                     market.shape.height)


def test_a_room_the_world_measured_does_not_grow_to_fit_an_archer():
    """Found while wiring this up, and it would have undone the whole reader: when a
    combatant would stand off the edge, `_lay_battlefield` widened the GRID. A thirty-foot
    shop became a seventy-foot hall the moment somebody spawned at `far`, so the authored
    dimensions survived exactly until a fight started in them. The room is the room now,
    and the distance is what gives way; open ground nobody measured still grows, because a
    bowshot is twenty-four squares and the blank field is twenty."""
    market = _market()
    scene, foe = _fight(market, spawn_far=True)
    assert scene.grid.width == market.shape.width, "the walls moved for the archer"
    x, y = scene.positions[foe.ref][:2]
    assert 0 <= x < scene.grid.width and 0 <= y < scene.grid.height
