"""The caravan's raiders are people: bandits, or the world's own outlaws — never ponies.

The deferred row of the 2026-09-30 batch: in Pangrella the caravan-ambush start
(`road-caravan-attack`) drew its "raiders" `from: land` — the bestiary by the road head's
biome — and the land sent **two ponies**, side "raiders"; the prose then tried to put riders
on them. The land's draw had no notion that a caravan is robbed by people. Measured over
the land draw itself (`foes_from_the_land`, which the step used): see
`test_the_land_draw_is_what_sent_the_ponies`.

Now the step is `from: outlaws` (`rules/openings.py`): the codex by the step's own words
(bandit, raider, brigand) at the same XP budget, wearing the people of the world's own
outlaws where the world names one that raids (Pangrella's Nirkor, "Nomadic herders,
occasional raiders"), else the local people.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from play import campaign as cm
from rules import bestiary, names, openings, places
from rules.sheet import load_pc
from world.loader import load_cached

SEEDS = range(12)


def _raiders(worlds, tmp_path, seed):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign(f"raid-{seed}", seed=seed, character=load_pc("fixtures/pc-borin.json"),
                            world_source=str(worlds.source), start_id="road-caravan-attack")
    assert c.start_id == "road-caravan-attack"
    return c, [c.scene.people[r] for r in c.scene.start["foes"]]


def _humanoid(template: str) -> bool:
    row = bestiary.raw_block(template) or {}
    return str(row.get("creature_type") or "humanoid").lower() == "humanoid"


def test_the_raiders_are_humanoid_over_many_seeds(worlds, tmp_path):
    """Twelve seeds in each of the three worlds: every raider a humanoid stat block, on
    the raiders' side, with a person's face — never an animal (the ponies)."""
    kinds = set()
    for seed in SEEDS:
        c, foes = _raiders(worlds, tmp_path, seed)
        assert foes and c.scene.sides.get("raiders") == [f.ref for f in foes]
        for f in foes:
            assert _humanoid(f.from_template), (seed, f.name, f.from_template)
            assert f.appearance, (seed, f.name)
            kinds.add(f.from_template)
        assert "pony" not in {f.from_template for f in foes}
    assert kinds


def test_pangrellas_raiders_are_its_own_outlaws(tmp_path):
    """Pangrella names one people that raids — the Nirkor. Its raiders are Nirkor: the
    people recorded and the face in their name (the world ships no Nirkor body, so the
    face is the person's own details and not a Korvu's)."""
    pang = load_cached("fixtures/pangrella-campaign.json")
    nirkor = next(k for k, v in names.peoples(pang).items() if v == "Nirkor")
    for seed in (0, 3, 7):
        _, foes = _raiders(pang, tmp_path, seed)
        for f in foes:
            assert f.world_people_id == nirkor and f.heritage == "Nirkor"
            assert f.appearance.startswith("Nirkor: ") and "Korvu" not in f.appearance


def test_a_world_with_no_outlaws_robs_the_road_with_its_own_people(tmp_path):
    aur = load_cached("fixtures/aurvantis-campaign.json")
    assert openings.outlaw_people(aur, openings.rng_for(0, "x")) == ""
    _, foes = _raiders(aur, tmp_path, 1)
    for f in foes:
        assert f.world_people_id and f.heritage in names.peoples(aur).values()


def test_the_land_draw_is_what_sent_the_ponies():
    """The measurement behind the row: the land's draw on Pangrella's road heads takes
    animals — the pony among them — because `RAIDER_TYPES` holds "animal". It is kept
    for what it is (the beasts of the ground); the caravan no longer asks it."""
    pang = load_cached("fixtures/pangrella-campaign.json")
    drawn = set()
    for town in openings.towns(pang):
        spot = openings.spot_for(pang, town, openings.get("road-caravan-attack"))
        if spot is None:
            continue
        ground = str(getattr(spot, "terrain", "") or "") or places.terrain_of(spot.id)
        for seed in range(40):
            got = openings.foes_from_the_land(ground, 1, 2,
                                              openings.rng_for(seed, "foes:raiders"))
            if got:
                drawn.add((got[0]["id"], got[0].get("creature_type")))
    assert any(kind != "humanoid" for _, kind in drawn), drawn
    raiders = openings.get("road-caravan-attack")["incident"][-1]
    assert raiders["from"] == "outlaws"


def test_the_road_document_validates_and_an_unknown_source_names_the_fix():
    import copy

    doc = copy.deepcopy(openings.get("road-caravan-attack"))
    assert openings.validate(doc) == []
    doc["incident"][-1]["from"] = "sky"
    problems = openings.validate(doc)
    assert any("`outlaws`" in p for p in problems), problems
