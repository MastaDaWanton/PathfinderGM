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

from dataclasses import dataclass

from .dice import Modifier
from .grid import SQUARE_FT, distance_between, enters_occupied, flanking, footprint

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
    the refs on it — and it is only populated inside an encounter. Outside one, or for an
    attacker nobody has assigned, the answer is "yes": a scene with no declared sides is
    one where the engine has not been told otherwise, and refusing every flank there
    would silently switch the rule off for every fight that started without `sides`.
    Inside one, a would-be ally on no side is a bystander and the answer is "no".
    """
    sides = getattr(scene, "sides", None) or {}
    mine = next((s for s, refs in sides.items() if a in refs), None)
    theirs = next((s for s, refs in sides.items() if b in refs), None)
    if mine is None:
        return True
    if theirs is None:
        # A fight with declared sides, and this one is in none of them: a bystander,
        # who is helping nobody. Measured 2026-10-04 (the robbers in the warrens): the
        # second robber's natural 20 was confirmed at 17 against AC 17 only because the
        # +2 read "flanking with the basket carrier" — the robbers' own VICTIM, pressed
        # to the wall and on no side — and the confirmed critical put the player at -2.
        # The "unassigned is an ally" answer above was written for a scene with no
        # sides at all, and it still holds there.
        return False
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
    # Solid things only. Fog and smoke were counted as walls here until alchemy lane C
    # (2026-10-06): a smokestick, and the fog cloud spell itself, made whoever stood in
    # them untargetable as TOTAL cover, where the book gives "concealment (attacks have a
    # 20% miss chance)" within 5 ft and 50% beyond (CRB, fog cloud). The miss chance is
    # the attack's (`Engine._fog_chance`, read through `Actor.concealment`).
    hard = grid.cover_between(tuple(here), actor.size, tuple(there), defender.size,
                              solid_only=True)
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
                          tuple(there), defender.size, solid_only=True) == "cover":
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


# --- Reach: whether the blow lands at all ------------------------------------------------
#
# The board's one question that is not a modifier. Measured 2026-09-27: `_ensure_encounter`
# lays a foe with no zone at `near`, fifteen feet off, and from there a disarm, a trip, a
# grapple and a plain rapier thrust all resolved, because nothing between the intent and
# the dice asked how far away the target stood. "With a normal melee weapon, you can strike
# any opponent within 5 feet" (Core Rulebook p.182, aonprd.com/Rules.aspx?ID=131), and a
# manoeuvre made in place of a melee attack reaches no further (p.198).
#
# Asked here rather than in the engine because two doors need the same answer: the engine
# refusing a declared blow (`Engine._reach_refusal`), and a creature's own turn composed
# without a model (`judgement.default_npc_action`, `Engine.struck_first`) closing the
# distance before it swings. Two copies of "how far does a glaive reach" would disagree
# with each other the first time either was edited. Still nothing mutates.


@dataclass(frozen=True)
class OutOfReach:
    """How a melee blow falls short: the gap, the reach, and why the reach is what it is."""
    feet: int
    reach: int
    gap: bool             # a reach weapon, which cannot strike what is beside it
    with_weapon: bool     # the reach is the weapon's, not the body's

    @property
    def too_close(self) -> bool:
        return self.gap and self.feet <= SQUARE_FT


def out_of_reach(scene, actor, defender, weapon_key: str | None,
                 manoeuvre: str = "", thrown: bool = False) -> OutOfReach | None:
    """None when this blow can land from where the two of them stand — or when the board
    cannot say (no map, either of them off it: a distance nobody measured is not a
    refusal), or when it is not a melee blow at all (a bow, a thrown knife).

    A manoeuvre made with the weapon (`MANEUVERS_WITH_THE_WEAPON`: disarm, sunder,
    trip) reaches as far as the weapon does, which is what a whip is for; every other
    one is the body's and reaches as far as the body.
    """
    from . import reactions
    from .tables import MANEUVERS_WITH_THE_WEAPON

    if defender is None or actor is None or defender.ref == actor.ref:
        return None
    try:
        weapon = actor.weapon(weapon_key) if weapon_key else {}
    except KeyError:
        weapon = {}
    if not manoeuvre and (not _melee(weapon) or (
            thrown and (weapon.get("range_ft") or weapon_key == "improvised"))):
        return None
    feet = scene.distance_between(actor.ref, defender.ref)
    if feet is None:
        return None
    with_weapon = not manoeuvre or manoeuvre in MANEUVERS_WITH_THE_WEAPON
    reach, gap = reactions.reach_with(actor, weapon_key if with_weapon else None)
    miss = OutOfReach(feet, reach, gap, with_weapon)
    if feet <= reach and not miss.too_close:
        return None
    return miss


def occupancy_toward(scene, actor, defender) -> set[tuple[int, int]]:
    """The squares `actor` must route around on its way to `defender`.

    Everybody's but its own — and, for a creature small enough to share a square
    (`grid.enters_occupied`: Fine, Diminutive, Tiny), not its target's either: "They
    must enter an opponent's square to attack in melee" (aonprd.com/Rules.aspx?ID=179).
    Before this, a Tiny creature's reach of 0 named exactly one square to attack from,
    the target's own, and this set always held it — so a Clockwork Spy forty feet off
    was told "There is no open square in reach" and never moved (2026-10-01).

    Only the target's squares open up, though the rule lets a Tiny creature through any
    occupied square: passing through somebody provokes from them, and the engine knows
    where a move ends, not the route it took (`reactions.provoked_by_move` says why it
    will not invent one), so a route through a stranger would be a swing nobody owed.
    """
    taken = scene.occupied(ignore=actor.ref)
    there = scene.positions.get(defender.ref) if defender is not None else None
    if there is not None and enters_occupied(actor.size):
        taken -= set(footprint(tuple(there[:2]), defender.size))
    return taken


def square_in_reach(scene, actor, defender, reach: int,
                    gap: bool = False) -> tuple[tuple[int, int], int] | None:
    """The cheapest open square from which `actor` reaches `defender`, and what the walk
    there costs in feet; None when there is none.

    Walked with `Grid.reachable` over the same occupancy `Engine._check_move` refuses by,
    so a square named here is one the move op will accept. Ties go to the square
    squarest-on to the target — the first cut named the diagonal [6, 9] for a thug
    straight ahead at [7, 10] — then the lower row and column, so the same board always
    names the same square. For a creature with a reach of 0 the square is the target's
    own (`occupancy_toward`).
    """
    grid = getattr(scene, "grid", None)
    start = scene.positions.get(actor.ref)
    there = scene.positions.get(defender.ref)
    if grid is None or start is None or there is None:
        return None
    level = tuple(start[2:3])
    routes = grid.reachable(tuple(start[:2]), 10_000, size=actor.size,
                            occupied=occupancy_toward(scene, actor, defender))
    best = None
    for square, cost in routes.items():
        flat = tuple(square[:2])
        feet = distance_between(flat + level, actor.size, there, defender.size)
        if feet > reach or (gap and feet <= SQUARE_FT):
            continue
        rank = (cost, (flat[0] - there[0]) ** 2 + (flat[1] - there[1]) ** 2,
                flat[1], flat[0])
        if best is None or rank < best[0]:
            best = (rank, flat, cost)
    return None if best is None else (best[1], best[2])


def closing_move(scene, actor, defender,
                 weapon_key: str | None) -> tuple[dict, bool] | None:
    """The move a creature makes toward `defender`, as a raw intent, and whether it ends
    in reach — so a blow can follow it this turn. None when it is in reach already,
    when the board cannot say, or when there is no open ground to cover.

    Too far for one move, it goes as far as one move takes it toward them: a thug forty
    feet off spends his turn crossing the room, which is what 1e has him do, rather than
    standing still because the square he wanted was out of range.

    For the turns the engine composes on a creature's behalf. A blow a model or the
    player declared is closed by `Engine._closing_step` instead (the owner's ruling of
    2026-09-29: "close the distance and strike if one move reaches"), which walks only
    when the step ARRIVES — a declared blow more than one move off is refused with the
    square named, never turned into a walk the player did not ask for. A fallback that
    swung from where it stood would be refused every round, and "holds back" at
    fifteen feet, for ever, is the bug the fallback was written to end.
    """
    miss = out_of_reach(scene, actor, defender, weapon_key)
    if miss is None:
        return None
    found = square_in_reach(scene, actor, defender, miss.reach, miss.gap)
    speed = int(getattr(actor, "speed_feet", 0) or 0)
    arrives = found is not None and not (speed and found[1] > speed)
    if arrives:
        square = found[0]
    else:
        start = scene.positions.get(actor.ref)
        there = scene.positions.get(defender.ref)
        grid = getattr(scene, "grid", None)
        if grid is None or start is None or there is None or not speed:
            return None
        level = tuple(start[2:3])
        routes = grid.reachable(tuple(start[:2]), speed, size=actor.size,
                                occupied=occupancy_toward(scene, actor, defender))
        here = distance_between(tuple(start), actor.size, there, defender.size)
        nearer = [(distance_between(tuple(q[:2]) + level, actor.size, there,
                                    defender.size), cost, q[1], q[0])
                  for q, cost in routes.items()]
        nearer = [n for n in nearer if n[0] < here]
        if not nearer:
            return None
        _, _, y, x = min(nearer)
        square = (x, y)
    return ({"op": "move", "actor": actor.ref,
             "params": {"square": [square[0], square[1]]},
             "because": f"closing on {defender.name}"}, arrives)


__all__ = ["attack_mods", "ac_mods", "cover_of", "reflex_mods", "explain",
           "OutOfReach", "out_of_reach", "square_in_reach", "closing_move",
           "occupancy_toward",
           "FLANKING_BONUS", "HIGHER_GROUND_BONUS", "HIGHER_GROUND_SQUARES",
           "COVER_AC", "COVER_REFLEX", "SOFT_COVER_AC"]
