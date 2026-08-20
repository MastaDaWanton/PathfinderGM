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
FEATS: dict[str, dict] = {
    "weapon finesse": {"name": "Weapon Finesse", "finesse": True},
    "stealthy": {"name": "Stealthy", "skills": {"stealth": 2, "escape artist": 2}},
    "alertness": {"name": "Alertness", "skills": {"perception": 2, "sense motive": 2}},
    "acrobatic": {"name": "Acrobatic", "skills": {"acrobatics": 2, "fly": 2}},
    "deceitful": {"name": "Deceitful", "skills": {"bluff": 2, "disguise": 2}},
    "persuasive": {"name": "Persuasive", "skills": {"diplomacy": 2, "intimidate": 2}},
    "improved initiative": {"name": "Improved Initiative", "initiative": 4},
    "lightning reflexes": {"name": "Lightning Reflexes", "saves": {"ref": 2}},
    "iron will": {"name": "Iron Will", "saves": {"will": 2}},
    "great fortitude": {"name": "Great Fortitude", "saves": {"fort": 2}},
    "toughness": {"name": "Toughness", "hp_bonus": True},
    "dodge": {"name": "Dodge", "ac": 1, "ac_type": "dodge"},
    "point-blank shot": {"name": "Point-Blank Shot", "ranged_near": {"attack": 1, "damage": 1}},
    # Weapon Focus is per-weapon: sheets write it as "weapon focus (rapier)".
    "weapon focus": {"name": "Weapon Focus", "weapon_attack": 1},
    "weapon specialization": {"name": "Weapon Specialization", "weapon_damage": 2},
    # Power Attack is a choice made per attack, not a passive bonus, so the numbers are
    # computed in sheet.power_attack_terms() rather than sitting in this table.
    "power attack": {"name": "Power Attack", "power_attack": True,
                     "requires": {"bab": 1, "str": 13}},
}

# Feats written with a parenthesised target, e.g. "weapon focus (rapier)".
FEAT_TARGET_RE = r"^(?P<feat>[^(]+?)\s*\((?P<target>[^)]+)\)$"


def power_attack_terms(bab: int, two_handed: bool) -> tuple[int, int]:
    """PF1e Power Attack: -1 attack for +2 damage, both scaling every 4 points of BAB,
    and half again as much damage in two hands.

    Returns (attack_penalty, damage_bonus), attack_penalty negative.
    """
    steps = 1 + max(0, bab) // 4
    damage = steps * 2
    if two_handed:
        damage = (steps * 3)
    return -steps, damage

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
        "lose_dex_to_ac": True, "ac": -2, "can_act": False,
        "note": "cannot act, loses Dex to AC, -2 AC",
    },
    "unconscious": {
        "name": "Unconscious",
        "lose_dex_to_ac": True, "can_act": False, "helpless": True,
        "note": "helpless and unaware",
    },
    "dead": {"name": "Dead", "can_act": False, "note": "dead"},
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
}

# Using a weapon you are not proficient with.
NON_PROFICIENT_PENALTY = -4

ARMOUR: dict[str, dict] = {
    "none": {"name": "no armour", "ac": 0, "max_dex": 99, "acp": 0},
    "padded": {"name": "padded armour", "ac": 1, "max_dex": 8, "acp": 0},
    "leather": {"name": "leather armour", "ac": 2, "max_dex": 6, "acp": 0},
    "studded leather": {"name": "studded leather", "ac": 3, "max_dex": 5, "acp": -1},
    "chain shirt": {"name": "chain shirt", "ac": 4, "max_dex": 4, "acp": -2},
    "breastplate": {"name": "breastplate", "ac": 6, "max_dex": 3, "acp": -4},
    "chainmail": {"name": "chainmail", "ac": 6, "max_dex": 2, "acp": -5},
    "full plate": {"name": "full plate", "ac": 9, "max_dex": 1, "acp": -6},
}

SHIELDS: dict[str, dict] = {
    "none": {"name": "no shield", "ac": 0, "acp": 0},
    "buckler": {"name": "buckler", "ac": 1, "acp": -1},
    "light shield": {"name": "light shield", "ac": 1, "acp": -1},
    "heavy shield": {"name": "heavy shield", "ac": 2, "acp": -2},
}

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
