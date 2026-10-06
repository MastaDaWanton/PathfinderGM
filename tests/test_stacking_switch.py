"""One switch, one funnel: the `magic_stacking` house rule read by `dice.stack`.

The book (CRB, Getting Started, Common Terms): bonuses of one type "do not stack ... only
the greater bonus granted applies", and "bonuses without a type always stack, unless they
are from the same source". The owner (alchemy Q8.4 and open point 2, 2026-10-06): with the
`magic_stacking` house rule on, typed bonuses from DIFFERENT sources stack — every typed
bonus, not only alchemical — and the same source still keeps the better.

Measured before (build/alchemy, 3bbd361): the switch was read by `gain_temp_hp` alone;
the funnel never saw it, so two alchemical bonuses took the best whatever the table said.
And `dice.stack` added untyped bonuses whatever their source: one jar's untyped +2 drunk
twice under two names of the same effect was +4.
"""
from __future__ import annotations

import pytest

from rules import houserules
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice, Modifier, stack
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def isolated(tmp_path, settings):
    """The rules file in a scratch directory: never the player's real homebrew folder,
    never a toggle a previous run left on."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _sum(mods):
    return sum(m.value for m in mods)


def test_untyped_bonuses_from_the_same_source_keep_the_better():
    """"Bonuses without a type always stack, unless they are from the same source." Two
    separate effects with one source added: +2 and +3 from one tonic made +5. Held where
    a source is an effect's identity (`Actor._buff_mods`), not in `dice.stack`, where a
    source is a label: measured, collapsing labels there took a level-8 greatsword's Power
    Attack damage from +13 to +10 (its two-handed rung shares the feat's label)."""
    from rules.activeeffect import ActiveEffect

    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    base = _sum(pc.skill_modifiers("climb"))
    for amount in (2, 3):
        pc.apply_effect(ActiveEffect(name="a tonic", kind="effect", source="a tonic",
                                     stacking="stack",
                                     modifiers=[{"kind": "skill_mod", "target": "climb",
                                                 "amount": amount}]))
    assert _sum(pc.skill_modifiers("climb")) == base + 3
    pc.apply_effect(ActiveEffect(name="a salve", kind="effect", source="a salve",
                                 modifiers=[{"kind": "skill_mod", "target": "climb",
                                             "amount": 1}]))
    assert _sum(pc.skill_modifiers("climb")) == base + 4
    # The funnel itself leaves labels alone: one document's split terms still add.
    split = [Modifier(4, "Power Attack"), Modifier(2, "Power Attack")]
    assert _sum(stack(split, magic_stacking=False)) == 6


def test_typed_bonuses_take_the_best_by_the_book_and_add_by_source_with_the_switch():
    antitoxin = Modifier(5, "antitoxin", "alchemical")
    other = Modifier(2, "a bitter draught", "alchemical")
    again = Modifier(5, "antitoxin", "alchemical")
    assert _sum(stack([antitoxin, other], magic_stacking=False)) == 5
    assert _sum(stack([antitoxin, other], magic_stacking=True)) == 7
    # Two antitoxins are one source: +5, never +10, with the switch on or off.
    assert _sum(stack([antitoxin, again], magic_stacking=False)) == 5
    assert _sum(stack([antitoxin, again], magic_stacking=True)) == 5


def test_the_switch_reaches_every_typed_bonus_not_only_alchemical():
    """Open point 2's answer: "every typed bonus" — enhancement, morale and the rest."""
    belt = Modifier(4, "belt of giant strength", "enhancement")
    spell = Modifier(4, "bull's strength", "enhancement")
    assert _sum(stack([belt, spell], magic_stacking=False)) == 4
    assert _sum(stack([belt, spell], magic_stacking=True)) == 8
    # Penalties, dodge and circumstance are what they always were.
    assert _sum(stack([Modifier(1, "a", "dodge"), Modifier(1, "b", "dodge")],
                      magic_stacking=False)) == 2
    assert _sum(stack([Modifier(-2, "a", "morale"), Modifier(-2, "b", "morale")],
                      magic_stacking=False)) == -4


def test_with_no_answer_given_the_funnel_reads_the_table(isolated):
    belt = Modifier(4, "belt", "enhancement")
    spell = Modifier(4, "bull's strength", "enhancement")
    assert _sum(stack([belt, spell])) == 4
    houserules.set_active({"magic_stacking": True})
    assert _sum(stack([belt, spell])) == 8
    houserules.set_active({"magic_stacking": False})
    assert _sum(stack([belt, spell])) == 4


ANTITOXIN = {"type": "save_mod", "target": "fort", "amount": 5, "bonus_type": "alchemical",
             "when": {"against": "poison"}, "source": "antitoxin",
             "duration": {"amount": 1, "unit": "hour"}}
BITTER = {"type": "save_mod", "target": "fort", "amount": 2, "bonus_type": "alchemical",
          "source": "a bitter draught", "duration": {"amount": 1, "unit": "hour"}}


def _drinker():
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    pc.stock["anti#1"] = Stock(base="Antitoxin", count=2, specs=[dict(ANTITOXIN)])
    pc.stock["bitter#1"] = Stock(base="Bitter Draught", count=1, specs=[dict(BITTER)])
    return s, Engine(s, Dice(seed=2)), pc


def _drink(e, item):
    e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she drinks",
                       "params": {"item": item, "how": "drink"}}]))


def _fort_against_poison(pc):
    return _sum(pc.save_modifiers("fort", {"against": "poison"}))


def test_two_antitoxins_give_five_not_ten_with_the_switch_off(isolated):
    """The plan's test (§20.1): "two antitoxins give +5, not +10, with magic_stacking
    off; antitoxin plus a different alchemical +2 give +7 with it on"."""
    s, e, pc = _drinker()
    base = _fort_against_poison(pc)
    _drink(e, "anti#1")
    _drink(e, "anti#1")
    assert _fort_against_poison(pc) == base + 5
    _drink(e, "bitter#1")
    assert _fort_against_poison(pc) == base + 5           # the book: the better one


def test_antitoxin_and_another_alchemical_give_seven_with_the_switch_on(isolated):
    houserules.set_active({"magic_stacking": True})
    s, e, pc = _drinker()
    base = _fort_against_poison(pc)
    _drink(e, "anti#1")
    _drink(e, "anti#1")
    assert _fort_against_poison(pc) == base + 5           # one source, still +5
    _drink(e, "bitter#1")
    assert _fort_against_poison(pc) == base + 7


def test_antitoxin_is_against_poison_only(isolated):
    """Its `when` rides the timed bonus now: a +5 "against poison" read on every
    Fortitude save was the clause nothing asked (plan §16.7)."""
    s, e, pc = _drinker()
    plain = _sum(pc.save_modifiers("fort"))
    _drink(e, "anti#1")
    assert _sum(pc.save_modifiers("fort")) == plain
    assert _fort_against_poison(pc) == plain + 5
