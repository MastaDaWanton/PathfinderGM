"""Blacksmithing: the second world class, and the proof the framework is generic.

`rules/worldclass.py` claims blacksmithing is "three more files rather than three more
code paths". These tests pin that claim: the track loads through the same generic loader
as the Herbalist, the materials load through the same shipped-plus-homebrew layering, and
every mechanical effect speaks the same `effectspec` vocabulary the rest of the app runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.conf import settings

from rules import blacksmith, effectspec
from rules import worldclass as wc
from rules.blacksmith import Chain


@pytest.fixture
def stock():
    return blacksmith.materials()


# --- the track loads through the unchanged framework --------------------------------------

def test_track_loads_through_the_generic_loader():
    """The whole point of the framework: `load_dir` reads blacksmith.json with zero code
    changes to worldclass.py. If this needs a special case, the design has failed."""
    tracks = wc.load_dir(Path(settings.BASE_DIR) / "content" / "world-classes")
    assert "blacksmith" in tracks
    track = tracks["blacksmith"]
    assert track.name == "Blacksmith"
    assert track.max_level == 5


def test_levels_gate_tiers_in_order():
    """common -> uncommon -> rare -> exotic -> legendary, one band per level, exactly the
    Herbalist's ladder. A skipped or repeated band would let a level-2 smith work
    skymetal or strand a level-4 one on rare."""
    track = wc.get("blacksmith")
    ranks = [wc.tier_rank(track.at(n).max_tier) for n in range(1, 6)]
    assert ranks == [1, 2, 3, 4, 5]


def test_methods_accumulate_and_never_expire():
    """`unlocked_methods` is cumulative: a Blacksmith 5 still smelts. All eleven methods
    exist by level 5, and the level-1 set is the minimum that can forge anything at all
    (fire, hammer, bath)."""
    track = wc.get("blacksmith")
    assert set(track.unlocked_methods(1)) == {"smelt", "forge", "quench"}
    assert len(track.unlocked_methods(5)) == 11
    for lo, hi in zip(range(1, 5), range(2, 6)):
        assert set(track.unlocked_methods(lo)) <= set(track.unlocked_methods(hi))


def test_level_5_deed_is_the_material_not_the_method():
    """Mirrors the Herbalist's legendary-catalyst lesson: gating level 5 on a level-5
    method is a gate that never opens, so the deed is working legendary *metal*, and the
    novel-alloy rule (tested below) is the level-4 path to it."""
    track = wc.get("blacksmith")
    assert track.milestones[5] == "legendary-metal"
    assert track.deeds["legendary-metal"]["min_tier"] == "legendary"
    assert track.deed_done(tier="legendary", success=True) == "legendary-metal"
    assert track.deed_done(tier="exotic", success=True) == ""


# --- the material catalogue ---------------------------------------------------------------

def _raw_entries() -> list[dict]:
    path = Path(settings.BASE_DIR) / "content" / "materials" / "blacksmith-materials.json"
    return json.loads(path.read_text(encoding="utf-8"))["materials"]


def test_every_material_id_is_unique():
    """The loader keys on id, so a duplicate would silently shadow its twin — the file
    would look complete and one entry would never exist."""
    ids = [e["id"] for e in _raw_entries()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate material ids: {sorted(dupes)}"


def test_the_catalogue_is_big_enough_and_every_tier_is_populated():
    """The brief's floor was 110 entries with all five tiers represented. Counted rather
    than eyeballed, because a tier with two entries makes that whole level of the track
    a shopping trip to nowhere."""
    entries = _raw_entries()
    assert len(entries) >= 110, f"only {len(entries)} materials"
    by_tier: dict[str, int] = {}
    for e in entries:
        by_tier[e["tier"]] = by_tier.get(e["tier"], 0) + 1
    print(f"per tier: {by_tier}")
    for tier in wc.TIERS:
        assert by_tier.get(tier, 0) >= 5, \
            f"{tier} has {by_tier.get(tier, 0)} materials: {by_tier}"


def test_every_kind_is_one_the_module_knows():
    """Eight kinds, fixed: a typo'd kind would load fine and then never count as fuel or
    metal in any validation, failing silently at the bench."""
    allowed = {"ore", "metal", "alloy", "fuel", "flux", "quenchant", "fitting",
               "treatment"}
    bad = [(e["id"], e["kind"]) for e in _raw_entries() if e["kind"] not in allowed]
    assert not bad, f"unknown kinds: {bad}"
    present = {e["kind"] for e in _raw_entries()}
    assert present == allowed, f"missing kinds: {allowed - present}"


def test_every_authored_effect_passes_the_shared_vocabulary(stock):
    """Every mechanical effect must be one `rules/effectspec.py` can validate — what the
    vocabulary cannot say stays prose with no fake spec, exactly how the creature import
    handled the same problem. An invalid spec looks authored and does nothing, which is
    the failure the effects system exists to prevent."""
    offenders = []
    for m in stock.values():
        for i, spec in enumerate(m.effects):
            problems = effectspec.validate(spec, f"{m.id} effect {i + 1}")
            offenders.extend(problems)
    assert not offenders, "invalid effects:\n" + "\n".join(offenders)


def test_the_three_famous_metals_are_not_reskins(stock):
    """Cold iron bites fey, mithral halves weight, adamantine ignores hardness and grants
    DR. If any two of them carry the same effect set, the catalogue has failed its own
    brief: no two same-tier metals should read as reskins — and these three, the ones
    every player knows, least of all."""
    rendered = {}
    for mid in ("cold-iron", "mithral", "adamantine"):
        lines = tuple(effectspec.render(e) for e in stock[mid].effects)
        assert lines, f"{mid} has no effects at all"
        rendered[mid] = lines
    assert rendered["cold-iron"] != rendered["mithral"]
    assert rendered["mithral"] != rendered["adamantine"]
    assert rendered["cold-iron"] != rendered["adamantine"]


# --- chain validation refuses before rolling ----------------------------------------------

def test_quench_before_forge_is_refused_with_a_sentence():
    """The physical grammar of the forge: you cannot quench what was never forged. The
    refusal is a sentence a player can read, not a code or a silent grey button."""
    r = blacksmith.preview(1, Chain("blacksmith", ["quench", "forge"],
                                    ["iron", "charcoal"], base="longsword"))
    assert "You cannot quench what was never forged — quench follows forge." \
        in r.problems


def test_metal_above_your_tier_is_refused_by_name():
    """Same sentence shape as the Herbalist's tier refusal, so the two benches read the
    same. Adamantine is exotic; a Blacksmith 1 works common at best."""
    r = blacksmith.preview(1, Chain("blacksmith", ["smelt", "forge", "quench"],
                                    ["adamantine", "charcoal"], base="longsword"))
    assert any("Adamantine is exotic" in p and "works common" in p
               for p in r.problems)


def test_a_cold_forge_is_refused():
    """Smelting and forging burn fuel. A chain with metal and no fuel is not a weaker
    craft, it is a smith staring at a cold hearth."""
    r = blacksmith.preview(1, Chain("blacksmith", ["smelt", "forge", "quench"],
                                    ["iron"], base="longsword"))
    assert any("The forge is cold" in p for p in r.problems)


def test_skymetal_does_not_melt_over_charcoal():
    """Exotic metal needs a rare-tier fuel: dragonfire coal exists as an entry precisely
    so that adamantine over charcoal can be a refusal rather than a house-rule."""
    cold = blacksmith.preview(5, Chain("blacksmith", ["smelt", "forge", "quench"],
                                       ["adamantine", "charcoal"], base="longsword"))
    assert any("does not melt over" in p for p in cold.problems)
    hot = blacksmith.preview(5, Chain("blacksmith", ["smelt", "forge", "quench"],
                                      ["adamantine", "dragonfire-coal"],
                                      base="longsword"))
    assert not any("does not melt over" in p for p in hot.problems)


def test_solitary_metals_refuse_the_crucible():
    """What makes cold iron cold iron does not survive being melted into something else.
    The refusal names both metals, because 'invalid alloy' teaches nothing."""
    r = blacksmith.preview(3, Chain("blacksmith", ["smelt", "alloy", "forge", "quench"],
                                    ["cold-iron", "iron", "charcoal"],
                                    base="longsword"))
    assert any("Cold Iron works alone" in p for p in r.problems)


def test_the_base_item_must_really_exist():
    """Grounded names, the lesson every model project here has paid for: the base item
    comes from the real weapons table or the armour list, never free text."""
    r = blacksmith.preview(1, Chain("blacksmith", ["smelt", "forge", "quench"],
                                    ["iron", "charcoal"], base="vorpal-zweihander"))
    assert any("No such base item" in p for p in r.problems)


# --- the quality ladder -------------------------------------------------------------------

def test_masterwork_requires_temper_shaping_and_finishing():
    """Masterwork is the book's DC-20 component made procedural: tempered steel, shaped
    past plain forging (fold or draw), and a finished edge (hone or polish). Drop the
    shaping and the same chain is merely fine; drop the finishing too and it is plain."""
    full = ["smelt", "forge", "quench", "temper", "fold", "hone"]
    r = blacksmith.preview(4, Chain("blacksmith", full,
                                    ["steel", "charcoal"], base="longsword"))
    assert r.quality == "masterwork"
    assert r.dc >= blacksmith.MASTERWORK_DC
    # PF1e's actual masterwork rule: +1 enhancement on attack rolls, never damage.
    assert {"type": "combat_mod", "amount": 1, "bonus_type": "enhancement",
            "target": "attack", "note": "(masterwork)"} in r.specs

    fine = blacksmith.preview(4, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
        ["steel", "charcoal"], base="longsword"))
    assert fine.quality == "fine"
    plain = blacksmith.preview(4, Chain(
        "blacksmith", ["smelt", "forge", "quench"],
        ["steel", "charcoal"], base="longsword"))
    assert plain.quality == "plain"


def test_a_novel_alloy_is_one_band_rarer_and_reaches_the_deed():
    """The Blacksmith 4 path to the level-5 milestone, mirroring the Herbalist's
    concentration ladder: two distinct exotic skymetals in one crucible come out
    legendary, and the ceiling is checked against the inputs, never the stepped-up
    output — gating on the output is exactly the unreachable-deed bug the Herbalist's
    _deeds_note records."""
    r = blacksmith.preview(4, Chain(
        "blacksmith", ["smelt", "alloy", "forge", "quench"],
        ["siccatite", "abysium", "dragonfire-coal"], base="longsword"))
    assert r.problems == []
    assert r.tier == "legendary"


def test_mithral_halves_weight_and_the_cost_rounds_down():
    """The rounding rule, applied where it bites: a 4 lb longsword in mithral is 2 lb,
    and weight is a cost, so it rounds down — the character is never surprised in the
    direction that hurts them."""
    r = blacksmith.preview(3, Chain("blacksmith", ["smelt", "forge", "quench"],
                                    ["mithral", "charcoal"], base="longsword"))
    assert r.weight_lb == 2
    assert blacksmith.round_cost(2.5) == 2
    assert blacksmith.round_benefit(0.8) == 1


def test_flux_cleans_the_ore_but_not_the_smith(stock):
    """Flux is to dirty ore what Purify is to a poisonous herb: bog iron's slag-brittle
    penalty is stripped, and the removal is named on the result. But it cleans the
    metal, not the smith — a chain of hazardous *metal* stays risky whatever went in
    the melt."""
    dirty = blacksmith.preview(2, Chain(
        "blacksmith", ["smelt", "forge", "quench"],
        ["bog-iron", "charcoal"], base="longsword"))
    assert any("slag-brittle" in line for line in dirty.effects)

    fluxed = blacksmith.preview(2, Chain(
        "blacksmith", ["smelt", "flux", "forge", "quench"],
        ["bog-iron", "limestone", "charcoal"], base="longsword"))
    assert not any("slag-brittle" in line for line in fluxed.effects)
    assert fluxed.removed and "impurity" in fluxed.removed[0]


def test_the_finished_piece_is_named_after_its_metal():
    """"Masterwork Cold Iron Longsword", not "Untitled" — and ore names shed the word
    "ore", because a sword smelted from cold iron ore is a cold iron sword."""
    r = blacksmith.preview(4, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper", "fold", "hone"],
        ["cold-iron", "charcoal"], base="longsword"))
    assert r.name == "Masterwork Cold Iron Longsword"


# --- homebrew layering --------------------------------------------------------------------

def test_a_homebrew_metal_dropped_in_a_file_just_works():
    """Modularity is the brief: a user drops one JSON file in homebrew/materials and the
    metal exists — loadable, forgeable, no registration step. Layered over the shipped
    set rather than replacing it, the same staleness rule `worldclass.tracks()` states."""
    home = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
    home.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": "orichalch", "name": "Orichalch", "kind": "metal", "tier": "rare",
        "craft_dc": 20, "text": "A test metal from a homebrew file.",
        "source": "mined", "biomes": ["mountain"],
        "effects": [{"type": "narrative", "target": "Gleams like sunset"}],
        "effects_converted": True,
    }
    path = home / "orichalch.json"
    path.write_text(json.dumps(entry), encoding="utf-8")
    try:
        found = blacksmith.materials(refresh=True)
        assert "orichalch" in found
        assert found["orichalch"].tier == "rare"
        # And it forges, through the same preview as shipped metal.
        r = blacksmith.preview(3, Chain("blacksmith", ["smelt", "forge", "quench"],
                                        ["orichalch", "charcoal"], base="longsword"))
        assert r.problems == []
        assert r.name == "Orichalch Longsword"
    finally:
        path.unlink(missing_ok=True)
        blacksmith.materials(refresh=True)
    assert "orichalch" not in blacksmith.materials()
