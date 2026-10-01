"""closing-claimed: a creature's own beat has it reach the player, and the board says no.

Measured on the owner's save, 2026-10-01. A Clockwork Spy forty feet off took its turn;
the engine resolved its move as "Clockwork Spy moves from far to far." and left it where
it stood. The consequence beat for that turn said it "covers the distance in a blur of
motion, closing the gap and landing right before you", and the owner's map showed it
still far off. The engine fault is fixed (`Engine._toward_before`: the move walks the
board and its tell says where it ended), but a walk that stops short — thirty feet of a
forty-foot gap — is the same invitation to the prose, and nothing on the page checked a
creature's distance against what the beat claimed.

What is detected, in code: on the consequence beat of a creature's own turn (door
`outcome`, `ctx.acting` set), a sentence about that creature (`_people.about`, carried on
by "it" as well, since a beast is "it" on the page) that puts it at the player — "closes
the gap", "covers the distance", "lands right before you", "is upon you", "reaches you",
"within reach of you" — while the engine holds it further off than it can strike from
and further than the square beside them: `Scene.distance_between` greater than both
five feet and the creature's reach. An attempt is not a claim ("lunges forward,
attempting to close the gap", "rushes to close the distance"), and nothing is read on a
scene with no map — a distance nobody measured contradicts nothing.

Bounded on purpose: the acting creature, on its own beat, against the player. Another
creature's position, the player's own movement (`refused_move` owns that) and the plan
beat written before the engine resolves anything (door `npc`, where the creature has not
moved yet and nothing is settled) are not read.

Repair: the house shape. One targeted rewrite of the flagged sentences with the distance
named; if a rewrite still claims arrival, the backstop cuts the flagged sentences and ends
the beat on the engine's own fact — how far off the creature still is.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 30
KINDS = frozenset({"closing-claimed"})
DOORS = frozenset({"outcome"})

# Arrival at the player. Each branch needs "you"/"your" or a gap/distance the sentence is
# closing, so a creature that "lands" on a rooftop or "stops" to listen is not arriving.
_CLAIM = re.compile(
    r"\b(?:"
    r"clos(?:es|ed|ing)\s+(?:the\s+|that\s+|this\s+)?(?:remaining\s+|last\s+|final\s+)?"
    r"(?:gap|distance)"
    r"|clos(?:es|ed|ing)\s+(?:in\s+)?on\s+you\b"
    r"|cover(?:s|ed|ing)?\s+the\s+(?:remaining\s+|last\s+|final\s+)?(?:distance|gap)"
    r"|cover(?:s|ed|ing)?\s+the\s+ground\s+(?:between|to)\s+(?:you|the\s+two\s+of\s+you)"
    r"|(?:lands?|landed|landing|stops?|stopped|stopping|halts?|halted|halting|"
    r"arrives?|arrived|arriving|skids?|skidded|skidding|comes?\s+to\s+rest|"
    r"came\s+to\s+rest|settles?|settled|settling|plants?\s+itself|planted\s+itself)"
    r"\s+(?:right\s+|just\s+|directly\s+|squarely\s+)?"
    r"(?:before|in\s+front\s+of|beside|next\s+to|at)\s+(?:you\b|your\s+(?:feet|side|boots|"
    r"heels|knees|shins|ankles))"
    r"|(?:is|are)\s+(?:now\s+|suddenly\s+|already\s+)?(?:upon|on)\s+you\b"
    r"|(?:is|are)\s+(?:now\s+|suddenly\s+|already\s+)?(?:right\s+)?(?:beside|next\s+to|"
    r"in\s+front\s+of)\s+you\b"
    r"|reach(?:es|ed)\s+you\b"
    r"|within\s+(?:arm's\s+|arm’s\s+|striking\s+|easy\s+)?reach\s+of\s+you\b"
    r"|(?:face\s+to\s+face|toe\s+to\s+toe|nose\s+to\s+nose)\s+with\s+you\b"
    r")", re.I)

# The words in front of a claim that make it an attempt, a purpose or a denial: "tries
# to close the gap", "rushes forward to close the distance", "has not reached you".
_NOT_YET = re.compile(
    r"\b(?:tries|try|trying|tried|attempts?|attempting|attempted|struggles?|struggling|"
    r"struggled|fails?|failing|failed|cannot|can't|can’t|couldn't|couldn’t|unable|not|"
    r"never|nearly|almost|begins?|beginning|began|starts?|starting|started|seeks?|"
    r"seeking|means?|meaning|wants?|wanting|hopes?|hoping|eager|yet)"
    r"\s+(?:[\w'’]+\s+){0,3}$"
    # A bare "to" only right before the claim — "rushes forward to close the gap" is a
    # purpose — never a "to" further back ("turns to the left and lands before you").
    r"|\bto\s+$", re.I)
# The player is the one closing: "you close the gap" is the player's own walk. "You" as
# a subject only — at the start, or after a comma or "and" — so "hurls itself at you and
# lands right before you" is still the creature's.
_YOU_BEFORE = re.compile(r"(?:^|[,;]\s*|\band\s+|\bthen\s+)you\s+(?:[\w'’]+\s+)?$", re.I)

_IT = frozenset({"it", "its", "itself"})


def claims(narration: str) -> bool:
    """Whether one sentence of narration puts its subject at the player."""
    if "?" in narration:
        return False
    for m in _CLAIM.finditer(narration):
        before = narration[max(0, m.start() - 48):m.start()]
        if _NOT_YET.search(before) or _YOU_BEFORE.search(before):
            continue
        return True
    return False


def _gap(ctx):
    """(the acting creature, feet between it and the player, the most it can be off and
    still be "at" them), or None when the beat is not a creature's own on a map."""
    scene = ctx.scene
    ref = str(ctx.acting or "")
    actors = getattr(scene, "actors", {}) or {}
    actor = actors.get(ref)
    pc = scene.pc() if hasattr(scene, "pc") else None
    if actor is None or pc is None or getattr(actor, "is_pc", False) \
            or not getattr(scene, "has_grid", False):
        return None
    feet = scene.distance_between(ref, pc.ref)
    if feet is None:
        return None
    from rules import reactions
    from rules.grid import SQUARE_FT

    try:
        reach = reactions.reach_with(actor, actor.wielded_key())[0]
    except Exception:  # noqa: BLE001 — a body with no reach to read is a body of 5 ft
        reach = SQUARE_FT
    return actor, int(feet), max(SQUARE_FT, int(reach))


