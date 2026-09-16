"""How long it takes to get from one settlement to another.

The gap this closes is not subtle. `Scene.location_id` was assigned once, at campaign
creation, and **never reassigned anywhere in the engine** — so a world shipping twelve
settlements and five trade routes could be played in exactly one of them, for ever. Travel
meant changing the ground underfoot inside a town. There was nowhere else to go.

And travel cost nothing: `_op_travel` never touched the clock, while thirst, hunger and
sleep were metered in hours. The one time cost attached to movement anywhere in the app was
`places.VENTURES[kind]["hours"]`, a hand-authored constant with two values.

**The output of a journey is time, not distance.** Miles are an input; hours are what the
rest of the game already knows how to spend. `_op_venture` has had the shape for this since
it was written — `survival.pass_hours` to roll the body's checks, then `scene.advance` to
move the world's clock — and this is that, with the hours computed instead of typed.

THE RULES, and they are unchanged from 3.5 (the two tables are byte-for-byte identical):

  miles per hour  = speed in feet / 10, so a human's 30 ft is 3 mph and 24 miles a day
  a day           = 8 hours of walking; past that is a forced march
  terrain         Table: Terrain and Overland Movement, aonprd.com/Rules.aspx?ID=122

WHAT THE WORLD DOES NOT YET SAY. `docs/campaign-format.md` states it plainly — "No maps or
coordinates" — so a route today carries `carrying` and `friction`, both prose, and no
length at all. Two of the four inputs the rules want have no source: how long the road is,
and whether it is a road.

So the answer is three-way, exactly as `races.price_tag` answers a tag it has never seen:

  exact    the world said how many miles, and the rules did the arithmetic
  derived  it did not, and the time comes from how far apart the two sit in the world's
           own containment tree — reported in days on the road and NEVER in miles,
           because a mileage nobody stated is a number this app made up
  unknown  there is no route between them at all

`docs/distance-and-geography.md` §5 is the reasoning, and §7 the shape the export would
take. Nothing here requires that export to exist: a world that gains `miles` gets sharper
answers and a world without one still lets the party leave town.
"""
from __future__ import annotations

from dataclasses import dataclass

# 30 ft of speed is 3 miles an hour. The whole left column of Table: Movement and Distance
# is speed/10, which is why this is a ratio rather than a table.
FEET_PER_MPH = 10
HOURS_PER_DAY = 8

# Table: Terrain and Overland Movement — (highway, road or trail, trackless).
# Verified against aonprd.com/Rules.aspx?ID=122 and found identical to the 3.5 SRD's
# table in every cell, which is worth knowing: Pathfinder inherited overland travel
# unchanged rather than redesigning it.
TERRAIN_PACE: dict[str, tuple[float, float, float]] = {
    "desert": (1, 0.5, 0.5),
    "forest": (1, 1, 0.5),
    "hills": (1, 0.75, 0.5),
    "jungle": (1, 0.75, 0.25),
    "moor": (1, 1, 0.75),
    "mountain": (0.75, 0.75, 0.5),
    "plains": (1, 1, 0.75),
    "swamp": (1, 0.75, 0.5),
    "tundra": (1, 0.75, 0.75),
}

# This app's fourteen biomes against the table's nine rows. Nine map; five do not, and
# saying so is the point — `coast`, `urban`, `ruins`, `underground` and `planar` have no
# row, and the table's own `moor` has no biome. A silent default would make a swamp as
# quick as a plain and nobody would ever find out.
BIOME_ROW: dict[str, str] = {
    "grassland": "plains", "farmland": "plains",
    "desert": "desert", "forest": "forest", "hills": "hills", "jungle": "jungle",
    "mountain": "mountain", "swamp": "swamp", "tundra": "tundra",
}

ROADS = ("highway", "road", "trail", "none")
_COLUMN = {"highway": 0, "road": 1, "trail": 1, "none": 2, "": 2}


@dataclass(frozen=True)
class Leg:
    """One journey between two settlements, and how much of it the world actually said."""
    to_id: str
    to_name: str
    miles: int | None = None
    road: str = ""
    crosses: tuple[str, ...] = ()
    days_apart: int = 1
    source: str = "derived"          # exact | derived
    friction: str = ""
    # Whether this journey crosses water, and whether either end can put a ship to sea.
    #
    # "Continents should be separated by water unless otherwise specified" (2026-09-16),
    # and the export already carries what that needs: every settlement's line of ancestors
    # runs up through a CONTINENT, so two settlements on different ones are across water
    # from each other and nobody has to author a coastline to say so.
    #
    # Measured the day the rule was made, on the two shipped worlds: **48 of Aurvantis's
    # 48 travel legs cross a continent boundary**, and 2 of Pangrella's 5. Every one of
    # them was being walked. That is not a defect in the export — those routes are trade
    # relationships, which is what a trade route is — it is this app having read an
    # economic edge as a road.
    #
    # "Otherwise specified" is the `road` field the contract already has: a world that
    # states a road between two continents has said there is a way across, and a stated
    # road beats a derived sea.
    by_sea: bool = False
    from_port: bool = False
    to_port: bool = False


