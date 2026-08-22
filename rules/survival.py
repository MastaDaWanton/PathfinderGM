"""Sleep, food and water, and what happens when a character goes without.

Time was free before this. A character could forage for thirty hours, cross a continent and
sit up three nights running, and nothing on the sheet knew — the clock moved and the body
did not. That is fine while every action is a single swing, and it stops being fine the
moment the player can say "I forage for eighteen hours", which is the point of the slider
this module exists for.

**The 1e rules, kept.** Thirst bites after a day plus your Constitution score in hours, and
then it is an hourly Constitution check at DC 10, rising by one each time. Hunger waits
three days and then asks daily. Both deal non-lethal damage and leave the character
fatigued — non-lethal because thirst does not stab you, and because the engine already
knows that non-lethal drops a character without killing them.

**Staying awake is a Will save**, not the Constitution check 1e's forced-march rule uses.
That is the project owner's decision and it is deliberate: the question being asked is
whether you keep going, not whether your body holds out, and it makes staying up all night
a discipline rather than a hit point total.

**Anything here can be switched off per character.** A construct does not drink and
something stranger might not sleep, so all three needs are `ACTOR_RULES` exemptions and a
class or a homebrew ruleset can grant them. Checked through `allows()`, so a misspelled
exemption fails loudly instead of silently making a character immortal.
"""
from __future__ import annotations

from dataclasses import dataclass

MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24

# 1e: "A character can go without water for 1 day plus a number of hours equal to his
# Constitution score." Food is three days flat, and the Constitution grace is not repeated
# — the book gives it to thirst only.
THIRST_GRACE_HOURS = HOURS_PER_DAY
FOOD_GRACE_HOURS = 3 * HOURS_PER_DAY

# After the grace runs out, thirst asks every hour and hunger every day.
THIRST_INTERVAL_HOURS = 1
FOOD_INTERVAL_HOURS = HOURS_PER_DAY

# The hour at which staying awake starts to cost something. A full day is the number the
# player was given, so it is the number the rule uses.
AWAKE_GRACE_HOURS = 24

BASE_DC = 10
PARCHED_DAMAGE = "1d6"

# What the ground does to a body trying to stay upright on it. Not a forage modifier — the
# same biome can be generous and punishing at once, and a night in the open on a mountain
# is harder than a night in a barn whatever grows nearby.
BIOME_HARDSHIP = {
    "desert": 4, "tundra": 4, "mountain": 3, "swamp": 3, "jungle": 2, "planar": 2,
    "underground": 1, "coast": 1, "ruins": 1,
    "forest": 0, "hills": 0, "grassland": 0, "farmland": 0, "urban": 0,
}

# The exemptions. Named for what becomes true of the character, which is how the two rules
# already in ACTOR_RULES are named.
NO_SLEEP = "needs.no_sleep"
NO_FOOD = "needs.no_food"
NO_WATER = "needs.no_water"


@dataclass
class Toll:
    """What a stretch of time cost somebody."""
    hours: int = 0
    checks: list[dict] = None
    nonlethal: int = 0
    conditions: list[str] = None
    collapsed: bool = False

    def __post_init__(self):
        if self.checks is None:
            self.checks = []
        if self.conditions is None:
            self.conditions = []

    @property
    def ok(self) -> bool:
        return not self.collapsed and not self.nonlethal

    def as_dict(self) -> dict:
        return {"hours": self.hours, "checks": self.checks,
                "nonlethal": self.nonlethal, "conditions": self.conditions,
                "collapsed": self.collapsed}


def exempt(actor, rule: str) -> bool:
    """Is this character free of that need? False for anything that cannot answer."""
    try:
        return bool(actor.allows(rule))
    except (AttributeError, KeyError):
        return False


def hardship(biome: str) -> int:
    return BIOME_HARDSHIP.get((biome or "").strip().lower(), 0)


def awake_dc(hours_awake: int, biome: str = "") -> int:
    """DC 10 at the first hour past the grace, and one harder every hour after.

    The rise is what makes a long night a decision rather than a single gamble: hour
    twenty-five is trivial and hour forty is not, and the character can always stop.
    """
    over = max(0, int(hours_awake) - AWAKE_GRACE_HOURS)
    if over <= 0:
        return 0
    return BASE_DC + over + hardship(biome)


def thirst_dc(checks_made: int) -> int:
    return BASE_DC + max(0, int(checks_made))


def hunger_dc(checks_made: int) -> int:
    return BASE_DC + max(0, int(checks_made))


def hours_until_thirsty(actor) -> int:
    """How long before water starts to matter. Constitution buys the grace."""
    if exempt(actor, NO_WATER):
        return 1 << 30
    con = actor.ability_score("con") if hasattr(actor, "ability_score") else 10
    return THIRST_GRACE_HOURS + max(0, int(con))


def hours_until_hungry(actor) -> int:
    if exempt(actor, NO_FOOD):
        return 1 << 30
    return FOOD_GRACE_HOURS


