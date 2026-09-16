"""Ships, and the water between continents (`rules/ships.py`, `rules/journey.py`).

Two rulings on 2026-09-16 and one measurement that made them urgent.

**"Continents should be separated by water unless otherwise specified."** The export
already carries what that needs — every settlement's ancestors run up through a CONTINENT
— so nobody has to author a coastline for it to be true. Measured the same hour: **48 of
Aurvantis's 48 travel legs cross a continent boundary**, and 2 of Pangrella's 5. Every one
of them was being walked, with a day count derived from tree depth. That is not a defect
in the export: a trade route is an economic relationship, and "Brackgate sells tempered
steel to Ashwatch" was never a claim that you can walk there. It is this app having read
an economic edge as a road.

**"There would be both land and sea travel unless every place is on the coast."** So a
crossing that starts inland starts on a road, and the tell says so rather than teleporting
the party onto a deck. A settlement is a port when it has somewhere for a ship to tie up.

**And ships close, then people board.** Pillars of Eternity II shipped text-based naval
combat that reviewers called the worst in any RPG: no orientation shown, tactically
trivial, and the winning move was always to close and board — which made the exchange a
tedious prelude to the fight that mattered. So the deck is a place with a floor plan, and
the fight happens on it. Table 7-49 is transcribed unaltered; a rowboat is deliberately
absent because it is not on that table.
"""
from __future__ import annotations

import pytest

from rules import biomes, floorplan, journey, places, ships, water
from world import loader

AURVANTIS = loader.load_cached("fixtures/aurvantis-campaign.json")
PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")


# --- the table is the book's -----------------------------------------------------------------

def test_table_7_49_is_transcribed_and_not_invented():
    """Five rows, the ones the GameMastery Guide prints. A rowboat is not among them —
    it lives in the vehicle rules, which this deliberately does not use — and adding one
    would be inventing Pathfinder."""
    assert set(ships.VESSELS) == {"keelboat", "longship", "sailing ship", "warship",
                                  "galley"}
    assert ships.VESSELS["galley"]["hp"] == 200
    assert ships.VESSELS["galley"]["ram"] == "6d6+24"
    assert ships.VESSELS["keelboat"]["ac"] == 8
    assert ships.VESSELS["sailing ship"]["speed"] == 60
    assert ships.HARDNESS == 5, "wood"
    # The bigger the hull the worse it dodges, which is the shape of the printed table.
    assert ships.VESSELS["keelboat"]["ac"] > ships.VESSELS["galley"]["ac"]


def test_a_ship_is_somewhere_to_stand():
    """The whole design. A deck is a place with a floor plan, so a fight on one is a
    fight this engine already knows how to run."""
    vessel = ships.offered_at("5bbd0c40345f", "city")[0]
    rooms = ships.places_of(vessel)
    assert rooms and rooms[0].name == "the deck"
    assert all(p.terrain == ships.DECK for p in rooms)
    assert all(p.parent == vessel.id for p in rooms)
    # Every room reachable from every other: a ship is not a maze.
    for room in rooms:
        assert len(room.exits) == len(rooms) - 1


def test_a_deck_is_not_the_sea():
    """Its own ground, and the reason is mechanical rather than tidy: a creature standing
    on planking is not swimming, so none of the underwater table may reach them."""
    assert ships.DECK in biomes.BIOMES
    assert not water.is_wet(ships.DECK)
    vessel = ships.offered_at("5bbd0c40345f", "town")[0]
    deck = ships.deck_of(vessel)
    assert places.terrain_of(deck) == ships.DECK
    shape = floorplan.shape_for(deck, ships.DECK)
    assert shape.ceiling is None and shape.vertical == "ledge", shape
    assert "rail" in shape.about


def test_the_same_port_keeps_the_same_ships():
    """Derived off the port's own id, so a harbour has its regulars: the player who took
    the Grey Gull out last month finds her at the same quay. Worth more to a campaign
    than a fresh roll every visit, and it costs nothing to store."""
    first = [(v.id, v.name, v.kind) for v in ships.offered_at("5bbd0c40345f", "city")]
    again = [(v.id, v.name, v.kind) for v in ships.offered_at("5bbd0c40345f", "city")]
    assert first == again
    other = [(v.id, v.name) for v in ships.offered_at("44ee0af3c2fd", "city")]
    assert other != first, "every port has the same ships"


