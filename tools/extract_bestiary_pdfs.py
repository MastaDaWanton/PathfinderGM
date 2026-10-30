"""Pull core bestiary stat blocks out of the Bestiary PDFs.

The spreadsheet import gave 6,406 creatures and no plain Ogre: it is a variant and NPC
bestiary, and its Environment column is empty. The core creatures and their ecology are in
the PDFs, and `reference/` already knows where — it indexed 816 creature anchors, each a
name, a page and a CR. That is the hard half of the problem already solved, so this walks
the anchors, reads the page, and parses the stat block.

Pathfinder stat blocks are rigidly formatted, which is why this is parsing rather than
guessing: `AC 17, touch 11, flat-footed 16`, `hp 30 (4d10+8)`, `Fort +6, Ref +2, Will +1`,
`Str 21, Dex 8, Con 15`. Every field is anchored on a keyword the layout guarantees.

The typography repair from `reference/build_reference.py` is reused rather than rewritten —
these PDFs render "flat" as "f lat" and "situation" as "s itu ation", and that was solved
once already.

Run:  python tools/extract_bestiary_pdfs.py H:/Pathfinder content/bestiary/core.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from pypdf import PdfReader  # noqa: E402

import build_reference as ref  # noqa: E402

sys.path.insert(0, str(ROOT))

from rules.statblock import RESISTANCE, trim  # noqa: E402

SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge",
         "gargantuan", "colossal")
ALIGNMENTS = ("LG", "NG", "CG", "LN", "N", "CN", "LE", "NE", "CE")


# The classes a Bestiary block's class line can name: the core and base classes and the NPC
# classes. Whole words, so "Goblin warrior 1" is warrior 1 and "Huge 3" is nothing.
_CLASS_WORDS = {"adept", "aristocrat", "commoner", "expert", "warrior", "barbarian", "bard",
                "cleric", "druid", "fighter", "monk", "paladin", "ranger", "rogue", "sorcerer",
                "wizard", "alchemist", "cavalier", "inquisitor", "oracle", "summoner", "witch",
                "magus", "gunslinger", "antipaladin", "ninja", "samurai", "arcanist",
                "bloodrager", "brawler", "hunter", "investigator", "shaman", "skald", "slayer",
                "swashbuckler", "warpriest", "kineticist", "medium", "mesmerist", "occultist",
                "psychic", "spiritualist", "vigilante"}


# The thirteen creature types (Bestiary 1, Appendix 2), the word after the size on the
# alignment line. Read as one free word until 2026-10-29, which cut both two-word types in
# half: 246 of 1,417 blocks were "magical" or "monstrous", and 4 kerned "construc t" read
# "construc" — so no rule asking for a magical beast or a monstrous humanoid found one.
# Each letter may be followed by one stray space (the PDFs' kerning, as `join_kerned`).
_TYPES = ("aberration", "animal", "construct", "dragon", "fey", "humanoid", "magical beast",
          "monstrous humanoid", "ooze", "outsider", "plant", "undead", "vermin")
def _kerned(type_name: str) -> str:
    return r"\s+".join(r" ?".join(word) for word in type_name.split())


_TYPE_ALT = "|".join(_kerned(t) for t in _TYPES)


def _type_of(text: str) -> str:
    """The type as the book names it, the kerning's stray spaces gone."""
    return next(t for t in _TYPES if re.fullmatch(_kerned(t), text.strip(), re.I))


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "creature"


def cr_value(text: str) -> float | None:
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", text or "")
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r"\s*(\d+)", text or "")
    return float(m.group(1)) if m else None


def _num(m, group=1) -> int | None:
    return int(m.group(group)) if m else None


def _between(text: str, start: str, *stops: str) -> str:
    """The run of text after a keyword and before the next one.

    Stat block lines have no punctuation to close them — the next keyword is the
    terminator — so every field is bounded by the labels that can follow it.
    """
    stop = "|".join(stops) if stops else r"$"
    m = re.search(rf"\b{start}\b\s+(.+?)(?=\s*(?:{stop})|$)", text, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip(" ;,.") if m else ""


_RACIAL = r"R\s?acial\s+M\s?odifiers?"


def _xp(t: str) -> int | None:
    m = re.search(r"\bXP\s+(\d[\d,]*)", t)
    return int(m.group(1).replace(",", "")) if m else None


def _top_level(text: str) -> list[str]:
    """Split on the commas and semicolons outside parentheses: "Knowledge (arcana, planes)
    +25, Perception +25" is two parts, not three."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch in ",;" and depth <= 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return [p for p in parts if p]


def _skills(text: str) -> dict[str, int]:
    """The Skills line as {name: total}, in the sheet's spelling (lower case, the sub-skill
    in parentheses). "Knowledge (arcana, planes) +25" is both knowledge skills at +25 —
    the spreadsheet split it on the comma and filed a skill called "planes)". A situational
    total in parentheses ("Acrobatics +5 (+9 when jumping)") is left out, as the printed
    AC's conditional parts are."""
    out: dict[str, int] = {}
    for part in _top_level(text):
        m = re.match(r"([A-Za-z][A-Za-z' \-]*?)\s*(?:\(([^)]*)\))?\s*([+-]\s?\d+)", part)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip().lower()
        value = int(m.group(3).replace(" ", ""))
        # "(arcana, dungeoneering, and religion)", "(arcana and nature)": each one.
        subs = [s.strip().lower() for s in re.split(r",|\band\b", m.group(2) or "")
                if s.strip()]
        if subs:
            for s in subs:
                out[f"{name} ({s})"] = value
        else:
            out[name] = value
    return out


def _feats(text: str) -> list[str]:
    """The Feats line as names, the bonus-feat and mythic marks off ("Power AttackB",
    "Toughness M")."""
    out = []
    for part in _top_level(text):
        name = re.sub(r"\s+", " ", part).strip(" .")
        name = re.sub(r"(?:(?<=[a-z)])|\s+)[BM]$", "", name).strip()
        if name and len(name) <= 60:
            out.append(name)
    return out


