"""A creature is a box, not a dot on a flat map.

Stage 2 of the distance work (docs/distance-and-geography.md). Before it, `grid.Point` was
`tuple[int, int]` and there was nowhere to put a spider on a ceiling: the whole engine had
one plane, and a flier, a climber and a man standing in a doorway were all the same height.

The rule this implements was given on 2026-09-14: "the amount of space an npc, monster or
the player take up is defined by their size with medium taking up a single 5ft square and
their height contained within 2x5ft squares (8ft is max for medium)."

**Sourced, and the obvious source does not have it.** Table 8-4 Creature Size and Scale
carries no height column at all — only Space and Natural Reach (checked against
aonprd.com/Rules.aspx?ID=179). The typical height bands come from the Creature Sizes table
at d20pfsrd.com/gamemastering/combat/space-reach-threatened-area-templates/, which prints
"4' to 8 ft." against Medium, and which warns in its own words that the values are
*typical* and that exceptions exist. That warning is why `height_ft` takes an override.

**And the third axis of the distance rule is invented here**, because Pathfinder does not
have one: Movement, Position and Distance (ID=173) and Measuring Distance (ID=175) define
the five-foot square and the 5-10-5 diagonal and contain no vertical clause. The house
rule is written down in `grid.distance` rather than left implicit, and
`test_the_third_axis_is_the_same_rule_as_the_other_two` pins the shape of it.
"""
from __future__ import annotations

import itertools

from rules import grid
from rules.tables import SPACE_AND_REACH


# --- the box --------------------------------------------------------------------------

def test_a_medium_creature_is_one_square_of_floor_and_two_of_air():
    """The rule as it was asked for: eight feet of person inside ten feet of space."""
    assert grid.size_squares("medium") == 1
    assert grid.height_ft("medium") == 8
    assert grid.height_squares("medium") == 2
    assert grid.volume((3, 4), "medium", level=0) == [(3, 4, 0), (3, 4, 1)]


def test_every_size_carries_its_own_height():
    """A column on the same table as space and reach, because it is the same kind of
    fact. If a size is added without one, this fails rather than defaulting it to
    Medium's eight feet behind everybody's back."""
    for size, row in SPACE_AND_REACH.items():
        assert "tall_ft" in row, f"{size} has no height"
        assert grid.height_squares(size) >= 1, size


def test_height_rounds_up_because_the_question_is_what_has_to_clear_it():
    """Four feet of Small is one square; eight feet of Medium is two, not one and a
    half. A ceiling either clears a creature or does not."""
    assert grid.height_squares("small") == 1      # 4 ft
    assert grid.height_squares("medium") == 2     # 8 ft
    assert grid.height_squares("large") == 4      # 16 ft
    assert grid.height_squares("tiny") == 1       # 2 ft, and never zero


def test_a_long_creature_is_not_as_tall_as_it_is_long():
    """Large (tall) and Large (long) carry the same "8 to 16 ft" band in the source, and
    the difference is whether that dimension stands up. A horse is Large and is not
    sixteen feet tall, so a long creature gets its space instead."""
    assert grid.height_squares("large", "tall") == 4
    assert grid.height_squares("large", "long") == 2
    assert grid.height_ft("large", "long") == 10


def test_a_creature_that_knows_its_own_height_overrides_the_table():
    """The source says the bands are typical and that exceptions exist, so the table is
    a default and not a law. A nine-foot Medium is legal in a way that a Medium with a
    ten-foot space is not."""
    assert grid.height_squares("medium", override=9) == 2
    assert grid.height_squares("medium", override=11) == 3
    assert grid.height_ft("medium", override=9) == 9


def test_volume_is_the_footprint_stacked():
    """Large is 2x2 on the floor and four squares of air, so sixteen cells."""
    cells = grid.volume((0, 0), "large", level=0)
    assert len(cells) == len(grid.footprint((0, 0), "large")) * 4 == 16
    assert {(x, y) for x, y, _z in cells} == set(grid.footprint((0, 0), "large"))
    assert {z for _x, _y, z in cells} == {0, 1, 2, 3}


def test_a_volume_stands_on_the_level_it_is_given():
    """A spider clinging twenty feet up is on level 4, and its feet are there."""
    assert min(z for _x, _y, z in grid.volume((1, 1), "medium", level=4)) == 4


# --- the distance rule ----------------------------------------------------------------

