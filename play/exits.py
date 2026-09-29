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


def exits(engine, world) -> list[dict]:
    """`[{"id", "name", "group", "time_words", "blocked", "journey"}]` for where the party
    stands. [] when they stand nowhere yet."""
    from rules import geography, journey as journey_mod, keepers, outskirts
    from rules import places as places_mod

    scene = engine.scene
    if not str(scene.at or ""):
        return []
    pc = scene.pc()
    known = engine.places()
    here = engine.here()
    loc = world.get(scene.location_id) if world is not None else None
    scale = places_mod.scale_of(loc) if loc is not None else "town"
    speed = int(getattr(pc, "speed_feet", 30) or 30) if pc is not None else 30
    clock = int(scene.clock_minutes or 0)

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
        out.append({"id": p.id, "name": p.name, "group": group,
                    "time_words": geography.walk_words(_minutes(known, path, scale, speed)),
                    "blocked": blocked_for(p), "journey": False})

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
        ride = riding(engine)
        watched = _page_words(engine.watch_on_the_road(pc))
        legs = {leg.to_id: leg for leg in journey_mod.legs_from(world, scene.location_id)}
        head_slug = outskirts.road_head_of(here.id)
        roads = []
        for road in geography.roads_out(world, loc, speed):
            if road.how in ("road", ""):
                # The head of this road, or the stretch of it a stopped journey left
                # the party on (both carry the destination's slug).
                mine = bool(head_slug) and \
                    outskirts._road_slug(road.to_id) == "the-road-to-" + head_slug
            else:
                # A passage is boarded where the brief says it leaves from.
                mine = _norm(here.name) == _norm(road.leaves_from)
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
            roads.append((hours, {
                "id": road.to_id, "name": road.to_name, "group": "road",
                "time_words": _road_words(road, leg, hours, ride and not sea),
                "blocked": watched, "journey": True}))
        out.extend(entry for _h, entry in sorted(roads, key=lambda t: t[0]))
    return out


def find(entries, place_id: str) -> dict | None:
    """The exit an attachment names, by its id, or None."""
    return next((e for e in entries or () if e.get("id") == str(place_id or "")), None)
