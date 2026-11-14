"""The ways on from where the party stands: `scene.exits` on `/api/state` (I6).

The owner, 2026-09-29: "give the choices based on entrances, what areas are connected to
where i am." Measured the day before (G2, the leave-town script): "I walk to the nearest
crossroads" was refused by the engine and narrated as a walk anyway, and every later turn
resolved from where the engine was, not where the page said. A row of the ways that
actually exist, read off the engine's own place graph, is the player's side of the same
fix: nothing on it is a guess, so nothing clicked on it can be refused for not existing.

**What the traditions do.** Diku enumerates a room's exits and prints them on every look;
Inform's Recipe Book calls for "a small number of named positions"; Angband and DCSS
travel to one named destination and derive the path themselves (the engine's
`places.route`). Pointcrawl play lists a node's connections with their time on each, and
Daggerfall's travel map quotes days before it spends them. So: the exits listed are the
graph's edges, each with its time in words, a journey quotes its days and asks before it
spends them, and a way the rules would refuse is shown shut with the rule's own sentence
rather than hidden (hiding it is how the player learns the gate is watched by walking
into the watch).

Three groups, all derived every turn, never stored:

  next_door  one step along `Place.exits` to somewhere in or under the settlement,
             with the walk's minutes in words (`outskirts.hop_minutes`, Q10's bands);
  outside    the ring (`rules/outskirts.py`) — offered from a way out and from anywhere
             in the ring itself, each with the minutes of the walk `places.route` finds;
  road       a journey, from the head of its road (or the docks, or the shore, for a
             passage): days in words, riding when the party has a mount for every rider,
             which is the pace the declared journey then takes (Lane B's Q13).

`blocked` is the engine's own sentence, from the checks the doors themselves make
(`Engine.watch_at_the_way_out`, `watch_on_the_road`, `shut_for_the_night`) — one rule,
asked from two places, so the row can never grey a way the engine would let through or
offer one it would refuse.
"""
from __future__ import annotations


def _page_words(sentence: str) -> str:
    """The engine's sentence as the row shows it. The owner's rule for UI text is no
    dashes as punctuation; the engine's refusal parenthesises with them ("Leave by
    another way — ground you have founded… — or clear your name"), and commas carry the
    same clause. The tell the narrator reads is untouched."""
    return str(sentence or "").replace(" — ", ", ").replace(" – ", ", ")


def _norm(name: str) -> str:
    return " ".join(str(name or "").split()).lower()


def riding(engine) -> bool:
    """Whether the party would ride a journey: a mount for every rider, as `_op_journey`
    counts them (whoever travels with you, the mounts among them, one per rider)."""
    from rules import journey as journey_mod
    from rules import states

    scene = engine.scene
    party = [a for a in scene.actors.values()
             if not a.is_pc and a.has_state(states.TRAVELS_WITH_YOU)]
    mounts = [a for a in party
              if str(getattr(a, "from_template", "") or "") in journey_mod.MOUNTS
              and not a.is_down]
    riders = 1 + len([a for a in party if a not in mounts])
    return bool(mounts) and len(mounts) >= riders


def _minutes(known, path, scale: str, speed: int) -> int:
    from rules import outskirts
    from rules import places as places_mod

    total = 0
    for a, b in zip(path, path[1:]):
        pa, pb = places_mod.find(known, a), places_mod.find(known, b)
        if pa is None or pb is None:
            continue
        total += outskirts.hop_minutes(pa, pb, scale, speed)
    return total


def _road_words(road, leg, hours: int, ride: bool) -> str:
    """The journey's time as the ROADS OUT brief says it (`geography.roads_out`): days in
    words, never miles; "how far, nobody has written down" when the world never said."""
    from rules import geography

    if road.how in ("sea", "sea-after-road", "river") or leg is None or leg.source != "exact":
        return road.time_words
    words = geography._walk_time_words(hours)
    return words.replace(" on foot", " riding") if ride else words


def _days_aboard(days: int, river: bool = False) -> str:
    return f"{'a day' if days == 1 else f'{days} days'} " \
           f"{'on the river' if river else 'at sea'}"


