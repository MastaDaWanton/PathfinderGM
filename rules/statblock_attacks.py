"""A stat block's attack lines, read as attacks the engine can swing.

"greatclub +7 (2d8+7)" is the ogre's whole offence, and until 2026-09-27 nothing read it.
The line was stripped with the rest of `_NOT_ON_THE_SHEET`, the ogre arrived with no weapon,
and the engine swung its fists: 1d3 plus Strength, 6 to 8 a hit where the book says 9 to
23. Measured over 50 hits through `Engine.run` against the Kesst fixture: mean 7.1, every
one an "unarmed strike". A full attack gave an owlbear one swing where its line gives three.

This module is the reader. It turns a melee or ranged line into OPTIONS (the book's "or"),
each a list of ATTACKS (the book's commas), each attack carrying exactly what was printed:
its name, how many of it, the printed total bonus for every swing ("+11/+6"), the damage
dice and the printed flat bonus, the crit, and what rides the hit.

**The printed numbers are kept as printed, never re-derived.** This is how the tools that
import 1e stat blocks do it, and the reason is the same one `flat_attack` already states on
the sheet: a printed +7 already contains base attack, Strength, size, masterwork,
enhancement, Weapon Focus and — for a secondary natural attack — the -5, and a printed +7
damage already contains 1.5x Strength on a two-hander or half Strength on a secondary
attack. Re-deriving any of it from the ability scores is how a converter drifts from the
book. What the sheet adds on top is only what the printed block cannot know: conditions,
spells, the board. See `Actor.attack_modifiers`.

Riders the engine has no executor for yet ("plus grab", "plus poison", "plus trip") are
parsed and carried, not fired. A typed extra die ("plus 1d6 fire") is damage, and is rolled.

Nothing here is model output. The corpus is two imported files and the parse is pure: the
same line always reads the same way, so it is cached by the line itself.
"""
from __future__ import annotations

import re
from functools import lru_cache

# The PDF-parsed core blocks carry the book's typography: an en dash for a minus sign and
# for a crit range ("claw –3", "18–20"), a multiplication sign for a crit multiplier ("/×3").
# Measured over both files: 370 en dashes, 117 multiplication signs, one acute accent where
# a × was meant. An em dash appears only in prose that leaked into the field.
_TYPOGRAPHY = str.maketrans({"–": "-", "−": "-", "×": "x", "´": "x"})

# One attack: "[count] name +b[/+b...] [touch] (damage)". The damage parenthesis is
# optional because 1e prints some attacks without one — "2 wings +22" on a dragon whose
# wing damage the line never states — and those are refused below rather than guessed.
#
# The lookahead after the bonuses is what stops "Large +1 giant-bane greatsword +21/+16"
# reading as an attack called "Large" at +1: a bonus is only the bonus when the damage
# parenthesis (or the end of the entry) follows it.
_ATTACK = re.compile(
    r"^\s*(?:(?P<count>\d+)\s+)?(?P<name>.+?)\s+"
    r"(?P<bonuses>[+-]\s*\d+(?:\s*/\s*[+-]\s*\d+)*)"
    r"(?P<touch>\s+(?:ranged\s+|melee\s+)?touch)?"
    r"(?=\s*(?:\(|$))\s*(?:\((?P<damage>[^()]*)\))?", re.I)
# A swarm or a troop prints no bonus at all — "swarm (2d6 plus distraction)", "troop
# (4d6+12)" — because it makes no attack roll: its damage is automatic.
_AUTOMATIC = re.compile(r"^\s*(?P<name>swarm|troop)\s*\((?P<damage>[^()]*)\)", re.I)
_SIZE_WORD = re.compile(
    r"^(?:fine|diminutive|tiny|small|medium|large|huge|gargantuan|colossal)\s+", re.I)
# Names the weapons table knows by another word. "flail" is the Core Rulebook's light
# flail; an unarmed strike and a flurry of blows are the same fist.
_BASE_ALIASES = {"flail": "light-flail", "unarmed strike": "unarmed",
                 "flurry of blows": "unarmed", "unarmed strike flurry of blows": "unarmed",
                 "armor spikes": "spiked-armor", "armour spikes": "spiked-armor",
                 "shield bash": "heavy-shield", "heavy shield bash": "heavy-shield",
                 "light shield bash": "light-shield"}
