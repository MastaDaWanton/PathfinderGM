"""`GMAgent._repair_sentences`: what the truth checks find is repaired the house way —
one rewrite of the flagged sentence with the fact named, kept only if the check no longer
finds it, then the member's deterministic backstop (docs/design-a-truth.md §4).

The measurement behind the shape is the project's own (CLAUDE.md, "detect mechanically,
repair with a targeted call") and Re3's: its whole-passage edit module changed nothing in
ablation, so nothing here rewrites a whole beat.
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import checks
from gm.checks import face_kept, refused_move

from _a_truth import MARKET, WAY_IN, context, scene_at

_REFUSED = [{"intent_id": "i1", "op": "travel", "status": "refused", "effects": [],
             "tell": "There is no the crossroads here to go to."}]


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _answer(monkeypatch, *sentences):
    asked: list = []
    queue = list(sentences)

    def fake_chat(messages, *a, **k):
        asked.append(messages)
        return _Reply(json.dumps({"sentence": queue.pop(0) if queue else ""}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    return asked


def test_a_rewrite_that_holds_is_kept(monkeypatch):
    agent, _ = scene_at(MARKET)
    text = "The stalls are loud. You set off toward the crossroads. What do you do?"
    ctx = context(agent, text, outcomes=_REFUSED)
    found = checks.run(ctx)
    asked = _answer(monkeypatch, "You look toward the crossroads, but stay by the stalls.")
    out, notes, attempts = agent._repair_sentences(text, found, ctx)
    assert out == ("The stalls are loud. You look toward the crossroads, but stay by the "
                   "stalls. What do you do?")
    assert len(asked) == 1 and len(attempts) == 1
    assert "still at the market" in asked[0][1]["content"]


def test_a_rewrite_that_still_moves_them_falls_to_the_backstop(monkeypatch):
    agent, _ = scene_at(MARKET)
    text = "The stalls are loud. You set off toward the crossroads. What do you do?"
    ctx = context(agent, text, outcomes=_REFUSED)
    _answer(monkeypatch, "You head out toward the crossroads at a run.")
    out, notes, _ = agent._repair_sentences(text, checks.run(ctx), ctx)
    assert out == "The stalls are loud. You are still at the market."
    assert any("still did it" in n for n in notes)
    assert refused_move.find(context(agent, out, outcomes=_REFUSED)) == []


def test_at_most_three_calls_a_beat_and_the_backstop_takes_the_rest(monkeypatch):
    agent, _ = scene_at(MARKET)
    text = ("You walk toward the road. You head north. You set off east. You make your "
            "way west. You reach the ford.")
    ctx = context(agent, text, outcomes=_REFUSED)
    asked = _answer(monkeypatch)
    out, _, _ = agent._repair_sentences(text, checks.run(ctx), ctx)
    assert len(asked) == 3
    assert out == "You are still at the market."


def test_a_face_has_no_backstop_and_a_failed_rewrite_is_left_as_written(monkeypatch):
    agent, _ = scene_at(WAY_IN, [("the watchman waving traffic through", "watchman")])
    a = next(x for x in agent.engine.scene.actors.values() if not x.is_pc)
    a.described, a.appearance = True, "Orc: old enough to have stopped counting."
    text = "The watchman is a young man with a quick grin."
    ctx = context(agent, text)
    found = face_kept.find(ctx)
    assert found
    _answer(monkeypatch, "The watchman is a young man with a quicker grin.")
    out, notes, _ = agent._repair_sentences(text, found, ctx)
    assert out == text
    assert any("no backstop" in n for n in notes)


def test_the_groom_runs_the_truth_pass_and_logs_it(monkeypatch):
    """Through the real door: `_groom` with a context runs the registered checks after
    the attribution and logs one `truth-checks` row."""
    agent, _ = scene_at(MARKET)
    text = "You set off toward the crossroads. What do you do?"
    _answer(monkeypatch)
    ctx = agent._beat_context("turn", player_input="I go to the crossroads", brief="",
                              outcomes=[__import__("_a_truth").outcome(_REFUSED[0])])
    out, repairs, _ = agent._groom(text, ctx=ctx, rewrite=False, claims=False)
    assert "set off" not in out and "still at the market" in out
    assert any(r.get("kind") == "truth-checks" for r in agent.mention_rows)
