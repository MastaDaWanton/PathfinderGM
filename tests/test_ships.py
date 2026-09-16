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


# --- closing, and then boarding ----------------------------------------------------------------
#
# The ruling, run end to end: ships close, and then people board, and the fight is on the
# deck. Five verbs and a band — no mat, no orientation to lose track of, and every rung of
# the approach a decision rather than a die roll dressed up.

def _at_sea(seed: int = 11, sailor: bool = False, ours_scale: str = "city",
            theirs_scale: str = "town"):
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    town = "5bbd0c40345f"
    scene = Scene(location_id=town)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    if sailor:
        # Paid for rather than added: the sheet is legality-checked on save, and a test
        # that hands a character free ranks is a test that would be caught by the engine
        # the moment it wrote the campaign to disk. It was.
        for skill, rank in sorted(pc.ranks.items(), key=lambda kv: -kv[1]):
            if rank and skill != "profession":
                pc.ranks[skill] = rank - 1
                pc.ranks["profession"] = pc.ranks.get("profession", 0) + 1
                break
    engine = Engine(scene, Dice(seed=seed), world=PANGRELLA)
    engine.place_party(f"{town}~urban:the-market")
    ours = ships.offered_at(town, ours_scale)[0]
    theirs = ships.offered_at("another-port", theirs_scale)[0]
    scene.vessels = [ours.as_dict(), theirs.as_dict()]
    scene.sea = {"ours": ours.id, "theirs": theirs.id, "range": "distant",
                 "grappled": False}
    scene.at = ships.deck_of(ours)
    pc.at = scene.at
    return scene, engine, ours, theirs


def _do(engine, do, face: int = 18, **params):
    res = engine.run(engine.validate(
        [{"op": "sea", "actor": "pc", "because": "the chase",
          "params": {"do": do, **params}}], origin="author:test"))
    if res.awaiting:
        res = engine.resume(face)
    return res.outcomes[-1]


def test_a_sail_on_the_horizon_becomes_oars_touching():
    """Three bands and one step a round. A player can hold that in their head from prose
    alone, which is the thing Deadfire's mat-less naval combat could not give anybody."""
    scene, engine, _ours, theirs = _at_sea()
    assert scene.sea["range"] == "distant"
    _do(engine, "close")
    assert scene.sea["range"] == "closing"
    _do(engine, "close")
    assert scene.sea["range"] == "alongside"
    _do(engine, "close")
    assert scene.sea["range"] == "alongside", "there is nothing closer than alongside"


def test_running_away_is_a_real_answer():
    """The book's ships are faster than they are tough, and a merchantman's best move is
    to be somewhere else. A fight you can decline is a fight worth having."""
    scene, engine, _ours, _theirs = _at_sea()
    _do(engine, "close")
    out = _do(engine, "sheer off")
    assert scene.sea == {}, "the engagement did not end"
    assert "only the sea" in out.tell


def test_the_grapnels_are_the_one_thing_you_cannot_take_back():
    """Everything else in the engagement is reversible in a round. That is what makes
    throwing them a decision rather than a formality."""
    scene, engine, _ours, _theirs = _at_sea()
    _do(engine, "close")
    _do(engine, "close")
    _do(engine, "grapple")
    assert scene.sea["grappled"] is True
    out = _do(engine, "sheer off")
    assert "not going anywhere" in out.tell
    assert scene.sea["range"] == "alongside"


def test_ramming_wants_a_sailor_and_says_so():
    """Profession (sailor) is trained-only, and the rule has teeth here: a party with
    nobody who has sailed cannot ram anybody. The refusal names what is missing rather
    than quietly rolling an untrained check the book does not allow."""
    _scene, engine, _ours, _theirs = _at_sea(sailor=False)
    _do(engine, "close")
    out = _do(engine, "ram")
    assert "no sailor" in out.tell and "Profession (sailor)" in out.tell


