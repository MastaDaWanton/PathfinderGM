"""The leather bench through its API (docs/leatherworking-contracts.md §7, lane E).

Driven through the Django test client on a real campaign, on the merged lanes' real
materials and build; lane G's `places.leather_bench_here` and its two rents are patched per
test so a test can stand at the field kit or in a tannery without walking the map. Each test
names the defect it prevents.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import campaign as cm
from play import leather_views
from rules import inprogress
from rules import leatherworker as lw
from rules.sheet import load_pc


@pytest.fixture
def where(monkeypatch):
    """Lane G's door, switchable per test: "field" (the kit), "tannery" (a town tannery at
    the place the party stands, so collecting there works) or None."""
    from rules import market, places

    state = {"at": "field", "rent": [], "vat": []}

    def bench(scene, actor, known=()):
        if state["at"] == "tannery":
            here = str(getattr(actor, "at", "") or "here")
            return {"at": "tannery", "field_kit": False, "vats": True,
                    "tiers": ("common", "uncommon", "rare", "exotic", "legendary"),
                    "tannery": {"kind": "town", "place": here, "keeper": None,
                                "rate_cp_per_hour": 10, "vat_rate_cp_per_day": 20,
                                "vats": 4, "vats_free": 4, "vat_units": 4}}
        if state["at"] == "field":
            return {"at": "field", "tannery": None, "field_kit": True,
                    "tiers": ("common", "uncommon"), "vats": False}
        return {"at": None, "tannery": None, "field_kit": False, "tiers": (), "vats": False}

    def tannery_rent(scene, hours, known=()):
        state["rent"].append(hours)
        return int(round(10 * hours)) if state["at"] == "tannery" else 0

    def vat_rent(scene, days, vats=1, known=()):
        state["vat"].append((days, vats))
        import math

        return 20 * int(vats) * int(math.ceil(days)) if state["at"] == "tannery" else 0

    monkeypatch.setattr(places, "leather_bench_here", bench)
    monkeypatch.setattr(market, "tannery_rent", tannery_rent)
    monkeypatch.setattr(market, "vat_rent", vat_rent)
    return state


@pytest.fixture
def client(tmp_path, where):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        leather_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.purse = {"gp": 50}
        c.save()
        yield Client()
        cm._LIVE.clear()
        leather_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def _level(n: int):
    _pc().track("leatherworker").level = n
    cm.current().save()


def _carry(**counts):
    for iid, n in counts.items():
        _pc().carry(iid.replace("_", "-"), n)
    cm.current().save()


def _put(form, material, **kw) -> str:
    key = lw.put_hide(_pc(), lw.Hide(form=form, material=material, **kw))
    cm.current().save()
    return f"stock:{key}"


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def state(client):
    r = client.get("/api/leather/state")
    assert r.status_code == 200, r.content[:300]
    return r.json()


def rack_key(client, form, *, material=None):
    for row in state(client)["rack"]:
        if row["form"] == form and (material is None or row["material"] == material):
            return row["key"]
    raise AssertionError(f"no {form} {material or ''} on the rack")


def step(client, method, slots, score=0.6, face=20, **extra):
    body = {"method": method, "slots": slots, "face": face, **extra}
    chk = post(client, "/api/leather/check", body)
    assert chk.status_code == 200, chk.content[:300]
    assert chk.json()["can_roll"], chk.json()["problems"]
    r = post(client, "/api/leather/roll", body)
    assert r.status_code == 200, r.content[:300]
    got = r.json()
    assert got["roll"]["success"], got
    f = post(client, "/api/leather/finish", {"token": got["token"], "score": score})
    assert f.status_code == 200, f.content[:300]
    return chk.json(), got, f.json()


# --- routes and state ---------------------------------------------------------------------------

def test_every_leather_route_reaches_the_leather_views():
    """The herb bench's route-order bug (a parameter route swallowing "state",
    test_bench_routes): every fixed name sits above any catch-all."""
    for path, view in (("/api/leather/state", "leather_state"),
                       ("/api/leather/check", "leather_check"),
                       ("/api/leather/roll", "leather_roll"),
                       ("/api/leather/finish", "leather_finish"),
                       ("/api/leather/collect", "leather_collect"),
                       ("/api/leather/grade", "leather_grade"),
                       ("/api/leather/perks", "leather_perks"),
                       ("/api/leather/ask", "leather_ask"),
                       ("/api/leather/manual", "leather_manual"),
                       ("/api/leather/ledger", "leather_ledger"),
                       ("/api/leather/material/deer-hide", "leather_material")):
        assert resolve(path).func.__name__ == view, path


def test_state_carries_the_rack_with_swatches_units_and_where_you_are(client, where):
    """UI §4 and §6.2: every rack row carries its document's colour and surface, its units
    in words and its grade, so the page computes nothing; the method strip says each lock in
    words; the footer's In progress count is every craft's."""
    _carry(deer_hide=2, linen_thread=1)
    s = state(client)
    deer = next(r for r in s["rack"] if r["material"] == "deer-hide")
    assert deer["color"].startswith("#") and deer["surface"] == "smooth"
    assert (deer["units"], deer["units_words"], deer["grade"]) == (1.0, "1 unit", 2)
    assert s["where"]["line"].startswith("At the field kit")
    locks = {m["id"]: m["lock_reason"] for m in s["methods"]}
    assert locks["curry"] == "Leatherworker 2" and locks["cut"] == ""
    assert {"products", "tannages", "works", "in_progress", "slots"} <= set(s)
    assert any(p["id"] == "leather armour" and p["body_words"] == "2 units"
               for p in s["products"])
    where["at"] = None
    locks = {m["id"]: m["lock_reason"] for m in state(client)["methods"]}
    assert locks["cut"] == "Needs a field kit or a tannery"


# --- the field: a suit from bought hides to the sheet --------------------------------------------

def test_a_hide_suit_from_bought_hides_is_worn_and_reaches_the_ac(client):
    """The proof the plan asks of the bench (§13.3, Q7.1) on the field kit: bought elk and
    deer leather cut, stitched, laced and assembled into hide armour, worn, and the AC on
    the sheet moves by what the suit's row says. Measured before (Inv §0.1): a bench suit
    could not be worn at all ("not built on any suit the rules know")."""
    _carry(elk_hide=1, deer_hide=1, linen_thread=2)
    pc = _pc()
    ac_before, dex = pc.ac(), pc.ability_mod("dex")
    chk, _, done = step(client, "cut", {"hide": "inv:elk-hide"}, product="hide armour")
    assert chk["preview"]["card"]["rows"], "the build card is the server's"
    assert done["products"][0]["form"] == "panel"
    assert any(l["mp"] for l in done["mastery"]["lines"]), "every successful step pays"
    panels = rack_key(client, "panel")
    step(client, "stitch", {"piece": panels, "thread": "inv:linen-thread"})
    step(client, "cut", {"hide": "inv:deer-hide"}, product="lacing")
    body = rack_key(client, "panel")
    lacing = rack_key(client, "lacing")
    chk, _, done = step(client, "assemble", {"body": body, "fastenings": lacing})
    assert chk["dc"] == 14 and chk["masterwork"]["why"] == "the body is not curried"
    rec = done["products"][0]["record"]
    assert rec["base"] == "hide armour" and done["products"][0]["card"]
    r = post(client, "/api/wear", {"item": rec["id"]})
    assert r.status_code == 200, r.content[:300]
    pc = _pc()
    row = pc.armour_stats()
    assert pc.armour == "hide armour" and pc.armour_record()["id"] == rec["id"]
    assert pc.ac() == ac_before - 2 + row["ac"] - max(0, dex - row["max_dex"])


# --- the tannery: a tannage In progress, collected with the cut test -------------------------------

def test_a_bark_tannage_waits_in_the_vat_and_is_collected_there(client, where):
    """Plan §8: bark tanning sits in a tannery vat for weeks while the party is away, paid
    for as the hides go in (lane G: "a rent charged at collection would let a player walk
    away from the bill"); collecting early is refused with the time left; the cut test at
    collection decides the tier with the setup half. Measured before (Inv §0.5): tanning was
    instant."""
    where["at"] = "tannery"
    _level(2)
    _carry(oak_bark=1)
    pelt = _put("pelt", "deer-hide", quarters=4, grade=1)
    chk, _, done = step(client, "tan", {"hide": pelt, "tannin": "inv:oak-bark"}, score=1.0)
    assert chk["wait"]["vats"] == 1 and chk["vat_rent_cp"] > 0
    assert done["paid"] and done["paid"][0]["cp"] == chk["vat_rent_cp"]
    row = done["works"][0]
    assert row["craft"] == "leatherworker" and row["state"] == "working"
    assert "oak bark" in row["label"].lower()
    early = post(client, "/api/leather/collect", {"key": row["key"], "score": 1.0})
    assert early.status_code == 409 and "not ready" in early.json()["error"]
    c = cm.current()
    c.scene.advance(int(row["ready_in"]))
    c.save()
    got = post(client, "/api/leather/collect", {"key": row["key"], "score": 1.0})
    assert got.status_code == 200, got.content[:300]
    assert got.json()["product"]["quality"] == chk["ceiling"]
    assert any(r["form"] == "leather" and r["tannage"] == "oak-bark"
               for r in got.json()["rack"])


def test_wait_for_it_passes_the_time_through_the_one_clock_door(client, where):
    """Rawhide dries a day in the pack; "wait" stays with it until it is ready and then
    collects it (the alchemy bench's Wait for it), through `Scene.advance`."""
    pelt = _put("pelt", "deer-hide", quarters=4, grade=2)
    _, _, done = step(client, "tan", {"hide": pelt})
    key = done["works"][0]["key"]
    before = cm.current().scene.clock_minutes
    got = post(client, "/api/leather/collect", {"key": key, "wait": True})
    assert got.status_code == 200, got.content[:300]
    assert got.json()["waited"] > 0
    assert cm.current().scene.clock_minutes >= before + got.json()["waited"]


# --- the Craft rule, the score, the reservation ----------------------------------------------------

def test_a_miss_by_five_ruins_half_and_says_what(client):
    """Plan §11, the book's Craft rule. Measured (Inv §1): every input spent on any failure."""
    _carry(curing_salt=2)
    green = _put("green", "deer-hide", quarters=4, grade=2,
                 harvested_at=int(cm.current().scene.clock_minutes))
    body = {"method": "salt", "slots": {"hide": green, "salt": "inv:curing-salt"}, "face": 1}
    r = post(client, "/api/leather/roll", body)
    assert r.status_code == 200, r.content[:300]
    got = r.json()
    assert not got["roll"]["success"] and got["roll"]["margin"] <= -5
    assert got["lost"] and "ruined" in got["said"]
    assert got["mastery"]["lines"], "a failure teaches, MISHAP_LIMIT times"


def test_the_score_is_clamped_server_side(client):
    """The page sends 0..1 and the server decides what it is worth: a forged score of 7 at
    Leatherworker 1 lands on the step ceiling and no higher."""
    _carry(deer_hide=2)
    chk, _, done = step(client, "cut", {"hide": "inv:deer-hide"}, score=7,
                        product="leather armour")
    assert done["tier"] == chk["ceiling"] and done["score"] == 1.0


def test_a_lost_reservation_finishes_nothing(client):
    """A fresh GET of the state lets a step in flight go: the page has just opened, so the
    roll was abandoned, and its materials were never spent."""
    _carry(deer_hide=2)
    body = {"method": "cut", "slots": {"hide": "inv:deer-hide"}, "face": 20,
            "product": "leather armour"}
    token = post(client, "/api/leather/roll", body).json()["token"]
    state(client)
    r = post(client, "/api/leather/finish", {"token": token, "score": 0.5})
    assert r.status_code == 409
    assert _pc().inventory.get("deer-hide") == 2


# --- grade, perks, ledger, card ----------------------------------------------------------------------

def test_grade_takes_a_quarter_unit_and_pays_a_point_per_property(client):
    """Plan §16 and the owner's 2026-10-06 ruling: studying pays `STUDY_MP` (1) for each
    property found, 0 for none. A grade costs a scrap: a quarter unit off the hide, the
    rest back on the rack."""
    _carry(deer_hide=1)
    r = post(client, "/api/leather/grade", {"material": "deer-hide", "face": 20})
    assert r.status_code == 200, r.content[:300]
    got = r.json()
    assert got["success"] and got["revealed"]
    assert sum(l["mp"] for l in got["mastery"]["lines"]) == len(got["revealed"])
    left = [row for row in got["rack"] if row["material"] == "deer-hide"]
    assert left and left[0]["units"] == 0.75


def test_perks_are_the_forges_four(client):
    _level(5)
    r = post(client, "/api/leather/perks", {"picks": ["hardening", "quality"]})
    assert r.status_code == 200, r.content[:300]
    assert r.json()["perks"] == {"hardening": 1, "quality": 1}
    assert "harvest" in r.json()["perk_info"]["yield"]["next"]
    assert post(client, "/api/leather/perks", {"picks": ["duration"]}).status_code == 400


def test_the_ledger_and_a_material_card(client):
    """UI §6.7: the card carries the swatch and surface, the units carried, what grading
    costs, and the book effects this build cannot play yet."""
    _carry(deer_hide=2)
    post(client, "/api/leather/grade", {"material": "deer-hide", "face": 20})
    led = client.get("/api/leather/ledger").json()["ledger"]
    assert any(r["id"] == "deer-hide" and r["color"] for r in led)
    card = client.get("/api/leather/material/deer-hide").json()
    assert card["surface"] == "smooth" and card["carried_units"] == 1.75
    assert card["grade_cost"] == "a quarter unit of hide"
    assert client.get("/api/leather/material/no-such").status_code == 404


def test_hostile_bodies_never_500(client):
    """apiutil's measured lesson: seven of twenty-seven hostile bodies were 500s once."""
    for url in ("/api/leather/check", "/api/leather/roll", "/api/leather/finish",
                "/api/leather/collect", "/api/leather/grade", "/api/leather/perks"):
        for body in ([], "x", None, {"method": 3}, {"slots": [1]}, {"slots": {"hide": 5}},
                     {"method": "cut", "slots": {"hide": "nope"}}, {"face": "lots"},
                     {"key": {"a": 1}}, {"batch": "many", "method": "salt"}):
            r = client.post(url, data=json.dumps(body), content_type="application/json")
            assert r.status_code < 500, (url, body, r.content[:200])


# --- lane F's rows: the tanner's lesson and the manuals ------------------------------------------

def _lane_f():
    from rules import knowledge

    if not getattr(knowledge, "LEATHERWORKER", None) or not hasattr(knowledge, "read_manual"):
        pytest.skip("lane F (rules/knowledge.py LEATHERWORKER) is not merged on this tree")
    return knowledge


def test_grade_compares_a_hide_by_its_creature_type_through_lane_f(client):
    """Plan §16: Grade is lane F's `knowledge.grade` (a quarter unit, -1 DC for each known
    hide of the same creature type), called by the bench and never duplicated. Measured
    before lane F: grading a hide was the forge's assay, a tenth of a bar."""
    kn = _lane_f()
    _carry(deer_hide=1)
    r = post(client, "/api/leather/grade", {"material": "deer-hide", "face": 20})
    assert r.status_code == 200, r.content[:300]
    assert r.json()["dc"] == kn.study_dc(kn.material("deer-hide"))


def test_a_tanner_teaches_on_the_leatherworkers_rows(client, monkeypatch):
    """Lane F's finding: every leather material answered to the SMITH's rows, so a
    blacksmith taught deer hide. The leather bench asks a tanner, at the tanner's price,
    and nobody who is not one."""
    kn = _lane_f()
    from rules.bestiary import instantiate

    c = cm.current()
    tanner = instantiate("thug", scene=c.scene, name="Hollin")
    c.scene.add(tanner)
    c.save()
    assert post(client, "/api/leather/ask",
                {"material": "deer-hide", "ref": tanner.ref}).status_code == 400
    monkeypatch.setattr(kn, "teaches", lambda person, rec=None, craft=None:
                        craft == kn.LEATHERWORKER and person.name == "Hollin")
    rows = client.get("/api/leather/material/deer-hide").json()["tanners_here"]
    assert [r["name"] for r in rows] == ["Hollin"]
    r = post(client, "/api/leather/ask", {"material": "deer-hide", "ref": tanner.ref})
    assert r.status_code == 200, r.content[:300]
    price = int(kn.lore(kn.LEATHERWORKER)["teacher"]["price_cp"])
    assert r.json()["refused"] or r.json()["paid"] == leather_views._coins(price)


def test_a_leatherworking_manual_teaches_and_pays_its_mastery_once(client):
    """Plan §16-17.3: an unread leatherworking manual pays +5 once (lane F's
    `knowledge.read_manual`). Before it, only the herb bench read a manual at all."""
    kn = _lane_f()
    manual = next(iter(kn.manuals(kn.LEATHERWORKER).values()))
    _pc().goods[manual["name"]] = 1
    cm.current().save()
    first = post(client, "/api/leather/manual", {"item": manual["id"]})
    assert first.status_code == 200, first.content[:300]
    assert first.json()["first"] and first.json()["revealed"]
    assert sum(l["mp"] for l in first.json()["mastery"]["lines"]) == 5
    again = post(client, "/api/leather/manual", {"item": manual["id"]})
    assert again.status_code == 200 and not again.json()["first"]
    assert not again.json()["mastery"]["lines"]
    assert post(client, "/api/leather/manual", {"item": "no such book"}).status_code == 400


def test_an_unknown_property_row_carries_nothing_but_its_blankness(client):
    """Measured 2026-10-08 by lane U5: every unknown row on /api/leather/material went out
    with its `group`, and its key's letter (a0, t0) named the group too, so the page held
    which list a property was in before any Grade. An unknown row now says only that it
    is unknown, and the book clauses not yet in play wait until something is known."""
    card = client.get("/api/leather/material/deer-hide").json()
    blind = [p for p in card["properties"] or [] if not p.get("known")]
    assert blind, "a fresh character knows nothing of deer hide"
    for i, p in enumerate(blind):
        assert p == {"key": f"unknown-{i}", "known": False, "text": None,
                     "drawback": None, "how": None}, p
    if not any(p.get("known") for p in card["properties"]):
        assert card["not_yet"] == []
