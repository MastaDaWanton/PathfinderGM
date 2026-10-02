"""The owner's homebrew Power leaf: +20 Str and +20 Con, permanent, landed as +26 each.

Playtest 2026-09-30, the aside in docs/playtest-2026-09-30-findings.md. Traced on the
owner's save: Sam's `Power leaf Tea` carried `potency: 1.3` and specs reading "+20"; the
drink scaled the bonus by the potency and landed +26, while the card printed the authored
"+20". Two readers of one number. The fix then was one reader, `consumables.scaled_bonus`.

Re-pinned 2026-10-02 on the step bench, which retired the chain's brew potency (+25% plus
5% a level) for rule rows and a quality ladder. The defect is the same and so is the
answer, made stronger: the bench bakes the strength into the specs the engine runs, so the
line on the card, the spec on the jar and the number on the sheet are one number. A Fine
infusion is x1.15, so +20 is +23 on all three.
"""
from __future__ import annotations

import pytest

from rules import consumables, crafting, effectspec, ingredients
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

# The owner's document, as it sits in their homebrew folder (abridged to what matters).
POWER_LEAF = {
    "id": "power-leaf", "name": "Power leaf", "kind": "herb", "tier": "common",
    "description": "leaf of power", "biomes": ["mountain"], "craft_dc": 1,
    "risky": "no", "needs_extraction": "no", "volatile": "no", "can_grind": "yes",
    "mix_raw": "yes", "brew_raw": "yes", "animal": "no", "liquid": "no",
    "effects": [
        {"type": "ability_mod", "amount": "+20", "bonus_type": "enhancement",
         "target": "str", "duration": {"unit": "permanent"}, "uses": "unlimited"},
        {"type": "ability_mod", "amount": "+20", "bonus_type": "enhancement",
         "target": "con", "duration": {"unit": "permanent"}, "uses": "unlimited"},
    ],
}

FINE = 2


@pytest.fixture
def leaf(monkeypatch):
    shelf = dict(ingredients.all_ingredients())
    shelf["power-leaf"] = ingredients.from_dict(POWER_LEAF)
    monkeypatch.setattr(ingredients, "_ALL", shelf)
    return shelf["power-leaf"]


def _brew(pc):
    """A herbalist 1's tea, brewed raw at the step bench — the owner's chain."""
    pc.carry("power-leaf", 1)
    leaf_item = next(m for m in crafting.satchel(pc) if m.ingredient_id == "power-leaf")
    plan = crafting.plan_step(pc, pc.track("herbalist"), "brew", [(leaf_item, 1)])
    assert plan.can_roll and plan.form == "infusion", plan.problems
    return plan


def test_the_card_the_jar_and_the_spec_say_one_number(leaf):
    """The card said "+20 Strength" and the drink gave +26. Now the card's Fine line is
    rendered from the very spec the jar carries, and the jar carries the landed number."""
    from rules import herbknowledge

    pc = load_pc("fixtures/pc-kesst.json")
    plan = _brew(pc)
    # The owner knows their own leaf; an unknown property is never on the card.
    herbknowledge.reveal(pc, "power-leaf", herbknowledge.property_keys(leaf), "homebrew")
    card = crafting.product_card(plan, pc)
    lines = [e["by_tier"][FINE] for e in card["effects"]]
    assert lines == ["+23 Strength (permanent)", "+23 Constitution (permanent)"], lines
    tea = crafting.make(plan, FINE, 0)
    assert [s["amount"] for s in tea.specs] == [23, 23]
    assert [effectspec.render(s) for s in tea.specs] == lines
    # Baked, so the drink adds nothing on top: the jar's own potency is 1.0.
    assert tea.potency == 1.0
    assert consumables.scaled_bonus(tea.specs[0]["amount"], tea.potency) == 23
    # Penalties are never made worse by a better brew.
    assert consumables.scaled_bonus(-2, 1.3) == -2


def test_drinking_it_lands_once_typed_and_as_printed(leaf):
    """One applicator, typed stacking: one enhancement modifier per ability, at the
    printed 23; a second dose refreshes rather than adding; an enhancement belt of +4
    beside it does not stack (best of a type)."""
    s = Scene(location_id="x")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    engine = Engine(s, Dice(seed=1))
    tea = crafting.make(_brew(pc), FINE, 0)
    pc.add_stock(tea, 2)
    base_str, base_con = pc.ability_score("str"), pc.ability_score("con")

    def drink():
        return engine.run(engine.validate([{
            "op": "use_item", "actor": "pc", "because": "drinks",
            "params": {"item": tea.id, "how": "drink"}}]))

    out = drink()
    assert "+23 str" in " ".join(o.tell for o in out.outcomes)
    assert pc.ability_score("str") == base_str + 23
    assert pc.ability_score("con") == base_con + 23
    leaf_mods = [m for e in pc.effects for m in e.modifiers
                 if e.source == "Power leaf"]
    assert sorted((m["target"], m["amount"], m["bonus_type"]) for m in leaf_mods) == [
        ("con", 23, "enhancement"), ("str", 23, "enhancement")]
    drink()
    assert pc.ability_score("str") == base_str + 23, "a second dose stacked"
    pc.add_buff("ability_mod", "str", 4, source="belt", bonus_type="enhancement")
    assert pc.ability_score("str") == base_str + 23, "two enhancements added up"
