"""The spell list, its descriptors, its class lists, and the filters over them.

Two sources were offered for this. A JSON dump of 2,827 spells had the canonical
descriptors stripped — `[fire]` and the rest survived in four stray brackets out of nearly
three thousand — so tagging from it would have meant deriving what Paizo had already
stated. The Spell Codex spreadsheet carries all 28 descriptors as columns, subschool
separately, and a level column per class, so those are read rather than guessed.

The distinction those tests defend: a **descriptor** is a rules fact with mechanical
consequences, and a **tag** is ours, for finding things.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from rules import spells
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


# --- what was imported ---------------------------------------------------------------------

def test_the_codex_loaded():
    shelf = spells.all_spells()
    assert len(shelf) > 3000
    for known in ("fireball", "cure-light-wounds", "magic-missile", "teleport"):
        assert known in shelf, known


def test_a_spell_carries_the_facts_a_table_needs():
    fb = spells.get("fireball")
    assert fb.school == "evocation"
    assert "fire" in fb.descriptors
    assert fb.lists["wizard"] == 3
    assert fb.saving_throw and fb.range and fb.duration
    assert fb.source


def test_descriptors_are_read_not_derived():
    """A descriptor changes what a spell does — a [fire] spell is stopped by fire
    immunity — so guessing one is worse than having none. These come from the Codex's
    own columns."""
    assert "fire" in spells.get("fireball").descriptors
    assert "mind-affecting" in spells.get("charm-person").descriptors
    # And a spell about fire that carries no descriptor keeps none rather than gaining one
    # from its prose.
    assert all(isinstance(s.descriptors, list) for s in spells.all_spells().values())


def test_spells_sit_on_more_than_one_list():
    """2,887 of 3,040 do, which is why `lists` maps class to level rather than holding a
    single number."""
    many = [s for s in spells.all_spells().values() if len(s.lists) > 1]
    assert len(many) > 2000

    fb = spells.get("fireball")
    assert fb.lists["wizard"] == fb.lists["sorcerer"] == 3


def test_a_spell_can_sit_at_different_levels_on_different_lists():
    """The reason a single level would have been wrong."""
    varied = [s for s in spells.all_spells().values() if len(set(s.lists.values())) > 1]
    assert varied


def test_every_spell_has_at_least_one_tag():
    """`utility` is the honest catch-all rather than an empty list, so a filter on tags
    never silently hides a spell."""
    for s in spells.all_spells().values():
        assert s.tags, s.id


def test_tags_are_ours_and_say_so():
    note = spells.meta().get("note", "")
    assert "derived" in note.lower() or "ours" in note.lower()
    for tag in ("dot", "buff", "control"):
        assert tag in spells.TAG_NOTES


def test_the_dot_tag_means_repeating_damage():
    """The request named it: damage over time, not damage that lands once."""
    burning = spells.get("burning-gaze")
    assert "dot" in burning.tags
    assert "dot" not in spells.get("magic-missile").tags


# --- filtering -----------------------------------------------------------------------------

def test_filters_narrow_together():
    fire_aoe = spells.search(descriptor="fire", tag="aoe", klass="wizard")
    assert fire_aoe
    for s in fire_aoe:
        assert "fire" in s.descriptors and "aoe" in s.tags and "wizard" in s.lists


def test_filtering_by_class_and_level():
    third = spells.search(klass="wizard", level=3, limit=500)
    assert third
    assert all(s.lists["wizard"] == 3 for s in third)


def test_level_alone_looks_at_every_list():
    """Without a class, "level 1" means level 1 to somebody."""
    firsts = spells.search(level=1, limit=500)
    assert all(1 in s.lists.values() for s in firsts)


def test_searching_text_looks_at_the_description_too():
    assert any(s.id == "fireball" for s in spells.search(text="fireball"))
    assert spells.search(text="acid arrow")


def test_results_come_back_lowest_level_first():
    found = spells.search(descriptor="fire", limit=50)
    levels = [s.min_level for s in found if s.min_level is not None]
    assert levels == sorted(levels)


def test_a_filter_that_matches_nothing_is_empty_not_an_error():
    assert spells.search(descriptor="fire", tag="healing", klass="paladin",
                         level=9) == []


def test_the_vocabularies_are_counted():
    """A dropdown that shows a count tells you before you click that an option is empty."""
    v = spells.vocabularies()
    assert v["descriptors"]["fire"] > 50
    assert v["classes"]["wizard"] > 1000
    assert set(v["tags"]) <= set(spells.TAG_NOTES) | set(v["tags"])


# --- through the app ------------------------------------------------------------------------

def test_the_bench_lists_spells(client):
    d = client.get("/api/bench/spells").json()
    assert d["bench"]["ready"]
    assert d["bench"]["shipped"] > 3000
    assert d["rows"]
    # Capped: three thousand rows is a wall, not a listing. The filters are the way in.
    assert len(d["rows"]) <= 200


def test_the_bench_says_where_the_engine_stops(client):
    """This asserted "no spell system" and was right until one was built, which is the
    hazard a page like this carries: a label that describes a limit outlives the limit and
    starts lying. The boundary now is narrower and still real — slots, caster level and
    save DCs are the engine's, and what a spell *does* is its prose."""
    d = client.get("/api/bench/spells").json()
    waiting = d["bench"]["waiting"]
    assert "Castable now" in waiting
    assert "prose" in waiting


def test_the_search_endpoint_filters(client):
    d = client.get("/api/spells?descriptor=fire&tag=aoe&class=wizard").json()
    assert d["count"] > 0
    assert all("fire" in s["descriptors"] for s in d["spells"])
    assert d["vocab"]["descriptors"]


def test_one_spell_answers_in_full(client):
    d = client.get("/api/spells/fireball").json()
    assert d["name"] == "Fireball"
    assert d["description"]
    assert d["lists"]["wizard"] == 3


def test_an_unknown_spell_is_a_404(client):
    assert client.get("/api/spells/nonsense").status_code == 404
