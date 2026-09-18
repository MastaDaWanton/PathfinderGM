"""Pathfinder 1e reference tables.

Open Game Content under the OGL 1.0a. See `OGL-NOTICE.md` at the repo root for what is
covered and what still has to be done before a build ships — the verbatim licence is not
in the repo yet, and it has to be, because the licence must travel with the content.

These are the small structural tables (progressions, skill/ability mapping, condition
effects), not the bulk content; monsters, spells and items come from an SRD import later,
and that import brings its own attribution obligations with it.
"""
from __future__ import annotations

# --- Abilities ------------------------------------------------------------------

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")

ABILITY_NAMES = {
    "str": "Str", "dex": "Dex", "con": "Con",
    "int": "Int", "wis": "Wis", "cha": "Cha",
}

# The short forms above are what the sheet's ability grid wants. Prose wants the word:
# "2 Con damage" reads as a spreadsheet, and the GM narrates from these strings.
ABILITY_FULL = {
    "str": "Strength", "dex": "Dexterity", "con": "Constitution",
    "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma",
}


def ability_modifier(score: int) -> int:
    """PF1e: (score - 10) // 2, floored toward negative infinity.

    Python's // already floors, so a score of 7 gives -2 and not -1. Written out because
    the C-style truncating version of this is a classic silent off-by-one on low scores.
    """
    return (score - 10) // 2


# --- Save and BAB progressions ---------------------------------------------------

def bab_for(progression: str, level: int) -> int:
    if progression == "full":
        return level
    if progression == "three_quarter":
        return level * 3 // 4
    if progression == "half":
        return level // 2
    raise ValueError(f"unknown BAB progression {progression!r}")


def save_for(good: bool, level: int) -> int:
    """Good: 2 + level/2. Poor: level/3."""
    return 2 + level // 2 if good else level // 3


def iterative_attacks(bab: int) -> list[int]:
    """Attack bonuses for a full attack: BAB, BAB-5, BAB-10, BAB-15."""
    out = [bab]
    nxt = bab - 5
    while nxt >= 1 and len(out) < 4:
        out.append(nxt)
        nxt -= 5
    return out


# --- Classes ---------------------------------------------------------------------

CLASSES = {
    "rogue": {
        "name": "Rogue",
        "hit_die": 8,
        "bab": "three_quarter",
        "good_saves": ("ref",),
        "skill_ranks": 8,
        "starting_wealth": "4d6 x 10 gp",
        "proficiencies": ("simple", "rapier", "sap", "shortbow", "shortsword"),
        "class_skills": (
            "acrobatics", "appraise", "bluff", "climb", "craft", "diplomacy",
            "disable device", "disguise", "escape artist", "intimidate",
            "knowledge (dungeoneering)", "knowledge (local)", "linguistics",
            "perception", "perform", "profession", "sense motive", "sleight of hand",
            "stealth", "swim", "use magic device",
        ),
    },
    "fighter": {
        "name": "Fighter",
        "hit_die": 10,
        "bab": "full",
        "good_saves": ("fort",),
        "skill_ranks": 2,
        "starting_wealth": "5d6 x 10 gp",
        "proficiencies": ("simple", "martial"),
        "class_skills": (
            "climb", "craft", "handle animal", "intimidate",
            "knowledge (dungeoneering)", "knowledge (engineering)", "profession",
            "ride", "survival", "swim",
        ),
    },
    "wizard": {
        "name": "Wizard",
        "hit_die": 6,
        "bab": "half",
        "good_saves": ("will",),
        "skill_ranks": 2,
        "starting_wealth": "3d6 x 10 gp",
        "proficiencies": ("club", "dagger", "light crossbow", "quarterstaff"),
        "class_skills": (
            "appraise", "craft", "fly", "knowledge (arcana)", "knowledge (dungeoneering)",
            "knowledge (engineering)", "knowledge (geography)", "knowledge (history)",
            "knowledge (local)", "knowledge (nature)", "knowledge (nobility)",
            "knowledge (planes)", "knowledge (religion)", "linguistics", "profession",
            "spellcraft",
        ),
    },
    "cleric": {
        "name": "Cleric",
        "hit_die": 8,
        "bab": "three_quarter",
        "good_saves": ("fort", "will"),
        "skill_ranks": 2,
        "starting_wealth": "4d6 x 10 gp",
        "proficiencies": ("simple",),
        "class_skills": (
            "appraise", "craft", "diplomacy", "heal", "knowledge (arcana)",
            "knowledge (history)", "knowledge (nobility)", "knowledge (planes)",
            "knowledge (religion)", "linguistics", "profession", "sense motive",
            "spellcraft",
        ),
    },
}

