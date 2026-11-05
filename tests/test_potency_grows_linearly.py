"""Herbal potency stays uncapped but grows linearly (the owner's ruling, 2026-11-01).

Measured on Ansel's save: a Caranator Decoction worked grind (Fine), dry (Flawless +4),
brew (Flawless +6), reduce (Flawless +4) -- the tiers read off his transcript -- carried
potency 33.7147, duration 30.6497 and drawback 0.0453, so a +2 Will save became +68 for 31
hours. Every step multiplied the running strength by method x form x perk x quality, and
four steps compounded geometrically: at Flawless +9 every step the same chain was 128.3x
(+257). The bench now combines multipliers by the Core Rulebook's rule for multiplying
(each one above 1 adds its value less 1), so the same chain at Flawless +9 is 8.2x (+17).
docs/herbalism-revamp-plan.md §17 has the before/after table.

Driven through the real step code (`plan_step` then `make`, as the bench's finish does)
on the shipped Caranator, so the numbers are the ones a player's satchel would carry.
"""
from __future__ import annotations

import pytest

from rules import crafting
from rules.sheet import load_pc

CHAIN = ("grind", "dry", "brew", "reduce")


def _chain(tiers, perks=None):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory.clear()
    pc.stock.clear()
    progress = pc.track("herbalist")
    progress.level = 8
    pc.carry("caranator", 16)
    lead = None
    for method, tier in zip(CHAIN, tiers):
        items = crafting.satchel(pc, 0)
        m = next(x for x in items if (x.key == lead if lead
                                      else not x.crafted and x.ingredient_id == "caranator"))
        per = min(8, m.count)
        per -= per % 2 if method in ("dry", "reduce") else 0
        plan = crafting.plan_step(pc, progress, method, [(m, per)], 1, perks=perks or {})
        assert not plan.problems, plan.problems
        made = crafting.make(plan, tier, 0)
        pc.add_stock(made, made.count)
        lead = f"stock:{made.id}"
    return made


def _will(stock) -> int:
    return next(s for s in stock.specs if s.get("target") == "will")["amount"]


def test_jasons_decoction_is_no_longer_thirty_three_times_as_strong():
    """Ansel's own tiers (2, 8, 10, 8), no perks: was potency 33.7147 / duration 30.6497
    (+68 Will for 31 hours); now 5.65 / 5.55 (+12 for 6 hours)."""
    made = _chain((2, 8, 10, 8))
    assert made.mults["potency"] == pytest.approx(5.65)
    assert made.mults["duration"] == pytest.approx(5.55)
    assert _will(made) == 12


def test_the_four_step_chain_at_flawless_plus_nine_is_eight_point_two_not_128():
    """Herbalist 8 with nine Quality perks, every step at the ceiling (Flawless +9, index
    13): was 128.304x (+257 Will); now 8.2x (+17), under Ansel's measured 33.7 by far."""
    made = _chain((13,) * 4)
    assert made.mults["potency"] == pytest.approx(8.2)
    assert made.mults["potency"] < 33.7147
    assert _will(made) == 17


def test_potency_is_still_uncapped_more_quality_is_always_more():
    """The ruling keeps potency uncapped: every rung of quality, Flawless and on past the
    ladder's end, makes the chain strictly stronger, and by the same amount each time
    (linear: four steps x 0.1 a rung past Flawless = +0.4 a rung)."""
    got = [_chain((t,) * 4).mults["potency"] for t in range(4, 18)]
    assert all(b > a for a, b in zip(got, got[1:])), got
    steps = {round(b - a, 6) for a, b in zip(got, got[1:])}
    assert steps == {0.4}, steps


def test_a_step_below_one_still_multiplies_and_never_reaches_zero():
    """A multiplier under 1 (Crude hands, Neutralize's 0.9, the drawback softening by good
    hands) still multiplies: I found no Pathfinder rule for stacked fractions, and adding
    them would take a line to zero or below. Four Crude steps keep potency positive, and
    the drawback still softens geometrically in Flawless hands (0.25 a step)."""
    crude = _chain((0,) * 4)
    assert 0 < crude.mults["potency"] < _chain((1,) * 4).mults["potency"]
    assert crafting.combine_multipliers(1.0, [0.9, 0.8]) == pytest.approx(0.72)
    assert crafting.combine_multipliers(2.0, [1.5, 0.25]) == pytest.approx(0.625)


def test_two_doublings_make_a_tripling():
    """The Core Rulebook's own example of its Multiplying rule: x2 applied twice is x3."""
    assert crafting.combine_multipliers(1.0, [2.0, 2.0]) == pytest.approx(3.0)
    assert crafting.combine_multipliers(crafting.combine_multipliers(1.0, [2.0]), [2.0]) \
        == pytest.approx(3.0)
