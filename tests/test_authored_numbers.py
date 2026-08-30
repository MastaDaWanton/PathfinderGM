"""No model authors a number — the half of law 3 that had no enforcement.

`spawn.count` was bounded and its neighbours were not, so one model-authored value
could mint a million gold pieces into a hand-priced economy, drive a foraging loop for
a year, or index past the end of an attack sequence and raise *inside resolution* as a
500 rather than as a refusal the model could act on. The dice guard had the same shape
of hole: it bounded the dice and not the constant, so "1d6+999999" read as plausible.

Every bound here is clamped rather than refused, matching `rules/dc.py`: the model meant
"a lot", the engine decides how much, and the turn survives. Only a value that is not a
number is refused, and the refusal names what the field is for.
"""
from __future__ import annotations

import pytest

from rules.dice import BadDice, Dice
from rules.intents import IntentError, parse_all


def _params(op, **params):
    return parse_all([{"op": op, "actor": "pc", "because": "t", "params": params}])[0].params


def test_a_give_cannot_mint_a_fortune():
    """`count = max(1, int(...))` in the engine had no ceiling, and `give` is how the
    world hands over coin. One authored number was an unbounded deposit."""
    assert _params("give", item="gold piece", count=1_000_000)["count"] == 500
    assert _params("give", item="arrow", count=40)["count"] == 40      # a real sack
    assert _params("give", item="rope")             .get("count") is None


def test_an_attack_iteration_is_bounded_before_it_indexes():
    """Unvalidated, this reached `whole[min(int(it), len(whole) - 1)]` inside
    resolution: a non-numeric value raised there as a 500, which is the one shape of
    failure the intent layer exists to convert into a refusal."""
    assert _params("attack", iteration=99)["iteration"] == 15
    assert _params("attack", iteration=-4)["iteration"] == 0
    with pytest.raises(IntentError, match="which swing of a full attack"):
        _params("attack", iteration="the second one")


def test_forage_hours_are_bounded_on_the_path_the_model_uses():
    """Bounded on the browser path and in the injector; unbounded on the one path the
    model actually uses, where the number drives the loop the op runs. 48 is the
    injector's own ceiling rather than a third answer to the same question."""
    assert _params("forage", hours=100_000)["hours"] == 48
    assert _params("forage", hours=30)["hours"] == 30       # past a day, and legal
    with pytest.raises(IntentError, match="how long is spent on the ground"):
        _params("forage", hours="all day")


def test_the_implausible_dice_guard_is_not_defeated_by_a_plus_sign():
    """The guard bounded `count` and `faces` and never `flat`, so the whole check was
    sidestepped by writing the number after a plus: "1d6+999999" parsed as plausible
    and dealt a million points of damage."""
    d = Dice(seed=1)
    with pytest.raises(BadDice, match="implausible flat term"):
        d.parse("1d6+999999")
    with pytest.raises(BadDice, match="implausible dice"):
        d.parse("500d6")
    assert d.parse("2d6+3") == (2, 6, 3)                    # ordinary notation is untouched
    assert d.parse("1d8-1") == (1, 8, -1)


def test_a_refusal_names_the_field_so_the_retry_is_a_repair():
    """The house standard: a rejection the model cannot act on costs a whole
    regeneration, so every one of these names what the field is for."""
    for op, params, phrase in (
        ("give", {"item": "x", "count": "lots"}, "how many of the item"),
        ("attack", {"iteration": "second"}, "counting from 0"),
        ("forage", {"hours": "a while"}, "1 to 48"),
    ):
        with pytest.raises(IntentError) as got:
            _params(op, **params)
        assert phrase in str(got.value), (op, str(got.value))
