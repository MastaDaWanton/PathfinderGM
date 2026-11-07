"""Real jobs: work the engine holds before anybody speaks of it.

The owner's report of 2026-10-27 (0.2.21, Planned): at the "hiring table" start the clerk's
opening line was "Hands wanted for the week, fed and paid at the end of it", and over five
replies the clerk made up an escort, a shipment, an outpost, papers and a caravan that
"moved toward the outskirts". Nothing in the engine stood behind any of it, so the player
then tracked a caravan that never was (docs/known-matters.md §1). The owner's answers of
the same day (§4.2, answered) are what this module builds, and each is named where it
lives:

  1. "I can fight" is offered EITHER a real escort, when one is going out, OR a week of
     guard work in town — the existing `work` op (`Engine._op_job`, `offer_for`).
  2. A caravan is SEVERAL REAL PEOPLE — a master, drivers, a guard — each with a sheet, a
     face and a people (`open_escort`, `_mint`), never one group actor.
  3. An opening MAY list real jobs: the hiring table's document names them
     (content/openings/core.json, `jobs`), and they are opened when the start is staged
     (`openings.stage`), so the clerk's answers come from the engine.
  4. A job not turned up for lapses, and the employer's regard drops a little
     (`settle`, `MISSED_REGARD`).
  5. Pay is the book's hireling wage for the work's danger, the engine's own number
     (`per_day_cp`); Diplomacy can raise it, up to three times what was offered
     (`haggled_times`), through the Make Request machinery (`Engine._haggle_job`).

**The traditions** (docs/known-matters.md §2, and the 2026-10-27 research pass):

  * Daggerfall's quest scripts declare their Person, Place, Item and Clock before the
    offer text; a job here is opened with its employer, its meeting place and time, its
    route and its people before the clerk says a word of it.
  * Battle Brothers' escort caravan is a real party, and its developers ABANDONED
    contracts that "artificially spawn things for you to fight" — so the road's own
    encounter roll (`rules/ontheway.py`) is the only trouble on the way; nothing is
    spawned for the job. They also abandoned haggling the sum ("ask for more money until
    the employer denies ... there's little thought behind it", dev blog 95) in favour of
    negotiating the terms. The owner chose the sum, by Diplomacy and bounded at three
    times; the book's own "+5 per additional request" and "a refused request does not
    change" (CRB p.93, `rules/requests.py`) are the employer's patience.
  * RimWorld keeps an accept-by and a complete-by timer; Daggerfall's escort employer,
    arrived at late, "leaves in a huff without paying" (UESP, Daggerfall: The Escort). The
    caravan here leaves at its hour (`GRACE_MINUTES` after it), without anybody who is
    not there.
  * Daggerfall's reputation runs -100..100, and a failed quest costs 2 (UESP, Daggerfall:
    Reputation); regard here runs 0..100, and a missed meeting costs what a Diplomacy
    failure by five costs (`attitude.REGARD_LOST_ON_FAILURE`, 5).

**The pay, from the books** (read 2026-10-27; legacy.aonprd.com and d20pfsrd.com):

  * Core Rulebook, Services: "Hireling, trained 3 sp per day", "Hireling, untrained 1 sp
    per day" — "a minimum wage"; the trained hireling includes "mercenary warriors ...
    teamsters". Ultimate Equipment has no separate guard or caravan-guard wage.
  * Pathfinder Player Companion: Cohorts & Companions, "Contingency Services": wages by
    the work's Risk — harmless 3 sp, questionable 6 sp, hazardous 1 gp, deadly 3 gp,
    suicidal 3 pp a day — "multiplied by the level of each hireling squared". Risk
    starts at 1; +1 for challenging terrain or hostile non-sentient inhabitants, +2 for
    harsh terrain or hostile sentient inhabitants above the hireling's level. The page
    number could not be confirmed.

  So a guard in town is harmless work (3 sp, the CRB's trained wage at level 1), and an
  escort on a road is questionable at least (+1: the road's beasts, which `ontheway`
  really rolls for), more over hard country. Carrying is untrained labour (1 sp); counting
  is a trained hireling's work (3 sp, a scribe's). The level-squared factor is applied to
  the dangerous work it was written for (guard and escort), never to the CRB's flat
  labouring wages.

**Not built (said, not hidden):** the caravan's own journey when the player is not with it
is not walked — its people are put at the far town when its hour passes; payment in
advance and per-head terms (Battle Brothers' and Cohorts & Companions' options) are not
offered: the terms are the opening's own, paid at the end; the caravan's people do not
fight beside the player unless the fight's own sides put them there.
"""
from __future__ import annotations

import math
import random
import re

# The work a job can be, a closed list (docs/known-matters.md §4.1).
WORK = ("labour", "carry", "count", "guard", "escort")
# What the hiring table asks — "Can you carry, count or fight?" — as the reader answers it
# (`gm/interpret.WORK_SAID`), and the work each is. "fight" is an escort when one is going
# out, else a week's guard work (the owner's answer 1).
SAID = ("carry", "count", "fight")
SAID_WORK = {"carry": "carry", "count": "count", "fight": "guard"}
# How the pay is made up. Only the opening's own ("paid at the end of it") is offered.
TERMS = ("on_completion",)
# The record's states, in the order a job moves through them.
#   open      held, the meeting not yet made;  met       the player reported at the hour;
#   paid      done and paid;  lapsed  taken and not turned up for (the owner's answer 4);
#   gone      the caravan left, never taken up;  declined  turned down.
STATES = ("open", "met", "paid", "lapsed", "gone", "declined")

