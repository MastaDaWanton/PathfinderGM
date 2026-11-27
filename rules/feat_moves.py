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
from . import stepping
from .activeeffect import ActiveEffect

SIDESTEP = "movement.sidestep"
SIDESTEP_IMPROVED = "movement.sidestep.improved"
LANDING_ROLL = "movement.landing-roll"
LIGHTNING_STANCE = "movement.lightning-stance"
WIND_STANCE = "movement.wind-stance"                  # feat loop b5-other
EASY_SPENT = "movement.difficult.spent"               # feat loop b5-other
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
        _spend_easy(engine, intent, outcome)
        spend_allowance(engine, intent, outcome)          # feat loop b7-moves
        return [], (_second_move(engine, intent, outcome, twice)
                    + _wind_stance(engine, intent, outcome, twice)
                    + _ride_by_walk(engine, intent, outcome))
    if intent.op == "use_item":
        said = _walk_earned(engine, intent, outcome)      # feat loop b7-moves: Wand Dancer
        _wand_dancer_after(engine, intent)
        return [], said
    if intent.op != "attack":
        return [], []
    said = _walk_earned(engine, intent, outcome)          # feat loop b7-moves
    _mark_pounce(engine, intent, outcome)
    _count_unarmed(engine, intent, outcome)
    more: list[dict] = []
    more += _cleave_through(engine, intent, outcome)
    more += _mounted_blade(engine, intent, outcome)
    more += _sidestep(engine, intent, outcome)
    more += _landing_roll(engine, intent, outcome)
    more += _wings(engine, intent, outcome)
    more += _wings_readied(engine, intent, outcome)          # feat loop b5-core
    return more, said


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
    """A second move action this turn: the standard action is what paid for it, and
    Lightning Stance's 50% concealment for a round is laid on its holder.

    Batch 4 built the standard's spending and backed it out: the reach refusal's repair
    ("Click square ...", then move and strike) was offered with the move already walked.
    Batch 5 (b5-core) changed the repair to say the strike waits for the next turn, and
    the panel's door refuses a walk-and-strike after the move is spent."""
    from .engine import Outcome

    actor = engine.scene.actors.get(intent.actor or "")
    if actor is None or not twice:
        return []
    # Feat loop b5-core: the second move action is paid with the standard (CRB: "You can
    # take a move action in place of a standard action"), unless it was the round's 5-foot
    # step (rules/stepping.py), which is no action at all. The reach refusal's repair no
    # longer offers a walk and a strike after the move is spent (`_reach_refusal`).
    went = next((e for e in outcome.effects or () if e.get("kind") == "position"
                 and e.get("ref") == actor.ref), None)
    if went is not None and not went.get("step"):
        engine.scene.standard_spent[actor.ref] = engine.scene.round
    if _walked(outcome, actor.ref) <= gridmod.SQUARE_FT:
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


def _wind_stance(engine, intent, outcome, twice: bool) -> list:
    """Wind Stance (CRB): "If you move more than 5 feet this turn, you gain 20%
    concealment for 1 round against ranged attacks" — laid on its holder by a walk past a
    5-foot step, or a second move this turn (5 feet then 5 more is 10). The miss chance is
    scoped to ranged blows (`when.weapon.ranged`, read by `Actor.concealment` with the
    blow's own facts). Feat loop b5-other, on Lightning Stance's door."""
    from .engine import Outcome

    actor = engine.scene.actors.get(intent.actor or "")
    if actor is None or not actor.has_state(WIND_STANCE):
        return []
    walked = _walked(outcome, actor.ref)
    if walked <= gridmod.SQUARE_FT and not (twice and walked > 0):
        return []
    actor.apply_effect(ActiveEffect(
        name="wind stance", kind="buff", key="wind stance",
        source="Wind Stance", origin="rule:feat-wind-stance",
        duration="rounds", rounds_left=1, tags=("buff.stance.wind",),
        modifiers=[{"kind": "concealment", "target": "miss_chance", "amount": 20,
                    "bonus_type": "", "note": "Wind Stance",
                    "when": {"weapon": {"ranged": True}}}]))
    return [Outcome(intent_id=intent.id, op="move", actor=actor.ref,
                    effects=[{"ref": actor.ref, "kind": "buff", "buff": "wind stance",
                              "rounds": 1, "origin": "rule:feat-wind-stance"}],
                    tell=f"{actor.name} weaves as they move (Wind Stance): 20% concealment "
                         f"against ranged attacks until their next turn.",
                    because="Wind Stance")]


def _spend_easy(engine, intent, outcome) -> None:
    """Nimble Moves and Acrobatic Steps are "each round", not each move (feat loop
    b5-other): a walk that crossed difficult ground on the allowance spends it until the
    walker's next turn — a one-round `movement.difficult.spent` effect `Engine._easy_ft`
    asks. Whether the allowance was used is the walk priced twice, with it and without.
    shortcut: a walk that used part of the allowance spends all of it; upgrade if a walk
    ever records the difficult squares it crossed."""
    sc = engine.scene
    actor = sc.actors.get(intent.actor or "")
    grid = getattr(sc, "grid", None)
    if actor is None or grid is None or actor.has_state(EASY_SPENT):
        return
    easy = engine._easy_ft(actor)
    if easy <= 0 or easy >= gridmod.Grid.EASY_ALL:
        return
    went = next((e for e in outcome.effects or () if e.get("kind") == "position"
                 and e.get("ref") == actor.ref and e.get("from") is not None
                 and e.get("to") is not None), None)
    if went is None:
        return
    start, end = tuple(went["from"])[:2], tuple(went["to"])[:2]
    occupied = sc.occupied(ignore=actor.ref)
    plain = grid.reachable(start, 10_000, size=actor.size, occupied=occupied).get(end)
    eased = grid.reachable(start, 10_000, size=actor.size, occupied=occupied,
                           easy_ft=easy).get(end)
    if plain is None or eased is None or eased >= plain:
        return
    actor.apply_effect(ActiveEffect(
        name="difficult ground crossed", kind="situation", key="difficult ground crossed",
        source="Nimble Moves", origin="rule:feat-nimble-moves", duration="rounds",
        rounds_left=1, tags=(EASY_SPENT,)))


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


# --- the turn's walking, split around an action (feat loop b7-moves) -------------------------
#
# CRB, Combat, Action Types: "In a normal round, you can perform a standard action and a move
# action, or you can perform a full-round action"; a move in place of the standard is the
# second. So a move, a blow and another move is three actions. Measured before this lane: a
# fighter walked 30 ft, shot, and walked 30 ft more in one batch, every step resolved — the
# only refusal after a blow was for a blow (`_standard_spent_refusal`), and nothing asked a
# walk what the turn had left. Shot on the Run (CRB) is the book's exception: "As a
# full-round action, you can move up to your speed and make a single ranged attack at any
# point during your movement" — Normal: "You cannot move before and after an attack with a
# ranged weapon". Its siblings say the same with other actions: Wand Dancer (UM) around a
# spell trigger item, Ride-By Attack (CRB) after a mounted charge, Slaying Sprint (UC)
# around a coup de grâce, and Tiger Pounce (UC) pays a half-speed move with the swift action.
#
# One shape for all of them: the walk still owed is an `ActiveEffect` on the walker for the
# round (`key` "split walk", the feet in its payload), laid by the act that earns it and
# spent by the walk that uses it, so nothing keeps a store and the round's end takes it
# away. Spring Attack's `spring_left` is the same rule written into the queue before this
# existed; it is left as it is, a walk the queue already holds.
#
# Prior art: Owlcat's Pathfinder CRPGs keep one move and one standard per turn and grey the
# move out once both are spent; Foundry PF1 counts nothing (the GM does). Neither models
# Shot on the Run beyond allowing the move — the remaining feet are this engine's own call.