_DICE = re.compile(r"^\s*(?P<dice>\d+d\d+|\d+)\s*(?P<bonus>[+-]\s*\d+)?", re.I)
_EXTRA = re.compile(r"^(?P<dice>\d+d\d+(?:\s*[+-]\s*\d+)?)\s+(?P<type>[a-z]+)", re.I)
_ENHANCEMENT = re.compile(r"^(?:[+-]\d+\s+|mwk\s+|masterwork\s+)+", re.I)

# What a natural attack does, by the Bestiary's universal monster rules (natural attacks
# table): bite B/P/S, claw B/S, gore P, hoof B, tentacle B, wing B, pincers B, tail slap B,
# slam B, sting P, talons S. The engine carries one type per blow, so the first letter the
# table gives is the one kept — except a bite, where the piercing a jaw does is the one a
# reader expects to hear about.
NATURAL = {
    "bite": "piercing", "claw": "slashing", "gore": "piercing", "hoof": "bludgeoning",
    "tentacle": "bludgeoning", "wing": "bludgeoning", "pincer": "bludgeoning",
    "tail slap": "bludgeoning", "slam": "bludgeoning", "sting": "piercing",
    "talon": "slashing", "rake": "slashing", "tail": "bludgeoning",
    "tongue": "bludgeoning", "head butt": "bludgeoning", "stamp": "bludgeoning",
    "horn": "piercing", "tusk": "piercing", "foreclaw": "slashing",
}
_PLURALS = {"hooves": "hoof", "teeth": "tooth", "knives": "knife", "claws": "claw",
            "wings": "wing", "tentacles": "tentacle", "talons": "talon",
            "pincers": "pincer", "hooves ": "hoof", "slams": "slam", "gores": "gore",
            "stings": "sting", "rakes": "rake", "horns": "horn", "tusks": "tusk"}
# Words a model uses for a creature's body that the line does not: "fangs" is the bite.
ALIASES = {"fangs": "bite", "teeth": "bite", "jaws": "bite", "talon": "claw",
           "talons": "claw", "horns": "gore", "horn": "gore", "tail": "tail slap",
           "fist": "slam", "fists": "slam"}

_RIDER_REPAIRS = {"gra b": "grab"}

DAMAGE_TYPES = ("acid", "cold", "electricity", "fire", "sonic", "negative", "positive",
                "force", "bludgeoning", "piercing", "slashing", "holy", "unholy")


def _clean(line: str) -> str:
    return " ".join(str(line or "").translate(_TYPOGRAPHY).split())


def _split_top(text: str, sep: str) -> list[str]:
    """Split on `sep` outside parentheses: "1d6+4 plus grab, bite" has a comma inside."""
    out, depth, buf, i = [], 0, [], 0
    while i < len(text):
        ch = text[i]
        depth += ch == "("
        depth -= ch == ")" and depth > 0
        if depth == 0 and text.startswith(sep, i):
            out.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [p.strip() for p in out if p.strip()]


def singular(name: str) -> str:
    low = name.lower()
    if low in _PLURALS:
        return _PLURALS[low]
    words = low.split()
    if words and words[-1] in _PLURALS:
        return " ".join(words[:-1] + [_PLURALS[words[-1]]])
    if len(low) > 3 and low.endswith("s") and not low.endswith(("ss", "us")):
        return low[:-1]
    return low


def base_weapon(name: str) -> str:
    """The weapons-table key a printed name stands on, or "".

    "+4 ghost touch unholy heavy flails" is a heavy flail; the enchantments and the
    material ride in front of the name, so the longest suffix the table knows is the
    weapon. Tried longest-first so "light crossbow" is not read as "crossbow".
    """
    plain = _ENHANCEMENT.sub("", _SIZE_WORD.sub("", name)).rstrip("*").strip().lower()
    # The name as printed first, then its singular: "aklys" and "flurry of blows" are
    # not plurals, and singularising them first found "akly" and "flurry of blow".
    for bare in dict.fromkeys((plain, singular(plain))):
        found = _base_of(bare)
        if found:
            return found
    return ""


def _base_of(bare: str) -> str:
    from . import weapons as weapons_mod

    if bare in _BASE_ALIASES:
        return _BASE_ALIASES[bare]
    words = bare.replace("-", " ").split()
    for i in range(len(words)):
        tail = words[i:]
        # "khopeshUE", "bardicheUE": a footnote marker the PDF glued to the name.
        tails = [tail] + ([tail[:-1] + [tail[-1][:-2]]]
                          if tail[-1].endswith("ue") and len(tail[-1]) > 4 else [])
        for t in tails:
            # "short bow" is the table's "shortbow": the joined spelling too.
            for key in ("-".join(t), " ".join(t), "".join(t)):
                if key in _BASE_ALIASES:
                    return _BASE_ALIASES[key]
                if weapons_mod.has(key):
                    return key
    return ""


