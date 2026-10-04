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

# How a place comes to be heard of is the beat reader's answer since 2026-10-03
# (gm/beat_reader.py, the "places" call; play/aftermath/places_heard.py applies it). This
# module read it itself until then — `heard_in`, a pattern for "<article> <describing
# words> <a place word>", a tie pattern for its landmark ("past", "by", "behind" …), a
# "side door" pattern for the speaker's own place, a possessive pattern for somebody's
# house — and the day it was written it recorded "The Forge of the Broken Tide" and "the
# back of the smithy" as two places with no landmark, though the speaker had said "follow
# the main quay … the wharf". What stays here is the record and its readers, which hold
# structure only: a name, a kind from the vocabulary, a landmark place id.


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
