"""Ship rooms, a ship's cargo, the sewers' outfall and steps inside a place: playtest
2026-11-16 (Vesna Kroll, overnight on integrate/0.4.0, transcript T304-T328).

Each test names the item and what was measured in the save:

* #92 the hold of the Red Gull, taken from her merchant master, "held nothing": no cargo
  record, so a Perception search (a natural 1) decided whether the crates held goods;
* #95 hold to deck was "a few minutes' walk", the city's band for a ladder;
* #100 aboard her the head read "Mirabalos — city", and at sea it was blank;
* #91 stepping onto her at the quay told "The ground changes: a ship's planking";
* #83 the outfall under a port city was a dead end, its only exit back to the sewers;
* #79 down the grate and a few minutes along to the outfall was refused as a second
  journey;
* #80 "The sewers opens off the gardens".
"""
from __future__ import annotations

from gm.brief import BriefContext
from gm.brief import in_the_hold
from rules import geography, outskirts, places, ships, trade, words
from tests.test_playtest_2026_11_16_travel import MIRABALOS, _city, _place, _run
from tests.test_ships_and_piracy import _travel, held_at_quay  # noqa: F401 — the fixture
from tests.test_ships_at_sea import PANGRELLA


def _room(engine, ship, name):
    return next(p for p in ships.places_of(ship) if p.name == name)


def _brief(engine):
    return BriefContext(world=PANGRELLA, scene=engine.scene,
                        location=PANGRELLA.get(engine.scene.location_id), here=engine.here(),
                        known=tuple(engine.places()), recent_events=None, recent=None,
                        secret=False, turn=0, names_for=None, absent="", buying="",
                        reading=None, player_text="")


# --- #92: a trader's hold is laden, and what is in it is seen -------------------------------

def test_a_taken_traders_cargo_is_the_takers_in_her_hold_and_sells_at_the_quay(held_at_quay):
    """#92: the taken Red Gull carried no cargo, so a search roll decided whether there was
    any. A trader is laden off her home port's trade when first kept, and a prize's cargo
    becomes her taker's lots in her hold: priced by the trade table, sellable where she
    lies."""
    scene, engine, pc, ship = held_at_quay
    mine = trade.shipping_in(scene, ship.id)
    assert mine, scene.cargo
    assert all(x["owner"] == pc.ref and x["plunder"] == ship.id for x in mine)
    assert all(x["key"] in trade.ROWS and x["units"] > 0 for x in mine)
    assert engine.vessel(ship.id).cargo == []            # moved, not held twice
    # About three plunder points of goods, never more (S&S: ~1,000 gp a point).
    assert 0 < trade.book_value_cp(mine) <= 3 * ships.PLUNDER_GP * 100
    assert {x["id"] for x in trade.reachable(scene)} >= {x["id"] for x in mine}


def test_a_ship_nobody_has_taken_keeps_her_owners_cargo_out_of_the_partys_reach():
    """The other half of #92: a merchant's own cargo is hers until she is taken; selling
    it would be selling what is not the party's."""
    from tests.test_ships_at_sea import _at_port

    scene, engine, pc = _at_port()
    ship = ships.offered_at(MIRABALOS, "city", n=1)[0]
    ship.kind = "sailing ship"
    engine._keep_vessel(ship)
    kept = engine.vessel(ship.id)
    assert kept.cargo and not trade.lots(scene)
    # The same ship carries the same goods: seeded off her id, like her name.
    assert kept.cargo == ships.lading(ship.id, ship.kind,
                                      trade.supplied_at(PANGRELLA, MIRABALOS))
    assert ships.lading("x", "warship") == []


def test_standing_in_her_hold_the_brief_says_what_it_holds_as_fact(held_at_quay):
    """#92: "inspecting the various crates and barrels, but find nothing of value": the
    brief said nothing of a cargo. In her hold it says what is stowed, and that no search
    is needed to see it."""
    scene, engine, pc, ship = held_at_quay
    engine.place_party(_room(engine, ship, "the hold").id)
    text, facts = in_the_hold.section(_brief(engine))
    lot = trade.shipping_in(scene, ship.id)[0]
    assert trade.said(lot) in text and "no search needed" in text, text
    assert facts["hold"]["vessel"] == ship.id
    engine.place_party(ships.deck_of(ship))
    assert in_the_hold.section(_brief(engine)) == ("", {})


# --- #95: a ladder is seconds ----------------------------------------------------------------

def test_hold_to_deck_charges_no_minutes_and_says_no_walk(held_at_quay):
    """#95: hold to deck was charged the city's band and told as "a few minutes' walk";
    the narration stretched it to "several minutes"."""
    scene, engine, pc, ship = held_at_quay
    engine.place_party(_room(engine, ship, "the hold").id)
    before = scene.clock_minutes
    out = _travel(engine, _room(engine, ship, "the deck").id)
    assert out[-1].status == "resolved", out[-1].tell
    assert scene.clock_minutes == before
    assert "walk" not in out[-1].tell and "minute" not in out[-1].tell, out[-1].tell
    deck, hold = _room(engine, ship, "the deck"), _room(engine, ship, "the hold")
    assert outskirts.hop_minutes(hold, deck, "city") == 0


