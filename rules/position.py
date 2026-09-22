"""What standing there is worth, as modifiers.

The route that did not exist. `rules/grid.py` has been able to answer "are these two
flanking?" since the grid was built, and **nothing ever called it**; the same was true of
cover, which the geometry could see and no attack ever felt. Positions decided where a
creature was and never what it cost anybody. Measured 2026-09-14: `grid.flanking` had no
caller outside its own tests, and the word "cover" appears nowhere in `rules/engine.py`.

So this is one module for all of it, rather than four bolted onto the attack path one at
a time — the four being flanking, higher ground, cover, and the loss of Dex to AC on a
wall, which are all the same sentence: *the board changes the roll*.

**Why it lives here and not on the sheet.** `Actor.attack_modifiers` cannot answer any of
these, because every one of them depends on somebody else's position as well as your own.
That is exactly the argument `rules/compulsion.py` already makes for `penalty_against` —
"the penalty depends on *who is being attacked*, which the sheet does not know" — and this
is the same shape with the scene in place of the target. Both are added by the engine at
the moment of the swing, and both return bare `Modifier`s so the dice popup itemises them
beside Strength and the weapon's enhancement, with a name a player can argue with.

**Nothing here mutates anything.** Scene in, modifiers out. Legality is the engine's,
geometry is the grid's, and this is only the arithmetic between them.

The rules, with their sources, because two of the four are easy to misremember:

  flanking      +2 attack, and it is a *flanking* bonus that only melee gets
                (aonprd.com/Rules.aspx?ID=183)
  higher ground +1 melee, +0 ranged — Table 8-5, Attack Roll Modifiers
                (aonprd.com/Rules.aspx?ID=180). **No minimum height is defined**: two
                Paizo rules threads asking what counts as higher ground close with no FAQ
                and no errata, so the threshold below is this project's, and is written
                down as such.
  cover         +4 AC, +2 Reflex. Soft cover — a creature in the way — is +4 AC and no
                Reflex at all. Total cover cannot be attacked through
                (aonprd.com/Rules.aspx?ID=181).
"""
from __future__ import annotations

from .dice import Modifier
from .grid import distance_between, flanking

# How far above a defender an attacker has to be before the ground counts as higher.
# One square — five feet — because that is the smallest difference this engine can
# represent, and because a rule that fires on any difference at all would hand the bonus
# to anybody standing on a doorstep.
#
# The rules do not say. Table 8-5 prints the +1 and defines nothing; the community
# answers range from "three feet" to "waist height" and Paizo never settled it. So this is
# a choice, it is the smallest defensible one, and it is here rather than inlined so there
# is one place to argue with.
HIGHER_GROUND_SQUARES = 1

FLANKING_BONUS = 2
HIGHER_GROUND_BONUS = 1
COVER_AC = 4
COVER_REFLEX = 2
SOFT_COVER_AC = 4


def _level(p) -> int:
    return p[2] if p is not None and len(p) > 2 else 0


def _same_side(scene, a: str, b: str) -> bool:
    """Whether these two are fighting together.

    Allegiance lives on the scene, not the actor — `Scene.sides` maps a side's name to
    the refs on it — and it is only populated inside an encounter. Outside one, or for a
    creature nobody has assigned, the answer is "yes": a scene with no declared sides is
    one where the engine has not been told otherwise, and refusing every flank there
    would silently switch the rule off for every fight that started without `sides`.
    """
    sides = getattr(scene, "sides", None) or {}
    mine = next((s for s, refs in sides.items() if a in refs), None)
    theirs = next((s for s, refs in sides.items() if b in refs), None)
    if mine is None or theirs is None:
        return True
    return mine == theirs


def _melee(weapon: dict | None) -> bool:
    """Whether this swing is a melee one. Both of the attack-side bonuses are melee-only:
    Table 8-5 gives higher ground `+0` for ranged in as many words, and flanking requires
    threatening the target, which a bow does not do."""
    if not weapon:
        return True
    return str(weapon.get("category") or "").lower() != "ranged"


def attack_mods(scene, actor, defender, weapon: dict | None = None) -> list[Modifier]:
    """What the board adds to this swing, itemised.

    Empty on a scene with no map, and deliberately so: a mapless scene takes the GM's
    word for where people are, and inventing a flanking bonus out of a zone word would be
    the engine asserting a fact it does not have. "We are not tracking that" is an answer.
    """
    grid = getattr(scene, "grid", None)
    if grid is None:
        return []
    here = scene.positions.get(actor.ref)
    there = scene.positions.get(defender.ref)
    if here is None or there is None or not _melee(weapon):
        return []

    mods: list[Modifier] = []

    with_whom = flanking_with(scene, actor, defender, weapon)
    if with_whom:
        mods.append(Modifier(FLANKING_BONUS, f"flanking with {with_whom}", "flanking"))

    if _level(here) - _level(there) >= HIGHER_GROUND_SQUARES:
        mods.append(Modifier(HIGHER_GROUND_BONUS, "higher ground"))
    return mods


