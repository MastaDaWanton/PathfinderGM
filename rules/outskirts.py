"""The ground just outside a settlement: the middle scale between a room and a road of days.

Measured 2026-09-28 (docs/playtest-2026-09-28.md, items 16, 17 and 20): the app had two
scales of movement and nothing between them. `travel` among a town's fixed rooms, and
`journey` to another settlement at a cost of days. "I leave the village and stand outside
it" became a travel to the way in — INSIDE the village — and was stopped by the watch;
"I walk to the nearest crossroads" and "I take the path away from town" were both refused
(`found kind=crossroads`, `found kind=road`: "no such kind of place") and both narrated as
movement, so the page stood the player on the outskirts while the engine held them at the
way in. Every later turn resolved from where the engine was.

**What the traditions did** (docs/design-b-space.md §2–3, with sources). Ultima I–V cut
from the overworld straight into a town at another scale; Ultima VI abandoned the cut.
Mount & Blade leaves a town straight onto the world map and has no middle scale at all.
Inform's Recipe Book (§3.4) models the outdoors as a handful of rooms with the land around
them as a backdrop — described, never entered — and that is the shape here: a closed ring
of at most six named places, each drawn from what the world wrote, and the land beyond
them in words (`gm/brief/land_around.py`). Daggerfall's generated wilderness is remembered
as empty, and Morrowind turned away from generating one; so the ring is small and closed,
never a map.

**The ring**, built from `geography.roads_out` and `geography.land_around`:

  the outskirts        always, for a settlement: where the last houses give out
  the road to {To}     one per overland route the world wrote; its ground is what the
                       route crosses first ("the way to {To}" when the export never said
                       it was a road — a road nobody wrote down is not invented)
  the crossroads       the owner's ruling of 2026-09-28 (Q11): "crossroads are place[s]
                       not in a town where all the roads leave to different places" — out
                       past the outskirts, on the road network, where two or more roads to
                       different destinations part; never a room of the settlement and
                       never beside the fields. Journeys along those roads pass through it
                       (`_op_journey` says so). One per fork: a sixth road hangs off a
                       second fork, so nothing offers more than six ways on
  the fields           when the land close by is farmland
  the shore            when the settlement is a port or its own words put it on water
  the tannery          when the settlement's own words name its tanners and its own
                       places hold no tannery (`places.tannery_implied`, leatherworking
                       plan §10): the trade kept outside the walls, kept by a tanner
  the reaches          the hinterland (`geography.Reach`, 2026-10-05): up to four named
                       stretches of open ground a short walk out ("the ridgelines", "the
                       badlands"), each on its own ground, at its own miles, off the
                       fields (or the outskirts where there are none)

Ids are `{loc}~{ground}:@{slug}` (`places.RING`), derived and never stored — the same bargain
every generated place keeps. The ground in the head is a biome word the world gave, so
`terrain_of`, `scene.biome` and the floor plans read them exactly as they read any place.

**Time.** A hop costs minutes by the rules' own local movement (PF1e Table 7-6: 300 feet
a minute at speed 30, "for characters exploring an area" — AoN Rules ID=50); the bands are
the owner's accepted answer to Q10 (village 2, town 4, city 8 minutes a hop; half a mile
a ring hop). Open ground is the overland rate (3 miles an hour at speed 30), and ground
BEYOND the near land is as far as the world's own routes put it, at the same pace rule a
journey pays (Q13) — never a flat band.
"""
from __future__ import annotations

from . import places as places_mod

# --- the ring's own words -----------------------------------------------------------------

OUTSKIRTS = "the outskirts"
CROSSROADS = ("the crossroads", "the far crossroads")
FIELDS = "the fields"
SHORE = "the shore"

# A crossroads with its way back to the outskirts may offer five roads and stay at six
# ways on (Fate's two-to-four zones, Inform's "small number of named positions"). Past
# that, the rest of the roads part again further out. Measured: 2 of Aurvantis's 76
# settlements have six road legs.
ROADS_PER_FORK = 5

