"""A long wait the player chose is lived through on what they carry (2026-10-08).

Measured by the leatherworking bench lane, in the RELEASED game (0.2.11): a 21-day bark
tannage's "Wait for it" killed a scratch character of thirst — twice, the second time
carrying 40 waterskins — and the bench said only "You waited 21 days. You take the leather
out". Earlier an 8-day enchanting binding wait killed an unfed character the same way.
Every long wait went through `Scene.advance`, which charges the body each hour and rolls
its checks (`survival.charge`) but never ate or drank: only a march's camp did, and a
wait has no camp. Waterskins did nothing at all — no row in content/rules/gear.json.

Now (`survival._provide`, `gear.provide`, `Scene.wait`): a stretch of a day or more is
lived through — a day's water (a gallon, two waterskins) and a day's food (a pound, one
trail ration) out of the pack as each comes due, and a night's sleep once a day (CRB
p.444, Starvation and Thirst). A chosen wait that the pack cannot carry stops at the hour
the book's grace would run out after the last drink or meal, before any check is rolled,
and says so in words. A wait shorter than a day behaves exactly as before.
"""
from __future__ import annotations

import random

import pytest

from rules import gear, survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

HOUR = 60
DAY = 24 * HOUR


def _pc(**kw):
    pc = from_dict(to_dict(load_pc("fixtures/pc-kesst.json")), ref="pc")
    pc.kind = "pc"
    for k, v in kw.items():
        setattr(pc, k, v)
    return pc


def _scene(pc, seed=7, clock=3 * DAY + 8 * HOUR):
    s = Scene(location_id="bde94b038cba")
    s.add(pc)
    s.clock_minutes = clock
    return s, Engine(s, Dice(seed=seed))


def _checks(passed, kinds=("Thirst", "Hunger", "Exhaustion")):
    return [c for r in passed["body"] for c in r.get("checks") or () if c["kind"] in kinds]


def test_a_21_day_tannage_wait_no_longer_kills_a_character_carrying_40_waterskins():
    """The lane's second death: 40 waterskins and 21 rations carried, a 21-day wait, dead
    of thirst. 40 skins are 20 gallons, twenty days at the book's gallon a day; the 21st
    day falls inside the 24 + Constitution hours of grace, so the wait runs whole, nobody
    is asked a single check, and every skin is drunk and kept, empty."""
    pc = _pc()
    pc.goods.update({"waterskin": 40, "trail rations": 21})
    scene, _ = _scene(pc)
    hp = pc.hp
    passed = scene.wait(21 * DAY)
    assert passed["minutes"] == 21 * DAY and not passed["stopped"]
    assert not pc.has_state("state.down") and pc.hp == hp and not pc.nonlethal
    assert _checks(passed) == []
    assert "waterskin" not in pc.goods and pc.goods["empty waterskin"] == 40
    assert pc.goods.get("trail rations", 0) == 0          # one a day, 21 days
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert "drinks 20 gallons of water (40 of their waterskins)" in said, said
    assert "eats 21 pounds of food (21 of their trail rations)" in said, said
    assert "sleeps 21 nights" in said, said


def test_the_cost_is_told_to_the_narrator_through_the_bodys_outcome():
    """Law 3: the meals are a toll like the checks, told at the end of the batch
    (`Engine._body_settles`) — "I wait 3 days" at the table says what it ate."""
    pc = _pc()
    pc.goods.update({"waterskin": 10, "trail rations": 5})
    scene, engine = _scene(pc)
    res = engine.run(engine.validate([
        {"op": "advance_time", "actor": "pc", "because": "the player waits",
         "params": {"amount": 3, "unit": "day"}}]))
    body = [o for o in res.outcomes if o.op == "body"]
    assert body and "drinks 3 gallons of water" in body[0].tell, [o.tell for o in res.outcomes]
    assert "eats 3 pounds of food" in body[0].tell
    assert pc.goods["waterskin"] == 4 and pc.goods["trail rations"] == 2


def test_an_8_day_wait_at_the_table_on_an_empty_pack_stops_and_says_why():
    """The enchanting death: an 8-day wait for a binding, nothing carried, an unfed
    character dead at the end of it. "I wait 8 days" is `advance_time`; it now ends at
    36 hours and both the op's tell and the body's say so."""
    pc = _pc()
    scene, engine = _scene(pc)
    res = engine.run(engine.validate([
        {"op": "advance_time", "actor": "pc", "because": "the player waits",
         "params": {"amount": 8, "unit": "day"}}]))
    tells = [o.tell for o in res.outcomes]
    assert any(t == "The wait ends after 1 day 12 hours of the 8 days asked." for t in tells), tells
    assert any("stops waiting after 1 day 12 hours" in t for t in tells), tells
    assert not pc.has_state("state.down") and not pc.nonlethal


