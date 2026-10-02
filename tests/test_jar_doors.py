"""Two doors a drunk jar went through that raised instead of working.

Found by Lane C on 2026-10-02 while tasting all 161 herbs: the taste op worked round both,
and the jar door (`use_item`) still raised. Measured before the fix:
- any jar with an "Ends X" line raised at parse, because `consumables` wrote the lift as
  `remove` and the condition op only ever took `ends`;
- any condition with a dice duration ("nauseated for 1d4 rounds") raised ValueError in
  `_op_condition`, which read the amount with int().
"""
from __future__ import annotations

from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _board():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=4))


def _drink(engine, specs):
    pc = engine.scene.pc()
    pc.stock["jar#1"] = Stock(base="Jar", count=1, effects=["x"], specs=specs)
    return engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "params": {"item": "jar#1", "how": "drink"}}]))


def test_a_jar_that_ends_a_condition_lifts_it():
    """Cowslip's "Ends paralyzed": the lift reaches the condition op as `ends`, so the
    paralysis is gone rather than the drink raising at parse."""
    scene, engine = _board()
    pc = scene.pc()
    pc.add_condition("paralyzed", 10, source="test")
    assert pc.has_state("state.unable.paralyzed")  # the premise, so the test cannot pass empty
    _drink(engine, [{"type": "remove_condition", "target": "paralyzed"}])
    assert not pc.has_state("state.unable.paralyzed")


def test_a_dice_duration_is_rolled_not_read_as_a_number():
    """Aconite's "nauseated for 1d4 rounds": the engine rolls the 1d4, and the condition
    lands for 1 to 4 rounds instead of the drink dying on int("1d4")."""
    scene, engine = _board()
    pc = scene.pc()
    _drink(engine, [{"type": "apply_condition", "target": "nauseated",
                     "duration": {"amount": "1d4", "unit": "round"}}])
    held = [e for e in pc.effects if getattr(e, "key", "") == "nauseated"]
    assert held and 1 <= (held[0].rounds_left or 0) <= 4