# Cohorts & Companions, Contingency Services: the day's wage by the work's Risk, in copper.
RISK = ("harmless", "questionable", "hazardous", "deadly", "suicidal")
RISK_CP = {"harmless": 30, "questionable": 60, "hazardous": 100, "deadly": 300,
           "suicidal": 3000}
# The CRB's untrained hireling: "a crier, laborer, maid, mourner, porter".
UNTRAINED_CP = 10
TRAINED_CP = 30
# Ground the book's Risk calls challenging (+1) and harsh (+2). C&C does not list them; the
# split is ours, from the CRB's overland movement table's slowest columns (rules/journey.py
# `pace`): forest, hills, marsh, jungle and desert slow a march, mountain and the frozen
# north stop one.
CHALLENGING = frozenset({"forest", "hills", "swamp", "jungle", "desert"})
HARSH = frozenset({"mountain", "tundra", "underground"})

# "I should get paid up to 3x" (the owner, 2026-10-27).
HAGGLE_MOST = 3.0
# A day's guard work in town is a week of it: "Hands wanted for the week".
WEEK_DAYS = 7
# How long the wagons wait past their hour for a guard who has signed on. Ours: no source
# gives one; an hour is the turn a party takes to cross a town.
GRACE_MINUTES = 60
# What a missed meeting costs with the employer (the owner's answer 4: "drops a little").
MISSED_REGARD = 5
# When a caravan leaves: noon today while the morning is young enough to get there, else
# first light tomorrow.
_NOON = 12 * 60
_DAWN = 6 * 60
_DAY = 24 * 60
LATEST_FOR_NOON = 10 * 60


# --- the record --------------------------------------------------------------------------

def jobs(scene) -> list:
    from . import cards as cards_mod

    return [c for c in cards_mod.load(scene) if c.kind == "job"]


def live(scene) -> list:
    return [c for c in jobs(scene) if c.live]


def held_by(scene, ref: str) -> list:
    """The live jobs this person is the employer of."""
    return [c for c in live(scene) if c.giver == ref]


def holds_ref(scene, ref: str) -> bool:
    """Whether a live job holds this person — the caravan's people, kept in the world when
    the party leaves them standing (`Engine._stays_in_the_world`)."""
    return any(ref in (c.job.get("counterpart") or {}).get("people", ())
               for c in jobs(scene) if c.job.get("state") in ("open", "met"))


def mark(scene, card_id: str, state: str) -> None:
    """Write a job's state (`STATES`)."""
    from . import cards as cards_mod

    card = cards_mod.find(scene, card_id)
    if card is not None and card.kind == "job":
        card.job["state"] = state
        cards_mod._store(scene, card)


def close(engine, card_id: str, state: str, *, paid_cp: int = 0,
          days: int | None = None) -> None:
    """A job the player took comes to its end — `paid` or `lapsed` — and its card says so:
    the state, what was paid, the days worked, the minute it was settled, and what came of
    it as the card's newest fact (`outcome_line`).

    The owner's save of 2026-11-05: the week's guard work for Vyrnys was worked and paid
    (the purse held the 2 gold 1 silver), and the card's facts still said only the offer —
    "… all of it paid at the end of the week." Every reader of the card (the brief, the
    plan, the clerk's reply) read a job still to be worked, and the clerk then made up "the
    record for the northern gate is incomplete" when the player came to collect."""
    from . import cards as cards_mod

    card = cards_mod.find(engine.scene, card_id)
    if card is None or card.kind != "job":
        return
    card.job["state"] = state
    card.job["paid_cp"] = int(paid_cp or 0)
    if days is not None:
        card.job["days_worked"] = int(days)
    card.job["settled"] = int(getattr(engine.scene, "clock_minutes", 0) or 0)
    fact = outcome_line(engine, card)
    if fact and fact not in card.facts:
        card.facts = (list(card.facts) + [fact])[-cards_mod.FACT_CAP:]
    cards_mod._store(engine.scene, card)


def settled(card) -> bool:
    """Whether a job the player took has come to its end, paid or lapsed (`close`)."""
    return (card.job or {}).get("state") in ("paid", "lapsed")


def days_said(n: int) -> str:
    """"a day", "seven days": a number word, never a digit. A tell's "for 7 days" is taken
    off whole by the page line (`narration.page_line`, whose damage-amount rule lifts "for"
    and a number), so the week a job took never reached the planned narrator's tells check
    — "Kesst Vayr works as a guard in Pangrella (…)", on the owner's save of 2026-11-05."""
    from .geography import _count_words

    if int(n or 0) <= 0:
        return "less than a day"        # a body that gave out before the first day's end
    return _count_words(int(n), "day")


def outcome_line(engine, card) -> str:
    """What came of a job the player took, as one fact for its card, or "" while it is not
    settled. Said in the past, with the sum paid in this world's coin and the days in words
    (`days_said`): the card is read by the brief, the plan and the employer's reply, and a
    week said as "7 days" in a line that also offers the work reads as one still to come."""
    j = card.job or {}
    state = j.get("state")
    if state not in ("paid", "lapsed"):
        return ""
    scene = engine.scene
    pc = scene.pc()
    who = getattr(pc, "name", "") or "The player"
    paid = int(j.get("paid_cp", 0) or 0)
    coins = coin_words(engine, paid)
    if j.get("work") == "escort":
        to = (j.get("route") or {}).get("to_name", "the far town")
        master = _name(scene, (j.get("counterpart") or {}).get("master", ""),
                       "the caravan master")
        if state == "lapsed":
            return (f"{who} did not go with the wagons to {to}: the job was lost, and "
                    f"nothing was paid.")
        if not paid:
            return (f"{who} saw the wagons safe to {to}, and there was nobody to pay what "
                    f"was agreed.")
        short = paid < total_cp(card)
        return (f"{who} saw the wagons safe to {to}, and {master} paid {who} {coins} at "
                f"the end of the road" + (", short of what was agreed." if short else "."))
    employer = _name(scene, j.get("employer", ""), "the employer")
    if state == "paid":
        return (f"{who} worked the whole week for {employer} and was paid {coins} at the "
                f"end of it. The job is done and settled; nothing more is owed.")
    worked = int(j.get("days_worked", 0) or 0)
    if not worked:
        return f"{who} gave out on the first day of the week's work for {employer}, unpaid."
    return (f"{who} worked {days_said(worked)} of the week for {employer} before giving "
            f"out, was paid {coins} for them, and the rest of the week was let go.")


