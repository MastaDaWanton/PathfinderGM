"""Options B and C: Craft and Profession do things away from the benches.

The owner, 2026-10-06: "the craft skill and the profession skill seem pretty useless".
Measured that day (docs/craft-profession-options.md §1): a Craft rank bought one
house-rule construct repair; a Profession rank bought herb study (which Knowledge (nature)
already covered) and ramming at sea. There was no mending of ordinary gear (a sword broken
by a sunder stayed broken for ever — nothing in the engine raised an `Item`'s hit points),
no look at a thing's make, no trade question, no haggle (prices were tables, haggling an
alias to Diplomacy that moved nothing), and no earning: "Downtime" appeared once in the
code, as a citation. The owner chose B and C on 2026-10-07; every number below is a row in
content/rules/trade-uses.json, and the player rolls each die.
"""
from __future__ import annotations

import pytest

from rules import tradecraft
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"            # Pangrella, a town
CITY = "7ef5e373c993"            # Mirabalos, a city


def _table(town: str = TOWN, *, craft: int = 4, profession: int = 3, seed: int = 3):
    s = Scene(location_id=town)
    pc = s.add(load_pc("fixtures/pc-thessaly.json"))
    pc.ranks = {k: v for k, v in pc.ranks.items() if k not in ("craft", "profession")}
    if craft:
        pc.ranks["craft"] = craft
    if profession:
        pc.ranks["profession"] = profession
    pc.purse = {"gp": 50}
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    return s, e, pc


def _run(e, raw, *faces):
    res = e.run(e.validate([{"actor": "pc", "because": "test", **raw}]))
    for f in faces:
        assert res.awaiting, "the engine stopped asking for the player's die"
        res = e.resume(f)
    assert not res.awaiting
    return res.outcomes[-1]


# --- judge -----------------------------------------------------------------------------

def test_judging_reads_the_things_own_record_and_the_roll_is_the_players():
    s, e, pc = _table()
    res = e.run(e.validate([{"op": "judge", "actor": "pc", "because": "t",
                             "params": {"item": "quarterstaff"}}]))
    assert res.awaiting and res.awaiting["dc"] == 15
    assert res.awaiting["label"] == "Craft check (judge its make)"
    out = _run(e, {"op": "judge", "params": {"item": "dagger"}}, 1)
    assert out.verdict == "failure" and "cannot tell" in out.tell


def test_beaten_by_five_the_look_reads_hardness_and_hit_points():
    s, e, pc = _table()
    pc.damage_item("quarterstaff", 12)
    out = _run(e, {"op": "judge", "params": {"item": "my quarterstaff"}}, 15)
    assert "not masterwork" in out.tell
    assert ("Hardness 5, 3 of 10 hit points; broken — a two-handed hafted weapon "
            "(CRB Table 7-12).") in out.tell


def test_a_second_look_the_same_day_reveals_the_same_result():
    """CRB Appraise: 'Additional attempts ... reveal the same result' — no second die."""
    s, e, pc = _table()
    first = _run(e, {"op": "judge", "params": {"item": "dagger"}}, 2)
    again = e.run(e.validate([{"op": "judge", "actor": "pc", "because": "t",
                               "params": {"item": "dagger"}}]))
    assert not again.awaiting
    assert again.outcomes[-1].tell == first.tell


# --- mend -------------------------------------------------------------------------------

def test_a_broken_staff_is_mended_whole_for_a_fifth_of_its_price_and_an_hour_a_point():
    """Before this nothing raised an `Item`'s hit points: a sundered weapon stayed broken."""
    s, e, pc = _table()
    pc.damage_item("quarterstaff", 12)
    assert pc.gear["quarterstaff"].broken
    before = s.clock_minutes
    out = _run(e, {"op": "mend", "params": {"item": "quarterstaff"}}, 10)
    staff = pc.gear["quarterstaff"]
    assert (staff.hp, staff.broken) == (10, False)
    assert s.clock_minutes - before == 7 * 60          # 7 points, an hour each
    assert "the DC for a simple weapon" in out.tell and "no longer broken" in out.tell
    # A quarterstaff is unlisted in the Core gear table here, so a fifth of its worth.
    assert any(f["kind"] == "spent" for f in out.effects)


def test_a_failure_by_five_ruins_half_the_materials_and_mends_nothing():
    s, e, pc = _table(craft=1)
    # A projectile weapon: hardness 5, 5 hit points (CRB Table 7-12); 8 leaves 2.
    pc.damage_item("light crossbow", 8)               # a crossbow is DC 15 to make
    purse = dict(pc.purse)
    out = _run(e, {"op": "mend", "params": {"item": "light crossbow"}}, 1)
    assert pc.gear["light crossbow"].hp == 2
    assert "the DC for a crossbow" in out.tell
    assert "ruins half the materials" in out.tell
    assert pc.purse != purse


