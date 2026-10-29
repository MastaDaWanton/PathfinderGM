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


def parse_block(text: str, name: str, cr: str) -> dict | None:
    """One stat block, or None if the page did not actually hold one."""
    t = re.sub(r"\s+", " ", text)

    # The comma after the AC is sometimes missing ("AC 17 touch 10", Bestiary 5's swamp
    # mummy), and a block printed for a group gives "hp 127 each (15d8+60)" (the adlets).
    ac = re.search(r"\bAC\s+(\d+)\s*,?\s*touch\s+(\d+)\s*,?\s*flat-?\s?footed\s+(\d+)", t, re.I)
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

    head = re.search(rf"({'|'.join(ALIGNMENTS)})\s+({'|'.join(SIZES)})\s+([a-z]+)"
                     r"(?:\s*\(([^)]+)\))?", t, re.I)
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
    for m2 in re.finditer(r"\bDR\s+(\d+)\s*/\s*([^;,]+)", t, re.I):
        bypass = m2.group(2).strip()
        dr.append({"amount": int(m2.group(1)),
                   "bypass": "" if bypass in ("—", "-", "–") else bypass,
                   "source": "natural"})

    def sign(m2):
        return int(m2.group(1).replace(" ", "")) if m2 else None

    return {
        "id": slug(name),
        "name": name,
        "kind": "npc",
        "cr": cr,
        "cr_value": cr_value(cr),
        "size": (head.group(2).lower() if head else "medium"),
        "creature_type": (head.group(3).lower() if head else ""),
        "subtype": (head.group(4).lower() if head and head.group(4) else ""),
        "alignment": (head.group(1).upper() if head else ""),
        "abilities": abil,
        "hp": int(hp.group(1)),
        "hit_dice": hp.group(2).strip(),
        "flat_ac": int(ac.group(1)),
        "ac_note": f"touch {ac.group(2)}, flat-footed {ac.group(3)}",
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
