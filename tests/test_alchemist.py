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
    would make Stabilize a dead method. Measured: 29 of the 137 materials are volatile
    when this was written, and the floor is set well below that so adding calm
    potion-components never quietly kills the rule."""
    volatile = [m for m in shipped if m.get("volatile")]
    assert len(volatile) >= 25


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


# --- potions that hold spells ----------------------------------------------------------


@pytest.fixture
def potions() -> list[dict]:
    return json.loads(
        Path("content/materials/alchemist-spell-potions.json")
        .read_text(encoding="utf-8"))["potions"]


@pytest.fixture
def spell_ids() -> set:
    return {s["id"] for s in json.loads(
        Path("content/spells/spells.json").read_text(encoding="utf-8"))["spells"]}


def test_every_potion_names_a_spell_the_app_actually_has(potions, spell_ids):
    """The "ground every name" rule, as a gate. A potion of a spell that does not
    resolve in content/spells/spells.json is a name the model invented and the app
    would carry as fact — and `holds_spell` is a cross-craft contract, so a bad id
    would break the enchanter's lookup rather than only this page's label.

    This test caught three real errors when the catalogue was written: the brief asked
    for `lesser-restoration`, `mage-armour` and `eagle-s-splendour`, and the corpus
    spells them `restoration-lesser`, `mage-armor` and `eagle-s-splendor`.
    """
    bad = [(p["id"], p["spell"]) for p in potions if p["spell"] not in spell_ids]
    for pid, spell in bad:
        print(f"{pid}: no spell {spell!r}")
    assert not bad, f"{len(bad)} potions name a spell that does not exist"


def test_the_potion_catalogue_covers_the_classics(potions):
    """Breadth, and the named examples from the brief specifically — a catalogue that
    quietly dropped enlarge person would have dropped the user's own example."""
    ids = {p["spell"] for p in potions}
    for must in ("enlarge-person", "cure-light-wounds", "bull-s-strength",
                 "mage-armor", "invisibility", "barkskin", "resist-energy",
                 "restoration-lesser", "eagle-s-splendor", "spider-climb",
                 "darkvision", "delay-poison", "magic-weapon"):
        assert must in ids, f"no potion of {must}"
    assert len(potions) >= 30, f"only {len(potions)} potions"
    assert {p["spell_level"] for p in potions} == {1, 2, 3}


def test_every_potion_effect_validates(potions):
    """Same gate as the materials: zero guessed specs. Where a spell's mechanic has no
    home in the vocabulary — lesser restoration's drinker-chosen ability, gaseous form
    — it is authored as `narrative` and narrated, never invented."""
    bad: list[str] = []
    for p in potions:
        for i, spec in enumerate(p.get("effects") or []):
            bad.extend(effectspec.validate(spec, f"{p['id']} effect {i + 1}"))
    for line in bad:
        print(line)
    assert not bad, f"{len(bad)} invalid potion effects"


def test_every_potion_material_is_on_the_shelf(potions):
    """A recipe that names a material nobody stocks can never be brewed, and would sit
    in the catalogue looking available forever."""
    bad = [(p["id"], m) for p in potions for m in p["materials"]
           if m not in alch.materials()]
    assert not bad, bad


def test_a_potion_cannot_lie_about_its_tier(potions):
    """The declared tier must be the tier the materials actually produce, because the
    tier is what gates who may brew it. A recipe claiming to be uncommon while holding
    an exotic solvent would advertise a level-2 potion that only a level-4 alchemist
    could ever make."""
    for p in potions:
        derived = max(alch.get(m).rank for m in p["materials"])
        assert derived == wc.tier_rank(p["tier"]), \
            f"{p['id']}: declared {p['tier']}, materials give {wc.TIERS[derived - 1]}"


