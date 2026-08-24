"""The spell list, the filters that make three thousand of them usable, and the structured
half that lets one be authored and executed rather than only read.

Two kinds of label live on a spell here and they are kept apart on purpose.

**Descriptors** — `[fire]`, `[mind-affecting]`, `[curse]` — are rules facts with mechanical
consequences: a [fire] spell is stopped by fire immunity, a [mind-affecting] one does
nothing to an ooze. They are read from The Spell Codex's own columns and never inferred.
A guessed descriptor is worse than no descriptor, because it changes what the spell does.

**Tags** — `damage`, `dot`, `buff`, `control` — are ours. Pathfinder does not define them.
They exist so a player can find the right spell out of three thousand, and they are never
consulted by any rule. `tags_derived` is on the payload so nobody has to remember which is
which.

Spells belong to as many lists as they belong to: 2,887 of the 3,040 are on more than one,
so `lists` is a mapping of class to the level it sits at for that class, not a single
number.

---

## The structured half

The Codex gave us the *descriptive* half — school, range, duration, save, the class lists —
and nothing executable. `docs/spells.md` sets out the whole schema; the two decisions that
shape this file are these.

**Derived or stored, and the line between them.** Anything that is a re-reading of a fact
the corpus already states is *derived at load* and never written down: `element` from the
descriptors, `level_available` from `lists` plus the domain/bloodline/patron columns,
`range_value` and `area_value` from the printed lines, `save`/`save_effect` from the
saving-throw line. Storing those would put one fact in two places, which is the failure
`rules/creature_effects.py` names about `reductions` — correcting one leaves the other
saying the old thing and nothing reports the disagreement.

Anything that is a *machine's guess at English prose* is stored, in
`content/spells/spells-mechanics.json`, and flagged `effects_converted`. Once a person
corrects a converted effect, re-deriving it would overwrite the correction on the next
load. That is the same reason the ingredient corpus stopped deriving at read time.

**An authored value always wins.** Every derivation fills a field only when it is absent or
empty. A homebrew spell that states its own element keeps it; one that says nothing gets
the reading of its descriptors.

**The editor speaks text, the engine speaks structure.** `level_available` and `scaling`
are lists and dicts to the engine, and one-per-line text in the homebrew form, because the
form's field types are text, textarea, number, choice, list-of-fixed-choices and effects —
there is no editor for a mapping. `derive()` renders them out for the form and
`normalise()` reads them back, so authored → saved → loaded → castable is a round trip.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec

SCHOOLS = ("abjuration", "conjuration", "divination", "enchantment", "evocation",
           "illusion", "necromancy", "transmutation", "universal")

# The energy a spell is made of, as the user's own tag vocabulary names it. Deliberately
# *not* the descriptor list: [earth], [light] and [water] are real descriptors and none of
# them is an energy type anything takes damage as. Every member here is also a member of
# `effectspec.VOCAB["damage_type"]`, so an element can always be handed to a damage effect.
ELEMENTS = ("acid", "cold", "electricity", "fire", "force", "negative", "positive",
            "sonic", "untyped")

# Which descriptor states which element. Read straight off the Codex's own columns, so this
# is a lookup rather than an inference — the six energy descriptors and nothing else.
# [negative] and [positive] are not descriptors in 1e, so those two elements can only ever
# arrive from a converted damage formula or from an author.
DESCRIPTOR_ELEMENT = {e: e for e in ("acid", "cold", "electricity", "fire", "force",
                                     "sonic")}

COMPONENTS = ("V", "S", "M", "F", "DF")

# The 1e list names, and which class lists make each one up. `sorcerer/wizard` is the user's
# SPELLBOOK tag and it is a real thing in the book — one list two classes share — which is
# why it is derived from both rather than stored. A label appears only when every class in
# it carries the spell at the same level, so a spell that is 3rd for a wizard and 4th for a
# sorcerer reports neither rather than picking one.
SPELLBOOKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sorcerer/wizard", ("sorcerer", "wizard")),
    ("cleric/oracle", ("cleric", "oracle")),
    ("alchemist", ("alchemist",)), ("antipaladin", ("antipaladin",)),
    ("arcanist", ("arcanist",)), ("bard", ("bard",)), ("bloodrager", ("bloodrager",)),
    ("druid", ("druid",)), ("hunter", ("hunter",)), ("inquisitor", ("inquisitor",)),
    ("investigator", ("investigator",)), ("magus", ("magus",)), ("medium", ("medium",)),
    ("mesmerist", ("mesmerist",)), ("occultist", ("occultist",)), ("paladin", ("paladin",)),
    ("psychic", ("psychic",)), ("ranger", ("ranger",)), ("shaman", ("shaman",)),
    ("skald", ("skald",)), ("spiritualist", ("spiritualist",)), ("summoner", ("summoner",)),
    ("warpriest", ("warpriest",)), ("witch", ("witch",)),
)

# Everything that can grant a spell at a level. A class list is one of these rather than the
# special case it used to be, which is the whole point: a Domain, a Bloodline, a Mystery or
# a Patron says "you get this, at this level" in exactly the way a class list does, and the
# UI should not need a second widget to say it.
#
# `mystery` and `elemental school` carry no shipped data — the Codex export has columns for
# domain, bloodline and patron and none for those two — so they are authorable and empty
# rather than guessed at. `docs/spells.md` says so where somebody will read it.
GRANT_VIA = ("class", "domain", "bloodline", "patron", "mystery", "elemental school")

# What our derived tags mean, so a filter can explain itself rather than being a bare word.
TAG_NOTES = {
    "damage": "Deals hit point damage.",
    "dot": "Damage that repeats over rounds rather than landing once.",
    "healing": "Restores hit points or cures a condition.",
    "buff": "Grants a bonus, or is harmless to its target.",
    "debuff": "Imposes a penalty.",
    "control": "Denies movement or actions — held, entangled, asleep, paralysed.",
    "summoning": "Brings a creature.",
    "movement": "Teleport, flight, or speed.",
    "detection": "Finds or reveals something.",
    "defence": "Wards, resistances and deflection.",
    "illusion": "Of the illusion school.",
    "utility": "Everything the other tags did not claim.",
    "aoe": "Affects an area rather than a target.",
    "touch": "Range: touch.",
    "personal": "Range: personal — the caster only.",
    "ranged": "Cast at a distance.",
    "sustained": "Lasts while you concentrate.",
    "instant": "Resolves and is over.",
    "permanent": "Does not expire on its own.",
    "harmless": "The save is there for an unwilling ally.",
    "save-negates": "A successful save stops it entirely.",
    "save-half": "A successful save halves it.",
    "save-partial": "A successful save reduces it.",
    "no-save": "No saving throw.",
}


@dataclass
class Spell:
    id: str
    name: str
    school: str = ""
    subschool: str = ""
    descriptors: list[str] = field(default_factory=list)
    lists: dict[str, int] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    casting_time: str = ""
    range: str = ""
    area: str = ""
    effect: str = ""
    targets: str = ""
    duration: str = ""
    saving_throw: str = ""
    spell_resistance: str = ""
    components: list[str] = field(default_factory=list)
    component_cost: str = ""
    dismissible: bool = False
    shapeable: bool = False
    source: str = ""
    description: str = ""
    deity: str = ""
    domain: str = ""
    bloodline: str = ""
    patron: str = ""
    sla_level: int | None = None

    # --- the structured half -------------------------------------------------------------
    # Every one of these is filled by `normalise` when the stored entry does not carry it,
    # and left exactly as authored when it does.
    element: str = ""
    # One entry per way of getting the spell: {"via", "name", "level"} and, where the source
    # printed a class level rather than a spell level, the `at` it printed.
    level_available: list[dict] = field(default_factory=list)
    spellbooks: list[str] = field(default_factory=list)
    # {"kind": "damage"|"healing", "die", "dice_per", "per_levels", "cap_dice",
    #  "base_dice", "flat_bonus", "bonus_per_level", "bonus_cap", "damage_type",
    #  "lethality"} — see `scaling_dice`.
    scaling: dict = field(default_factory=dict)
    effects: list[dict] = field(default_factory=list)
    # True while a machine's reading of the prose stands unreviewed. The editor clears it
    # on save, exactly as the ingredient and creature corpora do.
    effects_converted: bool = False
    range_value: dict = field(default_factory=dict)
    area_value: dict = field(default_factory=dict)
    save: str = ""              # "" | fort | ref | will
    save_effect: str = ""       # "" | none | negates | half | partial | disbelief | see text
    save_harmless: bool = False
    sr: bool | None = None      # None where the line says "see text" or says nothing

    @property
    def min_level(self) -> int | None:
        return min(self.lists.values()) if self.lists else None

    @property
    def line(self) -> str:
        """The one-line summary a list view shows."""
        bits = [self.school + (f" ({self.subschool})" if self.subschool else "")]
        if self.descriptors:
            bits.append("[" + "] [".join(self.descriptors) + "]")
        if self.lists:
            bits.append(", ".join(f"{k} {v}" for k, v in
                                  sorted(self.lists.items(), key=lambda kv: kv[1])[:4]))
        return " · ".join(b for b in bits if b)

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["min_level"] = self.min_level
        d["line"] = self.line
        return d


def from_dict(d: dict) -> Spell:
    known = Spell.__dataclass_fields__
    return Spell(**{k: v for k, v in d.items() if k in known})


# --- the level a thing is available at ---------------------------------------------------
#
# Domain, bloodline and patron are printed in the corpus as "Fire (3)", "Efreeti (7)",
# "Elements (6)" — and the number does not mean the same thing in all three, which is the
# trap that makes a naive read wrong.
#
#   Domain    the number IS the spell level. Fire (3) is fireball as a 3rd-level domain
#             spell. Measured across the corpus: 1-9, every value, nothing else.
#   Bloodline the number is the *sorcerer level* the bonus spell arrives at. 3, 5, 7 … 19,
#             odd only, measured — and 1e grants spell level (n-1)/2 at each. Efreeti (7)
#             is therefore a 3rd-level spell, which is what the user's own tag list says.
#   Patron    the number is the *witch level*: 2, 4, 6 … 18, even only, measured, granting
#             spell level n/2. Elements (6) is a 3rd-level spell.
#
# A bloodrager's bloodline runs on its own clock — 7, 10, 13, 16 for spell levels 1-4 — and
# the corpus writes those as "Aberrant (BloodRager) (16)", which is why the class is parsed
# out of the name rather than assumed.
_GRANT = re.compile(r"^(?P<name>.+?)\s*\((?P<at>\d+)\)$")
_GRANT_CLASS = re.compile(r"^(?P<name>.+?)\s*\((?P<klass>[A-Za-z ]+)\)$")


def _spell_level_from(via: str, at: int, of: str) -> int | None:
    """The spell level a printed class level corresponds to, or None if it does not."""
    if via == "domain":
        return at if 0 <= at <= 9 else None
    if via == "bloodline":
        if of == "bloodrager":
            # 7/10/13/16 → 1/2/3/4. Anything off that grid is not a bloodrager grant.
            return (at - 4) // 3 if at in (7, 10, 13, 16) else None
        return (at - 1) // 2 if at % 2 == 1 and 3 <= at <= 19 else None
    if via == "patron":
        return at // 2 if at % 2 == 0 and 2 <= at <= 18 else None
    return None


def _column_grants(via: str, column: str) -> list[dict]:
    """"Fire (3), Ash (3)" as grants. One column, however many things it names."""
    out: list[dict] = []
    for part in (column or "").split(","):
        part = part.strip()
        if not part:
            continue
        m = _GRANT.match(part)
        if not m:
            continue
        name, at = m.group("name").strip(), int(m.group("at"))
        of = "sorcerer" if via == "bloodline" else ("witch" if via == "patron" else "")
        inner = _GRANT_CLASS.match(name)
        if inner:
            # "Aberrant (BloodRager)" — the class is stated, so use it rather than the
            # default. Thirteen entries in the corpus are written this way and reading them
            # as sorcerer grants would have put a 16th-level number through the sorcerer
            # formula and produced an 8th-level fireball.
            name, of = inner.group("name").strip(), inner.group("klass").strip().lower()
        level = _spell_level_from(via, at, of)
        if level is None:
            continue
        grant = {"via": via, "name": name.lower(), "level": level}
        if at != level:
            # Kept because it is the number the book prints and a player looking for
            # "when do I get this" needs it. Dropped for domains, where it is the level.
            grant["at"] = at
            grant["of"] = of
        out.append(grant)
    return out


def level_available_for(d: dict) -> list[dict]:
    """Every way of getting this spell, unified — a class list is one of them.

    Derived rather than stored: `lists`, `domain`, `bloodline` and `patron` already carry
    every fact in here, and a second copy is the thing that disagrees after somebody edits
    the first.
    """
    out = [{"via": "class", "name": k, "level": int(v)}
           for k, v in sorted((d.get("lists") or {}).items())]
    for via, column in (("domain", d.get("domain")), ("bloodline", d.get("bloodline")),
                        ("patron", d.get("patron"))):
        out.extend(_column_grants(via, column or ""))
    return out


def parse_level_available(text) -> tuple[list[dict], list[str]]:
    """The homebrew form's one-per-line notation, and everything wrong with it.

    `wizard 3`, `domain fire 3`, `bloodline efreeti 3`, `mystery flame 3`. This is as close
    as a textarea gets to the user's `{{Domain : fire} : 3}` — the same three facts in the
    same order, without asking anyone to balance braces.

    Problems come back as a list rather than an exception because `validate_spell` shows a
    form all of its errors at once.
    """
    if isinstance(text, list):
        # Already structured, or a list of lines. Both shapes reach here: the engine's own
        # and a client that posted the textarea split.
        if all(isinstance(x, dict) for x in text):
            return [dict(x) for x in text], []
        text = "\n".join(str(x) for x in text)
    grants: list[dict] = []
    problems: list[str] = []
    for raw in str(text or "").replace(";", "\n").splitlines():
        line = raw.strip().strip(",").lower()
        if not line:
            continue
        # The user's own braces and colons are accepted and thrown away, so a line pasted
        # straight out of their tag notation is not an error.
        line = re.sub(r"[{}:]", " ", line)
        words = line.split()
        if not words:
            continue
        if not words[-1].isdigit():
            problems.append(f"level_available: {raw.strip()!r} does not end in a level.")
            continue
        level = int(words[-1])
        words = words[:-1]
        via = "class"
        for candidate in sorted(GRANT_VIA, key=len, reverse=True):
            parts = candidate.split()
            if [w for w in words[:len(parts)]] == parts:
                via, words = candidate, words[len(parts):]
                break
        name = " ".join(words).strip()
        if not name:
            problems.append(f"level_available: {raw.strip()!r} names no {via}.")
            continue
        if not 0 <= level <= 9:
            problems.append(
                f"level_available: {name} {level} — spell levels run 0 to 9.")
            continue
        grants.append({"via": via, "name": name, "level": level})
    return grants, problems


def format_level_available(grants: list[dict]) -> str:
    """Grants back as the text the homebrew form edits."""
    lines = []
    for g in grants or []:
        via = str(g.get("via", "class"))
        head = "" if via == "class" else f"{via} "
        lines.append(f"{head}{g.get('name', '')} {g.get('level', '')}".strip())
    return "\n".join(lines)


def spellbooks_for(lists: dict) -> list[str]:
    """The 1e list names this spell is on — the user's SPELLBOOK tag."""
    out = []
    for label, members in SPELLBOOKS:
        levels = {lists.get(m) for m in members}
        if len(levels) == 1 and None not in levels:
            out.append(label)
    return out


