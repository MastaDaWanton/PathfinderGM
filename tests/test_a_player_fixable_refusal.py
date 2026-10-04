"""A refusal only the player can fix goes to the player once (item 21.3), and the refusal
codes Lane A places (docs/fix-interfaces.md §2.6).

The measurement, turn 12 of the Bobby playtest (2026-09-28): "I cast burning hands into
the tree tops" with nothing prepared. "cast: Bobby did not prepare Burning Hands today."
came back 7 times of 7 — five attempts on the narrator, two on the fallback — and the turn
was then disguised as `narrate_only` with "the moment does not answer". No plan could have
fixed it; the fix was the player's.
"""
from __future__ import annotations

import json

import pytest

import replays
from gm import agent as agent_mod
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc

from _a_truth import VORMOOR, WORLD


class _Reply:
    def __init__(self, text, model="fake"):
        self.text, self.seconds, self.model = text, 0.0, model

    def json(self):
        return json.loads(self.text)


def _wizard_agent():
    s = Scene(location_id=VORMOOR.id)
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.spellbook = ["burning-hands"]
    pc.prepared = {}
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party()
    gm = agent_mod.GMAgent(WORLD, e)
    return gm


@pytest.fixture
def coded_cast(monkeypatch):
    """The cast refusal's code is Lane E's to place in `_check_cast` (register §2.6: E owns
    that method). Until E merges, it is stood in here exactly as the register gives it —
    `code="unprepared"`, `fix={"kind": "prepare", "spell": id}` — and is a no-op once
    E's own code is there."""
    real = Engine._check_cast

    def coded(self, intent, index):
        try:
            real(self, intent, index)
        except IntentError as exc:
            if not exc.code and "did not prepare" in str(exc):
                exc.code = "unprepared"
                exc.fix = {"kind": "prepare", "spell": str(intent.params.get("spell"))}
            raise

    monkeypatch.setattr(Engine, "_check_cast", coded)


def _script(monkeypatch, reply: dict):
    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        return _Reply(json.dumps(reply))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    return calls


def test_the_unprepared_cast_is_one_refusal_and_no_retries(monkeypatch, coded_cast):
    """G2's replay proof: turn 12's player line through `plan_turn`, the model answering
    the cast every time as both models did. Before: 7 identical legality refusals, then
    "the moment does not answer". Now: one plan call, one refusal, the plan's
    `refusal` carrying the code and the fix — and nothing resolved."""
    line = "I cast burning hands into the tree tops"
    if replays.available():
        assert replays.case("unprepared-burning-hands")["record"]["player"] == line
        was = replays.turn(12)["plan"]["rejections"]
        assert sum("did not prepare Burning Hands" in r for r in was) == 7
    gm = _wizard_agent()
    calls = _script(monkeypatch, {"narration": "", "intents": [
        {"op": "cast", "actor": "pc", "params": {"spell": "burning-hands"}}]})
    # The reading declares the cast since 2026-10-03: with none, the plan stands alone and
    # its cast is an op nobody asked for (docs/structured-turn.md).
    from gm import interpret

    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "cast", "object": "burning hands", "place": "the tree tops"}]})
    plan = gm.plan_turn(line, history=[])
    assert len(calls) == 1, "one plan call, no retry and no second model"
    # The sentence is Lane E's `for_a_person` from `_check_cast` since both lanes merged:
    # the player-facing line with its fix named, not the engine's third-person reason.
    assert plan.refusal == {"text": "Burning Hands is not prepared. Prepare it in the "
                                    "Spells tab first.",
                            "code": "unprepared",
                            "fix": {"kind": "prepare", "spell": "burning-hands"}}
    assert [i.op for i in plan.intents] == ["narrate_only"]
    assert "does not answer" not in plan.narration
    assert plan.narration == plan.refusal["text"]
    assert len(plan.rejections) == 1


def test_the_same_refusal_on_an_op_the_player_never_asked_for_is_dropped(
        monkeypatch, coded_cast):
    """"I look around" declares no cast. A plan that casts anyway, unprepared, is the
    plan's invention: the cast goes, the rest of the turn stands, and nobody is refused
    anything they did not ask for."""
    gm = _wizard_agent()
    calls = _script(monkeypatch, {"narration": "", "intents": [
        {"op": "cast", "actor": "pc", "params": {"spell": "burning-hands"}},
        {"op": "narrate_only", "because": "looking"}]})
    plan = gm.plan_turn("I look around", history=[])
    assert plan.refusal is None
    assert [i.op for i in plan.intents] == ["narrate_only"]
    assert len(calls) == 1
    assert any("never asked for" in r for r in plan.rejections)


def test_a_plan_fixable_refusal_still_retries(monkeypatch):
    """The loop is unchanged for everything else: a travel to a place that is nowhere is
    the plan's to fix (code "no_such_place", not player-fixable), and it goes round."""
    gm = _wizard_agent()
    calls = _script(monkeypatch, {"narration": "", "intents": [
        {"op": "travel", "params": {"place": "the moon"}}]})
    plan = gm.plan_turn("I go to the moon", history=[])
    assert plan.refusal is None
    assert len(calls) > 1


def test_the_non_cast_legality_refusals_carry_codes():
    """Every raise in `_check_legality`'s non-cast branches names its refusal. Measured by
    the syntax tree, not the words: a raise with no code is the plan's to fix by default,
    and a new raise written without one should be a decision, not an accident."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "rules" / "engine.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Engine")
    legality = next(n for n in engine.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_check_legality")
    raises = [n for n in ast.walk(legality) if isinstance(n, ast.Raise)
              and isinstance(n.exc, ast.Call) and getattr(n.exc.func, "id", "") == "IntentError"]
    uncoded = [n.lineno for n in raises if not any(k.arg == "code" for k in n.exc.keywords)]
    assert len(raises) >= 25 and uncoded == []


def test_out_of_reach_is_the_players_and_the_player_reads_the_square():
    """"out_of_reach" is in PLAYER_FIXABLE: closing the distance is the character's move
    action to spend, and the refusal's `for_a_person` names the square the map names.
    Since the close-and-strike ruling (2026-09-29) a gap one move closes is walked, not
    refused, so this is asked with Kesst's move action already walked this round."""
    from rules.bestiary import instantiate

    # The board test_maneuver_reach.py measured the defect on: the thug fifteen feet off.
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=7))
    e._ensure_encounter("pc", "c1")
    s.move_spent["pc"] = s.round
    with pytest.raises(IntentError) as got:
        e.validate([{"op": "attack", "actor": "pc", "target": "c1", "params": {}}])
    assert got.value.code == "out_of_reach" and got.value.fixable_by == "player"
    assert "{" not in got.value.for_a_person