def test_every_potion_recipe_can_actually_be_brewed(potions):
    """A recipe its own rules refuse is dead content that looks available forever.

    Caught two when this was written: `potion-of-endure-elements` (camphor + rectified
    spirits) and `oil-of-magic-weapon` (quicklime + rectified spirits) each hold two
    volatile materials and neither chain stabilized, so both were refused at every
    level — a potion nobody could ever make, sitting in the catalogue looking fine.
    Both now stabilize.

    Brewed at the level its tier implies: 1st- and 2nd-level potions at Alchemist 3
    (react is a level-3 method), 3rd-level potions at 4 (azoth is exotic).
    """
    at = {1: 3, 2: 3, 3: 4}
    bad = []
    for p in potions:
        chain = alch.Chain(methods=list(p["methods"]),
                           material_ids=list(p["materials"]))
        got = alch.preview(at[p["spell_level"]], chain)
        if got.problems:
            bad.append((p["id"], got.problems))
        elif got.output["holds_spell"] != p["spell"]:
            bad.append((p["id"], f"brewed but held {got.output['holds_spell']!r}"))
    for pid, why in bad:
        print(f"{pid}: {why}")
    assert not bad, f"{len(bad)} potions cannot be brewed by their own recipe"


def test_brewing_enlarge_person_yields_a_real_size_buff():
    """The user's own example, end to end. It must produce live specs the engine can
    apply — +2 Strength and -2 Dexterity as *size* modifiers, the attack and AC steps
    that come with growing — not a paragraph saying the drinker got bigger."""
    recipe = alch.spell_potion("potion-of-enlarge-person")
    got = alch.preview(3, alch.Chain(methods=list(recipe.methods),
                                     material_ids=list(recipe.materials)))
    assert not got.problems
    out = got.output
    assert out["holds_spell"] == "enlarge-person"
    assert out["caster_level"] == 1
    assert out["usable"] is True and out["how"] == ["drink"]

    by_target = {(s["type"], s.get("target")): s for s in out["specs"]}
    assert by_target[("ability_mod", "str")]["amount"] == 2
    assert by_target[("ability_mod", "str")]["bonus_type"] == "size"
    assert by_target[("ability_mod", "dex")]["amount"] == -2
    assert by_target[("combat_mod", "attack")]["amount"] == -1
    # And every one of them is a spec the engine can actually run.
    assert any(effectspec.executable(s) for s in out["specs"])


def test_a_potion_is_only_brewed_by_its_own_recipe():
    """Strict matching, on purpose: a near-miss must not quietly hand over a different
    potion. "You got blur because you were one reagent short of invisibility" is a bug
    nobody could write a report for."""
    recipe = alch.spell_potion("potion-of-invisibility")
    short = alch.preview(3, alch.Chain(methods=list(recipe.methods),
                                       material_ids=recipe.materials[:-1]))
    assert short.output["holds_spell"] is None


def test_an_ordinary_chain_holds_no_spell():
    """`holds_spell` is None rather than absent for everything else — the enchanter
    reads the key, and a missing key is a KeyError on their page."""
    got = alch.preview(3, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "naphtha", "clay-flask"]))
    assert got.output["holds_spell"] is None
    assert got.output["caster_level"] is None


def test_spell_potions_layer_homebrew(tmp_path, monkeypatch):
    """A homebrew potion just works — same overlay as materials, same reason."""
    from django.conf import settings

    home = tmp_path / "homebrew" / "materials"
    home.mkdir(parents=True)
    (home / "mine.json").write_text(json.dumps({"potions": [
        {"id": "potion-of-house-rules", "name": "Potion of House Rules",
         "spell": "jump", "spell_level": 1, "caster_level": 1, "tier": "uncommon",
         "how": ["drink"], "materials": ["rectified-spirits", "glass-vial"],
         "methods": ["dissolve", "seal"], "effects": []},
    ]}), encoding="utf-8")

    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(alch, "_POTIONS", None)
    got = alch.spell_potions()
    assert "potion-of-house-rules" in got
    assert "potion-of-enlarge-person" in got       # shipped set still underneath


# --- the dispatchable surface ----------------------------------------------------------