# --- range and area as values rather than prose -------------------------------------------

# 1e's three bands, as (base feet, feet added, per how many caster levels). Typed out
# because they are not one rule: close adds every two levels and the other two add every
# level, and a single "feet per level" field would be wrong for 876 spells.
_RANGE_BANDS = {"close": (25, 5, 2), "medium": (100, 10, 1), "long": (400, 40, 1)}
_RANGE_FIXED = re.compile(r"^(?:feet|ft\.?)\s*\((\d+)\)")
_RANGE_PER_LEVEL = re.compile(r"^(miles?|feet|ft\.?)\s*/\s*level\s*\((\d+)\)")


def parse_range(text: str) -> dict:
    """The printed range line as something the grid can measure.

    Left empty rather than guessed when the line is "see text" or something the vocabulary
    has no shape for: a range of zero would read as a value somebody chose.
    """
    s = (text or "").strip().lower()
    if not s:
        return {}
    for band, (base, add, every) in _RANGE_BANDS.items():
        if s.startswith(band):
            return {"kind": band, "feet": base, "add": add, "every": every,
                    "unit": "feet"}
    if s.startswith("touch"):
        return {"kind": "touch", "feet": 0, "unit": "feet"}
    if s.startswith("personal"):
        return {"kind": "personal", "feet": 0, "unit": "feet"}
    if s.startswith("unlimited"):
        return {"kind": "unlimited"}
    m = _RANGE_FIXED.match(s)
    if m:
        return {"kind": "fixed", "feet": int(m.group(1)), "unit": "feet"}
    m = _RANGE_PER_LEVEL.match(s)
    if m:
        unit = "miles" if m.group(1).startswith("mile") else "feet"
        return {"kind": "per_level", "feet": 0, "add": int(m.group(2)), "every": 1,
                "unit": unit}
    return {}


