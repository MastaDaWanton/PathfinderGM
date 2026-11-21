"""Naming a far town is a journey, from anywhere (fix/journey-words, 2026-11-21).

Both defects were found live by the travel lane on a copy of the owner's save (Shadow, at
the ruins east of Branford on the region map's hexes):

1. "I leave the ruins and set out on the road to Brackgate" was read rightly, `leave: the
   ruins` + `journey: Brackgate`, but the leave owed a `travel` of its own. The plan wrote
   `found` "the road to Brackgate" off the ruins and a travel into it: 8 minutes, a new
   place named after a real far town, and the journey refused as the turn's second. Out
   on a hex there was no Journey chip either, so typing was the only way onto the road.
2. "book passage by ship to Balgrim" and, the turn after, "set sail for Balgrim" were each
   read `journey`; the plan put a travel ashore to the docks beside each, which walked the
   party off the ship it had just boarded. Booking took 2 turns and sailing a third.

Every engine test runs once per export (fixes are world-agnostic, 2026-09-28).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops
from rules import hexes, journey, ontheway
from rules.intents import IntentError
from tests.test_hex_travel import _move, _party


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    monkeypatch.setattr(ontheway, "road_stretches", lambda *a, **k: None)


def _on_a_hex(worlds):
    """The party one hex out of a town with a land road; the road."""
    for row in worlds.play["settlements"]:
        for leg in journey.legs_from(worlds, row["id"]):
            if not leg.by_sea and leg.by not in ("sea", "river"):
                s, e, pc = _party(worlds, row["id"])
                g = e.hex_world()
                if g is None or g.town_hex.get(row["id"]) is None:
                    continue
                land = [h for h in hexes.neighbours(*e.party_hex(g)) if g.cell(*h)["land"]]
                if not land or _move(e, land[0]).status != "resolved":
                    continue
                assert hexes.parse_place(s.at) is not None
                return s, e, leg
    pytest.skip("no land road with a hex beside its town in this export")


def test_leaving_the_ground_and_setting_out_owes_the_journey_alone(worlds, quiet):
    """#1: the leave's travel ran first, founded "the road to Brackgate" in the ruins and
    walked 8 minutes into it; the journey was then refused. The journey is the way out."""
    s, e, leg = _on_a_hex(worlds)
    head = f"the road to {leg.to_name}"
    frame = {"question": False, "claims": [], "actions": [
        {"act": "leave", "place": "the ruins", "span": "leave the ruins"},
        {"act": "journey", "place": leg.to_name, "span": f"set out on {head}"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert acts_to_ops.declared(rows) == ["journey"]
    plan = [{"op": "found", "params": {"name": head, "kind": "road"}},
            {"op": "travel", "params": {"place": head}},
            {"op": "journey", "params": {"to": leg.to_name}}]
    assert [r["op"] for r in acts_to_ops.apply(plan, rows, frame, s)] == ["journey"]


def test_a_walk_to_a_road_head_from_open_ground_is_the_journey(worlds, quiet):
    """#1, the other reading: `go: the road to Brackgate` from a hex, where the ring's road
    heads are not among the places, owes the journey — and the journey finds its road by
    that name."""
    s, e, leg = _on_a_hex(worlds)
    head = f"the road to {leg.to_name}"
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": head, "span": f"walk on down {head}"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].ops == ["journey"]
    r = e.run(e.validate([{"op": "journey", "actor": "pc", "params": {"to": head}}]))
    out = [o for o in r.outcomes if o.op == "journey"][0]
    assert out.status == "resolved", out.tell
    assert s.location_id == leg.to_id


@pytest.mark.parametrize("op", ["found", "travel"])
def test_a_real_far_town_is_never_minted_as_a_place_here(worlds, quiet, op):
    """#1: `found` "the road to Brackgate" off the ruins made a place named after a real
    far town. Refused at validation with the journey named, so the retry writes it."""
    s, e, leg = _on_a_hex(worlds)
    head = f"the road to {leg.to_name}"
    params = {"name": head, "kind": "road"} if op == "found" else {"place": head}
    with pytest.raises(IntentError) as err:
        e.validate([{"op": op, "actor": "pc", "params": params}])
    assert err.value.code == "far_town"
    assert f'"to": "{leg.to_name}"' in str(err.value)
    if op == "found":
        from rules.intents import Intent

        before = len(s.founded or ())
        out = e._op_found(Intent(op="found", actor="pc", id="i1",
                                 params={"name": leg.to_name}), {})
        assert out.status == "refused" and len(s.founded or ()) == before


def test_open_ground_offers_every_road_out_as_a_journey_chip(worlds, quiet):
    """#1: from the ruins east of Branford the exits row offered no Journey. On a hex each
    land road out is offered, its time the share of the road still ahead."""
    from play import exits

    s, e, leg = _on_a_hex(worlds)
    rows = [r for r in exits.exits(e, worlds) if r["journey"]]
    assert leg.to_id in {r["id"] for r in rows}, rows


def test_a_passage_booked_or_sailed_is_not_walked_ashore_beside(worlds):
    """#2: "book passage by ship to Balgrim" and "set sail for Balgrim" were read
    `journey`, and the plan's travel to the docks (and to "the deck") beside each walked
    the party off the ship just boarded: booking took 2 turns, sailing a third."""
    s, e, _pc = _party(worlds)
    to = worlds.play["settlements"][-1]["name"]
    for span in (f"book passage by ship to {to}", f"set sail for {to}"):
        frame = {"question": False, "claims": [], "actions": [
            {"act": "journey", "place": to, "span": span}]}
        rows = acts_to_ops.table(frame, s, places=e.places())
        plan = [{"op": "journey", "params": {"to": to}},
                {"op": "travel", "params": {"place": "the docks"}}]
        assert [r["op"] for r in acts_to_ops.apply(plan, rows, frame, s)] == ["journey"]


def test_a_journey_is_the_leaving_no_walk_is_injected_beside_it(worlds):
    """#2, live replay 2026-11-21: with the plan's walk to the docks struck beside "book
    passage by ship to Balgrim", `inject_travel` added a travel "Back within Branford" and
    the leaving-in-place check refused 7 of 7 attempts. A journey moves the ground."""
    from gm import judgement

    s, e, leg = _on_a_hex(worlds)
    town = worlds.get(s.location_id).name
    raw = [{"op": "journey", "params": {"to": leg.to_name}}]
    out = judgement.inject_travel(
        raw, f"I head back to {town}'s docks and book passage to {leg.to_name}.", s, worlds)
    assert [r["op"] for r in out] == ["journey"]
