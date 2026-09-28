"""ROADS OUT: the settlements a journey from here can reach.

Moved out of `prompts.scene_brief` unchanged (fix pass S2, docs/fix-interfaces.md §2.2);
Lane B rewrites it over `geography.roads_out` in Phase 2 (docs/design-b-space.md, 17.4).
"""
from __future__ import annotations

ORDER = 20
SLOT = "place"
SCAFFOLD = (
    "ROADS OUT OF",
    "(the only settlements that can be reached, and only by journey, which takes days):",
)


def section(ctx) -> tuple[str, dict]:
    # And the roads out. Named for the same reason the places are: a model told only
    # about the room it is in reconstructs the rest of the world from earlier beats,
    # and "we set out for Zhilgoroth" is refused if Zhilgoroth has no road. The
    # engine is the one that says how long it takes; this only says where is
    # reachable at all.
    location, world = ctx.location, ctx.world
    if not location or world is None:
        return "", {}
    from rules import journey as _journey

    out = _journey.legs_from(world, getattr(location, "id", "") or "")
    if not out:
        return "", {}
    text = (f"  ROADS OUT OF {location.name.upper()} (the only settlements that "
            f"can be reached, and only by journey, which takes days): "
            f"{', '.join(leg.to_name for leg in out)}.")
    return text, {"roads": [leg.to_name for leg in out],
                  "to_ids": [leg.to_id for leg in out]}
