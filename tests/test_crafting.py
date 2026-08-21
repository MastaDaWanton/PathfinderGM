"""Crafting chains, and the ingredient shelf behind them.

A craft is an ordered list of methods applied to a set of ingredients, per the Herbalist
document's own framing: "crafting is no longer limited to single-step recipes. Complex
items require Crafting Chains—combining multiple methods across different tools."

The workbench is assumed to fold out wherever the character is standing, per the design
call, so nothing here gates on location.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import crafting, ingredients
from rules.crafting import Chain
from rules.sheet import load_pc


@pytest.fixture
def shelf():
    return ingredients.all_ingredients()


# --- the shelf ----------------------------------------------------------------------------

def test_the_document_loaded(shelf):
    """160 entries out of the herbs document, read from its own bold runs rather than
    guessed from punctuation — the entries use " ", ": ", "- " and "-" as separators and
    the first twenty use nothing at all."""
    assert len(shelf) > 150
    assert "woundwort" in shelf and "phoenix-feather" in shelf


def test_monster_parts_carry_their_harvesting(shelf):
    hydra = shelf["hydra-gall"]
    assert hydra.kind == "monster part"
    assert "silver scalpel" in hydra.harvesting
    assert hydra.risky


def test_tier_is_marked_inferred(shelf):
    """The document never states a tier. It states a crafting DC on 31 entries, which is
    the only quantity in it that tracks difficulty, so tier is derived from that and
    flagged — a guessed number that looks authored is worse than no number."""
    assert shelf["tahtoalehti"].tier == "legendary"
    assert shelf["tahtoalehti"].tier_inferred
    assert all(i.tier_inferred for i in shelf.values())


def test_world_flora_is_marked_rather_than_assumed_present(shelf):
    """Whether Nura Stalk grows in this world is a World Bible question. Until the export
    carries flora, they load and say so instead of being silently assumed."""
    assert shelf["nura-stalk"].world_gated
    assert not shelf["woundwort"].world_gated


def test_a_crafter_sees_only_their_own_tier_and_below(shelf):
    low = ingredients.usable_at(1)
    assert any(i.id == "woundwort" for i in low)
    assert not any(i.id == "phoenix-feather" for i in low)


# --- chains -------------------------------------------------------------------------------

def test_a_simple_chain_previews(shelf):
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind", "brew"], ["woundwort", "comfrey"]))
    assert not r.problems
    assert r.stages == 2 and r.tier == "common"
    assert len(r.effects) == 2


def test_mix_costs_potency_and_distil_returns_it():
    """The author's percentages: mix keeps 80%, distil adds 25%, refine reaches 125%."""
    mixed = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["mix"], ["woundwort"]))
    assert mixed.potency == pytest.approx(0.80)

    both = crafting.preview("herbalist", 3,
                            Chain("herbalist", ["mix", "distill"], ["woundwort"]))
    assert both.potency == pytest.approx(1.00)


def test_purifying_removes_the_drawback():
    """"Passing a dangerous ingredient through Purify or Neutralize completely removes
    its negative side effects.\""""
    raw = crafting.preview("herbalist", 3,
                           Chain("herbalist", ["grind"], ["nightshade"]))
    assert raw.risky and raw.drawbacks

    clean = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["grind", "purify"], ["nightshade"]))
    assert not clean.risky and not clean.drawbacks


def test_a_method_you_have_not_learned_is_named_with_the_level_that_grants_it():
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["distill"], ["woundwort"]))
    assert any("Herbalist 3" in p for p in r.problems)


def test_material_above_your_tier_is_refused_by_name():
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind"], ["phoenix-feather"]))
    assert any("Phoenix Feather" in p and "legendary" in p for p in r.problems)


def test_the_result_is_as_rare_as_its_rarest_component():
    """A common chain with one legendary petal in it is a legendary brew, which is also
    what gates who can make it."""
    r = crafting.preview("herbalist", 5,
                         Chain("herbalist", ["grind"], ["woundwort", "phoenix-feather"]))
    assert r.tier == "legendary"


