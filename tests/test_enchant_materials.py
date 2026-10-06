"""The enchanting data pass (lane D): essences, their phases, recipes and the price bands.

Each test names the defect it prevents, measured on the shelf before the pass
(build/enchanting 511cee9, 2026-10-05): 14 of 81 essences were `narrative` prose and none
said which book property it bound; bought essence prices were authored by eye (flaming 1,800
gp against the 3,000 gp the book charges to make the +1 it adds); no family named the time
of day it favours; the catalogue printed Ring of Protection +4 at caster level 20 where the
book prints 5 (and a creator level of 12); ten wondrous rows could not be found in any book;
and 35 of 112 wondrous rows sat outside their own price band.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

from rules import effectspec, materials, pricing, sky

ROOT = Path(__file__).resolve().parents[1]
ENCHANTER = ROOT / "content" / "materials" / "enchanter-materials.json"
ITEMS = ROOT / "content" / "materials" / "magic-items.json"


@pytest.fixture(scope="module")
def shelf():
    return materials.essences()


@pytest.fixture(scope="module")
def recipes():
    return materials.recipes()


def _raw(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- the essence documents -----------------------------------------------------------------

def test_the_shipped_shelf_loads_clean(shelf):
    """`essences()` validates on load and raises `BadEssences` on a shipped problem, so
    loading at all is the whole-shelf check. 92 essences: the 81 old ones and eleven new
    ones for the ring and wondrous bonuses no old essence granted (a Ring of Protection had
    no essence it could be made from), and arcane residue (lane E, at the lead's ask): what
    Unbind gives back, a quarter of the layer's motes, which no material carried until then
    so the residue lane F's `knowledge.unbind` names went nowhere."""
    assert len(shelf) == 93
    assert shelf["arcane-residue"]["motes"] == 1 and shelf["arcane-residue"]["grants"] is None
    for new in ("deflecting-essence", "barkhide-essence", "mantling-essence",
                "resistance-essence", "might-essence", "knack-essence"):
        assert new in shelf


def test_no_essence_is_narrative_and_each_has_three_traits(shelf):
    """14 of 81 essences were narrative before the pass ("Doubles the weapon's threat
    range", "Grants spell resistance 15"): a card line with nothing behind it. Every
    essence now has at least three discoverable traits and no narrative anywhere."""
    for mid, doc in shelf.items():
        assert len(materials.essence_traits(doc)) >= 3, mid
        for spec in doc["house"]:
            for nested in materials._walk(spec):
                assert nested.get("type") != "narrative", mid


def test_every_grant_resolves_to_lane_as_property_table(shelf):
    """Every `grants` names a property in content/rules/magic-properties.json (never an old
    mi- id) or an enhancement step, and `effectspec.bind` can build its documents."""
    for mid, doc in shelf.items():
        g = doc["grants"]
        if not g:
            continue
        assert not materials.grant_problems(g, doc["polarity"]), mid
        if g.get("property"):
            prop = effectspec.properties()[g["property"]]
            choice = dict(g.get("choice") or {})
            if prop.get("scaled"):
                choice["bonus"] = g.get("bonus") or prop["scaled"]["values"][0]
            if prop.get("choice") and not g.get("choice"):
                continue        # bane: the binder names the foe
            # A property whose whole effect is a rule a reader asks of its tag (dancing,
            # returning) binds to no documents; every other binds to some.
            assert effectspec.bind(prop, choice) or prop.get("reads_tag"), mid


# --- motes and prices -----------------------------------------------------------------------

# The book's making costs, stated here by hand (CRB magic weapons and armor; half the
# market price), independently of `materials.grant_motes`.
BOOK_MOTES = {
    "arcane-essence-i": 10, "arcane-essence-ii": 40, "arcane-essence-iii": 90,
    "arcane-essence-iv": 160, "arcane-essence-v": 250,            # (n² × 2,000) / 2 / 100
    "warding-essence-i": 5, "warding-essence-ii": 20, "warding-essence-iii": 45,
    "warding-essence-iv": 80, "warding-essence-v": 125,           # (n² × 1,000) / 2 / 100
    "flaming-essence": 30,      # +1 flaming over +1: (8,000 − 2,000) / 2 / 100
    "icy-burst-essence": 80,    # +2 over +1: (18,000 − 2,000) / 2 / 100
    "vorpal-essence": 350,      # +5 over +1: (72,000 − 2,000) / 2 / 100
    "fortification-light-essence": 15,   # armour +1 over +1: (4,000 − 1,000) / 2 / 100
    "shadow-essence": 19,       # 3,750 gp flat, halved and rounded up
    "resist-fire-essence": 90,  # 18,000 gp flat
    "deflecting-essence": 10,   # deflection +1: 1² × 2,000 / 2 / 100
}


def test_bought_motes_are_the_books_making_cost(shelf):
    """"Essences are the cost" (owner, round 1) and 1 mote = 100 gp of the book's making
    cost (round 4). Before the pass flaming cost 1,800 gp against a making cost of 3,000:
    the gold route was cheaper than the book."""
    for mid, motes in BOOK_MOTES.items():
        assert shelf[mid]["motes"] == motes, mid
        assert shelf[mid]["price_gp"] == motes * 100, mid


def test_a_plus_one_flaming_sword_costs_the_book_price_in_essences(shelf):
    """The worked example in docs/enchanting-review.md: a +1 flaming longsword is 8,000 gp
    market, 4,000 to make. Arcane Essence I (grants +1) and Flaming Essence (grants
    flaming) carry exactly 40 motes and cost exactly 4,000 gp."""
    pair = [shelf["arcane-essence-i"], shelf["flaming-essence"]]
    assert sum(e["motes"] for e in pair) * materials.MOTE_GP == (2 ** 2 * 2000) // 2
    assert sum(e["price_gp"] for e in pair) == 4000


def test_found_essences_are_never_sold(shelf):
    """A gathered or harvested essence carries no price (an absent price is "the world
    does not sell this", play/craft_views._price_cp); one with a price would sit on a
    counter at a number nobody derived."""
    for mid, doc in shelf.items():
        if doc["obtain"] != "bought":
            assert doc["price_gp"] in (None, "", 0), mid


def test_tier_is_the_band_of_the_motes_and_the_price_rule_holds(shelf):
    """The first draft kept lane A's property tiers and the price rule refused it: the
    exotic ghost touch essence at 3,000 gp under the rare Arcane Essence III at 9,000. An
    essence's tier is the band of the market value its motes carry."""
    for mid, doc in shelf.items():
        assert doc["tier"] == materials.essence_tier(doc["motes"]), mid
    rows = _raw(ENCHANTER)["materials"]
    assert pricing.material_price_problems(rows, "enchanter-materials.json") == []


def test_the_price_bands_are_the_owners():
    """Under 1,000 gp common, under 5,000 uncommon, under 20,000 rare, under 50,000
    exotic, then legendary (owner, 2026-10-05)."""
    assert [materials.tier_for_price(g) for g in (999, 1000, 4999, 5000, 19999, 20000,
                                                  49999, 50000)] == [
        "common", "uncommon", "uncommon", "rare", "rare", "exotic", "exotic", "legendary"]


# --- the validator's fences ---------------------------------------------------------------

def _flaming():
    return copy.deepcopy(materials.essences()["flaming-essence"])


def test_a_house_top_up_over_the_ceiling_is_refused():
    """House top-ups are ±1 common and uncommon, ±2 rare and exotic, ±3 legendary (plan
    §7.2): a +3 resistance on a rare essence is refused with the ceiling named."""
    doc = _flaming()
    doc["house"][0]["amount"] = 3
    assert any("at most ±2" in p for p in materials.essence_problems(doc))


def test_a_book_type_inside_a_top_up_is_refused():
    """An essence names book properties through `grants` and never carries their documents
    as a top-up. First held by "waits on lane C's reader"; when lane C's readers landed
    (2026-10-05) that refusal fell away and a keen crit_range top-up on a flaming essence
    passed the check. Top-ups are now an allow-list of small typed numbers."""
    doc = _flaming()
    doc["house"].append({"type": "crit_range", "multiply": 2, "house": True})
    assert any("is a crit_range; a top-up is one of" in p
               for p in materials.essence_problems(doc))


def test_narrative_and_dice_are_refused_in_a_top_up():
    doc = _flaming()
    doc["house"].append({"type": "narrative", "target": "glows", "house": True})
    doc["house"].append({"type": "damage", "dice": "1d6", "damage_type": "fire",
                         "lethality": "lethal", "trigger": "hit", "house": True})
    problems = materials.essence_problems(doc)
    assert any("narrative prose" in p for p in problems)
    assert any("flat number" in p for p in problems)


def test_a_mispriced_bought_essence_is_refused():
    doc = _flaming()
    doc["price_gp"] = 1800
    assert any("Set \"price_gp\" to 3000" in p for p in materials.essence_problems(doc))
    doc = _flaming()
    doc["motes"] = 18
    assert any("Raise \"motes\" to at least 30" in p for p in materials.essence_problems(doc))


def test_an_unknown_grant_is_refused_with_the_new_id_named():
    doc = _flaming()
    doc["grants"] = {"property": "mi-flaming"}
    assert any("old id of 'flaming'" in p for p in materials.essence_problems(doc))


# --- phases of the day ---------------------------------------------------------------------

def test_every_family_names_a_phase_of_the_day_with_a_reason():
    """The owner's ruling (round 4 point 10, round 5): phases of the day, never a planet,
    and the owner reviews the mapping, so each family says why."""
    fams = materials.families()
    assert not materials.family_problems(fams, shelf=materials.all())
    for name, fam in fams.items():
        assert fam["phase"] in sky.PHASES, name
        assert len(fam["why"]) > 20, name


def test_an_essence_takes_its_familys_phase(shelf):
    """"Each essence family names its phase": the owner's own examples hold (fire at noon,
    frost before dawn, the dead at midnight)."""
    assert shelf["flaming-essence"]["phase"] == "noon"
    assert shelf["frost-essence"]["phase"] == "dawn"
    assert shelf["ghost-residue"]["phase"] == "midnight"
    assert shelf["lich-dust"]["phase"] == "midnight"
    for mid, doc in shelf.items():
        assert doc["phase"] in sky.PHASES, mid


def test_an_unknown_phase_is_refused_with_the_phases_named():
    doc = _flaming()
    doc["phase"] = "mars"
    fams = {"fire": {"phase": "mars", "why": "x", "color": "#ffffff"}}
    problems = materials.essence_problems(doc, fams=fams)
    assert any("dawn, morning, noon, afternoon, dusk, night, midnight" in p
               for p in problems)


PLANETS = re.compile(r"(?<![a-z])(mars|saturn|jupiter|venus|mercury|neptune|uranus|pluto)"
                     r"(?![a-z])", re.I)


def test_no_planet_is_named_in_the_enchanting_data():
    """"This is not earth" (owner, round 4 point 10): the plan's first draft mapped fire to
    Mars and the dead to the Moon. Neither data file may name a planet anywhere."""
    for path in (ENCHANTER, ITEMS):
        found = PLANETS.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} names {sorted(set(found))}"


