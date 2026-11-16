"""A ship the player took: getting back aboard her, sailing her, her people, and piracy.

Playtest 2026-11-16 (a human outlaw who took the Red Gull by threat at sea). Each test names
the item and what was measured:

* #19 / #22 "I board my ship, the Red Gull" at the docks she had just tied up at was refused
  "There is no road from here to the Red Gull", and "I go aboard the Red Gull" "You don't
  know of anywhere called the Red Gull here": a held ship was unreachable once ashore;
* #14 "I go back aboard the Red Gull" walked her half an hour to the merchants row;
* #18 "climb aboard" did nothing; #20 the docks' exits offered paid passage and not her;
* #12 / #13 she came into port with the captain she was taken from aboard, her new owner
  went ashore, and nothing happened, nor did anything say what her people do;
* #8 / #9 "take the Red Gull out along the trade route, hunting for a merchant ship to
  rob" was refused (no such port) and "a merchant ship" was looked up as a person.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops
from play import exits
from rules import morale, ontheway, places, ships, states
from rules.bestiary import instantiate
from tests.test_ships_at_sea import PANGRELLA, _at_port, _journey

DOCKS_NAME = "the docks"


@pytest.fixture
def held_at_quay(monkeypatch):
    """The Red Gull's case: booked at Mirabalos, a day out, taken (her people yielded),
    and sailed into port by her new owner, who is still on her deck."""
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "calm")
    monkeypatch.setattr(ontheway, "sea", lambda *a, **k: None)
    scene, engine, pc = _at_port()
    _journey(engine)                        # booked for Zhilvarnia: aboard at the quay
    _journey(engine, days=1)                # a day out
    ship = engine.aboard()
    for a in engine.crew_of(ship):
        a.add_condition(morale.YIELDED_KEY, None, source="test", origin="test")
    ship.held_by = pc.ref
    engine._keep_vessel(ship)
    out = _journey(engine, to="Zhilvarnia")
    ship = engine.vessel(ship.id)
    assert ship.at == "6953424c8a82" and ships.vessel_of(scene.at) == ship.id, out.tell
    return scene, engine, pc, ship


def _travel(engine, place):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "travel", "actor": "pc", "because": "walk", "params": {"place": place}}],
        origin="author:test"))
    return res.outcomes


def _docks(engine):
    return next(p for p in engine.places() if p.name == DOCKS_NAME)


def test_a_held_ship_makes_port_with_her_master_still_aboard(held_at_quay):
    """#12/#19: she tied up and her new owner was put ashore like a passenger; now the
    deck is where she stays, and going ashore is her own step."""
    scene, engine, pc, ship = held_at_quay
    assert engine.aboard().id == ship.id


def test_ashore_her_ship_is_a_place_by_her_name_and_a_journey_to_her_boards(
        held_at_quay, monkeypatch):
    """#19/#22: "board my ship, the Red Gull" (a journey) and "go aboard the Red Gull" (a
    walk) both found no such place once she was ashore. #14: the walk went to the
    merchants row. A deck is no street either: boarding met a squabble "in the middle of
    the road at the Red Gull"."""
    scene, engine, pc, ship = held_at_quay
    _travel(engine, _docks(engine).id)
    assert not ships.vessel_of(scene.at)
    named = places.find(engine.places(), ship.name)
    assert named is not None and named.id == ships.deck_of(ship)
    assert named.id in _docks(engine).exits
    monkeypatch.setattr(ontheway, "street", lambda *a, **k: pytest.fail("a street meeting"))
    out = _journey(engine, to=ship.name)
    assert out.status == "resolved", out.tell
    assert scene.at == ships.deck_of(ship)
    monkeypatch.undo()
    _travel(engine, _docks(engine).id)
    _travel(engine, ship.name)
    assert scene.at == ships.deck_of(ship)


def test_her_rooms_answer_to_her_name_aboard_and_ashore(held_at_quay):
    """Live 2026-11-16: aboard her, "climb down into the hold of the Red Gull" found no
    place and was answered with a Perception check."""
    scene, engine, pc, ship = held_at_quay
    hold = next(p for p in ships.places_of(ship) if p.name == "the hold")
    for _ in range(2):
        known = engine.places()
        assert places.find(known, f"the hold of {ship.name}").id == hold.id
        assert places.find(known, f"the deck of {ship.name}").id == ships.deck_of(ship)
        _travel(engine, _docks(engine).id)


def test_a_walk_to_her_room_by_her_name_is_never_a_move_inside_the_deck(held_at_quay):
    """Live 2026-11-16: "climb down into the hold of the Red Gull" was read `within_place`
    with fixture `floor`, and the plan's travel was dropped as a walk inside the deck."""
    from gm import interpret

    scene, engine, pc, ship = held_at_quay
    a = {"act": "go", "place": f"the hold of {ship.name}", "within_place": True,
         "fixture": "floor"}
    assert not interpret.within_place(a, engine.places(), scene.at)


