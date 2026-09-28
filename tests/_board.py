"""Stand two combatants within reach of each other, the way a fight's tests mean it.

Since 2026-09-27 a melee blow is refused from further than the attacker reaches (Core
Rulebook p.182; `position.out_of_reach`). Forty-six tests swung across the fifteen feet
`_ensure_encounter` lays a foe with no zone at, because nothing had ever asked — every one
of them was about the blow (its dice, its rider, its tell), none about the distance. Since
2026-09-28 a newcomer also stands at their zone from the moment they arrive, and the fight
moves nobody, so `near` is fifteen feet before the fight as well as during it. This is
their premise said once: the two are at arm's length. The distance itself has its own
tests in tests/test_maneuver_reach.py.
"""
from __future__ import annotations

from rules.grid import size_squares


def face_to_face(scene, a: str = "pc", b: str = "c1") -> None:
    """Put `b` in an open square beside `a`, on `a`'s level, and re-measure the zones.
    East first, then round the compass, so a board with nobody else on it always gets
    the same square.

    A no-op on a scene with no map or with `a` not on it: there is no distance to close,
    and the reach check does not refuse what it cannot measure.
    """
    if not scene.has_grid or a not in scene.positions or b not in scene.actors:
        return
    here = scene.positions[a]
    x, y = here[0], here[1]
    w = size_squares(scene.actors[a].size)
    taken = scene.occupied(ignore=b)
    for dx, dy in ((w, 0), (-1, 0), (0, -1), (0, w), (w, -1), (-1, -1), (w, w), (-1, w)):
        square = (x + dx, y + dy)
        if scene.grid.inside(square) and scene.grid.passable(square) \
                and square not in taken:
            scene.positions[b] = square + tuple(here[2:3])
            break
    scene.resync_zones()
