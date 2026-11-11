"""Named map fixtures, phase 1 (docs/turn-budget-and-fixtures-plan.md, Part 2).

The owner, 2026-11-11: "we had talked about adding crates and barrels bookshelfs stairs
etc.. lets do that now". Before this the floorplan had no named features at all: a
tavern's bar and its tables were anonymous walls (an archer behind a table could not be
seen, the rule for a low obstacle is cover), and every gallery a ledge-shaped room laid
was unreachable on foot — no stair existed, so a PC with no climb speed was refused "no
way up" on all 16 squares of the tavern's gallery, while the SAME move written as (x, y)
without its level walked straight up.

Phase 1 names the geometry that exists and never moves it: campaigns have people
standing on today's derived maps.
"""
from __future__ import annotations

import json

import pytest

from rules import fixtures, floorplan, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid

TAVERN = "5bbd0c40345f~urban:the-tavern"
LIBRARY = "5bbd0c40345f~urban:the-library"
MARKET = "5bbd0c40345f~urban:the-market"


def _at(place_id, foe=False):
    s = Scene(location_id="5bbd0c40345f")
    s.at = place_id
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc, zone="near")
    e = Engine(s, Dice(seed=3), world=None)
    e.lay_the_ground()
    return s, e, pc


def _move(engine, ref, square):
    raw = {"op": "move", "actor": ref, "because": "t",
           "params": {"who": ref, "square": list(square)}}
    return engine.run(engine.validate([raw], origin="author:test"))


def _kind(grid, kind):
    return [f for f in grid.fixtures if f["kind"] == kind]


# --- the data -------------------------------------------------------------------------

def test_the_fixture_kinds_validate_and_a_bad_one_is_refused_with_the_fix():
    """Every kind declares only properties the engine reads, validated on load the way
    feat documents are: a low obstacle that does not occupy a blocked square, a made-up
    property, or a place row naming a kind nobody wrote would otherwise reach the map."""
    assert fixtures.validate(fixtures.data()) == []
    owner = {"crate", "barrel", "bookshelf", "stair", "table", "counter", "rack", "hearth",
             "chandelier", "cart", "crane", "water", "door", "window"}
    assert owner <= set(fixtures.names())
    bad = {"kinds": {"stool": {"name": "a stool", "plural": "stools", "source": "x",
                               "occupies": ["open"], "form": "box", "cover": "cover",
                               "low": True, "wobbles": True}},
           "places": {"the-tavern": {"solid": ["throne"]}}}
    problems = " ".join(fixtures.validate(bad))
    assert "kinds.stool.wobbles: not a fixture property" in problems
    assert "kinds.stool.low: a low obstacle occupies blocked squares" in problems
    assert "places.the-tavern.solid: no kind called 'throne'" in problems


# --- the safety rule ------------------------------------------------------------------

def _all_places(world):
    seen = {}
    for ent in world.entities.values():
        for p in places.home_set(ent):
            seen.setdefault(p.id, p)
    return list(seen.values())


def test_typing_the_ground_moves_no_square_in_any_real_world(worlds):
    """THE safety rule. Existing campaigns have people standing on today's derived maps,
    so typing must leave every blocked, difficult, raised and railed square exactly where
    the plan put it — checked on every place of every real export, not a sample."""
    for p in _all_places(worlds):
        terrain = p.terrain or places.terrain_of(p.id)
        before = floorplan.for_place(p.id, terrain, getattr(p, "shape", None))
        g = floorplan.for_place(p.id, terrain, getattr(p, "shape", None))
        s = Scene(location_id="t")
        s.grid = g
        fixtures.type_the_ground(s, p.id, terrain, getattr(p, "shape", None))
        # The one change allowed: the rail opens where the stair arrives (a rail is never
        # a square anybody stands in, so no saved position moves for it).
        stairs = {tuple(q) for f in g.fixtures if f["kind"] == "stair" for q in f["squares"]}
        assert (g.blocked, g.difficult, g.floor) == (
            before.blocked, before.difficult, before.floor), p.id
        assert g.parapet == {q: v for q, v in before.parapet.items() if q not in stairs}, p.id
        for f in g.fixtures:
            occupies = fixtures.kinds()[f["kind"]]["occupies"]
            squares = {tuple(q) for q in f["squares"]}
            if occupies == ["blocked"]:
                assert squares <= g.blocked, (p.id, f)
            if f["kind"] == "stair":
                assert squares.isdisjoint(g.blocked), (p.id, f)


