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
_PROSE = re.compile(
    r"[.!?]\s+[A-Z]"          # a sentence ends and another begins
    r"|\b(?:and|but|which|because|though|while|when|their|these|those|its"
    r"|they|them|it is|there are)\b\s", re.I)

# The longest legitimate term measured across the 782 printed blocks is "mind-affecting
# effects" at 22 characters. 30 leaves room for one this import has not seen without
# admitting a clause. Terms in the 30-60 band were sampled and every one was spill:
# "raid caravans and humanoid settlements", "and his eight archdevil tyrants".
MAX_TERM = 30

# A whole list this long is spill on its own evidence. The largest hand-checked real one is
# a devil at nine. 42 immune lists and 76 resist lists were at or past twelve, which is
# where the parser had stopped reading a line and started reading a book.
MAX_TERMS = 12


# The stat-block line reads `Immune cold, fire`. Prose reads "is immune *to* fire" and
# "resist this effect *with* a DC 18 save" — and `_between` searches case-insensitively for
# the first match, so a creature whose DEFENSE line has no Immune at all gets whatever
# sentence in its flavour text used the word. Every such match starts with a function word,
# and no printed immunity or resistance ever does: they are bare noun phrases.
_PROSE_OPENER = re.compile(
    r"^(?:to|the|a|an|this|that|these|those|with|from|by|for|of|in|on|as|at|it|he|she"
    r"|they|his|her|its|their)\b", re.I)

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


def mend(term: str) -> str:
    """Rejoin a word the PDF extraction broke apart, where the join has been checked."""
    t = term.strip()
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
_WELDED = re.compile(
    r"\s+(?=(?:Defensive Abilities|Immune|Resist|SR|Weaknesses|DR|Aura|Senses|Speed"
    r"|Melee|Ranged|Space|Reach|Special Attacks|Str|Fort|Ref|Will|hp|AC)\b)")


def clip(term: str) -> str:
    """A term with a welded-on label cut off at the label."""
    return _WELDED.split((term or "").strip(), maxsplit=1)[0].strip(" ;,.")


# The watermark as it is actually stamped, for cutting out of prose fields. A capped field
# like `treasure[:120]` cannot run away, but the watermark sits inside the cap all the same:
# the Devourer's treasure reads "standard paizo.com #1276082, D M <...@...>, Oct 20, 2009".
# There is no field in which this is content, so it is removed wherever it appears.
_STAMP = re.compile(
    r"\s*paizo\.com\s*#\s*\d+\s*,?\s*(?:[A-Z]\s*)*(?:<[^>]*>)?\s*,?"
    r"(?:\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}\s*,?"
    r"\s*\d{4}\s*)?|\s*<[^@>]*@[^>]*>\s*,?", re.I)


def scrub(text: str) -> str:
    """A prose field with the store watermark taken out.

    The watermark carries a real purchaser's email address, which is a reason to remove it
    beyond the fact that it is not a rule. It is in the PDFs on every page, so it can land
    in any field the parser reads.
    """
    return re.sub(r"\s{2,}", " ", _STAMP.sub(" ", text or "")).strip(" ;,.")


def is_spill(term: str) -> bool:
    """True when this list entry came from past the end of the stat-block line."""
    t = (term or "").strip()
    if not t:
        return True
    return bool(len(t) > MAX_TERM or _PROSE_OPENER.match(t) or _WATERMARK.search(t)
                or _NEXT_BLOCK.search(t) or _PROSE.search(t))


# `Resist` on a DEFENSE line always takes an amount: "Resist cold 10, fire 10". There is no
# such thing as a printed resistance without a number, so the number is a shape test rather
# than a heuristic — and it is needed, because "resist" also appears inside the SPELL-LIKE
# ABILITIES block and in spell names, and `_between` takes the first match either way. It
# is what let "cure light wounds", "sound burst (DC 22)" and "all spells cast on it" through
# every test above: they are short, they are noun phrases, and they are not resistances.
RESISTANCE = re.compile(r"^[a-z][a-z \-]*\s\d+$", re.I)


def trim(terms, limit: int = MAX_TERMS, shape: re.Pattern | None = None) -> list[str]:
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
        if is_spill(term) or (shape is not None and not shape.match(term)):
            break
        out.append(term)
    return out
