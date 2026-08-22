"""Where a stat-block list ends, when the page did not say.

`tools/extract_bestiary_pdfs.py` reads each field as the run of text between its own
keyword and the next keyword that can follow it. That works because Pathfinder stat blocks
have no punctuation closing a line — the next label is the terminator.

It fails silently when the next label is not there. `Immune` is bounded by `Resist`, `SR`,
`Weaknesses` and `OFFENSE`, and a creature carrying none of those runs to the end of the
page and keeps going: the flavour text, the illustration credit, the store watermark, and
then the *next* creature's stat block. Basilisk's immunities contained the whole Dire Bat.

Every other field survived this because every other field is capped — `melee[:200]`,
`senses[:160]`, `environment[:120]`. The three that split on commas were not, so instead of
one long wrong string they became a list of a hundred plausible-looking short ones, which
is the version nobody notices. Measured on the shipped file: 392 immune terms and 835
resist terms over 90 characters, against 701 resist terms under 10.

The repair is a cut, not a rewrite. Spill is sequential — once the parser is past the end
of the line every term after it is spill too — so the list is truncated at the first term
that is not a stat-block term, and everything before it is kept untouched.

`tools/repair_statblock_lists.py` applies this to the shipped file, which cannot simply be
regenerated: the parse needs the PDFs and only the extracted index of them is in the repo.
"""
from __future__ import annotations

import re

# The store watermark stamped on every page of the purchased PDFs, the page furniture
# around it, and the run of order numbers that follows. Any of these means the parser is
# reading the page rather than the stat block. The email address is a real person's, which
# is its own reason to cut here rather than ship it.
_WATERMARK = re.compile(
    r"paizo\.com|@|\bOct\s+\d|\b20\d\d\b\s*$|\b\d{6}\b|illustration by", re.I)

# A label that only appears at the top of a stat block. Finding one inside a DEFENSE line
# means the next creature has started.
_NEXT_BLOCK = re.compile(
    r"\b(?:DEFENSE|OFFENSE|STATISTICS|ECOLOGY|TACTICS|SPECIAL ABILITIES)\b"
    r"|\bCR\s+\d|\bXP\s+[\d,]|\bInit\s+[+-]|\bhp\s+\d+\s*\(|\bAC\s+\d+\s*,"
    r"|\bFort\s*[+-]|\bWill\s*[+-]|\bRef\s*[+-]|\bSenses\b|\bhit dice\b", re.I)

# Prose, as opposed to a term. A stat-block entry is a noun phrase: "cold", "undead
# traits", "mind-affecting effects", "acid 10". It never runs a sentence.
#
# `and`, `or` and `but` are deliberately not in here, though they were at first. Pathfinder
# writes real immunities with `and` in them — "ability damage and drain", "charm and
# compulsion effects", "positive and negative energy", "visual effects and illusions" —
# and treating the word as evidence emptied Baba Yaga's and the ahriman's immunity lists
# entirely. Nothing was gained by it either: every spilled fragment those words appeared in
# was over the length limit and already caught. When one *opens* a term it is still a
# continuation of the term before, and `_PROSE_OPENER` catches that.
_PROSE = re.compile(
    r"[.!?]\s+[A-Z]"          # a sentence ends and another begins
    r"|\b(?:which|because|though|while|when|their|these|those"
    r"|they|them|it is|there are)\b\s", re.I)

# The longest legitimate term in the printed blocks is "mind-affecting effects" at 22, and
# 30 looked like generous slack for it. Against the spreadsheet it was not: "bludgeoning
# and piercing damage" is 31, "enchantment and illusion spells" is 31, "channel energy from
# non-mythic sources" is 38, and because the cut is a truncation each of those took every
# real immunity after it — the whispering tyrant lost cold, electricity and undead traits
# to a 38-character first entry, and two liches lost their whole lists.
#
# 45 is above every real term found in either source and still far below spill, which runs
# to hundreds of characters and in practice trips one of the content tests before this one.
MAX_TERM = 45

# The Languages line holds more than languages — "telepathy with haunted ones 100 ft.",
# "speak with animals (including vermin)", "tongue of the sun and moon" are all printed
# there and all real. 30 characters cut every one of them, so this field gets its own
# ceiling; spill in a language list is still hundreds of characters, not fifty.
MAX_LANGUAGE_TERM = 48

