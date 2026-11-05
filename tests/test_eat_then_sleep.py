"""A meal said before a sleep is eaten before it (owner report 2026-11-01, Ansel).

"have a bite to eat and then sleep" was read `consume: a bite`, `rest`. The act→op table
owed `rest` for the second action and nothing for the first — a meal is the survival
door's (`judgement.inject_survival`), not an op the reading names — so `order` could
place the rest and not the plan's `eat`, written last. The turn ran: "Ansel rests for 8
hours. Ansel wakes still fatigued: hunger holds it until Ansel eats", THEN "Ansel has no
bread to eat". One of one eat-then-sleep lines ran backwards.
"""
from __future__ import annotations

from gm import acts_to_ops as a2o


def _rows(*acts_and_ops):
    rows = []
    for k, (act, ops) in enumerate(acts_and_ops):
        r = a2o.Row(index=k, act=act)
        r.ops = list(ops)
        rows.append(r)
    return rows


def test_the_meal_before_the_sleep_runs_before_it():
    rows = _rows(("consume", []), ("rest", ["rest"]))
    raw = [{"op": "narrate_only"},
           {"op": "rest", "actor": "pc", "params": {"kind": "night"}},
           {"op": "eat", "actor": "pc", "params": {"item": "bread"}}]
    assert [r["op"] for r in a2o.order(raw, rows)] == ["narrate_only", "eat", "rest"]


def test_a_drink_after_a_sleep_stays_after_it():
    """The other order is the words' too: "I sleep, then drink from the well"."""
    rows = _rows(("rest", ["rest"]), ("consume", []))
    raw = [{"op": "drink", "actor": "pc", "params": {}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert [r["op"] for r in a2o.order(raw, rows)] == ["rest", "drink"]


def test_placing_a_meal_does_not_make_the_plan_owe_one():
    """Owned for order only: the schema's `declared` keys stay what the reading names, so
    a line that drinks is never made to carry an `eat`."""
    rows = _rows(("consume", []), ("rest", ["rest"]))
    assert a2o.declared(rows) == ["rest"]