def _special_abilities(t: str, name: str = "") -> str:
    """The SPECIAL ABILITIES section: "Poison (Ex) Sting—injury; save Fort DC 17; ...".
    Unread until 2026-10-29, so the harvest's poison, burn and heat rounds (rules/
    harvest.py reads "Name (Ex)" paragraphs) had nothing to read on a Bestiary block —
    after option D they ran on 6 shipped creatures. The description's prose follows the
    last entry with no heading, so the section ends at the first full stop past the last
    "(Ex)", "(Su)" or "(Sp)" entry's first 600 characters: an entry's tail can be cut, an
    ecology's prose is never read as an ability."""
    m = re.search(r"\bS\s?P\s?E\s?C\s?I\s?A\s?L\s+A\s?B\s?I\s?L\s?I\s?T\s?I\s?E\s?S\b", t, re.I)
    if not m:
        return ""
    body = t[m.end():].strip()
    marks = list(re.finditer(r"\((?:Ex|Su|Sp)\)", body))
    if not marks:
        return ""
    limit = min(len(body), marks[-1].end() + 600)
    # The description opens on the creature itself: "Giant scorpions are monstrous
    # versions...". A sentence past the last entry that names it in its first words ends
    # the section; failing that, the last full stop inside the window.
    head = (name.split()[-1].lower() if name else "")
    end = None
    if head:
        for s in re.finditer(r"\.\s+(?=[A-Z])", body[marks[-1].end():limit]):
            start = marks[-1].end() + s.end()
            if re.search(rf"\b{re.escape(head)}(?:e?s)?\b", body[start:start + 60], re.I):
                end = marks[-1].end() + s.start() + 1
                break
    if end is None:
        stop = body.rfind(". ", marks[-1].end(), limit)
        end = stop + 1 if stop != -1 else limit
    return re.sub(r"\s+", " ", body[:end]).strip()[:4000]


_GEAR_STOPS = ("ECOLOGY", "SPECIAL ABILITIES", "Environment", "Organization", "DESCRIPTION")


def _gear(t: str) -> dict:
    """The Bestiaries print a people's possessions in the Treasure line — "Treasure NPC
    gear (leather armor, short sword, short bow with 20 arrows, other treasure)" — and a
    statted caster's in STATISTICS ("Combat Gear ...; Other Gear ..."). The first cut read
    the word "gear" wherever it fell and took the description's prose after it."""
    combat = _between(t, "Combat Gear", "Other Gear", *_GEAR_STOPS)[:400]
    other = _between(t, "Other Gear", *_GEAR_STOPS)[:400]
    if not (combat or other):
        # "NPC gear (...)", and a monster's "standard (hide armor, greatclub, other
        # treasure)" or "double (...)" — the ogre's club is in its Treasure line too.
        m = re.search(r"\bTreasure\s+(?:[A-Za-z]+\s+){0,2}\(((?:[^()]|\([^()]*\))*)\)", t,
                      re.I)
        if m:
            other = m.group(1)
        else:
            # A "Gear" entry is capitalised and sits in STATISTICS, before ECOLOGY; the
            # word anywhere else is prose ("or armor the yai carries", "the gear it used
            # in life"), which the case-blind first cut read for 13 blocks.
            eco = re.search(r"\bECOLOGY\b", t, re.I)
            g = re.search(r"\bGear\s+(.+?)(?=\s*(?:\bECOLOGY\b|\bSPECIAL ABILITIES\b|"
                          r"\bEnvironment\b|\bOrganization\b)|$)", t[:eco.start()] if eco
                          else t)
            other = g.group(1)[:400] if g else ""
    # Page furniture the PDF text runs into a list's end ("400 gp 115115 757046").
    other = re.sub(r"(?:\s+\d{5,})+.*$", "", other)
    # "darts [10]", "drow poison [2 doses]": the book's brackets inside a parenthesis are
    # a count, written as every other count is; "other treasure" is not a thing carried.
    other = re.sub(r"\[(\d+)[^\]]*\]", r"(\1)", other)
    parts = [p.strip() for p in other.split(",")]
    other = ", ".join(p for p in parts if p and p.lower() != "other treasure")
    return {"printed_gear": combat, "printed_other_gear": other}


def _spell_like(t: str) -> str:
    """The Spell-Like Abilities entry, its heading kept as the spreadsheet keeps it."""
    m = re.search(r"\bSpell-Like Abilities\b.+?(?=\s*(?:\bSpells Known\b|\bSpells Prepared\b|"
                  r"\bTACTICS\b|\bSTATISTICS\b|\bStr\s+\d)|$)", t, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(0)).strip()[:600] if m else ""