def pace(biome: str, road: str = "") -> tuple[float, str, str]:
    """The multiplier this ground puts on a day's travel, and how sure we are of it.

    Three-way like `races.price_tag`, and for the same reason: a terrain the table has no
    row for must not quietly travel at full speed. `unknown` returns 1.0 so the journey
    still happens — refusing to move the party because a coastline is not in a table from
    2009 would be the wrong failure — but it says so, and the caller can pass that on.
    """
    row = BIOME_ROW.get(str(biome or "").strip().lower())
    if row is None:
        return 1.0, f"{biome or 'this ground'} is not on the overland table", "unknown"
    column = _COLUMN.get(str(road or "").strip().lower(), 2)
    got = TERRAIN_PACE[row][column]
    words = f"{row}{' by ' + road if road else ', trackless'}"
    return got, words, "exact"


def miles_per_hour(speed_ft: int, biome: str = "", road: str = "") -> float:
    """A creature's overland speed on this ground, in miles an hour."""
    base = max(0, int(speed_ft)) / FEET_PER_MPH
    return base * pace(biome, road)[0]


def hours_for(leg: Leg, speed_ft: int = 30) -> tuple[int, str, str]:
    """How long this journey takes, what to say about it, and how sure we are.

    Returns whole hours, because the clock this feeds counts in minutes and a journey
    measured to the minute is a precision the inputs do not have.
    """
    # A crossing goes at the ship's speed and not the walker's, and it goes all day: a
    # ship has watches and does not camp at dusk. Which ship is the port's business
    # (`ships.offered_at`), so the leg asks for the commonest deep-water trader rather
    # than pretending to know — and says `sea` rather than `exact`, because the number is
    # as good as the miles were and no better.
    if leg.by_sea:
        from . import ships as ships_mod

        days = ships_mod.days_for(leg.miles if leg.source == "exact" else None,
                                  "sailing ship", leg.days_apart)
        # The WHOLE day, not the eight hours a walking day is: a ship keeps watches and
        # makes way through the night, which is most of why the sea is faster than the
        # road at the same speed. The caller must not spend these as marching hours —
        # nobody aboard is marching — and `_op_journey` branches on the `sea` answer.
        return days * ships_mod.HOURS_AT_SEA, "", "sea"

    if leg.miles is not None and leg.source == "exact":
        worst = 1.0
        words = ""
        for ground in leg.crosses or ():
            got, said, _how = pace(ground, leg.road)
            if got < worst:
                worst, words = got, said
        if not leg.crosses:
            _got, words, _how = pace("", leg.road)
        speed = max(0.1, (max(0, int(speed_ft)) / FEET_PER_MPH) * worst)
        hours = max(1, round(leg.miles / speed))
        return hours, f"{leg.miles} miles{', ' + words if words else ''}", "exact"

    # No mileage anywhere in the world file. The time comes from how far apart the two
    # sit in its containment tree, and is reported in days — never converted back into a
    # mileage, because that would be this app inventing a fact about somebody's world.
    return max(1, leg.days_apart) * HOURS_PER_DAY, "", "derived"


def continent_of(world, entity_id: str) -> str:
    """The continent a settlement stands on, by id, or "" when the world has no such tier.

    Walks the line of ancestors the export already carries. Nothing is derived from
    geometry — containment is not geography, which `_depth_apart` says at length — but
    "these two are on different landmasses" is a fact the tree states outright.
    """
    if world is None or not entity_id:
        return ""
    found = world.get(entity_id)
    if found is None:
        return ""
    line = [found] + list(world.ancestors(entity_id))
    for node in line:
        if str(getattr(node, "kind", "")).upper() == "CONTINENT":
            return str(node.id)
    return ""


def crosses_water(world, here: str, there: str, road: str = "") -> bool:
    """Whether getting from one to the other means going over water.

    The ruling of 2026-09-16: **continents are separated by water unless otherwise
    specified.** A stated road is the otherwise — a world that wrote one between two
    landmasses has said there is a way across, whether that is an isthmus, a bridge or a
    causeway, and a thing the world said beats a thing this app worked out.
    """
    if str(road or "").strip():
        return False
    mine, theirs = continent_of(world, here), continent_of(world, there)
    return bool(mine) and bool(theirs) and mine != theirs


