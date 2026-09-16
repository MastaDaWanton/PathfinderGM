"""Talking somebody round, by the book.

`rules/states.py` has held 1e's attitude track since the spell import, and said so:
thirty-three spells set an attitude, `effectspec` offered the type, and the note beside
it read "no check in the app consults an attitude yet". The track existed, the vocabulary
existed, the applicator existed — and the three skills a player actually reaches for did
nothing to it. `_op_check` rolled Diplomacy, printed the margin, awarded the XP for
beating a DC, and left the merchant exactly as hostile as they had been. A whole pillar of
the game ended at a number in a sentence.

Worse, the engine was already telling the model otherwise. The refusal that stops a plan
from simply declaring somebody helpful ends: "To move somebody by ordinary means, talk to
them and roll it: check skill=diplomacy, check skill=intimidate, check skill=bluff." That
was the app describing a feature it did not have.

**The rules, from the Core Rulebook, and only the rules.** No number here is invented:

  Diplomacy, Influence Attitude — a DC of 25/20/15/10/0 by the target's current attitude
  (hostile to helpful), plus their Charisma modifier. One minute of continuous talk. On a
  success the attitude improves one step, and one more step for every 5 the check beats
  the DC by, to a limit of **two steps**. Fail by 4 or less and nothing moves; fail by 5
  or more and it worsens one step. A shift lasts 1d4 hours. You may not try the same
  creature twice in 24 hours.

  Intimidate, Change Attitude — DC 10 + the target's Hit Dice + their Wisdom modifier,
  one minute of conversation. Success makes them act friendly for 1d6x10 minutes.

**What Bluff is not.** Bluff moves nobody on this track and is not wired to it, because
the book does not put it there: a lie is an opposed check against Sense Motive, which
`check` has supported through `opposed_by` all along. Wiring Bluff to the attitude track
because it appears in the same sentence as the other two would be inventing a rule and
calling it Pathfinder. Said here rather than left for somebody to notice.

**The simplification, named.** After an intimidated creature's friendliness lapses, the
book has them treat you as unfriendly and possibly report you. That is not implemented:
there is no "when this effect ends" trigger in the engine — wards fire each round or when
struck — and inventing a third trigger for one rule is how a mechanism ossifies around a
special case. The friendliness runs out and they are whatever they were. docs/attitude.md
carries this as an open gap rather than a quiet one.
"""
from __future__ import annotations

from . import states

# The track, worst to best. `states.ATTITUDES` is the one definition; this is a name for
# it so that reading this file does not send anybody looking.
TRACK = states.ATTITUDES

# Where a creature sits when nobody has said anything about them. The book's own default
# for an NPC with no reason to care either way, and the reason a shift is computed from
# `of()` rather than from the absence of a tag.
DEFAULT = "indifferent"

# Core Rulebook, Diplomacy: the DC to influence a creature's attitude, by the attitude it
# starts at, before its Charisma modifier.
INFLUENCE_DC = {"hostile": 25, "unfriendly": 20, "indifferent": 15,
                "friendly": 10, "helpful": 0}

# "A creature's attitude cannot be shifted more than two steps up in this way."
MOST_STEPS_UP = 2

# How long a shift lasts, and how long the talking takes. Both the book's.
SHIFT_DICE = "1d4"          # hours
INFLUENCE_MINUTES = 1
# "You cannot use Diplomacy to influence a given creature's attitude more than once in a
# 24 hour period."
COOLDOWN_MINUTES = 24 * 60

# Intimidate, Change Attitude: DC 10 + Hit Dice + Wisdom modifier, and the duration of
# the friendliness it buys.
INTIMIDATE_BASE_DC = 10
INTIMIDATE_DICE = "1d6"     # x10 minutes

# The two skills that move the track, and how each does it. Bluff is deliberately absent;
# the module docstring says why.
LEVERS = ("diplomacy", "intimidate")