def parse_block(text: str, name: str, cr: str) -> dict | None:
    """One stat block, or None if the page did not actually hold one."""
    t = re.sub(r"\s+", " ", text)

    # The comma after the AC is sometimes missing ("AC 17 touch 10", Bestiary 5's swamp
    # mummy), and a block printed for a group gives "hp 127 each (15d8+60)" (the adlets).
    ac = re.search(r"\bAC\s+(\d+)\s*,?\s*touch\s+(\d+)\s*,?\s*flat-?\s?footed\s+(\d+)", t, re.I)
    # And what the AC is made of, "(+2 Dex, +2 natural)": kept since 2026-10-28, because a
    # template that replaces natural armour (the zombie's, the skeleton's) has to know which
    # part of the printed total was natural and which was a chain shirt.
    parts = re.match(r"\s*\(([^()]{2,120})\)", t[ac.end():]) if ac else None
    # The class line under the XP, "Goblin warrior 1" or "Human cleric 3/rogue 2": which of
    # the Hit Dice are class levels. A humanoid's may be racial (the ogre's 4d8, the
    # troll's 6d8) or a class's (the goblin's 1d10 is warrior 1), and the zombie and
    # skeleton keep racial dice and drop class ones (Bestiary 1 pp. 250, 288).
    classes = {}
    desc = re.search(r"\bXP\s+[\d,]+\s+(?:each\s+)?(.{0,80}?)\s+(?:LG|NG|CG|LN|N|CN|LE|NE|CE)"
                     r"\s+(?:Fine|Diminutive|Tiny|Small|Medium|Large|Huge|Gargantuan|Colossal)\b",
                     t)
    if desc:
        for cls, lvl in re.findall(r"\b([a-z]+(?: [a-z]+)?)\s+(\d{1,2})\b", desc.group(1).lower()):
            word = cls.split()[-1]
            if word in _CLASS_WORDS:
                classes[word] = classes.get(word, 0) + int(lvl)
    hp = re.search(r"\bhp\s+(\d+)\s*(?:each\s*)?\(([^)]{2,40})\)", t, re.I)
    saves = re.search(r"\bFort\s*([+-]\s?\d+)\s*,\s*Ref\s*([+-]\s?\d+)\s*,\s*Will\s*([+-]\s?\d+)",
                      t, re.I)
    # Without an AC and hit points there is no creature here — the anchor pointed at a
    # page of prose, or the extraction failed. Reported, never invented.
    if not (ac and hp):
        return None

    abil = {}
    # Commas optional: the wood golem prints "Con 25 Int —".
    m = re.search(r"\bStr\s+(\d+|—|-)\s*,?\s*Dex\s+(\d+|—|-)\s*,?\s*Con\s+(\d+|—|-)\s*,?\s*"
                  r"Int\s+(\d+|—|-)\s*,?\s*Wis\s+(\d+|—|-)\s*,?\s*Cha\s+(\d+|—|-)", t, re.I)
    if m:
        for key, raw in zip(("str", "dex", "con", "int", "wis", "cha"), m.groups()):
            if raw.isdigit():
                abil[key] = int(raw)
    else:
        # No ability line in the block: a sidebar cut it before its STATISTICS (Bestiary
        # 3's great horned owl, interrupted by the giant owl's page). Unparsed, like a
        # block with no AC — never a creature with no scores for the engine to roll.
        return None

    # "Any alignment (same as creator) Tiny construct" (the homunculus) and "N (but see
    # below)" (the soulbound doll): a qualified alignment, which read as no header at all
    # and left three blocks Medium and of no type.
    head = re.search(rf"({'|'.join(ALIGNMENTS)}|Any alignment|Any)(?:\s*\([^)]*\))?\s+"
                     rf"({'|'.join(SIZES)})\s+({_TYPE_ALT})(?:\s*\(([^)]+)\))?", t, re.I)
    init = re.search(r"\bInit\s*([+-]\s?\d+)", t, re.I)
    cmd = re.search(r"\bCMD\s+(\d+)", t, re.I)
    cmb = re.search(r"\bCMB\s*([+-]\s?\d+)", t, re.I)
    bab = re.search(r"\bBase Atk\s*([+-]\s?\d+)", t, re.I)
    speed = re.search(r"\bSpeed\s+(\d+)\s*ft", t, re.I)
    sr = re.search(r"\bSR\s+(\d+)", t, re.I)

    melee = _between(t, "Melee", "Ranged", "Special Attacks", "STATISTICS", "Space",
                     "Reach", "TACTICS")
    atk = re.search(r"([+-]\d+)", melee)
    dmg = re.search(r"\((\d+d\d+(?:[+-]\d+)?)", melee)

    dr = []
    # The bypass is the words a DR can name, joined by "and"/"or" — not everything up to
    # the next comma: a dragon's age table ran on into the ancient red dragon's DR ("magic
    # 3rd Old Freezing fog 5th Very old DR 15/magic ...", found 2026-10-29).
    # And only the block's own, in its DEFENSE section: a dragon's page prints every age
    # category's DR in its table, and all five went on each age's block — the ancient
    # black dragon carried the great wyrm's DR 20/magic beside its own 15/magic. Kerning
    # ("m agic", Bestiary 3's forest dragon) is read as the word.
    words = ("alchemical silver", "cold iron", "nonmagical weapons", "magic", "epic", "good", "evil", "lawful",
             "chaotic", "silver", "adamantine", "mithral", "bludgeoning", "piercing",
             "slashing", "wood", "bone", "glass", "vorpal", "aligned")
    word = "(?:" + "|".join(_kerned(w) for w in words) + r"|—|-|–|�)"
    # Every DEFENSE section to its OFFENSE: a lycanthrope prints two blocks (the
    # werewolf's DR 10/silver is its hybrid form's, after the first OFFENSE). Prose DR —
    # a lycanthrope template's, the bandersnatch's offspring's, a cave fisher's filament —
    # is in no DEFENSE section, and 1e gives it to no one this block describes.
    heads = [m.end() for m in re.finditer(r"\bD\s?E\s?F\s?E\s?N\s?S\s?E\b", t, re.I)]
    offenses = [m.start() for m in re.finditer(r"\bO\s?F\s?F\s?E\s?N\s?S\s?E\b", t, re.I)]
    if heads:
        defence = " ".join(t[h:next((o for o in offenses if o > h), len(t))] for h in heads)
    else:
        defence = t[:offenses[0]] if offenses else t
    # And the line after the saves, where a DR is printed: a page that sets two blocks
    # side by side loses one block's DEFENSE heading to the other column (Bestiary 1's
    # medium fire elemental, "Will +6 DR 5/—").
    defence += " " + " ".join(t[m.end():m.end() + 200]
                              for m in re.finditer(r"\bWill\s*[+-]\s?\d+", t))
    for m2 in re.finditer(rf"\bDR\s+(\d+)\s*/\s*({word}(?:\s*(?:,|and|or)\s*{word})*)",
                          defence, re.I):
        bypass = m2.group(2).strip()
        for w in words:
            bypass = re.sub(_kerned(w), w, bypass, flags=re.I)
        row = {"amount": int(m2.group(1)),
               "bypass": "" if bypass in ("—", "-", "–", "�") else bypass,
               "source": "natural"}
        if row not in dr:                   # the two anchors overlap: one DR, read twice
            dr.append(row)

    def sign(m2):
        return int(m2.group(1).replace(" ", "")) if m2 else None

    return {
        "id": slug(name),
        "name": name,
        "kind": "npc",
        "cr": cr,
        "cr_value": cr_value(cr),
        "size": (head.group(2).lower() if head else "medium"),
        "creature_type": (_type_of(head.group(3)) if head else ""),
        "subtype": (head.group(4).lower() if head and head.group(4) else ""),
        "alignment": ((head.group(1).upper() if len(head.group(1)) <= 2 else "Any") if head else ""),
        "abilities": abil,
        "hp": int(hp.group(1)),
        "hit_dice": hp.group(2).strip(),
        "flat_ac": int(ac.group(1)),
        "class_levels": classes,
        "ac_note": f"touch {ac.group(2)}, flat-footed {ac.group(3)}"
                   + (f" ({re.sub(r'[–—]', '-', parts.group(1)).strip()})" if parts else ""),
        "flat_saves": {"fort": sign(re.match(r"([+-]\s?\d+)", saves.group(1))) if saves else None,
                       "ref": sign(re.match(r"([+-]\s?\d+)", saves.group(2))) if saves else None,
                       "will": sign(re.match(r"([+-]\s?\d+)", saves.group(3))) if saves else None}
        if saves else {},
        "flat_initiative": sign(init),
        "flat_attack": int(atk.group(1)) if atk else None,
        "flat_damage": dmg.group(1) if dmg else "",
        "melee": melee[:200],
        "ranged": _between(t, "Ranged", "Special Attacks", "STATISTICS", "Space",
                           "Reach", "TACTICS")[:200],
        "flat_cmd": _num(cmd),
        "cmb": sign(cmb),
        "base_attack": sign(bab),
        "speed": _num(speed),
        # Five fields the Bestiaries never gave until 2026-10-29. For the 112 creatures the
        # spreadsheet also carried, its row filled them in the merged store; option D
        # removed those rows, and the measurement before it found 104 of them would lose
        # their fly, climb and swim speeds, 91 their skills and 86 their feats — and the
        # other 1,300 had never had any.
        "xp": _xp(t),
        "speed_note": _between(t, "Speed", "Melee", "Ranged", "Space", "Special Attacks",
                               "Spell-Like Abilities", "Spells Known", "Spells Prepared",
                               "STATISTICS", "TACTICS", "Reach")[:160],
        # Stops kerning-tolerant ("r acial m odifiers", Bestiary 2), and Feats among them:
        # a dragon's page prints a second, abridged set ("feats Hover, Imp. Critical")
        # that ran on into the first one's skills.
        "flat_skills": _skills(_between(t, "Skills", _RACIAL, "Languages?", "SQ", "Feats",
                                        "ECOLOGY", "Combat Gear", "Gear", "SPECIAL")),
        "feats": _feats(_between(t, "Feats", "Skills", _RACIAL, "Languages?", "SQ",
                                 "ECOLOGY")),
        "spell_like": _spell_like(t),
        "special_abilities": _special_abilities(t, name),
        # What the block says it carries ("Gear leather armor, longsword, longbow with 20
        # arrows"; a caster's "Combat Gear ... Other Gear ..."), as printed: the compile's
        # `carries` (rules/compile_block.py). Unread before 2026-10-29, so every Bestiary
        # creature's possessions were guessed from its attack line.
        **_gear(t),
        "reductions": dr,
        # `trim` on all three, because these are the only fields that split on commas and
        # so the only ones a runaway `_between` turns into a list of plausible short terms
        # rather than one visibly wrong long one. Every other field below is capped by a
        # slice for the same reason. See rules/statblock.py.
        # The next field, in the shapes the re-read welded on (2026-10-28): "Weakness" in
        # the singular ("sleep Weakness vulnerability to cold"), a bare "vulnerability"
        # ("fire; vulnerability cold"), and SR kerned apart ("mind-affecting effects; s r 13").
        "immune": trim([x.strip() for x in _between(t, "Immune", "Resist", "SR",
                                                    "Weaknesses", "Weakness", "vulnerability",
                                                    r"S\s+R\s+\d", "OFFENSE").split(",")
                        if x.strip()]),
        "resist": trim([x.strip() for x in _between(t, "Resist", "SR", "Weaknesses",
                                                    "Weakness", r"S\s+R\s+\d",
                                                    "OFFENSE").split(",") if x.strip()],
                       shape=RESISTANCE),
        "sr": _num(sr),
        # Read, not just used as a terminator. `Weaknesses` was one of the stop keywords
        # above from the first version and never a field of its own, so no printed stat
        # block carried a weakness at all: a frost giant's `vulnerability to fire` reached
        # the file only for the creatures the spreadsheet also had. 236 vulnerabilities
        # come from the spreadsheet and none from the six Bestiaries.
        "weaknesses": _between(t, "Weaknesses", "OFFENSE", "STATISTICS")[:160],
        "senses": _between(t, "Senses", "DEFENSE", "Aura")[:160],
        "special_attacks": _between(t, "Special Attacks", "STATISTICS", "TACTICS")[:300],
        "languages": trim([x.strip() for x in
                           _between(t, "Languages", "SQ", "ECOLOGY", "SPECIAL").split(",")
                           if x.strip()]),
        # The gap the spreadsheet could not fill: this is what ties a creature to a biome.
        "environment": _between(t, "Environment", "Organization", "Treasure")[:120],
        "organization": _between(t, "Organization", "Treasure", "SPECIAL")[:160],
        "treasure": _between(t, "Treasure", "SPECIAL ABILITIES", "DESCRIPTION")[:120],
        "playable": True,
    }


