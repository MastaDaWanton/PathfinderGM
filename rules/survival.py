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

    def __post_init__(self):
        if self.checks is None:
            self.checks = []
        if self.conditions is None:
            self.conditions = []

    @property
    def ok(self) -> bool:
        return not self.collapsed and not self.nonlethal

    @property
    def happened(self) -> bool:
        """Anything the player is owed a sentence about."""
        return bool(self.checks or self.fell_asleep or self.woke or self.knocked_out
                    or self.came_round)

    def absorb(self, other: "Toll") -> None:
        """Fold one hour's toll into the stretch's."""
        self.checks.extend(other.checks)
        self.nonlethal += other.nonlethal
        self.lethal += other.lethal
        self.conditions.extend(c for c in other.conditions if c not in self.conditions)
        for flag in ("collapsed", "fell_asleep", "woke", "knocked_out", "came_round"):
            if getattr(other, flag):
                setattr(self, flag, True)

    def as_dict(self) -> dict:
        return {"hours": self.hours, "checks": self.checks,
                "nonlethal": self.nonlethal, "conditions": self.conditions,
                "collapsed": self.collapsed, "fell_asleep": self.fell_asleep,
                "woke": self.woke, "knocked_out": self.knocked_out,
                "came_round": self.came_round, "lethal": self.lethal}


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


def _harm(actor, amount: int, toll: Toll) -> None:
    """1d6 of a need's non-lethal damage, landed as the book lands it.

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


def _wake(actor, toll: Toll) -> None:
    """Eight hours on: they wake, and it was a night's sleep (`Actor.rest`).

    The night's own door, so a collapse heals, clears and resets exactly what a night in
    a bed does — exhaustion to fatigue, the awake clock to nothing — and no second copy
    of what a night is can drift from it. What `Engine._op_rest` adds on top (spells
    prepared, pools refilled, the camp's cold) is a camp's, and a body that dropped in
    the street did not make one."""
    actor.remove_effects(match=lambda e: e is asleep(actor))
    actor.rest("night")
    toll.woke = True


def charge(actor, minutes: int, dice=None, biome: str = "", clock: int | None = None,
           roll: bool = True) -> Toll:
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
            _wake(actor, toll)
            woke = True

        watered = int(actor.watered_minutes)
        if (watered % MINUTES_PER_HOUR == 0 and not exempt(actor, NO_WATER)
                and watered // MINUTES_PER_HOUR > hours_until_thirsty(actor)):
            made = int(getattr(actor, "thirst_checks", 0))
            got = _check(actor, "Thirst", thirst_dc(made), dice)
            actor.thirst_checks = made + 1
            toll.checks.append(got)
            if not got["passed"]:
                _harm(actor, dice.roll(PARCHED_DAMAGE, label="thirst",
                                       visibility="player").total, toll)
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
                                       visibility="player").total, toll)
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
            healed = bool(actor.heal_nonlethal(level))

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


def said(actor, toll: Toll) -> list[str]:
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
    return out


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


def eat(actor) -> None:
    actor.fed_minutes = 0
    actor.hunger_checks = 0


def drink(actor) -> None:
    actor.watered_minutes = 0
    actor.thirst_checks = 0


__all__ = ["AWAKE_GRACE_HOURS", "BIOME_HARDSHIP", "NO_FOOD", "NO_SLEEP", "NO_WATER",
           "SLEEP_SOURCE", "Strain", "Toll", "asleep", "awake_dc", "charge", "drink",
           "eat", "exempt", "hardship", "hours_until_hungry", "hours_until_thirsty",
           "hunger_dc", "pass_hours", "said", "sleep", "sleep_left", "state", "strains",
           "thirst_dc"]