def test_an_old_save_loads_with_fixtures_and_nobody_inside_one(tmp_path):
    """An old-format save — written before fixtures, so with no `fixtures_named` and a
    grid with no names on it — loads, gains its fixtures from the one derivation, and
    every saved position is where it was and outside every blocked square."""
    from django.test import override_settings

    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"),
                          start_id="quiet-the-bread-stall")
        path = c.save()
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["scene"].pop("fixtures_named", None)
        path.write_text(json.dumps(raw), encoding="utf-8")
        saved = {r: tuple(p) for r, p in raw["scene"]["positions"].items()}
        back = cm.Campaign.load(path)
        Engine(back.scene, Dice(seed=1), world=None).lay_the_ground()
        g = back.scene.grid
        assert g is not None and g.fixtures is not None, "the loaded ground was not typed"
        assert back.scene.positions == saved
        for ref, spot in back.scene.positions.items():
            assert tuple(spot[:2]) not in g.blocked, (ref, spot)
        cm._LIVE.clear()


def test_the_same_place_is_typed_the_same_way_every_time():
    """Derived, not stored: the same seed gives the same bar in the same squares, on any
    machine, so nothing about it has to be in the save."""
    a, _e, _pc = _at(TAVERN)
    b, _e2, _pc2 = _at(TAVERN)
    assert a.grid.fixtures == b.grid.fixtures and a.grid.fixtures


def test_a_spell_wall_is_never_typed_as_furniture():
    """Typed from the PRISTINE plan intersected with the grid: a wall of stone a spell
    raised on a reload is not "a table"."""
    s, _e, _pc = _at(TAVERN)
    g = s.grid
    extra = next((x, y) for x in range(1, g.width - 1) for y in range(1, g.height - 1)
                 if g.passable((x, y)) and not fixtures.at(g, (x, y)))
    g.blocked.add(extra)
    fixtures.type_the_ground(s, TAVERN, "urban")
    assert fixtures.at(g, extra) is None


# --- what the engine reads ------------------------------------------------------------

def test_a_stair_lets_a_man_walk_up_to_the_gallery():
    """Measured before: every square of the tavern's gallery refused a PC with no climb
    speed ("no way up") — there was no stair anywhere. Now the gallery is reached by one."""
    s, e, pc = _at(TAVERN)
    gallery = _kind(s.grid, "gallery")
    assert gallery and gallery[0].get("stair"), "a ledge room with no stair to its gallery"
    top = tuple(gallery[0]["squares"][0])
    level = gallery[0]["level"]
    res = _move(e, pc.ref, (*top, level))
    assert tuple(s.positions[pc.ref]) == (*top, level), [o.tell for o in res.outcomes]


def test_without_a_stair_the_gallery_still_needs_a_climb_however_the_square_is_written():
    """The hole the stair work found: a move written (x, y) — no level — onto a ten-foot
    gallery walked a man straight up, while (x, y, 2) was refused. The rule depended on how
    the square was spelled."""
    s, e, pc = _at(TAVERN)
    top = tuple(_kind(s.grid, "gallery")[0]["squares"][0])
    s.grid.fixtures = []                      # the room as it was: nothing named
    res = _move(e, pc.ref, top)
    assert tuple(s.positions[pc.ref])[:2] != top
    assert "no way up" in " ".join(o.tell for o in res.outcomes).lower()


def test_climbing_onto_a_crate_names_the_check():
    """A crate stack is a Climb check (CRB p.90, DC 10). Phase 1 does not roll it from a
    move; the refusal says so, with the DC, instead of "nothing here to climb"."""
    g = Grid(width=6, height=6)
    g.floor[(3, 3)] = 1
    g.fixtures = [fixtures._fixture("crate", [(3, 3)], 1, {})]
    s = Scene(location_id="t")
    man = instantiate("guildhand", scene=s, name="the man")
    s.add(man, at=(2, 3))
    s.grid = g
    e = Engine(s, Dice(seed=2), world=None)
    said = e._cannot_leave_the_ground(man, (2, 3), (3, 3, 1))
    assert "Climb check (DC 10)" in said and "a crate" in said, said


