"""A scheme that fails half-way leaves nothing of itself; a body anywhere takes damage by
the rules.

Measured 2026-09-25: `schemes_mod.tick` reads and changes the scene, and `Engine.run`
caught its exceptions with no rollback — whatever it had done before failing stayed, and
the next save wrote it. And a scheme's off-stage death wrote `who.hp -= amount` around
the one damage door, because the door read the here-view and raised KeyError for a body
in another room; resistances, damage reduction and guards never applied off-stage.
"""
from __future__ import annotations

from rules import schemes as schemes_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def test_a_tick_that_raises_half_way_is_undone(monkeypatch):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.schemes = [{"id": "x", "step": "one"}]
    engine = Engine(s, Dice(seed=1))

    def half_then_fail(eng, outcomes):
        eng.scene.schemes[0]["step"] = "two"         # changed the scene...
        eng.scene.clock_minutes += 600
        raise RuntimeError("...and then fell over")

    monkeypatch.setattr(schemes_mod, "tick", half_then_fail)
    clock = s.clock_minutes
    res = engine.run(engine.validate([{"op": "narrate_only", "because": "a look"}]))
    assert s.schemes[0]["step"] == "one", "the half-run step was kept"
    assert s.clock_minutes == clock
    assert any(e.get("kind") == "scheme_error" for o in res.outcomes for e in o.effects)


def test_the_damage_door_reaches_a_body_in_another_room():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    far = instantiate("thug", scene=s, name="the fence")
    s.add(far)
    far.at = "somewhere-else"
    assert far.ref not in s.actors and far.ref in s.people
    engine = Engine(s, Dice(seed=1))
    hp = far.hp
    engine._apply_damage(far, 3, "untyped", lethality="lethal")
    assert far.hp == hp - 3
