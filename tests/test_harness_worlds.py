"""The three-world harness: every export loads, and the synthetic one differs as built.

docs/playtest-2026-09-28.md measured Aurvantis's habits — all 64 settlements `kind: CITY`
(48 of them villages or towns), all 256 `play.cast` roles "Person", "the city's leading
families" in all 64 settlements' stock sentences, no mileage-free route anywhere (132 of 132
travel rows carry `miles`). A correction tested only there can key on any of those and
pass. `fixtures/synthetic-world.json` is the third world the fix plan (fact 5) asked for;
these tests hold it to the shapes it was built to have, so nobody "tidies" it back into
Aurvantis's.
"""
from __future__ import annotations

import re

from conftest import WORLD_EXPORTS
from play import opening
from rules import journey, names, places
from world.loader import load_cached

SYNTHETIC = dict(WORLD_EXPORTS)["synthetic"]


def _settlements(world):
    return [e for e in world.entities.values()
            if e.kind in opening.SETTLEMENT_KINDS or (e.scale or "") in places.SCALES]


def test_the_fixture_is_three_worlds():
    assert [name for name, _ in WORLD_EXPORTS] == ["aurvantis", "pangrella", "synthetic"]


def test_every_world_loads_with_settlements_and_people(worlds):
    towns = _settlements(worlds)
    assert towns, f"{worlds.name}: no settlements"
    assert worlds.play.get("cast"), f"{worlds.name}: no cast"
    assert opening.starting_place(worlds) is not None
    # Every settlement gets somewhere to stand, authored or generated.
    for t in towns:
        assert places.home_set(t), f"{worlds.name}: {t.name} has no places"


def test_every_world_starts_a_campaign_and_round_trips(worlds, tmp_path):
    """The whole start path — starting place, opening company, cards, undercurrent — on
    each export, then a save and a load."""
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        c = cm.new_campaign("harness", seed=7, world_source=str(worlds.source))
        c.save()
        again = cm.Campaign.load(c.path())
    assert again.scene.location_id == c.scene.location_id
    assert again.scene.at == c.scene.at


# --- the synthetic world keeps the shapes it was built to have ---------------------------

def test_synthetic_kinds_match_their_scale():
    """Aurvantis: 64 of 64 settlements `kind: CITY`, 48 of them not cities. Here every
    settlement's kind is its own scale word, and all three scales appear."""
    world = load_cached(SYNTHETIC)
    towns = _settlements(world)
    assert len(towns) >= 6
    assert all(t.kind == (t.scale or "").upper() for t in towns), \
        [(t.name, t.kind, t.scale) for t in towns]
    assert {t.kind for t in towns} == {"VILLAGE", "TOWN", "CITY"}


def test_synthetic_stock_sentences_agree_with_scale():
    """Aurvantis: "drawn… from the city's own leading families" in all 64 settlements.
    Here a settlement calls itself by its own scale word and never another."""
    world = load_cached(SYNTHETIC)
    for t in _settlements(world):
        text = " ".join([t.summary, *t.facts.values(), t.prose]).lower()
        others = [s for s in places.SCALES if s != t.scale]
        for other in others:
            assert not re.search(rf"\bthe {other}'s\b|\bthe {other}\b", text), \
                f"{t.name} ({t.scale}) calls itself a {other}"


def test_synthetic_cast_carries_real_roles():
    """Aurvantis: 256 of 256 `play.cast[].role` are "Person". Here none is, and each row's
    role is the person's own Role fact."""
    world = load_cached(SYNTHETIC)
    cast = world.play["cast"]
    roles = {c["role"] for c in cast}
    assert "Person" not in roles
    assert {"healer", "smith", "trader"} <= roles
    for c in cast:
        assert world.get(c["id"]).fact("Role") == c["role"]


def test_synthetic_facts_use_the_alternate_keys():
    """Aurvantis keys its land as Geography/Biomes and its streets as Urban Life. The
    synthetic world uses only the alternates the code already accepts (play/opening.py
    LOOK_KEYS and LIFE_KEYS, rules/biomes.from_world), so a reader that knows one spelling
    is caught."""
    world = load_cached(SYNTHETIC)
    used = {k for e in world.entities.values() for k in e.facts}
    assert not used & {"Geography", "Biomes", "Urban Life", "Tension"}
    assert {"Terrain", "Landscape", "Daily Life"} <= used
    assert set(opening.LOOK_KEYS) & used and set(opening.LIFE_KEYS) & used


def test_synthetic_has_a_route_with_no_distance():
    """Aurvantis: 132 of 132 travel rows carry `miles` and `crosses`. Here at least one row
    carries neither, and journey still reads it (the 'derived' source)."""
    world = load_cached(SYNTHETIC)
    bare = [r for r in world.play["travel"] if "miles" not in r and "crosses" not in r]
    assert bare
    row = bare[0]
    legs = journey.legs_from(world, row["from_id"])
    leg = next(leg for leg in legs if leg.to_id == row["to_id"])
    assert leg.miles is None and leg.source == "derived" and leg.crosses == ()


def test_synthetic_has_a_port_and_a_town_with_no_cast():
    world = load_cached(SYNTHETIC)
    towns = _settlements(world)
    assert [t.name for t in towns if journey.is_port(world, t.id)] == ["Marrowby"]
    homes = {c["home_id"] for c in world.play["cast"]}
    assert [t.name for t in towns if t.id not in homes] == ["Oakhollow"]


def test_synthetic_names_come_from_the_local_people():
    """A settlement's name pool is its own people's, read off the residents' Identity."""
    world = load_cached(SYNTHETIC)
    brindle = world.by_name("Brindle Ford", kind="VILLAGE")
    marrowby = world.by_name("Marrowby", kind="TOWN")
    fenwic = world.by_name("Fenwic", kind="PEOPLE")
    carrow = world.by_name("Carrow", kind="PEOPLE")
    assert names.pool_for(world, brindle.id)["people_id"] == fenwic.id
    assert names.pool_for(world, marrowby.id)["people_id"] == carrow.id
