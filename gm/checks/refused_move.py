"""A move the engine refused, narrated as a move that happened (item 17.5).

Measured on the Bobby playtest, 2026-09-28. "I walk to the nearest crossroads" and "I
take the path away from town": `found` and `travel` were refused both times, the party
stood at the way in both times, and the page said "You are standing where the paths
diverge" and "You are now on the outskirts". The only check that fired caught the word
"gate". Every later turn resolves from where the engine holds the party, so a page that
moves them anyway is wrong for the rest of the session — the highest-priority truth check.

Inform's order is the model (WI §12.2, §12.9): a check that fails says why and stops the
action, and the report rule that describes a move is never reached. Here the report is a
model's prose, so it is reached, and this check is the stop: detect the move claim in
code, ask for one rewrite of those sentences with the refusal named, and, if the rewrite
still moves the player, cut the beat from the first move claim and let the refusal's own
sentence stand (`hold_the_door`'s shape).

What counts as a claim is the second person being put somewhere: "you are (now) on / at /
in / standing where…", "you reach / arrive / emerge", "you walk / head / set off / turn
your back on…". Only the verb immediately after "you", so "you could walk", "you will
reach" and "you do not reach" are never claims; a question is never one. A phrase naming
the place the party is actually in is no displacement. World-agnostic: the only place
names read are the engine's own `here()` and what it is (`places.words_for_here`).

**Leaving is a move, and moving inside the place is not** (the owner's save, 2026-10-01).
The walk to "the house 3 streets over" was refused and the page read "You leave the
Velvet Veil, … You move through the town … Each street takes you further from the
tavern", then "You reach the destination". The first cut of this check read "you leave
the Velvet Veil" as naming where the party is — so not a displacement — and had no
`move`; the first claim it found was the arrival, five sentences in, so the backstop cut
there and appended "You are still at the Velvet Veil." after a walk out of it. Leaving
here, and stepping out into the street, are now claims, and the cut lands on the first.

The other half is the same rule from the inside. Inform's world model is the authority
here: only `going` changes the room the player is in, and the things inside a room —
the bar, a table, the stairs, a supporter or container — are reached without leaving it.
So "you move to the bar", "you reach the top of the stairs", "you are at the counter",
"you walk toward her" and "you step into the Velvet Veil" (when that is where the party
stands, or what it is — the chamber is in the Velvet Veil, which is a tavern) are no
displacement. Precision over recall: a door, a gate and a threshold are left out of the
inside words, because "you stand before the door" was, in that same save, the door of a
house three streets away.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import field, here_name, moved, page_sentences, refused_moves

ORDER = 10
KINDS = frozenset({"refused-move-shown-as-moved"})
DOORS = frozenset({"plan", "turn"})

# Somewhere is being stood in. The complement must open like a place — a determiner or
# "where" — so "you are in no hurry" and "you are at ease" are not places. `out` before
# the preposition is the street outside ("You stand out in the cooling evening" — the
# owner's save, the rewrite of "You step out into the cooling evening" that slipped the
# first cut of this pattern).
_POSITION = re.compile(
    r"\byou(?:'re|\s+are|\s+stand|\s+find\s+yourself|\s+now\s+stand)\s+"
    r"(?:now\s+|finally\s+|already\s+|still\s+)?(?:standing\s+|waiting\s+|left\s+)?"
    r"(?P<out>out\s+|back\s+out\s+)?"
    r"(?P<prep>on|at|in|inside|outside|beyond|among|upon|near|before|where)\b"
    r"(?P<rest>[^.!?;]*)", re.I)
_PLACE_OPENS = re.compile(r"^\s*(?:the|a|an|this|that|these|those)\b", re.I)
# Not places, though they open like one: states and stances.
_NOT_A_PLACE = re.compile(
    r"^\s*(?:the|a|an|this|that)\s+(?:\w+\s+)?(?:way|mood|hurry|position|state|debt|"
    r"trouble|danger|luck|charge|doubt|moment|middle\s+of\s+(?:a|the)\s+(?:conversation|"
    r"sentence|thought)|presence|company|care|habit|dark\s+about)\b", re.I)
_ARRIVE = re.compile(
    r"\byou\s+(?:finally\s+|soon\s+|at\s+last\s+)?(?P<verb>reach(?!\s+(?:out|for|into|"
    r"up|down|across|over|behind|toward|towards|under|inside|around|through|past|back|"
    r"in)\b)|arrive|emerge|step\s+out|"
    r"come\s+out|come\s+to\s+(?:a|the)\s+(?:stop|halt)\s+(?:at|beside|before))\b"
    r"(?P<rest>[^.!?;]*)", re.I)
_LEAVE = re.compile(
    r"\byou\s+(?:walk|head|set\s+off|set\s+out|make\s+your\s+way|leave|stride|move|"
    r"strike\s+out|start\s+down|follow\s+the\s+(?:road|path|track|lane)|"
    r"turn\s+your\s+back\s+(?:on|to))\b(?P<rest>[^.!?;]*)", re.I)
# A door closing behind the player is the player having gone through it. The owner's
# save, the second refused walk to the house: the beat opened "The heavy door of the
# Velvet Veil thuds shut behind you, cutting off the low hum of the crowd" — and only
# ever reaches this check on a turn whose move was refused, when no door was gone through.
_DOOR_BEHIND = re.compile(
    r"\b(?:door|doors|gate|gates)\b[^.!?;]*?\b(?:shut|shuts|closes|closed|slams|bangs|"
    r"swings\s+to|falls\s+to)\b[^.!?;]*?\bbehind\s+you\b", re.I)
_DIRECTIONAL = re.compile(
    r"\b(?:toward|towards|to|into|out|away|along|down|up|past|beyond|through|north|"
    r"south|east|west|behind|off|across|onto)\b", re.I)

# Words that put the player OUT of wherever they were: the street, the town around it.
# Grammar's nouns for "outside", not place names — every settlement has streets.
_OUTWARD = re.compile(
    r"\b(?:out|outside|street|streets|town|city|village|district|quarter|road|roads|"
    r"lane|lanes|alley|alleys|alleyway|thoroughfare|night|evening|outskirts)\b", re.I)
# What a place has inside it. Reaching one is not leaving the place (Inform: the things
# in a room are entered, sat on and walked to without `going`). A door, a gate and a
# threshold are deliberately NOT here — see the module docstring.
_INSIDE = re.compile(
    r"^\s*(?:the|a|an|this|that|her|his|their|its|your)?\s*(?:\w+\s+){0,2}?"
    r"(?:room|foyer|hall|hallway|corridor|stairs|staircase|stairwell|steps|landing|"
    r"corner|bar|counter|hearth|fire|fireplace|table|tables|booth|bench|benches|window|"
    r"windows|alcove|nook|back|front|far\s+end|end|rail|stall|stalls|curtain|shelf|"
    r"shelves|chair|seat|stool|crowd|cage|ring|pit|light|shadow|shadows|cart|crates|"
    r"wall|walls|middle|centre|center|side|top|bottom|edge|bed|fireside|area|spot)\b",
    re.I)
# Somebody, not somewhere: "you walk toward her", "you move to the woman's side".
_SOMEBODY = re.compile(
    r"^\s*(?:her|him|them|the\s+(?:\w+\s+)?(?:man|woman|men|women|girl|boy|figure|"
    r"stranger|keeper|barkeep|guard|guards|child|old\s+man|old\s+woman|person|people|"
    r"others?))\b", re.I)
# Where the object of "leave" / "turn your back on" ends: a comma, a conjunction, a
# preposition that starts a new phrase, or a participle ("the woman's words hanging in
# the smoke of the tavern" is words, not a tavern). "of" is kept: "the heavy doors of the
# Velvet Veil" is the Velvet Veil.
_OBJECT_ENDS = re.compile(
    r"[,;:—–]|\s(?:as|and|while|when|but|to|toward|towards|into|behind|for|with|in|on|"
    r"at|so|then)\b|\s\w+ing\b", re.I)
# What a departure has to be leaving for it to be a move: a building or the ground.
_A_PLACE_NOUN = re.compile(
    r"\b(?:room|building|house|home|hall|place|tavern|inn|shop|chamber|establishment|"
    r"premises|warmth|safety|square|yard|market|gate|crossing|camp)\b", re.I)


def _words(here) -> tuple[str, ...]:
    """`here` as the tuple of words that name it: a bare name, or `words_for_here`."""
    if isinstance(here, str):
        here = (here,) if here else ()
    return tuple(" ".join(str(w).split()).lower().removeprefix("the ")
                 for w in (here or ()) if str(w).strip())


def _names_here(rest: str, here) -> bool:
    low = rest.lower()
    for name in _words(here):
        words = [w for w in re.findall(r"[a-z0-9']+", name)
                 if w not in ("the", "a", "an", "of")]
        if words and all(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            return True
    return False


def _leaves_here(rest: str, here) -> bool:
    """Whether the phrase goes out of / away from where the party is."""
    for name in _words(here):
        last = re.findall(r"[a-z0-9']+", name)
        if last and re.search(
                r"\b(?:out\s+of|away\s+from|from|beyond|behind|outside)\s+(?:the\s+)?"
                r"(?:[\w']+\s+){0,3}?" + re.escape(last[-1]) + r"\b", rest, re.I):
            return True
    return False


def _after_prep(rest: str) -> str:
    """The noun phrase after the first directional word: "toward the bar where…" → "the
    bar where…"."""
    m = _DIRECTIONAL.search(rest)
    return rest[m.end():] if m else rest


