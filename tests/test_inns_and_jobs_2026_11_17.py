"""Inns, taverns, lodging and the guild's openings: playtest 2026-11-17b items 4-13.

Played overnight on 0.4.1 (master cf3d37f3) in Mirabalos, a city of the shipped Pangrella
export. The city's 23 authored places held no inn and no tavern, so "head to an inn in the
city, take a room for the night" walked the player aboard her own ship (#4, twice), the
harbourmaster named the gardens as a place to rest (#7), and a tavern founded on demand had
a keeper who sold nothing: "I buy a meal and a drink from the barkeep" built nothing and
the trade panel answered 409 (#10). In the guildhall, a question asked aloud with the clerk
the one person there went to nobody (#11), and the clerk, holding no job, claimed "several
openings ... posted on the notice board" (#12) that the next turn could not find (#13).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops
from rules import goods, jobs, keepers, lodging, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict
from world import loader

from test_a_take_is_not_a_boast import SAM

MIRABALOS = "7ef5e373c993"


@pytest.fixture(autouse=True)
def _book_terms(monkeypatch):
    """The book's prices, unmoved by a seller's own terms (pinned elsewhere)."""
    from rules import pricing

    monkeypatch.setattr(pricing, "seller_terms", lambda scene, seller: (0, []))


@pytest.fixture(scope="module")
def pangrella():
    return loader.load("fixtures/pangrella-campaign.json")


# --- #4, #7, #8: a bed in every settlement ----------------------------------------------------

def test_every_shipped_settlement_has_an_inn_and_every_city_a_tavern(pangrella):
    """#8: measured 2026-11-17, none of Pangrella's 12 authored settlements listed an inn
    and 2 of its 6 cities (Mirabalos, Khalmorin) no tavern either. Every one now has an
    inn, and every city a tavern."""
    for e in pangrella.entities.values():
        if e.kind not in ("CITY", "TOWN", "VILLAGE"):
            continue
        names = {p.name for p in places.home_set(e)}
        assert "the inn" in names, (e.name, sorted(names))
        if places.scale_of(e) == "city":
            assert "the tavern" in names, (e.name, sorted(names))


def test_a_generated_settlement_of_every_scale_has_its_inn():
    """A generated village whose words earned four places used to spend its whole budget
    of six before "somewhere to sleep" was reached; the inn is now guaranteed by scale."""
    for scale in places.SCALES:
        class Loc:
            id = f"ffff{scale[:4]:4}".replace(" ", "0")
            name = "Testville"
            kind = "CITY"
            facts = {"Trade": "fountain, guild, temple, tannery, smithy, docks"}
            prose = ""
            places = []
        Loc.scale = scale
        names = [p.name for p in places.home_set(Loc())]
        assert "the inn" in names, (scale, names)


def test_an_inn_named_with_an_article_and_a_place_is_the_inn(pangrella):
    """#4: "head to an inn in the city" was found nowhere, and the plan's own walk took
    her aboard the Red Gull. "the nearest tavern or inn" ends in the inn's own word."""
    home = places.home_set(pangrella.get(MIRABALOS))
    assert places.find(home, "an inn in the city").name == "the inn"
    assert places.find(home, "an inn").name == "the inn"
    assert places.find(home, "a tavern").name == "the tavern"
    assert places.find(home, "the nearest tavern or inn").name == "the inn"


# --- #5, #9, #10: the house's counter ------------------------------------------------------------

def _tavern(purse=None):
    at = f"{MIRABALOS}~urban:the-docks/the-tavern"
    s = Scene(location_id=MIRABALOS)
    s.at = at
    s.founded.append({"id": at, "name": "the tavern", "kind": "tavern",
                      "parent": f"{MIRABALOS}~urban:the-docks"})
    pc = from_dict(dict(SAM, purse=dict(purse if purse is not None else {"gp": 5})),
                   ref="pc")
    s.add(pc)
    keeper = instantiate("thug", scene=s, name="the one behind the bar")
    keeper.world_entity_id = keepers.entity_id(at)
    s.add(keeper)
    return s, pc, keeper, Engine(s, Dice(seed=3))


