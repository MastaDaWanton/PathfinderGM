"""Armour and shields: the one name resolver, what putting one on costs, and what wearing
one does to a caster and to somebody never trained in it.

**One name.** `wear` took armour only by its exact table key. "leather armour", the
table's own display name, and "chain-shirt", the spelling the loot op wrote, were filed as
gear and could be neither seen as armour nor worn (measured 2026-09-30: every armour in the
table worn by its key, none by its name). `key_for` is the armour half of
`weapons.key_for`: key, display name, title case, hyphen or space, armor or armour, with
or without the word "armour" on the end.

**What it costs to change.** Core Rulebook Table 6-8, "Donning Armor" (owner's ruling E2,
2026-09-30): a suit takes minutes, so out of a fight the minutes pass through the one clock
(`Scene.advance`) and in a fight a suit cannot change at all; a shield is a move action
either way and may.

**What it does besides AC.** Owner's ruling E3: "Arcane Spell Failure" (CRB p.150-151) —
an arcane caster in armour or carrying a shield rolls the table's percentage on every
spell with a somatic component, and on a failure the spell and its slot are lost. And
"Armor Proficiency" (CRB p.152) — a wearer not proficient "takes the armor's (and/or
shield's) armor check penalty on attack rolls"; the two stack. Both read the class's own
proficiency tokens as tags (`proficient.armour.<weight>`, `proficient.shield`,
`proficient.shield.tower`), the way weapons already do.
"""
from __future__ import annotations

import re

from .tables import ARMOUR, DONNING, SHIELDS

# The words a person writes for a table key, beyond the key and the display name. Never a
# bare material or an everyday noun on its own — "chain", "plate", "hide" and "shield" are
# a goods line, a dish, a tanner's skin and a question, and each would have made something
# carried into a thing to wear.
_ALIASES = {
    "quilted armour": "padded", "studded": "studded leather",
    "chain mail": "chainmail", "chainshirt": "chain shirt",
    "plate armour": "full plate", "fullplate": "full plate", "plate mail": "full plate",
    "half plate": "half-plate", "halfplate": "half-plate",
    "banded": "banded mail", "splint": "splint mail", "scale": "scale mail",
    "breast plate": "breastplate",
    # The leatherworker's rows (tables.ARMOUR): the British spelling of the coat, and the
    # Archives' own "Lamellar (leather)" word order. "hide" is NOT here, although the
    # leatherworking contracts (§4.2) asked for it: a carried tanner's hide must never be a
    # suit (test_a_bare_material_word_is_not_armour), and every record's `base` is the table
    # key "hide armour", which needs no alias (tests/test_leather_items.py measures it).
    "armoured coat": "armored coat", "lamellar leather": "leather lamellar",
    "lamellar horn": "horn lamellar", "lamellar steel": "steel lamellar",
}
_SHIELD_ALIASES = {
    "steel shield": "heavy shield", "wooden shield": "heavy wooden shield",
    "light wooden": "light wooden shield", "heavy wooden": "heavy wooden shield",
    "light steel": "light shield", "heavy steel": "heavy shield", "tower": "tower shield",
}


def _norm(text: str) -> str:
    low = " ".join(re.sub(r"[-_]+", " ", str(text or "").lower()).split())
    low = re.sub(r"^(?:a|an|the|my|his|her|their|some|suit of|a suit of)\s+", "", low)
    low = re.sub(r"^suit of\s+", "", low)
    low = re.sub(r"\barmor\b", "armour", low)
    return low


def key_for(text: str) -> tuple[str, str]:
    """("armour" | "shield", the table key), or ("", "") for anything that is neither.

    Never a nearest guess: "a stern look" is ("", ""), and the caller files it as gear."""
    low = _norm(text)
    if not low or low in ("none", "no armour", "no shield"):
        return "", ""
    for table, kind, aliases in ((ARMOUR, "armour", _ALIASES),
                                 (SHIELDS, "shield", _SHIELD_ALIASES)):
        names = {_norm(v["name"]): k for k, v in table.items() if k != "none"}
        for cand in (low, re.sub(r"\s+armour$", "", low)):
            if cand in table and cand != "none":
                return kind, cand
            if cand in names:
                return kind, names[cand]
            if cand in aliases:
                return kind, aliases[cand]
    return "", ""


def row(kind: str, key: str) -> dict:
    table = ARMOUR if kind == "armour" else SHIELDS
    return table.get(key) or table["none"]


# --- the time it takes ---------------------------------------------------------------------