# The time bands (docs/fix-interfaces.md §4, Q10, accepted 2026-09-28), at speed 30.
# A village of five hundred is about six hundred feet across and a hop is most of it; a
# town of seven thousand is about 2,240 feet across in two hops; a city of a hundred
# thousand is 8,470 feet across in three or four (Medieval Demographics Made Easy's
# density, used only for the order of magnitude of a walk).
HOP_MINUTES = {"village": 2, "town": 4, "city": 8}
RING_HOP_FEET = 2_640          # half a mile, from one outside place to the next (Q10)
OPEN_GROUND_MILES = 3          # the reaches of open ground: an hour at a walk, as it was
BEYOND_FALLBACK_MILES = 12     # ground the world names only in prose: half a walking day

# PF1e local movement: "Characters exploring an area use local movement, measured in feet
# per minute" — a speed of 30 is 300 feet a minute (AoN Rules ID=50, Table 7-6).
FEET_PER_MINUTE_PER_SPEED = 10


def ring_id(location_id: str, ground: str, slug: str) -> str:
    return f"{places_mod.region_key(location_id, ground)}:{places_mod.RING}{slug}"


def _road_slug(to_id: str) -> str:
    """`the-road-to-{to_id}`: the World Bible id, never the name — a rename rewrites names."""
    return "the-road-to-" + (places_mod._slug(str(to_id).replace("-", " ").replace("_", " "))
                             or "somewhere")


def along_slug(to_id: str) -> str:
    return "along-" + _road_slug(to_id)


def is_along(place_id: str) -> bool:
    """Whether this is the stretch of road a stopped journey left the party on."""
    path = places_mod._spot_path(place_id)
    return bool(path) and path[0].startswith(places_mod.RING + "along-the-road-to-")


def road_head_of(place_id: str) -> str:
    """The `to_id` slug a road head or a stretch of road is for, or ""."""
    path = places_mod._spot_path(place_id)
    if not path:
        return ""
    root = path[0].removeprefix(places_mod.RING).removeprefix("along-")
    return root.removeprefix("the-road-to-") if root.startswith("the-road-to-") else ""


def _joined_to(home: tuple) -> "places_mod.Place | None":
    """The town room the outskirts is reached from: the gate or the way in first, then any
    other way in that is not the water (the docks and a bridge lead to the water, not the
    fields), then the first place. A city's crossings are junctions inside it, not exits."""
    by_name = {" ".join(str(p.name or "").split()).lower(): p for p in home}
    for want in ("the gate", "the way in"):
        if want in by_name:
            return by_name[want]
    inner = {"the docks", "the bridge", "the north crossing", "the east crossing",
             "the south crossing", "the west crossing"}
    for label in places_mod.ENTRANCES:
        if label in by_name and label not in inner:
            return by_name[label]
    for want in ("the bridge", "the docks"):
        if want in by_name:
            return by_name[want]
    return home[0] if home else None


def _ground_of(land) -> str:
    """The outskirts' own ground: the first near ground that is land, else the coast, else
    the generic open ground `region_set` stands on when the world said nothing."""
    # Not the land it sits in: the region's ground is a reach further out, and the
    # outskirts kept the ground the roads start on before reaches existed, so a save
    # standing at `…~grassland:@the-outskirts` still stands somewhere that exists.
    region = {r.ground for r in getattr(land, "reaches", ()) if r.source != "near"}
    near = [g for g in land.near if g not in ("coast", "water") and g not in region]
    if near:
        return near[0]
    if land.coast or "coast" in land.near:
        return "coast"
    return "grassland"


