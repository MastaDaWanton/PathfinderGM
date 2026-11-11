"""A model's wrong-typed param is a refusal with the fix named, never a crash.

The params schema the model is sampled against is a bare object (gm/prompts.py), so the
TYPE of each value is the model's to get wrong. Review 2026-11-11, finding 5: a sweep of
every op's every param with thirteen wrong-typed values (`probe_ops.py`) found 100 distinct
(op, param, exception) crashes that were not IntentError — ValueError, TypeError,
AttributeError, KeyError, OverflowError, IndexError — each a 500 or a 502 with the
player's line popped, where a refusal would have gone back round the plan loop. After the
fix the same sweep found none.

Every payload below is one the sweep or the review ran, with the exception it raised.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse
from rules.sheet import load_pc


@pytest.fixture
def table():
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    hand = instantiate("guildhand", scene=scene, name="the guildhand")
    scene.add(hand)
    return Engine(scene, Dice(seed=1)), hand.ref


def _refused(engine, raw, match):
    with pytest.raises(IntentError, match=match):
        engine.run(engine.validate([raw]))


def test_a_cast_square_is_read_like_an_attack_or_a_move_square():
    """`cast` with `"square": "5,3"` raised `ValueError: invalid literal for int() with
    base 10: ','` at rules/areas.py:207 out of validate — the copy of the `_square` fix
    that attack and move got and cast did not."""
    cast = {"op": "cast", "actor": "pc", "params": {"spell": "burning hands"}}
    for said in ("5,3", [5, 3], {"col": 5, "row": 3}):
        got = parse({**cast, "params": {**cast["params"], "square": said}})
        assert got.params["square"] == (5, 3)
    for bad in ({"x": 5, "y": 3}, ["a", "b"], [5], 7, True):
        with pytest.raises(IntentError, match="cast: square must"):
            parse({**cast, "params": {**cast["params"], "square": bad}})


def test_a_save_branch_that_is_not_an_object_is_refused_or_read():
    """`save` with `"on_failure": ["shaken"]` raised `AttributeError: 'list' object has
    no attribute 'get'` at rules/engine.py:8058, at resolution. A bare condition name is
    exactly `{"condition": name}`; nothing else has an honest reading."""
    save = {"op": "save", "actor": "pc", "params": {"save": "will", "dc": 15}}
    got = parse({**save, "params": {**save["params"], "on_failure": "Shaken"}})
    assert got.params["on_failure"] == {"condition": "shaken"}
    for bad in (["shaken"], 5, "half the room", {"condition": ["shaken"]}):
        with pytest.raises(IntentError, match="on_failure is an object"):
            parse({**save, "params": {**save["params"], "on_failure": bad}})


def test_a_string_save_branch_resolves_as_the_condition(table):
    """The coerced branch runs: before, the string form never got past resolution."""
    engine, _ = table
    done = engine.run(engine.validate([{
        "op": "save", "actor": "pc", "visibility": "hidden",
        "params": {"save": "will", "dc": 99, "on_failure": "shaken"}}]))
    assert engine.scene.actors["pc"].has_condition("shaken"), done.outcomes[0].tell


def test_the_mover_is_checked_as_a_ref(table):
    """`move` with `"who": "the guildhand"` raised `KeyError: 'the guildhand'` at
    rules/engine.py:22265 — `to` was checked as a ref and `who` was not."""
    engine, _ = table
    _refused(engine, {"op": "move", "actor": "pc",
                      "params": {"who": "the guildhand", "zone": "near"}},
             "unknown mover 'the guildhand'; known refs are")


@pytest.mark.parametrize("op", ["extinguish", "break_free"])
def test_an_op_that_reads_its_actor_refuses_having_none(table, op):
    """`extinguish` and `break_free` with no actor raised `KeyError: None` at
    rules/engine.py:23624 and :23676; with a name for a ref, `KeyError: 'two'`."""
    engine, _ = table
    _refused(engine, {"op": op, "params": {}}, "unknown actor None")
    _refused(engine, {"op": op, "actor": "two", "params": {}}, "unknown actor 'two'")


@pytest.mark.parametrize("op", ["use_item", "sell", "buy"])
def test_a_trade_by_somebody_who_is_not_here_is_refused(table, op):
    """`buy` with `"actor": "two"` raised `KeyError: 'two'` at resolution. No actor at
    all is still the player's own trade (the 2026-10-03 default), not a refusal."""
    engine, _ = table
    _refused(engine, {"op": op, "actor": "two", "params": {"item": "dagger"}},
             "unknown actor 'two'")
    assert engine.validate([{"op": op, "params": {"item": "dagger"}}])[0].actor == "pc"


