"""The leatherworker track, its shelf library, and the retired chain (docs/leatherworking-
revamp-plan.md §7, §17, §20; rewritten by leather lane E, 2026-10-08, plan §23.1).

The step bench's rules are tests/test_leather_bench.py and its API tests/test_leather_api.py.
This file pins the track's shape (three levels and endless perks, the owner's Q6.2 and Q6.3,
with Harden at level 1 for the field kit's small kettle, answer 3 of 2026-10-08), the
conversion of old progress, and the shelf the market's counter and the acquisition hub
still read. Every test names the decision it pins.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, effectspec, herbprep
from rules import leatherworker as lw
from rules import worldclass as wc

TRACK_FILE_DIR = Path("content/world-classes")
MATERIALS_FILE = Path("content/materials/leatherworker-materials.json")


@pytest.fixture(autouse=True)
def _fresh_material_cache():
    """The module caches materials for the app's lifetime; a test that redirects the
    homebrew directory must not inherit another test's cache, or poison the next."""
    lw._MATERIALS = None
    yield
    lw._MATERIALS = None


def _shipped() -> list[dict]:
    return json.loads(MATERIALS_FILE.read_text(encoding="utf-8"))["materials"]


def _track() -> wc.Track:
    return wc.load_dir(TRACK_FILE_DIR)["leatherworker"]


# --- the track ------------------------------------------------------------------------------

def test_three_unlock_levels_then_endless_levels_with_the_forges_four_perks():
    """Owner Q6.2 and Q6.3 (2026-10-05): field work, then the tannery, then legendary; past
    3 the levels never stop and each banks two picks of potency, hardening, quality or
    yield. Measured before: five written levels and a flat 100 a level after them, the last
    world class still on the per-recipe table."""
    t = _track()
    assert t.max_level == 3 and t.thresholds == [25, 65]
    assert t.perks == ("potency", "hardening", "quality", "yield")
    assert [t.to_next(n) for n in (1, 2, 3, 4, 10)] == [25, 65, 50, 60, 120]
    assert not t.milestones and not t.deeds, "the legendary-hide milestone is retired"
    assert [t.at(n).ceiling for n in (1, 2, 3)] == [2, 3, 4]


def test_the_rarity_ladder_is_uncommon_exotic_legendary():
    """Plan §17.1: common and uncommon hides at 1, rare and exotic at 2, legendary at 3."""
    ranks = [wc.tier_rank(l.max_tier) for l in sorted(_track().levels, key=lambda x: x.level)]
    assert ranks == [2, 4, 5]


def test_the_methods_by_level_and_harden_is_field_work():
    """Owner Q2.1: twelve methods. Q6.2 put Harden at level 2; the owner's answer 3 of
    2026-10-08 ("add a small kettle to the field kit") makes plain leather armour makeable
    at level 1 in the field, so Harden is level 1. Skin, Cure, Oil and Line are gone."""
    t = _track()
    assert set(t.unlocked_methods(1)) == {"salt", "flense", "tan", "cut", "stitch", "harden",
                                          "assemble", "grade"}
    assert set(t.unlocked_methods(2)) - set(t.unlocked_methods(1)) == {
        "curry", "tool", "dye", "laminate"}
    assert set(t.unlocked_methods(3)) == set(lw.METHODS)
    for gone in ("skin", "cure", "oil", "line"):
        assert gone not in t.unlocked_methods(9)
    assert [lw.old_method(m) for m in ("cure", "oil", "line", "skin")] == \
        ["salt", "curry", "assemble", ""]


