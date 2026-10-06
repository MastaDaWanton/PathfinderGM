"""Enchanting: the Enchanter track after the revamp, and the old shelf library it keeps.

The owner's rulings of 2026-10-05 (docs/enchanting-answers.md) replaced the five-level
chain track (attune, scribe, bind, seal; focus, channel; imbue; empower; awaken) with the
other crafts' shape: three unlock levels on material rarity, then endless levels with
perks. The circle's step rules are tests/test_enchant_bench.py and its API
tests/test_enchant_api.py; this file pins the track, the check, and what still reads the
old shelf (the /craft/ page's catalogue and the acquisition hub).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import enchanter as en
from rules import worldclass as wc

SHIPPED = Path("content/materials/enchanter-materials.json")
TRACK_FILE = Path("content/world-classes/enchanter.json")


@pytest.fixture
def track():
    return wc.get("enchanter")


def _shipped_ids() -> set[str]:
    return {m["id"] for m in json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]}


# --- the track -----------------------------------------------------------------------------

def test_three_levels_then_endless_like_the_other_crafts(track):
    """The owner (round 2): "same as the others". Before it the Enchanter had five written
    levels with a `legendary-binding` deed whose ladder (empower) was a method nothing
    enforced; the Herbalist's and the Blacksmith's shape is three unlock levels, 25 and 65
    to reach them, then 50, 60, 70... with two perk picks a level."""
    assert track.max_level == 3
    assert [track.to_next(n) for n in (1, 2, 3, 4)] == [25, 65, 50, 60]
    assert set(track.perks) == {"potency", "quality", "yield", "capacity"}
    assert track.endless["picks_per_level"] == 2
    assert not track.milestones and not track.deeds


def test_each_level_opens_its_methods_rarity_and_ceiling(track):
    """Plan §5.1: L1 the whole ritual on common and uncommon essence, Fine at best; L2
    Refine and rare and exotic, Superior; L3 Cleanse and legendary, Flawless. The old
    track put Bind at L1 but legendary work behind a level-5 deed; levels past 3 now read
    level 3's row and keep every method."""
    assert track.unlocked_methods(1) == ["prepare", "attune", "bind", "read", "identify",
                                         "unbind"]
    assert "refine" in track.unlocked_methods(2) and "cleanse" not in track.unlocked_methods(2)
    assert "cleanse" in track.unlocked_methods(9)
    assert [wc.tier_rank(track.at(n).max_tier) for n in (1, 2, 3, 9)] == [2, 4, 5, 5]
    assert [track.at(n).ceiling for n in (1, 2, 3)] == [2, 3, 4]


def test_the_retired_methods_are_gone_and_mapped_for_old_recipes(track):
    """Scribe, focus, channel, seal, imbue, empower and awaken had no code behind them
    (plan §1: the help text described rules nobody enforced). None is offered; each is
    mapped for the migration (plan §19), the dropped ones to nothing."""
    retired = {"scribe", "focus", "channel", "seal", "imbue", "empower", "awaken"}
    assert not retired & set(track.unlocked_methods(99))
    data = json.loads(TRACK_FILE.read_text(encoding="utf-8"))
    assert set(data["old_methods"]) == retired
    assert data["old_methods"]["seal"] == "bind" and data["old_methods"]["empower"] == ""


def test_method_help_matches_method_descriptions_and_the_bench_rows(track):
    """Three hand-written sets of one list: the descriptions, the tooltips (does, needs,
    for) and the bench's rule rows. A method in one and not another is a bench that
    explains half of itself, or offers a method it has no rule for."""
    data = json.loads(TRACK_FILE.read_text(encoding="utf-8"))
    methods = set(track.unlocked_methods(99))
    assert set(data["method_descriptions"]) == methods
    assert set(data["method_help"]) == methods
    assert set(data["bench"]["methods"]) == methods == set(data["bench"]["order"])
    for method, help_text in data["method_help"].items():
        for key in ("does", "needs", "for"):
            assert help_text.get(key), f"{method}: method_help has no {key!r}"


def test_an_old_enchanter_five_keeps_its_level_as_banked_perks():
    """Plan §19 (convert): an old Enchanter 5 is level 3 plus two endless levels, so it
    holds four picks to spend at the circle, and the stamp runs once."""
    p = wc.Progress(track="enchanter", level=5, mp=40)
    assert wc.perk_picks_banked(p) == 4
    assert wc.migrate(p) is True and p.schema == wc.ENCHANTER_SCHEMA
    assert wc.migrate(p) is False and p.mp == 40


def test_the_capacity_perk_is_a_count_the_layer_adds():
    """The Enchanter's own perk (owner round 2): +1 to what an item holds per pick, said as
    a count (`perk_multipliers["capacity"]`), which `magic_layer.capacity` adds."""
    p = wc.Progress(track="enchanter", level=4, perks={"capacity": 2})
    assert wc.perk_multipliers(p)["capacity"] == 2
    assert "capacity" not in wc.perk_multipliers(wc.Progress(track="herbalist", level=4))


# --- the check -------------------------------------------------------------------------------

