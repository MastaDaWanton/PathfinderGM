"""Zoom and pan on the ground board (play/static/js/table/24-map-zoom.js), 2026-11-12.

The owner: "yes build zoom and middle mouse pan", with the 24-square cap lifted outside
town interiors (rules/floorplan.py), so a street may be sixty squares across."""
from __future__ import annotations

from pagesource import _SRC, TABLE, TABLE_SCRIPTS


def test_zoom_loads_before_the_first_board_is_drawn():
    """Measured live: with the script tag after 23-thats-wrong.js the first board was drawn
    while the zoom script was still loading, so the page opened with 0 of the 4 zoom buttons
    (they appeared only after the next redraw). It loads straight after the board's own
    script, and is a `var` so `typeof MapZoom` can never meet an unmade `const`."""
    page = TABLE.read_text(encoding="utf-8")
    tags = [m for m in _SRC.findall(page) if "js/table/" in m]
    at = {n: next(i for i, t in enumerate(tags) if n in t)
          for n in ("03-offers-and-map.js", "24-map-zoom.js", "04-combat-and-turns.js")}
    assert at["03-offers-and-map.js"] < at["24-map-zoom.js"] < at["04-combat-and-turns.js"], at
    src = (TABLE_SCRIPTS / "24-map-zoom.js").read_text(encoding="utf-8")
    assert "var MapZoom" in src


def test_the_middle_button_pans_and_the_wheel_zooms():
    """The two inputs the owner named. Variant E, the mock this is ported from, refused both:
    it zoomed only on ctrl + wheel and ignored every mouse button but the left."""
    src = (TABLE_SCRIPTS / "24-map-zoom.js").read_text(encoding="utf-8")
    assert 'e.button !== 0 && e.button !== 1' in src
    assert 'addEventListener("wheel"' in src and "e.ctrlKey" not in src.split('"wheel"')[1][:400]