def _sentences_about(ctx, actor) -> list[str]:
    """The page's sentences about the acting creature, as written: `_people.about`, and
    the "it" continuation after them — a creature with no pronouns set is "they" to the
    helper, and "it" on every page a beast appears on."""
    from ._page import page_sentences
    from ._people import linked, names_person

    pairs = page_sentences(ctx.text)
    theirs = {w for w, _ in _about(ctx, actor.ref)}
    others = [str(a.name or "") for r, a in ctx.scene.actors.items()
              if r != actor.ref and not getattr(a, "is_pc", False)]
    narr = [n for _, n in pairs]
    by_n = {n: w for w, n in pairs}
    picked = linked(narr, lambda n: by_n.get(n, n) in theirs,
                    lambda n: any(names_person(n, o) for o in others if o),
                    family=_IT | _family(actor))
    return [pairs[i] for i in picked]


def _about(ctx, ref):
    from ._people import about

    return about(ctx, ref)


def _family(actor) -> frozenset[str]:
    from ._people import pronoun_words

    return pronoun_words(getattr(actor, "pronouns", ""))


def _subject(actor) -> str:
    """How the backstop names it: "The Clockwork Spy" for a bestiary creature (a kind of
    thing, `engine._the_creature`), the name as it stands for anybody else."""
    from rules.engine import _the_creature

    name = str(actor.name or "")
    return _the_creature(name) if getattr(actor, "from_template", "") else name


def find(ctx) -> list:
    measured = _gap(ctx)
    if measured is None:
        return []
    actor, feet, near = measured
    if feet <= near:
        return []
    flagged = [w for w, n in _sentences_about(ctx, actor) if claims(n)]
    if not flagged:
        return []
    who = _subject(actor)
    return [Finding(
        "closing-claimed",
        f"{actor.name} is {feet} ft from the player after its turn, and the prose has it "
        f"reach them: {flagged[0][:90]!r}",
        f"{who} did not reach you: it is still {feet} feet away. Rewrite the sentence so "
        f"it comes on but is still that far off — it has not reached you and is not "
        f"beside you.",
        weight=4, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut every sentence that still puts the creature at the player, and end the beat on
    the engine's fact: how far off it still is."""
    from ._page import cut, page_sentences

    measured = _gap(ctx)
    if measured is None:
        return text, []
    actor, feet, near = measured
    if feet <= near:
        return text, []
    from dataclasses import is_dataclass, replace

    probe = replace(ctx, text=text) if is_dataclass(ctx) else ctx
    flagged = [w for w, n in _sentences_about(probe, actor) if claims(n)]
    if not flagged:
        # The labeller read the original beat; a rewrite may have lost the sentence it
        # attributed. Read the page plain, by the claim alone, before giving up.
        flagged = [w for w, n in page_sentences(text) if claims(n)
                   and w in {s for f in findings for s in (f.sentences or ())}]
    if not flagged:
        return text, []
    kept = cut(text, flagged)
    line = f"{_subject(actor)} is still {feet} feet from you."
    return f"{kept} {line}".strip(), [f"closing claimed: cut {len(flagged)} sentence(s) "
                                      f"putting {actor.name} at the player, {feet} ft off"]
