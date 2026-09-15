"""A building's floors, as places joined by stairs.

Stage 5 of the distance work. The shape is not invented here: every system that keeps
verticality and stays legible stacks flat maps and puts a transition between them — Foundry
VTT's Levels module, Caves of Qud's strata, Dwarf Fortress's z-levels — and this app was
already half of the way there, because `places.mint` has had a branch for "a different
ground under the same roof: the sewers under a town" since places were written. A storey is
that branch pointing up.

**The storey lives in the place id**, like the ground does, and for the same reason: the id
is the one spatial authority, and a second field recording which floor you are on would be
exactly the fifth authority `docs/places-plan.md` refused. `^` is safe as the separator —
`_slug` strips everything but `[a-z0-9 ]`, a location id is twelve hex characters, and a
terrain is one lower-case word — so nothing else can ever contain it.

What that buys, and the reason this is not a third axis on the tactical grid: a floor is a
map you can draw, a stair is a move you can refuse, and neither needs the grid to know what
is underneath a square. `docs/distance-and-geography.md` §6 has the sweep behind it.
"""
from __future__ import annotations

from rules import floorplan, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

TAVERN = "5bbd0c40345f~urban:the-tavern"
MARKET = "5bbd0c40345f~urban:the-market"


# --- the grammar ----------------------------------------------------------------------

def test_a_storey_is_read_off_the_id_and_the_ground_floor_is_zero():
    assert places.storey_of(TAVERN) == 0
    assert places.storey_of(f"{TAVERN}^1") == 1
    assert places.storey_of(f"{TAVERN}^-1") == -1


def test_the_building_survives_stripping_the_floor_off():
    assert places.base_of(f"{TAVERN}^2") == TAVERN
    assert places.storey_id(f"{TAVERN}^2", -1) == f"{TAVERN}^-1"
    assert places.storey_id(f"{TAVERN}^2", 0) == TAVERN


def test_the_rest_of_the_id_still_parses_on_an_upper_floor():
    """The storey rides on the tail, so everything that reads the head goes on working —
    which is what makes this additive rather than a migration. `terrain_of` IS
    `scene.biome`, and an upstairs room is still urban."""
    upstairs = f"{TAVERN}^1"
    assert places.terrain_of(upstairs) == "urban"
    assert places.location_of(upstairs) == "5bbd0c40345f"


def test_a_save_written_before_storeys_reads_as_the_ground_floor():
    """Every `at` on disk today has no `^` in it, and answers 0, which is true of all of
    them."""
    assert places.storey_of("5bbd0c40345f~urban:the-market") == 0
    assert places.storey_of("") == 0


# --- which buildings have floors --------------------------------------------------------

def test_outdoors_has_no_upstairs():
    """A market has no first floor. "Indoors" is asked of `floorplan` — a shape with a
    ceiling is a room — so there is one source for it and a tavern cannot be indoors for
    stairs and outdoors for flying."""
    assert places.storeys(MARKET, "urban") == (0,)
    assert not places.is_indoors(MARKET, "urban")


def test_a_building_has_the_same_floors_every_time():
    """Derived from the building's own id, like its spots. The same tavern is the same
    height in every session and none of it is saved."""
    assert places.storeys(TAVERN, "urban") == places.storeys(TAVERN, "urban")
    assert places.is_indoors(TAVERN, "urban")
    assert len(places.storeys(TAVERN, "urban")) > 1


# --- the stairs -------------------------------------------------------------------------

def test_stairs_only_reach_the_next_floor():
    """You cannot step from the undercroft to the top of the house without passing the
    room between, which is the whole reason these are places joined by stairs rather than
    a coordinate anybody can name."""
    levels = places.storeys(TAVERN, "urban")
    for level in levels:
        here = places.storey_id(TAVERN, level)
        for other in places.stairs_from(here, "urban"):
            assert abs(places.storey_of(other) - level) == 1


def test_the_ground_floor_gains_its_stairs_as_exits():
    """The move vocabulary IS the exit list — the one thing every tradition in the sweep
    agreed on. A floor nothing lists is a floor nobody can be told about."""
    here = next(p for p in places.for_scene("5bbd0c40345f", TAVERN, "urban")
                if p.id == TAVERN)
    reachable = [x for x in here.exits if places.storey_of(x) != 0]
    assert reachable, here.exits
    assert all(abs(places.storey_of(x)) == 1 for x in reachable)


def test_every_floor_is_offered_where_the_party_is_standing():
    found = {places.storey_of(p.id) for p in places.for_scene(
        "5bbd0c40345f", TAVERN, "urban") if places.base_of(p.id) == TAVERN}
    assert found == set(places.storeys(TAVERN, "urban"))


# --- what a floor looks like -------------------------------------------------------------

def test_an_upstairs_room_still_has_a_roof_on_it():
    """The bug this was written to prevent. `the-tavern^1` matches no spot, so without
    the storey being stripped first it falls through to `urban`, comes out **roofless**,
    and a flier leaves through a bedroom ceiling. The sort of wrong that only shows up
    when somebody tries it."""
    assert floorplan.shape_for(f"{TAVERN}^1", "urban").ceiling is not None
    assert floorplan.shape_for(f"{TAVERN}^-1", "urban").ceiling is not None


