"""The forge revamp's lanes, joined: nothing faked.

Each wave-1 lane proved its half against stand-ins for the others (lane D's bench against
echoing fakes of B, C and E; lane B's readers against hand-written records). Merged on
2026-10-04, the two halves had never met: the bench put a finished blade on the shelf as a
plain `crafting.Stock` with its build in tags, and the readers looked only for lane B's
`ForgedStock`, so the forged longsword could be assembled and then could not be drawn as
what it was. This drives the whole chain the page drives, on the real material documents,
the real build and the real readers, and then swings the result.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import forge_views
from rules import blacksmith as bs
from rules import forge_items, places
from rules.sheet import load_pc


@pytest.fixture
def forge(tmp_path, monkeypatch):
    # The kit is asked of lane G's real door; only "where am I" is pinned, so the test does
    # not depend on what the opening scene happens to stand in.
    monkeypatch.setattr(places, "has_field_kit", lambda actor: True)
    monkeypatch.setattr(places, "smithy_here", lambda scene, known=(): None)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        forge_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.track("blacksmith").level = 2
        for iid in ("iron", "charcoal", "water", "ash-haft", "brass-guard"):
            pc.carry(iid, 1)
        c.save()
        yield Client()
        cm._LIVE.clear()
        forge_views._PENDING.clear()


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def _step(client, body):
    r = _post(client, "/api/forge/roll", {**body, "face": 20})
    assert r.status_code == 200, r.content[:400]
    rolled = r.json()
    assert rolled["roll"]["success"], rolled
    f = _post(client, "/api/forge/finish", {"token": rolled["token"], "score": 1.0})
    assert f.status_code == 200, f.content[:400]
    return f.json()


def test_a_blade_forged_at_the_bench_is_drawn_and_swung_with_its_own_numbers(forge):
    blank = _step(forge, {"method": "forge", "shape": "longsword",
                          "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
                  )["products"][0]["key"]
    blank = _step(forge, {"method": "quench", "slots": {"piece": blank,
                                                        "quenchant": "inv:water"}}
                  )["products"][0]["key"]
    blank = _step(forge, {"method": "temper", "slots": {"piece": blank}})["products"][0]["key"]
    blank = _step(forge, {"method": "hone", "slots": {"piece": blank}})["products"][0]["key"]
    done = _step(forge, {"method": "assemble", "slots": {
        "head": blank, "haft": "inv:ash-haft", "fittings": "inv:brass-guard"}})
    product = done["products"][0]
    rec = product["record"]
    assert rec["masterwork"] is True and rec["gear"] == "weapon"

    # The build the page was sent is lane B's real one, computed from lane C's documents.
    build = product["build"]
    assert build and not build.get("problems"), build
    real = forge_items.build(rec)
    assert {r["target"]: r["final"] for r in real["sum"]} == \
        {r["target"]: r["final"] for r in build["sum"]}

    # Reloaded from disk, drawn through the engine's wear op, swung.
    cm._LIVE.clear()
    c = cm.current()
    pc = c.scene.pc()
    plain_attack = sum(m.value for m in pc.attack_modifiers("longsword"))
    plain_damage = sum(m.value for m in pc.damage_modifiers("longsword"))
    out = c.engine().run(c.engine().validate([{
        "op": "wear", "actor": "pc", "because": "test", "params": {"item": rec["id"]}}]))
    assert pc.equipped == rec["id"], out.outcomes[0].tell
    w = pc.weapon()
    assert w.get("crafted_record", {}).get("id") == rec["id"], w

    final = {r["target"]: r["final"] for r in real["sum"]}
    attack = sum(m.value for m in pc.attack_modifiers())
    damage = sum(m.value for m in pc.damage_modifiers())
    # Masterwork's +1 rides the attack on top of the material sum (plan §6.3).
    assert attack == plain_attack + final.get("attack", 0) + 1
    assert damage == plain_damage + final.get("damage", 0)
