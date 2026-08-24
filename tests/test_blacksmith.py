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

def test_masterwork_requires_temper_and_a_finished_surface():
    """Masterwork is the book's DC-20 component made procedural: tempered steel and a
    finished working surface (hone or polish). One of the two alone is merely fine;
    neither is plain."""
    full = ["smelt", "forge", "quench", "temper", "hone"]
    r = blacksmith.preview(3, Chain("blacksmith", full,
                                    ["steel", "charcoal"], base="longsword"))
    assert r.quality == "masterwork"
    assert r.dc >= blacksmith.MASTERWORK_DC
    # PF1e's actual masterwork rule: +1 enhancement on attack rolls, never damage.
    assert {"type": "combat_mod", "amount": 1, "bonus_type": "enhancement",
            "target": "attack", "note": "(masterwork)"} in r.specs

    fine = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper"],
        ["steel", "charcoal"], base="longsword"))
    assert fine.quality == "fine"
    plain = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench"],
        ["steel", "charcoal"], base="longsword"))
    assert plain.quality == "plain"


def test_masterwork_is_reachable_at_blacksmith_3_for_the_enchanter():
    """The dead-end check, measured rather than assumed.

    `rules/enchanter.py` refuses every binding whose vessel is not masterwork — at
    Enchanter *1*, with the message "Commission one from the smith". The first version
    of this ladder also required fold or draw, which are Blacksmith 4, so the entire
    enchanting economy sat behind 140 MP of a track the enchanter may never have taken.
    Masterwork is DC 20 professional work in 1e, purchasable in any city, so it belongs
    with the professional methods at Blacksmith 3.

    Pinned on both vessels the enchanter is most likely to be handed: a longsword and a
    breastplate, at the level and DC the book says.
    """
    for base, weapon, armour in (("longsword", "longsword", None),
                                 ("breastplate", None, "breastplate")):
        r = blacksmith.preview(3, Chain(
            "blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
            ["steel", "charcoal"], base=base))
        assert r.problems == [], f"{base}: {r.problems}"
        assert r.quality == "masterwork"
        assert r.dc == 20, f"{base} came out DC {r.dc}"
        assert r.output["masterwork"] is True
        assert r.output["weapon"] == weapon
        assert r.output["armour"] == armour

    # And a Blacksmith 2 still cannot: temper is learned at 3, so the gate is a real
    # one rather than a formality.
    early = blacksmith.preview(2, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
        ["steel", "charcoal"], base="longsword"))
    assert any("Temper is learned at Blacksmith 3" in p for p in early.problems)


# --- the dispatch surface -----------------------------------------------------------------

def test_chain_from_body_parses_the_benchs_post():
    """One shape for all five crafts. Tolerant on purpose: a missing key is an empty
    chain, not an error, because `preview` is the place that says what is wrong with a
    chain in sentences and a parser that raised here would turn "you have not chosen a
    method yet" into a 500."""
    c = blacksmith.chain_from_body({
        "methods": ["smelt", "forge"], "materials": ["iron", "charcoal"],
        "name": "Test Blade", "base": "longsword",
    })
    assert c.track == "blacksmith"
    assert c.methods == ["smelt", "forge"]
    assert c.material_ids == ["iron", "charcoal"]
    assert c.name == "Test Blade" and c.base == "longsword"

    empty = blacksmith.chain_from_body({})
    assert empty.methods == [] and empty.material_ids == [] and empty.base == ""
    assert blacksmith.chain_from_body(None).methods == []

    # A plain HTML form with scripting off sends comma-joined strings; reading only the
    # list form would make the bench work only with JavaScript.
    typed = blacksmith.chain_from_body({"methods": "smelt, forge",
                                        "materials": "iron,charcoal"})
    assert typed.methods == ["smelt", "forge"]
    assert typed.material_ids == ["iron", "charcoal"]

    # Three things send the base item under three names.
    for key in ("base", "item", "weapon"):
        assert blacksmith.chain_from_body({key: "longsword"}).base == "longsword"


