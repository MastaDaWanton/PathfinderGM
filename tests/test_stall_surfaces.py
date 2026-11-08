"""A wedged Ollama is said wherever in the turn it is met (ponytail audit #6).

The audit, 2026-11-07, against 0.2.26: `client.ModelStalled` ("restart Ollama") was
honoured only by the planner. The interpreter, the free narrator, the retries and every
read-back caught it as a plain `Exception` and carried on: a stall at the interpreter
cost 120 s and then the planner waited another 120 s; a stall mid-groom cost 120 s per
read-back; and under Free narration the player never saw the restart sentence at all —
the view rendered the raw tells and said nothing (under Planned too: `_finish` caught the
re-raised stall as `ModelUnavailable` and rendered the tells).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import agent as agent_mod
from gm import client


def _stall_on(host, model="gemma"):
    """What the real `client.chat` does on a stall: remember it, then raise it."""
    return client._remember_stall(host, model, True, client.ModelStalled(
        "The model has stopped answering. Quit Ollama from its tray icon, start it "
        "again, and send your line again. Your turn has not been lost."))


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"
        self.cut_off = False

    def json(self):
        return json.loads(self.text)


def _agent():
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc
    from tests.test_a_model_that_is_down_hands_on import _World

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    return agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))


def test_a_swallowed_stall_still_ends_the_beat():
    """A read-back that "must never lose the turn" swallowed the stall, and the beat went
    on half-groomed; `surfaces_a_stall` gives it up once, at the narrator's boundary."""
    class Narrator:
        host = "http://localhost:11434"
        prose_host = "http://localhost:11434"

        @agent_mod.surfaces_a_stall
        def narrate(self):
            try:
                raise _stall_on(self.prose_host)
            except Exception:  # noqa: BLE001 — as every read-back does
                return "a half-groomed beat"

        @agent_mod.surfaces_a_stall
        def fine(self):
            return "a beat"

    with pytest.raises(client.ModelStalled):
        Narrator().narrate()
    client._stalls.clear()
    assert Narrator().fine() == "a beat"


def test_a_stall_on_another_host_is_not_this_narrators():
    class Narrator:
        host = prose_host = "http://localhost:11434"

        @agent_mod.surfaces_a_stall
        def narrate(self):
            _stall_on("http://elsewhere:11434")
            return "a beat"

    assert Narrator().narrate() == "a beat"


def test_the_interpreter_does_not_read_past_a_stall(monkeypatch):
    """On 0.2.27 the interpreter's stall became `{"error": …}` and the planner was asked
    next, on the same wedged Ollama: two waits. Now the reader's stall is the turn's."""
    from gm import interpret

    g = _agent()
    monkeypatch.setattr(interpret, "ENABLED", True)
    monkeypatch.setattr(interpret, "handed", lambda text: None)

    def stalled(text, **kw):
        raise _stall_on(g.host)

    asked = []
    monkeypatch.setattr(interpret, "interpret", stalled)
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: asked.append(a[1]) or _Reply("{}"))
    with pytest.raises(client.ModelStalled):
        g.plan_turn("I look around.", [])
    assert asked == [], "the planner was asked after the reader stalled"


def test_the_free_draft_gives_up_on_a_stall(monkeypatch):
    """`_free_draft` caught the stall, moved to the spare on the same Ollama and returned
    "" — the turn shipped the raw tells with no word of why."""
    from play import modelcfg

    g = _agent()
    monkeypatch.setattr(modelcfg, "for_role",
                        lambda role: {"model": "spare-model", "host": g.prose_host}
                        if role == "fallback" else {})
    monkeypatch.setattr(client, "has_model", lambda *a, **k: True)
    asked = []

    def chat(messages, model, host, *a, **kw):
        asked.append(model)
        raise _stall_on(host, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    with pytest.raises(client.ModelStalled):
        g.narrate_turn([], "I look around.", "BRIEF")
    assert asked == [g.prose_model], asked


@pytest.fixture
def game(tmp_path, monkeypatch):
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)

    def plan(agent, text, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "looks around"}]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.save()
        yield c
        cm._LIVE.clear()


def test_the_player_is_told_when_the_narrator_stalls_after_the_turn(game, monkeypatch):
    """The view rendered the engine's own lines and said nothing. Now the reply carries
    the restart sentence — not the client's own, which ends "send your line again", and
    sent again here the deed would happen twice."""
    from play import views

    def chat(messages, model, host="http://localhost:11434", *a, **kw):
        raise _stall_on(host, model)

    monkeypatch.setattr(client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": "I look around."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    body = r.json()
    assert body["stalled"] == views.STALLED_AFTER_THE_TURN
    assert "send your line again" not in body["stalled"]
    assert body["transcript"][-1]["who"] == "gm"


def test_an_ordinary_turn_carries_no_stall(game, monkeypatch):
    monkeypatch.setattr(client, "chat", lambda *a, **k: _Reply(json.dumps(
        {"narration": "You look around the square. " * 6 + "What do you do?",
         "suggestions": []})))
    r = Client().post("/api/say", data=json.dumps({"text": "I look around."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    assert "stalled" not in r.json()


def test_the_page_shows_the_stall_beside_the_turn():
    """The table draws `stalled` as it draws a stall before the turn: the sentence and
    "Make a report" (04-combat-and-turns.js `showStalled`)."""
    from pathlib import Path

    js = Path("play/static/js/table/02-state.js").read_text(encoding="utf-8")
    assert "s.stalled" in js and "showStalled(s.stalled)" in js
