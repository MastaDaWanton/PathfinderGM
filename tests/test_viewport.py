"""The three-dimensional viewport, and the contract that lets it exist.

Asked for on 2026-09-14: "a 3D viewport where i can see the action and choose where to
cast spells/use abilities (like x-com, but still text based and without fancy textures.
Just something you can clearly see and rotate)."

**The viewport adds no facts.** Everything it draws comes from the geometry payload
`play/views.py::_grid_state` already sends, and every cell it offers is written with the
same `data-sq` attribute the flat map writes — so the combat builder cannot tell the two
views apart, and neither can the engine. A viewport that decided where a wall was would be
a second map disagreeing with the one the rules use.

That is also why the flat level-picker was built first, in stage 7: it proved the payload
and the interaction, and the 3D view is a second reader of both rather than a new system.
Measured in the browser against a real generated tavern, both views offered exactly the
same six cells and queued identical moves from them.

These tests are what Python can hold: that the module ships, that the page loads it, that
it is asked for the payload the server actually sends, and that nothing about it can reach
the engine except through `data-sq`. The drawing itself was verified by driving the real
renderer in the real browser — 180 polygons, four rotations, the archer on the gallery and
the depth sort holding through every quarter-turn.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings


def _js() -> str:
    return Path(settings.BASE_DIR, "play", "static", "js", "scene3d.js").read_text(
        encoding="utf-8")


def _page() -> str:
    return Path(settings.BASE_DIR, "play", "templates", "play", "table.html").read_text(
        encoding="utf-8")


def test_the_viewport_ships_and_the_table_loads_it():
    """A module nothing loads is the defect this whole run of work keeps finding."""
    assert _js().strip(), "scene3d.js is empty"
    assert "js/scene3d.js" in _page(), "the table never loads the viewport"


def test_it_is_bundled_by_the_spec():
    """`play/static/` goes into the exe wholesale, so this needs no spec entry — but if
    that ever changes, the packaged build would lose the viewport silently, exactly as it
    would have lost the fonts."""
    spec = Path(settings.BASE_DIR, "pathfindergm.spec").read_text(encoding="utf-8")
    assert "play/static" in spec


def _code(text: str) -> str:
    """The file with its comments taken out.

    Because the first version of the test below searched the whole file and the rewrite's
    own docstring — which explains that a CDN is *not available* — failed it. A test that
    reads prose is a test that fires on the sentence describing the rule it enforces.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            i = text.find("*/", i + 2)
            if i < 0:
                break
            i += 2
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def test_it_carries_no_third_party_code():
    """The app bundles no third-party JavaScript and ships as an offline executable, so a
    CDN is not available and a library would be a bundling decision rather than an
    import. `dice3d.js` builds five Platonic solids from vertex arrays with nothing behind
    it; this is the same bargain."""
    js = _code(_js()).lower()
    for smell in ("cdn", "unpkg", "three.min", "import ", "require("):
        assert smell not in js, smell


def test_it_reads_the_payload_the_server_sends_and_invents_nothing():
    """Every field it draws from must be one `_grid_state` actually produces. A viewport
    reading a key the server does not send is a blank map nobody can explain."""
    import inspect

    from play import views

    sent = inspect.getsource(views._grid_state)
    js = _js()
    for field in ("floor", "parapet", "blocked", "difficult", "obscuring", "reachable"):
        assert f'"{field}"' in sent, f"the server stopped sending {field}"
        assert field in js, f"the viewport does not draw {field}"


def test_both_views_write_the_same_targeting_attribute():
    """The architectural point, and the reason the flat map was built first. The combat
    builder reads `data-sq` and splits it on commas; it has no idea which view drew it,
    and `intents._square` has accepted three numbers since stage 3."""
    page = _page()
    js = _js()
    assert "data-sq" in js, "the viewport offers nothing to click"
    assert "data-sq" in page, "the flat map stopped offering cells"
    assert 'sq.dataset.sq.split(",").map(Number)' in page, \
        "the one reader of a targeted cell has moved; both views feed it"


def test_the_viewport_is_a_way_of_looking_and_not_a_fact_about_the_scene():
    """`MAP_3D`, `MAP_TURN` and `MAP_LEVEL` are deliberately not in `STATE`: they are
    where the player's attention is, and the server is not responsible for that. If they
    ever reach the payload, a reload starts dictating the camera."""
    import inspect

    from play import views

    sent = inspect.getsource(views._grid_state)
    # As payload KEYS, not as substrings: the first version of this asserted `"turn" not
    # in source` and failed on the word `return`, which is the sort of test that gets
    # deleted rather than understood.
    for name in ("turn", "camera", "view", "view3d", "level_shown"):
        assert f'"{name}"' not in sent, f"the server has started deciding the {name}"
    assert "let MAP_TURN = 0, MAP_3D = false;" in _page()


def test_rotation_is_quarter_turns():
    """Four fixed orientations, which is what Firaxis chose for XCOM — a fixed camera
    with 90-degree steps, specifically against the disorientation a free camera causes
    over a tactical map. Free rotation is the one thing WebGL would buy here, and it is
    the thing that was decided against."""
    js = _js()
    assert "TURNS: 4" in js
    assert "& 3" in js, "the turn is not clamped to four orientations"


# --- the rework: one light, and it belongs to the room --------------------------------------
#
# Asked for on 2026-09-15: "I want the viewport reworked using the style as the 3D dice,
# make sure to do a pass for clarity and precision." Reading the two files side by side
# found the viewport carrying the exact defect `dice3d.js` had already been reported for
# and cured — and a second one that made the picture contradict the rules.


