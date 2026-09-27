"""Provocation: what an insult costs, and whether the insulted one swings.

Asked for 2026-09-25, after the provoke script insulted one man nine times and he never
struck — the prose held the tension and waited, and nothing in the world moved. The
user's ruling (option 1, "by temper"): an insult or provocation aimed at somebody lowers
their attitude; the worse it gets, the likelier they strike, and how fast depends on their
temper — a hot-tempered man swings after one or two insults, a placid one may never swing
and does something else instead.

The shape, from the research pass of the same day (citations in docs/provocation.md):

  * **Temper changes the chance of striking, not how far regard falls.** Every source
    keeps these apart: RimWorld gives every pawn the same −15 opinion for an insult and
    multiplies the fight CHANCE by trait (Bloodlust ×4); Dwarf Fortress's anger facet
    picks WHICH breakdown stress produces; Oblivion attacks when disposition falls more
    than 5 below the actor's aggression. So an insult costs everybody the same regard,
    and a seeded roll — the response, never the insult — decides the swing.
  * **An insult moves regard by less than a band.** RimWorld's −15 is 7.5% of its range;
    on regard's 0–100 with bands of about 20, an insult is 10 and a slight 4, each repeat
    in a day worth ×0.9 of the one before (RimWorld's own stacking factor).
  * **Temper as a multiplier from ×0 to ×4**: Dwarf Fortress's "never becomes angry" at
    the bottom, RimWorld's Bloodlust ×4 at the top.
  * **Watchmen present hold most tempers back** (Skyrim's Morality/Assistance values);
    only the hottest still swing with the watch looking on.
  * **A provoked blow is fists**, as a Skyrim brawl is: a drawn weapon is assault.
  * **Somebody who will not swing does something the engine holds**: they turn their
    back and leave the conversation. PF1e's Intimidate says a lapsed target "may report
    you to local authorities"; calling the watch waits on the watch system.

No number here reaches the narrator (the third law): the tells say what the person does.
"""
from __future__ import annotations

INSULT = 10
SLIGHT = 4
REPEAT = 0.9

# The chance of a swing at a temper multiplier of 1, by where the provocation left them.
# Tuned by simulation against the ruling (2026-09-25): at the first cut (0.45 / 0.20 /
# 0.06, a linear multiplier) an AVERAGE temper swung on the first insult in half of twenty
# seeded runs; the ruling gives one or two insults to the hot-tempered, not to everybody.
#
# Keyed off the one track (`states.ATTITUDES`, worst first), never spelled: no reader
# names an attitude (rules/attitude.py, COMES_ALONG).
from .states import ATTITUDES as _TRACK  # noqa: E402

STRIKE_BASE = {_TRACK[0]: 0.35, _TRACK[1]: 0.12, _TRACK[2]: 0.02}

# Below this temper nobody swings at all: Dwarf Fortress's "never becomes angry" band.
NEVER_BELOW = 15
TOP_MULTIPLIER = 4.0
# Watchmen present: most tempers hold back. Only past this temper does anybody still swing.
WATCH_HOLDS = 0.25
SWINGS_BEFORE_THE_WATCH = 85
# The kinds that are the watch, for the witness rule.
WATCH_KINDS = frozenset({"watchman", "guard", "soldier"})
# Below this chance a person who is hostile will not come to blows at all: they turn away.
WILL_NOT_FIGHT = 0.10


def temper_of(scene, actor) -> int:
    """Their rolled temper, 0 (placid) to 100 (volcanic); 50 for somebody with no life
    rolled (a world character, a creature spawned for a fight)."""
    from . import population

    rec = population.of_ref(scene, getattr(actor, "ref", ""))
    axes = ((rec or {}).get("life") or {}).get("axes") or {}
    try:
        return int(axes.get("temper", 50))
    except (TypeError, ValueError):
        return 50


def multiplier(temper: int) -> float:
    """×1 at an average temper (50), rising convexly to about ×3.7 at the top — near
    RimWorld's Bloodlust ×4 — and nothing below NEVER_BELOW."""
    if temper < NEVER_BELOW:
        return 0.0
    return min(TOP_MULTIPLIER, ((temper - NEVER_BELOW) / 35) ** 1.5)


def watch_looking_on(scene, actor) -> bool:
    for ref, other in (getattr(scene, "actors", {}) or {}).items():
        if other is actor or getattr(other, "is_pc", False) or other.is_down:
            continue
        kind = str(getattr(other, "from_template", "") or "").lower()
        words = set(str(getattr(other, "name", "") or "").lower().split())
        if kind in WATCH_KINDS or words & {"watchman", "guard", "guardsman", "watch"}:
            return True
    return False


def strike_chance(scene, actor, step: str) -> float:
    """The chance this provocation brings them to blows, 0 to 0.95."""
    temper = temper_of(scene, actor)
    chance = STRIKE_BASE.get(step, 0.0) * multiplier(temper)
    if chance and temper < SWINGS_BEFORE_THE_WATCH and watch_looking_on(scene, actor):
        chance *= WATCH_HOLDS
    return max(0.0, min(0.95, chance))


