"""Fights on two levels of one room: a foyer with a landing, a library with a gallery.

Asked for on 2026-09-14, and the question found two defects and one gap:

> "what about a fight that takes place in a foyer with a staircase and there are enemies
> shooting down at you? or a multi storey Library where I'm being attack from above and
> or below from another floor?"

Measured before anything was changed, on exactly that foyer — an archer on a landing, a
man on the floor below, a balustrade between them:

    your cover from the archer   total
    the archer's cover from you  total

Neither could attack the other at all. `blocked` is solid at every height, so a gallery
rail read as a wall. **A balustrade is a thing to shoot over.**

The three things behind that:

  * `Grid` had no way to say "low obstacle". 1e does — "a low obstacle (such as a wall no
    higher than half your height) provides cover" — so `parapet` is that, keyed by the
    level of its top, and the cover geometry now carries the height of the line along it.
  * `position.cover_of` truncated both positions to two dimensions before asking. Written
    when cover was flat, and it would have silently defeated the whole fix: the geometry
    grew a third axis and the caller went on handing it squares.
  * Standing on raised ground did not raise you. A dais was drawn, saved and measured, and
    the creature on it was still at level zero — no higher ground, and nothing could tell
    it was up there. `Scene.settle_levels` puts everybody on the floor they are on.

A closed upper storey stays a separate place and you cannot shoot through a floor, which
is right. What a heightmap cannot do is an overhang — nothing is ever *under* a walkable
square — so a gallery is something you fight across and not something you walk beneath.
That trade is recorded in `docs/distance-and-geography.md` §6 and was made deliberately.
"""
from __future__ import annotations

from rules import floorplan, grid as G, position
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

LIBRARY = "5bbd0c40345f~urban:the-library"


def _foyer(rail: bool):
    """A hall with a landing along the top of it, and either a rail or a wall at its lip."""
    g = G.Grid(width=12, height=12, ceiling=5)
    for x in range(2, 10):
        g.floor[(x, 2)] = 2
        if rail:
            g.parapet[(x, 3)] = 2
        else:
            g.blocked.add((x, 3))
    s = Scene(location_id="t")
    below = instantiate("guildhand", scene=s, name="Below")
    s.add(below, at=(5, 8))
    archer = instantiate("guildhand", scene=s, name="Archer")
    s.add(archer, at=(5, 2))
    s.grid = g
    e = Engine(s, Dice(seed=1), world=None)
    s.settle_levels()
    return s, e, below, archer


# --- the foyer ---------------------------------------------------------------------------

def test_standing_on_the_landing_puts_you_on_the_landing():
    """The gap that made the heightmap scenery. A raised square nobody is raised by does
    nothing at all."""
    _s, _e, _below, archer = _foyer(rail=True)
    assert _s.positions[archer.ref][2] == 2


def test_a_rail_is_cover_and_a_wall_is_total():
    """The defect this file is named for. Both give +4 — 1e's low obstacle grants cover
    to creatures within thirty feet of it, either side — but a rail can never stop the
    fight, and before this it did."""
    s, _e, below, archer = _foyer(rail=True)
    assert position.cover_of(s, archer, below) == "cover"
    assert position.cover_of(s, below, archer) == "cover"

    walled, _e2, below2, archer2 = _foyer(rail=False)
    assert position.cover_of(walled, archer2, below2) == "total"


def test_rising_above_the_rail_clears_it():
    """The height in the geometry, and the proof it is real: a rail whose top is level 2
    stops a line running under it and does nothing to one running over."""
    s, _e, below, archer = _foyer(rail=True)
    s.positions[archer.ref] = (5, 2, 5)
    assert position.cover_of(s, below, archer) == ""


def test_shooting_down_is_worth_nothing_and_swinging_down_is_worth_one():
    """Table 8-5 gives higher ground +1 melee and +0 ranged in as many words, so the
    archer on the landing gains nothing for the height while they are shooting — which
    is the rule, and the sort of thing a house would get wrong in the player's favour."""
    s, _e, below, archer = _foyer(rail=True)
    melee = [m.source for m in position.attack_mods(s, archer, below)]
    ranged = position.attack_mods(s, archer, below, {"category": "ranged"})
    assert "higher ground" in melee
    assert ranged == []


