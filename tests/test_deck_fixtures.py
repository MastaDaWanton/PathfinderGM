"""A ship's rooms laid like a ship, and a quay laid like a quay (2026-11-13).

The owner: "make sure we have some boat/ship specific 3D objects like coils of rope and
masts to populate the maps". Until then a deck was the `deck` terrain's twelve-by-twenty
scatter — four clumps typed barrel or crate and a gallery down one side — so a galley's
deck and a keelboat's were the same room, with no mast to put between you and them, no
rail with the sea past it and no hatch (docs/ships.md promised all three).
"""
from __future__ import annotations

import pytest

from rules import fixtures, floorplan, ships
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from tests.test_map_fixtures import _move

DOCKS = "5bbd0c40345f~urban:the-docks"


def _vessel(kind):
    vid = ships.vessel_id("5bbd0c40345f", kind)
    return ships.Vessel(id=vid, name=ships.name_for(vid), kind=kind,
                        hp=ships.VESSELS[kind]["hp"])


def _aboard(kind, room=0):
    """The party standing in one room of a ship, the way boarding leaves them."""
    v = _vessel(kind)
    s = Scene(location_id="5bbd0c40345f")
    s.vessels = [v.as_dict()]
    s.at = ships.places_of(v)[room].id
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc, zone="near")
    e = Engine(s, Dice(seed=3), world=None)
    e.lay_the_ground()
    return s, e, pc


def _kind(grid, kind):
    return [f for f in grid.fixtures if f["kind"] == kind]


def _squares(grid, kind):
    return {tuple(p) for f in _kind(grid, kind) for p in f["squares"]}


ROOMS = [(kind, i, label) for kind, row in ships.VESSELS.items()
         for i, (label, _a, _in) in enumerate(row["places"])]


@pytest.mark.parametrize("kind,room,label", ROOMS)
def test_every_room_of_every_ship_is_a_hull_of_her_own_size(kind, room, label):
    """Ultimate Combat pp.184-185: a keelboat is 20 by 50 ft, a galley 20 by 130. Before
    this every deck was 12 by 20 squares whatever ship it was."""
    s, e, pc = _aboard(kind, room)
    g = s.grid
    beam, length, _m, _h = floorplan.HULLS[kind]
    assert g.width == beam // 5 + 2
    if label in ("the steering deck", "the sterncastle"):
        assert g.height < length // 5 + 2       # a castle is the aft end, not the ship
    else:
        assert g.height == length // 5 + 2
    assert g.height > g.width, "a ship is long and narrow"
    assert (g.ceiling is None) == (label in ("the deck", "the steering deck",
                                             "the sterncastle", "the rigging"))


