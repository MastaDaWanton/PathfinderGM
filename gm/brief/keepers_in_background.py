"""IN THE BACKGROUND: a keeper minted on arrival stays at their work until dealt with.

Measured on the 2026-09-28 playtest (item 9.1): the market's keeper, Ashla, was the first
person the player met there — minted on arrival by `keepers.staff` (the trade panel needs
a body) and listed in WHO IS HERE like anybody else, so the narrator walked her up to the
player. The owner's correction: "keepers are present but in the background until dealt
with (addressed, traded with, asked for). First introductions come from the start, the
background, or whoever the player went looking for."

"Dealt with" is asked of existing state, never a new flag (the second law):
`rules.hooks.dealt_with` — `talk.with-you`, a recorded regard or any bond, or this turn's
talk, seek or buy turning to them, or the counter this turn opens. The check that holds
the page to it is `gm/checks/keeper_forward.py`.
"""
from __future__ import annotations

ORDER = 40
SLOT = "people"
SCAFFOLD = (
    "IN THE BACKGROUND (fact):",
    "is at their work and busy with it.",
    "does not approach the player or speak first; if the player turns to them, they answer.",
)


def background(scene, reading, player_text: str, buying: str = "") -> list:
    """The keepers here the player has not dealt with, in the scene's own order."""
    from rules import hooks, keepers

    out = []
    for actor in (getattr(scene, "actors", {}) or {}).values():
        if actor.is_pc or actor.has_state("state.hidden") or actor.hp <= 0:
            continue
        if not keepers.is_keeper(getattr(actor, "world_entity_id", "") or ""):
            continue
        if hooks.dealt_with(scene, actor, reading, player_text, buying):
            continue
        out.append(actor)
    return out


def section(ctx) -> tuple[str, dict]:
    quiet = background(ctx.scene, ctx.reading, ctx.player_text, ctx.buying)
    if not quiet:
        return "", {}
    lines = [f"  IN THE BACKGROUND (fact): {a.name} ({a.ref}) is at their work and busy with "
             f"it. {a.name} does not approach the player or speak first; if the player turns "
             f"to them, they answer." for a in quiet]
    return "\n" + "\n".join(lines), {"refs": [a.ref for a in quiet]}
