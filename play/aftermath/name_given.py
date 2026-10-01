"""The name the player asked for, written on the page, is learned — said or narrated.

Measured live 2026-09-30 on a copy of Sam's save (lane F's check of owner ruling F1): Sam
asked "What's your name, sergeant?"; the brief handed the sergeant's true name over for
that turn (`judgement.names_asked_for`), and the page wrote **"The sergeant's name is
Caspian Tidestone."** — in narration, not in his mouth. `apply_introductions` reads a name
SPOKEN ("'Caspian,' he says") or given in apposition ("The man—Korgath Varn—"), so the
panel kept "the sergeant of the watch" for somebody whose name the player had just read.

Keepers made this common: since F1 every keeper keeps their name back, so every keeper's
name now arrives through this question. The certainty here is the brief's own: the name
went into the brief for exactly the person asked and nobody else, so that exact name on
the page is theirs — however the sentence carries it. Nothing else is guessed: a page that
does not write the name teaches nothing, and a name somebody else here answers to is left
alone (`judgement._answers_to`).

The "people" stage, so the panel's name is right before `hailed_by` reads the room.
"""
from __future__ import annotations

import re

STAGE = "people"
ORDER = 5
DOORS = frozenset({"turn"})


def step(ctx) -> list[dict]:
    from gm import judgement

    scene, text = ctx.scene, str(ctx.text or "")
    if not ctx.player_text or not text:
        return []
    asked = judgement.names_asked_for(scene, ctx.player_text)
    actors = getattr(scene, "actors", {}) or {}
    rows = []
    for ref, given in asked.items():
        who = actors.get(ref)
        if who is None or not given or str(who.name) == given:
            continue
        if not re.search(rf"(?<![\w'’-]){re.escape(given)}(?![\w-])", text):
            continue
        if judgement._answers_to(actors, who, given):
            continue
        was = str(who.name)
        judgement._take_the_name(scene, who, given)
        rows.append({"kind": "name-given", "ref": ref, "was": was, "name": given})
    return rows
