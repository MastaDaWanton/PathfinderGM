"""A word-detector's op stands only where an act of the reading stands behind it.

Ponytail audit 2026-11-07, finding #7: `interpret.supported` kept any detector op with no
`_OP_NEEDS` row, so `take_off`, `found`, `venture` and `check` survived a reading with
nothing but a `talk` act — and the take-off regex matches "I promise I'll never take off
my armour", so the promise took the armour off. "Models read, code validates"
(docs/structured-turn.md) held only for the ops somebody remembered to list. Now an op
with no row is dropped, except the closed-vocabulary declarers (`interpret.UNJUDGED`).
"""
from __future__ import annotations

import pytest

from gm import interpret, judgement


def _talk(says):
    return {"question": False, "claims": [], "actions": [
        {"span": f"say {says}", "says": says, "act": "talk", "cost": "free",
         "means": "ordinary"}]}


def test_the_promise_matches_the_take_off_detector():
    """The sentence the audit measured: the regex reads it as taking the armour off."""
    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    got = judgement.declare_take_off([], "I promise I'll never take off my armour", s)
    assert [r["op"] for r in got] == ["take_off"]


@pytest.mark.parametrize("op", ["take_off", "found", "venture"])
def test_a_talk_reading_backs_none_of_three(op):
    kept, dropped = interpret.supported([op], _talk("I'll never take off my armour"))
    assert kept == [] and dropped == [op]


def test_a_check_needs_a_deed_a_skill_rolls_for():
    """Speech backs a check (persuade, bluff, threaten are talk), so the check's row is
    wide; a reading of nothing but a purchase still backs none."""
    frame = {"question": False, "claims": [], "actions": [
        {"span": "buy a rope", "object": "a rope", "act": "buy", "cost": "addresses",
         "means": "ordinary"}]}
    kept, dropped = interpret.supported(["check"], frame)
    assert kept == [] and dropped == ["check"]


@pytest.mark.parametrize("op,act", [("take_off", "use"), ("take_off", "other"),
                                    ("found", "other"), ("found", "go"),
                                    ("venture", "go"), ("venture", "search"),
                                    ("check", "athletics"), ("check", "stealth"),
                                    ("check", "talk"), ("check", "search")])
def test_the_acts_that_back_them_keep_them(op, act):
    frame = {"question": False, "claims": [], "actions": [
        {"span": "x", "act": act, "cost": "quick", "means": "ordinary"}]}
    kept, dropped = interpret.supported([op], frame)
    assert kept == [op], (op, act, dropped)


def test_every_op_a_detector_can_declare_is_judged():
    """The class, not the four: every op `judgement.declared_ops` can name has a row, or
    is a closed-vocabulary declarer. A new detector op with neither fails here, before it
    can leak past the reading."""
    import ast
    from pathlib import Path

    assert judgement._DECLARERS, "no declarers found"
    declarers = {"declare_use_item", "declare_taste", "inject_survival", "declare_leaving",
                 "declare_going_to_a_place", "inject_ability", "inject_cast",
                 "inject_checks", "inject_introduce", "inject_provoke", "inject_say",
                 "inject_travel", "inject_forage", "inject_prospect", "inject_wait",
                 "_inject_found", "inject_venture", "inject_loot", "declare_take_off"}
    # The AST, not the source text (tests/test_suite_isolation.py's ceiling): every
    # `{"op": "<name>", …}` literal the declarers write.
    tree = ast.parse(Path(judgement.__file__).read_text(encoding="utf-8"))
    ops, seen = set(), set()
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in declarers:
            seen.add(fn.name)
            for node in ast.walk(fn):
                if isinstance(node, ast.Dict):
                    for k, v in zip(node.keys, node.values):
                        if isinstance(k, ast.Constant) and k.value == "op" \
                                and isinstance(v, ast.Constant) and isinstance(v.value, str):
                            ops.add(v.value)
    assert seen == declarers, declarers - seen
    ops |= {"use_item", "found", "travel", "journey"}
    ops.discard("narrate_only")     # only ever beside a forage already planned
    unjudged = sorted(op for op in ops
                      if op not in interpret._OP_NEEDS and op not in interpret.UNJUDGED)
    assert unjudged == [], unjudged


def test_an_op_with_no_row_and_no_exemption_is_dropped():
    kept, dropped = interpret.supported(["a_new_op"], _talk("hello"))
    assert kept == [] and dropped == ["a_new_op"]


def test_a_closed_vocabulary_declarer_is_not_judged():
    """An ability's name read against the sheet is not English read by a regex: the
    detector's own vocabulary is closed (the audit's exemption: spell, item, ability)."""
    kept, _ = interpret.supported(["use_ability"], _talk("hello"))
    assert kept == ["use_ability"]
