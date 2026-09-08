"""Outfitting: the starting gold spent before the sandbox.

"at the end of making your character we need a buy screen to spend starting gold, this
needs to happen before you start in the sandbox" (2026-09-07). Measured before this:
`creation.starting_purse` rolled the class's wealth into the purse and nothing let it
be spent until a stall turned up in play — and a character with Toughness began at 40
of 44 hit points, wounded before the first turn.
"""
from __future__ import annotations

import json

from play import outfit_views, roster
from rules import creation
from rules.sheet import from_dict


def _make(client, **over):
    body = {"name": "Outfit Test", "race": "human", "class": "fighter", "gender": "woman",
            "choices": ["str"],
            "abilities": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "skills": ["climb", "swim", "perception"], "feats": ["toughness", "dodge"]}
    body.update(over)
    r = client.post("/api/character/create", data=json.dumps(body),
                    content_type="application/json")
    assert r.status_code == 200, r.content
    return r.json()["id"]


def test_a_new_character_starts_whole(client):
    cid = _make(client)
    entry = roster.load(cid)
    actor = from_dict(entry.sheet, ref="pc")
    assert actor.hp == actor.hp_max
    # Toughness is on the sheet, so the maximum is above the die plus Con.
    assert actor.hp_max > creation.max_hit_die("d10") + 1


def test_the_catalogue_prices_the_tables_and_the_purse_is_the_wall(client):
    cat = outfit_views.catalogue()
    names = {w["key"] for w in cat["weapons"]}
    assert {"longsword", "dagger", "longbow"} <= names
    assert all(w["cost_gp"] > 0 for w in cat["weapons"])
    assert {a["key"] for a in cat["armour"]} >= {"leather", "chain shirt", "full plate"}
    assert any(g["key"] == "rope" and g["unit"] == "ft" for g in cat["gear"])
    cid = _make(client)
    state = client.get(f"/api/outfit/{cid}").json()
    assert state["purse_gp"] > 0 and "longsword" in state["weapons"]
    # A basket over the purse buys nothing and names the shortfall.
    r = client.post(f"/api/outfit/{cid}/buy", data=json.dumps({"buys": [
        {"kind": "armour", "key": "full plate", "count": 1}]}), content_type="application/json")
    assert r.status_code == 400 and "short" in r.json()["problems"][0]
    assert client.get(f"/api/outfit/{cid}").json()["purse_gp"] == state["purse_gp"]
    # A basket the purse covers lands on the sheet: worn, in hand, in the pack.
    r = client.post(f"/api/outfit/{cid}/buy", data=json.dumps({"buys": [
        {"kind": "weapon", "key": "dagger", "count": 1},
        {"kind": "gear", "key": "rope", "count": 1},
        {"kind": "gear", "key": "torch", "count": 3}]}), content_type="application/json")
    assert r.status_code == 200, r.content
    got = r.json()
    assert got["purse_gp"] < state["purse_gp"]
    assert got["weapons"].count("dagger") >= 1
    assert any("hemp rope" in s and s.startswith("50x") for s in got["stock"])
    assert any("torch" in s and s.startswith("3x") for s in got["stock"])
    # Unknown goods are refused by name.
    r = client.post(f"/api/outfit/{cid}/buy", data=json.dumps({"buys": [
        {"kind": "gear", "key": "dragon", "count": 1}]}), content_type="application/json")
    assert r.status_code == 400 and "dragon" in r.json()["problems"][0]


def test_bought_armour_is_worn_and_the_old_suit_goes_to_the_pack(client):
    cid = _make(client)
    state = client.get(f"/api/outfit/{cid}").json()
    assert state["armour"] == "scale mail" or state["armour"]   # the fighter's kit
    old = state["armour"]
    r = client.post(f"/api/outfit/{cid}/buy", data=json.dumps({"buys": [
        {"kind": "armour", "key": "leather", "count": 1},
        {"kind": "shield", "key": "heavy shield", "count": 1}]}), content_type="application/json")
    assert r.status_code == 200, r.content
    got = r.json()
    assert got["armour"] == "leather" and got["shield"] == "heavy shield"
    if old not in ("", "none"):
        assert any(s.endswith(x) for s in got["stock"] for x in (old, old + " armour"))


def test_the_outfit_page_carries_the_catalogue(client):
    r = client.get("/outfit/?character=nobody&world=pangrella-campaign")
    assert r.status_code == 200
    page = r.content.decode("utf-8")
    assert '"weapons"' in page and "Begin the sandbox" in page
    assert client.get("/api/outfit/nobody").status_code == 404
