"""Where somebody is when the party is not looking.

The user's ruling of 2026-09-25: the woman watching from a doorway "should stay there until
i leave or something moves them ... and once I leave that woman remains a resident of the
city/town/village unless she is a merchant or traveller" — "those people should persist
move around and their lives should evolve". Design record: docs/the-population.md §4 and
"Built: residency and movement".

Nothing here is simulated and nothing iterates the population on a clock. Where a person
is is a FUNCTION of their record and the time, asked when somebody needs the answer — the
party arriving somewhere, or the player asking after them:

  residents   a schedule key: Ultima VII's eight three-hour slots, each naming an activity
              (home, work, gather, temple, market), the activity resolved against the
              places this settlement actually has. Confirmed in the Exult source
              (actors.cc `find_schedule_at_time`); off-screen, Exult does not walk anybody
              to their slot, it teleports them there (`teleport_offscreen_to_schedule`) —
              which is what `Engine.settle_people` does when the party arrives.
  mobile      the world's real roads, walked by arithmetic from the last time they were
              seen: stay a seeded number of days, take a seeded road (a trader prefers the
              roads the world's trade runs along), arrive after the hours `journey` says
              that road costs, stay, go on. Kerbal Space Program's "on rails" is the
              precedent: position from elapsed time, never ticked. No RPG or MUD was found
              doing this for a traveller (Oblivion's low-process travel is a blogger's
              inference, not confirmed by any primary source, 2026-09-27).
  transient   gone on once the party leaves them: one road out, a day where it leads, and
              then out of these parts.

An observation beats the key (Stardew Valley's schedule keys are overridden by date,
weather and marriage; Shadows of Doubt abandoned PRECOMPUTED routines because reactions
broke them — so nothing here is precomputed but the traveller's roads, and those are
re-anchored every time the traveller is seen). Two observations count: the slot a person
was first seen in is that person's slot at the place they were seen, and while the party
stays in a place everybody in it stays too (the ruling above).

Refused, with reasons:
  * Radiant AI's goal-seeking NPCs (Oblivion): the designers' own words were that it
    "screws up our quests". Nobody here decides anything; a key and a road do.
  * Off-screen death: nobody dies of being away. Skyrim's `Protected` flag (only the
    player may kill them) is the precedent; the catch-up step that gives lives events
    will have to honour it.
  * Model-decided days (Generative Agents): drift and cost, measured by its own authors.

Seeds come from SHA-256 of a string and only `random.random()` is drawn: Python promises
that one method stable across versions and not `choice`/`randint`
(docs.python.org, "Notes on Reproducibility"). What was rolled for a traveller is
stored on the record, so a reload never re-walks a road.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

SLOT_MINUTES = 180
SLOTS = 8
DAY = 24 * 60

HOME, WORK, GATHER, TEMPLE, MARKET = "home", "work", "gather", "temple", "market"
SOCIAL = "social"  # gather if sociable, else home — decided per person, once

# A day in eight slots, starting at midnight: 0, 3, 6, 9, 12, 15, 18, 21. Written as
# "general routines for a class of NPCs where only the location varies" (the Ultima
# fan-dev advice the research turned up), and shaped by the historical town day: shops
# from about six, the curfew bell closing taverns and gates at eight or nine.
_H, _W, _G, _T, _M, _S = HOME, WORK, GATHER, TEMPLE, MARKET, SOCIAL
_DAY_WORK = (_H, _H, _W, _W, _W, _W, _S, _H)
TEMPLATES: dict[str, tuple[str, ...]] = {
    "default": _DAY_WORK,
    "sea": (_H, _W, _W, _W, _W, _H, _S, _H),          # the boats go out before dawn
    "service": _DAY_WORK,
    "faith": (_H, _H, _T, _T, _W, _W, _T, _H),        # the offices at dawn and dusk
    "rogue": (_W, _H, _H, _H, _M, _M, _G, _W),        # the crowd is where the work is
    "gentry": (_H, _H, _H, _M, _W, _W, _S, _H),
    "young": (_H, _H, _H, _W, _W, _W, _H, _H),        # out by day, in by dark
}
# Trades that keep other hours than their class.
_BY_WORK: dict[str, tuple[str, ...]] = {
    "innkeeper": (_W, _H, _H, _W, _W, _W, _W, _W),
    "barmaid": (_W, _H, _H, _H, _W, _W, _W, _W),
    "cook": (_H, _H, _W, _W, _W, _W, _W, _H),
    "lamplighter": (_H, _H, _W, _H, _H, _W, _W, _W),
    "beggar": (_H, _H, _W, _W, _W, _W, _W, _H),
}
# A watch has a night shift. Which one a guard keeps is rolled once, like anything else
# about them.
_WATCH_DAY = (_H, _H, _W, _W, _W, _W, _H, _H)
_WATCH_NIGHT = (_W, _W, _H, _H, _H, _H, _W, _W)
SOCIABLE = 60   # the sociability axis at which an evening is spent in company

# How long a traveller stops in a town, in days (low, high).
STAYS: dict[str, tuple[float, float]] = {
    "merchant": (2, 4), "peddler": (1, 3), "carter": (1, 2), "caravan-guard": (1, 3),
    "minstrel": (2, 6), "messenger": (0.25, 1), "sailor": (1, 4), "soldier": (3, 10),
    "pilgrim": (1, 1),
}
TRADES = frozenset({"merchant", "peddler", "carter", "caravan-guard"})
# Where in a town a traveller is found by day.
_TRAVELLER_PLACE = {
    "merchant": (MARKET, "gate"), "peddler": (MARKET, "gate"), "carter": ("gate", MARKET),
    "caravan-guard": ("gate", GATHER), "minstrel": (GATHER, MARKET),
    "messenger": ("gate", MARKET), "sailor": ("docks", "gate"), "soldier": ("gate", MARKET),
    "pilgrim": (TEMPLE, "gate"),
}
# How far a traveller's roads are walked ahead in one asking. A campaign of a year with a
# road every three days is ~120 stops; the cap is the paranoia NetHack's catch-up clamps
# with, not a limit anybody should meet.
MOST_STOPS = 400

# Places this settlement has, by what they are for. Matched on the place's own name,
# because a settlement's places are named by their kind ("the market", "the way in").
_KIND_WORDS = {
    GATHER: ("tavern", "inn", "alehouse", "taproom"),
    TEMPLE: ("shrine", "temple", "cathedral", "chapel"),
    MARKET: ("market", "merchants row"),
    "gate": ("way in", "gate"),
    "docks": ("docks", "quay", "wharf", "harbour"),
}

# Where somebody is when they are nowhere the party can walk into: at home, lodging, on a
# road between two towns, or gone out of these parts. Ids under the location they belong
# to, with a ground word no map is drawn for, so `places.location_of` still answers the
# town and no `travel` can ever reach them — `travel` only goes to a place `places()`
# lists. A person at home is found by asking, not by walking in.
OFFSTAGE = "offstage"


# The world in play, registered by the Engine that holds it (`use_world`). Asked for only
# when a caller has none to pass: half the finder's callers hold a scene and not a world,
# and without one a settlement loses the places its own words imply (Vormoor's guildhall)
# and a traveller can take no road — a different answer from the same record.
_WORLD = None


def use_world(world) -> None:
    global _WORLD
    _WORLD = world


def _world(world):
    return world if world is not None else _WORLD


def offstage(location_id: str, what: str) -> str:
    from .places import SEP

    return f"{location_id}{SEP}{OFFSTAGE}:{what}"


def is_offstage(place_id: str) -> bool:
    from . import places as places_mod

    return places_mod.terrain_of(place_id) == OFFSTAGE


def _rng(*parts) -> random.Random:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def slot_of(clock: int) -> int:
    return (int(clock) % DAY) // SLOT_MINUTES


# --- residents ---------------------------------------------------------------------------

def schedule_for(rec: dict) -> tuple[str, ...]:
    """Their eight slots: the class's routine, the trade's own hours over it, SOCIAL
    decided by their temper, and the slot they were first seen in overridden by the fact
    of having been seen then (they are out at that hour, where they were)."""
    life = rec.get("life") or {}
    work = str(life.get("work") or "")
    cls = _class_of(work)
    if work in _BY_WORK:
        slots = list(_BY_WORK[work])
    elif cls == "law":
        night = _rng(rec.get("id"), "watch").random() < 0.3
        slots = list(_WATCH_NIGHT if night else _WATCH_DAY)
    else:
        slots = list(TEMPLATES.get(cls, TEMPLATES["default"]))
    social = int((life.get("axes") or {}).get("sociability", 50))
    slots = [(GATHER if social >= SOCIABLE else HOME) if s == SOCIAL else s for s in slots]
    first = rec.get("first_seen")
    if first is not None and slots[slot_of(first)] == HOME:
        slots[slot_of(first)] = WORK
    return tuple(slots)


def _class_of(work: str) -> str:
    from . import lives

    for occ in lives.tables()["occupations"]:
        if occ["id"] == work:
            return occ["class"]
    return "default"


def mobility_of(rec: dict) -> str:
    return str((rec.get("life") or {}).get("mobility") or "resident")


_PLACES: dict = {}


def _places_of(location_id: str, world, founded) -> tuple:
    """A settlement's places, cached per call site's world and founded set: asked once
    per person otherwise, and a finder over a town's people would derive the town's
    layout hundreds of times over."""
    key = (location_id, id(world), tuple(str(p.get("id")) for p in founded or ()))
    if key not in _PLACES:
        if len(_PLACES) > 256:
            _PLACES.clear()
        _PLACES[key] = _derive_places(location_id, world, founded)
    return _PLACES[key]


def _derive_places(location_id: str, world, founded) -> tuple:
    from . import places as places_mod

    loc = None
    try:
        loc = world.get(location_id) if world is not None else None
    except Exception:
        loc = None
    try:
        return places_mod.for_scene(loc or location_id, "", founded=founded)
    except Exception:
        return ()


def _kind_place(places, kind: str):
    words = _KIND_WORDS.get(kind, ())
    for p in places:
        name = p.name.lower().removeprefix("the ")
        if any(name == w or name.endswith(" " + w) for w in words):
            return p
    return None


def _holds(ref: str, founded) -> str:
    """A place this person holds (`found` with them as owner): their house, their shop."""
    for p in founded or ():
        if ref and p.get("owner") == ref:
            return str(p.get("id") or "")
    return ""


def resolve(activity: str, rec: dict, location_id: str, world, founded) -> str:
    """The place id an activity means for this person in this settlement.

    WORK is where they were first seen: the stall, the doorway, the forge. The rest
    are the settlement's own places when it has them, and fall back — a town with no
    tavern sends its sociable home, a town with no shrine keeps its priest at work.
    """
    places = _places_of(location_id, _world(world), founded)
    spot = str(rec.get("spot") or "")
    from . import places as places_mod

    own_spot = spot if places_mod.location_of(spot) == location_id else ""
    home = _holds(str(rec.get("ref") or ""), founded) or offstage(location_id, f"home-{rec.get('id')}")
    if activity == HOME:
        return home
    if activity == WORK:
        # Somebody only heard of, with no place said (`population.note(spot="")`), is not
        # put at the settlement's first place by default — that was where the party stood
        # in the owner's save (2026-10-01), so the woman Gorm said lives "three streets
        # over" would have been reckoned into the tavern. Unseen and unplaced is at home.
        if not own_spot and rec.get("seen") is False:
            return home
        return own_spot or (places[0].id if places else home)
    p = _kind_place(places, activity)
    if p is not None:
        return p.id
    if activity == GATHER:
        return home
    return own_spot or (places[0].id if places else home)


# --- travellers ----------------------------------------------------------------------------

def _anchor(rec: dict) -> tuple[str, str, int]:
    """Where and when a traveller was last seen: the one fact their roads are walked
    from. Re-anchored every time they are seen (`observe`)."""
    a = rec.get("anchor") or {}
    return (str(a.get("loc") or rec.get("home") or ""),
            str(a.get("place") or rec.get("spot") or ""),
            int(a.get("t") if a.get("t") is not None else rec.get("last_seen") or 0))


def observe(rec: dict, location_id: str, place_id: str, clock: int) -> None:
    """The party has seen them, here, now. For a traveller that moves the anchor their
    roads are walked from and drops the roads walked from the old one."""
    rec["last_seen"] = int(clock)
    if mobility_of(rec) == "resident":
        return
    old = rec.get("anchor") or {}
    if (old.get("loc"), old.get("place"), old.get("t")) != (location_id, place_id, int(clock)):
        rec["anchor"] = {"loc": location_id, "place": place_id, "t": int(clock)}
        rec.pop("route", None)


# The world's roads do not change under a running game; asked once per town and world.
# Measured 2026-09-27: walking 2,500 travellers' roads thirty days on took 25 s when each
# asking derived its own roads, trade partners and hours.
_ROADS: dict = {}


def _memo(key, make):
    if key not in _ROADS:
        if len(_ROADS) > 4096:
            _ROADS.clear()
        _ROADS[key] = make()
    return _ROADS[key]


def _legs(world, loc: str):
    def make():
        from . import journey

        try:
            return journey.legs_from(world, loc) if world is not None else []
        except Exception:
            return []
    return _memo(("legs", id(world), loc), make)


def _hours(world, leg) -> int:
    def make():
        from . import journey

        try:
            return max(1, int(journey.hours_for(leg, 30)[0]))
        except Exception:
            return 24
    return _memo(("hours", id(world), leg.to_id, leg.miles, leg.by_sea), make)


def _trade_partners(world, loc: str) -> set[str]:
    return _memo(("trade", id(world), loc), lambda: _find_partners(world, loc))


def _find_partners(world, loc: str) -> set[str]:
    try:
        rows = world.routes_touching(loc) or []
    except Exception:
        return set()
    out = set()
    for r in rows:
        for a, b in (("origin_id", "destination_id"), ("destination_id", "origin_id")):
            if r.get(a) == loc and r.get(b):
                out.add(r[b])
    return out


def _next_leg(rec: dict, loc: str, came_from: str, n: int, world):
    work = str((rec.get("life") or {}).get("work") or "")
    legs = list(_legs(world, loc))
    if work == "sailor":
        legs = [lg for lg in legs if lg.by_sea]
    if not legs:
        return None
    partners = _trade_partners(world, loc) if work in TRADES else set()
    weights = []
    for lg in legs:
        w = 3.0 if lg.to_id in partners else 1.0
        if lg.to_id == came_from and len(legs) > 1:
            w *= 0.3
        weights.append(w)
    roll = _rng(rec.get("id"), "road", n, loc).random() * sum(weights)
    for lg, w in zip(legs, weights):
        roll -= w
        if roll <= 0:
            return lg
    return legs[-1]


def route(rec: dict, until: int, world) -> list[dict]:
    """The traveller's stops and roads from their anchor to `until`, walked and stored.

    Each entry is {"at": location, "from": minute, "to": minute} for a stay or
    {"road": [from, to], "from": minute, "to": minute} for the road between. Extended
    lazily and kept on the record — "store what was rolled" — so a later asking reads it
    and a reload never re-walks it.
    """
    loc, _place, t0 = _anchor(rec)
    kept = rec.get("route") or []
    work = str((rec.get("life") or {}).get("work") or "")
    lo, hi = STAYS.get(work, (1, 3))
    transient = mobility_of(rec) == "transient"
    if not kept:
        if transient:
            # Passing through: they go on when the party leaves them, which is the
            # anchor — the last time they were seen.
            kept = [{"at": loc, "from": t0, "to": t0}]
        else:
            # Met in the middle of a stay: some of it is already behind them.
            stay = lo + (hi - lo) * _rng(rec.get("id"), "stay", 0, t0).random()
            left = _rng(rec.get("id"), "left", t0).random()
            kept = [{"at": loc, "from": t0, "to": t0 + int(stay * left * DAY)}]
    while kept[-1]["to"] < until and len(kept) < MOST_STOPS:
        last = kept[-1]
        if "gone" in last:
            break
        if "road" in last:
            here = last["road"][1]
            n = len(kept)
            days = 1 if transient else lo + (hi - lo) * _rng(rec.get("id"), "stay", n, here).random()
            kept.append({"at": here, "from": last["to"], "to": last["to"] + int(days * DAY)})
            if transient:
                kept.append({"gone": True, "from": kept[-1]["to"], "to": 10 ** 12})
            continue
        here = last["at"]
        came = next((e["road"][0] for e in reversed(kept) if "road" in e), "")
        leg = _next_leg(rec, here, came, len(kept), world)
        if leg is None:
            # No road out that they would take: they stay, a day at a time.
            kept[-1] = {**last, "to": last["to"] + DAY}
            continue
        kept.append({"road": [here, leg.to_id], "from": last["to"],
                     "to": last["to"] + _hours(world, leg) * 60})
    # Walked without a world, nobody can take a road, so a traveller only seems to stay
    # put; that guess is answered and never stored, or it would outlive the asking.
    if world is not None:
        rec["route"] = kept
    return kept


# --- the answer --------------------------------------------------------------------------

@dataclass(frozen=True)
class Where:
    """Where somebody is now. `kind`: "place" (a place the party could walk into),
    "home" (in their settlement, indoors), "road" (between `location` and `bound`),
    "gone" (out of these parts)."""
    kind: str
    location: str = ""
    place: str = ""
    bound: str = ""
    since: int = 0


def whereabouts(rec: dict, clock: int, world=None, founded=None) -> Where:
    """Where the key or the road puts this person at `clock`. Knows nothing of bodies
    or of the party: `population.where_now` asks that first."""
    world = _world(world)
    mob = mobility_of(rec)
    if mob == "resident":
        loc = str(rec.get("home") or "")
        activity = schedule_for(rec)[slot_of(clock)]
        place = resolve(activity, rec, loc, world, founded)
        return Where("home" if is_offstage(place) else "place", loc, place)
    stops = route(rec, clock, world)
    now = next((e for e in stops if e["from"] <= clock < e["to"]), stops[-1])
    if "gone" in now:
        return Where("gone", since=now["from"])
    if "road" in now:
        return Where("road", now["road"][0], offstage(now["road"][0], f"road-{now['road'][1]}"),
                     bound=now["road"][1], since=now["from"])
    loc = now["at"]
    work = str((rec.get("life") or {}).get("work") or "")
    places = _places_of(loc, world, founded)
    if slot_of(clock) in (0, 1, 7):
        # Night: under a roof. The inn if the town has one, else lodgings nobody walks into.
        p = _kind_place(places, GATHER)
        place = p.id if p is not None else offstage(loc, f"lodging-{rec.get('id')}")
        return Where("home" if p is None else "place", loc, place, since=now["from"])
    anchor_loc, anchor_place, _t = _anchor(rec)
    if loc == anchor_loc and anchor_place and not is_offstage(anchor_place):
        return Where("place", loc, anchor_place, since=now["from"])
    for kind in _TRAVELLER_PLACE.get(work, (MARKET, "gate")):
        p = _kind_place(places, kind)
        if p is not None:
            return Where("place", loc, p.id, since=now["from"])
    return Where("place", loc, places[0].id if places else offstage(loc, "about"),
                 since=now["from"])


def where_of_place(at: str, since: int = 0) -> Where:
    """A body's place id, read back as a Where: an offstage id says what it is."""
    from . import places as places_mod

    loc = places_mod.location_of(at)
    if not is_offstage(at):
        return Where("place", loc, at)
    what = at.rsplit(":", 1)[-1]
    if what.startswith("road-"):
        return Where("road", loc, at, bound=what[len("road-"):], since=since)
    if what == "gone":
        return Where("gone", since=since)
    return Where("home", loc, at)