def test_a_ship_nobody_holds_is_still_boarded_by_booking(held_at_quay):
    """Only her holder or a passenger walks aboard: another ship at the quay is a berth."""
    scene, engine, pc, ship = held_at_quay
    ship.held_by, ship.passengers = "", []
    engine._keep_vessel(ship)
    _travel(engine, _docks(engine).id)
    assert places.find(engine.places(), ship.name) is None


def test_the_exits_offer_her_from_the_docks_and_her_waters_from_her_deck(held_at_quay):
    """#20: at the docks the row offered only paid passage, and nothing offered to sail
    her. Aboard her at the quay, every port her waters reach is a row."""
    scene, engine, pc, ship = held_at_quay
    rows = exits.ways_from(engine, PANGRELLA, [scene.at])[scene.at]
    assert [r for r in rows if r["journey"]], rows
    _travel(engine, _docks(engine).id)
    rows = exits.ways_from(engine, PANGRELLA, [scene.at])[scene.at]
    assert any(r["name"] == ship.name and not r["journey"] for r in rows), rows


def test_a_journey_from_her_deck_sails_her_and_buys_no_berth(held_at_quay):
    """Aboard her at the quay, a journey bought a berth on the port's passenger ship."""
    scene, engine, pc, ship = held_at_quay
    purse = dict(pc.purse)
    out = _journey(engine, to="Mirabalos")
    assert out.status == "resolved", out.tell
    assert pc.purse == purse and engine.aboard().id == ship.id, out.tell
    assert engine.vessel(ship.id).at == "7ef5e373c993"


def test_her_yielded_master_left_unheld_goes_to_the_watch(held_at_quay):
    """#12/#13: ashore with the captain she was taken from aboard, and nothing happened.
    The book: a threat holds only while made good, and the one it held "may report you to
    local authorities" (CRB p.99). Her master goes; her hands stay and work her."""
    scene, engine, pc, ship = held_at_quay
    master = ships.master_of(engine.crew_of(ship))
    outs = _travel(engine, _docks(engine).id)
    left = next(o for o in outs if o.op == "ship_left")
    assert master.ref not in scene.people
    assert pc.has_state(states.wanted_tag(scene.location_id))
    assert "to the watch" in left.tell and "stays aboard" in left.tell, left.tell
    # Once: nobody is left to go.
    assert not [o for o in _travel(engine, ship.name) + _travel(engine, _docks(engine).id)
                if o.op == "ship_left"]


def test_somebody_of_hers_left_aboard_holds_her_people(held_at_quay):
    """#12/#13 the other way: one of the party left on her deck holds her people."""
    scene, engine, pc, ship = held_at_quay
    mate = scene.add(instantiate("thug", scene=scene, name="Bren"))
    scene.move(mate.ref, ships.deck_of(ship))
    engine._travels_with_you(mate)
    master = ships.master_of(engine.crew_of(ship))
    engine.place_party(_docks(engine).id)
    scene.move(mate.ref, ships.deck_of(ship))
    assert engine._ships_left_settle() == []
    assert master.ref in scene.people
    mate.remove_effects(match=lambda e: states.TRAVELS_WITH_YOU in (e.tags or ()))
    assert [o.op for o in engine._ships_left_settle()] == ["ship_left"]


def test_a_cruise_meets_a_merchant_she_can_close_with_board_and_take(held_at_quay,
                                                                       monkeypatch):
    """#8: piracy had no path. A cruise checks the sea each watch (four a day, the land's
    Ultimate Wilderness rate); a merchant a held ship meets is a real vessel at `distant`,
    and boarded, her people at the rail yield to a threat and she is a prize."""
    scene, engine, pc, ship = held_at_quay
    met = iter([None, ontheway.Meeting(kind="merchant", roll=1, count=0)])
    monkeypatch.setattr(ontheway, "sea", lambda *a, **k: next(met, None))
    start = scene.clock_minutes
    res = engine.run(engine.validate(
        [{"op": "sea", "actor": "pc", "because": "hunt", "params": {"do": "cruise"}}],
        origin="author:test"))
    out = res.outcomes[0]
    assert out.status == "resolved", out.tell
    assert scene.clock_minutes - start == 2 * ships.WATCH_MINUTES
    assert scene.sea and not scene.sea["hostile"] and scene.sea["range"] == "distant"
    assert "merchantman" in out.tell
    for do in ("close", "close", "board"):
        res = engine.run(engine.validate(
            [{"op": "sea", "actor": "pc", "because": "hunt", "params": {"do": do}}],
            origin="author:test"))
    board = res.outcomes[0]
    assert not scene.initiative, board.tell
    prize = engine.aboard()
    assert prize.id == scene.sea["theirs"]
    for a in engine.crew_of(prize):
        res = engine.run(engine.validate(
            [{"op": "check", "actor": "pc", "target": a.ref, "because": "a threat",
              "params": {"skill": "intimidate", "demand": "yield"}}], origin="author:test"))
        if res.awaiting:
            res = engine.resume(20)
    assert engine.vessel(prize.id).held_by == pc.ref
    assert not scene.sea
    # Sailed in, the ship she came in keeps company.
    engine._journeyed = ""
    out = _journey(engine, to="Mirabalos")
    assert out.status == "resolved", out.tell
    assert engine.vessel(ship.id).at == engine.vessel(prize.id).at == "7ef5e373c993"