@pytest.mark.parametrize("kind", list(ships.VESSELS))
def test_every_deck_has_a_mast_a_hatch_and_a_rail_down_both_sides(kind):
    """The three things docs/ships.md says a deck is for: "the mast to put between you
    and them, a rail with the sea past it, below-decks through a hatch"."""
    s, e, pc = _aboard(kind)
    g = s.grid
    masts = _kind(g, "mast")
    assert len(masts) == floorplan.HULLS[kind][2]
    assert {f["squares"][0][0] for f in masts} <= {(g.width - 1) // 2, g.width // 2}, \
        "masts stand on the centre line"
    assert len(_kind(g, "hatch")) == 1
    rail = _squares(g, "rail")
    for y in range(2, g.height - 1):            # every row of the hull past the bow
        assert (0, y) in rail and (g.width - 1, y) in rail, y
    # The rail and the sea are solid to feet, never to eyes: shot across, and the sea
    # covers nobody.
    for p in _squares(g, "sea"):
        assert p in g.blocked and not g.opaque(p)
    assert all(p in g.blocked and not g.opaque(p) for p in rail)
    helm = _kind(g, "helm")
    castle = any(lbl in ("the steering deck", "the sterncastle")
                 for lbl, _a, _i in ships.VESSELS[kind]["places"])
    assert len(helm) == (0 if castle else 1), "the helm is aft, on the castle if she has one"
    if helm:
        assert helm[0]["squares"][0][1] >= g.height - 3
    assert _kind(g, "rope"), "no coil of rope on the deck"


@pytest.mark.parametrize("kind,room,label", ROOMS)
def test_every_walkable_square_of_a_ship_is_reachable_from_the_hatch(kind, room, label):
    """Benches, cargo and masts never close the ship across: everyone can get to the
    hatch, and the rigging is a step up from the deck beside it."""
    s, e, pc = _aboard(kind, room)
    g = s.grid
    walk = {(x, y) for x in range(g.width) for y in range(g.height)
            if (x, y) not in g.blocked and not g.ground((x, y))}
    hatch = _squares(g, "hatch")
    start = next(iter(hatch or walk))
    seen, todo = set(), [start]
    while todo:
        p = todo.pop()
        if p in seen or p not in walk:
            continue
        seen.add(p)
        todo.extend((p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    assert seen == walk, sorted(walk - seen)
    for p in _squares(g, "rigging"):
        assert any((p[0] + dx, p[1] + dy) in walk for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    if label != "the rigging":
        assert hatch, f"{label} has no hatch"


def test_the_rigging_is_climbed_at_the_rigging_dc_of_the_climb_table():
    """CRB p.90, the Climb table, DC 10: "a surface with ledges to hold on to and stand
    on, such as a very rough wall or a ship's rigging". A failed climb stays on deck."""
    s, e, pc = _aboard("sailing ship")
    g = s.grid
    shroud = sorted(_squares(g, "rigging"))[0]
    assert fixtures.climb_onto(g, shroud) == ("the rigging", 10)
    assert g.ground(shroud) == 2
    foot = next(q for q in ((shroud[0], shroud[1] + 1), (shroud[0], shroud[1] - 1))
                if q not in g.blocked and not g.ground(q))
    s.positions[pc.ref] = (*foot, 0)
    _move(e, pc.ref, (*shroud, 2))
    climbed = tuple(s.positions[pc.ref])
    assert climbed in ((*shroud, 2), (*foot, 0)), climbed


def test_the_rail_covers_from_outboard_and_never_along_the_deck():
    """Why the rail is laid on the squares of sea and not on the hull's edge squares: as
    a parapet in the hull (a gallery's lip, the first idea) two people at the same rail
    had cover from each other down the whole length of the ship."""
    s, e, pc = _aboard("warship")
    g = s.grid
    # Nothing but the rail beside or in line with them: once vessel ids carried their kind
    # (2026-11-13) the warship's seed changed, and the 15 ft run first found ended beside
    # her boat and the next began behind a crate — real cover both, not the rail's. This
    # hull has no clear 15 ft stretch, so the pair stands 10 ft apart.
    things = {tuple(p)[:2] for f in g.fixtures if f["kind"] not in ("rail", "sea")
              for p in f["squares"]}
    free = [y for y in range(2, g.height - 1) if (1, y) not in g.blocked
            and not g.ground((1, y))]
    run = next(y for y in free if y + 1 in free and y + 2 in free and not things & (
        {(x, y + d) for x in (1, 2) for d in range(3)} | {(1, y - 1), (1, y + 3)}))
    a, b = (1, run, 0), (1, run + 2, 0)          # both at the port rail, 10 ft apart
    assert g.cover_between(a, "medium", b, "medium") == "none"
    sea = sorted(_squares(g, "sea") | _squares(g, "rail"))
    assert all(g.low[p] == (1 if p in _squares(g, "rail") else -1) for p in sea)


def test_the_reader_names_the_ship_and_walks_to_it():
    """'I climb the rigging', 'go down the hatch', 'hide behind the mast': the closed list
    carries every ship kind, and the existing fixture walk takes them there."""
    for k in ("mast", "rigging", "rope", "hatch", "helm", "capstan", "anchor", "bench",
              "boat", "rail", "sea", "bollard"):
        assert k in fixtures.names()
    s, e, pc = _aboard("sailing ship")
    g = s.grid
    sq, why = fixtures.walk_to(s, "hatch", pc)
    assert sq[:2] in _squares(g, "hatch") and not why
    sq, why = fixtures.walk_to(s, "rigging", pc)
    assert sq[:2] in _squares(g, "rigging") and sq[2] == 2
    sq, why = fixtures.walk_to(s, "mast", pc)
    assert any(max(abs(sq[0] - m[0]), abs(sq[1] - m[1])) == 1 for m in _squares(g, "mast"))
    assert fixtures.held_to_words(g, "barrel", "I climb the rigging") == "rigging"
    said = fixtures.said(g)
    assert "masts" in said and "the rail" in said and "the hatch" in said


def test_the_same_ship_keeps_the_same_deck_and_her_hatch_is_over_the_hold():
    one, _e, _pc = _aboard("sailing ship")
    two, _e, _pc = _aboard("sailing ship")
    assert one.grid.fixtures == two.grid.fixtures
    hold, _e, _pc = _aboard("sailing ship", 2)
    assert _squares(one.grid, "hatch") == _squares(hold.grid, "hatch")


def test_a_ship_room_known_only_by_its_id_still_lays_a_hull():
    """A caller holding only the place id (the brief, the map caption) gets the room's
    likeliest hull rather than the old blank deck."""
    pid = ships.places_of(_vessel("galley"))[1].id        # the oar deck
    shape = floorplan.shape_for(pid, ships.DECK)
    assert (shape.layout, shape.vessel) == ("ship", "galley")


def test_the_docks_have_a_harbour_bollards_rope_and_a_boat_tied_up():
    s = Scene(location_id="5bbd0c40345f")
    s.at = DOCKS
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc, zone="near")
    Engine(s, Dice(seed=3), world=None).lay_the_ground()
    g = s.grid
    names = {f["name"] for f in g.fixtures}
    assert {"the harbour", "a ship's boat", "a bollard"} <= names
    water = _squares(g, "sea")
    assert {(x, g.height - 1) for x in range(g.width)} <= water | _squares(g, "boat")
    for p in _squares(g, "bollard"):
        assert (p[0], p[1] + 1) in water | _squares(g, "boat"), "a bollard stands at the edge"
    assert tuple(s.positions[pc.ref][:2]) not in g.blocked


def test_both_boards_draw_every_ship_kind():
    """The 3D board builds each kind as the thing it is; the flat board's symbols are
    checked for every kind by test_every_fixture_kind_is_drawn_as_itself_on_the_flat_board."""
    from django.conf import settings

    js = (settings.BASE_DIR / "play" / "static" / "js" / "scene3d.js").read_text(
        encoding="utf-8")
    for k in ("mast", "helm", "capstan", "anchor", "bench", "boat", "bollard"):
        assert f'k === "{k}"' in js, k
    for k in ("rope", "hatch", "rigging"):
        assert f'f.kind === "{k}"' in js, k
    assert "WATERY = { sea: true, rail: true }" in js
