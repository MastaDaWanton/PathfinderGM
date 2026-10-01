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

Delivered in Phase 1 wired into nothing (S1). Lane A (Phase 2) points `_mentions`,
`faceless`, `_name_stems` and `mentions._head` at it — every copy of the rule, per
CLAUDE.md's law about rules with more than one copy.

Beside it, the two readers the truth checks share (docs/design-a-truth.md §4):

  * `about(ctx, ref)` — the sentences a beat spends on one person: the attribution's
    answer, the page's words for them where it has none, and a pronoun continuation. The
    continuation is the gap that hid item 22.4: "the heat licks across **his** face" names
    nobody, and the man it burned was never checked.
  * `spans_in_context(text)` — every quotation found over the WHOLE beat, each with the
    narration of the sentences it opens and closes in. Item 13: `hailed_by` split into
    sentences first and looked for whole quotes inside each; "'You!" ends a sentence, so
    Drenn's two lines were found in no sentence at all and neither hail was read.

`head_of` stays pure; `about` reads the context it is handed and nothing else.
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


# --- the words a page finds a person by -------------------------------------------------

def name_words(name: str) -> list[str]:
    """The words, lower-case, that say a sentence is about this person: every word of a
    proper name (three letters or more), or a descriptor's head noun alone. Never the
    last word of a descriptor — "through" is not the watchman."""
    head = head_of(name)
    if not head:
        return []
    if " " in head or head[:1].isupper():
        return [w.lower() for w in _WORD.findall(head)
                if len(w) >= 3 and w.lower() not in _DETERMINERS]
    return [head]


def names_person(sentence: str, name: str) -> bool:
    """Whether `sentence` names this person by one of their words (a plural or a
    possessive of it included)."""
    for w in name_words(name):
        if re.search(r"\b" + re.escape(w) + r"(?:s|es)?(?:['’]s)?\b", str(sentence or ""),
                     re.I):
            return True
    return False


# --- a pronoun carries the person on ----------------------------------------------------
#
# BookNLP resolves pronouns properly; this is its cheapest slice, in code: a sentence that
# names nobody but holds a third-person pronoun of the right family is still about the one
# person the sentences before it were about. It stops at the first sentence that names
# somebody else, and a sentence naming two people carries nobody on. Measured on the Bobby
# beat of item 22.4: the three sentences that burned the man said "his face", "He hits the
# ground" and "his voice is a raspy growl of pain" — none of them named him.

_THIRD = {
    "he": frozenset({"he", "him", "his", "himself"}),
    "she": frozenset({"she", "her", "hers", "herself"}),
    "it": frozenset({"it", "its", "itself"}),
}
_ANY_THIRD = frozenset({"he", "him", "his", "himself", "she", "her", "hers", "herself",
                        "they", "them", "their", "theirs", "themselves", "themself"})


def pronoun_words(pronouns: str) -> frozenset[str]:
    """The pronouns a sentence may carry a person on by. "they/them" — or nothing set —
    is the world giving no gender, and the page picks one (docs/fix-interfaces.md Q26:
    the page's first gendered reference is adopted), so any third person may carry
    them."""
    first = str(pronouns or "").split("/")[0].strip().lower()
    return _THIRD.get(first, _ANY_THIRD)


def pronoun_forms(pronouns: str) -> tuple[str, str, str]:
    """(subject, object, possessive) for a person's pronouns: "he/him" -> ("he", "him",
    "his"); unset or "they/them" -> ("they", "them", "their").

    For the fix hints a check writes about a person. Measured on the 2026-09-30 playtest
    (item 12): keeper-forward's hint said "their work … if the player turns to them" of
    Gorm Vesper, whom the page called "he", and the repair's rewrite carried "until you
    turn to them" into his mouth — wrong pronoun and all."""
    first = str(pronouns or "").split("/")[0].strip().lower()
    return {"he": ("he", "him", "his"), "she": ("she", "her", "her"),
            "it": ("it", "it", "its")}.get(first, ("they", "them", "their"))