def is_port(world, entity_id: str) -> bool:
    """Whether a settlement can put a ship to sea.

    A settlement is a port when it has somewhere for a ship to tie up — authored by the
    world or minted by this app's own cue table, which turns "a port town with a quay"
    into a docks. Not every place is on the coast, which is the other half of the ruling
    this file carries: an inland town is inland, and a crossing that starts there starts
    with a road.
    """
    from . import places as places_mod
    from . import ships as ships_mod

    found = world.get(entity_id) if world is not None else None
    if found is None:
        return False
    names = {str(p.name).strip().lower() for p in places_mod.home_set(found)}
    return bool(names & set(ships_mod.PORT_PLACES))


def _depth_apart(world, here: str, there: str) -> int:
    """Days on the road, derived from the world's own tree when it gives no distance.

    Containment is not geography — `world_map.py` says so in as many words, and a ring
    radius encodes depth rather than latitude — so this is emphatically not a distance. It
    is the one ordering a world does state: two towns in one nation are nearer each other
    than two towns on different continents, whatever the miles turn out to be.
    """
    def line(entity_id: str) -> list[str]:
        found = world.get(entity_id) if world is not None else None
        if found is None:
            return [entity_id]
        return [entity_id] + [a.id for a in world.ancestors(entity_id)]

    mine, theirs = line(here), line(there)
    shared = set(theirs)
    for step, node in enumerate(mine):
        if node in shared:
            # 0 would be the same settlement; 1 a shared parent — a day's walk.
            return max(1, step * 2 + 1)
    return 7


def legs_from(world, here: str) -> list[Leg]:
    """Every settlement reachable from this one, by the routes the world wrote down.

    Read off `play.travel`, which is the edge list a world states about itself and the
    only spatial claim it makes. A world that later ships `miles`, `road` and `crosses` on
    these entries sharpens every answer here without a line of this changing.
    """
    if world is None:
        return []
    out: list[Leg] = []
    seen: set[str] = set()
    for row in (getattr(world, "play", None) or {}).get("travel") or []:
        ends = (str(row.get("from_id") or ""), str(row.get("to_id") or ""))
        if here not in ends:
            continue
        other = ends[1] if ends[0] == here else ends[0]
        if not other or other in seen:
            continue
        seen.add(other)
        found = world.get(other)
        miles = row.get("miles")
        out.append(Leg(
            to_id=other,
            to_name=str(getattr(found, "name", "") or row.get("to") or row.get("from")
                        or "somewhere"),
            miles=int(miles) if isinstance(miles, int) and miles > 0 else None,
            road=str(row.get("road") or ""),
            crosses=tuple(str(x) for x in (row.get("crosses") or ())),
            days_apart=_depth_apart(world, here, other),
            source="exact" if isinstance(miles, int) and miles > 0 else "derived",
            friction=str(row.get("friction") or ""),
            by_sea=crosses_water(world, here, other, str(row.get("road") or "")),
            from_port=is_port(world, here),
            to_port=is_port(world, other),
        ))
    return sorted(out, key=lambda leg: leg.to_name.lower())


def find(legs: list[Leg], name: str) -> Leg | None:
    """A leg by the name of where it goes, however the GM wrote it."""
    want = " ".join(str(name or "").split()).strip().lower()
    if not want:
        return None
    for leg in legs:
        if leg.to_name.lower() == want or leg.to_id == name:
            return leg
    for leg in legs:
        if want in leg.to_name.lower():
            return leg
    return None


def describe(leg: Leg, hours: int) -> str:
    """What the narrator is told about the road, in a player's words.

    Days and half-days, never a mileage the world did not state, and never the hour count
    itself — the third law: the model is fed tells and no numbers it could contradict.
    """
    # A crossing is counted in whole days of the ship making way, and it is said
    # differently — "four days on the road" for a sea passage is the tell describing
    # something that did not happen, which is the one thing a tell may never do.
    if leg.by_sea:
        from . import ships as ships_mod

        days = max(1, round(max(1, hours) / ships_mod.HOURS_AT_SEA))
        aboard = "a day at sea" if days == 1 else f"{days} days at sea"
        if leg.from_port:
            return aboard
        # Not every place is on the coast. A crossing that starts inland starts on a
        # road, and the tell says so rather than teleporting the party onto a deck.
        return f"the road to the coast, and then {aboard}"

    days, left = divmod(max(1, hours), HOURS_PER_DAY)
    if not days:
        return "most of a day on the road" if left > 4 else "a few hours on the road"
    if days == 1 and not left:
        return "a day on the road"
    if left:
        return f"{days} days and a bit on the road"
    return f"{days} days on the road"
