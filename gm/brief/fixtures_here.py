"""ON THE MAP: the named fixtures where the party stands (rules/fixtures.py).

The narrator describing the market's cart is describing the cart the player can see on
the board and get behind — said in plain words, never a number (the third law: the DC,
the cover bonus and the squares stay with the engine). What the map holds is named so the prose
and the board agree; lesser furniture stays the prose's, as the floorplan always said.
"""
from __future__ import annotations

ORDER = 12
SLOT = "place"
SCAFFOLD = (
    "ON THE MAP at",
    "(drawn on the board the player sees):",
)


def section(ctx) -> tuple[str, dict]:
    scene, here = ctx.scene, ctx.here
    grid = getattr(scene, "grid", None) if scene is not None else None
    if grid is None or here is None or not getattr(grid, "fixtures", None):
        return "", {}
    from rules import fixtures

    said = fixtures.said(grid)
    if not said:
        return "", {}
    return (f"  ON THE MAP at {here.name} (drawn on the board the player sees): "
            f"{'; '.join(said)}."), {"fixtures": said}
