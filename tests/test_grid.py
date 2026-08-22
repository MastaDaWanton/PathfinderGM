"""The battlefield in five-foot squares.

`docs/architecture.md` said "initiative and positions, no grid", and zones were enough for
a fight the GM narrated. They stopped being enough the moment anything needed to know
*where*: an attack of opportunity is defined by which squares a creature threatens, a
fireball by which squares it covers, a charge by whether there is a straight lane to run
down. Every one of those was being refused or hand-waved, and hand-waving is how a rules
engine turns back into a chat log.

The measurements this file pins down, each of which a plausible implementation gets wrong:

  - diagonals alternate 5 and 10 feet, so `max(dx, dy) * 5` makes a diagonal retreat free
    and Pythagoras makes every distance a fraction;
  - reach is measured from a creature's whole footprint, so anchor-to-anchor puts a
    Colossal dragon permanently out of arm's reach of somebody touching it;
  - a line drawn along the *edge* of a pillar grazes it and gets through, which is what
    lets you see around one — but a line drawn along the face of a wall does not, and the
    first implementation let sight travel the whole length of a stone wall;
  - difficult terrain makes the shortest path and the cheapest path different, which is
    why movement is Dijkstra and not a flood fill.
"""
from __future__ import annotations

import pytest

from rules import grid as g
from rules.grid import Grid


# --- distance ------------------------------------------------------------------------------

def test_a_straight_line_is_five_feet_a_square():
    assert [g.distance((0, 0), (n, 0)) for n in range(1, 5)] == [5, 10, 15, 20]


def test_diagonals_alternate_five_and_ten():
    """"The first diagonal counts as 5 feet, the second counts as 10 feet, the third as 5."

    `max(dx, dy) * 5` — the obvious implementation — gives 5, 10, 15, 20 here and makes
    running away diagonally strictly better than running away straight."""
    assert [g.distance((0, 0), (n, n)) for n in range(1, 7)] == [5, 15, 20, 30, 35, 45]


def test_distance_does_not_care_which_way_round():
    assert g.distance((3, 7), (9, 2)) == g.distance((9, 2), (3, 7))


def test_a_square_is_no_distance_from_itself():
    assert g.distance((4, 4), (4, 4)) == 0


def test_a_knights_move_is_not_pythagoras():
    """dx 2, dy 1: one diagonal and one straight — 10 feet, not 11.18."""
    assert g.distance((0, 0), (2, 1)) == 10


# --- footprints ------------------------------------------------------------------------------

def test_a_medium_creature_stands_on_one_square():
    assert g.footprint((3, 3), "medium") == [(3, 3)]


def test_a_large_creature_stands_on_four():
    assert set(g.footprint((3, 3), "large")) == {(3, 3), (4, 3), (3, 4), (4, 4)}


def test_a_colossal_creature_stands_on_thirty_six():
    assert len(g.footprint((0, 0), "colossal")) == 36


def test_reach_is_measured_from_the_footprint_not_the_anchor():
    """A Colossal dragon anchored at (0,0) fills six squares. Somebody standing against
    its far edge is touching it; measured anchor to anchor they are 25 feet away and every
    reach check in the game fails while the two are nose to nose."""
    assert g.distance_between((0, 0), "colossal", (6, 5), "medium") == 5
    assert g.distance((0, 0), (6, 5)) == 40


def test_an_ogre_threatens_ten_feet_and_a_horse_five():
    """Both are Large. Reach comes in two shapes and the difference decides who can be
    hit without moving, which is most of what a grid is for."""
    assert g.natural_reach("large", "tall") == 10
    assert g.natural_reach("large", "long") == 5


def test_a_goblin_threatens_the_eight_squares_around_it():
    assert g.threatened_squares((5, 5), "small") == {
        (4, 4), (5, 4), (6, 4), (4, 5), (6, 5), (4, 6), (5, 6), (6, 6)}


def test_a_creature_does_not_threaten_its_own_squares():
    threatened = g.threatened_squares((5, 5), "large")
    assert not threatened & set(g.footprint((5, 5), "large"))


def test_an_ogres_threatened_area_reaches_past_its_own_bulk():
    """A 2x2 body with 10 feet of reach. The four far corners are two diagonals out — 15
    feet — and are not threatened, which is the whole reason this counts by distance
    rather than by a bounding box."""
    threatened = g.threatened_squares((5, 5), "large")
    assert len(threatened) == 28
    assert (7, 7) in threatened                          # one diagonal from (6,6): 5 ft
    assert (3, 3) not in threatened                      # two diagonals from (5,5): 15 ft


def test_something_with_no_reach_threatens_nothing():
    """Tiny and smaller have no natural reach — they have to enter your square."""
    assert g.threatened_squares((5, 5), "tiny") == set()


def test_a_reach_weapon_overrides_natural_reach():
    """Twenty squares, not the twenty-four a 5x5 box would give: the four far corners are
    two diagonals out, which is 15 feet, and a glaive does not reach them."""
    threatened = g.threatened_squares((5, 5), "medium", reach=10)
    assert len(threatened) == 20
    assert (7, 5) in threatened                          # two squares east: 10 ft
    assert (7, 7) not in threatened                      # two diagonals: 15 ft