BOOKS = {
    "bestiary-1": "Pathfinder Bestiary 1.pdf",
    "bestiary-2": "Pathfinder Bestiary 2.pdf",
    "bestiary-3": "pathfinder - bestiary 3.pdf",
    "bestiary-4": "Pathfinder Bestiary 4.pdf",
    "bestiary-5": "pathfinder - bestiary 5.pdf",
    "bestiary-6": "pathfinder - bestiary 6.pdf",
}


# --- every block, found by its header --------------------------------------------------------
#
# The anchor walk above read ONE block per index anchor, from a page that can print two, and
# took the first AC on the page: measured 2026-10-28, `wolf-dire` shipped the plain wolf's
# block (CR 1, 13 hp, Medium; the printed dire wolf is CR 3, Large) and `ant-giant` an army
# ant swarm's (Fine, "swarm (3d6)"). The index had 224 anchors for Bestiary 1, 37 for
# Bestiary 2 and 41 for Bestiary 4, so `wolf`, `goblin`'s kin and most of two books never
# arrived at all. A printed block opens "NAME CR n XP n" on every page of every Bestiary —
# the shape every statblock importer splits on (the Roll20 and Foundry PF1 parsers) — so
# the book is cut at those headers and each piece is one block.

# The purchase watermark printed on every page: "paizo.com #1234567, Name <mail>, Oct 20,
# 2009". The buyer's own details; never written into content.
WATERMARK = re.compile(r"paizo\.com\s*#\s*\d+\s*,[^<\n]{0,80}<[^>\n]{0,120}>\s*,\s*"
                       r"[A-Z][a-z]{2,8}\.?\s+\d{1,2}\s*,\s*\d{4}")
