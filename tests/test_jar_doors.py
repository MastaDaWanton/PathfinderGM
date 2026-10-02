"""Two doors a drunk jar went through that raised instead of working.

Found by Lane C on 2026-10-02 while tasting all 161 herbs: the taste op worked round both,
and the jar door (`use_item`) still raised. Measured before the fix:
- any jar with an "Ends X" line raised at parse, because `consumables` wrote the lift as
  `remove` and the condition op only ever took `ends`;
- any condition with a dice duration ("nauseated for 1d4 rounds") raised ValueError in
  `_op_condition`, which read the amount with int().
"""
from __future__ import annotations

import pytest

from rules import ingredients
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


def test_a_steeping_jar_cannot_be_drunk_before_its_day():
    """A tincture steeps for two weeks (plan §6). The bench refused an early jar, but the
    narrated door ("I drink my tincture") had no clock check, so it was the one way round
    the steep: found at the bench engine's merge, 2026-10-02."""
    scene, engine = _board()
    pc = scene.pc()
    scene.clock_minutes = 1000
    pc.stock["jar#1"] = Stock(base="Comfrey Tincture", count=1, effects=["x"],
                              specs=[{"type": "heal", "amount": "1d4"}], ready_minute=1000 + 3 * 1440)
    out = engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "params": {"item": "jar#1", "how": "drink"}}])).outcomes[0]
    assert "still steeping" in out.tell and pc.stock["jar#1"].count == 1


# --- the herbal cures, restored ----------------------------------------------------------

# Every herb whose corpus entry ends a condition, and the condition it ends. The relevance
# pass removed all five `remove_condition` effects on 2026-10-02 to dodge the `remove`
# bug above; once the jar door sent `ends`, three were appended back as each herb's LAST
# effect (knowledge keys are positional). Skull Orchid's "ends dead" (read out of "until
# cured or dead") and Sherpa's Friend's "ends sickened" (immunity to altitude sickness,
# which is not the sickened condition) were misparses and stay out.
CURES = {"cowslip": "paralyzed", "allnight": "fatigued", "dawnpetal": "fatigued"}


def test_every_cure_in_the_corpus_is_drunk_here():
    """The table above is the corpus's own list, so a cure added later gets a drink test
    and a cure removed again is noticed. 5 before the relevance pass, 0 after it, 3 now."""
    found = {i: s["target"] for i, ing in ingredients.all_ingredients().items()
             for s in ing.specs if s.get("type") == "remove_condition"}
    assert found == CURES


@pytest.mark.parametrize("herb", sorted(CURES))
def test_drinking_a_herbal_cure_lifts_its_condition(herb):
    """Cowslip's "Ends paralyzed", and Allnight's and Dawnpetal's "Ends fatigued", drunk
    through `use_item` with every other effect the herb carries: the condition is on the
    drinker first and gone after. Before the `ends` fix every one of these drinks raised
    at parse, and the whole jar, its bonuses too, did nothing."""
    condition = CURES[herb]
    scene, engine = _board()
    pc = scene.pc()
    pc.add_condition(condition, 10, source="test")
    assert pc.has_condition(condition)  # the premise, so the test cannot pass empty
    _drink(engine, [dict(s) for s in ingredients.get(herb).specs])
    assert not pc.has_condition(condition)


def test_the_cure_is_the_last_property_so_no_key_moved():
    """The herbarium's knowledge keys are positional (p0, p1, ...): a cure inserted
    anywhere but the end would have re-pointed every key after it at a different
    property in every save that knew one."""
    for herb in CURES:
        specs = ingredients.get(herb).specs
        assert specs[-1]["type"] == "remove_condition", herb
        assert sum(s["type"] == "remove_condition" for s in specs) == 1, herb
