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


@pytest.fixture
def stock():
    return blacksmith.materials()


# --- the track loads through the unchanged framework --------------------------------------

def test_track_loads_through_the_generic_loader():
    """The whole point of the framework: `load_dir` reads blacksmith.json through the same
    loader as the Herbalist. Three written levels since the 2026-10-03 ruling (plan
    §4.1), then endless ones priced by the track's own `endless` block, with no
    track id named in worldclass.py's pricing."""
    tracks = wc.load_dir(Path(settings.BASE_DIR) / "content" / "world-classes")
    assert "blacksmith" in tracks
    track = tracks["blacksmith"]
    assert track.name == "Blacksmith"
    assert track.max_level == 3
    assert track.thresholds == [25, 65], "paced as the Herbalist, on purpose"
    assert [track.to_next(n) for n in (1, 2, 3, 4, 5)] == [25, 65, 50, 60, 70]
    assert track.perks == ("potency", "hardening", "quality", "yield")


def test_levels_gate_tiers_in_order():
    """Plan §4.1: Blacksmith 1 works common and uncommon, 2 rare and exotic, 3 legendary,
    the Herbalist's three-level ladder. Retired: the five-level, one-band-a-level table
    (its defect, a skipped band stranding a smith, is re-pinned on the new bands)."""
    track = wc.get("blacksmith")
    ranks = [wc.tier_rank(track.at(n).max_tier) for n in range(1, 6)]
    assert ranks == [2, 4, 5, 5, 5]


def test_methods_accumulate_and_never_expire():
    """`unlocked_methods` is cumulative: a Blacksmith 3 still forges. All eleven methods of
    plan §7 exist by level 2, the level-1 set is the minimum that makes a usable item
    (forge, quench, assemble) plus assay and smelt, and the merged methods are gone."""
    track = wc.get("blacksmith")
    assert set(track.unlocked_methods(1)) == {"forge", "quench", "assemble", "assay",
                                              "smelt"}
    assert set(track.unlocked_methods(3)) == set(blacksmith.METHODS)
    assert len(track.unlocked_methods(3)) == 11
    for gone in ("draw", "polish", "flux", "rivet"):
        assert gone not in track.unlocked_methods(9)
    for lo, hi in zip(range(1, 3), range(2, 4)):
        assert set(track.unlocked_methods(lo)) <= set(track.unlocked_methods(hi))


def test_no_deed_gates_a_level_any_more():
    """Retired: the level-5 `legendary-metal` deed (plan §4.1 removes it). Its defect was
    a gate that never opened; re-pinned as "no level waits on a deed": legendary metal is
    simply Blacksmith 3's band, and an old save holding the milestone loses nothing."""
    track = wc.get("blacksmith")
    assert track.milestones == {} and track.deeds == {}
    p = wc.Progress(track="blacksmith", level=3, mp=55, milestones=["legendary-metal"])
    got = wc.award_bonus(track, p, why="test", mp=0)
    assert got["level"] == 4, "65 to leave level 3 would be wrong: endless base is 50"


def test_endless_levels_bank_forge_perks():
    """Plan §4.2: past level 3 every level banks two picks of potency, hardening, quality
    or yield. The Herbalist's duration is not a forge perk, and asking for it is refused
    in words."""
    track = wc.get("blacksmith")
    p = wc.Progress(track="blacksmith", level=5)
    assert wc.perk_picks_banked(p) == 4
    wc.pick_perks(track, p, ["hardening", "hardening"])
    with pytest.raises(ValueError, match="no perk called 'duration'"):
        wc.pick_perks(track, p, ["duration"])
    got = wc.perk_multipliers(p)
    assert got["hardening"] == round(0.95 ** 2, 4)
    assert wc.track_summary(track, p)["perks"] == {"hardening": 2}
    assert wc.perk_picks_banked(p) == 2


def test_the_ceiling_is_fine_superior_flawless_and_masterwork_is_superior():
    """Plan §4.4: the quality ceiling is Fine at 1, Superior (masterwork) at 2, Flawless at
    3, plus one per Quality perk. Superior is the masterwork rung."""
    ceilings = [wc.ceiling_index(wc.Progress(track="blacksmith", level=n))
                for n in (1, 2, 3)]
    assert ceilings == [2, 3, 4]
    assert wc.ceiling_index(wc.Progress(track="blacksmith", level=4,
                                        perks={"quality": 1})) == 5
    assert blacksmith._mw_index() == 3 and wc.quality_name(3) == "Superior"