def test_a_floor_is_not_the_room_below_it():
    """Upper rooms are smaller and more divided than the hall you walk into, and derived
    from the ground floor's own shape so a change to the tavern reaches its bedrooms."""
    ground = floorplan.shape_for(TAVERN, "urban")
    upper = floorplan.shape_for(f"{TAVERN}^1", "urban")
    assert (upper.width, upper.height) != (ground.width, ground.height)
    assert upper.about != ground.about


def test_two_floors_of_one_building_are_different_rooms():
    a = floorplan.for_place(TAVERN, "urban")
    b = floorplan.for_place(f"{TAVERN}^1", "urban")
    assert a.blocked != b.blocked


# --- and the party can walk up them --------------------------------------------------------

def _at_the_tavern():
    s = Scene(location_id="5bbd0c40345f")
    s.at = TAVERN
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=None)
    e.place_party(s.at)
    return s, e, pc


def test_the_party_can_walk_upstairs():
    """End to end through the real travel op, which needed no change at all: a storey is
    a place, and travel has always moved between places."""
    s, e, pc = _at_the_tavern()
    raw = {"op": "travel", "actor": pc.ref, "because": "t",
           "params": {"place": "the upper floor of the tavern"}}
    e.run(e.validate([raw], origin="author:test"))
    assert places.storey_of(s.at) == 1
    assert places.base_of(s.at) == TAVERN


def test_a_floor_the_building_does_not_have_is_refused_with_the_ones_it_does():
    """The courtesy the place graph already extends to every destination: name what
    exists rather than failing silently.

    Raised at *validate* time rather than returned as a refusal, which is the engine's own
    arrangement — "the legality check names the fix at validate time, where the model can
    act on it". What matters for storeys is that the list it offers now includes the
    floors, so a model that asked for the wrong one is told the right ones.
    """
    import pytest

    from rules.intents import IntentError

    s, e, pc = _at_the_tavern()
    raw = {"op": "travel", "actor": pc.ref, "because": "t",
           "params": {"place": "the belfry"}}
    with pytest.raises(IntentError) as caught:
        e.run(e.validate([raw], origin="author:test"))
    said = str(caught.value)
    assert "the belfry" in said
    assert "the upper floor of the tavern" in said, said
    assert s.at == TAVERN, "the party moved anyway"


def test_a_flier_cannot_leave_by_the_ceiling_instead_of_the_stairs():
    """The reason a storey is a place and not four more levels of the grid. A ten-foot
    room is one square of air, so the way to the floor above is the staircase — the
    engine does not have to know what is over a square to say so."""
    s, e, pc = _at_the_tavern()
    s.grid = floorplan.for_place(s.at, "urban")
    spot = s.positions.get(pc.ref) or (3, 3)
    s.positions[pc.ref] = spot
    from unittest import mock

    with mock.patch.object(type(pc), "can_move_vertically", lambda _self: "fly"):
        refused = e._cannot_leave_the_ground(pc, spot, (spot[0], spot[1], 4))
    assert "ceiling" in refused.lower(), refused


def test_a_floor_cannot_be_reached_without_the_stairs_to_it():
    """Found by reading what the app offered a live campaign, not by a failing test.

    Standing in the market, the party was offered "the top floor of the temple" and could
    simply be there. The place graph inside a settlement is deliberately a clique — "a
    settlement is not a maze" — and `_op_travel` has always resolved a destination by NAME
    among the places within reach rather than by walking exits, which was harmless while
    every exit list held everything. Storeys are the first edges in this graph that mean
    something, so floors are checked against them and ground level is left alone.
    """
    s, e, pc = _at_the_tavern()
    s.at = MARKET
    e.place_party(s.at)

    raw = {"op": "travel", "actor": pc.ref, "because": "t",
           "params": {"place": "the upper floor of the tavern"}}
    res = e.run(e.validate([raw], origin="author:test"))
    tell = " ".join(o.tell for o in res.outcomes)
    assert "not reached from here" in tell, tell
    assert "the tavern" in tell, "the refusal does not say which door the stairs are behind"
    assert s.at == MARKET, "the party teleported up a staircase it never entered"


def test_the_ground_floor_of_a_town_is_still_a_clique():
    """The other half, and deliberately unchanged: a settlement is not a maze. Only the
    stairs are a real edge."""
    s, e, pc = _at_the_tavern()
    s.at = MARKET
    e.place_party(s.at)
    raw = {"op": "travel", "actor": pc.ref, "because": "t",
           "params": {"place": "the tavern"}}
    e.run(e.validate([raw], origin="author:test"))
    assert s.at == TAVERN


def test_the_stairs_go_both_ways():
    s, e, pc = _at_the_tavern()
    for want, expect in (("the upper floor of the tavern", 1), ("the tavern", 0)):
        raw = {"op": "travel", "actor": pc.ref, "because": "t",
               "params": {"place": want}}
        e.run(e.validate([raw], origin="author:test"))
        assert places.storey_of(s.at) == expect, (want, s.at)
