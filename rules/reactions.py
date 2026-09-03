"""Things that happen on somebody else's turn.

Everything the engine did before this was somebody's own action, taken in their own turn,
proposed by the GM. A reaction is none of those: it belongs to one creature, fires during
another creature's action, and is not proposed by anyone — it is *owed*, by the rules, the
moment its trigger happens. The GM does not get a say in whether an attack of opportunity
occurs, which is exactly why it has to live here rather than in a prompt.

The interrupt is the whole problem. `docs/intent-protocol.md` listed attacks of opportunity
under "deliberately not in v1" on the grounds that `run()` had no way to suspend one intent
to resolve another. It turns out it does: `_drive` works a queue, and a reaction is intents
spliced in *front* of the one that triggered them. They then resolve through the ordinary
machinery — including suspending for a player roll, because when the PC takes the attack of
opportunity, the PC rolls it.

Order matters and is not cosmetic. An attack of opportunity provoked by movement happens as
the creature leaves the square, not after it arrives: if the blow drops them, they never get
there. So movement triggers are resolved *before* the move applies, which is why `Engine`
asks for reactions before resolving an intent rather than after.

What a reaction costs is a budget, not a pool. 1e gives everyone one attack of opportunity
per round and Combat Reflexes raises that to 1 + Dexterity modifier — a separate allowance
that refills at the top of the round and has nothing to do with ki or rage.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import grid as gridmod

# Events the engine emits. Named and listed for the same reason `ACTOR_RULES` is: a
# reaction whose trigger is misspelled is a feature that silently never fires, and the only
# symptom is a player wondering why their ability never went off.
TRIGGERS = {
    "leaves_threatened_square": (
        "A creature moves out of a square this one threatens, without withdrawing. The "
        "classic attack of opportunity."
    ),
}


@dataclass
class Reaction:
    """One thing a creature may do when a trigger fires.

    `budget` names which allowance it spends. Attacks of opportunity share one — taking a
    swing at a fleeing goblin and at a passing ogre in the same round is two of the same
    resource — so the allowance is named rather than being a counter per reaction.
    """
    id: str
    trigger: str
    op: str = "attack"
    params: dict = field(default_factory=dict)
    budget: str = "attack_of_opportunity"
    source: str = ""
    because: str = ""


def attack_of_opportunity(actor) -> Reaction:
    return Reaction(
        id="attack_of_opportunity",
        trigger="leaves_threatened_square",
        op="attack",
        source="attack of opportunity",
        because="they moved out of reach",
    )


def reactions_for(actor) -> list[Reaction]:
    """Everything this creature may react with.

    Every creature that can act has the attack of opportunity, because 1e gives it to
    everyone rather than to anyone in particular. Class- and feat-granted reactions will
    layer on here; Blood Bending's paths are built on them, which is why the shape is a
    list rather than a single hard-coded case.
    """
    # The attack question, not the general one. A nauseated creature may take its
    # single move action and may not swing, and asking `can_act` gave it the attack
    # of opportunity back the moment the vocabulary let it move again. A spliced
    # reaction never passes `validate`, so this is the only gate it meets.
    if actor.blocking_key("attack"):
        return []
    return [attack_of_opportunity(actor)]


def budget_for(actor, name: str = "attack_of_opportunity") -> int:
    """How many of these a creature gets in a round.

    1e: one, "plus one additional attack of opportunity for every point of Dexterity bonus"
    with Combat Reflexes. The feat is checked by name because that is how feats are held on
    the sheet; a creature with a negative Dexterity modifier still gets its one.
    """
    # Stage 8: the count comes from the feat's document (`budget`), not from a
    # substring match on the sheet — which also matched "mythic combat reflexes".
    # The best budget any held feat declares, and never fewer than one.
    from . import feats as feats_mod, resources

    best = 1
    for raw in getattr(actor, "feats", ()) or ():
        doc = feats_mod.document(raw)
        formula = ((doc or {}).get("budget") or {}).get(name)
        if formula is None:
            continue
        try:
            best = max(best, resources.evaluate(formula, actor))
        except resources.FormulaError:
            continue
    return best


def threatens(scene, watcher_ref: str, square) -> bool:
    """Does this creature threaten that square?

    False for anything the scene cannot place, which is every creature on a scene with no
    map. A reaction that fired on an unmeasurable battlefield would be the engine inventing
    geometry, and the GM's zones do not carry enough to tell whether a square was left.
    """
    if not scene.has_grid:
        return False
    anchor = scene.positions.get(watcher_ref)
    watcher = scene.actors.get(watcher_ref)
    # Threatening a square is about being able to swing into it.
    if anchor is None or watcher is None or watcher.blocking_key("attack"):
        return False
    reach = _reach_of(watcher)
    if reach <= 0:
        return False
    threatened = gridmod.threatened_squares(anchor, watcher.size, reach=reach)
    if reach_gap(watcher):
        # A reach weapon cannot strike what is right beside you. Subtracting the adjacent
        # ring here rather than in `grid` keeps geometry ignorant of inventory.
        threatened -= gridmod.threatened_squares(anchor, watcher.size,
                                                 reach=gridmod.SQUARE_FT)
    return tuple(square) in threatened


def _reach_of(actor) -> int:
    """Reach in feet, weapon included.

    This was natural reach only for as long as `tables.WEAPONS` held eleven weapons and
    none of them had a trait field. The weapons import brought 40 reach weapons with it,
    so the branch is real now — and both halves of the rule land together, because the
    half that is easy to forget is the one that costs the player: a reach weapon doubles
    the threatened area *and* stops the wielder threatening adjacent squares. Implementing
    only the first would make a glaive strictly better in the app than at a table.

    The adjacent hole is the caller's to apply — `threatened_squares` is geometry and does
    not know what anybody is holding — so `reach_gap` says whether there is one.

    Still missing: 1e says an unarmed creature without Improved Unarmed Strike does not
    threaten at all. Left out because it would silently disarm every monster in the
    bestiary, none of which carry the feat.
    """
    from . import weapons as weapons_mod

    natural = gridmod.natural_reach(actor.size)
    if weapons_mod.has_trait(actor.equipped or "", "reach"):
        return natural * 2
    return natural


def reach_gap(actor) -> bool:
    """Does this creature's weapon leave the squares next to it unthreatened?

    True only for a reach weapon. A creature with natural reach — an ogre — threatens
    everything out to ten feet including what is under its nose.
    """
    from . import weapons as weapons_mod

    return weapons_mod.has_trait(actor.equipped or "", "reach")


def provoked_by_move(scene, mover_ref: str, start, end) -> list[tuple[str, Reaction]]:
    """Who gets an attack of opportunity because this creature moved, and with what.

    1e: leaving a threatened square provokes. *Entering* one does not, and neither does a
    five-foot step — "you can move 5 feet in any round when you don't perform any other
    kind of movement" is the whole point of it, and treating a step as a move would make
    the safest option in the game the most dangerous one.

    A creature does not provoke from its allies, but the app has no side model for NPCs
    beyond `scene.sides`, so this asks that. Where sides are not declared, everybody who
    threatens gets the swing — which is the rule, and is also what a solo character walking
    into a room of strangers should expect.
    """
    if start is None or not scene.has_grid or start == end:
        return []

    mover = scene.actors.get(mover_ref)
    if mover is None:
        return []

    # A five-foot step provokes nothing. Measured rather than declared, because a GM that
    # has to remember to say "this is a step" will not.
    if gridmod.distance(tuple(start), tuple(end)) <= gridmod.SQUARE_FT:
        return []

    left = set(gridmod.footprint(tuple(start), mover.size))
    arrived = set(gridmod.footprint(tuple(end), mover.size))

    out: list[tuple[str, Reaction]] = []
    for ref, watcher in scene.actors.items():
        if ref == mover_ref or _allied(scene, ref, mover_ref):
            continue
        # Squares this watcher threatened that the mover has now vacated. Comparing
        # against the squares it *left* rather than the ones it crossed is deliberate: the
        # engine does not know the route the mover took, and inventing one would hand out
        # attacks of opportunity nobody at a table would have allowed.
        vacated = {sq for sq in left - arrived if threatens(scene, ref, sq)}
        if not vacated:
            continue
        for reaction in reactions_for(watcher):
            if reaction.trigger == "leaves_threatened_square":
                out.append((ref, reaction))
    return out


def _allied(scene, a: str, b: str) -> bool:
    for members in (scene.sides or {}).values():
        if a in members and b in members:
            return True
    return False


__all__ = ["Reaction", "TRIGGERS", "budget_for", "provoked_by_move", "reactions_for",
           "threatens"]
