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
    # How the world says this route is travelled: `road`, `sea`, `river`, or "" where it
    # did not say. Shipped at schema 1.5 and it beats the inference above outright — the
    # rule this whole exchange keeps returning to is that a thing the world said beats a
    # thing this app worked out.
    #
    # Measured on arrival, and worth recording because it is the happy case: across both
    # worlds the stated `by` and the continent inference agreed on every single route,
    # 144 of 144, in both directions. The inference was right; it is still being replaced,
    # because being right by luck is not the same as being told.
    by: str = ""


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

        # A river is a keelboat's work — shallow draught, thirty feet, no pretensions —
        # and open sea is a trader's. The vessel table already knows the difference and
        # this is the first thing to ask it.
        vessel = "keelboat" if leg.by == "river" else "sailing ship"
        days = ships_mod.days_for(leg.miles if leg.source == "exact" else None,
                                  vessel, leg.days_apart)
        # The WHOLE day, not the eight hours a walking day is: a ship keeps watches and
        # makes way through the night, which is most of why the sea is faster than the
        # road at the same speed. The caller must not spend these as marching hours —
        # nobody aboard is marching — and `_op_journey` branches on the `sea` answer.
        return days * ships_mod.HOURS_AT_SEA, "", "sea"

    if leg.miles is not None and leg.source == "exact":
        # The AVERAGE of the ground, not the worst of it — changed 2026-09-16 when the
        # first export carrying `crosses` arrived and the table turned out not to
        # discriminate at all: 148 of Aurvantis's 152 road routes came out at exactly the
        # same multiplier, because `crosses` is a SAMPLE of the ground (one terrain for a
        # short haul, two for a long one) and the worst of any two samples from a
        # continent with mountains in it is always harsh.
        #
        # Worst-wins would be right if the field meant "the hardest stretch". It does not,
        # and taking it that way had a bad gradient: the more carefully a supplier
        # described their world, the slower every journey in it became. A route that
        # crosses desert and farmland is roughly half each, and the mean says so —
        # three bands across the same routes rather than one.
        #
        # The PHRASE still names the hardest ground, because that is what a traveller
        # remembers about a road, and the NUMBER averages.
        rates, words, worst = [], "", 1.0
        for ground in leg.crosses or ():
            got, said, _how = pace(ground, leg.road)
            rates.append(got)
            if got < worst:
                worst, words = got, said
        if not leg.crosses:
            _got, words, _how = pace("", leg.road)
        ground_rate = sum(rates) / len(rates) if rates else 1.0
        speed = max(0.1, (max(0, int(speed_ft)) / FEET_PER_MPH) * ground_rate)
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