def test_the_one_behind_the_bar_keeps_a_counter():
    """#10: the founded tavern's keeper sold nothing, so the panel answered 409."""
    _s, _pc, keeper, _e = _tavern()
    assert keepers.keeps_a_counter(keeper)
    shelf = {g.name for g in goods.goods_at("tavern")}
    assert {"mug of ale", "common meal", "pitcher of common wine"} <= shelf


def test_a_meal_and_a_drink_are_picked_on_the_counter():
    """#10's words, "a meal and a drink": no shelf name stands whole in them, so each
    part is matched on its own; "a meal" is the book's common meal, "a drink" a mug of ale
    (CRB Food, Drink, and Lodging: common meal 3 sp, ale 4 cp)."""
    shelf = goods.goods_at("tavern")
    got = [g.name for g in goods.wants_among("a meal and a drink", shelf)]
    assert got == ["common meal", "mug of ale"]
    # A whole list still reads as before (playtest 2026-11-17 #11).
    assert [g.name for g in goods.wants_among("some bread and cheese", shelf)] == [
        "loaf of bread", "hunk of cheese"]


def test_the_stays_are_the_books_three():
    """CRB Goods and Services: inn stay poor 2 sp, common 5 sp, good 2 gp. A room asked
    for with no quality named is the common stay, the rest door's."""
    assert [(r["quality"], r["cp"]) for r in lodging.menu()] == [
        ("poor", 20), ("common", 50), ("good", 200)]
    assert lodging.find("a room for the night")["quality"] == "common"
    assert lodging.find("a good room")["quality"] == "good"
    assert lodging.find("a mug of ale") is None


def test_a_good_room_bought_at_the_counter_holds_the_night():
    """#5: "take a room for the night" paid nothing and held nothing. Bought at the
    counter, the good stay costs 2 gp, holds the room through the applicator, and the
    night slept there after it costs nothing more."""
    s, pc, keeper, engine = _tavern(purse={"gp": 5})
    out = engine.run(engine.validate([{"op": "buy", "actor": "pc", "because": "t",
                                       "params": {"item": lodging.PREFIX + "good"}}]))
    o = out.outcomes[-1]
    assert o.status == "resolved", o.tell
    assert goods.in_copper(pc.purse) == 500 - 200
    assert lodging.held(pc, s.at)
    assert "good room" in o.tell and keeper.name in o.tell
    again = engine.run(engine.validate([{"op": "buy", "actor": "pc", "because": "t",
                                         "params": {"item": "a room"}}])).outcomes[-1]
    assert again.status == "refused" and "already paid" in again.tell
    night = engine.run(engine.validate([{"op": "rest", "actor": "pc", "because": "t",
                                         "params": {"kind": "night"}}])).outcomes[-1]
    assert night.status != "refused", night.tell
    assert goods.in_copper(pc.purse) == 300, "the night was charged again"


def test_a_meal_bought_from_the_barkeep_is_paid_for():
    """#10: the barkeep's "you can pay for them now" had no way to be paid. The common
    meal is 3 sp at the book's price."""
    _s, pc, _keeper, engine = _tavern(purse={"sp": 10})
    o = engine.run(engine.validate([{"op": "buy", "actor": "pc", "because": "t",
                                     "params": {"item": "a common meal"}}])).outcomes[-1]
    assert o.status == "resolved", o.tell
    assert goods.in_copper(pc.purse) == 100 - 30


# --- #11: asked aloud in a room of one ---------------------------------------------------------

