"""The board's night (views._light_state), mock round 2026-11-13, plan item 10.

The board is shaded by the light the PC sees, never by the hour, so the picture and the
miss chance cannot disagree about whether it is dark."""
from __future__ import annotations

from rules.engine import ActiveEffect
from tests.test_map_fixtures import MARKET, TAVERN, _at


def _night(s):
    s.clock_minutes = 22 * 60


def test_the_open_market_at_night_is_dim_and_a_torch_lights_its_ring():
    """Measured: before this the market at ten at night was drawn exactly as at noon."""
    from play.views import _light_state

    s, e, pc = _at(MARKET)
    s.clock_minutes = 12 * 60          # a bare scene starts at midnight
    assert _light_state(s, pc) == {"level": "bright", "lit": []}
    _night(s)
    assert _light_state(s, pc)["level"] == "dim"
    pc.apply_effect(ActiveEffect(name="a torch", kind="effect", key="light.torch",
                                 source="t", duration="until-dismissed",
                                 tags=("light.torch",),
                                 payload={"light": {"radius_ft": 20, "raised_ft": 40}}))
    light = _light_state(s, pc)
    here = tuple(s.positions[pc.ref][:2])
    assert [here[0], here[1], "normal"] in light["lit"]


def test_a_roofed_room_at_night_keeps_its_lamps():
    from play.views import _light_state

    s, e, pc = _at(TAVERN)
    _night(s)
    assert _light_state(s, pc)["level"] == "normal"
