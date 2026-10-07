"""The Alchemist world class and its shelf (docs/alchemy-revamp-plan.md §4, §5, §12, §15;
contracts §8, lane F).

Rewritten for the step bench (2026-10-06). The old file pinned the chain bench: five
levels, the 25/65/50/100 curve, the two-volatiles refusal, Seal last, exact-recipe
spell potions. Those rules are gone by the owner's rulings and their defects are re-pinned
against the new gates here and in tests/test_alchemy_bench.py. The id-uniqueness test
moved to tests/test_alchemy_shelf.py with lane A. Each test names the defect it prevents.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.conf import settings

from rules import alchemist as al
from rules import benches, crafting, effectspec, formulae, materials
from rules import worldclass as wc
from rules.sheet import load_pc

ROOT = Path(settings.BASE_DIR)


@pytest.fixture
def track():
    return wc.get("alchemist")


def _potions() -> list[dict]:
    return json.loads((ROOT / "content" / "materials" / "alchemist-spell-potions.json")
                      .read_text(encoding="utf-8"))["potions"]


def _rows() -> list[dict]:
    return json.loads((ROOT / "content" / "materials" / "alchemist-materials.json")
                      .read_text(encoding="utf-8"))["materials"]


# --- the track (plan §4) -------------------------------------------------------------------

def test_three_levels_open_the_owners_methods(track):
    """Owner Q6.1 and Q3.1: L1 Dissolve, Calcine, Bottle (and Assay), L2 Distill, Filter,
    React, L3 Sublime, Transmute. The old table had five levels and gated React at 3 and
    Sublime at 4, with Seal, Precipitate, Stabilize and Catalyze as methods."""
    assert track.max_level == 3
    assert set(track.at(1).methods) == {"dissolve", "calcine", "bottle", "assay"}
    assert set(track.at(2).methods) == {"distill", "filter", "react"}
    assert set(track.at(3).methods) == {"sublime", "transmute"}
    every = set(track.unlocked_methods(3))
    assert every == set(al.METHODS)
    assert not every & {"seal", "precipitate", "stabilize", "catalyze"}


def test_the_track_paces_as_the_other_two_and_runs_on_in_perks(track):
    """Plan §4.1-4.2: 25 and 65 to reach 2 and 3 (herbalism's and the forge's, kept equal
    on purpose), then endless levels with two picks each, Containment the alchemist's own
    perk. Measured before: the 25/65/50/100 curve and a `legendary-work` deed at 5."""
    assert track.thresholds == [25, 65]
    assert not track.milestones and not track.deeds
    assert track.perks == ("potency", "duration", "quality", "yield", "containment")
    assert track.to_next(3) == 50 and track.to_next(4) == 60
    p = wc.Progress(track="alchemist", level=5)
    assert wc.perk_picks_banked(p) == 4
    assert [wc.ceiling_index(wc.Progress(track="alchemist", level=n)) for n in (1, 2, 3)] \
        == [2, 3, 4]


def test_every_method_has_a_rule_row_and_bench_help(track):
    """A method with no `bench.methods` row cannot be planned and one without
    `method_help` is a blank beside its button; the order lists all nine."""
    rows = track.data["bench"]["methods"]
    assert set(rows) == set(al.METHODS) == set(track.data["bench"]["order"])
    for mid in al.METHODS:
        assert rows[mid]["where"] in ("kit", "lab"), mid
        assert mid in track.data["method_help"] or mid == "assay", mid
    labs = {m for m, r in rows.items() if r["where"] == "lab"}
    assert labs == {"distill", "sublime", "transmute"}            # owner Q6.3


def test_no_intermediate_word_answers_herbalisms_questions():
    """`crafting.is_tincture` and friends read shape words off names; an alchemist's
    Solution must never be read as a herbal Tincture."""
    words = {r["word"] for r in wc.get("alchemist").data["bench"]["forms"].values()}
    assert not words & set(crafting.SHAPE_WORDS.values())


def test_the_old_chain_is_refused_in_words():
    """The old chain bench retired with the /craft/ tab (owner Q9.1). A chain sent there
    is refused with a sentence naming the new bench, never run on retired rules."""
    with pytest.raises(benches.MovedBench) as got:
        benches.chain_from_body("alchemist", {"methods": ["seal"]})
    assert "one step at a time" in str(got.value)
    assert set(benches.method_glyphs("alchemist")) == set(al.METHODS)


def test_the_check_is_intelligence_and_the_laboratory_adds_two():
    """d20 + Alchemist level + half level + Int, itemised; the book's alchemist's lab is
    +2 circumstance (UE p.77). No naturals: a DC 30 at +5 is impossible, not a 5%."""
    pc = load_pc("fixtures/pc-kesst.json")
    base = al.check_terms(pc, 2)
    assert [t["label"] for t in base][0] == "Alchemist 2"
    assert sum(t["value"] for t in al.check_terms(pc, 2, lab=True)) == \
        sum(t["value"] for t in base) + 2
    assert al.check_odds(30, 5) == (None, "needs +5 more to the check")


# --- the shelf through the one door (lane A's hand-off) ---------------------------------------

def test_the_harvest_excursion_finds_the_basilisk_eye():
    """The alchemist's private loader never saw the hybrid herbs, so when lane A merged
    the basilisk-eye gland into the herb the harvest excursion lost it: `obtainable(
    "harvested", creature="basilisk")` found nothing. Read through `alchemy_shelf`, the
    herb is there with its `from_creatures`."""
    got = {m.id for m in al.obtainable("harvested", creature="the basilisk")}
    assert "basilisk-eye" in got
    assert "basilisk-eye" in al.materials()
    assert al.get("basilisk-eye").from_creatures == ["basilisk"]


def test_every_kind_on_the_shelf_has_a_glyph():
    kinds = {d["kind"] for d in materials.alchemy_shelf().values()
             if not materials.is_herb_view(d)}
    assert kinds <= set(al.KIND_GLYPH)


def test_no_alchemist_row_keeps_the_old_effects_list():
    """Lane D kept `effects` only for the old chain bench; with it retired, the copies go
    (the data tool, tools/alchemy_data_pass.py, removes them). A second list beside
    `product` is a second answer to what a reagent does."""
    assert not [r["id"] for r in _rows() if "effects" in r or "effects_converted" in r]


def test_every_family_has_a_vessel():
    """Lane D's pass found no material with the `stick` trait, so the tool family
    (sunrod, tindertwig, smokestick) had no vessel and none could be bottled. Every family
    the formula table names is bottled by at least one vessel on the shelf."""
    have = set()
    for mid, doc in materials.alchemy_shelf().items():
        if doc.get("kind") == "vessel":
            have |= set(formulae.vessel_families(mid))
    assert set(formulae.FAMILIES) <= have
    assert formulae.vessel_families("wooden-rod") == ("tool",)


def test_every_old_recipe_names_a_drinkable_vessel():
    """The nine 3rd-level recipes named the crystal retort as their only vessel, and the
    retort is apparatus now (never spent, decides no family): bottled as written they made
    no potion. Each old recipe names a vial a potion is drunk from."""
    short = []
    for p in _potions():
        fams = set()
        for m in p["materials"]:
            fams |= set(formulae.vessel_families(m))
        if "potion" not in fams and "oil" not in fams:
            short.append(p["id"])
    assert short == []


def test_every_shelf_material_is_valid_through_the_door():
    """The rows the data tool wrote (the wooden rod included) pass lane D's validator."""
    shelf = materials.all()
    bad = []
    for r in _rows():
        doc = materials.normalise(r, materials.ALCHEMY_CATALOGUE)
        bad += materials.validate(doc, shelf=shelf)
    assert bad == []


def test_every_working_trait_has_words():
    """A working trait with no line in a lore file shows on a card as its bare id."""
    from rules import knowledge

    words = dict(knowledge.lore(knowledge.ALCHEMIST)["working_words"])
    words.update(knowledge.lore(knowledge.BLACKSMITH)["working_words"])
    used = {str(w.get("trait")) for d in materials.alchemy_shelf().values()
            for w in d.get("working") or ()}
    assert used - set(words) == set()
    assert set(effectspec.ALCHEMY_WORKING_TRAITS) - set(words) == set()