def test_the_one_below_gets_no_height_bonus():
    s, _e, below, archer = _foyer(rail=True)
    assert not [m for m in position.attack_mods(s, below, archer)
                if "higher" in m.source]


# --- the library -----------------------------------------------------------------------

def test_the_library_is_generated_with_a_gallery_and_a_rail_on_it():
    """The second scene asked for, and it has to come out of the generator rather than
    out of a test fixture, or the rooms a player actually walks into stay flat."""
    g = floorplan.for_place(LIBRARY, "urban")
    assert {v for v in g.floor.values()} == {floorplan.LEDGE_AT}
    assert g.parapet, "a gallery with no rail on it"
    assert g.ceiling is not None, "a library with no roof"


def test_a_fight_in_the_library_spans_both_levels():
    """End to end on a generated room: somebody on the gallery, somebody on the floor,
    and the engine has an answer for every part of it."""
    g = floorplan.for_place(LIBRARY, "urban")
    gallery = sorted(p for p, v in g.floor.items() if v == floorplan.LEDGE_AT)
    ground = [(x, y) for x in range(1, g.width - 1) for y in range(1, g.height - 1)
              if g.ground((x, y)) == 0 and g.passable((x, y))]
    assert gallery and ground

    s = Scene(location_id="5bbd0c40345f")
    s.at = LIBRARY
    you = instantiate("guildhand", scene=s, name="You")
    you.kind = "pc"
    s.add(you, at=ground[len(ground) // 2])
    sniper = instantiate("guildhand", scene=s, name="Sniper")
    s.add(sniper, at=gallery[len(gallery) // 2])
    s.grid = g
    Engine(s, Dice(seed=1), world=None)
    s.settle_levels()

    assert s.positions[sniper.ref][2] == floorplan.LEDGE_AT
    assert G.distance_between(s.positions[sniper.ref], "medium",
                              s.positions[you.ref], "medium") > 0
    # Neither is cut off from the other, which was the whole complaint.
    assert position.cover_of(s, sniper, you) != "total"
    assert position.cover_of(s, you, sniper) != "total"


# --- the bias ---------------------------------------------------------------------------

def test_most_places_are_built_with_height_in_them():
    """Asked for in as many words: "the designs it thinks of are more likely to have
    verticality than not", without being silly about it. So `Shape.vertical` defaults to
    a ledge and flatness is the thing that has to be written down — a back alley, open
    grassland, the bottom of a sump."""
    shapes = list(floorplan.BY_SPOT.values()) + list(floorplan.BY_TERRAIN.values())
    flat = [s for s in shapes if s.vertical == "none"]
    assert len(flat) < len(shapes) / 2, "most places are flat again"
    assert flat, "nowhere is flat, which is its own kind of silly"


def test_somewhere_flat_is_left_flat():
    """The other half of that instruction. A back alley with a mezzanine in it is worse
    than a back alley."""
    for spot in ("the-back-streets", "the-sump"):
        g = floorplan.for_place(f"5bbd0c40345f~urban:{spot}", "urban")
        assert not g.floor and not g.parapet, spot


def test_a_ledge_is_in_the_same_place_in_that_room_for_ever():
    a = floorplan.for_place(LIBRARY, "urban")
    b = floorplan.for_place(LIBRARY, "urban")
    assert a.floor == b.floor and a.parapet == b.parapet


def test_the_rail_survives_a_save():
    """`floor` and `ceiling` were both dropped by the serialiser when they arrived last
    stage. `parapet` arrived this stage, so it gets the same check rather than the same
    bug."""
    from play.campaign import _grid

    before = floorplan.for_place(LIBRARY, "urban")
    raw = {"width": before.width, "height": before.height,
           "difficult": sorted(before.difficult), "blocked": sorted(before.blocked),
           "obscuring": sorted(before.obscuring),
           "floor": {f"{x},{y}": v for (x, y), v in before.floor.items()},
           "ceiling": before.ceiling,
           "parapet": {f"{x},{y}": v for (x, y), v in before.parapet.items()}}
    after = _grid(raw)
    assert after.parapet == before.parapet
    assert after.floor == before.floor