def test_a_village_quay_does_not_keep_a_galley():
    """Two hundred oars do not tie up at a fishing village. What a port has is decided by
    the same `scale` everything else about a settlement reads."""
    for vessel in ships.offered_at("5bbd0c40345f", "village"):
        assert vessel.kind == "keelboat", vessel.kind
    kinds = {v.kind for v in ships.offered_at("5bbd0c40345f", "city")}
    assert kinds <= set(ships.BY_SCALE["city"])


# --- sinking ---------------------------------------------------------------------------------

def test_hardness_comes_off_before_the_hull():
    vessel = ships.offered_at("x", "town")[0]
    before = vessel.hp
    ships.take_damage(vessel, ships.HARDNESS)
    assert vessel.hp == before, "hardness did not absorb it"
    ships.take_damage(vessel, ships.HARDNESS + 10)
    assert vessel.hp == before - 10


def test_zero_is_sinking_and_not_sunk():
    """Ten rounds of people getting off, which is the only reason a ship fight has a
    clock worth feeling."""
    vessel = ships.offered_at("x", "town")[0]
    ships.take_damage(vessel, vessel.hp + ships.HARDNESS)
    assert vessel.hp == 0
    assert vessel.sinking == ships.SINKS_AFTER
    assert not vessel.afloat
    said = [ships.sink_tick(vessel) for _ in range(ships.SINKS_AFTER)]
    assert vessel.sinking == 0
    assert any("goes under" in s for s in said), said


def test_hitting_a_sinking_ship_hurries_it():
    """"Damage to sinking ships reduces remaining time by 1 round per 25 damage." The
    book's own rule, and the reason to keep shooting at something already lost."""
    vessel = ships.offered_at("x", "city")[0]
    ships.take_damage(vessel, vessel.hp + ships.HARDNESS)
    was = vessel.sinking
    ships.take_damage(vessel, ships.HASTEN_PER * 2 + ships.HARDNESS)
    assert vessel.sinking == was - 2


def test_a_ship_below_her_crew_does_not_sail():
    """The quiet reason you cannot simply steal a warship."""
    vessel = ships.Vessel(id="ship:x", name="the Test", kind="galley",
                          hp=200, crew=4)
    assert not ships.crewed(vessel)
    vessel.crew = ships.VESSELS["galley"]["crew"][0]
    assert ships.crewed(vessel)


# --- the water between continents ---------------------------------------------------------

def test_two_settlements_on_different_continents_are_across_water():
    """The ruling, as the export can already answer it."""
    settlements = AURVANTIS.play["settlements"]
    here = settlements[0]["id"]
    legs = journey.legs_from(AURVANTIS, here)
    assert legs, "no routes to test"
    assert all(leg.by_sea for leg in legs), [(l.to_name, l.by_sea) for l in legs]


def test_a_stated_road_is_the_otherwise_specified():
    """A world that wrote a road between two landmasses has said there is a way across —
    an isthmus, a causeway, a bridge — and a thing the world said beats a thing this app
    worked out."""
    settlements = AURVANTIS.play["settlements"]
    a = settlements[0]["id"]
    b = next(s["id"] for s in settlements
             if journey.continent_of(AURVANTIS, s["id"])
             != journey.continent_of(AURVANTIS, a))
    assert journey.crosses_water(AURVANTIS, a, b) is True
    assert journey.crosses_water(AURVANTIS, a, b, road="highway") is False


def test_two_settlements_on_one_continent_are_not():
    got = [(t["from_id"], t["to_id"]) for t in PANGRELLA.play["travel"]
           if journey.continent_of(PANGRELLA, t["from_id"])
           == journey.continent_of(PANGRELLA, t["to_id"])]
    assert got, "the fixture has no same-continent route left to check"
    for here, there in got:
        assert journey.crosses_water(PANGRELLA, here, there) is False