# --- #100: the head names the ship ------------------------------------------------------------

def test_aboard_at_the_quay_the_head_names_her_and_her_mooring(held_at_quay):
    """#100: in her hold the head read "Mirabalos — city"."""
    scene, engine, pc, ship = held_at_quay
    engine.place_party(_room(engine, ship, "the hold").id)
    w = geography.where(PANGRELLA, scene, engine.here())
    port = PANGRELLA.get(ship.at).name
    assert (w.setting, w.label, w.detail) == ("aboard", ship.name, f"moored at {port}")


def test_at_sea_the_head_names_her_and_where_she_is_bound():
    """#100: at sea, where the location is the ship, the head was blank."""
    from tests.test_ships_at_sea import ZHILVARNIA, _at_port, _journey

    scene, engine, pc = _at_port()
    _journey(engine)
    _journey(engine, days=1)
    ship = engine.aboard()
    assert ship is not None and not ship.at
    w = geography.where(PANGRELLA, scene, engine.here())
    assert w.label == ship.name and w.detail.startswith("at sea"), w
    if ship.bound_for == ZHILVARNIA:
        assert w.detail == f"at sea, bound for {PANGRELLA.get(ZHILVARNIA).name}"


def test_her_rooms_are_aboard_a_ship_to_the_beat_check():
    """Seen in the same save's turn log: "walk through the shadows of the ship's hold"
    was flagged "not aboard a ship or boat" with the player in her hold."""
    ship = ships.offered_at(MIRABALOS, "city", n=1)[0]
    for room in ships.places_of(ship):
        assert places.SET_SHIP in places.settings_for(room), room.name
        assert places.SET_STREET not in places.settings_for(room), room.name


# --- #91: boarding is boarding ------------------------------------------------------------

def test_stepping_aboard_from_the_quay_is_told_as_boarding_not_new_ground(held_at_quay):
    """#91: "The ground changes: a ship's planking: decks, rigging and the hold below"."""
    scene, engine, pc, ship = held_at_quay
    docks = next(p for p in engine.places() if p.name == "the docks")
    ashore = _travel(engine, docks.id)[0]
    assert "ground changes" not in ashore.tell and "ashore" in ashore.tell, ashore.tell
    aboard = _travel(engine, ships.deck_of(ship))[0]
    assert aboard.status == "resolved", aboard.tell
    assert "ground changes" not in aboard.tell, aboard.tell
    assert f"aboard {ship.name}" in aboard.tell, aboard.tell


# --- #83, #79, #80: the sewers ------------------------------------------------------------

def test_a_port_citys_outfall_opens_onto_its_waterside():
    """#83: the outfall was a dead end; under a port it opens by the docks, both ways."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    known = e.places()
    fall = next(p for p in known if p.name == "the outfall" and p.parent == s.at)
    water = places.find(known, fall.exits[-1])
    assert water.name in ("the harbour", "the docks", "the quay", "the wharf"), water.name
    assert fall.id in water.exits and water.name in fall.about


def test_an_inland_towns_outfall_is_left_as_it_was():
    """A town with no waterside place has nowhere for the outfall to open onto."""
    town = places.Place(id="t~urban:the-market", name="the market", about="", terrain="urban",
                        exits=())
    fall = places.Place(id="t~underground:the-market/the-sewers/the-outfall",
                        name="the outfall", about="where it meets the daylight",
                        terrain="underground", exits=(), parent="t~underground:the-market/"
                        "the-sewers", origin="venture")
    assert places._outfall_to_water((town, fall)) == (town, fall)


def test_down_the_grate_and_along_to_the_outfall_is_one_turn():
    """#79 (T304): the drop was freed from the journey guard in 0.3.9 (#41), but the few
    minutes along to the outfall was then refused: "One journey a turn". The save had been
    down these sewers before, so the outfall was a known place."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    e.place_party(_place(e, "the gardens").id)
    out = _run(e, {"op": "venture", "params": {"kind": "sewers"}},
               {"op": "travel", "params": {"place": "the outfall"}},
               {"op": "travel", "params": {"place": "the great square"}})
    assert [o.status for o in out] == ["resolved", "resolved", "refused"], [o.tell for o in out]
    assert s.at.endswith("the-gardens/the-sewers/the-outfall"), s.at
    # Out across the city is still the next turn's journey.
    assert "One journey a turn" in out[2].tell


def test_the_sewers_open_off_the_gardens():
    """#80: "The sewers opens off the gardens"."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    out = _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    assert "The sewers open off the gardens" in out[0].tell, out[0].tell
    assert "inside them before" in out[0].tell
    assert words.verb("the crypt", "opens", "open") == "opens"
    assert not words.is_plural("the pass") and words.is_plural("the ruins")