# --- Skills ----------------------------------------------------------------------

# skill -> (key ability, trained only, armour check penalty applies)
SKILLS: dict[str, tuple[str, bool, bool]] = {
    "acrobatics": ("dex", False, True),
    "appraise": ("int", False, False),
    "bluff": ("cha", False, False),
    "climb": ("str", False, True),
    "craft": ("int", False, False),
    "diplomacy": ("cha", False, False),
    "disable device": ("dex", True, True),
    "disguise": ("cha", False, False),
    "escape artist": ("dex", False, True),
    "fly": ("dex", False, True),
    "handle animal": ("cha", True, False),
    "heal": ("wis", False, False),
    "intimidate": ("cha", False, False),
    "linguistics": ("int", True, False),
    "perception": ("wis", False, False),
    "perform": ("cha", False, False),
    "profession": ("wis", True, False),
    "ride": ("dex", False, True),
    "sense motive": ("wis", False, False),
    "sleight of hand": ("dex", True, True),
    "spellcraft": ("int", True, False),
    "stealth": ("dex", False, True),
    "survival": ("wis", False, False),
    "swim": ("str", False, True),
    "use magic device": ("cha", True, False),
}

for _k in ("arcana", "dungeoneering", "engineering", "geography", "history", "local",
           "nature", "nobility", "planes", "religion"):
    SKILLS[f"knowledge ({_k})"] = ("int", True, False)

SAVES = {"fort": "Fortitude", "ref": "Reflex", "will": "Will"}
SAVE_ABILITY = {"fort": "con", "ref": "dex", "will": "wis"}

# --- Feats with a mechanical effect ----------------------------------------------

# Only feats the engine actually applies. A feat on the sheet that is not here is carried
# as flavour and contributes nothing — better than silently pretending it worked.
# Feats written with a parenthesised target, e.g. "weapon focus (rapier)".
FEAT_TARGET_RE = r"^(?P<feat>[^(]+?)\s*\((?P<target>[^)]+)\)$"


# --- Conditions ------------------------------------------------------------------

