"""The enchanting circle through its API (docs/enchanting-contracts.md §6), the path the
player clicks: the Django test client on a real campaign, the real track, property table,
essence shelf, magic layer and In-progress section.

Each test names the defect it prevents. The first lane E test of the plan (§21.1) is the one
the revamp exists for: an enchantment started at the bench reaches the sheet. Measured on
master e028885, the `/craft/` tab sent the Shaping text as the item and every essence
binding came back "not masterwork": no enchantment could be made from the page at all.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import campaign as cm
from play import enchant_views
from rules import forge_items, magic_layer
from rules.sheet import load_pc

NOON = 12 * 60


def forged(rid="iron-longsword", head="iron"):
    return {"id": rid, "name": "Superior Iron Longsword", "kind": "crafted",
            "craft": "blacksmith", "count": 1, "gear": "weapon", "base": "longsword",
            "slot": "hands", "quality_index": 3, "masterwork": True,
            "pieces": {"head": {"material": head, "passes": 1},
                       "haft": {"material": "ash-haft", "passes": 0},
                       "fittings": {"material": "brass-guard", "passes": 0}},
            "quench": None, "finish": [], "flaws": [], "smith": {"level": 3, "perks": {}},
            "schema": 3}


@pytest.fixture
def circle(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        enchant_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        prog = pc.track("enchanter")
        prog.level = 4
        c.scene.clock_minutes = NOON
        c.save()
        yield Client()
        cm._LIVE.clear()
        enchant_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def _carry(**counts):
    for k, n in counts.items():
        _pc().carry(k.replace("_", "-"), n)
    cm.current().save()


def _give(rec):
    _pc().add_stock(forge_items.stock_item(rec), 1)
    cm.current().save()
    return f"stock:{rec['id']}"


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def _step(client, body, face=20, score=1.0):
    chk = post(client, "/api/enchant/check", body).json()
    assert chk["can_roll"], chk["problems"]
    r = post(client, "/api/enchant/roll", dict(body, face=face)).json()
    assert r.get("token"), r
    f = post(client, "/api/enchant/finish", {"token": r["token"], "score": score}).json()
    return chk, r, f


def test_every_enchant_route_reaches_the_circle():
    """The herb bench's measured route-order bug (2026-10-02): a fixed name read as a
    parameter answered 404. Every fixed name resolves to its own view, above the homebrew
    benches' `api/bench/<bench_id>`, and an essence card still resolves to the card."""
    for name in ("state", "check", "roll", "finish", "read", "identify", "wait", "perks",
                 "ledger", "recipes"):
        assert resolve(f"/api/enchant/{name}").func is getattr(enchant_views,
                                                                 f"enchant_{name}")
    hit = resolve("/api/enchant/essence/flaming-essence")
    assert hit.func is enchant_views.enchant_essence
    assert hit.kwargs == {"essence_id": "flaming-essence"}


def test_state_carries_the_shelf_the_locks_and_the_hour(circle):
    """Contracts §6 `state`: the shelf of what is carried, grouped; every method with its
    lock in words; where you are; the phase of the day. Refine says "Enchanter 2" at 1 and
    "Needs a sanctum" at 2 with none."""
    _carry(flaming_essence=1, white_chalk=1, silver_ink=1)
    _give(forged())
    pc = _pc()
    pc.track("enchanter").level = 1
    cm.current().save()
    d = circle.get("/api/enchant/state").json()
    assert [v["key"] for v in d["shelf"]["vessels"]] == ["stock:iron-longsword"]
    assert {e["key"] for e in d["shelf"]["essences"]} == {"inv:flaming-essence"}
    assert {x["key"] for x in d["shelf"]["circle"]} == {"inv:white-chalk", "inv:silver-ink"}
    locks = {m["id"]: m["lock_reason"] for m in d["methods"]}
    assert locks["refine"] == "Enchanter 2" and locks["prepare"] == ""
    assert locks["cleanse"] == "Enchanter 3"
    assert d["hour"]["phase"] == "noon" and d["works"] == []
    assert d["shelf"]["vessels"][0]["holds"]["words"] == "+0 of +1"


