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

# PF1e: a stable character has a chance each hour of waking. Rolling hour by hour for a
# solo game is bookkeeping nobody enjoys, so the wait is resolved in one step and the
# character comes round at 1 hit point.
HOURS_UNTIL_CONSCIOUS = 1


@dataclass
class Outcome:
    state: str                       # fine | disabled | dying | stable | dead | held
    lines: list[str] = field(default_factory=list)
    playable: bool = True

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
    if pc.has_condition("disabled"):
        return "disabled"
    if pc.has_state("state.unable") or pc.has_state("state.down"):
        return "held"
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

    # Stable, one way or the other: the fight is long over and the character wakes.
    if scene.in_encounter:
        scene.end_encounter()
    # An hour used to pass with nothing ticking at all — not conditions, not buffs,
    # not pools, not compulsions.
    scene.advance(HOURS_UNTIL_CONSCIOUS * 60)
    pc.hp = max(pc.hp, 1)
    pc.clear_states("recovery.hit-points")
    lines.append(
        f"You come round about an hour later, face down where you fell, on "
        f"{pc.hp} hit point{'s' if pc.hp != 1 else ''}. Whoever was standing over you "
        f"has gone."
    )
    return Outcome(state="stable", playable=True, lines=lines)


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
    scene = campaign.scene
    key = pc.blocking_key()
    held = next((e for e in pc.effects if e.key == key), None)
    what = ((held.name if held else "") or key or "unable to move").lower()
    rounds = int(getattr(held, "rounds_left", 0) or 0) if held else 0

    if rounds <= 0:
        return Outcome(state="held", playable=False, lines=[
            f"You are {what}, and it is not wearing off on its own. Nothing you decide "
            f"changes that — this one needs somebody else, or magic. Time can pass, but "
            f"you cannot spend it."])

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