def ring(world, location, at: str = "") -> tuple:
    """The outside places of one settlement, wired to each other and to its way in.

    () for somewhere that is not a settlement (a wild site has no outskirts: it IS the
    outside), and for an engine with no world, which has no roads and no land to read —
    the world-less engine keeps the two scales it always had.

    `at` adds the stretch of road a stopped journey left the party on
    (`@along-the-road-to-{to_id}`), which joins the ring only while they stand on it, as a
    region of open ground joins the set only while they are in it.
    """
    if world is None or location is None or isinstance(location, str):
        return ()
    # Seven and a half milliseconds a build, measured on Vormoor (the roads read every
    # neighbour's places to ask whether it is a port), and `Engine.places()` is asked many
    # times a turn. Pure in (world, settlement, the stretch of road stood on), so it is
    # remembered per world OBJECT — held and compared by identity, never by `id()` alone,
    # which a collected world's successor could reuse.
    key = (id(world), str(getattr(location, "id", "") or ""),
           at if is_along(at) else "")
    held = _MEMO.get(key)
    if held is not None and held[0] is world and held[1] is location:
        return held[2]
    made = _ring(world, location, at if is_along(at) else "")
    if len(_MEMO) > 256:
        _MEMO.clear()
    _MEMO[key] = (world, location, made)
    return made


_MEMO: dict = {}


def _ring(world, location, at: str) -> tuple:
    from . import geography

    if not places_mod._settled(location, ""):
        return ()
    sid = str(getattr(location, "id", "") or "")
    here_name = str(getattr(location, "name", "") or "here")
    home = places_mod.home_set(location)
    if not sid or not home or home[0].id == "here":
        return ()
    land = geography.land_around(world, location)
    roads = geography.roads_out(world, location)
    ground = _canon(_ground_of(land)) or "grassland"
    gate = _joined_to(home)

    made: dict[str, dict] = {}

    def add(pid: str, name: str, about: str, terrain: str, exits=(), miles=0.0) -> str:
        made[pid] = {"name": name, "about": about, "terrain": terrain,
                     "exits": list(exits), "miles": float(miles)}
        return pid

    def link(a: str, b: str) -> None:
        if b not in made[a]["exits"]:
            made[a]["exits"].append(b)
        if b in made and a not in made[b]["exits"]:
            made[b]["exits"].append(a)

    out_id = add(ring_id(sid, ground, "the-outskirts"), OUTSKIRTS,
                 "where the last houses give out and the land begins", ground,
                 (gate.id,) if gate is not None else ())

    # The roads out that are walked. Sea and river legs are boarded, not walked out to:
    # they leave from the docks, or the shore, or (inland) by the road to the coast, which
    # `journey.describe` already says.
    walked = [r for r in roads if r.how in ("road", "")]
    heads: list[str] = []
    seen_to: set[str] = set()
    for r in walked:
        if r.to_id in seen_to:
            continue
        seen_to.add(r.to_id)
        head_ground = (_canon(r.crosses[0]) if r.crosses else "") or ground
        if head_ground == places_mod.URBAN:
            head_ground = ground
        way = "the road" if r.how == "road" else "the way"
        heads.append(add(ring_id(sid, head_ground, _road_slug(r.to_id)),
                         f"{way} to {r.to_name}",
                         f"where {way} to {r.to_name} leaves {here_name}", head_ground))

    # One crossroads per fork where two or more roads lead to different places (Q11).
    if len(heads) >= 2:
        first = heads[:ROADS_PER_FORK] if len(heads) <= ROADS_PER_FORK else \
            heads[:ROADS_PER_FORK - 1]
        rest = heads[len(first):]
        fork = add(ring_id(sid, ground, "the-crossroads"), CROSSROADS[0],
                   f"out past {here_name}, where the roads part", ground)
        link(out_id, fork)
        for h in first:
            link(fork, h)
        if rest:
            far = add(ring_id(sid, ground, "the-far-crossroads"), CROSSROADS[1],
                      "further out, where the road forks again", ground)
            link(fork, far)
            for h in rest:
                link(far, h)
    elif heads:
        link(out_id, heads[0])

    fields_id = ""
    if "farmland" in land.near:
        fields_id = add(ring_id(sid, "farmland", "the-fields"), FIELDS,
                        f"what {here_name} grows, and whoever is working it", "farmland")
        link(out_id, fields_id)
    if land.coast or land.water or "coast" in land.near:
        link(out_id, add(ring_id(sid, "coast", "the-shore"), SHORE,
                         "where the land stops and the water starts", "coast"))

    # The hinterland (`geography.Reach`): the named open ground a short walk out, each on
    # its own ground and as far as the world puts it. Through the fields where there are
    # fields — the waste and the wood lie past the ploughland, as every village plan from
    # Domesday to von Thünen draws it — and off the outskirts where there are none.
    # Measured 2026-10-05: before this, 15 of Aurvantis's 64 settlements offered no
    # ground outside but farmland and the shore, Vormoor and Scrapden among them.
    for reach in land.reaches:
        slug = places_mod._slug(reach.name) or reach.ground
        about = reach.words or biomes_describe(reach.ground)
        link(fields_id or out_id,
             add(ring_id(sid, reach.ground, slug), reach.name, about, reach.ground,
                 miles=reach.miles))

    # The tannery (leatherworking plan §10, contracts §8): out here, not in the street,
    # because the trade was kept outside — fifteenth-century Coventry's tanneries stood
    # just outside the walls by the river, where the town's own rules sent them for the
    # smell and the runoff (`places.TANNERY_CUES` has the sources). Only when the
    # settlement's OWN words name its tanners, and never beside one it already has: an
    # author's tannery stands where the author put it, in town or not. Hung off the
    # outskirts — or, when the outskirts already offer six ways on, the fields or the
    # shore, whichever offers fewest — so nothing on the ring offers more than six.
    if places_mod.tannery_implied(location) and not places_mod.has_a_tannery(home):
        anchors = [a for a in (out_id, fields_id, ring_id(sid, "coast", "the-shore"))
                   if a in made]
        roomy = [a for a in anchors if len(made[a]["exits"]) < 6]
        anchor = roomy[0] if roomy else min(anchors, key=lambda a: len(made[a]["exits"]))
        link(anchor, add(ring_id(sid, ground, "the-tannery"), places_mod.TANNERY_LABEL,
                         places_mod.TANNERY_ABOUT, ground))

    # The stretch of road a stopped journey left the party on: joined while they stand on
    # it, and hung off its own road head, so walking back is walking to the head.
    if is_along(at) and places_mod.location_of(at) == sid:
        slug = road_head_of(at)
        head = next((h for h in heads if road_head_of(h) == slug), "")
        to_name = next((r.to_name for r in walked if places_mod._slug(
            str(r.to_id).replace("-", " ").replace("_", " ")) == slug), "")
        name = f"on the road to {to_name}" if to_name else "on the road"
        add(at, name, f"out of sight of {here_name}, with the road either way",
            places_mod.terrain_of(at) or ground, (head,) if head else ())
        if head:
            link(at, head)

    return tuple(
        places_mod.Place(id=pid, name=row["name"], about=row["about"],
                         terrain=row["terrain"], exits=tuple(row["exits"]),
                         origin="generated", parent=sid, miles=row["miles"])
        for pid, row in made.items())