# Each entry lists the penalties the engine applies automatically. Durations live on the
# combatant, not here.
CONDITIONS: dict[str, dict] = {
    "shaken": {
        "name": "Shaken",
        "attack": -2, "saves": -2, "skills": -2, "ability_checks": -2,
        "note": "-2 on attack rolls, saves, skill and ability checks",
    },
    "frightened": {
        "name": "Frightened",
        "attack": -2, "saves": -2, "skills": -2, "ability_checks": -2,
        "note": "as shaken, and must flee",
    },
    "sickened": {
        "name": "Sickened",
        "attack": -2, "saves": -2, "skills": -2, "ability_checks": -2, "damage": -2,
        "note": "-2 on attack, damage, saves, skill and ability checks",
    },
    "prone": {
        "name": "Prone",
        "melee_attack": -4, "ac_melee": -4, "ac_ranged": 4,
        "note": "-4 melee attack, -4 AC vs melee, +4 AC vs ranged",
    },
    "flat-footed": {
        "name": "Flat-footed",
        "lose_dex_to_ac": True,
        "note": "loses Dex bonus to AC",
    },
    "fatigued": {
        "name": "Fatigued",
        "ability_penalty": {"str": -2, "dex": -2},
        "note": "-2 Str and Dex; cannot run or charge",
    },
    "exhausted": {
        "name": "Exhausted",
        "ability_penalty": {"str": -6, "dex": -6},
        "note": "-6 Str and Dex; moves at half speed",
    },
    "entangled": {
        "name": "Entangled",
        "attack": -2, "ability_penalty": {"dex": -4},
        "note": "-2 attack, -4 Dex, cannot move at full speed",
    },
    "staggered": {"name": "Staggered", "note": "one action per round"},
    "stunned": {
        "name": "Stunned",
        "lose_dex_to_ac": True, "ac": -2, "note": "cannot act, loses Dex to AC, -2 AC",
    },
    "unconscious": {
        "name": "Unconscious",
        "lose_dex_to_ac": True, "helpless": True,
        "note": "helpless and unaware",
    },
    "dead": {"name": "Dead", "note": "dead"},
    "dazzled": {"name": "Dazzled", "attack": -1, "note": "-1 on attack rolls"},
    "blinded": {
        "name": "Blinded",
        "lose_dex_to_ac": True, "ac": -2, "skills": -4,
        "note": "-2 AC, loses Dex to AC, -4 on most Dex- and Str-based skills",
    },
    "grappled": {
        "name": "Grappled",
        "attack": -2, "ability_penalty": {"dex": -4},
        "note": "-2 attack, -4 Dex, cannot move",
    },
    # Added from Appendix 2 once the books were machine-readable. Before that the table
    # was written from memory and covered barely half the conditions in the game; a
    # condition the engine does not know is one it silently ignores when a GM applies it.
    "dazed": {
        "name": "Dazed", "note": "can take no actions, but has no penalty to AC",
    },
    "deafened": {
        "name": "Deafened", "initiative": -4,
        "note": "-4 on initiative, and a 20% chance to miscast spells with verbal components",
    },
    "cowering": {
        "name": "Cowering", "ac": -2, "lose_dex_to_ac": True, "note": "-2 AC, loses Dex to AC, and takes no actions",
    },
    "helpless": {
        "name": "Helpless", "lose_dex_to_ac": True, "helpless": True,
        "note": "treated as Dex 0; melee attackers gain +4 to hit",
    },
    "pinned": {
        "name": "Pinned", "ac": -4, "lose_dex_to_ac": True, "attack": -4,
        "note": "-4 AC, loses Dex to AC, tightly bound and barely able to act",
    },
    "paralyzed": {
        "name": "Paralyzed", "lose_dex_to_ac": True, "helpless": True,
        "note": "Str and Dex reduced to 0, helpless, cannot move or act",
    },
    "nauseated": {
        "name": "Nauseated", "note": "can take only a single move action; cannot attack or cast",
    },
    "panicked": {
        "name": "Panicked",
        "attack": -2, "saves": -2, "skills": -2, "ability_checks": -2,
        "note": "-2 as shaken, drops what it holds, and must flee",
    },
    "fascinated": {
        "name": "Fascinated", "skills": -4,
        "note": "-4 on skill checks made as reactions; takes no other actions",
    },
    "disabled": {
        "name": "Disabled",
        "note": "at 0 hp; a standard action costs 1 hp and may start it dying",
    },
    "dying": {
        "name": "Dying", "lose_dex_to_ac": True, "helpless": True,
        "note": "unconscious and losing 1 hp a round until stabilised or dead",
    },
    "stable": {
        "name": "Stable", "note": "below 0 hp but no longer losing hit points",
    },
    "petrified": {
        "name": "Petrified", "helpless": True,
        "note": "turned to stone: unconscious and unaware",
    },
    "confused": {
        "name": "Confused",
        "note": "acts randomly each round; roll on the confusion table",
    },
    # Two that were on the unimplemented ledger in tests/test_reference.py until the
    # machinery each of them was waiting for arrived. Both are Appendix 2 conditions; the
    # four the spell readers also asked for — slowed, cursed, diseased, poisoned — are
    # not, and are refused rather than invented. `slow` is a spell whose effect is a
    # bundle of modifiers, and a curse, a disease and a poison are afflictions with their
    # own rules, not entries on this table.
    "bleed": {
        "name": "Bleed",
        "note": "takes the stated damage at the start of its turn until it is stopped, "
                "by a DC 15 Heal check or any cure spell",
    },
    # +2 to hit, and — the half that could not be said before — total concealment. The
    # `concealment` key is read by `Actor.concealment`, not by `_condition_mods`, which
    # only picks up integers it is asked for by name; the miss chance is not a modifier
    # to anything, it is a percentile rolled before damage.
    "invisible": {
        "name": "Invisible",
        "attack": 2, "concealment": 50,
        "note": "+2 on attack rolls, ignores the opponent's Dex bonus to AC, and 50% "
                "total concealment",
    },
}

# --- Difficulty bands ------------------------------------------------------------

# The PF1e difficulty table's own vocabulary. The GM agent picks one of these words; code
# turns the word into the number. See docs/intent-protocol.md §1 for why the model is not
# asked for the integer.
DC_BANDS: dict[str, int] = {
    "very_easy": 0,
    "easy": 5,
    "average": 10,
    "tough": 15,
    "challenging": 20,
    "formidable": 25,
    "heroic": 30,
    "nearly_impossible": 40,
}

CIRCUMSTANCE = {"favorable": 2, "unfavorable": -2}

# --- Weapons and armour (the slice's subset) --------------------------------------