def place_for(where: Where, rec: dict) -> str:
    """The place id a body should stand at for this answer."""
    if where.kind == "gone":
        return offstage(str(rec.get("home") or ""), "gone")
    return where.place


def sentence(text: str) -> str:
    """Capitalised at the start and nowhere else: `who` arrives as running text ("the
    one selling bread") and may open the sentence or sit inside it."""
    text = str(text or "").strip()
    return text[:1].upper() + text[1:]


def _ago(minutes: int) -> str:
    minutes = max(0, int(minutes))
    if minutes < 90:
        return "within the hour"
    if minutes < DAY:
        return f"{round(minutes / 60)} hours ago"
    days = round(minutes / DAY)
    return "a day ago" if days <= 1 else f"{days} days ago"


def line(who: str, where: Where, *, here_loc: str, clock: int, world=None,
         day_place: str = "") -> str:
    """What asking around turns up, as a fact: where they are, never what they are.

    The hidden-facts ruling (2026-09-25): a rolled life may direct the player to
    somebody and must never be told. Where a person can be found is not their life —
    it is what any neighbour would say — so it is said, and nothing else is.
    """
    def name_of(loc_id: str) -> str:
        try:
            return str(getattr(world.get(loc_id), "name", "") or "") if world else ""
        except Exception:
            return ""

    if where.kind == "gone":
        return sentence(f"{who} has moved on, out of these parts.")
    if where.kind == "road":
        to, frm = name_of(where.bound), name_of(where.location)
        return sentence(f"{who} left {frm or 'here'} for {to or 'another town'} "
                        f"{_ago(clock - where.since)}, and is on the road.")
    town = name_of(where.location)
    if where.location and where.location != here_loc:
        return sentence(f"{who} is in {town or 'another town'} now, not here.")
    if where.kind == "home":
        by_day = f" By day they are at {day_place}." if day_place else ""
        return f"At this hour {who} would be indoors, at home.{by_day}"
    return ""


