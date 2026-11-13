"""A market's stalls stand in straight rows (rules/floorplan._rows), plan item 6, 2026-11-13.

The owner's market picture showed three L-shaped stalls: the floorplan scattered its runs
anywhere, two that touched were typed as one stall bent round a corner. Saved rooms are
left alone, and nobody saved standing beside an old stall may end up inside a new one."""
from __future__ import annotations

from rules import fixtures, floorplan
from rules.engine import Engine, Scene
from rules.dice import Dice
from tests.test_map_fixtures import MARKET, _at

MARKETS = [f"{w}~urban:the-market" for w in
           ("5bbd0c40345f", "fc76ff68032e", "abc", "zz9", "q1", "harbour", "x" * 12)]


def test_no_market_stall_is_bent_and_none_touches_another():
    """Measured on the old scatter: 3 of the 7 test markets had a bent clump."""
    bent = 0
    for pid in MARKETS:
        old = fixtures._components(floorplan.for_place(pid, "urban", scatter=True).blocked)
        bent += any(len({p[0] for p in c}) > 1 and len({p[1] for p in c}) > 1 for c in old)
        g = floorplan.for_place(pid, "urban")
        for c in fixtures._components(g.blocked):
            assert len({p[0] for p in c}) == 1 or len({p[1] for p in c}) == 1, (pid, c)
        assert all(0 < p[0] < g.width - 1 and 0 < p[1] < g.height - 1 for p in g.blocked)
        assert len(fixtures._components(g.blocked)) == floorplan.BY_SPOT["the-market"].clumps
    assert bent, "the old scatter no longer bends anything: this test proves nothing"


def test_a_market_saved_before_rows_keeps_its_stalls_and_nobody_is_inside_one():
    """A save carries its grid and its squares; the fixtures are derived on load. Loaded
    under the rows code, the old grid must be named by the old stalls, untouched."""
    old = floorplan.for_place(MARKET, "urban", scatter=True)
    s = Scene(location_id="5bbd0c40345f")
    s.at = MARKET
    s.grid = old
    s.grid.fixtures = None                # as a load leaves it
    blocked = set(old.blocked)
    e = Engine(s, Dice(seed=3), world=None)
    e.lay_the_ground()
    assert s.grid.blocked == blocked
    stalls = [f for f in s.grid.fixtures if f["kind"] == "stall"]
    assert stalls and all(tuple(p) in blocked for f in stalls for p in f["squares"])
    typed = {tuple(p) for f in s.grid.fixtures for p in f["squares"]
             if f["level"] == 0 and f["form"] != "steps"}
    assert blocked <= typed, "an old stall square went untyped and would draw as a wall"


def test_everyone_laid_into_a_new_market_stands_on_open_ground():
    s, e, pc = _at(MARKET)
    from rules.bestiary import instantiate

    for i in range(8):
        s.add(instantiate("guildhand", scene=s, name=f"shopper {i}"), zone="near")
    e.lay_the_ground()
    for ref, p in s.positions.items():
        assert tuple(p[:2]) not in s.grid.blocked, (ref, p)
