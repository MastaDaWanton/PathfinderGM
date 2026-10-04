"""A place a person names that this settlement does not have is written down as heard of —
as the beat reader read it (gm/beat_reader.py, the "places" call).

Measured on the owner's items save (docs/playtest-2026-10-03.md): the clerk said "make your
exit through the side door, past the smithy", the docks man spoke of "the western
warehouses", and nothing recorded either; the smithy was later founded off wherever the
planner could reach once a travel to it had been refused. The owner's ruling of the same
day keeps places creatable (people's houses above all), so the fix is the missing middle
state: heard of, with the speaker's landmark, made real on the first visit
(`rules/heard_places.py`, `judgement.go_to_heard_place`).

**Read by the reader, not by `heard_places.heard_in`.** The pattern reader that first did
this recorded "'The Forge of the Broken Tide,' … 'Follow the main quay until you hit the
turn for the wharf … sitting in the back of the smithy'" as TWO places, neither with a
landmark, the same day it was written. The reader answers which places a speaker named
that the town lacks, the same place told of twice as one ("same as"), a kind from the
settlement table's own vocabulary, and a landmark from this town's own place names; code
checks the words are the speaker's own and the place is not on the map already.

Only NPC speakers: the narration describing a place is not somebody telling the player of
one (the reader is shown NPC lines only). No reading records nothing.
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 22


def step(ctx) -> list[dict]:
    from gm import beat_reader
    from rules import heard_places

    reading = ctx.attribution
    scene = ctx.scene
    if scene is None or getattr(scene, "heard_places", None) is None:
        return []
    if not isinstance(reading, beat_reader.Reading) or not reading.places_read:
        if isinstance(reading, beat_reader.Reading) and reading.read and reading.error:
            return [reading.unread_row("places_heard")]
        return []
    lines = {ln.id: ln for ln in reading.lines}
    rows: list[dict] = []
    for p in reading.places:
        said_by = _ref(reading, p.said_by)
        ln = lines.get(p.line)
        kept = heard_places.record(scene, {"name": p.words, "kind": p.kind,
                                           "landmark": p.landmark},
                                   said_by=said_by, line=ln.words if ln else "",
                                   turn=int(ctx.turn or 0))
        if kept:
            rows.append({"kind": "heard-of-place", "name": kept["name"],
                         "kind_of_place": kept.get("kind", ""),
                         "landmark": kept.get("landmark", ""), "from": said_by})
    return rows


def _ref(reading, who: str) -> str:
    n = reading.newcomer(who)
    return (n.ref if n is not None else who) or ""
