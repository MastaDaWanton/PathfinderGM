"""Being pulled towards a target you did not choose.

A compulsion is the app's answer to a problem every solo game has and no tabletop game
does: with one player character, nothing on the board makes a monster attack the *right*
person, because there is only one person. Blood Bending's Blood Commander path is built on
forcing that choice — a taunt, a bloodlink, a compulsion to strike the one who called you.

**The rule this module exists to enforce: a compulsion penalises, it never prohibits.**

That is a design decision, not a reading of 1e, and it is load-bearing enough to be the
first thing in the file. An aggro mechanic that *forbids* attacking anyone else takes the
decision away from the creature and hands it to a number — the fight stops being a fight
and becomes a queue. Worse, in this engine a prohibition would surface as an `IntentError`,
which means the GM's whole intent list dies because a monster wanted to do something
reasonable. A penalty leaves the choice on the board and prices it, which is what every
good version of this mechanic in any system actually does.

So: a compelled creature may always swing at whoever it likes. Doing so is just worse.
"""
from __future__ import annotations

from dataclasses import dataclass

from .dice import Modifier


@dataclass
class Compulsion:
    """One pull on a creature's attention.

    `penalty` is stored positive and applied negative, because every caller reads it as
    "how bad is it" and a stored −4 gets double-negated by somebody eventually.
    """
    by: str
    penalty: int = 4
    rounds_left: int | None = None
    source: str = ""
    # Whether the compelled creature knows why. A magical compulsion it saved against
    # partially, versus a taunt it simply resents, read the same to the engine and very
    # differently to a narrator.
    why: str = ""

    def as_dict(self) -> dict:
        return {"by": self.by, "penalty": self.penalty, "rounds_left": self.rounds_left,
                "source": self.source, "why": self.why}


def from_dict(d: dict) -> Compulsion:
    return Compulsion(
        by=str(d.get("by", "")),
        penalty=int(d.get("penalty", 4) or 0),
        rounds_left=None if d.get("rounds_left") is None else int(d["rounds_left"]),
        source=str(d.get("source", "")),
        why=str(d.get("why", "")),
    )


def add(actor, by: str, penalty: int = 4, rounds: int | None = None,
        source: str = "", why: str = "") -> Compulsion:
    """Compel this creature towards `by`.

    Through the one applicator, which gives the refresh rule for free: re-compelling
    from the same source resets the clock rather than stacking, because two taunts from
    the same enemy are one taunt shouted twice and letting them add would make the
    mechanic scale with how often the GM happened to mention it.

    The effect carries NO modifiers. The penalty lives in the payload and is read by
    `penalty_against`, which is the only reader that knows who is being attacked —
    routing it through the modifier funnel would charge the creature for obeying.
    """
    from .activeeffect import ActiveEffect

    # The stronger pull wins a refresh. `apply_effect` replaces the payload wholesale,
    # so re-shouting a weaker taunt over a stronger one would quietly lower the price of
    # defying it — the rule is that two taunts from one enemy are one taunt shouted
    # twice, not a way to talk somebody down.
    for held in actor.compulsions:
        if held.by == by and held.source == source:
            penalty = max(int(penalty), held.penalty)
            why = why or held.why
            break
    actor.apply_effect(ActiveEffect(
        name=source or f"compulsion towards {by}", kind="compulsion",
        key=f"{by}|{source}", source=source,
        duration="until-dismissed" if rounds is None else "rounds",
        rounds_left=rounds,
        payload={"by": by, "penalty": int(penalty), "why": why}))
    return next(c for c in actor.compulsions if c.by == by and c.source == source)


def remove(actor, by: str = "", source: str = "") -> int:
    return len(actor.remove_effects(
        kind="compulsion", source=source,
        match=lambda e: not by or str(e.payload.get("by", "")) == by))


def penalty_against(actor, target_ref: str) -> list[Modifier]:
    """What it costs this creature to attack that one.

    Nothing when the target *is* somebody compelling them — obeying is free, and obeying
    two rival compulsions at once by attacking one of them satisfies that one. Only the
    compulsions being defied are charged for, which is why this sums rather than taking
    the worst: three creatures screaming for your attention and being ignored by all three
    is meaningfully worse than one.
    """
    mods: list[Modifier] = []
    for c in actor.compulsions:
        if c.by == target_ref or not c.penalty:
            continue
        label = c.source or "compelled elsewhere"
        mods.append(Modifier(-abs(c.penalty), label))
    return mods


def pulled_towards(actor) -> list[str]:
    """Everyone currently compelling this creature — what a GM needs to narrate it."""
    return [c.by for c in actor.compulsions]


# `tick` is gone. Compulsions expire on `Actor.tick_effects` with everything else, so
# they count down on every clock rather than only on the combat rollover — which is why
# a compulsion applied out of a fight used to last until the next fight began.
__all__ = ["Compulsion", "add", "from_dict", "penalty_against", "pulled_towards",
           "remove"]
