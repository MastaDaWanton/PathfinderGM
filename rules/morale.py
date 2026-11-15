"""When a creature stops fighting: it runs, or it yields.

Playtest 2026-11-15 (a human outlaw taking a ship): nobody ever stopped fighting. A
commoner punched in round 2 "remains unmoving in your space" (#30); a captain at 1 of 11
hit points, told "yield the Red Gull to me or die", fought on (#97); and so a ship could
not be taken without killing her crew (#94). The engine had a morale check for a crowd
(`rules/troops.py`, Basic D&D's 2d6) and nothing for one person.

**What the rules say, and what this takes from each** (researched 2026-11-15):

* Pathfinder 1e has no general morale rule. The GameMastery Guide p.16 tells the GM to
  "think about what might make the creature surrender or flee. Few creatures fight to the
  death if there's an alternative available" (aonprd Rules ID 455). Its published stat
  blocks write morale per creature as an hit-point line and what is done then: "if reduced
  below 5 hit points, attempts to flee, but if it's obvious that she can't escape ... fights
  to the death". That SHAPE is what is built: a threshold, then flee, then a fallback when
  there is nowhere to run.
* The threshold is half hit points, the 5th edition DMG's optional rule (p.273: a creature
  "reaches half its hit points for the first time"), which is also where B/X put "half the
  group down" for a crowd. Checked once, as 5e does.
* The roll is Basic D&D's, which `troops.py` already uses: 2d6 against a morale score of 8,
  higher and it breaks. One number for a crowd and one person.
* When it cannot run it surrenders: 5e ("If escape is impossible ... surrenders") and
  Ultimate Campaign's armies ("If it cannot retreat, it surrenders and is captured"). On a
  ship's deck at sea there is nowhere to run.
* A leader's yielding is a check for the rest: AD&D's "leader slain" and 5e's group trigger
  ("the leader drops to 0, is captured"). Crew not in the fight yield with their master.
* A frightened creature "flees from the source of its fear as best it can. If unable to
  flee, it may fight" (CRB Appendix 2): an animal (Intelligence 2 or less) has no terms to
  offer and flees; a mindless creature (no Intelligence score) never checks at all.
* A civilian — somebody with no fighting training (`Engine.martial`) — does not wait for
  half: hurt in a fight, they run (the owner's splash ruling of 2026-10-06, RimWorld's
  traders, BG3's townsfolk).

**Tried elsewhere and not adopted.** AD&D's percentage tables with a dozen modifiers were
dropped by every later edition for two to six named triggers and one roll; this keeps
three. Fallout 2's run-away modes and Bannerlord's routing are modded away by players when
a runner costs the loot and the experience: a creature that yields here stays on the deck
and is out of the fight, so nothing is lost by its yielding. 3rd edition dropped morale
altogether, for reasons nobody sourced; Pathfinder inherited the gap, which is the bug.
"""
from __future__ import annotations

from . import states

# Basic D&D's morale check, the same dice and the same middling score a crowd uses
# (`troops.MORALE_DICE`, `troops.MORALE_DEFAULT`): above it, the creature breaks.
DICE = "2d6"
SCORE = 8

# The two answers a broken creature gives, and the one it gives when it cannot.
FLEES = "flees"
YIELDS = "yields"

# The tag a yielding lays (states.TAGS["yielded"]) and the one a check leaves behind so it
# is made once (states.TAGS["morale tested"]).
YIELDED = "state.yielded"
YIELDED_KEY = "yielded"
TESTED = "morale.tested"
TESTED_KEY = "morale tested"
# Demoralize's condition (CRB p.99), the one key a threat in a fight writes.
SHAKEN_KEY = "shaken"

# What a threat can demand (`interpret.DEMANDS`, the reader's closed answer about the
# player's words): give up the fight, hand over what they carry, back off, do as told.
DEMANDS = ("yield", "hand_over", "back_off", "obey")


def intelligence(actor) -> int | None:
    """The creature's Intelligence score, or None for a mindless one (no score at all)."""
    raw = (getattr(actor, "abilities", None) or {}).get("int")
    try:
        return None if raw in (None, "", "-", "—") else int(raw)
    except (TypeError, ValueError):
        return None


def checks_morale(actor) -> bool:
    """A mindless creature (a construct, an ooze, mindless undead) never breaks."""
    score = intelligence(actor)
    return score is not None and score > 0


def can_yield(actor) -> bool:
    """Whether it can surrender: it has the wits to offer terms (Intelligence 3 or more,
    the CRB's line between animal and person). An animal flees instead."""
    score = intelligence(actor)
    return score is not None and score >= 3


def bloodied(actor) -> bool:
    """At half its hit points or worse, counting non-lethal damage as the book does for
    staggering (CRB p.191: non-lethal damage equal to current hit points)."""
    top = int(getattr(actor, "hp_max", 0) or 0)
    if top <= 0:
        return False
    left = int(getattr(actor, "hp", 0) or 0) - int(getattr(actor, "nonlethal", 0) or 0)
    return left * 2 <= top


def hurt(actor) -> bool:
    top = int(getattr(actor, "hp_max", 0) or 0)
    return bool(int(getattr(actor, "nonlethal", 0) or 0)) or (
        top > 0 and int(getattr(actor, "hp", 0) or 0) < top)


def holds(roll_total: int, score: int = SCORE) -> bool:
    """Basic D&D: higher than the score and it breaks."""
    return int(roll_total) <= int(score)


def yielded(actor) -> bool:
    return actor is not None and actor.has_state(YIELDED)


def _cap(name: str) -> str:
    return f"{name[:1].upper()}{name[1:]}"


def yield_said(name: str, armed: bool) -> str:
    return (f"{_cap(name)} throws down their weapon and yields." if armed
            else f"{_cap(name)} gives up the fight and yields.")


def flee_said(name: str, into_the_sea: bool = False) -> str:
    return (f"{_cap(name)} breaks off and goes over the side." if into_the_sea
            else f"{_cap(name)} breaks and runs from the fight.")