def _coins(engine):
    from . import goods

    return goods.coins_here(getattr(engine, "world", None), engine.scene)


def coin_words(engine, cp: int) -> str:
    from . import goods

    return goods.purse_line(goods.coins_for(max(0, int(cp))), _coins(engine))


# --- the pay -----------------------------------------------------------------------------

def risk_of(work: str, crosses=()) -> str:
    """The Risk of the work (Cohorts & Companions): a guard in town is harmless; an
    escort is questionable for the road's beasts, and harder over hard country."""
    if work != "escort":
        return "harmless"
    from . import biomes

    risk = 1 + 1                       # starts at 1; +1 hostile non-sentient inhabitants
    ground = {biomes.canonical(str(x)) for x in crosses or ()} - {None, ""}
    if ground & HARSH:
        risk += 2
    elif ground & CHALLENGING:
        risk += 1
    return RISK[min(len(RISK), risk) - 1]


def per_day_cp(work: str, level: int, risk: str = "harmless") -> int:
    """The day's wage in copper: the CRB's flat wage for labour, carrying and counting;
    Cohorts & Companions' risk wage times the hireling's level squared for guarding and
    escorting."""
    if work in ("labour", "carry"):
        return UNTRAINED_CP
    if work == "count":
        return TRAINED_CP
    return RISK_CP.get(risk, TRAINED_CP) * max(1, int(level or 1)) ** 2


def haggled_times(margin: int) -> float:
    """What a granted request for more pay multiplies the offer by: Influence Attitude's
    shape (one step, and one more per 5 the check beat the DC by), a half of the offer a
    step, never past three times it."""
    steps = 1 + max(0, int(margin)) // 5
    return min(HAGGLE_MOST, 1.0 + 0.5 * steps)


def pay_of(card) -> dict:
    return dict((card.job or {}).get("pay") or {})


def total_cp(card) -> int:
    p = pay_of(card)
    return int(p.get("per_day_cp", 0) or 0) * int(p.get("days", 0) or 0)


def _price(card, pc, risk: str, days: int) -> None:
    level = int(getattr(pc, "level", 1) or 1) if pc is not None else 1
    base = per_day_cp(card.job["work"], level, risk)
    card.job["pay"] = {"base_per_day_cp": base, "per_day_cp": base, "days": int(days),
                       "risk": risk, "times": 1.0, "level": level}


# --- where and when ------------------------------------------------------------------------

def meeting_minute(now: int) -> int:
    """Noon today while the morning is young, else first light tomorrow."""
    day = int(now) // _DAY
    if int(now) % _DAY <= LATEST_FOR_NOON:
        return day * _DAY + _NOON
    return (day + 1) * _DAY + _DAWN


def hour_words(minute: int) -> str:
    """"noon", "first light", "3 o'clock"."""
    of_day = int(minute) % _DAY
    return ("noon" if of_day == _NOON else "first light" if of_day == _DAWN else
            f"{of_day // 60 % 12 or 12} o'clock")


def when_words(minute: int, now: int) -> str:
    """"at noon today", "at first light tomorrow", "at noon on day 3"."""
    minute, now = int(minute), int(now)
    hour = hour_words(minute)
    days = minute // _DAY - now // _DAY
    day = {0: "today", 1: "tomorrow"}.get(days, f"on day {minute // _DAY + 1}")
    return f"at {hour} {day}"


def _land_legs(engine):
    from . import journey as journey_mod

    return [leg for leg in journey_mod.legs_from(engine.world, engine.scene.location_id)
            if not leg.by_sea]


def _road_head(engine, leg):
    from . import outskirts as outskirts_mod

    return outskirts_mod.road_for(engine.places(), leg.to_id)


# --- minting -----------------------------------------------------------------------------

def _mint(engine, label: str, words, place_id: str):
    """One of the caravan's people, through the arrival door, at the meeting place: a
    stat block for their work (`npcs.choose`), a true name and a face from the world's
    pools (`names.true_name`, `names.appearance_for`) and a people (`person_words.
    settle_people`) — the same steps every minted person takes. No population record:
    the caravan keeps to the wagons, not to a resident's day (`Engine._settle` moves only
    people with one)."""
    from . import names as names_mod
    from . import npcs
    from . import person_words
    from .bestiary import instantiate

    scene, world = engine.scene, engine.world
    pc = scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    words = [str(w) for w in (words or ())]
    got = npcs.choose(words, level) or {}
    template = str(got.get("id") or "guildhand")
    actor = instantiate(template, scene=scene, name=label)
    scene.arrive(actor, zone="near", place_id=place_id, source="job")
    if world is not None:
        taken = [getattr(a, "true_name", "") for a in scene.people.values()]
        taken += [a.name for a in scene.people.values()]
        actor.true_name = names_mod.true_name(world, scene.location_id, actor.ref,
                                              [t for t in taken if t])
        actor.appearance = names_mod.face_of(world, scene.location_id, actor)
        person_words.settle_people(scene, world, actor, words=label, template=template,
                                   place=place_id, take_grant=False, keep_name=True)
    return actor