def _canon(word: str) -> str:
    from . import biomes

    return biomes.canonical(str(word or "")) or ""


def biomes_describe(ground: str) -> str:
    """A stock caption for a reach the world wrote no clause for: "downs, moor and rough
    upland"."""
    from . import biomes

    return biomes.describe(ground).lower()


def is_reach(place) -> bool:
    """Whether this is a reach of the hinterland: a ring place with a distance of its own."""
    return bool(getattr(place, "miles", 0)) and places_mod.is_ring(getattr(place, "id", ""))


def reach_of(ring_places, ground: str):
    """The reach of the hinterland on this ground, or None: where "I head into the hills"
    goes when the hills are a short walk out."""
    return next((p for p in ring_places or () if is_reach(p) and p.terrain == ground), None)


def road_for(ring_places, to_id: str):
    """The road head for a destination, or None."""
    slug = _road_slug(to_id)
    return next((p for p in ring_places or ()
                 if places_mod._spot_path(p.id)[:1] == [places_mod.RING + slug]), None)


# --- how long a hop takes -----------------------------------------------------------------

def _pace(ground: str) -> float:
    """The road column of Table 7-8 for this ground; 1 where the table has no row, as
    `journey.pace` answers it (a coastline is not a reason to refuse to walk)."""
    from . import journey

    return journey.pace(ground, "road")[0] or 1.0


