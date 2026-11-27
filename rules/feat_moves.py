"""The moving feats: what a feat lets its bearer do with their feet, and a charge's multiple.

Feat loop batch 4, lane b4-moves (2026-11-26). Each function here answers one moment the
engine already has — the damage roll of a blow, the outcome of a move or an attack — and
returns intents for the queue (`Engine._drive` splices them next, the way `_riders_after`
and `_step_up_after` do) or outcomes that tell what changed. Nothing here keeps a store:
a feat is a tag on its document (`content/feats/mechanics/b4-moves.json`), asked with
`has_state`, and every timed thing is an `ActiveEffect` on the one ticker.

Read before writing (the research rule): the rules are aonprd.com's FeatDisplay pages for
each feat (checked 2026-11-26, the text in content/feats/feats.json); the reaction-step
shape is this engine's own Step Up (`Engine._step_up_after`, APG), which Sidestep and
Landing Roll mirror clause for clause. Foundry PF1 models none of these as automation —
each is a chat-card reminder and the GM moves the token — so there was no prior art to
borrow beyond the book, and the engine choosing the square is this file's own call, the
one Step Up made before it (owner call, said in the lane report).

- **Charge multiples** (CRB, Lance: "A lance deals double damage when used from the back of
  a charging mount"; Spirited Charge: "When mounted and using the charge action, you deal
  double damage with a melee weapon (or triple damage with a lance)"). CRB, Combat,
  Multiplying Damage: "When you multiply damage more than once, each multiplier works off
  the original, unmultiplied damage. So if you are asked to double the damage twice, the
  end result is three times the normal damage" — so multiples ADD their extra parts.
- **Sidestep / Improved Sidestep** (APG): a melee miss lets the one missed move 5 feet as an
  immediate action, staying in the attacker's threatened area, without provoking; then no
  5-foot step next turn and 5 feet less movement (the `stepped` effect Step Up lays) —
  unless Improved Sidestep.
- **Landing Roll** (UC): tripped, an immediate action moves the faller 5 feet without
  provoking, and they are prone after it. The square chosen is out of the tripper's reach
  when one is, the reason a faller rolls.
- **Lightning Stance** (CRB): "If you take two actions to move or a withdraw action in a
  turn, you gain 50% concealment for 1 round." A grid fight has no withdraw op (a withdraw
  IS two moves out of melee), so the second move action of a turn is the one door.
- **Wings of the Androsphinx** (People of the Sands): "If a creature charges you and fails
  its attack roll, as an immediate action you can attempt a reposition combat maneuver".
"""
from __future__ import annotations

from . import grid as gridmod
from .activeeffect import ActiveEffect

SIDESTEP = "movement.sidestep"
SIDESTEP_IMPROVED = "movement.sidestep.improved"
LANDING_ROLL = "movement.landing-roll"
LIGHTNING_STANCE = "movement.lightning-stance"
WINGS = "reaction.reposition-failed-charger"
SPIRITED_CHARGE = "charge.mounted.multiplied"
MOUNTED = "state.position.mounted"


def charge_multiple(actor, weapon: dict, weapon_key: str, choices, mult: int) -> int:
    """This blow's damage multiple with a mounted charge folded in: a lance doubles from a
    charging mount, Spirited Charge doubles any melee weapon and triples a lance; with a
    critical's multiple the extra parts add (CRB, Multiplying Damage)."""
    if "charge" not in (choices or ()) or not actor.has_state(MOUNTED) \
            or str(weapon.get("category") or "melee").lower() == "ranged":
        return mult
    lance = "lance" in {str(weapon_key or "").lower(), str(weapon.get("id") or "").lower(),
                        str(weapon.get("crafted_base") or "").lower()}
    times = 1
    if actor.has_state(SPIRITED_CHARGE):
        times = 3 if lance else 2
    elif lance:
        times = 2
    return mult + times - 1


def moved_already(engine, intent) -> bool:
    """Whether this move is the turn's second move action: the mover's first walk this
    round already spent the move (`Scene.move_spent`). Asked before `_move_paid` writes."""
    sc = engine.scene
    # A closing step the engine splices before a blow is not counted: its own rule
    # (`_close_before`, `after_close`) already says what a walk leaves of the turn.
    return (intent.op == "move" and sc.in_encounter and not intent.params.get("reaction")
            and not intent.params.get("closing_on") and not intent.params.get("charging")
            and sc.move_spent.get(intent.actor or "") == sc.round)


def after(engine, intent, outcome, twice: bool = False) -> tuple[list[dict], list]:
    """(intents to splice next, outcomes telling what changed) for this act's outcome."""
    sc = engine.scene
    if not sc.in_encounter or outcome.status != "resolved":
        return [], []
    if intent.op == "move":
        return [], _second_move(engine, intent, outcome, twice)
    if intent.op != "attack":
        return [], []
    more: list[dict] = []
    more += _sidestep(engine, intent, outcome)
    more += _landing_roll(engine, intent, outcome)
    more += _wings(engine, intent, outcome)
    more += _wings_readied(engine, intent, outcome)          # feat loop b5-core
    return more, []


