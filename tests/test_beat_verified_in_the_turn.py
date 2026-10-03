"""`gm/checks/beat_verified.py` through the real repair path (`GMAgent._repair_sentences`,
`_groom`): the beat read back, the contradiction confirmed, one targeted rewrite with the
engine's fact named, the rewrite read back, and the backstop under it.

The model's replies are scripted by what each call asks for — the read (its schema holds
`player_ends_at`), the second read (`answer`), the rewrite (`sentence`) — so these pin the
plumbing, not the model. tests/test_beat_verify.py replays the model's real answers.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify as bv
from gm import checks, client
from gm.checks import beat_verified

from _a_truth import MARKET, context, outcome, scene_at

_REFUSED = [{"intent_id": "i1", "op": "travel", "status": "refused", "effects": [],
             "tell": "There is no the crossroads here to go to."}]


class _Reply:
    def __init__(self, obj):
        self.text = obj if isinstance(obj, str) else json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _empty(**over):
    out = {"player_ends_at": {"place": "the market", "quote": ""}, "changed_hands": [],
           "trades": [], "harmed": [], "arrived": [], "left": [],
           "time_of_day": {"part": "unstated", "quote": ""}}
    out.update(over)
    return out


@pytest.fixture
def scripted(monkeypatch):
    """A chat that answers the read from `reads` (in order, then "claims nothing"), the
    second read with `answers`, and a rewrite with `rewrites`; it records every ask."""
    monkeypatch.setattr(bv, "ENABLED", True)
    bv.clear_cache()
    beat_verified._CONFIRMED.clear()
    state = {"reads": [], "answers": [], "rewrites": [], "asked": []}

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        if "player_ends_at" in props:
            state["asked"].append(("read", messages[-1]["content"]))
            return _Reply(state["reads"].pop(0) if state["reads"] else _empty())
        if "answer" in props:
            state["asked"].append(("confirm", messages[-1]["content"]))
            return _Reply({"answer": state["answers"].pop(0) if state["answers"] else "yes"})
        state["asked"].append(("rewrite", messages[-1]["content"]))
        return _Reply({"sentence": state["rewrites"].pop(0) if state["rewrites"] else ""})

    monkeypatch.setattr(client, "chat", chat)
    yield state
    bv.clear_cache()
    beat_verified._CONFIRMED.clear()


def _moved_out():
    return _empty(player_ends_at={"place": bv.UNLISTED_PLACE,
                                  "quote": "You set off toward the crossroads"})


def test_a_refused_move_read_back_is_rewritten_and_the_rewrite_is_read_back(scripted):
    """The house shape: the read finds the move, the second read confirms it, one rewrite
    names the engine's fact, and the rewrite is read back — only its own sentence — before
    it is kept."""
    agent, _ = scene_at(MARKET)
    text = "The stalls are loud. You set off toward the crossroads. What do you do?"
    ctx = context(agent, text, outcomes=_REFUSED)
    scripted["reads"] = [_moved_out()]
    scripted["rewrites"] = ["You look toward the crossroads, but stay by the stalls."]
    found = checks.run(ctx)
    assert [f.kind for f in found] == ["beat-moves-player"]
    out, notes, attempts = agent._repair_sentences(text, found, ctx)
    assert out == ("The stalls are loud. You look toward the crossroads, but stay by the "
                   "stalls. What do you do?")
    kinds = [k for k, _ in scripted["asked"]]
    assert kinds == ["read", "confirm", "rewrite", "read"]
    assert "still at the market" in scripted["asked"][2][1]
    # The second read is of the rewritten sentence alone; the rest was read once.
    assert "The stalls are loud" not in scripted["asked"][3][1].split("Passage:")[-1]


def test_a_rewrite_that_still_moves_them_is_cut_from_the_move_on(scripted):
    agent, _ = scene_at(MARKET)
    text = "The stalls are loud. You set off toward the crossroads. What do you do?"
    ctx = context(agent, text, outcomes=_REFUSED)
    scripted["reads"] = [_moved_out(), _empty(player_ends_at={
        "place": bv.UNLISTED_PLACE, "quote": "You head out toward the crossroads"})]
    scripted["rewrites"] = ["You head out toward the crossroads at a run."]
    out, notes, _ = agent._repair_sentences(text, checks.run(ctx), ctx)
    assert out == "The stalls are loud. You are still at the market."
    assert any("still did it" in n for n in notes)


def test_a_contradiction_the_second_read_refutes_costs_nothing(scripted):
    agent, _ = scene_at(MARKET)
    text = "The stalls are loud. You set off toward the crossroads. What do you do?"
    ctx = context(agent, text, outcomes=_REFUSED)
    scripted["reads"] = [_moved_out()]
    scripted["answers"] = ["no"]
    assert beat_verified.find(ctx) == []
    # Asked again by the repair's backstop pass: neither read nor question costs a call.
    assert beat_verified.find(ctx) == []
    assert [k for k, _ in scripted["asked"]] == ["read", "confirm"]


def test_a_failed_read_costs_the_turn_nothing_and_is_logged(monkeypatch):
    """Ollama down: the member raises, the registry books a `check-error` row and the
    turn goes on with the other members' findings."""
    monkeypatch.setattr(bv, "ENABLED", True)
    bv.clear_cache()

    def down(*a, **k):
        raise ConnectionError("ollama is not running")

    monkeypatch.setattr(client, "chat", down)
    agent, _ = scene_at(MARKET)
    ctx = context(agent, "You set off toward the crossroads.", outcomes=_REFUSED)
    errors: list = []
    checks.run(ctx, errors=errors)
    assert [e["member"] for e in errors] == ["beat_verified"]
    assert "could not be read back" in errors[0]["error"]
    bv.clear_cache()