# --- the catalogue -------------------------------------------------------------------------

def test_the_catalogue_tiers_are_the_price_bands():
    """35 of 112 wondrous rows sat outside their own price band before the re-tier (a
    2,500 gp Ring of Climbing "common", a 25,000 gp Cloak of Resistance +5
    "legendary"). The rule is checked on load so it cannot drift."""
    rows = _raw(ITEMS)["materials"]
    assert materials.magic_item_tier_problems(rows) == []
    by_id = {r["id"]: r for r in rows}
    assert by_id["mi-ring-climbing"]["tier"] == "uncommon"
    assert by_id["mi-cloak-resistance-5"]["tier"] == "exotic"
    drifted = [dict(by_id["mi-ring-climbing"], tier="common")]
    assert any("Set \"tier\" to 'uncommon'" in p
               for p in materials.magic_item_tier_problems(drifted))


# Stated here by hand from the AoN pages (CRB rings, wondrous items and rods; Ultimate
# Equipment belts and headbands), independently of tools/enchant_data_pass.py, and compared
# as a whole: (price gp, caster level, creator level or None).
AON = {
    **{f"mi-ring-protection-{n}": (p, 5, 3 * n) for n, p in
       ((1, 2000), (2, 8000), (3, 18000), (4, 32000), (5, 50000))},
    **{f"mi-cloak-resistance-{n}": (p, 5, 3 * n) for n, p in
       ((1, 1000), (2, 4000), (3, 9000), (4, 16000), (5, 25000))},
    **{f"mi-amulet-natural-armor-{n}": (p, 5, 3 * n) for n, p in
       ((1, 2000), (2, 8000), (3, 18000), (4, 32000), (5, 50000))},
    **{f"mi-bracers-armor-{n}": (n * n * 1000, 7, 2 * n) for n in (1, 2, 4, 6, 8)},
    "mi-amulet-mighty-fists-1": (4000, 5, 3), "mi-amulet-mighty-fists-2": (16000, 5, 6),
    "mi-cloak-elvenkind": (2500, 3, None), "mi-eyes-eagle": (2500, 3, None),
    "mi-goggles-minute-seeing": (2500, 3, None), "mi-ring-climbing": (2500, 5, None),
    "mi-elixir-hiding": (250, 5, None), "mi-elixir-vision": (250, 2, None),
    "mi-elixir-swimming": (250, 2, None), "mi-glove-storing": (10000, 6, None),
    "mi-mantle-spell-resistance": (90000, 9, None), "mi-ring-mindshield": (8000, 3, None),
    "mi-crown-blasting-minor": (6480, 6, None), "mi-belt-dwarvenkind": (14900, 12, None),
    "mi-headband-mental-prowess": (10000, 12, None),
    "mi-belt-physical-perfection": (16000, 16, None),
    "mi-belt-tumbling": (800, 1, None),
    "mi-headband-alluring-charisma-cha-skill": (5100, 8, None),
    "mi-belt-mighty-hurling": (14000, 8, None),
    "mi-boots-speed": (12000, 10, None), "mi-scarab-protection": (38000, 18, None),
}