def _group_label(to_name: str) -> str:
    return f"the caravan to {to_name}"


# --- opening jobs -------------------------------------------------------------------------

def open_escort(engine, spec: dict, employer: str, *, rng: random.Random,
                known: str = "heard", origin: str = "opening"):
    """A real escort: a land road out of this settlement, the road head toward it as the
    meeting place, an hour to leave at, and the caravan's people standing at the road
    head. None when this settlement has no road out by land (the clerk then has only the
    week's work)."""
    from . import cards as cards_mod
    from . import journey as journey_mod

    scene = engine.scene
    legs = _land_legs(engine)
    legs = [leg for leg in legs if _road_head(engine, leg) is not None]
    if not legs:
        return None
    leg = legs[rng.randrange(len(legs))]
    head = _road_head(engine, leg)
    pc = scene.pc()
    hours, _measured, _how = journey_mod.hours_for(leg, getattr(pc, "speed_feet", 30) or 30)
    days = max(1, math.ceil(int(hours) / journey_mod.HOURS_PER_DAY))
    meet = meeting_minute(scene.clock_minutes)
    from . import openings

    people, master, roles = [], "", {}
    for row in spec.get("caravan") or ():
        for _ in range(openings.count_of(row)):
            who = _mint(engine, str(row.get("label") or "a carter"), row.get("words"),
                        head.id)
            people.append(who.ref)
            roles[who.ref] = str(row.get("role") or "driver")
            if row.get("role") == "master" and not master:
                master = who.ref
    master = master or (people[0] if people else "")
    title = f"Guard the wagons to {leg.to_name}"
    objectives = [f"Meet the wagons at {head.name} at {hour_words(meet)}",
                  f"See the wagons safe to {leg.to_name}",
                  "Be paid at the end of the road"]
    card = cards_mod.Card(
        id=f"job-{len(jobs(scene)) + 1}-escort-{cards_mod._slug(leg.to_name)[:20]}",
        title=title, tags=(cards_mod.TAG_JOB, cards_mod.TAG_PLAY),
        people=[employer] + people, place="", origin=origin, always_on=True,
        kind="job", objectives=[{"text": o, "done": False} for o in objectives],
        clock_max=len(objectives), giver=employer, known=known)
    card.job = {
        "work": "escort", "employer": employer, "terms": "on_completion",
        "meets": {"at": head.id, "where": head.name, "minute": meet},
        "route": {"from": scene.location_id, "to": leg.to_id, "to_name": leg.to_name,
                  "hours": int(hours)},
        "counterpart": {"label": _group_label(leg.to_name), "people": people,
                        "master": master, "roles": roles},
        "state": "open",
    }
    _price(card, pc, risk_of("escort", leg.crosses), days)
    card.reward = _reward_words(engine, card)
    card.facts = [facts_line(engine, card)]
    return cards_mod.open_card(scene, card)


def open_week(engine, spec: dict, employer: str, *, known: str = "heard",
              origin: str = "opening"):
    """The week's work at the table: carry, count or guard, chosen by what the player says
    they can do (`choose_work`), and priced then."""
    from . import cards as cards_mod

    scene = engine.scene
    who = scene.people.get(employer)
    title = f"A week's work for {getattr(who, 'name', 'the guild') if who else 'the guild'}"
    choices = [w for w in (spec.get("choices") or ("carry", "count", "guard")) if w in WORK]
    card = cards_mod.Card(
        id=f"job-{len(jobs(scene)) + 1}-week", title=title,
        tags=(cards_mod.TAG_JOB, cards_mod.TAG_PLAY), people=[employer], origin=origin,
        always_on=True, kind="job",
        objectives=[{"text": "Work the week", "done": False},
                    {"text": "Be paid at the end of it", "done": False}],
        clock_max=2, giver=employer, known=known)
    card.job = {"work": "", "choices": choices, "employer": employer,
                "terms": "on_completion", "state": "open"}
    card.facts = [f"Hands wanted for the week, to {', '.join(choices)}, fed and paid at the "
                  f"end of it."]
    return cards_mod.open_card(scene, card)


def open_from_opening(engine, doc: dict, slots: dict, story_seed: int) -> list[str]:
    """The jobs a start document lists (`jobs`), opened as it is staged: the owner's answer
    3. Returns the card ids opened.

    Opened `heard`: the clerk's call ("Hands wanted for the week") reached the player, and
    no particular job has been put to them yet. They are put — `offered`, in the Journal,
    and what "I'll take it" agrees to — when the clerk answers what the player can do or
    asks (`Engine._op_job`). Opened `offered` at first, a bare "I'll take it" before the
    clerk had said a word of any caravan signed the player on to one."""
    from . import openings

    out: list[str] = []
    for i, spec in enumerate(doc.get("jobs") or ()):
        if not isinstance(spec, dict):
            continue
        employer = slots.get(str(spec.get("employer") or "$lead").lstrip("$"), "")
        if not employer:
            continue
        if spec.get("work") == "escort":
            card = open_escort(engine, spec, employer,
                               rng=openings.rng_for(story_seed, f"job:{i}"),
                               origin=f"start:{doc['id']}")
        else:
            card = open_week(engine, spec, employer, origin=f"start:{doc['id']}")
        if card is not None:
            out.append(card.id)
    return out


# --- what is said of a job -----------------------------------------------------------------

def _cap(name: str) -> str:
    """A name opening a sentence: "the caravan master" is "The caravan master" there."""
    return str(name)[:1].upper() + str(name)[1:]