def test_an_old_leatherworker_4_or_5_keeps_its_level_as_perk_picks():
    """Plan §20 and owner Q9.1 ("convert"): levels 4 and 5 become endless levels, the picks
    chosen on first load. Nothing moves: the bank is counted from the level. Only a level
    past the unlocks is stamped, so a Leatherworker 1 save round-trips unchanged."""
    old5 = wc.Progress(track="leatherworker", level=5, mp=40,
                       milestones=["legendary-hide"])
    assert wc.migrate(old5) is True and old5.schema == wc.LEATHERWORKER_SCHEMA
    assert (old5.level, old5.mp, wc.perk_picks_banked(old5)) == (5, 40, 4)
    assert wc.migrate(old5) is False, "idempotent"
    old4 = wc.Progress(track="leatherworker", level=4)
    wc.migrate(old4)
    assert wc.perk_picks_banked(old4) == 2
    fresh = wc.Progress(track="leatherworker", level=1)
    assert wc.migrate(fresh) is False and fresh.schema == 0


def test_every_successful_step_pays_and_a_batch_pays_its_steps():
    """Mastery (owner 2026-10-05): every successful step pays through `award_step`, a batch
    of N as N steps. The per-recipe award paid a first craft 3 and repeats 1."""
    t = wc.get("leatherworker")
    p = wc.Progress(track="leatherworker")
    one = wc.award_step(t, p, method="salt", ingredient_id="deer-hide", rarity_rank=1,
                        quality_index=1)
    again = wc.award_step(t, p, method="salt", ingredient_id="deer-hide", rarity_rank=1,
                          quality_index=1)
    five = wc.award_step(t, p, method="cut", ingredient_id="deer-hide", rarity_rank=1,
                         quality_index=1, count=5, noun="set of panels")
    assert (one["mp"], again["mp"], five["mp"]) == (1, 1, 5)


def test_check_terms_are_itemised_and_intelligence_based():
    """Craft is Int-based in PF1e; the Craft-ranks term (option A, 2026-10-07) is last and
    absent with no ranks. Itemised because '+9' says nothing."""

    class Crafter:
        level = 5
        ranks = {}

        def ability_mod(self, which):
            return 2 if which == "int" else 0

    terms = lw.check_terms(Crafter(), 2)
    assert [t["value"] for t in terms] == [2, 2, 2]
    assert terms[-1]["label"] == "Intelligence"
    assert lw.check_bonus(None, 3) == 3


def test_every_method_has_structured_help_and_an_icon_of_its_own():
    """The tooltip's three questions, for every method the track has and no other, and a
    station icon each (the old page drew eleven identical crates)."""
    data = json.loads((TRACK_FILE_DIR / "leatherworker.json").read_text(encoding="utf-8"))
    every = _track().unlocked_methods(3)
    help_ = data.get("method_help") or {}
    assert set(help_) == set(every) == set(lw.METHODS)
    for method in every:
        for key in ("does", "needs", "for"):
            assert help_[method].get(key), f"{method}.{key} is empty"
        assert method in data["method_descriptions"], method
    assert set(lw.METHOD_GLYPH) == set(lw.METHODS)
    assert len(set(lw.METHOD_GLYPH.values())) == len(lw.METHOD_GLYPH)
    assert list(lw.bench_rules()["order"]) == list(lw.METHODS)


def test_every_number_the_plan_proposes_is_a_rule_row():
    """Contracts §7: "every proposed number lives in leatherworker.json under bench" — the
    tannages, the units, the grade caps, the DCs, the salted keep. A number in code is one
    the owner cannot tune without a release."""
    rules = lw.bench_rules()
    for key in ("methods", "tannages", "hide_units", "products", "grade_caps",
                "masterwork_dc", "book_dc", "salted_keep_minutes", "fresh_hours", "bought",
                "traits", "suit_by_size"):
        assert key in rules, key
    assert set(rules["products"]) >= set(lw.PRODUCTS) | set(lw.CUT_PIECES)
    assert set(rules["tannages"]) == {"brain", "rawhide", "alum", "bark", "mineral", "planar"}