def _passage_words(engine, leg, scene) -> str:
    """A passage row's days and fare, from the same quote the booking charges
    (`Engine.passage_quote`) — never "how far, nobody has written down", which is a
    road's words: a passage's days are the ship's and its price is the book's."""
    from rules import goods, states

    heads = 1 + sum(1 for a in scene.actors.values()
                    if not a.is_pc and a.has_state(states.TRAVELS_WITH_YOU))
    coast = engine.road_to_the_coast(leg)
    harbour = coast.to_id if coast is not None and coast.to_id != leg.to_id else ""
    _ship, days, cost = engine.passage_quote(leg, heads, port=harbour)
    fare = goods.purse_line(goods.coins_for(cost), engine._coins_here())
    aboard = f"{_days_aboard(days, leg.by == 'river')}, {fare} passage"
    if coast is None:
        return aboard
    # Inland, the road to the harbour comes first and is walked (`_op_journey`): the row
    # says its time too, so the total is never only the days at sea (0.3.2's row was).
    from rules import geography, journey as journey_mod

    pc = scene.pc()
    hours, _said, _how = journey_mod.hours_for(coast, pc.speed_feet if pc else 30)
    left = scene.road or {}
    if left.get("to") == coast.to_id and left.get("from") == scene.location_id:
        hours = max(1, hours - int(left.get("walked") or 0))
    walk = geography._walk_time_words(hours)
    if riding(engine):
        walk = geography._walk_time_words(
            journey_mod.mounted_hours(hours, "ride")[0]).replace(" on foot", " riding")
    return f"{walk} to {coast.to_name}, then {aboard}"


def exits(engine, world) -> list[dict]:
    """`[{"id", "name", "group", "time_words", "blocked", "journey"}]` for where the party
    stands. [] when they stand nowhere yet."""
    scene = engine.scene
    if not str(scene.at or ""):
        return []
    here = engine.here()
    rows = ways_from(engine, world, (here.id,)).get(here.id, [])
    return [{k: v for k, v in row.items() if k != "minutes"} for row in rows]


def ways_from(engine, world, place_ids) -> dict[str, list[dict]]:
    """The exits row as it would read standing in each of `place_ids`, without moving
    anybody: `{place_id: [row, ...]}`, each row the `exits()` row plus `minutes` (the
    walk's minutes; 0 for a journey, whose time is days in words).

    The fog-of-war chart (play/places_found.py) asks this of every place the player has
    been and every place one way from them; `exits()` asks it of where they stand. One
    body for both, so the chart can never draw a way the row would not offer, nor grey
    one the row would let through. The mock's data builder had to stand the party in each
    place in turn (`place_party`) to read this; the graph never needed the party there,
    only the place — `watch_at_the_way_out` already took the place walked from.

    An id that is not one of `engine.places()` (a place of another settlement, a reach of
    wild ground the party is no longer on) is left out: the graph read live is the graph
    from where the party stands.
    """
    from rules import geography, journey as journey_mod
    from rules import places as places_mod

    scene = engine.scene
    if not str(scene.at or ""):
        return {}
    pc = scene.pc()
    known = engine.places()
    loc = world.get(scene.location_id) if world is not None else None
    scale = places_mod.scale_of(loc) if loc is not None else "town"
    speed = int(getattr(pc, "speed_feet", 30) or 30) if pc is not None else 30
    clock = int(scene.clock_minutes or 0)

    # Asked once for every place: none of it depends on which place the row is for.
    roads_here: list = []
    ride, watched, legs = False, "", {}
    if loc is not None:
        ride = riding(engine)
        watched = _page_words(engine.watch_on_the_road(pc))
        legs = {leg.to_id: leg for leg in journey_mod.legs_from(world, scene.location_id)}
        roads_here = list(geography.roads_out(world, loc, speed))

    out: dict[str, list[dict]] = {}
    for place_id in place_ids:
        here = places_mod.find(known, place_id)
        if here is None or here.id in out:
            continue
        out[here.id] = _rows_from(engine, here, known, pc, loc, scale, speed, clock,
                                  roads_here, ride, watched, legs)
    # Aboard a booked ship, the way on is the voyage (`Engine._sail`): one journey row,
    # from every room of her, to where she is bound. Keyed by the SHIP's id, not the
    # port's: the page keeps a chip whose id is still a way on as "the move did not
    # happen", and live the booking row and this one shared the port's id.
    ship = engine.aboard()
    if ship is not None and ship.bound_for:
        from rules import ships

        dest = world.get(ship.bound_for) if world is not None else None
        days = ship.days_left
        row = {"id": ship.id, "name": str(getattr(dest, "name", "") or "port"),
               "group": "road", "blocked": "", "journey": True, "minutes": 0,
               "time_words": _days_aboard(days, ship.river)}
        for place_id, rows in out.items():
            if ships.vessel_of(place_id) == ship.id:
                rows.append(dict(row))
    return out