def _name(scene, ref: str, default: str = "somebody") -> str:
    a = (getattr(scene, "people", {}) or {}).get(ref)
    return str(a.name) if a is not None else default


def _reward_words(engine, card) -> str:
    p = pay_of(card)
    if not p:
        return ""
    each = coin_words(engine, p["per_day_cp"])
    days = int(p["days"])
    return (f"{each} a day for {days} day{'s' if days != 1 else ''}, "
            f"{coin_words(engine, total_cp(card))} in all, paid at the end")


def facts_line(engine, card) -> str:
    """The job as the engine holds it, in a sentence: what the clerk may say of it, and
    nothing past it (the planned reply slot, `planned.build_plan`)."""
    scene = engine.scene
    j = card.job or {}
    now = int(scene.clock_minutes)
    if j.get("work") == "escort":
        cp = j.get("counterpart") or {}
        crew = [_name(scene, r) for r in cp.get("people", ()) if r != cp.get("master")]
        meets, route = j.get("meets") or {}, j.get("route") or {}
        days = int(pay_of(card).get("days", 1))
        line = (f"{_name(scene, cp.get('master', ''), 'a caravan master')} takes wagons to "
                f"{route.get('to_name', 'another town')}, leaving from {meets.get('where')} "
                f"{when_words(meets.get('minute', now), now)}, {days} "
                f"day{'s' if days != 1 else ''} on the road"
                + (f", with {', '.join(crew)}" if crew else "")
                + f"; a guard is wanted, at {_reward_words(engine, card)} by the caravan "
                  f"master")
        return line + "."
    if j.get("work"):
        # Measured live 2026-10-27: "A week's work to guard for the guild clerk: 3 silver a
        # day ..., 2 gold, 1 silver in all" came back as guarding the clerk, at 3 silver a
        # day PLUS 2 gold 1 silver at the end. Who is hired, what is guarded and that the
        # sum is the whole week's are each said once.
        p = pay_of(card)
        kind = {"guard": "guard work in town",
                "carry": "carrying work in town", "count": "counting and tallying work",
                "labour": "labouring work in town"}.get(j["work"], f"{j['work']} work")
        return (f"A week of {kind}, hired by {_name(scene, j.get('employer', ''))}: "
                f"{coin_words(engine, p.get('per_day_cp', 0))} a day for "
                f"{p.get('days', WEEK_DAYS)} days, which is "
                f"{coin_words(engine, total_cp(card))} for the whole week, all of it paid "
                f"at the end of the week.")
    return (f"Hands wanted for the week, to {', '.join(j.get('choices') or ())}, fed and "
            f"paid at the end of it; the pay is set by the work chosen.")


def slot_facts(engine, ref: str) -> str:
    """Every live job this person holds that the player may hear of, for the reply slot."""
    from . import cards as cards_mod

    rows = [facts_line(engine, c) for c in held_by(engine.scene, ref)
            if cards_mod.standing(c) != cards_mod.UNHEARD]
    # And the work they gave the player that is over, as it ended (`outcome_line`): who
    # hired the player knows whether the week was worked and paid. On the owner's save of
    # 2026-11-05 a finished job left the employer holding nothing, so "I am here to collect
    # my money" was answered with "the record for the northern gate is incomplete".
    rows += [outcome_line(engine, c) for c in jobs(engine.scene)
             if c.giver == ref and not c.live and settled(c)
             and cards_mod.standing(c) == cards_mod.OWN]
    # One job a line: the read-back numbers them (`beat_verify.invented_job_sentence`).
    return "\n".join(r for r in rows if r)


# --- offering, choosing, taking -----------------------------------------------------------

def escort_going_out(scene, employer: str):
    """The live escort this person holds whose caravan has not left: the owner's answer 1
    — "fight" is offered it when one is going out."""
    for c in held_by(scene, employer):
        if c.job.get("work") == "escort" and c.job.get("state") == "open" \
                and int((c.job.get("meets") or {}).get("minute", 0)) + GRACE_MINUTES \
                > int(scene.clock_minutes):
            return c
    return None


def week_of(scene, employer: str):
    return next((c for c in held_by(scene, employer) if c.job.get("work") != "escort"
                 and c.job.get("state") == "open"), None)


def choose_work(engine, card, work: str):
    """Set the week's work to what the player said they can do, and price it."""
    from . import cards as cards_mod

    card = cards_mod.find(engine.scene, card.id)
    if work not in WORK:
        return card
    if card.job.get("work") != work:
        card.job["work"] = work
        _price(card, engine.scene.pc(), risk_of(work), WEEK_DAYS)
        verb = {"carry": "carrying", "count": "counting", "guard": "guarding",
                "labour": "labouring"}.get(work, work)
        card.title = f"A week {verb} for {_name(engine.scene, card.giver, 'the guild')}"
        card.reward = _reward_words(engine, card)
        card.keys = cards_mod.keys_from(card.title)
    card.facts = [facts_line(engine, card)]
    cards_mod._store(engine.scene, card)
    return card


def offer_for(engine, employer: str, said: str):
    """The job this employer puts to a player who says they can `said` (carry, count or
    fight), or None when they hold nothing that fits."""
    scene = engine.scene
    if said == "fight":
        escort = escort_going_out(scene, employer)
        if escort is not None:
            return escort
    week = week_of(scene, employer)
    if week is None:
        return None
    work = SAID_WORK.get(said, "")
    if work not in (week.job.get("choices") or ()):
        return None
    return choose_work(engine, week, work)