def test_chain_from_body_tolerates_a_half_empty_form():
    """The bench posts a form and the dispatcher hands the body straight here, so a
    missing key must become an empty list rather than a 500. The refusal belongs in
    `problems`, where the page can show it."""
    empty = alch.chain_from_body({})
    assert empty.methods == [] and empty.material_ids == []
    got = alch.preview(1, empty)
    assert "Nothing on the bench." in got.problems
    assert "No method chosen." in got.problems


def test_chain_from_body_reads_the_bench_form():
    body = {"methods": ["dissolve", "react", "seal"],
            "materials": ["Brimstone", " naphtha "], "name": "Firebomb",
            "stock": {"woundwort-tincture#1": 2}}
    chain = alch.chain_from_body(body)
    assert chain.methods == ["dissolve", "react", "seal"]
    assert chain.material_ids == ["brimstone", "naphtha"]
    assert chain.name == "Firebomb"
    # Crafted inputs are spent from a finite shelf, so they are counted, not merged.
    assert chain.stock_used == {"woundwort-tincture#1": 2}
    assert chain.every_material.count("woundwort-tincture#1") == 2


def test_the_crafters_bonus_is_intelligence_and_itemised():
    """Craft is Int-based in PF1e, which is the one substitution that makes an
    alchemist a different character from a herbalist rather than the same one with
    two shelves. Itemised because "+9" says nothing and "Alchemist 4, half level +3,
    Int +2" says which term to go and improve."""
    class Actor:
        level = 7

        def ability_mod(self, which):
            return {"int": 4, "wis": -1}[which]

    terms = alch.check_terms(Actor(), 4)
    assert [t["value"] for t in terms] == [4, 3, 4]
    assert terms[2]["label"] == "Intelligence"
    assert alch.check_bonus(Actor(), 4) == 11


def test_an_actor_turns_a_legality_check_into_odds():
    """Without an actor the preview answers "is this legal"; with one it answers
    "will I make it". The chance is 0 while any problem stands, so a page cannot
    show a tempting percentage on a chain that is refused."""
    class Actor:
        level = 6

        def ability_mod(self, which):
            return 3

    # Stabilized, because brimstone and naphtha are both volatile — an unstabilized
    # version of this chain is refused, and a refused chain has no odds to report.
    chain = _chain(["dissolve", "react", "stabilize", "seal"],
                   ["brimstone", "naphtha", "clay-flask"])
    bare = alch.preview(3, chain)
    assert not bare.problems
    assert bare.bonus == 0 and bare.terms == [] and bare.chance == 0

    withactor = alch.preview(3, chain, actor=Actor())
    assert withactor.bonus == 3 + 3 + 3
    assert 5 <= withactor.chance <= 95

    # Too low a level to work uncommon material: refused, and the percentage must not
    # tempt anybody with a number the chain cannot deliver.
    refused = alch.preview(1, chain, actor=Actor())
    assert refused.problems and refused.chance == 0


def test_the_result_dict_carries_everything_the_bench_needs():
    """The shared bench reads one shape from every craft. A key this track forgets is
    a KeyError on a page four crafts share."""
    got = alch.preview(3, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "naphtha", "clay-flask"])).as_dict()
    for key in ("name", "tier", "rank", "stages", "dc", "risky", "problems",
                "effects", "specs", "consumes", "output", "bonus", "terms", "chance"):
        assert key in got, f"Result.as_dict() is missing {key!r}"


def test_the_output_is_a_complete_inventory_item():
    """The output contract, in full — this is what makes a crafted thing usable from
    the play page's inventory rather than a line of text on a bench."""
    got = alch.preview(3, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "naphtha", "clay-flask"]))
    out = got.output
    for key in ("id", "name", "kind", "craft", "tier", "rank", "count", "effects",
                "specs", "from_materials", "usable", "how", "wearable", "slot",
                "holds_spell", "caster_level"):
        assert key in out, f"output is missing {key!r}"
    assert out["kind"] == "crafted" and out["craft"] == alch.TRACK_ID
    assert out["count"] == 1 and out["wearable"] is False and out["slot"] is None


