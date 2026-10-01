"""The candle's veil must out-reach any window, so its edge never shows.

Reported 2026-09-30 by the owner on an ultrawide, at full screen: "a line that follows the
cursor … it sways a bit". Measured on a 3440x1440 window: `#cursorshade` was a fixed
6000px square centred on the pointer, so it ended 2934-3138px from the cursor. It left 356
columns undimmed, a ~10% brightness step that followed the pointer and swayed 204px with
the flicker's scale (.978-1.046). Nothing showed at 2560 or narrower, which is why no
earlier check saw it.

The fix sizes the square from the viewport, `max(6000px, calc(200vmax + 400px))`, and pins
the gradient's last stop at 4243px (the old 100%, the 6000px box's corner), so the light is
identical at every size up to 2560 and the veil reaches past every edge above it. Every
copy of the rule is held to it: the table, the shelf, the bench and the mock.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIES = [
    ROOT / "play" / "templates" / "play" / "table.html",
    ROOT / "play" / "templates" / "play" / "home.html",
    ROOT / "play" / "templates" / "play" / "craft.html",
    ROOT / "docs" / "mock" / "table-layout" / "mock.css",
]


def _rules(text: str) -> list[str]:
    """The rule that draws the veil: the one with a background. A copy may also carry a
    one-line `#cursorshade { display: none; }` for touch screens, which sizes nothing."""
    out = []
    for m in re.finditer(r"#cursorshade\s*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i - 1]
        if "background" in _without_comments(body):
            out.append(body)
    return out


def _without_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_every_copy_of_the_veil_is_sized_from_the_window():
    seen = 0
    for path in COPIES:
        for rule in _rules(path.read_text(encoding="utf-8")):
            css = _without_comments(rule)
            seen += 1
            assert "vmax" in css, f"{path.name}: the veil is not sized from the window"
            for prop in ("width", "height"):
                m = re.search(rf"(?<![-\w]){prop}\s*:\s*([^;]+);", css)
                assert m, f"{path.name}: no {prop} on #cursorshade"
                assert not re.fullmatch(r"\s*\d+px\s*", m.group(1)), (
                    f"{path.name}: #cursorshade {prop} is a fixed {m.group(1).strip()}; "
                    "a 3440px window saw its edge")
    assert seen == len(COPIES), f"expected one #cursorshade rule per copy, found {seen}"


def test_the_light_itself_is_unchanged():
    """The gradient's stops are the measured ones, and the last is pinned in px so a
    larger box does not stretch the dusk outwards."""
    for path in COPIES:
        for rule in _rules(path.read_text(encoding="utf-8")):
            css = _without_comments(rule)
            assert "transparent 0 130px" in css and "460px" in css, path.name
            assert "rgba(4, 3, 2, .13) 4243px" in css, (
                f"{path.name}: the veil's last stop must be 4243px, not a percentage")