def state(actor) -> dict:
    """What the sheet shows: how long since each need was met, and how long is left."""
    awake = int(getattr(actor, "awake_minutes", 0)) // MINUTES_PER_HOUR
    fed = int(getattr(actor, "fed_minutes", 0)) // MINUTES_PER_HOUR
    watered = int(getattr(actor, "watered_minutes", 0)) // MINUTES_PER_HOUR
    return {
        "awake_hours": awake,
        "fed_hours": fed,
        "watered_hours": watered,
        "sleep_due_in": None if exempt(actor, NO_SLEEP) else AWAKE_GRACE_HOURS - awake,
        "water_due_in": None if exempt(actor, NO_WATER)
                        else hours_until_thirsty(actor) - watered,
        "food_due_in": None if exempt(actor, NO_FOOD)
                       else hours_until_hungry(actor) - fed,
        "exempt": [name for name, rule in
                   (("sleep", NO_SLEEP), ("food", NO_FOOD), ("water", NO_WATER))
                   if exempt(actor, rule)],
    }


def _check(actor, kind: str, dc: int, dice, save: str = "") -> dict:
    """One endurance roll, as the log records it."""
    if save:
        mods = actor.save_modifiers(save)
        roll = dice.d20(mods, label=f"{kind} ({save.title()} save)",
                        visibility="player")
    else:
        from .dice import Modifier

        mod = actor.ability_mod("con")
        roll = dice.d20([Modifier(mod, "Constitution")], label=f"{kind} check",
                        visibility="player")
    return {"kind": kind, "dc": dc, "total": roll.total,
            "passed": roll.total >= dc, "save": save}


def pass_hours(actor, hours: int, dice, biome: str = "") -> Toll:
    """Spend real time, and let the body have its say.

    One hour at a time rather than one roll for the stretch, because the DCs rise as it
    goes and a single check against the final DC would make an eighteen-hour day either
    trivial or impossible with nothing in between. It also means the character stops at
    the hour they actually fell over, which is what the player needs to be told.
    """
    toll = Toll(hours=0)
    hours = max(0, int(hours))

    for _ in range(hours):
        actor.awake_minutes = int(getattr(actor, "awake_minutes", 0)) + MINUTES_PER_HOUR
        actor.fed_minutes = int(getattr(actor, "fed_minutes", 0)) + MINUTES_PER_HOUR
        actor.watered_minutes = int(getattr(actor, "watered_minutes", 0)) + MINUTES_PER_HOUR
        toll.hours += 1

        awake_hours = actor.awake_minutes // MINUTES_PER_HOUR
        watered_hours = actor.watered_minutes // MINUTES_PER_HOUR
        fed_hours = actor.fed_minutes // MINUTES_PER_HOUR

        # Thirst first: it is the one that bites soonest and hardest.
        if not exempt(actor, NO_WATER) and watered_hours > hours_until_thirsty(actor):
            made = int(getattr(actor, "thirst_checks", 0))
            got = _check(actor, "Thirst", thirst_dc(made), dice)
            actor.thirst_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                taken = dice.roll(PARCHED_DAMAGE, label="thirst", visibility="player")
                actor.take_nonlethal(taken.total)
                toll.nonlethal += taken.total
                if not actor.has_condition("fatigued"):
                    actor.add_condition("fatigued", source="thirst")
                    toll.conditions.append("fatigued")

        if (not exempt(actor, NO_FOOD) and fed_hours > hours_until_hungry(actor)
                and fed_hours % FOOD_INTERVAL_HOURS == 0):
            made = int(getattr(actor, "hunger_checks", 0))
            got = _check(actor, "Hunger", hunger_dc(made), dice)
            actor.hunger_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                taken = dice.roll(PARCHED_DAMAGE, label="hunger", visibility="player")
                actor.take_nonlethal(taken.total)
                toll.nonlethal += taken.total
                if not actor.has_condition("fatigued"):
                    actor.add_condition("fatigued", source="hunger")
                    toll.conditions.append("fatigued")

        if not exempt(actor, NO_SLEEP) and awake_hours > AWAKE_GRACE_HOURS:
            dc = awake_dc(awake_hours, biome)
            got = _check(actor, "Exhaustion", dc, dice, save="will")
            toll.checks.append(got)
            if not got["passed"]:
                taken = dice.roll(PARCHED_DAMAGE, label="exhaustion",
                                  visibility="player")
                actor.take_nonlethal(taken.total)
                toll.nonlethal += taken.total
                for name in ("fatigued", "exhausted"):
                    if not actor.has_condition(name):
                        actor.add_condition(name, source="going without sleep")
                        toll.conditions.append(name)
                        break
                toll.collapsed = True

        actor.apply_nonlethal_state()
        if toll.collapsed or not actor.can_act():
            break

    return toll


def sleep(actor, hours: int = 8) -> None:
    """A night resets the clock. Called by `rest`, which already does the healing."""
    if int(hours) >= 6:
        actor.awake_minutes = 0
        actor.thirst_checks = 0
        actor.hunger_checks = 0


def eat(actor) -> None:
    actor.fed_minutes = 0
    actor.hunger_checks = 0


def drink(actor) -> None:
    actor.watered_minutes = 0
    actor.thirst_checks = 0


__all__ = ["AWAKE_GRACE_HOURS", "BIOME_HARDSHIP", "NO_FOOD", "NO_SLEEP", "NO_WATER",
           "Toll", "awake_dc", "drink", "eat", "exempt", "hardship", "hours_until_hungry",
           "hours_until_thirsty", "hunger_dc", "pass_hours", "sleep", "state",
           "thirst_dc"]