def test_a_question_after_a_walk_goes_to_the_one_person_where_it_ends():
    """#11: "I walk to the guildhall and ask if anyone's hiring a blade" — the plan wrote
    the say to the barkeep left in the tavern, and the clerk, the one person in the
    guildhall, was told "ignoring the inquiry"."""
    tavern = f"{MIRABALOS}~urban:the-tavern"
    hall = f"{MIRABALOS}~urban:the-guildhall"
    s = Scene(location_id=MIRABALOS)
    s.at = tavern
    pc = from_dict(dict(SAM), ref="pc")
    s.add(pc)
    barkeep = instantiate("thug", scene=s, name="the one behind the bar")
    s.add(barkeep)
    clerk = instantiate("thug", scene=s, name="the clerk of the guild")
    s.add(clerk)
    clerk.at = hall
    known = (places.Place(id=tavern, name="the tavern", about="", terrain="urban",
                          exits=(hall,)),
             places.Place(id=hall, name="the guildhall", about="", terrain="urban",
                          exits=(tavern,)))
    frame = {"actions": [
        {"act": "go", "place": "the guildhall", "span": "walk to the guildhall"},
        {"act": "talk", "says": "is anyone hiring a blade",
         "span": "ask if anyone's hiring a blade"}]}
    raw = [{"op": "travel", "params": {"place": "the guildhall"}},
           {"op": "say", "params": {"words": "Is anyone hiring a blade?",
                                    "to": barkeep.ref}}]
    got = acts_to_ops.address_the_named(raw, frame, s, places=known)
    assert got[-1]["params"].get("to") == clerk.ref, got


# --- #12, #13: the guild's openings are the engine's -------------------------------------------

def test_the_guild_clerk_hires_a_blade_by_the_week():
    """#12: the clerk held no job and claimed "several openings". Asked for work, the
    guild's clerk now opens a real week of guard work, priced by the engine (the owner's
    answer 1 of 2026-10-27: a real escort when one goes out, else a week's guard work)."""
    hall = f"{MIRABALOS}~urban:the-guildhall"
    s = Scene(location_id=MIRABALOS)
    s.at = hall
    pc = from_dict(dict(SAM), ref="pc")
    s.add(pc)
    clerk = instantiate("thug", scene=s, name="the clerk of the guild")
    clerk.world_entity_id = keepers.entity_id(hall)
    s.add(clerk)
    engine = Engine(s, Dice(seed=3))
    assert jobs.hires_hands(clerk)[0] == "guard"
    o = engine.run(engine.validate([{"op": "job", "actor": "pc", "target": clerk.ref,
                                     "because": "t", "params": {"do": "offer"}}])).outcomes[-1]
    assert o.status == "resolved", o.tell
    assert "guard work" in o.tell and "a day" in o.tell, o.tell


def test_a_clerk_who_names_a_board_of_postings_is_read_as_naming_work():
    """#12/#13: "the contracts posted on the notice board" was read as only "work is
    wanted"; the read-back is shown that naming postings to go and read IS particular."""
    from gm import beat_verify

    assert "board" in beat_verify._JOB_SYSTEM
    assert beat_verify._JOB_DEMO_ANSWER_3 == {"sentence": "2"}
    assert "board" in beat_verify._JOB_DEMO_USER_3


def test_asking_for_paid_work_is_the_job_not_a_favour_roll():
    """Live 2026-11-17 on this lane's save: "I ask the clerk of the guild if there is any
    paid work for a blade" was read a `request` for payment, and a Diplomacy roll (8 vs
    DC 14, "offers no payment or acknowledgement of a fee") stood beside the week of guard
    work the clerk put. The job op is the answer, and the favour roll goes."""
    hall = f"{MIRABALOS}~urban:the-guildhall"
    s = Scene(location_id=MIRABALOS)
    s.at = hall
    s.add(from_dict(dict(SAM), ref="pc"))
    clerk = instantiate("thug", scene=s, name="the clerk of the guild")
    clerk.world_entity_id = keepers.entity_id(hall)
    s.add(clerk)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "request", "target": "the clerk of the guild",
         "object": "any paid work for a blade", "asks_for": "payment",
         "span": "ask the clerk of the guild if there is any paid work for a blade"}]}
    rows = acts_to_ops.table(frame, s)
    assert any(i["op"] == "check" for r in rows for i in r.intents), "the roll was built"
    acts_to_ops.jobs_spoken(rows, frame, s, ask=lambda *a: {
        "answer": "asks about the work", "work": "not said", "job": "not said"})
    ops = [i["op"] for r in rows for i in r.intents]
    assert ops == ["job"], ops
