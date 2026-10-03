"""A place a person names that this settlement does not have is written down as heard of.

The companion to `mentioned_elsewhere.py`, which does the same for a person an NPC places
somewhere. Measured on the owner's items save (docs/playtest-2026-10-03.md): the clerk
said "make your exit through the side door, past the smithy", the docks man spoke of "the
western warehouses", and nothing recorded either; the smithy was later founded off
wherever the planner could reach once a travel to it had been refused. The owner's ruling
of the same day keeps places creatable (people's houses above all), so the fix is not a
fixed map but the missing middle state: heard of, with the speaker's landmark, made real
on the first visit (`rules/heard_places.py`, `judgement.go_to_heard_place`).

Read over the beat's kept `said` records from NPC speakers only — the narration describing
a place is not somebody telling the player of one — against the engine's places for this
settlement, so nothing already on the map is recorded twice.
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 22


def step(ctx) -> list[dict]:
    from rules import heard_places

    scene = ctx.scene
    if scene is None or not ctx.said or getattr(scene, "heard_places", None) is None:
        return []
    try:
        engine = ctx.campaign.engine()
        known = tuple(engine.places()) + tuple(engine.open_ground())
    except Exception:  # noqa: BLE001 — no places to read, nothing to compare against
        return []
    if not known:
        return []
    people = getattr(scene, "people", None) or getattr(scene, "actors", {}) or {}
    here = str(getattr(scene, "at", "") or "")
    rows: list[dict] = []
    for rec in ctx.said:
        who = str(rec.get("who") or "")
        speaker = people.get(who)
        if not who or who == "you" or speaker is None or getattr(speaker, "is_pc", False):
            continue
        # Where the speaker stands is "here" for "through the side door"; they are in the
        # scene, so that is where the party is.
        for found in heard_places.heard_in(str(rec.get("line") or ""), known, here):
            kept = heard_places.record(scene, found, said_by=who,
                                       line=str(rec.get("line") or ""),
                                       turn=int(ctx.turn or 0))
            if kept:
                rows.append({"kind": "heard-of-place", "name": kept["name"],
                             "landmark": kept.get("landmark", ""), "from": who})
    return rows