# `prof` is the proficiency group a character must have to use the weapon without the
# -4 non-proficiency penalty; `hands` matters for Power Attack's larger damage bonus.
WEAPONS: dict[str, dict] = {
    "rapier": {"name": "rapier", "damage": "1d6", "crit_range": 18, "crit_mult": 2,
               "type": "piercing", "category": "melee", "finessable": True,
               "prof": "martial", "hands": 1},
    "dagger": {"name": "dagger", "damage": "1d4", "crit_range": 19, "crit_mult": 2,
               "type": "piercing", "category": "melee", "finessable": True,
               "prof": "simple", "hands": 1},
    "shortsword": {"name": "short sword", "damage": "1d6", "crit_range": 19, "crit_mult": 2,
                   "type": "piercing", "category": "melee", "finessable": True,
                   "prof": "martial", "hands": 1},
    "sap": {"name": "sap", "damage": "1d6", "crit_range": 20, "crit_mult": 2,
            "type": "bludgeoning", "category": "melee", "finessable": True,
            "nonlethal": True, "prof": "martial", "hands": 1},
    "longsword": {"name": "longsword", "damage": "1d8", "crit_range": 19, "crit_mult": 2,
                  "type": "slashing", "category": "melee", "finessable": False,
                  "prof": "martial", "hands": 1},
    "club": {"name": "club", "damage": "1d6", "crit_range": 20, "crit_mult": 2,
             "type": "bludgeoning", "category": "melee", "finessable": False,
             "prof": "simple", "hands": 1},
    "quarterstaff": {"name": "quarterstaff", "damage": "1d6", "crit_range": 20,
                     "crit_mult": 2, "type": "bludgeoning", "category": "melee",
                     "finessable": False, "prof": "simple", "hands": 2},
    "greatsword": {"name": "greatsword", "damage": "2d6", "crit_range": 19, "crit_mult": 2,
                   "type": "slashing", "category": "melee", "finessable": False,
                   "prof": "martial", "hands": 2},
    "shortbow": {"name": "shortbow", "damage": "1d6", "crit_range": 20, "crit_mult": 3,
                 "type": "piercing", "category": "ranged", "finessable": False,
                 "prof": "martial", "hands": 2},
    "light crossbow": {"name": "light crossbow", "damage": "1d8", "crit_range": 19,
                       "crit_mult": 2, "type": "piercing", "category": "ranged",
                       "finessable": False, "prof": "simple", "hands": 2},
    "unarmed": {"name": "unarmed strike", "damage": "1d3", "crit_range": 20, "crit_mult": 2,
                "type": "bludgeoning", "category": "melee", "finessable": False,
                "nonlethal": True, "prof": "simple", "hands": 1},
    # A chunk of wood, a pebble, a chair leg. Core Rulebook, Improvised Weapons: "any
    # creature that uses an improvised weapon in combat is considered to be
    # nonproficient with it and takes a –4 penalty on attack rolls made with that
    # object. To determine the size category and appropriate damage … compare its
    # relative size and damage potential to the weapon list to find a reasonable
    # match. An improvised weapon scores a threat on a natural roll of 20 and deals
    # double damage on a critical hit. An improvised thrown weapon has a range
    # increment of 10 feet." The `prof` is one nobody holds, which is how the -4
    # arrives through the ordinary proficiency check. 1d4 is the club's light cousin;
    # the object's own name rides on the attack as `params.item`.
    "improvised": {"name": "improvised weapon", "damage": "1d4", "crit_range": 20,
                   "crit_mult": 2, "type": "bludgeoning", "category": "melee",
                   "finessable": False, "prof": "improvised", "hands": 1, "light": True,
                   "range_ft": 10.0, "traits": ["improvised"]},
}

# Using a weapon you are not proficient with.
NON_PROFICIENT_PENALTY = -4

# --- damage types -----------------------------------------------------------------------
#
# The distinction earns its keep in exactly one place, and it is not cosmetic: **damage
# reduction applies to physical damage and not to energy.** A creature with DR 10/— still
# takes a fireball in full. Without a vocabulary here, DR would silently soak acid and
# fire, and nothing in the numbers on screen would reveal it.

# --- objects ------------------------------------------------------------------------------
#
# Core Rulebook, "Smashing an Object" (p.173-175). Hardness subtracts from every hit
# before the object's own hit points are touched — the same shape as damage reduction,
# and for the same reason: an object with hardness 10 is not scratched by a knife.