def test_a_ram_wants_a_run_at_them():
    """"The ship must move at least 30 feet and end with its bow adjacent." Alongside is
    too late and hull down is too far, which leaves exactly one band it happens from."""
    _scene, engine, _ours, _theirs = _at_sea(sailor=True)
    out = _do(engine, "ram")
    assert "way on" in out.tell
    _do(engine, "close")
    _do(engine, "close")
    assert "too late" in _do(engine, "ram").tell


def test_a_ram_that_lands_hurts_both_hulls():
    """"...inflicting damage as indicated on the ship statistics table to the target, as
    well as minimum damage to the ramming ship." A ram is a thing you do to a hull with
    a hull."""
    scene, engine, ours, theirs = _at_sea(sailor=True)
    _do(engine, "close")
    out = _do(engine, "ram", face=20)
    assert engine.vessel(theirs.id).hp < theirs.hp, out.tell
    assert engine.vessel(ours.id).hp < ours.hp, "the rammer took nothing"
    assert scene.sea["range"] == "alongside", "a ram ends alongside, hit or miss"


def test_boarding_puts_the_party_on_their_deck():
    """The whole point. The fight is not resolved out here — it happens on a deck, with a
    floor plan, a mast to put between you and them, and a rail with the sea past it."""
    scene, engine, _ours, theirs = _at_sea()
    _do(engine, "close")
    _do(engine, "close")
    out = _do(engine, "board")
    assert scene.at == ships.deck_of(theirs)
    assert places.terrain_of(scene.at) == ships.DECK
    assert "over the rail" in out.tell


def test_you_cannot_step_across_open_water():
    scene, engine, _ours, _theirs = _at_sea()
    assert "too far to step" in _do(engine, "board").tell
    assert scene.at != ""


def test_somebody_is_waiting_at_the_rail():
    """Arriving on an empty deck is the anticlimax the ruling exists to avoid. The watch
    comes from the NPC codex, by role words, at the party's own level — the same door a
    shop's keeper and a scheme's cast come through.

    A handful, never the crew list: a galley carries two hundred rowers, and two hundred
    creatures is not an encounter. What the count says is how many were quick enough to
    be there; the rest are why the fight has to be won before they come up."""
    scene, engine, _ours, theirs = _at_sea()
    _do(engine, "close")
    _do(engine, "close")
    out = _do(engine, "board")
    met = [a for a in scene.actors.values() if not a.is_pc]
    assert met, out.tell
    assert len(met) <= 4, [a.name for a in met]
    assert len({a.name for a in met}) == len(met), "the crew are all called the same thing"


def test_a_ship_with_nobody_aboard_is_boarded_unopposed():
    scene, engine, _ours, theirs = _at_sea()
    hulk = ships.Vessel.from_dict({**theirs.as_dict(), "crew": 0})
    scene.vessels = [v for v in scene.vessels if v["id"] != theirs.id] + [hulk.as_dict()]
    _do(engine, "close")
    _do(engine, "close")
    out = _do(engine, "board")
    assert "Nobody is on it" in out.tell


def test_the_engagement_and_the_hulls_survive_a_save(tmp_path, settings):
    """A hull does not heal and a chase does not reset."""
    from play import campaign as cm

    settings.CAMPAIGN_DIR = tmp_path
    scene, engine, _ours, theirs = _at_sea(sailor=True)
    _do(engine, "close")
    _do(engine, "ram", face=20)
    hurt = engine.vessel(theirs.id).hp
    c = cm.Campaign(id="sea-test", world_source="fixtures/pangrella-campaign.json",
                    scene=scene)
    c.save()
    back = cm.Campaign.load(c.path())
    assert back.scene.sea["range"] == "alongside"
    assert [v for v in back.scene.vessels if v["id"] == theirs.id][0]["hp"] == hurt


def test_nothing_happens_at_sea_with_nobody_to_fight():
    _scene, engine, _ours, _theirs = _at_sea()
    engine.scene.sea = {}
    assert "no other ship" in _do(engine, "close").tell