def put_to_player(engine, card) -> None:
    """The job was put to the player this turn: offered, and the one an agreement means."""
    from . import cards as cards_mod

    card = cards_mod.find(engine.scene, card.id)
    if cards_mod.KNOWN.index(card.known or "unheard") < cards_mod.KNOWN.index("offered"):
        card.known = "offered"
    # An order, not a minute: two jobs put in one breath are still put one after the other.
    card.job["put_at"] = 1 + max([int(c.job.get("put_at", 0) or 0)
                                  for c in jobs(engine.scene)] + [0])
    card.facts = [facts_line(engine, card)]
    cards_mod._store(engine.scene, card)


def last_put(scene, employer: str = ""):
    """The live job most recently put to the player and not yet taken, by this employer
    when one is named: what "I'll do it" agrees to."""
    from . import cards as cards_mod

    rows = [c for c in live(scene) if cards_mod.standing(c) == cards_mod.OFFERED
            and (not employer or c.giver == employer) and c.job.get("work")]
    rows.sort(key=lambda c: int(c.job.get("put_at", -1)), reverse=True)
    return rows[0] if rows else None


def priced_offer(scene, employer: str):
    """The job whose pay a request for more is about: the last put to the player, priced."""
    card = last_put(scene, employer)
    return card if card is not None and pay_of(card) else None


def haggle(engine, card, margin: int) -> tuple[float, float]:
    """A granted request for more pay: (times before, times now). The offer only rises."""
    from . import cards as cards_mod

    card = cards_mod.find(engine.scene, card.id)
    p = pay_of(card)
    was = float(p.get("times", 1.0) or 1.0)
    now = max(was, haggled_times(margin))
    p["times"] = now
    p["per_day_cp"] = int(round(int(p["base_per_day_cp"]) * now))
    p["haggled"] = True
    card.job["pay"] = p
    card.reward = _reward_words(engine, card)
    card.facts = [facts_line(engine, card)]
    cards_mod._store(engine.scene, card)
    return was, now


def accept(engine, card):
    """The player takes the job on. The escort's pay goes with the wagons: the agreed sum
    is put in the caravan master's purse, the guild's money for its guard."""
    from . import cards as cards_mod
    from . import goods

    card = cards_mod.take_up(engine.scene, card.id)
    card = cards_mod.find(engine.scene, card.id)
    master = engine.scene.people.get((card.job.get("counterpart") or {}).get("master", ""))
    if card.job.get("work") == "escort" and master is not None \
            and not card.job.get("funded"):
        from .bestiary import collapse_kit

        collapse_kit(master)
        master.purse = goods.credit(master.purse, total_cp(card))
        card.job["funded"] = total_cp(card)
        cards_mod._store(engine.scene, card)
    return card


def decline(engine, card):
    from . import cards as cards_mod

    card = cards_mod.find(engine.scene, card.id)
    if card.job.get("work") == "escort":
        card.job["state"] = "declined"
        cards_mod._store(engine.scene, card)
        return cards_mod.resolve(engine.scene, card.id, how="dropped")
    # The week's posting stays on the table: turning down one kind of work is not turning
    # the table down.
    card.job["work"] = ""
    card.job.pop("pay", None)
    card.reward = ""
    card.facts = [facts_line(engine, card)]
    cards_mod._store(engine.scene, card)
    return card


# --- travelling with it --------------------------------------------------------------------

def set_out(engine, to_id: str) -> list[str]:
    """The player gives the word: the met caravan bound for `to_id` takes the road with
    them. Each of its people standing here travels with the party until the wagons are in
    (`bond.travels-with-you`, through the applicator, source `job:<id>`), and the job
    records the minute it set out, which ends the wait at the road head (`settle`).

    Why the bond and not a list of the job's own: a fight on the road is drawn by
    `Engine._ensure_encounter`, which brings everybody who travels with the player into
    the order on the player's side (`_companions_join`), and a companion's turn is its
    own, decided in character (`gm/companions.py`, the owner's ruling of 2026-10-01). The
    0.2.22 escort run met a reptoid six hours out and the caravan's four stood outside any
    fight that came of it. Granted only on the road, never at the meeting: with the bond
    the wagons would follow the player back across the market. Returns the refs bound."""
    from . import cards as cards_mod
    from . import states
    from .activeeffect import ActiveEffect

    scene = engine.scene
    here = getattr(scene, "actors", {}) or {}
    bound: list[str] = []
    for c in live(scene):
        j = c.job or {}
        if j.get("work") != "escort" or j.get("state") != "met" \
                or (j.get("route") or {}).get("to") != to_id:
            continue
        for r in (j.get("counterpart") or {}).get("people", ()):
            a = here.get(r)
            if a is None or a.is_down or a.has_state(states.TRAVELS_WITH_YOU):
                continue
            a.apply_effect(ActiveEffect(
                name=f"on the road with {(j.get('counterpart') or {}).get('label')}",
                kind="bond", key=f"job:{c.id}", source=f"job:{c.id}",
                origin=f"job:{c.id}", duration="until-dismissed",
                tags=(states.TRAVELS_WITH_YOU,)))
            bound.append(r)
        if not j.get("set_out"):
            j["set_out"] = int(scene.clock_minutes)
            cards_mod._store(scene, c)
    return bound


def _unbind(scene, card) -> None:
    """The road is over for the caravan's people: the bond `set_out` gave goes."""
    for r in ((card.job or {}).get("counterpart") or {}).get("people", ()):
        a = (getattr(scene, "people", {}) or {}).get(r)
        if a is not None:
            a.remove_effects(source=f"job:{card.id}")