def hop_minutes(frm, to, scale: str, speed_ft: int = 30) -> int:
    """How many minutes one step between two adjacent places takes, at this speed.

    - both in (or under) the settlement: the scale's band (Q10);
    - to or from the outskirts, a road head, the fields: half a mile at local movement,
      over the road column of the ground walked;
    - into a reach of open ground: three miles at the overland rate (an hour at a walk on
      good going — the hour `_op_travel` always charged for crossing the wall, now derived);
    - to or from a reach of the hinterland (`is_reach`): its own miles at the overland
      rate, over its ground's road column.
    """
    speed = max(5, int(speed_ft or 30))
    a = places_mod.setting_of(getattr(frm, "id", "") or "")
    b = places_mod.setting_of(getattr(to, "id", "") or "")
    if a != "outside" and b != "outside":
        band = HOP_MINUTES.get(scale or "town", HOP_MINUTES["town"])
        return max(1, round(band * 30 / speed))
    far = to if b == "outside" else frm
    # A reach of the hinterland is as far out as it lies, walked either way: from the
    # fields to the badlands and back again both cross the badlands' miles, at the
    # badlands' pace.
    # Not a step to somewhere founded in the reach itself ("the cave" off the ridgelines),
    # which is the half-mile ring hop it always was.
    reach = max((p for p in (frm, to) if is_reach(p)),
                key=lambda p: float(getattr(p, "miles", 0) or 0), default=None)
    other = to if reach is frm else frm
    if reach is not None and str(getattr(other, "id", "")).startswith(reach.id + "/"):
        reach = None
    if reach is not None:
        mph = speed / 10 * _pace(str(reach.terrain or places_mod.terrain_of(reach.id)))
        return max(1, round(float(reach.miles) / mph * 60))
    ground = str(getattr(far, "terrain", "") or places_mod.terrain_of(far.id))
    pace = _pace(ground)
    if places_mod.is_ring(far.id):
        feet_a_minute = speed * FEET_PER_MINUTE_PER_SPEED
        return max(1, round(RING_HOP_FEET / (feet_a_minute * pace)))
    # Open ground, or somewhere minted out there: the overland rate.
    mph = speed / 10 * pace
    return max(1, round(OPEN_GROUND_MILES / mph * 60))


def beyond_miles(world, location, biome: str) -> int:
    """How far out ground the world puts BEYOND the near land lies, in miles.

    Read off the routes the world wrote: a road that crosses farmland then mountain puts
    the mountain about half-way along it, so the mountain is as far as that half. The
    nearest such ground wins. Ground the world names only in its prose (a continent's
    Terrain) has no route to measure along, and stands half a walking day out.
    """
    from . import biomes, journey

    want = biomes.canonical(str(biome or "")) or ""
    sid = str(getattr(location, "id", "") or "")
    best = None
    for leg in journey.legs_from(world, sid) if world is not None else []:
        if leg.by_sea and leg.by != "river":
            continue
        crosses = [biomes.canonical(str(c)) or "" for c in leg.crosses]
        if want not in crosses[1:]:
            continue
        i = crosses.index(want, 1)
        miles = leg.miles if leg.miles is not None and leg.source == "exact" \
            else max(1, leg.days_apart) * journey.HOURS_PER_DAY * 3
        at = max(1, round(miles * i / len(crosses)))
        best = at if best is None else min(best, at)
    return best if best is not None else BEYOND_FALLBACK_MILES


def beyond_hours(world, location, biome: str, speed_ft: int = 30) -> int:
    """Whole hours on foot to ground beyond the near land, at the road column's pace —
    the rule `journey.hours_for` prices a route with (owner's ruling Q13)."""
    from . import journey

    miles = beyond_miles(world, location, biome)
    mph = max(0.1, max(5, int(speed_ft or 30)) / journey.FEET_PER_MPH
              * (journey.pace(biome, "road")[0] or 1.0))
    return max(1, round(miles / mph))
