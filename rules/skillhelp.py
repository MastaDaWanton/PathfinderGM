"""What each skill does in THIS game, for the hover on a skill name.

The owner, 2026-10-06: "in the character creator you should be able to hover on the skills
when choosing skill ranks to see what the skill affects in game." The forge listed 35 bare
names and the level-up picker the same 35, and nothing on either said what a rank bought.

The words live in content/rules/skills-explained.json, one entry per skill: a line of what
the book says the skill is, and "In this game" — the uses the engine and the GM actually
make of it. Every use names the file that makes it and a literal piece of that file's
code; `tests/test_skill_help.py` reads each one back, so a sentence cannot outlive the
code it describes and turn into a promise. What the book offers and this game does not do
yet is said as `not_yet`, never claimed.

The anchors are for the test. The page is sent the words only (`for_page`): a file path
on the player's screen is the system talking, not the game.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA: dict | None = None


def _load() -> dict:
    global _DATA
    if _DATA is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "skills-explained.json"
        _DATA = json.loads(path.read_text(encoding="utf-8"))
    return _DATA


def entries() -> dict[str, dict]:
    """skill id -> its entry, anchors included (the test's view)."""
    return dict(_load().get("skills") or {})


def general() -> str:
    """The one sentence true of every skill: the GM's ordinary check."""
    return str(_load().get("general") or "")


def for_page() -> dict:
    """What the forge and the sheet draw: words only, no anchors.

    {"general": str, "skills": {id: {"name", "ability", "trained_only", "book", "uses": [str],
    "not_yet"}}}

    The key ability and trained-only come from the skill table itself (rules/tables.py),
    not the file: the forge's list marks neither, and a card that said "a skill marked
    trained only" pointed at a mark that was not on the page (seen in the live check).
    """
    from .tables import SKILLS

    out = {}
    for sid, e in entries().items():
        ability, trained, _acp = SKILLS.get(sid, ("", False, False))
        out[sid] = {
            "name": e.get("name") or sid.title(),
            "ability": str(ability).upper(),
            "trained_only": bool(trained),
            "book": e.get("book") or "",
            "uses": [str(u.get("text") or "") for u in e.get("uses") or [] if u.get("text")],
            "not_yet": e.get("not_yet") or "",
        }
    return {"general": general(), "skills": out}
