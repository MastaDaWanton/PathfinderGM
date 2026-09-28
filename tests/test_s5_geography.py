"""S5: `rules/geography.py`, `residency.day_part` and `narrator_audit --world`.

docs/fix-interfaces.md §2.8 is the register these functions answer to, and §3.5 G1 the gate.
Every test that reads a world takes `worlds`, so it runs on Aurvantis, Pangrella and the
synthetic Calvessa — three exports that disagree about fact keys, kinds, cast roles and
mileage on purpose. Each docstring records what was measured before the function existed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from conftest import WORLD_EXPORTS
from rules import biomes, geography, journey, places, residency
from rules.engine import Scene
from world.loader import load_cached

AURVANTIS = dict(WORLD_EXPORTS)["aurvantis"]
PANGRELLA = dict(WORLD_EXPORTS)["pangrella"]
SYNTHETIC = dict(WORLD_EXPORTS)["synthetic"]

DIGIT = re.compile(r"\d")


def _settlements(world):
    return [world.get(row["id"]) for row in world.play.get("settlements") or []
            if world.get(row["id"]) is not None]


def _by_name(world, name):
    return next(e for e in _settlements(world) if e.name == name)


# --- G1's sharpened assertion (register §2.8, design B §5) --------------------------------

def test_vormoor_land_is_farmland_then_mountain():
    """Measured 2026-09-28: `biomes.from_world` gave Vormoor `urban, desert, grassland,
    mountain`, and the grassland was "ash-fields" read as a field. Every road out of
    Vormoor crosses farmland, then mountain. So: near is farmland and nothing else,
    beyond begins with mountain, and grassland is nowhere."""
    world = load_cached(AURVANTIS)
    vormoor = _by_name(world, "Vormoor")
    assert "grassland" in biomes.from_world(world, vormoor)   # the defect, still in biomes
    land = geography.land_around(world, vormoor)
    assert land.near == ("farmland",)
    assert land.beyond[0] == "mountain"
    assert "grassland" not in land.near + land.beyond
    assert "urban" not in land.near + land.beyond
    assert land.coast is False
    assert "stilt" in land.water                    # its own words, not a port
    assert land.climate.startswith("hot, dry")
    assert any("ash-fields" in words for _, words in land.words)
    assert land.source == "derived"


def test_vormoor_roads_three_by_road_two_by_sea_no_bearing():
    """The brief's ROADS OUT gave names only (prompts.py 926), and the narrator invented
    "north to Dustgate, west to Grotburrow" — the world has no bearings, and three of the
    five routes were never mentioned. Vormoor has three road legs and two sea legs."""
    world = load_cached(AURVANTIS)
    roads = geography.roads_out(world, _by_name(world, "Vormoor"))
    assert len(roads) == 5
    by_road = [r for r in roads if r.how == "road"]
    by_sea = [r for r in roads if r.how in ("sea", "sea-after-road")]
    assert len(by_road) == 3 and len(by_sea) == 2
    assert all(r.bearing == "" for r in roads)
    for r in by_road:
        assert r.crosses_words == "farmland, then mountain"
        assert r.leaves_from == "the outskirts"
        assert r.time_words.endswith("on foot")
    for r in by_sea:
        # Vormoor is no port: the engine's own tell is "the road to the coast, and then…".
        assert r.how == "sea-after-road"
        assert r.crosses == ()          # a sea leg's crosses describe the far shore
        assert r.time_words.endswith("aboard")


def test_roads_out_agrees_with_the_journey_the_engine_would_spend(worlds):
    """`roads_out` wraps `legs_from` + `hours_for` so the brief's days are the engine's
    days: one Road per leg, same order, same destination, and no digit anywhere a
    narrator would read (72 miles and 38 hours are both numbers it would do sums with)."""
    for town in _settlements(worlds):
        legs = journey.legs_from(worlds, town.id)
        roads = geography.roads_out(worlds, town)
        assert [r.to_id for r in roads] == [leg.to_id for leg in legs]
        for road in roads:
            for text in (road.time_words, road.crosses_words, road.leaves_from, road.to_kind):
                assert not DIGIT.search(text), (town.name, road)
            assert road.how in ("road", "river", "sea", "sea-after-road", "")
            assert road.source in ("exact", "derived")


def test_the_mileage_free_leg_invents_no_road_facts():
    """The synthetic Oakhollow–Brindle Ford row carries nothing but its endpoints: no
    `by`, no `miles`, no `crosses`. Everything a narrator could repeat as fact about that
    road must be empty or say that nobody wrote it down."""
    world = load_cached(SYNTHETIC)
    row = next(r for r in world.play["travel"]
               if not r.get("by") and not r.get("miles") and not r.get("crosses"))
    here, there = row["from_id"], row["to_id"]
    road = next(r for r in geography.roads_out(world, here) if r.to_id == there)
    assert road.how == ""                     # "by road" would be invented
    assert road.crosses == () and road.crosses_words == ""
    assert road.bearing == ""
    assert road.time_words == geography.UNWRITTEN_DISTANCE
    assert road.source == "derived"
    back = next(r for r in geography.roads_out(world, there) if r.to_id == here)
    assert back.how == "" and back.crosses == () and back.time_words == road.time_words


def test_pangrella_falls_back_to_prose():
    """Design B §5: Pangrella's town has a single sea leg, so no road gives it near
    ground; its Land comes from its nation's Region and its continent's prose."""
    world = load_cached(PANGRELLA)
    town = _by_name(world, "Pangrella")
    roads = geography.roads_out(world, town)
    assert [r.how for r in roads] == ["sea-after-road"]
    land = geography.land_around(world, town)
    assert land.near == ()
    assert {"grassland", "desert", "mountain"} <= set(land.beyond)
    assert land.source == "derived"


def test_every_land_is_well_formed(worlds):
    """Near and beyond are biome words, disjoint, never urban; the world's words come
    back unedited; the source is one of the three honest answers."""
    for town in _settlements(worlds):
        land = geography.land_around(worlds, town)
        assert land.settlement_id == town.id
        assert set(land.near) <= set(biomes.BIOMES) and set(land.beyond) <= set(biomes.BIOMES)
        assert not set(land.near) & set(land.beyond)
        assert "urban" not in land.near + land.beyond
        assert land.source in ("exact", "derived", "unknown")
        for whose, words in land.words:
            assert whose and words
        # Sea legs never feed the ground: their `crosses` is the far shore.
        for leg in journey.legs_from(worlds, town.id):
            if leg.by_sea and leg.by != "river":
                continue
            if leg.crosses:
                assert biomes.canonical(leg.crosses[0]) in land.near


def test_grounded_three_ways():
    """Playtest item 20.2: `travel biome=forest` was accepted unchecked outside Vormoor,
    whose roads cross farmland then mountain. Absent ground is named as absent, with what
    IS there; a world that says nothing is `unknown`, never refused on a guess."""
    world = load_cached(AURVANTIS)
    land = geography.land_around(world, _by_name(world, "Vormoor"))
    assert geography.grounded(land, "farmland") == ("near", "")
    assert geography.grounded(land, "mountain") == ("beyond", "")
    got, words = geography.grounded(land, "forest")
    assert got == "absent"
    assert "forest" in words and "farmland" in words and "mountain" in words
    assert not DIGIT.search(words)
    assert geography.grounded(land, "water")[0] == "near"     # stilts over the water
    assert geography.grounded(land, "no such ground")[0] == "unknown"
    nothing = geography.Land("x", (), (), (), "", "", False, "unknown")
    assert geography.grounded(nothing, "forest") == ("unknown", "")


def test_stated_export_fields_beat_the_derivation(tmp_path):
    """docs/from-world-bible.md asks for `near`, `water`, `bearing` and `leaves_by`. No
    export ships them yet, so a copy of the synthetic world is given them here: stated
    ground replaces the derived, a bearing is read (and reversed walking the row the other
    way), and an unrecognised bearing is dropped rather than guessed at."""
    import json

    from world.loader import load

    doc = json.loads(Path(SYNTHETIC).read_text(encoding="utf-8"))
    brindle = next(r for r in doc["play"]["settlements"] if r["name"] == "Brindle Ford")
    brindle["near"] = ["pasture", "hills"]
    brindle["water"] = "river"
    first = places.home_set(load_cached(SYNTHETIC).get(brindle["id"]))[0]
    for row in doc["play"]["travel"]:
        if row["from"] == "Brindle Ford" and row["to"] == "Kestwick":
            row["bearing"] = "NE"
            row["leaves_by"] = first.id
        if row["from"] == "Oakhollow":
            row["bearing"] = "up the hill"
    path = tmp_path / "stated.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    world = load(path)

    land = geography.land_around(world, brindle["id"])
    assert land.near == ("farmland", "hills")
    assert land.source == "exact" and land.coast is False
    assert geography.grounded(land, "water")[0] == "near"
    out = {r.to_name: r for r in geography.roads_out(world, brindle["id"])}
    assert out["Kestwick"].bearing == "north-east"
    assert out["Kestwick"].leaves_from == first.name
    assert out["Oakhollow"].bearing == ""
    back = {r.to_name: r for r in geography.roads_out(world, out["Kestwick"].to_id)}
    assert back["Brindle Ford"].bearing == "south-west"
    assert back["Brindle Ford"].leaves_from == "the outskirts"


# --- the compound-aware ground matcher (register §1.3 B4) ---------------------------------

def test_ash_fields_are_not_grassland_and_plurals_still_match():
    """`biomes.detect("ash-fields")` returns `['grassland']`: `\\bfield` matches after the
    hyphen. The first proposed fix, a trailing `\\b`, would have broken every plural
    ("canyons", "mountains", "fields"), and `s?\\b` lets "ash-fields" back in. The
    compound-aware matcher refuses a hyphen before the word and allows the inflection."""
    assert biomes.detect("ash-fields") == ["grassland"]          # the measured defect
    assert geography.ground_in("ash-fields") == ()
    assert geography.ground_in("ash-fields, iron-rich badlands, geothermal vents") == ("desert",)
    assert geography.ground_in("open fields") == ("grassland",)
    assert geography.ground_in("fields") == ("grassland",)
    assert geography.ground_in("mountains") == ("mountain",)
    assert geography.ground_in("salt marshes") == ("swamp",)
    assert geography.ground_in("a steep wooded combe") == ("forest",)
    assert geography.ground_in("chalk downs") == ("hills",)
    # Order is the prose's, nearest first as the world wrote it.
    assert geography.ground_in("farmland, then mountain") == ("farmland", "mountain")
    # The tail admits inflections only: "mineral" is not a mine, "streams running down
    # to the sea" are not the downs.
    assert "underground" not in geography.ground_in("mineral springs")
    assert "hills" not in geography.ground_in("streams running down to the sea")


def test_no_drossakar_settlement_reads_grassland_from_ash(worlds):
    """Across every world, grassland reaches a Land only from a route's own `crosses` or
    from a word that is really grass — never from a compound like "ash-fields"."""
    grass = re.compile(r"(?<![\w-])(grass|plain|meadow|steppe|prairie|savanna|veldt|"
                       r"lowland|open field|field)")
    for town in _settlements(worlds):
        land = geography.land_around(worlds, town)
        if "grassland" not in land.near + land.beyond:
            continue
        crossed = {c for leg in journey.legs_from(worlds, town.id) for c in leg.crosses}
        prose = " ".join(words for _, words in land.words).lower()
        assert "grassland" in crossed or grass.search(prose), town.name


# --- where -------------------------------------------------------------------------------

def _panel(location, biome):
    """Today's panel line, as `02-state.js:216` composes it from `/api/state`'s scene:
    `${location}${scale ? " · " + scale : ""}` then ` · ${biome}`."""
    name = location.name if location else ""
    scale = places.scale_of(location) if location else ""
    return (name + (f" · {scale}" if scale else "")), biome


def test_where_is_todays_panel_for_every_settlements_first_place(worlds):
    """Phase 1 must change nothing the player sees: S3 routes `/api/state` through
    `where()`, so for every settlement's first place its label and detail equal today's
    panel text exactly, and the setting is `in` on urban ground."""
    for town in _settlements(worlds):
        first = places.home_set(town)[0]
        scene = Scene(location_id=town.id, at=first.id)
        got = geography.where(worlds, scene, first)
        label, detail = _panel(town, scene.biome)
        assert (got.label, got.detail) == (label, detail), town.name
        assert got.setting == ("in" if scene.biome == "urban" else "outside")


def test_where_matches_the_live_state_of_a_new_campaign(worlds, tmp_path):
    """The same through the real path: a fresh campaign's `/api/state` scene keys."""
    from django.test import override_settings

    from play import campaign as cm
    from play import views

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        c = cm.new_campaign("s5-where", seed=5, world_source=str(worlds.source))
        state = views._state(c)["scene"]
    got = geography.where(c.world, c.scene)
    want = state["location"] + (f" · {state['scale']}" if state["scale"] else "")
    assert got.label == want
    assert got.detail == state["biome"]