def test_a_finishing_method_has_to_come_last():
    """You brew the mixture; you do not grind the tea."""
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["brew", "grind"], ["woundwort"]))
    assert any("finishes a chain" in p for p in r.problems)


def test_an_empty_pot_says_so_rather_than_erroring():
    """Preview never raises for a chain that is merely bad — the page has to be able to
    grey the button and say why."""
    r = crafting.preview("herbalist", 1, Chain("herbalist", ["grind"], []))
    assert "Nothing in the pot." in r.problems
    assert r.chance == 0


def test_a_longer_chain_is_harder():
    short = crafting.preview("herbalist", 3, Chain("herbalist", ["grind"], ["woundwort"]))
    long = crafting.preview("herbalist", 3,
                            Chain("herbalist", ["grind", "mix", "purify", "brew"],
                                  ["woundwort"]))
    assert long.dc > short.dc


def test_an_authored_dc_beats_a_derived_one():
    """31 ingredients carry their own crafting DC. An authored number beats a tier
    lookup every time."""
    r = crafting.preview("herbalist", 5, Chain("herbalist", ["grind"], ["cotsbalm"]))
    assert ingredients.get("cotsbalm").craft_dc == 35
    assert r.dc == 35


def test_no_craft_is_ever_certain():
    """Clamped to 5-95 rather than allowed to reach 100: a natural 1 fails, so the number
    on the button must never claim otherwise."""
    r = crafting.preview("herbalist", 5, Chain("herbalist", ["grind"], ["barley"]))
    assert 5 <= r.chance <= 95


# --- through the page ---------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_bench_opens(client):
    assert client.get("/craft/").status_code == 200


def test_the_shelf_shows_what_is_out_of_reach_rather_than_hiding_it(client):
    """A shelf that silently hides the interesting half gives a player no reason to
    level. One showing a Phoenix Feather greyed out gives them a goal."""
    d = client.get("/api/craft/ingredients?craft=herbalism").json()
    by_id = {i["id"]: i for i in d["ingredients"]}
    assert by_id["woundwort"]["usable"]
    assert not by_id["phoenix-feather"]["usable"]
    assert by_id["phoenix-feather"]["tier"] == "legendary"


def test_a_discipline_with_no_rules_says_so(client):
    d = client.get("/api/craft/ingredients?craft=enchanting").json()
    assert d["track"]["available"] is False

    r = client.post("/api/craft/preview",
                    data=json.dumps({"craft": "enchanting", "ingredients": ["woundwort"]}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "no rules yet" in r.json()["error"]


def test_crafting_advances_the_track(client):
    r = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort", "comfrey"],
        "methods": ["grind", "brew"]}), content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["track"]["mp"] > 0
    assert 1 <= d["roll"] <= 20


def test_a_chain_that_cannot_be_made_is_refused_before_it_is_scored(client):
    """Scoring it would let a track level itself on work the character has neither the
    tools nor the methods to attempt."""
    r = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["phoenix-feather"],
        "methods": ["grind"]}), content_type="application/json")
    assert r.status_code == 400

    after = client.get("/api/craft/ingredients?craft=herbalism").json()
    assert after["track"]["mp"] == 0


def test_a_recipe_can_be_kept_and_corrected(client):
    body = {"craft": "herbalism", "name": "Wound Wash",
            "ingredients": ["woundwort"], "methods": ["grind"]}
    d = client.post("/api/craft/recipes", data=json.dumps(body),
                    content_type="application/json").json()
    assert len(d["recipes"]) == 1

    body["ingredients"] = ["woundwort", "comfrey"]
    d = client.post("/api/craft/recipes", data=json.dumps(body),
                    content_type="application/json").json()
    # Saved under a name that exists replaces it. A bench where the second save silently
    # makes a duplicate is a bench nobody can correct a recipe at.
    assert len(d["recipes"]) == 1
    assert d["recipes"][0]["ingredients"] == ["woundwort", "comfrey"]


def test_a_nameless_recipe_is_refused(client):
    r = client.post("/api/craft/recipes",
                    data=json.dumps({"ingredients": ["woundwort"]}),
                    content_type="application/json")
    assert r.status_code == 400
