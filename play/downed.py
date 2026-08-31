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
"""
from __future__ import annotations

from dataclasses import dataclass, field

# PF1e: a stable character has a chance each hour of waking. Rolling hour by hour for a
# solo game is bookkeeping nobody enjoys, so the wait is resolved in one step and the
# character comes round at 1 hit point.
HOURS_UNTIL_CONSCIOUS = 1


@dataclass
class Outcome:
    state: str                       # fine | disabled | dying | stable | dead
    lines: list[str] = field(default_factory=list)
    playable: bool = True

    @property
    def died(self) -> bool:
        return self.state == "dead"


def state_of(pc) -> str:
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
    for gone in ("stable", "unconscious", "dying", "disabled"):
        pc.remove_condition(gone)
    pc.hp = max(pc.hp, 1)
    lines.append(
        f"You come round about an hour later, face down where you fell, on "
        f"{pc.hp} hit point{'s' if pc.hp != 1 else ''}. Whoever was standing over you "
        f"has gone."
    )
    return Outcome(state="stable", playable=True, lines=lines)


def death_notice(pc) -> str:
    return (
        f"{pc.name} is dead.\n\n"
        f"There is no save against this and no roll left to make. What they did is in "
        f"the record; the world carries on without them.\n\n"
        f"Choose who plays next."
    )