def test_where_outside_town_is_still_todays_label():
    """Bobby stood at `bde94b038cba~forest:the-approach` under the label "Vormoor ·
    village · forest". Phase 1 keeps that (Lane B changes it); only `setting` says
    outside."""
    world = load_cached(AURVANTIS)
    scene = Scene(location_id="bde94b038cba", at="bde94b038cba~forest:the-approach")
    got = geography.where(world, scene)
    assert got == geography.Where("outside", "Vormoor · village", "forest")


def test_walk_words_are_words():
    """Item 16.5: a walk across town cost nothing and said nothing. The minutes become
    words for the tell, never a count."""
    assert geography.walk_words(0) == ""
    assert geography.walk_words(4) == "a few minutes' walk"
    assert geography.walk_words(15) == "a quarter of an hour"
    assert geography.walk_words(50) == "the better part of an hour"
    assert geography.walk_words(60) == "about an hour"
    assert geography.walk_words(240) == "about four hours"
    for m in range(0, 2000, 7):
        assert not DIGIT.search(geography.walk_words(m)), m


# --- Lane C's three ----------------------------------------------------------------------

def test_role_of_reads_the_person_not_the_cast_list(worlds):
    """Every Aurvantis and Pangrella `play.cast[].role` is "Person" (256 and 47 of them);
    their entities say "Role: healer". `_role_for` matched nobody and handed every
    campaign Drenn Ironvale. `role_of` never returns the placeholder."""
    for row in worlds.play.get("cast") or []:
        got = geography.role_of(worlds, row)
        assert got.lower() not in geography.GENERIC_ROLES or got == ""
        entity = worlds.get(row["id"])
        if entity is not None and entity.facts.get("Role"):
            assert got == entity.facts["Role"].strip()


