"""The enchanting data pass (docs/enchanting-revamp-plan.md §7.5, lane D), as a record.

What it writes:

- `content/materials/enchanter-materials.json`: the **families** table (each family's phase
  of the day with the folklore that put it there, its colour, its affinity materials and
  working traits), and on every essence `grants`, `motes`, `phase` (from the family),
  `polarity`, `affinity`, `house` top-ups, `working`, `color` and the derived `tier` and
  `price_gp`. Eleven new bought essences grant the ring and wondrous bonuses no old essence
  could (deflection, natural armour, armour, resistance, the six abilities, competence).
  The seven vessel entries are retired (kept loadable, never offered: a vessel is a real
  record now, plan §7.3).
- `content/materials/magic-items.json`: every wondrous row becomes a recipe (plan §7.4):
  `book` effects, `spells` groups, the book's `caster_level` and `creator_level`, the
  creator's other clauses, the `essences` it needs, `source` and `not_yet`; and every
  wondrous row's `tier` is re-banded by its price (the owner, 2026-10-05).

Two kinds of number, kept apart:

- **Book** numbers (price, caster level, creator level, every amount in `book`) read by hand
  from the AoN pages named in each row's `source`, fetched 2026-10-05: the Core Rulebook's
  rings, wondrous items and rods pages and Ultimate Equipment's belts and headbands pages.
  Scaled items (rings of protection, cloaks of resistance, the ability belts and headbands,
  amulets of natural armour, bracers of armour) take their documents from lane A's property
  table through `effectspec.bind`, so the two tables cannot disagree.
- **House** numbers (each essence's top-ups, the motes of an essence that grants nothing,
  the family table) drafted inside `rules/materials.py`'s fences for the owner's review in
  docs/enchanting-review.md (`tools/enchant_review.py` writes its tables).

Every essence and recipe is validated before anything is written, and the run refuses to
write if any has a problem. Dry run by default:

    python tools/enchant_data_pass.py            # validate and report
    python tools/enchant_data_pass.py --apply    # validate, then write both files

Idempotent: the enchanting fields are replaced, never appended. Essence ids, names and kinds
never change (old saves and the old bench name them).
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import effectspec, materials, pricing  # noqa: E402

MAT_DIR = ROOT / "content" / "materials"
ENCHANTER = MAT_DIR / "enchanter-materials.json"
ITEMS = MAT_DIR / "magic-items.json"

# --- the families -----------------------------------------------------------------------------
#
# The owner's ruling (round 4 point 10, round 5): phases of the day, never a planet; seven
# phases (rules/sky.PHASES). Each family's `why` is the folklore or the observation that put
# it in its phase, cited where it could be sourced on 2026-10-05 and said plainly where it
# could not. docs/enchanting-review.md lays this table out for the owner.

ALVISSMAL = "https://en.wikipedia.org/wiki/Alv%C3%ADssm%C3%A1l"
MIDDAY = "https://en.wikipedia.org/wiki/Lady_Midday"
WITCHING = "https://en.wikipedia.org/wiki/Witching_hour"
STORMS = ("https://geo.libretexts.org/Bookshelves/Meteorology_and_Climate_Science/"
          "Practical_Meteorology_(Stull)/14%3A_Thunderstorm_Fundamentals/"
          "14.7%3A_Thunderstorm_Forecasting")
CURFEW = "https://wordhistories.net/2016/08/22/curfew/"
COCKCROW = "https://www.almanac.com/folklore-cocks-cockcrows-and-weathercocks"

FAMILIES: dict[str, dict] = {
    # --- dawn
    "cold": dict(phase="dawn", color="#8fd3ff",
                 affinity=["frost-forged-steel", "white-dragonhide", "winter-wolf-pelt"],
                 working=["heavy"],
                 why="Frost before dawn (the owner's own example): the coldest hour of the "
                     "day is just before sunrise, when the night's cooling has run longest "
                     "and the sun has not yet begun to repay it (the diurnal temperature "
                     "minimum; any meteorology text)."),
    "earth": dict(phase="dawn", color="#9a7b55",
                  affinity=["iron", "bulette-plate", "ironwood-haft"], working=["heavy"],
                  why="Stone takes at sunrise: in the Eddic Alvissmal the dwarf All-Wise is "
                      "kept talking until dawn and the first light turns him to stone "
                      f"({ALVISSMAL}); trolls share the fate in Norse folklore."),
    "invulnerability": dict(phase="dawn", color="#8a8f99",
                            affinity=["adamantine", "tarrasque-plate"], working=["heavy"],
                            why="The hardening at first light, as earth: Alvissmal's dwarf "
                                f"made stone by the sunrise ({ALVISSMAL}). A house pairing "
                                "with earth; no separate source."),
    "light": dict(phase="dawn", color="#fff4c2",
                  affinity=["silver", "gold", "glowlizard-hide"], working=["pure"],
                  why="First light, the cockcrow: in the folk belief the crow before dawn "
                      f"sends the night's spirits home ({COCKCROW}); Hamlet's ghost fades "
                      "at it."),
    "holy": dict(phase="dawn", color="#ffe08a",
                 affinity=["silver", "angelskin-binding", "unicorn-hide", "elysian-bronze"],
                 working=["pure"],
                 why="The cockcrow that ends the dead's hour: spirits and devils "
                     f"\"disappear with the first cry of the cock\" ({COCKCROW}). Dawn is "
                     "the hour the holy wins back."),
    "vorpal": dict(phase="dawn", color="#e8e8f0",
                   affinity=["adamantine", "high-carbon-steel"], working=["volatile"],
                   why="Executions at dawn, the custom of military and civil justice alike. "
                       "A house reading; not sourced in this pass."),
    # --- morning
    "air": dict(phase="morning", color="#cfe8f2",
                affinity=["griffon-hide", "bat-wing-leather", "mithral"],
                working=["skittish"],
                why="The day's winds rise as the morning sun warms the ground and the air "
                    "above it begins to climb (the same heating that builds the "
                    f"afternoon's storms, {STORMS}). A house reading of the meteorology."),
    "keen": dict(phase="morning", color="#d8dde3",
                 affinity=["high-carbon-steel", "pattern-steel"], working=["eager"],
                 why="The mower's hours: scythes were whetted and the hay cut early, while "
                     "the dew still softened the stalks. Common country practice; not "
                     "sourced in this pass."),
    "speed": dict(phase="morning", color="#ffd25a",
                  affinity=["mithral", "wyvern-sinew"], working=["eager"],
                  why="The messenger's start at first light, the day's whole road ahead. "
                      "A house reading; not sourced."),
    "mercy": dict(phase="morning", color="#f6c9d7",
                  affinity=["silver", "moonstone-focus"], working=["pure"],
                  why="Mercies \"new every morning\" (Lamentations 3:22-23, a text in the "
                      "public domain): the morning is the hour of a fresh start."),
    "vigour": dict(phase="morning", color="#e07a4a",
                   affinity=["wolf-pelt", "grizzly-hide", "black-bear-hide"],
                   working=["eager"],
                   why="The body's strength is for the day's first work: the field hands "
                       "out before the heat Lady Midday walks in ({MIDDAY}). A house "
                       "reading.".format(MIDDAY=MIDDAY)),
    "skill": dict(phase="morning", color="#c8b28a",
                  affinity=["brass", "leather-grip"], working=[],
                  why="The working day's opening hours, when a craftsman's hand is "
                      "freshest. A house reading; not sourced."),
    # --- noon
    "fire": dict(phase="noon", color="#e0703a",
                 affinity=["copper", "red-dragonhide", "salamander-hide", "ruby-focus",
                           "fire-forged-steel"],
                 working=["eager"],
                 why="Fire at noon (the owner's own example): the sun at its height, and "
                     "Lady Midday of the Slavic fields, the personified sunstroke who walks "
                     f"only in the hottest part of the day ({MIDDAY})."),
    "axiomatic": dict(phase="noon", color="#c0c8d8", affinity=["platinum", "steel"],
                      working=["heavy"],
                      why="Noon is the hour of plain sight: the shortest shadows, nothing "
                          "hidden, the court in session. A house reading; not sourced."),
    "fortification": dict(phase="noon", color="#b7a27a",
                          affinity=["adamantine", "dragon-turtle-shell", "bulette-plate"],
                          working=["heavy"],
                          why="Fortification turns the blow from hiding (the sneak attack "
                              "and the vital strike), and at noon there is least shadow to "
                              "strike from. A house reading."),
    # --- afternoon
    "electricity": dict(phase="afternoon", color="#f2e85c",
                        affinity=["copper", "blue-dragonhide", "electric-eel-skin",
                                  "behir-hide"],
                        working=["skittish"],
                        why="Thunderstorms over land peak in the late afternoon and early "
                            "evening, two or three hours before sunset, when the day's "
                            f"heating has lifted the most air ({STORMS}). The one family "
                            "in the afternoon the owner added in round 5; dusk is the "
                            "alternative if afternoon should stay empty."),
    "sonic": dict(phase="afternoon", color="#c9b6ff",
                  affinity=["bell-bronze", "singing-steel"], working=["eager"],
                  why=f"Thunder, the storm's voice: the same afternoon peak ({STORMS})."),
    "defending": dict(phase="afternoon", color="#7d93a8", affinity=["steel", "adamantine"],
                      working=["heavy"],
                      why="The long watch of the afternoon. The weakest reason in the "
                          "table, a house placement; noon (with fortification) is the "
                          "alternative."),
    # --- dusk
    "acid": dict(phase="dusk", color="#9ccc3c",
                 affinity=["black-dragonhide", "green-dragonhide", "ankheg-shell-leather"],
                 working=["volatile"],
                 why="The evening damp the old physicians feared: the miasma theory held "
                     "the night air that rises at nightfall to be corrupting. A house "
                     "reading; not sourced in this pass."),
    "warding": dict(phase="dusk", color="#6f9bd1", affinity=["steel", "adamantine"],
                    working=["heavy"],
                    why="Curfew: the medieval evening bell (couvre-feu, cover-fire) at which "
                        f"hearths were covered and the house shut against the night "
                        f"({CURFEW})."),
    "abjuration": dict(phase="dusk", color="#9db7ff", affinity=["platinum", "silver"],
                       working=["pure"],
                       why=f"Wards set at nightfall, as the curfew's ({CURFEW})."),
    "bane": dict(phase="dusk", color="#b5651d", affinity=["cold-iron", "silver"],
                 working=[],
                 why="The hunter's hour: wolves, owls and the great cats are crepuscular, "
                     "hunting at dusk and dawn. Cold iron against fey and silver against "
                     "the shapechangers line up with the book's own materials."),
    "anarchic": dict(phase="dusk", color="#d14fd1", affinity=["living-steel", "chimera-hide"],
                     working=["skittish"],
                     why="Twilight is the liminal hour, neither day nor night, when the "
                         "order of the day comes apart. A house reading; not sourced."),
    "wounding": dict(phase="dusk", color="#a3122a",
                     affinity=["high-carbon-steel", "viper-skin"], working=["eager"],
                     why="The sky's red hour. A house image, the weakest kind of reason; "
                         "not sourced."),
    # --- night
    "water": dict(phase="night", color="#3a7bd5",
                  affinity=["kraken-hide", "sharkskin-grip", "crocodile-hide"],
                  working=["skittish"],
                  why="Dew settles through the night as the ground cools below the air "
                      "(and was gathered before sunrise for magic, Folkard's Plant Lore, "
                      "cited in rules/sky.py)."),
    "shadow": dict(phase="night", color="#3b3355",
                   affinity=["shadow-silk", "shadow-mastiff-hide", "umbral-dragonhide",
                             "shadow-black"],
                   working=["skittish"],
                   why="Darkness itself: the hours with no sun."),
    "slick": dict(phase="night", color="#c4b07a",
                  affinity=["mink-oil", "currier-tallow", "troll-fat"],
                  working=["skittish"],
                  why="The burglar's hours, slipping through bars and bonds. A house "
                      "reading; not sourced."),
    "vicious": dict(phase="night", color="#8b1e2d", affinity=["fiend-bone-core", "abysium"],
                    working=["volatile"],
                    why="The predator's dark, when the wolf comes to the fold. A house "
                        "reading; not sourced."),
    "dancing": dict(phase="night", color="#e0a8ff", affinity=["singing-steel", "silk-thread"],
                    working=["skittish"],
                    why="The fairy revel, danced through the night until the cockcrow "
                        "breaks it. Widespread in British fairy lore; not sourced in this "
                        "pass."),
    "arcane": dict(phase="night", color="#7b6cf6", affinity=["mithral", "gold", "platinum"],
                   working=[],
                   why="The scholar's lamp: study by night, the midnight oil. A house "
                       "reading; not sourced."),
    "mind": dict(phase="night", color="#8fb3e8", affinity=["gold", "silver"],
                 working=["pure"],
                 why="The night owl and the scholar's lamp, as arcane: wisdom keeps the "
                     "night hours. A house reading; not sourced."),
    # --- midnight
    "unholy": dict(phase="midnight", color="#6b1030",
                   affinity=["fiend-bone-core", "hell-hound-hide", "abysium"],
                   working=["volatile"],
                   why="The witching hour, \"the hour immediately after midnight\", when "
                       f"witches, demons and ghosts are at their most powerful ({WITCHING})."),
    "ghost": dict(phase="midnight", color="#b8f0e8", affinity=["ghost-wax", "silver"],
                  working=["night_only"],
                  why=f"The dead at midnight (the owner's own example; {WITCHING})."),
    "negative": dict(phase="midnight", color="#2f2a3a",
                     affinity=["bone-grip", "fiend-bone-core"], working=["volatile"],
                     why=f"The dead at midnight, as ghost ({WITCHING})."),
}

# --- the essences -----------------------------------------------------------------------------
#
# Notation. House top-ups are typed, small and marked; the bonus types follow the book's
# own habits (a skill's item bonus is competence, a save's resistance, an AC ward
# deflection) so a top-up never stacks where the book's items would not.


def H(spec: dict) -> dict:
    return {**spec, "house": True}


def sk(skill, n, bonus="competence"):
    return H({"type": "skill_mod", "target": skill, "amount": n, "bonus_type": bonus})


def sv(save, n, bonus="resistance"):
    return H({"type": "save_mod", "target": save, "amount": n, "bonus_type": bonus})


def cm(target, n, bonus="insight"):
    return H({"type": "combat_mod", "target": target, "amount": n, "bonus_type": bonus})


def res(energy, n):
    return H({"type": "resistance", "target": energy, "amount": n})


def rider(n, energy):
    return H({"type": "damage", "dice": str(n), "damage_type": energy,
              "lethality": "lethal", "trigger": "hit"})


# Motes for an essence that grants nothing: the mote supply found in the world. House
# numbers by band, each sitting inside its own band (materials.essence_tier).
SUPPLY_MOTES = {"common": 2, "uncommon": 10, "rare": 30, "exotic": 100, "legendary": 250}

# id: (family, polarity, grants, house, motes or None for "its grant's cost"). An essence
# found or harvested may carry more motes than its grant costs (a trophy is richer than a
# shop phial); a bought one carries exactly its grant's cost, which the validator holds.
P = lambda pid, **kw: {"property": pid, **kw}  # noqa: E731
E = lambda n: {"enhancement": n}  # noqa: E731

ESSENCES: dict[str, tuple] = {
    # the gathered motes: the common supply
    "fire-mote": ("fire", "weapon", None, [rider(1, "fire")], SUPPLY_MOTES["common"]),
    "frost-mote": ("cold", "weapon", None, [rider(1, "cold")], SUPPLY_MOTES["common"]),
    "spark-mote": ("electricity", "weapon", None, [rider(1, "electricity")],
                   SUPPLY_MOTES["common"]),
    "stone-mote": ("earth", "armour", None, [cm("ac", 1, "natural armour")],
                   SUPPLY_MOTES["common"]),
    "gale-mote": ("air", "any", None, [cm("initiative", 1)], SUPPLY_MOTES["common"]),
    "tide-mote": ("water", "armour", None, [sk("swim", 1)], SUPPLY_MOTES["common"]),
    "glow-mote": ("light", "any", None, [sk("perception", 1)], SUPPLY_MOTES["common"]),
    "hearth-ember": ("fire", "armour", None, [res("fire", 1)], SUPPLY_MOTES["common"]),
    # the enhancement ladders, the general bought supply
    "arcane-essence-i": ("arcane", "weapon", E(1), [sk("spellcraft", 1)], None),
    "arcane-essence-ii": ("arcane", "weapon", E(2), [sk("spellcraft", 2)], None),
    "arcane-essence-iii": ("arcane", "weapon", E(3), [sk("spellcraft", 2)], None),
    "arcane-essence-iv": ("arcane", "weapon", E(4), [sk("spellcraft", 2)], None),
    "arcane-essence-v": ("arcane", "weapon", E(5), [sk("spellcraft", 3)], None),
    "warding-essence-i": ("warding", "armour", E(1), [cm("cmd", 1)], None),
    "warding-essence-ii": ("warding", "armour", E(2), [cm("cmd", 1)], None),
    "warding-essence-iii": ("warding", "armour", E(3), [cm("cmd", 2)], None),
    "warding-essence-iv": ("warding", "armour", E(4), [cm("cmd", 2)], None),
    "warding-essence-v": ("warding", "armour", E(5), [cm("cmd", 2)], None),
    # weapon properties, bought
    "merciful-essence": ("mercy", "weapon", P("merciful"), [sk("heal", 2)], None),
    "vicious-essence": ("vicious", "weapon", P("vicious"),
                        [sk("intimidate", 2), sk("diplomacy", -1, "untyped")], None),
    "flaming-essence": ("fire", "weapon", P("flaming"),
                        [res("fire", 2), sk("stealth", -1, "untyped")], None),
    "frost-essence": ("cold", "weapon", P("frost"),
                      [res("cold", 2), cm("initiative", -1, "untyped")], None),
    "shock-essence": ("electricity", "weapon", P("shock"),
                      [res("electricity", 2), sk("stealth", -1, "untyped")], None),
    "corrosive-essence": ("acid", "weapon", P("corrosive"),
                          [res("acid", 2), sk("diplomacy", -1, "untyped")], None),
    "keen-essence": ("keen", "weapon", P("keen"), [sk("perception", 2)], None),
    "bane-essence": ("bane", "weapon", P("bane"), [sk("survival", 2)], None),
    "thundering-essence": ("sonic", "weapon", P("thundering"),
                           [res("sonic", 2), sk("perception", -1, "untyped")], None),
    "flaming-burst-essence": ("fire", "weapon", P("flaming-burst"),
                              [res("fire", 2), sk("stealth", -1, "untyped")], None),
    "icy-burst-essence": ("cold", "weapon", P("icy-burst"),
                          [res("cold", 2), cm("initiative", -1, "untyped")], None),
    "shocking-burst-essence": ("electricity", "weapon", P("shocking-burst"),
                               [res("electricity", 2), sk("stealth", -1, "untyped")], None),
    "wounding-essence": ("wounding", "weapon", P("wounding"), [sk("intimidate", 2)], None),
    "defending-essence": ("defending", "weapon", P("defending"), [cm("cmd", 2)], None),
    "speed-essence": ("speed", "weapon", P("speed"), [cm("initiative", 2)], None),
    "dancing-essence": ("dancing", "weapon", P("dancing"), [sk("acrobatics", 2)], None),
    "vorpal-essence": ("vorpal", "weapon", P("vorpal"),
                       [sk("intimidate", 3), sk("diplomacy", -1, "untyped")], None),
    "brilliant-energy-essence": ("light", "weapon", P("brilliant-energy"),
                                 [sk("perception", 2), sk("stealth", -2, "untyped")], None),
    # weapon properties, harvested from outsiders (exotic trophies)
    "holy-essence": ("holy", "weapon", P("holy"), [sv("will", 2, "sacred")],
                     SUPPLY_MOTES["exotic"]),
    "unholy-essence": ("unholy", "weapon", P("unholy"),
                       [sv("will", 2, "profane"), sk("diplomacy", -1, "untyped")],
                       SUPPLY_MOTES["exotic"]),
    "anarchic-essence": ("anarchic", "weapon", P("anarchic"),
                         [cm("initiative", 2, "luck"), sv("will", -1, "untyped")],
                         SUPPLY_MOTES["exotic"]),
    "axiomatic-essence": ("axiomatic", "weapon", P("axiomatic"),
                          [sv("will", 2, "insight"), cm("initiative", -1, "untyped")],
                          SUPPLY_MOTES["exotic"]),
    "ghost-touch-essence": ("ghost", "weapon", P("ghost-touch"), [sk("perception", 2)],
                            SUPPLY_MOTES["exotic"]),
    # armour properties, bought
    "slick-essence": ("slick", "armour", P("slick"),
                      [sv("ref", 1, "luck"), sk("climb", -1, "untyped")], None),
    "improved-slick-essence": ("slick", "armour", P("slick-improved"),
                               [sv("ref", 2, "luck"), sk("climb", -1, "untyped")], None),
    "greater-slick-essence": ("slick", "armour", P("slick-greater"),
                              [sv("ref", 2, "luck"), sk("climb", -1, "untyped")], None),
    "shadow-essence": ("shadow", "armour", P("shadow"),
                       [sk("bluff", 1), sk("perception", -1, "untyped")], None),
    "improved-shadow-essence": ("shadow", "armour", P("shadow-improved"),
                                [sk("bluff", 2), sk("perception", -1, "untyped")], None),
    "greater-shadow-essence": ("shadow", "armour", P("shadow-greater"),
                               [sk("bluff", 2), sk("perception", -1, "untyped")], None),
    "fortification-light-essence": ("fortification", "armour", P("fortification-light"),
                                    [cm("cmd", 1)], None),
    "fortification-moderate-essence": ("fortification", "armour",
                                       P("fortification-moderate"), [cm("cmd", 2)], None),
    "fortification-heavy-essence": ("fortification", "armour", P("fortification-heavy"),
                                    [cm("cmd", 2)], None),
    "spell-resistance-essence": ("abjuration", "armour", P("spell-resistance-15"),
                                 [sv("will", 2), sk("spellcraft", -1, "untyped")], None),
    "invulnerability-essence": ("invulnerability", "armour", P("invulnerability"),
                                [cm("cmd", 2)], None),
    "etherealness-essence": ("ghost", "armour", P("etherealness"), [sk("stealth", 3)],
                             SUPPLY_MOTES["legendary"]),
}
# Acid's family is volatile (reading it burns), and volatile needs a drawback to apply: the
# reek of it, -1 Diplomacy, on every acid essence.
REEK = sk("diplomacy", -1, "untyped")
for _energy in ("fire", "cold", "electricity", "acid", "sonic"):
    _reek = [copy.deepcopy(REEK)] if _energy == "acid" else []
    ESSENCES[f"resist-{_energy}-essence"] = (
        _energy, "armour", P("energy-resistance", choice={"energy": _energy}),
        [sv("fort", 2)] + _reek, None)
    ESSENCES[f"resist-{_energy}-essence-improved"] = (
        _energy, "armour", P("energy-resistance-improved", choice={"energy": _energy}),
        [sv("fort", 2)] + _reek, None)
    ESSENCES[f"resist-{_energy}-essence-greater"] = (
        _energy, "armour", P("energy-resistance-greater", choice={"energy": _energy}),
        [sv("fort", 3)] + _reek, None)
ESSENCES.update({
    # gathered and harvested
    "ghost-residue": ("ghost", "weapon", P("ghost-touch"), [sk("perception", 2)], None),
    "shadowstuff": ("shadow", "armour", P("shadow"),
                    [sk("bluff", 1), sk("perception", -1, "untyped")], None),
    "red-dragon-ichor": ("fire", "weapon", P("flaming"), [res("fire", 2)],
                         SUPPLY_MOTES["exotic"]),
    "blue-dragon-ichor": ("electricity", "weapon", P("shock"), [res("electricity", 2)],
                          SUPPLY_MOTES["exotic"]),
    "white-dragon-ichor": ("cold", "weapon", P("frost"), [res("cold", 2)],
                           SUPPLY_MOTES["exotic"]),
    "green-dragon-ichor": ("acid", "weapon", P("corrosive"),
                           [res("acid", 2), copy.deepcopy(REEK)], SUPPLY_MOTES["exotic"]),
    "black-dragon-ichor": ("acid", "weapon", P("corrosive"),
                           [res("acid", 2), copy.deepcopy(REEK)], SUPPLY_MOTES["exotic"]),
    "celestial-tears": ("holy", "ward", P("deflection", bonus=2), [sv("will", 2, "sacred")],
                        SUPPLY_MOTES["exotic"]),
    "fiend-ash": ("unholy", "weapon", P("flaming"),
                  [res("fire", 2), sk("diplomacy", -1, "untyped")], SUPPLY_MOTES["exotic"]),
    "phoenix-ember": ("fire", "armour", P("energy-resistance-greater",
                                          choice={"energy": "fire"}),
                      [H({"type": "fast_healing", "amount": 1})], 330),
    "lich-dust": ("negative", "weapon", None,
                  [rider(2, "negative"), sv("will", -1, "untyped")],
                  SUPPLY_MOTES["legendary"]),
    "storm-heart": ("electricity", "weapon", P("shocking-burst"), [res("electricity", 3)],
                    SUPPLY_MOTES["legendary"]),
    "angel-feather": ("holy", "armour", P("deflection"), [sv("ref", 2, "sacred")],
                      SUPPLY_MOTES["legendary"]),
})

# New bought essences: the ring and wondrous bonuses (lane A's scaled properties) that no
# old essence granted, so the rings of protection, cloaks of resistance and ability belts in
# the catalogue had no essence to be made from.
NEW_ESSENCES: dict[str, dict] = {
    "deflecting-essence": dict(
        name="Deflecting Essence", family="warding", polarity="ward",
        grants=P("deflection"), house=[cm("cmd", 1)],
        text="A pale phial that turns aside what reaches for it. Grants deflection: the "
             "ring of protection's ward."),
    "barkhide-essence": dict(
        name="Barkhide Essence", family="earth", polarity="ward",
        grants=P("natural-armour"), house=[sk("survival", 1)],
        text="Sap gone hard as bark. Grants a natural armour bonus: the amulet of natural "
             "armour's toughening."),
    "mantling-essence": dict(
        name="Mantling Essence", family="warding", polarity="ward",
        grants=P("armour-bonus"), house=[cm("cmd", 1)],
        text="A shimmer that settles like a mail shirt nobody wears. Grants an armour "
             "bonus: the bracers of armour's force."),
    "resistance-essence": dict(
        name="Resistance Essence", family="abjuration", polarity="ward",
        grants=P("resistance"), house=[sk("perception", 1)],
        text="A faint ward that braces body and mind. Grants a resistance bonus on saves: "
             "the cloak of resistance's."),
    "might-essence": dict(
        name="Essence of Might", family="vigour", polarity="ward",
        grants=P("ability-strength"), house=[sk("climb", 1)],
        text="Grants an enhancement bonus to Strength: the belt of giant strength's."),
    "grace-essence": dict(
        name="Essence of Grace", family="vigour", polarity="ward",
        grants=P("ability-dexterity"), house=[sk("acrobatics", 1)],
        text="Grants an enhancement bonus to Dexterity: the belt of incredible dexterity's."),
    "endurance-essence": dict(
        name="Essence of Endurance", family="vigour", polarity="ward",
        grants=P("ability-constitution"), house=[sv("fort", 1)],
        text="Grants an enhancement bonus to Constitution: the belt of mighty "
             "constitution's."),
    "cunning-essence": dict(
        name="Essence of Cunning", family="mind", polarity="ward",
        grants=P("ability-intelligence"), house=[sk("spellcraft", 1)],
        text="Grants an enhancement bonus to Intelligence: the headband of vast "
             "intelligence's."),
    "insight-essence": dict(
        name="Essence of Insight", family="mind", polarity="ward",
        grants=P("ability-wisdom"), house=[sk("sense motive", 1)],
        text="Grants an enhancement bonus to Wisdom: the headband of inspired wisdom's."),
    "splendour-essence": dict(
        name="Essence of Splendour", family="mind", polarity="ward",
        grants=P("ability-charisma"), house=[sk("diplomacy", 1)],
        text="Grants an enhancement bonus to Charisma: the headband of alluring "
             "charisma's."),
    "knack-essence": dict(
        name="Essence of Knack", family="skill", polarity="any",
        grants=P("skill-competence"), house=[sk("appraise", 1)],
        text="A knack in a phial. Grants a competence bonus on one skill, chosen when it is "
             "bound: the boots of elvenkind's, the cloak of elvenkind's."),
}

# --- the recipes ------------------------------------------------------------------------------
#
# Book documents. `B` marks one book; `power` is an item power (effectspec `item_power`,
# run by lane C's `use_item`); `tell` is a power that changes no number.

CRB_W = "https://legacy.aonprd.com/coreRulebook/magicItems/wondrousItems.html#"
CRB_R = "https://legacy.aonprd.com/coreRulebook/magicItems/rings.html#"
CRB_ROD = "https://legacy.aonprd.com/coreRulebook/magicItems/rods.html#"
UE = "https://legacy.aonprd.com/ultimateEquipment/wondrousItems/"


def B(spec: dict) -> dict:
    return {**spec, "book": True}


def bsk(skill, n):
    return B({"type": "skill_mod", "target": skill, "amount": n, "bonus_type": "competence"})


def bab(ability, n):
    return B({"type": "ability_mod", "target": ability, "amount": n,
              "bonus_type": "enhancement"})


def power(spell, uses="unlimited", count=None, cl=None, **kw):
    out = {"type": "item_power", "spell": spell, "uses": uses}
    if count:
        out["uses_count"] = count
    if cl:
        out["caster_level"] = cl
    out.update(kw)
    return B(out)


def tell(words, uses="unlimited", count=None):
    out = {"type": "item_power", "tell": words, "uses": uses}
    if count:
        out["uses_count"] = count
    return B(out)


def once(effect):
    return B({"type": "item_power", "effect": [effect], "uses": "once", "uses_count": 1})


def worn(spec):
    return B({**spec, "trigger": "worn"})


def bound(prop, **choice):
    return effectspec.bind(prop, choice)


def G(*names):
    """A recipe's essence needs: a property id grants it, `fam:x` names a family."""
    out = []
    for n in names:
        if n.startswith("fam:"):
            out.append({"family": n[4:], "count": 1})
        else:
            out.append({"grants": n, "count": 1})
    return out