def test_a_world_with_no_continents_walks_everywhere_as_before():
    """Additive, and fail-open: a world that does not have that tier says nothing about
    water, so nothing changes for it."""
    assert journey.continent_of(None, "anything") == ""
    assert journey.crosses_water(None, "a", "b") is False


# --- not every place is on the coast ---------------------------------------------------------

def test_a_settlement_is_a_port_when_it_has_somewhere_to_tie_up():
    """And the measurement that goes with it, which is an ask rather than a bug.

    **Nothing in the export says a settlement is on the coast.** Aurvantis has 11 ports
    out of 64 and every one of them is this app's own cue table minting a docks out of
    the settlement's prose — "a port town with a quay". Pangrella has **none out of 12**,
    and the reason is worth knowing: its places are authored, an authored list replaces
    the generated one by design, and so the cue that was the only way to spot a port
    never fires. Authoring places removed the one signal this app had.

    So the rule is fail-closed and stays that way until the supplier ships a marker: a
    settlement with nowhere to tie up is inland, whatever its prose says about the view.
    """
    ports = [s["name"] for s in AURVANTIS.play["settlements"]
             if journey.is_port(AURVANTIS, s["id"])]
    inland = [s["name"] for s in AURVANTIS.play["settlements"]
              if not journey.is_port(AURVANTIS, s["id"])]
    assert ports and inland, "every settlement in the world is the same kind"
    # Pangrella authors its places, which is why it has no ports at all.
    assert not [s for s in PANGRELLA.play["settlements"]
                if journey.is_port(PANGRELLA, s["id"])]


def test_a_crossing_from_inland_starts_on_a_road():
    """"There would be both land and sea travel unless every place is on the coast." The
    tell says the road first rather than teleporting the party onto a deck."""
    here = AURVANTIS.play["settlements"][0]["id"]
    leg = journey.legs_from(AURVANTIS, here)[0]
    hours, _measured, how = journey.hours_for(leg, 30)
    said = journey.describe(leg, hours)
    assert how == "sea"
    assert "at sea" in said
    if not leg.from_port:
        assert "road to the coast" in said, said


def test_a_passage_is_counted_in_whole_days_of_the_ship_making_way():
    """A ship keeps watches and does not camp at dusk, which is most of why the sea is
    faster than the road at the same speed. So a sea day is twenty-four hours where a
    marching day is eight."""
    here = AURVANTIS.play["settlements"][0]["id"]
    leg = journey.legs_from(AURVANTIS, here)[0]
    hours, _m, how = journey.hours_for(leg, 30)
    assert how == "sea"
    assert hours % ships.HOURS_AT_SEA == 0, hours
    assert ships.HOURS_AT_SEA == 24 and journey.HOURS_PER_DAY == 8


def test_a_crossing_never_takes_less_than_a_day():
    """A crossing that takes an afternoon is a ferry, and a ferry is a road with water
    under it rather than a passage."""
    assert ships.days_for(1, "galley") == 1
    assert ships.days_for(None, "keelboat", 0) == 1


def test_the_wind_is_worth_double_and_says_so():
    """The one weather rule in the book's ship table, and it is on the table itself."""
    assert ships.days_for(2000, "sailing ship", with_the_wind=True) \
        < ships.days_for(2000, "sailing ship")


# --- and the road still works -----------------------------------------------------------------

def test_a_land_journey_is_untouched():
    """Everything here is additive. A leg that crosses no water is the journey this app
    has always made, down to the wording."""
    got = [t for t in PANGRELLA.play["travel"]
           if journey.continent_of(PANGRELLA, t["from_id"])
           == journey.continent_of(PANGRELLA, t["to_id"])]
    here = got[0]["from_id"]
    leg = next(l for l in journey.legs_from(PANGRELLA, here) if not l.by_sea)
    hours, _m, how = journey.hours_for(leg, 30)
    assert how in ("exact", "derived")
    assert "on the road" in journey.describe(leg, hours)