def test_with_nothing_carried_the_wait_stops_before_thirst_is_rolled():
    """The same 21-day wait with an empty pack killed the first scratch character. Now it
    stops at 24 + Constitution (12) = 36 hours, the hour before the first thirst check,
    and says why — the body has paid nothing it will not get back by drinking."""
    pc = _pc()
    scene, _ = _scene(pc)
    passed = scene.wait(21 * DAY)
    assert passed["stopped"] == "water"
    assert passed["minutes"] == 36 * HOUR and passed["unwaited"] == 21 * DAY - 36 * HOUR
    assert _checks(passed, ("Thirst", "Hunger")) == []
    assert not pc.has_state("state.down") and not pc.nonlethal
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert "stops waiting after 1 day 12 hours" in said, said
    assert "no water in the pack" in said and "half a gallon" in said, said
    # Queued for the narrator too, on the same record (one toll, not two).
    assert any(r.get("stopped") == "water" for r in scene._body_said)


def test_already_parched_with_nothing_to_drink_the_wait_does_not_begin():
    pc = _pc(watered_minutes=40 * HOUR)
    scene, _ = _scene(pc)
    before = scene.clock_minutes
    passed = scene.wait(3 * DAY)
    assert passed["minutes"] == 0 and scene.clock_minutes == before
    said = " ".join(survival.wait_lines(passed, "pc"))
    assert said.startswith("Kesst Vayr cannot wait 3 days: there is no water"), said


def test_food_runs_out_on_its_own_grace():
    """Water for a week, food for one day: the meal is due at the day's mark, the one
    ration is eaten, and the wait stops when hunger's three days run out after it."""
    pc = _pc()
    pc.goods.update({"waterskin": 14, "trail rations": 1})
    scene, _ = _scene(pc)
    passed = scene.wait(7 * DAY)
    assert passed["stopped"] == "food"
    assert passed["minutes"] == DAY + 72 * HOUR
    assert _checks(passed) == []


def test_a_wait_shorter_than_a_day_is_exactly_what_it_was():
    """A meal's interval is a day; under it the pack is not touched and the counters run
    as before — 23 hours since the last drink and a two-hour wait drinks nothing."""
    pc = _pc(watered_minutes=23 * HOUR, fed_minutes=23 * HOUR, awake_minutes=23 * HOUR)
    pc.goods.update({"waterskin": 4, "trail rations": 2})
    scene, _ = _scene(pc)
    passed = scene.wait(2 * HOUR)
    assert passed["minutes"] == 2 * HOUR and not passed["stopped"]
    assert pc.goods == {"waterskin": 4, "trail rations": 2}
    assert pc.watered_minutes == 25 * HOUR and pc.awake_minutes == 25 * HOUR


def test_sleep_inside_a_long_wait_spares_every_will_save():
    """Before: three days of waiting were 48 Will saves against sleep past the first day.
    Living through it, the body sleeps once a day and is never asked."""
    pc = _pc()
    pc.goods.update({"waterskin": 6, "trail rations": 3})
    scene, _ = _scene(pc)
    passed = scene.wait(3 * DAY)
    assert _checks(passed, ("Exhaustion",)) == []
    rec = next(r for r in passed["body"] if r["ref"] == "pc")
    assert rec["nights"] == 3 and pc.awake_minutes < 24 * HOUR


def test_the_stop_and_the_spend_never_disagree():
    """`survival.lasts` is the pre-flight and `_provide` the spend; each is worked from
    the same counters, daily need and greedy draw. Over 200 random packs and starting
    counters, a wait stopped where `lasts` says never rolls a thirst or hunger check, and
    one that `lasts` lets run never stops."""
    rng = random.Random(11)
    for i in range(200):
        pc = _pc(watered_minutes=rng.randrange(0, 34 * HOUR),
                 fed_minutes=rng.randrange(0, 70 * HOUR))
        pc.goods.update({k: n for k, n in (("waterskin", rng.randrange(0, 9)),
                                            ("trail rations", rng.randrange(0, 4)),
                                            ("loaf of bread", rng.randrange(0, 3)))
                         if n})
        scene, _ = _scene(pc, seed=i)
        asked = rng.randrange(1, 8) * DAY
        covered, short = survival.lasts(pc, asked)
        passed = scene.wait(asked)
        assert passed["minutes"] == covered and passed["stopped"] == short, i
        assert _checks(passed, ("Thirst", "Hunger")) == [], (i, pc.goods)