CHA_SKILLS = ("bluff", "diplomacy", "disguise", "handle animal", "intimidate", "perform",
              "use magic device")

RECIPES: dict[str, dict] = {}


def recipe(rid, **kw):
    RECIPES[rid] = kw


for n in range(1, 6):
    recipe(f"mi-ring-protection-{n}", cl=5, creator_level=3 * n, vessel="ring",
           spells=[["shield-of-faith"]], book=bound("deflection", bonus=n),
           essences=G("deflection"), source=CRB_R + "ring-of-protection")
    recipe(f"mi-cloak-resistance-{n}", cl=5, creator_level=3 * n, vessel="shoulders",
           spells=[["resistance"]], book=bound("resistance", bonus=n),
           essences=G("resistance"), source=CRB_W + "cloak-of-resistance")
    recipe(f"mi-amulet-natural-armor-{n}", cl=5, creator_level=3 * n, vessel="neck",
           spells=[["barkskin"]], book=bound("natural-armour", bonus=n),
           essences=G("natural-armour"), source=CRB_W + "amulet-of-natural-armor")
TEMP = ("The book's bonus is a temporary one for the first 24 hours worn, then counts for "
        "hit points and skill ranks; here it is a standing bonus while worn.")
for ability, prop, belt, spell, anchor in (
        ("strength", "ability-strength", "belt", "bull-s-strength", "belt-of-giant-strength"),
        ("dexterity", "ability-dexterity", "belt", "cat-s-grace",
         "belt-of-incredible-dexterity"),
        ("constitution", "ability-constitution", "belt", "bear-s-endurance",
         "belt-of-mighty-constitution"),
        ("intelligence", "ability-intelligence", "headband", "fox-s-cunning",
         "headband-of-vast-intelligence"),
        ("wisdom", "ability-wisdom", "headband", "owl-s-wisdom",
         "headband-of-inspired-wisdom"),
        ("charisma", "ability-charisma", "headband", "eagle-s-splendor",
         "headband-of-alluring-charisma")):
    for n in (2, 4, 6):
        recipe(f"mi-{belt}-{ability}-{n}", cl=8, vessel=belt, spells=[[spell]],
               book=bound(prop, bonus=n), essences=G(prop), source=CRB_W + anchor,
               not_yet=[TEMP] + (["The headband's skill ranks are not granted."]
                                 if ability == "intelligence" else []))