def test_two_dimensional_distance_did_not_move():
    """The third axis was added to `distance` rather than beside it, so this is the
    check that every existing answer survived. 2,401 pairs, against the arithmetic the
    module used before."""
    def before(a, b):
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        diagonals, straights = min(dx, dy), max(dx, dy) - min(dx, dy)
        return grid.SQUARE_FT * (straights + diagonals + diagonals // 2)

    for a in itertools.product(range(7), repeat=2):
        for b in itertools.product(range(7), repeat=2):
            assert grid.distance(a, b) == before(a, b), (a, b)


def test_a_point_without_a_third_coordinate_still_means_the_ground():
    """Every position in the app was a two-tuple before this, and most still are. A save
    written before height existed must load without a migration."""
    assert grid.distance((0, 0), (3, 0)) == grid.distance((0, 0, 0), (3, 0, 0))
    assert grid.distance((0, 0), (0, 0, 2)) == 10


def test_the_third_axis_is_the_same_rule_as_the_other_two():
    """The house rule, pinned. Straight up costs five feet a square; a step that climbs
    and moves at once is a diagonal like any other, so the first costs five and the
    second ten; and moving on all three axes at once is still one diagonal step."""
    assert grid.distance((0, 0, 0), (0, 0, 3)) == 15
    assert grid.distance((0, 0, 0), (1, 0, 1)) == 5
    assert grid.distance((0, 0, 0), (2, 0, 2)) == 15
    assert grid.distance((0, 0, 0), (1, 1, 1)) == 5


def test_the_box_gap_agrees_with_comparing_every_cell():
    """`distance_between` computes the gap on each axis instead of comparing all cells,
    because a pair of Colossal creatures is 468 cells against 468 and the old loop would
    ask 219,024 questions to answer one reach check. The two must agree exactly, so this
    brute-forces the enumeration it replaced across sizes, offsets and levels."""
    sizes = ("tiny", "small", "medium", "large")
    for a_size, b_size in itertools.product(sizes, repeat=2):
        for az, bz in itertools.product(range(4), repeat=2):
            for ax, bx in itertools.product(range(0, 7, 3), repeat=2):
                want = min(grid.distance(p, q)
                           for p in grid.volume((ax, 0), a_size, az)
                           for q in grid.volume((bx, 2), b_size, bz))
                assert grid.distance_between((ax, 0, az), a_size,
                                             (bx, 2, bz), b_size) == want


def test_two_creatures_on_one_floor_measure_what_they_always_did():
    """Both standing on the ground overlap on the vertical axis, so the gap there is
    zero and the answer is the old one. This is what makes the change invisible to every
    scene that has no height in it."""
    for a_size, b_size in itertools.product(("small", "medium", "large", "huge"),
                                            repeat=2):
        for ax, ay, bx, by in itertools.product(range(0, 9, 2), repeat=4):
            flat = min(grid.distance(p, q)
                       for p in grid.footprint((ax, ay), a_size)
                       for q in grid.footprint((bx, by), b_size))
            assert grid.distance_between((ax, ay), a_size, (bx, by), b_size) == flat


# --- what it answers that nothing could answer before ---------------------------------

def test_the_spider_on_the_ceiling_is_out_of_reach():
    """The question the rules imply and never state. A Medium character fills the ten
    feet above their square, so a climber ten feet up is one square away — swattable —
    and one twenty feet up is fifteen feet away and is not.

    PF1e has no vertical reach rule at all: a Paizo thread on monster height and reach
    settles on treating a creature's space as a cube and closes with no developer having
    resolved it. This is that reading, made arithmetic.
    """
    pc = (5, 5, 0)
    reach = grid.natural_reach("medium")

    assert grid.distance_between(pc, "medium", (5, 5, 2), "medium") == 5
    assert grid.distance_between(pc, "medium", (5, 5, 2), "medium") <= reach

    assert grid.distance_between(pc, "medium", (5, 5, 4), "medium") == 15
    assert grid.distance_between(pc, "medium", (5, 5, 4), "medium") > reach


def test_an_ogre_reaches_higher_than_a_man():
    """Reach and height are different columns and both matter. An ogre is four squares
    tall, so its head is at the top of the fourth square and the spider clinging one
    square above it is five feet away — where a man had to measure fifteen. With ten feet
    of reach that is comfortably its business, and the same spider is out of the man's."""
    ogre, man, spider = (5, 5, 0), (6, 5, 0), (5, 5, 4)
    assert grid.distance_between(ogre, "large", spider, "medium") == 5
    assert grid.distance_between(ogre, "large", spider, "medium") <= \
        grid.natural_reach("large")
    assert grid.distance_between(man, "medium", spider, "medium") == 15
    assert grid.distance_between(man, "medium", spider, "medium") > \
        grid.natural_reach("medium")


def test_the_zone_words_gained_the_vertical_for_nothing():
    """`zone_between` derives engaged/near/far from measured distance, so it answers
    about height without having been told height exists — the same way it gained the map
    without the intent protocol changing. Nothing in `gm/prompts.py` has to learn a word.
    """
    pc = (5, 5, 0)
    assert grid.zone_between(pc, "medium", (5, 5, 0), "medium") == "engaged"
    assert grid.zone_between(pc, "medium", (5, 5, 4), "medium") == "near"
    assert grid.zone_between(pc, "medium", (5, 5, 12), "medium") == "far"
