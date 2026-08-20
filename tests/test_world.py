"""Tests for reading the World Bible export.

Run against the real shipped Pangrella export, not synthetic fixtures. Synthetic fixtures
and regex metrics have repeatedly given confident, wrong answers about quality in World
Bible; the real export carries the irregularities that have to be survived.
"""
from __future__ import annotations

import json

import pytest

from world.loader import UnsupportedSchema, load

EXPORT = "fixtures/pangrella-campaign.json"

# The home town, by id. Written as a constant precisely because its *name* is ambiguous —
# see test_names_collide_inside_a_single_world.
PANGRELLA_TOWN = "5bbd0c40345f"


@pytest.fixture(scope="module")
def world():
    return load(EXPORT)


def test_the_shipped_export_loads_with_its_documented_counts(world):
    """74 entities, 111 events, 5 routes, 5 factions, 6 unwritten — as fixtures/README
    states. If these move, the fixture was regenerated and the docs need it."""
    assert world.name == "Pangrella"
    assert len(world.entities) == 74
    assert len(world.chronology) == 111
    assert len(world.trade_routes) == 5
    assert len(world.factions) == 5
    assert len(world.unwritten) == 6


def test_a_major_schema_bump_is_refused_rather_than_guessed(tmp_path):
    """A MINOR bump adds fields we ignore; a MAJOR bump changes what existing fields
    mean. Guessing at that produces a campaign quietly keyed to the wrong thing."""
    data = json.load(open(EXPORT, encoding="utf-8"))
    data["schema_version"] = "2.0"
    p = tmp_path / "future.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(UnsupportedSchema, match="major 1"):
        load(p)


def test_a_minor_bump_still_loads(tmp_path):
    data = json.load(open(EXPORT, encoding="utf-8"))
    data["schema_version"] = "1.7"
    data["some_new_field"] = {"we": "ignore this"}
    p = tmp_path / "minor.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert load(p).name == "Pangrella"


def test_null_entity_ids_do_not_crash_a_lookup(world):
    """`entity_id` is legitimately null on a chronology figure who was never written up.
    Five events in this export are also undated. Neither is an error."""
    assert world.get(None) is None
    figures = [f for e in world.chronology for f in e.figures]
    unwritten_figures = [f for f in figures if not f.get("entity_id")]
    assert unwritten_figures, "expected the export's documented null entity_ids"
    for f in unwritten_figures[:20]:
        assert world.get(f.get("entity_id")) is None


def test_undated_events_are_present_and_have_a_null_year(world):
    undated = [e for e in world.chronology if e.year is None]
    assert len(undated) == 5


def test_role_falls_back_to_the_facts_because_the_play_layer_role_is_empty(world):
    """`play.cast[].role` is the entity summary, which in this export is the literal
    string "Person" for all 47 characters — it carries no information at all. The real
    role is a fact, and reading the play layer alone would give the GM 47 identical
    people.
    """
    cast = world.play["cast"]
    assert {c["role"] for c in cast} == {"Person"}

    roles = {world.get(c["id"]).role for c in cast if world.get(c["id"])}
    assert len(roles) > 30, f"expected varied roles from facts, got {len(roles)}"
    assert "Person" not in roles


def test_names_collide_inside_a_single_world(world):
    """The WORLD and one of its CITYs are both called "Pangrella" in the shipped export.

    A bare name lookup for the home town returns the entire world — which is how this
    was found: the opening scene of the vertical slice was set in a planet. Names are
    not identifiers even within one world, which is why every piece of campaign state is
    keyed on `id`.
    """
    both = world.all_named("Pangrella")
    assert {e.kind for e in both} == {"WORLD", "CITY"}
    assert world.by_name("Pangrella", kind="CITY").id == PANGRELLA_TOWN
    assert world.by_name("Pangrella", kind="WORLD").id != PANGRELLA_TOWN


def test_containment_is_walked_by_parent_id_not_by_path(world):
    """Renaming is supported in World Bible and rewrites folder paths. Anything that
    parsed `path` would break on the first rename; `parent_id` does not."""
    chain = [e.name for e in world.ancestors(PANGRELLA_TOWN) if e.kind != "WORLD"]
    assert chain == ["Kaldrimia", "Kaelinora"]


def test_residents_of_the_home_town_are_found_by_id(world):
    residents = world.residents(PANGRELLA_TOWN)
    assert len(residents) == 21
    assert all(r.kind == "CHARACTER" for r in residents)


def test_the_pcs_people_exists_in_the_world(world):
    """The pregenerated PC is Zhilakai, keyed by id. If a future export drops that
    people, the sheet is pointing at nothing and we want to know here."""
    pc = json.load(open("fixtures/pc-kesst.json", encoding="utf-8"))
    people = world.get(pc["world_people_id"])
    assert people is not None
    assert people.kind == "PEOPLE" and people.name == "Zhilakai"
    assert "Flightless" in people.fact("Origin")


def test_unwritten_names_are_offered_rather_than_treated_as_dead_ends(world):
    assert world.is_unwritten("Kaelvyr")
    assert not world.is_unwritten("Pangrella")