def natural_kind(name: str) -> str:
    """The natural-attack family a printed name belongs to ("tail slap", "claw"), or ""."""
    low = singular(_ENHANCEMENT.sub("", name))
    low = ALIASES.get(low, low)
    if low in NATURAL:
        return low
    last = low.split()[-1] if low.split() else ""
    return last if last in NATURAL else ""


def _damage(text: str) -> dict | None:
    """"2d8+7/19-20 plus grab and 1d6 fire" -> dice, bonus, crit, riders, extra dice."""
    text = _clean(text)
    head, *plus = re.split(r"\s+plus\s+", text, flags=re.I)
    m = _DICE.match(head)
    if not m:
        return None
    rest = head[m.end():]
    dice = m.group("dice")
    # "1d1" is printed on five blocks (a crawling hand, a shuriken) and the roller
    # refuses a one-faced die as implausible, which would have raised mid-fight. It is
    # a constant, so it is written as one.
    one = re.fullmatch(r"(\d+)d1", dice)
    if one:
        dice = one.group(1)
    out = {"dice": dice,
           "bonus": int((m.group("bonus") or "0").replace(" ", "")),
           "crit_range": None, "crit_mult": None, "nonlethal": False,
           "type": "", "extra": [], "riders": [], "ability": "", "drain": False}
    # The crit can sit after the riders ("1d6+3 plus grab/19-20"), so it is looked for in
    # the whole text, not only after the dice.
    for c in re.finditer(r"/\s*(?:(\d+)\s*-\s*20)?(?:\s*/?\s*x\s*(\d+))?", text, re.I):
        if c.group(1):
            out["crit_range"] = int(c.group(1))
        if c.group(2):
            out["crit_mult"] = int(c.group(2))
    # A multiplier printed without its "x" — "longbow +11/+6 (1d8/3)" — is one the
    # spreadsheet dropped; a lone "/3" or "/4" after the dice can only be that.
    bare = re.match(r"^\s*/\s*([234])\b(?!\s*-)", rest)
    if bare and out["crit_mult"] is None:
        out["crit_mult"] = int(bare.group(1))
    words = re.sub(r"/.*$", "", rest).strip().lower()
    if "nonlethal" in words:
        out["nonlethal"] = True
    # "incorporeal touch +4 (1d6 Strength damage)": the dice are a score's, not hit
    # points. Read as hit points, a shadow would club the player for 1d6 bludgeoning.
    # 35 printed attacks say an ability; "str and 1d4 con" keeps the first.
    score = re.match(r"^(str|dex|con|int|wis|cha)[a-z]*\b(?:\s+(damage|drain))?", words)
    if score:
        out["ability"] = score.group(1)
        out["drain"] = score.group(2) == "drain"
    for t in () if score else DAMAGE_TYPES:
        if re.search(rf"\b{t}\b", words):
            out["type"] = t
            break
    # "(1d8+2 x3)": five blocks print the multiplier with no slash in front of it.
    loose = re.search(r"(?:^|\s)x\s*([234])\b", words)
    if loose and out["crit_mult"] is None:
        out["crit_mult"] = int(loose.group(1))
    for part in plus:
        for piece in re.split(r"\s*(?:,|\band\b)\s*", re.sub(r"/.*$", "", part)):
            piece = piece.strip()
            if not piece:
                continue
            e = _EXTRA.match(piece)
            if e and e.group("type").lower() in DAMAGE_TYPES:
                out["extra"].append({"dice": e.group("dice").replace(" ", ""),
                                     "type": e.group("type").lower()})
            elif not re.match(r"^\d", piece):
                # "gra b": the PDF broke the word across a column, sixteen times.
                out["riders"].append(_RIDER_REPAIRS.get(piece.lower(), piece.lower()))
    return out