MATERIALS: dict[str, dict] = {
    "paper":      {"hardness": 0,  "hp_per_inch": 2},
    "cloth":      {"hardness": 0,  "hp_per_inch": 2},
    "rope":       {"hardness": 0,  "hp_per_inch": 2},
    "ice":        {"hardness": 0,  "hp_per_inch": 3},
    "glass":      {"hardness": 1,  "hp_per_inch": 1},
    "leather":    {"hardness": 2,  "hp_per_inch": 5},
    "hide":       {"hardness": 2,  "hp_per_inch": 5},
    "wood":       {"hardness": 5,  "hp_per_inch": 10},
    "bone":       {"hardness": 6,  "hp_per_inch": 10},
    "stone":      {"hardness": 8,  "hp_per_inch": 15},
    "iron":       {"hardness": 10, "hp_per_inch": 30},
    "steel":      {"hardness": 10, "hp_per_inch": 30},
    "mithral":    {"hardness": 15, "hp_per_inch": 30},
    "adamantine": {"hardness": 20, "hp_per_inch": 40},
}

# What a thing is made of, when nobody said. Guessed from the name because the alternative
# is asking the GM, and a GM asked for a material will invent one.
MATERIAL_HINTS = (
    ("adamantine", "adamantine"), ("mithral", "mithral"), ("mithril", "mithral"),
    ("silk", "cloth"), ("cloak", "cloth"), ("robe", "cloth"), ("tunic", "cloth"),
    ("boots", "leather"), ("gloves", "leather"), ("belt", "leather"),
    ("scabbard", "leather"), ("pouch", "leather"), ("hide", "hide"),
    ("bow", "wood"), ("staff", "wood"), ("club", "wood"), ("haft", "wood"),
    ("shield", "wood"), ("scroll", "paper"), ("book", "paper"),
    ("vial", "glass"), ("bottle", "glass"), ("flask", "glass"), ("potion", "glass"),
    ("rope", "rope"), ("amulet", "stone"), ("ring", "iron"),
    # The armour table's own names, which mostly say what they are but not always.
    ("padded", "cloth"), ("quilted", "cloth"), ("chain", "steel"), ("scale", "steel"),
    ("plate", "steel"), ("banded", "steel"), ("splint", "steel"), ("buckler", "steel"),
)

# Energy attacks deal half damage to objects (CRB p.174). Acid is the exception this app
# needs first: Blood Bending's Caustic Blood eats equipment, and halving it would make a
# defining ability read as a rounding error.
ENERGY_VS_OBJECTS_HALVED = ("cold", "electricity", "fire", "sonic")

PHYSICAL_DAMAGE = ("bludgeoning", "piercing", "slashing")
ENERGY_DAMAGE = ("acid", "cold", "electricity", "fire", "sonic")

# The words a narrator reaches for instead of the book's. Left alone, "lightning" reads as
# an unknown type, and an unknown type is treated as physical — which would hand DR a
# reduction it should never get.
DAMAGE_TYPE_ALIASES = {
    "b": "bludgeoning", "blunt": "bludgeoning", "bludgeon": "bludgeoning",
    "crushing": "bludgeoning", "impact": "bludgeoning",
    "p": "piercing", "pierce": "piercing", "stabbing": "piercing",
    "s": "slashing", "slash": "slashing", "cutting": "slashing",
    "lightning": "electricity", "shock": "electricity", "electric": "electricity",
    "flame": "fire", "burning": "fire", "heat": "fire",
    "frost": "cold", "ice": "cold", "freezing": "cold",
    "thunder": "sonic", "force": "untyped", "untyped": "untyped",
}


def material_for(name: str) -> str:
    """Guess what an item is made of from its name. Steel when nothing suggests otherwise
    — most adventuring gear is, and it is the middle of the range rather than the
    forgiving end.

    Materials are checked before hints because half of them are also ordinary words for
    the things made from them. Found in the app: `leather` armour came back *steel,
    hardness 10*, since the hints knew about leather boots and leather belts and nothing
    knew that "leather" is itself leather. Acid would have run off a jerkin like a
    breastplate.
    """
    low = (name or "").lower()
    for material in MATERIALS:
        if material in low:
            return material
    for hint, material in MATERIAL_HINTS:
        if hint in low:
            return material
    return "steel"


def normalise_damage_type(dtype: str | None) -> str:
    d = (dtype or "untyped").strip().lower()
    return DAMAGE_TYPE_ALIASES.get(d, d)


