"""Our own versions of the adventures' items, written into the magic-item catalogue.

The owner, 2026-10-28: "pull some adventure path specific items and descriptions to write
your own version we dont need licencing for", after step 6 (option D, the rulebook line
only). Paizo's legal page marks as Product Identity "proper names (characters, deities,
etc.) ... locations, characters" and leaves "the game mechanics" open
(docs/own-items.md has the source and every item's original). So each item here keeps the
printed numbers and nothing else: a name and words of our own, no place, faith or order
it belonged to, and any rule that worked only for one of them dropped.

Which items, and why these: tools in the session scratchpad listed every piece of gear the
5,649 removed rows carried and no rulebook row did (4,310 distinct, 390 in three or more
blocks); the setting's own items among them were read on Archives of Nethys, and the ones
whose every effect the catalogue's grammar can carry are written below. The rest, each with
its reason, are in docs/own-items.md.

    python tools/own_items.py     # rewrite the rows (idempotent), then the checks
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

ITEMS = ROOT / "content" / "materials" / "magic-items.json"
# The catalogue's rule (`materials.recipe_problems`): every row names the AoN page its
# numbers were read from. A citation of where a mechanic was read, not the original's
# name on our item; the item's own name and words are ours (docs/own-items.md).
AON = "https://aonprd.com/MagicWondrousDisplay.aspx?FinalName="
DAY = {"amount": 24, "unit": "hour"}
PAINT_SOURCE = "war paint"


def _saves(amount: int, bonus: str) -> list[dict]:
    return [{"type": "save_mod", "target": s, "amount": amount, "bonus_type": bonus,
             "book": True} for s in ("fort", "ref", "will")]


def _paint(colour: str, price: int, spell: str, effect: dict, essence: dict,
           said: str) -> dict:
    src = AON + "Shoanti%20War%20Paint" + colour.title()
    return {
        "id": f"mi-war-paint-{colour}", "name": f"War Paint ({colour.title()})",
        "kind": "wondrous", "slot": None, "vessel": "slotless", "caster_level": 7,
        "price_gp": price, "obtain": "bought", "spell": spell, "spells": [[spell]],
        "text": (f"A clay pot of {colour} paint, ground with ash and bitter root. Smeared "
                 f"on the skin it {said} for a day; a second colour wipes out the first."),
        # One source for every colour: "you can benefit from only one color of Shoanti
        # war paint at a time and applying a dose of a different color replaces the
        # effects of the previous application" (AoN, read 2026-10-30). `use_item` lifts
        # what an earlier power of the same `source` laid before it lays this one.
        "book": [{"type": "item_power",
                  "effect": [dict(effect, duration=DAY, source=PAINT_SOURCE)],
                  "uses": "once", "uses_count": 1, "book": True}],
        "essences": [essence], "source": src,
        "not_yet": ["Putting it on is a full-round action that provokes, in the book; "
                    "here it is put on outside a fight."],
    }


ROWS = [
    {
        "id": "mi-lodestar-compass", "name": "Lodestar Compass", "kind": "wondrous",
        "slot": None, "vessel": "slotless", "caster_level": 5, "price_gp": 500,
        "obtain": "bought", "spell": "light", "spells": [["light"]],
        "text": ("A brass case the size of a palm, its needle a sliver of lodestone. A word "
                 "lights it like a lantern, and an old hollow in its lid takes a small "
                 "stone of power."),
        "book": [{"type": "item_power", "spell": "light", "uses": "unlimited",
                  "caster_level": 5, "book": True}],
        "essences": [{"family": "light", "count": 1}], "source": AON + "Wayfinder",
        "not_yet": ["A +2 circumstance bonus on Survival checks to avoid becoming lost: no "
                    "roll reads being lost yet.",
                    "The hollow in the lid holds an ioun stone; the game has none."],
    },
    {
        "id": "mi-wardstar-medallion", "name": "Wardstar Medallion", "kind": "wondrous",
        "slot": "neck", "vessel": "neck", "caster_level": 5, "price_gp": 3500,
        "obtain": "bought", "spell": "false-life",
        "spells": [["false-life"], ["gentle-repose"], ["resistance"]],
        "text": ("A seven-pointed star of dark iron on a chain. It turns aside a little of "
                 "every harm, and once a day it lends its wearer a borrowed vigour."),
        "book": _saves(1, "resistance") + [
            {"type": "item_power", "spell": "false-life", "uses": "per_day", "uses_count": 1,
             "caster_level": 5, "book": True}],
        "essences": [{"grants": "resistance", "count": 1}, {"family": "vigour", "count": 1}],
        "source": AON + "Sihedron%20Medallion",
        "not_yet": ["Laid on a body it keeps the body from decay (gentle repose); nothing "
                    "keeps a corpse yet."],
    },
    {
        "id": "mi-wardstar-ring", "name": "Wardstar Ring", "kind": "wondrous",
        "slot": "ring", "vessel": "ring", "caster_level": 9, "price_gp": 35000,
        "obtain": "bought", "spell": "shield",
        "spells": [["endure-elements"], ["resistance"], ["shield"]],
        "text": ("A heavy ring cut with a seven-pointed star. Its wearer stands easier "
                 "against blows and spells alike, feels neither frost nor furnace, and may "
                 "dress in whatever clothes the ring is told to show."),
        "book": [{"type": "combat_mod", "target": "ac", "amount": 3, "bonus_type": "deflection",
                  "book": True}] + _saves(3, "resistance") + [
            {"type": "spell_effect", "target": "endure-elements", "caster_level": 9,
             "trigger": "worn", "book": True},
            {"type": "item_power", "tell": "The ring dresses its wearer's clothes or armour "
                                           "to look like any others",
             "uses": "unlimited", "book": True}],
        "essences": [{"grants": "deflection", "count": 1}, {"grants": "resistance", "count": 1},
                     {"family": "warding", "count": 1}],
        "source": "https://aonprd.com/MagicRingsDisplay.aspx?FinalName=Sihedron+Ring",
        "not_yet": [],
    },
    {
        "id": "mi-iron-saints-mask", "name": "Iron Saint's Mask", "kind": "wondrous",
        "slot": "head", "vessel": "head", "caster_level": 1, "price_gp": 2100,
        "obtain": "bought", "spell": "cause-fear",
        "spells": [["cause-fear"], ["shadow-conjuration"]],
        "text": ("A mask of beaten iron with a calm, unmoving face. Behind it a healer's "
                 "hands are surer and a threat lands harder; once a day it mends a wound, "
                 "and once a day it frightens."),
        "book": [{"type": "skill_mod", "target": "heal", "amount": 2,
                  "bonus_type": "competence", "book": True},
                 {"type": "skill_mod", "target": "intimidate", "amount": 2,
                  "bonus_type": "competence", "book": True},
                 {"type": "item_power", "spell": "cure-light-wounds", "uses": "per_day",
                  "uses_count": 1, "caster_level": 1, "book": True},
                 {"type": "item_power", "spell": "cause-fear", "uses": "per_day",
                  "uses_count": 1, "caster_level": 1, "book": True}],
        "essences": [{"grants": "skill-competence", "count": 1},
                     {"family": "mind", "count": 1}],
        "source": AON + "Holy+Mask+of+the+Living+God",
        "not_yet": ["The book's maker also needs 5 ranks in Heal and Intimidate; the bench "
                    "does not ask ranks of an enchanter yet."],
    },
    _paint("black", 1800, "blur",
           {"type": "concealment", "miss_chance": 20},
           {"family": "shadow", "count": 1}, "blurs the wearer's outline"),
    _paint("blue", 900, "expeditious-retreat",
           {"type": "speed", "target": "land", "amount": 30, "bonus_type": "enhancement"},
           {"family": "speed", "count": 1}, "quickens the wearer's stride by thirty feet"),
    _paint("orange", 900, "stoneskin",
           # "This effect stacks with damage reduction gained via a character class,
           # such as barbarian" (AoN, read 2026-10-30): `stacks_with`, read by
           # `Actor.damage_reduction`.
           {"type": "damage_reduction", "amount": 1, "bypass": "", "stacks_with": "class"},
           {"family": "earth", "count": 1}, "hardens the skin against every blow (DR 1/—)"),
    _paint("red", 900, "resist-energy",
           {"type": "resistance", "target": "fire", "amount": 10},
           {"family": "fire", "count": 1}, "turns aside fire"),
    _paint("silver", 900, "shield-of-faith",
           {"type": "combat_mod", "target": "ac", "amount": 3, "bonus_type": "deflection"},
           {"grants": "deflection", "count": 1}, "turns blows aside"),
    _paint("yellow", 900, "clairaudience-clairvoyance",
           {"type": "skill_mod", "target": "perception", "amount": 5,
            "bonus_type": "competence"},
           {"grants": "skill-competence", "count": 1}, "sharpens the wearer's eyes and ears"),
]


def main() -> int:
    from rules import materials

    doc = json.loads(ITEMS.read_text(encoding="utf-8"))
    ours = {r["id"] for r in ROWS}
    rows = [r for r in doc["materials"] if r["id"] not in ours]
    for r in ROWS:
        r = dict(r)
        r["tier"] = materials.tier_for_price(r["price_gp"])
        r["effects"] = []          # the book list is what is read (`magicitem._book_effects`)
        rows.append(r)
    doc["materials"] = rows
    problems = [p for r in rows if r["id"] in ours for p in materials.recipe_problems(r)]
    problems += materials.magic_item_tier_problems([r for r in rows if r["id"] in ours])
    if problems:
        print("\n".join(problems))
        return 1
    ITEMS.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(ROWS)} own items written to {ITEMS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