@pytest.mark.parametrize("hurt,why", [(0, "is whole"), (99, "ruined")])
def test_mending_refuses_what_is_whole_and_what_is_ruined(hurt, why):
    s, e, pc = _table()
    if hurt:
        pc.damage_item("quarterstaff", hurt)
    res = e.run(e.validate([{"op": "mend", "actor": "pc", "because": "t",
                             "params": {"item": "quarterstaff"}}]))
    assert not res.awaiting and res.outcomes[-1].status == "refused"
    assert why in res.outcomes[-1].tell


def test_the_making_dc_comes_from_the_crafts_table():
    """CRB p.91: simple weapon 12, martial 15, armour 10 + AC; masterwork at 20."""
    pc = load_pc("fixtures/pc-thessaly.json")
    assert tradecraft.creation_dc(pc, "dagger")[0] == 12
    assert tradecraft.creation_dc(pc, "longsword")[0] == 15
    assert tradecraft.creation_dc(pc, "chain shirt")[0] == 14
    assert tradecraft.creation_dc(pc, "masterwork longsword")[0] == 20


# --- a question of the trade -----------------------------------------------------------

def test_a_trade_question_is_the_crbs_dc_and_profession_is_trained_only():
    s, e, pc = _table()
    res = e.run(e.validate([{"op": "trade_lore", "actor": "pc", "because": "t",
                             "params": {"trade": "smith", "depth": "basic"}}]))
    assert res.awaiting["dc"] == 10
    s, e, pc = _table(profession=0)
    res = e.run(e.validate([{"op": "trade_lore", "actor": "pc", "because": "t",
                             "params": {"trade": "smith"}}]))
    assert res.outcomes[-1].status == "refused"
    assert "cannot be tried untrained" in res.outcomes[-1].tell


def test_knowing_the_trade_names_only_places_that_exist_here():
    s, e, pc = _table()
    out = _run(e, {"op": "trade_lore", "params": {"trade": "smith", "depth": "complex"}}, 18)
    names = {p.name for p in e.places()}
    for name in out.effects[0]["places"]:
        assert name in names


# --- haggle -----------------------------------------------------------------------------

def _keeper(s):
    return s.add(instantiate("guildhand", scene=s, name="Ama"))


def test_a_haggle_won_moves_the_counters_prices_both_ways_and_only_today():
    s, e, pc = _table()
    ama = _keeper(s)
    out = _run(e, {"op": "haggle", "target": ama.ref, "params": {"stall": "ama"}}, 20)
    pct = out.effects[0]["percent"]
    assert 2 <= pct <= 25
    from rules import market

    day = market.day_of(s.clock_minutes)
    assert tradecraft.haggled(s, pc.ref, s.location_id, "ama", day) == pct
    assert tradecraft.buy_price(100, pct) == 100 - pct
    assert tradecraft.sell_price(100, pct) == 100 + pct
    assert tradecraft.haggled(s, pc.ref, s.location_id, "ama", day + 1) == 0


def test_the_undercut_is_ultimate_campaigns_and_stops_at_its_floor():
    """2% + 1% a point (Ultimate Campaign, Bargaining); the seller's floor is 75%."""
    assert tradecraft.undercut(-1) == 0
    assert tradecraft.undercut(0) == 2
    assert tradecraft.undercut(10) == 12
    assert tradecraft.undercut(40) == 25


def test_once_a_counter_a_day_win_or_lose():
    s, e, pc = _table()
    ama = _keeper(s)
    _run(e, {"op": "haggle", "target": ama.ref, "params": {"stall": "ama"}}, 1)
    again = e.run(e.validate([{"op": "haggle", "actor": "pc", "target": ama.ref,
                               "because": "t", "params": {"stall": "ama"}}]))
    assert again.outcomes[-1].status == "refused" and "once today" in again.outcomes[-1].tell


def test_the_engine_charges_the_haggled_price_at_the_counter():
    """`_op_buy` reads the haggle: the price on the counter is the price paid."""
    from rules import market, pricing

    s, e, pc = _table()
    ama = _keeper(s)
    pc.purse = {"gp": 500}
    place, day = s.location_id, market.day_of(s.clock_minutes)
    s.dealings[tradecraft.dealing_key("haggle", pc.ref, place, "market", day)] = \
        {"percent": 20}
    shelf = market.on_sale(place, "market", day, s.market_taken)
    thing = next(m for m in shelf if pricing.worth(m, buyer=pc, town=place) >= 1)
    out = _run(e, {"op": "buy", "params": {"item": thing.id, "stall": "market"}})
    want = tradecraft.buy_price(round(pricing.worth(thing, buyer=pc, town=place), 2), 20)
    assert out.effects[0]["paid_cp"] == int(round(want * 100))
    assert "20% off for the haggle" in out.tell


# --- a day's work -----------------------------------------------------------------------

def test_a_week_of_work_in_town_pays_the_tables_rate_through_the_clock():
    s, e, pc = _table()
    offer = tradecraft.work_offer(pc, "town")
    before, purse = s.clock_minutes, dict(pc.purse)
    out = _run(e, {"op": "work", "params": {"days": 7, "trade": "smith"}}, 10)
    earned = next(f for f in out.effects if f["kind"] == "earned")
    assert earned["days"] == 7
    assert earned["paid_cp"] == 7 * offer["pay_cp"][earned["degree"]]
    # Six full days and the seventh's working hours: the evenings between are slept.
    assert s.clock_minutes - before == 6 * 24 * 60 + 8 * 60
    assert pc.purse != purse


