"""The 5-foot step (CRB, Combat, "Take 5-Foot Step"; aonprd.com/Rules.aspx?ID=167, read
2026-11-26): "You can move 5 feet in any round when you don't perform any other kind of
movement. Taking this 5-foot step never provokes an attack of opportunity. You can't take
more than one 5-foot step in a round, and you can't take a 5-foot step in the same round
that you move any distance ... You can't take a 5-foot step into difficult terrain".

Measured before (feat loop b4-moves' Pack Attack): a one-square move was a step by its
distance alone (`reactions.provoked_by_move`), so a fighter who walked 30 feet past an ogre
and then one square more was spared the ogre's swing, a step after a step was free, and a
step into rubble provoked nothing. Now the round's walking is the scene's ledger
(`Scene.walked`, `move_spent`'s shape: the round, and whether that round's first movement
was a step) and three rules read it:

- a one-square move is a step only as the round's first movement, into a square that costs
  5 feet (difficult terrain doubles it; Nimble Moves' and Acrobatic Steps' `difficult_ft`
  forgive it, `Engine._easy_ft`), and not in the turn after Step Up (`movement.stepped`);
- no movement follows a step in the same round (refused, `after_step_refusal`);
- anything that is not a step provokes as movement does.

Pack Attack (UC): "When you are adjacent to an ally with this feat, the first time you melee
attack an opponent, you can spend an immediate action to take a 5-foot step, even if you
have otherwise moved this round" — a one-square move by its holder, beside such an ally,
after a melee blow this turn, is that step and spends the immediate action.

Prior art: Foundry PF1 and Roll20 leave the step to the table; PCGen does not model a turn.
Owlcat's Pathfinder CRPGs enforce exactly these three (a step is unavailable once you have
moved, and in difficult terrain), which is the shape taken here.
"""
from __future__ import annotations

from . import grid as gridmod

PACK_ATTACK = "teamwork.pack-attack"


def walked(scene, ref: str) -> str:
    """This round's movement so far: "" for none, "step" or "move"."""
    got = (getattr(scene, "walked", None) or {}).get(ref)
    if not got or int(got[0]) != int(scene.round):
        return ""
    return str(got[1])


def _difficult(scene, actor, end) -> bool:
    grid = getattr(scene, "grid", None)
    if grid is None:
        return False
    squares = set(gridmod.footprint(tuple(end)[:2], actor.size))
    if not squares & set(grid.difficult or ()):
        return False
    from .engine import Engine

    return Engine._easy_ft(actor) < gridmod.SQUARE_FT


def is_step(scene, actor, start, end) -> bool:
    """Whether a move from `start` to `end` is the round's 5-foot step."""
    if start is None or end is None or actor is None:
        return False
    if gridmod.distance(tuple(start)[:2], tuple(end)[:2]) > gridmod.SQUARE_FT:
        return False
    if not scene.in_encounter:
        return True
    if walked(scene, actor.ref) or actor.has_state("movement.stepped"):
        return pack_attack(scene, actor)
    return not _difficult(scene, actor, end)


def pack_attack(scene, actor) -> bool:
    """Pack Attack's immediate step is open: the holder swung in melee this turn and stands
    beside an ally who holds the feat too. The immediate action is spent by `record`."""
    if not actor.has_state(PACK_ATTACK) or scene.swung.get(actor.ref) != scene.round:
        return False
    from .reactions import _allied

    for ref, ally in scene.actors.items():
        if ref == actor.ref or ally.is_down or not ally.has_state(PACK_ATTACK) \
                or not _allied(scene, ref, actor.ref):
            continue
        if (scene.distance_between(ref, actor.ref) or 99) <= gridmod.SQUARE_FT:
            return True
    return False


def after_step_refusal(scene, actor, start, end) -> str:
    """Why this move cannot be made: the round's 5-foot step was taken, and "you can't take
    a 5-foot step in the same round that you move any distance" cuts both ways. ""."""
    if not scene.in_encounter or start is None or end is None \
            or tuple(start)[:2] == tuple(end)[:2]:
        return ""
    if walked(scene, actor.ref) != "step":
        return ""
    if gridmod.distance(tuple(start)[:2], tuple(end)[:2]) <= gridmod.SQUARE_FT \
            and pack_attack(scene, actor):
        return ""
    return (f"{actor.name} took a 5-foot step this round, and no other movement may follow "
            f"it until their next turn.")


def record(engine, actor, start, end) -> str:
    """Write this round's movement; returns "step", "move" or "pack" (Pack Attack's)."""
    scene = engine.scene
    if not scene.in_encounter or start is None or end is None \
            or tuple(start)[:2] == tuple(end)[:2]:
        return ""
    before = walked(scene, actor.ref)
    step = is_step(scene, actor, start, end)
    kind = "move"
    if step and (before or actor.has_state("movement.stepped")):
        kind = "pack"
        engine._spend_swift(actor, True, "Pack Attack")
    elif step:
        kind = "step"
    if not hasattr(scene, "walked") or scene.walked is None:
        scene.walked = {}
    scene.walked[actor.ref] = [scene.round, "move" if before == "move" or kind == "move"
                               else "step"]
    return kind
