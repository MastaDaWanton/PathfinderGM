"""Where the party is standing, as something the engine can refuse.

The bug, from a live session: the player left a merchant's building for the square, the
GM narrated the square and four men in it, and the next beat was back inside by the fire
with somebody several turns dead. A stall and the square outside it are the same
`location_id` and the same `biome`, so the move changed nothing the engine could see.

The first fix made the room a free-text field written straight from a model param — which
is the narrator establishing a fact rather than proposing one, and gave "where the party
is" a second writer beside `thread["where"]`. This is the second fix: a closed, seeded,
engine-owned list, stated in the brief and refused off it, which is the courtesy the ref
registry has always extended to people and never to places.
"""
from __future__ import annotations

import pytest

from rules import places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


class _Loc:
    """Just enough world entity: the id is the only load-bearing part."""

    def __init__(self, id="loc-1", name="Zhilvarnia", kind="CITY", scale="city"):
        self.id, self.name, self.kind, self.scale = id, name, kind, scale


def _scene(biome="urban", location_id="loc-1"):
    s = Scene(location_id=location_id)
    stand_on(s, biome)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s, Engine(s, Dice(seed=7))


def test_a_town_has_the_same_rooms_every_session():
    """Seeded off the location's own durable id, not `hash()` — Python salts string
    hashing per process, so the same town would lay itself out differently after a
    restart. That is the class of bug the campaign save exists to prevent, arriving
    through the back door."""
    first = [p.id for p in places.spots_for(_Loc())]
    again = [p.id for p in places.spots_for(_Loc())]
    assert first == again and len(first) > 1

    # A different town is a different layout, not a copy with the same names.
    other = [p.id for p in places.spots_for(_Loc(id="loc-2"))]
    assert other != first


def test_the_list_is_closed_and_small():
    """Fate caps a conflict at "two to four zones"; Inform's Recipe Book calls for "a
    small number of named positions". An open-ended list is free text wearing a tuple."""
    for loc in (_Loc(), _Loc(id="x", kind="RUIN", scale="site")):
        got = places.spots_for(loc)
        # The ceiling is per SCALE now — a village of five, a town of nine, a city of
        # eighteen plus its junctions — because one number for a hamlet and a capital was
        # the thing that made every settlement in every world the same six rooms.
        assert 1 < len(got) <= places.MOST_IN_A_SETTLEMENT + places.CITY_QUARTERS + 1
        assert len({p.id for p in got}) == len(got), "two places share an id"


def test_with_nowhere_named_there_is_one_place_and_no_way_out():
    """Fail closed. The party is always somewhere, and somewhere unknown refuses every
    move rather than inventing a destination for the narrator to commit to."""
    got = places.spots_for(None)
    assert len(got) == 1 and got[0].exits == ()


def test_the_ground_chooses_the_table_when_the_world_is_not_to_hand():
    """An engine built without a world still has `scene.location_id` and `scene.biome`,
    and between them that is enough — derivation, not a guess."""
    town = {p.name for p in places.spots_for("loc-1", terrain="urban")}
    wild = {p.name for p in places.spots_for("loc-1", terrain="forest")}
    assert town != wild
    assert "the market" in town and "the market" not in wild


def test_walking_to_another_place_sheds_the_room_it_left():
    """The reported bug. A change of room is a scene transition and sheds its cast
    exactly as a change of biome always did — the merchant stays in his stall."""
    s, engine = _scene()
    start = engine.here()
    other = next(p for p in engine.places() if p.id != start.id)

    got = engine.run(engine.validate(
        [{"op": "travel", "because": "she walks out",
          "params": {"place": other.name}}]))

    assert engine.here().id == other.id
    assert s.biome == "urban", "a change of room is not a change of ground"
    assert list(s.actors) == ["pc"], "the merchant followed her out of his own stall"
    assert other.name in got.outcomes[0].tell


def test_a_place_that_does_not_exist_is_refused_with_the_ones_that_do():
    """The difference between the model CHOOSING a place and INVENTING one. A rewrite
    naming a real place works, so this raises rather than printing — the test stage 7
    sets for a correct raise — and it names the fix, which is the contract's rule."""
    s, engine = _scene()
    with pytest.raises(IntentError) as e:
        engine.run(engine.validate(
            [{"op": "travel", "because": "she goes",
              "params": {"place": "the docks"}}]))
    said = str(e.value)
    assert "no 'the docks' here" in said
    for p in engine.places():
        assert p.name in said, "the refusal must say what would have worked"


def test_a_name_is_matched_leniently_and_refused_hard():
    """"market", "the market" and the raw id all mean the same place; anything else
    means none of them."""
    known = places.spots_for(_Loc())
    first = known[0]
    for said in (first.id, first.name, first.name.removeprefix("the ")):
        assert places.find(known, said) is first
    assert places.find(known, "the moon") is None
    assert places.find(known, "") is None


def test_new_ground_is_a_real_place_and_the_town_is_still_there():
    """Open ground is a REGION of the location — `{location}~forest:the-approach` — not
    a blank. Stage 8a blanked `at` on a biome change, which left the party pointing at
    nowhere and the ground in a sibling field; the ground lives inside the id now, and
    "the market" still resolves from the forest so the party can walk back."""
    s, engine = _scene()
    was = engine.here().id
    engine.run(engine.validate(
        [{"op": "travel", "because": "she makes for the treeline",
          "params": {"biome": "forest"}}]))
    assert s.biome == "forest"
    assert places.terrain_of(s.at) == "forest" and s.at != was
    assert engine.here().id == s.at, "the party is standing somewhere places() knows"
    assert places.find(engine.places(), "the market") is not None, \
        "the town vanished the moment she stepped outside it"
    assert list(s.actors) == ["pc"], "the merchant followed her into the forest"
    assert s.people["c1"].at == was, "the merchant is not where she left him"


def test_every_place_a_settlement_can_earn_is_a_place_it_can_have():
    """The cue table mints a place by NAME and the settlement table builds it by name, so
    a row in one and not the other is a place the world can ask for and never receive.

    Measured 2026-09-15, the day the settlement vocabulary was rebuilt: `the mine head`,
    `the library` and `the keep` were all earnable and none of the three was in the new
    table, so Vyrakon's own paragraphs asked for a mine head and got a warehouse. Silent,
    because an unearned place is indistinguishable from one the seed did not pick.
    """
    buildable = {label for label, *_rest in places.SETTLEMENT_PLACES}
    for _words, (spot, _about) in places.IMPLIED:
        assert spot in buildable, (
            f"{spot!r} can be earned from a settlement's own words and is not in "
            f"SETTLEMENT_PLACES, so nothing can build it")


def test_every_place_has_somewhere_to_happen():
    """A place with no tuned shape falls through to plain `urban` — a workable room, and
    the same room every time. The vocabulary is the thing a player sees; the shape is the
    thing they fight in, and a bathhouse that fights like a gaol is half a place."""
    from rules import floorplan

    for label, *_rest in places.SETTLEMENT_PLACES:
        slug = label.strip().lower().replace(" ", "-")
        assert slug in floorplan.BY_SPOT, f"{label!r} has no room to happen in"