def test_the_pay_is_the_task_and_training_not_the_dies_total():
    """PF2e replaced PF1's half-the-check wage so stacked bonuses stop inflating income:
    a natural 20 and a total that beats the DC by 10 pay the same critical column."""
    s, e, pc = _table()
    offer = tradecraft.work_offer(pc, "town")
    assert tradecraft.degree(10) == tradecraft.degree(30) == "critical success"
    assert offer["pay_cp"]["critical success"] > offer["pay_cp"]["success"] \
        > offer["pay_cp"]["failure"] > offer["pay_cp"]["critical failure"] == 0


def test_a_level_3_week_in_a_city_pays_half_what_it_did():
    """The owner, 2026-10-07: "Paid work: halve it." At coin_scale 10 a level-3 expert in
    a city (task 3, DC 18) earned 500 cp a day on a success — 35 gp a week, about four
    times the CRB's half-the-check wage of 8 gp. At 5: 250 cp a day, 17 gp 5 sp a week.
    The untrained wage is the CRB's own 1 sp and does not move."""
    assert tradecraft.row("day-work")["coin_scale"] == 5
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.level, pc.ranks["profession"] = 3, 3
    offer = tradecraft.work_offer(pc, "city")
    assert (offer["task"], offer["proficiency"], offer["dc"]) == (3, "expert", 18)
    assert offer["pay_cp"] == {"critical success": 400, "success": 250, "failure": 40,
                               "critical failure": 0}
    assert 7 * offer["pay_cp"]["success"] == 1750
    pc.ranks["profession"] = 0
    assert tradecraft.work_offer(pc, "city")["pay_cp"] == {"untrained": 10}


def test_the_task_is_capped_by_the_settlement_and_by_the_level():
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.ranks["profession"] = 1
    pc.level = 9
    assert tradecraft.work_offer(pc, "village")["task"] == 1
    assert tradecraft.work_offer(pc, "town")["task"] == 4
    assert tradecraft.work_offer(pc, "city")["task"] == 7
    pc.level = 2
    assert tradecraft.work_offer(pc, "city")["task"] == 2


@pytest.mark.parametrize("ranks,prof", [(0, "untrained"), (1, "trained"), (3, "expert"),
                                        (7, "master"), (15, "legendary")])
def test_training_is_read_from_ranks_at_pf2es_levels(ranks, prof):
    assert tradecraft.proficiency(ranks) == prof


def test_with_no_trade_ranks_anyone_may_labour_for_the_crbs_silver_a_day():
    s, e, pc = _table(craft=0, profession=0)
    res = e.run(e.validate([{"op": "work", "actor": "pc", "because": "t",
                             "params": {"days": 1}}]))
    assert not res.awaiting
    earned = next(f for f in res.outcomes[-1].effects if f["kind"] == "earned")
    assert earned["paid_cp"] == 10


def test_there_is_no_work_alone_in_the_wilds():
    s, e, pc = _table()
    s.at = f"{TOWN}~forest:the-approach"
    res = e.run(e.validate([{"op": "work", "actor": "pc", "because": "t",
                             "params": {"days": 1}}]))
    assert res.outcomes[-1].status == "refused"
    assert "no work out here" in res.outcomes[-1].tell


def test_a_critical_failure_ends_the_work_the_first_day_unpaid():
    """PF2e: a critical failure earns nothing and is let go at once."""
    s, e, pc = _table(craft=1, profession=0)
    pc.abilities["int"] = 3                       # Craft +1: a 1 misses DC 15 by 14
    before = s.clock_minutes
    out = _run(e, {"op": "work", "params": {"days": 7}}, 1)
    earned = next(f for f in out.effects if f["kind"] == "earned")
    assert earned["degree"] == "critical failure"
    assert (earned["paid_cp"], earned["days"]) == (0, 1)
    assert s.clock_minutes - before == 8 * 60


def test_the_plan_cannot_write_a_number_of_days():
    """A model-authored count is held to the row's two stints."""
    from rules.intents import parse

    raw = {"op": "work", "actor": "pc", "because": "t", "params": {"days": 365}}
    assert parse(raw).params["days"] == 7
    assert parse({**raw, "params": {"days": 1}}).params["days"] == 1


# --- the means gate ---------------------------------------------------------------------

def test_the_means_gate_lets_the_trade_uses_through_as_ordinary_attempts():
    """A skill use is anybody's to try (gm/means.py): the gate strikes amount ops and
    guesses beside a refused power, and must not strike these."""
    from gm import means

    s, e, pc = _table()
    plan = [{"op": op, "actor": "pc", "params": {}} for op in
            ("judge", "mend", "trade_lore", "haggle", "work")]
    judged = [{"span": "I read his mind", "refused_name": "read minds", "held": None}]
    kept = means.strike(plan, judged, {"actions": []}, s)
    assert [r["op"] for r in kept[:5]] == ["judge", "mend", "trade_lore", "haggle", "work"]