for n in (1, 2, 4, 6, 8):
    recipe(f"mi-bracers-armor-{n}", cl=7, creator_level=2 * n, vessel="wrists",
           spells=[["mage-armor"]], book=bound("armour-bonus", bonus=n),
           essences=G("armour-bonus"), source=CRB_W + "bracers-of-armor",
           not_yet=["The book lets bracers carry armour special abilities; none are "
                    "offered here."])

recipe("mi-boots-striding", cl=3, vessel="feet", spells=[["longstrider"]],
       creator=["5 ranks in Acrobatics"],
       book=[B({"type": "speed", "target": "land", "amount": 10}), bsk("acrobatics", 5)],
       essences=G("skill-competence", "fam:speed"),
       source=CRB_W + "boots-of-striding-and-springing",
       not_yet=["The +5 is for jumps only in the book; here it is on every Acrobatics "
                "check.", "Speed changes are recorded, not yet run by the grid."])
recipe("mi-boots-elvenkind", cl=5, vessel="feet", spells=[], creator=["an elf"],
       book=bound("skill-competence", skill="acrobatics", bonus=5),
       essences=G("skill-competence"), source=CRB_W + "boots-of-elvenkind")
recipe("mi-boots-levitation", cl=3, vessel="feet", spells=[["levitate"]],
       book=[power("levitate", cl=3)], essences=G("fam:air"),
       source=CRB_W + "boots-of-levitation")
