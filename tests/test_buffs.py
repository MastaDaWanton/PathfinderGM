"""Timed bonuses from consumables, and the gap they close.

The modifier family — save_mod, skill_mod, ability_mod, combat_mod — was marked
executable in the taxonomy and had no branch in `consumables._spec_to_intents`: drinking
a +1 Will tea produced a card, spent the dose, and changed no roll. Found while making
every herb usable; the conversions would have been cards over nothing.
"""
from __future__ import annotations

import pytest

from rules import crafting
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _tea(potency=1.0, amount=1):
    return crafting.Stock(
        base="Acacia Tea", tier="common", count=3, potency=potency, craft="herbalist",
        effects=[f"+{amount} Will saves"],
        specs=[{"type": "save_mod", "amount": amount, "target": "will",
                "bonus_type": "untyped", "from": "Acacia",
                "duration": {"amount": 1, "unit": "hour"}}])


@pytest.fixture
def table():
    s = Scene(location_id="x")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    return s, Engine(s, Dice(seed=1)), pc


def _drink(engine, pc, tea):
    pc.add_stock(tea, tea.count)
    return engine.run(engine.validate([{
        "op": "use_item", "actor": "pc", "because": "drinks",
        "params": {"item": tea.id, "how": "drink"}}]))


def _will(pc):
    return sum(m.value for m in pc.save_modifiers("will"))


def test_drinking_a_modifier_tea_changes_the_roll(table):
    """The defect, exactly: this used to spend the dose and change nothing."""
    scene, engine, pc = table
    before = _will(pc)
    r = _drink(engine, pc, _tea())
    assert _will(pc) == before + 1
    assert any("Acacia" in (o.tell or "") for o in r.outcomes)


def test_the_bonus_expires_on_the_same_clock_as_everything_timed(table):
    scene, engine, pc = table
    before = _will(pc)
    _drink(engine, pc, _tea())
    pc.tick_conditions(599)
    assert _will(pc) == before + 1
    pc.tick_conditions(1)
    assert _will(pc) == before


def test_potency_scales_the_modifier_not_only_the_dice(table):
    """"if i have 3000% potency potion does that actually give me 30x the base effect"
    — for dice it always did (1d8 at 30.0 is 1d8+131); for modifiers it now does too."""
    scene, engine, pc = table
    before = _will(pc)
    _drink(engine, pc, _tea(potency=30.0))
    assert _will(pc) == before + 30


def test_the_same_tea_reapplies_rather_than_stacking(table):
    """Same source, same roll: refreshed, not doubled — the reapply rule the
    magic-stacking homebrew states for same-source effects."""
    scene, engine, pc = table
    before = _will(pc)
    tea = _tea()
    _drink(engine, pc, tea)
    engine.run(engine.validate([{
        "op": "use_item", "actor": "pc", "because": "drinks again",
        "params": {"item": tea.id, "how": "drink"}}]))
    assert _will(pc) == before + 1


def test_a_buff_survives_the_save_file(table):
    scene, engine, pc = table
    _drink(engine, pc, _tea())
    back = from_dict(to_dict(pc), ref="pc")
    assert sum(m.value for m in back.save_modifiers("will")) == _will(pc)


def test_no_herb_is_inert_any_more():
    """"way to many useless herbs" — measured at 58 of 162 with nothing the engine could
    run. Extraction recovered the ones whose prose stated numbers; the rest were authored
    from their own text. The floor is now zero, and this keeps it there."""
    from rules import consumables as con, effectspec, ingredients

    inert = []
    for i in ingredients.all_ingredients().values():
        specs = [s for _, s in i.pairs if s.get("type") and effectspec.executable(s)]
        if not specs:
            inert.append(i.name)
    assert inert == [], inert
