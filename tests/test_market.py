"""A shop has a shelf, not a catalogue.

Before this, "Buy from the market" drew from every priced material in the game — 339 of
them at the alchemist's stall in Zhilvarnia, including every legendary catalyst — and the
only thing between the player and any of it was a d20. Measured in play: one market run
came back with eight items nobody had chosen, four of which the alchemy bench could not
use.

The shelf is drawn rather than stored, seeded on the place, the stall and the day, so the
same shop on the same day is the same shelf and tomorrow is a fresh roll. Only the sales
are written to the save.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules import benches, market
from rules.sheet import load_pc
from tests._places import stand_on


@pytest.fixture
def priced():
    return [m for m in benches.obtainable("alchemist", "bought", biome="urban")
            if getattr(m, "price_gp", None)]


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_shelf_thins_as_the_rarity_climbs(priced):
    """The asked-for shape: thirty common things, twenty uncommon, fifteen rare, ten
    exotic and exactly one legendary. The engine's ladder has five rungs and no "epic"
    or "mythic", so the six bands requested are mapped onto the five that exist."""
    shelf = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=0)
    assert market.summary(shelf) == {"common": 30, "uncommon": 20, "rare": 15,
                                     "exotic": 10, "legendary": 1}
    assert len(shelf) == 76
    assert len(shelf) < len(priced), "the stall still carries everything"


def test_one_shop_on_one_day_is_one_shelf(priced):
    """Walk out and back in and the amethyst is still there. Drawing fresh on every
    look would make the stock meaningless and the prose a liar."""
    a = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=3)
    b = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=3)
    assert [m.id for m in a] == [m.id for m in b]


def test_the_shelf_is_rerolled_every_day_and_differs_by_shop(priced):
    """"can be rerolled every in game day" — and two stalls in one town are two
    shelves, so the ironmonger and the apothecary are not selling from one crate."""
    here = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=0)
    tomorrow = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=1)
    elsewhere = market.stock(priced, place="mirabalos", stall="alchemist:market-run", day=0)
    other_stall = market.stock(priced, place="zhilvarnia", stall="blacksmith:buy", day=0)
    assert [m.id for m in here] != [m.id for m in tomorrow]
    assert [m.id for m in here] != [m.id for m in elsewhere]
    assert [m.id for m in here] != [m.id for m in other_stall]


def test_the_day_turns_over_on_the_clock(priced):
    assert market.day_of(0) == 0
    assert market.day_of(23 * 60 + 59) == 0
    assert market.day_of(24 * 60) == 1
    assert market.day_of(49 * 60) == 2


def test_what_has_been_bought_is_off_the_shelf(priced):
    """One legendary on the shelf is one legendary, not one per market run."""
    shelf = market.stock(priced, place="zhilvarnia", stall="alchemist:market-run", day=0)
    legendary = [m for m in shelf if market.tier_of(m) == "legendary"]
    assert len(legendary) == 1
    taken: dict[str, int] = {}
    market.mark_sold(taken, legendary[0].id, "zhilvarnia", "alchemist:market-run", 0)
    left = market.remaining(shelf, taken, "zhilvarnia", "alchemist:market-run", 0)
    assert legendary[0].id not in {m.id for m in left}
    assert len(left) == len(shelf) - 1
    # And yesterday's sales do not follow the shop into tomorrow.
    tomorrow = market.stock(priced, place="zhilvarnia",
                            stall="alchemist:market-run", day=1)
    assert len(market.remaining(tomorrow, taken,
                                "zhilvarnia", "alchemist:market-run", 1)) == len(tomorrow)


def test_a_material_with_no_rarity_is_shelved_as_common(priced):
    """The only safe direction: something the bench never tiered belongs on the cheap
    end of the shelf, not sold as the day's one legendary."""
    class Untiered:
        id, name, tier, price_gp = "mystery", "Mystery", "", 1

    assert market.tier_of(Untiered()) == "common"


def test_a_stall_that_sold_out_says_so_rather_than_offering_nothing(client):
    """The refusal has to name the reason. An empty `within` used to come back as
    "There is nothing of that kind to be had here", which is what an empty *field*
    says and reads as a bug in a market."""
    c = cm.current()
    pc = c.scene.pc()
    pc.purse = {"gp": 5000}
    day = market.day_of(c.scene.clock_minutes)
    place = str(c.scene.location_id or c.biome or "nowhere")
    priced_here = [m for m in benches.obtainable("blacksmith", "bought",
                                                 biome=c.biome or None)
                   if getattr(m, "price_gp", None)]
    shelf = market.stock(priced_here, place=place, stall="blacksmith:buy", day=day)
    for m in shelf:
        market.mark_sold(c.scene.market_taken, m.id, place, "blacksmith:buy", day)
    c.save()

    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "blacksmith:buy"}),
                    content_type="application/json")
    assert r.status_code == 409
    assert "bare" in r.json()["error"] or "tomorrow" in r.json()["error"]


def test_buying_takes_it_off_the_shelf_for_the_rest_of_the_day(client):
    """The whole point of a shelf. Without this the stall restocked itself between one
    market run and the next, and "1 legendary item for sale" meant one per visit."""
    c = cm.current()
    c.scene.pc().purse = {"gp": 5000}
    c.scene.clock_minutes = 0
    c.save()
    bought: set[str] = set()
    # One hour a run, so the twelve runs stay inside one day. Written with 12-hour runs
    # first, this failed on "Bismuth was sold twice" — two of those is twenty-four hours,
    # the day turns over and the shelf is *supposed* to reroll. The bug was in the test.
    for _ in range(12):
        r = client.post("/api/craft/excursion",
                        data=json.dumps({"action": "blacksmith:buy", "hours": 1}),
                        content_type="application/json")
        if r.status_code != 200:
            break
        for h in r.json()["found"]:
            assert h["id"] not in bought, f"{h['name']} was sold twice in one day"
            bought.add(h["id"])
    assert market.day_of(cm.current().scene.clock_minutes) == 0, "the day turned over"
    assert bought, "nothing was ever bought"