recipe("mi-boots-speed", cl=10, vessel="feet", spells=[["haste"]],
       book=[power("haste", "per_day", 1, cl=10)], essences=G("fam:speed"),
       source=CRB_W + "boots-of-speed",
       not_yet=["The book's ten rounds a day may be split across uses; here one use a day "
                "runs haste for its full duration."])
recipe("mi-cloak-elvenkind", cl=3, vessel="shoulders", spells=[["invisibility"]],
       creator=["an elf"], book=bound("skill-competence", skill="stealth", bonus=5),
       essences=G("skill-competence"), source=CRB_W + "cloak-of-elvenkind",
       not_yet=["Only with the hood drawn up, in the book."])
recipe("mi-gloves-swimming-climbing", cl=5, vessel="hands",
       spells=[["bull-s-strength"], ["cat-s-grace"]],
       book=[bsk("swim", 5), bsk("climb", 5)], essences=G("skill-competence"),
       source=CRB_W + "gloves-of-swimming-and-climbing")
recipe("mi-goggles-night", cl=3, vessel="eyes", spells=[["darkvision"]],
       book=[worn({"type": "sense", "target": "darkvision", "range": 60})],
       essences=G("fam:shadow"), source=CRB_W + "goggles-of-night")
recipe("mi-eyes-eagle", cl=3, vessel="eyes", spells=[["clairaudience-clairvoyance"]],
       book=bound("skill-competence", skill="perception", bonus=5),
       essences=G("skill-competence"), source=CRB_W + "eyes-of-the-eagle",
       not_yet=["Wearing one lens of the pair stuns for a round, in the book."])
