"""Where every creature in the bestiary lives.

The measurement this whole pass came from: of the 7,188 creatures the app ships, 6,406 —
every row of the variant and NPC spreadsheet — carried no environment at all. The
Environment column exists in that file and is empty in all 6,406. So a swamp encounter
could be built from a tenth of the bestiary and the other nine tenths were unreachable.

The second measurement, which shaped the answer: a Bestiary Environment line carries two
axes at once. "warm deserts" is a climate and a terrain, and the canonical biome list holds
only one — it already mixes them, since `tundra` and `desert` are half climate while
`forest` and `mountain` are pure terrain. Climate is therefore kept as its own list and
never folded in, because folding it in would file a frost giant and a fire giant on the
same mountain.
"""
from __future__ import annotations

import json

import pytest
from django.conf import settings
from django.test import Client, override_settings

from rules import bestiary, biomes
from rules.sheet import load_pc
from tools import tag_creature_biomes as tagger


@pytest.fixture(scope="module")
def core():
    path = settings.BASE_DIR / "content" / "bestiary" / "core.json"
    return json.loads(path.read_text(encoding="utf-8"))["creatures"]


@pytest.fixture(scope="module")
def spread():
    path = settings.BASE_DIR / "content" / "bestiary" / "creatures.json"
    return json.loads(path.read_text(encoding="utf-8"))["creatures"]


# --- reading the prose ---------------------------------------------------------------

@pytest.mark.parametrize("prose,expect_biomes,expect_climates", [
    ("warm deserts", ["desert"], ["warm"]),
    ("any forests", ["forest"], []),
    ("temperate forests", ["forest"], ["temperate"]),
    ("any underground", ["underground"], []),
    ("any (Hell)", ["planar"], []),
    ("temperate marshes", ["swamp"], ["temperate"]),
    ("warm hills or mountains", ["hills", "mountain"], ["warm"]),
    # The sea, not the sand beside it. Until 2026-09-16 this read `coast`, because that
    # was the only water word the table had — so every shark, kraken and aquatic
    # elemental in the bestiary was filed on a beach. 468 creatures moved.
    ("any oceans", ["water"], []),
    ("any urban", ["urban"], []),
    ("temperate or tropical swamps", ["swamp"], ["temperate", "warm"]),
])
def test_a_line_is_read_onto_both_axes(prose, expect_biomes, expect_climates):
    env = biomes.parse_environment(prose)
    assert env.biomes == expect_biomes
    assert env.climates == expect_climates


def test_281_lines_that_produced_no_biome_at_all_now_do(core):
    """The count that started this: run over the 782 printed stat blocks, the biome matcher
    came back empty for 281 of them — every line whose only terrain word was "any", "land",
    "water" or the name of a plane the alias table spelled differently. One is left, the
    stat block whose Environment line is blank in the book."""
    empty = [c for c in core if not biomes.parse_environment(c["environment"]).biomes]
    assert len(empty) == 1
    assert empty[0]["id"] == "exoskeleton"
    assert empty[0]["environment"] == ""


def test_a_split_word_from_the_pdf_is_repaired():
    """Two stat blocks read "warm de serts" — a word the PDF extraction broke in half. It is
    the only split word in the whole Environment vocabulary, and without the repair those
    two creatures came back with no terrain and a climate on its own."""
    assert biomes.parse_environment("warm de serts").biomes == ["desert"]


def test_a_negated_climate_is_not_read_as_that_climate():
    r"""One stat block reads "any non-cold underground", and `\b` finds "cold" inside
    "non-cold" quite happily — so the creature that cannot survive the cold was filed under
    cold. Negation strips the word and leaves the other two climates."""
    env = biomes.parse_environment("any non-cold underground")
    assert env.climates == ["temperate", "warm"]
    assert env.biomes == ["underground"]


def test_cold_open_ground_is_tundra():
    """The literal string "tundra" appears in exactly one of the 782 Environment lines, and
    the canonical entry for it reads "Snowfield, ice and the far north" — which is what the
    book means by "cold plains". Translating the pair is the only way the biome survives at
    all; left alone, a search for tundra returned five creatures out of 7,188."""
    assert biomes.parse_environment("cold plains, hills, or mountains").biomes == [
        "grassland", "hills", "mountain", "tundra"]
    # A taiga is still a forest and a frozen fen is still a fen: only open ground converts.
    assert "tundra" not in biomes.parse_environment("cold forests").biomes
    assert "tundra" not in biomes.parse_environment("cold swamps").biomes


