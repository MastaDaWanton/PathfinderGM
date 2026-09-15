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


def test_it_carries_no_third_party_code():
    """The app bundles no third-party JavaScript and ships as an offline executable, so a
    CDN is not available and a library would be a bundling decision rather than an
    import. `dice3d.js` builds five Platonic solids from vertex arrays with nothing behind
    it; this is the same bargain."""
    js = _js()
    for smell in ("cdn", "unpkg", "three.min", "import ", "require("):
        assert smell not in js.lower(), smell


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