def test_without_a_route_or_switched_off_it_reads_nothing(scripted, monkeypatch):
    agent, _ = scene_at(MARKET)
    ctx = context(agent, "You set off toward the crossroads.", outcomes=_REFUSED)
    from dataclasses import replace

    assert beat_verified.find(replace(ctx, reader=None)) == []
    monkeypatch.setattr(bv, "ENABLED", False)
    assert beat_verified.find(ctx) == []
    assert scripted["asked"] == []


def test_a_refused_sale_the_page_never_mentions_gets_the_refusal(scripted):
    """The omission the owner measured (playtest 2026-10-03, item 8): the refusal "the
    one thing the player needed to read, was nowhere on it". With the page silent on the
    sale and never naming the thing, the engine's own refusal goes before the hand-back."""
    agent, _ = scene_at(MARKET)
    refusal = "The smith's counter is not open yet; it opens at first light."
    sale = {"intent_id": "i2", "op": "sell", "status": "refused", "effects": [],
            "tell": refusal, "params": {"item": "crate"}}
    text = "The forge is quiet and the coals are banked. What do you do?"
    ctx = context(agent, text, outcomes=[sale])
    found = checks.run(ctx)
    assert [f.kind for f in found] == ["beat-omits-outcome"]
    out, notes, _ = agent._repair_sentences(text, found, ctx)
    assert out == f"The forge is quiet and the coals are banked. {refusal} What do you do?"


def test_the_groom_logs_what_the_beat_was_read_as(scripted):
    """Through `_groom`: a `beat-verify` row beside the `truth-checks` row, holding the
    claims and the seconds — how the read's failure rate is measured from turn logs."""
    agent, _ = scene_at(MARKET)
    scripted["reads"] = [_moved_out()]
    ctx = agent._beat_context("turn", player_input="I go to the crossroads", brief="",
                              outcomes=[outcome(_REFUSED[0])])
    out, _r, _a = agent._groom("You set off toward the crossroads. What do you do?",
                               ctx=ctx, rewrite=False, claims=False)
    assert "set off" not in out and "still at the market" in out
    rows = [r for r in agent.mention_rows if r.get("kind") == "beat-verify"]
    assert rows and rows[0]["claims"][0]["category"] == "move"