def test_a_condition_on_nobody_is_refused(table):
    """`condition` with no actor, target or `to` raised `KeyError: None` at
    rules/engine.py:17053."""
    engine, _ = table
    _refused(engine, {"op": "condition", "params": {"condition": "prone"}},
             "nobody is named for it to land on")
    _refused(engine, {"op": "condition", "actor": "two", "params": {"condition": "prone"}},
             "unknown actor 'two'")


@pytest.mark.parametrize("op, key", [("buy", "count"), ("sell", "count"),
                                     ("spend_pools", "count"), ("blood_pool", "amount")])
def test_a_count_that_is_not_a_number_is_refused(op, key):
    """`buy` with `"count": "two"` raised `ValueError: invalid literal for int()` at
    rules/engine.py:19788; a list raised TypeError; `Infinity` raised OverflowError."""
    base = {"item": "dagger"} if op in ("buy", "sell") else {}
    for bad in ("two", [1], float("inf")):
        with pytest.raises(IntentError, match="is not a number"):
            parse({"op": op, "actor": "pc", "params": {**base, key: bad}})
    assert parse({"op": op, "actor": "pc", "params": {**base, key: "3"}}).params[key] == 3


def test_spend_pools_keeps_its_own_word():
    """"all" is the op's own count (Hemorrhagic Eruption) and must survive the bound."""
    assert parse({"op": "spend_pools", "actor": "pc",
                  "params": {"count": "all"}}).params["count"] == "all"


def test_infinity_is_not_a_number():
    """JSON's `Infinity` parses to a float; `int(inf)` raised OverflowError at
    rules/intents.py:277, which `_bounded` did not catch — attack.iteration, work.days,
    forage.hours, give.count and introduce.count each died in validate."""
    inf = float("inf")
    for raw in ({"op": "attack", "actor": "pc", "target": "c1", "params": {"iteration": inf}},
                {"op": "give", "actor": "pc", "target": "c1",
                 "params": {"item": "arrow", "count": inf}},
                {"op": "forage", "actor": "pc", "params": {"hours": inf}},
                {"op": "work", "actor": "pc", "params": {"days": inf}},
                {"op": "introduce", "params": {"who": "a smith", "count": inf}}):
        with pytest.raises(IntentError, match="number"):
            parse(raw)


def test_an_actor_is_one_ref():
    """`"actor": ["pc"]` raised `TypeError: unhashable type: 'list'` out of validate for
    44 ops, and `"actor": 3` a `KeyError: 3` at resolution for six."""
    for bad in (["pc"], {"a": 1}, 3, True):
        with pytest.raises(IntentError, match="actor is one ref"):
            parse({"op": "say", "actor": bad, "params": {"words": "hello"}})


def test_one_target_in_a_list_is_that_target(table):
    """`attack` with `"target": ["c1"]` raised `TypeError: unhashable type: 'list'` at
    resolution — the roster was keyed with the list."""
    engine, ref = table
    got = engine.validate([{"op": "attack", "actor": "pc", "target": [ref], "params": {}}])
    assert got[0].target == ref


@pytest.mark.parametrize("raw", [
    {"op": "compel", "actor": "pc", "params": {"to": 0}},
    {"op": "give", "actor": "pc", "target": "c1", "params": {"item": "dagger", "to": ["c1"]}},
    {"op": "buy", "actor": "pc", "params": {"item": "dagger", "from_": ["c1"]}},
    {"op": "wear", "actor": "pc", "params": {"item": "dagger", "actor": ["pc"]}},
    {"op": "move", "actor": "pc", "params": {"who": ["c1"]}},
])
def test_a_param_that_names_somebody_is_one_ref(raw):
    """`"to": 0` slipped past every truthiness check to `KeyError: 0` in compel and
    guard; a list in `to`, `from_`, `who` or a param `actor` was `TypeError: unhashable
    type: 'list'` at resolution."""
    with pytest.raises(IntentError, match="is one ref, a string"):
        parse(raw)


