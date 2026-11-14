"""A berth's fare moves with the one selling it, a talk with the harbourmaster offers the
berths, and a crew name keeps its own words (owner rulings 2026-11-13).

1. "keep the rulebook's base price augmented by the relationship and the personality of
   the seller": the book's 1 sp a mile a head (CRB Table 6-9) stays the base; the
   harbourmaster's attitude to the player, their thrift and a haggle won with them move
   it, through the shop's own machinery (`pricing.markup_for`, `tradecraft.buy_price`,
   the day's haggle at their stall). The exits row's quote and the coin taken are one
   number (`Engine.passage_quote`).
2. Measured live: "I ask the master for passage to Mirabalos, pay the fare and go aboard"
   was read as talk and booked nothing. Talking with the harbourmaster now offers the
   berths (`views._passage_offer`), and "the master" finds the harbourmaster.
3. Measured live: "the ship's master" printed "The ship's the master and a deckhand are
   on deck." The tells' article pass took "master" (somebody else in the scene) inside it.
"""
from __future__ import annotations

import json
import shutil
from types import SimpleNamespace

import pytest

import _exits_dom as exits_dom
from rules import attitude, goods, journey, lives, names, pricing, scope, ships, tradecraft
from rules import market
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
MIRABALOS, ZHILVARNIA = "7ef5e373c993", "6953424c8a82"
BOOK_CP = 2880   # 288 miles at 1 sp: the fare test_ships_at_sea.py measures for one head


def _at_port(gp: int = 500):
    scene = Scene(location_id=MIRABALOS)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=4), world=PANGRELLA)
    engine.place_party(f"{MIRABALOS}~urban:the-docks")
    pc.purse = {"gp": gp}
    return scene, engine, pc


def _leg():
    return {l.to_id: l for l in journey.legs_from(PANGRELLA, MIRABALOS)}[ZHILVARNIA]


def _book(engine):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "journey", "actor": "pc", "because": "passage",
          "params": {"to": "Zhilvarnia"}}], origin="author:test"))
    return res.outcomes[-1]


def test_the_harbourmaster_is_the_seller_and_a_stranger_pays_the_book():
    """The fare is quoted on the docks before anybody has met the crew, so the seller is
    the harbourmaster stood up there; this one is indifferent and of middling thrift, so
    the book's fare stands and no reason is given."""
    scene, engine, pc = _at_port()
    seller = engine.passage_seller()
    assert seller is not None and seller.name == "the harbourmaster"
    assert engine.passage_quote(_leg())[2] == BOOK_CP
    assert engine._fare_moved() == ""


@pytest.mark.parametrize("regard,cp,said", [
    (60, 2736, "likes you: 5% off"),
    (80, 2592, "would do you a good turn: 10% off"),
    (95, 2448, "would do anything for you: 15% off"),
    (20, 3168, "does not like you: 10% over"),
    (5, 3600, "cannot stand you: 25% over"),
])
def test_the_fare_moves_with_regard_and_the_quote_is_what_is_charged(regard, cp, said):
    """A friend's price and a dearer one for somebody disliked (`pricing.REGARD_PERCENT`).
    The exits row's words, the quote and the coin out of the purse are one number."""
    from play import exits

    scene, engine, pc = _at_port()
    attitude.set_regard(engine.passage_seller(), regard, "test")
    assert engine.passage_quote(_leg())[2] == cp
    row = next(r for r in exits.exits(engine, PANGRELLA) if r["id"] == ZHILVARNIA)
    assert goods.purse_line(goods.coins_for(cp), engine._coins_here()) in row["time_words"]
    had = goods.in_copper(pc.purse)
    out = _book(engine)
    assert had - goods.in_copper(pc.purse) == cp, out.tell
    assert f"The harbourmaster {said} the book's fare." in out.tell


def test_a_tight_fisted_seller_charges_more_and_says_why():
    """Thrift is the personality term: a recorded life's score when there is one, a
    seeded one off the keeper's world id when not (a keeper has no life recorded)."""
    scene, engine, pc = _at_port()
    seller = engine.passage_seller()
    scene.population = {"p1": {"id": "p1", "ref": seller.ref,
                               "life": {"axes": {"thrift": 90}}}}
    assert pricing.seller_terms(scene, seller) == (-8, ["is tight-fisted"])
    assert engine.passage_quote(_leg())[2] == int(round(BOOK_CP * 1.08))
    assert "is tight-fisted: 8% over" in _book(engine).tell
    # No record: the same keeper, the same score, every time it is asked.
    scene.population = {}
    seed = lives.axis_score("thrift", seller.world_entity_id)
    assert seed == lives.axis_score("thrift", seller.world_entity_id)