def _attack(text: str, category: str) -> dict | None:
    auto = _AUTOMATIC.match(_clean(text))
    if auto:
        dmg = _damage(auto.group("damage"))
        if dmg is None:
            return None
        return {"name": auto.group("name").lower(), "key": auto.group("name").lower(),
                "count": 1, "bonuses": [0], "touch": False, "automatic": True,
                "category": category, "base": "", "natural": False, "kind": "", **dmg}
    m = _ATTACK.match(_clean(text))
    if not m or not m.group("damage"):
        return None
    name = _SIZE_WORD.sub("", m.group("name").strip()).rstrip("*").strip()
    # A leading enhancement that is not the count: "2 +1 short swords" is two of them.
    if re.search(r"[()]", name) or len(name) > 48:
        return None
    dmg = _damage(m.group("damage"))
    if dmg is None:
        return None
    bonuses = [int(b.replace(" ", "")) for b in m.group("bonuses").split("/")]
    bare = _ENHANCEMENT.sub("", name).strip().lower()
    if not bare:
        return None
    base = base_weapon(name)
    kind = "" if base else natural_kind(name)
    return {
        "name": name, "key": bare, "count": int(m.group("count") or 1),
        # "tongue +7 touch" says it after the bonus; "incorporeal touch +4" says it in the
        # name, and resolves against touch AC just the same.
        "bonuses": bonuses, "automatic": False,
        "touch": bool(m.group("touch") or re.search(r"\btouch(?:es)?\b", name, re.I)),
        "category": category, "base": base, "natural": bool(kind), "kind": kind,
        **dmg,
    }


@lru_cache(maxsize=4096)
def _parse_cached(line: str, category: str, _table: int) -> tuple:
    # `_table` is the identity of the weapons table the `base` of each attack was looked
    # up in. It carries homebrew, so a parse made against one campaign's table must not
    # answer for another's; the identity changes exactly when that cache is rebuilt.
    options = []
    for opt in _split_top(_clean(line), " or "):
        attacks = []
        for piece in _split_top(opt, ","):
            a = _attack(piece, category)
            if a is not None:
                attacks.append(a)
        if attacks:
            options.append(tuple(attacks))
    return tuple(options)


def parse(line: str, category: str = "melee") -> list[list[dict]]:
    """A melee or ranged line as options of attacks. Copies, so a caller cannot edit
    the cache."""
    from . import weapons as weapons_mod

    table = id(weapons_mod.all_weapons())
    return [[dict(a) for a in opt]
            for opt in _parse_cached(str(line or ""), category, table)]


def swings(attack: dict) -> list[int]:
    """Which printed bonus each swing of one attack entry uses, in order.

    "2 claws +8" is two swings at +8. "unarmed strike +21/+21/+17/+17/+11" is five, one
    per printed bonus. "2 +1 short swords +19/+17/+12/+12/+9" is also five: when a count
    comes with as many bonuses or more, the bonuses already list every blow (two-weapon
    fighting, printed out), and multiplying by the count would swing ten.
    """
    n = len(attack["bonuses"])
    count = max(1, int(attack.get("count", 1) or 1))
    if n > 1 and n >= count:
        return list(range(n))
    return [i for _ in range(count) for i in range(n)]


# Keyed on the identity of the bestiary's own cache, the arrangement `rules/npcs.py` uses:
# it rebuilds exactly when the bestiary does (a homebrew creature saved, a test moving
# CAMPAIGN_DIR) without an entry in conftest's list.
_NAMES_BUILT: tuple = ()


def printed_names() -> frozenset[str]:
    """Every attack name any stat block prints, for the one gate that cannot see an actor.

    `intents._known_weapon` runs at parse, before anybody is looked up, and knew only the
    weapons table and the races' natural attacks — so "tendrils", "corrupting touch" and
    "tail slap" were refused as no such weapon before the engine could ask the creature
    whether it has them. Let through here and decided by the engine's legality check,
    which does see the actor — the arrangement the natural attacks already have.
    Measured 2026-09-27: 1,403 names, 0.9 s to read the corpus, paid once and only when a
    name misses both tables.
    """
    global _NAMES_BUILT
    from . import bestiary

    store = bestiary.imported()
    if _NAMES_BUILT and _NAMES_BUILT[0] is store:
        return _NAMES_BUILT[1]
    out: set[str] = set()
    for doc in store.values():
        for options in of_block(doc).values():
            for option in options:
                for a in option:
                    out.add(a["key"])
                    out.add(singular(a["key"]))
    _NAMES_BUILT = (store, frozenset(out))
    return _NAMES_BUILT[1]


def of_block(doc: dict) -> dict[str, list[list[dict]]]:
    """Both lines of a stat block, keyed by category."""
    doc = doc or {}
    return {"melee": parse(doc.get("melee") or "", "melee"),
            "ranged": parse(doc.get("ranged") or "", "ranged")}