def _elsewhere(rest: str, here) -> bool:
    """Whether the phrase names the ground outside, or a place of the app's own
    vocabulary that is not this one — "through the crowd toward the gate" is going to the
    gate, crowd or no crowd."""
    from gm.narration import _place_words

    if _OUTWARD.search(rest):
        return True
    low, mine = rest.lower(), set(_words(here))
    return any(w not in mine and re.search(rf"\bthe\s+{re.escape(w)}\b", low)
               for w in _place_words(wild=False))


def _inside(rest: str, here, after_prep: bool = True) -> bool:
    """Whether the phrase is somewhere or somebody inside the place already."""
    head = _after_prep(rest) if after_prep else rest
    return (bool(_INSIDE.search(head) or _SOMEBODY.search(head))
            and not _elsewhere(rest, here))


def _object(rest: str) -> str:
    m = _OBJECT_ENDS.search(rest)
    return rest[:m.start()] if m else rest


# Where the place phrase after "you are at / you reach" ends — punctuation, a
# conjunction, a relative, a participle — so "at the way in, the tavern behind you" is
# the way in, not the tavern. Prepositions are kept: "the upper floor of the guildhall".
_PHRASE_ENDS = re.compile(
    r"[,;:—–]|\s(?:as|and|while|when|but|where|which|that|so|then|until)\b|\s\w+ing\b",
    re.I)