def test_the_lower_likelihood_shapes_are_refused_or_read():
    """quest.objectives 3 (`TypeError: 'int' object is not iterable`, engine.py:16062),
    attack.undecided true (the same, engine.py:8258), condition.descriptors true
    (states.py:1006), begin_encounter sides `{"foes": null}` (intents.py:1759),
    travel.with 3 (engine.py:3625), move.square "" (`IndexError`, grid.py:291)."""
    with pytest.raises(IntentError, match="objectives is a list of sentences"):
        parse({"op": "quest", "actor": "pc", "params": {"title": "Find it", "objectives": 3}})
    got = parse({"op": "attack", "actor": "pc", "target": "c1", "params": {"undecided": True}})
    assert "undecided" not in got.params
    kept = parse({"op": "attack", "actor": "pc", "target": "c1",
                  "params": {"undecided": ["c1", "c2"]}})
    assert kept.params["undecided"] == ["c1", "c2"]
    with pytest.raises(IntentError, match="descriptors is a list of words"):
        parse({"op": "condition", "actor": "pc", "params": {"condition": "prone",
                                                            "descriptors": True}})
    # A bare string was iterated letter by letter and named no descriptor at all.
    assert parse({"op": "condition", "actor": "pc", "params": {
        "condition": "prone", "descriptors": "fear"}}).params["descriptors"] == ["fear"]
    for sides in ({"party": ["pc"], "foes": None}, {"a": 1}):
        with pytest.raises(IntentError, match="sides is a map of side name"):
            parse({"op": "begin_encounter", "params": {"sides": sides}})
    assert parse({"op": "begin_encounter", "params": {"sides": {"you": "pc"}}}
                 ).params["sides"] == {"you": ["pc"]}
    with pytest.raises(IntentError, match="with is a list of the refs"):
        parse({"op": "travel", "actor": "pc", "params": {"place": "the market", "with": 3}})
    assert "square" not in parse({"op": "move", "actor": "pc",
                                  "params": {"zone": "near", "square": ""}}).params
    for params in ("hello", [1], 5):
        with pytest.raises(IntentError, match="params must be an object"):
            parse({"op": "say", "actor": "pc", "params": params})


def test_the_ref_repair_survives_a_string_opposed_by(table):
    """`opposed_by: "c1"` raised `AttributeError: 'str' object has no attribute 'get'`
    at gm/judgement.py:1869, inside the repair that runs AFTER validation has refused
    the plan — so the refusal became a crash."""
    from gm import judgement

    engine, _ = table
    raw = [{"op": "check", "actor": "pc",
            "params": {"skill": "perception", "opposed_by": "c1"}},
           {"op": "say", "actor": "pc", "params": "hello"}]
    judgement.repair_unknown_refs(raw, "I look around", engine.scene)


def test_a_creature_turn_holds_back_on_a_type_error():
    """The two NPC-turn handlers caught (IntentError, ValueError, KeyError): a
    wrong-typed plan that raised TypeError or AttributeError at resolution took the
    PLAYER's request down as a 500 on a turn already finished. Walked in the AST, and
    counted: exactly the two creature-turn handlers are wide, because the player-turn
    handlers must NOT be widened — a bug there stays loud."""
    import ast
    from pathlib import Path

    from play import views

    tree = ast.parse(Path(views.__file__).read_text(encoding="utf-8"))
    caught = [{getattr(e, "id", "") for e in h.type.elts}
              for h in ast.walk(tree)
              if isinstance(h, ast.ExceptHandler) and isinstance(h.type, ast.Tuple)]
    wide = [names for names in caught if {"IntentError", "TypeError"} <= names]
    assert wide == [{"IntentError", "ValueError", "KeyError", "TypeError",
                     "AttributeError"}] * 2