def role_line(scene, ref: str) -> str:
    """What one of a job's caravan is to the player, for their own turn (`gm/companions.
    who_they_are`), or "" for anybody who is not. The role is the opening's own row
    (`counterpart.roles`: master, driver, guard). Whether a teamster stands or runs is
    theirs to decide on their turn, from this and their sheet; the engine refuses only a
    blow at the player's side (`companions.turning_on_the_party`)."""
    for c in jobs(scene):
        cp = (c.job or {}).get("counterpart") or {}
        if ref not in cp.get("people", ()) or c.job.get("state") != "met":
            continue
        a = (getattr(scene, "people", {}) or {}).get(ref)
        name = getattr(a, "name", "they")
        to = (c.job.get("route") or {}).get("to_name", "the far town")
        role = (cp.get("roles") or {}).get(ref) or (
            "master" if ref == cp.get("master") else
            "guard" if "guard" in str(getattr(a, "from_template", "")) else "driver")
        if role == "master":
            return (f"{name} is the caravan master, who hired the player to guard the "
                    f"wagons to {to} and pays at the end of the road; a trader, not a "
                    f"fighter, who looks to the wagons and their own skin first")
        if role == "guard":
            return (f"{name} is the caravan's hired sword, paid to fight for the wagons "
                    f"on the road to {to}, and fights for them")
        return (f"{name} drives one of the caravan's wagons to {to} for a wage: hired to "
                f"drive, not to fight — they defend themselves and the wagons as far as "
                f"their nerve and their arms allow, and may run from a fight they cannot "
                f"win")
    return ""


def coming_along(scene, to_id: str) -> list[str]:
    """The caravan's people standing with the party, on a job met and bound for `to_id`:
    who a journey there takes along (`Engine._op_journey`)."""
    out: list[str] = []
    here = getattr(scene, "actors", {}) or {}
    for c in live(scene):
        j = c.job or {}
        if j.get("work") != "escort" or j.get("state") != "met" \
                or (j.get("route") or {}).get("to") != to_id:
            continue
        out += [r for r in (j.get("counterpart") or {}).get("people", ())
                if r in here and not here[r].has_state("state.down.dead")]
    return out


def group_named(scene, phrase: str):
    """The caravan a phrase names, as {ref, name}: its master's ref (the one whose trail is
    the wagons') and the group's own label. Matched like the counter matches a want
    (`goods.match_want`): every content word of the phrase is a word of the group's label
    or its destination's name — the engine's own names, never a reading of the English."""
    words = [w for w in re.findall(r"[a-z']+", str(phrase or "").lower())
             if w not in ("the", "a", "an", "of", "to", "for", "our", "my", "that")]
    if not words:
        return None
    for c in jobs(scene):
        cp = (c.job or {}).get("counterpart") or {}
        if not cp.get("people"):
            continue
        label = str(cp.get("label") or "")
        own = set(re.findall(r"[a-z']+", label.lower())) | {"wagons", "wagon"}
        if all(w in own or w.rstrip("s") in own for w in words):
            master = cp.get("master") or cp["people"][0]
            return {"ref": master, "name": label}
    return None