@pytest.mark.parametrize("mats,expected", [
    # A vessel is what makes a thing throwable: the flask is the delivery.
    (["brimstone", "naphtha", "clay-flask"], ["throw"]),
    (["oil-of-vitriol", "lead-glass-vial"], ["throw"]),
    # Harmful with no vessel goes on a blade instead.
    (["saints-tallow", "rectified-spirits"], ["coat"]),
    # Nothing harmful in it: it is a draught.
    (["willow-charcoal", "distilled-water"], ["drink"]),
])
def test_how_an_item_is_used_is_read_off_what_is_in_it(mats, expected):
    """Alchemist's fire is thrown, grease is painted on, antitoxin is drunk — and the
    rule has to answer for chains nobody wrote down, so it is read off the vessel and
    the harm rather than declared per recipe."""
    got = alch.preview(5, _chain(["dissolve", "seal"], mats))
    assert got.output["how"] == expected


def test_what_the_chain_consumes_is_reported():
    got = alch.preview(3, _chain(["dissolve", "react", "seal"],
                                 ["brimstone", "brimstone", "naphtha", "clay-flask"]))
    assert got.consumes["brimstone"] == 2
    assert got.consumes["naphtha"] == 1


# --- acquisition and icons -------------------------------------------------------------


def test_every_material_declares_how_it_is_obtained(shipped):
    """The craft-action button is the single hub for obtaining materials, so a material
    with no `obtain` is one the hub can never offer — invisible, un-buyable, and
    impossible to notice from the bench."""
    ways = {"bought", "mined", "gathered", "harvested"}
    bad = [m["id"] for m in shipped if m.get("obtain") not in ways]
    assert not bad, f"{len(bad)} materials do not say where they come from: {bad[:8]}"


def test_acquisition_data_uses_the_shape_the_other_crafts_use(shipped):
    """Flat `obtain` with `biomes`/`from_creatures`/`price_gp` beside it, because the
    blacksmith, leatherworker and enchanter all landed there and one hub reads the whole
    shared shelf. This started as a nested dict here; the odd craft out conformed rather
    than making the hub learn two shapes."""
    for m in shipped:
        assert isinstance(m["obtain"], str), f"{m['id']}: obtain must be a plain word"


def test_bought_materials_carry_a_price_and_a_market(shipped):
    for m in shipped:
        if m["obtain"] == "bought":
            assert m.get("market"), f"{m['id']}: bought where?"
            assert int(m["price_gp"]) > 0, f"{m['id']}: no price"


def test_harvested_materials_name_their_creatures(shipped):
    """Named the way the leatherworker's `from_creatures` reads, so an excursion can
    match "the ankheg" in the scene against the sac it drops."""
    for m in shipped:
        if m["obtain"] == "harvested":
            assert m.get("from_creatures"), f"{m['id']}: harvested from what?"


def test_gathered_and_mined_materials_name_real_biomes(shipped):
    """A biome the world does not have is an excursion that can never fire."""
    from rules.biomes import BIOMES

    for m in shipped:
        if m["obtain"] in ("mined", "gathered"):
            biomes = m.get("biomes") or []
            assert biomes, f"{m['id']}: gathered where?"
            for b in biomes:
                assert b in BIOMES, f"{m['id']}: {b!r} is not a biome"


def test_no_material_id_is_claimed_by_two_crafts():
    """One shelf, four catalogues, and `load_dir` merges by id in filename order — so a
    duplicate id means the alphabetically-later craft silently wins.

    Measured when this was written: my `blessed-water` (uncommon solvent) was shadowed
    by the blacksmith's `blessed-water` (rare quenchant), which moved four potions up a
    tier and removed the reaction medium from three chains, with nothing anywhere
    reporting a problem. Mine were renamed to `font-water` and `standing-oak-bark`. The
    test is shelf-wide rather than mine-only because the next collision will not be
    mine either.
    """
    seen: dict[str, list[str]] = {}
    for path in Path("content/materials").glob("*-materials.json"):
        for m in json.loads(path.read_text(encoding="utf-8"))["materials"]:
            seen.setdefault(m["id"], []).append(path.stem)
    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not clashes, f"ids claimed by two crafts: {clashes}"