def _rows_from(engine, here, known, pc, loc, scale, speed, clock,
               roads_here, ride, watched, legs) -> list[dict]:
    from rules import geography, journey as journey_mod, keepers, outskirts
    from rules import places as places_mod

    scene = engine.scene
    out: list[dict] = []
    seen = {here.id}

    def blocked_for(p) -> str:
        refused, _line = engine.watch_at_the_way_out(pc, here.id, p, known)
        if refused:
            return _page_words(refused)
        keeper = engine.shut_for_the_night(p)
        if keeper is not None:
            return keepers.shut_line(p.id, clock, scene.founded, who=str(keeper.name or ""))
        return ""

    def add(p, group: str, path) -> None:
        if p is None or p.id in seen or p.described_only:
            return
        seen.add(p.id)
        minutes = _minutes(known, path, scale, speed)
        out.append({"id": p.id, "name": p.name, "group": group,
                    "time_words": geography.walk_words(minutes),
                    "blocked": blocked_for(p), "journey": False, "minutes": minutes})

    # One step along the graph's own edges. A step out onto the ring is "outside".
    adjacent = [places_mod.find(known, x) for x in here.exits]
    for p in adjacent:
        if p is not None and places_mod.setting_of(p.id) != "outside":
            add(p, "next_door", (here.id, p.id))
    for p in adjacent:
        if p is not None and places_mod.setting_of(p.id) == "outside":
            add(p, "outside", (here.id, p.id))

    # The ring, from a way out or from anywhere on it: the rest of it by the walk the
    # engine would take (`places.route`), nearest first.
    on_ring = places_mod.is_ring(here.id)
    at_a_way_out = any(p is not None and places_mod.is_ring(p.id) for p in adjacent)
    if on_ring or at_a_way_out:
        further = []
        for p in known:
            if p.id in seen or not places_mod.is_ring(p.id) or outskirts.is_along(p.id):
                continue
            path = places_mod.route(known, here.id, p.id)
            if path:
                further.append((_minutes(known, (here.id, *path), scale, speed), p, path))
        for _m, p, path in sorted(further, key=lambda t: t[0]):
            add(p, "outside", (here.id, *path))

    # Journeys, from where each one leaves.
    if loc is not None:
        head_slug = outskirts.road_head_of(here.id)
        roads = []
        for road in roads_here:
            if road.how in ("road", ""):
                # The head of this road, or the stretch of it a stopped journey left
                # the party on (both carry the destination's slug).
                mine = bool(head_slug) and \
                    outskirts._road_slug(road.to_id) == "the-road-to-" + head_slug
            else:
                # A passage is boarded where the brief says it leaves from — or, inland,
                # taken up again from the stretch of the harbour road it stopped on.
                mine = _norm(here.name) == _norm(road.leaves_from) or (
                    outskirts.is_along(here.id)
                    and (scene.road or {}).get("then") == road.to_id)
                coast = engine.road_to_the_coast(legs[road.to_id]) \
                    if road.how == "sea-after-road" and road.to_id in legs else None
                if coast is not None and coast.to_id != road.to_id:
                    # Inland with a road to a harbour: offered where that road leaves
                    # (its head, or a stretch of it), as the road itself is — not from
                    # the town's shore, five days from where the ship is.
                    mine = bool(head_slug) and outskirts._road_slug(coast.to_id) \
                        == "the-road-to-" + head_slug
            if not mine:
                continue
            leg = legs.get(road.to_id)
            sea = road.how in ("sea", "sea-after-road")
            hours = 0
            if leg is not None:
                hours, _said, _how = journey_mod.hours_for(leg, speed)
                # A road half walked is half a road (`_op_journey`'s `resumed`).
                left = scene.road or {}
                if left.get("to") == leg.to_id and left.get("from") == scene.location_id:
                    hours = max(1, hours - int(left.get("walked") or 0))
                if ride and not sea:
                    hours = journey_mod.mounted_hours(hours, "ride")[0]
            voyage = leg is not None and leg.by_sea
            roads.append((hours, {
                "id": road.to_id, "name": road.to_name, "group": "road",
                "time_words": (_passage_words(engine, leg, scene) if voyage else
                               _road_words(road, leg, hours, ride and not sea)),
                "blocked": watched, "journey": True, "minutes": 0}))
        out.extend(entry for _h, entry in sorted(roads, key=lambda t: t[0]))
    return out


def find(entries, place_id: str) -> dict | None:
    """The exit an attachment names, by its id, or None."""
    return next((e for e in entries or () if e.get("id") == str(place_id or "")), None)
