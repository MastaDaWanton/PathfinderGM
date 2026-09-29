"""The order of doing in one line of the player's: which clause is the move, which is the
cast, and what comes before and after it. Read in code, never asked of a model.

The owner, 2026-09-29: "when you click a next door button it should attach like a spell
does and then apply when you send", and then, of the words written beside it: "i think
the interpreter should be able to see where in the described action the move should take
place same with spells". The chip decides WHICH place (or spell); the words decide WHEN
in the turn it happens. "I buy a waterskin, then head to the market" buys here and then
walks; "I go to the market and ask after the smith" walks and then asks, at the market.

The shape is the parsers' own, researched before this was written:
  * A line is a sequence of commands, parsed and acted on ONE AT A TIME, because "the
    meaning of the noun phrase ... depends on where the player is by then" (Inform
    Designer's Manual 4, §34: "'take sword. east. put sword in stone' is broken into a
    sequence of three verb phrases, each parsed and acted on in turn"). That is why the
    clauses after the move are planned again at the destination, against its people, and
    not validated up front against the room being left.
  * The separators are the Infocom parser's end-of-command tokens: a full stop, THEN and
    AND (ifwiki, "Infocom-type parser": "GO NORTH THEN GO WEST. WAIT"). A bare AND also
    joins two nouns ("bread and cheese"), so here it separates only where the words after
    it begin a new verb.
  * When a command in the chain fails, the rest of the line is thrown away: Zork I's main
    loop clears `P-CONT`, the pointer to the unread rest of the input, when an action
    returns `M-FATAL` or the parse fails (historicalsource/zork1, gmain.zil). We keep
    the unrun words instead of discarding them, in the pen with a line saying so, because
    a player who wrote them meant them — but the chain stops, as Zork's did. Whether
    Inform 7 also stops a chain on a failed action (as opposed to a parser error) could not
    be confirmed from its documentation; an intfiction.org thread (2016, "multiple
    commands per line") reports later commands running after an earlier one failed.
  * "After I X, I Y" and "Before I Y, I X" are written in one order and done in the other;
    both are turned into the order of doing. That part is ours: none of the parsers above
    reads BEFORE or AFTER as a separator.

Deliberately small. It does not parse English; it finds the joins a player types between
two things they do, and leaves a clause it cannot split whole — an unsplit clause is only
ever planned together, as the whole line always was before.
"""
from __future__ import annotations

import re

# Verbs a new clause starts with, for the one ambiguous join (a bare AND or a comma).
# Base forms, as a player writes the second verb of "I X and Y": "and head out", ", buy
# a loaf". Nouns that are also verbs a player might list ("water", "light") are left out
# on purpose — "bread and water" must stay one thing bought.
_VERBS = (
    "go|walk|head|run|leave|slip|sneak|step|stroll|wander|hurry|dash|flee|bolt|make|set|"
    "travel|return|ride|sail|climb|jump|cross|enter|exit|depart|withdraw|retreat|escape|"
    "buy|sell|trade|pay|give|hand|take|grab|pick|steal|drink|eat|use|cast|draw|sheathe|"
    "attack|strike|stab|shoot|hit|punch|kick|ask|say|tell|talk|speak|greet|shout|call|"
    "whisper|look|search|examine|listen|watch|wait|rest|sleep|hide|forage|gather|follow|"
    "find|seek|knock|open|close|order|offer|thank|wave|nod|bow|smile|read|lead|mount|"
    "dismount|sit|stand|turn|bargain|haggle|hire|rent|bribe|drop|put|throw|toss|check|"
    "try|keep|pray|sing|play|demand|warn|pull|push|push|light|prepare"
)
_STARTS_A_VERB = re.compile(r"^(?:I\s+)?(?:\w+ly\s+)?(?:" + _VERBS + r")\b", re.I)
# The same verbs as a gerund, for "before leaving" and "after buying the bread".
_GERUND = re.compile(r"^(\w+?)ing\b", re.I)