def test_a_table_gives_cover_and_not_a_wall():
    """1e: a low obstacle "provides cover" (CRB p.195). Before fixtures a row of tables was
    a wall: no line of sight across it, and TOTAL cover — an archer could not shoot a man
    crouched behind a table at all."""
    g = Grid(width=9, height=5)
    for y in range(0, 5):
        g.blocked.add((4, y))
    assert g.cover_between((1, 2), "medium", (7, 2), "medium") == "total"
    assert not g.line_of_sight((1, 2), (7, 2))
    g.low = {(4, y): 1 for y in range(0, 5)}
    assert g.cover_between((1, 2), "medium", (7, 2), "medium") == "cover"
    assert g.line_of_sight((1, 2), (7, 2))
    assert not g.passable((4, 2)), "a table still refuses a walk through it"


# --- the payload, the brief, the reader -----------------------------------------------

def test_the_map_payload_carries_fixtures_and_keeps_the_terrain_sets():
    """`fixtures: [{kind, name, squares, level}]`, and `blocked`, `difficult` and the rest
    exactly as they were so nothing downstream breaks. One wholly inside fog is not sent:
    nothing reaches the page the player could not see."""
    from play.views import _grid_state

    s, _e, _pc = _at(TAVERN)
    out = _grid_state(s)
    assert {"blocked", "difficult", "floor", "parapet", "reachable"} <= set(out)
    assert out["blocked"] == sorted(s.grid.blocked)
    names = {f["name"] for f in out["fixtures"]}
    assert "the bar" in names, names
    assert all({"kind", "name", "squares", "level"} <= set(f) for f in out["fixtures"])
    bar = next(f for f in s.grid.fixtures if f["name"] == "the bar")
    s.grid.obscuring |= {tuple(p) for p in bar["squares"]}
    assert "the bar" not in {f["name"] for f in _grid_state(s)["fixtures"]}


def test_the_brief_says_the_fixtures_in_words_and_no_numbers():
    """The narrator is told what the board shows, never the DC or the cover bonus."""
    from gm.brief import fixtures_here

    s, e, _pc = _at(TAVERN)

    class Ctx:
        scene, here = s, e.here()

    text, facts = fixtures_here.section(Ctx)
    # The tavern's raised floor by the place's own word (fixtures.json `names`).
    assert "the bar" in text and "the landing reached by a stair" in text, text
    assert not any(ch.isdigit() for ch in text.split(":", 1)[1]), text
    assert facts["fixtures"]


def test_the_reader_names_a_fixture_from_the_closed_list():
    """Models read, code validates (2026-10-03): the go act's `fixture` is an enum the
    sampler holds; a word outside it is dropped and said, never matched by a regex."""
    from gm import interpret

    go = next(a for a in interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
              if a["properties"]["act"]["const"] == "go")
    assert go["properties"]["fixture"]["enum"] == list(interpret.fixture_kinds())
    line = "I duck behind the barrels."
    frame, dropped = interpret.ground({"actions": [
        {"span": "duck behind the barrels", "act": "go", "place": "the barrels",
         "within_place": True, "fixture": "barrel"}]}, line)
    assert frame["actions"][0]["fixture"] == "barrel"
    assert interpret.within_place(frame["actions"][0])
    frame, dropped = interpret.ground({"actions": [
        {"span": "duck behind the barrels", "act": "go", "place": "the barrels",
         "fixture": "keg-pyramid"}]}, line)
    assert "fixture" not in frame["actions"][0] and dropped


def test_a_fixture_the_reader_names_is_placed_once_and_keeps_its_square(tmp_path):
    """A library has no barrel. Named, one is put down on a free square nearest the
    player, with nothing solid beside it (so it can wall nobody in), and it keeps that
    square: a second naming adds nothing, and it comes back on the next lay of the room."""
    s, e, pc = _at(LIBRARY)
    assert not _kind(s.grid, "barrel")
    placed = fixtures.name_one(s, "barrel")
    assert placed is not None
    sq = tuple(placed["squares"][0])
    assert sq in s.grid.blocked and sq not in s.occupied()
    assert fixtures.name_one(s, "barrel") is None, "named twice, placed twice"
    # Leave and come back: the ground is re-derived and the barrel is where it was.
    s.grid = None
    e.lay_the_ground()
    again = _kind(s.grid, "barrel")
    assert again and tuple(again[0]["squares"][0]) == sq
    for ref, spot in s.positions.items():
        assert tuple(spot[:2]) not in s.grid.blocked, (ref, spot)


