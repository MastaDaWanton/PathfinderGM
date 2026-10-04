"""The forge bench through its API (docs/blacksmithing-contracts.md §7).

Driven through the Django test client on a real campaign, with lanes B, C and E standing
in as the echoing fakes of tests/test_forge_bench.py and lane G's two places functions and
its rent patched onto the real modules. Each test names the defect it prevents.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import campaign as cm
from play import forge_views
from rules import blacksmith as bs
from rules.sheet import load_pc
from tests.test_forge_bench import SMITHY, TOWN, fake_forge_items, fake_knowledge, \
    fake_materials

import sys


@pytest.fixture
def where(monkeypatch):
    """Lane G's door, switchable per test: {"smithy": dict | None, "kit": bool}."""
    from rules import market, places

    state = {"smithy": None, "kit": True, "rent": []}
    monkeypatch.setattr(places, "smithy_here", lambda scene, known=(): state["smithy"],
                        raising=False)
    monkeypatch.setattr(places, "has_field_kit", lambda actor: state["kit"],
                        raising=False)

    def forge_rent(scene, hours, known=()):
        state["rent"].append(hours)
        here = state["smithy"]
        return int(round(int(here["rate_cp_per_hour"]) * hours)) if here else 0

    monkeypatch.setattr(market, "forge_rent", forge_rent, raising=False)
    return state


@pytest.fixture
def forge(tmp_path, monkeypatch, where):
    calls: list = []
    monkeypatch.setitem(sys.modules, "rules.materials", fake_materials())
    monkeypatch.setitem(sys.modules, "rules.forge_items", fake_forge_items(calls))
    monkeypatch.setitem(sys.modules, "rules.knowledge", fake_knowledge())
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        forge_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.purse = {"gp": 5}
        c.save()
        client = Client()
        client.calls = calls
        yield client
        cm._LIVE.clear()
        forge_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def _level(n: int):
    _pc().track("blacksmith").level = n
    cm.current().save()


def _carry(**counts):
    for iid, n in counts.items():
        _pc().carry(iid.replace("_", "-"), n)
    cm.current().save()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def do_step(client, body, *, face=20, score=1.0):
    """check, roll, finish: one step as the page drives it."""
    r = post(client, "/api/forge/roll", {**body, "face": face})
    assert r.status_code == 200, r.content[:400]
    rolled = r.json()
    assert rolled["roll"]["success"], rolled
    f = post(client, "/api/forge/finish", {"token": rolled["token"], "score": score})
    assert f.status_code == 200, f.content[:400]
    return f.json()


def rack_key(client, form, material=None):
    rack = client.get("/api/forge/state").json()["rack"]
    return next(x["key"] for x in rack if x["form"] == form
                and (material is None or x["material"] == material))


# --- routes ------------------------------------------------------------------------------

def test_every_forge_route_reaches_the_forge():
    """The herb bench's measured route-order bug (2026-10-02): a fixed name read as a
    parameter by a pattern declared first answered 404. Every fixed forge name resolves to
    its own view, and a material card still resolves to the card."""
    for name in ("state", "check", "roll", "finish", "assay", "perks", "ledger"):
        assert resolve(f"/api/forge/{name}").func is getattr(forge_views, f"forge_{name}")
    hit = resolve("/api/forge/material/iron")
    assert hit.func is forge_views.forge_material and hit.kwargs == {"material_id": "iron"}


# --- state -------------------------------------------------------------------------------