def _phrase(rest: str) -> str:
    m = _PHRASE_ENDS.search(rest)
    return rest[:m.start()] if m else rest


def _departs(rest: str, here) -> bool:
    """Whether what is being left ("you leave X", "you turn your back on X") is a place:
    here, a building, the ground outside, or nothing at all ("you leave.")."""
    obj = _object(rest)
    if not obj.strip():
        return True
    return bool(_names_here(obj, here) or _OUTWARD.search(obj)
                or _A_PLACE_NOUN.search(obj))


def here_words(source) -> tuple[str, ...]:
    """Every word for where the party is — the place's name, its kind, and the founded
    buildings it is inside (`places.words_for_here`, `outside=False`: the street a tavern
    opens off is somewhere else) — from a check context or an engine."""
    from rules import places as places_mod

    engine = getattr(source, "engine", source)
    try:
        here = engine.here()
        known = tuple(engine.places())
    except Exception:  # noqa: BLE001 — a check with no engine answer reads no place
        return ()
    return places_mod.words_for_here(here, known, outside=False)


def claims(narration: str, here) -> bool:
    """Whether one sentence of narration moves the player somewhere.

    `here` is the place's name, or every word for it (`here_words`)."""
    if "?" in narration:
        return False
    if _DOOR_BEHIND.search(narration):
        return True
    for m in _POSITION.finditer(narration):
        rest = m.group("rest")
        prep = m.group("prep").lower()
        if prep != "where" and (not _PLACE_OPENS.search(rest) or _NOT_A_PLACE.search(rest)):
            continue
        where = _phrase(rest)
        # Out in the street, or outside the very place they are in, is out of it.
        if m.group("out") or (prep in ("outside", "beyond") and _names_here(where, here)):
            return True
        if _names_here(where, here) or (prep != "where" and _inside(where, here, False)):
            continue
        return True
    for m in _ARRIVE.finditer(narration):
        rest, verb = m.group("rest"), " ".join(m.group("verb").lower().split())
        if verb in ("step out", "come out") and (
                re.match(r"\s*of\b", rest) or not re.match(r"\s*(?:into|onto|on|in)\b", rest)):
            return True                         # out of here, or simply out
        where = _phrase(rest)
        if _names_here(where, here) or _inside(where, here, False):
            continue
        return True
    for m in _LEAVE.finditer(narration):
        rest = m.group("rest")
        verb = m.group(0).lower()
        if re.search(r"\byou\s+leave\b", verb) or "turn your back" in verb:
            if _departs(rest, here):
                return True
            continue
        if not _DIRECTIONAL.search(rest):
            continue
        # Toward / into where they already are is no displacement; away from it, out of
        # it, is — read off the words right before the name, so "you walk into the
        # tavern, out of the rain" is still walking in.
        if _names_here(rest, here):
            if _leaves_here(rest, here):
                return True
            continue
        if _inside(rest, here):
            continue
        return True
    return False