def flanking_with(scene, actor, defender, weapon=None) -> str:
    """The name of the ally this attacker is flanking the defender with, or "".

    Pulled out of `attack_mods` when sneak attack needed the same answer for a different
    purpose (`rules/precision.py`): flanking is one of the two ways a rogue's dice come
    out, and a second copy of this loop would be a rule with two homes — the thing
    CLAUDE.md records as having shipped a corrected consequence rule and a stale one side
    by side. The +2 and the sneak dice now read the same fact.

    `weapon` is optional exactly as it is on `attack_mods`, and means the same thing
    there: no weapon named is treated as melee, because flanking requires threatening
    the target and a bow does not.
    """
    grid = getattr(scene, "grid", None)
    if grid is None:
        return ""
    # Improved uncanny dodge: "the character can no longer be flanked". Asked before the
    # geometry, because it is an answer about the defender rather than about the map —
    # and asked HERE rather than in `precision.py` so that the +2 to hit goes with the
    # sneak dice. The book denies the flank itself, not just its consequence.
    from . import classfeatures

    if classfeatures.cannot_be_flanked(defender, actor):
        return ""
    here = scene.positions.get(actor.ref)
    there = scene.positions.get(defender.ref)
    if here is None or there is None or not _melee(weapon):
        return ""
    for ref, other in scene.actors.items():
        if ref in (actor.ref, defender.ref) or other.is_down:
            continue
        if not _same_side(scene, actor.ref, ref):
            continue                      # an enemy of yours is not helping you flank
        ally = scene.positions.get(ref)
        if ally is None or _level(ally) != _level(here):
            continue                      # flanking is a fact about one plane
        if flanking(tuple(here[:2]), tuple(ally[:2]),
                    tuple(there[:2]), defender.size):
            return str(other.name)
    return ""


def cover_of(scene, actor, defender) -> str:
    """`""`, `"cover"`, `"soft"` or `"total"` — what the defender has against this attacker.

    Terrain first, then bodies: a wall and a bystander both grant +4, but only the wall
    helps against a fireball, so which one it is has to survive to the caller.
    """
    grid = getattr(scene, "grid", None)
    if grid is None:
        return ""
    here = scene.positions.get(actor.ref)
    there = scene.positions.get(defender.ref)
    if here is None or there is None:
        return ""

    # Full positions, levels and all. These were truncated to two dimensions when this
    # was written, which was harmless while cover was flat and became the thing that
    # silently defeated height-aware cover the day it landed: the geometry grew a third
    # axis and the caller went on handing it squares.
    hard = grid.cover_between(tuple(here), actor.size, tuple(there), defender.size)
    if hard == "total":
        return "total"
    if hard == "cover":
        return "cover"

    # Soft cover: somebody else in the line. Asked of the squares the line actually
    # crosses rather than of everybody in the scene, and only of bodies standing on the
    # same level, because a creature overhead is not between anybody and anything.
    from .grid import line as grid_line

    span = distance_between(here, actor.size, there, defender.size)
    crossed = grid_line(tuple(here[:2]), tuple(there[:2]), span)
    for ref, other in scene.actors.items():
        if ref in (actor.ref, defender.ref) or other.is_down:
            continue
        spot = scene.positions.get(ref)
        if spot is None or _level(spot) != _level(there):
            continue
        if tuple(spot[:2]) in crossed:
            return "soft"
    return ""


def ac_mods(scene, actor, defender) -> list[Modifier]:
    """What the board adds to the defender's AC against this attacker.

    Returned as modifiers rather than folded into a number so the attack's own
    explanation can name them — the sheet's rule that a total has to be traceable to the
    term that produced it applies just as much to the number being rolled against.
    """
    kind = cover_of(scene, actor, defender)
    if kind == "cover":
        return [Modifier(COVER_AC, "cover", "cover")]
    if kind == "soft":
        return [Modifier(SOFT_COVER_AC, "soft cover", "cover")]
    return []


def reflex_mods(scene, source_at, defender) -> list[Modifier]:
    """Cover's +2 on a Reflex save, which soft cover does not give.

    Separate from `ac_mods` because the two disagree: a bystander in the way is worth +4
    to AC and nothing at all against a fireball, and a rule that read the AC number would
    get that wrong in the player's favour.
    """
    grid = getattr(scene, "grid", None)
    there = scene.positions.get(defender.ref) if grid is not None else None
    if grid is None or there is None or source_at is None:
        return []
    if grid.cover_between(tuple(source_at), "medium",
                          tuple(there), defender.size) == "cover":
        return [Modifier(COVER_REFLEX, "cover", "cover")]
    return []


def explain(scene, actor, defender, weapon: dict | None = None) -> str:
    """One short phrase naming what the board is doing, for a tell.

    The narrator is fed this and never the numbers — the third law. "Flanked, and from
    above" is something a GM can say; "+3 to hit" is not.
    """
    words = [m.source for m in attack_mods(scene, actor, defender, weapon)]
    kind = cover_of(scene, actor, defender)
    if kind == "cover":
        words.append("behind cover")
    elif kind == "soft":
        words.append("shielded by somebody in the way")
    return ", ".join(words)


__all__ = ["attack_mods", "ac_mods", "cover_of", "reflex_mods", "explain",
           "FLANKING_BONUS", "HIGHER_GROUND_BONUS", "HIGHER_GROUND_SQUARES",
           "COVER_AC", "COVER_REFLEX", "SOFT_COVER_AC"]