def test_state_carries_the_rack_methods_with_locks_and_where_you_are(forge, where):
    """Contracts §7 `state`: the rack (only what is carried), every method with its lock
    in words, where you are, level, perks banked and ceiling. Before a smithy, Smelt says
    "Needs a smithy"; at Blacksmith 1, Alloy says "Blacksmith 2"."""
    _carry(iron=2, charcoal=1, ash_haft=1)
    d = forge.get("/api/forge/state").json()
    assert {x["key"] for x in d["rack"]} == {"inv:iron", "inv:charcoal", "inv:ash-haft"}
    groups = {x["key"]: x["group"] for x in d["rack"]}
    assert groups["inv:ash-haft"] == "Hafts, grips and fittings"
    locks = {m["id"]: m["lock_reason"] for m in d["methods"]}
    assert locks["smelt"] == "Needs a smithy" and locks["alloy"] == "Blacksmith 2"
    assert locks["forge"] == "" and len(d["methods"]) == 11
    assert d["where"]["smithy"] is None and d["where"]["kit"] is True
    assert (d["level"], d["ceiling"], d["picks_banked"]) == (1, 2, 0)
    assert d["track"]["tiers"] == ["Crude", "Sound", "Fine"]
    assert any(f["family"] == "One-Handed Weapons" for f in d["shapes"])
    assert any(a["id"] == "bronze" for a in d["alloys"])
    where["smithy"] = SMITHY["smithy"]
    locks = {m["id"]: m["lock_reason"] for m in
             forge.get("/api/forge/state").json()["methods"]}
    assert locks["smelt"] == ""


# --- one item, end to end ----------------------------------------------------------------