# "CR" in any case — Bestiary 2 prints "Cr 1/2" and "cr 18" — and "XP" always in capitals.
# Bestiary 5's text layer splits a two-digit CR, "CR 1 1 XP 12,800": the digits may be
# spaced, and the XP beside them settles what they were (`_cr_of`).
#
# Mythic blocks print a rank after it, "CR 18/MR 7 XP 153,600", and their XP follows the
# mythic rules rather than the CR table, so it settles nothing. And a few headers lost
# their XP in the text layer ("DUPPY CR 7 CE Medium undead"): without the XP the CR must be
# followed by an alignment and a size, which prose ("Djinn nobles are CR 8.") never is.
HEADER = re.compile(
    r"\b[Cc][Rr]\s+(?P<cr>\d(?:\s?\d)?(?:\s*/\s*\d+)?)"
    r"(?:\s*/\s*MR\s+(?P<mr>\d(?:\s?\d)?))?"
    r"(?:\s+XP\s+(?P<xp>[\d,]+)\b"
    r"|(?=\s+(?:LG|NG|CG|LN|N|CN|LE|NE|CE|Any)\b[^.]{0,30}?\b(?:Fine|Diminutive|Tiny|Small"
    r"|Medium|Large|Huge|Gargantuan|Colossal)\b))")

# The award table (CRB Table 12-2 to CR 20, as `rules.xp.CR_AWARD`; the Bestiaries' own
# continuation above it), XP -> CR, to read a header's CR from the number least damaged.
_XP_CR = {50: "1/8", 65: "1/6", 100: "1/4", 135: "1/3", 200: "1/2", 400: "1", 600: "2",
          800: "3", 1200: "4", 1600: "5", 2400: "6", 3200: "7", 4800: "8", 6400: "9",
          9600: "10", 12800: "11", 19200: "12", 25600: "13", 38400: "14", 51200: "15",
          76800: "16", 102400: "17", 153600: "18", 204800: "19", 307200: "20",
          409600: "21", 614400: "22", 819200: "23", 1228800: "24", 1638400: "25",
          2457600: "26", 3276800: "27", 4915200: "28", 6553600: "29", 9830400: "30"}


def _cr_of(printed: str, xp: str | None, mythic: bool = False) -> str:
    """The CR the header means: the printed digits with the text layer's spaces taken out,
    unless the XP beside it says otherwise. A group's XP is not in the table, a mythic
    block's follows the mythic rules, and a header with no XP has nothing to say: the
    digits stand."""
    cr = re.sub(r"\s+", "", printed)
    if mythic or not xp:
        return cr
    by_xp = _XP_CR.get(int(xp.replace(",", "") or 0))
    return by_xp if by_xp and by_xp != cr else cr
_NOT_A_NAME = {"illustration", "illustrations", "by", "and", "the", "of", "or"}


def _caps_word(w: str) -> bool:
    """A word of a title set in small capitals, as the text layer returns it: the font
    comes back with some letters lower case — "WOLf", "jAnnI", "ghOST", "gIAnT" — so any
    capital after the first letter, or all capitals, marks it. Prose has at most one."""
    letters = [c for c in w if c.isalpha()]
    return len(letters) >= 1 and any(c.isupper() for c in letters[1:]) or (
        len(letters) >= 1 and all(c.isupper() for c in letters))


def _title_word(w: str) -> bool:
    """A word of a title set in plain title case (Bestiary 2: "Badger", "Nightcrawler")."""
    return bool(re.fullmatch(r"[A-Z][a-z'’-]+", w)) and w.lower() not in _NOT_A_NAME


_SMALL_WORDS = {"of", "the", "and", "in", "on", "a", "an"}


def _title(words: list[str]) -> str:
    """"HOUND OF TINDALOS" -> "Hound of Tindalos"."""
    return " ".join(w.lower() if i and w.lower() in _SMALL_WORDS
                    else w[:1].upper() + w[1:].lower() for i, w in enumerate(words))