def test_drenn_ironvale_is_a_healer():
    """Playtest item 8: Drenn's cast row says `role: "Person"`; his entity says healer."""
    world = load_cached(AURVANTIS)
    row = next(r for r in world.play["cast"]
               if r["name"] == "Drenn Ironvale" and r.get("home") == "Vormoor")
    assert row["role"] == "Person"
    assert geography.role_of(world, row) == "healer"
    # A row with no entity and a placeholder role says nothing; a real role is kept.
    assert geography.role_of(world, {"id": "nobody", "role": "Person"}) == ""
    assert geography.role_of(world, {"id": "nobody", "role": "ferryman"}) == "ferryman"


def test_in_its_own_words_puts_the_scale_back():
    """Playtest item 1: all 64 Aurvantis settlements say "the city's own leading
    families", 48 of them not cities, and the opening called Vormoor, a village, "the
    city's bustling thoroughfares". "the city of X" is another place and is kept."""
    text = "drawn, by long custom, from the city's own leading families"
    assert geography.in_its_own_words(text, "village") == \
        "drawn, by long custom, from the village's own leading families"
    assert geography.in_its_own_words("The city sleeps.", "town") == "The town sleeps."
    kept = "the city of Ledgerwarren sent ships"
    assert geography.in_its_own_words(kept, "village") == kept
    assert geography.in_its_own_words("the City Watch", "village") == "the City Watch"
    assert geography.in_its_own_words(text, "city") == text
    assert geography.in_its_own_words(text, "") == text


