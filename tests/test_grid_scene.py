"""The grid, wired into a scene.

`rules/grid.py` is geometry and knows nothing about actors. This is the other half: where
everybody is standing, what a move costs them, and — the part that decides whether any of
it was worth building — that a scene *without* a map behaves exactly as it did before
there was one. The grid had to arrive without changing a line of the intent protocol,
because every GM prompt in the app is written in engaged / near / far.

The trick that made that possible: zones stay, and a scene with a map re-derives them from
measured distance instead of taking the GM's word. The model keeps saying "near"; when the
square it also gave is forty feet away, the square wins.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


def scene_with_map(width=20, height=20, **terrain):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(width, height, **terrain))
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    s.add(instantiate("thug", scene=s, name="the thug"), at=(9, 5))
    return s


def engine_with_map(**terrain):
    s = scene_with_map(**terrain)
    e = Engine(s, Dice(seed=42))
    return e


def fight(engine):
    """Start an encounter, because the speed limit only applies inside one."""
    engine.scene.initiative = [("pc", 20), ("c1", 10)]
    engine.scene.turn = 0
    return engine


# --- a scene that has no map is not a broken scene ---------------------------------------

def test_a_scene_without_a_grid_still_moves_by_zone():
    """The behaviour every existing save and every GM prompt depends on."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=42))

    res = e.run(e.validate([{"op": "move", "actor": "pc", "because": "closing in",
                             "params": {"zone": "engaged"}}]))
    assert s.zones["pc"] == "engaged"
    assert "engaged" in res.outcomes[0].tell
    assert not s.has_grid


def test_a_square_on_a_mapless_scene_is_refused_rather_than_ignored():
    """Silently dropping the square would leave the GM believing it had positioned
    somebody, and every later intent would be reasoning about a square nobody is on."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=42))
    with pytest.raises(IntentError, match="no map"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "near", "square": [3, 3]}}])


def test_distance_on_a_mapless_scene_is_none_and_not_zero():
    """"We are not tracking that" and "they are touching" are different answers. A silent
    zero makes every reach check succeed on a scene with no map."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    assert s.distance_between("pc", "c1") is None


# --- positions ------------------------------------------------------------------------------

def test_the_scene_measures_between_two_creatures():
    s = scene_with_map()
    assert s.distance_between("pc", "c1") == 20         # (5,5) to (9,5)


def test_occupied_squares_cover_a_big_creature_whole_body():
    """An ogre is four squares of obstacle, not one. Routing around only its anchor walks
    everybody straight through the other three."""
    s = scene_with_map()
    s.actors["c1"].size = "large"
    assert {(9, 5), (10, 5), (9, 6), (10, 6)} <= s.occupied()


def test_a_corpse_stops_being_an_obstacle():
    s = scene_with_map()
    s.actors["c1"].add_condition("dead")
    assert (9, 5) not in s.occupied()


def test_a_creature_does_not_block_itself():
    s = scene_with_map()
    assert (5, 5) not in s.occupied(ignore="pc")


# --- zones, re-derived rather than believed --------------------------------------------------

def test_zones_are_measured_when_there_is_a_map():
    s = scene_with_map()
    s.positions["c1"] = (6, 5)
    assert s.resync_zones()["c1"] == "engaged"
    s.positions["c1"] = (11, 5)
    assert s.resync_zones()["c1"] == "near"
    s.positions["c1"] = (18, 5)
    assert s.resync_zones()["c1"] == "far"


def test_the_square_wins_when_the_gm_contradicts_itself():
    """A model asked for a zone and a square will eventually give two that disagree. The
    square is checkable and the word is not, so the square is what the engine keeps."""
    e = engine_with_map()
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "backing off",
                       "params": {"zone": "engaged", "square": [15, 5]}}]))
    assert e.scene.positions["pc"] == (15, 5)
    assert e.scene.zones["c1"] == "near"                # 30 ft from the thug, not engaged


# --- moving, through the engine ------------------------------------------------------------

def test_a_move_reports_what_it_cost():
    e = engine_with_map()
    res = e.run(e.validate([{"op": "move", "actor": "pc", "because": "closing",
                             "params": {"zone": "engaged", "square": [8, 5]}}]))
    assert e.scene.positions["pc"] == (8, 5)
    assert res.outcomes[0].effects[0]["feet"] == 15
    assert "15 ft" in res.outcomes[0].tell


def test_a_move_beyond_your_speed_is_refused_with_the_number():
    """"You can't move there" with no distance in it is exactly the GM ruling this engine
    exists to replace.

    50 feet, not the 45 of the straight line: the thug is standing at (9,5) and the route
    has to step around them. The number in the refusal is the one the character would
    actually have to pay."""
    e = fight(engine_with_map())
    with pytest.raises(IntentError, match="50 ft away.*30 ft of movement"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "far", "square": [14, 5]}}])