ALLOWANCE = "movement.allowance"           # the walk still owed this round
SPLIT_KEY = "split walk"
SHOT_ON_THE_RUN = "movement.split.ranged"
WAND_DANCER = "movement.split.trigger"
SLAYING_SPRINT = "movement.split.coup"
RIDE_BY = "charge.mounted.ride-by"
MOUNTED_BLADE = "charge.mounted.blade-follow"
TIGER_POUNCE = "movement.pounce"
POUNCE_MARK = "movement.pounced"          # .<ref>: hit this turn or last, on the hitter
TIGER_STYLE = "style.tiger-style"


def _half(feet: int) -> int:
    return (int(feet) // 2 // gridmod.SQUARE_FT) * gridmod.SQUARE_FT


def allowance(actor):
    """The walk this actor is still owed this round (the "split walk" effect), or None."""
    return next((e for e in actor.effects if e.key == SPLIT_KEY), None)


def grant_walk(engine, actor, feet: int, source: str, origin: str,
               line=None, intent_id: str = "") -> list:
    """Lay the walk owed after an act, and say so; [] when there is nothing to walk."""
    from .engine import Outcome

    actor.remove_effects(match=lambda e: e.key == SPLIT_KEY)
    feet = (max(0, int(feet)) // gridmod.SQUARE_FT) * gridmod.SQUARE_FT
    if feet < gridmod.SQUARE_FT:
        return []
    payload = {"feet": feet, "round": engine.scene.round}
    if line:
        payload["line"] = [int(v) for v in line]
    actor.apply_effect(ActiveEffect(
        name="walk left", kind="situation", key=SPLIT_KEY, source=source, origin=origin,
        duration="rounds", rounds_left=1, tags=(ALLOWANCE,), payload=payload))
    return [Outcome(intent_id=intent_id, op="move", actor=actor.ref,
                    effects=[{"ref": actor.ref, "kind": "walk_left", "feet": feet,
                              "origin": origin}],
                    tell=f"{actor.name} may still move {feet} ft this turn ({source}).",
                    because=source)]


def _on_line(line, here, end) -> bool:
    """Whether `end` carries on the straight line `line` ([ax, ay, bx, by]) from `here`:
    ahead of it, and within three quarters of a square of the line (a diagonal's rounding)."""
    ax, ay, bx, by = line
    dx, dy = bx - ax, by - ay
    wx, wy = end[0] - here[0], end[1] - here[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0 or wx * dx + wy * dy <= 0:
        return False
    return abs(wx * dy - wy * dx) / length <= 0.75


def no_move_left(engine, intent, actor, start, end):
    """(sentence, code) refusing this walk, or None.

    A walk after a move action and a blow (or a spent standard) this turn is a third
    action; a walk the turn still owes (`allowance`) or a Tiger Pounce paid with the swift
    action goes. Engine-spliced walks (a closing step, a charge, Spring Attack's rest, a
    reaction) have their own rules and are not asked."""
    sc = engine.scene
    params = intent.params or {}
    if not sc.in_encounter or start is None or tuple(start)[:2] == tuple(end)[:2] \
            or params.get("reaction") or params.get("closing_on") \
            or params.get("charging") or params.get("spring_left") is not None:
        return None
    if stepping.is_step(sc, actor, start, end):
        return None                           # a 5-foot step is no action at all
    cost = engine._move_cost(actor.ref, start, tuple(end))
    cost = int(cost) if cost is not None else gridmod.distance(tuple(start)[:2],
                                                              tuple(end)[:2])
    owed = allowance(actor)
    if owed is not None:
        feet = int(owed.payload.get("feet") or 0)
        if cost > feet:
            return (f"{actor.name} has {feet} ft of walking left this turn ({owed.source}), "
                    f"and {tuple(end)} is {cost} ft away.", "too_far")
        line = owed.payload.get("line")
        if line and not _on_line(line, tuple(start)[:2], tuple(end)[:2]):
            return (f"{owed.source}'s walk after the blow carries on the straight line of "
                    f"the charge, and {tuple(end)} is off it.", "off_the_line")
        return None
    rnd, ref = sc.round, actor.ref
    rider = _rider_charged(engine, actor)
    if rider is not None:
        return (f"{rider.name} charged on {actor.name} this turn, and a charge is the whole "
                f"round: no further movement until their next turn.", "standard_spent")
    if sc.move_spent.get(ref) != rnd or (sc.standard_spent.get(ref) != rnd
                                         and sc.swung.get(ref) != rnd):
        return None
    if _pounce(engine, actor, start, end, cost):
        return None
    return (f"{actor.name} has already used this turn's move and standard actions, and "
            f"may not move again until their next turn.", "standard_spent")


def refuse_before(engine, raw: dict):
    """The walk at the head of the queue refused before anything is owed for it, or None.

    Asked in `Engine._drive` ahead of the attacks of opportunity: measured while building
    this, a walk refused inside `_op_move` had already drawn the adjacent thug's swing —
    a free attack of opportunity for a move that never happened. The round's 5-foot step
    rule (`stepping.after_step_refusal`) is asked here for the same reason."""
    from . import bodyskills
    from .engine import _intent_from_dict

    sc = engine.scene
    if raw.get("op") != "move" or not sc.in_encounter or not sc.has_grid:
        return None
    params = raw.get("params") or {}
    square = params.get("square")
    if square is None or params.get("reaction"):
        return None
    walker = sc.actors.get(str(params.get("who") or raw.get("actor") or ""))
    if walker is None:
        return None
    steed = bodyskills.mount_of(sc, walker) if not params.get("who") else None
    mover = steed or walker
    start = sc.positions.get(mover.ref)
    if start is None:
        return None
    intent = _intent_from_dict(raw)
    stepped = stepping.after_step_refusal(sc, mover, start, tuple(square))
    if stepped:
        return engine._refuse(intent, stepped, code="stepped")
    spent = no_move_left(engine, intent, mover, start, tuple(square))
    if spent:
        return engine._refuse(intent, spent[0], code=spent[1])
    return None


def _rider_charged(engine, steed):
    """The rider who charged on this steed this round, or None: the charge was the
    steed's whole round as much as the rider's (CRB, Mounted Combat)."""
    from . import bodyskills

    sc = engine.scene
    rider = bodyskills.rider_of(sc, steed)
    if rider is None or not rider.has_state("buff.stance.charging") \
            or sc.standard_spent.get(rider.ref) != sc.round:
        return None
    return rider


def spend_allowance(engine, intent, outcome) -> None:
    """A walk that used the turn's owed feet spends it (all of it: the book's "total
    distance" is one walk after the act)."""
    params = intent.params or {}
    if params.get("reaction") or params.get("closing_on") or params.get("charging"):
        return
    ref = params.get("who") or intent.actor
    actor = engine.scene.actors.get(ref or "")
    if actor is None or allowance(actor) is None or _walked(outcome, actor.ref) <= 0:
        return
    actor.remove_effects(match=lambda e: e.key == SPLIT_KEY)


def _pounce(engine, actor, start, end, cost: int) -> bool:
    """Tiger Pounce (UC): "once per round as a swift action, you can move up to half your
    speed closer to a target you hit with an unarmed strike or made a successful combat
    maneuver against on this turn or your last turn" — while in Tiger Style. Taken when the
    turn has no move action left, so a move action is never traded for the swift unasked
    (owner call). Spends the swift action."""
    sc = engine.scene
    if not actor.has_state(TIGER_POUNCE) or not actor.has_state(TIGER_STYLE) \
            or cost > _half(actor.speed_feet):
        return False
    for ref in sc.actors:
        there = sc.positions.get(ref)
        if ref == actor.ref or there is None or not actor.has_state(f"{POUNCE_MARK}.{ref}"):
            continue
        if gridmod.distance(tuple(end)[:2], tuple(there)[:2]) \
                < gridmod.distance(tuple(start)[:2], tuple(there)[:2]):
            return engine._spend_swift(actor, False, "Tiger Pounce") is None
    return False


def _mark_pounce(engine, intent, outcome) -> None:
    """An unarmed hit or a successful manoeuvre by a Tiger Pounce holder marks the foe for
    this turn and the next (rounds_left 2 on the one round ticker)."""
    from . import classfeatures

    actor = engine.scene.actors.get(intent.actor or "")
    if actor is None or not actor.has_state(TIGER_POUNCE):
        return
    params = intent.params or {}
    if params.get("manoeuvre"):
        won = [str(intent.target or "")] if outcome.verdict == "success" else []
    elif classfeatures._unarmed_key(str(params.get("weapon") or "unarmed")):
        won = [str(b.get("ref") or "") for b in outcome.blows or ()
               if b.get("result") in ("hit", "critical")]
    else:
        won = []
    for ref in dict.fromkeys(r for r in won if r):
        actor.apply_effect(ActiveEffect(
            name=f"pounce on {ref}", kind="situation", key=f"pounce-{ref}",
            source="Tiger Pounce", origin="rule:feat-tiger-pounce", duration="rounds",
            rounds_left=2, tags=(f"{POUNCE_MARK}.{ref}",)))


def _walk_earned(engine, intent, outcome) -> list:
    """The walk a split-walk feat owes after this act, laid and told (`grant_walk`)."""
    from . import stepping

    sc = engine.scene
    params = intent.params or {}
    actor = sc.actors.get(intent.actor or "")
    if actor is None or params.get("reaction") or not sc.has_grid:
        return []
    walked = stepping.feet_walked(sc, actor.ref)
    speed = int(actor.speed_feet)
    if intent.op == "attack" and params.get("coup_de_grace"):
        # Slaying Sprint: half speed in place of the 5-foot step, before or after the coup.
        if actor.has_state(SLAYING_SPRINT) and not walked and _sprint_weapon(actor, params):
            return grant_walk(engine, actor, _half(speed), "Slaying Sprint",
                              "rule:feat-slaying-sprint", intent_id=intent.id)
        return []
    if intent.op == "attack" and actor.has_state(SHOT_ON_THE_RUN) and walked \
            and stepping.walked(sc, actor.ref) == "move" \
            and sc.standard_spent.get(actor.ref) != sc.round:
        w = actor.weapon(params.get("weapon") or None) or {}
        if str(w.get("category") or "").lower() == "ranged" or params.get("thrown"):
            return grant_walk(engine, actor, speed - walked, "Shot on the Run",
                              "rule:feat-shot-on-the-run", intent_id=intent.id)
    if intent.op == "use_item" and actor.has_state(WAND_DANCER) \
            and walked >= gridmod.SQUARE_FT and _spell_trigger(actor, params):
        return grant_walk(engine, actor, speed - walked, "Wand Dancer",
                          "rule:feat-wand-dancer", intent_id=intent.id)
    return []


def _sprint_weapon(actor, params) -> bool:
    """Slaying Sprint: "only when wielding a light or one-handed weapon"."""
    w = actor.weapon(params.get("weapon") or None) or {}
    return str(w.get("category") or "melee").lower() != "ranged" and (
        bool(w.get("light")) or int(w.get("hands", 1) or 1) <= 1)


def coup_walk_ok(engine, actor, weapon_key: str) -> bool:
    """Whether the walk already taken this round still leaves the coup de grâce its full
    round: a 5-foot step does (CRB: a step may go with a full-round action), and with
    Slaying Sprint one walk of no more than half speed does ("instead of taking a 5-foot
    step"). Measured before this lane: a step then a coup was refused "already moved"."""
    from . import stepping

    sc = engine.scene
    if sc.standard_spent.get(actor.ref) == sc.round:
        return False
    kind = stepping.walked(sc, actor.ref)
    if kind == "step":
        return True
    return (kind == "move" and actor.has_state(SLAYING_SPRINT)
            and _sprint_weapon(actor, {"weapon": weapon_key})
            and stepping.feet_walked(sc, actor.ref) <= _half(actor.speed_feet))


def _spell_trigger(actor, params) -> bool:
    """Whether this use sets off a spell trigger item (a wand; rules/spellitems.py)."""
    from . import spellitems

    item = str(params.get("item") or "")
    if not params.get("power") or not item:
        return False
    for rec in actor.item_records(item):
        entry = spellitems.entry_of(rec)
        if entry and entry.get("activation") == "trigger":
            return True
    return False


def before(engine, raw: dict, queue: list) -> None:
    """Waivers a walk needs before it is weighed for attacks of opportunity.

    - Wand Dancer: "Your movement does not provoke attacks of opportunity from that
      creature only" — the one the wand is aimed at, when this walk comes before a use of a
      spell trigger item queued behind it (and the walk after a use, `_wand_dancer_after`).
    - Ride-By Attack: "You and your mount do not provoke an attack of opportunity from the
      opponent that you attack" — laid on rider and steed as the charge sets off, held for
      the round so the walk after the blow is spared too.
    Both are the tumble's waiver shape (`reactions.TUMBLED_PAST`, Spring Attack's)."""
    from . import bodyskills, reactions

    if raw.get("op") != "move" or not engine.scene.in_encounter:
        return
    sc = engine.scene
    params = raw.get("params") or {}
    actor = sc.actors.get(str(raw.get("actor") or ""))
    if actor is None:
        return
    spared: list = []
    if params.get("charging") == "charge" and params.get("closing_on") \
            and actor.has_state(RIDE_BY) and actor.has_state(MOUNTED):
        for who in (actor, bodyskills.mount_of(sc, actor)):
            if who is not None:
                spared.append((who, str(params["closing_on"]), "Ride-By Attack"))
    if actor.has_state(WAND_DANCER) and not params.get("reaction"):
        later = next((q for q in queue[1:] if q.get("actor") == actor.ref
                      and q.get("op") == "use_item"), None)
        if later is not None and _spell_trigger(actor, later.get("params") or {}):
            aim = str((later.get("params") or {}).get("to") or later.get("target") or "")
            if aim and aim != actor.ref:
                spared.append((actor, aim, "Wand Dancer"))
    for who, foe, source in spared:
        _spare(who, foe, source)


def _spare(who, foe: str, source: str) -> None:
    from . import reactions

    who.apply_effect(ActiveEffect(
        name=f"unprovoking {foe}", kind="situation", key=f"spared-by-{foe}",
        source=source, origin=f"rule:feat-{source.lower().replace(' ', '-')}",
        duration="rounds", rounds_left=1, tags=(f"{reactions.TUMBLED_PAST}.{foe}",)))


def _wand_dancer_after(engine, intent) -> None:
    """Wand Dancer's waiver for the walk after the use: the creature the wand was aimed at."""
    actor = engine.scene.actors.get(intent.actor or "")
    params = intent.params or {}
    aim = str(params.get("to") or intent.target or "")
    if actor is None or not aim or aim == actor.ref or allowance(actor) is None \
            or allowance(actor).source != "Wand Dancer":
        return
    _spare(actor, aim, "Wand Dancer")


def _ride_by_walk(engine, intent, outcome) -> list:
    """Ride-By Attack (CRB): "you may move and attack as if with a standard charge and then
    move again (continuing the straight line of the charge). Your total movement for the
    round can't exceed double your mounted speed." Laid on the steed when the charge's walk
    is done: the walk after the blow is the steed's, on the charge's line."""
    from . import bodyskills, stepping

    params = intent.params or {}
    if params.get("charging") != "charge":
        return []
    rider = engine.scene.actors.get(intent.actor or "")
    if rider is None or not rider.has_state(RIDE_BY) or not rider.has_state(MOUNTED):
        return []
    steed = bodyskills.mount_of(engine.scene, rider)
    if steed is None:
        return []
    went = next((e for e in outcome.effects or () if e.get("kind") == "position"
                 and e.get("ref") == steed.ref and e.get("from") is not None), None)
    if went is None:
        return []
    a, b = tuple(went["from"])[:2], tuple(went["to"])[:2]
    left = 2 * int(steed.speed_feet) - stepping.feet_walked(engine.scene, steed.ref)
    return grant_walk(engine, steed, left, "Ride-By Attack", "rule:feat-ride-by-attack",
                      line=[*a, *b], intent_id=intent.id)


def _mounted_blade(engine, intent, outcome) -> list[dict]:
    """Mounted Blade (UC): "When you use the Ride-By Attack feat, if your attack hits, you
    may also make an attack against a target adjacent to your original target. This
    additional attack has a -5 penalty" (`_op_attack` reads the reaction's name). The
    engine picks the nearest foe beside the first within the rider's reach (owner call, as
    Cleave's next target is the engine's)."""
    from . import position as position_mod

    sc = engine.scene
    params = intent.params or {}
    rider = sc.actors.get(intent.actor or "")
    if rider is None or not params.get("charge") or params.get("reaction") \
            or not rider.has_state(MOUNTED_BLADE) or not rider.has_state(RIDE_BY) \
            or not rider.has_state(MOUNTED) or not sc.has_grid:
        return []
    first = str(intent.target or "")
    if not any(b.get("ref") == first and b.get("result") in ("hit", "critical")
               for b in outcome.blows or ()):
        return []
    weapon = params.get("weapon") or None
    for ref, foe in sc.actors.items():
        if ref in (rider.ref, first) or foe.is_down or _friends(sc, ref, rider.ref) \
                or (sc.distance_between(ref, first) or 99) > gridmod.SQUARE_FT \
                or position_mod.out_of_reach(sc, rider, foe, weapon or "") is not None:
            continue
        return [{"op": "attack", "actor": rider.ref, "target": ref,
                 "id": f"{intent.id}-mounted-blade",
                 "visibility": "player" if rider.is_pc else "hidden",
                 "because": f"{rider.name} carries the blade on into {foe.name} "
                            f"(Mounted Blade)",
                 "params": {"full_attack": False, "reaction": "mounted-blade",
                            **({"weapon": weapon} if weapon else {})}}]
    return []


# --- the run (feat loop b7-moves; ledger group 40) -------------------------------------------
#
# CRB, Combat, Run (aonprd.com/Rules.aspx?ID=149, read 2026-11-27): "You can run as a
# full-round action. If you do, you do not also get a 5-foot step. When you run, you can
# move up to four times your speed in a straight line (or three times your speed if you're
# in heavy armor). You lose any Dexterity bonus to AC unless you have the Run feat. You can
# run for a number of rounds equal to your Constitution score, but after that you must make
# a DC 10 Constitution check to continue running. You must check again each round in which
# you continue to run, and the DC of this check increases by 1 for each check you have
# made. When you fail this check, you must stop running. A character who has run to his
# limit must rest for 1 minute (10 rounds) before running again ... You can't run across
# difficult terrain or if you can't see where you're going." Run (CRB): five times (four in
# heavy armour or a heavy load) and the Dexterity bonus kept.
#
# There is no run op: a single walk further than a double move (two moves are two intents),
# in a straight line, as the turn's first act, IS the run — the only legal way there in one
# move. Owner call: a square past a double move's reach in a straight line is read as a run
# rather than refused. Measured before: no action carried a body further than its speed,
# and the Run feat's own document said so.

RUNNING = "state.moving.running"
RUN_EXPOSED = "state.exposed.running"
RUN_SPENT = "movement.run.spent"           # ran to the limit: a minute's rest first
RUN_STREAK = "run streak"
DRAGON_STYLE = "style.dragon-style"
DRAGON_THROUGH = "movement.charge.through"  # Dragon Style's document tag
MOUNTED_ARCHERY = "mounted.archery.halved"


def _run_feat() -> str:
    from .bodyskills import RUN_JUMP

    return RUN_JUMP


def run_multiple(actor) -> int:
    """Four times speed (three in heavy armour or a heavy load); the Run feat one more."""
    from . import classfeatures

    suit = actor.armour_stats() or {}
    heavy = str(suit.get("move_weight") or suit.get("weight") or "") == "heavy" \
        or classfeatures._load_band(actor) == "heavy"
    return (3 if heavy else 4) + (1 if actor.has_state(_run_feat()) else 0)


def through_all(actor) -> bool:
    """Dragon Style (UC): "you can charge or run through difficult terrain and through
    squares occupied by allies" — while in the style."""
    return actor.has_state(DRAGON_THROUGH) and actor.has_state(DRAGON_STYLE)


def _ally_at(engine, actor, square) -> bool:
    sc = engine.scene
    for ref, there in sc.positions.items():
        if ref != actor.ref and ref in sc.actors and tuple(square) in set(
                gridmod.footprint(tuple(there)[:2], sc.actors[ref].size)):
            return _friends(sc, ref, actor.ref)
    return False


def line_blocked(engine, actor, a, b) -> str:
    """What stops a straight run from `a` to `b`: a solid square, difficult ground or a
    body, under the runner's footprint along the line (the charge's measure), or ""."""
    sc = engine.scene
    grid = sc.grid
    free = through_all(actor)
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    taken = sc.occupied(ignore=actor.ref)
    for i in range(1, n + 1):
        anchor = (round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n))
        for p in gridmod.footprint(anchor, actor.size):
            if not grid.passable(p):
                return f"something solid stands in the way at {p}"
            if p in grid.difficult and not free:
                return f"the line crosses difficult ground at {p}, and nobody runs across it"
            if p in taken and not (free and i < n and _ally_at(engine, actor, p)):
                return f"somebody stands in the way at {p}"
    return ""


def run_refusal(engine, actor, start, end, routes_far: dict) -> str | None:
    """None when this walk is a legal run, else why it is not (said beside the too-far
    refusal). `routes_far`: the cheapest open routes from `start` at any length."""
    sc = engine.scene
    if not sc.in_encounter or start is None:
        return "out of a fight"
    rnd, ref = sc.round, actor.ref
    if rnd in (sc.move_spent.get(ref), sc.standard_spent.get(ref), sc.swung.get(ref)) \
            or stepping.walked(sc, ref):
        return "a run is the whole round, and this turn is under way"
    if actor.has_state("state.position.prone") or actor.has_state("state.senses.blinded"):
        return "nobody runs prone or blind"
    if actor.has_state(RUN_SPENT):
        return f"{actor.name} ran to their limit and must rest a minute before running again"
    speed = int(actor.speed_feet)
    cost = routes_far.get(tuple(end)[:2])
    if cost is None or cost <= 2 * speed or cost > run_multiple(actor) * speed:
        return "too far to run"
    blocked = line_blocked(engine, actor, tuple(start)[:2], tuple(end)[:2])
    return f"a run is a straight line, and {blocked}" if blocked else None


def is_run(engine, actor, cost) -> bool:
    """Whether a walk resolving now is the run: further than the walker's speed in one
    move, in a fight (validation let it through only as a run)."""
    return bool(engine.scene.in_encounter and cost is not None
                and int(cost) > 2 * int(actor.speed_feet))


def run_starts(engine, intent, actor):
    """A run about to be made: the Constitution check past the Constitution score's rounds
    (Endurance's +4 rides `against: running`), then the running state and the round spent.
    Returns (the refusing Outcome when the runner is spent, else None; the rolls made)."""
    from .engine import Outcome

    sc = engine.scene
    held = next((e for e in actor.effects if e.key == RUN_STREAK), None)
    streak = dict(held.payload) if held is not None and \
        int(held.payload.get("round", -9)) == sc.round - 1 else {"rounds": 0, "checks": 0}
    rounds = int(streak.get("rounds", 0)) + 1
    checks = int(streak.get("checks", 0))
    rolls = []
    if rounds > actor.ability_score("con"):
        dc = 10 + checks
        roll = engine.dice.d20(actor.ability_check_modifiers("con", {"against": "running"}),
                               label=f"{actor.name} Constitution (keep running)",
                               visibility="player" if actor.is_pc else "hidden")
        rolls.append(roll)
        checks += 1
        if roll.total < dc:
            actor.remove_effects(match=lambda e: e.key == RUN_STREAK)
            actor.apply_effect(ActiveEffect(
                name="run to the limit", kind="situation", key="run spent",
                source="Run", origin="rule:run", duration="rounds", rounds_left=10,
                tags=(RUN_SPENT,)))
            return Outcome(intent_id=intent.id, op="move", status="prevented",
                           effects=[{"ref": actor.ref, "kind": "move_stopped",
                                     "why": "run to the limit", "origin": "rule:run"}],
                           rolls=rolls,
                           tell=f"{actor.name} has run as far as their lungs allow "
                                f"(Constitution {roll.total} against DC {dc}) and must rest "
                                f"a minute before running again.",
                           because=intent.because), rolls
    actor.remove_effects(match=lambda e: e.key == RUN_STREAK)
    actor.apply_effect(ActiveEffect(
        name="running", kind="situation", key=RUN_STREAK, source="Run", origin="rule:run",
        duration="rounds", rounds_left=2,
        payload={"rounds": rounds, "checks": checks, "round": sc.round}))
    tags = (RUNNING,) if actor.has_state(_run_feat()) else (RUNNING, RUN_EXPOSED)
    actor.apply_effect(ActiveEffect(
        name="running", kind="situation", key="running", source="Run", origin="rule:run",
        duration="rounds", rounds_left=1, tags=tags))
    sc.move_spent[actor.ref] = sc.round
    sc.standard_spent[actor.ref] = sc.round
    return None, rolls


def mounted_ranged(engine, rider, weapon: dict) -> list:
    """CRB, Mounted Combat: "If your mount is taking a double move, you take a -4 penalty
    on ranged attacks; if your mount is running, the penalty is -8"; Mounted Archery
    halves it. Read off the steed's round: its running state, or more than its speed
    walked. Measured before (Mounted Archery's not_yet line): neither was tracked."""
    from . import bodyskills
    from .dice import Modifier

    if str(weapon.get("category") or "").lower() != "ranged":
        return []
    sc = engine.scene
    steed = bodyskills.mount_of(sc, rider) if rider.has_state(MOUNTED) else None
    if steed is None or not sc.in_encounter:
        return []
    if steed.has_state(RUNNING):
        n, how = -8, "running"
    elif stepping.feet_walked(sc, steed.ref) > int(steed.speed_feet):
        n, how = -4, "double-moving"
    else:
        return []
    if rider.has_state(MOUNTED_ARCHERY):
        n //= 2
    return [Modifier(n, f"shooting from a {how} mount")]


# --- crawling and standing up (feat loop b7-moves; ledger group 2) ---------------------------
#
# CRB, Combat, Move Actions (p.188-189; the text read through forum quotations of the Core
# Rulebook, aonprd.com's Move Actions page not fetched — said plainly): "Crawl: You can crawl
# 5 feet as a move action. Crawling incurs attacks of opportunity from any attackers who
# threaten you at any point of your crawl. A crawling character is considered prone";
# "Stand Up: Standing up from a prone position requires a move action and provokes attacks
# of opportunity." Normal (Fast Crawl): "You cannot take a 5-foot step while crawling."
# Measured before this lane: a prone body walked its full speed and took 5-foot steps, and
# standing up (the reader's `rise`, `condition ends prone`) cost nothing and drew no swing.
#
# - Fast Crawl (APG): "While prone, you can move at half speed ... You can take a 5-foot step
#   while crawling."
# - Monkey Style (UC): "you can crawl and stand up from lying prone without provoking attacks
#   of opportunity, and you can stand up as a swift action if you succeed at a DC 20
#   Acrobatics check."
# - Monkey Moves (UC): "you can also climb and crawl at half your speed; you can take a
#   5-foot step by jumping, crawling, or climbing; and you retain your Dexterity bonus to AC
#   while climbing. Further, while using Monkey Style, when you use your unarmed strike to
#   hit an opponent twice or more on your turn, you can spend a swift action to take a
#   5-foot step even if you have moved this round."

PRONE = "state.position.prone"
FAST_CRAWL = "movement.crawl.fast"
MONKEY_MOVES = "movement.monkey-moves"
MONKEY_STYLE = "style.monkey-style"
MONKEY_STEP = "movement.step.swift"          # two unarmed hits this turn (Monkey Moves)
STAND_DC = 20


def monkey_moving(actor) -> bool:
    return actor.has_state(MONKEY_MOVES) and actor.has_state(MONKEY_STYLE)


def crawling(actor) -> bool:
    """Prone and on the ground: a walk is a crawl (a climber or a rider is not)."""
    from . import bodyskills

    return actor.has_state(PRONE) and not actor.has_state(bodyskills.CLIMBING) \
        and not actor.has_state(MOUNTED)


def crawl_budget(actor, budget: int) -> int:
    """A move's feet for a crawler: 5, or half speed with Fast Crawl or Monkey Moves."""
    if not crawling(actor):
        return budget
    if actor.has_state(FAST_CRAWL) or monkey_moving(actor):
        return max(gridmod.SQUARE_FT, _half(actor.speed_feet))
    return gridmod.SQUARE_FT


def crawl_steps(actor) -> bool:
    """Whether this crawler may take a 5-foot step (Fast Crawl, Monkey Moves in style)."""
    return actor.has_state(FAST_CRAWL) or monkey_moving(actor)


def crawl_unprovoking(actor) -> bool:
    """Monkey Style: a crawl provokes nothing."""
    return crawling(actor) and actor.has_state(MONKEY_STYLE)


def monkey_step(scene, actor) -> bool:
    """Monkey Moves' swift 5-foot step "even if you have moved this round", earned by two
    unarmed hits this turn (`_count_unarmed`)."""
    return monkey_moving(actor) and actor.has_state(MONKEY_STEP)


def _count_unarmed(engine, intent, outcome) -> None:
    """Two unarmed hits on the holder's own turn: Monkey Moves' swift step is open."""
    from . import classfeatures

    actor = engine.scene.actors.get(intent.actor or "")
    params = intent.params or {}
    if actor is None or not monkey_moving(actor) or params.get("reaction") \
            or not classfeatures._unarmed_key(str(params.get("weapon") or "unarmed")):
        return
    hits = sum(1 for b in outcome.blows or () if b.get("result") in ("hit", "critical"))
    if not hits:
        return
    sc = engine.scene
    held = next((e for e in actor.effects if e.key == "unarmed hits"), None)
    before = int(held.payload.get("hits", 0)) if held is not None \
        and int(held.payload.get("round", -1)) == sc.round else 0
    actor.remove_effects(match=lambda e: e.key == "unarmed hits")
    total = before + hits
    actor.apply_effect(ActiveEffect(
        name="unarmed hits", kind="situation", key="unarmed hits", source="Monkey Moves",
        origin="rule:feat-monkey-moves", duration="rounds", rounds_left=1,
        tags=(MONKEY_STEP,) if total >= 2 else (), payload={"round": sc.round, "hits": total}))


def standing_up(raw: dict, actor) -> bool:
    """Whether this intent is the actor getting up off the ground themselves."""
    params = raw.get("params") or {}
    return (raw.get("op") == "condition" and bool(params.get("ends"))
            and str(params.get("condition") or "").strip().lower() == "prone"
            and str(params.get("to") or raw.get("actor") or "") == actor.ref
            and not raw.get("origin") and actor.has_state(PRONE))


def provoked_by_standing(engine, raw: dict) -> list[dict]:
    """CRB, Stand Up: "provokes attacks of opportunity" — from every foe threatening the
    one rising (`reactions.provoked_by_action`, the cast's question); none in Monkey
    Style."""
    from . import reactions

    sc = engine.scene
    actor = sc.actors.get(str(raw.get("actor") or ""))
    if actor is None or not sc.in_encounter or not standing_up(raw, actor) \
            or actor.has_state(MONKEY_STYLE):
        return []
    return engine._swings_at(actor.ref, reactions.provoked_by_action(sc, actor.ref),
                             why="standing up")


def stand_up(engine, intent, actor):
    """Price getting up in a fight: (the refusing Outcome or None, rolls, words said).
    A move action (paid with the standard when the move is gone); in Monkey Style a DC 20
    Acrobatics check first makes it the swift action, and a failed one leaves the move."""
    sc = engine.scene
    raw = {"op": intent.op, "actor": intent.actor, "params": intent.params,
           "origin": getattr(intent, "origin", "")}
    if not sc.in_encounter or not standing_up(raw, actor):
        return None, [], ""
    if actor.is_down or actor.blocking_key("move"):
        return engine._refuse(intent, f"{actor.name} cannot get up: "
                                      f"{(actor.blocking_condition('move') or 'down').lower()}.",
                              code="cannot_act"), [], ""
    rolls: list = []
    if actor.has_state(MONKEY_STYLE) and not engine._swift_refusal(actor, False, "standing"):
        roll = engine.dice.d20(actor.skill_modifiers("acrobatics"),
                               label=f"{actor.name} Acrobatics (stand up)",
                               visibility="player" if actor.is_pc else "hidden")
        rolls.append(roll)
        if roll.total >= STAND_DC:
            engine._spend_swift(actor, False, "standing up")
            return None, rolls, (f" {actor.name} springs up as a swift action (Acrobatics "
                                 f"{roll.total} against DC {STAND_DC}).")
    why = engine._spend_ability_action(intent, actor, "move", "standing up")
    if why is not None:
        why.rolls = list(rolls) + list(why.rolls or [])
        return why, rolls, ""
    return None, rolls, ""


# --- charge variants (feat loop b7-moves; ledger group 8) ------------------------------------
#
# Charging Hurler (APG): "You can use the charge rules to make a thrown weapon attack. All
# the parameters of a charge apply, except that you must only move closer to your opponent,
# and you must end your movement within 30 feet of that opponent. If you do, you can make a
# single thrown weapon attack against that opponent, gaining the +2 bonus on the attack roll
# and taking a -2 penalty to your AC until the start of your next turn." Improved Charging
# Hurler (APG): "your target can be at any range up to your weapon's maximum range. If your
# target is within 30 feet, you gain a +2 bonus on damage rolls" (its document's term).
# Measured before: a charge's walk always ended within melee reach (`Engine._charge_path`),
# so a thrown charge was never laid.

CHARGING_HURLER = "charge.thrown"
CHARGING_HURLER_FAR = "charge.thrown.any-range"


def thrown_charge(actor, params) -> bool:
    return bool(params.get("charge") and params.get("thrown")) \
        and actor.has_state(CHARGING_HURLER)


def thrown_charge_path(engine, actor, defender, weapon_key: str, budget: int):
    """((x, y), feet) for a thrown charge's walk — the first square along the straight
    line toward the foe, at least 10 ft on, that ends within 30 ft (Improved: within the
    weapon's five range increments) — or the sentence refusing it."""
    from . import position as position_mod

    sc = engine.scene
    grid = getattr(sc, "grid", None)
    start = sc.positions.get(actor.ref)
    there = sc.positions.get(defender.ref)
    if grid is None or start is None or there is None:
        return "A charge is measured on the map, and there is none here."
    w = actor.weapon(weapon_key) or {}
    far = 5 * int(w.get("range_ft") or 10) if actor.has_state(CHARGING_HURLER_FAR) else 30
    level = tuple(start[2:3])
    here = tuple(start[:2])
    goal = tuple(there[:2])
    n = max(abs(goal[0] - here[0]), abs(goal[1] - here[1]))
    taken = position_mod.occupancy_toward(sc, actor, defender)
    was = gridmod.distance_between(here + level, actor.size, there, defender.size)
    why = (f"{defender.name} is too far for a thrown charge: it must end within {far} ft.")
    # The walk ends within 30 ft when the line gets there (Improved's +2 damage, and the
    # point-blank range), else at the first square in range (owner call: the engine
    # chooses the stopping square, as it chooses a charge's).
    first = None
    for k in range(2, n):
        sq = (round(here[0] + (goal[0] - here[0]) * k / n),
              round(here[1] + (goal[1] - here[1]) * k / n))
        feet = gridmod.distance(here, sq)
        if feet > budget:
            break
        gap = gridmod.distance_between(sq + level, actor.size, there, defender.size)
        if gap > far or gap >= was:
            continue
        if not all(grid.passable(p) and p not in taken
                   for p in gridmod.footprint(sq, actor.size)) or \
                engine._charge_line_blocked(actor, here, sq, taken):
            why = (engine._charge_line_blocked(actor, here, sq, taken)
                   or f"The line of the charge is blocked at {sq}.")
            break
        first = first or (sq, feet)
        if gap <= 30:
            return sq, feet
    if first is not None:
        return first
    return why if n > 2 else (f"A charge must move at least 10 ft, and {defender.name} is "
                              f"too close for a thrown charge.")


# --- Cleave Through and Swap Places (feat loop b7-moves; ledger groups 1 and 2) ---------------
#
# Cleave Through (Dwarves of Golarion): "When using Cleave or Great Cleave, if your initial
# attack hits, you may take a single 5-foot step as a free action before making your
# additional attacks. If doing so places a creature within your threatened area, that
# creature becomes a legal target for your additional Cleave attack(s) as long as it meets
# all the other prerequisites." Measured before (its not_yet line): Cleave's extra blows were
# chosen only from those threatened when it was declared. The step is the round's 5-foot
# step (owner call: not taken after other movement), and the engine picks the square, as it
# picks the cleave's next foe.
#
# Swap Places (UC, teamwork): "Whenever you are adjacent to an ally who also has this feat,
# you can move into your ally's square as part of normal movement. At the same time, your
# ally moves into your previous space as an immediate action ... Your ally must be the same
# size as you ... Your ally does not provoke an attack of opportunity from this movement, but
# you provoke as normal. This movement does not count against your ally's movement on his
# next turn." Measured before (its not_yet line): a move into an occupied square was refused.

CLEAVE_THROUGH = "attack.cleave.step"
SWAP_PLACES = "teamwork.swap-places"


def _cleave_through(engine, intent, outcome) -> list[dict]:
    from . import position as position_mod
    from . import reactions as reactions_mod

    sc = engine.scene
    params = intent.params or {}
    actor = sc.actors.get(intent.actor or "")
    defender = sc.actors.get(str(intent.target or ""))
    if actor is None or defender is None or not params.get("cleave") \
            or params.get("cleaving") or not actor.has_state(CLEAVE_THROUGH) \
            or not sc.has_grid or actor.ref not in sc.positions \
            or defender.ref not in sc.positions or stepping.walked(sc, actor.ref):
        return []
    if not any(b.get("ref") == defender.ref and b.get("result") in ("hit", "critical")
               for b in outcome.blows or ()):
        return []
    if any(e.get("kind") == "cleave" for e in outcome.effects or ()):
        return []                               # a foe was already in reach
    weapon = str(params.get("weapon") or actor.wielded_key() or "").lower()
    here = tuple(sc.positions[actor.ref])
    there = tuple(sc.positions[defender.ref])
    foes = [ref for ref, foe in sc.actors.items()
            if ref not in (actor.ref, defender.ref) and not foe.is_down
            and ref in sc.positions and not reactions_mod._allied(sc, actor.ref, ref)
            and gridmod.distance_between(there, defender.size,
                                         tuple(sc.positions[ref]), foe.size)
            <= gridmod.SQUARE_FT]
    if not foes:
        return []
    squares, level = _open_squares(engine, actor, here[:2])
    for sq in sorted(squares, key=lambda q: (q[1], q[0])):
        if not stepping.is_step(sc, actor, here, sq + level):
            continue
        sc.positions[actor.ref] = tuple(sq) + level
        try:
            reached = [r for r in foes if position_mod.out_of_reach(
                sc, actor, sc.actors[r], weapon) is None]
        finally:
            sc.positions[actor.ref] = here
        if not reached:
            continue
        foe = sc.actors[reached[0]]
        keep = {k: v for k, v in params.items()
                if k in ("weapon", "power_attack", "lethality")}
        keep.update({"weapon": weapon, "cleave": True, "cleaving": [defender.ref]})
        vis = intent.visibility or ("player" if actor.is_pc else "hidden")
        return [{"op": "move", "actor": actor.ref, "id": f"{intent.id}-cleave-through",
                 "target": None, "visibility": vis,
                 "because": f"{actor.name} steps through the cleave (Cleave Through)",
                 "params": {"square": list(sq) + list(level)}},
                {"op": "attack", "actor": actor.ref, "target": foe.ref,
                 "id": f"{intent.id}-cleave1", "visibility": vis,
                 "because": f"cleaving on from {defender.name} (Cleave Through)",
                 "params": keep}]
    return []


def swap_partner(engine, mover, square):
    """The ally whose square this walk ends in, by Swap Places: adjacent to the mover, the
    same size, both holding the feat, able to move and with an immediate action to spend;
    else None."""
    sc = engine.scene
    if square is None or not mover.has_state(SWAP_PLACES) or not sc.has_grid:
        return None
    start = sc.positions.get(mover.ref)
    if start is None:
        return None
    for ref, ally in sc.actors.items():
        spot = sc.positions.get(ref)
        if ref == mover.ref or spot is None or tuple(spot)[:2] != tuple(square)[:2] \
                or not ally.has_state(SWAP_PLACES) or ally.size != mover.size \
                or ally.is_down or ally.blocking_key("move") or not _friends(sc, ref, mover.ref) \
                or gridmod.distance(tuple(start)[:2], tuple(spot)[:2]) > gridmod.SQUARE_FT:
            continue
        if sc.in_encounter and engine._swift_refusal(ally, True, "Swap Places"):
            return None
        return ally
    return None


def swap(engine, mover, ally, from_square) -> dict:
    """The ally into the mover's old square: an immediate action, no attack of
    opportunity (moved by the engine, never walked), and no step or move spent."""
    sc = engine.scene
    if sc.in_encounter:
        engine._spend_swift(ally, True, "Swap Places")
    sc.positions[ally.ref] = tuple(from_square)
    return {"ref": ally.ref, "kind": "position", "from": None, "to": tuple(from_square),
            "swapped_with": mover.ref, "origin": "rule:feat-swap-places"}


# --- a full attack of throws (feat loop b7-moves; ledger group 27) ---------------------------
#
# Quick Draw (CRB): "you can draw a weapon as a free action instead of as a move action ...
# A character who has selected this feat may throw weapons at his full normal rate of
# attacks (much like a character with a bow)." Two-Handed Thrower (APG): "Using two hands to
# throw any weapon requires only a standard action for you. If you also have the Quick Draw
# feat, you can throw two-handed weapons at your full normal rate of attacks"; Normal:
# "Throwing a two-handed weapon is a full-round action." Raging Hurler (APG): "While raging,
# you can throw a two-handed weapon as a standard action, and you double the range increment
# for weapons you throw. If you also have the Quick Draw feat, you can throw two-handed
# weapons at your full normal rate of attacks."
#
# Measured before: a thrown weapon was one throw an op (`Engine._op_attack`, "full = False"
# for every throw), and throwing a spear two-handed cost a standard action like a dagger.
# Each throw of a full attack is one of the weapons carried (`Actor.weapons`), each landing
# where it fell (`Engine._thrown_lands`, once a throw).

QUICK_DRAW = "action.draw.free"
TWO_HANDED_THROWER = "throw.two-handed"
RAGING_HURLER = "throw.raging"
RAGE = "buff.stance.rage"


def raging_hurler(actor) -> bool:
    return actor.has_state(RAGING_HURLER) and actor.has_state(RAGE)


def _two_handed(weapon: dict) -> bool:
    return int(weapon.get("hands", 1) or 1) >= 2


def throws_at_full_rate(actor, weapon: dict) -> bool:
    """Whether this thrower may make a full attack of throws with this weapon."""
    if not actor.has_state(QUICK_DRAW):
        return False
    return not _two_handed(weapon) or actor.has_state(TWO_HANDED_THROWER) \
        or raging_hurler(actor)


def copies(actor, weapon_key: str) -> int:
    """How many of this table weapon the thrower carries (each throw is one)."""
    from . import weapons as weapons_mod

    want = weapons_mod.key_for(weapon_key) or str(weapon_key).lower()
    return sum(1 for w in actor.weapons if (weapons_mod.key_for(w) or w.lower()) == want)


def whole_round_throw(actor, weapon: dict, params) -> str:
    """The full-round action a two-handed throw is (Two-Handed Thrower's Normal), or ""."""
    if actor is None or not (params or {}).get("thrown") or not _two_handed(weapon) \
            or actor.has_state(TWO_HANDED_THROWER) or raging_hurler(actor):
        return ""
    return f"throwing the {str(weapon.get('name') or 'weapon').lower()} two-handed"


def thrown_increment(actor, inc: int, thrown: bool) -> int:
    """Raging Hurler: "you double the range increment for weapons you throw"."""
    return inc * 2 if thrown and inc and raging_hurler(actor) else inc



# --- the monk's slow fall (feat loop b7-moves; ledger group 23) ------------------------------
#
# CRB, Monk (aonprd.com/ClassDisplay.aspx?ItemName=Monk, read 2026-11-27): "Slow Fall (Ex):
# At 4th level or higher, a monk within arm's reach of a wall can use it to slow his
# descent. When first gaining this ability, he takes damage as if the fall were 20 feet
# shorter than it actually is. The monk's ability to slow his fall (that is, to reduce the
# effective distance of the fall when next to a wall) improves with his monk level until at
# 20th level he can use a nearby wall to slow his descent and fall any distance without
# harm." The distance is the class table's own ladder ("slow fall 20 ft" .. "slow fall any
# distance"), read by `classfeatures.rungs`, never a number written here. Measured before:
# slow fall was a name on the class table and a fall beside a wall hurt a 20th-level monk
# as it hurt anybody.
#
# Within arm's reach of a wall: falling off a climb (the wall it was on), or a square
# beside a solid one on the board (owner call: no wall is assumed off the board).

SLOW_FALL = "class.slow-fall"
ANY_DISTANCE = 10_000


def slow_fall_ft(actor) -> int:
    """The feet this body's slow fall takes off a fall beside a wall (0 for none)."""
    from . import classfeatures

    if not actor.has_state(SLOW_FALL) or not actor.char_class:
        return 0
    ladder = classfeatures.rungs(actor.char_class, actor.level, "slow-fall")
    if ladder and "any distance" in str(ladder[-1]).lower():
        return ANY_DISTANCE
    return classfeatures.number(actor.char_class, actor.level, "slow-fall")


def beside_wall(engine, actor) -> bool:
    """A wall within arm's reach: on one (climbing), or a solid square beside it."""
    from . import bodyskills

    if actor.has_state(bodyskills.CLIMBING):
        return True
    sc = engine.scene
    grid = getattr(sc, "grid", None)
    spot = sc.positions.get(actor.ref) if sc is not None else None
    if grid is None or spot is None:
        return False
    x, y = tuple(spot)[:2]
    return any(grid.inside((x + dx, y + dy)) and not grid.passable((x + dx, y + dy))
               for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)


# --- moving unable to see (feat loop b7-moves; ledger group 2) -------------------------------
#
# CRB, Conditions, Blinded: "Blinded creatures must make a DC 10 Acrobatics check to move
# faster than half speed"; CRB p.172, Vision and Light: "In areas of darkness, creatures
# without darkvision are effectively blinded" (`Engine.sees_nothing`). Blind-Fight (CRB):
# "You do not need to make Acrobatics skill checks to move at full speed while blinded";
# Normal: "The speed reduction for darkness and poor visibility also applies." Measured
# before (Blind-Fight's not_yet line): a blinded body, or one in the dark, walked its full
# speed. The walk is priced at half; the Acrobatics check to go faster is not offered
# (a body may always take half speed; said in the lane report).

BLIND_STRIDE = "movement.blind.full-speed"     # Blind-Fight's document tag


def unsighted_budget(engine, actor, budget: int) -> int:
    """Half the move's feet for a body that cannot see, unless Blind-Fight."""
    if actor.has_state(BLIND_STRIDE):
        return budget
    blind = actor.has_state("state.senses.blinded")
    if not blind:
        try:
            blind = bool(engine.scene.sees_nothing(actor))
        except Exception:  # noqa: BLE001 — a bare scene with no place to light
            blind = False
    return max(gridmod.SQUARE_FT, _half(budget)) if blind else budget


__all__ = ["charge_multiple", "moved_already", "after", "no_move_left", "allowance",
           "grant_walk", "coup_walk_ok", "before"]
