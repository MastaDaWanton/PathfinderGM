"""Biomes, the satchel, and forage tables built from where you are standing.

Two vocabularies meet here and neither was written for the other: the World Bible export
describes places in prose ("Pangrellan grasslands, Kyropticus deserts"), and the herb
document describes habitats in prose ("grows in temperate forests", "damp, shadowy
caves"). Neither will ever say `grassland`, so both are matched into one canonical list.

Tables are assembled rather than authored. Thirteen biomes across a hundred and sixty
ingredients is two thousand hand-written rows nobody would keep current; derived from the
tags, a herb added tomorrow appears on every table it belongs to.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import biomes, foraging, ingredients
from rules.dice import Dice
from rules.sheet import from_dict, load_pc, to_dict


# --- the vocabulary -----------------------------------------------------------------------

@pytest.mark.parametrize("prose,expect", [
    ("This plant grows in alpine environments", "mountain"),
    ("found in damp, shadowy caves", "underground"),
    ("thrive in snowy tundras", "tundra"),
    ("found in haunted marshes", "swamp"),
    ("an orchid that grows on jungle vines", "jungle"),
    ("grow in open fields with plenty of sun", "grassland"),
    ("known to grow exclusively in urban areas", "urban"),
    ("found beneath ancient battlegrounds", "ruins"),
    ("originating on the Elemental Plane of Air", "planar"),
])
def test_habitat_prose_is_matched_into_the_canonical_list(prose, expect):
    assert expect in biomes.detect(prose)


def test_the_canonical_names_are_detected_too():
    """Found by tagging: matching only the alias table meant `urban` was never detected,
    because the aliases list "city" and "street" and never the word itself. Golden Maple
    Leaves, which grow exclusively in urban areas, were filed as ordinary woodland."""
    for name in biomes.BIOMES:
        assert name in biomes.detect(f"it is found in {name} country")


def test_matching_is_word_bounded():
    """Without it, "planar" is found inside "plane", "mine" inside "determine", and half
    the herb list ends up growing underground."""
    assert "underground" not in biomes.detect("we shall determine the dose")


def test_the_biome_is_read_from_the_world_not_invented(tmp_path):
    """The export carries `Biomes`, `Terrain` and `Climate`, and they live on the
    continent rather than the town — reading only the location itself would have found
    nothing for every settlement in the world."""
    from django.conf import settings
    from world.loader import load_cached

    world = load_cached(settings.WORLD_EXPORT)
    town = world.get("5bbd0c40345f")
    found = biomes.from_world(world, town)
    assert "urban" in found                     # it is a city
    assert "grassland" in found                 # Kaelinora's Biomes fact


# --- tags -----------------------------------------------------------------------------------

def test_every_ingredient_carries_biomes():
    for ing in ingredients.all_ingredients().values():
        assert ing.biomes, ing.id


def test_monster_parts_are_not_foraged():
    """They are cut off a corpse, not picked."""
    assert not ingredients.get("hydra-gall").forageable
    assert ingredients.get("woundwort").forageable


def test_a_guessed_habitat_says_so():
    """The plain herb lists give no habitat at all, so those fall back to temperate
    ground and are flagged — the same treatment tier gets, for the same reason."""
    shelf = ingredients.all_ingredients()
    inferred = [i for i in shelf.values() if i.biomes_inferred]
    stated = [i for i in shelf.values() if not i.biomes_inferred]
    assert inferred and stated
    assert not ingredients.get("frostbloom").biomes_inferred
    assert ingredients.get("frostbloom").biomes == ["tundra"]


# --- tables ---------------------------------------------------------------------------------

def test_a_table_is_built_from_what_grows_there():
    t = foraging.table_for("tundra", rank_ceiling=5)
    names = [r.name for r in t.rows]
    assert "Frostbloom" in names
    assert "Mistveil Fern" not in names          # a cave fern, not a snowfield one


def test_a_table_covers_exactly_one_to_a_hundred():
    t = foraging.table_for("forest", rank_ceiling=5)
    assert t.rows[0].low == 1
    for a, b in zip(t.rows, t.rows[1:]):
        assert b.low == a.high + 1
    assert t.nothing_from == t.rows[-1].high + 1


def test_every_candidate_gets_at_least_one_percent():
    """A rare herb in a thin biome should be findable rather than rounded out of
    existence."""
    t = foraging.table_for("forest", rank_ceiling=5)
    assert all(r.span >= 1 for r in t.rows)


def test_the_ceiling_filters_rather_than_marks():
    """Unlike the crafting shelf: you cannot recognise what you have no training to
    handle, and a table full of rows the character must discard is worse than a shorter
    honest one."""
    low = foraging.table_for("planar", rank_ceiling=1)
    high = foraging.table_for("planar", rank_ceiling=5)
    assert len(high.rows) > len(low.rows)


def test_a_biome_with_nothing_in_it_says_so_rather_than_improvising():
    t = foraging.table_for("desert", rank_ceiling=5)
    assert t.empty
    assert t.nothing_from == 1


def test_rarer_things_are_rarer_finds():
    t = foraging.table_for("forest", rank_ceiling=5)
    common = sum(r.span for r in t.rows if r.rank == 1)
    rare = sum(r.span for r in t.rows if r.rank >= 3)
    assert common > rare


def test_a_better_forager_comes_back_with_more():
    """The track's payoff outside the workbench, without the tables changing at all."""
    assert foraging.attempts_for(1) == 1
    assert foraging.attempts_for(5) == 3


