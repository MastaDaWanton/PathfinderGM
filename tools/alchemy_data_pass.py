"""The alchemy data pass (docs/alchemy-revamp-plan.md §5 and §16.9, lane D), as a record.

What it writes:

- `content/materials/alchemist-materials.json`: on every one of the 138 materials, the
  alchemy document's fields (docs/alchemy-contracts.md §3): `product` (what it puts in a
  bottle, each trait a complete typed effect with an `essence` and a `route`), `working`
  (how it behaves at the bench), `mishap` (volatile materials only: what a roll failed by 5
  or more does to the alchemist), `toxic` (toxic-to-handle materials only: what working it
  unprotected does), `color` (the [r, g, b] the stage draws it in) and, where a printed
  number was used, `book` and `book_source`. Ids, names, kinds, tiers and prices do not
  change. The pre-revamp `effects` list was kept for the old chain bench until alchemy
  lane F retired it (2026-10-06); the pass now removes it (`RETIRED_FIELDS`), and adds
  the rows in `NEW_MATERIALS` (the tool family's wooden rod).
- `content/materials/alchemist-spell-potions.json`: the 44 potions' narrative lines typed
  (plan §16.9). Ids, spells and caster levels do not change (owner, Q10.2); a recipe
  with no drinkable vessel among its materials gains one (`RECIPE_VESSEL`, lane F).
- `content/ingredients/herbs-and-parts.json`: an `essence` on every effect of the 63
  hybrid herbs, and nothing else (contracts §1 row D).

Two kinds of number, kept apart:

- **Book** numbers, read by hand from the page each one cites: the five creature venoms
  (Core Rulebook poisons table; Bestiary 2's crag linnorm), the fire beetle's glow, the
  arsenic DC on realgar, itching powder's DC and penalty on itchweed, the thunderstone's
  Fortitude 15 and an hour's deafness on storm quartz. Marked `"book": true` on the trait
  and exempt from the house ceilings.
- **House** numbers, drafted here inside `materials.alchemy_problems`' fences (tier
  ceilings on flat numbers and on dice, at least three properties, a drawback on anything
  that puts a trait in a bottle, no narrative, essence and route on every product trait,
  `volatile` with a mishap, `toxic_to_handle` with a toxic document) for the owner's
  review in docs/alchemy-review.md (`tools/alchemy_review.py` writes it).

Every row is validated before anything is written, through the same functions the loaders
and the tests use, and the run refuses to write if any has a problem. Dry run by default:

    python tools/alchemy_data_pass.py            # validate and report
    python tools/alchemy_data_pass.py --apply    # validate, then write the three files

Idempotent: the alchemy fields are replaced, never appended, and the herb essences are
re-derived from the effects each run.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import effectspec, materials, pricing  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from alchemy_essence import essence_of  # noqa: E402

MAT_DIR = ROOT / "content" / "materials"
ALCHEMIST = MAT_DIR / "alchemist-materials.json"
POTIONS = MAT_DIR / "alchemist-spell-potions.json"
HERBS = ROOT / "content" / "ingredients" / "herbs-and-parts.json"

# --- sources for the book numbers (read 2026-10-06) -------------------------------------------
CRB_POISONS = "https://legacy.aonprd.com/coreRulebook/glossary.html (Poison, Table 13-5)"
CRB_GOODS = "https://legacy.aonprd.com/coreRulebook/equipment.html (Special Substances and Items)"
B1_FIRE_BEETLE = "https://legacy.aonprd.com/bestiary/vermin.html#beetle-fire"
B2_CRAG_LINNORM = ("https://www.d20pfsrd.com/bestiary/monster-listings/dragons/linnorm/"
                   "linnorm-crag/ (Bestiary 2, crag linnorm: poison)")
UE_ITCHING = "https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Itching%20powder"

# --- building blocks ----------------------------------------------------------------------------

def D(amount, unit="round"):
    return {"amount": amount, "unit": unit}


def T(spec: dict, route: str, **kw) -> dict:
    """A product trait: the effect, its route, its essence (the rule's unless given), and
    grade 1 — every house trait starts at the weakest grade; the bench adds grades."""
    out = dict(spec)
    out.update(kw)
    out["route"] = route
    out.setdefault("grade", 1)
    out["essence"] = essence_of(out)
    return out


def bad(spec: dict) -> dict:
    """A drawback: a cost to whoever uses the product (contracts §2.1)."""
    spec = dict(spec)
    spec["drawback"] = True
    return spec


def dmg(dice, kind, route="struck", **kw):
    return T({"type": "damage", "dice": dice, "damage_type": kind, "lethality": "lethal"},
             route, **kw)


def cond(target, amount, unit="round", route="struck", **kw):
    return T({"type": "apply_condition", "target": target, "duration": D(amount, unit)},
             route, **kw)


def gate(save, dc, fail, route="struck", **kw):
    return T({"type": "save_gate", "target": save, "dc": dc, "on_failure": fail}, route,
             **kw)


def mod(kind, target, amount, bonus="alchemical", dur=(10, "minute"), route="ingest",
        **kw):
    spec = {"type": kind, "target": target, "amount": amount, "bonus_type": bonus}
    if dur:
        spec["duration"] = D(*dur)
    return T(spec, route, **kw)


def res(energy, amount, route="ingest", dur=(1, "hour"), **kw):
    return T({"type": "resistance", "target": energy, "amount": amount,
              "duration": D(*dur)}, route, **kw)


def sick(route="ingest", rounds=1):
    """The commonest drawback: a mouthful of something the body rejects."""
    return bad(cond("sickened", rounds, route=route))


def W(*traits) -> list[dict]:
    return [{"type": "working", "trait": t} for t in traits]


def mishap(dice, kind, note):
    """What a roll failed by 5 or more on a step with this volatile input does to the
    alchemist (plan §8.2). House dice, under the material's tier ceiling."""
    return {"type": "damage", "dice": dice, "damage_type": kind, "lethality": "lethal",
            "recipient": "self", "note": note}


def toxic(dc, ability="con", dice="1", note=""):
    """What working a toxic-to-handle material unprotected does (plan §8.4): a Fortitude
    save or a point of an ability, the shape the plan names."""
    return {"type": "save_gate", "target": "fort", "dc": dc, "recipient": "self",
            "on_failure": [{"type": "ability_damage", "target": ability, "dice": dice}],
            "note": note or "working it bare-handed, without a mask and gloves or a fume hood"}


def book(spec: dict, source: str) -> dict:
    spec = dict(spec)
    spec["book"] = True
    spec["cite"] = source
    return spec


# --- the plan, material by material --------------------------------------------------------------
#
# `product`, `working`, `mishap`, `toxic`, `color`. A material with no product traits is
# an apparatus class (vessel, catalyst, a neutral medium, or prima materia's wild trait):
# it works at the bench and never reaches the bottle, and Q7.1's "one a drawback" is a
# reagent's rule ("at least three discoverable traits per reagent"). Neutral media
# (distilled water, rectified spirits) carry the work and no trait of their own, as the
# Witcher's alcohol base does (prior art §3): a medium with an essence would put that
# essence into the signature of every potion brewed in it.
#
# Colours are [r, g, b] in 0..1, the liquid or powder the stage draws (UI plan §4).

PLAN: dict[str, dict] = {
    # ---------------------------------------------------------------- common
    "brimstone": dict(
        product=[dmg("1d4", "fire"), sick()],
        working=W("solid", "volatile", "combustible"),
        mishap=mishap("1d4", "fire", "the charge flashes in the crucible"),
        color=[0.86, 0.78, 0.22]),
    "saltpetre": dict(
        product=[dmg("1d4", "sonic"),
                 mod("save_mod", "fort", 1, dur=(1, "hour"), note="against disease")],
        working=W("solid", "volatile"),
        mishap=mishap("1d4", "fire", "the nitre takes the flame and roars"),
        color=[0.93, 0.93, 0.9]),
    "willow-charcoal": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), note="against ingested poison")],
        working=W("solid", "combustible"),
        color=[0.12, 0.12, 0.12]),
    "quicklime": dict(
        # Caustic, not hot: a lime burn is the alkali's, and the alkali flask it is the
        # base of deals acid (UE p.107), so its burn is acid too.
        product=[dmg("1d3", "acid"),
                 mod("combat_mod", "damage", 1, dur=(1, "minute"), route="external",
                     note="the coated weapon; the lime scalds where it bites")],
        working=W("solid", "volatile"),
        mishap=mishap("1d4", "fire", "it slakes in a sweating hand"),
        color=[0.95, 0.95, 0.92]),
    "slaked-lime": dict(
        product=[res("acid", 2, route="skin")],
        working=W("solid", "slow_to_dissolve"),
        color=[0.96, 0.96, 0.94]),
    "natron": dict(
        product=[T({"type": "remove_condition", "target": "bleed"}, "skin"),
                 mod("save_mod", "fort", 1, dur=(1, "hour"),
                     note="against heat, cold and thirst"),
                 sick()],
        working=W("solid"),
        color=[0.9, 0.88, 0.8]),
    "rock-salt": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), note="against disease"),
                 sick()],
        working=W("solid"),
        color=[0.92, 0.9, 0.88]),
    "alum": dict(
        product=[T({"type": "remove_condition", "target": "bleed"}, "skin"),
                 mod("skill_mod", "heal", 1, dur=(1, "hour"), route="skin",
                     note="to staunch bleeding"),
                 sick()],
        working=W("solid"),
        color=[0.95, 0.95, 0.97]),
    "green-vitriol": dict(
        product=[dmg("1d3", "acid"), sick()],
        working=W("solid", "corrosive"),
        color=[0.45, 0.75, 0.5]),
    "blue-vitriol": dict(
        product=[gate("fort", 12, [{"type": "apply_condition", "target": "sickened",
                                    "duration": D("1d4")}])],
        working=W("solid", "corrosive"),
        color=[0.2, 0.45, 0.9]),
    "pine-pitch": dict(
        product=[cond("entangled", "2d4")],
        working=W("solid", "combustible"),
        color=[0.45, 0.28, 0.1]),
    "birch-tar": dict(
        product=[mod("save_mod", "fort", 2, dur=(1, "hour"), route="skin",
                     note="against disease carried by a wound")],
        working=W("liquid", "combustible"),
        color=[0.1, 0.08, 0.06]),
    "iron-filings": dict(
        product=[mod("combat_mod", "ac", 1, bonus="natural armour", essence="change",
                     note="the skin takes on a little of the iron"),
                 mod("combat_mod", "damage", 1, note="the iron's heft in the blow"),
                 sick()],
        working=W("solid", "slow_to_dissolve"),
        color=[0.35, 0.33, 0.32]),
    "lead-dust": dict(
        product=[gate("fort", 12, [{"type": "ability_damage", "target": "str",
                                    "dice": "1"}], route="area"),
                 bad(T({"type": "ability_damage", "target": "con", "dice": "1"}, "ingest"))],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(12, note="lead breathed at the bench: the trembling hands of the old "
                             "trade"),
        color=[0.55, 0.55, 0.58]),
    "powdered-chalk": dict(
        product=[mod("skill_mod", "climb", 2, dur=(1, "hour"), route="skin",
                     note="chalked hands")],
        working=W("solid", "stabilizer", "slow_to_dissolve"),
        color=[0.97, 0.97, 0.95]),
    "lamp-black": dict(
        product=[T({"type": "concealment", "miss_chance": 20, "duration": D(1)}, "area"),
                 mod("skill_mod", "linguistics", 2,
                     note="the ink remembers every hand it wrote"),
                 sick()],
        working=W("solid", "combustible"),
        color=[0.05, 0.05, 0.05]),
    "tallow": dict(
        product=[mod("skill_mod", "escape artist", 2, route="skin", note="greased")],
        working=W("solid", "combustible"),
        color=[0.95, 0.9, 0.75]),
    "distilled-water": dict(
        product=[],
        working=W("liquid", "solvent:water", "stabilizer"),
        color=[0.85, 0.92, 0.98]),
    "strong-spirits": dict(
        product=[mod("save_mod", "will", 1, bonus="morale", note="against fear"),
                 bad(mod("ability_mod", "dex", -1, bonus="untyped"))],
        working=W("liquid", "solvent:alcohol", "volatile", "combustible"),
        mishap=mishap("1d3", "fire", "the spirit catches with a blue flame"),
        color=[0.95, 0.93, 0.85]),
    "white-vinegar": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), route="skin",
                     note="against disease")],
        working=W("liquid", "solvent:vinegar", "corrosive"),
        color=[0.97, 0.96, 0.9]),
    "lamp-oil": dict(
        product=[dmg("1d3", "fire")],
        working=W("liquid", "solvent:oil", "volatile", "combustible"),
        mishap=mishap("1d3", "fire", "the oil takes the lamp's flame"),
        color=[0.85, 0.7, 0.3]),
    "olive-oil": dict(
        product=[mod("skill_mod", "escape artist", 2, route="skin", note="oiled skin")],
        working=W("liquid", "solvent:oil", "light_sensitive"),
        color=[0.6, 0.65, 0.2]),
    "turpentine": dict(
        product=[dmg("1d3", "fire"), sick(route="inhale")],
        working=W("liquid", "solvent:oil", "volatile", "combustible"),
        mishap=mishap("1d3", "fire", "the fumes take a flame across the bench"),
        color=[0.9, 0.85, 0.6]),
    "lye-water": dict(
        product=[dmg("1d3", "acid")],
        working=W("liquid", "solvent:water", "corrosive"),
        color=[0.85, 0.85, 0.7]),
    "brine": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), route="skin",
                     note="against disease carried by a wound")],
        working=W("liquid", "solvent:water", "corrosive"),
        color=[0.8, 0.85, 0.9]),
    "brewers-yeast": dict(
        product=[], working=W("catalyst", "solid", "light_sensitive"),
        color=[0.85, 0.75, 0.5]),
    "mother-of-vinegar": dict(
        product=[], working=W("catalyst", "liquid", "corrosive"),
        color=[0.7, 0.6, 0.4]),
    "rennet": dict(
        product=[], working=W("catalyst", "solid", "light_sensitive"),
        color=[0.8, 0.7, 0.6]),
    "clay-flask": dict(product=[], working=W("shatters", "fireproof", "solid"),
                       color=[0.7, 0.45, 0.3]),
    # The tool family's vessel (alchemy lane F, 2026-10-06): lane D's pass found no material
    # with the `stick` trait, so the tool family (sunrod, tindertwig, smokestick, plan §12.1)
    # had no vessel and none of the three could be bottled. A whittled rod: the book's
    # tindertwig and smokestick are wooden sticks, and a sunrod is a rod (CRB, Goods and
    # Services). Combustible, because it is wood; free at a counter, as water is.
    "wooden-rod": dict(product=[], working=W("stick", "combustible", "solid"),
                       color=[0.55, 0.4, 0.25]),
    "glass-vial": dict(product=[], working=W("drinkable", "solid", "light_sensitive"),
                       color=[0.85, 0.92, 0.95]),
    "waxed-bladder": dict(product=[], working=W("bursts", "solid", "combustible"),
                          color=[0.8, 0.7, 0.5]),
    "stoneware-pot": dict(product=[], working=W("struck", "fireproof", "solid"),
                          color=[0.55, 0.5, 0.45]),
    "beeswax": dict(
        product=[res("acid", 1, route="skin")],
        working=W("solid", "combustible"),
        color=[0.95, 0.8, 0.35]),
    "cork-and-wick": dict(
        product=[dmg("1d2", "fire")],
        working=W("solid", "combustible"),
        color=[0.75, 0.6, 0.4]),
    "oilcloth-wrap": dict(
        product=[], working=W("solid", "combustible", "lead_lined"),
        color=[0.6, 0.55, 0.35]),
    "fullers-earth": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), note="against ingested poison"),
                 mod("skill_mod", "acrobatics", 1, route="skin", essence="grace",
                     note="sure footing on a slick floor"),
                 mod("combat_mod", "cmd", 1, route="skin", essence="might",
                     note="against a trip, on a sure footing")],
        working=W("solid", "stabilizer", "slow_to_dissolve"),
        color=[0.75, 0.7, 0.55]),
    "fire-beetle-gland": dict(
        product=[book(T({"type": "light", "radius_ft": 10, "duration": D("1d6", "day")},
                        "external"), B1_FIRE_BEETLE),
                 sick()],
        working=W("solid"),
        color=[0.95, 0.35, 0.15]),
    "skunk-musk-gland": dict(
        product=[gate("fort", 13, [{"type": "apply_condition", "target": "sickened",
                                    "duration": D("1d4")}], route="area"),
                 sick(route="inhale")],
        working=W("liquid"),
        color=[0.6, 0.6, 0.4]),
    "camphor": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), route="inhale",
                     note="against disease and inhaled poison"),
                 # Camphor's cooling, as frost (a cold that holds heat off): the second
                 # essence the potion of endure elements needs from its old recipe. Every
                 # other pair its ingredients carried was another potion's signature
                 # (antiplague, mage armor, protection from energy), measured 2026-10-06.
                 res("fire", 2, route="skin", essence="frost",
                     note="its cooling vapour against heat")],
        working=W("solid", "volatile"),
        mishap=mishap("1d3", "fire", "the camphor fumes take light"),
        color=[0.95, 0.95, 0.95]),
    "gum-arabic": dict(
        product=[mod("skill_mod", "stealth", 2),
                 mod("skill_mod", "disguise", 1, note="it holds an illusion together"),
                 sick()],
        working=W("solid"),
        color=[0.9, 0.82, 0.6]),
    "talc": dict(
        product=[mod("skill_mod", "perception", 2),
                 mod("skill_mod", "escape artist", 2, route="skin",
                     note="small and slippery as the flour itself"),
                 mod("skill_mod", "disguise", 1, route="skin", note="a dusted, pale face"),
                 sick(route="inhale")],
        working=W("solid"),
        color=[0.97, 0.97, 0.97]),
    "standing-oak-bark": dict(
        product=[mod("combat_mod", "ac", 1, bonus="natural armour"),
                 mod("skill_mod", "disguise", 1, note="skin gone rough as bark"),
                 bad(mod("ability_mod", "dex", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.45, 0.35, 0.25]),
    "licorice-root": dict(
        product=[T({"type": "speed", "target": "land", "amount": 5,
                    "duration": D(10, "minute")}, "ingest"),
                 mod("skill_mod", "acrobatics", 1, note="a lighter step"),
                 bad(mod("ability_mod", "wis", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.35, 0.2, 0.1]),
    "river-reed": dict(
        product=[T({"type": "permission", "target": "Breathe water freely.",
                    "tag": "breathe_water", "duration": D(1, "minute")}, "ingest")],
        working=W("solid", "combustible"),
        color=[0.5, 0.65, 0.35]),
    "fine-gauze": dict(
        product=[mod("skill_mod", "escape artist", 1, route="skin", essence="change",
                     note="slips through as a vapour does"),
                 mod("skill_mod", "fly", 1, note="it drifts")],
        working=W("solid", "combustible"),
        color=[0.92, 0.9, 0.85]),
    "bull-hairs": dict(
        product=[mod("ability_mod", "str", 2),
                 bad(mod("ability_mod", "int", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.3, 0.2, 0.15]),
    "cat-fur": dict(
        product=[mod("ability_mod", "dex", 2), mod("combat_mod", "attack", 1),
                 bad(mod("ability_mod", "wis", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.8, 0.6, 0.35]),
    "bear-hairs": dict(
        product=[mod("ability_mod", "con", 2),
                 T({"type": "temp_hp", "dice": "1d4", "duration": D(10, "minute")},
                   "ingest"),
                 bad(mod("ability_mod", "dex", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.35, 0.25, 0.18]),
    "eagle-feathers": dict(
        product=[mod("ability_mod", "cha", 2), mod("skill_mod", "fly", 2)],
        working=W("solid", "combustible"),
        color=[0.55, 0.4, 0.25]),
    "fox-hairs": dict(
        product=[mod("ability_mod", "int", 2),
                 bad(mod("ability_mod", "wis", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.85, 0.4, 0.15]),
    "owl-feathers": dict(
        product=[mod("ability_mod", "wis", 2), mod("skill_mod", "perception", 1),
                 bad(mod("ability_mod", "dex", -1, bonus="untyped"))],
        working=W("solid", "combustible"),
        color=[0.6, 0.5, 0.4]),
    "grasshopper-legs": dict(
        product=[mod("skill_mod", "acrobatics", 2, note="to jump"),
                 mod("ability_mod", "str", 1, note="the spring in its legs"), sick()],
        working=W("solid"),
        color=[0.5, 0.6, 0.25]),
    "cellar-spider": dict(
        product=[mod("skill_mod", "climb", 2), sick()],
        working=W("solid"),
        color=[0.4, 0.35, 0.3]),
    "mistletoe-sprig": dict(
        product=[T({"type": "permission", "target": "Leave no trail.",
                    "tag": "pass_without_trace", "duration": D(10, "minute")}, "ingest"),
                 mod("skill_mod", "acrobatics", 1, note="owing the earth no footprint"),
                 sick()],
        working=W("solid"),
        color=[0.75, 0.85, 0.6]),
    "cured-leather-scrap": dict(
        product=[mod("combat_mod", "ac", 1, bonus="armour")],
        working=W("solid", "combustible"),
        color=[0.5, 0.33, 0.2]),
    # ---------------------------------------------------------------- uncommon
    "quicksilver": dict(
        product=[T({"type": "speed", "target": "land", "amount": 5,
                    "duration": D(10, "minute")}, "ingest"),
                 bad(T({"type": "ability_damage", "target": "con", "dice": "1"}, "ingest"))],
        working=W("liquid", "toxic_to_handle"),
        toxic=toxic(14, note="quicksilver worked over heat without a mask and gloves: "
                             "its price is paid by the alchemist, never the target"),
        color=[0.8, 0.82, 0.85]),
    "oil-of-vitriol": dict(
        product=[dmg("1d6", "acid")],
        working=W("liquid", "solvent:acid", "corrosive"),
        color=[0.75, 0.7, 0.4]),
    "aqua-fortis": dict(
        product=[dmg("1d4", "acid"),
                 bad(mod("skill_mod", "disguise", -2, bonus="untyped", dur=(1, "day"),
                         route="skin", note="the warning-yellow stain on the skin"))],
        working=W("liquid", "solvent:acid", "corrosive"),
        color=[0.95, 0.85, 0.4]),
    "phosphorus": dict(
        product=[dmg("1d4", "fire"),
                 T({"type": "light", "radius_ft": 0, "raised_ft": 5,
                    "duration": D(1, "hour")}, "external")],
        working=W("solid", "volatile", "combustible", "toxic_to_handle"),
        mishap=mishap("1d6", "fire", "the open air is enough to light it"),
        toxic=toxic(13, note="phosphorus handled bare: the old match-makers' jaw"),
        color=[0.95, 0.95, 0.8]),
    "sal-ammoniac": dict(
        product=[mod("skill_mod", "perception", 1, route="inhale",
                     note="the pungent spirit clears the head"),
                 sick(route="inhale")],
        working=W("solid"),
        color=[0.93, 0.93, 0.9]),
    "sal-volatile": dict(
        product=[T({"type": "remove_condition", "target": "dazed"}, "inhale"),
                 mod("save_mod", "will", 1, route="inhale", note="against sleep"),
                 mod("save_mod", "will", 2, route="inhale", essence="binding",
                     note="against hold and paralysis"),
                 bad(cond("dazzled", 1, route="eyes"))],
        working=W("solid"),
        color=[0.95, 0.95, 0.92]),
    "antimony-regulus": dict(
        product=[mod("save_mod", "fort", 2, dur=(1, "hour"), note="against ingested poison"),
                 sick()],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(13),
        color=[0.6, 0.62, 0.68]),
    "realgar": dict(
        product=[gate("fort", 13, [{"type": "ability_damage", "target": "con",
                                    "dice": "1d2"}], route="area",
                      note="arsenic smoke; the book's arsenic is Fort DC 13, 1d2 Con")],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(12),
        color=[0.85, 0.25, 0.15]),
    "cinnabar": dict(
        product=[mod("skill_mod", "disguise", 2, dur=(1, "hour"), route="skin",
                     note="vermilion paint"),
                 bad(T({"type": "ability_damage", "target": "con", "dice": "1"}, "ingest"))],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(13),
        color=[0.85, 0.15, 0.12]),
    "verdigris": dict(
        product=[dmg("1d3", "acid")],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(12),
        color=[0.3, 0.7, 0.55]),
    "naphtha": dict(
        product=[dmg("1d6", "fire")],
        working=W("liquid", "solvent:oil", "volatile", "combustible"),
        mishap=mishap("1d6", "fire", "it ignites at a harsh word"),
        color=[0.7, 0.55, 0.25]),
    "rectified-spirits": dict(
        product=[],
        working=W("liquid", "solvent:alcohol", "volatile"),
        mishap=mishap("1d4", "fire", "the spirit flashes off the bench"),
        color=[0.95, 0.95, 0.95]),
    "storm-quartz": dict(
        product=[gate("fort", 15, [{"type": "apply_condition", "target": "deafened",
                                    "duration": D(1, "hour")}], route="area",
                      note="the thunderstone's own numbers (CRB)"),
                 dmg("1d4", "sonic")],
        working=W("solid", "volatile"),
        mishap=mishap("1d4", "sonic", "it cracks with a report that boxes the ears"),
        color=[0.75, 0.78, 0.85]),
    "smoke-resin": dict(
        product=[T({"type": "manifest", "what": "thick grey smoke", "terrain": "obscuring",
                    "shape": "square", "size": 10, "duration": D(1, "minute")}, "area"),
                 sick(route="inhale")],
        working=W("solid", "combustible"),
        color=[0.5, 0.48, 0.45]),
    "itchweed-floss": dict(
        # The book's DC 12 at impact (UE p.107); its "-2 on attack rolls, saving throws,
        # skill checks, and ability checks until washed off" is sickened's penalties, and
        # 10 minutes stands in for "until washed off" — lane E's itching powder core reads
        # it the same way, so the floss and the powder agree.
        product=[book(gate("fort", 12, [{"type": "apply_condition", "target": "sickened",
                                         "duration": D(10, "minute")}], route="struck",
                           essence="decay", note="maddening itch until washed off"),
                      UE_ITCHING),
                 bad(mod("combat_mod", "attack", -1, bonus="untyped", route="skin",
                         note="handling the floss"))],
        working=W("solid"),
        color=[0.8, 0.78, 0.7]),
    "ankheg-acid-sac": dict(
        product=[dmg("1d6", "acid")],
        working=W("liquid", "corrosive"),
        color=[0.6, 0.75, 0.3]),
    "shocker-lizard-node": dict(
        product=[dmg("1d6", "electricity")],
        working=W("solid", "volatile"),
        mishap=mishap("1d6", "electricity", "the node discharges into the hand"),
        color=[0.55, 0.75, 0.95]),
    "giant-frog-mucus": dict(
        product=[gate("ref", 15, [{"type": "apply_condition", "target": "entangled",
                                   "duration": D("2d4")}])],
        working=W("liquid", "light_sensitive"),
        color=[0.65, 0.8, 0.45]),
    "adder-venom-gland": dict(
        product=[book(gate("fort", 11, [{"type": "ability_damage", "target": "con",
                                         "dice": "1d2"}],
                           note="black adder venom"), CRB_POISONS),
                 mod("save_mod", "fort", 1, dur=(1, "hour"), essence="ward",
                     note="against poison: the cure is taught by the poison")],
        working=W("liquid", "toxic_to_handle"),
        toxic=toxic(11, note="venom on a cut finger"),
        color=[0.85, 0.85, 0.6]),
    "silver-salt": dict(
        product=[mod("save_mod", "fort", 2, dur=(1, "hour"), essence="ward",
                     note="against disease: disease does not argue with silver")],
        working=W("solid", "light_sensitive"),
        color=[0.88, 0.88, 0.92]),
    "bitter-aloes": dict(
        product=[mod("save_mod", "fort", 1, dur=(1, "hour"), note="against ingested poison"),
                 gate("fort", 11, [{"type": "apply_condition", "target": "sickened",
                                    "duration": D(1)}], note="the purgative, thrown"),
                 sick()],
        working=W("solid"),
        color=[0.55, 0.45, 0.2]),
    "slick-jelly": dict(
        product=[gate("ref", 10, [{"type": "apply_condition", "target": "prone",
                                   "duration": D(1)}], route="area", essence="grace",
                      note="the floor it coats"),
                 mod("skill_mod", "escape artist", 2, dur=(1, "hour"), route="skin")],
        working=W("liquid", "combustible"),
        color=[0.75, 0.8, 0.7]),
    "lodestone-powder": dict(
        product=[], working=W("catalyst", "solid", "slow_to_dissolve"),
        color=[0.25, 0.25, 0.28]),
    "quick-match-cord": dict(
        product=[dmg("1d4", "fire")],
        working=W("solid", "volatile", "combustible"),
        mishap=mishap("1d4", "fire", "the cord runs faster than a shout"),
        color=[0.8, 0.75, 0.6]),
    "iron-flask": dict(product=[], working=W("drinkable", "fireproof", "solid"),
                       color=[0.35, 0.35, 0.38]),
    "lead-glass-vial": dict(product=[], working=W("drinkable", "warded", "lead_lined"),
                            color=[0.6, 0.62, 0.6]),
    "brass-casing": dict(product=[], working=W("struck", "fireproof", "solid"),
                         color=[0.8, 0.65, 0.3]),
    "wintergreen-essence": dict(
        product=[mod("save_mod", "fort", 2, dur=(1, "hour"), route="skin",
                     note="against fatigue and exhaustion", essence="vigour"),
                 sick(rounds="1d4")],
        working=W("liquid"),
        color=[0.75, 0.9, 0.8]),
    "oil-of-cloves": dict(
        product=[mod("save_mod", "will", 2, dur=(1, "hour"), route="skin",
                     note="against pain effects", essence="ward"),
                 bad(mod("skill_mod", "sleight of hand", -2, bonus="untyped", route="skin",
                         note="numb fingers"))],
        working=W("liquid"),
        color=[0.65, 0.4, 0.2]),
    "dragons-blood-resin": dict(
        product=[mod("skill_mod", "disguise", 2, dur=(1, "hour"), route="skin")],
        working=W("solid", "combustible"),
        color=[0.65, 0.08, 0.08]),
    "powdered-silver": dict(
        product=[mod("combat_mod", "ac", 1, bonus="deflection",
                     note="it refuses the profane"),
                 mod("skill_mod", "perception", 1),
                 T({"type": "strikes_as", "target": "silver", "duration": D(1, "minute")},
                   "external"),
                 T({"type": "light", "radius_ft": 0, "raised_ft": 5,
                    "duration": D(1, "hour")}, "external",
                   note="it glints where nothing should be: the outline of the unseen")],
        working=W("solid", "slow_to_dissolve"),
        color=[0.75, 0.76, 0.78]),
    "agate-chip": dict(
        product=[T({"type": "sense", "target": "low_light", "duration": D(10, "minute")},
                   "ingest")],
        working=W("solid", "slow_to_dissolve"),
        color=[0.7, 0.55, 0.45]),
    "font-water": dict(
        product=[T({"type": "heal", "dice": "1d4", "lethality": "lethal"}, "ingest"),
                 mod("save_mod", "will", 1, bonus="morale", note="against fear"),
                 bad(T({"type": "damage", "dice": "1", "damage_type": "positive",
                        "lethality": "lethal", "when": {"target": {"type": "undead"}}},
                       "ingest", note="it scalds the dead who drink it"))],
        working=W("liquid", "solvent:water"),
        color=[0.85, 0.9, 1.0]),
    "holy-parchment": dict(
        product=[mod("combat_mod", "ac", 1, bonus="deflection")],
        working=W("solid", "combustible"),
        color=[0.92, 0.88, 0.75]),
    # ---------------------------------------------------------------- rare
    "alkahest": dict(
        product=[dmg("2d6", "acid")],
        working=W("liquid", "solvent:acid", "volatile", "corrosive"),
        mishap=mishap("2d6", "acid", "it finds a way out of the vessel"),
        color=[0.85, 0.9, 0.7]),
    "aqua-regia": dict(
        product=[dmg("1d8", "acid"),
                 T({"type": "object_damage", "dice": "1d6", "damage_type": "acid",
                    "item": "metal armour or weapon"}, "struck",
                   note="the struck creature's metal gear (the metal tag)")],
        working=W("liquid", "solvent:acid", "corrosive", "light_sensitive"),
        color=[0.95, 0.65, 0.2]),
    "white-phosphorus": dict(
        product=[dmg("2d4", "fire"),
                 T({"type": "burning", "dice": "1d4", "damage_type": "fire", "rounds": 1,
                    "save": "ref", "dc": 15, "smother_bonus": 2}, "struck")],
        working=W("solid", "volatile", "combustible", "toxic_to_handle"),
        mishap=mishap("2d4", "fire", "it ignites on air and sticks while it burns"),
        toxic=toxic(15),
        color=[0.98, 0.98, 0.9]),
    "cockatrice-wattle": dict(
        product=[gate("fort", 12, [{"type": "apply_condition", "target": "staggered",
                                    "duration": D("1d2")}])],
        working=W("solid", "toxic_to_handle"),
        toxic={"type": "save_gate", "target": "fort", "dc": 12, "recipient": "self",
               "on_failure": [{"type": "apply_condition", "target": "staggered",
                               "duration": D(1)}],
               "note": "the joints stiffen in the hand that grinds it"},
        color=[0.8, 0.3, 0.25]),
    "dragon-bile": dict(
        product=[dmg("2d6", "fire")],
        working=W("liquid", "volatile", "corrosive"),
        mishap=mishap("2d6", "fire", "the dragon's element leaves the jar"),
        color=[0.9, 0.45, 0.1]),
    "frostworm-chill-gland": dict(
        product=[dmg("2d6", "cold"),
                 bad(T({"type": "damage", "dice": "1d3", "damage_type": "cold",
                        "lethality": "lethal"}, "skin", note="it never quite warms up"))],
        working=W("solid"),
        color=[0.7, 0.85, 1.0]),
    "salamander-ash": dict(
        product=[res("fire", 3), dmg("1d6", "fire"),
                 bad(T({"type": "vulnerability", "target": "cold",
                        "duration": D(1, "hour")}, "ingest",
                       note="the salamander's own weakness"))],
        working=W("solid"),
        color=[0.45, 0.4, 0.38]),
    "winter-wolf-humour": dict(
        product=[res("cold", 3),
                 bad(T({"type": "vulnerability", "target": "fire",
                        "duration": D(1, "hour")}, "ingest",
                       note="the winter wolf's own weakness"))],
        working=W("liquid"),
        color=[0.6, 0.8, 0.95]),
    "gray-ooze-core": dict(
        product=[dmg("2d4", "acid"),
                 T({"type": "object_damage", "dice": "1d6", "damage_type": "acid",
                    "item": "metal armour or weapon"}, "struck",
                   note="the struck creature's metal gear (the metal tag)")],
        working=W("liquid", "corrosive"),
        color=[0.5, 0.52, 0.5]),
    "ghost-salt": dict(
        product=[dmg("1d6", "negative"),
                 T({"type": "temp_hp", "dice": "1d4", "duration": D(10, "minute")},
                   "ingest")],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(14, ability="wis", note="cold to the soul of whoever grinds it"),
        color=[0.8, 0.85, 0.9]),
    "sunmetal-filings": dict(
        product=[dmg("1d6", "positive", when={"target": {"type": "undead"}},
                     note="harms only undead; the living feel warmth"),
                 mod("save_mod", "will", 1, bonus="morale", note="against fear"),
                 mod("combat_mod", "attack", 1, bonus="morale")],
        working=W("solid", "slow_to_dissolve"),
        color=[1.0, 0.85, 0.4]),
    "essence-of-ether": dict(
        product=[gate("fort", 13, [{"type": "apply_condition", "target": "staggered",
                                    "duration": D("1d4")}], route="area")],
        working=W("liquid", "volatile", "combustible"),
        mishap=mishap("2d4", "fire", "the vapour finds the lamp"),
        color=[0.9, 0.92, 0.95]),
    "philosophers-wool": dict(
        product=[], working=W("catalyst", "stabilizer", "solid"),
        color=[0.97, 0.97, 0.97]),
    "mithral-dust": dict(
        product=[], working=W("catalyst", "pure", "solid"),
        color=[0.85, 0.88, 0.95]),
    "everfrost-salt": dict(
        product=[dmg("1d6", "cold"), res("fire", 2, route="skin"),
                 bad(T({"type": "damage", "dice": "1d3", "damage_type": "cold",
                        "lethality": "lethal"}, "ingest", note="frost in the throat"))],
        working=W("solid"),
        color=[0.75, 0.9, 1.0]),
    "wyvern-venom-gland": dict(
        product=[book(gate("fort", 17, [{"type": "ability_damage", "target": "con",
                                         "dice": "1d4"}], note="wyvern poison"),
                      CRB_POISONS)],
        working=W("liquid", "toxic_to_handle"),
        toxic=toxic(15),
        color=[0.5, 0.6, 0.3]),
    "troll-marrow": dict(
        product=[T({"type": "fast_healing", "amount": 1, "duration": D(5)}, "ingest"),
                 bad(mod("ability_mod", "cha", -2, bonus="untyped", dur=(1, "hour"),
                         note="it keeps trying to be a troll"))],
        working=W("solid"),
        color=[0.5, 0.55, 0.35]),
    "pyre-gel": dict(
        product=[dmg("1d6", "fire"),
                 T({"type": "burning", "dice": "1d6", "damage_type": "fire", "rounds": 1,
                    "save": "ref", "dc": 15, "smother_bonus": 2}, "struck")],
        working=W("liquid", "volatile", "combustible"),
        mishap=mishap("2d4", "fire", "it clings to the sleeve and burns there"),
        color=[0.9, 0.5, 0.15]),
    "drakes-breath-sac": dict(
        product=[dmg("2d4", "fire", route="area")],
        working=W("liquid", "volatile"),
        mishap=mishap("2d4", "fire", "the bladder spends its breath at the bench"),
        color=[0.95, 0.55, 0.2]),
    "crystal-retort": dict(product=[], working=W("apparatus", "pure", "solid"),
                           color=[0.9, 0.95, 1.0]),
    "salamander-glass-flask": dict(product=[], working=W("shatters", "fireproof", "solid"),
                                   color=[0.85, 0.5, 0.3]),
    "warded-phial": dict(product=[], working=W("drinkable", "warded", "solid"),
                         color=[0.8, 0.82, 0.88]),
    "quenching-clay": dict(
        product=[res("fire", 2, route="skin")],
        working=W("solid", "stabilizer", "slow_to_dissolve"),
        color=[0.5, 0.5, 0.52]),
    "saints-tallow": dict(
        product=[T({"type": "damage", "dice": "1d4", "damage_type": "positive",
                    "lethality": "lethal", "trigger": "hit",
                    "when": {"target": {"type": "undead"}}}, "external", essence="vigour",
                   note="the coated blade, against undead only")],
        working=W("solid", "combustible"),
        color=[0.98, 0.95, 0.8]),
    # A catalyst that also carries traits, because lane E's formulae read its purity
    # (cure moderate wounds is {vigour, purity}, lesser restoration {purity, might}) and
    # its old recipes had nothing else to give it. Never spent; whether a catalyst's
    # traits enter every batch it sits in is lane F's rule to state (open rows).
    "unicorn-horn-shaving": dict(
        product=[T({"type": "remove_condition", "target": "sickened"}, "ingest"),
                 T({"type": "ability_restore", "target": "str", "dice": "1"}, "ingest",
                   essence="might", note="it mends what was wasted")],
        working=W("catalyst", "pure", "solid", "slow_to_dissolve"),
        color=[0.97, 0.95, 0.98]),
    # ---------------------------------------------------------------- exotic
    "phlogiston": dict(
        product=[dmg("3d6", "fire")],
        working=W("liquid", "volatile", "combustible"),
        mishap=mishap("3d6", "fire", "the fire-principle gets loose"),
        color=[0.95, 0.65, 0.15]),
    "azoth": dict(
        product=[T({"type": "heal", "dice": "2d8", "lethality": "lethal"}, "ingest"),
                 T({"type": "remove_condition", "target": "nauseated"}, "ingest"),
                 mod("save_mod", "fort", 2, bonus="resistance", dur=(1, "hour"))],
        working=W("liquid", "solvent:alcohol", "volatile", "toxic_to_handle"),
        mishap=mishap("2d6", "acid", "the restless liquid eats at the bench"),
        toxic=toxic(16, note="quicksilver's wilder cousin, and the same slow tax"),
        color=[0.85, 0.85, 0.95]),
    "fire-elemental-ember": dict(
        product=[dmg("3d6", "fire"), res("fire", 3, dur=(10, "minute"))],
        working=W("solid", "volatile"),
        mishap=mishap("3d6", "fire", "a knot of the plane of fire comes undone"),
        color=[1.0, 0.45, 0.1]),
    "bottled-thunderhead": dict(
        product=[dmg("3d6", "electricity"), dmg("1d6", "sonic")],
        working=W("liquid", "volatile"),
        mishap=mishap("3d6", "electricity", "weather, indoors, at you"),
        color=[0.45, 0.5, 0.65]),
    "umbral-distillate": dict(
        product=[book(gate("fort", 17, [{"type": "ability_drain", "target": "str",
                                         "dice": "1"},
                                        {"type": "ability_damage", "target": "str",
                                         "dice": "1d2"}], note="shadow essence"),
                      CRB_POISONS),
                 T({"type": "concealment", "miss_chance": 20, "duration": D(1, "minute")},
                   "ingest")],
        working=W("liquid", "light_sensitive", "toxic_to_handle"),
        toxic=toxic(17, ability="str"),
        color=[0.08, 0.06, 0.12]),
    "demon-ichor": dict(
        product=[dmg("2d6", "acid"),
                 T({"type": "bleed", "amount": 1}, "struck",
                   note="wounds it opens scar black and heal slow")],
        working=W("liquid", "volatile", "corrosive"),
        mishap=mishap("2d6", "acid", "it eats what it touches out of spite"),
        color=[0.35, 0.05, 0.1]),
    "angel-tears": dict(
        product=[T({"type": "heal", "dice": "3d6", "lethality": "lethal"}, "ingest"),
                 T({"type": "remove_condition", "target": "sickened"}, "ingest"),
                 bad(cond("dazzled", 1, route="eyes", note="a light the eyes were not "
                                                         "made for"))],
        working=W("liquid"),
        color=[0.9, 0.95, 1.0]),
    "ectoplasm-residuum": dict(
        product=[T({"type": "strikes_as", "target": "ghost_touch",
                    "duration": D(1, "minute")}, "external")],
        working=W("liquid", "light_sensitive"),
        color=[0.75, 0.9, 0.85]),
    "void-salt": dict(
        product=[dmg("2d6", "cold"), res("fire", 3, route="skin")],
        working=W("solid", "toxic_to_handle"),
        toxic=toxic(16),
        color=[0.2, 0.2, 0.35]),
    "star-iron-dust": dict(
        product=[mod("combat_mod", "damage", 1, dur=(1, "hour")),
                 mod("combat_mod", "attack", 1, dur=(1, "hour"))],
        working=W("solid", "slow_to_dissolve"),
        color=[0.4, 0.4, 0.5]),
    "purple-worm-venom": dict(
        product=[book(gate("fort", 24, [{"type": "ability_damage", "target": "str",
                                         "dice": "1d3"}], note="purple worm poison"),
                      CRB_POISONS)],
        working=W("liquid", "toxic_to_handle"),
        toxic=toxic(18, ability="str"),
        color=[0.45, 0.2, 0.5]),
    "remorhaz-thermal-gland": dict(
        product=[dmg("3d6", "fire")],
        working=W("solid", "volatile"),
        mishap=mishap("3d6", "fire", "it still thinks it is inside the worm"),
        color=[1.0, 0.75, 0.4]),
    "genie-breath-phial": dict(product=[], working=W("struck", "warded", "fireproof"),
                               color=[0.85, 0.7, 0.35]),
    "adamantine-crucible": dict(product=[], working=W("apparatus", "fireproof", "warded"),
                                color=[0.3, 0.3, 0.32]),
    # ---------------------------------------------------------------- legendary
    "prima-materia": dict(
        product=[],
        working=W("wild", "volatile", "solid"),
        mishap=mishap("4d6", "force", "it becomes, briefly, something that explodes"),
        color=[0.6, 0.55, 0.6]),
    "phoenix-ash": dict(
        product=[T({"type": "heal", "dice": "4d6", "lethality": "lethal"}, "ingest"),
                 T({"type": "remove_condition", "target": "fatigued"}, "ingest")],
        working=W("solid", "volatile"),
        mishap=mishap("4d6", "fire", "the pyre remembers it is a pyre"),
        color=[1.0, 0.6, 0.2]),
    "philosophers-mercury": dict(
        product=[], working=W("catalyst", "liquid", "toxic_to_handle"),
        toxic=toxic(20),
        color=[0.85, 0.75, 0.9]),
    "dragon-heart-blood": dict(
        product=[dmg("4d6", "fire"), mod("ability_mod", "str", 2, dur=(1, "hour"))],
        working=W("liquid", "volatile"),
        mishap=mishap("4d6", "fire", "centuries of banked fire, at the bench"),
        color=[0.6, 0.05, 0.05]),
    "linnorm-venom": dict(
        product=[book(gate("fort", 24, [{"type": "damage", "dice": "2d6",
                                         "damage_type": "fire", "lethality": "lethal"},
                                        {"type": "ability_drain", "target": "con",
                                         "dice": "1d4"}], note="crag linnorm poison"),
                      B2_CRAG_LINNORM)],
        working=W("liquid", "toxic_to_handle"),
        toxic=toxic(20),
        color=[0.3, 0.5, 0.25]),
    "world-egg-shell": dict(product=[], working=W("apparatus", "warded", "pure"),
                            color=[0.95, 0.93, 0.85]),
    "quintessence": dict(
        product=[T({"type": "temp_hp", "dice": "20", "source": "quintessence",
                    "duration": D(1, "hour")}, "ingest"),
                 bad(cond("dazed", 1, route="ingest", note="the fifth element's weight"))],
        working=W("liquid"),
        color=[0.95, 0.95, 1.0]),
    "tarrasque-humour": dict(
        product=[T({"type": "fast_healing", "amount": 4, "duration": D(1, "minute")},
                   "ingest"),
                 bad(mod("ability_mod", "int", -2, bonus="untyped", dur=(1, "minute"),
                         note="it does not accept that anything has happened"))],
        working=W("liquid"),
        color=[0.4, 0.45, 0.3]),
    "starfall-core": dict(
        product=[dmg("4d6", "fire")],
        working=W("solid", "volatile"),
        mishap=mishap("4d6", "fire", "a very small apocalypse"),
        color=[1.0, 0.9, 0.6]),
    "orichalcum-grains": dict(
        product=[], working=W("catalyst", "pure", "solid"),
        color=[0.9, 0.6, 0.3]),
}

# The named job of a catalyst that is never spent (plan §5.8, §9), as the trait's note.
# PROPOSED for the owner (docs/alchemy-review.md, open rows): only philosopher's mercury's
# is the plan's; the others are this pass's drafts. Lane F reads the note's job, if any.
CATALYST_JOBS = {
    "philosophers-mercury": "Transmute: one unit makes one, not two for one (plan §9)",
    "orichalcum-grains": "proposed: an experiment that fits several formulae is the one "
                         "the alchemist names, if it is within reach",
    "unicorn-horn-shaving": "proposed: strips one drawback in the step, as Filter does",
    "mithral-dust": "proposed: widens the step's band (plan §5.5) and the check is "
                    "rolled twice, the better kept (pure)",
    "philosophers-wool": "proposed: widens the step's band and calms one volatile input "
                         "(it is a stabilizer too)",
}

# Texts whose words the new mechanics contradict, rewritten so the description follows
# the mechanics (plan §5.10 step 5, the owner's herb rule). Every other text already says
# what the material now does, and is left in its author's words.
TEXTS = {
    "philosophers-wool": (
        "Snow-white flakes that drift up from burning zinc — the old texts thought it wool "
        "from a hidden sheep. It seeds crystallisation and quiets a reaction's temper "
        "without joining it: a catalyst, never spent, that calms one volatile input in the "
        "step it sits in."),
    "unicorn-horn-shaving": (
        "A curl of alicorn, given by a living unicorn or taken from one that died unhunted "
        "— the distinction matters, and the shaving knows. It purifies what it is stirred "
        "through and mends what was wasted, and is never itself spent."),
    "lead-dust": (
        "Sweet, soft, heavy and slowly ruinous. Thrown as a choking cloud it weakens whoever "
        "breathes it, and swallowed it poisons the drinker; it costs the alchemist who "
        "works it unmasked — the trembling hands of the old trade are lead's signature, "
        "not age's."),
    "quicksilver": (
        "Living metal that pools and runs. A draught of it quickens the step and poisons "
        "the blood together; worked bare-handed over heat it costs the alchemist, never "
        "the target — the classic slow ruin of the trade, and the classic reward for "
        "mastering it."),
    "font-water": (
        "Water sanctified in a font and drawn off in a silver dipper. It is the medium "
        "every kind draught is built in, and carries a little healing of its own; the dead "
        "who drink it are scalded."),
    "distilled-water": (
        "Water with nothing in it, which is rarer than it sounds. The default medium: a "
        "reaction happens in it and it adds nothing of its own to the bottle."),
    "rectified-spirits": (
        "Spirits distilled past drinkability into a pure working solvent. Extracts essences "
        "whole and vanishes from the finished work without a trace of itself: it carries "
        "no trait into the bottle."),
    "sunmetal-filings": (
        "Filings of temple-forged sunmetal, warm in the hand at midnight. Anathema to the "
        "unliving: thrown, they burn the dead and do nothing to the living; drunk, the "
        "warmth steadies the nerve."),
    "fire-beetle-gland": (
        "The luminous organ of a fire beetle, still glowing for days after the beetle has "
        "stopped needing it: ten feet of steady red light. The cold heart of a sunrod, and "
        "the striker-paste of a tindertwig."),
    "drakes-breath-sac": (
        "The breath-bladder of a fire drake, tied off full. Punctured, it spends the "
        "drake's last breath all at once — a burst of flame that catches everyone in it."),
}

# The note lane D's first run wrote, replaced (not appended to) by the one below now that
# `effects` is gone.
ALCHEMIST_NOTE_WAS = (
    "\n\nThe alchemy revamp (2026-10-06, docs/alchemy-revamp-plan.md §5, lane D, "
    "tools/alchemy_data_pass.py): every material now carries the alchemy document's fields "
    "(docs/alchemy-contracts.md §3) — `product` (what it puts in a bottle: typed effects, "
    "each with an `essence`, a `route` and a `grade`, `drawback: true` where it costs the "
    "user), `working` (how it behaves at the bench), `mishap` (volatile materials: what a "
    "roll failed by 5 or more does to the alchemist), `toxic` (toxic-to-handle materials: "
    "what working it unprotected does) and `color`. `rules/materials.py` reads `product` "
    "first; `effects` is the pre-revamp list the old chain bench reads until it retires, "
    "and nothing new reads it. House numbers are the owner's to review in "
    "docs/alchemy-review.md.")
ALCHEMIST_NOTE_ADD = (
    "\n\nThe alchemy revamp (2026-10-06, docs/alchemy-revamp-plan.md §5, lanes D and F, "
    "tools/alchemy_data_pass.py): every material carries the alchemy document's fields "
    "(docs/alchemy-contracts.md §3) — `product` (what it puts in a bottle: typed effects, "
    "each with an `essence`, a `route` and a `grade`, `drawback: true` where it costs the "
    "user), `working` (how it behaves at the bench), `mishap` (volatile materials: what a "
    "roll failed by 5 or more does to the alchemist), `toxic` (toxic-to-handle materials: "
    "what working it unprotected does) and `color`. The pre-revamp `effects` lists retired "
    "with the old chain bench (lane F). House numbers are the owner's to review in "
    "docs/alchemy-review.md.")


# --- the 44 potions: their narrative lines typed (plan §16.9) -----------------------------------
#
# Each entry replaces the potion's narrative effects (in order) with these documents; a
# `None` drops a narrative whose content the potion's other lines already carry. Durations
# are the potion's own, at its caster level. A permission's `target` keeps the words the
# card prints; its `tag` is what is granted (effectspec.PERMISSIONS names each reader).

def _perm(words, tag, dur):
    return {"type": "permission", "target": words, "tag": tag, "duration": dur}


POTION_TYPING: dict[str, list] = {
    "potion-of-enlarge-person": [_perm("One size larger: space and natural reach 10 ft, "
                                       "gear grows with the wearer.", "size_larger",
                                       D(1, "minute"))],
    "potion-of-reduce-person": [_perm("One size smaller: space 2-1/2 ft, natural reach "
                                      "0 ft, gear shrinks with the wearer.", "size_smaller",
                                      D(1, "minute"))],
    "potion-of-protection-from-evil": [
        _perm("Blocks mental control.", "ward_mind_control", D(1, "minute")),
        _perm("Bars bodily contact by summoned creatures.", "ward_summoned_contact",
              D(1, "minute"))],
    "potion-of-endure-elements": [_perm("Comfortable between -50 and 140 degrees "
                                        "Fahrenheit, with no Fortitude saves.",
                                        "endure_elements", D(24, "hour"))],
    "potion-of-comprehend-languages": [_perm("Understands any spoken or written language; "
                                             "no ciphers or secret writing.",
                                             "comprehend_languages", D(10, "minute"))],
    "potion-of-pass-without-trace": [_perm("Leaves no tracks, trail or scent.",
                                           "pass_without_trace", D(1, "hour"))],
    # Invisibility (CRB): "If the subject attacks any creature, however, the spell ends."
    # `ends_when` is the effect's own end, the shape class abilities already use
    # (engine payload `ends_when`); lane C's consumable door forwards it.
    "potion-of-invisibility": [{"type": "apply_condition", "target": "invisible",
                                "duration": D(3, "minute"),
                                "ends_when": {"acts": ["attack", "cast_offensive"]}}],
    # Blur (CRB): "attacks against the subject have a 20% miss chance".
    "potion-of-blur": [{"type": "concealment", "miss_chance": 20,
                        "duration": D(3, "minute")}],
    # Delay poison: the immunity already on the potion is the suspension; the narrative's
    # "resumes where it left off" has no reader (no running-poison clock to pause).
    "potion-of-delay-poison": [None],
    # Lesser restoration (CRB): "dispels any magical effects reducing one of the subject's
    # ability scores or cures 1d4 points of temporary ability damage to one of the
    # subject's ability scores" — the drinker chooses which, so a choice of six.
    "potion-of-lesser-restoration": [
        {"type": "choose_one",
         "options": [{"type": "ability_restore", "target": a, "dice": "1d4"}
                     for a in ("str", "dex", "con", "int", "wis", "cha")]}],
    # The climb speed already on the potion is the spell's "climb walls and ceilings".
    "potion-of-spider-climb": [None],
    # remove_condition paralyzed already carries it; "hold or slow" have no condition id.
    "potion-of-remove-paralysis": [None],
    "oil-of-align-weapon": [{"type": "strikes_as", "target": "good",
                             "duration": D(3, "minute")}],
    # Fly (CRB): "a bonus on Fly skill checks equal to 1/2 your caster level" (CL 5: +2).
    "potion-of-fly": [{"type": "skill_mod", "target": "fly", "amount": 2,
                       "bonus_type": "untyped", "duration": D(5, "minute")}],
    # Heroism (CRB): "+2 morale bonus on attack rolls, saves, and skill checks". One line
    # at the engine's every-skill target (`sheet.ALL_SKILLS`, "all"), which the
    # vocabulary has listed since alchemy lane C3; lane D had to write it as 35 lines, one
    # per skill, while the vocabulary refused it.
    "potion-of-heroism": [{"type": "skill_mod", "target": "all", "amount": 2,
                           "bonus_type": "morale", "duration": D(50, "minute")}],
    "potion-of-water-breathing": [_perm("Breathes water freely.", "breathe_water",
                                        D(10, "hour"))],
    "potion-of-gaseous-form": [_perm("Insubstantial smoke: fly 10 ft (perfect), through "
                                     "small cracks, immune to poison and critical hits, "
                                     "no attacks, somatic casting or most items.",
                                     "gaseous_form", D(10, "minute"))],
    # Neutralize poison: the immunity already on the potion; "poison currently affecting
    # them ends" has no condition to end (a running poison is queued ability damage).
    "potion-of-neutralize-poison": [None],
    "potion-of-protection-from-energy": [_perm("Absorbs up to 60 points of one energy "
                                               "type, fixed when brewed, then ends.",
                                               "absorb_energy", D(50, "minute"))],
    # Keen edge (CRB): "doubles the threat range of a weapon"; the enchanter's keen is the
    # same document (effectspec crit_range, sheet._with_layer).
    "oil-of-keen-edge": [{"type": "crit_range", "multiply": 2, "stacking": "threat-range",
                          "duration": D(50, "minute")}],
}


# Rows this pass adds to the catalogue (alchemy lane F): their own fields, beside the PLAN
# entry that gives them their alchemy fields. Appended when the file does not have them.
NEW_MATERIALS: list[dict] = [
    {"id": "wooden-rod", "name": "Wooden rod", "kind": "vessel", "tier": "common",
     "craft_dc": None,
     "text": ("A whittled stick or a short rod of hard wood: the body of a tindertwig, a "
              "smokestick or a sunrod. Bottled into, the work becomes a tool you strike or "
              "light rather than a thing you drink or throw."),
     "risky": False, "volatile": False, "obtain": "bought", "market": "market",
     "price_gp": 0.01},
]

# The old chain bench's own lists, retired with it (alchemy lane F): `effects` was the
# pre-revamp product the chain bench read, and `effects_converted` its bookkeeping. The
# step bench reads `product` through rules/materials.py, so the copies go (lane D's
# hand-off: "when your bench replaces it, retire the old chain bench for alchemy and
# delete `effects` from the alchemist rows").
RETIRED_FIELDS = ("effects", "effects_converted")

# Every old recipe bottles in a drinkable vessel (alchemy lane F). Lane D found the nine
# 3rd-level recipes naming the crystal retort as their only vessel, and the retort is
# `apparatus` now (a vessel that is equipment, never spent): with no vial among their
# materials they could not be bottled as a potion at all. The retort stays (it is the
# apparatus that helps); the vial the book's 3rd-level work wants is added.
RECIPE_VESSEL = {1: "glass-vial", 2: "glass-vial", 3: "warded-phial"}


# --- assembling -----------------------------------------------------------------------------------

def build_material(raw: dict) -> dict:
    mid = raw["id"]
    plan = PLAN[mid]
    row = {k: v for k, v in raw.items()
           if k not in ("product", "working", "mishap", "toxic", "color", "book",
                        "book_source") + RETIRED_FIELDS}
    product = [copy.deepcopy(p) for p in plan.get("product", [])]
    cites = []
    for p in product:
        if p.get("cite"):
            cites.append(p.pop("cite"))
    working = copy.deepcopy(plan.get("working", []))
    job = CATALYST_JOBS.get(mid)
    if job:
        for w in working:
            if w["trait"] == "catalyst":
                w["note"] = job
    row["product"] = product
    row["working"] = working
    row["mishap"] = copy.deepcopy(plan.get("mishap"))
    row["toxic"] = copy.deepcopy(plan.get("toxic"))
    row["color"] = list(plan["color"])
    if cites:
        row["book"] = True
        row["book_source"] = sorted(set(cites))
    if mid in TEXTS:
        row["text"] = TEXTS[mid]
    return row


def _drinkable(mid: str) -> bool:
    plan = PLAN.get(mid) or {}
    return any(w.get("trait") == "drinkable" for w in plan.get("working") or [])


# Lines an earlier run of this pass wrote in place of a narrative line, which a later
# typing supersedes. The pass replaces narrative lines and nothing else, so once a row was
# typed a changed typing could never reach the file again: heroism's 35 per-skill lines
# (lane D, written while the skill vocabulary refused `all`) would have stayed beside the
# one `all` line for ever. Each predicate names exactly the old lines; the new typing is
# then added once, so the run stays idempotent.
SUPERSEDED = {
    "potion-of-heroism": lambda e: (e.get("type") == "skill_mod"
                                    and e.get("bonus_type") == "morale"
                                    and e.get("target") != "all"),
}


def build_potion(raw: dict) -> dict:
    row = copy.deepcopy(raw)
    if not any(_drinkable(m) for m in row.get("materials") or []):
        vessel = RECIPE_VESSEL.get(int(row.get("spell_level") or 1), "glass-vial")
        row["materials"] = list(row.get("materials") or []) + [vessel]
    typing = POTION_TYPING.get(row["id"])
    narr = [i for i, e in enumerate(row["effects"]) if e.get("type") == "narrative"]
    old = SUPERSEDED.get(row["id"])
    if not narr and old is not None and typing:
        kept = [e for e in row["effects"] if not old(e)]
        kept.extend(copy.deepcopy(t) for t in typing if t is not None and t not in kept)
        row["effects"] = kept
        return row
    if not narr:
        return row
    if typing is None or len(typing) < 1:
        raise SystemExit(f"NO TYPING for {row['id']}: {len(narr)} narrative line(s)")
    out = [e for e in row["effects"] if e.get("type") != "narrative"]
    out.extend(copy.deepcopy(t) for t in typing if t is not None)
    row["effects"] = out
    return row


def herb_essences(herbs: dict) -> tuple[dict, int]:
    """An `essence` on every effect of every hybrid herb, by the rule; nothing else
    changes. Returns the rewritten file and how many effects gained one."""
    out = copy.deepcopy(herbs)
    n = 0
    for ing in out["ingredients"]:
        if not ing.get("hybrid"):
            continue
        for e in ing.get("effects") or []:
            e["essence"] = essence_of({k: v for k, v in e.items() if k != "essence"})
            n += 1
    return out, n


def main() -> int:
    apply = "--apply" in sys.argv
    alch = json.loads(ALCHEMIST.read_text(encoding="utf-8"))
    pots = json.loads(POTIONS.read_text(encoding="utf-8"))
    herbs = json.loads(HERBS.read_text(encoding="utf-8"))

    have = {m["id"] for m in alch["materials"]}
    alch["materials"] = list(alch["materials"]) + [copy.deepcopy(m) for m in NEW_MATERIALS
                                                   if m["id"] not in have]
    ids = [m["id"] for m in alch["materials"]]
    missing = [i for i in ids if i not in PLAN]
    extra = [i for i in PLAN if i not in ids]
    if missing or extra:
        print(f"NO PLAN for {missing}; planned but not in the file: {extra}")
        return 1
    rows = [build_material(m) for m in alch["materials"]]
    note = alch.get("note", "").replace(ALCHEMIST_NOTE_WAS, "")
    if ALCHEMIST_NOTE_ADD.strip() not in note:
        note += ALCHEMIST_NOTE_ADD
    new_alch = {"source": alch.get("source"), "note": note, "materials": rows}
    new_pots = dict(pots, potions=[build_potion(p) for p in pots["potions"]])
    new_herbs, n_herb = herb_essences(herbs)

    problems = check(new_alch, new_pots, new_herbs)
    for p in problems:
        print(p)
    with_product = sum(1 for r in rows if r["product"])
    print(f"{len(problems)} problem(s). Materials: {len(rows)} ({with_product} with product "
          f"traits, {len(rows) - with_product} apparatus, media or wild); product traits: "
          f"{sum(len(r['product']) for r in rows)}; hybrid herb effects given an essence: "
          f"{n_herb}; potions typed: {len(POTION_TYPING)}.")
    if problems:
        return 1
    if apply:
        # Each file keeps the indent it was written with, so the diff is the data.
        ALCHEMIST.write_text(json.dumps(new_alch, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        POTIONS.write_text(json.dumps(new_pots, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        HERBS.write_text(json.dumps(new_herbs, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
        materials.refresh()
        print("written.")
    return 0


def check(new_alch: dict, new_pots: dict, new_herbs: dict) -> list[str]:
    """Validate the batch as it is about to be written, through the functions the loaders
    and tests use: the alchemy validator, the product-trait rule, the price rule, and the
    vocabulary's own `validate` on every potion line."""
    shelf = materials.all()
    docs = {r["id"]: materials.normalise(r, materials.ALCHEMY_CATALOGUE)
            for r in new_alch["materials"]}
    shelf.update(docs)
    out: list[str] = []
    for doc in docs.values():
        out.extend(materials.validate(doc, shelf=shelf))
    out.extend(pricing.material_price_problems(new_alch["materials"],
                                               "alchemist-materials.json"))
    for p in new_pots["potions"]:
        for i, e in enumerate(p["effects"]):
            where = f"{p['id']} effect {i + 1}"
            if e.get("type") == "narrative":
                out.append(f"{where}: still narrative.")
            out.extend(effectspec.validate(e, where))
    for ing in new_herbs["ingredients"]:
        if not ing.get("hybrid"):
            continue
        for i, e in enumerate(ing.get("effects") or []):
            out.extend(effectspec.product_trait_problems(e, f"{ing['id']} effect {i + 1}"))
    return out


if __name__ == "__main__":
    sys.exit(main())