def test_bars_to_a_wieldable_longsword_through_the_api(forge):
    """The whole chain the page drives, against the real campaign: forge, quench, temper,
    hone, assemble. Every number comes back from the server (DC, need, info, tier), the
    finished record lands in `pc.stock` and survives a reload, and lane B's build is
    asked of that exact record."""
    _level(2)
    _carry(iron=1, charcoal=1, water=1, ash_haft=1, brass_guard=1)
    body = {"method": "forge", "shape": "longsword",
            "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
    chk = post(forge, "/api/forge/check", body).json()
    assert chk["can_roll"] and chk["dc"] == 15 and chk["need"] == 15 - chk["bonus"]
    assert chk["info"].startswith("1 blank. 1h 30m. DC 15")
    assert chk["preview"]["build"]["quality_index"] == chk["ceiling"]
    assert chk["fits"]["metal"]["inv:iron"] == "" and chk["fits"]["metal"]["inv:water"]
    done = do_step(forge, body)
    assert done["tier_name"] == "Superior" and done["products"][0]["form"] == "blank"
    blank = done["products"][0]["key"]
    blank = do_step(forge, {"method": "quench", "slots": {"piece": blank,
                                                          "quenchant": "inv:water"}}
                    )["products"][0]["key"]
    blank = do_step(forge, {"method": "temper", "slots": {"piece": blank}})["products"][0]["key"]
    blank = do_step(forge, {"method": "hone", "slots": {"piece": blank}})["products"][0]["key"]
    chk = post(forge, "/api/forge/check", {"method": "assemble", "slots": {
        "head": blank, "haft": "inv:ash-haft", "fittings": "inv:brass-guard"}}).json()
    assert chk["dc"] == 20 and chk["masterwork"]["ready"] is True
    done = do_step(forge, {"method": "assemble", "slots": {
        "head": blank, "haft": "inv:ash-haft", "fittings": "inv:brass-guard"}})
    product = done["products"][0]
    rec = product["record"]
    assert rec["name"] == "Superior Iron Longsword" and rec["masterwork"] is True
    assert rec["pieces"]["head"] == {"material": "iron", "passes": 0}
    assert product["build"]["masterwork"] is True
    assert ("build", rec) in forge.calls
    assert any("first item" in x["why"] for x in done["mastery"]["lines"])

    cm._LIVE.clear()
    pc = cm.current().scene.pc()
    assert [bs.record(st) for st in pc.stock.values()] == [rec]
    assert pc.inventory == {}


def test_smelting_at_a_town_smithy_pays_the_smith(forge, where):
    """Plan §10: a town smithy is paid by the hour, through lane G's `forge_rent`. Two
    ingots are two hours; the rent leaves the purse at the roll, and a purse that cannot
    cover it refuses the step before any die is thrown."""
    where["smithy"] = TOWN["smithy"]
    _carry(iron_ore=4, charcoal=4)
    body = {"method": "smelt", "batch": 2,
            "slots": {"ore": "inv:iron-ore", "fuel": "inv:charcoal"}}
    chk = post(forge, "/api/forge/check", body).json()
    assert chk["rent_cp"] == 20 and chk["can_roll"]
    done = do_step(forge, body, score=0.5)
    assert done["products"][0]["count"] == 2
    assert done["products"][0]["name"] == "Iron Ingot"
    from rules import goods

    assert goods.in_copper(_pc().purse) == 500 - 20
    _pc().purse = {"cp": 3}
    cm.current().save()
    _carry(iron_ore=2, charcoal=2)
    poor = post(forge, "/api/forge/roll", {**body, "batch": 1, "face": 20})
    assert poor.status_code == 400 and "wants 10 cp" in poor.json()["error"]


def test_smelting_on_the_field_kit_is_refused_in_words(forge):
    """No furnace on a field kit (plan §10): the roll is refused with the reason, and
    nothing is spent."""
    _carry(iron_ore=2, charcoal=2)
    r = post(forge, "/api/forge/roll", {"method": "smelt", "face": 20,
                                        "slots": {"ore": "inv:iron-ore",
                                                  "fuel": "inv:charcoal"}})
    assert r.status_code == 400 and "needs a smithy" in r.json()["error"]
    assert _pc().inventory == {"iron-ore": 2, "charcoal": 2}


def test_a_miss_by_five_ruins_half_and_says_what(forge):
    """The PF1e fail rule (plan §11), applied at the roll: half of what was on the anvil
    is lost, named, and written to the table's log once."""
    _carry(iron=2, charcoal=2)
    before = len(cm.current().transcript)
    r = post(forge, "/api/forge/roll", {"method": "forge", "shape": "dagger", "face": 1,
                                        "slots": {"metal": "inv:iron",
                                                  "fuel": "inv:charcoal"}})
    d = r.json()
    assert d["roll"]["success"] is False and d["lost"]
    assert sum(x["count"] for x in d["lost"]) == 1
    assert "Half of what was on the anvil is ruined" in d["said"]
    assert len(cm.current().transcript) == before + 1


def test_a_lost_reservation_goes_back_on_the_rack(forge):
    """Nothing is spent between roll and finish: opening the forge again lets the step in
    flight go, its token stops working and the materials were never taken."""
    _carry(iron=1, charcoal=1)
    body = {"method": "forge", "shape": "dagger", "face": 20,
            "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
    token = post(forge, "/api/forge/roll", body).json()["token"]
    held = {x["key"] for x in forge.get("/api/forge/state").json()["rack"]}
    assert held == {"inv:iron", "inv:charcoal"}
    late = post(forge, "/api/forge/finish", {"token": token, "score": 1})
    assert late.status_code == 409
    assert _pc().inventory == {"iron": 1, "charcoal": 1}


def test_the_score_is_clamped_server_side(forge):
    """The page sends a score; the server decides what it is worth. A forged score of 7 at
    Blacksmith 1 lands on Fine and no higher."""
    _carry(iron=1, charcoal=1)
    done = do_step(forge, {"method": "forge", "shape": "dagger",
                           "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}},
                   score=7)
    assert done["tier_name"] == "Fine" and done["score"] == 1.0


def test_working_a_metal_reveals_its_working_traits(forge):
    """Plan §9.2: working a material reveals its working traits ("you watched it
    behave"). Forging iron teaches its `forgiving` trait, once, with mastery for it."""
    _carry(iron=2, charcoal=2)
    body = {"method": "forge", "shape": "dagger",
            "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
    first = do_step(forge, body)
    assert [d["text"] for d in first["discoveries"] if d["material"] == "iron"] == \
        ["works forgiving"]
    assert any(x["why"].startswith("learned: Iron") for x in first["mastery"]["lines"])
    again = do_step(forge, body)
    assert not [d for d in again["discoveries"] if d["material"] == "iron"]


# --- assay, perks, ledger ----------------------------------------------------------------

def test_assay_takes_a_sliver_and_pays_for_what_it_teaches(forge):
    """Plan §9.2 through lane E's `knowledge.assay`: a tenth of a carried bar, ten
    minutes, the revealed properties in words and +3 mastery each."""
    _carry(iron=1)
    clock = cm.current().scene.clock_minutes
    d = post(forge, "/api/forge/assay", {"material": "iron", "face": 15}).json()
    assert [x["key"] for x in d["revealed"]] == ["k0", "k1"]
    assert d["minutes"] == 10 and cm.current().scene.clock_minutes == clock + 10
    assert sum(x["mp"] for x in d["mastery"]["lines"]) == 6
    iron = [x for x in d["rack"] if x["material"] == "iron"]
    assert [x["amount"] for x in iron] == [0.9]
    none = post(forge, "/api/forge/assay", {"material": "mithral"})
    assert none.status_code == 409 and "no Mithral" in none.json()["error"]


def test_assay_says_plainly_when_lane_e_is_missing(forge, monkeypatch):
    """A half-built feature is refused honestly rather than 500ing (benches.supports
    learned the same): no knowledge module, a 501 with a sentence."""
    monkeypatch.setitem(sys.modules, "rules.knowledge", None)
    _carry(iron=1)
    r = post(forge, "/api/forge/assay", {"material": "iron"})
    assert r.status_code == 501


def test_perks_are_the_forges_four(forge):
    """Plan §4.2: an endless Blacksmith picks from potency, hardening, quality and yield.
    The Herbalist's duration is refused; a good pick comes back as the track."""
    _level(4)
    bad = post(forge, "/api/forge/perks", {"picks": ["duration"]})
    assert bad.status_code == 400 and "duration" in bad.json()["error"]
    ok = post(forge, "/api/forge/perks", {"picks": ["hardening", "yield"]}).json()
    assert ok["perks"] == {"hardening": 1, "yield": 1} and ok["picks_banked"] == 0
    assert set(ok["perk_info"]) == {"potency", "hardening", "quality", "yield"}


def test_the_ledger_and_a_material_card(forge):
    """Contracts §7: the ledger and one card come from lane E, with what is carried and
    whether assaying it is dangerous."""
    _carry(iron=2)
    post(forge, "/api/forge/assay", {"material": "iron", "face": 15})
    led = forge.get("/api/forge/ledger").json()["ledger"]
    assert led == [{"id": "iron", "known": 2}]
    card = forge.get("/api/forge/material/iron").json()
    assert card["carried"] == 1.9 and card["assay_dc"] == 12 and card["reactive"] is False
    assert [p["known"] for p in card["properties"]][:2] == [True, True]
    assert forge.get("/api/forge/material/noqual").json()["reactive"] is True
    assert forge.get("/api/forge/material/no-such-thing").status_code == 404


def test_hostile_bodies_never_500(forge):
    """Every forge POST reads the body through `apiutil`: junk is refused in words or read
    as empty, never a traceback (the 27-body probe that found seven 500s elsewhere)."""
    for url in ("/api/forge/check", "/api/forge/roll", "/api/forge/assay",
                "/api/forge/perks", "/api/forge/finish"):
        for body in ("[1,2]", "null", "{", json.dumps({"method": "forge", "slots": [1]}),
                     json.dumps({"method": "forge", "slots": {"metal": 7}}),
                     json.dumps({"method": "alloy", "batch": "many",
                                 "slots": {"a": {"key": 5, "count": "x"}}})):
            r = forge.post(url, data=body, content_type="application/json")
            assert r.status_code < 500, (url, body, r.content[:200])
