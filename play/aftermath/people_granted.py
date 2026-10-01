"""A people the page granted in reply is recorded, and binds the next person made there.

Owner ruling F2 (2026-09-30), measured on Sam's save at turns 22-23: "any human women
here?" — Gorm, "There is one," — and the chamber's keeper, Quin Nutmeg, was minted two
turns later with a Ratfolk face. The detection and the record are `rules/granted.py`; this
step only hands it the beat: the player's own words (the question) and the lines the beat
kept, each already tagged to its speaker. In code, never asked of a model: the people word
is matched against the world's own peoples, and the NPC's line must open with a yes.

The "beat" stage, because the lines it reads are the ones the beat KEPT (`said` on the
transcript entry), after the people stage has made any speaker real. The turn door only:
Continue carries no words of the player's, so it asks nothing.
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 40
DOORS = frozenset({"turn"})


def step(ctx) -> list[dict]:
    from rules import granted

    found = granted.detect(ctx.player_text, ctx.said, ctx.world, ctx.scene)
    rows = []
    for g in found:
        rec = granted.grant(ctx.scene, g, turn=int(ctx.turn or 0))
        if rec is None:
            continue
        rows.append({"kind": "people-granted", "record": rec.get("id", ""),
                     "people": g.get("people_id") or g.get("kind"),
                     "gender": g.get("gender", ""), "by": g.get("by", ""),
                     "place": rec["granted"]["place"], "line": g.get("line", "")[:120]})
    return rows
