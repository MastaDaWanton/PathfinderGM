"""companion-off-turn: on the player's beat in a fight, the page has a companion move or
strike — and their deeds belong to their own turn, which comes after this beat.

Measured on the companions replays, 2026-10-01 (the owner's ruling that companions take
spoken orders "as their character dictates"). Told "Bob, get round behind him! Drover,
stay back and keep the crowd off me!", the PLAYER's beat said "Bob is a blur of motion,
diving into the gap between the thug and the crowd, while the drover steps back" — then
Bob's own turn moved him, and the drover's own turn moved him the other way. A second run
had the drover "lunging forward and throwing their weight into the man's side". The
companions are in the initiative (`Engine._companions_join`) and the player's plan no
longer acts for them (`companions.on_their_own_turn`); a brief line saying they act only
on their own turn halved it and did not end it, which is this repo's first lesson.

What is detected, in code: door `turn`, a fight on, and a sentence the attribution (or the
page's words) gives to a companion in the initiative whose narration carries a deed verb —
lunges, charges, strikes, dives, steps forward or back, closes, grabs, tackles. Reactions
are left alone: a flinch, a look, a word, a grip tightening — they heard the player.

Repair: the house shape. One targeted rewrite naming the fact; the backstop cuts the
flagged sentences.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 35
KINDS = frozenset({"companion-off-turn"})
DOORS = frozenset({"turn"})

_DEED = re.compile(
    r"\b(?:lung(?:es|ed|ing)|charg(?:es|ed|ing)|strik(?:es|ing)|struck|swings?|swung|"
    r"swinging|slams?|slammed|tackl(?:es|ed|ing)|hits?|stabs?|stabbed|div(?:es|ed|ing)|"
    r"leaps?|leapt|leaping|rush(?:es|ed|ing)|dash(?:es|ed|ing)|sprint(?:s|ed|ing)|"
    r"clos(?:es|ed|ing)\s+(?:in|the\s+(?:gap|distance))|wrench(?:es|ed|ing)|"
    r"grab(?:s|bed|bing)|seiz(?:es|ed|ing)|pins?|pinned|attacks?|attacked|"
    r"throws?\s+(?:their|his|her|its)\s+weight|"
    r"steps?\s+(?:forward|in|back|between|into|aside)|stepped\s+(?:forward|in|back|between|"
    r"into|aside)|mov(?:es|ed|ing)\s+(?:to|toward|towards|into|between|forward|round|"
    r"around|behind)|circl(?:es|ed|ing)|flank(?:s|ed|ing)?|blur\s+of\s+motion)\b", re.I)


def _theirs(ctx) -> list:
    scene = ctx.scene
    if not getattr(scene, "in_encounter", False):
        return []
    from gm import companions

    order = {r for r, _ in (getattr(scene, "initiative", None) or [])}
    return [a for r, a in (getattr(scene, "actors", {}) or {}).items()
            if r in order and companions.is_companion(a)]


def _flagged(ctx, actor) -> list[str]:
    from ._people import about

    return [w for w, n in about(ctx, actor.ref) if _DEED.search(n)]


def find(ctx) -> list:
    out = []
    for actor in _theirs(ctx):
        flagged = _flagged(ctx, actor)
        if not flagged:
            continue
        out.append(Finding(
            "companion-off-turn",
            f"{actor.name} acts on the player's beat: {flagged[0][:90]!r}",
            f"It is not {actor.name}'s turn: {actor.name} acts on their own turn, which "
            f"comes after this beat. Rewrite the sentence so {actor.name} only hears and "
            f"reacts — a look, a flinch, a word — without moving or striking yet.",
            weight=3, sentences=tuple(flagged)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut every sentence that still has a companion move or strike off their turn."""
    from dataclasses import is_dataclass, replace

    from ._page import cut

    probe = replace(ctx, text=text) if is_dataclass(ctx) else ctx
    gone = [s for a in _theirs(probe) for s in _flagged(probe, a)]
    if not gone:
        return text, []
    kept = cut(text, gone)
    if not kept.strip():
        return text, []
    return kept, [f"companion off turn: cut {len(gone)} sentence(s)"]