def test_any_is_expanded_and_says_that_it_was():
    """"any" and "any land" are 213 stat blocks between them. Expanding them is what lets a
    swamp query find the ghost that really can be there; the flag is what lets the same
    query put the boggard first. Without it the two were indistinguishable."""
    anywhere = biomes.parse_environment("any")
    assert anywhere.unrestricted and len(anywhere.biomes) == len(biomes.EVERYWHERE)

    land = biomes.parse_environment("any land")
    assert land.unrestricted
    assert "coast" not in land.biomes and "underground" not in land.biomes

    swamp = biomes.parse_environment("temperate marshes")
    assert not swamp.unrestricted


def test_a_narrowing_parenthesis_beats_the_any_in_front_of_it():
    """"any land (graveyards)" and "any (Plane of Fire)" both start with "any" and neither
    means anywhere. Expanding on the word alone would have put nine devils and every
    graveyard-bound undead in the open fields."""
    assert biomes.parse_environment("any land (graveyards)").biomes == ["ruins"]
    assert biomes.parse_environment("any land (Plane of Fire)").biomes == ["planar"]


def test_wilderness_is_not_a_city():
    """Two lines read "any wilderness". Land minus the places people built."""
    found = biomes.parse_environment("any wilderness").biomes
    assert "urban" not in found and "farmland" not in found and "forest" in found


# --- what the two files ended up carrying ----------------------------------------------

def test_every_creature_but_one_knows_where_it_lives(core, spread):
    """7,188 creatures, 782 of which stated an environment. The one exception is the stat
    block whose Environment line is blank in the book — it is left empty rather than given
    a default, the same way a missing AC is."""
    untagged = [c for c in core + spread if not c["biomes"]]
    assert [c["id"] for c in untagged] == ["exoskeleton"]


def test_the_stated_and_the_guessed_are_counted_separately(core, spread):
    """782 from real prose, 6,406 guessed. The flag is the same one ingredients carry and
    exists for the same reason: a guess that cannot be told from an observation is a guess
    that gets quoted back as fact."""
    stated = [c for c in core + spread if not c["biomes_inferred"]]
    guessed = [c for c in core + spread if c["biomes_inferred"]]
    assert len(stated) == 782
    assert len(guessed) == 6406
    assert all(c["biomes_from"] in ("environment", "") for c in stated)


def test_every_route_records_which_one_it_was(spread):
    """Four ways to reach a creature that never stated anything, each a weaker claim than
    the one before, so each is counted on its own rather than under one "inferred" bit.
    Measured on this import: 55 exact name matches, 754 species read out of a longer name,
    1,180 from a subtype, 465 from the creature type, and 3,952 left with nothing to read.
    """
    routes = {}
    for c in spread:
        routes[c["biomes_from"]] = routes.get(c["biomes_from"], 0) + 1
    assert routes == {"name": 55, "name-word": 754, "subtype": 1180,
                      "type": 465, "floor": 3952}


def test_the_species_in_a_name_carries_the_ecology(spread):
    """"Frost Giant Battle Priest" has no Environment line and never will; the Bestiary
    printed the frost giant on cold mountains and the species is right there in the name.
    754 rows are reached this way that would otherwise have fallen to "any land"."""
    by_id = {c["id"]: c for c in spread}
    assert by_id["frost-giant-battle-priest"]["biomes"] == ["mountain", "tundra"]
    assert by_id["frost-giant-battle-priest"]["climates"] == ["cold"]
    assert by_id["hobgoblin-archer"]["biomes"] == ["hills"]
    assert by_id["boggard-brute"]["biomes"] == ["swamp"]


def test_a_named_npc_falls_to_any_land_and_admits_it(spread):
    """3,952 rows are adventure-path people — "Nereza Rigalio, human" — with no ecology to
    read. "Any land" is the honest answer for a person and a useless one for a search, so
    it is recorded as the floor rather than as a habitat."""
    floor = [c for c in spread if c["biomes_from"] == "floor"]
    assert len(floor) == 3952
    assert all(c["biomes_any"] and c["biomes_inferred"] for c in floor)


def test_a_native_outsider_is_not_filed_off_the_material_plane(spread):
    """The outsider profile derived from core is `planar`, because 52 of the 63 core
    outsiders that name a habitat name a plane. 211 spreadsheet outsiders carry the
    `native` subtype, which means precisely the opposite, and inheriting the type would
    have sent every summoned creature and half the villains off-world."""
    natives = [c for c in spread
               if "native" in c["subtype"] and c["creature_type"] == "outsider"]
    assert len(natives) > 100
    assert all("planar" not in c["biomes"] for c in natives)