def test_a_small_body_drinks_half_and_the_desert_twice():
    """CRB p.444: "Small characters need half as much"; "In very hot climates ... two or
    three times as much water" — the desert, at two."""
    small = _pc(size="small")
    assert survival.daily_need(small, "water") == 0.5
    assert survival.daily_need(small, "food") == 0.5
    assert survival.daily_need(_pc(), "water", "desert") == 2.0


def test_the_waterskin_is_a_gear_row_and_the_rows_validate():
    """Waterskins were nothing to the engine: no row, so 40 of them watered nobody."""
    key, row = gear.row_for("waterskin")
    assert key == "waterskin" and row["drink"]["gallons"] == 0.5
    assert gear.validate() == []
    bad = {"items": {"x": {"names": ["x"], "does": "x", "drink": {"gallons": "lots"}}}}
    assert any("drink" in p for p in gear.validate(bad))


def test_a_companion_is_not_fed_out_of_the_players_pack():
    """Only the player rolls and only the player is fed (`charge`'s rule): a companion's
    counters run as before, and the player's pack pays for one."""
    pc = _pc()
    pc.goods.update({"waterskin": 8, "trail rations": 4})
    scene, _ = _scene(pc)
    friend = _pc()
    friend.ref, friend.kind, friend.name = "c1", "npc", "Ivo"
    scene.add(friend)
    scene.wait(2 * DAY)
    assert pc.goods["waterskin"] == 4 and friend.watered_minutes == 2 * DAY


def test_alchemy_wait_for_it_stops_in_words_on_an_empty_pack(tmp_path):
    """The bench's own door (`api/alchemy/collect {wait: true}`), the one the tannage used:
    a work three weeks out, nothing carried — the wait stops, says why, collects nothing,
    and the character is alive; with water and food it waits the whole way and says what
    it cost."""
    import json

    from django.test import Client, override_settings

    from play import alchemy_views
    from play import campaign as cm
    from rules import goods, inprogress

    def post(client, url, body):
        return client.post(url, data=json.dumps(body), content_type="application/json")

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        try:
            c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                              start_id="quiet-the-bread-stall")
            pc = c.scene.pc()
            pc.inventory.clear()
            pc.stock.clear()
            pc.goods.clear()
            pc.purse = {"gp": 200}
            pc.fed_minutes = pc.watered_minutes = pc.awake_minutes = 0
            goods.deliver(c.scene, pc, goods.good("alchemist's field kit"))
            pc.carry("wintergreen-essence", 1)
            pc.carry("glass-vial", 1)
            c.save()
            bench = Client()
            body = {"method": "bottle", "inputs": ["inv:wintergreen-essence"],
                    "vessel": "inv:glass-vial", "face": 20}
            r = post(bench, "/api/alchemy/roll", body).json()
            f = post(bench, "/api/alchemy/finish", {"token": r["token"], "score": 0.5}).json()
            key = f["products"][0]["key"]
            # Three weeks to set, as the tannage did.
            pc = cm.current().scene.pc()
            pc.fed_minutes = pc.watered_minutes = pc.awake_minutes = 0
            now = cm.current().scene.clock_minutes
            working = [s for s in pc.stock.values() if inprogress.work_of(s, now)]
            assert len(working) == 1, list(pc.stock)
            block = inprogress._stored(working[0])
            if block is not None:
                block["minutes"] = int(now) - int(block["started"]) + 21 * DAY
            else:
                working[0].ready_minute = int(now) + 21 * DAY
            cm.current().save()
            row = next(r for r in alchemy_views._works(cm.current(), pc))
            assert row["ready_in"] == 21 * DAY, row

            got = post(bench, "/api/alchemy/collect", {"key": key, "wait": True})
            assert got.status_code == 200, got.content[:300]
            got = got.json()
            assert got["stopped"] == "water" and got["waited"] == 36 * HOUR
            assert "stops waiting after 1 day 12 hours" in " ".join(got["body"])
            pc = cm.current().scene.pc()
            assert not pc.has_state("state.down") and got["works"]

            pc.goods.update({"waterskin": 42, "trail rations": 21})
            cm.current().save()
            got = post(bench, "/api/alchemy/collect", {"key": key, "wait": True}).json()
            assert got.get("product") and not got.get("stopped"), got
            assert "gallons of water" in " ".join(got["body"]), got["body"]
            assert not cm.current().scene.pc().has_state("state.down")
        finally:
            cm._LIVE.clear()
            alchemy_views._PENDING.clear()
