"""Every name the world ships is a name the narrator may use.

Measured 2026-09-25: `GMAgent._known_names` read chronology entries as `c["name"]`, but they
are `world.loader.Event` dataclasses, so the line raised TypeError on every call from
2026-08-20 on, and a bare `except Exception: pass` hid it for five weeks. Every name
gathered after that line — every faction, and the world's own name — was never allowed, and
the un-namer could strike "the Winged Scales" or "Pangrella" as a person from nowhere. The
failure surfaced only because the review pass (fb83b25) made that `pass` log.
"""
from __future__ import annotations

import glob

import pytest

from gm.agent import GMAgent
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached


@pytest.mark.parametrize("path", sorted(glob.glob("fixtures/*-campaign.json")))
def test_factions_events_and_the_world_itself_are_known(path, caplog):
    world = load_cached(path)
    agent = GMAgent(world, Engine(Scene(), Dice(seed=1)))
    with caplog.at_level("WARNING", logger="pathfindergm"):
        known = agent._known_names()
    assert not [r for r in caplog.records if "names could not be read" in r.message]
    assert world.name in known
    for f in world.factions:
        assert f["name"] in known, f["name"]
    for e in world.chronology:
        assert e.name in known, e.name