def test_speed_is_only_counted_inside_a_fight():
    """Walking across a village is not a tactical decision, and making the GM issue six
    move intents to cross a room would be a rules engine getting in the way."""
    e = engine_with_map()                                # no initiative: not an encounter
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "crossing the room",
                       "params": {"zone": "far", "square": [17, 12]}}]))
    assert e.scene.positions["pc"] == (17, 12)


def test_too_far_and_no_way_through_are_different_refusals():
    """They lead to different next moves: one wants a double move, the other wants a
    different route."""
    walled = engine_with_map(blocked={(7, y) for y in range(20)})
    fight(walled)
    with pytest.raises(IntentError, match="no route"):
        walled.validate([{"op": "move", "actor": "pc",
                          "params": {"zone": "near", "square": [8, 5]}}])


def test_you_cannot_stand_in_a_wall():
    e = fight(engine_with_map(blocked={(6, 5)}))
    with pytest.raises(IntentError, match="is solid"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "near", "square": [6, 5]}}])


def test_you_cannot_stand_where_somebody_already_is():
    e = fight(engine_with_map())
    with pytest.raises(IntentError, match="is taken"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "engaged", "square": [9, 5]}}])


def test_you_cannot_walk_off_the_map():
    e = fight(engine_with_map())
    with pytest.raises(IntentError, match="off the map"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "far", "square": [99, 99]}}])


def test_difficult_terrain_costs_a_move_its_range():
    """Six squares of mud at 10 feet each is 60 feet. A 30-foot move gets three of them."""
    e = fight(engine_with_map(difficult={(x, 5) for x in range(6, 12)}))
    with pytest.raises(IntentError, match="ft away"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "near", "square": [10, 5]}}])
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "wading in",
                       "params": {"zone": "near", "square": [8, 5]}}]))
    assert e.scene.positions["pc"] == (8, 5)


def test_the_route_costs_what_the_route_costs_not_the_straight_line():
    """Around a wall is further than through it, and the character pays for around."""
    e = engine_with_map(blocked={(6, y) for y in range(4, 20)})
    res = e.run(e.validate([{"op": "move", "actor": "pc", "because": "round the corner",
                             "params": {"zone": "near", "square": [7, 5]}}]))
    assert res.outcomes[0].effects[0]["feet"] > 10       # 10 ft as the crow flies


# --- armour, which is why speed is not a constant ----------------------------------------------

def test_heavy_armour_slows_you_to_twenty_feet():
    """Core Rulebook table 7-6: 30 becomes 20 and 20 becomes 15. Neither is two thirds of
    the other, which is why this is a lookup and not a fraction."""
    a = load_pc("fixtures/pc-kesst.json")
    a.armour = "full plate"
    assert a.speed_feet == 20
    a.speed = 20
    assert a.speed_feet == 15


def test_light_armour_does_not():
    a = load_pc("fixtures/pc-kesst.json")
    a.armour = "chain shirt"
    assert a.speed_feet == 30


def test_being_entangled_halves_what_is_left():
    a = load_pc("fixtures/pc-kesst.json")
    a.armour = "full plate"
    a.add_condition("entangled")
    assert a.speed_feet == 10                            # 30 -> 20 -> 10


def test_speed_rounds_down_to_a_whole_square():
    """22 feet crosses four squares, not four and a bit, and carrying the remainder makes
    the fifth square arrive one move early."""
    a = load_pc("fixtures/pc-kesst.json")
    a.speed = 22
    assert a.speed_feet == 20


# --- the shapes a model writes a square in ---------------------------------------------------------

@pytest.mark.parametrize("written", [[3, 4], (3, 4), "3,4", "(3, 4)",
                                     {"col": 3, "row": 4}, ["3", "4"]])
def test_a_square_is_read_however_the_model_wrote_it(written):
    """A model asked for coordinates returns a list, a dict or a string depending on the
    phase of the moon, and all of them mean the same square."""
    e = engine_with_map()
    intents = e.validate([{"op": "move", "actor": "pc",
                           "params": {"zone": "near", "square": written}}])
    assert intents[0].params["square"] == (3, 4)


def test_a_square_that_is_not_a_square_says_so():
    e = engine_with_map()
    with pytest.raises(IntentError, match="must be a square"):
        e.validate([{"op": "move", "actor": "pc",
                     "params": {"zone": "near", "square": "over by the door"}}])


# --- persistence ---------------------------------------------------------------------------------------