def test_catalogue_book_numbers_match_aon(recipes):
    """The catalogue folded the creator's level into the item's caster level: Ring of
    Protection +4 at CL 20 where the book prints CL 5 and "caster must be of a level at
    least three times the bonus" (12). 47 of the 102 sourced rows carried a wrong caster
    level, price, name, slot or prerequisite (docs/enchanting-review.md, "Book fixes"); a
    set comparison against the book, stated by hand above."""
    got = {rid: (int(recipes[rid]["price_gp"]), recipes[rid]["caster_level"],
                 recipes[rid]["creator_level"]) for rid in AON}
    assert got == AON


def test_the_goggles_of_minute_seeing_are_disable_device():
    """The old row gave the goggles +5 Perception; the book's lenses give +5 on Disable
    Device ("see much better than normal at distances of 1 foot or less")."""
    book = materials.recipe("mi-goggles-minute-seeing")["book"]
    assert [(d["type"], d["target"], d["amount"]) for d in book] == [
        ("skill_mod", "disable device", 5)]


UNSOURCED = {"mi-periapt-wisdom", "mi-vest-resistance", "mi-shirt-gliding",
             "mi-gauntlet-infinite-blades", "mi-cap-water-breathing",
             "mi-sandals-quiet-tread", "mi-bracelet-steady-hand", "mi-goggles-charming",
             "mi-shield-ring-arrow-deflection", "mi-headband-recall"}