# A whole list this long is spill on its own evidence. The largest hand-checked real one is
# a devil at nine. 42 immune lists and 76 resist lists were at or past twelve, which is
# where the parser had stopped reading a line and started reading a book.
MAX_TERMS = 12

# Languages are the exception and need their own number. A creature that speaks thirteen is
# unusual but not impossible, and the shared cap silently truncated one: an outsider lost
# Terran and Undercommon off the end of a legitimate list because Orc happened to be
# twelfth. Nothing else in a stat block runs that long, so the cap stays tight elsewhere.
MAX_LANGUAGES = 24


# The stat-block line reads `Immune cold, fire`. Prose reads "is immune *to* fire" and
# "resist this effect *with* a DC 18 save" — and `_between` searches case-insensitively for
# the first match, so a creature whose DEFENSE line has no Immune at all gets whatever
# sentence in its flavour text used the word. Every such match starts with a function word,
# and no printed immunity or resistance ever does: they are bare noun phrases.
#
# `and`, `or` and `but` are here rather than in `_PROSE` below: mid-term they are ordinary
# ("charm and compulsion effects"), but a term that *begins* with one is the tail of the
# term before it, split on a comma that was inside a sentence — "and attacks relying on
# sight", "and all forms of madness".
_PROSE_OPENER = re.compile(
    r"^(?:to|the|a|an|this|that|these|those|with|from|by|for|of|in|on|as|at|it|he|she"
    r"|they|his|her|its|their|and|or|but)\b", re.I)

# The Bestiary PDFs render "mind-affecting" as "mind- aff ecting" — the same typography
# defect `reference/build_reference.py` already repairs for the rules text, arriving here
# through a different door. Left alone it splits one immunity into three spellings and a
# search for the commonest immunity in the game misses the creatures spelled the other way.
#
# Written out rather than derived. A general "rejoin a short fragment to the word before
# it" rule was tried and turned "mind- aff ecting" into "mindaff ecting", because the
# fragment lengths differ and the hyphen is real in one place and noise in another. The
# whole broken vocabulary across 782 blocks is small enough to list, and a list can be
# checked; the general rule could only be trusted by re-reading its output anyway.
_BROKEN = {
    "mind- aff ecting effects": "mind-affecting effects",
    "mind- affecting effects": "mind-affecting effects",
    "mind-aff ecting effects": "mind-affecting effects",
    "f ire": "fire",
    "f ear": "fear",
    "sp ecial": "special",
    "construct trait s": "construct traits",
    "undead trait s": "undead traits",
}

# The same defect inside a resistance, where the amount follows: "co ld 10".
_BROKEN_WORDS = {"co ld": "cold", "f ire": "fire", "aci d": "acid",
                 "electricit y": "electricity", "soni c": "sonic"}


# A term that opens with a conjunction is the tail of the one before it, split on a comma
# inside a list the source wrote as prose: "Immune paralysis, sleep, and poison" gives
# "and poison". Dropping it loses a real immunity — poison — so the conjunction comes off
# and the rest is judged on its own. What is left is usually a term; when it is not
# ("and his eight archdevil tyrants" -> "his eight...") `_PROSE_OPENER` still catches it.
_LEADING_CONJUNCTION = re.compile(r"^(?:and|or|but)\s+", re.I)


def mend(term: str) -> str:
    """Rejoin a word the PDF extraction broke apart, where the join has been checked."""
    t = _LEADING_CONJUNCTION.sub("", term.strip())
    if t.lower() in _BROKEN:
        return _BROKEN[t.lower()]
    for broken, whole in _BROKEN_WORDS.items():
        if t.lower().startswith(broken + " "):
            return whole + t[len(broken):]
    return t


# A stat-block label with no comma in front of it, welded onto the end of a real term
# because the line ended without one. Berbalang's first immunity is "undead traits
# Defensive Abilities projection" — the immunity is real and everything from `Defensive`
# is the next field. Cutting the whole term loses a fact the book printed; cutting at the
# label keeps it. 61 terms have this shape.
#
# Case-insensitive because the two sources capitalise differently: the PDF prints
# "Defensive Abilities" and the spreadsheet writes "defensive abilities". Without the flag
# the spreadsheet's own welded terms — "undead traits defensive abilities projection",
# "electricity 10 immune construct traits" — survived every test in this module.
_WELDED = re.compile(
    r"\s+(?=(?:Defensive Abilities|Immune|Resist|SR|Weaknesses|DR|Aura|Senses|Speed"
    r"|Melee|Ranged|Space|Reach|Special Attacks|Str|Fort|Ref|Will|hp|AC)\b)", re.I)


