"""SPEAK OF THEM AS: the pronouns of every present person whose pronouns are set.

Measured on the 2026-09-28 playtest (item 15): the suggestions read "I ask her what she's
looking for…" while the man speaking was Drenn — they/them on the sheet, because no world
character carries a gender, and "a man" on the page. The brief stated pronouns for the
player's character and for nobody else, so each beat re-guessed them.

"Set" is the owner's Q26 ruling (2026-09-28): a person the world gives no gender adopts
the page's first gendered reference and holds it (`play/aftermath/pronouns_adopted.py`);
the player's or the plan's word at entry sets them too (`rules/person_words.py`). Until
one of those has happened a person is not listed — "they" is not a fact about them, only
the absence of one.
"""
from __future__ import annotations

ORDER = 60
SLOT = "people"
SCAFFOLD = ("SPEAK OF THEM AS (fact; keep to it in narration and in suggestions):",)


def is_set(actor) -> bool:
    """Whether somebody's pronouns are a fact: a gender on the actor, or pronouns other
    than the they/them every actor starts with."""
    return bool(str(getattr(actor, "gender", "") or "").strip()) or \
        str(getattr(actor, "pronouns", "") or "they/them").strip().lower() != "they/them"


def section(ctx) -> tuple[str, dict]:
    said = {}
    for ref, actor in (getattr(ctx.scene, "actors", {}) or {}).items():
        if actor.is_pc or actor.has_state("state.hidden") or not is_set(actor):
            continue
        said[ref] = str(actor.pronouns)
    if not said:
        return "", {}
    actors = ctx.scene.actors
    rows = "; ".join(f"{actors[r].name} ({r}) {p}" for r, p in said.items())
    return (f"\n  SPEAK OF THEM AS (fact; keep to it in narration and in suggestions): "
            f"{rows}."), said