def range_feet(spell, caster_level: int) -> int | None:
    """How far this spell reaches for that caster, or None where it is not a distance.

    1e rounds *down* to the whole increment: close range at caster level 5 is 25 + 5×(5//2)
    = 35 feet, not 37. That is what `every` is for.
    """
    v = spell.range_value if isinstance(spell, Spell) else (spell or {})
    if not v or v.get("kind") in ("unlimited", "personal"):
        return None
    feet = int(v.get("feet", 0))
    if v.get("add"):
        feet += int(v["add"]) * (max(1, int(caster_level)) // int(v.get("every", 1)))
    if v.get("unit") == "miles":
        feet *= 5280
    return feet


_AREA_RADIUS = re.compile(
    r"(\d+)\s*-?\s*(?:foot|ft\.?)\s*-?\s*radius\s*(spread|burst|emanation|cylinder)?", re.I)
_AREA_CONE = re.compile(r"cone\s*-?\s*shaped\s*(burst|emanation|spread)?", re.I)
_AREA_LINE = re.compile(r"(\d+)\s*-?\s*(?:foot|ft\.?)\s*(line|cube|square|wall)", re.I)


def parse_area(text: str) -> dict:
    """The printed area line as a shape and a size.

    "20-foot-radius spread" is the whole fact for fireball, and the same six words appear on
    hundreds of spells. Anything the three patterns do not recognise stays prose — an area
    the grid draws wrongly is worse than an area it declines to draw.
    """
    s = (text or "").strip()
    if not s:
        return {}
    out: dict = {}
    m = _AREA_RADIUS.search(s)
    if m:
        out = {"shape": (m.group(2) or "radius").lower(), "radius": int(m.group(1)),
               "unit": "feet"}
    else:
        m = _AREA_LINE.search(s)
        if m:
            out = {"shape": m.group(2).lower(), "length": int(m.group(1)), "unit": "feet"}
        elif _AREA_CONE.search(s):
            # The cone's length is in the spell's prose, not in this line. Recording a
            # length here would be inventing one.
            out = {"shape": "cone", "unit": "feet"}
    if out and re.search(r"centered on you|centred on you", s, re.I):
        out["origin"] = "you"
    elif out and re.search(r"centered on|centred on|from the touched", s, re.I):
        out["origin"] = "point"
    return out


# --- the saving throw line, and spell resistance -------------------------------------------

_SAVES = {"fortitude": "fort", "fort": "fort", "reflex": "ref", "ref": "ref",
          "will": "will"}
_SAVE_EFFECTS = ("negates", "half", "partial", "disbelief", "none")


def parse_save(text: str) -> tuple[str, str, bool]:
    """(save, what a success does, whether it is harmless) out of "Reflex half".

    `harmless` matters and is not decoration: 560 spells carry it, and it means the save is
    there for an ally who does not want the spell rather than for an enemy resisting it.
    """
    s = (text or "").strip().lower()
    if not s:
        return "", "", False
    harmless = "harmless" in s
    save = ""
    for word, key in _SAVES.items():
        if re.search(r"\b" + word + r"\b", s):
            save = key
            break
    effect = ""
    for word in _SAVE_EFFECTS:
        if word in s:
            effect = word
            break
    if not effect and "see text" in s:
        effect = "see text"
    return save, effect, harmless


def parse_sr(text: str) -> bool | None:
    """Whether spell resistance applies. None where the line will not say.

    442 spells state nothing and 21 say "see text"; answering False for those would tell a
    GM that SR does not apply, which the source never said.
    """
    s = (text or "").strip().lower()
    if not s or s.startswith("see text"):
        return None
    if s.startswith("yes"):
        return True
    if s.startswith("no and yes") or s.startswith("no or yes"):
        return None
    if s.startswith("no"):
        return False
    return None


# --- scaling ------------------------------------------------------------------------------
#
# The user wrote it as `{Damage] : 1d6/caster_lvl`. As a value it needs five numbers, because
# the corpus writes five different shapes of the same idea:
#
#   fireball          1d6 per caster level, maximum 10d6
#   searing light     1d8 per *two* caster levels, maximum 5d8
#   acid arrow        2d4, flat, no scaling at all
#   magic missile     1d4+1, flat, with a fixed bonus
#   cure light wounds 1d8 plus 1 point per caster level, maximum +5
#
# One dict holds all five: dice_per/per_levels/cap_dice for the dice, base_dice/flat_bonus
# for what does not scale, bonus_per_level/bonus_cap for the points that do.

_SCALING_KEYS = ("kind", "die", "dice_per", "per_levels", "cap_dice", "base_dice",
                 "flat_bonus", "bonus_per_level", "bonus_cap", "damage_type", "lethality")
_DIVISORS = {"two": 2, "2": 2, "three": 3, "3": 3, "four": 4, "4": 4}


def scaling_dice(spell, caster_level: int) -> str:
    """The actual dice this spell rolls for that caster. "" when it has no formula.

    Fireball at caster level 5 is 5d6 and at 10, 20 or 40 it is 10d6, because the cap is
    part of the formula rather than a note beside it.
    """
    sc = spell.scaling if isinstance(spell, Spell) else (spell or {})
    if not sc or not sc.get("die"):
        return ""
    cl = max(1, int(caster_level))
    per = max(1, int(sc.get("per_levels", 1) or 1))
    dice_per = int(sc.get("dice_per", 0) or 0)
    count = int(sc.get("base_dice", 0) or 0)
    if dice_per:
        # At least one die: "1d8 per two caster levels" at caster level 1 is not zero dice,
        # it is the smallest the spell can be.
        count += max(dice_per, dice_per * (cl // per))
    cap = int(sc.get("cap_dice", 0) or 0)
    if cap:
        count = min(count, cap)
    count = max(1, count)

    bonus = int(sc.get("flat_bonus", 0) or 0)
    if sc.get("bonus_per_level"):
        scaled = int(sc["bonus_per_level"]) * cl
        cap_b = int(sc.get("bonus_cap", 0) or 0)
        bonus += min(scaled, cap_b) if cap_b else scaled
    return f"{count}d{int(sc['die'])}" + (f"+{bonus}" if bonus else "")


def parse_scaling(text) -> tuple[dict, list[str]]:
    """The homebrew form's own notation: `1d6/level, max 10d6`, `1d8/2 levels, max 5d8`,
    `2d4`, `1d8+1/level, max +5`.

    Written to read like the user's `1d6/caster_lvl` rather than like a JSON object, on the
    grounds that somebody authoring a spell is thinking in the book's notation.
    """
    if isinstance(text, dict):
        return {k: v for k, v in text.items() if k in _SCALING_KEYS}, []
    s = str(text or "").strip().lower().replace("caster_lvl", "level")
    if not s:
        return {}, []
    m = re.match(r"^\s*(\d*)d(\d+)\s*(?:\+\s*(\d+))?", s)
    if not m:
        return {}, [f"scaling: {text!r} does not start with dice — write 1d6/level."]
    out: dict = {"kind": "healing" if "heal" in s or "cure" in s else "damage",
                 "die": int(m.group(2))}
    count = int(m.group(1) or 1)
    rest = s[m.end():]
    per = re.search(r"/\s*(?:(\d+)\s*)?levels?", rest)
    bonus_per = re.search(r"\+\s*(\d+)\s*(?:points?\s*)?/\s*(?:(\d+)\s*)?levels?", rest)
    if bonus_per:
        out["base_dice"] = count
        out["bonus_per_level"] = int(bonus_per.group(1))
        cap = re.search(r"max(?:imum)?\s*\+\s*(\d+)", rest)
        if cap:
            out["bonus_cap"] = int(cap.group(1))
    elif per:
        out["dice_per"] = count
        out["per_levels"] = int(per.group(1) or 1)
        cap = re.search(r"max(?:imum)?\s*(?:of\s*)?(\d+)\s*d\s*\d+", rest)
        if cap:
            out["cap_dice"] = int(cap.group(1))
    else:
        out["base_dice"] = count
        if m.group(3):
            out["flat_bonus"] = int(m.group(3))
    for word in ELEMENTS:
        if re.search(r"\b" + word + r"\b", rest):
            out["damage_type"] = word
            break
    return out, []


def format_scaling(sc: dict) -> str:
    """A scaling formula back as the text the homebrew form edits."""
    if not sc or not sc.get("die"):
        return ""
    die = int(sc["die"])
    if sc.get("dice_per"):
        head = f"{int(sc['dice_per'])}d{die}/"
        every = int(sc.get("per_levels", 1) or 1)
        head += "level" if every == 1 else f"{every} levels"
        if sc.get("cap_dice"):
            head += f", max {int(sc['cap_dice'])}d{die}"
    else:
        head = f"{int(sc.get('base_dice', 1) or 1)}d{die}"
        if sc.get("flat_bonus"):
            head += f"+{int(sc['flat_bonus'])}"
        if sc.get("bonus_per_level"):
            head += f"+{int(sc['bonus_per_level'])}/level"
            if sc.get("bonus_cap"):
                head += f", max +{int(sc['bonus_cap'])}"
    if sc.get("damage_type"):
        head += f" {sc['damage_type']}"
    return head


def effects_at(spell, caster_level: int) -> list[dict]:
    """This spell's effects with the dice a given caster actually rolls filled in.

    The stored effect carries the smallest the spell can be — fireball's `1d6` — plus a
    `scales` marker, because `effectspec.validate` requires the dice field to *be* dice and
    "1d6/level" is not. The formula lives once, on the spell, and this is the only place it
    is applied.

    `scales: "half"` is the success branch of a "Reflex half" spell. It carries half the
    dice rather than half the rolled total: the schema has no way to say "roll and halve",
    and the two have the same mean, the same floor and the same ceiling. The engine, which
    does have the rolled total, should prefer halving it — `docs/spells.md` says so under
    INTEGRATION NOTES.
    """
    dice = scaling_dice(spell, caster_level)
    out = copy.deepcopy(spell.effects if isinstance(spell, Spell) else (spell or []))
    if not dice:
        return out

    def half(text: str) -> str:
        m = re.match(r"^(\d+)d(\d+)(?:\+(\d+))?$", text)
        if not m:
            return text
        count = max(1, int(m.group(1)) // 2)
        bonus = int(m.group(3) or 0) // 2
        return f"{count}d{m.group(2)}" + (f"+{bonus}" if bonus else "")

    def walk(specs: list[dict]) -> None:
        for spec in specs:
            mark = spec.get("scales")
            if mark == "full":
                spec["dice"] = dice
            elif mark == "half":
                spec["dice"] = half(dice)
            for branch in ("on_failure", "on_success"):
                if isinstance(spec.get(branch), list):
                    walk(spec[branch])

    walk(out)
    return out


# --- reading the prose ---------------------------------------------------------------------
#
# Every one of these is a *detection*, in the shape CLAUDE.md names as the only kind of fix
# that has held: find the defect — here, find the formula — mechanically, and leave alone
# what was not found. Nothing below infers a number that the sentence did not print.

# The energy words the corpus actually writes, mapped onto `effectspec`'s damage types. A
# word that is not in here is a refusal, not a guess: "magical slashing", "dexterity and
# strength" and "hit points of" all appear as the matched group and none of them is a
# damage type. Converting them by picking the nearest one is how a spell ends up dealing
# the wrong kind of damage with nobody able to see why.
_ENERGY_WORDS = {
    "": "untyped", "energy": "untyped", "untyped": "untyped",
    "fire": "fire", "cold": "cold", "acid": "acid", "sonic": "sonic",
    "electricity": "electricity", "electrical": "electricity",
    "force": "force", "negative energy": "negative", "positive energy": "positive",
    "bludgeoning": "bludgeoning", "piercing": "piercing", "slashing": "slashing",
    "nonlethal": "untyped",
}

_DICE = r"(?P<count>\d*)d(?P<die>\d+)"
_OF_DAMAGE = r"\s*(?:points?\s*)?(?:of\s*)?(?P<type>[a-z][a-z ]*?)?\s*damage"
_PER_LEVEL = (r"\s*(?:/|per\s+)\s*(?:(?P<div>two|three|four|2|3|4)\s+)?caster\s+levels?")

# "deals 1d6 points of fire damage/caster level" — 1e's commonest formula by a distance.
_RE_PER_LEVEL = re.compile(_DICE + _OF_DAMAGE + _PER_LEVEL, re.I)
# "cures 1d8 points of damage + 1 point per caster level"
_RE_HEAL_PLUS = re.compile(
    r"cur(?:es|ing)\s+" + _DICE + r"\s*points?\s*of\s*damage\s*\+\s*(?P<per>\d+)\s*"
    r"points?\s*(?:/|per\s+)\s*caster\s+level", re.I)
# "deals 1d8 points of damage + 1 point per caster level" — inflict wounds and its family.
_RE_DAMAGE_PLUS = re.compile(
    r"deals?\s+" + _DICE + r"\s*points?\s*of\s*damage\s*\+\s*(?P<per>\d+)\s*"
    r"points?\s*(?:/|per\s+)\s*caster\s+level", re.I)
# "deals 2d4 points of acid damage", "dealing 1d4+1 points of force damage"
_RE_FLAT = re.compile(
    r"(?:deals?|dealing|inflicts?|takes?|taking|suffers?)\s+" + _DICE
    + r"(?:\s*\+\s*(?P<plus>\d+))?" + _OF_DAMAGE, re.I)

_RE_CAP_DICE = re.compile(r"maximum\s+(?:of\s+)?(\d+)\s*d\s*(\d+)", re.I)
_RE_CAP_BONUS = re.compile(r"maximum\s+(?:of\s+)?\+\s*(\d+)", re.I)

# Words immediately before a formula that mean it is not the spell's own damage. "an
# additional 1d4 points of acid damage" on acid maw is a rider on a companion's bite, and
# converting it makes the spell itself deal damage it does not deal.
_VETO_BEFORE = re.compile(
    r"(additional|extra|more|another|each additional|instead|rather than|as if|"
    r"such as|for example)\s*$", re.I)


def _energy(word: str | None) -> str | None:
    return _ENERGY_WORDS.get((word or "").strip().lower())


def _cap_near(text: str, end: int, pattern: re.Pattern) -> re.Match | None:
    """A maximum stated within the same clause as the formula.

    Bounded to 140 characters because "maximum" appears elsewhere in long descriptions —
    "a maximum depth of 100 feet" on acid pit — and an unbounded search picks up the wrong
    one two sentences later.
    """
    return pattern.search(text[end:end + 140])


def read_scaling(entry: dict) -> dict | None:
    """The damage or healing formula printed in this spell's prose, or None.

    Gated on our own `damage` and `healing` tags: a spell that is not about damage but
    mentions some in passing is not converted. `dot` is refused outright — repeating damage
    has no shape in `effectspec` beyond `bleed`, and flattening "1d6 each round" into one
    hit understates the spell by however many rounds it lasts.
    """
    tags = set(entry.get("tags") or ())
    if "dot" in tags or not ({"damage", "healing"} & tags):
        return None
    text = entry.get("description") or ""

    for pattern, kind in ((_RE_HEAL_PLUS, "healing"), (_RE_DAMAGE_PLUS, "damage")):
        m = pattern.search(text)
        if not m:
            continue
        out = {"kind": kind, "die": int(m.group("die")),
               "base_dice": int(m.group("count") or 1),
               "bonus_per_level": int(m.group("per"))}
        cap = _cap_near(text, m.end(), _RE_CAP_BONUS)
        if cap:
            out["bonus_cap"] = int(cap.group(1))
        # cure/inflict are the positive and negative energy pair, and the prose says which.
        out["damage_type"] = "positive" if kind == "healing" else (
            "negative" if re.search(r"negative energy", text, re.I) else "untyped")
        return out

    for m in _RE_PER_LEVEL.finditer(text):
        if _VETO_BEFORE.search(text[max(0, m.start() - 24):m.start()]):
            continue
        energy = _energy(m.group("type"))
        if energy is None:
            return None
        out = {"kind": "damage", "die": int(m.group("die")),
               "dice_per": int(m.group("count") or 1),
               "per_levels": _DIVISORS.get((m.group("div") or "").lower(), 1),
               "damage_type": energy}
        if (m.group("type") or "").strip().lower() == "nonlethal":
            out["lethality"] = "nonlethal"
        cap = _cap_near(text, m.end(), _RE_CAP_DICE)
        if cap:
            out["cap_dice"] = int(cap.group(1))
        return out

    for m in _RE_FLAT.finditer(text):
        if _VETO_BEFORE.search(text[max(0, m.start() - 24):m.start()]):
            continue
        energy = _energy(m.group("type"))
        if energy is None:
            return None
        out = {"kind": "damage", "die": int(m.group("die")),
               "base_dice": int(m.group("count") or 1), "damage_type": energy}
        if m.group("plus"):
            out["flat_bonus"] = int(m.group("plus"))
        if (m.group("type") or "").strip().lower() == "nonlethal":
            out["lethality"] = "nonlethal"
        return out
    return None


# The DC an authored save gate carries. The engine recomputes it from the sheet — the spell
# does not know the caster's ability modifier — so this is the formula rather than a number,
# and `effectspec`'s `dc` field is declared as a formula for exactly this.
SAVE_DC_FORMULA = "10 + spell level + casting ability modifier"


def effects_from_scaling(entry: dict, sc: dict) -> list[dict]:
    """One converted formula as effects the engine can hold.

    The save gate is built from the printed saving-throw line rather than assumed, which is
    why "Reflex half" and "Reflex negates" produce different success branches and "none"
    produces no gate at all.
    """
    if not sc:
        return []
    dice = f"{max(1, int(sc.get('dice_per') or sc.get('base_dice') or 1))}d{sc['die']}"
    if sc.get("kind") == "healing":
        core = {"type": "heal", "dice": dice, "lethality": "lethal", "scales": "full",
                "note": "scales with caster level"}
    else:
        core = {"type": "damage", "dice": dice,
                "damage_type": sc.get("damage_type", "untyped"),
                "lethality": sc.get("lethality", "lethal"), "scales": "full",
                "note": "scales with caster level"}

    save, effect, harmless = parse_save(entry.get("saving_throw", ""))
    if not save or harmless or effect in ("", "none", "see text", "disbelief"):
        return [core]

    branch_ok: list[dict] = []
    if effect == "half":
        halved = dict(core)
        halved["scales"] = "half"
        halved["note"] = "half on a successful save"
        branch_ok = [halved]
    gate = {"type": "save_gate", "target": save, "dc": SAVE_DC_FORMULA,
            "on_failure": [core], "on_success": branch_ok}
    if effect == "partial":
        gate["note"] = "partial: the rest of the effect is in the spell's text"
    return [gate]


# --- the buffs and cures nobody's regex was going to find ------------------------------------
#
# Hand-authored, one at a time, because their prose says "+4 armor bonus to AC" in a
# sentence and no pattern that reads that reliably would stop at these eleven. They are not
# flagged `effects_converted`: a person wrote them, which is a different state from "a
# machine read the prose and nobody has checked".
#
# Two of these are honest compromises with a vocabulary this module may not change, and both
# say so in a `note` that reaches the card:
#
#   mage armor  grants an *armour* bonus, and `effectspec.VOCAB["bonus_type"]` has no such
#               entry — it has shield, deflection and natural armour and stops there. Written
#               untyped, which stacks with things it should not. Named in docs/spells.md
#               under INTEGRATION NOTES as one missing vocabulary entry.
#   resist energy chooses its energy type when it is cast, and no effect type takes a
#               parameter at cast time. Written as narrative rather than as `resistance
#               fire`, because naming fire would be inventing a choice the caster makes.
CURATED: dict[str, list[dict]] = {
    # Hand-written because the corpus tags it `utility` and the converter is gated on
    # `damage` — relaxing that gate to catch this one spell also caught constricting coils,
    # black tentacles and summon stampede, all three of which deal their damage every round
    # and would have been flattened into a single hit. One wrong number in three is a worse
    # trade than writing this one out.
    #
    # The missile count has no shape in `scaling`: 1e adds a missile every two caster levels
    # to a maximum of five, and each is its own attack. Expressing it as 5d4+5 would be
    # right about the total and wrong about everything else, so the note carries it.
    "magic-missile": [
        {"type": "damage", "dice": "1d4+1", "damage_type": "force", "lethality": "lethal",
         "note": "per missile — one, plus one more per two caster levels above 1st, to a "
                 "maximum of five at caster level 9"},
    ],
    "bless": [
        {"type": "combat_mod", "amount": 1, "bonus_type": "morale", "target": "attack"},
        {"type": "save_mod", "amount": 1, "bonus_type": "morale", "target": "will",
         "note": "against fear effects"},
    ],
    "mage-armor": [
        {"type": "combat_mod", "amount": 4, "bonus_type": "untyped", "target": "ac",
         "note": "armour bonus — does not stack with worn armour"},
    ],
    "shield-of-faith": [
        {"type": "combat_mod", "amount": 2, "bonus_type": "deflection", "target": "ac",
         "note": "+1 more per six caster levels, maximum +5"},
    ],
    "barkskin": [
        {"type": "combat_mod", "amount": 2, "bonus_type": "natural armour", "target": "ac",
         "note": "+1 more per three caster levels above 3rd, maximum +5"},
    ],
    "resist-energy": [
        {"type": "narrative",
         "target": "Resist 10 against one energy type chosen as the spell is cast — 20 at "
                   "caster level 7, 30 at caster level 11"},
    ],
    "bull-s-strength": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "str"},
    ],
    "cat-s-grace": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "dex"},
    ],
    "bear-s-endurance": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "con"},
    ],
    "fox-s-cunning": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "int"},
    ],
    "owl-s-wisdom": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "wis"},
    ],
    "eagle-s-splendor": [
        {"type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "cha"},
    ],
}