def clip(term: str) -> str:
    """A term with a welded-on label cut off at the label, and otherwise untouched.

    The tidying strip only runs when a cut was actually made. Applied unconditionally it
    turned `"telepathy 100 ft."` into `"telepathy 100 ft"` on several hundred language
    entries — the full stop there belongs to the abbreviation, not to the parser.
    """
    t = (term or "").strip()
    parts = _WELDED.split(t, maxsplit=1)
    return parts[0].strip(" ;,.") if len(parts) > 1 else t


# The watermark as it is actually stamped, for cutting out of prose fields. A capped field
# like `treasure[:120]` cannot run away, but the watermark sits inside the cap all the same:
# the Devourer's treasure reads "standard paizo.com #1276082, D M <...@...>, Oct 20, 2009".
# There is no field in which this is content, so it is removed wherever it appears.
_STAMP = re.compile(
    r"\s*paizo\.com\s*#\s*\d+\s*,?\s*(?:[A-Z]\s*)*(?:<[^>]*>)?\s*,?"
    r"(?:\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}\s*,?"
    r"\s*\d{4}\s*)?|\s*<[^@>]*@[^>]*>\s*,?", re.I)


def scrub(text: str) -> str:
    """A prose field with the store watermark taken out, and otherwise untouched.

    The watermark carries a real purchaser's email address, which is a reason to remove it
    beyond the fact that it is not a rule. It is in the PDFs on every page, so it can land
    in any field the parser reads.

    The early return is the whole point of the function's shape. Without it, the tidying
    that follows a removal — collapse runs of spaces, strip trailing punctuation — ran on
    every field in the file: 11,620 of them in `creatures.json`, turning `"30 ft."` into
    `"30 ft"` and cutting the full stop off the end of every ability description. A repair
    that rewrites 11,620 fields to fix 40 is not a repair.
    """
    text = text or ""
    if not _STAMP.search(text):
        return text
    return re.sub(r"\s{2,}", " ", _STAMP.sub(" ", text)).strip(" ;,.")


def is_spill(term: str, max_term: int = MAX_TERM) -> bool:
    """True when this list entry came from past the end of the stat-block line."""
    t = (term or "").strip()
    if not t:
        return True
    return bool(len(t) > max_term or _PROSE_OPENER.match(t) or _WATERMARK.search(t)
                or _NEXT_BLOCK.search(t) or _PROSE.search(t))


# `Resist` on a DEFENSE line always takes an amount: "Resist cold 10, fire 10". There is no
# such thing as a printed resistance without a number, so the number is a shape test rather
# than a heuristic — and it is needed, because "resist" also appears inside the SPELL-LIKE
# ABILITIES block and in spell names, and `_between` takes the first match either way. It
# is what let "cure light wounds", "sound burst (DC 22)" and "all spells cast on it" through
# every test above: they are short, they are noun phrases, and they are not resistances.
RESISTANCE = re.compile(r"^[a-z][a-z \-]*\s\d+$", re.I)


def trim(terms, limit: int = MAX_TERMS, shape: re.Pattern | None = None,
         max_term: int = MAX_TERM) -> list[str]:
    """Keep a stat-block list up to the point the parser left the line.

    Truncating rather than filtering is deliberate. A filter would keep the short
    innocuous-looking fragments that appear *after* the spill starts — "wild hair",
    "burn", "and die" all pass a length test on their own — and those are the entries that
    read as real immunities and would be quoted back as rules.
    """
    out: list[str] = []
    for term in terms or ():
        if len(out) >= limit:
            break
        # Clipped before the spill test, not instead of it: "undead traits Defensive
        # Abilities projection" is a real immunity carrying the next field, and testing the
        # whole string throws the immunity away with it.
        term = mend(clip(term))
        if is_spill(term, max_term) or (shape is not None and not shape.match(term)):
            break
        out.append(term)
    return out
