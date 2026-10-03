"""Places heard of: a place a person names that the settlement does not have yet.

The owner's ruling of 2026-10-03: places must be creatable — people's houses, the smithy
behind the counting house — and a fixed map is ruled out. What was missing was the step
between hearing of a place and standing in it. In the items save the clerk said "make your
exit through the side door, past the smithy"; nothing wrote the smithy down, and when the
player headed for the side door the planner, refused a travel to a place that did not
exist, founded *the smithy* off wherever it could and walked the player in
(docs/playtest-2026-10-03.md, item 9). The docks man's "the western warehouses" was never
recorded at all, and his "at the docks" was lost by the time anybody went looking.

The traditions agree on three states, not two. Inform's Epistemology extension (Eric Eve;
Recipe Book §5.5) gives every thing *seen* and *familiar* — familiar being known about
"for other reasons", heard of but not found. Skyrim draws a place an NPC has told you of
as a grey marker you cannot fast-travel to until you have been there. Morrowind keeps no
marker at all and writes the speaker's directions into the journal, relative to landmarks
the player already knows. This module is the familiar state, with Morrowind's directions:

  * **recorded** from an NPC's own line, never the narration's — a person telling the
    player about a place is the source, the way `play/aftermath/mentioned_elsewhere.py`
    records a person an NPC places somewhere;
  * **only what the settlement lacks**: a place `places.find` already answers is on the
    map, and nothing is recorded for it;
  * **with the landmark the speaker gave**, when the line ties it to one of this
    settlement's real places ("the warehouse by the docks", "the smithy past the counting
    house"), or to where the speaker stands ("through the side door", "out back");
  * **made real on the first visit**, through the one door that makes places
    (`Engine.found`, via `judgement.go_to_heard_place`), under that landmark.

A person's house is not recorded here: "Marra's house" and "the house of the clerk" are
`call_on`'s, which founds a house the first time anybody calls and knows whose it is. A
bare "a house three streets over" is a place like any other.

Records are plain dicts on `Scene.heard_places`, saved with the scene; nothing derives
them, because a conversation made them. Each holds the name as said, its kind (a
`places.KINDS` / `DWELLINGS` kind or ""), the landmark place id (or ""), who said it, the
line, the settlement, and the turn.
"""
from __future__ import annotations

import re

# How many places one settlement may hold as heard of. A town's talk names a great many
# places; a list the planner is shown has to stay short enough to choose from (the
# ceiling every other place list here keeps).
MOST_HEARD = 8

# The words a place is headed by: the settlement kinds, the words people say for them
# (`places.KIND_WORDS`), and the handful of rooms and premises no table draws.
_EXTRA_HEADS = ("office", "offices", "yard", "forge", "workshop", "stall", "cellar", "loft",
                "hall", "house", "home", "storehouse", "boathouse", "counting room",
                "chandlery", "apothecary", "bakery", "butchery", "kennels", "pens",
                "lodge", "hideout", "den", "camp", "tower", "manor", "estate", "farm")


def _heads() -> tuple[str, ...]:
    from . import places as places_mod

    words = set(places_mod.KINDS) | set(places_mod.KIND_WORDS) | set(_EXTRA_HEADS)
    words -= {"way in", "green", "lane", "gate", "well", "bridge", "back streets", "rooms",
              "flat", "bar", "ring", "store", "keep", "end"}
    return tuple(sorted(words, key=len, reverse=True))


_DET = r"(?:the|a|an|that|this|old|their|his|her)"
# Prepositions that tie a place to a landmark: "the smithy past the counting house", "the
# warehouse by the docks". `in`/`at` too: "the office at the docks".
_TIE = (r"(?:(?:out|just|right|down|up|over)\s+)?(?:past|behind|beside|by|near|next\s+to|"
        r"off|across\s+from|opposite|beyond|at|in|on|along|round|around|outside|under|"
        r"above|below)")
# Where the speaker stands, said without naming it: through a door of this building, next
# door, out back, round the back.
_HERE = re.compile(r"\b(?:side|back|rear|other)\s+door\b|\bnext\s+door\b|\bout\s+back\b|"
                   r"\bround\s+the\s+back\b|\bthrough\s+the\s+(?:yard|courtyard|kitchen)\b|"
                   r"\bbehind\s+(?:this|here|us)\b|\bacross\s+the\s+(?:street|way|lane)\b",
                   re.I)
# A person's house — `call_on`'s, never this module's.
_SOMEBODYS = re.compile(r"(?:'s|’s)\s+(?:house|home|cottage|place|rooms|lodgings)\b|"
                        r"\bthe\s+(?:house|home)\s+of\b", re.I)


def _phrases(line: str) -> list[tuple[int, int, str, str]]:
    """(start, end, phrase, head) for every place phrase the line holds."""
    heads = "|".join(re.escape(h).replace(r"\ ", r"\s+") for h in _heads())
    # The words between the article and the head describe it ("the western warehouses");
    # a function word among them means the phrase runs through somebody else first — "the
    # master of the docks" is a man, and "the docks" is read on its own.
    word = r"(?!(?:of|the|a|an|and|or|to|in|at|by|for|from|with|on|who|that)\b)[a-z'’-]+"
    rx = re.compile(rf"\b{_DET}\s+(?:{word}\s+){{0,3}}?(?P<head>{heads})\b(?!['’]s)",
                    re.I)
    out = []
    for m in rx.finditer(str(line or "")):
        phrase = " ".join(m.group(0).split())
        out.append((m.start(), m.end(), phrase, " ".join(m.group("head").lower().split())))
    return out


def _the(phrase: str) -> str:
    """"the smithy" for "the smithy", "a smithy", "that smithy", "his workshop"."""
    words = phrase.split()
    if words and words[0].lower() in ("a", "an", "that", "this", "his", "her", "their"):
        words[0] = "the"
    return " ".join(words)


