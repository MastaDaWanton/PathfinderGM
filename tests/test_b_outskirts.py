"""The middle scale: the ground just outside a settlement (Lane B, rules/outskirts.py).

Measured 2026-09-28 (docs/playtest-2026-09-28.md, items 16, 17, 20): two scales of
movement and nothing between them. "I leave the village and stand outside it" travelled
to the way in, INSIDE the village; "I walk to the nearest crossroads" and "I take the path
away from town" were refused as "no such kind of place" and narrated as movement anyway;
the forest Bobby then walked into was filed under the village's own id, so every panel
still read VORMOOR · VILLAGE. These tests hold the ring every settlement now has, across
all three exports, and the parse that says which side of the edge a place is on.
"""
from __future__ import annotations

import pytest

from rules import geography, outskirts, places


def _settlements(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


def test_every_settlement_has_ground_outside_it(worlds):
    """17.1: before this, 0 of 82 settlements across the three worlds had anywhere
    outside to stand but the open-ground reaches, which were filed under the town's id
    and reached only by naming a biome. Every one now has at least the outskirts, joined
    both ways to a way in."""
    for e in _settlements(worlds):
        ring = outskirts.ring(worlds, e)
        names = [p.name for p in ring]
        assert "the outskirts" in names, e.name
        out = next(p for p in ring if p.name == "the outskirts")
        home = {p.id for p in places.home_set(e)}
        assert set(out.exits) & home, f"{e.name}: the outskirts lead nowhere in town"
        for p in ring:
            assert places.setting_of(p.id) == "outside", p.id
            assert places.is_ring(p.id)
            assert places.terrain_of(p.id) == p.terrain != places.URBAN, p.id
            assert places.location_of(p.id) == e.id


def test_nothing_on_the_ring_offers_more_than_six_ways_on(worlds):
    """Fate's two-to-four zones and Inform's "small number of named positions": the
    ceiling protects the size of the choice put in front of the player. Two of
    Aurvantis's settlements have six road legs; the sixth hangs off a second fork."""
    for e in _settlements(worlds):
        for p in outskirts.ring(worlds, e):
            assert len(p.exits) <= 6, (e.name, p.name, len(p.exits))


def test_a_crossroads_is_out_on_the_road_where_roads_part(worlds):
    """The owner's ruling Q11: "crossroads are place[s] not in a town where all the
    roads leave to different places". So: one only where two or more walked roads lead
    to different destinations, reached from the outskirts and never beside the fields,
    and every road head it serves hangs off it."""
    seen = 0
    for e in _settlements(worlds):
        ring = outskirts.ring(worlds, e)
        by_id = {p.id: p for p in ring}
        heads = [p for p in ring if outskirts.road_head_of(p.id)]
        forks = [p for p in ring if "crossroads" in p.name]
        walked = {r.to_id for r in geography.roads_out(worlds, e) if r.how in ("road", "")}
        if len(walked) >= 2:
            assert forks, f"{e.name}: {len(walked)} roads and no crossroads"
            seen += 1
            first = next(p for p in forks if p.name == "the crossroads")
            out = next(p for p in ring if p.name == "the outskirts")
            assert out.id in first.exits and first.id in out.exits
            fields = next((p for p in ring if p.name == "the fields"), None)
            if fields is not None:
                assert first.id not in fields.exits, "a crossroads beside the fields"
            for h in heads:
                assert any(f.id in h.exits for f in forks), h.name
        else:
            assert not forks, f"{e.name}: a crossroads with {len(walked)} road"
        for p in forks:
            assert all(x in by_id for x in p.exits), "a crossroads joined to a town room"
    if len(worlds.play["settlements"]) > 50:          # Aurvantis: 44 of 64, measured
        assert seen == 44


def test_a_road_nobody_wrote_down_is_not_called_a_road(worlds):
    """The synthetic world has a route with nothing but its two ends: no `by`, no miles.
    "The road to Oakhollow" would be a road fact this app invented; it is "the way to"."""
    for e in _settlements(worlds):
        roads = {r.to_id: r for r in geography.roads_out(worlds, e)}
        for p in outskirts.ring(worlds, e):
            slug = outskirts.road_head_of(p.id)
            if not slug:
                continue
            r = next(r for tid, r in roads.items()
                     if outskirts._road_slug(tid) == "the-road-to-" + slug)
            want = "the road to" if r.how == "road" else "the way to"
            assert p.name == f"{want} {r.to_name}", (p.name, r.how)


def test_outside_is_parsed_from_the_id_and_never_stored():
    """Q3: the plan's `Scene.outside` was dropped, because a field beside `scene.at` is
    the sibling store `scene.biome` was before it was removed. The parse covers every
    shape of id the app makes, and Bobby's save — standing at the forest's approach under
    the village's id — reads as outside with no migration."""
    loc = "bde94b038cba"
    cases = {
        f"{loc}~urban:the-market": "in",
        f"{loc}~urban:the-tavern^1": "in",
        f"{loc}~urban:the-market/the-alley": "in",
        f"{loc}~forest:the-approach": "outside",          # Bobby, 2026-09-28
        f"{loc}~farmland:@the-outskirts": "outside",
        f"{loc}~farmland:@the-outskirts/the-milestone": "outside",
        f"{loc}~mountain:@along-the-road-to-4b1bcd462628": "outside",
        f"{loc}~underground:the-market/the-sewers": "under",
        f"{loc}~underground:the-market/the-sewers/the-outfall": "under",
        f"{loc}~ruins:the-temple/the-crypt": "under",
        f"{loc}~underground:the-market/the-cave": "outside",
        f"{loc}~underground:the-market/the-cave/the-mouth": "outside",
        f"{loc}~underground:the-approach/the-old-mine": "outside",
        "": "in",
        "here": "in",
    }
    for pid, want in cases.items():
        assert places.setting_of(pid) == want, pid


def test_every_caption_is_its_own(worlds):
    """20.3: the forest's approach was captioned "the way in, and little to hide
    behind" — the gate's words — so the map said the party was at the entrance it had
    left. No caption of any place a party can name from outside may name another place of
    the same set."""
    from rules import floorplan

    assert "way in" not in floorplan.BY_SPOT["the-approach"].about
    for e in list(_settlements(worlds))[:12]:
        ring = outskirts.ring(worlds, e)
        known = places.for_scene(e, ring[0].id if ring else "", ring=ring)
        names = {p.name.lower() for p in known}
        for p in ring:
            said = f"{p.about} {floorplan.shape_for(p.id, p.terrain).about}".lower()
            others = [n for n in names if n != p.name.lower() and n in said
                      and n not in ("the road",)]
            assert not others, (p.name, said, others)


def test_the_ring_joins_the_scene_set_with_its_door_both_ways(worlds):
    """A way out with no way back is a door with no handle on the inside — measured once
    already on the generated ways in (`_with_a_way_in`, 2026-09-23)."""
    for e in list(_settlements(worlds))[:10]:
        ring = outskirts.ring(worlds, e)
        known = places.for_scene(e, places.home_set(e)[0].id, ring=ring)
        by_id = {p.id: p for p in known}
        out = next(p for p in ring if p.name == "the outskirts")
        door = next(x for x in out.exits if x in by_id and not places.is_ring(x))
        assert out.id in by_id[door].exits
        start = places.home_set(e)[0].id
        assert places.route(known, start, out.id), e.name
        assert places.route(known, out.id, start), e.name


def test_a_world_less_engine_keeps_the_two_scales_it_had():
    """No world, no roads and no land to read: the ring is empty and the set is today's,
    so every engine test built without a world is untouched by this lane."""
    assert outskirts.ring(None, "bde94b038cba") == ()
    home = places.for_scene("bde94b038cba", "bde94b038cba~urban:the-market")
    assert not any(places.is_ring(p.id) for p in home)


@pytest.mark.parametrize("minutes_scale", [("village", 2), ("town", 4), ("city", 8)])
def test_a_hop_in_town_costs_the_scale_s_minutes(minutes_scale):
    """Q10, accepted: village 2, town 4, city 8 minutes a hop at speed 30 — the
    measured "still 08:00 after two crossings of town" (16.5) is what this ends. A slower
    walker takes longer, by the rules' own ratio."""
    scale, want = minutes_scale
    a = places.Place(id="x~urban:the-market", terrain="urban")
    b = places.Place(id="x~urban:the-well", terrain="urban")
    assert outskirts.hop_minutes(a, b, scale, 30) == want
    assert outskirts.hop_minutes(a, b, scale, 20) > want


def test_a_ring_hop_is_half_a_mile_and_open_ground_an_hour():
    """PF1e local movement is 300 feet a minute at speed 30 (AoN Rules ID=50, Table
    7-6); half a mile is about nine minutes on good going. Three miles into open ground
    is the hour the travel door always charged, now derived at 3 mph."""
    gate = places.Place(id="x~urban:the-gate", terrain="urban")
    out = places.Place(id="x~farmland:@the-outskirts", terrain="farmland")
    wood = places.Place(id="x~forest:the-approach", terrain="forest")
    assert outskirts.hop_minutes(gate, out, "town", 30) == 9
    assert outskirts.hop_minutes(out, wood, "town", 30) == 60
    desert = places.Place(id="x~desert:the-approach", terrain="desert")
    assert outskirts.hop_minutes(out, desert, "town", 30) == 120   # road column 0.5