@override_settings()
def test_a_map_survives_a_save(tmp_path, settings):
    """Squares come back from JSON as lists, and a list is unhashable — every set
    operation in `rules.grid` would raise. That is a crash at load rather than a wrong
    answer, but only for saves that carry terrain, so it would ship perfectly happily
    until the first map with a wall in it."""
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.scene.grid = Grid(12, 14, blocked={(3, 3)}, difficult={(4, 4), (5, 4)},
                        obscuring={(6, 6)})
    c.scene.positions["pc"] = (2, 2)
    c.save()

    back = campaign_mod.Campaign.load(c.path())
    assert back.scene.grid.width == 12 and back.scene.grid.height == 14
    assert back.scene.grid.blocked == {(3, 3)}
    assert back.scene.grid.difficult == {(4, 4), (5, 4)}
    assert back.scene.positions["pc"] == (2, 2)
    # The operation that raises if the squares came back as lists.
    assert back.scene.grid.passable((0, 0))


@override_settings()
def test_a_save_from_before_the_grid_still_loads(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.save()
    back = campaign_mod.Campaign.load(c.path())
    assert back.scene.grid is None
    assert not back.scene.has_grid


def test_speed_survives_a_save():
    a = load_pc("fixtures/pc-kesst.json")
    a.speed = 20
    assert from_dict(to_dict(a)).speed == 20


def test_a_sheet_written_before_speed_existed_defaults_rather_than_failing():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.pop("speed", None)
    assert from_dict(d).speed == 30


# --- what crosses the wire to the browser ----------------------------------------------------

def test_the_state_carries_no_grid_when_there_is_no_map():
    """Every scene in the app before this one. `None` rather than an empty grid, so the
    page can tell "no map here" from "a map with nothing on it"."""
    from play.views import _grid_state

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    assert _grid_state(s) is None


def test_the_state_carries_where_the_character_can_actually_go():
    """Computed by the engine and sent down, never worked out in the browser. Two
    implementations of the alternating diagonal rule would eventually disagree, and the one
    on screen is the one the player would believe."""
    from play.views import _grid_state

    s = scene_with_map()
    out = _grid_state(s)
    assert out["speed"] == 30
    assert out["reachable"]
    # Four elements since stage 7: the level a destination lands you on rides with the
    # cost, because a square is only half of where somebody ends up — walking onto a
    # dais is walking up onto it, and the map has to be able to say which those are.
    costs = {(c, r): cost for c, r, cost, _level in out["reachable"]}
    assert costs[(5, 4)] == 5
    assert max(costs.values()) <= 30


def test_the_reachable_set_stops_at_a_wall():
    from play.views import _grid_state

    s = scene_with_map(blocked={(7, y) for y in range(20)})
    out = _grid_state(s)
    assert not [sq for sq in out["reachable"] if sq[0] > 7]


def test_a_character_who_cannot_act_is_offered_nowhere():
    """An unconscious character with a ring of reachable squares painted around them is
    the page telling the player they have a move they do not have."""
    from play.views import _grid_state

    s = scene_with_map()
    s.pc().add_condition("unconscious")
    assert _grid_state(s)["reachable"] == []


def test_actors_carry_their_square_and_their_size():
    """A Large creature is four squares of token. Sending only the anchor draws an ogre
    the same size as a goblin, which is wrong in exactly the way a map is meant to fix."""
    s = scene_with_map()
    s.actors["c1"].size = "large"
    from rules.grid import size_squares

    assert size_squares(s.actors["c1"].size) == 2
    assert s.positions["c1"] == (9, 5)


def test_the_state_carries_the_vertical_it_has_been_drawing_since_stage_four():
    """Measured 2026-09-14: rooms gained raised ground, roofs and rails, and every one of
    them stopped at `_grid_state`. A gallery was generated on the server, saved, measured
    and fought over, and the page was sent a flat floor.

    Sent in the same shape as the terrain sets — sorted lists of small integer tuples —
    deliberately, because that shape is renderer-agnostic. The 3D viewport this is
    groundwork for reads exactly this; the flat map is the special case.
    """
    from play.views import _grid_state

    s = scene_with_map()
    s.grid.floor[(3, 3)] = 2
    s.grid.parapet[(3, 4)] = 2
    s.grid.ceiling = 4

    out = _grid_state(s)
    assert [3, 3, 2] in out["floor"]
    assert [3, 4, 2] in out["parapet"]
    assert out["ceiling"] == 4
    # Only the levels something is actually on, so the view offers those and not a
    # spinner from zero to the sky. Ground is always among them.
    assert out["levels"] == [0, 2], out["levels"]


def test_a_flat_room_offers_no_levels_to_choose_between():
    """A level picker over a flat market is a control that does nothing, and the first
    thing a player learns from one is that it does not matter."""
    from play.views import _grid_state

    out = _grid_state(scene_with_map())
    assert out["levels"] == [0]
    assert out["floor"] == [] and out["parapet"] == []
