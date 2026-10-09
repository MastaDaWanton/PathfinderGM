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

**What thirst and hunger deal does not mend until the need is met** (CRB p.444; the
owner, 2026-10-05). It is withheld as it lands (`Actor.withhold_nonlethal`, a `withheld`
effect per need), every heal stops at it (`Actor.heal_nonlethal` is the floor and every
cure, rest and hour passes through it), a refused heal says why (`unmended`), and eating or
drinking lifts it (`eat`, `drink`), after which it heals by the ordinary clock. So a
parched character out cold and alone no longer heals faster than thirst harms them; they
die of it, which is the book's answer and the owner's.

**Staying awake is a Will save**, not the Constitution check 1e's forced-march rule uses.
That is the project owner's decision and it is deliberate: the question being asked is
whether you keep going, not whether your body holds out, and it makes staying up all night
a discipline rather than a hit point total.

**Anything here can be switched off per character.** A construct does not drink and
something stranger might not sleep, so all three needs are `ACTOR_RULES` exemptions and a
class or a homebrew ruleset can grant them. Checked through `allows()`, so a misspelled
exemption fails loudly instead of silently making a character immortal.

**The checks roll wherever the clock moves** (`charge`, 2026-10-05). Until then only
`pass_hours` rolled them, and it was reached from four ops (forage, the crafting trip, a
journey's march, venture); `Scene.advance` — waiting, walking the town, repairs, the
crafting benches, a knockout's hours — moved the counters and rolled nothing. The owner's
Sammy went 121 hours without sleep, food or water and nothing ever asked, and the panel's
DC climbed past anything a Will save can make. `charge` is the one place a body's hour is
spent: the clock's door calls it for the player, and `pass_hours` is the same hour in a
loop that stops when the work must.

Checks are rolled for hours as they pass, never for hours that passed before: a save
written before this change, days awake with no checks made, starts its first check at
DC 10 on the next hour boundary, not with a wall of saves for the backlog. tbaMUD freezes
needs while a player is offline and caps its own catch-up of missed ticks (`comm.c`, "If we
missed more than 30 seconds worth of pulses, just do 30 secs"); this is that call.
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
    # A night in open water is the worst there is — you cannot lie down in it, and going
    # to sleep is going under. A deck is a hard bed in the weather, which is a night in
    # the open with a roof over part of it.
    "water": 4, "underwater": 4, "deck": 1,
    "forest": 0, "hills": 0, "grassland": 0, "farmland": 0, "urban": 0,
}

# The exemptions. Named for what becomes true of the character, which is how the two rules
# already in ACTOR_RULES are named.
NO_SLEEP = "needs.no_sleep"
NO_FOOD = "needs.no_food"
NO_WATER = "needs.no_water"

# The sleep a body takes when it will not be refused any longer: the owner's ladder is a
# failed save to fatigued, a second to exhausted, and a third — failed while exhausted —
# drops the character asleep where they stand. Eight hours, because that is the night
# `Actor.rest` already means ("8 hours of sleep or more", CRB p.191) and waking from it is
# that night's rest. It is the `unconscious` condition, the one the sleep spell lands
# (content/spells/mechanics), told apart by its source.
SLEEP_SOURCE = "asleep where they fell"
COLLAPSE_SLEEP_MINUTES = 8 * MINUTES_PER_HOUR

# The needs whose non-lethal will not mend until they are met (CRB p.444), each with the
# act that meets it: (third person, as the tells say it; the bare verb).
WITHHELD_NEEDS = {"thirst": ("drinks", "drink"), "hunger": ("eats", "eat")}

# What a day of living costs, from the pack (CRB p.444, Starvation and Thirst): "Characters
# need at least a gallon of fluids and about a pound of decent food per day to avoid
# starvation. (Small characters need half as much.) In very hot climates, characters need
# two or three times as much water to avoid dehydration." Gallons and pounds because those
# are the book's units, and a waterskin "holds about 1/2 gallon of liquid" (CRB p.158,
# Ultimate Equipment p.58), so a day is two of them. The hot climate is read as the desert
# biome at the book's lower figure, two.
WATER_GALLONS_PER_DAY = 1.0
FOOD_LB_PER_DAY = 1.0
HOT_WATER = {"desert": 2.0}
HALF_RATIONS = frozenset({"small", "tiny", "diminutive", "fine"})

# The shortest stretch of time a body LIVES through rather than merely spends: a day, the
# interval a meal is due on. A wait the player asked for that long eats, drinks and sleeps
# from what is carried (`charge`'s `live`); anything shorter behaves exactly as it always
# did, so "I wait an hour" never empties a waterskin.
#
# Measured 2026-10-08 (the leatherworking bench lane), in the released game: a 21-day bark
# tannage's Wait for it killed a scratch character of thirst — twice, the second time
# carrying 40 waterskins — and the bench said only "You waited 21 days. You take the
# leather out"; an 8-day enchanting binding wait had killed an unfed character the same
# way. `Scene.advance` charged the body every hour of it and nothing in the clock's door
# ever ate or drank: only a march's camp did, and a wait has no camp. Fallout: New Vegas's
# hardcore mode is the cautionary tradition — its needs rise through the Wait and Sleep
# menus with nothing eaten, characters died in their sleep, and the community answered
# with mods ("NO Dying on rest in Hardcore Mode"). RimWorld's caravans are the shape kept
# here: members eat from the caravan's own inventory as they need to, and the forming
# screen says how many days the food lasts before anyone leaves.
LIVED_MINUTES = HOURS_PER_DAY * MINUTES_PER_HOUR
DAY_MINUTES = HOURS_PER_DAY * MINUTES_PER_HOUR

# Which pack verb meets which need, and the counter the meal resets.
PROVISIONS = {"water": ("watered_minutes", NO_WATER), "food": ("fed_minutes", NO_FOOD)}


@dataclass
class Toll:
    """What a stretch of time cost somebody."""
    hours: int = 0
    checks: list[dict] = None
    nonlethal: int = 0
    conditions: list[str] = None
    # The work has to stop: any failed save against sleep. `pass_hours` ends its stretch
    # here; the clock's door does not, because its caller already chose how far it goes.
    collapsed: bool = False
    # The third failure: asleep on the spot (`SLEEP_SOURCE`).
    fell_asleep: bool = False
    # And the sleep's end, eight hours on: the night's rest taken where they dropped.
    woke: bool = False
    # Non-lethal past their hit points (CRB p.191), and back below them.
    knocked_out: bool = False
    came_round: bool = False
    # Past their maximum the rest of it lands as lethal (CRB p.444).
    lethal: int = 0
    # Of the non-lethal, how much thirst and hunger now hold until they are met (CRB
    # p.444, `Actor.withhold_nonlethal`), and the most an hour's healing found it could
    # not touch — the latter is what earns the sentence saying why.
    withheld: int = 0
    unmended: int = 0
    # The night's own sentences when the sleep ended in waking (`Actor.sleep_through`):
    # pools and slots back, the morning's preparation, a level settled.
    rested: list[str] = None
    # A stretch lived through (`live`): what was eaten and drunk from the pack, one record
    # per thing spent ({"need", "name", "count", "amount"}), the nights slept inside it,
    # and the needs that came due with nothing carried to meet them.
    meals: list[dict] = None
    nights: int = 0
    ran_out: list[str] = None
    # A wait cut short because the pack ran out (`Scene.wait`): the need that stopped it,
    # the minutes waited and the minutes not.
    stopped: str = ""
    waited: int = 0
    unwaited: int = 0

    def __post_init__(self):
        if self.checks is None:
            self.checks = []
        if self.conditions is None:
            self.conditions = []
        if self.rested is None:
            self.rested = []
        if self.meals is None:
            self.meals = []
        if self.ran_out is None:
            self.ran_out = []

    @classmethod
    def from_record(cls, r: dict) -> "Toll":
        """A toll back from the record `as_dict` wrote — the one reader, so a field added
        here cannot be dropped by a copy of this list somewhere else (the engine folds
        several stretches' records into one telling)."""
        return cls(hours=int(r.get("hours") or 0), checks=list(r.get("checks") or []),
                   nonlethal=int(r.get("nonlethal") or 0),
                   conditions=list(r.get("conditions") or []),
                   **{k: bool(r.get(k)) for k in ("collapsed", "fell_asleep", "woke",
                                                  "knocked_out", "came_round")},
                   lethal=int(r.get("lethal") or 0),
                   withheld=int(r.get("withheld") or 0),
                   unmended=int(r.get("unmended") or 0),
                   rested=list(r.get("rested") or []),
                   meals=[dict(m) for m in r.get("meals") or []],
                   nights=int(r.get("nights") or 0),
                   ran_out=list(r.get("ran_out") or []),
                   stopped=str(r.get("stopped") or ""),
                   waited=int(r.get("waited") or 0),
                   unwaited=int(r.get("unwaited") or 0))

    @property
    def ok(self) -> bool:
        return not self.collapsed and not self.nonlethal

    @property
    def happened(self) -> bool:
        """Anything the player is owed a sentence about."""
        return bool(self.checks or self.fell_asleep or self.woke or self.knocked_out
                    or self.came_round or self.unmended or self.meals or self.nights
                    or self.ran_out or self.stopped)

    def absorb(self, other: "Toll") -> None:
        """Fold one hour's toll into the stretch's."""
        self.checks.extend(other.checks)
        self.meals.extend(other.meals)
        self.nights += other.nights
        self.ran_out.extend(n for n in other.ran_out if n not in self.ran_out)
        if other.stopped:
            self.stopped = other.stopped
        self.waited += other.waited
        self.unwaited = max(self.unwaited, other.unwaited)
        self.nonlethal += other.nonlethal
        self.lethal += other.lethal
        self.withheld += other.withheld
        self.unmended = max(self.unmended, other.unmended)
        self.rested.extend(other.rested)
        self.conditions.extend(c for c in other.conditions if c not in self.conditions)
        for flag in ("collapsed", "fell_asleep", "woke", "knocked_out", "came_round"):
            if getattr(other, flag):
                setattr(self, flag, True)

    def as_dict(self) -> dict:
        return {"hours": self.hours, "checks": self.checks,
                "nonlethal": self.nonlethal, "conditions": self.conditions,
                "collapsed": self.collapsed, "fell_asleep": self.fell_asleep,
                "woke": self.woke, "knocked_out": self.knocked_out,
                "came_round": self.came_round, "lethal": self.lethal,
                "withheld": self.withheld, "unmended": self.unmended,
                "rested": list(self.rested), "meals": [dict(m) for m in self.meals],
                "nights": self.nights, "ran_out": list(self.ran_out),
                "stopped": self.stopped, "waited": self.waited,
                "unwaited": self.unwaited}


def exempt(actor, rule: str) -> bool:
    """Is this character free of that need? False for anything that cannot answer."""
    try:
        return bool(actor.allows(rule))
    except (AttributeError, KeyError):
        return False


def hardship(biome: str) -> int:
    return BIOME_HARDSHIP.get((biome or "").strip().lower(), 0)


def awake_dc(checks_made: int, biome: str = "") -> int:
    """DC 10 for the first Will save past the grace, and one harder for every save made
    since the last sleep — the book's "+1 for each previous check", as thirst and hunger
    already count it.

    It counted HOURS AWAKE until 2026-10-05, and the two are not the same number: the
    owner's panel read "past a day awake — Will save every active hour, DC 107" (Sammy,
    day 6, 121 hours awake). Hours reach the awake counter by two doors — `pass_hours`,
    which rolls a save for each one, and `Scene.advance`, which moves the counters and
    rolls nothing — so ninety-seven hours that had never been asked raised the DC as if
    each had been passed. 107 is past any Will save a character can make: only a natural
    20 (`dice.d20_succeeds`) ever passes it. Counted by checks made, the rise is the one
    the design asked for — inside one long `pass_hours` stretch a check IS an hour, so
    hour twenty-five is still trivial and hour forty still is not — and it cannot run
    away on hours nobody rolled for.

    That only hid the defect; the same day `Scene.advance` began rolling the saves too
    (`charge`). Now every waking hour past the grace IS a save, and the third failure puts
    the character to sleep, which resets the count — so the DC is bounded by how many
    saves a body can pass before it fails three, not by how long nobody looked.
    """
    return BASE_DC + max(0, int(checks_made)) + hardship(biome)


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
    # A save's face decides before its total (CRB p.180, `dice.d20_succeeds`); the
    # Constitution check beside it is a check, and 1e gives checks no such rule.
    from .dice import d20_succeeds

    passed = d20_succeeds(roll, dc) if save else roll.total >= dc
    return {"kind": kind, "dc": dc, "total": roll.total, "passed": passed, "save": save}


def asleep(actor):
    """The sleep a failed night took them into (`SLEEP_SOURCE`), or None.

    Asked by source on top of the tag, because the question is not "is this body down"
    (`has_state("state.down.unconscious")` answers that) but "is this the sleep that
    ends in a night's rest" — a sap's knockout is the same condition and ends otherwise.
    """
    for e in getattr(actor, "effects", None) or ():
        if (e.kind == "condition" and e.key == "unconscious"
                and str(e.source or "") == SLEEP_SOURCE):
            return e
    return None


def sleep_left(actor) -> int:
    """Minutes of that sleep still to run; 0 when they are not in it."""
    nap = asleep(actor)
    if nap is None:
        return 0
    slept = int((nap.payload or {}).get("slept", 0) or 0)
    return max(0, COLLAPSE_SLEEP_MINUTES - slept)


def _to_hour(counter: int) -> int:
    """Minutes until this counter next reads a whole hour (60 when it already does)."""
    return MINUTES_PER_HOUR - (int(counter) % MINUTES_PER_HOUR)


def _harm(actor, amount: int, toll: Toll, need: str = "") -> None:
    """1d6 of a need's non-lethal damage, landed as the book lands it.

    Thirst's and hunger's (`need`) is withheld as it lands: "Nonlethal damage from thirst
    or starvation cannot be recovered until the character gets food or water, as
    needed—not even magic that restores hit points heals this damage" (CRB p.444; the
    owner, 2026-10-05: "yes it should not heal until you eat or drink"). Without it the
    hourly healing (1 a level) outran 1d6 from about level 4, so thirst only ever
    fatigued. The lethal overflow is not withheld — the book withholds the non-lethal —
    and the sleep ladder's damage is not a need's (`need` ""), so a night mends it.

    "Characters that take an amount of nonlethal damage equal to their total hit points
    begin to take lethal damage instead" (CRB p.444, Starvation and Thirst; the general
    rule is p.191). Without the ceiling a body left unconscious and parched took
    non-lethal for ever and could neither die nor come round — the knockout path waited
    out hours that only added to it. `Actor.take_damage` carries the same ceiling but
    also DR and resistance, which thirst does not get to argue with, so the ceiling is
    stated here and the hit points still change through the actor's own state ladder.
    """
    amount = max(0, int(amount))
    room = max(0, int(getattr(actor, "hp_max", 0) or 0) - int(actor.nonlethal or 0))
    soft = min(amount, room)
    if soft:
        actor.take_nonlethal(soft)
        toll.nonlethal += soft
        if need in WITHHELD_NEEDS:
            actor.withhold_nonlethal(need, soft)
            toll.withheld += soft
    hard = amount - soft
    if hard:
        actor.hp -= hard
        toll.lethal += hard
        actor.apply_hp_state()


def _tire(actor, toll: Toll, source: str, ladder: bool) -> None:
    """Fatigued, or — on the sleep ladder — exhausted when already fatigued.

    Thirst and hunger only ever fatigue: "Characters who have taken nonlethal damage from
    lack of food or water are fatigued" is a state the damage leaves, not a fresh cause
    each hour. Staying awake climbs (CRB Appendix 2: anything that would fatigue a
    fatigued character exhausts them). Exhausted replaces fatigued rather than standing
    beside it — the two rows' −2 and −6 would otherwise both reach the funnel.
    """
    if actor.has_state("state.impaired.exhausted"):
        return
    if actor.has_state("state.impaired.fatigued"):
        if not ladder:
            return
        actor.remove_condition("fatigued")
        actor.add_condition("exhausted", source=source)
        toll.conditions.append("exhausted")
        return
    actor.add_condition("fatigued", source=source)
    toll.conditions.append("fatigued")


def _fall_asleep(actor, toll: Toll) -> None:
    """The third failure: the body takes the sleep it was refused, where it stands.

    Through the one applicator as the `unconscious` condition — which is what sleep is to
    every rule that asks (`state.down`, `state.helpless`, the turn gate in
    play/downed.py). The eight hours are counted on the effect itself, in its payload,
    not in `rounds_left`: the activity ops charge the body BEFORE they move the clock
    (`pass_hours`, then `Scene.advance(charge_body=False)`), so a rounds clock would be
    ticked down by the very hours the character worked before dropping. The payload is
    advanced only here, by the body's own hours — remove the effect and the sleep is gone
    with it.
    """
    actor.add_condition("unconscious", source=SLEEP_SOURCE)
    nap = asleep(actor)
    if nap is not None:
        nap.payload = dict(nap.payload or {}, slept=0)
    toll.fell_asleep = True
    toll.conditions.append("asleep")


def _wake(actor, toll: Toll, dice=None) -> None:
    """Eight hours on: they wake, and it was a full night's sleep (`Actor.sleep_through`).

    The night's own door — the same one `Engine._op_rest` goes through — so a collapse
    heals, clears and resets exactly what a night in a bed does, and no second copy of
    what a night is can drift from it. Until 2026-10-05 this called `Actor.rest` alone,
    on the argument that the spells, the pools and the level were a camp's; the owner
    ruled the other way ("yes if you collapse for 8 hours"): the slots, the daily pools,
    the preparation and an earned level come back with the eight hours. What stays the
    camp's is only what the ground does (the cold, sleeping rough, the night's check):
    `_op_rest` asks those of a camp, and nobody made one.

    Reached only when the eight hours have run (`charge`). A sleep cut short — a fight,
    a cure that wakes them, anything that lifts the condition first — never gets here,
    and so gets none of it."""
    actor.remove_effects(match=lambda e: e is asleep(actor))
    night = actor.sleep_through("night", dice)
    toll.woke = True
    if night.get("refilled"):
        toll.rested.append("Recovered: " + ", ".join(night["refilled"]) + ".")
    if night.get("prepared"):
        toll.rested.append(str(night["prepared"]))
    lv = night.get("levelled") or {}
    if lv.get("ok"):
        grants = ", ".join(lv.get("grants") or ())
        toll.rested.append(f"In the sleep, level {lv['level']} settles: +{lv['hp']} hp"
                           + (f", {grants}" if grants else "") + ".")


def daily_need(actor, need: str, biome: str = "") -> float:
    """A day's water in gallons or a day's food in pounds for this body (CRB p.444)."""
    small = str(getattr(actor, "size", "medium") or "medium").lower() in HALF_RATIONS
    base = WATER_GALLONS_PER_DAY if need == "water" else FOOD_LB_PER_DAY
    if need == "water":
        base *= HOT_WATER.get((biome or "").strip().lower(), 1.0)
    return base * (0.5 if small else 1.0)


def _due(actor, toll: Toll) -> bool:
    """Anything `_provide` would see to now — counters only, so the hourly step asks the
    sheet nothing until a day's mark comes round."""
    for need, (counter, rule) in PROVISIONS.items():
        if need not in toll.ran_out and int(getattr(actor, counter, 0) or 0) >= DAY_MINUTES \
                and not exempt(actor, rule):
            return True
    return (int(getattr(actor, "awake_minutes", 0) or 0)
            >= AWAKE_GRACE_HOURS * MINUTES_PER_HOUR and not exempt(actor, NO_SLEEP))


def _up(actor) -> bool:
    """Whether the body can see to itself: eat, drink, lie down. Not out cold, not in the
    sleep a failed night took them into, not dead, and free to act."""
    return asleep(actor) is None and not actor.is_down and actor.can_act()


def _provide(actor, toll: Toll, biome: str) -> None:
    """A body living through a stretch sees to itself as each need comes due: a day's
    water once a day since the last drink, a day's food once a day since the last meal,
    out of the pack (`gear.provide`, the reader of the pack's `eat`/`drink` verbs), and a
    night's sleep once it has been up a day.

    Due at a day, not at the grace: the book's rate is a gallon and a pound "per day", and
    a character who waits until thirst bites before drinking is not living through a wait,
    they are rationing. The meal goes through `eat` and `drink`, the same reset `_op_eat`
    and a march's camp use, and the night through `sleep`, the camp's own — so nothing
    here is a second ticker (law 2): the counters move only in `charge`, and only those
    three doors put them back. A need due with too little carried is noted once in
    `ran_out` and left to the ordinary checks, which tell the rest; `Scene.wait` stops the
    wait before those checks begin.
    """
    from . import gear as gear_mod

    for need, (counter, rule) in PROVISIONS.items():
        if need in toll.ran_out or exempt(actor, rule) \
                or int(getattr(actor, counter, 0) or 0) < DAY_MINUTES:
            continue
        spent = gear_mod.provide(actor, need, daily_need(actor, need, biome))
        if spent is None:
            toll.ran_out.append(need)
            continue
        toll.meals.extend(spent)
        freed = drink(actor) if need == "water" else eat(actor)
        if freed:
            toll.rested.append(released_said(actor, "thirst" if need == "water"
                                             else "hunger", freed))
    if not exempt(actor, NO_SLEEP) \
            and int(getattr(actor, "awake_minutes", 0) or 0) >= AWAKE_GRACE_HOURS * MINUTES_PER_HOUR:
        sleep(actor)
        toll.nights += 1


def lasts(actor, minutes: int, biome: str = "") -> tuple[int, str]:
    """How many of `minutes` a body living through them (`_provide`) is carried by its
    pack, and the need that ends it sooner ("" when the pack lasts the whole stretch).

    The end is the hour the book's grace runs out after the last meal or drink the pack
    can pay for — the hour before the first check of thirst or hunger would be rolled — so
    a wait stopped here has cost the body nothing it will not get back by eating. Worked
    from the same counters, the same daily need and the same greedy spend (`gear.portions`)
    `_provide` uses, so the two cannot disagree about what the pack holds.
    """
    from . import gear as gear_mod

    minutes = max(0, int(minutes))
    best, why = minutes, ""
    for need, (counter, rule) in PROVISIONS.items():
        if exempt(actor, rule):
            continue
        grace = (hours_until_thirsty(actor) if need == "water"
                 else hours_until_hungry(actor)) * MINUTES_PER_HOUR
        now = int(getattr(actor, counter, 0) or 0)
        portions = gear_mod.portions(actor, need, daily_need(actor, need, biome))
        first = max(0, DAY_MINUTES - now)
        if portions:
            last = first + (portions - 1) * DAY_MINUTES
            if last >= minutes:
                continue
            ends = last + grace
        else:
            ends = max(0, grace - now)
        if ends < best:
            best, why = ends, need
    return best, why


def charge(actor, minutes: int, dice=None, biome: str = "", clock: int | None = None,
           roll: bool = True, live: bool = False) -> Toll:
    """Spend `minutes` of a body's time, and roll every check those minutes owe.

    The one place a body's hour is spent. Each counter's hour boundaries are walked in
    time order — thirst every hour past its grace, hunger every day past its own, a Will
    save every waking hour past a day awake — and the checks fall as they come, so the
    hour a character drops is an hour in the stretch and not its end.

    `clock` is the world clock at the start, and asks for the hourly non-lethal healing
    (CRB p.191) to be interleaved at the world's hour boundaries — without it a long wait
    knocked a parched character out mid-stretch on damage the hours either side of it
    would have healed, and told them so. `None` leaves healing to the caller (the activity
    ops, whose `Scene.advance` heals the stretch afterwards).

    `roll=False`, or no dice, moves the counters and rolls nothing: everybody else the
    campaign holds. Nothing feeds, waters or beds a companion or a merchant — `rest`,
    `eat` and a march's camp are the player's — so rolling theirs would starve every
    companion by the fourth day. The dead keep no clock at all: nine to twenty-seven days
    in the grave (play/views.py's resurrection) are not days without water.
    """
    toll = Toll()
    minutes = max(0, int(minutes))
    if not minutes or actor.has_state("state.down.dead"):
        return toll
    if not roll or dice is None:
        actor.awake_minutes = int(actor.awake_minutes) + minutes
        actor.fed_minutes = int(actor.fed_minutes) + minutes
        actor.watered_minutes = int(actor.watered_minutes) + minutes
        return toll

    level = max(1, int(getattr(actor, "level", 1) or 1))
    # Whether they are out cold, carried between steps and asked again only after a step
    # that changed something: a state is asked of the whole sheet (about a millisecond,
    # measured 2026-09-27), and a three-day wait is a few hundred steps.
    cold = actor.has_state("state.down.unconscious")
    spent = 0
    while spent < minutes:
        nap = asleep(actor)
        steps = [minutes - spent, _to_hour(actor.fed_minutes),
                 _to_hour(actor.watered_minutes)]
        if nap is not None:
            steps.append(max(1, sleep_left(actor)))
        else:
            steps.append(_to_hour(actor.awake_minutes))
        if clock is not None:
            steps.append(_to_hour(int(clock) + spent))
        step = max(1, min(steps))
        spent += step
        actor.fed_minutes = int(actor.fed_minutes) + step
        actor.watered_minutes = int(actor.watered_minutes) + step
        if nap is not None:
            # Asleep, the awake clock stands still; the stomach does not (tbaMUD's
            # `point_update` hungers every character "whatever their position").
            nap.payload = dict(nap.payload or {},
                               slept=int((nap.payload or {}).get("slept", 0) or 0) + step)
        else:
            actor.awake_minutes = int(actor.awake_minutes) + step
        before = len(toll.checks)
        woke = False

        if nap is not None and sleep_left(actor) <= 0:
            _wake(actor, toll, dice)
            woke = True

        # Living through it: the meal, the drink and the night come before the hour's
        # checks, so a body that eats at the day's mark is never asked about hunger.
        if live and _due(actor, toll) and _up(actor):
            _provide(actor, toll, biome)

        watered = int(actor.watered_minutes)
        if (watered % MINUTES_PER_HOUR == 0 and not exempt(actor, NO_WATER)
                and watered // MINUTES_PER_HOUR > hours_until_thirsty(actor)):
            made = int(getattr(actor, "thirst_checks", 0))
            got = _check(actor, "Thirst", thirst_dc(made), dice)
            actor.thirst_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                _harm(actor, dice.roll(PARCHED_DAMAGE, label="thirst",
                                       visibility="player").total, toll, need="thirst")
                _tire(actor, toll, "thirst", ladder=False)

        fed = int(actor.fed_minutes)
        if (fed % MINUTES_PER_HOUR == 0 and not exempt(actor, NO_FOOD)
                and fed // MINUTES_PER_HOUR > hours_until_hungry(actor)
                and (fed // MINUTES_PER_HOUR) % FOOD_INTERVAL_HOURS == 0):
            made = int(getattr(actor, "hunger_checks", 0))
            got = _check(actor, "Hunger", hunger_dc(made), dice)
            actor.hunger_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                _harm(actor, dice.roll(PARCHED_DAMAGE, label="hunger",
                                       visibility="player").total, toll, need="hunger")
                _tire(actor, toll, "hunger", ladder=False)

        awake = int(actor.awake_minutes)
        # Only a body that is up can fight sleep. Asleep it is already lost; knocked out
        # (or dying) there is no Will to ask — the hours still count against them, and the
        # saves resume when they come round.
        if (nap is None and asleep(actor) is None and awake % MINUTES_PER_HOUR == 0
                and not exempt(actor, NO_SLEEP)
                and awake // MINUTES_PER_HOUR > AWAKE_GRACE_HOURS
                and not actor.is_down and actor.can_act()):
            made = int(getattr(actor, "awake_checks", 0))
            got = _check(actor, "Exhaustion", awake_dc(made, biome), dice, save="will")
            actor.awake_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                _harm(actor, dice.roll(PARCHED_DAMAGE, label="exhaustion",
                                       visibility="player").total, toll)
                toll.collapsed = True
                if actor.has_state("state.impaired.exhausted") and not actor.is_down:
                    _fall_asleep(actor, toll)
                else:
                    _tire(actor, toll, "going without sleep", ladder=True)

        healed = False
        if clock is not None and (int(clock) + spent) % MINUTES_PER_HOUR == 0 \
                and actor.nonlethal:
            had = int(actor.nonlethal)
            healed = bool(actor.heal_nonlethal(level))
            # The hour that could not reach what thirst or hunger holds is said, once a
            # stretch (`said`): ten hours of the same refusal are one fact.
            toll.unmended = max(toll.unmended, refused(actor, level, had))

        if not (woke or healed or len(toll.checks) > before):
            continue
        actor.apply_nonlethal_state()
        now_cold = actor.has_state("state.down.unconscious")
        # A sleeper is unconscious too; only a knockout is told as one.
        if now_cold and not cold and asleep(actor) is None:
            toll.knocked_out = True
        if cold and not now_cold and not woke:
            toll.came_round = True
        cold = now_cold
        if actor.has_state("state.down.dead"):
            break
    toll.hours = spent // MINUTES_PER_HOUR
    return toll


def pass_hours(actor, hours: int, dice, biome: str = "") -> Toll:
    """Spend real time on work, and let the body have its say.

    One hour at a time rather than one roll for the stretch, because the DCs rise as it
    goes and a single check against the final DC would make an eighteen-hour day either
    trivial or impossible with nothing in between. It also means the character stops at
    the hour they actually fell over, which is what the player needs to be told.

    Each hour is `charge`'s, the same hour the clock's door spends; this only adds the
    stop. Healing is left to the caller's `Scene.advance(charge_body=False)`, which runs
    after and heals the stretch.
    """
    toll = Toll(hours=0)
    for _ in range(max(0, int(hours))):
        got = charge(actor, MINUTES_PER_HOUR, dice, biome=biome)
        toll.absorb(got)
        toll.hours += 1
        if toll.collapsed or not actor.can_act():
            break
    return toll


def said(actor, toll: Toll, biome: str = "") -> list[str]:
    """The body's stretch, as the tells the narrator is fed (law 3).

    One sentence per failed check — each one changed a number or a state — and one for
    the checks that held, because ten hours of "resists sleep" read as ten events is the
    log narrating its own bookkeeping. The DC is the engine's and said as it was rolled.
    """
    name = getattr(actor, "name", "") or "They"
    out: list[str] = []
    noun = {"Thirst": "thirst", "Hunger": "hunger", "Exhaustion": "sleep"}
    held: dict[str, list[int]] = {}
    for c in toll.checks:
        what = noun.get(c["kind"], c["kind"].lower())
        test = "a Will save" if c.get("save") == "will" else "a Constitution check"
        if c["passed"]:
            held.setdefault(what, []).append(int(c["dc"]))
            continue
        out.append(f"{name} fails {test} against {what} ({c['total']} against DC "
                   f"{c['dc']}).")
    for what, dcs in held.items():
        span = f"DC {dcs[0]}" if len(set(dcs)) == 1 else f"DC {min(dcs)}–{max(dcs)}"
        times = "once" if len(dcs) == 1 else f"{len(dcs)} times"
        out.append(f"{name} holds out against {what} {times} ({span}).")
    if toll.nonlethal:
        out.append(f"It costs {name} {toll.nonlethal} non-lethal damage.")
    if toll.lethal:
        out.append(f"Past what non-lethal can hold, {toll.lethal} of it is real damage.")
    for c in toll.conditions:
        if c == "asleep":
            continue
        out.append(f"{name} is {c}.")
    if toll.fell_asleep:
        out.append(f"{name} cannot stay awake any longer and falls asleep where they "
                   f"stand.")
    if toll.knocked_out:
        out.append(f"{name} collapses, senseless.")
    if toll.came_round:
        out.append(f"{name} comes round.")
    if toll.woke:
        out.append(f"{name} wakes after eight hours' sleep where they dropped.")
    out.extend(toll.rested)
    lived = lived_said(actor, toll)
    if lived:
        out.append(lived)
    for need in toll.ran_out:
        if need != toll.stopped:
            out.append(f"{name} has no {_NEED_WORDS[need][0]} in the pack to "
                       f"{'drink' if need == 'water' else 'eat'} when the day comes round.")
    if toll.stopped:
        out.append(stopped_said(actor, toll, biome))
    # What thirst and hunger hold is said where the healing met it, not where it was
    # dealt: "It costs Sammy 4 non-lethal damage" already told the blow, and the reader
    # learns the rule the first time an hour's rest does not take it off.
    if toll.unmended:
        line = unmended_said(actor)
        if line:
            out.append(line)
    return out


_NEED_WORDS = {"water": ("water", "drink", "gallon"), "food": ("food", "meal", "pound")}


def _span(minutes: int) -> str:
    """Exact days and hours, never rounded up: "2 days 6 hours", "5 hours"."""
    m = max(0, int(minutes))
    d, rest = divmod(m, DAY_MINUTES)
    h = rest // MINUTES_PER_HOUR
    bits = []
    if d:
        bits.append(f"{d} day{'s' if d != 1 else ''}")
    if h or not d:
        bits.append(f"{h} hour{'s' if h != 1 else ''}")
    return " ".join(bits)


def _amount(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def lived_said(actor, toll: Toll) -> str:
    """What living through the stretch cost, in one sentence for the narrator (law 3):
    the food and water spent out of the pack, by what was spent, and the nights slept.
    The brief's own example: "ate 21 rations, drank 21 gallons of water"."""
    if not (toll.meals or toll.nights):
        return ""
    name = getattr(actor, "name", "") or "They"
    parts: list[str] = []
    for need, verb, unit in (("food", "eats", "pound"), ("water", "drinks", "gallon")):
        rows = [m for m in toll.meals if m.get("need") == need]
        if not rows:
            continue
        total = sum(float(m.get("amount") or 0) for m in rows)
        by: dict[str, int] = {}
        for m in rows:
            by[str(m.get("name"))] = by.get(str(m.get("name")), 0) + int(m.get("count") or 0)
        # "42 of their waterskins", not "...waterskin" (seen live 2026-10-08): the pack
        # keeps a thing under its singular name, the sentence counts them.
        what = ", ".join(f"{n} of their {k}{'' if n == 1 or k.endswith('s') else 's'}"
                         for k, n in by.items())
        noun = "food" if need == "food" else "water"
        parts.append(f"{verb} {_amount(total)} {unit}{'s' if total != 1 else ''} of {noun} "
                     f"({what})")
    if toll.nights:
        parts.append(f"sleeps {toll.nights} night{'s' if toll.nights != 1 else ''}")
    joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"Through the wait {name} {joined}."


def stopped_said(actor, toll: Toll, biome: str = "") -> str:
    """Why a wait the player asked for ended short, or never began — said in words, with
    what a day needs, because the alternative the tradition shows is a corpse."""
    name = getattr(actor, "name", "") or "They"
    what, act, unit = _NEED_WORDS.get(toll.stopped, ("supplies", "meal", ""))
    need = daily_need(actor, toll.stopped, biome) if toll.stopped in PROVISIONS else 0
    hint = (f" A day needs {_amount(need)} {unit}{'s' if need != 1 else ''} of {what}"
            + ("; a waterskin holds half a gallon." if toll.stopped == "water" else ".")
            if need else "")
    if toll.waited:
        return (f"{name} stops waiting after {_span(toll.waited)}, with "
                f"{_span(toll.unwaited)} still to go: there is no {what} in the pack, "
                f"and they cannot go longer without a {act}.{hint}")
    return (f"{name} cannot wait {_span(toll.unwaited)}: there is no {what} in the pack, "
            f"and they cannot go longer without a {act}.{hint}")


def wait_lines(passed: dict, ref: str) -> list[str]:
    """The body's sentences for one creature out of a `Scene.wait`/`advance` result, for a
    bench page to show beside its own words. The record stays queued for the narrator
    (`Scene.take_body_said`): the page reads it, it does not take it."""
    return [str(s) for r in (passed or {}).get("body") or ()
            if str(r.get("ref")) == str(ref) for s in r.get("said") or ()]


def told_on_page(scene, passed: dict, ref: str) -> list[str]:
    """`wait_lines`, for a bench that writes them into the transcript itself: the creature's
    records are then TOLD, and come off the scene's queue (`Scene._body_said`) so the next
    batch does not tell them a second time. Measured in the leather final pass's playthrough
    (2026-10-09): the tannery's 15-day wait was written by the bench ("waits 15 days ...
    eats 14 pounds of food ..."), stayed queued, and came back on the next act, putting the
    armour on: "puts on the Crude Deer Leather Armour (1 minute). Through the wait Kesst
    Vayr eats 14 pounds of food ...", as though dressing took a fortnight of rations. The
    works queue had the same defect and the same cure (`alchemy_collect`, 2026-10-07)."""
    lines = wait_lines(passed, ref)
    mine = [r for r in (passed or {}).get("body") or () if str(r.get("ref")) == str(ref)]
    queue = getattr(scene, "_body_said", None)
    if mine and isinstance(queue, list):
        queue[:] = [r for r in queue if not any(r is m for m in mine)]
    return lines


def refused(actor, wanted: int, had: int) -> int:
    """Of the non-lethal a heal set out to take off, how much a need's hold refused.

    `wanted` is the cure's points, `had` the non-lethal before it. Whatever the cure did
    not take off, up to the non-lethal still carried, was stopped by the floor in
    `Actor.heal_nonlethal` — the only thing that stops a heal short of its amount while
    there is non-lethal left to take. 0 when nothing is withheld.
    """
    if not actor.withheld_nonlethal():
        return 0
    mended = max(0, int(had) - int(actor.nonlethal))
    return max(0, min(int(wanted) - mended, int(actor.nonlethal)))


def unmended_said(actor, *, magic: bool = False) -> str:
    """The sentence a refused heal owes the narrator (law 3): what is held, by which
    need, and the one thing that frees it. "Not even magic" only where it was magic —
    an hour's rest that does not touch thirst damage is not a spell failing."""
    held = actor.withheld_nonlethal()
    if not held:
        return ""
    name = getattr(actor, "name", "") or "They"
    needs = [n for n in WITHHELD_NEEDS if held.get(n)]
    what = " and ".join(needs)
    acts = " and ".join(WITHHELD_NEEDS[n][1] for n in needs)
    tail = "; not even magic heals it." if magic else "."
    return (f"{name}'s {what} damage ({sum(held.values())}) will not mend until they "
            f"{acts}{tail}")


def unmended(actor, wanted: int, had: int, *, magic: bool = True) -> str:
    """The refusal sentence when a heal of `wanted` met a need's hold, else ""."""
    return unmended_said(actor, magic=magic) if refused(actor, wanted, had) else ""


_NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten", "eleven", "twelve")


def _days(hours: int) -> str:
    """Whole days in words, for the narrator: "five days", "more than a day"."""
    days = int(hours) // HOURS_PER_DAY
    if days <= 1:
        return "more than a day"
    word = _NUMBER_WORDS[days] if days < len(_NUMBER_WORDS) else "many"
    return f"{word} days"


@dataclass(frozen=True)
class Strain:
    """One thing the body is carrying that the page should show (`strains`)."""
    key: str        # hunger | thirst | sleep | wounds | fatigue
    words: str      # the fact, in words for the brief — never a number the model could copy
    severe: bool = True


def strains(actor) -> list[Strain]:
    """What the player's body is carrying right now, worst first, in words.

    The owner, 2026-10-05: *"prose acts like im okay but im literally starving and days
    past the last rest. the prose should reflect this."* The panel said Life 18 of 73,
    starving, past a day awake; the brief said "18/73 hp" and nothing else — hunger,
    thirst and wakefulness reached the sidebar (`Actor._needs_summary`) and never the
    narrator. This is the one derivation both the brief (`gm.prompts.scene_now`) and the
    check that holds the page to it (`gm/checks/body_shown.py`) read, so the two cannot
    disagree, and it reads the same counters and graces the panel reads.

    Only what 1e itself treats as a cost: a need past its grace (the hour the checks
    start), a fatigue condition (asked as a tag, `has_state`), and wounds at half or
    worse. "Hungry since lunch" is not a fact the page owes the player. A body that is
    down is the fight's business, not this line's.
    """
    out: list[Strain] = []
    if actor is None or getattr(actor, "is_down", False):
        return out
    hp, top = int(getattr(actor, "hp", 0) or 0), int(getattr(actor, "hp_max", 0) or 0)
    left = hp - int(getattr(actor, "nonlethal", 0) or 0)
    if top > 0 and left * 4 <= top:
        out.append(Strain("wounds", "gravely hurt, with little strength left in them"))
    elif top > 0 and left * 2 <= top:
        out.append(Strain("wounds", "badly hurt"))
    fed = int(getattr(actor, "fed_minutes", 0) or 0) // MINUTES_PER_HOUR
    if not exempt(actor, NO_FOOD) and fed > hours_until_hungry(actor):
        out.append(Strain("hunger", f"starving — {_days(fed)} without food"))
    wet = int(getattr(actor, "watered_minutes", 0) or 0) // MINUTES_PER_HOUR
    if not exempt(actor, NO_WATER) and wet > hours_until_thirsty(actor):
        out.append(Strain("thirst", f"parched — {_days(wet)} without water"))
    awake = int(getattr(actor, "awake_minutes", 0) or 0) // MINUTES_PER_HOUR
    if not exempt(actor, NO_SLEEP) and awake > AWAKE_GRACE_HOURS:
        out.append(Strain("sleep", f"{_days(awake)} without sleep"))
    has = getattr(actor, "has_state", None)
    if callable(has) and has("state.impaired.exhausted"):
        out.append(Strain("fatigue", "exhausted — every movement is an effort"))
    elif callable(has) and has("state.impaired.fatigued"):
        out.append(Strain("fatigue", "fatigued — heavy-limbed and slow"))
    return out


def sleep(actor, hours: int = 8) -> None:
    """A night resets the awake clock. Called by `rest`, which already does the healing.

    The awake clock and its saves only. It reset the thirst and hunger counts too until
    2026-10-05, and the book does not: Starvation and Thirst (CRB p.444) gives the DC as
    "10, +1 for each previous check" and never says what clears the count — not food, not
    water, and nothing about sleep. Clearing it on a meal and a drink (`eat`, `drink`) is
    the reading that ties the count to the need it measures; clearing it on a night let a
    character three days without water sleep their way back to DC 10 every morning.
    """
    if int(hours) >= 6:
        actor.awake_minutes = 0
        actor.awake_checks = 0


def eat(actor) -> int:
    """A meal: the hunger clock and its count back to nothing, and whatever hunger held
    released to heal by the ordinary clock. Returns the points released."""
    actor.fed_minutes = 0
    actor.hunger_checks = 0
    return _met(actor, "hunger")


def drink(actor) -> int:
    """Water: as `eat`, for thirst."""
    actor.watered_minutes = 0
    actor.thirst_checks = 0
    return _met(actor, "thirst")


def _met(actor, need: str) -> int:
    """Release what `need` held, and lift the fatigue thirst and hunger leave once nothing
    holds any more (owner, 2026-10-05: "keep fatigue until you drink"; a night's sleep
    leaves it — `Actor.rest`). Fatigue from going without sleep is not this need's, and
    a fatigue thirst left stays while hunger still holds damage too."""
    released = actor.release_nonlethal(need)
    if not actor.withheld_nonlethal():
        # Asked of the tag (law 1), and lifted only where thirst or hunger laid it.
        from .states import matches

        actor.remove_effects(
            kind="condition",
            match=lambda e: e.source in ("thirst", "hunger")
            and any(matches(t, "state.impaired.fatigued") for t in e.tags))
    return released


def released_said(actor, need: str, points: int) -> str:
    """The tell for a need met over damage it held: it can mend now — not that it has."""
    if not points:
        return ""
    name = getattr(actor, "name", "") or "They"
    return f"The {need} damage on {name} ({points}) can mend now."


__all__ = ["AWAKE_GRACE_HOURS", "BIOME_HARDSHIP", "LIVED_MINUTES", "NO_FOOD", "NO_SLEEP",
           "NO_WATER", "SLEEP_SOURCE", "Strain", "Toll", "WITHHELD_NEEDS", "asleep",
           "awake_dc", "charge", "daily_need", "drink", "eat", "exempt", "hardship",
           "hours_until_hungry", "hours_until_thirsty", "hunger_dc", "lasts", "lived_said",
           "pass_hours", "refused", "released_said", "said", "sleep", "sleep_left", "state",
           "stopped_said", "strains", "thirst_dc", "unmended", "unmended_said"]