def test_stock_from_body_keeps_only_real_counts():
    """Junk in the stock dict must not become a phantom material the chain thinks the
    smith is carrying."""
    got = blacksmith.stock_from_body(
        {"stock": {"iron": 3, "charcoal": "2", "steel": 0, "bogus": "many"}})
    assert got == {"iron": 3, "charcoal": 2}
    assert blacksmith.stock_from_body({}) == {}


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


def test_an_actor_gets_a_bonus_and_a_chance_and_no_actor_does_not():
    """`preview` must keep working with actor=None — every rules test calls it that
    way — and must carry the itemised terms when a character is supplied."""
    class FakeActor:
        level = 8

        def ability_mod(self, which):
            return 3

    chain = Chain("blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
                  ["steel", "charcoal"], base="longsword")
    bare = blacksmith.preview(3, chain)
    assert bare.bonus == 0 and bare.terms == [] and bare.chance == 0

    withactor = blacksmith.preview(3, chain, actor=FakeActor())
    assert withactor.bonus == 10
    assert len(withactor.terms) == 3
    # DC 20 against +10 needs a 10: eleven faces of twenty.
    assert withactor.chance == 55

    # A chain with problems is never a percentage — the button is greyed, not gambled.
    broken = blacksmith.preview(1, Chain("blacksmith", ["quench"], ["iron"]),
                                actor=FakeActor())
    assert broken.chance == 0


def test_as_dict_carries_everything_the_bench_needs():
    """The dispatch contract: a bench that renders five crafts through one template
    reads these keys and no others. A missing key is a blank panel with no error."""
    r = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
        ["steel", "charcoal"], base="longsword"))
    d = r.as_dict()
    for key in ("name", "tier", "rank", "stages", "dc", "risky", "problems",
                "effects", "specs", "consumes", "output", "bonus", "terms", "chance"):
        assert key in d, f"as_dict is missing {key}"


# --- the output contract ------------------------------------------------------------------

def test_the_output_is_an_equippable_inventory_item():
    """A forged sword that cannot be wielded is a paragraph. The output names the real
    weapons.json key and a `tables.SLOTS` slot, so the pack and the equip screen can act
    on it without knowing which craft made it."""
    from rules.tables import SLOTS

    r = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench", "temper", "hone"],
        ["cold-iron", "charcoal"], base="longsword"))
    out = r.output
    assert out["kind"] == "crafted" and out["craft"] == "blacksmith"
    assert out["count"] == 1 and out["tier"] == "uncommon"
    assert out["weapon"] == "longsword" and out["armour"] is None
    assert out["slot"] == "hands" and out["slot"] in SLOTS
    assert out["wearable"] is True and out["usable"] is False and out["how"] == []
    assert "cold-iron" in out["from_materials"]
    assert out["masterwork"] is True
    # Every spec on the finished item must be one the engine can actually read.
    for spec in out["specs"]:
        assert effectspec.validate(spec) == []


def test_armour_and_shields_land_in_their_own_slots():
    """Three slots a forge can fill, and they are the vocabulary `tables.SLOTS` owns —
    not invented words that would silently equip nothing."""
    from rules.tables import SLOTS

    armour = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench"],
        ["steel", "charcoal"], base="breastplate"))
    assert armour.output["slot"] == "armor" and armour.output["armour"] == "breastplate"
    assert armour.output["weapon"] is None

    shield = blacksmith.preview(3, Chain(
        "blacksmith", ["smelt", "forge", "quench"],
        ["steel", "charcoal"], base="heavy-shield"))
    assert shield.output["slot"] == "shield"
    for slot in ("armor", "shield", "hands"):
        assert slot in SLOTS


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
    assert {"salvage", "gather", "buy"} <= set(blacksmith.ACQUISITION)


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