def test_a_binding_started_at_the_bench_reaches_the_sheet(circle):
    """Plan §21.1, lane E's first test: through the API, prepare, attune and bind a +1
    flaming longsword, see it wait In progress, collect it through the shared In-progress
    route once its days have passed, wield it, and read its +1 in the attack's terms."""
    from rules import inprogress

    _carry(arcane_essence_i=1, flaming_essence=1, consecrated_chalk=1, silver_ink=1)
    key = _give(forged())
    _step(circle, {"method": "prepare", "vessel": key,
                   "circle": ["inv:consecrated-chalk", "inv:silver-ink"]})
    _step(circle, {"method": "attune", "vessel": key,
                   "seats": {"point": "inv:flaming-essence", "edge": "inv:arcane-essence-i"}})
    chk, r, f = _step(circle, {"method": "bind", "vessel": key})
    assert chk["costs"]["motes"] == 40 and chk["costs"]["days"] == 8
    assert chk["lines"]["miss_big"].startswith("Miss by 5 or more")
    assert r["verdict"]["verdict"] == "success"
    assert f["work"]["ok"] and f["products"][0]["state"] == "in_progress"
    rows = circle.get("/api/works").json()["rows"]
    assert rows[0]["craft"] == "enchanter" and rows[0]["state"] == "working"
    refused = post(circle, "/api/works/collect", {"key": key[6:]})
    assert refused.status_code == 409
    c = cm.current()
    c.scene.advance(8 * 1440)
    c.save()
    got = post(circle, "/api/works/collect", {"key": key[6:]}).json()
    assert got["ok"], got
    pc = _pc()
    rec = forge_items.record_of(pc.stock[key[6:]])
    assert rec["magic"]["enhancement"] == 1 and rec["name"].startswith("+1 Flaming")
    row = pc.weapon(rec["id"])
    assert row.get("crafted_record", {}).get("magic", {}).get("enhancement") == 1
    from rules.dice import stack

    # Damage, not attack: a Superior blade's masterwork +1 is an enhancement to attack
    # already, so only the damage roll tells the layer's +1 from the smith's.
    dmg = stack(pc.damage_modifiers(rec["id"]))
    assert any(m.value == 1 and getattr(m, "type", "") == "enhancement" for m in dmg), \
        [(m.value, m.source, getattr(m, "type", "")) for m in dmg]
    plain = forge_items.stock_item(forged(rid="plain-sword"))
    pc.add_stock(plain, 1)
    assert not any(getattr(m, "type", "") == "enhancement"
                   for m in stack(pc.damage_modifiers("plain-sword")))


def test_a_flawed_binding_says_flawed_and_never_sends_the_curse(circle):
    """Owner round 4 point 2: the d20 and margin are shown and the verdict says FLAWED;
    which curse stays hidden. Every response of the flawed path is swept for the curse
    record's fields."""
    _carry(arcane_essence_i=1, flaming_essence=1, consecrated_chalk=1, silver_ink=1)
    key = _give(forged())
    _step(circle, {"method": "prepare", "vessel": key,
                   "circle": ["inv:consecrated-chalk", "inv:silver-ink"]})
    _step(circle, {"method": "attune", "vessel": key,
                   "seats": {"point": "inv:flaming-essence", "edge": "inv:arcane-essence-i"}})
    chk = post(circle, "/api/enchant/check", {"method": "bind", "vessel": key}).json()
    face = max(1, chk["dc"] - chk["bonus"] - 6)
    r = post(circle, "/api/enchant/roll", {"method": "bind", "vessel": key,
                                           "face": face}).json()
    assert r["verdict"]["verdict"] == "flawed" and r["verdict"]["word"] == "Flawed"
    f = post(circle, "/api/enchant/finish", {"token": r["token"], "score": 0.5}).json()
    seen = json.dumps([r, f, circle.get("/api/enchant/state").json(),
                       circle.get("/api/works").json()])
    assert "d100" not in seen and "pending" not in seen