def test_the_light_is_not_welded_to_a_side_of_the_box():
    """The defect the rework was for.

    The first viewport shaded by CLASS: `#view3d .face-a { filter: brightness(.72) }` was
    the +y wall and `.face-b` at .55 the +x wall. Those are geometric sides, so a quarter
    turn kept the same two brightnesses on the same two walls while they swapped sides of
    the screen — the light rotated with the board. `dice3d.js` carried the same mistake
    and it was reported from the table in those words: "the lighting is assigned to a few
    faces and it spins with those faces, all other faces are darker."

    Checked as "the stylesheet states no fill and no brightness for the view", because
    that is the condition that keeps it fixed: a CSS rule beats a presentation attribute,
    so one `fill:` in here would silently overrule every shaded face.
    """
    page = _page()
    block = page[page.index("#view3d {"):page.index("#view3d") + 2200]
    for banned in ("face-a", "face-b", "brightness("):
        assert banned not in block, f"{banned} is back: the light is baked onto a side again"
    fills = [ln for ln in block.splitlines()
             if "fill:" in ln and "#view3d" in ln and ":hover" not in ln]
    assert not fills, f"a fill rule overrules the shading: {fills}"


def test_both_renderers_light_from_the_same_lamp():
    """The one constant genuinely shared between the two files, so CLAUDE.md's "when you
    fix a rule, grep for every copy of it" applies to it and to nothing else in there.
    A board lit from one direction beside a die lit from another is two rooms."""
    import re

    board = _js()
    dice = Path(settings.BASE_DIR, "play", "static", "js", "dice3d.js").read_text(
        encoding="utf-8")
    pat = re.compile(r"LIGHT\s*=\s*norm\(\[([^\]]+)\]\)")
    mine, theirs = pat.search(board), pat.search(dice)
    assert mine and theirs, "one of the two renderers no longer names its light"
    assert mine.group(1).strip() == theirs.group(1).strip(), (
        f"the board is lit from {mine.group(1)} and the dice from {theirs.group(1)}")


def test_a_parapet_is_drawn_over_the_levels_it_actually_stops():
    """The precision bug, and it was in both earlier versions.

    `rules/grid.py` holds a parapet "by the absolute level of their top" and
    `_crosses_parapet` spells out what that means: "a rail whose top is level 2 stops a
    line running at 1 and does nothing to one running at 3." So the barrier fills the
    square from the ground UP TO that level. The viewport drew it from the top upward —
    `project(x, y, rz + 0.55)` down to `project(x, y, rz)` — a beam floating above the
    levels it blocks, showing clear air exactly where a shot is stopped. A player plans
    from the picture, so a picture that contradicts the rule is worse than none.
    """
    js = _code(_js())
    assert "rz + 0.55" not in js, "the rail floats above the levels it blocks again"
    # It now spans from the square's own ground to the stored top.
    assert "foot = Math.max(0, topAt(x, y))" in js
    assert "if (top > foot)" in js


def test_the_rule_the_parapet_is_drawn_from_is_still_the_rule():
    """The other half of the pair above: the drawing is pinned to `grid.py`'s wording, so
    if the engine ever changes what a parapet's number means, this fails rather than the
    viewport quietly going on drawing the old meaning."""
    import inspect

    from rules.grid import Grid

    # Whitespace-normalised: the sentence is wrapped in the source and the first version
    # of this failed on the line break rather than on the rule.
    doc = " ".join((inspect.getdoc(Grid._crosses_parapet) or "").split())
    assert "top is level 2 stops a line running at 1" in doc, (
        "the parapet rule has been reworded; check scene3d.js still draws what it means")


def test_a_wall_is_never_drawn_through_and_a_gallery_over_your_head_is():
    """The clarity pass, and the line it must not cross. Standing on the library floor,
    the player's own token sits behind ten feet of gallery — correct occlusion and no use
    to anybody, which is why XCOM cuts the walls between the camera and the floor being
    played on. The level picker is already that control, so it drives this rather than a
    second control being invented.

    A raised FLOOR above the level being looked at is drawn through. A wall is not: a wall
    is a wall from every level, and a translucent one would be telling the player they
    have a shot they do not have."""
    js = _code(_js())
    assert "if (!solid[k] && topz > level) cls += \" above\";" in js, \
        "the cutaway no longer excludes walls"
    assert "#view3d .above" in _page(), "nothing draws the cutaway"


def test_reach_is_a_wash_over_the_ground_and_not_a_colour_of_its_own():
    """Clarity, measured by looking at it: the reachable squares were their own flat gold,
    near enough to the player's own token that on a board of lit squares the token stopped
    being findable. The flat map has always done this as a wash — `#map .reach { fill:
    var(--gold); opacity: .12 }` — and both views are one click apart."""
    js = _code(_js())
    assert "GOLD" in js and "WASH" in js
    assert "lit: [" not in js, "reach is a material again rather than a tint"


def test_the_four_tokens_are_the_colours_the_flat_map_paints():
    """Both views are on screen within one click of each other. A foe that is #a33 in one
    and #e0261e in the other is two different foes to anybody not looking closely."""
    js = _code(_js())
    page = _page()
    for name, hexes in (("foe", "e0261e"), ("ally", "6fc276"), ("bystander", "f2ecdd")):
        assert f"#{hexes}" in page.lower(), f"the flat map no longer paints {name} #{hexes}"
        trio = ", ".join("0x" + hexes[i:i + 2] for i in (0, 2, 4))
        assert trio in js, f"the viewport paints {name} some other colour than #{hexes}"


def test_one_square_and_one_level_are_the_same_distance():
    """Precision. The first version carried TILE_W 26 and LEVEL_H 16 — two pixel constants
    for the same five feet, with nothing saying why they disagreed. A square and a level
    are both one unit now and the projection turns them into pixels."""
    js = _code(_js())
    assert "TILE_W" not in js and "LEVEL_H" not in js
    assert "UNIT = " in js