def is_physical(dtype: str | None) -> bool:
    """Unknown types count as physical.

    Deliberately the cautious direction: an unrecognised type that DR ignores is a
    creature taking damage it should have shrugged off, which a player can see and query.
    An unrecognised type that DR *soaks* is damage silently vanishing, which nobody
    catches.
    """
    d = normalise_damage_type(dtype)
    return d not in ENERGY_DAMAGE

# `weight` is the armour category, which is what decides the speed penalty: medium and
# heavy armour drop a 30-foot speed to 20 and a 20-foot speed to 15. Absent until the grid
# arrived, because nothing measured movement in feet before there were squares to cross.
ARMOUR: dict[str, dict] = {
    "none": {"name": "no armour", "ac": 0, "max_dex": 99, "acp": 0, "weight": "light"},
    "padded": {"name": "padded armour", "cost_gp": 5, "ac": 1, "max_dex": 8, "acp": 0, "weight": "light"},
    "leather": {"name": "leather armour", "cost_gp": 10, "ac": 2, "max_dex": 6, "acp": 0, "weight": "light"},
    "studded leather": {"name": "studded leather", "cost_gp": 25, "ac": 3, "max_dex": 5, "acp": -1,
                        "weight": "light"},
    "chain shirt": {"name": "chain shirt", "cost_gp": 100, "ac": 4, "max_dex": 4, "acp": -2,
                    "weight": "light"},
    "breastplate": {"name": "breastplate", "cost_gp": 200, "ac": 6, "max_dex": 3, "acp": -4,
                    "weight": "medium"},
    "chainmail": {"name": "chainmail", "cost_gp": 150, "ac": 6, "max_dex": 2, "acp": -5, "weight": "medium"},
    "full plate": {"name": "full plate", "cost_gp": 1500, "ac": 9, "max_dex": 1, "acp": -6, "weight": "heavy"},
}

# Core Rulebook table 7-6. A creature slowed by armour keeps the reduced speed until it
# takes the armour off, which is why this is a lookup rather than a fraction: 30 goes to
# 20 and 20 goes to 15, and neither is two thirds of the other.
ARMOUR_SPEED = {30: 20, 20: 15}

# --- Magic item body slots ---------------------------------------------------------

# Ultimate Equipment p.206: "There are 15 categories of slotted wondrous items. Armor,
# rings, and shields are described in other sections of this book, while the 11 other
# body slots are detailed below."
#
# `count` is how many of that slot a character has by default and `max` is how many the
# sheet will let you add. The rules give everyone two ring slots and one neck slot, and
# a creature only benefits from one item per slot — but sheets need to *record* what is
# owned and worn beyond that, so the maxima here are deliberately generous. Extra slots
# past the rules default are marked `beyond_rules` in the sheet so the display can say
# so rather than implying they all work.
SLOTS: dict[str, dict] = {
    "head":      {"label": "Head", "count": 1, "max": 1, "side": "left",
                  "holds": "circlets, crowns, hats, helms, masks"},
    "headband":  {"label": "Headband", "count": 1, "max": 1, "side": "right",
                  "holds": "headbands, phylacteries"},
    "eyes":      {"label": "Eyes", "count": 1, "max": 1, "side": "left",
                  "holds": "goggles, lenses, spectacles"},
    "neck":      {"label": "Neck", "count": 1, "max": 5, "side": "right",
                  "holds": "amulets, brooches, necklaces, periapts, scarabs"},
    "shoulders": {"label": "Shoulders", "count": 1, "max": 1, "side": "left",
                  "holds": "capes, cloaks, mantles"},
    "chest":     {"label": "Chest", "count": 1, "max": 1, "side": "right",
                  "holds": "jackets, shirts, vests"},
    "body":      {"label": "Body", "count": 1, "max": 1, "side": "left",
                  "holds": "robes, vestments, body wraps"},
    "armor":     {"label": "Armour", "count": 1, "max": 1, "side": "left",
                  "holds": "worn armour"},
    "belt":      {"label": "Belt", "count": 1, "max": 1, "side": "right",
                  "holds": "belts, girdles, sashes"},
    "wrists":    {"label": "Wrists", "count": 1, "max": 1, "side": "left",
                  "holds": "bracers, bracelets"},
    "hands":     {"label": "Hands", "count": 1, "max": 1, "side": "right",
                  "holds": "gauntlets, gloves"},
    "ring":      {"label": "Rings", "count": 2, "max": 10, "side": "right",
                  "holds": "rings"},
    "feet":      {"label": "Feet", "count": 1, "max": 1, "side": "left",
                  "holds": "boots, sandals, shoes, slippers"},
    "shield":    {"label": "Shield", "count": 1, "max": 1, "side": "right",
                  "holds": "carried shields"},
}

