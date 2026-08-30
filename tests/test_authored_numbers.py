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


# --- refusals that used to cost the whole turn ----------------------------------------


def test_a_passive_refuses_as_an_outcome_and_never_as_a_raise():
    """The 502 shape, and the one this repo has buried four times: the intent schema
    may REQUIRE the op the player declared, so a hard refusal is carried by every
    regeneration, refused every time, and the turn dies with a 502 where a sentence
    would have done.

    Nine ability names in the shipped class file reach this branch, and the raise sat
    twenty lines above `_op_use_ability`'s own comment stating the rule."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import from_dict, load_pc, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "blood bending", "level": 1, "ranks": {},
              "paths": ["battle blood"]})
    pc = from_dict(d, ref="pc")
    scene = Scene()
    scene.add(pc)
    e = Engine(scene, dice=Dice(seed=3))
    out = e.run(e.validate([{"op": "use_ability", "actor": "pc",
                             "params": {"ability": "swift strikes"},
                             "because": "t"}])).outcomes[-1]
    assert out.op == "use_ability"
    assert out.effects == [] and not out.rolls
    assert "always active" in out.tell


def test_the_engine_has_no_raise_where_a_refusal_belongs_in_use_ability():
    """A ratchet, not a boolean. `_op_use_ability` is reachable from every ability the
    class files list, and every raise inside it is a turn the player loses. One
    survives — the unknown-ability name, where a DIFFERENT intent genuinely would have
    worked, which is the test for a legitimate raise."""
    import ast
    from pathlib import Path

    source = Path("rules/engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_op_use_ability")
    raises = [n for n in ast.walk(fn)
              if isinstance(n, ast.Raise)
              and "IntentError" in ast.dump(n.exc or ast.Constant(None))]
    # Two survive, and both pass the test for a legitimate raise — a DIFFERENT intent
    # would have worked: "nobody here to use it" (name an actor who exists) and "has no
    # ability called X" (name an ability they have). The third, the passive, did not:
    # no other intent helps a player who owns an always-active ability, so it refuses
    # with a sentence instead.
    assert len(raises) <= 2, (
        f"{len(raises)} raises in _op_use_ability; a refusal the player could not "
        f"have predicted is an Outcome with a printable tell, never a raise")