def test_a_new_day_restocks_the_stall(client):
    """The other half of the same rule: sold out today, open again tomorrow."""
    c = cm.current()
    c.scene.pc().purse = {"gp": 5000}
    c.scene.clock_minutes = 0
    day = market.day_of(c.scene.clock_minutes)
    place = str(c.scene.location_id or c.biome or "nowhere")
    priced_here = [m for m in benches.obtainable("blacksmith", "bought",
                                                 biome=c.biome or None)
                   if getattr(m, "price_gp", None)]
    for m in market.stock(priced_here, place=place, stall="blacksmith:buy", day=day):
        market.mark_sold(c.scene.market_taken, m.id, place, "blacksmith:buy", day)
    c.save()
    assert client.post("/api/craft/excursion",
                       data=json.dumps({"action": "blacksmith:buy"}),
                       content_type="application/json").status_code == 409

    c = cm.current()
    c.scene.clock_minutes = 24 * 60          # sleep on it
    c.save()
    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "blacksmith:buy"}),
                    content_type="application/json")
    assert r.status_code == 200, r.content[:200]


def test_there_is_no_stall_in_an_empty_field(client):
    """Measured in play. Grist walked out of Zhilvarnia into open grassland — `travel`
    moved the biome and shed the bystander correctly — and all five "buy" cards were
    still offered, because `_at_market` read only the location's *kind* and `travel`
    never touches `location_id`. The scene still pointed at a CITY, so an ironmonger
    sold Iron to a character with nothing around them but grass."""
    c = cm.current()
    c.scene.pc().purse = {"gp": 500}
    stand_on(c.scene, "urban")
    c.save()
    d = client.get("/api/craft/actions").json()
    markets = [a for a in d["actions"] if a["requires"] == "market"]
    assert markets, "no market excursions at all"
    assert all(a["available"] for a in markets), "cannot buy in town"

    c = cm.current()
    stand_on(c.scene, "grassland")                 # walked out past the walls
    c.save()
    d = client.get("/api/craft/actions").json()
    markets = [a for a in d["actions"] if a["requires"] == "market"]
    assert all(not a["available"] for a in markets), "a stall in an empty field"
    assert all("nobody here selling" in a["why"] for a in markets)

    # And the endpoint refuses it, not just the button.
    r = client.post("/api/craft/excursion",
                    data=json.dumps({"action": "blacksmith:buy"}),
                    content_type="application/json")
    assert r.status_code == 409
    assert "nobody here selling" in r.json()["error"]



# --- what the stall can pay ---------------------------------------------------------

def test_a_market_stall_cannot_hand_over_a_thousand_gold():
    """The shop's side of a trade was as unmodelled as the trade itself. Measured on the
    real satchel: one Blackthorn purified draught is worth 1,325 gp, and an ordinary town
    stall was under no constraint at all about being able to buy it."""
    from rules import market

    till = market.purse("Pangrella", "apothecary", 2)
    assert 150 <= till <= 400, f"an uncommon stall had {till} gp on hand"
    assert till < 1325


def test_the_till_is_the_same_till_when_you_walk_back_in():
    """Drawn, not stored — seeded on (place, stall, day) exactly as the shelf is. Walk out
    and back and the money has not changed; tomorrow is a fresh day's takings."""
    from rules import market

    assert (market.purse("Pangrella", "apothecary", 2)
            == market.purse("Pangrella", "apothecary", 2))
    assert (market.purse("Pangrella", "apothecary", 2)
            != market.purse("Pangrella", "apothecary", 3))


def test_the_purse_and_the_shelf_are_drawn_from_different_streams():
    """`stock` seeds a Random on `key(place, stall, day)`. Drawing the purse from the same
    string would make the shelf change every time the purse formula was retuned, which is
    a shop's entire inventory moving because somebody adjusted how much money it had."""
    from rules import market

    before = [getattr(m, "id", "") for m in market.stock(
        [], place="Pangrella", stall="apothecary", day=2)]
    market.purse("Pangrella", "apothecary", 2)
    after = [getattr(m, "id", "") for m in market.stock(
        [], place="Pangrella", stall="apothecary", day=2)]
    assert before == after


def test_a_short_stall_makes_a_smaller_offer_rather_than_refusing():
    """"i can still sell to them if i am willing to any get what they can give" — so the
    cap is an offer, not a refusal, and whether it is worth taking is the player's call."""
    from rules import market

    taken = {}
    offered = market.can_pay(taken, 1325.6, "Pangrella", "apothecary", 2)
    assert 0 < offered < 1325.6
    assert offered == market.purse("Pangrella", "apothecary", 2)


def test_coin_that_has_left_the_till_is_gone_until_tomorrow():
    """Otherwise a stall with 247 gp buys the whole satchel one bottle at a time."""
    from rules import market

    taken = {}
    first = market.can_pay(taken, 1000, "Pangrella", "apothecary", 2)
    market.mark_spent(taken, first, "Pangrella", "apothecary", 2)
    assert market.can_pay(taken, 200, "Pangrella", "apothecary", 2) == 0
    # A new day is a new float.
    assert market.can_pay(taken, 200, "Pangrella", "apothecary", 3) > 0


def test_a_richer_house_can_buy_what_a_stall_cannot():
    """The reason the cap is worth having: selling a masterwork draught becomes a matter
    of finding somebody who can pay for it, and the refusal is mechanical rather than
    narrated."""
    from rules import market

    assert market.purse("Pangrella", "the guild vault", 2, "legendary") > 1325