def test_an_old_blacksmith_5_migrates_to_endless_levels_with_picks():
    """Plan §14: levels above 3 become endless levels with perks picked on first load,
    as `migrate_herbalist` did: the level and mastery are kept, the picks are banked, and
    the migration runs once."""
    p = wc.Progress(track="blacksmith", level=5, mp=40, milestones=["legendary-metal"])
    assert wc.migrate(p) is True and p.schema == wc.BLACKSMITH_SCHEMA
    assert (p.level, p.mp) == (5, 40)
    assert wc.perk_picks_banked(p) == 4
    assert wc.migrate(p) is False


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


# --- the quality ladder -------------------------------------------------------------------


# --- the dispatch surface -----------------------------------------------------------------


def test_the_check_is_intelligence_not_wisdom():
    """Craft is an Intelligence skill in 1e, and smithing is Craft (weapons) or Craft
    (armour). Herbalism's Wisdom is not the precedent — that number is authored in the
    Herbalist document, which speaks for that track alone."""
    class FakeActor:
        level = 8

        def ability_mod(self, which):
            return {"int": 3, "wis": 9}[which]

    terms = blacksmith.check_terms(FakeActor(), 3)
    assert [t["label"] for t in terms] == [
        "Blacksmith 3", "half character level (8)", "Intelligence"]
    assert [t["value"] for t in terms] == [3, 4, 3]
    assert blacksmith.check_bonus(FakeActor(), 3) == 10
    # No actor is a legitimate question about the chain rather than about anybody.
    assert blacksmith.check_bonus(None, 3) == 3


# --- the output contract ------------------------------------------------------------------


# --- icons ------------------------------------------------------------------------------

def test_every_kind_has_its_own_distinct_glyph(stock):
    """The shelf shows five crafts' materials together, so a glyph has to identify a
    kind at a glance. Distinct within the track; the orchestrator asserts distinctness
    across all five."""
    mine = {e["kind"] for e in _raw_entries()}
    assert mine <= set(blacksmith.KIND_GLYPH), \
        f"kinds with no glyph: {mine - set(blacksmith.KIND_GLYPH)}"
    glyphs = list(blacksmith.KIND_GLYPH.values())
    assert len(glyphs) == len(set(glyphs)), f"duplicate glyphs: {glyphs}"
    # Herbalism's symbols are spoken for.
    assert not set(glyphs) & {"🌿", "🍄", "🦴", "☠️"}
    assert blacksmith.get("iron").glyph == blacksmith.KIND_GLYPH["metal"]


# --- method tooltips ----------------------------------------------------------------------

def test_every_method_has_a_structured_tooltip():
    """A method with no tooltip is a button whose effect the player can only learn by
    spending materials on it. The two sets must match exactly — an entry for a method
    that does not exist is just as wrong as a method with no entry."""
    path = Path(settings.BASE_DIR) / "content" / "world-classes" / "blacksmith.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    methods = {m for l in data["levels"] for m in l["methods"]}
    help_ = data["method_help"]
    assert set(help_) == methods, (
        f"missing help: {methods - set(help_)}; "
        f"help for no such method: {set(help_) - methods}")
    assert set(data["method_descriptions"]) == methods
    for name, entry in help_.items():
        assert set(entry) == {"does", "needs", "for"}, f"{name}: {sorted(entry)}"
        for key, value in entry.items():
            assert value.strip(), f"{name}.{key} is empty"


# --- acquisition --------------------------------------------------------------------------