# --- line of sight ------------------------------------------------------------------------------

def test_you_can_see_around_a_single_pillar():
    """1e draws corner to corner, and a line along the *edge* of a blocking square grazes
    it rather than crossing it. Nudging the corners inward "to be safe" was the first
    implementation and it turned every pillar into a wall."""
    assert Grid(12, 12, blocked={(6, 5)}).line_of_sight((5, 5), (7, 5))


def test_you_cannot_see_through_a_wall():
    wall = Grid(12, 12, blocked={(6, y) for y in range(12)})
    assert not wall.line_of_sight((5, 5), (7, 5))


def test_sight_does_not_travel_along_the_face_of_a_wall():
    """The seam case, and the bug the grazing rule caused. A line run along a grid line
    belongs to the squares on *both* sides of it; grazing works because one of the two is
    open. When both are solid there is nothing to graze past — otherwise sight runs the
    entire length of a stone wall."""
    wall = Grid(12, 12, blocked={(6, y) for y in range(12)})
    assert not wall.line_of_sight((5, 0), (7, 11))


def test_a_doorway_in_a_wall_can_be_seen_through():
    door = Grid(12, 12, blocked={(6, y) for y in range(12) if y != 5})
    assert door.line_of_sight((5, 5), (7, 5))


def test_smoke_blocks_sight_without_blocking_movement():
    smoke = Grid(12, 12, obscuring={(6, y) for y in range(12)})
    assert not smoke.line_of_sight((5, 5), (7, 5))
    assert smoke.passable((6, 5))


def test_open_ground_is_open():
    assert Grid(12, 12).line_of_sight((0, 0), (11, 11))


def test_you_can_always_see_your_own_square():
    assert Grid(4, 4, blocked={(1, 1)}).line_of_sight((1, 1), (1, 1))


# --- movement ------------------------------------------------------------------------------------

def test_a_thirty_foot_move_reaches_six_squares_in_a_straight_line():
    assert Grid(20, 20).reachable((5, 5), 30).get((11, 5)) == 30


def test_a_thirty_foot_move_reaches_only_four_squares_diagonally():
    """Four diagonals are 5 + 10 + 5 + 10 = 30. A fifth would be 35 and is out of reach —
    the whole point of the alternating rule."""
    reached = Grid(20, 20).reachable((5, 5), 30)
    assert reached.get((9, 1)) == 30
    assert (10, 0) not in reached


def test_the_alternating_diagonal_is_tracked_along_the_path_not_rounded_at_the_end():
    """Rounding once at the end is the obvious shortcut and it prices a zig-zag like a
    straight line, which lets a character cross the map for free."""
    zigzag = [(0, 0), (1, 1), (2, 0), (3, 1), (4, 0)]
    assert Grid(20, 20).path_cost(zigzag) == 30          # 5 + 10 + 5 + 10
    assert Grid(20, 20).path_cost([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]) == 20


def test_difficult_terrain_costs_double_to_enter():
    mud = Grid(20, 20, difficult={(6, 5)})
    assert mud.path_cost([(5, 5), (6, 5)]) == 10
    assert mud.path_cost([(5, 5), (6, 4)]) == 5


def test_the_cheapest_path_is_not_always_the_shortest_one():
    """Why this is Dijkstra and not a flood fill. Straight through two squares of mud is
    25 feet; stepping around them diagonally is 20, and a character with 20 feet of speed
    can make it only if the engine knows that."""
    mud = Grid(20, 20, difficult={(6, 5), (7, 5)})
    assert mud.path_cost([(5, 5), (6, 5), (7, 5), (8, 5)]) == 25
    assert mud.reachable((5, 5), 20).get((8, 5)) == 20


def test_you_cannot_walk_through_a_wall():
    wall = Grid(20, 20, blocked={(6, y) for y in range(20)})
    assert (7, 5) not in wall.reachable((5, 5), 60)


def test_you_cannot_cut_a_diagonal_past_a_corner():
    """1e says so in as many words, "even by taking a different diagonal to avoid the
    corner". Slipping between two wall corners is one of the oldest ways to cheat a map."""
    corner = Grid(8, 8, blocked={(4, 3), (3, 4)})
    assert (4, 4) not in Grid(8, 8, blocked={(4, 3), (3, 4)}).reachable((3, 3), 5)
    assert corner.reachable((3, 3), 30).get((4, 4), 999) > 5


def test_another_creature_blocks_a_square():
    occupied = {(6, 5)}
    assert (6, 5) not in Grid(20, 20).reachable((5, 5), 30, occupied=occupied)


def test_a_large_creature_needs_room_for_all_four_of_its_squares():
    """An ogre cannot stand in a one-square gap. Checking only the anchor square is the
    obvious implementation and it walks ogres through doorways they do not fit in."""
    corridor = Grid(10, 10, blocked={(x, 4) for x in range(10)} | {(x, 6) for x in range(10)})
    assert (5, 5) not in corridor.reachable((0, 5), 60, size="large")
    assert (5, 5) in corridor.reachable((0, 5), 60, size="medium")