def of(actor, default: str = DEFAULT) -> str:
    """Where this creature sits on the track. Asked through the vocabulary, always."""
    return states.attitude_of(actor, default=default)


def step_of(name: str) -> int:
    """The track as a number, so a shift is arithmetic. -1 for a word off the track."""
    try:
        return TRACK.index(str(name or "").strip().lower())
    except ValueError:
        return -1


def moved(name: str, steps: int) -> str:
    """Where a creature ends up, `steps` along the track from where they are.

    Clamped at both ends: there is nothing past helpful and nothing below hostile, and a
    check that would drive somebody off either end simply leaves them there.
    """
    at = step_of(name)
    if at < 0:
        at = step_of(DEFAULT)
    return TRACK[max(0, min(len(TRACK) - 1, at + int(steps)))]


def influence_dc(target) -> int:
    """The Diplomacy DC for this creature, as the book states it.

    Computed by the engine and never proposed by the GM. This is a rule with a table
    behind it, not a judgement about how hard something looks, and the whole arrangement
    of this app is that the model proposes and the engine disposes — a plan that could
    name its own DC for talking somebody round could talk anybody into anything.
    """
    return INFLUENCE_DC.get(of(target), INFLUENCE_DC[DEFAULT]) + _mod(target, "cha")


def intimidate_dc(target) -> int:
    """Core Rulebook, Intimidate: 10 + Hit Dice + Wisdom modifier."""
    return INTIMIDATE_BASE_DC + _hit_dice(target) + _mod(target, "wis")


def steps_for(margin: int) -> int:
    """How far a Diplomacy check moves somebody, from how far it beat the DC.

    One step for the success, one more per 5 over, capped at two up. Failure by 4 or less
    moves nobody; by 5 or more it costs a step — which is the half that makes the check
    worth thinking about rather than worth spamming.
    """
    margin = int(margin)
    if margin >= 0:
        return min(MOST_STEPS_UP, 1 + margin // 5)
    return -1 if margin <= -5 else 0


def _mod(actor, ability: str) -> int:
    """An ability modifier off whatever kind of sheet this is, or 0.

    Fails soft on purpose: a creature with no scores at all is every hand-written
    townsfolk's ancestor and a great many bestiary blocks, and a missing modifier must
    leave the book's base DC standing rather than raise.
    """
    fn = getattr(actor, "ability_mod", None)
    if callable(fn):
        try:
            return int(fn(ability))
        except Exception:
            return 0
    score = getattr(actor, "ability_score", None)
    if callable(score):
        try:
            return (int(score(ability)) - 10) // 2
        except Exception:
            return 0
    return 0


def _hit_dice(actor) -> int:
    """How many Hit Dice this creature has. A character's level is their Hit Dice, and a
    creature's stat block says so directly; either way, never less than one."""
    for name in ("hit_dice", "hd", "level"):
        got = getattr(actor, name, None)
        if callable(got):
            try:
                got = got()
            except Exception:
                got = None
        try:
            if got is not None:
                return max(1, int(got))
        except (TypeError, ValueError):
            continue
    return 1


def said(who: str, was: str, now: str) -> str:
    """The tell, in words and never in numbers — the third law.

    The narrator is fed this and nothing else about the check: no DC, no margin, no step
    count. "Warmer towards you" is a thing a character can notice; "attitude +1" is not.
    """
    if was == now:
        return f"{who} is unmoved."
    # States, not movements. Written as movements — "warms to you" for friendly — the
    # line came out as "Grix cools: warms to you" the first time a threat moved somebody
    # DOWN the track to friendly, which is a sentence that says nothing. The direction is
    # the verb; the phrase is where they have ended up.
    phrase = {
        "hostile": "wants you gone, and is past talking",
        "unfriendly": "has no time for you",
        "indifferent": "is neither here nor there about you",
        "friendly": "is well disposed towards you",
        "helpful": "is on your side",
    }.get(now, now)
    verb = "warms" if step_of(now) > step_of(was) else "cools"
    return f"{who} {verb}: {phrase}."