def test_every_material_says_how_it_is_obtained(stock):
    """The craft-action button dispatches on this, so a material with no `obtain`
    belongs to no excursion and can never be acquired — it would sit on the shelf
    looking available and be unreachable in play."""
    kinds = {"mined", "bought", "harvested", "gathered"}
    mine = [blacksmith.get(e["id"]) for e in _raw_entries()]
    for m in mine:
        assert m.obtain in kinds, f"{m.id}: obtain={m.obtain!r}"
    counts: dict[str, int] = {}
    for m in mine:
        counts[m.obtain] = counts.get(m.obtain, 0) + 1
    print(f"obtain: {counts}")
    assert set(counts) == kinds, f"an excursion with nothing to find: {counts}"
    # Each excursion's own promise: a price to pay, a creature to cut, ground to dig.
    for m in mine:
        if m.obtain == "bought":
            assert m.price_gp is not None and m.price_gp > 0, f"{m.id} has no price"
        if m.obtain == "harvested":
            assert m.from_creatures, f"{m.id} names no creature"
        if m.obtain == "mined":
            assert m.biomes, f"{m.id} is mined from nowhere"


def test_the_shelf_is_shared_but_the_excursions_are_not(stock):
    """`content/materials` is one shelf for five crafts, and `kind` cannot tell them
    apart — "treatment" appears in all four shipped catalogues and "fitting" in two.

    Measured when this was missed: prospecting for ore in the mountains turned up wyvern
    hide and wyvern sinew, because `obtainable` walked the whole shelf. So `materials()`
    stays shelf-wide (a smith may rivet a leatherworker's grip onto a blade, and a chain
    naming one must resolve it) and `mine()` is the narrower question the bench asks.
    """
    assert "wyvern-hide" in stock, "the shelf should still hold every craft's materials"
    assert "wyvern-hide" not in blacksmith.mine()
    assert "iron-ore" in blacksmith.mine()
    assert len(blacksmith.mine()) < len(stock)
    # Cross-craft materials still resolve in a chain, which is the point of one shelf.
    assert blacksmith.get("wyvern-hide").name


def test_prospecting_answers_to_the_ground_underfoot():
    """Mining is the flagship, and it matches the biome the way foraging does: a smith
    standing in mountains comes back with mountain ore and not sea-salt."""
    mountain = {m.id for m in blacksmith.obtainable("mined", biome="mountain")}
    assert "iron-ore" in mountain and "silver-ore" in mountain
    # Bog iron is raked out of marshes and belongs to the swamp, not the peaks.
    assert "bog-iron" not in mountain
    # Silica sand is a coast-and-desert flux: not in the mountains either.
    assert "silica-sand" not in mountain

    swamp = {m.id for m in blacksmith.obtainable("mined", biome="swamp")}
    assert "bog-iron" in swamp and "iron-ore" not in swamp

    # And the excursion is declared, so the page can offer it.
    assert blacksmith.ACQUISITION["prospect"]["obtain"] == "mined"
    assert blacksmith.ACQUISITION["prospect"]["requires"] == "biome"


def test_harvesting_needs_a_carcass_and_matches_what_died():
    """Every harvested entry comes off something specific. With no creature named the
    excursion turns up nothing rather than everything — otherwise a player skins thin
    air and walks away with a phoenix ember."""
    assert blacksmith.obtainable("harvested") == []
    wyvern = {m.id for m in blacksmith.obtainable("harvested", creature="wyvern")}
    assert wyvern == {"wyvern-blood"}
    # Matched on fragments, because the GM types what they killed: "young red dragon"
    # has to find the dragon entries without a bestiary lookup.
    dragon = {m.id for m in blacksmith.obtainable("harvested",
                                                  creature="young red dragon")}
    assert "dragon-blood" in dragon and "dragonhide-grip" in dragon
    assert "wyvern-blood" not in dragon


def test_buying_and_gathering_are_offered_and_populated():
    """The other two excursions. Water is available on any ground — a material with no
    biomes listed is not the same as one whose biomes exclude here."""
    bought = blacksmith.obtainable("bought")
    assert len(bought) > 40 and all(m.price_gp for m in bought)
    anywhere = {m.id for m in blacksmith.obtainable("gathered", biome="desert")}
    assert "water" in anywhere
    assert "peat" not in anywhere          # peat is a bog thing
    assert "quenching-brine" not in anywhere   # and brine is a tideline thing
    assert {"gather", "buy"} <= set(blacksmith.ACQUISITION)
    # `salvage` left with the other carcass excursions (leatherworking lane C).
    assert "salvage" not in blacksmith.ACQUISITION


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
    finally:
        path.unlink(missing_ok=True)
        blacksmith.materials(refresh=True)
    assert "orichalch" not in blacksmith.materials()
