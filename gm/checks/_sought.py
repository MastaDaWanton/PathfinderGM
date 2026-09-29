"""Who the player went looking for this beat, and the engine's answer — a helper, not a
check (fix-interfaces §2.1: "D's sought result is gm/checks/_sought.py").

One answer for the brief and the checks: `gm.brief.sought.answer`, the finder
(`scope.look_for`) over the reading's `seek`/`call_on` target, asked after the
resolution. A check that re-derived it its own way would be a second copy of the rule
(CLAUDE.md: when you fix a rule, grep for every copy).
"""
from __future__ import annotations


def sought(ctx) -> dict:
    """`{"scope", "who", "record", "ref", "line", "sought"}`, or {} when nobody is sought."""
    from gm.brief.sought import answer

    return answer(ctx.world, ctx.scene, ctx.reading, ctx.player_text)


def people_refs(ctx, names) -> set[str]:
    """The refs of the scene's people whose names are among `names`."""
    want = {str(n).strip().lower() for n in names or () if str(n).strip()}
    return {ref for ref, a in (getattr(ctx.scene, "actors", {}) or {}).items()
            if str(getattr(a, "name", "")).strip().lower() in want}


def lines_by(ctx, refs) -> list[str]:
    """The lines this beat's `said` records give to any of `refs`."""
    refs = set(refs or ())
    return [str(r.get("line") or "") for r in ctx.said or ()
            if str(r.get("who") or "") in refs and str(r.get("line") or "").strip()]
