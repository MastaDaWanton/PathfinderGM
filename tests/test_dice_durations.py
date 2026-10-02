"""A dice duration is rolled by the engine, every time, in every op that reads one.

The owner, 2026-10-02: "roll them, it's what should have been happening". Measured before
this file:
- `_op_condition` and the compulsion op read the amount with int(), so "nauseated for
  1d4 rounds" raised ValueError and the drink died with it (fixed at e0a7c9a);
- the buff op did the same, so a dice-length bonus raised;
- the defence op's reader swallowed the error and returned None, so a dice-length
  resistance silently became PERMANENT;
- and the herb rework had flattened every dice duration to its average to dodge all of
  that, so nothing was rolled at all.
- The bench's quality scaling also passed a dice duration through untouched, so Fine
  work lengthened every duration except the ones written as dice.
"""
from __future__ import annotations

from rules import crafting
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _drink(seed, specs):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=seed))
    pc = s.pc()
    pc.stock["jar#1"] = Stock(base="Jar", count=1, effects=["x"], specs=specs)
    engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "params": {"item": "jar#1", "how": "drink"}}]))
    return pc


def test_a_dice_length_bonus_is_rolled_and_ends():
    """+2 Fortitude for 1d4 hours: lands, and lasts 1 to 4 hours (600 to 2400 rounds),
    rolled, never a crash and never for ever."""
    seen = set()
    for seed in range(1, 25):
        pc = _drink(seed, [{"type": "save_mod", "target": "fort", "amount": 2,
                            "bonus_type": "alchemical",
                            "duration": {"amount": "1d4", "unit": "hour"}}])
        rounds = [e.rounds_left for e in pc.effects if getattr(e, "kind", "") == "buff"]
        assert rounds and all(r and 600 <= r <= 2400 for r in rounds), rounds
        seen.update(rounds)
    assert len(seen) > 1, "the duration was the same every time: it was not rolled"


def test_a_dice_length_resistance_wears_off():
    """Resist fire 10 for 1d4 hours. The defence op's old reader turned a dice duration
    into None, which is "never ends"; a herb's few hours of protection became a permanent
    resistance."""
    pc = _drink(3, [{"type": "resistance", "target": "fire", "amount": 10,
                     "duration": {"amount": "1d4", "unit": "hour"}}])
    timed = [e for e in pc.effects if "fire" in str(getattr(e, "key", "")) or
             "resist" in str(getattr(e, "kind", ""))]
    assert timed and all(e.rounds_left for e in timed), [vars(e) for e in timed]


def test_quality_lengthens_a_dice_duration_and_keeps_it_dice():
    """At x1.5 a 1d4-round duration (average 2.5) gains half its average, 1.25, as a
    flat extra, rounded UP because it is a benefit (the module's rule for every number:
    benefits up, costs down): 1d4+2. Still rolled, longer on average."""
    longer = crafting._scale_duration({"amount": "1d4", "unit": "round"}, 1.5, True)
    assert longer == {"amount": "1d4+2", "unit": "round"}
    softer = crafting._scale_duration({"amount": "2d4", "unit": "round"}, 0.5, False)
    assert softer["amount"].startswith("2d4-")


def test_a_non_lethal_cure_heals_non_lethal_damage_only():
    """Lane T, 2026-10-02: the jar door dropped a heal's `lethality`, so every one of the
    corpus's 39 "heals N non-lethal" restored REAL hit points; a liniment brought a
    taster at 0 back to 1. A non-lethal cure takes off the beating and nothing else."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=2))
    pc = s.pc()
    pc.hp, pc.nonlethal = pc.hp_max - 6, 5
    pc.stock["jar#1"] = Stock(base="Liniment", count=1, effects=["x"],
                              specs=[{"type": "heal", "amount": 4, "lethality": "nonlethal"}])
    engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "params": {"item": "jar#1", "how": "drink"}}]))
    assert pc.hp == pc.hp_max - 6 and pc.nonlethal == 1