def test_from_a_cruise_she_sails_back_into_her_port(held_at_quay):
    """Live 2026-11-16: after a day's cruise off Mirabalos, "bring her back into
    Mirabalos" had no leg: the legs from a port never lead to itself."""
    scene, engine, pc, ship = held_at_quay
    home = ship.at
    res = engine.run(engine.validate(
        [{"op": "sea", "actor": "pc", "because": "hunt", "params": {"do": "cruise"}}],
        origin="author:test"))
    assert res.outcomes[0].status == "resolved", res.outcomes[0].tell
    assert any(leg.to_id == home for leg in ships.her_waters(PANGRELLA, engine.aboard()))
    out = _journey(engine, to=engine._settlement_name(home))
    assert out.status == "resolved", out.tell
    assert engine.vessel(ship.id).at == home


def test_a_cruise_is_only_for_a_ship_the_player_holds(held_at_quay):
    scene, engine, pc, ship = held_at_quay
    ship.held_by = ""
    engine._keep_vessel(ship)
    res = engine.run(engine.validate(
        [{"op": "sea", "actor": "pc", "because": "hunt", "params": {"do": "cruise"}}],
        origin="author:test"))
    assert res.outcomes[0].status == "refused"


def test_a_journey_to_her_name_is_read_as_the_walk_aboard(held_at_quay):
    """#19 live: "board my ship, the Red Gull" read `journey`, and the plan wrote the
    journey and a placeless travel beside it. A journey to a ship lying at this quay owes
    the walk."""
    from gm import interpret

    scene, engine, pc, ship = held_at_quay
    _travel(engine, _docks(engine).id)
    frame = {"actions": [{"act": "journey", "place": ship.name, "commit": "done",
                          "span": "board my ship"}]}
    assert interpret.ops_for(frame, scene, engine.places()) == ["travel"]
    frame["actions"][0]["place"] = "Mirabalos"
    assert interpret.ops_for(frame, scene, engine.places()) == ["journey"]


def test_a_placeless_walk_is_given_her_deck_from_the_words(held_at_quay):
    """#14 replayed live: "I go back aboard the Red Gull" read `go: the Red Gull`; the plan
    wrote a `travel` whose only aim was a placeholder, taken out, and the engine refused
    "Nobody moves: where to?"."""
    scene, engine, pc, ship = held_at_quay
    _travel(engine, _docks(engine).id)
    frame = {"actions": [{"act": "go", "place": ship.name, "commit": "done",
                          "span": "go back aboard the Red Gull"}]}
    out = acts_to_ops.travel_named([{"op": "travel", "actor": "pc", "params": {}}], frame,
                                   engine.places())
    assert out[0]["params"]["place"] == ships.deck_of(ship)
    # A walk the plan aimed is left alone.
    aimed = [{"op": "travel", "params": {"place": "the market"}}]
    assert acts_to_ops.travel_named(aimed, frame, engine.places()) == aimed


def test_hunting_words_aboard_her_become_the_cruise(held_at_quay):
    """#8/#9: the reading was `journey: the trade route` and `seek: a merchant ship`; the
    plan's journey was refused (no such port) and the seek printed "The merchant, is not
    here". One closed question per act (stubbed here) turns them into her cruise."""
    scene, engine, pc, ship = held_at_quay
    frame = {"actions": [
        {"act": "journey", "place": "the trade route", "span": "take her out along the "
         "trade route", "commit": "done"},
        {"act": "seek", "target": "a merchant ship", "span": "hunting for a merchant ship",
         "commit": "done"}]}
    raw = [{"op": "journey", "params": {"to": "the trade route"}},
           {"op": "found", "params": {"name": "the trade route", "kind": "road"}},
           {"op": "travel", "params": {"place": "the trade route"}},
           {"op": "narrate_only", "params": {"not_here": "The merchant, is not here."}}]
    out = acts_to_ops.cruise_spoken(raw, frame, scene, ask=lambda span: "cruise")
    assert out == [{"op": "sea", "actor": pc.ref, "because": "the player puts her out to "
                    "cruise", "params": {"do": "cruise"}}]
    # A port named stays a voyage; and ashore nothing is asked.
    assert acts_to_ops.cruise_spoken(raw, frame, scene, ask=lambda span: "") == raw
    _travel(engine, _docks(engine).id)
    assert acts_to_ops.cruise_spoken(raw, frame, scene,
                                     ask=lambda span: pytest.fail("asked ashore")) == raw
