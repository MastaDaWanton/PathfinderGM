"""The owner's homebrew Power leaf: +20 Str and +20 Con, permanent, landed as +26 each.

Playtest 2026-09-30, the aside in docs/playtest-2026-09-30-findings.md. Traced on the
owner's save: Sam's `Power leaf Tea` carries `potency: 1.3` and specs reading "+20"; both
ActiveEffects hold one `enhancement` modifier of 26, one per ability, applied once. Not a
doubled application and not a stacking fault: brewing is +25% potency plus 5% per
herbalist level (`herbprep.potency_change`), and `consumables` has scaled positive flat
bonuses by potency since 775145d ("a +1 tea at 3000% potency is +30 Will"). The fault was
that the card read the same spec through a different rule — it printed the authored "+20
Strength" — so the jar said one number and the drink gave another. One reader now,
`consumables.scaled_bonus`, for both.
"""
from __future__ import annotations

import pytest

from rules import consumables, crafting, ingredients
from rules.crafting import Chain
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


@pytest.fixture
def leaf(monkeypatch):
    shelf = dict(ingredients.all_ingredients())
    shelf["power-leaf"] = ingredients.from_dict(POWER_LEAF)
    monkeypatch.setattr(ingredients, "_ALL", shelf)
    return shelf["power-leaf"]


def _brew():
    """A herbalist 1's tea, brewed raw — the owner's chain."""
    return crafting.preview("herbalist", 1, Chain("herbalist", ["brew"], ["power-leaf"]))


def test_the_twenty_six_is_the_brew_and_not_a_doubled_application(leaf):
    """+20 x 1.30 = 26, the number on the owner's sheet: brewed at herbalist 1."""
    r = _brew()
    assert r.potency == pytest.approx(1.30)
    assert consumables.scaled_bonus("+20", r.potency) == 26
    assert consumables.scaled_bonus("+20", 1.0) == 20
    # Penalties are never made worse by a better brew.
    assert consumables.scaled_bonus(-2, r.potency) == -2


def test_the_jar_says_the_number_the_drink_gives(leaf):
    """The card said "+20 Strength" and the drink gave +26. Now both read
    `scaled_bonus`, and the line keeps the authored number so the player can see why."""
    r = _brew()
    lines = [e for e in r.effects if e.startswith("Power leaf:")]
    assert lines == ["Power leaf: +26 Strength (permanent; +20 at 130%)",
                     "Power leaf: +26 Constitution (permanent; +20 at 130%)"], lines
    # The record the engine runs from is untouched: the authored +20, once.
    assert [s["amount"] for s in r.output["specs"]] == ["+20", "+20"]


def test_drinking_it_lands_once_typed_and_as_printed(leaf):
    """One applicator, typed stacking: one enhancement modifier per ability, at the
    printed 26; a second dose refreshes rather than adding; an enhancement belt of +4
    beside it does not stack (best of a type)."""
    r = _brew()
    s = Scene(location_id="x")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    engine = Engine(s, Dice(seed=1))
    tea = crafting.from_stock_dict(r.output)
    tea.count = 2
    pc.add_stock(tea, 2)
    base_str, base_con = pc.ability_score("str"), pc.ability_score("con")

    def drink():
        return engine.run(engine.validate([{
            "op": "use_item", "actor": "pc", "because": "drinks",
            "params": {"item": tea.id, "how": "drink"}}]))

    out = drink()
    assert "+26 str" in " ".join(o.tell for o in out.outcomes)
    assert pc.ability_score("str") == base_str + 26
    assert pc.ability_score("con") == base_con + 26
    leaf_mods = [m for e in pc.effects for m in e.modifiers
                 if e.source == "Power leaf"]
    assert sorted((m["target"], m["amount"], m["bonus_type"]) for m in leaf_mods) == [
        ("con", 26, "enhancement"), ("str", 26, "enhancement")]
    drink()
    assert pc.ability_score("str") == base_str + 26, "a second dose stacked"
    pc.add_buff("ability_mod", "str", 4, source="belt", bonus_type="enhancement")
    assert pc.ability_score("str") == base_str + 26, "two enhancements added up"
