"""The ground a fight happens on, and the fact that it used to be nowhere in particular.

Measured 2026-09-14. `_lay_battlefield` laid a bare `Grid()` — twenty by twenty of open
floor — and `end_encounter` threw it away, so:

  * a brawl in a cellar had the same geometry as one in a meadow;
  * the only `blocked` square that ever existed was one a spell had conjured, because
    `engine.py:630` is the single writer of that set;
  * the place graph knew the party was in the cellar and the grid had never heard of it.

A place has a shape now, derived from its own id the way its spot list already is, so the
market has the same stalls in every session on every machine and not a byte of it is saved.

**A place is one room.** Nothing here generates a building: the house is the place graph,
and `places.mint` has always made a cellar a child place of the house above it. This
answers one question — what is underfoot and what is in the way, right here.
"""
from __future__ import annotations

from rules import floorplan, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

MARKET = "5bbd0c40345f~urban:the-market"
TAVERN = "5bbd0c40345f~urban:the-tavern"
SUMP = "nowhere~underground:the-sump"


def _plan(place_id):
    return floorplan.for_place(place_id, places.terrain_of(place_id))


# --- the same room every time ---------------------------------------------------------

def test_a_place_lays_out_the_same_way_every_time():
    """The whole reason this is derived rather than stored. `places._seed` is a SHA-256
    and not `hash()` for exactly this: Python salts string hashing per process, so the
    same town would rearrange itself after every restart."""
    a, b = _plan(MARKET), _plan(MARKET)
    assert a.blocked == b.blocked and a.difficult == b.difficult and a.floor == b.floor
    assert (a.width, a.height, a.ceiling) == (b.width, b.height, b.ceiling)


def test_two_places_are_not_the_same_room():
    assert _plan(MARKET).blocked != _plan(TAVERN).blocked


def test_nothing_is_saved_to_get_this():
    """A plan is a pure function of the id and the ground: entities in, grid out. If it
    ever needed scene state the save would have to carry it, and every campaign written
    before today would lose its rooms."""
    import inspect

    sig = inspect.signature(floorplan.for_place)
    assert list(sig.parameters) == ["place_id", "terrain"], sig
    assert _plan(MARKET).blocked == floorplan.for_place(
        MARKET, places.terrain_of(MARKET)).blocked


# --- the room is actually shaped ------------------------------------------------------

def test_a_fight_indoors_has_walls_in_it_now():
    """The measurement this file exists for: before, this set was empty unless a spell
    had filled it."""
    assert _plan(TAVERN).blocked, "the tavern is an empty field again"


def test_a_tavern_has_a_ceiling_and_a_market_does_not():
    """Ten feet of headroom is what makes a room a room: a flier can get one square up
    and no further, which is the difference between an indoor fight and an outdoor one."""
    assert _plan(TAVERN).ceiling == floorplan.LOW
    assert _plan(MARKET).ceiling is None


def test_the_ground_can_rise():
    """The heightmap, and the reason higher ground is now reachable without flying: a
    cart in the market, a wall-walk over the gate."""
    assert any(v > 0 for v in _plan(MARKET).floor.values())


def test_headroom_is_measured_from_the_square_you_are_on():
    """A dais in a cellar has less air over it than the flagstones beside it, which is
    why the floor and the ceiling are two numbers and not one."""
    g = _plan(TAVERN)
    flat = next(p for p in [(x, y) for x in range(1, g.width - 1)
                            for y in range(1, g.height - 1)]
                if g.ground(p) == 0 and g.passable(p))
    g.floor[flat] = 1
    assert g.headroom(flat) == g.ceiling      # 0 + ceiling - 1, then one higher floor
    g.floor.pop(flat)
    assert g.headroom(flat) == g.ceiling - 1


def test_a_place_nobody_has_a_shape_for_falls_through_to_open_ground():
    """The right failure. An unknown room — one World Bible authored, one the fiction
    founded — is a clearing until somebody says otherwise, and a clearing is exactly what
    every fight in this game used to get."""
    unknown = floorplan.shape_for("whatever~planar:somewhere-strange", "planar")
    assert unknown is floorplan.OPEN
    assert not _plan("whatever~planar:somewhere-strange").blocked


def test_the_scatter_is_not_a_stripe():
    """Written after the first version laid one. The generator's numbers came off the
    LOW bits of a linear congruential sequence, and those cycle with a period of eight —
    `n % 8` ran 6,7,4,5,2,3,0,1 and repeated for ever. A sump asking for ten squares of
    standing water got two, because every draw landed in the same few columns. A plan
    that looks scattered and is really a stripe never announces itself, so this counts
    what was asked for against what arrived."""
    g = _plan(SUMP)
    shape = floorplan.shape_for(SUMP, "underground")
    assert len(g.difficult) >= shape.rough - 1, (len(g.difficult), shape.rough)
    assert len({p[0] for p in g.difficult}) > 2, "every rough square is in two columns"