# How many of a slot the *rules* let you benefit from at once, where that differs from
# the sheet's maximum. Everything else is one.
SLOT_RULES_LIMIT = {"ring": 2}

# Top-to-bottom order down each side of the figure, so the boxes sit roughly where the
# thing is worn.
SLOT_ORDER_LEFT = ("head", "eyes", "shoulders", "body", "armor", "wrists", "feet")
SLOT_ORDER_RIGHT = ("headband", "neck", "chest", "hands", "ring", "belt", "shield")

SHIELDS: dict[str, dict] = {
    "none": {"name": "no shield", "ac": 0, "acp": 0},
    "buckler": {"name": "buckler", "cost_gp": 5, "ac": 1, "acp": -1},
    "light shield": {"name": "light shield", "cost_gp": 9, "ac": 1, "acp": -1},
    "heavy shield": {"name": "heavy shield", "cost_gp": 20, "ac": 2, "acp": -2},
}

# --- Combat manoeuvres ------------------------------------------------------------

# All resolved identically: an attack roll with CMB in place of the attack bonus,
# against the target's CMD. Only the consequences differ.
#
# `size_limit` — the manoeuvre only works on a target at most one size category larger.
# `degrees`    — extra effects keyed on how far the roll exceeded CMD.
# `backfire`   — what happens to the attacker on failing by 10 or more.
MANEUVERS: dict[str, dict] = {
    "bull rush": {
        "name": "bull rush",
        "size_limit": 1,
        "provokes": True,
        "effect": "pushes the target back 5 feet",
        "per_5_over": "another 5 feet",
    },
    "disarm": {
        "name": "disarm",
        "provokes": True,
        "effect": "the target drops one carried item",
        "degrees": {10: "the target drops what it holds in both hands"},
        "backfire": "you drop the weapon you were using",
        "unarmed_penalty": -4,
    },
    "grapple": {
        "name": "grapple",
        "size_limit": None,
        "provokes": True,
        "effect": "both of you gain the grappled condition",
        "condition": "grappled",
        "also_grapples_attacker": True,
        "needs_two_hands": True,
    },
    "overrun": {
        "name": "overrun",
        "size_limit": 1,
        "provokes": True,
        "effect": "you move through the target's space",
        "degrees": {5: "and the target is knocked prone"},
        "degree_condition": {5: "prone"},
        "extra_legs_penalty": True,
    },
    "sunder": {
        "name": "sunder",
        "provokes": True,
        "effect": "you damage an item the target is holding or wearing",
        "damages_item": True,
    },
    "trip": {
        "name": "trip",
        "size_limit": 1,
        "provokes": True,
        "effect": "the target is knocked prone",
        "condition": "prone",
        "backfire": "you are knocked prone instead",
        "backfire_condition": "prone",
        "extra_legs_penalty": True,
    },
    "reposition": {
        "name": "reposition",
        "size_limit": 1,
        "provokes": True,
        "effect": "you move the target to another square within your reach",
    },
    "dirty trick": {
        "name": "dirty trick",
        "provokes": True,
        "effect": "the target is blinded, dazzled, deafened, entangled, shaken or sickened for 1 round",
        "condition": "dazzled",
    },
    "steal": {
        "name": "steal",
        "provokes": True,
        "effect": "you take an object the target is carrying",
    },
    "drag": {
        "name": "drag",
        "size_limit": 1,
        "provokes": True,
        "effect": "you drag the target 5 feet",
        "per_5_over": "another 5 feet",
    },
}

MANEUVER_ALIASES = {
    "bullrush": "bull rush", "bull-rush": "bull rush", "push": "bull rush",
    "shove": "bull rush", "knock down": "trip", "knockdown": "trip",
    "tackle": "grapple", "wrestle": "grapple", "grab": "grapple",
    "break weapon": "sunder", "smash": "sunder", "run through": "overrun",
    "run over": "overrun", "trip attack": "trip", "disarm attack": "disarm",
}

# Order of size categories, for the "no more than one size category larger" limit.
SIZE_ORDER = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge",
              "gargantuan", "colossal")