def change_cost(kind: str, key: str, off: bool) -> dict:
    """What putting on (or taking off) this costs, read off Table 6-8.

    {"action": "move"} for any shield; else {"minutes": n, "dice": "1d4+1" or "", "said":
    "1 minute", "hasty": bool}. Plate alone is the hasty time — the book's footnote: "The
    wearer must have help to don this armor. Without help, it can be donned only
    hastily" — and nobody helps yet, so it always is."""
    if kind == "shield":
        return {"action": "move", "minutes": 0, "dice": "", "said": "a move action",
                "hasty": False}
    group = DONNING[str(row("armour", key).get("don") or "light")]
    if off:
        dice = group["remove"]
        if "d" in dice:
            return {"minutes": 0, "dice": dice, "said": f"{dice} minutes", "hasty": False}
        n = int(dice)
        return {"minutes": n, "dice": "", "said": _minutes(n), "hasty": False}
    if group.get("alone") == "hasty":
        n = max(1, group["hasty_rounds"] // 10)
        return {"minutes": n, "dice": "", "said": _minutes(n), "hasty": True}
    n = int(group["don"])
    return {"minutes": n, "dice": "", "said": _minutes(n), "hasty": False}


def _minutes(n: int) -> str:
    return f"{n} minute{'s' if n != 1 else ''}"


# --- two hands and a shield -----------------------------------------------------------------

def needs_two_hands(weapon_key: str) -> bool:
    from . import weapons as weapons_mod

    if not weapon_key or not weapons_mod.has(weapon_key):
        return False
    return int(weapons_mod.get(weapon_key).get("hands") or 1) >= 2


def hands_clash(actor, weapon_key: str = "", shield_key: str = "") -> str:
    """Why this weapon and this shield cannot be in use together, or "" (owner's ruling
    E4, 2026-09-30). A two-handed weapon takes both hands, so a shield on the arm has to
    come off first — but a buckler straps to the forearm, and the CRB lets a bow or a
    crossbow be used "without penalty while carrying it". Either half may be the one
    being changed; the other is read off the actor."""
    from . import weapons as weapons_mod

    w = weapon_key or str(getattr(actor, "equipped", "") or "unarmed")
    s = shield_key or str(getattr(actor, "shield", "none") or "none")
    if s == "none" or not needs_two_hands(w):
        return ""
    fams = set(weapons_mod.ammo_families(w))
    if row("shield", s).get("bow_ok") and fams & {"arrows", "bolts", "bolas bolts"}:
        return ""
    name = str(weapons_mod.get(w)["name"]).lower()
    if weapon_key:
        return (f"The {name} takes both hands and the {row('shield', s)['name']} is on "
                f"the other arm: take the shield off first.")
    return (f"The {name} in hand takes both hands: put it away before strapping on the "
            f"{row('shield', s)['name']}.")


# --- proficiency ----------------------------------------------------------------------------

def proficiency_tags(token: str) -> list[str]:
    """The tags a class's armour token grants: "light armour" -> proficient.armour.light;
    "medium armour" also gives light, "heavy armour" all three, as the book's feats
    chain them; "shields" the shield tag; "tower shields" the tower one. [] for a token
    that is not about armour."""
    low = _norm(token)
    order = ("light", "medium", "heavy")
    m = re.match(r"^(light|medium|heavy) armour$", low)
    if m:
        return [f"proficient.armour.{w}" for w in order[:order.index(m.group(1)) + 1]]
    if low in ("shield", "shields"):
        return ["proficient.shield"]
    if low in ("tower shield", "tower shields"):
        return ["proficient.shield", "proficient.shield.tower"]
    return []


def is_armour_token(token: str) -> bool:
    low = _norm(token)
    return bool(proficiency_tags(token)) or low in ("no armour", "no metal armour")


def proficient_with(actor, kind: str, key: str) -> bool:
    """Whether the wearer is trained in what they have on. Nothing worn is always yes; a
    stat block's printed attack already counts whatever it wears."""
    if not key or key == "none" or getattr(actor, "flat_attack", None) is not None:
        return True
    if kind == "armour":
        return actor.has_state(f"proficient.armour.{row('armour', key).get('weight', 'light')}")
    if row("shield", key).get("tower"):
        return actor.has_state("proficient.shield.tower")
    return actor.has_state("proficient.shield")


def worn_rows(actor) -> tuple[dict, dict]:
    """(armour row, shield row) for what this creature has on — a forged suit's or
    shield's numbers from its build (`Actor.armour_stats` / `shield_stats`), else the
    table's.

    Measured 2026-10-04 (lane H): spell failure and the unproficient attack penalty both
    read `row("armour", actor.armour)`, the BASE suit's table row, so a mithral chain shirt
    still failed a wizard's spell 20% of the time where the book (and the sheet's own AC
    line, which already read the build) says 10%. One reader of what is worn, here."""
    a_key = str(getattr(actor, "armour", "none") or "none")
    s_key = str(getattr(actor, "shield", "none") or "none")
    a = actor.armour_stats() if hasattr(actor, "armour_stats") else row("armour", a_key)
    s = actor.shield_stats() if hasattr(actor, "shield_stats") else row("shield", s_key)
    return a, s


def worn_things(actor) -> list:
    """What this creature has on its body and arm, as things `item_tags` can read: the
    forged record when the suit (or shield) is one, else the crafted record in the slot
    whose base is the suit being worn (a tanner's studded leather, which knows its own
    studs), else the table key. Nothing for "none"."""
    out: list = []
    for kind, slot, record_of in (("armour", "armor", "armour_record"),
                                  ("shield", "shield", "shield_record")):
        key = str(getattr(actor, kind, "none") or "none")
        if key == "none":
            continue
        rec = getattr(actor, record_of)() if hasattr(actor, record_of) else None
        if rec is None:
            for name in (getattr(actor, "slots", {}) or {}).get(slot) or ():
                cand = (getattr(actor, "worn", {}) or {}).get(str(name or "").strip().lower())
                if isinstance(cand, dict) and key_for(str(cand.get("armour") or ""))[1] == key:
                    rec = cand
                    break
        out.append(rec if rec is not None else key)
    return out


def wears_metal(actor) -> bool:
    """Whether this creature has metal armour or a metal shield on — what inubrix's house
    clause (`when: {"target": {"armour_metal": true}}`) asks of a defender, and what the
    druid's rule and shocking grasp will ask. A stat block with a printed AC wears what its
    note says, which this cannot read, so it answers no: a clause nothing can evaluate is
    dropped, never applied.

    Asked of the material tag (`item_tags`, enchanting plan §16), never of a name. It was
    two name lists here, `METAL_ARMOUR` and `METAL_SHIELDS`, which made a forged shield
    metal by its base's name whatever it was made of, and a forged noqual breastplate
    metal only because "breastplate" was on the list."""
    if getattr(actor, "flat_ac", None) is not None:
        return False
    from . import item_tags
    from .states import METAL

    return any(item_tags.has_material(t, METAL) for t in worn_things(actor))


def attack_penalties(actor) -> list[tuple[int, str]]:
    """(value, why) for every attack-roll penalty what is worn imposes: the armour check
    penalty of anything worn unproficiently (CRB "Armor Proficiency": "The penalty for
    nonproficiency with armor stacks with the penalty for shields"), and the tower
    shield's own −2. Read by `Actor.attack_modifiers` into the one funnel."""
    out: list[tuple[int, str]] = []
    a_key = str(getattr(actor, "armour", "none") or "none")
    s_key = str(getattr(actor, "shield", "none") or "none")
    a, s = worn_rows(actor)
    if a_key != "none" and a.get("acp") and not proficient_with(actor, "armour", a_key):
        out.append((int(a["acp"]), f"not proficient with {a['name']}"))
    if s_key != "none" and s.get("acp") and not proficient_with(actor, "shield", s_key):
        out.append((int(s["acp"]), f"not proficient with {s['name']}"))
    if s_key != "none" and s.get("attack"):
        out.append((int(s["attack"]), f"{s['name']} (encumbering)"))
    return out


# --- arcane spell failure -------------------------------------------------------------------

# Which spell lists are arcane. 1e's arcane casters among the shipped classes are the
# wizard, the sorcerer and the bard; the rest are the later books', named so a homebrew class
# using their list is read the same way.
ARCANE_LISTS = frozenset({"wizard", "sorcerer", "sorcerer/wizard", "bard", "magus", "witch",
                          "summoner", "arcanist", "bloodrager", "skald"})


def is_arcane(actor) -> bool:
    from . import casting

    data = casting.caster_data(actor)
    if not data:
        return False
    if str(data.get("tradition") or "").lower() == "arcane":
        return True
    return str(data.get("list") or actor.char_class or "").strip().lower() in ARCANE_LISTS


def spell_failure(actor, spell) -> tuple[int, str]:
    """(percent, what causes it) for this caster casting this spell now, or (0, "").

    CRB "Arcane Spell Failure": "If the spell lacks a somatic component, however, it can be
    cast with no chance of arcane spell failure." Armour and shield add. The bard's own
    exception, CRB Bard "Armor and shield proficiency": bard spells in light armour carry
    no chance; medium or heavy armour or a shield still does."""
    if not is_arcane(actor):
        return 0, ""
    comps = [str(c).strip().upper() for c in (getattr(spell, "components", None) or ())]
    if comps and "S" not in comps:
        return 0, ""
    from . import casting

    a_key = str(getattr(actor, "armour", "none") or "none")
    s_key = str(getattr(actor, "shield", "none") or "none")
    a, s = worn_rows(actor)
    pct, why = 0, []
    bard = str(casting.caster_data(actor).get("list") or "").lower() == "bard"
    if a_key != "none" and a.get("asf") and not (bard and a.get("weight") == "light"):
        pct += int(a["asf"])
        why.append(str(a["name"]))
    if s_key != "none" and s.get("asf"):
        pct += int(s["asf"])
        why.append(str(s["name"]))
    return pct, " and ".join(why)


__all__ = ["key_for", "row", "change_cost", "proficiency_tags", "is_armour_token",
           "proficient_with", "attack_penalties", "is_arcane", "spell_failure",
           "ARCANE_LISTS", "worn_rows", "wears_metal", "worn_things"]