def linked(sentences, is_it, is_other, family=_ANY_THIRD) -> list[int]:
    """Indexes of the sentences about one person: those `is_it` accepts, and the pronoun
    continuation after them. `is_other(sentence)` says a sentence names somebody else,
    which ends the run."""
    out: list[int] = []
    carrying = False
    for i, s in enumerate(sentences):
        mine, theirs = bool(is_it(s)), bool(is_other(s))
        if mine:
            out.append(i)
            carrying = not theirs
            continue
        if theirs:
            carrying = False
            continue
        if carrying and {w.lower() for w in _WORD.findall(s)} & set(family):
            out.append(i)
    return out


def _named_by(att, sentence: str, ref: str, name: str) -> bool | None:
    """Whether the attribution says `sentence` means `ref`: True or False when it read
    the sentence, None when it did not (a cut or a rewrite changed it since). A mention
    the labeller could not place counts by its words; one it called nobody does not."""
    if att is None:
        return None
    refs = att.refs_in(sentence)
    if refs is None:
        return None
    if ref in refs:
        return True
    from gm.mentions import NOBODY

    return any(names_person(m.phrase, name) for m in att._in(sentence)
               if m.ref is None and m.model != NOBODY)


def sentences_of(text: str) -> list[str]:
    """The narration's sentences, speech out — what every truth check reads."""
    from gm.narration import _sentences
    from gm.speech import unquoted

    return _sentences(unquoted(str(text or "")))


def about(ctx, ref: str) -> list[tuple[str, str]]:
    """The sentences this beat spends on `ref`, in order, each as (written on the page,
    its narration with speech blanked — `_page.page_sentences`): the attribution's
    answer where it read the sentence, the page's words for them where it did not, and
    the pronoun continuation after either (`linked`). Matched on the narration only: a
    character may say anything about anybody."""
    from ._page import page_sentences

    scene = ctx.scene
    actor = (getattr(scene, "actors", {}) or {}).get(ref)
    if actor is None:
        return []
    name = str(actor.name or "")
    others = [(r, str(a.name or "")) for r, a in scene.actors.items()
              if r != ref and not getattr(a, "is_pc", False)]
    att = getattr(ctx, "attribution", None)
    pairs = page_sentences(ctx.text)
    by_narration = {n: w for w, n in pairs}

    def is_it(n: str) -> bool:
        said = _named_by(att, by_narration.get(n, n), ref, name)
        return said if said is not None else names_person(n, name)

    def is_other(n: str) -> bool:
        for r, other in others:
            said = _named_by(att, by_narration.get(n, n), r, other)
            if said if said is not None else names_person(n, other):
                return True
        return False

    family = pronoun_words(getattr(actor, "pronouns", ""))
    narr = [n for _, n in pairs]
    return [pairs[i] for i in linked(narr, is_it, is_other, family)]


# --- quotations over the whole beat -----------------------------------------------------

def spans_in_context(text: str) -> list[tuple[int, int, str]]:
    """(start, end, context) for every quotation in `text`, found over the whole beat.

    `context` is the narration of the sentence before the one the line opens in, and of
    every sentence from its opening mark to its closing one — speech out. The sentences
    are cut from `speech.blanked`, which keeps every offset, so a line that runs across
    a full stop ("'You! You have the look…'") is one span with one context rather than no
    span in any sentence."""
    from gm.narration import _SENTENCE
    from gm import speech

    text = str(text or "")
    blank = speech.blanked(text)
    bounds = [(m.start(), m.end()) for m in _SENTENCE.finditer(blank) if m.group(0).strip()]
    out: list[tuple[int, int, str]] = []
    for a, b in speech.spans(text):
        first = next((k for k, (s, e) in enumerate(bounds) if s <= a < e), None)
        last = next((k for k, (s, e) in enumerate(bounds) if s <= b - 1 < e), first)
        if first is None:
            out.append((a, b, ""))
            continue
        lo = max(0, first - 1)
        hi = max(first, last if last is not None else first)
        # The blanked slices, not `unquoted` of the text's: a slice can start inside
        # another line, and unquoting a fragment leaves its stray marks behind.
        context = " ".join(blank[s:e] for s, e in bounds[lo:hi + 1])
        out.append((a, b, " ".join(context.split())))
    return out
