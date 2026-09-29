"""greets-known-as-stranger: somebody who knows the player meets them as a stranger.

Measured on the 2026-09-28 playtest (item 12, turn 4): Bobby's background says he learned
his craft from Drenn Ironvale; Drenn's first words to him were "You! You have the look of
someone who can navigate the nuances of a search … I am Drenn Ironvale" — the sizing-up
of a stranger and a self-introduction, to his own former pupil.

A present person who is tied or known to the player (`rules.hooks.relationship`), or the
pull's giver, raises this when a line of theirs to the player introduces themselves by
name, calls the player a stranger, or uses a first-meeting formula ("you have the look
of", "who are you", "never seen you"). For a giver who is a stranger to the player only
the cold-open formulas count — a stranger may give their name. The repair carries the tie
sentence, when there is one.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 64
KINDS = frozenset({"greets-known-as-stranger"})
DOORS = frozenset({"turn", "npc"})

_COLD = re.compile(
    r"\byou have the look of\b|\byou look like (?:someone|somebody|a)\b|\bwho are you\b|"
    r"\bnever seen you\b|\bhaven'?t seen you\b|\bnew (?:here|in town|face)\b|"
    r"\byou(?:'re| are) not from (?:here|around)\b|\bwhat brings you\b", re.I)
_STRANGER = re.compile(r"\bstranger\b", re.I)


def _introduces(line: str, name: str) -> bool:
    words = [w for w in re.findall(r"[A-Z][A-Za-z'’-]+", str(name or ""))]
    if not words:
        return False
    alt = "|".join(re.escape(w) for w in words)
    return bool(re.search(rf"\b(?:I am|I'm|my name is|name's|they call me|call me)\s+"
                          rf"(?:{alt})\b", str(line or ""), re.I))


def find(ctx) -> list:
    from rules import hooks

    scene = ctx.scene
    actors = getattr(scene, "actors", {}) or {}
    giver = str(((ctx.pull or {}).get("giver") or {}).get("ref") or "")
    out = []
    flagged: set[str] = set()
    for rec in ctx.said or ():
        who = str(rec.get("who") or "")
        line = str(rec.get("line") or "")
        if who in flagged or who not in actors or str(rec.get("to") or "") != "you":
            continue
        actor = actors[who]
        rel = hooks.relationship(scene, actor)
        if rel == hooks.STRANGER and who != giver:
            continue
        cold = _COLD.search(line) or _STRANGER.search(line)
        named = _introduces(line, actor.name) or _introduces(line, getattr(actor, "true_name", ""))
        if not (cold or (named and rel != hooks.STRANGER)):
            continue
        tie = hooks.tie_sentence(scene, actor)
        flagged.add(who)
        out.append(Finding(
            "greets-known-as-stranger",
            f"{actor.name} ({rel} to the player) meets them as a stranger: {line[:120]!r}",
            (f"{actor.name} knows the player — {tie} " if tie else
             f"{actor.name} is not meeting the player for the first time. "
             if rel != hooks.STRANGER else
             f"{actor.name} does not size the player up or pitch to them cold. ")
            + "Greet them as someone known; no self-introduction, no 'stranger'.",
            weight=2, sentences=(line,)))
    return out
