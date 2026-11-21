"""Every wild draw keeps to the land's climate (playtest 2026-11-20 #20).

The road out of Branford (Kelmoria: "temperate, four clear seasons") met two pyraustas,
Bestiary 5, Environment "any warm". `gathering.draw_for`, `ontheway._the_land` and
`openings.foes_from_the_land` filtered the bestiary by ground alone; only the sea read a
climate. Research: docs/research/2026-11-21-wild-draws.md.
"""
from __future__ import annotations

import pytest

from rules import bestiary, biomes, gathering, geography, ontheway, openings
from rules.dice import Dice

WARM = {"name": "warm thing", "climates": ["warm"]}
COLD = {"name": "cold thing", "climates": ["cold"]}
ANY = {"name": "anywhere thing", "climates": []}


def test_a_warm_creature_is_not_drawn_in_temperate_land_and_an_unrestricted_one_is():
    """#20: the pyrausta's "any warm" is warm and nothing else; "any forests" is every band."""
    assert bestiary.of_the_climate([WARM, ANY], ("temperate",)) == [ANY]
    assert bestiary.of_the_climate([WARM, ANY], ("warm",)) == [WARM, ANY]
    assert bestiary.of_the_climate([WARM, COLD], ()) == [WARM, COLD]


def test_an_empty_band_borrows_only_from_next_door_never_the_far_band():
    """The book's crossover: a warm-desert behir can turn up in temperate desert, rarely in
    cold. With nothing of the land's own band, the next band; never warm in the cold."""
    assert bestiary.of_the_climate([WARM, COLD], ("temperate",)) == [WARM, COLD]
    assert bestiary.of_the_climate([WARM], ("cold",)) == []
    assert bestiary.of_the_climate([COLD], ("warm",)) == []


def test_climate_prose_reads_every_band_it_names_and_none_it_does_not():
    assert biomes.climates_in("temperate, four clear seasons") == ("temperate",)
    assert biomes.climates_in("hot days, cold nights, rare storms") == ("cold", "warm")
    assert biomes.climates_in("mild and wet, with hard westerly gales") == ()
    assert biomes.climates_in("subtropical") == ("warm",)


def test_every_settlement_reads_its_land_s_climate(worlds):
    """World-agnostic: whatever band a settlement's own land names is what its places,
    rooms and hexes under it read, through the place id."""
    for row in worlds.play["settlements"]:
        sid = row["id"]
        said = biomes.climates_in(geography.land_around(worlds, sid).climate)
        assert geography.climates_at(worlds, sid) == said
        assert geography.climates_at(worlds, f"{sid}~forest:@hex-1-1") == said


def test_branford_is_temperate():
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    assert geography.climates_at(world, "fffcb34e546e~ruins:@hex-m52-35/the-ruins") \
        == ("temperate",)


@pytest.mark.parametrize("biome", ["forest", "grassland", "farmland", "hills", "urban"])
def test_no_draw_on_temperate_ground_brings_a_creature_of_another_band(biome):
    """#20 measured on the real book: the pyrausta stands in all five of these grounds'
    windows ("any warm" expands to every land). Two hundred draws of each draw path at
    temperate: no row whose climates leave temperate out."""
    def fits(row):
        return bestiary.in_climate(row, ("temperate",))

    for seed in range(40):
        for lvl in (1, 3, 6):
            got = gathering.draw_for(biome, lvl, Dice(seed=seed), climates=("temperate",))
            assert got is None or fits(got.row), got.row["name"]
            met = ontheway._the_land(Dice(seed=seed), biome, lvl, None,
                                     climates=("temperate",))
            assert met is None or fits(met.row), met.row["name"]
    import random

    for seed in range(40):
        got = openings.foes_from_the_land(biome, 3, 3, random.Random(seed),
                                          climates=("temperate",))
        assert got is None or fits(got[0]), got[0]["name"]


def test_the_hex_road_is_handed_the_land_s_climate(worlds, monkeypatch):
    """The path #26 was on: a hex move's road check. It is handed the climate of the
    settlement the hex lies under."""
    from tests.test_hex_travel import _move, _party

    seen = []

    def road(dice, hours, *a, **k):
        seen.append(k.get("climates"))
        return None

    monkeypatch.setattr(ontheway, "road", road)
    s, e, pc = _party(worlds)
    g = e.hex_world()
    _move(e, e.hex_reach(g)[0])
    assert seen and seen[-1] == geography.climates_at(worlds, s.at)
