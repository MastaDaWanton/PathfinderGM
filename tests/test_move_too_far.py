"""A move further than this round's movement goes as far as it can toward the square.

Live 2026-11-12 (the Copper Kettle): told "(0, 0) is 55 ft away by the shortest open route
and Kesst Vayr has 30 ft of movement", the plan asked for (0, 0), (1, 0), (0, 0), (1, 0),
(0, 0), (0, 0), (1, 1) — seven refusals, and the turn fell to narration. The refusal now
names the nearest square in reach and carries it as the fix; the turn loop applies it.
"""
from __future__ import annotations

import pytest

from gm.agent import GMAgent
from rules.bestiary import instantiate
from rules.intents import IntentError

from test_map_fixtures import _at


def test_a_move_too_far_is_repaired_to_the_nearest_square_in_reach():
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    foe = s.add(instantiate("guildhand", scene=s, name="Bruiser"), zone="near")
    s.sides = {"party": [pc.ref], "foes": [foe.ref]}
    s.initiative, s.turn = [(pc.ref, 10), (foe.ref, 5)], 0
    g = s.grid
    here = tuple(s.positions[pc.ref][:2])
    every = g.reachable(here, 10_000, size=pc.size, occupied=s.occupied(ignore=pc.ref))
    far = max(every, key=lambda p: (every[p], p))
    assert every[far] > pc.speed_feet
    raw = [{"op": "move", "actor": pc.ref, "because": "runs",
            "params": {"square": list(far)}}]
    with pytest.raises(IntentError) as err:
        e.validate(raw)
    assert err.value.code == "too_far" and "nearest it can get" in str(err.value)
    fixed = GMAgent._move_toward(err.value, raw)
    [intent] = e.validate(fixed)
    to = tuple(intent.params["square"][:2])
    reach = g.reachable(here, pc.speed_feet, size=pc.size, occupied=s.occupied(ignore=pc.ref))
    assert to in reach
    back = g.reachable(far, 10_000, size=pc.size, occupied=s.occupied(ignore=pc.ref))
    assert back[to] < every[far]        # closer to where they meant to go than they were