def _walked(outcome, ref: str):
    went = next((e for e in outcome.effects or () if e.get("kind") == "position"
                 and e.get("ref") == ref and e.get("from") is not None
                 and e.get("to") is not None), None)
    if went is None:
        return 0
    feet = went.get("feet")
    if feet is None:
        feet = gridmod.distance(tuple(went["from"])[:2], tuple(went["to"])[:2])
    return int(feet or 0)


def _second_move(engine, intent, outcome, twice: bool) -> list:
    """A second move action this turn: Lightning Stance's 50% concealment for a round is
    laid on its holder.

    Not done here, on purpose: recording the standard action as spent by the second move
    (CRB: "You can take a move action in place of a standard action"). Tried in this lane
    and backed out — the reach refusal's own repair ("Click square ...", then move and
    strike) is offered with the move already walked (tests/test_maneuver_reach.py), so
    the rule needs that advice changed first. Reported to the owner as a defect."""
    from .engine import Outcome

    actor = engine.scene.actors.get(intent.actor or "")
    if actor is None or not twice or _walked(outcome, actor.ref) <= gridmod.SQUARE_FT:
        return []
    if not actor.has_state(LIGHTNING_STANCE):
        return []
    actor.apply_effect(ActiveEffect(
        name="lightning stance", kind="buff", key="lightning stance",
        source="Lightning Stance", origin="rule:feat-lightning-stance",
        duration="rounds", rounds_left=1, tags=("buff.stance.lightning",),
        modifiers=[{"kind": "concealment", "target": "miss_chance", "amount": 50,
                    "bonus_type": "", "note": "Lightning Stance"}]))
    return [Outcome(intent_id=intent.id, op="move", actor=actor.ref,
                    effects=[{"ref": actor.ref, "kind": "buff", "buff": "lightning stance",
                              "rounds": 1, "origin": "rule:feat-lightning-stance"}],
                    tell=f"{actor.name} moves so fast they blur (Lightning Stance): 50% "
                         f"concealment until their next turn.",
                    because="Lightning Stance")]


def _missed_by_melee(intent, outcome, actor) -> list[str]:
    """The refs this melee attack missed, off its blows."""
    params = intent.params or {}
    if params.get("manoeuvre") or params.get("mode") == "splash":
        return []
    w = actor.weapon(params.get("weapon") or None) or {}
    if str(w.get("category") or "melee").lower() == "ranged":
        return []
    return list(dict.fromkeys(str(b.get("ref") or "") for b in outcome.blows or ()
                              if b.get("result") == "miss" and b.get("ref")))


def _open_squares(engine, who, around, reach_ft: int = gridmod.SQUARE_FT):
    sc = engine.scene
    taken = sc.occupied(ignore=who.ref)
    level = tuple(sc.positions[who.ref][2:3])
    out = []
    for x in range(around[0] - 2, around[0] + 3):
        for y in range(around[1] - 2, around[1] + 3):
            if (x, y) == tuple(around) or gridmod.distance(tuple(around), (x, y)) > reach_ft:
                continue
            if all(sc.grid.inside(q) and sc.grid.passable(q) and q not in taken
                   for q in gridmod.footprint((x, y), who.size)):
                out.append((x, y))
    return out, level


def _step(intent, who, square, level, feat: str, why: str) -> dict:
    return {"op": "move", "actor": who.ref, "id": f"{intent.id}-{feat}-{who.ref}",
            "target": None, "visibility": "player" if who.is_pc else "hidden",
            "because": why, "params": {"square": list(square) + list(level),
                                       "reaction": feat}}