def test_every_product_is_a_table_key_or_a_worn_good():
    """The measured wear defect (Inv §0.1) was a NAME in `base`: every suit and shield the
    bench makes is a `tables.ARMOUR` / `SHIELDS` key, and every worn good names a slot."""
    from rules.tables import ARMOUR, SHIELDS, SLOTS

    for pid, info in lw.PRODUCTS.items():
        if info["gear"] == "armour":
            assert info["base"] in ARMOUR, pid
        elif info["gear"] == "shield":
            assert info["base"] in SHIELDS, pid
        elif not info.get("carried"):
            assert info["slot"] in SLOTS, pid
    for forge_suit in ("studded leather", "armored coat", "steel lamellar"):
        assert forge_suit not in {i["base"] for p, i in lw.PRODUCTS.items()
                                  if p != "bone-studded leather"}, \
            f"{forge_suit} is the forge's to finish (owner Q1.3)"


# --- the materials --------------------------------------------------------------------------

def test_material_ids_are_unique():
    ids = [m["id"] for m in _shipped()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate material ids: {sorted(dupes)}"


def test_all_five_tiers_are_populated_and_the_file_is_big_enough():
    """The brief's target was 110+ entries across every tier — a tier with two entries is
    a rules gate with nothing behind it. Counted, not assumed."""
    entries = _shipped()
    assert len(entries) >= 110, f"only {len(entries)} materials"
    by_tier: dict[str, int] = {}
    for m in entries:
        by_tier[m["tier"]] = by_tier.get(m["tier"], 0) + 1
    for tier in wc.TIERS:
        assert by_tier.get(tier, 0) >= 8, f"{tier} is thin: {by_tier.get(tier, 0)}"


def test_every_authored_effect_validates():
    offenders = []
    for m in _shipped():
        for i, spec in enumerate(m.get("effects") or []):
            offenders.extend(effectspec.validate(spec, f"{m['id']} effect {i + 1}"))
    assert not offenders, f"{len(offenders)} invalid effect specs"


def test_every_hide_names_a_creature_the_bestiary_has():
    """`from_creatures` is the old skin excursion's joint (lane C replaces it with bestiary
    tags). A fragment no bestiary name contains is a hide no fight can yield."""
    names = [c.get("name", "").lower() for c in bestiary.imported().values()]
    orphans = []
    for m in _shipped():
        if m["kind"] != "hide":
            continue
        if m["id"].startswith("generic-") or m.get("obtain") == "bought":
            continue
        frags = [f.lower() for f in m.get("from_creatures") or []]
        assert frags, f"{m['id']} has no from_creatures"
        if not any(any(f in n for n in names) for f in frags):
            orphans.append(m["id"])
    assert not orphans, f"hides no creature yields: {orphans}"


def test_hides_from_prefers_the_longest_fragment():
    found = lw.hides_from("worg, winter wolf")
    assert found and found[0].id == "winter-wolf-pelt"


def test_raw_hide_window_matches_the_herbalist_animal_clock():
    """A hide is an animal part: the bench's 48 hours and the herbalist's must not drift."""
    assert lw.FRESH_HOURS == herbprep.ANIMAL_HOURS == lw.bench_rules()["fresh_hours"]
    for m in _shipped():
        if m["kind"] == "hide" and "green" in (m.get("forms") or ["green"]):
            assert m.get("fresh_hours"), f"{m['id']} has no freshness window"


def test_a_hides_size_and_clock_are_read_from_its_row():
    """Measured 2026-10-08: the one door's normalised document carries no `size` or
    `fresh_hours`, so a Large horse hide read as one Medium unit. Read from the catalogue
    row (plan §5.5: Large is two units, Huge four)."""
    assert lw.hide_size("horse-hide") == "large"
    assert lw.units_of_size(lw.hide_size("horse-hide")) == 2
    assert lw.units_of_size(lw.hide_size("red-dragonhide")) == 4
    assert lw.make_hide("deer-hide").quarters == 4


def test_homebrew_hide_layers_over_the_shipped_set(tmp_path, monkeypatch):
    """A hide dropped in homebrew/materials just works on the shelf, and the shipped set is
    layered under, not replaced — the `worldclass.tracks()` overlay."""
    from django.conf import settings

    home = tmp_path / "homebrew" / "materials"
    home.mkdir(parents=True)
    (home / "glass-cat-hide.json").write_text(json.dumps({
        "id": "glass-cat-hide", "name": "Glass Cat Hide", "kind": "hide",
        "tier": "rare", "size": "small", "fresh_hours": 48, "source": "skinned",
        "from_creatures": ["cat"],
    }), encoding="utf-8")
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    lw._MATERIALS = None
    loaded = lw.materials()
    assert loaded["glass-cat-hide"].tier == "rare"
    assert "deer-hide" in loaded


# --- the old chain, retired -------------------------------------------------------------------

def test_the_chain_bench_refuses_and_says_where_the_bench_went():
    """The old chain ran the five-level rules the owner retired: a red dragonhide suit at
    DC 38, every input spent on a failure, Harden refused without a wax. It refuses now in
    words; an unknown pattern is still refused by name with the patterns it knows."""
    with pytest.raises(lw.CraftError) as why:
        lw.preview(1, lw.chain_from_body({"methods": ["flense"], "materials": ["deer-hide"],
                                          "product": "cloak"}))
    assert "at the table now" in str(why.value)
    with pytest.raises(lw.CraftError) as why:
        lw.preview(1, lw.Chain(methods=["cut"], material_ids=["deer-hide"],
                               product="codpiece"))
    assert "satchel" in str(why.value) and "cloak" in str(why.value)


# --- icons and the shelf ------------------------------------------------------------------------

def test_every_kind_has_its_own_glyph_and_none_is_herbalism_s():
    kinds = {m["kind"] for m in _shipped()}
    assert not kinds - set(lw.KIND_GLYPH)
    glyphs = list(lw.KIND_GLYPH.values())
    assert len(glyphs) == len(set(glyphs)), "two kinds share a glyph"
    assert not set(glyphs) & {"🌿", "🍄", "🦴", "☠️"}, "herbalism's glyphs reused"
    assert lw.get("deer-hide").glyph == lw.KIND_GLYPH["hide"]


def test_every_material_says_how_it_is_obtained():
    kinds = {"harvested", "gathered", "mined", "bought"}
    for m in _shipped():
        assert m.get("obtain") in kinds, f"{m['id']}: {m.get('obtain')!r}"
        if m["obtain"] == "bought":
            assert m.get("price_gp"), f"{m['id']} is bought with no price"
        if m["obtain"] in ("gathered", "mined"):
            assert m.get("biomes"), f"{m['id']} is {m['obtain']} from nowhere"


def test_skinning_a_winter_wolf_offers_its_pelt_and_no_other_beast_s_hide():
    """The old excursion's reader, kept until lane C's harvest replaces it."""
    got = [m.id for m in lw.obtainable("harvested", creature="worg, winter wolf")]
    assert got[0] == "winter-wolf-pelt"
    assert "red-dragonhide" not in got
    assert lw.obtainable("harvested") == []


def test_gathering_a_forest_offers_bark_not_hide():
    got = [m.id for m in lw.obtainable("gathered", biome="forest")]
    assert "oak-bark" in got
    assert not any(lw.get(i).kind == "hide" for i in got)
    assert "mangrove-bark" in [m.id for m in lw.obtainable("gathered", biome="coast")]


def test_acquisition_excursions_declare_what_the_scene_must_provide():
    for key, spec in lw.ACQUISITION.items():
        assert spec["id"] == key
        assert spec["obtain"] in ("harvested", "gathered", "mined", "bought")
        assert spec["requires"] in ("creature", "biome", "market")


def test_the_shared_shelf_does_not_leak_another_craft_s_materials():
    """Measured before the craft filter: `obtainable("gathered", biome="forest")` answered
    with six blacksmith entries out of eleven."""
    mine = lw.materials()
    for foreign in ("living-steel", "oak-haft", "darkwood-haft"):
        assert foreign not in mine
    assert "curing-salt" in mine
    with pytest.raises(KeyError):
        lw.get("living-steel")
