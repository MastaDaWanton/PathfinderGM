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
        assert "opacity" not in re.sub(r'<g class="xray.*?</g>', "", svg), \
            "something other than the ghost is drawn see-through"


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
