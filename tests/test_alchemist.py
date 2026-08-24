"""Alchemy: the second world class, and the proof the framework is generic.

The Alchemist loads through the same `rules/worldclass.py` the Herbalist does — no new
code path, one more JSON file, which was the framework's stated design goal. The chain
rules live in `rules/alchemist.py` and deliberately mirror `rules/crafting.py`'s surface
so a later dispatcher can route by track without learning two vocabularies.

Namespace pin: "alchemist" the world class and "Alchemist" the PF1e character class in
content/classes/ are separate namespaces (rules.worldclass.get vs rules.classes.get).
Nothing here touches the character class.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import alchemist as alch
from rules import effectspec
from rules import worldclass as wc

CATALOGUE = Path("content/materials/alchemist-materials.json")


@pytest.fixture
def track():
    return wc.get("alchemist")


@pytest.fixture
def shipped() -> list[dict]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))["materials"]


# --- the track loads through the generic framework -----------------------------------------


def test_the_alchemist_loads_through_the_shared_loader():
    """One more file, not one more code path: `load_dir` reads the track cold, with no
    alchemist-specific code anywhere in rules/worldclass.py."""
    tracks = wc.load_dir("content/world-classes")
    assert "alchemist" in tracks
    assert tracks["alchemist"].max_level == 5
    # The namespace pin: both tracks coexist in the one registry.
    assert "herbalist" in tracks


def test_tier_gating_walks_the_five_tiers_in_order(track):
    """Level N works tier N and nothing above it, common through legendary — the same
    staircase the Herbalist climbs, because the two tracks pay from one mastery table
    and a cheaper ladder in one file would be a balance bug in both."""
    ranks = [wc.tier_rank(track.at(lv).max_tier) for lv in range(1, 6)]
    assert ranks == [1, 2, 3, 4, 5]


def test_react_and_stabilize_are_learned_together(track):
    """React is the dangerous heart of the craft and Stabilize is what keeps it from
    going wrong; learning them at different levels would create a band of levels where
    the two-volatile rule could never be satisfied."""
    assert "react" in track.at(3).methods
    assert "stabilize" in track.at(3).methods


def test_no_method_name_collides_with_herbalism(track):
    """`crafting.is_tincture` and friends read shape words off jar names; a shared
    method or shape word would make an alchemist's product answer herbalism's
    questions. Both vocabularies are checked because both are load-bearing."""
    from rules import crafting

    herbal = wc.get("herbalist")
    ours = set(track.unlocked_methods(5))
    theirs = set(herbal.unlocked_methods(5))
    assert not ours & theirs
    assert not set(alch.SHAPE_WORDS.values()) & set(crafting.SHAPE_WORDS.values())


# --- the catalogue -------------------------------------------------------------------------


def test_material_ids_are_unique(shipped):
    ids = [m["id"] for m in shipped]
    assert len(ids) == len(set(ids)), sorted(
        i for i in set(ids) if ids.count(i) > 1)


def test_all_five_tiers_are_populated_and_the_catalogue_is_deep(shipped):
    """The brief's target was at least 110 entries with every tier represented — a
    catalogue with a hollow tier makes a whole Alchemist level unlockable but
    pointless, which is the Herbalist deed bug in a different coat."""
    by_tier: dict[str, int] = {}
    for m in shipped:
        by_tier[m["tier"]] = by_tier.get(m["tier"], 0) + 1
    assert len(shipped) >= 110, f"only {len(shipped)} materials"
    for tier in wc.TIERS:
        assert by_tier.get(tier, 0) >= 8, f"{tier}: {by_tier.get(tier, 0)} entries"


def test_every_authored_effect_validates(shipped):
    """Zero invalid specs. An effect the vocabulary cannot express stays prose
    (`narrative` or the entry's text), never a guessed spec — a spec that looks
    authored and does nothing is the failure docs/homebrew-rules.md exists to
    prevent. Offenders are printed so a regression names itself."""
    bad: list[str] = []
    for m in shipped:
        for i, spec in enumerate(m.get("effects") or []):
            for problem in effectspec.validate(spec, f"{m['id']} effect {i + 1}"):
                bad.append(problem)
    for line in bad:
        print(line)
    assert not bad, f"{len(bad)} invalid effects"


def test_volatility_is_a_real_presence(shipped):
    """Volatility is alchemy's signature; a catalogue where it is a rounding error
    would make Stabilize a dead method. At least a fifth of the shelf fights back."""
    volatile = [m for m in shipped if m.get("volatile")]
    assert len(volatile) >= len(shipped) // 5


# --- chain rules ---------------------------------------------------------------------------


def _chain(methods, mats, name=""):
    return alch.Chain(methods=list(methods), material_ids=list(mats), name=name)


def test_two_volatiles_without_a_stabilizer_are_refused():
    """The craft's cardinal sin, refused before any roll — with the sentence, because
    the sentence tells the player which method fixes it."""
    got = alch.preview(3, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "lamp-oil"]))
    assert ("Two volatile materials in one vessel is an explosion, not a "
            "preparation. Stabilize the chain, or take one out.") in got.problems


def test_stabilize_lifts_the_two_volatile_refusal():
    got = alch.preview(3, _chain(["dissolve", "react", "stabilize", "seal"],
                                 ["brimstone", "lamp-oil"]))
    assert not got.problems


def test_seal_before_react_is_refused():
    """A sealed flask is a closed one; sealing before the reaction is a grenade with
    extra steps. Named specifically because the generic 'seal finishes a chain'
    refusal does not say which two methods to swap."""
    got = alch.preview(3, _chain(["dissolve", "seal", "react"],
                                 ["brimstone", "distilled-water"]))
    assert "Nothing reacts inside a sealed flask. React first, seal last." \
        in got.problems


def test_a_reaction_with_no_solvent_is_refused():
    """A reaction happens in solution. Two dry powders ground together are herbalism's
    business, not a react chain."""
    got = alch.preview(3, _chain(["react", "seal"], ["brimstone"]))
    assert any("A reaction needs a medium" in p for p in got.problems)


def test_a_material_that_attacks_its_vessel_needs_stabilizing_even_alone():
    """Alkahest dissolves the flask as readily as the contents — `needs_stabilizer`
    is a per-material rule, not a count rule, so one jar of it is already a problem."""
    got = alch.preview(5, _chain(["dissolve", "react", "seal"],
                                 ["alkahest", "brimstone"]))
    assert any("Alkahest attacks its own vessel" in p for p in got.problems)


def test_tier_gates_refuse_material_above_the_level():
    got = alch.preview(1, _chain(["dissolve", "seal"], ["quicksilver"]))
    assert any("Quicksilver is uncommon" in p for p in got.problems)


def test_methods_above_the_level_are_refused_with_the_level_that_allows_them():
    got = alch.preview(1, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "distilled-water"]))
    assert any("React is learned at Alchemist 3" in p for p in got.problems)


def test_each_volatile_past_the_first_raises_the_dc_by_the_step():
    """The volatility surcharge, with the numbers. Same methods (so the per-stage term
    is constant), same tier (so the base is constant); only the volatile count moves.
    +3 per extra volatile rather than +2 so the itemised DC's surcharge term is
    visibly not the per-stage bump."""
    methods = ["dissolve", "react", "stabilize", "seal"]
    one = alch.preview(3, _chain(methods, ["brimstone", "distilled-water"]))
    two = alch.preview(3, _chain(methods, ["brimstone", "lamp-oil"]))
    three = alch.preview(3, _chain(methods, ["brimstone", "saltpetre", "lamp-oil"]))
    assert not one.problems and not two.problems and not three.problems
    # base 10 (common) + 6 (three stages past the first) = 16, then +3 per extra jar.
    assert one.dc == 16
    assert two.dc == one.dc + alch.VOLATILE_DC_STEP
    assert three.dc == one.dc + 2 * alch.VOLATILE_DC_STEP
    # And the surcharge is itemised, not buried in the total.
    assert any("volatile" in t["label"] for t in three.dc_terms)


def test_the_mishap_stakes_rise_with_the_volatile_count():
    """The preview says what failure costs before the material is committed — one
    volatile loses the jar, two or more lose everything. The stakes are words the
    player reads, so they are pinned as words."""
    methods = ["dissolve", "react", "stabilize", "seal"]
    one = alch.preview(3, _chain(methods, ["brimstone", "distilled-water"]))
    two = alch.preview(3, _chain(methods, ["brimstone", "lamp-oil"]))
    assert "half strength" in one.mishap
    assert "full strength" in two.mishap and "every material is lost" in two.mishap


# --- the cross-craft hook ------------------------------------------------------------------


def test_a_herbalism_product_is_accepted_as_a_material():
    """An infusion is a reagent: the crafts feed each other. Recognised by the shape
    word herbalism's own methods write into the stock id (`crafting.SHAPE_WORDS`,
    read rather than copied), carried as kind 'intermediate'."""
    got = alch.get("woundwort-tincture#1")
    assert got.kind == "intermediate"
    assert got.name == "Woundwort Tincture"


def test_a_liquid_intermediate_can_be_a_reactions_medium():
    """A tincture is a prepared liquid, which is exactly what react wants — a chain
    built on one needs no separate solvent."""
    got = alch.preview(3, _chain(["dissolve", "react", "stabilize", "seal"],
                                 ["woundwort-tincture#1", "brimstone"]))
    assert not got.problems


def test_an_unknown_id_that_is_not_a_herbal_product_still_fails():
    """The hook must not make every typo a valid 'intermediate'."""
    with pytest.raises(KeyError):
        alch.get("brimstone-typo")
    got = alch.preview(1, _chain(["dissolve", "seal"], ["no-such-thing"]))
    assert "No such material: no-such-thing." in got.problems


# --- homebrew ------------------------------------------------------------------------------


def test_homebrew_materials_layer_over_the_shipped_set(tmp_path, monkeypatch):
    """Layered, not replaced — a corrected shipped catalogue in a later build must not
    be shadowed by a stale user copy (the World Bible stylesheet trap CLAUDE.md
    records, and the same pattern worldclass.tracks() uses)."""
    from django.conf import settings

    home = tmp_path / "homebrew" / "materials"
    home.mkdir(parents=True)
    (home / "extra.json").write_text(json.dumps({
        "materials": [
            {"id": "grave-mould", "name": "Grave Mould", "kind": "reagent",
             "tier": "uncommon", "volatile": False, "effects": []},
            # An override: the user's brimstone wins over the shipped one.
            {"id": "brimstone", "name": "Sour Brimstone", "kind": "reagent",
             "tier": "common", "volatile": True, "effects": []},
        ]
    }), encoding="utf-8")

    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(alch, "_MATERIALS", None)
    got = alch.materials()
    assert "grave-mould" in got
    assert got["brimstone"].name == "Sour Brimstone"
    # The shipped set is still underneath, not replaced.
    assert "quicksilver" in got