# Leaving, walking, riding: a clause that is the move. The destination's own name is the
# other sign (`move_clause`).
_MOVES = re.compile(
    r"\b(?:go|goes|going|went|walk\w*|head\w*|run|runs|running|ran|leav\w+|left|"
    r"slip\w*\s+(?:out|away|off|back)|sneak\w*\s+(?:out|off|away|back)|"
    r"step\w*\s+(?:out|outside|over|in|inside|back)|stroll\w*|wander\w*|hurr\w+|dash\w*|"
    r"flee\w*|fled|bolt\w*|make\s+(?:my|our)\s+way|made\s+(?:my|our)\s+way|"
    r"set\w*\s+(?:out|off)|travel\w*|return\w*|ride|rides|riding|rode|sail\w*|"
    r"journey\w*|depart\w*|exit\w*|withdraw\w*|retreat\w*|escape\w*|"
    r"take\s+the\s+road|hit\s+the\s+road)\b", re.I)

_CASTS = re.compile(r"\b(?:cast\w*|conjur\w+|invok\w+|weav\w+|chant\w*|"
                    r"call\w*\s+(?:up|down|forth))\b", re.I)

# Speech keeps its commas and its full stops: '"Farewell. Stay safe," I say, and leave'
# is two clauses, not four. Quoted spans are set aside before splitting and put back,
# found by the project's one quotation scanner (`speech.spans`), never a second rule.
_HELD = re.compile(r"«(\d+)»")

_SENTENCES = re.compile(r"(?<=[.!?;])\s+")
_THEN = re.compile(r"\s*,?\s*\b(?:and\s+)?then\b\s*,?\s*", re.I)
_JOIN = re.compile(r",\s*and\s+|\s+and\s+|,\s+", re.I)
# "After I X, I Y" / "Before I Y, I X" at the head of a sentence, and "I X before I Y" /
# "I Y after I X" inside one. Only before "I" or a gerund: "I wait before the gate" and
# "I run after the thief" are places and pursuits, not an order of doing.
_LEADING = re.compile(r"^(after|before)\s+((?:I\b|\w+ing\b).+?),\s*(.+)$", re.I)
_INNER = re.compile(r",?\s+(before|after)\s+(?=I\b|\w+ing\b)", re.I)

# Gerunds whose base form ends in a silent e, which "strip ing" cannot recover.
_E_BASES = {"leav", "mak", "tak", "trad", "rid", "hid", "us", "mov", "wav", "arriv",
            "chas", "clos", "giv", "hav", "com", "din", "hir", "pac", "rac", "rais",
            "rescu", "sav", "escap", "retriev", "writ", "bargain"}


def _hold_quotes(text: str) -> tuple[str, list[str]]:
    from . import speech

    held: list[str] = []
    parts, at = [], 0
    for a, b in speech.spans(text):
        parts.append(text[at:a])
        held.append(text[a:b])
        parts.append(f"«{len(held) - 1}»")
        at = b
    parts.append(text[at:])
    return "".join(parts), held


def _put_back(text: str, held: list[str]) -> str:
    return _HELD.sub(lambda m: held[int(m.group(1))], text)


def _tidy(clause: str) -> str:
    c = clause.strip().strip(",;").strip()
    c = re.sub(r"^(?:and|then|so)\s+", "", c, flags=re.I).strip()
    return c.rstrip(".,;").strip()


def _split_joins(sentence: str) -> list[str]:
    """A sentence split at "then", and at "and" or a comma where a new verb starts."""
    out: list[str] = []
    for piece in _THEN.split(sentence):
        piece = piece.strip()
        if not piece:
            continue
        start = 0
        for m in _JOIN.finditer(piece):
            after = piece[m.end():]
            if _STARTS_A_VERB.match(after):
                out.append(piece[start:m.start()])
                start = m.end()
        out.append(piece[start:])
    return out