def _kind_of(head: str) -> str:
    from . import places as places_mod

    k = places_mod.kind_named(head)
    return k if places_mod.known_kind(k) else ""


def heard_in(line: str, known, here_id: str = "") -> list[dict]:
    """The places one NPC line names that `known` (this settlement's places) does not
    have, each with its landmark: [{"name", "kind", "landmark"}]."""
    from . import places as places_mod

    line = str(line or "")
    if not line.strip():
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for start, end, phrase, head in _phrases(line):
        name = _whose(line, start, phrase) or _the(phrase)
        if _SOMEBODYS.search(line[start:end + 8]):
            continue                       # somebody's house: call_on's
        if places_mod.find(known, name) is not None or \
                places_mod.find(known, head) is not None and name.lower() == f"the {head}":
            continue                       # on the map already
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        # The landmark: a real place this line ties it to, right after it ("the smithy
        # past the counting house"); else "through the side door" and its kind — here.
        landmark = ""
        tail = line[end:end + 80]
        m = re.match(rf"\s*,?\s*{_TIE}\s+(?P<rest>[^.!?;]+)", tail, re.I)
        if m:
            spot = _place_at(m.group("rest"), known)
            if spot is not None:
                landmark = spot.id
        if not landmark:
            before = line[max(0, start - 60):start]
            m = re.search(rf"{_TIE}\s+(?P<rest>[^.!?;]+?)\s*,?\s*(?:past|to|toward|towards|"
                          rf"and)?\s*$", before, re.I)
            spot = _place_at(m.group("rest"), known) if m else None
            if spot is not None:
                landmark = spot.id
        sentence = _sentence_around(line, start)
        if not landmark and here_id and _HERE.search(sentence):
            landmark = here_id
        out.append({"name": name, "kind": _kind_of(head), "landmark": landmark})
    return out


def _whose(line: str, start: int, phrase: str) -> str:
    """"his office" after "the harbourmaster" is "the harbourmaster's office": a place
    called by its holder's pronoun takes the holder the sentence named before it, so two
    offices in one town are two places. "" when the phrase has no pronoun or nobody
    stands before it."""
    words = phrase.split()
    if not words or words[0].lower() not in ("his", "her", "their"):
        return ""
    before = _sentence_around(line, start)[:max(0, start - _sentence_start(line, start))]
    heads = set(_heads())
    holders = [m.group(1) for m in re.finditer(r"\bthe\s+([a-z][a-z'’-]{2,})\b", before, re.I)
               if m.group(1).lower() not in heads]
    if not holders:
        return ""
    return f"the {holders[-1].lower()}'s " + " ".join(words[1:])


def _sentence_start(line: str, at: int) -> int:
    return max(line.rfind(".", 0, at), line.rfind("!", 0, at), line.rfind("?", 0, at)) + 1


def _sentence_around(line: str, at: int) -> str:
    a = max(line.rfind(".", 0, at), line.rfind("!", 0, at), line.rfind("?", 0, at)) + 1
    ends = [i for i in (line.find(".", at), line.find("!", at), line.find("?", at)) if i >= 0]
    return line[a:min(ends) + 1 if ends else len(line)]


def _place_at(rest: str, known):
    """The settlement place `rest` opens with, longest name first, or None."""
    low = " ".join(str(rest or "").lower().split())
    best = None
    for p in known or ():
        name = " ".join(str(p.name).lower().split())
        bare = re.sub(r"^the\s+", "", name)
        for n in {name, bare, "the " + bare}:
            if n and re.match(rf"{re.escape(n)}(?![\w-])", low):
                if best is None or len(p.name) > len(best.name):
                    best = p
    return best


def record(scene, rec: dict, *, said_by: str = "", line: str = "", turn: int = 0) -> dict:
    """Keep `rec` on the scene, once per name per settlement; the kept record. A second
    mention with a landmark the first lacked gives it the landmark."""
    loc = str(getattr(scene, "location_id", "") or "")
    held = getattr(scene, "heard_places", None)
    if held is None:
        return {}
    for old in held:
        if old.get("location") == loc and old.get("name", "").lower() == rec["name"].lower():
            if rec.get("landmark") and not old.get("landmark"):
                old["landmark"] = rec["landmark"]
            return old
    mine = [h for h in held if h.get("location") == loc]
    if len(mine) >= MOST_HEARD:
        held.remove(mine[0])               # the oldest of this town goes
    new = {"name": rec["name"], "kind": rec.get("kind", ""),
           "landmark": rec.get("landmark", ""), "from": str(said_by or ""),
           "line": " ".join(str(line or "").split())[:200], "location": loc,
           "turn": int(turn or 0)}
    held.append(new)
    return new


def of_here(scene, known=()) -> list[dict]:
    """This settlement's heard-of places that are not yet places — the ones still to be
    found. A name `known` now answers has been visited (founded) and is left out."""
    from . import places as places_mod

    loc = str(getattr(scene, "location_id", "") or "")
    return [h for h in (getattr(scene, "heard_places", None) or [])
            if h.get("location") == loc and places_mod.find(known, h["name"]) is None]


def named_in(text: str, scene, known=()) -> dict | None:
    """The heard-of place `text` names, longest name first, or None. Read on the name's
    words without its article: "I go to the western warehouses", "head for that smithy"."""
    low = " ".join(str(text or "").lower().split())
    best = None
    for h in of_here(scene, known):
        core = re.sub(r"^the\s+", "", h["name"].lower())
        if core and re.search(rf"(?<![\w'’]){re.escape(core)}(?![\w'’])", low):
            if best is None or len(h["name"]) > len(best["name"]):
                best = h
    return best
