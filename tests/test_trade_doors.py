"""The trade uses' buttons: Judge its make and Mend on the Equipment tab, Haggle at the
counter, Earn a living on the sheet (play/tradecraft_views.py; options B and C, 2026-10-07).

Each is the engine's op by another door, the way the Spells tab casts (`cast_act`): the
button's closed choices become the op, the player's die is asked for, and the narrator is
fed the tell. Found in the live check and pinned here:
  * the Equipment tab offered no way to see that a sword was broken — the row read like a
    whole one (now a `damage` chip, and Mend only where there is damage to mend);
  * the counter's Haggle answered with prices the engine would not charge unless the
    trade window drew the same numbers the buy op reads (`tradecraft.haggled` in both).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules.sheet import load_pc

WORK_HOUR = 10 * 60
TOWN = "5bbd0c40345f"            # Pangrella, a town


@pytest.fixture
def market(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        me = c.scene.pc().ref
        for ref in [r for r in list(c.scene.people) if r != me]:
            c.scene.remove(ref)
        c.scene.initiative = []
        c.scene.staffed = []
        c.scene.location_id = TOWN
        c.scene.clock_minutes = WORK_HOUR
        c.engine().place_party(f"{TOWN}~urban:the-market")
        pc = c.scene.pc()
        pc.purse = {"gp": 120}
        pc.ranks = {**pc.ranks, "craft": 3, "profession": 3}
        pc.weapons = list(pc.weapons) + ["longsword"]
        c.save()
        yield c, cm
        cm._LIVE.clear()


def _post(url, body):
    return Client().post(url, data=json.dumps(body), content_type="application/json")


def test_the_equipment_tab_says_a_sword_is_broken_and_offers_to_mend_it(market):
    from play import views

    c, cm = market
    pc = c.scene.pc()
    pc.damage_item("longsword", 26)
    rows = {r["key"]: r for r in views._carried(pc)}
    sword = rows["longsword"]
    assert sword["damage"] == "broken: 14 of 30 hit points"
    assert [a["label"] for a in sword["trade_acts"]] == ["Judge its make", "Mend"]
    # Whole things are judged, not mended; the wear doors are untouched.
    assert [a["label"] for a in rows["dagger"]["trade_acts"]] == ["Judge its make"]
    assert all(a["api"] != "/api/tradeskill" for r in rows.values() for a in r["acts"])


def test_mend_by_button_asks_the_players_die_then_makes_it_whole(market):
    c, cm = market
    c.scene.pc().damage_item("longsword", 26)
    c.save()
    r = _post("/api/tradeskill", {"use": "mend", "item": "longsword"})
    assert r.status_code == 200
    asked = r.json()["awaiting"]
    assert asked["label"] == "Craft check (mend)" and asked["dc"] == 15
    assert asked["because"] == "mending it"
    done = _post("/api/roll", {"face": 20})
    assert done.status_code == 200
    sword = cm.current().scene.pc().gear["longsword"]
    assert (sword.hp, sword.broken) == (sword.hp_max, False)


def test_haggle_at_the_counter_moves_the_prices_the_window_draws(market):
    c, cm = market
    before = _post("/api/trade", {"line": "general"}).json()
    assert before["can_haggle"] and before["haggled"] == 0
    r = _post("/api/tradeskill", {"use": "haggle", "line": "general"})
    assert r.status_code == 200 and r.json()["awaiting"]["label"] == "Profession check (haggle)"
    assert _post("/api/roll", {"face": 20}).status_code == 200
    after = _post("/api/trade", {"line": "general"}).json()
    assert not after["can_haggle"]
    pct = after["haggled"]
    if pct:
        was = {x["id"]: x["gp"] for x in before["theirs"]}
        for x in after["theirs"]:
            if x["id"] in was and was[x["id"]] >= 1:
                assert x["gp"] == pytest.approx(round(was[x["id"]] * (100 - pct) / 100, 2),
                                                abs=0.011)


def test_the_sheet_is_told_what_a_days_work_pays_here(market):
    r = Client().get("/api/tradeskill/offer").json()
    assert r["here"] and r["scale"] == "town"
    assert r["skill"] == "profession" and r["proficiency"] == "expert"
    assert set(r["pay"]) == {"critical success", "success", "failure", "critical failure"}


def test_a_week_of_work_by_button_pays_into_the_purse(market):
    c, cm = market
    r = _post("/api/tradeskill", {"use": "work", "days": "7"})
    assert r.status_code == 200 and r.json()["awaiting"]["because"] == "a day's work at the trade"
    assert _post("/api/roll", {"face": 15}).status_code == 200
    pc = cm.current().scene.pc()
    assert pc.purse != {"gp": 120}


def test_the_button_door_takes_only_its_closed_uses(market):
    assert _post("/api/tradeskill", {"use": "steal"}).status_code == 400
    assert _post("/api/tradeskill", {"use": "judge"}).status_code == 400