recipe("mi-hat-disguise", cl=1, vessel="head", spells=[["disguise-self"]],
       book=[power("disguise-self", cl=1)], essences=G("fam:shadow"),
       source=CRB_W + "hat-of-disguise")
recipe("mi-circlet-persuasion", cl=5, vessel="head", spells=[["eagle-s-splendor"]],
       book=[bsk(s, 3) for s in CHA_SKILLS], essences=G("skill-competence"),
       source=CRB_W + "circlet-of-persuasion",
       not_yet=["The book's +3 is on every Charisma-based check; plain Charisma checks "
                "are not covered here, only the Charisma skills."])
recipe("mi-vest-escape", cl=4, vessel="chest", spells=[["knock"], ["grease"]],
       book=[bsk("disable device", 4), bsk("escape artist", 6)],
       essences=G("skill-competence"), source=CRB_W + "vest-of-escape")
recipe("mi-robe-useful-items", cl=9, vessel="body", spells=[["fabricate"]],
       book=[tell("A patch comes away and becomes the thing it pictures")],
       essences=G("fam:arcane"), source=CRB_W + "robe-of-useful-items",
       not_yet=["The patches are finite (two each of the standard eight and 4d4 more "
                "rolled on the book's table) and nothing counts them yet."])
recipe("mi-ring-feather-fall", cl=1, vessel="ring", spells=[["feather-fall"]],
       book=[power("feather-fall", cl=1)], essences=G("fam:air"),
       source=CRB_R + "ring-of-feather-falling",
       not_yet=["The book's ring works by itself on a fall of more than 5 feet; here it is "
                "used."])
recipe("mi-ring-jumping", cl=2, vessel="ring", spells=[],
       creator=["5 ranks in Acrobatics"], book=[bsk("acrobatics", 5)],
       essences=G("skill-competence"), source=CRB_R + "ring-of-jumping",
       not_yet=["The +5 is for high and long jumps only in the book; here it is on every "
                "Acrobatics check."])
recipe("mi-ring-swimming", cl=2, vessel="ring", spells=[], creator=["5 ranks in Swim"],
       book=bound("skill-competence", skill="swim", bonus=5),
       essences=G("skill-competence"), source=CRB_R + "ring-of-swimming")
recipe("mi-ring-climbing", cl=5, vessel="ring", spells=[], creator=["5 ranks in Climb"],
       book=bound("skill-competence", skill="climb", bonus=5),
       essences=G("skill-competence"), source=CRB_R + "ring-of-climbing")
recipe("mi-ring-invisibility", cl=3, vessel="ring", spells=[["invisibility"]],
       book=[power("invisibility", cl=3)], essences=G("fam:shadow"),
       source=CRB_R + "ring-of-invisibility")
recipe("mi-ring-freedom-movement", cl=7, vessel="ring", spells=[["freedom-of-movement"]],
       book=[worn({"type": "spell_effect", "target": "freedom-of-movement",
                   "caster_level": 7})],
       essences=G("fam:slick"), source=CRB_R + "ring-of-freedom-of-movement")
recipe("mi-ring-water-walking", cl=9, vessel="ring", spells=[["water-walk"]],
       book=[worn({"type": "spell_effect", "target": "water-walk", "caster_level": 9})],
       essences=G("fam:water"), source=CRB_R + "ring-of-water-walking")
recipe("mi-ring-sustenance", cl=5, vessel="ring", spells=[["create-food-and-water"]],
       book=[tell("The ring feeds and rests its wearer")], essences=G("fam:vigour"),
       source=CRB_R + "ring-of-sustenance",
       not_yet=["No need to eat or drink, and two hours of sleep serve as eight, after a "
                "week worn: the hunger, thirst and rest clocks do not read it yet."])
for n in (1, 2):
    recipe(f"mi-amulet-mighty-fists-{n}", cl=5, creator_level=3 * n, vessel="neck",
           spells=[["magic-fang-greater"]],
           book=[B({"type": "combat_mod", "target": t, "amount": n,
                    "bonus_type": "enhancement"}) for t in ("attack", "damage")],
           essences=G("enhancement"), source=CRB_W + "amulet-of-mighty-fists",
           not_yet=["The book's bonus is for unarmed attacks and natural weapons only; "
                    "here it is on every attack until the attack reads which it is.",
                    "The book lets the amulet carry melee special abilities; none are "
                    "offered here."])
recipe("mi-periapt-health", cl=5, vessel="neck", spells=[["remove-disease"]],
       book=[B({"type": "immunity", "target": "disease"})], essences=G("fam:vigour"),
       source=CRB_W + "periapt-of-health")
recipe("mi-brooch-shielding", cl=1, vessel="neck", spells=[["shield"]],
       book=[tell("The brooch drinks the force bolts meant for its wearer")],
       essences=G("fam:warding"), source=CRB_W + "brooch-of-shielding",
       not_yet=["It absorbs up to 101 points of magic missile damage and then melts; "
                "nothing counts the points yet."])
recipe("mi-gauntlets-rust", name="Gauntlet of Rust", cl=7, vessel="hands",
       spells=[["rusting-grasp"]], book=[power("rusting-grasp", "per_day", 1, cl=7)],
       essences=G("fam:acid"), source=CRB_W + "gauntlet-of-rust",
       not_yet=["The book's gauntlet also guards its wearer and her gear from rust, a rust "
                "monster's touch included."])
recipe("mi-belt-tumbling", cl=1, vessel="belt", spells=[["cat-s-grace"]],
       book=[bsk("acrobatics", 4)], essences=G("skill-competence"),
       source=UE + "belts.html#belt-of-tumbling",
       not_yet=["The +4 is for moving through a threatened square or an enemy's space "
                "only; here it is on every Acrobatics check."])
recipe("mi-headband-alluring-charisma-cha-skill", cl=8, vessel="headband",
       price=5100, spells=[["know-the-enemy"]],
       book=bound("ability-intelligence", bonus=2) + [
           tell("The headband fills the mind with what is known of a creature in sight",
                "per_day", 3)],
       essences=G("ability-intelligence", "fam:mind"),
       source=UE + "headbands.html#headband-of-ponderous-recollection",
       not_yet=[TEMP, "The power reveals a creature as a Knowledge check with a natural 5, "
                "then 10, then 15 on the next two turns; it is told, not rolled.",
                "The headband's skill ranks are not granted."])
