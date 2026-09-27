"""A counter keeps hours (rules/keepers.py, docs/the-population.md "Built: shop hours
and calling on people").

Before 2026-09-27 a stallholder stood at her stall at three in the morning and sold to
anybody: nothing anywhere knew the time of day. Researched before building: Stardew
Valley opens a shop only while its owner stands in the counter's area; Skyrim's vendors
ask an hour window AND a place, and its innkeepers are always open; CircleMUD's keeper
says when to come back ("Sorry, come back tomorrow."); and Pierre's Wednesday closure,
which shut the whole building and cut players off from the people inside, is the
complaint a shut counter must not repeat — a keeper under a roof lives there and can be
talked to.
"""
from __future__ import annotations

from rules import keepers, residency
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
HOUR = 60


def _at_the_market(clock):
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    market = next(p for p in e.places() if p.name == "the market")
    e.run(e.validate([{"op": "travel", "params": {"place": market.name}}],
                     origin="author:test"))
    return s, e, market


def test_the_market_is_open_by_day_and_its_keeper_sells():
    s, e, market = _at_the_market(10 * HOUR)
    keeper = keepers.keeper_in(s, market.id)
    assert keeper is not None and keeper.ref in s.actors
    assert keepers.shut_here(s) == ""


def test_at_night_the_stall_is_packed_up_and_its_keeper_has_gone_home():
    s, e, market = _at_the_market(23 * HOUR)
    keeper = keepers.keeper_in(s, market.id)
    assert keeper is not None and keeper.ref not in s.actors
    assert residency.is_offstage(keeper.at)
    shut = keepers.shut_here(s)
    assert "tomorrow" in shut and "first light" in shut


def test_a_shut_counter_refuses_to_sell_and_says_when_to_come_back():
    s, e, market = _at_the_market(23 * HOUR)
    out = e.run(e.validate([{"op": "buy", "actor": "pc", "params": {"item": "rope"}}],
                           origin="author:test"))
    buy = out.outcomes[0]
    assert buy.status == "refused" and "first light" in buy.tell


def test_the_keeper_comes_back_when_the_counter_opens():
    s, e, market = _at_the_market(23 * HOUR)
    keeper = keepers.keeper_in(s, market.id)
    elsewhere = next(p for p in e.places() if p.id != market.id)
    e.run(e.validate([{"op": "travel", "params": {"place": elsewhere.name}}],
                     origin="author:test"))
    s.advance(9 * HOUR)
    e.run(e.validate([{"op": "travel", "params": {"place": market.name}}],
                     origin="author:test"))
    assert keeper.ref in s.actors and keepers.shut_here(s) == ""


def test_somebody_is_always_open():
    """Skyrim's innkeepers; the player is never stranded with nobody to buy from."""
    tavern = f"{VORMOOR}~urban:the-tavern"
    assert all(keepers.open_now(tavern, h * HOUR) for h in range(24))


def test_the_smith_works_to_the_curfew_bell_and_the_market_does_not():
    smithy = f"{VORMOOR}~urban:the-smithy"
    market = f"{VORMOOR}~urban:the-market"
    assert keepers.open_now(smithy, 19 * HOUR) and not keepers.open_now(market, 19 * HOUR)


def test_a_keeper_under_a_roof_lives_there():
    """The Pierre lesson: a shut shop is not a shut building."""
    assert keepers.lives_in(f"{VORMOOR}~urban:the-guildhall")
    assert not keepers.lives_in(f"{VORMOOR}~urban:the-market")


def test_a_new_game_starts_at_the_hour_its_opening_names():
    """Every game began at clock 0 — midnight, as the app reads the clock — under an
    opening that said "Mid-morning, in the market row". Harmless while nothing read the
    hour; wrong once the market's counter kept hours."""
    from play import opening

    assert opening.hour_of("Mid-morning") == 10 and opening.hour_of("Dusk") == 19
    assert {s.when.lower() for s in opening.SITUATIONS} <= set(opening._HOUR_OF)


def test_the_narrator_is_told_what_time_it_is():
    """The brief never said the hour, so a narrator not told it writes the market
    bustling at a stall the engine has shut."""
    from gm import prompts

    s, e, market = _at_the_market(23 * HOUR)
    brief = prompts.scene_brief(WORLD, s, WORLD.get(VORMOOR), here=market,
                                known=e.places())
    assert "WHEN (fact): day 1, late evening (about 11 at night)" in brief
    assert "COUNTER SHUT (fact)" in brief
