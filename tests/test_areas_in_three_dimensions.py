"""Spell areas with a top and a bottom.

A spread is defined by Aiming a Spell as extending "in all directions", and fireball's
printed area is a *20-ft.-radius spread* — so it has always been a sphere on paper and was
a flat disc in this engine.

**The defect ran the opposite way from the obvious guess, which is why it was measured
before it was fixed.** A disc did not miss things above it; it caught everything above
them. `Manifestation.covers` reads a stored square as "any level" — the right reading of a
save written before the vertical existed — so a disc was an *infinite column*:

                                        old disc    sphere
      beside it on the floor                True      True
      on a gallery 10 ft up                 True      True
      flying 30 ft up                       True     False
      flying 100 ft up                      True     False

A fireball on the floor reached a creature a hundred feet over it, and the fix is that a
sphere has a top.

This was the last thing between the engine and "choose where to cast" meaning a cell
rather than a square — `docs/distance-and-geography.md` and the viewport groundwork in
stage 7.
"""
from __future__ import annotations

from rules import grid as G
from rules.engine import Manifestation


def _area(cells):
    return Manifestation(what="fire", terrain="none", squares=sorted(cells))


def _body(square, level=0, size="medium"):
    return G.volume(square, size, level)


# --- the sphere ---------------------------------------------------------------------

def test_a_spread_is_a_sphere_when_it_is_told_which_level_it_is_on():
    flat = G.burst((5, 5), 20)
    ball = G.burst((5, 5, 3), 20)
    assert all(len(c) == 2 for c in flat)
    assert all(len(c) == 3 for c in ball)
    assert len(ball) > len(flat), "a sphere is bigger than the disc through its middle"


def test_a_two_element_centre_still_answers_in_squares():
    """Every caller and every save written before the vertical keeps working, and means
    what it always meant. This is the same bargain `distance` makes."""
    assert G.burst((5, 5), 20) == G.burst((5, 5), 20)
    assert all(len(c) == 2 for c in G.burst((5, 5), 20))


def test_the_blast_has_a_top():
    """The measurement this file exists for."""
    ball = _area(c for c in G.burst((5, 5, 0), 20) if c[2] >= 0)
    assert ball.covers(_body((6, 5), 0)), "somebody beside it escaped"
    assert ball.covers(_body((6, 5), 2)), "somebody on a gallery escaped"
    assert not ball.covers(_body((6, 5), 6)), "a flier 30 ft up was caught"
    assert not ball.covers(_body((6, 5), 20)), "a flier 100 ft up was caught"


def test_the_disc_it_replaced_had_no_top_at_all():
    """Kept as the record of what was wrong. A square stored with no level matches at
    every level, which is right for an old save and wrong for a fireball."""
    disc = _area(G.burst((5, 5), 20))
    assert disc.covers(_body((6, 5), 20)), \
        "the old shape has stopped being an infinite column, so this file is stale"


def test_nothing_reaches_below_the_floor():
    """A sphere centred on the ground reaches down as far as it reaches up, and there is
    no level under level zero — the first run of this put a bank of fog in the cellar of
    a room with no cellar."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.grid import Grid

    s = Scene(location_id="t")
    s.grid = Grid()
    e = Engine(s, Dice(seed=1), world=None)
    cells = e._squares_for({"shape": "radius", "size": 20}, {"square": (5, 5)})
    assert cells and all(c[2] >= 0 for c in cells)


# --- the cylinder, which the rules DO specify -----------------------------------------

def test_a_cylinder_shoots_down_from_its_circle():
    """The one area shape whose vertical extent the rules state outright: "the spell
    shoots down from the circle, filling a cylinder", and it "ignores any obstructions
    within its area"."""
    cells = G.cylinder((5, 5, 4), 10)
    levels = {c[2] for c in cells}
    assert levels == {0, 1, 2, 3, 4}, levels
    assert all(c[2] <= 4 for c in cells), "a cylinder reached above its own circle"


def test_a_cylinder_with_a_stated_height_stops_there():
    cells = G.cylinder((5, 5, 6), 10, height_ft=10)
    assert {c[2] for c in cells} == {5, 6}


# --- the line -------------------------------------------------------------------------

def test_a_flat_bolt_is_what_it_always_was():
    assert G.line((0, 0), (4, 0), 20) == G.line((0, 0), (4, 0), 20)
    assert all(len(c) == 2 for c in G.line((0, 0), (4, 0), 20))


def test_a_bolt_aimed_upward_climbs_as_it_travels():
    """A lightning bolt at something on a gallery does not run along the floor and then
    turn up at the end."""
    cells = sorted(G.line((0, 0, 0), (4, 0, 4), 20))
    assert cells[0][2] == 0
    assert cells[-1][2] > 0
    assert [c[2] for c in cells] == sorted(c[2] for c in cells), \
        "the bolt did not climb steadily"


# --- and the map still blocks sight ----------------------------------------------------

def test_a_cloud_puts_its_FOOTPRINT_on_the_map_and_keeps_its_cells():
    """The coupling this change had to get right, and did not at first. An area knows its
    own height — that is what decides who is standing in it — but the grid's terrain sets
    are flat, because sight and movement in this engine are: a square is opaque or it is
    not, at every level.

    Writing cells into `grid.obscuring` was silent and total. `line_of_sight` compares
    two-element squares, no three-element cell ever matched one, and sight went straight
    through a bank of fog that was drawn on the map.
    """
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.grid import Grid

    s = Scene(location_id="t")
    s.grid = Grid()
    Engine(s, Dice(seed=1), world=None)
    cells = sorted(c for c in G.burst((5, 5, 0), 20) if c[2] >= 0)
    made = s.place(Manifestation(what="fog", terrain="obscuring", squares=cells))

    assert made.squares and all(len(c) == 3 for c in made.squares), "the cells were lost"
    assert made.added and all(len(c) == 2 for c in made.added), \
        "three-element cells reached the grid's flat terrain set"
    assert not s.grid.line_of_sight((5, 5), (12, 5)), "sight went through the fog"