recipe("mi-slippers-spider-climbing", cl=4, vessel="feet", spells=[["spider-climb"]],
       book=[power("spider-climb", "per_day", 1, cl=4)], essences=G("fam:earth"),
       source=CRB_W + "slippers-of-spider-climbing",
       not_yet=["The book's ten minutes a day may be split into one-minute uses; here it "
                "is one use a day."])
recipe("mi-cloak-bat", cl=7, vessel="shoulders", spells=[["beast-shape-iii"], ["fly"]],
       book=[bsk("stealth", 5), power("fly", cl=7), power("beast-shape-iii", cl=7)],
       essences=G("fam:shadow", "fam:air"), source=CRB_W + "cloak-of-the-bat",
       not_yet=["Both flying powers work only in darkness, last up to 7 minutes and then "
                "rest as long; the wearer can hang from a ceiling like a bat."])
recipe("mi-cloak-displacement-minor", cl=3, vessel="shoulders", spells=[["blur"]],
       book=[B({"type": "concealment", "miss_chance": 20})], essences=G("fam:light"),
       source=CRB_W + "cloak-of-displacement-minor")
recipe("mi-bag-holding-i", cl=9, vessel="slotless", spells=[["secret-chest"]],
       book=[tell("The bag takes in more than its size allows")],
       essences=G("fam:arcane"), source=CRB_W + "bag-of-holding",
       not_yet=["Holds 250 lb. in 30 cubic feet and weighs 15 lb. whatever is inside; the "
                "pack's weight is not yet read from it."])
recipe("mi-handy-haversack", cl=9, vessel="slotless", spells=[["secret-chest"]],
       book=[tell("What its wearer reaches for is always on top")],
       essences=G("fam:arcane"), source=CRB_W + "handy-haversack",
       not_yet=["Holds 120 lb. and weighs 5; drawing from it provokes no attack of "
                "opportunity. Neither is read yet."])
recipe("mi-figurine-serpentine-owl", cl=11, vessel="slotless", spells=[["animate-objects"]],
       book=[tell("The figurine becomes a living owl that serves its owner", "per_day", 1)],
       essences=G("fam:arcane"), source=CRB_W + "figurines-of-wondrous-power",
       not_yet=["Up to 8 hours a day as a horned owl or a giant owl; after the third giant "
                "owl it is spent. The owl is told, not yet a companion with a sheet."])
recipe("mi-immovable-rod", cl=10, vessel="rod", spells=[["levitate"]],
       creator=["Craft Rod (the book's feat for rods)"],
       book=[tell("The rod locks where it hangs and will not move")],
       essences=G("fam:earth"), source=CRB_ROD + "immovable-rod",
       not_yet=["It holds up to 8,000 lb.; a DC 30 Strength check shifts it 10 feet."])
recipe("mi-lantern-revealing", cl=5, vessel="slotless", spells=[["invisibility-purge"]],
       book=[power("invisibility-purge", cl=5)], essences=G("fam:light"),
       source=CRB_W + "lantern-of-revealing",
       not_yet=["In the book it works whenever the lantern is lit, with no use spent."])
recipe("mi-dust-appearance", cl=5, vessel="slotless", spells=[["glitterdust"]],
       book=[tell("The dust coats what was hidden and shows it", "once", 1)],
       essences=G("fam:light"), source=CRB_W + "dust-of-appearance",
       not_yet=["A 10-foot burst for 5 minutes: negates invisibility, blur and "
                "displacement, and a coated creature takes -30 on Stealth."])
recipe("mi-elixir-hiding", cl=5, vessel="slotless", spells=[["invisibility"]],
       book=[once({"type": "skill_mod", "target": "stealth", "amount": 10,
                   "bonus_type": "competence", "duration": {"amount": 1, "unit": "hour"}})],
       essences=G("fam:shadow"), source=CRB_W + "elixir-of-hiding")
recipe("mi-elixir-vision", cl=2, vessel="slotless", spells=[["true-seeing"]],
       book=[once({"type": "skill_mod", "target": "perception", "amount": 10,
                   "bonus_type": "competence", "duration": {"amount": 1, "unit": "hour"}})],
       essences=G("fam:light"), source=CRB_W + "elixir-of-vision")
recipe("mi-elixir-swimming", cl=2, vessel="slotless", spells=[],
       creator=["5 ranks in Swim"],
       book=[once({"type": "skill_mod", "target": "swim", "amount": 10,
                   "bonus_type": "competence", "duration": {"amount": 1, "unit": "hour"}})],
       essences=G("fam:water"), source=CRB_W + "elixir-of-swimming")
recipe("mi-elixir-truth", cl=5, vessel="slotless", spells=[["zone-of-truth"]],
       book=[tell("The drinker can say nothing but the truth", "once", 1)],
       essences=G("fam:mind"), source=CRB_W + "elixir-of-truth",
       not_yet=["Ten minutes, Will DC 13 negates, and a further save against each "
                "question: no save is rolled yet."])
recipe("mi-stone-good-luck", cl=5, vessel="slotless", spells=[["divine-favor"]],
       book=[B({"type": "save_mod", "target": s, "amount": 1, "bonus_type": "luck"})
             for s in ("fort", "ref", "will")],
       essences=G("fam:holy"), source=CRB_W + "stone-of-good-luck",
       not_yet=["The book's +1 luck bonus is on ability checks and skill checks as well; "
                "here only the saves."])
for n, word in ((1, "1st"), (2, "2nd"), (3, "3rd")):
    recipe(f"mi-pearl-power-{n}", cl=17, vessel="slotless", spells=[],
           creator=[f"able to cast {word}-level spells"],
           book=[tell("The pearl returns a spell already cast that day", "per_day", 1)],
           essences=G("fam:arcane"), source=CRB_W + "pearl-of-power",
           not_yet=[f"Recalls one {word}-level spell a prepared caster cast that day; the "
                    f"slot is not yet restored by it."])
recipe("mi-bead-force", cl=10, vessel="neck", spells=[["fireball"]],
       book=[power("fireball", "once", 1, cl=6), power("fireball", "once", 2, cl=4)],
       essences=G("fam:fire"), source=CRB_W + "necklace-of-fireballs",
       not_yet=["Type I: one 6d6 sphere and two 4d6, thrown up to 70 feet, Reflex DC 14 "
                "half; read as fireballs at caster level 6 and 4.",
                "A failed save against magical fire can set off every sphere left."])
recipe("mi-horn-fog", cl=3, vessel="slotless", spells=[["obscuring-mist"]],
       book=[power("obscuring-mist", cl=3)], essences=G("fam:water"),
       source=CRB_W + "horn-of-fog")
recipe("mi-rope-climbing", cl=3, vessel="slotless", spells=[["animate-rope"]],
       book=[tell("The rope climbs, knots and fastens itself where it is told")],
       essences=G("fam:air"), source=CRB_W + "rope-of-climbing",
       not_yet=["60 feet, holds 3,000 lb.; knotted, it lowers Climb DCs by 10."])
recipe("mi-goggles-minute-seeing", cl=3, vessel="eyes", spells=[["true-seeing"]],
       book=bound("skill-competence", skill="disable device", bonus=5),
       essences=G("skill-competence"), source=CRB_W + "goggles-of-minute-seeing",
       text="Book: +5 competence on Disable Device checks. The old row gave Perception; "
            "the book's lenses see fine work within a foot.")
recipe("mi-medallion-thoughts", cl=5, vessel="neck", spells=[["detect-thoughts"]],
       book=[power("detect-thoughts", cl=5)], essences=G("fam:mind"),
       source=CRB_W + "medallion-of-thoughts")
recipe("mi-boots-winterlands", cl=5, vessel="feet",
       spells=[["cat-s-grace"], ["endure-elements"], ["pass-without-trace"]],
       book=[worn({"type": "spell_effect", "target": "endure-elements",
                   "caster_level": 5})],
       essences=G("fam:cold"), source=CRB_W + "boots-of-the-winterlands",
       not_yet=["Travel over snow at full speed leaving no tracks, and over ice without "
                "slipping."],
       text="Book: warms the wearer as endure elements, and carries her over snow and ice. "
            "The old row's cold resistance 5 is not in the book and is gone.")
recipe("mi-glove-storing", cl=6, vessel="hands", spells=[["shrink-item"]],
       book=[tell("The glove takes the held thing into its palm, and gives it back at a "
                  "snap")],
       essences=G("fam:arcane"), source=CRB_W + "glove-of-storing",
       not_yet=["One item of up to 20 lb., stored or drawn as a free action."])
