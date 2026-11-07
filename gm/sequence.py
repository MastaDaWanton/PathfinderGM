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
    # A player's lower-case "i" is still "I": the owner's own line of 2026-11-06 ("…then i
    # serve the food i made to everyone") came back to the pen as "I i serve the food".
    if re.match(r"^i\b", c):
        c = "I" + c[1:]
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


def _words(text) -> str:
    return " " + " ".join(re.findall(r"[\w']+", str(text or "").lower())) + " "


def said_in(span, text) -> bool:
    """Whether the span's words are in the text, word for word."""
    s = _words(span)
    return bool(s.strip()) and s in _words(text)


def clauses_of(span, parts: list[str]) -> list[int]:
    """The clauses an action's span lies across: each clause inside the span, or the one
    the span lies inside, word for word. Several when the reader read one deed where the
    joins cut two ("take a lantern off the shelf and pay the keeper for it" is one sale)."""
    s = _words(span)
    if not s.strip():
        return []
    out = []
    for i, p in enumerate(parts):
        w = _words(p)
        if w.strip() and (w in s or s in w):
            out.append(i)
    return out


# The quick deeds a turn holds (the owner's ruling of 2026-11-06: "up to two").
QUICK_PER_TURN = 2


def within_budget(parts: list[str], actions: list[dict], cost) -> tuple | None:
    """Where the turn's budget ends a line of several clauses: `(now, later, why)`, the
    clauses done this turn and the ones left for the pen, or None when the whole line
    runs as it always did.

    The owner's ruling, 2026-11-06: outside a fight a line may hold several deeds, but
    "once a limit of actions has been hit the world doesnt stand still it moves as well".
    Moving about is free; a turn holds up to two quick deeds; the turn ends at once after a
    deed that takes time, or after words to somebody here who would answer, so they reply
    first. His example: "I run to the other side of the room and begin cooking dinner then
    i serve the food i made to everyone" runs (free), starts the cooking (takes time: the
    turn ends there), and "serve the food" goes back to the pen.

    `actions` is the reader's frame in the order of doing, `cost(action)` its cost
    (`interpret.cost_of`, with the scene). Each action is placed at the clauses its span
    lies across (`clauses_of`). The cut falls between clauses, or — when the first deed
    left over shares a clause with the last deed done — inside that clause, at the start
    of the left-over deed's own span (`_split_at_span`), and only when a deed the reader
    read lies wholly after it, so nothing is put back that the reader did not read as a
    deed. Any action that cannot be placed, and a cost not in the four, leave the line
    whole: the turn as it was before the budget, never a guess. Inform's chain runs
    commands one at a time (gm/sequence.py's docstring); this decides how many of them are
    this turn's.

    The cut inside a clause, measured in the live check of 2026-11-07: `clauses` joins
    only where a verb it knows starts, so "drink the ale and wipe my mouth", "read the note
    and burn it" and "take the knife, pocket the ring" were one clause each, and a third
    quick deed sharing a clause with the second ran with it — "I light the lamp, read the
    note and burn it" burned the note, and "I look around, take the knife, pocket the ring
    and leave" pocketed the ring and walked Kesst to the town gate. The reader already
    marks where each deed's words are (`span`); a list of verbs long enough to split every
    line would be a regex deciding what a sentence means, which this project does not
    add. The returned clauses are the line's own words, cut at a word's start: the pen
    gets back exactly what the player wrote from that deed on."""
    placed = []
    for a in actions or ():
        c = cost(a)
        where = clauses_of(a.get("span"), parts)
        if not where:
            if c == "free":
                continue
            return None
        placed.append((c, min(where), max(where), a))

    quick, done_to, cut, why, stop = 0, -1, None, "", None
    for k, (c, first, last, _a) in enumerate(placed):
        if c == "quick":
            if quick == QUICK_PER_TURN:
                cut, why, stop = first, "quick", k
                break
            quick += 1
        elif c not in ("free", "takes_time", "addresses"):
            return None
        done_to = max(done_to, last)
        if c in ("takes_time", "addresses"):
            cut, why, stop = done_to + 1, c, k + 1
            break
    if stop is None or stop >= len(placed):
        return None
    # The first deed left over shares a clause with one done: cut inside it, at its span.
    if placed[stop][1] <= done_to:
        split = _split_at_span(parts, placed, stop, done_to)
        if split is not None:
            return split[0], split[1], why
    # Else between clauses, as before: never a deed held back from a clause it shares.
    if cut is None or cut <= done_to or cut >= len(parts):
        return None
    if not any(first >= cut for _c, first, _l, _a in placed):
        return None
    return parts[:cut], parts[cut:], why


def _span_at(span, clause: str, after: int = 0) -> tuple[int, int] | None:
    """Where a span's words stand in a clause, word for word (as `said_in` compares, case
    and punctuation aside): `(start, end)` in the clause's characters, the first match
    starting at or after `after`, or None."""
    want = [w.lower() for w in re.findall(r"[\w']+", str(span or ""))]
    words = [(m.start(), m.end(), m.group(0).lower())
             for m in re.finditer(r"[\w']+", clause)]
    n = len(want)
    if not n:
        return None
    for i in range(len(words) - n + 1):
        if words[i][0] >= after and [w for _s, _e, w in words[i:i + n]] == want:
            return words[i][0], words[i + n - 1][1]
    return None


# What joined the head of a cut clause to the deed cut off it: "read the note and | burn
# it", "take the knife, | pocket the ring". Only the joins `_JOIN` and `_THEN` split at.
_TRAILING_JOIN = re.compile(r"(?:[\s,;]+(?:and\s+then|and|then))*[\s,;]*$", re.I)


def _split_at_span(parts: list[str], placed: list, stop: int, at: int):
    """`(now, later)`: the clauses with clause `at` cut at the start of deed `stop`'s span,
    or None when that cannot be done cleanly — the left-over deed or a done one in that
    clause runs across clauses or is not found word for word, a done deed's words run past
    the cut, a later deed's start before it, the cut falls inside a quotation, or either
    side is left with no words. None leaves the cut to the clause boundaries."""
    from . import speech

    clause = parts[at]
    if placed[stop][1] != at or placed[stop][2] != at:
        return None
    end = 0
    for k in range(stop):
        _c, first, last, a = placed[k]
        if last < at:
            continue
        if first != at or last != at:
            return None
        got = _span_at(a.get("span"), clause, end)
        if got is None:
            return None
        end = got[1]
    got = _span_at(placed[stop][3].get("span"), clause, end)
    if got is None:
        return None
    cut = got[0]
    for _c, first, last, a in placed[stop + 1:]:
        if first == last == at:
            later = _span_at(a.get("span"), clause)
            if later is not None and later[0] < cut:
                return None
    if any(a < cut < b for a, b in speech.spans(clause)):
        return None
    head = _TRAILING_JOIN.sub("", clause[:cut])
    tail = clause[cut:].strip()
    if not _tidy(head) or not _tidy(tail) or not re.search(r"\w", head):
        return None
    return parts[:at] + [head], [tail] + parts[at + 1:]


def only_going(clause: str) -> bool:
    """A clause that is the move and nothing else a verb could carry: "I slip out
    quietly", "I run for it". Used with the declared ops, not instead of them."""
    return bool(_MOVES.search(clause))
