"""The 3D board's masses, materials and people (2026-11-11).

The owner, verbatim: "fix the glass block, make the textures like stone apear in the 3D
view as well and replace the square people with something that will indicate it is a
humanoid". These drive the real renderer (play/static/js/scene3d.js) under node, as
tests/test_polish_ui.py does, and read what it draws.
"""
from __future__ import annotations

import json
import re

from test_polish_ui import SCENE3D, _node, _read, needs_node


def _render(tmp_path, grid: dict, actors: list, opts: dict) -> str:
    code = _read(SCENE3D)
    out = _node(tmp_path, "const window = {};\n" + code + f"""
      console.log(JSON.stringify({{ svg: window.Scene3D.render(
        {json.dumps(grid)}, {json.dumps(actors)}, {json.dumps(opts)}) }}));
    """)
    return out["svg"]


def _grid(**extra) -> dict:
    g = {"width": 7, "height": 7, "blocked": [], "difficult": [], "obscuring": [],
         "floor": [], "parapet": [], "reachable": []}
    g.update(extra)
    return g


def _ring(c: int, r: int) -> list:
    return [[c + dx, r + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


_FOE = {"name": "Goblin", "stance": "foe", "at": [3, 3, 0], "hp": 5, "hp_max": 5}


@needs_node
def test_a_hidden_token_is_shown_through_the_wall_at_every_quarter_turn(tmp_path):
    """The glass block: raised ground was drawn at 45% everywhere so that a token under a
    gallery stayed visible. Now the mass is solid and the token it hides is drawn over it
    as a ghost. Walled in on all eight sides, a goblin is hidden from every side the
    board can be turned to, so the ghost must be there at all four turns."""
    grid = _grid(blocked=_ring(3, 3))
    for turn in range(4):
        svg = _render(tmp_path, grid, [_FOE], {"turn": turn})
        assert svg.count('<g class="xray') == 1, turn
        # The floor's joints are a translucent pattern (in <defs>); no mass is.
        drawn = re.sub(r'<g class="xray.*?</g>|<defs>.*?</defs>', "", svg)
        assert "opacity" not in drawn, "something other than the ghost is see-through"


@needs_node
def test_a_token_in_the_open_gets_no_ghost(tmp_path):
    """Everything not hidden stays solid and single: a ghost over a goblin standing in
    the open would double every token on the board."""
    for turn in range(4):
        svg = _render(tmp_path, _grid(), [_FOE], {"turn": turn})
        assert "xray" not in svg, turn


@needs_node
def test_a_reachable_square_under_a_gallery_still_takes_the_click(tmp_path):
    """The floor in front of the camera's side of a gallery is hidden by it. The covered
    square is redrawn on top as an outline carrying the same `data-sq`, so a move onto
    it can still be queued from the 3D board; an open square is not redrawn."""
    gallery = [[c, r, 2] for c in range(7) for r in (4, 5, 6)]
    grid = _grid(floor=gallery, reachable=[[3, 3, 5, 0], [0, 0, 5, 0]])
    svg = _render(tmp_path, grid, [], {"turn": 0, "reach": True})
    over = re.findall(r'<polygon class="xsq[^"]*"[^>]*>', svg)
    assert len(over) == 1 and 'data-sq="3,3"' in over[0]


@needs_node
def test_stone_runs_in_the_plane_of_the_wall_from_a_handful_of_patterns(tmp_path):
    """The flat board had stone, planks and spines; the 3D one had flat colour, and the
    owner asked for "the textures like stone" there too. Every side of a wall wears the
    stone pattern, laid by `patternTransform` in that face's plane. The patterns are per
    material, orientation and lit colour, never per square: a 24x24 board of walls needs
    no more of them than one wall does (measured: 8 on the library, the same on 24x24)."""
    one = _render(tmp_path, _grid(blocked=[[3, 3]]), [], {"turn": 0})
    sides = re.findall(r'<polygon class="solid[^"]*" fill="([^"]+)"', one)
    plain = [f for f in sides if not f.startswith("url(#s3stone")]
    assert len(sides) == 6 and len(plain) == 1, sides     # 4 walls, the top, its dark lip
    assert "patternTransform=\"matrix(" in one
    walls = [[c, r] for c in range(24) for r in range(24) if (c * 7 + r * 3) % 5 == 0]
    many = _render(tmp_path, _grid(width=24, height=24, blocked=walls), [], {"turn": 0})
    count = lambda svg: svg.count("<pattern ")
    assert count(many) == count(one), (count(one), count(many))


def _height(svg: str) -> float:
    """How tall the figure stands on screen: its polygons' highest point to lowest."""
    ys = [float(p.split(",")[1])
          for pts in re.findall(r'<polygon class="fig[^"]*"[^>]*points="([^"]+)"', svg)
          for p in pts.split()]
    return max(ys) - min(ys)


@needs_node
def test_a_person_stands_as_a_figure_and_a_beast_does_not(tmp_path):
    """The owner: "replace the square people with something that will indicate it is a
    humanoid". Every creature was the same tall box, a wolf and a goblin alike. Now a
    humanoid is a miniature with a head and its initial on a plate; an animal (`form`
    "beast", from its `type.*` tag) stands low on all fours, an ooze is lower still, and
    nothing about the shape is read from the name."""
    one = lambda form, **kw: _render(tmp_path, _grid(), [dict(_FOE, form=form, **kw)],
                                     {"turn": 0})
    person, beast, ooze = one("humanoid"), one("beast"), one("ooze")
    assert ">G</text>" in person, "the initial is gone from the figure"
    assert _height(beast) < 0.75 * _height(person)
    assert _height(ooze) < _height(beast)


@needs_node
def test_size_a_crowd_and_the_fallen_read_at_a_glance(tmp_path):
    """A Large body stands on its whole 2x2 footprint and is drawn bigger; a crowd is
    three small people and its count, never one giant (item 33); a body at zero hit
    points lies on its base. And the base of whoever's turn it is wears the rim."""
    def one(**kw):
        return _render(tmp_path, _grid(), [dict(_FOE, ref="g1", **kw)],
                       {"turn": 0, "up": "g1"})
    medium, large = one(), one(squares=2)
    assert _height(large) > 1.8 * _height(medium)
    crowd = one(squares=2, members=7, members_max=9)
    assert crowd.count("base") == 3 and ">7</text>" in crowd
    assert _height(one(hp=0)) < 0.4 * _height(medium)
    assert medium.count(" base up") == 1


def test_the_payload_says_what_shape_each_body_is(tmp_path):
    """The board needs the creature's type to tell a wolf from a man, and `_state` sent
    none. `form` comes from the vocabulary's `type.*` tags (law 1), so a goblin is a
    humanoid, a wolf a beast, a gray ooze an ooze, and the player — no type tag — a
    humanoid. A creature hidden from the player is not in the list at all."""
    from django.test import override_settings

    from play import campaign as cm
    from play import concurrency, views
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        try:
            c = cm.current()
            s = c.scene
            for name in ("goblin", "wolf", "gray-ooze"):
                s.add(instantiate(name, scene=s, name=f"the {name}"))
            forms = {a["name"]: a["form"] for a in views._state(c)["scene"]["actors"]}
            assert forms["the goblin"] == "humanoid"
            assert forms["the wolf"] == "beast"
            assert forms["the gray-ooze"] == "ooze"
            assert forms[s.pc().name] == "humanoid"
        finally:
            cm._LIVE.clear()