def convert(entry: dict) -> tuple[dict, list[str]]:
    """One spell's mechanical half, and any spec the schema refused.

    Refusals come back rather than being raised: a run over 3,040 spells that stops at the
    first bad one tells you nothing about the other 3,039.
    """
    out: dict = {}
    problems: list[str] = []
    curated = CURATED.get(entry.get("id", ""))
    sc = read_scaling(entry)
    if sc:
        out["scaling"] = sc
    specs = list(curated) if curated else effects_from_scaling(entry, sc)
    for spec in specs:
        found = effectspec.validate(spec, entry.get("id", "?"))
        problems.extend(found)
    if specs:
        out["effects"] = specs
        # Only a machine's reading is flagged. The eleven written by hand are not waiting
        # for anybody to check them.
        out["effects_converted"] = not curated
    return out, problems


def build_mechanics(entries: list[dict] | None = None) -> tuple[dict, dict]:
    """Every spell's converted mechanics, and an honest count of what was left as prose.

    Written to a file rather than derived at load, and that is the lesson from the
    ingredient corpus rather than a preference: an effect derived at read time is silently
    overwritten the moment somebody corrects it, so the parse becomes a starting point in a
    file and `effects_converted` marks what nobody has read.
    """
    if entries is None:
        entries = _shipped_entries()
    out: dict[str, dict] = {}
    report = {"total": len(entries), "scaling": 0, "effects": 0, "curated": 0,
              "prose": 0, "invalid": [], "by_kind": {}}
    for entry in entries:
        got, problems = convert(entry)
        report["invalid"].extend(problems)
        if not got:
            report["prose"] += 1
            continue
        out[entry["id"]] = dict(got, id=entry["id"])
        if got.get("scaling"):
            report["scaling"] += 1
            kind = got["scaling"].get("kind", "damage")
            report["by_kind"][kind] = report["by_kind"].get(kind, 0) + 1
        if got.get("effects"):
            report["effects"] += 1
        if not got.get("effects_converted", True):
            report["curated"] += 1
    return out, report


