"""What a fight conjured leaves the map with it, and no two areas share an id.

Measured 2026-09-25 by probe: `end_encounter` cleared `manifests` and `wards` without
lifting them — written when the grid went with the fight too. Since item 28 (2026-09-19)
the grid stays, so the fog's squares stayed in `grid.obscuring` with nothing claiming
them, and the room was blind and walled until the party left. And manifestation ids were
`len + 1`: two fogs, the first lifted, and the next was `m2` beside a standing `m2` —
wards find their area by that id.
"""
from __future__ import annotations

from rules.engine import Manifestation, Scene, Ward
from rules.grid import Grid


def test_ending_the_fight_lifts_its_fog_and_its_walls():
    scene = Scene(location_id="x", grid=Grid(width=10, height=10))
    scene.grid.obscuring.add((0, 0))                  # a pillar the room always had
    scene.place(Manifestation(what="fog", terrain="obscuring", squares=[(0, 0), (3, 3)]))
    scene.place(Manifestation(what="wall", terrain="blocked", squares=[(5, 5), (5, 6)]))
    scene.initiative, scene.turn = [("pc", 10)], 0
    scene.end_encounter()
    assert scene.grid is not None, "the ground stays (item 28)"
    assert scene.grid.obscuring == {(0, 0)}, "the fog's squares outlived the fog"
    assert scene.grid.blocked == set(), "the wall's squares outlived the wall"
    assert scene.manifests == []


def test_an_id_is_never_handed_out_twice_while_anything_names_it():
    scene = Scene(location_id="x", grid=Grid(width=10, height=10))
    first = scene.place(Manifestation(what="fog", terrain="obscuring", squares=[(1, 1)]))
    second = scene.place(Manifestation(what="fog", terrain="obscuring", squares=[(2, 2)]))
    scene.lift(first)
    third = scene.place(Manifestation(what="fog", terrain="obscuring", squares=[(3, 3)]))
    assert len({second.id, third.id}) == 2, (second.id, third.id)


def test_a_ward_still_pointing_at_an_area_keeps_its_id_taken():
    scene = Scene(location_id="x", grid=Grid(width=10, height=10))
    made = scene.place(Manifestation(what="fire", terrain="none", squares=[(1, 1)]))
    scene.wards.append(Ward(owner="pc", trigger="each_round", source="fire",
                            manifest_id=made.id))
    scene.lift(made)
    fresh = scene.place(Manifestation(what="ice", terrain="none", squares=[(2, 2)]))
    assert fresh.id != made.id, "a new area took the id a ward still points at"
