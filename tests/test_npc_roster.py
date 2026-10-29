"""The app's own people and templated creatures, shipped in place of the adventures' rows.

Measured 2026-10-28 (docs/compiled-bestiary-plan.md step 4). Every person comes through
`npcs.choose`, and an inventory of its callers found 378 role-word sets (jobs, keepers,
roads, schemes, openings, backgrounds, market counters, the GM's head words). Asked at
every level 1-20 — 7,560 requests:

    store                                       to the floor   worse than today
    full (adventures loaded), before builds          4,341          —
    option D (rulebook only), before builds          5,248         919
    full, with the builds and the plural fix         3,457          —
    option D, with the builds and the plural fix     3,840         395

So the D game with these builds falls to the hand-written floor less often than the full
game did without them. What still "loses" is chiefly the trades above level 5 — a
gardener at a 10th-level party's elbow is a commoner, and the floor is the honest answer —
and a world's own prose roles ("High King's Representative" past level 12).

Land encounters were never at stake: every door that draws a creature out of the land
asks `ground_stated`, the printed Bestiary's own Environment line, and the re-read of the
Bestiaries (tests/test_bestiary_rescan.py) only widened those pools.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, npc_builds, npcs

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = json.loads((ROOT / "content" / "npc-builds" / "people.json").read_text(encoding="utf-8"))
DERIVED = json.loads((ROOT / "content" / "bestiary" / "derived.json").read_text(encoding="utf-8"))


def test_every_shipped_build_follows_the_rules():
    """272 builds for 85 roles; each one through `npc_builds.check`: counts, prerequisites,
    targets, proficiency. A build the rules refuse is a person whose numbers do not follow."""
    builds = PEOPLE["builds"]
    assert len(builds) >= 100
    bad = {b["id"]: npc_builds.check(b) for b in builds}
    assert {k: v for k, v in bad.items() if v} == {}


def test_every_build_is_in_the_store_ranked_with_the_npc_codex():
    store = bestiary.imported()
    assert all(b["id"] in store for b in PEOPLE["builds"])
    assert npcs.source_rank(npc_builds.SOURCE) == 0


def test_no_build_names_a_person_or_a_place():
    """World-agnostic: a job and nothing else. Every id is role words and a level rung."""
    for b in PEOPLE["builds"]:
        base = b["id"].rsplit("-level-", 1)[0]
        assert b["name"] == base.replace("-", " "), b["id"]
        assert b["name"].islower(), b["id"]


@pytest.mark.parametrize("words, level, want", [
    (["teamster", "carter", "driver"], 1, "teamster"),
    (["farmer"], 1, "farmer"),
    (["dockworker", "laborer", "clerk"], 2, "dockworker"),
    (["alchemist", "apothecary", "herbalist"], 4, "alchemist"),
    (["harbormaster", "sailor", "captain"], 12, "harbormaster"),
    (["thief", "rogue", "smuggler"], 9, "thief"),
])
def test_a_role_the_adventures_used_to_supply_is_ours_now(words, level, want):
    got = npcs.choose(words, level)
    assert not got["floor"] and got["id"].startswith(want), got


def test_a_plural_word_finds_its_singular():
    """"thugs", "raiders", "pirates": the GM's head words arrive plural, and the chooser
    matched a plural only on the block's side — every one fell to the floor."""
    for word, want in (("thugs", "thug"), ("raiders", "raider"), ("pirates", "pirate")):
        got = npcs.choose([word], 3)
        assert not got["floor"] and want in got["id"], (word, got)


# --- templated creatures ----------------------------------------------------------------------

def test_every_declared_templated_creature_is_built():
    """58 summonable bases (CRB Table 10-1's starred entries) celestial and fiendish, and 24
    common raised dead as zombie and skeleton: 164, every one built at load."""
    assert len(DERIVED["derived"]) == 164
    store = bestiary.imported()
    built = [v for v in store.values() if v.get("biomes_from") == "template"]
    assert len(built) == 164


def test_a_summoned_celestial_dog_is_the_rules_dog():
    """The summon effect's own example: "Summons one celestial dog for 5 rounds". A dog is
    CR 1/3, so "SR equal to new CR +5" is 5 1/3, rounded down: 5. (A printed celestial dog's
    SR could not be confirmed from a primary source; this is the template's rule as read.)"""
    block = bestiary.raw_block("celestial-dog")
    assert block["resist"] == ["acid 5", "cold 5", "electricity 5"] and block["sr"] == 5
    assert bestiary.instantiate("celestial-dog").hp_max == 6


def test_a_templated_creature_is_reached_by_name_never_drawn_from_the_land():
    assert bestiary.lookup("wolf zombie") is not None
    for biome in ("forest", "hills", "swamp"):
        assert not any(v.get("biomes_from") == "template"
                       for v in bestiary.search(biome=biome, stated=True, limit=10000))


def test_the_rules_build_replaces_an_adventures_row_of_the_same_name():
    """`ogre-zombie` was an adventure's row with 8 Hit Dice; the template gives 6."""
    block = bestiary.raw_block("ogre-zombie")
    assert block["biomes_from"] == "template" and block["hit_dice"].startswith("6d8")