def test_rows_not_in_the_book_are_retired_never_offered(recipes):
    """Ten wondrous rows ("Book: ...") could not be found on AoN's Core Rulebook, Ultimate
    Equipment or Advanced Player's Guide pages: a model's inventions. "Ground every name":
    they stay loadable for old saves and are never offered as recipes."""
    rows = {r["id"]: r for r in _raw(ITEMS)["materials"]}
    for rid in UNSOURCED:
        assert rows[rid]["retired"] is True, rid
        assert rid not in recipes, rid
    assert len(recipes) == 112 - len(UNSOURCED)


def test_no_recipe_is_narrative_and_each_can_be_made_from_the_shelf(recipes, shelf):
    """47 of 170 catalogue entries were narrative before the pass. Every recipe's book
    effects are typed now, and every essence it needs is one the shelf has: a recipe whose
    essence nobody could get would be a recipe nobody could make."""
    granted = {(d["grants"] or {}).get("property") for d in shelf.values()}
    families = {d["family"] for d in shelf.values()}
    for rid, doc in recipes.items():
        assert doc["book"], rid
        for spec in doc["book"]:
            for nested in materials._walk(spec):
                assert nested.get("type") != "narrative", rid
        for need in doc["essences"]:
            if need.get("grants") and need["grants"] != "enhancement":
                assert need["grants"] in granted, (rid, need)
            elif need.get("family"):
                assert need["family"] in families, (rid, need)
        assert doc["source"].startswith("https://legacy.aonprd.com/"), rid


