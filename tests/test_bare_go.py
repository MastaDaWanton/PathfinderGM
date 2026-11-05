"""A walk with nowhere named asks where to in a few names, and "the town" is a place
(owner report 2026-11-01, Corvin, turns 33 and 35).

"go" and "go to the town" from the smithy in Reedsink were each refused "Nobody moves:
where to? From here you can reach …" with sixty names — the smithy the party stood in,
fourteen upper floors and undercrofts, and seventeen biomes including "deck", "planar"
and "underwater" — and the sentence reached the player. "the town" named no place at all,
so the plan's travel had nowhere in it.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import places as places_mod
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "58b90a214ada"                                  # Zhilgoroth, a quartered city
MARKET = f"{TOWN}~urban:the-market"


def _table(at=MARKET):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(at)
    return s, e


def _travel(e, **params):
    return e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t",
                              "params": params}], origin="author:test")).outcomes[-1]


def test_where_to_names_a_few_places_and_never_a_floor_the_spot_or_a_biome():
    s, e = _table()
    assert len(e.places()) > 30, "the measurement needs a big town"
    out = _travel(e)
    assert out.effects == [] and "where to?" in out.tell
    listed = out.tell.split("From here you can reach ", 1)[1].split(", or one of")[0].split(", ")
    assert len(listed) <= Engine.WHERE_TO_SHOWN, listed
    assert "the market" not in listed, "the place underfoot was offered"
    assert not [n for n in listed if places_mod.storey_of(
        places_mod.find(e.places(), n).id) != 0], listed
    for biome in ("planar", "deck", "underwater", "tundra"):
        assert biome not in out.tell
    assert "other places" in out.tell
    assert len(out.tell) < 300, len(out.tell)


def test_the_places_next_door_come_first():
    s, e = _table()
    here = places_mod.find(e.places(), MARKET)
    out = _travel(e)
    first = out.tell.split("From here you can reach ", 1)[1].split(", ")[0]
    assert places_mod.find(e.places(), first).id in here.exits


def test_the_town_from_inside_is_its_middle():
    s, e = _table()
    out = _travel(e, place="the town")
    assert s.at == f"{TOWN}~urban:the-great-square", out.tell


def test_the_town_from_outside_is_its_way_in():
    s, e = _table()
    outskirts = next(p for p in e.places() if p.name == "the outskirts")
    e.place_party(outskirts.id)
    out = _travel(e, place="the city")
    here = places_mod.find(e.places(), s.at)
    assert " ".join(here.name.split()).lower() in places_mod.ENTRANCES, out.tell


def test_the_settlements_own_name_means_the_town():
    name = WORLD.get(TOWN).name
    s, e = _table()
    hit = places_mod.the_settlement(e.places(), name, MARKET, name)
    assert hit is not None and hit.name == "the great square"
    assert places_mod.the_settlement(e.places(), "the docks", MARKET, name) is None


def test_go_to_the_town_is_built_whole_from_the_reading():
    """Corvin's turn 35: the reading's `go: the town` becomes the walk, built by the table."""
    s, e = _table(f"{TOWN}~urban:the-smithy" if places_mod.find(
        _table()[1].places(), "the smithy") else MARKET)
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the town", "span": "go to the town"}]},
        s, places=tuple(e.places()))
    built = rows[0].intents
    assert built and built[0]["op"] == "travel"
    assert built[0]["params"]["place"] == "the great square"