def test_a_world_may_author_its_own_fixtures_from_the_closed_list():
    """World-agnostic (2026-09-28): a World Bible place may list `fixtures`; a word outside
    the closed list is dropped, and naming fixtures alone never reshapes the room."""
    base = floorplan.shape_for(TAVERN)
    got = floorplan.from_world({"fixtures": ["bookshelf", "throne"]}, base)
    assert got.fixtures == ("bookshelf",)
    assert (got.width, got.height, got.clumps, got.rough) == (
        base.width, base.height, base.clumps, base.rough)
    g = floorplan.for_place(TAVERN, "urban", got)
    s = Scene(location_id="t")
    s.grid = g
    fixtures.type_the_ground(s, TAVERN, "urban", got)
    solids = {f["kind"] for f in g.fixtures if "blocked" in fixtures.kinds()[f["kind"]]["occupies"]}
    assert solids == {"bookshelf"}, solids


# --- the rail and the stair (2026-11-11, the owner at the gate) --------------------------

def test_the_rail_opens_where_the_stair_arrives_and_the_walk_up_is_not_stopped():
    """The owner, looking at the gate in 3D: "what is the random thin wall that cuts the
    stairs and goes through the character". `/api/state` there held parapet (1..7, 3) at
    level 2, the gallery (1..7, 4) at level 2, and the stair at (7, 3) — a rail stored on
    the very square the stair stands on, drawn as a pane through it and through the
    player at (2, 3). The rail now opens at the stair's foot, the walk up the stair onto
    the gallery is a move like any other, and a reload keeps it open."""
    s, e, pc = _at(TAVERN)
    stair = _kind(s.grid, "stair")[0]
    foot = tuple(stair["squares"][0])
    assert foot not in s.grid.parapet, "the rail still stands on the stair"
    assert s.grid.parapet, "the rest of the gallery lost its rail"
    gallery = _kind(s.grid, "gallery")[0]
    top = next(tuple(p) for p in gallery["squares"]
               if abs(p[0] - foot[0]) + abs(p[1] - foot[1]) == 1)
    _move(e, pc.ref, foot)
    assert tuple(s.positions[pc.ref])[:2] == foot
    res = _move(e, pc.ref, (*top, gallery["level"]))
    assert tuple(s.positions[pc.ref]) == (*top, gallery["level"]), \
        [o.tell for o in res.outcomes]
    s.grid.fixtures = None                     # a reload re-types the saved grid
    e.lay_the_ground()
    assert foot not in s.grid.parapet


def test_both_boards_draw_a_gallery_rail_on_its_edge_not_through_the_square_in_front():
    """The same report, the picture's half: the rail was drawn as a pane standing in the
    middle of the ground square in front of the gallery, from the floor up — so it cut the
    stair and anyone on that row. Both boards now find the neighbour that is floor at the
    rail's height and draw the rail on that shared edge, from the walkway up."""
    from django.conf import settings

    js = (settings.BASE_DIR / "play" / "static" / "js")
    three = (js / "scene3d.js").read_text(encoding="utf-8")
    flat = (js / "table" / "03-offers-and-map.js").read_text(encoding="utf-8")
    assert "(ground[n] || 0) >= top) edge = d;" in three
    assert "slab(faces, ex0, ey0, ex1, ey1, top, top + rh" in three
    assert "at(c + dx, r + dy) >= v);" in flat


def test_every_fixture_kind_is_drawn_as_itself_on_the_flat_board():
    """The owner, 2026-11-11: "i want the fixtures to actually look like what the
    represent". Until then every kind was one brass block, circle or square: a barrel and
    a crate differed only in corners. Each kind in the closed list now names a symbol the
    board defines, and the symbols carry no gradient — a url(#id) resolves to the first
    copy in the page, and with the map tab hidden Chrome painted the hearth's fire grey."""
    import re

    from django.conf import settings

    flat = (settings.BASE_DIR / "play" / "static" / "js" / "table"
            / "03-offers-and-map.js").read_text(encoding="utf-8")
    table = re.search(r"const FX_SYMBOL = \{(.*?)\};", flat, re.S).group(1)
    symbols = dict(re.findall(r"(\w+): \"(\w+)\"", table))
    defs = flat[flat.index("const FX_DEFS"):flat.index("function renderMap")]
    for kind in fixtures.kinds():
        assert kind in symbols, f"{kind} has no drawing on the flat board"
        assert f'id="fx-{symbols[kind]}"' in defs, f"no symbol fx-{symbols[kind]}"
    assert "url(#" not in defs
