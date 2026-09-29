"""ROADS OUT: the settlements a journey from here can reach, with the world's own facts.

Moved out of `prompts.scene_brief` by S2 (docs/fix-interfaces.md §2.2) and rewritten by
Lane B over `geography.roads_out` (docs/design-b-space.md, items 17.4 and 19).

**What it cost to print names only.** The world knows each route's length, whether it is
a road or the sea, and what it crosses; the brief said "Dustgate, Grotburrow, Scrapden,
Ledgerwarren, Moldwarren" and nothing else. On 2026-09-28 the prose filled the gap by
itself: "north to Dustgate, west to Grotburrow" — the world has no bearings at all — and
three of the five routes were never mentioned (docs/playtest-2026-09-28.md, 19).

**Label and fragment, on purpose.** Each row is the destination and fragments of fact:
"a town; by road, from the outskirts; about three days on foot; farmland, then mountain".
A complete sentence here is a sentence the model pastes (item 17.6: the ROADS OUT line
came back as signposts), and fragments give Lane A's `brief_verbatim` nothing to find
but the labels, which are in SCAFFOLD. Days are words from `journey.hours_for` at the
PC's speed, so the brief's days are the engine's days; never miles, never a bearing the
world did not write.
"""
from __future__ import annotations

ORDER = 20
SLOT = "place"
SCAFFOLD = (
    "ROADS OUT OF",
    "(fact; the only settlements that can be reached, each by a journey of days;",
    "no compass bearing is recorded — never give one):",
    "BEARINGS (fact): the world records no compass direction for any of these. Answer "
    "with the roads, where they leave from, what they cross, and how long.",
    "MOUNTED (fact): the party has",
    "to ride; a journey with",
    "takes half the time on foot, and",
    "a third, though a mount pushed past its first hour of galloping in a day is hurt "
    "by it and tires.",
)
# The SCAFFOLD strings printed only on some turns: a bearing asked for, a mount in the
# party, a world that states bearings. Named so the scaffold's own test knows which
# words it cannot expect in every brief.
SOMETIMES = SCAFFOLD[2:]

# A look or a search for which way to go. The reading's own words, matched as words.
_BEARING = ("bearing", "direction", "which way", "where", "road to", "signpost",
            "signage", "the way to", "sign", "destinations", "north", "south", "east",
            "west", "compass", "larger", "city")


def asks_a_bearing(reading) -> bool:
    """Whether the player's words ask which way somewhere lies (item 16.6)."""
    for a in (reading or {}).get("actions") or []:
        if a.get("act") not in ("look", "search", "seek", "talk", "go"):
            continue
        said = " ".join(str(a.get(s) or "") for s in ("object", "says", "place")).lower()
        if any(w in said for w in _BEARING):
            return True
    return False


def section(ctx) -> tuple[str, dict]:
    location, world = ctx.location, ctx.world
    if not location or world is None:
        return "", {}
    from rules import geography

    pc = ctx.scene.pc() if ctx.scene is not None and hasattr(ctx.scene, "pc") else None
    speed = int(getattr(pc, "speed_feet", 30) or 30) if pc is not None else 30
    roads = geography.roads_out(world, location, speed)
    if not roads:
        return "", {}
    rows, facts_rows = [], []
    for r in roads:
        how = {"road": "by road", "river": "by river", "sea": "by sea",
               "sea-after-road": "by sea, after the road to the coast",
               "": "the way not written down"}.get(r.how, r.how)
        if r.how == "sea-after-road" and r.leaves_from != "the outskirts":
            how = "by sea"            # a boat off the settlement's own shore
        bits = [b for b in (r.bearing, r.to_kind, f"{how}, from {r.leaves_from}",
                            r.time_words, r.crosses_words) if b]
        rows.append(f"    {r.to_name} — {'; '.join(bits)}.")
        facts_rows.append({"to_id": r.to_id, "to_name": r.to_name, "to_kind": r.to_kind,
                           "how": r.how, "leaves_from": r.leaves_from,
                           "time_words": r.time_words, "crosses": list(r.crosses),
                           "bearing": r.bearing})
    bearings = [r.bearing for r in roads if r.bearing]
    head = (f"  ROADS OUT OF {location.name.upper()} (fact; the only settlements that can "
            f"be reached, each by a journey of days;"
            + (" no compass bearing is recorded — never give one):" if not bearings
               else " the bearings are the world's own, and no other may be given):"))
    lines = [head, *rows]
    asked = asks_a_bearing(ctx.reading)
    if asked and not bearings:
        lines.append("  BEARINGS (fact): the world records no compass direction for any of "
                     "these. Answer with the roads, where they leave from, what they "
                     "cross, and how long.")
    # A mount in the party (owner's ruling Q13): the plan is told the pace it may ask
    # for, in the op's own words. Only when there is one — a line about horses to a
    # party with none is an invitation to invent one.
    mounts = _mounts(ctx.scene)
    if mounts:
        first = roads[0].to_name
        lines.append(f"  MOUNTED (fact): the party has {', '.join(mounts)} to ride; a "
                     f"journey with "
                     f'{{"op": "journey", "params": {{"to": "{first}", "pace": "ride"}}}} '
                     f"takes half the time on foot, and \"gallop\" a third, though a "
                     f"mount pushed past its first hour of galloping in a day is hurt by "
                     f"it and tires.")
    return "\n".join(lines), {"roads": [r.to_name for r in roads],
                              "to_ids": [r.to_id for r in roads],
                              "rows": facts_rows, "bearings_asked": asked,
                              "bearings": bearings, "mounts": mounts}


def _mounts(scene) -> list[str]:
    from rules import journey, states

    out = []
    for a in (getattr(scene, "actors", None) or {}).values():
        if getattr(a, "is_pc", False):
            continue
        if str(getattr(a, "from_template", "") or "") in journey.MOUNTS \
                and a.has_state(states.TRAVELS_WITH_YOU) and not a.is_down:
            out.append(a.name)
    return out
