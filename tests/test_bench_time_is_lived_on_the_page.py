"""Bench time is lived through, and told on the bench's own page (owner report 2026-11-01).

Measured on Ansel's save: every step bench's roll called `c.scene.advance(plan.minutes)`
and nothing else. His session's drying and the steps around it put 9.5 days on the clock;
the pack's food ran out on day 4 and he starved through days 4 to 9 without the bench
asking; and the hunger, fatigue and sleep of all of it stayed queued for the narrator and
came out on his next typed turn, told as travel. Now (`play/bench_clock.py`) work of a day
or more that the pack cannot carry the body through is refused before the die, and what
the body lives through on a step is written to the transcript and taken off the queue.
"""
from __future__ import annotations

import ast
from pathlib import Path

from play import alchemy_views, bench_views, enchant_views, forge_views, leather_views
from play import campaign as cm
from tests.test_bench_api import _carry, _key, _post, bench  # noqa: F401

# 48 doses of Glowcap decoction: 48 x 120 minutes = 5,760, four days at the bench.
FOUR_DAYS = 48


def _brew_body(client, face=1):
    return {"method": "brew", "face": face,
            "items": [{"key": _key(client, "Glowcap"), "count": FOUR_DAYS}]}


def test_four_days_of_brewing_with_no_food_is_refused_before_the_die(bench):
    """No food in the pack carries the body 72 hours (the book's three days of grace), so
    four days of brewing is refused: 409, the reason in words, and nothing rolled, spent or
    passed -- the clock, the herbs and the transcript are exactly as they were. The check
    says so too, and greys Roll."""
    _carry(glowcap=FOUR_DAYS)
    c = cm.current()
    pc = c.scene.pc()
    pc.goods.update({"waterskin": 20})
    before = (c.scene.clock_minutes, pc.inventory["glowcap"], len(c.transcript))
    checked = _post(bench, "/api/bench/check", _brew_body(bench))
    assert checked["minutes"] == 5760 and checked["can_roll"] is False
    assert any("cannot work 4 days" in p for p in checked["problems"]), checked["problems"]
    said = _post(bench, "/api/bench/roll", _brew_body(bench), status=409)["error"]
    assert "cannot work 4 days" in said and "food" in said and "smaller batch" in said, said
    c = cm.current()
    pc = c.scene.pc()
    assert (c.scene.clock_minutes, pc.inventory["glowcap"], len(c.transcript)) == before
    assert not bench_views._PENDING


def test_a_bench_steps_body_toll_is_told_on_the_page_not_on_the_next_turn(bench):
    """With food and water for the stretch the same four days are worked: the body eats
    and drinks from the pack, the stretch is one transcript consequence line naming its
    span and the meals, the roll's JSON carries it as `lived`, and the scene's body queue
    holds nothing of the player's for the next typed turn (`Scene._body_said`), where
    Ansel's 9.5 days surfaced as travel."""
    _carry(glowcap=FOUR_DAYS)
    c = cm.current()
    pc = c.scene.pc()
    pc.goods.update({"waterskin": 20, "trail rations": 10})
    r = _post(bench, "/api/bench/roll", _brew_body(bench))
    assert r["minutes"] == 5760
    c = cm.current()
    pc = c.scene.pc()
    told = [t["text"] for t in c.transcript if "works 4 days" in str(t.get("text"))]
    assert len(told) == 1, told
    assert "eats" in told[0] and "trail rations" in told[0], told[0]
    assert r["lived"] and r["lived"][0] in told[0]
    assert [x for x in c.scene._body_said if str(x.get("ref")) == str(pc.ref)] == []


def test_a_ten_minute_step_writes_no_second_log_line(bench):
    """A 10-minute grind lives through nothing worth a line: the roll adds only its own
    (a miss here), never an empty 'works 10 minutes' beside it. Measured before on the
    herb bench: two log lines for every step was a complaint."""
    _carry(comfrey=1)
    before = len(cm.current().transcript)
    r = _post(bench, "/api/bench/roll", {"method": "grind", "face": 1, "items": [
        {"key": _key(bench, "Comfrey"), "count": 1}]})
    assert r["lived"] == []
    assert len(cm.current().transcript) - before == (0 if r["roll"]["success"] else 1)


def test_all_five_step_bench_rolls_use_the_one_door():
    """The herb bench, the forge, the circle, the alchemy bench and the leather bench each
    asked `c.scene.advance(plan.minutes)` on its own; every roll door now refuses and passes
    its time through `bench_clock`, so no copy of the silent clock survives. Walked as
    an AST (tests/test_suite_isolation.py caps source-text pins)."""
    for mod, name in ((bench_views, "bench_roll"), (forge_views, "forge_roll"),
                      (enchant_views, "enchant_roll"), (alchemy_views, "alchemy_roll"),
                      (leather_views, "leather_roll")):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.setdefault(ast.unparse(node.func), []).append(node.lineno)
        assert "c.scene.advance" not in calls, name
        assert "bench_clock.refusal" in calls and "bench_clock.pass_time" in calls, name
        # The refusal comes before the die is thrown.
        assert min(calls["bench_clock.refusal"]) < min(calls["engine.dice.d20"]), name