def cost(how: str, times_today: int) -> int:
    base = INSULT if how == "insult" else SLIGHT
    return max(1, round(base * (REPEAT ** max(0, int(times_today)))))


# --- what a hostile person who will not swing does instead ------------------------------
#
# Chosen by their rolled life, never rolled: the gregarious turn the room, the orderly go
# to the watch (PF1e's lapsed Intimidate: they "may report you to local authorities"),
# anyone else turns their back. A report writes the town's existing `state.suspected`
# through the one applicator (docs/wanted.md): prices up, a warning at the gate.

TURNS_THE_ROOM_FROM = 65     # sociability at or above: they make sure everybody hears
REPORTS_FROM = 60            # order at or above: they go to the watch


def axis_of(scene, actor, axis: str) -> int:
    from . import population

    rec = population.of_ref(scene, getattr(actor, "ref", ""))
    axes = ((rec or {}).get("life") or {}).get("axes") or {}
    try:
        return int(axes.get(axis, 50))
    except (TypeError, ValueError):
        return 50


# --- the grudge: regard lost to provocation, and how it comes back ------------------------
#
# Only what provocation took is held as a grudge (a failed Diplomacy's loss is the book's
# and stays). It comes back with time, slowly at first and faster the longer nothing new
# happens — Dwarf Fortress 0.40.17: "Made stress levels drop faster the longer no
# stressors are applied" — gone in GRUDGE_DAYS. A fresh provocation starts it over.

GRUDGE_DAYS = 3


def note_grudge(actor, lost: int, now: int) -> None:
    from . import attitude as attitude_mod

    eff = attitude_mod._regard_effect(actor)
    pay = dict(getattr(eff, "payload", None) or {}) if eff is not None else {}
    grudge = int(pay.get("grudge", 0)) + int(lost)
    attitude_mod.set_regard(actor, attitude_mod.regard_of(actor), "grudge",
                            payload={"grudge": grudge, "grudge_start": grudge,
                                     "grudge_at": int(now)})


def recover(actor, now: int) -> int:
    """Give back what time has earned of the grudge; returns the regard returned."""
    from . import attitude as attitude_mod

    eff = attitude_mod._regard_effect(actor)
    pay = dict(getattr(eff, "payload", None) or {}) if eff is not None else {}
    grudge, start = int(pay.get("grudge", 0)), int(pay.get("grudge_start", 0))
    if grudge <= 0 or start <= 0:
        return 0
    elapsed = max(0, int(now) - int(pay.get("grudge_at", now)))
    healed = min(1.0, (elapsed / (GRUDGE_DAYS * 24 * 60)) ** 2)
    remaining = round(start * (1 - healed))
    back = grudge - remaining
    if back <= 0:
        return 0
    before, after = attitude_mod.nudge_regard(actor, back, "time")
    attitude_mod.set_regard(actor, after, "time", payload={"grudge": remaining})
    return after - before


# --- after an outburst ----------------------------------------------------------------
#
# RimWorld settles a social fight with a coin: "cathartic" (+38 opinion) or "angering"
# (−22), and resets the break clock after any outburst (doubled in Beta 19). Dwarf
# Fortress's tantrum spiral is the failure it prevents: injury and punishment feeding
# fresh anger. Here: cathartic clears the grudge and warms them a step; embittered costs a
# step; either way they are COOLED for COOL_MINUTES — an insult still costs regard, but
# they will not rise to it again yet.

COOL_MINUTES = 8 * 60
AFTERMATH = 8


def cooled(actor, now: int) -> bool:
    from . import attitude as attitude_mod

    eff = attitude_mod._regard_effect(actor)
    pay = dict(getattr(eff, "payload", None) or {}) if eff is not None else {}
    return int(now) < int(pay.get("cooled_until", -1))


def mark_outburst(actor) -> None:
    from . import attitude as attitude_mod

    attitude_mod.set_regard(actor, attitude_mod.regard_of(actor), "outburst",
                            payload={"outburst": True})


def settle_outbursts(people, now: int) -> list[str]:
    """When a fight ends: each person who swung because they were provoked has their
    coin tossed (seeded on who and when, so a replay settles the same way) and is
    cooled. Returns (name, "cathartic"|"embittered") strings for the log."""
    import hashlib

    from . import attitude as attitude_mod

    out = []
    for actor in people:
        eff = attitude_mod._regard_effect(actor)
        pay = dict(getattr(eff, "payload", None) or {}) if eff is not None else {}
        if not pay.get("outburst"):
            continue
        coin = int(hashlib.sha256(f"{actor.ref}|{now}".encode()).hexdigest()[:2], 16) % 2
        before = attitude_mod.regard_of(actor)
        after = max(0, min(attitude_mod.REGARD_MAX,
                           before + (AFTERMATH if coin else -AFTERMATH)))
        attitude_mod.set_regard(actor, after, "outburst",
                                payload={"outburst": False,
                                         "cooled_until": int(now) + COOL_MINUTES,
                                         **({"grudge": 0, "grudge_start": 0} if coin else {})})
        out.append(f"{actor.name}: {'cathartic' if coin else 'embittered'}")
    return out
