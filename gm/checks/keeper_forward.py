"""keeper-forward: a keeper the player has not dealt with speaks to them first.

Measured on the 2026-09-28 playtest (item 9.1): the market's keeper was the first person
the player met at the market — minted on arrival for the trade panel, listed in WHO IS
HERE, and so walked up to the player. The owner's ruling: keepers are present but in the
background until dealt with. The brief says so (`gm/brief/keepers_in_background.py`);
this holds the page to it. "Dealt with" is `rules.hooks.dealt_with`, the same answer the
brief gave, never a second copy of the rule.
"""
from __future__ import annotations

from gm.narration import Finding

ORDER = 66
KINDS = frozenset({"keeper-forward"})
DOORS = frozenset({"turn"})


def find(ctx) -> list:
    from gm.brief.keepers_in_background import background

    buying = ""
    facts = (ctx.brief_facts or {}).get("keepers_in_background")
    quiet = background(ctx.scene, ctx.reading, ctx.player_text, buying)
    if facts is not None:
        # What the brief was shown wins: a keeper it did not put in the background (the
        # counter opened this turn) was the player's to deal with.
        shown = set(facts.get("refs") or [])
        quiet = [a for a in quiet if a.ref in shown]
    out = []
    for actor in quiet:
        lines = [str(r.get("line") or "") for r in ctx.said or ()
                 if str(r.get("who") or "") == actor.ref and str(r.get("to") or "") == "you"
                 and str(r.get("line") or "").strip()]
        if not lines:
            continue
        out.append(Finding(
            "keeper-forward",
            f"{actor.name} ({actor.ref}) speaks to the player unprompted, while in the "
            f"background: {lines[0][:120]!r}",
            f"{actor.name} is at their work and does not approach the player or speak "
            f"first; they answer only if the player turns to them.",
            weight=2, sentences=tuple(lines)))
    return out
