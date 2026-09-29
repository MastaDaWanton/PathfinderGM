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
    # 1e Table 7-2 marks some actions as provoking wherever they are taken: "Pick up an
    # item — move action — attack of opportunity: yes". The first of them wired here is
    # the pick-up, because the disarm puts a weapon on the ground and a creature stooping
    # for it is the one moment in a fight its guard is down on purpose (TemplePlus's
    # "Retrieve Disarmed Weapon ... will provoke an AoO if done within combat").
    "provoking_action": (
        "A creature in a square this one threatens takes an action the rules say "
        "provokes — picking an item up off the ground."
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
    # Further triggers the same reaction answers. An attack of opportunity is ONE
    # reaction with one allowance whether the goblin fled or stooped, so it is one
    # record that fires on both rather than two records a budget could count twice.
    also: tuple[str, ...] = ()

    def fires_on(self, trigger: str) -> bool:
        return trigger == self.trigger or trigger in self.also


def attack_of_opportunity(actor) -> Reaction:
    return Reaction(
        id="attack_of_opportunity",
        trigger="leaves_threatened_square",
        also=("provoking_action",),
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
    return tuple(square) in threatened_by(scene, watcher_ref)


def threatened_by(scene, watcher_ref: str) -> set:
    """Every square this creature threatens right now — `threatens`, as the whole set.

    Split out so a question asked of many squares (the way out of a fight,
    `provoked_by_withdraw`) builds the set once per watcher instead of once per square.
    One rule either way: `threatens` is this set's membership test.
    """
    if not scene.has_grid:
        return set()
    anchor = scene.positions.get(watcher_ref)
    watcher = scene.actors.get(watcher_ref)
    # Threatening a square is about being able to swing into it.
    if anchor is None or watcher is None or watcher.blocking_key("attack"):
        return set()
    if disarmed_and_empty_handed(scene, watcher):
        return set()
    reach = _reach_of(watcher)
    if reach <= 0:
        return set()
    threatened = gridmod.threatened_squares(anchor, watcher.size, reach=reach)
    if reach_gap(watcher):
        # A reach weapon cannot strike what is right beside you. Subtracting the adjacent
        # ring here rather than in `grid` keeps geometry ignorant of inventory.
        threatened -= gridmod.threatened_squares(anchor, watcher.size,
                                                 reach=gridmod.SQUARE_FT)
    return threatened


def disarmed_and_empty_handed(scene, actor) -> bool:
    """Knocked out of its weapon and holding nothing: 1e's "an unarmed character can't
    take attacks of opportunity", in the one case this engine can say it safely.

    `_reach_of` below explains why the general rule is not applied — every bestiary
    creature fights with an empty `weapons` list, so "unarmed threatens nothing" would
    stop the whole bestiary threatening. A creature whose own weapon lies on the ground
    (the props ledger says so) is not that case: it HAD a weapon and lost it. Without
    this, a pick-up provoking (Table 7-2) handed the disarmed thug a punch at the player
    stooping for his sap, which the rule gives him no hand to throw. A body that is
    its own weapon — claws, a bite — or Improved Unarmed Strike still threatens
    (the Paizo forum's disarmed orc "doesn't threaten" unless it has natural attacks).
    """
    if str(getattr(actor, "equipped", "") or "unarmed").lower() != "unarmed":
        return False
    out = getattr(scene, "out_of_hand", None)
    if out is None or not any(out(actor.ref, w) for w in _own_weapons_off(scene, actor)):
        return False
    doc = actor._race_doc() if hasattr(actor, "_race_doc") else None
    if (doc or {}).get("weapons"):
        return False
    feats = [actor._feat_name(str(f)) for f in (getattr(actor, "feats", ()) or ())]
    return "improved unarmed strike" not in feats


def _own_weapons_off(scene, actor) -> list[str]:
    """What this creature owns that the props ledger has somewhere other than its hand."""
    return [str(r.get("from_")) for r in getattr(scene, "props", ()) or ()
            if r.get("owner") == actor.ref and r.get("from_")]


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
    return reach_with(actor, actor.equipped)[0]


def reach_gap(actor) -> bool:
    """Does this creature's weapon leave the squares next to it unthreatened?

    True only for a reach weapon. A creature with natural reach — an ogre — threatens
    everything out to ten feet including what is under its nose.
    """
    return reach_with(actor, actor.equipped)[1]


def reach_with(actor, weapon_key: str | None) -> tuple[int, bool]:
    """(reach in feet, whether the adjacent squares are out of it) for a swing made with
    this weapon — `None` for the body alone.

    The one rule behind both questions the board asks of a melee blow: what a creature
    threatens on somebody else's turn (`_reach_of`, with the weapon in hand) and whether
    the blow it declares on its own turn can land at all (`Engine._reach_refusal`, with
    the weapon it named — a glaive-wielder who punches has a fist's reach, not the
    glaive's). Written once so the attack of opportunity and the attack cannot disagree
    about how far a glaive goes.
    """
    from . import weapons as weapons_mod

    natural = gridmod.natural_reach(actor.size)
    if weapon_key and weapons_mod.has_trait(weapon_key, "reach"):
        return natural * 2, True
    return natural, False


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

    from . import states

    out: list[tuple[str, Reaction]] = []
    for ref, watcher in scene.actors.items():
        if ref == mover_ref or _allied(scene, ref, mover_ref):
            continue
        # A bystander is watching, not fighting, and joins a fight only by joining it
        # (`Engine.join_fight`, or a blow of their own). Measured 2026-09-27, the day
        # creatures began closing to reach before they swing: the merchant beside the
        # man in the apron took an attack of opportunity as he stepped in, knocked him
        # unconscious, and was drawn into a fight the scene had kept him out of.
        if watcher.has_state(states.BYSTANDER):
            continue
        # Squares this watcher threatened that the mover has now vacated. Comparing
        # against the squares it *left* rather than the ones it crossed is deliberate: the
        # engine does not know the route the mover took, and inventing one would hand out
        # attacks of opportunity nobody at a table would have allowed.
        vacated = {sq for sq in left - arrived if threatens(scene, ref, sq)}
        if not vacated:
            continue
        for reaction in reactions_for(watcher):
            if reaction.fires_on("leaves_threatened_square"):
                out.append((ref, reaction))
    return out


def provoked_by_action(scene, actor_ref: str) -> list[tuple[str, Reaction]]:
    """Who gets an attack of opportunity because this creature, where it stands, took an
    action that provokes.

    Every creature not on its side that threatens any square it fills — the same
    `threatens` a move asks, so reach weapons, the hole beside a glaive and a watcher who
    cannot swing all answer the same way here. Nothing on a scene with no map, for the
    reason `threatens` gives.
    """
    if not scene.has_grid:
        return []
    actor = scene.actors.get(actor_ref)
    anchor = scene.positions.get(actor_ref)
    if actor is None or anchor is None:
        return []
    filled = set(gridmod.footprint(tuple(anchor), actor.size))
    out: list[tuple[str, Reaction]] = []
    for ref, watcher in scene.actors.items():
        if ref == actor_ref or _allied(scene, ref, actor_ref):
            continue
        if not any(threatens(scene, ref, sq) for sq in filled):
            continue
        for reaction in reactions_for(watcher):
            if reaction.fires_on("provoking_action"):
                out.append((ref, reaction))
    return out


# The most watchers the way-out search weighs every combination of. The search tries
# each set of attackers of opportunity from the smallest up, so it is 2^n walks of the
# board: six is 64 walks and covers any fight this app has run. Past it, see
# `_owed_on_the_way_out`'s fallback.
_MOST_TO_WEIGH = 6


def provoked_by_withdraw(scene, mover_ref: str) -> list[tuple[str, Reaction]]:
    """Who gets an attack of opportunity because this creature walks out of the fight.

    Leaving a fight for somewhere else — a `travel` or a `journey` begun mid-encounter —
    is the WITHDRAW action (CRB p.188, aonprd.com/Rules.aspx?Name=Withdraw&Category=
    Full-Round%20Actions), not a plain move, because it is the one action 1e gives for
    exactly this and a player walking off the board is spending the whole round on it:

    - "The square you start out in is not considered threatened by any opponent you can
      see", so a visible foe who threatens only that square gets no swing. One man with
      a club beside you does not get a free hit as you back away from him.
    - "Invisible enemies still get attacks of opportunity against you, and you can't
      withdraw from combat if you're blinded" — so an unseen foe keeps the start square,
      and a blinded mover keeps no exemption at all.
    - "If, during the process of withdrawing, you move out of a threatened square (other
      than the one you started in), enemies get attacks of opportunity as normal." This
      is where reach comes back in: an ogre beside you threatens every square you can
      step into, so it still swings; a glaive-wielder standing ten feet off does not,
      because the first step directly away is out of his reach.

    The destination is off the map — another place — so the route is not the player's
    to draw here. What is decided instead is the route a sensible withdrawer would take:
    the way off the board (an unthreatened square, or the map's edge) that leaves the
    fewest foes owed a swing, by `_owed_on_the_way_out`. Each foe is owed at most once
    however many of its squares are crossed ("Moving out of more than one square
    threatened by the same opponent in the same round doesn't count as more than one
    opportunity", CRB p.180). A five-foot step never applies: a walk out of the place is
    more than five feet by definition.

    Allies, bystanders and anyone who cannot swing are skipped exactly as
    `provoked_by_move` skips them. Nothing on a scene with no map, for `threatens`'s
    reason.
    """
    if not scene.has_grid:
        return []
    mover = scene.actors.get(mover_ref)
    at = scene.positions.get(mover_ref)
    if mover is None or at is None:
        return []
    start = (at[0], at[1])

    from . import states

    watchers: dict[str, tuple[list[Reaction], set]] = {}
    for ref, watcher in scene.actors.items():
        if ref == mover_ref or _allied(scene, ref, mover_ref):
            continue
        if watcher.has_state(states.BYSTANDER):
            continue
        owed = [r for r in reactions_for(watcher) if r.fires_on("leaves_threatened_square")]
        zone = threatened_by(scene, ref) if owed else set()
        if zone:
            watchers[ref] = (owed, zone)
    if not watchers:
        return []

    cache: dict = {}

    def threat(anchor) -> frozenset:
        if anchor not in cache:
            body = gridmod.footprint(anchor, mover.size)
            cache[anchor] = frozenset(r for r, (_owed, zone) in watchers.items()
                                      if any(sq in zone for sq in body))
        return cache[anchor]

    at_start = threat(start)
    if mover.has_state("state.senses.blinded"):
        # "You can't withdraw from combat if you're blinded": no square is exempt.
        seen: set[str] = set()
    else:
        seen = {r for r in at_start if _seen_by(scene, mover_ref, r)}
    owed_refs = (at_start - seen) | _owed_on_the_way_out(scene, mover_ref, start, threat,
                                                         set(watchers), at_start)

    out: list[tuple[str, Reaction]] = []
    for ref in scene.actors:                  # the scene's order, so the swings are stable
        if ref in owed_refs:
            out.extend((ref, reaction) for reaction in watchers[ref][0])
    return out


def _seen_by(scene, viewer_ref: str, ref: str) -> bool:
    """Can the withdrawer see this foe — the Withdraw clause's "any opponent you can see".

    Unseen is the vocabulary's `state.hidden` (invisible, or anything a document hides
    under it) or no clear line between the two on the map (a wall, a fog cloud's
    obscuring squares). Not modelled: see invisibility, darkness and its darkvision —
    the map has no light level yet, so a foe in the dark reads as seen.
    """
    foe = scene.actors.get(ref)
    viewer = scene.actors.get(viewer_ref)
    if foe is None or viewer is None or foe.has_state("state.hidden"):
        return False
    a, b = scene.positions.get(viewer_ref), scene.positions.get(ref)
    if a is None or b is None:
        return False
    mine = gridmod.footprint((a[0], a[1]), viewer.size)
    theirs = gridmod.footprint((b[0], b[1]), foe.size)
    return any(scene.grid.line_of_sight(p, q) for p in mine for q in theirs)


def _owed_on_the_way_out(scene, mover_ref: str, start, threat, candidates: set,
                         at_start: frozenset) -> set:
    """The fewest foes whose threatened squares the withdrawer must leave after the first.

    A breadth-first walk of the board from the start square, stepping only where the
    mover's body fits (inside no wall, on no foe's body — allies may be passed, as the
    rule allows), until it reaches a square nobody threatens or steps off the map's
    edge. Every square left on the way after the start provokes from whoever threatens
    it, so the walk is tried with each set of foes allowed to threaten the squares it
    crosses, smallest set first; the first set with a way out is the answer. Ties go to
    the scene's order, which keeps the choice stable from run to run.

    Past `_MOST_TO_WEIGH` foes, and when no way out exists at all (walled in, or the only
    gap is through somebody), the answer is every foe who threatens the start square or
    any square beside it — a withdrawer surrounded that thoroughly has nowhere clean to
    go, and handing the swings out generously is the rule's own default ("enemies get
    attacks of opportunity as normal").
    """
    from itertools import combinations

    grid = scene.grid
    mover = scene.actors[mover_ref]
    bodies: set = set()
    for ref, anchor in scene.positions.items():
        other = scene.actors.get(ref)
        if ref == mover_ref or other is None or _allied(scene, ref, mover_ref):
            continue
        # "You can move through a square occupied by a helpless opponent without
        # penalty" (CRB p.193, Moving Through a Square) — the dead included.
        if other.is_helpless or other.is_down:
            continue
        bodies.update(gridmod.footprint((anchor[0], anchor[1]), other.size))

    steps = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]

    def way_out(allowed: frozenset) -> bool:
        seen = {start}
        frontier = [start]
        while frontier:
            nxt = []
            for x, y in frontier:
                for dx, dy in steps:
                    q = (x + dx, y + dy)
                    if q in seen:
                        continue
                    seen.add(q)
                    body = gridmod.footprint(q, mover.size)
                    if any(not grid.inside(sq) for sq in body):
                        return True          # off the edge of the board: out of the fight
                    if any(sq in grid.blocked or sq in bodies for sq in body):
                        continue
                    here = threat(q)
                    if not here:
                        return True
                    if here <= allowed:
                        nxt.append(q)
            frontier = nxt
        return False

    order = [r for r in scene.actors if r in candidates]
    if len(order) <= _MOST_TO_WEIGH:
        for k in range(len(order) + 1):
            for allowed in combinations(order, k):
                if way_out(frozenset(allowed)):
                    return set(allowed)
    beside = {(start[0] + dx, start[1] + dy) for dx, dy in steps}
    return set(at_start).union(*(threat(q) for q in beside))


def _allied(scene, a: str, b: str) -> bool:
    for members in (scene.sides or {}).values():
        if a in members and b in members:
            return True
    return False


__all__ = ["Reaction", "TRIGGERS", "budget_for", "disarmed_and_empty_handed",
           "provoked_by_action", "provoked_by_move", "provoked_by_withdraw", "reach_with",
           "reactions_for", "threatened_by", "threatens"]