def _one_sentence(sentence: str) -> list[str]:
    m = _LEADING.match(sentence.strip())
    if m:
        first, second = m.group(2), m.group(3)
        if m.group(1).lower() == "after":
            return _split_joins(first) + _split_joins(second)
        return _split_joins(second) + _split_joins(first)
    m = _INNER.search(sentence)
    if m:
        head, tail = sentence[:m.start()], sentence[m.end():]
        if m.group(1).lower() == "before":
            return _split_joins(head) + _split_joins(tail)
        return _split_joins(tail) + _split_joins(head)
    return _split_joins(sentence)


def clauses(text: str) -> list[str]:
    """The player's line as clauses in the order they are to be DONE.

    >>> clauses("I buy a waterskin, then head to the market")
    ['I buy a waterskin', 'head to the market']
    >>> clauses("After I cast sleep on the guard, I run for the gate")
    ['I cast sleep on the guard', 'I run for the gate']
    """
    held_text, held = _hold_quotes(str(text or ""))
    out: list[str] = []
    for sentence in _SENTENCES.split(held_text):
        for c in _one_sentence(sentence):
            c = _tidy(c)
            if c:
                out.append(_put_back(c, held))
    return out


def _base(gerund_word: str) -> str:
    stem = gerund_word[:-3]
    if stem.lower() in _E_BASES:
        return stem + "e"
    if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1].lower() not in "aeiouls":
        return stem[:-1]
    return stem


def as_sentence(clause: str) -> str:
    """A clause as a line the player could have typed on its own: "buy bread" is "I buy
    bread.", "leaving" is "I leave.". The planner's readers look for "I <verb>", and the
    pen shows the words back in the player's own voice."""
    c = _tidy(clause)
    if not c:
        return ""
    if not re.match(r"^(?:I\b|I'|\"|“)", c):
        m = _GERUND.match(c)
        if m:
            c = _base(m.group(0)) + c[m.end():]
        c = "I " + c[0].lower() + c[1:]
    return c if c[-1] in ".!?\"”" else c + "."


def joined(parts: list[str]) -> str:
    """Clauses back into the player's line, one sentence each."""
    return " ".join(as_sentence(p) for p in parts if _tidy(p))


def plain(parts: list[str]) -> str:
    """Clauses as a short list for a status line: "buy bread, ask after the smith"."""
    words = []
    for p in parts:
        s = as_sentence(p).rstrip(".")
        words.append(s[2:] if s.startswith("I ") else s)
    return ", ".join(w for w in words if w)


def _name_in(name: str, clause: str) -> bool:
    n = " ".join(str(name or "").lower().split())
    n = re.sub(r"^the\s+", "", n)
    if len(n) < 3:
        return False
    return re.search(r"\b" + re.escape(n) + r"\b", clause.lower()) is not None


def move_clause(parts: list[str], place_name: str) -> int | None:
    """Which clause is the move to `place_name`: the first that names it, else the last
    with a verb of going. None when no clause is recognisably the move — the caller puts
    the move LAST then, because leaving is what usually ends a turn ("I buy bread" beside
    a chip for the gate buys and then goes)."""
    for i, p in enumerate(parts):
        if _name_in(place_name, p):
            return i
    going = [i for i, p in enumerate(parts) if _MOVES.search(p)]
    return going[-1] if going else None


def cast_clause(parts: list[str], spell_name: str, quiet=None) -> int | None:
    """Which clause is the cast of the attached spell: the one naming it, else one with a
    verb of casting, else the first that declares nothing else (`quiet(clause)` answers
    that; "into the tree tops" is where the spell goes). None when none is."""
    for i, p in enumerate(parts):
        if _name_in(spell_name, p):
            return i
    for i, p in enumerate(parts):
        if _CASTS.search(p):
            return i
    if quiet is not None:
        for i, p in enumerate(parts):
            if quiet(p):
                return i
    return None


def only_going(clause: str) -> bool:
    """A clause that is the move and nothing else a verb could carry: "I slip out
    quietly", "I run for it". Used with the declared ops, not instead of them."""
    return bool(_MOVES.search(clause))
