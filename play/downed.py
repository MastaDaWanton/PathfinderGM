"""What happens when the player's character cannot act.

Found in play: Kesst was knocked to -3, "The fight is over" printed, and the player typed
"now what" — and the game carried on as though nothing had happened. The GM narrated her
stumbling and dodging, a thug attacked her again, a *second* encounter started because
someone swung, and "The fight is over" printed a second time. Nothing anywhere asked
whether the character was in a state to take a turn.

A character at or below 0 hit points does not get a turn. What happens instead is the
rules' business, not the GM's:

  disabled (exactly 0)  they are conscious and may act, but carefully
  dying   (below 0)     a hit point a round until they stabilise or die
  stable                unconscious, no longer bleeding, and will come round in time
  dead                  the campaign is over for that character
  held                  cannot act, and not on the hit-point track at all: paralysed,
                        stunned, petrified, bound. Waited out if it has a clock, and
                        said plainly if it has not.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rules import survival

# PF1e: a stable character has a chance each hour of waking. Rolling hour by hour for a
# solo game is bookkeeping nobody enjoys, so the wait is resolved in one step and the
# character comes round at 1 hit point.
HOURS_UNTIL_CONSCIOUS = 1


@dataclass
class Outcome:
    state: str                       # fine | disabled | dying | stable | dead | held
    lines: list[str] = field(default_factory=list)
    playable: bool = True
    # What the winners did while the player was down (`rules/defeat.py`), as records
    # for the turn log: who took what, who went where.
    effects: list[dict] = field(default_factory=list)

    @property
    def died(self) -> bool:
        return self.state == "dead"


def state_of(pc) -> str:
    """Which of the resolutions above this character is owed.

    The first four rungs name the conditions the hit-point ladder writes, and they are
    literal on purpose: `apply_hp_state` writes exactly these keys and this is the
    reading of them. The fifth rung is the one that was missing.

    Measured before it existed: seven conditions that cannot act — cowering, dazed,
    fascinated, helpless, paralyzed, petrified and stunned — fell through to "fine". The
    character was handed a turn, the GM planned it, and the engine's guard then refused
    every op in it as a legality error. A legality error regenerates rather than
    repairs, so the turn burned the retry loop and reached the player as a 502.

    Widening the "stable" rung to `state.down` instead is worse, and was the tempting
    fix: it routes a petrified character into the wake-up path, which burns an hour of
    world clock, floors their hit points at 1 and prints "You come round about an hour
    later" to a statue that is still a statue.
    """
    if pc is None:
        return "fine"
    if pc.has_condition("dead"):
        return "dead"
    if pc.has_condition("dying"):
        return "dying"
    if pc.has_condition("stable") or pc.has_condition("unconscious"):
        return "stable"
    # Before `disabled`, not after. Disabled means "conscious, and may act carefully" —
    # it is a rung that HANDS OUT a turn, so a character who is disabled *and* paralyzed
    # was reported fit for one. Measured: all seven of the conditions above reached the
    # turn gate as playable whenever the character sat at exactly 0 hit points, and the
    # engine then refused every op in the plan as a legality error. The 502 this rung
    # exists to close was still open for the whole hp == 0 case.
    if pc.has_state("state.unable") or pc.has_state("state.down"):
        return "held"
    if pc.has_condition("disabled"):
        return "disabled"
    return "fine"


def resolve(campaign) -> Outcome:
    """Carry a downed character forward to wherever the rules take them.

    Called instead of a turn, because the player has no turn to take. The dying bleed
    round by round until they stabilise or die; the stable wake up; the dead stay dead.
    """
    scene = campaign.scene
    pc = scene.pc()
    state = state_of(pc)

    if state == "fine" or state == "disabled":
        return Outcome(state=state, playable=True)

    if state == "dead":
        return Outcome(state="dead", playable=False, lines=[death_notice(pc)])

    if state == "held":
        return _wait_it_out(campaign, pc)

    engine = campaign.engine()
    lines: list[str] = []

    # Asleep where they fell (rules/survival.py): the third failed save against sleep. Not
    # a knockout and not stable — the general branch below would wake them after one hour
    # with their hit points floored, and the awake clock untouched, so the next hour's
    # save would drop them again, for ever. The body's own sleep runs out on the clock's
    # door (`survival.charge` wakes them into a night's rest); this only lets it.
    if survival.asleep(pc) is not None and not scene.in_encounter \
            and not pc.has_state("state.down.dying"):
        left = survival.sleep_left(pc)
        hours = max(1, round(left / 60))
        scene.advance(left)
        told = [s for r in scene.take_body_said() for s in r.get("said") or []]
        woke = survival.asleep(pc) is None and not pc.has_state("state.down")
        lines.append(
            f"You sleep on where you dropped, "
            f"{'about an hour' if hours == 1 else f'{hours} hours'} more"
            + (", and wake." if woke else ", and do not wake."))
        lines.extend(told)
        return Outcome(state="stable", playable=woke, lines=lines)

    if state == "dying":
        # Round by round, so the player watches it happen rather than being told the
        # result. This is the most frightening thing that can happen to a character and
        # it should not be a single line.
        for _ in range(24):
            result = pc.bleed_out(engine.dice)
            if result is None:
                break
            scene.round += 1
            if result["outcome"] == "dying":
                lines.append(f"You are bleeding out. ({pc.hp} hit points)")
            elif result["outcome"] == "stable":
                lines.append("The bleeding stops. You are still down, but you are alive.")
                break
            elif result["outcome"] == "dead":
                lines.append(death_notice(pc))
                return Outcome(state="dead", playable=False, lines=lines)
        if pc.has_condition("dead"):
            lines.append(death_notice(pc))
            return Outcome(state="dead", playable=False, lines=lines)

    # Beaten senseless rather than cut down: unconscious from nonlethal damage, hit
    # points above zero, nothing bleeding. 1e wakes them when the nonlethal falls back
    # to their hit points, at 1 point an hour per level (`Scene.advance` heals it), so
    # the wait is however many hours that takes — and their hit points are left alone.
    # The general branch below floors hp at 1 and clears the unconsciousness after one
    # hour, which for a knockout of 20 on 9 hit points woke a player who was still out
    # cold by the rules, to be knocked down again by the next hit-point check.
    if (pc.hp > 0 and pc.nonlethal > pc.nonlethal_threshold
            and not pc.has_state("state.down.dying")
            and not pc.has_state("state.down.stable")):
        if scene.in_encounter:
            scene.end_encounter()
        # The winners act while the player lies there, before the clock moves.
        effects, after = _the_winners_act(campaign, pc)
        per_hour = max(1, int(getattr(pc, "level", 1) or 1))
        hours = max(1, -(-(pc.nonlethal - pc.nonlethal_threshold) // per_hour))
        scene.advance(hours * 60)
        # The clock's door rolls the body's checks now (rules/survival.py, `charge`), so
        # the hours spent out cold can add to what keeps them there — a parched body
        # keeps failing its thirst checks while it lies senseless. Said as it is, never
        # "you come round" over a character who has not.
        told = [s for r in scene.take_body_said() for s in r.get("said") or []]
        if pc.has_state("state.down"):
            lines.append(
                f"{'About an hour' if hours == 1 else f'{hours} hours'} pass"
                f"{'es' if hours == 1 else ''}, and you do not come round.")
            lines.extend(told)
            lines.extend(after)
            return Outcome(state="stable", playable=False, lines=lines, effects=effects)
        lines.append(
            f"You come round {'about an hour' if hours == 1 else f'{hours} hours'} "
            f"later, aching, where you were knocked down.")
        lines.extend(told)
        lines.extend(after)
        return Outcome(state="stable", playable=True, lines=lines, effects=effects)

    # Stable, one way or the other: the fight is long over and the character wakes.
    if scene.in_encounter:
        scene.end_encounter()
    effects, after = _the_winners_act(campaign, pc)
    # An hour used to pass with nothing ticking at all — not conditions, not buffs,
    # not pools, not compulsions.
    scene.advance(HOURS_UNTIL_CONSCIOUS * 60)
    told = [s for r in scene.take_body_said() for s in r.get("said") or []]
    pc.hp = max(pc.hp, 1)
    pc.clear_states("recovery.hit-points")
    lines.append(
        f"You come round about an hour later, face down where you fell, on "
        f"{pc.hp} hit point{'s' if pc.hp != 1 else ''}."
    )
    lines.extend(told)
    lines.extend(after)
    return Outcome(state="stable", playable=True, lines=lines, effects=effects)


def _the_winners_act(campaign, pc) -> tuple[list[dict], list[str]]:
    """Whoever beat the player acts on it (`rules/defeat.py`): robs them of a share of
    the coin and one thing, goes, and leaves a quest in the Journal to get it back.

    Both wake-up lines used to END with a claim — "Whoever was standing over you has
    gone", "Whoever did it has gone" — that nothing made true. Measured 2026-10-04 on
    the owner's save: an hour after that line both robbers stood on the squares they
    had fought from, the player's purse untouched, and the panel, the map and the
    narration each said something different about them. The sentence about the winners
    is now built from what they actually did, and says nothing when nobody was there.
    """
    from rules import defeat, goods

    coins = None
    world = getattr(campaign, "world", None)
    if world is not None:
        try:
            coins = goods.coinage(world, getattr(campaign, "location", None))
        except Exception:      # noqa: BLE001 — the coin's name is never worth the turn
            coins = None
    # Where it happened, by the name the party knows it by, for the quest the robbery
    # opens ("beat you down at the warrens"). The engine's own namer; "" falls back.
    here = ""
    try:
        from rules import places as places_mod

        engine = campaign.engine()
        p = places_mod.find(engine.places(), str(campaign.scene.at or "")) if engine else None
        here = p.name if p is not None else ""
    except Exception:          # noqa: BLE001 — a name is never worth the turn either
        here = ""
    return defeat.aftermath(campaign.scene, pc, coins, here_name=here)


def _wait_it_out(campaign, pc) -> Outcome:
    """Cannot act, and not on the hit-point track: paralysed, stunned, bound, petrified.

    There is no turn to take and no bleeding to resolve either, and until this branch
    existed there was no third answer — the character came back "fine", was handed a
    turn, and every op in it was refused by the engine as a legality error. A legality
    error regenerates rather than repairs, so the turn burned the retry loop and reached
    the player as a 502.

    A hold with a clock is waited out, which is what a table does: everyone else acts and
    the clock comes round again. A hold without one is said plainly. The tempting
    alternative — routing these into the stable branch below — burns an hour of world
    clock, floors hit points at 1 and tells a petrified character they have come round.
    """
    from rules import states

    scene = campaign.scene
    # Found by the same predicate that chose it, not by key. `blocking_key` falls back
    # to the effect's NAME when a document-declared state carries no key, and looking
    # that up as a key matched nothing — so a three-round hold read as permanent.
    held = next((e for e in pc.effects if states.stops(e.tags)), None)
    what = ((held.name if held else "") or pc.blocking_key()
            or "unable to move").lower()
    rounds = int(getattr(held, "rounds_left", 0) or 0) if held else 0

    if scene.in_encounter:
        # No skipping time inside a fight. `Scene.advance` is EXPIRY ONLY by contract:
        # it runs no turns, fires no wards, drains no upkeep and never rolls the dying.
        # Using it here put the player inside a safety bubble — measured, a paralyzed
        # character stood among three thugs for four rounds and took not one attack,
        # while the burning cloud they were lying in lost four rounds of its clock for
        # free. Every stun and daze the player suffered cost them nothing.
        #
        # The turn is simply not theirs. The caller runs the world's turns instead, and
        # the rounds tick through `advance_turn`, which is the door that fires things.
        return Outcome(state="held", playable=False, lines=[
            f"You are {what} and can only watch."])

    if rounds <= 0:
        return Outcome(state="held", playable=False, lines=[
            f"You are {what}, and it is not wearing off on its own. Nothing you decide "
            f"changes that — this one needs somebody else, or magic. Time can pass, but "
            f"you cannot spend it."])

    # Out of a fight nobody is swinging, so skipping to the far side is honest.
    ended = scene.advance(0, rounds=rounds)
    lines = [f"You are {what} and can do nothing but wait. "
             f"{rounds} round{'s' if rounds != 1 else ''} pass."]
    # Everything else that ran out while they stood there — law 3 says an expiry the
    # engine records is one the player may be told about. The hold's own expiry tell is
    # dropped because the last line says it in words the player is already reading.
    lines.extend(line for line in (ended.get("ended") or [])
                 if what not in line.lower())
    still = pc.blocking_condition()
    lines.append("You have yourself back." if not still
                 else f"You are still {still.lower()}.")
    return Outcome(state="held", playable=not still, lines=lines)


def death_notice(pc) -> str:
    return (
        f"{pc.name} is dead.\n\n"
        f"There is no save against this and no roll left to make. What they did is in "
        f"the record; the world carries on without them.\n\n"
        f"Choose who plays next."
    )