def test_no_non_city_calls_itself_the_city_after_the_rewrite(worlds):
    """Measured: 96 + 12 occurrences in Aurvantis non-cities, 16 + 7 in Pangrella's
    towns. After the rewrite, none — and the synthetic world, already right, is
    unchanged."""
    city = re.compile(r"\bthe city\b(?!\s+of\b)(?!-)")
    before = after = 0
    for town in _settlements(worlds):
        scale = places.scale_of(town)
        for text in [town.summary, town.prose, *town.facts.values()]:
            before += len(city.findall(text or "")) if scale != "city" else 0
            rewritten = geography.in_its_own_words(text or "", scale)
            if scale == "city":
                assert rewritten == (text or "")
            else:
                after += len(city.findall(rewritten))
    assert after == 0
    if worlds.name == "Aurvantis":
        assert before > 0


def test_display_key():
    """"Urban Life" is the same stock-template defect on a village, one level up."""
    assert geography.display_key("Urban Life") == "Daily life"
    assert geography.display_key("urban  life") == "Daily life"
    assert geography.display_key("Social Classes") == "Social Classes"
    assert geography.display_key("Daily Life") == "Daily Life"
    assert geography.display_key("") == ""


# --- residency.day_part (register §2.9) --------------------------------------------------

def test_day_part_is_the_part_time_words_names():
    """One composer for the hour's words: `day_part` is exactly the part `time_words`
    already puts in the brief, for every slot of a day and past midnight."""
    for clock in range(0, 3 * residency.DAY, 30):
        part = residency.day_part(clock)
        assert part in residency._PARTS
        assert f", {part} (" in residency.time_words(clock)
    assert residency.day_part(0) == "deep in the night"
    assert residency.day_part(12 * 60) == "midday"


# --- narrator_audit --world (R0-5) --------------------------------------------------------

@pytest.mark.parametrize("which", ["pangrella", "synthetic", ""])
def test_audit_starts_in_the_world_it_was_given(which, tmp_path, monkeypatch):
    """R0-5: `--world` was parsed and passed to `audit()`, which ignored it — every
    run began in the shipped default. Zero turns, so no model is asked; the campaign it
    starts is the measurement."""
    from django.conf import settings

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from play import campaign as cm
    from tools import narrator_audit as audit

    monkeypatch.setenv("TEMP", str(tmp_path))
    started: list[str] = []
    real = cm.begin_with

    def spy(character, world_source=None):
        c = real(character, world_source=world_source)
        started.append(c.world.name)
        return c

    monkeypatch.setattr(cm, "begin_with", spy)
    source = dict(WORLD_EXPORTS)[which] if which else ""
    result = audit.audit(0, "town", source, "fixtures/pc-kesst.json")
    assert result["turns"] == 0
    want = load_cached(source or settings.WORLD_EXPORT).name
    assert started == [want]
