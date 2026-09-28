"""Who a name is, in the words the page will use for them — a helper, not a check.

`head_of(name)` is the one rule for the word a descriptor name is found by on the page:
"the watchman waving traffic through" is a watchman, and the page says "the watchman".

Two copies of the wrong rule were measured on the twelve opening companions
(`play/opening.py` SITUATIONS, docs/fix-interfaces.md §1.2):

  * the last word of three letters or more (`judgement._mentions`) is wrong for 12 of 12
    — "through", "you" twice, "door", "table"...; Bobby's watchman was owed his face on
    the beat that said "the way through" and on neither beat that said "watchman";
  * the last word before the first function word (`mentions._head`) is wrong for 10 of 12
    — "clearing", "ahead", "minding", "harness", "round"...

Delivered in Phase 1 wired into NOTHING (S1). From Phase 2 Lane A owns this module and
points `_mentions`, `faceless`, `_name_stems` and `mentions._head` at it — every copy of
the rule, per CLAUDE.md's law about rules with more than one copy.

Pure: no scene, no world, no model. The scene's templates and the world's peoples are
Lane A's to add as a second argument when a check needs them.
"""
from __future__ import annotations

import re

# Words that head a description of a person. The attribution's own list
# (`mentions._PERSON_WORDS`) plus the trades the openings and the booking door use; read
# first, so "the old man ahead of you" is a man whichever boundary comes after.
_PERSON = frozenset((
    "man men woman women boy girl child lad lass youth stranger figure person fellow "
    "folk people crowd warrior fighter brawler brute bruiser ruffian thug tough hulk "
    "giant drunk guard guardsman watchman soldier sailor merchant trader vendor keeper "
    "innkeeper barkeep bartender smith elder priest priestess servant apprentice "
    "farmer drover porter scribe beggar urchin noble mercenary sellsword raider "
    "bandit brigand outlaw intruder attacker opponent foe enemy challenger veteran "
    "beast creature monster abomination fiend demon devil animal horror "
    "clansman clanswoman swordsman duellist dockhand rider pirate cutthroat "
    "foreman crier lamplighter neighbour neighbor boatman ferryman fisherman fishwife "
    "hunter herder shepherd miller baker butcher cook maid widow wife husband mother "
    "father son daughter brother sister uncle aunt girlfriend boyfriend friend "
    "healer bonesetter carter wagoner teamster labourer laborer worker hand clerk "
    "official magistrate captain sergeant sentry sentinel gatekeeper warden "
    "stallholder shopkeeper hawker peddler pedlar tinker weaver tanner cooper mason "
    "carpenter wright chandler apothecary herbalist midwife nurse monk nun acolyte "
    "pilgrim traveller traveler wanderer vagrant lout oaf brat kid infant baby "
    "elf dwarf gnome halfling orc goblin").split())

# Where a descriptor's head noun has ended: a preposition or adverb of place, a relative,
# a conjunction. "the neighbour beside you who knows the words" ends at "beside".
_BOUNDARY = frozenset((
    "at with beside behind ahead near nearby through in on by from under over across "
    "along against outside inside before after beyond of to into onto among amongst "
    "around round next opposite past toward towards up down off out upon within without "
    "who that which whose whom where and or but than as while when").split())

_DETERMINERS = frozenset("the a an this that these those some one another".split())

# -ing and -ed words that are nouns, not participles: "the young king" is a king.
_ING_NOUNS = frozenset((
    "king viking sibling darling foundling youngling underling hireling halfling "
    "changeling nestling weakling earthling offspring thing ring wing sting").split())
_ED_NOUNS = frozenset("steed breed creed reed seed shed bred sled".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def _participle(word: str) -> bool:
    if word.endswith("ing") and len(word) > 4 and word not in _ING_NOUNS:
        return True
    return word.endswith("ed") and len(word) > 4 and word not in _ED_NOUNS


def _possessive(word: str) -> bool:
    return word.endswith(("'s", "’s", "s'", "s’"))


def head_of(name: str) -> str:
    """The word the page finds this person by, lower-case; a proper name, whole.

    1. A proper name keeps its own words: "Soren Kragnirath" is "Soren Kragnirath".
    2. The first person word ("the old man ahead of you" -> "man"), skipping a possessor
       ("the smith's wife" is a wife, not a smith).
    3. Else the word before the first boundary — a preposition or adverb of place, a
       relative, or an -ing/-ed word after the first noun: "the crier working through
       the notices" -> "crier", "the neighbour beside you" -> "neighbour".
    4. Else the last word: "the tall stranger" -> "stranger".
    """
    raw = " ".join(str(name or "").split())
    words = _WORD.findall(raw)
    if not words:
        return ""
    # A proper name: capitalised, and not opened by a determiner ("The woman at the
    # stall" at the head of a sentence is still a description).
    if words[0][0].isupper() and words[0].lower() not in _DETERMINERS:
        return raw
    content = [w.lower() for w in words if w.lower() not in _DETERMINERS]
    for w in content:
        if _possessive(w):
            continue
        if w in _PERSON:
            return w
        if w in _BOUNDARY:
            break
    return _by_boundary(content)


def _by_boundary(content: list[str]) -> str:
    """Steps 3 and 4 alone: the word before the first boundary, else the last word. On
    its own this gets the twelve opening companions right, 12 of 12 (design A, §4); the
    person list in front of it is for names with no boundary in them to find."""
    kept: list[str] = []
    for w in content:
        if w in _BOUNDARY and kept:
            break
        if kept and _participle(w):
            break
        if w not in _BOUNDARY and not _possessive(w):
            kept.append(w)
    return kept[-1] if kept else ""