recipe("mi-quiver-ehlonna", cl=9, vessel="slotless", spells=[["secret-chest"]],
       book=[tell("The quiver holds far more than it should and gives up what is asked")],
       essences=G("fam:arcane"), source=CRB_W + "efficient-quiver",
       not_yet=["60 arrows, 18 javelins and 6 bows or staves, at 2 lb.; not yet read."])
recipe("mi-scarab-protection", cl=18, vessel="neck",
       spells=[["death-ward"], ["spell-resistance"]],
       book=[B({"type": "spell_resistance", "amount": 20})],
       essences=G("fam:abjuration"), source=CRB_W + "scarab-of-protection",
       not_yet=["Absorbs twelve energy drains, death effects or negative energy effects, "
                "then turns to powder.", "Spell resistance is recorded; the cast path "
                "rolls no check against it until lane C's reader lands."])
recipe("mi-mantle-spell-resistance", cl=9, vessel="chest", spells=[["spell-resistance"]],
       book=[B({"type": "spell_resistance", "amount": 21})],
       essences=G("fam:abjuration"), source=CRB_W + "mantle-of-spell-resistance",
       not_yet=["Spell resistance is recorded; the cast path rolls no check against it "
                "until lane C's reader lands."])
recipe("mi-ring-counterspells", cl=11, vessel="ring", spells=[["imbue-with-spell-ability"]],
       book=[tell("The spell held in the ring breaks the same spell cast at its wearer")],
       essences=G("fam:abjuration"), source=CRB_R + "ring-of-counterspells",
       not_yet=["Holds one spell of 1st to 6th level, cast into it; nothing stores it yet."])
recipe("mi-bracers-archery-lesser", cl=4, vessel="wrists", spells=[],
       creator=["Craft Magic Arms and Armor", "proficient with a longbow or shortbow"],
       book=[B({"type": "combat_mod", "target": "attack", "amount": 1,
                "bonus_type": "competence"})],
       essences=G("fam:keen"), source=CRB_W + "bracers-of-archery-lesser",
       not_yet=["The +1 is with bows only, and the bracers grant bow proficiency; here it "
                "is on every attack."],
       text="Book: +1 competence on attack rolls with bows. The old row also gave +1 "
            "damage, which is the greater bracers'.")
recipe("mi-belt-mighty-hurling", name="Belt of Mighty Hurling, Lesser", cl=8, vessel="belt",
       price=14000, spells=[["bull-s-strength"], ["longshot"]],
       book=bound("ability-strength", bonus=2), essences=G("ability-strength"),
       source=UE + "belts.html#Belt-of-Mighty-Hurling-lesser",
       not_yet=[TEMP, "Thrown weapons may use Strength for the attack instead of Dexterity, "
                "and their range increment gains 10 feet."],
       text="Ultimate Equipment: +2 enhancement to Strength; thrown weapons use Strength to "
            "hit and fly 10 feet further. The old row's +2 to attack was not the book's.")
recipe("mi-headband-mental-prowess", cl=12, vessel="headband",
       spells=[["fox-s-cunning"], ["owl-s-wisdom"]],
       book=bound("ability-intelligence", bonus=2) + bound("ability-wisdom", bonus=2),
       essences=G("ability-intelligence", "ability-wisdom"),
       source=CRB_W + "headband-of-mental-prowess",
       not_yet=[TEMP, "The book's two scores are chosen at making; this recipe is the "
                "Intelligence and Wisdom one."])
recipe("mi-belt-physical-perfection", cl=16, vessel="belt",
       spells=[["bear-s-endurance"], ["bull-s-strength"], ["cat-s-grace"]],
       book=(bound("ability-strength", bonus=2) + bound("ability-dexterity", bonus=2)
             + bound("ability-constitution", bonus=2)),
       essences=G("ability-strength", "ability-dexterity", "ability-constitution"),
       source=CRB_W + "belt-of-physical-perfection", not_yet=[TEMP])
recipe("mi-robe-eyes", cl=11, vessel="body", spells=[["true-seeing"]],
       book=[worn({"type": "sense", "target": "darkvision", "range": 120}),
             worn({"type": "sense", "target": "see_invisible", "range": 120}),
             bsk("perception", 10)],
       essences=G("fam:light", "skill-competence"), source=CRB_W + "robe-of-eyes",
       not_yet=["Sees in all directions: keeps its Dexterity bonus when flat-footed and "
                "cannot be flanked; sees the ethereal too.",
                "Cannot avert its eyes from a gaze; light blinds it for 1d3 minutes and "
                "daylight for 2d4."])
recipe("mi-ring-mindshield", name="Ring of Mind Shielding", cl=3, vessel="ring",
       spells=[["nondetection"]],
       book=[tell("Thoughts, lies and leanings cannot be read from the wearer")],
       essences=G("fam:mind"), source=CRB_R + "ring-of-mind-shielding",
       not_yet=["Immune to detect thoughts, discern lies and any magic that reads "
                "alignment; nothing casts those at the player yet."])
recipe("mi-amulet-proof-detection", cl=8, vessel="neck", spells=[["nondetection"]],
       book=[tell("Scrying and locating magic slide off the wearer")],
       essences=G("fam:shadow"),
       source=CRB_W + "amulet-of-proof-against-detection-and-location",
       not_yet=["As nondetection: a divination against the wearer needs a caster level "
                "check against DC 19."])
recipe("mi-crown-blasting-minor", cl=6, vessel="head", spells=[["searing-light"]],
       book=[power("searing-light", "per_day", 1, cl=6)], essences=G("fam:light"),
       source=CRB_W + "crown-of-blasting-minor")
recipe("mi-belt-dwarvenkind", cl=12, vessel="belt", spells=[["tongues"]],
       creator=["a dwarf"],
       book=[bab("con", 2), worn({"type": "sense", "target": "darkvision", "range": 60})],
       essences=G("ability-constitution", "fam:earth"), source=CRB_W + "belt-of-dwarvenkind",
       not_yet=["+4 competence on Charisma checks and Charisma skills with dwarves, +2 "
                "with gnomes and halflings, -2 with anyone else; speaks and reads Dwarven.",
                "The Constitution, darkvision, stonecunning and +2 resistance on saves "
                "against poison, spells and spell-like effects are for a wearer who is "
                "not a dwarf; here they apply to anyone."])

# Rows that could not be found in the book: not on the Core Rulebook's rings, wondrous items
# or rods pages, Ultimate Equipment's slot pages, or the Advanced Player's Guide's wondrous
# items and rings (all fetched 2026-10-05), nor by a web search. "Ground every name": a
# model wrote them as "Book:" items. Kept loadable for old saves, never offered as recipes;
# the owner decides in docs/enchanting-review.md whether to delete them or keep them as
# house items with house numbers.
UNSOURCED = {
    "mi-periapt-wisdom": "Periapt of Wisdom is D&D 3.5's; Pathfinder's is the headband of "
                         "inspired wisdom.",
    "mi-vest-resistance": "Found only on a fan site, not on AoN.",
    "mi-shirt-gliding": "Not found.",
    "mi-gauntlet-infinite-blades": "Not found (the id and the name disagree, too).",
    "mi-cap-water-breathing": "Not found; Ultimate Equipment has a cap of the free "
                              "thinker, a different item.",
    "mi-sandals-quiet-tread": "Not found.",
    "mi-bracelet-steady-hand": "Not found.",
    "mi-goggles-charming": "Not found; the Core Rulebook's eyes of charming are a "
                           "different item at 56,000 gp.",
    "mi-shield-ring-arrow-deflection": "Not found; arrow deflection is a shield property "
                                       "(lane A's table).",
    "mi-headband-recall": "Not found.",
}

VESSEL_NOTE = ("Retired 2026-10-05 (enchanting plan §7.3): a vessel is a real item record "
               "now, picked from the rack; this entry stays loadable for old saves and is "
               "never offered.")

ENCHANTER_NOTE = (
    "The enchanter's shelf. Kinds: essence (what is bound), focus (the stone a ring or "
    "amulet is set with), ink / chalk / salt (the circle's materials, consumed by "
    "Prepare), catalyst (eases the binding; `dc_mod`), treatment (vessel preparation), "
    "vessel (retired: vessels are real item records now). An essence's enchanting "
    "fields, read through rules/materials.py (docs/enchanting-contracts.md §5): `grants` "
    "(a property in content/rules/magic-properties.json, or an enhancement step), "
    "`motes` (potency: 1 mote = 100 gp of the book's making cost; a bought essence "
    "carries exactly what its grant costs to make and sells for motes x 100), `tier` "
    "(the band of the market value its motes carry, the magic items' price bands), "
    "`family` and its `phase` of the day (the `families` table; never a planet), "
    "`polarity`, `affinity`, `house` (small typed top-ups, scaled by binding quality, "
    "for the owner's review in docs/enchanting-review.md), `working` and `color`. "
    "`effects`, `drawbacks`, `prefers`, `plus`, `adjective` and `binds_at` are the "
    "pre-revamp fields rules/enchanter.py still reads until its bench moves. Written by "
    "tools/enchant_data_pass.py.")