def _name_before(before: list[str]) -> list[str]:
    """The block's title, read backwards from its CR: one run of words in one style —
    small capitals ("DIRE WOLf") or plain title case ("Badger") — stopped by punctuation,
    a number, or a change of style. "Wolf Wolf , Dire WOLf CR 1" is "WOLf": the running
    header before it is title case and the capitals run ends there.

    Two more shapes, measured on Bestiary 1 and 2 (31 headers the first rule named
    nothing): a second name in brackets after the title, "DIRE APE (gIgAnTOPIThECUS)",
    "WERERAT (hUMAn fORM)", dropped; and Bestiary 2's titles whose font came back lower
    case, "CraWLing hand", "shemhazian", "ram" — case cannot tell those from prose, but
    each follows the full stop of the description before it, so the words since that stop
    (five at most) are the title."""
    joined = re.sub(r"\(\s*[^()]{1,40}\)\s*$", "", " ".join(before)).strip()
    before = joined.split()
    words = _styled_run(before)
    tail: list[str] = []
    for raw in reversed(before):
        w = raw.strip("*")
        if re.search(r"[.!?)]$", raw) or re.search(r"\d", raw) or _running_header(w, tail):
            break
        tail.insert(0, w)
    tail = _once(tail)
    tail_ok = (1 <= len(tail) <= 5 and all(re.fullmatch(r"[A-Za-z'’-]+", w) for w in tail)
               and not any(w.lower() in _FURNITURE for w in tail))
    if not words:
        return tail if tail_ok else []
    # The words since the full stop win when they extend the styled run by a word or two:
    # "cavern. Mu SPORe" is the mu spore, whose "Mu" the font set in title case. More than
    # two is a running header or a credit ("Gelatinous Cube GELATInOUS CUbE", measured).
    extra = len(tail) - len(words)
    if tail_ok and 0 < extra <= 2 and [w.lower() for w in tail[-len(words):]] == [
            w.lower() for w in words]:
        return tail
    return words


# Page furniture that sits right before a title: credits, and the ecology block's labels.
_FURNITURE = {"illustration", "illustrations", "by", "treasure", "none", "organization",
              "environment", "incidental", "standard", "double", "triple",
              # an ordinal's tail ("16 th Young Astral Dragon") and a sentence's last word
              # ("and others ADULT INFERNAL DRAGON"), both measured in Bestiary 6 — not
              # "of", which cut the hound of Tindalos to "Tindalos"
              "th", "st", "nd", "rd", "others"}

# Words a family's printed sizes and ages differ by: "Small Earth Elemental" and "Elder
# Earth Elemental" are one family, and so are a dragon's ten ages.
_FAMILY_WORDS = re.compile(r"^(?:wyrmling|very young|young adult|young|juvenile|mature adult|"
                           r"adult|very old|old|ancient|great wyrm|wyrm|small|medium|large|"
                           r"huge|greater|elder|lesser)\s+", re.I)


def _family(name: str) -> str:
    s = name.lower()
    while True:
        t = _FAMILY_WORDS.sub("", s)
        if t == s:
            return s
        s = t


def _shared_ecology(creatures: list[dict], blocks: list[str]) -> int:
    """Give a block with no Environment line its family's: a dragon's ten ages share one
    ecology section, printed once (measured: 120 of 1,417 blocks had none). From a sibling
    that prints one, else from the ecology printed just before the family's first block,
    which the cut at headers leaves at the end of the block before it — a second
    Environment line there is the next family's. Returns how many were filled."""
    filled = 0
    by_family: dict[tuple[str, str], list[int]] = {}
    for i, c in enumerate(creatures):
        by_family.setdefault((c["source"], _family(c["name"])), []).append(i)
    for (source, _), members in by_family.items():
        env = next((creatures[i]["environment"] for i in members
                    if creatures[i].get("environment")), "")
        if not env and members[0] > 0:
            prev = blocks[members[0] - 1]
            lines = re.findall(r"\bEnvironment\s+(.+?)(?=\s*Organization|$)", prev, re.S)
            if len(lines) >= 2:
                env = re.sub(r"\s+", " ", lines[-1]).strip(" ;,.")[:120]
        if not env:
            # A variant printed under its base creature: the great horned owl under the
            # owl, the drow noble under the drow — the base's name inside its own.
            words = set(_words_key(creatures[members[0]]["name"]))
            base = [c for c in creatures if c["source"] == source and c.get("environment")
                    and set(_words_key(c["name"])) < words]
            env = max(base, key=lambda c: len(c["name"]))["environment"] if base else ""
        if not env:
            continue
        for i in members:
            if not creatures[i].get("environment"):
                creatures[i]["environment"] = env
                filled += 1
    return filled


