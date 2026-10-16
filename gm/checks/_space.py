"""Lane B's shared readings for the four space checks — a helper, not a check.

`land_described`, `bearing_invented`, `road_claimed` and `route_walked` all read the same
three things: the beat's sentences, what the engine's move outcomes say happened, and the
land and roads around the settlement as the brief printed them. Written once here, so the
four cannot drift into four readings of one outcome (CLAUDE.md: when you fix a rule, grep
for every copy of it).
"""
from __future__ import annotations

import re


def sentences(text: str) -> list[str]:
    from gm import narration

    return narration._sentences(text)


def field(obj, name: str, default=None):
    """An Outcome's field, or a recorded outcome dict's key — the checks read both: the
    live beat hands them Outcomes, the replay corpus hands them dicts."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def effects(ctx, op: str, kind: str = "") -> list[dict]:
    """Every effect of this op this beat that happened (refusals carry no move)."""
    out = []
    for o in ctx.outcomes or ():
        if field(o, "op") != op or field(o, "status") == "refused":
            continue
        for e in field(o, "effects", None) or []:
            if isinstance(e, dict) and (not kind or e.get("kind") == kind):
                out.append(e)
    return out


def journeyed(ctx) -> bool:
    return bool(effects(ctx, "journey", "journey"))


def reading_acts(ctx) -> set[str]:
    return {a.get("act") for a in (ctx.reading or {}).get("actions") or []
            if isinstance(a, dict)}


# Quoted speech is a person talking, not the narrator claiming: "the road to Grotburrow
# isn't for the faint of heart", said by a stranger, is his opinion of a road — and a road
# named in an answer is never a position claim (owner, 2026-10-16).
#
# Read by `gm.speech`, the one reader of quotations. This module had its own regex, whose
# single-quote branch stopped at the first apostrophe: 'The road north isn't safe' was not
# speech to it, so a guard's answer about a road was read as the narrator putting the party
# on that road, and the repair garbled the answer (planned-narration bench, 2026-10-16).
def unquoted(sentence: str) -> str:
    from gm import speech

    return speech.unquoted(str(sentence or ""))


def settlement(ctx):
    location = ctx.location
    if location is None and ctx.world is not None and getattr(ctx.scene, "location_id", ""):
        location = ctx.world.get(ctx.scene.location_id)
    return location


def land(ctx):
    """The Land around the settlement, or None — never for a wild site."""
    from rules import geography, places

    location = settlement(ctx)
    if location is None or ctx.world is None or not places._settled(location, ""):
        return None
    got = geography.land_around(ctx.world, location)
    return None if got.source == "unknown" else got


def roads(ctx):
    from rules import geography

    location = settlement(ctx)
    if location is None or ctx.world is None:
        return ()
    return geography.roads_out(ctx.world, location)


def here_setting(ctx) -> str:
    from rules import places

    return places.setting_of(str(getattr(ctx.scene, "at", "") or ""))


_WORD = re.compile(r"[a-z][a-z'-]*")


def words(text: str) -> list[str]:
    return _WORD.findall(str(text or "").lower())