def trails_of(scene) -> list[dict]:
    """The caravans that left this ground, for `tracking.trails`: one trail each, the
    wagons' (Large: a loaded wagon and its team), aged from the hour they left."""
    at = str(getattr(scene, "at", "") or "")
    now = int(getattr(scene, "clock_minutes", 0) or 0)
    out = []
    for c in jobs(scene):
        cp = (c.job or {}).get("counterpart") or {}
        left = cp.get("left") or {}
        if left.get("from") != at or not cp.get("people"):
            continue
        out.append({"ref": cp.get("master") or cp["people"][0], "name": cp.get("label"),
                    "hours_ago": max(0, (now - int(left.get("minute", now))) // 60),
                    "here": False, "size": "large"})
    return out


# --- the clock's part ---------------------------------------------------------------------

def _leave(engine, card) -> None:
    """The caravan goes without the player: its people to the far town's road back, and the
    road head remembers that they left (the trail `trails_of` reads)."""
    from . import outskirts as outskirts_mod

    scene = engine.scene
    j = card.job
    cp = j.get("counterpart") or {}
    route = j.get("route") or {}
    away = outskirts_mod.ring_id(route.get("to", ""), "grassland",
                                 outskirts_mod._road_slug(route.get("from", "")))
    for ref in cp.get("people", ()):
        a = scene.people.get(ref)
        # The player standing with them does not hold them: the caravan that waited its
        # hour for the word goes (the wait's end, `settle`).
        if a is not None and a.at == (j.get("meets") or {}).get("at"):
            scene.move(ref, away)
            if ref in scene.came_along:
                scene.came_along.remove(ref)
    cp["left"] = {"from": (j.get("meets") or {}).get("at"),
                  "minute": int((j.get("meets") or {}).get("minute", scene.clock_minutes))}
    j["counterpart"] = cp


def settle(engine) -> list:
    """What the clock and the party's place did to the jobs this batch: met, lapsed, or
    arrived and paid. Returns outcomes with their tells (law 3)."""
    from . import attitude as attitude_mod
    from . import cards as cards_mod
    from . import goods
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None or getattr(scene, "in_encounter", False):
        return []
    out: list = []
    now = int(scene.clock_minutes)
    for card in live(scene):
        # The card's first fact is the job as the engine holds it, said against today's
        # clock: "at noon today" written in the morning is "at noon on day 1" by evening.
        fresh = facts_line(engine, card)
        if not card.facts or card.facts[0] != fresh:
            card.facts = [fresh] + list(card.facts[1:])
            cards_mod._store(scene, card)
        j = card.job or {}
        if j.get("work") != "escort":
            continue
        meets, route = j.get("meets") or {}, j.get("route") or {}
        cp = j.get("counterpart") or {}
        master = scene.people.get(cp.get("master", ""))
        state = j.get("state")
        stands = cards_mod.standing(card)
        over = now > int(meets.get("minute", now)) + GRACE_MINUTES
        with_them = master is not None and master.at == scene.at
        if state == "open" and stands == cards_mod.OWN and scene.at == meets.get("at") \
                and not over:
            j["state"] = "met"
            cards_mod._store(scene, card)
            cards_mod.objective_done(scene, card.id, 0, turn=int(getattr(engine, "turn", 0)))
            crew = [scene.people[r].name for r in cp.get("people", ())
                    if r in scene.people and r != cp.get("master")]
            tell = (f"At {meets.get('where')}, {master.name if master else 'the caravan'} "
                    f"counts {pc.name} in as the caravan's guard"
                    + (f"; {', '.join(crew)} are with the wagons" if crew else "")
                    # Not "the wagons go when ...": measured live, the beat read it as
                    # the wagons already rolling ("begin their journey ... as you set
                    # out") on a turn the journey had not been taken.
                    + f". The wagons stand ready here, and wait for {pc.name} to give the "
                      f"word to set out for {route.get('to_name')}.")
            out.append(Outcome(intent_id="", op="job", tell=tell, because="the job",
                               effects=[{"kind": "job", "id": card.id, "state": "met",
                                         "origin": f"job:{card.id}"}]))
            continue
        # The wagons leave at their hour (the job's own terms, `meets.minute`), and wait
        # GRACE_MINUTES past it for the word — the same hour of grace a late guard is
        # given, so the terms have one number, not two. Until 2026-10-27 a caravan met and
        # never set out waited for ever, the player standing beside it: the 0.2.22 escort
        # run's leftover. Once the road is taken (`set_out`) nothing here applies.
        if state in ("open", "met") and over and not j.get("set_out"):
            waited = state == "met"
            _leave(engine, card)
            if stands == cards_mod.OWN:
                j["state"] = "lapsed"
                cards_mod._store(scene, card)
                cards_mod.resolve(scene, card.id, how="dropped")
                employer = scene.people.get(j.get("employer", ""))
                said = ""
                fx = {"kind": "job", "id": card.id, "state": "lapsed",
                      "origin": f"job:{card.id}"}
                if employer is not None:
                    before, after = attitude_mod.nudge_regard(employer, -MISSED_REGARD,
                                                              "job missed")
                    fx.update({"regard_from": before, "regard_to": after,
                               "employer": employer.ref})
                    said = attitude_mod.regard_said(employer.name, before, after)
                if waited:
                    tell = (f"The hour has come and gone at {meets.get('where')}, and "
                            f"{pc.name} has not given the word to set out: "
                            f"{master.name if master else 'the caravan master'} takes the "
                            f"wagons out on the road to {route.get('to_name')} without "
                            f"{pc.name}, and the job is lost. "
                            f"{_cap(employer.name) if employer else 'The employer'} will "
                            f"hear that {pc.name} did not go.")
                else:
                    tell = (f"The hour has come and gone at {meets.get('where')}: the "
                            f"wagons for {route.get('to_name')} have left without "
                            f"{pc.name}, and the job is lost. "
                            f"{_cap(employer.name) if employer else 'The employer'} will "
                            f"hear that {pc.name} did not come.")
                # Opens a sentence: "the guild clerk cools" was told lower-case, live.
                tell += f" {_cap(said)}" if said else ""
                # And the card says so: the same `close` as the week's work, so a lapsed
                # escort's card does not read as the offer it was.
                close(engine, card.id, "lapsed")
                out.append(Outcome(intent_id="", op="job", tell=tell, because="the job",
                                   effects=[fx]))
            else:
                # Never taken up: the wagons simply go, and nobody is owed anything.
                j["state"] = "gone"
                cards_mod._store(scene, card)
                cards_mod.resolve(scene, card.id, how="dropped")
            continue
        if state == "met" and scene.location_id == route.get("to") and with_them:
            j["state"] = "paid"
            _unbind(scene, card)
            turn = int(getattr(engine, "turn", 0))
            cards_mod._store(scene, card)
            cards_mod.objective_done(scene, card.id, 1, turn=turn)
            owed = total_cp(card)
            paid = min(owed, goods.in_copper(master.purse)) if master is not None else 0
            if paid > 0 and not master.has_state("state.down.dead"):
                master.purse, _ok = goods.spend(master.purse, paid)
                pc.purse = goods.credit(pc.purse, paid)
                engine._mark_payment(pc, master.ref, paid)
            else:
                paid = 0
            cards_mod.objective_done(scene, card.id, 2, turn=turn)
            close(engine, card.id, "paid", paid_cp=paid)
            p = pay_of(card)
            tell = (f"The wagons are in at {route.get('to_name')}. "
                    + (f"{_cap(master.name)} pays {pc.name} {coin_words(engine, paid)} for the "
                       f"road, as agreed: {coin_words(engine, p.get('per_day_cp', 0))} a "
                       f"day for {p.get('days')} day{'s' if p.get('days') != 1 else ''}."
                       if paid >= owed and paid else
                       f"{_cap(master.name)} pays {pc.name} {coin_words(engine, paid)}, all the "
                       f"coin there is, short of what was agreed." if paid else
                       "There is nobody to pay what was agreed."))
            out.append(Outcome(intent_id="", op="job", tell=tell, because="the job",
                               effects=[{"kind": "job", "id": card.id, "state": "paid",
                                         "paid_cp": paid, "origin": f"job:{card.id}"},
                                        {"ref": pc.ref, "kind": "give", "item": "coin",
                                         "count": paid, "how": "paid",
                                         "from": cp.get("master", ""), "to": pc.ref,
                                         "purse": dict(pc.purse)}]))
    return out