def test_a_haggle_won_with_the_harbourmaster_comes_off_the_fare_up_to_the_floor():
    """The counter's haggle (`_op_haggle`), kept under the harbourmaster's stall key like
    every counter's, comes off the fare; with a devoted seller it stops at Ultimate
    Campaign's 25%."""
    scene, engine, pc = _at_port()
    seller = engine.passage_seller()
    key = tradecraft.dealing_key("haggle", pc.ref, MIRABALOS, market.stall_of(scene, seller),
                                 market.day_of(scene.clock_minutes))
    scene.dealings[key] = {"percent": 12, "keeper": seller.ref}
    assert engine.passage_quote(_leg())[2] == int(round(BOOK_CP * 0.88))
    attitude.set_regard(seller, 95, "test")
    assert engine.passage_quote(_leg())[2] == int(round(BOOK_CP * 0.75))
    assert "gave 12% to the haggle" in engine._fare_moved()


def test_the_master_finds_the_harbourmaster():
    """"I ask the master for passage" found nobody beside the harbourmaster and stood up a
    new "master" on the docks (the ships-at-sea save's c33)."""
    scene, engine, pc = _at_port()
    assert scope.in_the_room(scene, "the master") == engine.passage_seller().ref


def test_talking_with_the_harbourmaster_offers_the_berths():
    """The offer is the exits row's own passage rows, while the engine holds the player in
    conversation with the harbourmaster — nothing in the player's words is read for it."""
    from play import views

    scene, engine, pc = _at_port()
    c = SimpleNamespace(engine=lambda: engine, scene=scene, world=PANGRELLA)
    assert views._passage_offer(c) == {}
    engine.join_talk(engine.passage_seller())
    offer = views._passage_offer(c)
    assert offer["seller"] == "the harbourmaster"
    assert ZHILVARNIA in {r["id"] for r in offer["rows"]}
    assert all(r["journey"] for r in offer["rows"])
    note = views._passage_note(c)
    assert note.startswith("The harbourmaster sells berths: ")
    assert "to Zhilvarnia, 2 days at sea" in note
    _book(engine)
    assert views._passage_offer(c) == {}, "aboard, nobody sells a berth"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_a_berth_offered_attaches_the_exits_rows_journey_chip(tmp_path):
    """A click on the offer attaches the same journey chip the exits row would, so Say
    sends `journey to=<port>` (`views._take_the_exit`)."""
    row = {"id": ZHILVARNIA, "name": "Zhilvarnia", "group": "road", "blocked": "",
           "journey": True,
           "time_words": "2 days at sea, 2 platinum pieces passage"}
    state = {"awaiting": None, "ended": False, "scene": {
        "in_encounter": False, "exits": [row],
        "passage_offer": {"seller": "the harbourmaster", "rows": [row]}}}
    got = exits_dom.run(tmp_path, f"""
      ELS["passage-offer"] = el("passage-offer");
      renderAll({json.dumps(state)});
      const offered = ELS["passage-offer"].innerHTML;
      const btn = {{ dataset: {{ passage: "{ZHILVARNIA}" }}, getAttribute: () => null }};
      fire("click", {{ closest: sel => sel.includes(".passbtn") ? btn : null }});
      done(() => ({{ offered, body: sayBody() }}));
    """)
    assert "Book passage to Zhilvarnia · 2 days at sea" in got["offered"]
    assert got["body"]["attachments"][0]["id"] == ZHILVARNIA
    assert got["body"]["attachments"][0]["kind"] == "place"


def test_a_crew_name_keeps_its_own_words_beside_a_bare_descriptor():
    """"The ship's master and a deckhand are on deck." beside somebody named "master"
    printed "The ship's the master": the capitalised opening was not claimed as the
    longer name, and a possessive before "master" was not read as definite."""
    people = ["the ship's master", "master", "a deckhand"]
    said = "The ship's master and a deckhand are on deck."
    assert names.with_articles(said, people) == said
    assert names.with_articles("Kesst's master waits.", ["master"]) == "Kesst's master waits."
    # The pass still does its job on a bare descriptor.
    assert names.with_articles("Master nods. You see master.", ["master"]) \
        == "The master nods. You see the master."


def test_the_book_fare_is_still_the_ships_rule():
    assert ships.fare_cp(288) == BOOK_CP
