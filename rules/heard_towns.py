"""Towns heard of: a settlement somebody named aloud, known from then on (place map v2, phase 5).

The owner's decision 7 of 2026-11-18 (docs/place-map-v2-build-plan.md): a town is heard of
from what an NPC SAYS only, the rule `heard_places` already keeps inside a town. Notices,
books and narration don't count. The beat reader's places call reads the names a speaker
says (gm/beat_reader.py, "towns"); this module is the closed list they are checked against
and the record they are kept in. Models read, code validates (owner, 2026-10-03): a name
counts only when it IS one of the world's settlements, give or take case and a leading
"the", so a made-up town cannot be learned.

What is kept is Inform's *familiar* state for a whole settlement (Eric Eve's Epistemology,
the Recipe Book §5.5), the World map's "heard" pin: who said it, their line, the turn. It
only grows; the first telling is the one kept (NetHack 3.7 took map amnesia out because a
player just writes the map down, and places_found.py cites the same refusal).
"""
from __future__ import annotations

import re


def _key(name: str) -> str:
    words = " ".join(re.findall(r"[a-z0-9'’]+", str(name or "").lower().replace("’", "'")))
    return re.sub(r"^the ", "", words)


def names(world) -> dict[str, str]:
    """Every settlement of the world by its name's key: {key: settlement id}."""
    if world is None:
        return {}
    cached = getattr(world, "_heard_town_names", None)
    if cached is not None:
        return cached
    out: dict[str, str] = {}
    for row in (getattr(world, "play", None) or {}).get("settlements") or []:
        e = world.get(row.get("id"))
        if e is not None and _key(e.name):
            out.setdefault(_key(e.name), e.id)
    try:
        world._heard_town_names = out
    except AttributeError:   # a world that refuses new attributes is read every time
        pass
    return out


def match(world, words: str) -> str:
    """The settlement `words` name, exactly (case, spacing, punctuation and a leading "the"
    aside), or ""."""
    return names(world).get(_key(words), "")


def record(scene, city: str, *, who: str = "", said_by: str = "", line: str = "",
           turn: int = 0) -> dict:
    """Keep the first telling of `city` on the scene; returns the new record, or {} when the
    town was already heard of (or is unnamed)."""
    held = getattr(scene, "heard_towns", None)
    if held is None or not city or city in held:
        return {}
    held[city] = {"who": str(who or ""), "from": str(said_by or ""),
                  "line": " ".join(str(line or "").split())[:200], "turn": int(turn or 0)}
    return held[city]
