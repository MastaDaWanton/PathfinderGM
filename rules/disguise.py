"""A disguise, held (Disguise, Core Rulebook p.95; aonprd.com Skills "Disguise").

The book: "Your Disguise check result determines how good the disguise is, and it is
opposed by others' Perception check results. If you don't draw any attention to yourself,
others do not get to make Perception checks. If you come to the attention of people who
are suspicious (such as a guard who is watching commoners walking through a city gate),
it can be assumed that such observers are taking 10 on their Perception checks." The
check is made secretly, once per use; making one takes 1d3 x 10 minutes; a disguise kit
gives +2 (CRB, Goods and Services).

Playtest 2026-11-15 #82: the old path was a plain Disguise check "vs 10" that left
nothing on the character ("does not stay on you afterwards", the help said). Here the
result is an `ActiveEffect` (`state.disguised`, source `rule:disguise`) through the one
applicator, its result in the payload, and `passes` is the one question a viewer asks.

Not built (said, not hidden): the modifiers for passing as another gender, race, age or
size (the reader's `as` is the player's words, and nothing reads a people or an age out
of them); viewers who know the one impersonated (+4 to +10); the hourly re-check —
a suspicious viewer takes 10, so the answer does not change by the hour.
"""
from __future__ import annotations

from . import states

KEY = "disguised"
TAG = "state.disguised"
ORIGIN = "rule:disguise"
KIT = "disguise kit"
KIT_BONUS = 2


def worn(actor):
    """The disguise on this actor, or None."""
    return next((e for e in getattr(actor, "effects", None) or ()
                 if str(getattr(e, "source", "") or "") == ORIGIN), None)


def passes(viewer, actor) -> bool:
    """Whether `actor`'s disguise holds against `viewer`, a suspicious observer taking 10
    on Perception. False when there is no disguise to hold. Opposed: the higher result
    wins, a tie to the higher modifier (CRB p.86, Opposed Checks)."""
    held = worn(actor)
    if held is None or viewer is None:
        return False
    pay = dict(held.payload or {})
    result, own = int(pay.get("result", 0)), int(pay.get("modifier", 0))
    mod = sum(m.value for m in viewer.skill_modifiers("perception", opposed=True))
    look = 10 + mod
    return result > look or (result == look and own > mod)


def take_off(actor) -> bool:
    """The disguise comes off (its clothes changed, or a new one made). Whether one did."""
    if worn(actor) is None:
        return False
    actor.remove_effects(source=ORIGIN)
    return True


def tags():
    return states.tags_for(KEY)