def _applies(ctx) -> bool:
    if moved(ctx):
        return False
    if refused_moves(ctx):
        return True
    acts = (ctx.reading or {}).get("actions") or [] if isinstance(ctx.reading, dict) else []
    goes = [a for a in acts if isinstance(a, dict) and a.get("act") in ("go", "leave")]
    if not goes:
        return False
    # A walk across the room is not a journey nobody made. Measured live on the
    # 2026-10-03 batch: "I set the crate down on the ground and walk over toward the
    # anvil" read as `go: the anvil`, `keep_movement_in_the_scene` rightly planned no
    # travel, and with no move resolved this check took the reading's `go` for a refused
    # one — "You move toward the anvil" was cut and the beat ended "You are still at the
    # smithy." `_INSIDE`'s fixed list has no anvil, and no list ever will hold every
    # fitting of every room; the judge of "within the scene" is the one the planner
    # already used (`judgement.movement_within`), so the two cannot disagree about it.
    if all(a.get("act") == "go" for a in goes) and _moves_within(ctx):
        return False
    return True


def _moves_within(ctx) -> bool:
    """Whether the player's own words only move them within the place they stand in."""
    from gm.judgement import movement_within

    try:
        known = tuple(ctx.engine.places()) + tuple(ctx.engine.open_ground())
    except Exception:  # noqa: BLE001 — no engine answer, no judgement
        return False
    return bool(known) and bool(movement_within(ctx.player_text, known))


def refusal_words(ctx) -> str:
    """The refusal in words a player reads: the outcome's own `for_a_person` when the
    refusing rule wrote one. Today's refused-move tells are written for the planner
    ("The kinds are: arena, back streets…") and cannot stand on the page, so without one
    the sentence is the engine's plain fact: where the party still is."""
    for o in refused_moves(ctx):
        said = str(field(o, "for_a_person") or "").strip()
        if said:
            return said
    return ""


def find(ctx) -> list:
    if not _applies(ctx):
        return []
    here = here_name(ctx)
    words = here_words(ctx) or _words(here)
    flagged = [w for w, n in page_sentences(ctx.text) if claims(n, words)]
    if not flagged:
        return []
    why = refusal_words(ctx) or "nothing the engine resolved moved them"
    where = f"They are still at {here}." if here else "They are still where they were."
    return [Finding(
        "refused-move-shown-as-moved",
        f"the player did not move ({why}), and the prose moves them: {flagged[0][:90]!r}",
        f"The player did not move: {why}. {where} Rewrite the sentence so they are "
        f"still there — they may look, reach or want to go, but they have not gone.",
        weight=4, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut the beat from the first sentence that still moves the player — everything
    after it is a walk the engine never made — and end on the fact."""
    from ._page import cut_from

    here = here_name(ctx)
    words = here_words(ctx) or _words(here)
    first = next((w for w, n in page_sentences(text) if claims(n, words)), "")
    if not first:
        return text, []
    kept = cut_from(text, first)
    line = refusal_words(ctx) or (f"You are still at {here}." if here else "")
    if line:
        kept = f"{kept} {line}".strip()
    return kept, [f"refused move: cut the beat from {first[:60]!r}"]
