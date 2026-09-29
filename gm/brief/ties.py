"""WHO THEY ARE TO THE PLAYER: a present person the PC's background names, in the tie's
own sentence.

Measured on the 2026-09-28 playtest (item 12): Bobby's background says he learned his
craft from Drenn Ironvale — "a technique you learned from Drenn Ironvale" is in the
opening itself — and Drenn greeted him as a stranger ("You! You have the look of…"). The
tie sentences were in the brief, on the PC's own line, and nothing bound them to the man
standing at the market: the narrator had to make that join itself, and did not.

This section makes it for every present person a tie sentence names, and says what the
engine holds about them (`rules.hooks.relationship`: tied, known). The hook text itself
stays in the pull, last in the prompt, where D6/D7 measured it working (design D §5 S2:
this replaces the plan's `hook.py`).
"""
from __future__ import annotations

ORDER = 50
SLOT = "people"
SCAFFOLD = (
    "WHO THEY ARE TO THE PLAYER (fact, from the player's own past):",
    "knew the player before this game began:",
    "They greet the player as someone they know, never as a stranger.",
)


def section(ctx) -> tuple[str, dict]:
    from rules import hooks

    scene = ctx.scene
    lines, facts = [], {}
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if actor.is_pc or actor.has_state("state.hidden"):
            continue
        tie = hooks.tie_sentence(scene, actor)
        if not tie:
            continue
        lines.append(f"  WHO THEY ARE TO THE PLAYER (fact, from the player's own past): "
                     f"{actor.name} ({ref}) knew the player before this game began: {tie} "
                     f"They greet the player as someone they know, never as a stranger.")
        facts[ref] = {"tie": tie, "relationship": hooks.relationship(scene, actor)}
    if not lines:
        return "", {}
    return "\n" + "\n".join(lines), facts
