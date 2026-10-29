"""The app's own people: a role, a class, a ladder of levels, built by the rules.

Why these roles (measured 2026-10-28, docs/compiled-bestiary-plan.md step 4): every person
the game fields comes through one chooser (`rules/npcs.choose`), and an inventory of every
caller found 378 role-word sets — jobs, keepers, roads, schemes, openings, backgrounds,
market counters. Asked at every level 1-20, 4,341 of the 7,560 requests already fell to the
hand-written floor (a guildhand, watchman or thug) with the adventures loaded, and 919 more
fell or worsened under option D (the rulebook line only). The 65 fixed-source word sets
that lost are this roster's brief. Read against the world rather than the arithmetic: a
farmer is a commoner 1-3 at any party level, so the trades get rungs at 1-3 and the floor
stands above them; professionals ladder to about 12; officers and fighters to 20.

Every role is world-agnostic — a job and nothing else, no person's name, no setting word —
because the world supplies the rest (World Bible's peoples, the game's own names). Every
number comes out of `rules/npc_builds.py` (CRB Chapter 14), and a build the rules refuse
stops this script with the fix named. Feats are taken greedily from an ordered pool, each
checked against `feats.meets` on the sheet as it stands; gear is what the class may use.

    python tools/build_npc_roster.py      # writes content/npc-builds/people.json
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

from rules import feats, npc_builds  # noqa: E402

# --- archetypes: the class, the preset, the feat pool, the gear by level -----------------------

ARMOUR_LADDER = {  # (level at least, armour, shield) for a class with all armour
    "heavy": [(1, "scale mail", "heavy shield"), (4, "chainmail", "heavy shield"),
              (8, "banded mail", "heavy shield"), (12, "half-plate", "heavy shield"),
              (16, "full plate", "heavy shield")],
    "light": [(1, "leather", "none"), (4, "studded leather", "none"),
              (8, "chain shirt", "none")],
    "none": [(1, "none", "none")],
    "padded": [(1, "padded", "none")],
}

ARCHETYPES = {
    "commoner": {"class": "commoner", "preset": "skill", "armour": "none",
                 "feats": ["Toughness", "Skill Focus ($skill)", "Endurance", "Great Fortitude",
                           "Iron Will", "Diehard", "Lightning Reflexes", "Run", "Alertness",
                           "Self-Sufficient", "Athletic"]},
    "expert": {"class": "expert", "preset": "skill", "armour": "light",
               "feats": ["Skill Focus ($skill)", "Skill Focus ($skill2)", "Alertness",
                         "Persuasive", "Iron Will", "Toughness", "Improved Initiative",
                         "Deceitful", "Deft Hands", "Stealthy", "Great Fortitude",
                         "Lightning Reflexes", "Self-Sufficient", "Endurance", "Diehard",
                         "Athletic", "Magical Aptitude", "Animal Affinity", "Dodge", "Run"]},
    "warrior": {"class": "warrior", "preset": "melee", "armour": "heavy",
                "feats": ["Power Attack", "Toughness", "Weapon Focus ($weapon)",
                          "Improved Initiative", "Cleave", "Iron Will", "Dodge",
                          "Great Cleave", "Vital Strike", "Improved Critical ($weapon)",
                          "Combat Reflexes", "Great Fortitude", "Lightning Reflexes",
                          "Mobility", "Endurance", "Diehard", "Shield Focus", "Alertness",
                          "Run", "Athletic"]},
    "ranger-ish": {"class": "warrior", "preset": "ranged", "armour": "light",
                   "feats": ["Point-Blank Shot", "Precise Shot", "Weapon Focus ($weapon)",
                             "Rapid Shot", "Toughness", "Improved Initiative", "Dodge",
                             "Lightning Reflexes", "Iron Will", "Mobility", "Endurance",
                             "Great Fortitude", "Alertness", "Run", "Athletic", "Diehard"]},
    "adept": {"class": "adept", "preset": "divine", "armour": "none",
              "feats": ["Toughness", "Combat Casting", "Skill Focus ($skill)", "Iron Will",
                        "Self-Sufficient", "Great Fortitude", "Improved Initiative",
                        "Lightning Reflexes", "Alertness", "Endurance", "Diehard",
                        "Brew Potion", "Scribe Scroll", "Magical Aptitude"]},
    "aristocrat": {"class": "aristocrat", "preset": "skill", "armour": "light",
                   "feats": ["Skill Focus ($skill)", "Persuasive", "Iron Will",
                             "Weapon Focus ($weapon)", "Alertness", "Dodge", "Toughness",
                             "Improved Initiative", "Combat Expertise", "Deceitful",
                             "Mobility", "Lightning Reflexes", "Great Fortitude",
                             "Weapon Finesse", "Combat Reflexes", "Endurance"]},
}

# --- the roles: id word(s), archetype, rungs, skills, weapon, where they are, one line -----------
#
# The id carries the word a caller asks for (`npcs._hits`: exact, a plural, or a prefix of
# five letters or more), so "laborer" and "dockworker" are two roles, not one.

ROLES = [
    # trades: commoners at 1-3
    ("farmer", "commoner", [1, 3], ["profession", "handle animal", "survival", "climb"],
     "sickle", ["farmland"], "Works the fields from first light, and knows the weather by its smell."),
    ("villager", "commoner", [1, 3], ["perception", "profession", "craft", "climb"],
     "club", ["farmland", "grassland", "forest", "hills"], "Lives where the road thins out, and knows every face on it."),
    ("peasant", "commoner", [1], ["profession", "handle animal", "perception"],
     "quarterstaff", ["farmland"], "Owes the land more than it owes back."),
    ("servant", "commoner", [1, 3], ["perception", "profession", "craft"],
     "dagger", ["urban"], "Fetches, carries and overhears."),
    ("attendant", "commoner", [1, 3], ["perception", "profession", "ride"],
     "dagger", ["urban"], "Stands a step behind someone more important."),
    ("gardener", "commoner", [1, 3], ["profession", "craft", "perception"],
     "sickle", ["urban", "farmland"], "Keeps green things growing behind someone else's walls."),
    ("laborer", "commoner", [1, 3, 5], ["climb", "profession", "swim"],
     "club", ["urban", "farmland"], "Lifts, hauls and digs for a day's coin."),
    ("dockworker", "commoner", [1, 3], ["swim", "climb", "profession"],
     "club", ["urban", "coast"], "Loads and unloads cargo where the boats come in."),
    ("teamster", "commoner", [1, 3], ["handle animal", "ride", "profession", "perception"],
     "club", ["grassland", "farmland", "hills", "desert"], "Drives a wagon and its animals, and knows every rut on the road."),
    ("drover", "commoner", [1, 3], ["handle animal", "ride", "survival", "perception"],
     "quarterstaff", ["grassland", "hills", "farmland"], "Moves herds over long roads to market."),
    ("ostler", "commoner", [1, 3], ["handle animal", "ride", "profession"],
     "club", ["urban"], "Grooms, feeds and saddles other people's horses."),
    ("fisher", "commoner", [1, 3], ["swim", "profession", "survival"],
     "shortspear", ["coast", "water"], "Lives off what the water gives up."),
    ("ferryman", "commoner", [1, 3], ["swim", "profession", "perception"],
     "quarterstaff", ["coast", "water", "swamp"], "Takes people across for a fee, and remembers who crossed."),
    ("townsfolk", "commoner", [1], ["profession", "perception", "craft"],
     "club", ["urban"], "One of the many people a town is made of."),
    # Sleight of hand and stealth first: the street's cutpurse is an urchin, and the first
    # roster's had neither, so its theft was refused as untrained (2026-10-28).
    ("urchin", "commoner", [1], ["sleight of hand", "stealth", "climb", "perception"],
     "dagger", ["urban"], "Lives on the street and knows its back ways."),
    ("cook", "commoner", [1, 3], ["profession", "craft", "perception"],
     "dagger", ["urban"], "Feeds a house, an inn or a camp."),
    ("brewer", "expert", [1, 3], ["craft", "profession", "appraise", "perception", "diplomacy"],
     "club", ["urban", "farmland"], "Turns grain into ale and gossip into custom."),
    ("traveler", "commoner", [1, 3], ["perception", "ride", "climb", "swim"],
     "quarterstaff", ["grassland", "forest", "hills", "farmland"], "Somebody on the road for reasons of their own."),
    # trade and town: experts
    ("peddler", "expert", [1, 3], ["appraise", "bluff", "diplomacy", "profession", "sense motive"],
     "dagger", ["urban", "farmland", "grassland"], "Carries a pack of small goods from door to door."),
    ("stallholder", "expert", [1, 3], ["appraise", "diplomacy", "profession", "sense motive", "bluff"],
     "dagger", ["urban"], "Keeps a stall in the market and an eye on everyone at it."),
    ("shopkeeper", "expert", [1, 3, 6], ["appraise", "diplomacy", "profession", "sense motive", "perception"],
     "light-crossbow", ["urban"], "Runs a shop, its ledger and its door."),
    ("merchant", "expert", [1, 3, 6, 9], ["appraise", "diplomacy", "sense motive", "bluff", "profession", "linguistics"],
     "dagger", ["urban"], "Buys low, sells high, and remembers both prices."),
    ("trader", "expert", [1, 3, 6], ["appraise", "diplomacy", "sense motive", "ride", "profession", "linguistics"],
     "dagger", ["urban", "grassland", "desert"], "Moves goods between places that each want what the other has."),
    ("clerk", "expert", [1, 3, 6, 9], ["linguistics", "profession", "appraise", "sense motive", "knowledge (local)"],
     "dagger", ["urban"], "Keeps the records somebody will one day need."),
    ("artisan", "expert", [1, 3, 6], ["craft", "appraise", "profession", "perception", "diplomacy"],
     "club", ["urban"], "Makes fine things with practised hands."),
    ("craftsman", "expert", [1, 3, 6], ["craft", "appraise", "profession", "perception"],
     "club", ["urban", "farmland"], "Makes useful things and mends broken ones."),
    ("barkeep", "expert", [1, 3, 6], ["profession", "sense motive", "diplomacy", "perception", "intimidate"],
     "club", ["urban"], "Pours, listens and decides who has had enough."),
    ("innkeeper", "expert", [1, 3, 6], ["profession", "diplomacy", "sense motive", "appraise", "perception"],
     "club", ["urban", "grassland"], "Keeps the beds, the board and the peace under one roof."),
    ("blacksmith", "expert", [1, 4, 8, 12, 16], ["craft", "appraise", "profession", "perception", "intimidate"],
     "light-mace", ["urban", "farmland"], "Works iron at the forge, and knows a good blade from a bad one."),
    ("smith", "expert", [1, 4, 8, 12, 16], ["craft", "appraise", "profession", "perception"],
     "light-mace", ["urban", "farmland"], "Shapes metal into tools and blades."),
    ("weaponsmith", "expert", [2, 6, 10], ["craft", "appraise", "profession", "perception"],
     "light-mace", ["urban"], "Forges weapons and tests every edge."),
    ("armorer", "expert", [2, 6, 10], ["craft", "appraise", "profession", "perception"],
     "light-mace", ["urban"], "Fits armour to the body that will trust its life to it."),
    ("alchemist", "expert", [2, 5, 8, 12], ["craft", "appraise", "heal", "knowledge (nature)", "spellcraft", "profession"],
     "dagger", ["urban"], "Mixes reagents into cures, poisons and sometimes both."),
    ("apothecary", "expert", [1, 4, 8], ["heal", "craft", "knowledge (nature)", "profession", "appraise"],
     "dagger", ["urban"], "Sells remedies, and knows which ones work."),
    ("herbalist", "expert", [1, 4, 8], ["heal", "knowledge (nature)", "survival", "profession", "craft"],
     "sickle", ["forest", "farmland", "hills"], "Gathers and prepares the plants that heal or harm."),
    ("sailor", "expert", [1, 4, 8, 12, 16], ["swim", "climb", "profession", "acrobatics", "perception"],
     "dagger", ["coast", "water"], "Lives on a deck and trusts the rigging more than the land."),
    ("harbormaster", "expert", [4, 8, 12, 16, 20], ["profession", "diplomacy", "sense motive", "intimidate", "knowledge (local)", "swim"],
     "light-crossbow", ["coast", "urban"], "Says which ships may berth, and what they owe for it."),
    ("customs-officer", "expert", [3, 6, 9, 12, 15], ["appraise", "sense motive", "perception", "diplomacy", "intimidate", "linguistics"],
     "light-crossbow", ["urban", "coast"], "Counts what comes through the gate, and what it owes."),
    ("thief", "expert", [1, 4, 8, 12, 16], ["stealth", "sleight of hand", "disable device", "acrobatics", "perception", "bluff", "climb", "escape artist"],
     "dagger", ["urban"], "Takes what is not theirs and is gone before it is missed."),
    ("pickpocket", "expert", [1, 3], ["sleight of hand", "stealth", "bluff", "acrobatics", "perception"],
     "dagger", ["urban"], "Works crowds with light fingers."),
    ("smuggler", "expert", [2, 6, 10, 14], ["stealth", "bluff", "sense motive", "swim", "profession", "appraise", "perception"],
     "dagger", ["coast", "urban"], "Moves goods where the law would rather they did not go."),
    ("fixer", "expert", [2, 5, 8, 12], ["diplomacy", "sense motive", "bluff", "knowledge (local)", "appraise", "intimidate"],
     "dagger", ["urban"], "Knows who can get what, and takes a cut for knowing."),
    ("broker", "expert", [2, 5, 8, 12], ["appraise", "diplomacy", "sense motive", "bluff", "linguistics"],
     "dagger", ["urban"], "Arranges deals between people who would rather not meet."),
    ("informant", "expert", [1, 4], ["sense motive", "perception", "bluff", "stealth", "knowledge (local)"],
     "dagger", ["urban"], "Sells what they hear, to whoever pays most."),
    ("spy", "expert", [3, 7, 11, 15], ["bluff", "disguise", "stealth", "sense motive", "perception", "linguistics", "sleight of hand"],
     "dagger", ["urban"], "Is somebody else, for long enough to learn a secret."),
    ("sage", "expert", [3, 7, 11, 15], ["knowledge (arcana)", "knowledge (history)", "linguistics", "knowledge (nature)", "knowledge (planes)", "spellcraft", "knowledge (religion)"],
     "quarterstaff", ["urban"], "Has read more than most people will ever see."),
    ("scholar", "expert", [2, 6], ["knowledge (history)", "linguistics", "knowledge (local)", "knowledge (nobility)", "profession"],
     "quarterstaff", ["urban"], "Studies the past for what it says about now."),
    ("performer", "expert", [1, 4, 8], ["perform", "bluff", "diplomacy", "acrobatics", "sleight of hand"],
     "dagger", ["urban"], "Entertains for coin, and remembers every crowd."),
    ("poacher", "expert", [1, 4], ["stealth", "survival", "perception", "handle animal", "climb"],
     "light-crossbow", ["forest", "hills", "grassland"], "Hunts where hunting is forbidden."),
    # fighters: warriors
    ("soldier", "warrior", [1, 4, 8, 12, 16], ["intimidate", "climb", "ride", "swim"],
     "longsword", ["urban", "grassland", "hills"], "Serves under orders, with spear and shield."),
    ("fighter", "warrior", [1, 4, 8, 12, 16], ["intimidate", "climb", "swim"],
     "longsword", ["urban", "grassland", "hills", "forest"], "Makes a living with a blade."),
    ("officer", "warrior", [3, 7, 11, 15, 19], ["intimidate", "ride", "profession"],
     "longsword", ["urban"], "Gives the orders the soldiers follow."),
    ("captain", "warrior", [4, 8, 12, 16, 20], ["intimidate", "ride", "profession"],
     "longsword", ["urban", "coast"], "Commands a company, a watch or a ship."),
    ("warden", "warrior", [3, 7, 11, 15, 19], ["intimidate", "climb", "ride"],
     "longsword", ["urban", "forest", "hills"], "Keeps a place and what is kept in it."),
    ("jailer", "warrior", [1, 4, 8, 12], ["intimidate", "climb", "profession"],
     "club", ["urban"], "Holds the keys, and the prisoners behind them."),
    ("pit-fighter", "warrior", [2, 6, 10], ["intimidate", "climb", "swim"],
     "battleaxe", ["urban"], "Fights for a crowd and a purse."),
    ("gladiator", "warrior", [1, 5, 9], ["intimidate", "climb", "swim"],
     "trident", ["urban"], "Fights in the arena, and plays to the stands."),
    ("brawler", "warrior", [1, 4, 8], ["intimidate", "climb", "swim"],
     "club", ["urban"], "Settles things with fists and whatever is to hand."),
    ("bandit", "warrior", [1, 3, 6, 9], ["intimidate", "climb", "ride", "swim"],
     "shortsword", ["grassland", "forest", "hills", "desert"], "Takes from travellers what they will not give."),
    ("rustler", "warrior", [2, 5, 8], ["ride", "handle animal", "intimidate"],
     "shortsword", ["grassland", "hills"], "Steals herds by night and sells them by day."),
    ("hunter", "ranger-ish", [1, 4, 8], ["climb", "swim", "handle animal", "intimidate"],
     "longbow", ["forest", "hills", "grassland", "mountain"], "Lives by the bow and the patience to use it."),
    ("thug", "warrior", [1, 3, 6, 9], ["intimidate", "climb", "swim"],
     "club", ["urban"], "Is paid to make people afraid, and is good at it."),
    ("cutthroat", "expert", [1, 4, 8, 12], ["stealth", "intimidate", "bluff", "perception", "acrobatics"],
     "dagger", ["urban"], "Does the work nobody else will, for the right price."),
    ("ruffian", "warrior", [1, 3, 6], ["intimidate", "climb", "swim"],
     "club", ["urban"], "Starts fights and seldom finishes losing them."),
    ("raider", "warrior", [1, 4, 8, 12], ["intimidate", "ride", "climb", "swim"],
     "battleaxe", ["grassland", "hills", "coast", "forest"], "Strikes fast, takes what can be carried, and is gone."),
    ("marauder", "warrior", [2, 6, 10], ["intimidate", "ride", "climb"],
     "light-flail", ["grassland", "hills", "desert"], "Roams in a band that lives by plunder."),
    ("looter", "commoner", [1, 3], ["perception", "climb", "profession"],
     "club", ["urban", "ruins"], "Picks over what others left behind."),
    ("outlaw", "warrior", [1, 4, 8], ["intimidate", "ride", "climb", "swim"],
     "shortsword", ["forest", "hills", "grassland"], "Lives beyond the law's reach and means to stay there."),
    ("pirate", "warrior", [1, 4, 8, 12], ["swim", "climb", "intimidate", "profession"],
     "cutlass", ["coast", "water"], "Takes ships, and the cargo in them."),
    ("mercenary", "warrior", [2, 6, 10, 14], ["intimidate", "ride", "climb", "swim"],
     "longsword", ["urban", "grassland", "hills"], "Fights for whoever pays, until they stop paying."),
    ("guardsman", "warrior", [1, 4, 8], ["intimidate", "climb", "ride"],
     "longspear", ["urban"], "Walks a wall or a gate, and stops whoever should be stopped."),
    ("rider", "warrior", [1, 5, 10, 15, 19], ["ride", "handle animal", "intimidate"],
     "lance", ["grassland", "hills"], "Fights from the saddle and trusts the horse."),
    ("commoner", "commoner", [1, 3], ["profession", "perception", "craft", "climb"],
     "club", ["urban", "farmland"], "An ordinary person going about an ordinary day."),
    ("driver", "commoner", [1, 3], ["handle animal", "ride", "profession"],
     "quarterstaff", ["urban", "grassland", "farmland"], "Drives a cart or a carriage for whoever hires it."),
    ("apprentice", "commoner", [1, 3], ["craft", "profession", "perception"],
     "club", ["urban"], "Learns a trade at a master's elbow."),
    ("scribe", "expert", [1, 3, 6], ["linguistics", "profession", "knowledge (local)", "knowledge (history)", "craft"],
     "dagger", ["urban"], "Copies, records and reads aloud what others cannot."),
    ("saboteur", "expert", [3, 7, 11, 15], ["disable device", "stealth", "bluff", "disguise", "perception", "craft"],
     "dagger", ["urban"], "Breaks what others built, and is gone before the noise."),
    ("leader", "aristocrat", [2, 6, 10, 14], ["diplomacy", "sense motive", "intimidate", "knowledge (local)", "bluff"],
     "longsword", ["urban", "grassland", "hills"], "Speaks for others, and is followed."),
    ("representative", "aristocrat", [3, 7, 11], ["diplomacy", "sense motive", "knowledge (nobility)", "bluff", "linguistics"],
     "rapier", ["urban"], "Carries someone else's authority, and their instructions."),
    ("priestess", "adept", [1, 3, 6, 9, 12], ["heal", "knowledge (religion)", "spellcraft", "craft"],
     "club", ["urban", "farmland"], "Tends a shrine and the people who come to it."),
    ("shrine-keeper", "adept", [1, 4, 8], ["heal", "knowledge (religion)", "craft", "profession"],
     "quarterstaff", ["urban", "farmland", "hills"], "Keeps a small holy place swept and lit."),
    # faith and rank
    ("priest", "adept", [1, 3, 6, 9, 12], ["heal", "knowledge (religion)", "spellcraft", "craft"],
     "club", ["urban", "farmland"], "Tends a shrine and the people who come to it."),
    ("healer", "adept", [1, 4, 8], ["heal", "knowledge (nature)", "survival", "craft"],
     "quarterstaff", ["urban", "farmland", "forest"], "Mends what can be mended, and knows what cannot."),
    ("patron", "aristocrat", [2, 5, 8], ["diplomacy", "sense motive", "appraise", "knowledge (nobility)", "bluff"],
     "rapier", ["urban"], "Pays for things done in their name."),
    ("noble", "aristocrat", [1, 4, 8, 12, 16], ["diplomacy", "knowledge (nobility)", "ride", "sense motive", "intimidate", "bluff"],
     "rapier", ["urban"], "Born to rank, and expects it to be noticed."),
]


# Where a role's score goes, when its archetype's would be wrong for it: a thief who is an
# expert still lives by Dex, not the skill preset's Int (the first run built an 8th-level
# thief at Dex 12, Int 17), and a commoner's +2 is labour, not learning.
OVERRIDES = {
    "thief": {"preset": "ranged", "primary": "dex"}, "pickpocket": {"preset": "ranged", "primary": "dex"},
    "spy": {"preset": "ranged", "primary": "dex"}, "smuggler": {"preset": "ranged", "primary": "dex"},
    "poacher": {"preset": "ranged", "primary": "dex"}, "performer": {"primary": "cha"},
    "fixer": {"primary": "cha"}, "broker": {"primary": "cha"}, "informant": {"primary": "wis"},
    "patron": {"primary": "cha"}, "noble": {"primary": "cha"}, "merchant": {"primary": "cha"},
    "trader": {"primary": "cha"}, "peddler": {"primary": "cha"}, "stallholder": {"primary": "cha"},
    "shopkeeper": {"primary": "cha"}, "barkeep": {"primary": "cha"}, "innkeeper": {"primary": "cha"},
    "cutthroat": {"preset": "ranged", "primary": "dex"}, "saboteur": {"preset": "ranged", "primary": "dex"},
    "leader": {"primary": "cha"}, "representative": {"primary": "cha"},
}
_COMMONER_PRIMARY = "str"


def _armour_for(kind: str, level: int) -> tuple[str, str]:
    ladder = ARMOUR_LADDER[kind]
    got = ladder[0]
    for row in ladder:
        if level >= row[0]:
            got = row
    return got[1], got[2]


def _class_choices(cls: str, skills: list[str], weapon: str) -> dict:
    if cls == "commoner":
        return {"weapon proficiency": {"option": "class option",
                                       "picks": [{"pick": weapon, "level": 1}]}}
    if cls == "expert":
        from rules.tables import SKILLS

        pool = list(dict.fromkeys(skills + ["perception", "sense motive", "diplomacy",
                                            "profession", "craft", "appraise", "bluff",
                                            "knowledge (local)", "linguistics", "heal",
                                            "climb", "swim"]))
        picks = [s for s in pool if s in SKILLS][:10]
        return {"class skills": {"option": "class option",
                                 "picks": [{"pick": s.replace(" ", "-").replace("(", "")
                                            .replace(")", ""), "level": 1} for s in picks]}}
    return {}


def build_for(role, level: int) -> dict:
    rid, arch_id, _levels, skills, weapon, biomes, line = role
    arch = ARCHETYPES[arch_id]
    cls = arch["class"]
    armour, shield = _armour_for(arch["armour"], level)
    if weapon in ("longbow", "light-crossbow") or arch_id == "adept":
        shield = "none"
    over = OVERRIDES.get(rid, {})
    preset = over.get("preset", arch["preset"])
    primary = over.get("primary") or (_COMMONER_PRIMARY if cls == "commoner" else
                                      {"melee": "str", "ranged": "dex", "divine": "wis",
                                       "skill": "int"}[preset])
    doc = {
        "id": f"{rid}-level-{level}", "name": rid.replace("-", " "),
        "race": "human", "class": cls, "level": level,
        "abilities": {"preset": preset}, "racial_choices": [primary],
        "increases": [primary] * (level // 4),
        "skills": [], "feats": [], "class_choices": _class_choices(cls, skills, weapon),
        "weapons": [weapon], "equipped": weapon, "armour": armour, "shield": shield,
        "biomes": biomes, "role": rid.replace("-", " "), "description": line,
    }
    # Skill selections as the rules allow them (`npc_builds.skill_selections`), in the
    # role's order.
    doc["skills"] = skills[:npc_builds.skill_selections(doc)]
    # Feats greedily, each checked on the sheet as it stands.
    owed = npc_builds.feats_owed(doc)
    taken: list[str] = []
    # Longest key first: "$skill" replaced before "$skill2" wrote "Skill Focus (Stealth2)".
    fill = {"$skill2": (skills[1] if len(skills) > 1 else skills[0]).title(),
            "$skill": skills[0].title(), "$weapon": weapon.replace("-", " ")}
    for raw in arch["feats"]:
        if len(taken) >= owed:
            break
        name = raw
        for k, v in fill.items():
            name = name.replace(k, v)
        if name in taken:
            continue
        feat, _ = feats.resolve(name)
        if feat is None:
            continue
        try:
            actor = npc_builds.actor(dict(doc, feats=taken + [name] + _pad(owed - len(taken) - 1)))
        except ValueError:
            continue
        if feats.meets(actor, feat).get("ok"):
            taken.append(name)
    doc["feats"] = taken
    return doc


def _pad(n: int) -> list[str]:
    """Placeholders while a feat is tried, so the count check does not refuse the trial:
    the 'Run' feat has no prerequisite and is never the one being judged."""
    return ["Run"] * max(0, n)


def main() -> None:
    builds, refused = [], []
    for role in ROLES:
        for level in role[2]:
            doc = build_for(role, level)
            problems = npc_builds.check(doc)
            if problems:
                refused.append((doc["id"], problems))
                continue
            builds.append(doc)
    if refused:
        for rid, why in refused:
            print("REFUSED", rid, why)
        raise SystemExit(f"{len(refused)} builds refused; nothing written")
    out = ROOT / "content" / "npc-builds"
    out.mkdir(parents=True, exist_ok=True)
    (out / "people.json").write_text(json.dumps(
        {"source": npc_builds.SOURCE,
         "note": "Generated by tools/build_npc_roster.py; every number derived by rules/npc_builds.py.",
         "builds": builds}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(builds)} builds for {len(ROLES)} roles")


if __name__ == "__main__":
    main()