def test_a_small_miss_keeps_everything_and_says_so(circle):
    """Plan §10.1: a Bind missed by 1 to 4 does not take and keeps the essences; the
    vessel stays attuned. The roll answers with the words, no token."""
    _carry(arcane_essence_i=1, consecrated_chalk=1, silver_ink=1)
    key = _give(forged())
    _step(circle, {"method": "prepare", "vessel": key,
                   "circle": ["inv:consecrated-chalk", "inv:silver-ink"]})
    _step(circle, {"method": "attune", "vessel": key,
                   "seats": {"point": "inv:arcane-essence-i"}})
    chk = post(circle, "/api/enchant/check", {"method": "bind", "vessel": key}).json()
    face = chk["dc"] - chk["bonus"] - 2
    assert 1 <= face <= 20
    r = post(circle, "/api/enchant/roll", {"method": "bind", "vessel": key,
                                           "face": face}).json()
    assert r["verdict"]["verdict"] == "failure" and "token" not in r
    assert "essences are kept" in r["said"]
    assert _pc().inventory.get("arcane-essence-i") == 1


def test_check_sends_every_number_the_working_shows(circle):
    """UI plan §12: the page never computes a number. The check carries the DC's terms,
    the face needed, the holds pips, the motes and their parts, the days, the failure lines
    and the seats with their signs and choices (bane's foe from the engine's list)."""
    _carry(arcane_essence_i=1, bane_essence=1, consecrated_chalk=1, silver_ink=1)
    key = _give(forged())
    _step(circle, {"method": "prepare", "vessel": key,
                   "circle": ["inv:consecrated-chalk", "inv:silver-ink"]})
    body = {"method": "attune", "vessel": key,
            "seats": {"point": "inv:bane-essence", "edge": "inv:arcane-essence-i"}}
    chk = post(circle, "/api/enchant/check", body).json()
    assert any("choose its foe" in p for p in chk["problems"])
    seat = next(s for s in chk["seats"] if s["seat"] == "point")
    assert "undead" in seat["choice"]["options"]
    body["choices"] = {"point": {"foe": "undead"}}
    chk = post(circle, "/api/enchant/check", body).json()
    assert chk["can_roll"], chk["problems"]
    for k in ("dc", "dc_terms", "need", "holds", "costs", "lines", "tiers", "plan"):
        assert chk[k] is not None, k
    assert chk["holds"]["words"] == "+2 of +2"
    assert chk["costs"]["words"].startswith("Costs 40 motes")


def test_wait_moves_the_clock_to_the_phase_through_the_one_door(circle):
    """Owner round 4 point 10: Wait for it advances the clock through `Scene.advance` to
    the start of the essence family's phase of the day, never by writing the clock."""
    c = cm.current()
    d = post(circle, "/api/enchant/wait", {"phase": "midnight"}).json()
    assert d["waited"] == (23 * 60) - NOON
    assert cm.current().scene.clock_minutes == 23 * 60
    assert d["words"].startswith("Midnight,")
    again = post(circle, "/api/enchant/wait", {"phase": "midnight"}).json()
    assert again["waited"] == 0
    bad = post(circle, "/api/enchant/wait", {"phase": "mars"})
    assert bad.status_code == 400
    assert c is not None


def test_read_takes_a_tenth_and_tells_one_trait(circle):
    """Plan §10: a Read is a pinch (a tenth of a phial) for one trait, and the phial is
    then 0.9, not gone and not whole."""
    _carry(flaming_essence=1)
    # Face 20: lane F's Read has a DC (10 + 5 a rarity band, 20 for a rare essence).
    d = post(circle, "/api/enchant/read", {"essence": "inv:flaming-essence",
                                           "face": 20}).json()
    assert d["revealed"] and d["pinch"]["left"] == 0.9
    ess = [e for e in d["shelf"]["essences"] if e["id"] == "flaming-essence"]
    assert ess and ess[0]["amount"] == 0.9 and ess[0]["motes"] == 27


def test_perks_are_picked_at_the_circle(circle):
    """Endless levels bank two picks each (plan §5.2); the Capacity perk is the
    enchanter's own and raises what an item holds."""
    pc = _pc()
    pc.track("enchanter").level = 4
    cm.current().save()
    d = post(circle, "/api/enchant/perks", {"picks": ["capacity", "potency"]}).json()
    assert d["perks"] == {"potency": 1, "capacity": 1}
    assert "capacity" in d["perk_info"]
    key = _give(forged())
    v = circle.get("/api/enchant/state").json()["shelf"]["vessels"][0]
    assert v["key"] == key and v["holds"]["bonus"] == 3