def test_a_mechanical_subtype_never_votes_on_habitat():
    """`incorporeal` describes how a creature works. Eight core incorporeal creatures name
    a habitat and four of those are coastal by accident of which four the book printed —
    a 50% profile that would have filed every ghost in the spreadsheet on a beach."""
    assert "incorporeal" in tagger.MECHANICAL_SUBTYPES
    profiles = tagger.build_profiles(
        json.loads((settings.BASE_DIR / "content" / "bestiary" / "core.json")
                   .read_text(encoding="utf-8"))["creatures"])
    assert ("sub", "incorporeal") not in profiles
    # ...while the subtypes that are about habitat still do.
    assert profiles[("sub", "aquatic")][0] == ["water"]
    assert profiles[("sub", "cold")][1] == ["cold"]


def test_a_group_that_mostly_says_any_derives_nothing():
    """52 core constructs, 47 of them "any". The five that named a habitat voted the whole
    type into swamps and planes — which put all 217 spreadsheet golems, robots and animated
    objects in a bog until the ceiling was added."""
    profiles = tagger.build_profiles(
        json.loads((settings.BASE_DIR / "content" / "bestiary" / "core.json")
                   .read_text(encoding="utf-8"))["creatures"])
    assert ("type", "construct") not in profiles


def test_the_two_files_spell_the_creature_type_differently():
    """core.json's Type column came out of a PDF split on whitespace: it says "magical"
    where the spreadsheet says "magical beast" and "monstrous" for "monstrous humanoid".
    Joining the two on the raw string drops 162 creatures and reports nothing."""
    assert tagger._CORE_TYPE_FIX["magical"] == "magical beast"
    assert tagger.core_type({"creature_type": "monstrous"}) == "monstrous humanoid"
    assert tagger.spread_type(
        {"creature_type": "advanced magical beast"}) == "magical beast"
    assert tagger.uninvert("Giant, Frost") == "frost giant"


# --- through the lookup --------------------------------------------------------------

def test_the_climate_survives_onto_the_creature():
    """Both giants live on mountains and one of them is on fire. If climate were folded
    into the biome list there would be nothing left to tell them apart."""
    frost = bestiary.details("giant-frost")
    fire = bestiary.details("giant-fire")
    assert "mountain" in frost["biomes"] and "mountain" in fire["biomes"]
    assert frost["climates"] == ["cold"] and fire["climates"] == ["warm"]


def test_searching_by_biome_narrows():
    found = bestiary.search(biome="swamp", specialists=True, limit=500)
    assert found
    assert all("swamp" in c["biomes"] and not c["biomes_any"] for c in found)


def test_an_unrestricted_creature_answers_every_biome():
    """A ghost's line reads "any". It has to come back for the swamp as well as the city,
    or the expansion was pointless."""
    ghost = bestiary.details("ghost")
    assert ghost["biomes_any"]
    for biome in ("swamp", "urban", "tundra"):
        assert biome in ghost["biomes"]


def test_specialists_are_separable_from_the_anywhere_crowd():
    """4,636 of the 7,133 the app loads are found anywhere — not of the 7,188 the two files
    hold, because 55 names are in both and the printed block wins. Asked without the filter
    a swamp answers with 4,761 of 7,133, which is two thirds of the book and therefore not
    an answer; with it, 125.
    """
    everything = bestiary.search(biome="swamp", limit=99999)
    specialists = bestiary.search(biome="swamp", specialists=True, limit=99999)
    assert len(everything) > len(bestiary.search(limit=99999)) * 0.6
    assert len(specialists) < len(everything) / 10


def test_an_empty_climate_list_means_any_climate_not_no_climate():
    """"any forests" and "temperate forests" are different claims, and the first must not
    be written as all three climates or as none. Absent means unrestricted, so a cold
    search still returns it."""
    cold = bestiary.search(biome="forest", climate="cold", limit=9999)
    assert any(not c["climates"] for c in cold)
    assert all("cold" in c["climates"] or not c["climates"] for c in cold)


def test_the_vocabularies_count_only_the_specialists():
    """Counting the "any" expansions too showed every biome with roughly the same 4,700 and
    told a reader nothing about which ground is thin."""
    v = bestiary.vocabularies()
    assert v["biomes"]["forest"] > v["biomes"]["underground"] > 0
    # No printed Environment line uses the word farmland, in any of the six Bestiaries. It
    # only ever arrives by expanding "any land", so it has no specialists to count at all.
    assert v["biomes"].get("farmland", 0) == 0
    assert set(v["climates"]) == {"cold", "temperate", "warm"}


# --- through the app -----------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_bench_no_longer_claims_the_spreadsheet_has_no_ecology(client):
    """It said the 6,406 "do not" carry Environment and stopped there, which was true and
    is now half the story — they carry biomes even though they carry no prose."""
    d = client.get("/api/bench/creatures").json()
    assert "biomes" in d["bench"]["waiting"]