def _shipped_entries() -> list[dict]:
    """The Codex file as it ships, without the mechanics layered over it."""
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "spells" / "spells.json"
    return json.loads(path.read_text(encoding="utf-8"))["spells"]


def write_mechanics() -> dict:
    """Rebuild `content/spells/spells-mechanics.json`. Run when the conversion changes."""
    from django.conf import settings

    entries, report = build_mechanics()
    path = Path(settings.BASE_DIR) / "content" / "spells" / "spells-mechanics.json"
    payload = {
        "note": "Damage, healing and the classic buffs, read out of the Codex's prose by "
                "rules.spells.build_mechanics. `effects_converted` marks a machine's "
                "reading that nobody has checked; the eleven hand-written entries do not "
                "carry it. Everything the parser could not read with certainty is absent "
                "from this file and remains prose in spells.json.",
        "spells": [entries[k] for k in sorted(entries)],
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return report


# --- normalisation, and loading --------------------------------------------------------------

def normalise(d: dict) -> dict:
    """Fill in the structured half of one stored entry, without ever overwriting it.

    Called on the merged result of shipped-plus-homebrew, so a homebrew spell that states
    only a name, a school and three lines of `level_available` comes out of here with the
    `lists` a caster is checked against — which is what makes an authored spell castable
    rather than merely listed.
    """
    out = dict(d)

    # The form edits three of these as text because there is no editor for a list of free
    # strings, so what comes back is a string and what the engine reads is a list. Coerced
    # here rather than in the view, so a hand-written homebrew file may use either shape.
    for key in ("descriptors", "components"):
        value = out.get(key)
        if isinstance(value, str):
            out[key] = [p.strip() for p in re.split(r"[,;]", value) if p.strip()]
    if isinstance(out.get("dismissible"), str):
        out["dismissible"] = out["dismissible"].strip().lower() in ("yes", "true", "1")
    if isinstance(out.get("shapeable"), str):
        out["shapeable"] = out["shapeable"].strip().lower() in ("yes", "true", "1")
    if out.get("components"):
        out["components"] = [str(c).strip().upper() for c in out["components"]]
    if out.get("descriptors"):
        out["descriptors"] = [str(x).strip().lower() for x in out["descriptors"]]

    grants, _ = parse_level_available(out.get("level_available"))
    if not grants:
        grants = level_available_for(out)
    else:
        # An authored class grant is a fact about the spell's class lists. Written back into
        # `lists` because that is the field `rules/casting.py` reads, and a spell whose
        # editor said "wizard 3" and whose `lists` stayed empty is one nobody can cast — the
        # exact silent failure a homebrew ingredient hit before the registry existed.
        lists = dict(out.get("lists") or {})
        for g in grants:
            if g.get("via", "class") == "class":
                lists[str(g["name"]).lower()] = int(g["level"])
        out["lists"] = lists
        # The columns the corpus already carries are grants too, and an author adding one
        # line should not delete fireball's Fire domain.
        known = {(g.get("via"), g.get("name")) for g in grants}
        grants = grants + [g for g in level_available_for(out)
                           if (g.get("via"), g.get("name")) not in known]
    out["level_available"] = grants
    out["spellbooks"] = out.get("spellbooks") or spellbooks_for(out.get("lists") or {})

    if not out.get("scaling"):
        out.pop("scaling", None)
    else:
        parsed, _ = parse_scaling(out["scaling"])
        out["scaling"] = parsed

    if not out.get("element"):
        element = next((DESCRIPTOR_ELEMENT[x] for x in (out.get("descriptors") or ())
                        if x in DESCRIPTOR_ELEMENT), "")
        # A converted formula names its own damage type, which is the only place negative
        # and positive energy can come from — 1e has no [negative] descriptor.
        if not element:
            claimed = (out.get("scaling") or {}).get("damage_type", "")
            element = claimed if claimed in ELEMENTS else ""
        out["element"] = element

    if not out.get("range_value"):
        out["range_value"] = parse_range(out.get("range", ""))
    if not out.get("area_value"):
        # `effect` carries the shape for spells that create one rather than covering an
        # area — "20-ft.-radius spread" appears in both columns across the corpus.
        out["area_value"] = parse_area(out.get("area", "")) or parse_area(
            out.get("effect", ""))
    if not out.get("save") and not out.get("save_effect"):
        save, effect, harmless = parse_save(out.get("saving_throw", ""))
        out["save"], out["save_effect"], out["save_harmless"] = save, effect, harmless
    if out.get("sr") is None:
        out["sr"] = parse_sr(out.get("spell_resistance", ""))
    return out


_ALL: dict[str, Spell] | None = None
_META: dict = {}


def all_spells() -> dict[str, Spell]:
    """Every spell, shipped plus homebrew, layered the same way ingredients are."""
    global _ALL, _META
    if _ALL is None:
        from django.conf import settings

        raw: dict[str, dict] = {}
        for folder in (Path(settings.BASE_DIR) / "content" / "spells",
                       Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "spells"):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                entries = data.get("spells") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                for e in entries:
                    if e.get("id"):
                        # Merged, not replaced: an edit that changes one field must not
                        # drop the twenty it never asked about.
                        base = dict(raw.get(e["id"], {}))
                        base.update({k: v for k, v in e.items() if v not in (None, "")})
                        raw[e["id"]] = base
                if isinstance(data, dict) and data.get("descriptors"):
                    _META = {"descriptors": data["descriptors"],
                             "classes": data.get("classes", []),
                             "note": data.get("note", "")}
        # Normalised after the merge rather than per file, because the mechanics file and
        # the Codex file each hold half of what a derivation needs — an element read from
        # a scaling formula in one and from descriptors in the other.
        _ALL = {k: from_dict(normalise(v)) for k, v in raw.items()}
    return _ALL


def meta() -> dict:
    all_spells()
    return _META


def get(spell_id: str) -> Spell:
    s = all_spells().get((spell_id or "").strip().lower())
    if s is None:
        raise KeyError(f"no spell {spell_id!r}")
    return s


def known_classes() -> set[str]:
    """Every class a spell may name a level on.

    The Codex's own class columns plus anything a loaded spell actually sits on, so a
    homebrew class that has spells does not have its own spells rejected — and a typo still
    is. Derived rather than a second list of class names beside `rules/classes.py`.
    """
    found = set(meta().get("classes") or ())
    for s in all_spells().values():
        found.update(s.lists)
    return found


# --- validation, for a UI to call before it saves ---------------------------------------------

def validate_spell(d: dict) -> list[str]:
    """Everything wrong with one authored spell, named.

    A list rather than an exception, for the same reason `effectspec.validate` returns one:
    the builder shows a form all of its problems at once, and one-at-a-time is a form nobody
    finishes.
    """
    problems: list[str] = []
    if not str(d.get("name", "")).strip():
        problems.append("It needs a name.")

    school = str(d.get("school", "")).strip().lower()
    if school and school not in SCHOOLS:
        problems.append(f"{school!r} is not a school. One of: {', '.join(SCHOOLS)}.")

    element = str(d.get("element", "")).strip().lower()
    if element and element not in ELEMENTS:
        problems.append(f"{element!r} is not an element. One of: {', '.join(ELEMENTS)}.")

    grants, grant_problems = parse_level_available(d.get("level_available"))
    problems.extend(grant_problems)
    classes = known_classes()
    for g in grants:
        if g.get("via") == "class" and g["name"] not in classes:
            problems.append(
                f"level_available: there is no class called {g['name']!r}.")
    if not grants and not (d.get("lists") or {}):
        problems.append("Nothing can cast it: give it a class, domain or bloodline level.")

    for c in d.get("components") or ():
        if str(c).strip().upper() not in COMPONENTS:
            problems.append(
                f"{c!r} is not a component. One of: {', '.join(COMPONENTS)}.")

    known_descriptors = set(meta().get("descriptors") or ())
    for x in d.get("descriptors") or ():
        if known_descriptors and str(x).strip().lower() not in known_descriptors:
            problems.append(
                f"{x!r} is not a descriptor. A descriptor is a rules fact read from the "
                f"book, not a label — put it in the description instead.")

    scaling, scaling_problems = parse_scaling(d.get("scaling"))
    problems.extend(scaling_problems)
    if scaling and int(scaling.get("die", 0)) not in (2, 3, 4, 6, 8, 10, 12, 20, 100):
        problems.append(f"scaling: d{scaling.get('die')} is not a die.")

    for i, spec in enumerate(d.get("effects") or ()):
        problems.extend(effectspec.validate(spec, f"effect {i + 1}"))
    return problems


def derive(entry: dict) -> dict:
    """A spell with its structured half filled in, for the editor to show.

    Declared as the `spells` Kind's `derive` hook. Two things happen here that do not happen
    in `normalise`: the mapping-shaped fields are rendered back to the one-per-line text the
    form edits, and an entry with no effects is offered the conversion of its own prose so
    that opening a shipped spell shows what the parser made of it rather than a blank.

    An `effects` list already present is left alone. That is a person's answer, or a
    homebrew spell saying something the parse cannot, and either way it outranks a
    re-reading of the prose.
    """
    out = dict(entry)
    if not out.get("effects"):
        got, _ = convert(out)
        if got.get("effects"):
            out["effects"] = got["effects"]
            out["effects_converted"] = True
            out.setdefault("scaling", got.get("scaling") or {})
    out = normalise(out)
    out["level_available"] = format_level_available(out.get("level_available") or [])
    out["scaling"] = format_scaling(out.get("scaling") or {})
    out["components"] = [str(c).strip().upper() for c in (out.get("components") or ())]
    # The three text-shaped fields, rendered the way their inputs expect them. A list handed
    # to a text input renders as "['fire']" and saves that back, which is how a descriptor
    # list turns into one descriptor called "['fire']".
    out["descriptors"] = ", ".join(out.get("descriptors") or [])
    for flag in ("dismissible", "shapeable"):
        out[flag] = "yes" if out.get(flag) else "no"
    return out


def vocabularies() -> dict:
    """Everything a filter can be built from, counted so a zero option is visible."""
    spells = all_spells().values()
    def tally(get_values):
        out: dict[str, int] = {}
        for s in spells:
            for v in get_values(s):
                out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    return {
        "schools": tally(lambda s: [s.school] if s.school else []),
        "subschools": tally(lambda s: [s.subschool] if s.subschool else []),
        "descriptors": tally(lambda s: s.descriptors),
        "tags": tally(lambda s: s.tags),
        "classes": tally(lambda s: list(s.lists)),
        "sources": tally(lambda s: [s.source] if s.source else []),
        "elements": tally(lambda s: [s.element] if s.element else []),
        "grants": tally(lambda s: sorted({g["via"] for g in s.level_available})),
        "tag_notes": TAG_NOTES,
    }


def search(text: str = "", school: str = "", subschool: str = "",
           descriptor: str = "", tag: str = "", klass: str = "",
           level: int | None = None, element: str = "", executable: bool | None = None,
           limit: int = 200) -> list[Spell]:
    """Filter the list. Every argument narrows; none of them widens.

    `descriptor` and `tag` are separate arguments even though both read as labels, because
    they answer different questions: "is this spell stopped by fire immunity" and "is this
    spell the sort of thing I am looking for".

    `klass` matches any grant, not only a class list: a cleric with the Fire domain should
    find fireball on a search for what they can cast, and before `level_available` unified
    them there was no way to ask.
    """
    out = []
    needle = (text or "").strip().lower()
    wanted = (klass or "").strip().lower()
    for s in all_spells().values():
        if school and s.school != school:
            continue
        if subschool and s.subschool != subschool:
            continue
        if descriptor and descriptor not in s.descriptors:
            continue
        if element and s.element != element:
            continue
        if tag and tag not in s.tags:
            continue
        if executable is not None and bool(s.effects) is not executable:
            continue
        if wanted and wanted not in s.lists \
                and not any(g["name"] == wanted for g in s.level_available):
            continue
        if level is not None:
            if wanted:
                levels = [g["level"] for g in s.level_available if g["name"] == wanted]
                levels += [s.lists[wanted]] if wanted in s.lists else []
            else:
                levels = list(s.lists.values())
            if level not in levels:
                continue
        if needle and needle not in s.name.lower() \
                and needle not in s.description.lower():
            continue
        out.append(s)
    out.sort(key=lambda x: (x.min_level if x.min_level is not None else 99,
                            x.name.lower()))
    return out[:limit]


__all__ = [
    "CURATED", "COMPONENTS", "DESCRIPTOR_ELEMENT", "ELEMENTS", "GRANT_VIA", "SCHOOLS",
    "SPELLBOOKS", "TAG_NOTES", "Spell", "all_spells", "build_mechanics", "convert",
    "derive", "effects_at", "effects_from_scaling", "format_level_available",
    "format_scaling", "from_dict", "get", "known_classes", "level_available_for", "meta",
    "normalise", "parse_area", "parse_level_available", "parse_range", "parse_save",
    "parse_scaling", "parse_sr", "range_feet", "read_scaling", "scaling_dice", "search",
    "spellbooks_for", "validate_spell", "vocabularies", "write_mechanics",
]