def test_identify_through_the_api_learns_the_intent(circle):
    """Plan §12.1: identify a found item; a good roll learns what it was made to do, and
    the card then says so."""
    rec = magic_layer.write(forged(), {"enhancement": 1},
                            binding={"quality_index": 3, "level": 4, "perks": {}}, day=1)
    rec["magic"]["known"] = {"intent": False, "curse": False, "how": "found"}
    key = _give(rec)
    d = post(circle, "/api/enchant/identify", {"item": key, "face": 20}).json()
    assert d["result"] in ("intent", "curse") and d["card"]["identified"] is True


HIDDEN = {"schema": 1, "id": "curse:opposite", "d100": 27, "row": "opposite",
          "detail": {"rolls": []}, "tags": ["curse.opposite"], "cl": 3, "gear": "weapon",
          "origin": "item:cursed-longsword", "state": {}}


def test_no_enchant_response_carries_an_unknown_curse(circle):
    """Owner round 4 point 2 and law 3: which curse an item carries is hidden until it is
    identified by 10 or shows itself. A lane F curse record (its id, row and tags) is
    planted on an item whose curse is not known, and every enchant route's answer is swept
    for any of them: state, check and roll and finish of a step on that very item, read,
    identify missed by 1 and made by 9, wait, ledger, recipes, the essence card, In
    progress."""
    rec = magic_layer.write(forged(rid="cursed-longsword"), {"enhancement": 1},
                            binding={"quality_index": 3, "level": 4, "perks": {}},
                            curse=dict(HIDDEN), day=1)
    key = _give(rec)
    _carry(flaming_essence=1, consecrated_chalk=1, silver_ink=1)
    seen = [circle.get("/api/enchant/state").json()]
    body = {"method": "prepare", "vessel": key,
            "circle": ["inv:consecrated-chalk", "inv:silver-ink"]}
    seen.append(post(circle, "/api/enchant/check", body).json())
    r = post(circle, "/api/enchant/roll", dict(body, face=20)).json()
    seen.append(r)
    seen.append(post(circle, "/api/enchant/finish", {"token": r["token"], "score": 1}).json())
    for method in ("unbind", "cleanse", "attune", "bind"):
        seen.append(post(circle, "/api/enchant/check", {"method": method,
                                                        "vessel": key}).json())
    seen.append(post(circle, "/api/enchant/read", {"essence": "inv:flaming-essence",
                                                   "face": 1}).json())
    chk = post(circle, "/api/enchant/check", {"method": "unbind", "vessel": key}).json()
    dc = 15 + 3
    bonus = chk["bonus"]
    for face in (max(1, dc - bonus - 1), min(20, dc - bonus + 9)):
        seen.append(post(circle, "/api/enchant/identify", {"item": key,
                                                           "face": face}).json())
    seen.append(post(circle, "/api/enchant/wait", {"phase": "dusk"}).json())
    for url in ("/api/enchant/ledger", "/api/enchant/recipes",
                "/api/enchant/essence/flaming-essence", "/api/works"):
        seen.append(circle.get(url).json())
    text = json.dumps(seen)
    for secret in ("curse:opposite", "curse.opposite", '"opposite"', '"d100"'):
        assert secret not in text, secret
    stored = _pc().stock["cursed-longsword"].record["magic"]
    assert stored["curse"]["id"] == "curse:opposite"      # still there, only unseen


def test_the_old_craft_chain_is_refused_in_words(circle):
    """The `/craft/` chain could not enchant (plan §1) and its methods are gone from the
    track: it is refused with the sentence that says where enchanting is done now, as
    herbalism's was."""
    from rules import benches

    with pytest.raises(benches.MovedBench) as err:
        benches.chain_from_body("enchanter", {"methods": "attune,bind"})
    assert "circle at the table" in str(err.value)