# --- and the fight is laid out on it --------------------------------------------------

def _fight_at(place_id):
    s = Scene(location_id="5bbd0c40345f")
    s.at = place_id
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc, zone="near")
    foe = instantiate("guildhand", scene=s, name="Foe")
    s.add(foe, zone="near")
    e = Engine(s, Dice(seed=3), world=None)
    e.run(e.validate([{"op": "begin_encounter", "actor": pc.ref, "because": "t",
                       "params": {"sides": {"pc": [pc.ref], "them": [foe.ref]}}}],
                     origin="author:test"))
    return s, e, pc, foe


def test_a_fight_is_laid_out_on_the_place_the_party_is_standing_in():
    """`_lay_battlefield` asks the place for its ground instead of laying a blank field.
    The tavern is twelve by ten with a ceiling; the old default was twenty by twenty of
    nothing."""
    s, _e, _pc, _foe = _fight_at(TAVERN)
    assert (s.grid.width, s.grid.height) == (12, 10)
    assert s.grid.ceiling == floorplan.LOW
    assert s.grid.blocked


def test_nobody_is_laid_out_inside_a_wall():
    """The defect that arrives with the walls. The battlefield is laid by zone and row,
    and that arithmetic was written against an empty field — so against a room with
    stalls in it, it will stand a guard inside one. A creature in a blocked square cannot
    be routed to and cannot be left."""
    for place in (MARKET, TAVERN, SUMP):
        s, _e, _pc, _foe = _fight_at(place)
        for ref, spot in s.positions.items():
            assert s.grid.passable(tuple(spot[:2])), (place, ref, spot)


def test_a_flier_indoors_stops_at_the_ceiling():
    """Ten feet of air is one square of flying. The refusal names the ceiling rather
    than the creature, because the creature is perfectly capable."""
    s, e, _pc, foe = _fight_at(TAVERN)
    spot = s.positions[foe.ref]
    # Give it wings, so the only thing that can stop it is the roof.
    from unittest import mock

    with mock.patch.object(type(foe), "can_move_vertically", lambda _self: "fly"):
        assert e._cannot_leave_the_ground(foe, spot, (spot[0], spot[1], 1)) == "", \
            "one square of flying is inside a ten-foot ceiling"
        too_high = e._cannot_leave_the_ground(foe, spot, (spot[0], spot[1], 5))
        assert "ceiling" in too_high.lower(), too_high

    # And without them the refusal is about the creature, not the roof — two different
    # sentences for two different reasons, which is what makes either one actionable.
    grounded = e._cannot_leave_the_ground(foe, spot, (spot[0], spot[1], 1))
    assert "no way up" in grounded.lower(), grounded


def test_the_room_survives_a_save():
    """The silent loss. The grid's terrain sets have always been saved; the heightmap and
    the ceiling arrived with this stage and the serialiser knew nothing about them, so a
    campaign put down mid-fight came back with its raised ground gone and its roof open —
    which hands a flier unlimited air and quietly takes everybody's higher ground away.

    Saved rather than re-derived from the place id, because `floorplan` lays the room but
    does not own it afterwards: a spell can raise ground and `engine.py:630` can wall a
    doorway, so what is on the board at the end of a round is not always what the plan
    said.
    """
    from play.campaign import _grid

    before = _plan(TAVERN)
    before.floor[(3, 3)] = 2
    raw = {
        "width": before.width, "height": before.height,
        "difficult": sorted(before.difficult), "blocked": sorted(before.blocked),
        "obscuring": sorted(before.obscuring),
        "floor": {f"{x},{y}": v for (x, y), v in before.floor.items()},
        "ceiling": before.ceiling,
    }
    after = _grid(raw)
    assert after.floor == before.floor, "the raised ground did not survive the save"
    assert after.ceiling == before.ceiling, "the roof did not survive the save"
    assert after.headroom((3, 3)) == before.headroom((3, 3))


def test_a_save_written_before_rooms_had_a_shape_still_loads():
    """Every campaign on disk today has a grid with no `floor` and no `ceiling`. They
    load as flat and open, which is exactly what they were."""
    from play.campaign import _grid

    old = _grid({"width": 20, "height": 20, "difficult": [], "blocked": [],
                 "obscuring": []})
    assert old.floor == {} and old.ceiling is None
    assert old.headroom((5, 5)) is None