def crosses_water(world, here: str, there: str, road: str = "", by: str = "") -> bool:
    """Whether getting from one to the other means going over water.

    The ruling of 2026-09-16: **continents are separated by water unless otherwise
    specified.** `by` is the specification — schema 1.5 states `road`, `sea` or `river`
    on every route — and a stated road is a way across whether that is an isthmus, a
    bridge or a causeway. The continent tree is the fallback for every export at 1.4 and
    below, which is every world written before this week.

    A river counts as water. It is not an ocean passage and it is not a road either: you
    are on a boat, and `hours_for` picks a shallow-draught one for it.
    """
    said = str(by or "").strip().lower()
    if said in ("sea", "river"):
        return True
    if said == "road" or str(road or "").strip():
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
        # `by: "road"` IS the road column (owner's ruling Q12, 2026-09-28). This read
        # `row["road"]` alone, which no export has ever shipped: 0 of Aurvantis's 132
        # travel rows carry it, while every one of them says `by: "road"`, so every road
        # in every world was priced as trackless ground — Vormoor to Dustgate (72 miles,
        # farmland then mountain) cost 38 hours where the road column gives 27. A stated
        # `road` grade (highway, trail) still wins over the plain road.
        by = str(row.get("by") or "").strip().lower()
        road = str(row.get("road") or "").strip().lower() or ("road" if by == "road" else "")
        out.append(Leg(
            to_id=other,
            to_name=str(getattr(found, "name", "") or row.get("to") or row.get("from")
                        or "somewhere"),
            miles=int(miles) if isinstance(miles, int) and miles > 0 else None,
            road=road,
            crosses=tuple(str(x) for x in (row.get("crosses") or ())),
            days_apart=_depth_apart(world, here, other),
            source="exact" if isinstance(miles, int) and miles > 0 else "derived",
            friction=str(row.get("friction") or ""),
            by=str(row.get("by") or ""),
            by_sea=crosses_water(world, here, other, str(row.get("road") or ""),
                                 str(row.get("by") or "")),
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
        # A river is not the sea, and a tell that calls it one is describing something
        # that did not happen — the one thing a tell may never do. You are on a boat
        # either way; what is out of the window is different.
        where = "on the river" if leg.by == "river" else "at sea"
        aboard = f"a day {where}" if days == 1 else f"{days} days {where}"
        if leg.from_port or leg.by == "river":
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
        # "1 days and a bit" until 2026-09-28, the first time a ridden road came to a day
        # and some hours.
        return f"{'a day' if days == 1 else f'{days} days'} and a bit on the road"
    return f"{days} days on the road"


# --- a horse changes it (the owner's ruling Q13, 2026-09-28) ----------------------------
#
# "travel between settlement[s] should take days without a horse, half the time with a
# horse and a third of the full time if you gallop on the horse the whole way [horse
# fatigue should kick in if the journey is too far]." The multipliers are the owner's and
# are used as ruled; what the book supplies is WHEN the gallop has to stop (AoN, Rules
# ID=50, Movement — fetched 2026-09-28):
#
#   Hustle            "A character can hustle for 1 hour without a problem. Hustling for
#                     a second hour in between sleep cycles deals 1 point of nonlethal
#                     damage, and each additional hour deals twice the damage taken
#                     during the previous hour of hustling."
#   Run (overland)    "Attempts to run and rest in cycles effectively work out to a
#                     hustle."
#   Mounted movement  "A mount bearing a rider can move at a hustle. The damage it takes
#                     when doing so, however, is lethal damage, not nonlethal damage."
#                     "Mounts also become fatigued when they take any damage from
#                     hustling or forced marches."
#   Fatigued          cannot run or charge (CRB, Conditions) — and an overland gallop is
#                     running in cycles, so a fatigued mount has stopped galloping. This
#                     last step is our reading, stated as ours.
#
# So a gallop is a hustle: the first hour of a day is free, the second costs the mount
# one point of lethal damage and leaves it fatigued, and a fatigued mount is ridden at a
# walk for the rest of that day. A night's camp is the sleep cycle that resets it. That
# is "fatigue kicks in when the journey is too far" by rule: a gallop of two hours or less
# is a third of the walking time; a longer one tires the horse and falls back to riding.
#
# Pathfinder Second Edition ABANDONED the doubling damage for a flat cap (Hustle: "for a
# number of minutes equal to your Constitution modifier × 10", 2e.aonprd.com Actions
# ID=515). Recorded, not adopted: this is a 1e table, and the 1e rule answers the question
# the owner asked (when does the horse tire) where the 2e cap only bounds it.
PACES: dict[str, int] = {"walk": 1, "ride": 2, "gallop": 3}
PACE_ALIASES = {
    "": "walk", "foot": "walk", "on foot": "walk", "walking": "walk",
    "riding": "ride", "mounted": "ride", "horse": "ride", "horseback": "ride",
    "on horseback": "ride", "trot": "ride",
    "galloping": "gallop", "hustle": "gallop", "hard": "gallop", "run": "gallop",
    "fast": "gallop", "at a gallop": "gallop",
}
# The creatures a party can ride, by bestiary template: Table 7-9's light and heavy horse
# and pony, the riding dog and the camel ("Mounts and Related Gear", Ultimate Equipment),
# as the bestiary spells them. How a party comes to HAVE one is not this module's — see
# docs/design-b-space.md §10: owned on the sheet, bought at the stables (light horse
# 75 gp, pony 30 gp), or hired.
#
# Donkey and mule since 2026-09-29 (G3): the stables sold them for 8 gp (content/rules/
# stall-lines.json) from blocks in content/bestiary/mounts.json, and they were missing
# here, so a bought mule never sped a journey. Ultimate Equipment: "Donkeys and mules
# have the same statistics as ponies" — so the pony's speed, 40 ft (Bestiary, Horse,
# pony variant). Sources as recorded in content/bestiary/mounts.json, read from
# legacy.aonprd.com/bestiary/horse.html and d20pfsrd (Herd Animal, Camel; Pony) on
# 2026-09-29; the page was not re-fetched for this row. Speeds in feet, the bestiary's:
# the owner's journey multipliers (Q13: half the time riding, a third galloping) are the
# rule for every mount alike and do NOT scale with these — the speeds are the record of
# what each animal is, for the day the owner rules otherwise.
MOUNT_SPEEDS: dict[str, int] = {
    "horse": 50, "light-horse": 50, "warhorse": 50, "heavy-horse": 50, "pony": 40,
    "riding-dog": 40, "dog-riding": 40, "camel": 50, "donkey": 40, "mule": 40,
}
MOUNTS = frozenset(MOUNT_SPEEDS)

# A mount's keep. The owner's price source (d20pfsrd "Animals & Animal Gear", Ultimate
# Equipment, recorded in docs/fix-interfaces.md §3.4): feed 5 cp a day, stabling 5 sp a
# day. Until 2026-09-29 nothing charged either — a bought horse ate for nothing for ever,
# which is why stall-lines.json declined to sell stabling at all. Charged by the engine
# (`Engine._keep_the_mounts`) through `goods.spend`: feed for every day on the road or
# rested, stabling for a night slept in a settlement that has stables. A purse that
# cannot pay is said, and the animal goes without — the book prices the keep and names
# no penalty for skipping it, so none is invented here.
FEED_CP_A_DAY = 5
STABLING_CP_A_NIGHT = 50


def owned_mounts(scene) -> list:
    """The mounts that are the party's: a creature of a `MOUNTS` template, travelling with
    them, not dead. Wherever they stand — a horse stabled in the next room is still fed."""
    from . import states

    out = []
    for a in (getattr(scene, "people", {}) or {}).values():
        if getattr(a, "is_pc", False):
            continue
        if str(getattr(a, "from_template", "") or "") not in MOUNTS:
            continue
        if not a.has_state(states.TRAVELS_WITH_YOU) or a.has_state("state.down.dead"):
            continue
        out.append(a)
    return out
HUSTLE_FREE_HOURS = 1          # "can hustle for 1 hour without a problem"
GALLOP_HOURS_A_DAY = 2         # the free hour, and the second that tires the mount
FATIGUE_ROUNDS = 8 * 60 * 10   # PF1e: fatigue lifts after 8 hours of complete rest
# The condition the book names for a mount hurt by hustling, as a row of this table — the
# engine applies what the rule says rather than naming it (tests/test_three_laws.py).
MOUNT_FATIGUE = "fatigued"


def pace_of(said) -> str:
    """"walk", "ride" or "gallop" from however the plan wrote it; "" when unreadable."""
    word = " ".join(str(said or "").lower().split())
    if word in PACES:
        return word
    return PACE_ALIASES.get(word, "")


def mounted_hours(walk_hours: int, pace: str) -> tuple[int, int]:
    """(hours on the road at this pace, days the gallop hurt the mount).

    `walk_hours` is what the route costs on foot (`hours_for`). Riding halves it and
    galloping thirds it, as ruled; a gallop is held to the hustle rule above, day by day
    of eight travelling hours. A day that does not finish the road is a full eight hours
    (the gallop and then the ride fill it), so these hours split into days exactly where
    `_op_journey`'s march splits them.
    """
    import math

    walk_hours = max(1, int(walk_hours))
    pace = pace if pace in PACES else "walk"
    if pace == "walk":
        return walk_hours, 0
    if pace == "ride":
        return max(1, math.ceil(walk_hours / PACES["ride"])), 0
    left = float(walk_hours)          # still to cover, in hours of walking
    spent = 0.0                       # hours actually on the road
    hurt = 0
    while left > 1e-9:
        today = 0.0
        for n in range(GALLOP_HOURS_A_DAY):
            if left <= 1e-9:
                break
            cover = min(float(PACES["gallop"]), left)
            spent += cover / PACES["gallop"]
            today += cover / PACES["gallop"]
            left -= cover
            if n + 1 > HUSTLE_FREE_HOURS:
                hurt += 1
        cover = min(left, max(0.0, HOURS_PER_DAY - today) * PACES["ride"])
        spent += cover / PACES["ride"]
        left -= cover
    return max(1, math.ceil(spent - 1e-9)), hurt