def _sidestep(engine, intent, outcome) -> list[dict]:
    from . import reactions

    sc = engine.scene
    attacker = sc.actors.get(intent.actor or "")
    if attacker is None or not sc.has_grid or attacker.ref not in sc.positions:
        return []
    out: list[dict] = []
    for ref in _missed_by_melee(intent, outcome, attacker):
        who = sc.actors.get(ref)
        if who is None or who.is_down or not who.has_state(SIDESTEP) \
                or who.blocking_key("move") or ref not in sc.positions:
            continue
        here = tuple(sc.positions[ref][:2])
        squares, level = _open_squares(engine, who, here)
        threat = reactions.threatened_by(sc, attacker.ref, who.size)
        # "so long as you remain within that opponent's threatened area": the first open
        # square still threatened, the one fewest other foes threaten first.
        others = [r for r in sc.actors if r not in (ref, attacker.ref)
                  and not _friends(sc, r, ref)]
        ranked = sorted((sum(1 for r in others if reactions.threatens(sc, r, sq, who.size)),
                         sq[1], sq[0]) for sq in squares if sq in threat)
        if not ranked or engine._spend_swift(who, True, "Sidestep") is not None:
            continue
        _n, y, x = ranked[0]
        out.append(_step(intent, who, (x, y), level, "sidestep",
                         f"{who.name} sidesteps {attacker.name}'s miss (Sidestep)"))
        if not who.has_state(SIDESTEP_IMPROVED):
            nxt = engine._swift_turn(who) or sc.round
            who.apply_effect(ActiveEffect(
                name="sidestepped", kind="situation", key="stepped", source="Sidestep",
                origin="rule:feat-sidestep", duration="rounds",
                rounds_left=max(1, nxt - sc.round + 1),
                tags=("movement.stepped",),
                modifiers=[{"kind": "speed", "target": "land", "amount": -5,
                            "bonus_type": "untyped",
                            "note": "Sidestep: 5 ft less movement this turn"}]))
    return out


def _friends(scene, a: str, b: str) -> bool:
    from . import position

    return position._same_side(scene, a, b)


def _landing_roll(engine, intent, outcome) -> list[dict]:
    from . import reactions

    sc = engine.scene
    if (intent.params or {}).get("manoeuvre") != "trip" or not sc.has_grid:
        return []
    tripper = sc.actors.get(intent.actor or "")
    fell = [e.get("ref") for e in outcome.effects or ()
            if e.get("kind") == "condition" and e.get("condition") == "prone"
            and e.get("from") == "trip"]
    out: list[dict] = []
    for ref in dict.fromkeys(fell):
        who = sc.actors.get(str(ref))
        if who is None or tripper is None or who.is_down or ref not in sc.positions \
                or not who.has_state(LANDING_ROLL):
            continue
        here = tuple(sc.positions[ref][:2])
        squares, level = _open_squares(engine, who, here)
        threat = reactions.threatened_by(sc, tripper.ref, who.size)
        clear = sorted((sq[1], sq[0]) for sq in squares if sq not in threat)
        if not clear or engine._spend_swift(who, True, "Landing Roll") is not None:
            continue
        y, x = clear[0]
        out.append(_step(intent, who, (x, y), level, "landing-roll",
                         f"{who.name} rolls clear as they fall (Landing Roll)"))
    return out


def _wings(engine, intent, outcome) -> list[dict]:
    sc = engine.scene
    params = intent.params or {}
    if not params.get("charge") or params.get("charged") is None:
        return []
    charger = sc.actors.get(intent.actor or "")
    if charger is None or charger.is_down:
        return []
    out: list[dict] = []
    for ref in _missed_by_melee(intent, outcome, charger):
        who = sc.actors.get(ref)
        if who is None or who.is_down or not who.has_state(WINGS) \
                or who.blocking_key("attack"):
            continue
        if engine._spend_swift(who, True, "Wings of the Androsphinx") is not None:
            continue
        out.append({"op": "attack", "actor": ref, "target": charger.ref,
                    "id": f"{intent.id}-androsphinx",
                    "visibility": "player" if who.is_pc else "hidden",
                    "because": f"{who.name} turns {charger.name}'s failed charge aside "
                               f"(Wings of the Androsphinx)",
                    "params": {"full_attack": False, "reaction": "wings-of-the-androsphinx",
                               "manoeuvre": "reposition"}})
    return out


def _wings_readied(engine, intent, outcome) -> list[dict]:
    """Wings of the Androsphinx's readied clause (feat loop b5-core): "If you use a readied
    action to attack a creature charging you, you can roll to attack and then attempt to
    reposition that creature as a free action before it resolves its charge attack." The
    readied blow set against the charge (rules/readied.py, `vs_charge`) is followed, ahead of
    the charge's own blow, by the reposition — a free action, so no swift is spent."""
    params = intent.params or {}
    if params.get("reaction") != "readied" or not params.get("vs_charge"):
        return []
    who = engine.scene.actors.get(intent.actor or "")
    charger = engine.scene.actors.get(str(intent.target or ""))
    if who is None or charger is None or charger.is_down or who.is_down \
            or not who.has_state(WINGS) or who.blocking_key("attack"):
        return []
    return [{"op": "attack", "actor": who.ref, "target": charger.ref,
             "id": f"{intent.id}-androsphinx-readied",
             "visibility": "player" if who.is_pc else "hidden",
             "because": f"{who.name} turns {charger.name}'s charge aside before it lands "
                        f"(Wings of the Androsphinx)",
             "params": {"full_attack": False, "reaction": "wings-of-the-androsphinx",
                        "manoeuvre": "reposition"}}]


__all__ = ["charge_multiple", "moved_already", "after"]