def test_check_terms_are_itemised_and_intelligence_based():
    """d20 + Enchanter level + half character level + Intelligence, three named terms, so
    "+10" is a sentence the player can check (plan §4.3)."""
    class Stub:
        level = 6
        abilities = {"int": 16}

    terms = en.check_terms(Stub(), 4)
    assert [t["value"] for t in terms] == [4, 3, 3]
    assert en.check_bonus(Stub(), 4) == 10
    assert "Intelligence" in terms[-1]["label"]


# --- the old shelf library ---------------------------------------------------------------------

def test_material_ids_are_unique():
    ids = [m["id"] for m in json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]]
    assert len(ids) == len(set(ids))


def test_the_shipped_file_loads_through_the_shelf_library():
    """The /craft/ page's shelf and the hub still read `en.materials()`; an essence's
    effects there are its grant through lane A's table (lane D's fields), never the old
    narrative prose: a ghost residue card said "half damage to incorporeal" in words."""
    loaded = en.materials()
    assert loaded["quartz-focus"].capacity == 1 and loaded["diamond-focus"].fragile
    assert loaded["powdered-pearl"].dc_mod == -2
    assert loaded["moonlit-varnish"].lifts == "night"
    assert loaded["flaming-essence"].effects[0]["damage_type"] == "fire"
    assert all(e.get("type") != "narrative" for e in loaded["ghost-residue"].effects)


def test_every_material_says_where_it_comes_from():
    """The craft-action button is the hub for obtaining materials. Gathered and mined
    entries name biomes, harvested ones a creature or a place. Arcane residue is the one
    by-product: it comes from Unbind (`unbound`) and no excursion offers it."""
    for m in en.materials().values():
        if m.id not in _shipped_ids():
            continue
        assert m.obtain in ("bought", "mined", "harvested", "gathered", "unbound"), m.id
        if m.obtain in ("gathered", "mined"):
            assert m.biomes, f"{m.id} is {m.obtain} but names no biome"
        if m.obtain == "harvested":
            assert m.biomes or m.from_creature, m.id
    assert en.get("arcane-residue").obtain == "unbound"
    assert not any(m.id == "arcane-residue" for m in en.obtainable("bought"))


def test_the_shelf_walk_skips_files_that_are_not_shelves():
    """The magic-item catalogue lives in the same folder; read as a shelf it offered to sell
    a Ring of Protection +1 as a crafting material."""
    loaded = en.materials()
    assert "mi-flaming" not in loaded and "fire-mote" in loaded
    assert not any(m.id.startswith("mi-") for m in en.obtainable("bought"))


def test_obtainable_narrows_to_where_you_are_standing():
    mountain = {m.id for m in en.obtainable("gathered", biome="mountain")}
    swamp = {m.id for m in en.obtainable("gathered", biome="swamp")}
    assert "fire-mote" in mountain and "fire-mote" not in swamp
    assert "ghost-residue" in swamp
    dragons = {m.id for m in en.obtainable("harvested", creature="red dragon")}
    assert "red-dragon-ichor" in dragons and "lich-dust" not in dragons


def test_acquisition_excursions_are_declared():
    assert en.ACQUISITION
    for excursion in en.ACQUISITION:
        assert excursion["obtain"] in ("bought", "mined", "harvested", "gathered")
        for key in ("id", "label", "needs", "blurb"):
            assert excursion.get(key), f"{excursion.get('id')}: missing {key}"


def test_every_kind_has_a_distinct_glyph():
    glyphs = en.KIND_GLYPH
    kinds = {m.kind for m in en.materials().values() if m.id in _shipped_ids()}
    assert kinds <= set(glyphs)
    assert len(set(glyphs.values())) == len(glyphs)
    assert not (set(glyphs.values()) & {"🌿", "🍄", "🦴", "☠️"})


def test_a_fractional_price_survives_the_loader():
    """1 cp is 0.01 gp: `int()` made it free (measured 2026-10-05, the copper fix)."""
    assert en.from_dict({"id": "probe", "name": "Probe", "price_gp": 0.05}).price_gp == 0.05


def test_homebrew_materials_layer_over_shipped(tmp_path, monkeypatch):
    """A homebrew copy of a shipped id merges over it field by field (the
    `worldclass.tracks()` overlay), so a partial override keeps what it did not send."""
    from django.conf import settings

    hb = tmp_path / "homebrew" / "materials"
    hb.mkdir(parents=True)
    (hb / "flaming-essence.json").write_text(json.dumps({
        "id": "flaming-essence", "name": "Balefire Essence"}), encoding="utf-8")
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(en, "_MATERIALS", None)
    loaded = en.materials()
    assert loaded["flaming-essence"].name == "Balefire Essence"
    assert loaded["flaming-essence"].effects


# --- the old chain, retired --------------------------------------------------------------------

def test_the_old_chain_is_refused_with_where_enchanting_is_done_now():
    """Plan §1, measured on e028885: the /craft/ chain sent the Shaping text as the item
    and refused every essence binding "not masterwork"; its methods are gone from the
    track. `benches.MOVED` refuses it in words, as it does herbalism's, while
    `benches.supports` still answers for every track (the craft page asks it)."""
    from rules import benches

    assert benches.supports("enchanter")
    with pytest.raises(benches.MovedBench) as err:
        benches.preview("enchanter", 1, en.Chain(methods=["attune"]))
    assert "circle at the table" in str(err.value)
    assert en.preview(1, en.Chain()).problems == [en.MOVED_WORDS]