def _once(words: list[str]) -> list[str]:
    """A phrase printed twice back to back is once: the running header repeats the title."""
    low = [w.lower() for w in words]
    for n in range(len(low) // 2, 0, -1):
        if low[-2 * n:-n] == low[-n:]:
            return words[-n:]
    return words


def _running_header(w: str, after: list[str]) -> bool:
    """Page furniture glued to a title by the text layer: a page-range header
    ("Triceratops–Dog"), a word printed twice into one ("FamiliarFamiliar"), or the title
    repeated in title case right before itself ("Will-o'-Wisp WILL-O'-WISP")."""
    low = w.lower()
    half = len(low) // 2
    # Doubled only when it is a title-case word twice ("Familiar" + "Familiar"): an all-caps
    # "JUBJUB" is a jubjub bird, and the first cut of this rule named it "Bird" (CR 15).
    doubled = (len(w) % 2 == 0 and half > 2 and w[:half] == w[half:]
               and any(c.islower() for c in w[:half]))
    return "–" in w or "—" in w or doubled or (bool(after) and low == after[0].lower())


def _styled_run(before: list[str]) -> list[str]:
    words: list[str] = []
    style = None
    for raw in reversed(before):
        w = raw.strip("*")
        if (not w or re.search(r"[\d.,;:!?()]", w) or w in ("CR", "XP")
                or _running_header(w, words)):
            break
        kind = "caps" if _caps_word(w) else "title" if _title_word(w) else None
        if kind is None or (style and kind != style):
            break
        style = style or kind
        words.insert(0, w)
        if style == "title" and len(words) >= 4:
            break
    return words


def scan_blocks(text: str) -> list[tuple[str, str, str]]:
    """(name, cr, block text) for every printed block in a book's cleaned text."""
    text = WATERMARK.sub(" ", text)
    heads = []
    for m in HEADER.finditer(text):
        words = _name_before(text[max(0, m.start() - 120):m.start()].split())
        if not words or len(words) > 7:
            continue
        name_at = m.start() - len(" ".join(words)) - 1
        heads.append((max(0, name_at), _title(words),
                      _cr_of(m.group("cr"), m.group("xp"), bool(m.group("mr")))))
    out = []
    for i, (at, name, cr) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        out.append((name, cr, text[at:min(end, at + 9000)]))
    return out


def _words_key(name: str) -> tuple[str, ...]:
    """"Wolf, Dire" and "Dire Wolf" are one creature: the index prints the noun first."""
    return tuple(sorted(w for w in re.findall(r"[a-z0-9]+", name.lower())))


# Bestiary 4's PDF is a scan with an OCR text layer: its titles read "ttEijD an1mAL", most
# headers lose their CR, and digits come back as letters ("Sd10" for 5d10, "SO ft." for
# 50 ft.). The anchor file shipped twelve of its blocks, and the measurement found two with
# hit points that cannot be their dice (the giant emperor scorpion at 4 hp, a CR 7 Large
# creature; the manitou at "1 9d1 0+1 33"). Not read until a text copy, or an OCR repair
# that checks every number against its own derivation, exists — an invented number is
# worse than a missing creature.
SCANNED_OCR = {"bestiary-4"}


def join_kerned(creatures: list[dict], fields=("immune", "resist", "languages")) -> int:
    """Rejoin a word the text layer kerned apart — "ma gic", "ooze trait s", "mind-affecting
    ef fects", measured in the re-read's immunity lists — when the joined word is printed
    whole in other blocks' lists (three or more) and a piece is rare (two or fewer — the
    pieces occur only where the split did). A dictionary of the corpus's own terms, never a
    guess at English. Returns how many were joined."""
    import collections

    counts = collections.Counter(w for c in creatures for f in fields
                                 for term in (c.get(f) or [])
                                 for w in re.findall(r"[a-z]+", term.lower()))
    vocab = {w for w, n in counts.items() if n >= 3}
    joined = 0

    def fix(term: str) -> str:
        nonlocal joined
        words = term.split()
        out: list[str] = []
        for w in words:
            if out:
                a, b = out[-1].lower(), w.lower()
                # Five times as common whole as the rarer piece: "ooze trait s" repeats its
                # split three times, and "traits" is printed hundreds.
                if (a + b) in vocab and counts[a + b] >= 5 * min(counts[a], counts[b]):
                    out[-1] = out[-1] + w
                    joined += 1
                    continue
            out.append(w)
        return " ".join(out)

    for c in creatures:
        for f in fields:
            if c.get(f):
                c[f] = [fix(t) for t in c[f]]
    return joined


def aliases_for(old: list[dict], new: dict[str, dict]) -> tuple[dict[str, str], list[str]]:
    """Old id -> new id for every old creature whose id did not survive, so a save made
    before the re-read still finds a body. By what the id means first — its name's words
    and exactly one new name's, one inside the other ("skeleton" -> "human skeleton";
    "elephant-mastodon" is the mastodon, though the old file carried the elephant printed
    above it) — and, when the name fits several (the elementals, printed in four sizes),
    by the block it actually carried: same CR, hp and AC. Returns the map and the ids
    neither found."""
    out, lost = {}, []
    for c in old:
        if c["id"] in new or c.get("source") == "Bestiary 4":
            continue
        words = set(_words_key(c["name"]))
        # The index's "Family, Specific": the words after the comma name the creature
        # ("Elephant, Mastodon" is the mastodon; "Worg, Winter Wolf" the winter wolf).
        specific = set(_words_key(c["name"].split(",", 1)[1])) if "," in c["name"] else set()
        same = [k for k, n in new.items() if specific and n.get("source") == c.get("source")
                and specific <= set(_words_key(n["name"]))]
        if len(same) != 1:
            same = [k for k, n in new.items() if n.get("source") == c.get("source")
                    and (words <= set(_words_key(n["name"]))
                         or set(_words_key(n["name"])) <= words)]
        if len(same) != 1:
            # Hit points and AC, not CR: the old file read "CR 1 1" as CR 1, so its
            # "Plague Swarm" at CR 1 is the CR 11 rat plague swarm, 152 hp, AC 22.
            # Among creatures sharing a word of the name only: across the whole book the
            # first cut aliased `owl-great-horned` to the clockwork spy (both 5 hp, AC 15).
            kin = same or [k for k, n in new.items() if words & set(_words_key(n["name"]))]
            same = [k for k in kin if new[k].get("source") == c.get("source")
                    and (new[k]["hp"], new[k]["flat_ac"]) == (c["hp"], c["flat_ac"])]
        if len(same) > 1 and len({(new[k]["hp"], new[k]["flat_ac"], new[k]["cr"])
                                  for k in same}) == 1:
            # Variants printed with the same numbers (Bestiary 5's four veela): the
            # first in print order, which is the one the old file's page began with.
            same = same[:1]
        if len(same) == 1:
            out[c["id"]] = same[0]
        else:
            lost.append(c["id"])
    return out, lost


def run_scan(pdf_dir: Path, out: Path, keep_ids: dict[tuple[str, ...], str],
             texts: dict[str, list[str]] | None = None,
             old: list[dict] | None = None) -> dict:
    """Every block of every Bestiary, ids kept where the old anchor file had the creature
    (`keep_ids`, by its name's words), so a save's `from_template` still resolves; the
    rest of the old ids aliased (`aliases_for`). `texts`, each book's page texts, skips
    reading the PDFs again (seven minutes for the six)."""
    creatures: dict[str, dict] = {}
    report = []
    for slug_name, filename in BOOKS.items():
        if slug_name in SCANNED_OCR:
            report.append((slug_name, 0, 0, "OCR scan: not read (SCANNED_OCR)"))
            continue
        pdf = pdf_dir / filename
        if texts is None and not pdf.exists():
            report.append((slug_name, 0, 0, "missing"))
            continue
        title = json.loads((ROOT / "reference" / "books" / f"{slug_name}.json")
                           .read_text(encoding="utf-8")).get("title", slug_name)
        if texts is not None:
            text = ref.clean("\n".join(texts[slug_name]))
        else:
            reader = PdfReader(str(pdf))
            text = ref.clean(ref.page_text(reader, 0, len(reader.pages) - 1))
        found = scan_blocks(text)
        got = 0
        book: list[dict] = []
        book_blocks: list[str] = []
        for name, cr, block in found:
            parsed = parse_block(block, name, cr)
            if parsed is None:
                continue
            parsed["id"] = keep_ids.get(_words_key(name)) or slug(name)
            parsed["source"] = title
            parsed["notes"] = f"CR {parsed['cr']} {parsed['creature_type']}".strip()
            book.append(parsed)
            book_blocks.append(block)
        shared = _shared_ecology(book, book_blocks)
        for parsed in book:
            # First book wins: Bestiary 1 is the canonical printing of anything reprinted.
            creatures.setdefault(parsed["id"], parsed)
            got += 1
        report.append((slug_name, len(found), got,
                       f"{shared} given their family's environment" if shared else ""))
    kerned = join_kerned(list(creatures.values()))
    if kerned:
        report.append(("kerned words rejoined", kerned, 0, ""))
    aliases, lost = aliases_for(old or [], creatures)
    if lost:
        report.append(("old ids lost", len(lost), 0, ", ".join(lost)))
    payload = {
        "source": "Bestiary PDFs, every printed block found by its CR/XP header",
        "note": ("Parsed from the printed stat blocks. A block that could not be read is "
                 "skipped and counted rather than filled in — a creature with an invented "
                 "AC is one the engine rolls against wrongly forever."),
        # Ids the anchor file used that no block now carries, to the block each one was:
        # read by `bestiary.raw_block`, so a save's `from_template` keeps its body.
        "aliases": dict(sorted(aliases.items())),
        "creatures": sorted(creatures.values(), key=lambda c: c["name"].lower()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"payload": payload, "report": report}


def run(pdf_dir: Path, out: Path) -> dict:
    creatures: dict[str, dict] = {}
    report = []
    for slug_name, filename in BOOKS.items():
        book_file = ROOT / "reference" / "books" / f"{slug_name}.json"
        pdf = pdf_dir / filename
        if not book_file.exists() or not pdf.exists():
            report.append((slug_name, 0, 0, "missing"))
            continue

        book = json.loads(book_file.read_text(encoding="utf-8"))
        anchors = book.get("creatures") or []
        reader = PdfReader(str(pdf))
        title = book.get("title", slug_name)

        got = 0
        for a in anchors:
            page = a.get("page")
            if not isinstance(page, int):
                continue
            # A stat block can run onto the next page, so both are read and joined.
            text = ref.clean(ref.page_text(reader, page, min(page + 1,
                                                             len(reader.pages) - 1)))
            parsed = parse_block(text, a["name"], str(a.get("cr", "")))
            if parsed is None:
                continue
            parsed["source"] = title
            parsed["notes"] = f"CR {parsed['cr']} {parsed['creature_type']}".strip()
            # First book wins: Bestiary 1 is the canonical printing of anything reprinted.
            creatures.setdefault(parsed["id"], parsed)
            got += 1
        report.append((slug_name, len(anchors), got, ""))

    payload = {
        "source": "Bestiary PDFs, via the reference index's creature anchors",
        "note": ("Parsed from the printed stat blocks. A page whose block could not be "
                 "read is skipped and counted rather than filled in — a creature with an "
                 "invented AC is one the engine rolls against wrongly forever."),
        "creatures": sorted(creatures.values(), key=lambda c: c["name"].lower()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"payload": payload, "report": report}


if __name__ == "__main__":
    # The scan, not the anchor walk (`run`, kept for the record of what it did wrong). The
    # file being replaced supplies the ids to keep and the aliases for the rest.
    target = Path(sys.argv[2])
    previous = (json.loads(target.read_text(encoding="utf-8")).get("creatures") or []
                if target.exists() else [])
    result = run_scan(Path(sys.argv[1]), target,
                      {_words_key(c["name"]): c["id"] for c in previous}, old=previous)
    cs = result["payload"]["creatures"]
    print(f"aliases           {len(result['payload']['aliases'])}")
    print(f"{'book':14} {'headers':>8} {'parsed':>8}")
    for name, anchors, got, note in result["report"]:
        print(f"{name:14} {anchors:8} {got:8}  {note}")
    print()
    print(f"unique creatures  {len(cs)}")
    print(f"with environment  {sum(1 for c in cs if c['environment'])}")
    print(f"with abilities    {sum(1 for c in cs if len(c['abilities']) >= 5)}")
    print(f"with a melee atk  {sum(1 for c in cs if c['flat_attack'] is not None)}")
    print(f"with DR           {sum(1 for c in cs if c['reductions'])}")
    print()
    for probe in ("ogre", "skeleton", "dire-wolf", "goblin", "young-red-dragon", "troll"):
        hit = next((c for c in cs if c["id"] == probe), None)
        print(f"  {probe:18}", f"CR {hit['cr']}, {hit['hp']} hp, AC {hit['flat_ac']}, "
                               f"env {hit['environment'][:34]!r}" if hit else "not found")