def test_you_do_not_pay_to_stand_still():
    assert (5, 5) not in Grid(20, 20).reachable((5, 5), 30)


# --- areas of effect -------------------------------------------------------------------------------

def test_a_burst_counts_diagonals_the_same_way_movement_does():
    """A 20-foot burst does not reach four squares out diagonally, because four diagonals
    is 30 feet. A bounding box would catch it and hit six creatures too many."""
    caught = g.burst((10, 10), 20)
    assert (14, 10) in caught                            # four squares east: 20 ft
    assert (13, 13) in caught                            # three diagonals: 5+10+5 = 20 ft
    assert (14, 14) not in caught                        # four diagonals: 30 ft
    assert (15, 10) not in caught                        # five squares east: 25 ft


def test_a_burst_includes_its_own_centre():
    assert (10, 10) in g.burst((10, 10), 20)


def test_a_cone_widens_by_a_square_a_step():
    close = {p for p in g.cone((0, 0), "e", 15) if p[0] == 1}
    far = {p for p in g.cone((0, 0), "e", 15) if p[0] == 2}
    assert len(close) == 3
    assert len(far) == 5


def test_a_cone_points_where_it_is_aimed():
    assert all(p[0] > 0 for p in g.cone((5, 5), "e", 15) if p != (5, 5))
    assert all(p[1] < 5 for p in g.cone((5, 5), "n", 15) if p != (5, 5))


def test_a_diagonal_cone_covers_the_quadrant_it_faces():
    """1e anchors a cone on a corner, so one pointed at a corner is a quarter of the map.
    Every square in it is up and to the right, and none behind the caster."""
    caught = g.cone((5, 5), "ne", 15)
    assert caught
    assert all(p[0] >= 5 and p[1] <= 5 for p in caught)


def test_an_unknown_direction_is_an_error_not_an_empty_cone():
    """An empty set is a spell that hits nobody and says nothing about why."""
    with pytest.raises(KeyError):
        g.cone((0, 0), "northeasterly", 15)


def test_a_line_catches_both_squares_it_clips():
    """Bresenham picks one square per step. A lightning bolt that slips between two squares
    it visibly crosses is one somebody dodged by standing still."""
    bolt = g.line((0, 0), (4, 1), 30)
    assert (2, 0) in bolt and (2, 1) in bolt


def test_a_line_starts_where_it_is_cast_from():
    assert (0, 0) in g.line((0, 0), (4, 1), 30)


def test_a_line_stops_at_its_length():
    assert all(g.distance((0, 0), p) <= 30 for p in g.line((0, 0), (9, 0), 30))


# --- flanking ---------------------------------------------------------------------------------------

def test_two_attackers_on_opposite_sides_flank():
    assert g.flanking((4, 5), (6, 5), (5, 5))


def test_two_attackers_on_opposite_corners_flank():
    assert g.flanking((4, 4), (6, 6), (5, 5))


def test_two_attackers_side_by_side_do_not_flank():
    assert not g.flanking((4, 4), (4, 6), (5, 5))


def test_two_attackers_on_the_same_side_do_not_flank():
    assert not g.flanking((4, 5), (3, 5), (5, 5))


def test_a_bigger_creature_is_harder_to_flank():
    """Against an ogre's 2x2 the two attackers have to be opposite each other across the
    whole body, not merely opposite across one of its squares."""
    assert not g.flanking((4, 5), (6, 5), (5, 5), "large")   # (6,5) is standing *on* it
    assert g.flanking((4, 5), (7, 5), (5, 5), "large")


def test_standing_on_the_target_is_not_flanking_it():
    assert not g.flanking((5, 5), (7, 5), (5, 5))


# --- zones, so nothing that already worked has to change -----------------------------------------------

def test_a_grid_answers_the_same_three_words_the_protocol_speaks():
    """The intent protocol and every GM prompt are written in engaged / near / far. A
    scene with a map answers them from measured distance instead of taking the GM's word,
    and nothing in the protocol had to change to gain a grid."""
    assert g.zone_between((5, 5), "medium", (6, 5), "medium") == "engaged"
    assert g.zone_between((5, 5), "medium", (10, 5), "medium") == "near"
    assert g.zone_between((5, 5), "medium", (15, 5), "medium") == "far"


def test_a_reaching_creature_is_engaged_from_further_out():
    """An ogre ten feet away is in melee with you whether you like it or not."""
    assert g.zone_between((5, 5), "large", (8, 5), "medium") == "engaged"
    assert g.zone_between((5, 5), "medium", (8, 5), "medium") == "near"


def test_adjacency_is_the_short_way_of_saying_five_feet():
    assert g.is_adjacent((5, 5), "medium", (6, 6), "medium")
    assert not g.is_adjacent((5, 5), "medium", (7, 5), "medium")
