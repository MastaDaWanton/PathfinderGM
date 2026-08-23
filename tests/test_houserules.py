"""House rules: the table bends 1e only where the player has said to.

Both rules exist because the user asked for them by name — tiered point buy "up to
100 points, only 1 can be active at a time", and magic effect stacking where "normal
rules say no ... it stacks from different sources (same source just reapplies)".
Every test states the half of that sentence it protects.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import creation, houserules


@pytest.fixture
def isolated(tmp_path, settings):
    """Point the rules file into a scratch directory, so tests never write the
    player's real homebrew folder and never read a toggle a previous run left on."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def spec(**over):
    base = {
        "name": "Tier Test", "race": "dwarf", "class": "fighter",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"],
        "feats": ["power attack", "weapon focus"],
    }
    base.update(over)
    return base


# --- point buy tiers ---------------------------------------------------------------------

def test_the_book_budget_is_the_default(isolated):
    assert houserules.point_budget() == 20


def test_only_a_listed_tier_can_be_active(isolated):
    """"only 1 can be active at a time" — the rule is a single number, and 37 is not
    one of the tiers, however reasonable a number it is."""
    rules, problems = houserules.set_active({"point_buy": 37})
    assert problems and "37" in problems[0]
    assert rules["point_buy"] == 20

    rules, problems = houserules.set_active({"point_buy": 100})
    assert problems == []
    assert rules["point_buy"] == 100


def test_the_forge_enforces_the_active_tier(isolated):
    """The same build that 20 points refuses, 30 accepts — one validator, one number.
    Str 18 with two 14s spends 27 (17+5+5); the shipped budget calls that 7 over."""
    rich = spec(abilities={"str": 18, "dex": 14, "con": 14, "int": 10,
                           "wis": 10, "cha": 10})
    _, problems = creation.build(rich)
    assert any("27 of 20 points" in p for p in problems)

    houserules.set_active({"point_buy": 30})
    _, problems = creation.build(rich)
    assert problems == []


def test_a_hundred_points_still_stops_at_eighteen(isolated):
    """The tier raises the budget, not the cap: six 18s cost 102, so even the full
    hundred cannot buy them — and the score wall at 18-before-race stands regardless."""
    houserules.set_active({"point_buy": 100})
    _, problems = creation.build(spec(abilities={
        "str": 18, "dex": 18, "con": 18, "int": 18, "wis": 18, "cha": 18}))
    assert any("102 of 100 points" in p for p in problems)


def test_the_wizard_payload_reads_the_active_tier(isolated):
    houserules.set_active({"point_buy": 50})
    assert creation.options()["point_budget"] == 50


def test_a_mangled_rules_file_falls_back_to_the_book(isolated):
    houserules._path().write_text("{ not json", encoding="utf-8")
    assert houserules.active() == houserules.DEFAULTS


# --- magic effect stacking ---------------------------------------------------------------

def _actor():
    from rules.sheet import from_dict

    return from_dict({"name": "Ward Test", "class": "fighter", "level": 1,
                      "abilities": {"str": 10, "dex": 10, "con": 10,
                                    "int": 10, "wis": 10, "cha": 10},
                      "hp": 10, "hp_max": 10})


def test_by_the_book_the_best_source_wins(isolated):
    a = _actor()
    a.gain_temp_hp(10, "a ward")
    a.gain_temp_hp(6, "a blessing")
    assert a.temp_hp == 10


def test_stacking_on_different_sources_add(isolated):
    houserules.set_active({"magic_stacking": True})
    a = _actor()
    a.gain_temp_hp(10, "a ward")
    a.gain_temp_hp(6, "a blessing")
    assert a.temp_hp == 16


def test_stacking_on_the_same_source_reapplies_rather_than_piling(isolated):
    """The user's own words: "same source just reapplies". Two castings of one ward
    are a renewal — 10 then 10 is 10, not 20 — which is also what keeps the toggle
    distinct from Blood Bending's `temp_hp.stacks`, where accumulation is the point."""
    houserules.set_active({"magic_stacking": True})
    a = _actor()
    a.gain_temp_hp(10, "a ward")
    a.gain_temp_hp(10, "a ward")
    assert a.temp_hp == 10
    a.gain_temp_hp(4, "a ward")
    assert a.temp_hp == 4


# --- over the wire -----------------------------------------------------------------------

@pytest.fixture
def client(isolated):
    return Client()


def test_the_rules_endpoint_round_trips(client):
    d = client.get("/api/homebrew/rules").json()
    assert d["rules"] == {"point_buy": 20, "magic_stacking": False}
    assert d["tiers"][-1]["points"] == 100

    r = client.post("/api/homebrew/rules",
                    data=json.dumps({"point_buy": 100, "magic_stacking": True}),
                    content_type="application/json")
    assert r.status_code == 200
    assert r.json()["rules"] == {"point_buy": 100, "magic_stacking": True}

    r = client.post("/api/homebrew/rules", data=json.dumps({"point_buy": 37}),
                    content_type="application/json")
    assert r.status_code == 400
    # And the refusal did not half-apply.
    assert client.get("/api/homebrew/rules").json()["rules"]["point_buy"] == 100


def test_the_rulesets_bench_is_open_for_business(client):
    """It shipped saying "not built yet" long after these toggles existed in design;
    a bench that lies about itself is the drift the front page docstring warns of."""
    from play import homebrew

    bench = homebrew.get("rulesets")
    assert bench.ready
    assert homebrew.rows_for("rulesets") == []


def test_the_forge_payload_carries_the_feat_index(isolated):
    """The forge had a type-a-feat-in field, and "Dodge" typed into it looked
    uncommitted — the counter never moved. A picker needs the list to pick from."""
    opts = creation.options()
    names = {f["name"] for f in opts["feats"]}
    assert len(opts["feats"]) > 1000
    assert len(names) == len(opts["feats"]), "every row must be tellable from the rest"
    # 148 names have a Mythic Adventures twin. Two rows both reading "Dodge" is a
    # coin flip presented as a choice, so a collided name carries its source.
    assert "Dodge (PFRPG Core)" in names and "Dodge (Mythic Adventures)" in names
    # An uncontested name stays plain. (Power Attack is not one — it too has a
    # mythic twin, which is rather the point of checking.)
    assert "Ability Focus" in names