def test_scaled_recipes_are_lane_as_documents(recipes):
    """Rings of protection, cloaks of resistance and the ability belts take their book
    documents from lane A's table through `effectspec.bind`, so the two tables cannot
    disagree about a +3 deflection."""
    ring = recipes["mi-ring-protection-3"]["book"]
    assert ring == effectspec.bind("deflection", {"bonus": 3})
    belt = recipes["mi-belt-strength-4"]["book"]
    assert belt == effectspec.bind("ability-strength", {"bonus": 4})


def test_vessels_are_retired_from_the_shelf():
    """Plan §7.3: a vessel is a real item record now, picked from the rack; the seven
    vessel rows stay loadable for old saves and say they are retired."""
    vessels = [d for d in materials.all().values() if d["kind"] == "vessel"
               and d["catalogue"] == materials.ENCHANT_CATALOGUE]
    assert len(vessels) == 7
    assert all(d["retired"] for d in vessels)


# --- homebrew ------------------------------------------------------------------------------

def test_a_broken_homebrew_essence_is_left_off_not_fatal(tmp_path, monkeypatch):
    """A shipped problem stops the load (`BadEssences`); a user's broken homebrew essence
    must not take the bench down, so it is left off the shelf. A sound one, with a family
    the table does not know, names its own phase (how a world's own essence would)."""
    from django.conf import settings

    hb = tmp_path / "homebrew" / "materials"
    hb.mkdir(parents=True)
    good = {"id": "marsh-light", "name": "Marsh Light", "kind": "essence",
            "tier": "common", "obtain": "gathered", "biomes": ["swamp"],
            "family": "marsh", "phase": "dusk", "polarity": "any", "motes": 2,
            "color": "#88cc88",
            "house": [{"type": "skill_mod", "target": "stealth", "amount": 1,
                       "bonus_type": "competence", "house": True}],
            "text": "A cold light over still water."}
    bad = dict(good, id="bad-light", name="Bad Light", phase="teatime")
    (hb / "marsh.json").write_text(json.dumps({"materials": [good, bad]}),
                                   encoding="utf-8")
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    loaded = materials.essences()
    assert "marsh-light" in loaded and loaded["marsh-light"]["phase"] == "dusk"
    assert "bad-light" not in loaded


# --- the review page -----------------------------------------------------------------------

def test_the_review_page_is_current():
    """docs/enchanting-review.md is generated from the data; a page that drifted from it
    would ask the owner to rule on numbers the game no longer uses."""
    try:
        subprocess.run(["git", "cat-file", "-e", "511cee9"], cwd=ROOT, check=True,
                       capture_output=True)
    except Exception:
        pytest.skip("the pre-pass commit is not in this checkout")
    path = ROOT / "tools" / "enchant_review.py"
    spec = importlib.util.spec_from_file_location("_enchant_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    current = (ROOT / "docs" / "enchanting-review.md").read_text(encoding="utf-8")
    assert current == mod.build(), "run python tools/enchant_review.py"