_PARTS = ("deep in the night", "the small hours", "early morning", "morning", "midday",
          "afternoon", "evening", "late evening")


def day_part(clock: int) -> str:
    """The part of the day in words — "early morning", "late evening" — and nothing else.

    The same eight parts `time_words` names, split out so the panel (`/api/state`'s
    `scene.day_part`, docs/fix-interfaces.md §2.9) and the brief cannot name the hour two
    ways. No count and no clock face: the page shows words where the narrator reads them.
    """
    return _PARTS[slot_of(int(clock or 0))]


def time_words(clock: int) -> str:
    """The hour as the narrator is told it: "day 2, evening (about 7 in the evening)".

    Until 2026-09-27 the brief never said what time it was, which was harmless while
    nothing read the hour. Now the hour decides who is where and which counters are open,
    and a narrator who has not been told writes the market bustling at a shut stall.
    """
    clock = int(clock or 0)
    hour = (clock % DAY) // 60
    twelve = hour % 12 or 12
    half = "in the morning" if hour < 12 else ("in the afternoon" if hour < 18
                                                else "at night" if hour >= 21
                                                else "in the evening")
    if hour == 12:
        about = "about noon"
    elif hour == 0:
        about = "about midnight"
    else:
        about = f"about {twelve} {half}"
    return f"day {clock // DAY + 1}, {_PARTS[slot_of(clock)]} ({about})"