ITEMS_NOTE_ADD = (
    " Wondrous rows are also the enchanter's recipes (docs/enchanting-contracts.md §5, "
    "read through rules/materials.recipes()): `book` (what the item does, by hand from "
    "the AoN page in `source`), `spells` (groups, any one of each), `caster_level` and "
    "`creator_level` (the book's two numbers, kept apart), `creator` (the book's other "
    "creator clauses), `essences` (the grants or families a binding needs), `not_yet` "
    "(every clause nothing runs yet). `tier` is the price band (under 1,000 gp common, "
    "5,000 uncommon, 20,000 rare, 50,000 exotic, then legendary), checked on load. "
    "`retired` rows could not be found in the book and are never offered.")


# --- building ---------------------------------------------------------------------------------

def _grant_cost(grants, polarity):
    return materials.grant_motes(grants, polarity)


def build_essence(raw: dict, spec: tuple) -> dict:
    family, polarity, grants, house, motes = spec
    fam = FAMILIES[family]
    out = dict(raw)
    cost = _grant_cost(grants, polarity)
    motes = cost if motes is None else max(motes, cost)
    out.update({
        "family": family, "polarity": polarity, "grants": copy.deepcopy(grants),
        "motes": motes, "tier": materials.essence_tier(motes), "form": "phial",
        "affinity": list(fam["affinity"]), "house": copy.deepcopy(house),
        "working": [{"type": "working", "trait": t} for t in fam["working"]],
        "color": fam["color"],
    })
    out.pop("phase", None)          # the family's, filled on load
    if out.get("obtain") == "bought":
        out["price_gp"] = motes * materials.MOTE_GP
    else:
        out.pop("price_gp", None)
    if out["grants"] is None:
        out.pop("grants")
    return out


def build_new_essence(mid: str, d: dict) -> dict:
    fam = FAMILIES[d["family"]]
    motes = _grant_cost(d["grants"], d["polarity"])
    return {
        "id": mid, "name": d["name"], "kind": "essence",
        "tier": materials.essence_tier(motes), "obtain": "bought", "text": d["text"],
        "effects": [], "drawbacks": [], "family": d["family"],
        "prefers": "", "polarity": d["polarity"], "grants": copy.deepcopy(d["grants"]),
        "motes": motes, "price_gp": motes * materials.MOTE_GP, "form": "phial",
        "affinity": list(fam["affinity"]), "house": copy.deepcopy(d["house"]),
        "working": [{"type": "working", "trait": t} for t in fam["working"]],
        "color": fam["color"],
    }


def build_recipe(raw: dict, spec: dict) -> dict:
    out = dict(raw)
    price = spec.get("price", raw.get("price_gp"))
    out.update({
        "name": spec.get("name", raw.get("name")),
        "price_gp": price,
        "caster_level": spec["cl"],
        "vessel": spec["vessel"],
        "book": copy.deepcopy(spec["book"]),
        "spells": copy.deepcopy(spec["spells"]),
        "essences": copy.deepcopy(spec["essences"]),
        "source": spec["source"],
        "not_yet": list(spec.get("not_yet") or []),
        "tier": materials.tier_for_price(price),
    })
    if spec.get("creator_level"):
        out["creator_level"] = spec["creator_level"]
    else:
        out.pop("creator_level", None)
    if spec.get("creator"):
        out["creator"] = list(spec["creator"])
    else:
        out.pop("creator", None)
    # The old reader's single prerequisite: the first spell of the first group, or none.
    first = spec["spells"][0][0] if spec["spells"] else None
    if first:
        out["spell"] = first
    if spec.get("text"):
        out["text"] = spec["text"]
    out.pop("retired", None)
    out.pop("why_retired", None)
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    ench = json.loads(ENCHANTER.read_text(encoding="utf-8"))
    items = json.loads(ITEMS.read_text(encoding="utf-8"))

    # Families first: an essence's phase is read from them.
    ench_rows = []
    seen = set()
    for raw in ench["materials"]:
        mid = raw["id"]
        seen.add(mid)
        if raw.get("kind") == "essence":
            if mid not in ESSENCES:
                print(f"NO PLAN for essence {mid}")
                return 1
            ench_rows.append(build_essence(raw, ESSENCES[mid]))
        elif raw.get("kind") == "vessel":
            row = dict(raw)
            row["retired"] = True
            row["why_retired"] = VESSEL_NOTE
            ench_rows.append(row)
        else:
            ench_rows.append(dict(raw))
    for mid, d in NEW_ESSENCES.items():
        if mid not in seen:
            ench_rows.append(build_new_essence(mid, d))
    missing = set(ESSENCES) - seen
    if missing:
        print(f"planned essences not in the file: {sorted(missing)}")
        return 1

    item_rows = []
    planned = set(RECIPES) | set(UNSOURCED)
    for raw in items["materials"]:
        rid = raw["id"]
        if raw.get("kind") != "wondrous":
            item_rows.append(raw)
            continue
        if rid in RECIPES:
            item_rows.append(build_recipe(raw, RECIPES[rid]))
        elif rid in UNSOURCED:
            row = dict(raw)
            row["retired"] = True
            row["why_retired"] = "Not in the book: " + UNSOURCED[rid]
            row["tier"] = materials.tier_for_price(row.get("price_gp"))
            item_rows.append(row)
        else:
            print(f"NO PLAN for wondrous {rid}")
            return 1
    unknown = planned - {r["id"] for r in items["materials"]}
    if unknown:
        print(f"planned recipes not in the file: {sorted(unknown)}")
        return 1

    new_ench = {"source": ench.get("source"), "note": ENCHANTER_NOTE,
                "families": FAMILIES, "materials": ench_rows}
    note = items.get("note", "")
    if ITEMS_NOTE_ADD.strip() not in note:
        note = note + ITEMS_NOTE_ADD
    new_items = {"source": items.get("source"), "note": note, "materials": item_rows}

    problems = check(new_ench, new_items)
    for p in problems:
        print(p)
    moved = [(r["id"], r["name"], o["tier"], r["tier"], r["price_gp"])
             for r, o in zip(item_rows, items["materials"])
             if r.get("kind") == "wondrous" and r["tier"] != o["tier"]]
    print(f"{len(problems)} problem(s). Essences: "
          f"{sum(1 for r in ench_rows if r.get('kind') == 'essence')}; recipes: "
          f"{len(RECIPES)} (+{len(UNSOURCED)} retired); wondrous rows re-tiered: "
          f"{len(moved)}.")
    if problems:
        return 1
    if apply:
        ENCHANTER.write_text(json.dumps(new_ench, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        ITEMS.write_text(json.dumps(new_items, indent=1, ensure_ascii=False) + "\n",
                         encoding="utf-8")
        materials.refresh()
        print("written.")
    return 0


def check(new_ench: dict, new_items: dict) -> list[str]:
    """Validate the batch as it is about to be written (the shelf as rewritten, never as it
    was), through the same functions the loaders use."""
    shelf = materials.all()
    docs = {}
    for raw in new_ench["materials"]:
        doc = materials.normalise(raw, materials.ENCHANT_CATALOGUE)
        if doc["kind"] == "essence":
            doc["phase"] = FAMILIES.get(doc["family"], {}).get("phase", "")
        docs[doc["id"]] = doc
    shelf.update(docs)
    out = materials.family_problems(new_ench["families"], shelf=shelf)
    essences = {k: d for k, d in docs.items() if d["kind"] == "essence"}
    for d in essences.values():
        out.extend(materials.essence_problems(d, shelf=shelf, fams=new_ench["families"]))
    out.extend(pricing.material_price_problems(new_ench["materials"],
                                               "enchanter-materials.json"))
    out.extend(materials.magic_item_tier_problems(new_items["materials"]))
    for raw in new_items["materials"]:
        if raw.get("kind") == "wondrous" and not raw.get("retired"):
            out.extend(materials.recipe_problems(materials.normalise_recipe(raw),
                                                 essences=essences))
    return out


if __name__ == "__main__":
    sys.exit(main())
