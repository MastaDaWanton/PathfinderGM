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


def test_range_notation_rolls_as_exact_dice():
    """"Heals 1-4 hit points" is the corpus's own phrasing and the extractor keeps it.
    `Dice.parse` refused it, which made the drink button a 500 for every jar authored in
    those words — the second bug under "clicking the drink button does nothing"."""
    from rules.dice import Dice

    d = Dice(seed=7)
    assert d.parse("1-4") == (1, 4, 0)
    assert d.parse("2-8") == (1, 7, 1)
    rolls = [d.roll("1-4").total for _ in range(300)]
    assert min(rolls) == 1 and max(rolls) == 4


def test_drinking_a_range_healing_jar_works_end_to_end(table):
    """Comfrey Tea, as the user's shelf actually holds it."""
    scene, engine, pc = table
    from rules import crafting

    tea = crafting.Stock(
        base="Comfrey Tea", tier="common", count=1, potency=1.0, craft="herbalist",
        effects=["Comfrey: Heals 1-4 hit points"],
        specs=[{"type": "heal", "dice": "1-4", "from": "Comfrey"}])
    pc.add_stock(tea, 1)
    pc.hp = max(1, pc.hp_max - 4)
    before = pc.hp
    engine.run(engine.validate([{
        "op": "use_item", "actor": "pc", "because": "drinks",
        "params": {"item": tea.id, "how": "drink"}}]))
    assert pc.hp > before
    assert tea.id not in pc.stock


def test_potency_scales_range_notation_too():
    """"the comfry was x5.something potency so it should have healed way more" — it
    should have, and did not: "1-4" fell through scale()'s notation match and potency
    silently never applied. Normalised to 1d4 first, a 506% tea is 1d4+11."""
    from rules.consumables import scale

    assert scale("1-4", 5.06) == "1d4+11"
    assert scale("1-4", 1.0) == "1d4"
    assert scale("2-8", 1.0) == "1d7+1"


def test_the_cure_tell_names_the_nonlethal_and_the_bank(table):
    """"my nonlethal hp did not heal" — it healed, and the tell said "already unhurt",
    which is a cure lying about two of its three effects. For a class whose entire
    economy is non-lethal damage, the lie reads as the mechanic being broken."""
    from rules import crafting
    from rules.engine import Engine, Scene
    from rules.dice import Dice
    from rules.sheet import from_dict, load_pc, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["ranks"] = {}
    pc = from_dict(d, ref="pc")
    pc.hp = pc.hp_max
    pc.nonlethal = 8
    s = Scene(location_id="x")
    s.add(pc)
    e = Engine(s, Dice(seed=5))
    tea = crafting.Stock(base="Comfrey Tea", tier="rare", count=1, potency=5.06,
                         craft="herbalist", effects=["Heals 1-4 hit points"],
                         specs=[{"type": "heal", "dice": "1-4", "from": "Comfrey"}])
    pc.add_stock(tea, 1)
    r = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "drinks",
                           "params": {"item": tea.id, "how": "drink"}}]))
    tells = " ".join(o.tell for o in r.outcomes if o.tell)
    assert "non-lethal" in tells
    assert "temporary vitality" in tells
    assert "already unhurt" not in tells
    assert pc.nonlethal < 8


def test_the_nonlethal_rider_does_not_eat_the_bank(table):
    """1e's non-lethal clearing is a rider, not a spender: "healing that raises your
    hit points also removes an equal amount of nonlethal damage." A 14-point cure on a
    full-health bender carrying 8 non-lethal clears the 8 for free and banks all 14 —
    "it healed the non-lethal but gave me no temp hp?" was a fix that had made the
    rider consume the pool."""
    scene, engine, pc = table
    pc.overrides["heal.overflow_temp_hp"] = True
    pc.hp = pc.hp_max
    pc.nonlethal = 8
    pc.heal(14)
    assert pc.nonlethal == 0
    assert sum(p.amount for p in pc.temp_pools) == 14


def test_healing_real_damage_still_consumes_the_cure(table):
    """The control on the rider: 4 down and 8 non-lethal, cured 14 — heals 4, clears 8
    free, banks the 10 that had no hit points to raise."""
    scene, engine, pc = table
    pc.overrides["heal.overflow_temp_hp"] = True
    pc.hp = pc.hp_max - 4
    pc.nonlethal = 8
    pc.heal(14)
    assert pc.hp == pc.hp_max
    assert pc.nonlethal == 0
    assert sum(p.amount for p in pc.temp_pools) == 10


# --- the channel the author filled in and nothing carried -----------------------------


def _plain():
    from rules.sheet import from_dict

    return from_dict({"name": "x", "kind": "npc", "hp": 20, "hp_max": 20,
                      "abilities": {k: 12 for k in
                                    ("str", "dex", "con", "int", "wis", "cha")}})


def _will(a):
    return sum(m.value for m in a.save_modifiers("will"))


def test_two_bonuses_of_one_named_type_do_not_stack():
    """1e: two alchemical bonuses are the better one, not the sum.

    `bonus_type` was dropped between the author and the roll. `effectspec` has offered
    the field since it was written and 772 of the 1,145 modifier specs in shipped
    content fill it with a type that does NOT stack with itself — and `consumables`
    never passed it to the buff op, the op had no param for it, and `add_buff` had no
    argument to receive it. So every timed bonus in the game entered the funnel
    untyped, untyped stacks with everything, and two teas were worth +4."""
    a = _plain()
    base = _will(a)
    a.add_buff("save_mod", "will", 2, source="acacia tea", bonus_type="alchemical")
    a.add_buff("save_mod", "will", 2, source="willow tea", bonus_type="alchemical")
    assert _will(a) == base + 2, "two alchemical bonuses are the better one"


def test_two_bonuses_of_different_types_still_stack():
    """The other half of the rule, and the reason the fix is a channel and not a cap."""
    a = _plain()
    base = _will(a)
    a.add_buff("save_mod", "will", 2, source="a tea", bonus_type="alchemical")
    a.add_buff("save_mod", "will", 2, source="a prayer", bonus_type="morale")
    assert _will(a) == base + 4


def test_untyped_bonuses_stack_as_1e_says_they_do():
    a = _plain()
    base = _will(a)
    a.add_buff("save_mod", "will", 2, source="one")
    a.add_buff("save_mod", "will", 2, source="two")
    assert _will(a) == base + 4


def test_the_type_is_named_in_the_terms_and_survives_a_save():
    """The popup has to be able to say WHY the second tea did nothing."""
    from rules.sheet import from_dict, to_dict

    a = _plain()
    a.add_buff("save_mod", "will", 2, source="acacia tea", bonus_type="alchemical")
    assert any(m.source == "acacia tea" and m.type == "alchemical"
               for m in a.save_modifiers("will"))
    back = from_dict(to_dict(a))
    assert any(m.type == "alchemical" for m in back.save_modifiers("will"))


def test_a_misspelled_bonus_type_is_refused_with_the_list():
    """An unrecognised type would fall through to untyped, which stacks with
    everything — so a typo would silently double a number instead of being refused."""
    import pytest

    from rules.intents import IntentError, parse_all

    with pytest.raises(IntentError, match="is not a bonus type"):
        parse_all([{"op": "buff", "actor": "pc", "because": "t",
                    "params": {"type": "save_mod", "target": "will", "amount": 2,
                               "bonus_type": "alchemicel"}}])