def test_foraging_reports_every_roll_that_produced_it():
    got = foraging.forage("forest", level=5, rank_ceiling=5, dice=Dice(seed=7))
    assert len(got["rolls"]) == 3
    assert all(1 <= r["roll"] <= 100 for r in got["rolls"])


# --- the satchel ------------------------------------------------------------------------------

def test_carrying_and_spending():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 3)
    assert pc.inventory["woundwort"] == 3
    assert pc.spend("woundwort", 2) == 2
    assert pc.inventory["woundwort"] == 1


def test_an_emptied_pouch_leaves_the_satchel():
    """A count of nothing is something the page offers and the next preview refuses."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 1)
    pc.spend("woundwort", 5)
    assert "woundwort" not in pc.inventory


def test_the_satchel_survives_a_save():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("woundwort", 2)
    pc.carry("comfrey", 1)
    back = from_dict(to_dict(pc))
    assert back.inventory == {"woundwort": 2, "comfrey": 1}


def test_the_sheet_names_what_is_carried():
    """The sheet stores ids because that is what everything else keys on; a player should
    never be shown `adder-s-tongue`."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("adder-s-tongue", 1)
    assert pc.summary()["satchel"][0]["name"] == "Adder's-Tongue"


# --- through the app ----------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_campaign_starts_in_the_worlds_own_biome(client):
    d = client.get("/api/state").json()
    assert d["scene"]["biome"] == "urban"        # Pangrella is a city
    assert d["scene"]["biome_describe"]


def test_a_save_written_before_biomes_heals_on_read(client):
    """Healed on read rather than migrated: every campaign written before biomes existed
    has an empty one, and a save that needs a migration step to be playable is a save that
    breaks the moment somebody opens an old one."""
    from play import campaign as cm

    c = cm.current()
    c.scene.biome = ""
    assert c.biome == "urban"


def test_travelling_changes_what_grows(client):
    urban = client.get("/api/forage/table?biome=urban").json()
    forest = client.get("/api/forage/table?biome=forest").json()
    assert forest["table"]["rows"] and not urban["table"]["rows"]

    d = client.post("/api/travel", data=json.dumps({"biome": "forest"}),
                    content_type="application/json").json()
    assert d["biome"] == "forest"
    assert client.get("/api/forage/table").json()["here"] == "forest"


def test_an_invented_biome_is_refused_with_the_ones_that_exist(client):
    r = client.post("/api/travel", data=json.dumps({"biome": "the moon"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "forest" in r.json()["error"]


def test_foraging_fills_the_satchel(client):
    from play import campaign as cm

    client.post("/api/travel", data=json.dumps({"biome": "forest"}),
                content_type="application/json")
    for _ in range(8):
        client.post("/api/forage", data=json.dumps({}), content_type="application/json")
    assert cm.current().scene.pc().inventory


def test_crafting_spends_what_was_foraged(client):
    """The loop, closed: nothing can be brewed that was not first picked."""
    from play import campaign as cm

    r = client.post("/api/craft/preview", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort"], "methods": ["brew"]}),
        content_type="application/json").json()
    assert any("Forage for it" in p for p in r["problems"])

    cm.current().scene.pc().carry("woundwort", 1)
    cm.current().save()
    d = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort"], "methods": ["brew"]}),
        content_type="application/json").json()
    assert d["spent"] == {"woundwort": 1}
    assert "woundwort" not in cm.current().scene.pc().inventory