def test_a_sibling_crafts_shelf_entry_is_read_rather_than_crashing():
    """The shelf is shared: `materials()` loads all four catalogues. A craft whose
    entries this module cannot parse took the whole bench down with a ValueError on
    every chain, which is how the flat/nested mismatch was found."""
    shelf = alch.materials()
    assert len(shelf) > 300, "the shared shelf should hold every craft's catalogue"
    hide = shelf.get("deer-hide")                      # the leatherworker's
    assert hide is not None and hide.obtain_how == "harvested"
    assert "deer" in hide.from_creatures


def test_the_track_declares_what_excursions_it_offers():
    """The page asks what the track offers rather than knowing what alchemy is —
    which is what lets one hub serve four crafts."""
    assert set(alch.ACQUISITION) == {"market-run", "quarry", "field-gathering",
                                     "harvest-reagents"}
    kinds = {e["obtain"] for e in alch.ACQUISITION.values()}
    assert kinds == {"bought", "mined", "gathered", "harvested"}
    for entry in alch.ACQUISITION.values():
        assert entry["needs"] in ("market", "biome", "creature")
        assert entry["label"] and entry["blurb"]


def test_obtainable_filters_by_where_you_are_and_what_you_killed():
    """An ankheg acid sac comes off an ankheg the table actually killed; brimstone
    comes out of a mountain. The excursion is the question, this is the answer."""
    ankheg = alch.obtainable("harvested", creature="the ankheg")
    assert any(m.id == "ankheg-acid-sac" for m in ankheg)
    assert not any(m.id == "basilisk-eye" for m in ankheg)

    mountain = alch.obtainable("mined", biome="mountain")
    assert any(m.id == "brimstone" for m in mountain)
    assert not any(m.id == "rock-salt" for m in mountain)   # underground and coast

    # Shelf-wide on purpose: a market sells what it sells regardless of which bench
    # wanted it. Prices are asserted against this track's own catalogue, because a
    # sibling's pricing is the sibling's business.
    bought = alch.obtainable("bought")
    assert any(m.id == "quicksilver" for m in bought)
    mine = {m["id"] for m in json.loads(
        CATALOGUE.read_text(encoding="utf-8"))["materials"]}
    assert all(m.price_gp for m in bought if m.id in mine)


def test_every_kind_in_the_catalogue_has_a_glyph(shipped):
    """One shelf, four crafts: a kind with no glyph shows as a blank on a shared page,
    and a repeated one makes two different things look identical."""
    for kind in {m["kind"] for m in shipped}:
        assert kind in alch.KIND_GLYPH, f"no glyph for kind {kind!r}"
    assert len(set(alch.KIND_GLYPH.values())) == len(alch.KIND_GLYPH)
    # Herbalism's glyphs are reserved and must never appear here.
    assert not set(alch.KIND_GLYPH.values()) & {"🌿", "🍄", "🦴", "☠️"}


def test_every_method_has_bench_help(track):
    """`method_help` is what the bench shows beside the button. A method missing one
    is a button with no explanation on the page a beginner needs most."""
    data = json.loads(Path("content/world-classes/alchemist.json")
                      .read_text(encoding="utf-8"))
    help_ = data["method_help"]
    for method in track.unlocked_methods(track.max_level):
        assert method in help_, f"no method_help for {method!r}"
        for field in ("does", "needs", "for"):
            assert help_[method].get(field), f"{method}: empty {field!r}"
    # The prose descriptions stay: they are the rulebook voice, not the bench voice.
    assert set(data["method_descriptions"]) == set(help_)