# Size modifiers: (AC and attack, CMB and CMD, Stealth)
SIZES: dict[str, dict] = {
    "fine": {"attack_ac": 8, "cmb_cmd": -8, "stealth": 16},
    "diminutive": {"attack_ac": 4, "cmb_cmd": -4, "stealth": 12},
    "tiny": {"attack_ac": 2, "cmb_cmd": -2, "stealth": 8},
    "small": {"attack_ac": 1, "cmb_cmd": -1, "stealth": 4},
    "medium": {"attack_ac": 0, "cmb_cmd": 0, "stealth": 0},
    "large": {"attack_ac": -1, "cmb_cmd": 1, "stealth": -4},
    "huge": {"attack_ac": -2, "cmb_cmd": 2, "stealth": -8},
    "gargantuan": {"attack_ac": -4, "cmb_cmd": 4, "stealth": -12},
    "colossal": {"attack_ac": -8, "cmb_cmd": 8, "stealth": -16},
}

# Space and natural reach, in feet. Core Rulebook table 8-4.
#
# `space` is how much of the map a creature stands on and `squares` is that in five-foot
# squares, which is not always `space / 5`: everything Tiny and below occupies less than a
# full square and shares one, and the app gives them a whole square rather than modelling
# four kobold-sized creatures crowding a single one. Where that matters — a swarm, a
# familiar in its owner's square — it is a rule the grid does not yet have rather than one
# it gets wrong quietly.
#
# Reach comes in two shapes, and the distinction is real: a Large *tall* creature (an ogre)
# threatens 10 feet, a Large *long* one (a horse) threatens 5. Getting this wrong changes
# who can be attacked without moving, which is most of what a grid is for.
# `tall_ft` is how far up a creature of this size reaches when it stands — the TOP of the
# Core Rulebook's "typical height/length" band, which is the number a ceiling has to clear.
# Medium is 4-8 ft, so a Medium creature is two squares of vertical: eight feet of person
# inside ten feet of space. That was the shape asked for on 2026-09-14, and it checks out.
#
# Sourced carefully, because the obvious place does not have it: **Table 8-4 carries no
# height column at all** — only Space and Natural Reach (verified against
# aonprd.com/Rules.aspx?ID=179). The bands come from the Creature Sizes table at
# d20pfsrd.com/gamemastering/combat/space-reach-threatened-area-templates/, which prints
# them beside the same space and reach values, and which says in its own words: "These
# values are TYPICAL for creatures of the indicated size. Some exceptions exist."
#
# So this column is a default, not a law, and `height_ft` takes an override for the
# creature that is an exception — a nine-foot-tall Medium giant-kin is legal in a way a
# Medium creature with a 10-ft space is not.
#
# `tall_ft` is the band top for a creature built upright; a LONG creature of the same size
# wears that band horizontally — Large (tall) and Large (long) are both "8 to 16 ft" in the
# source, and the difference is whether that dimension stands up. A horse is not sixteen
# feet tall, so `height_ft(size, "long")` answers with the creature's space instead: about
# as tall as it is wide, which is the only other dimension the rules give us.
SPACE_AND_REACH: dict[str, dict] = {
    "fine":       {"space": 0.5, "squares": 1, "reach_tall": 0,  "reach_long": 0,
                   "tall_ft": 0.5},
    "diminutive": {"space": 1,   "squares": 1, "reach_tall": 0,  "reach_long": 0,
                   "tall_ft": 1},
    "tiny":       {"space": 2.5, "squares": 1, "reach_tall": 0,  "reach_long": 0,
                   "tall_ft": 2},
    "small":      {"space": 5,   "squares": 1, "reach_tall": 5,  "reach_long": 5,
                   "tall_ft": 4},
    "medium":     {"space": 5,   "squares": 1, "reach_tall": 5,  "reach_long": 5,
                   "tall_ft": 8},
    "large":      {"space": 10,  "squares": 2, "reach_tall": 10, "reach_long": 5,
                   "tall_ft": 16},
    "huge":       {"space": 15,  "squares": 3, "reach_tall": 15, "reach_long": 10,
                   "tall_ft": 32},
    "gargantuan": {"space": 20,  "squares": 4, "reach_tall": 20, "reach_long": 15,
                   "tall_ft": 64},
    # "64 ft. or more" has no top. The band's own floor is the honest reading of a row
    # with no ceiling: a Colossal creature is at least this tall, and a document that
    # knows better says so with an override rather than this table guessing higher.
    "colossal":   {"space": 30,  "squares": 6, "reach_tall": 30, "reach_long": 20,
                   "tall_ft": 64},
}
