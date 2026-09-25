"""A model that cannot be reached hands the turn to the fallback; a cut-off reply is said.

Measured 2026-09-25: a `ModelUnavailable` inside `plan_turn`'s attempt loop — a timeout,
Ollama restarting under a loaded model — left the loop and aborted the turn, so the
fallback model the schedule exists to reach was never tried. And `done_reason` was never
read, so a reply cut off at the token limit looked in the log like a model writing badly.
"""
from __future__ import annotations

import json
import logging

import pytest

from gm import agent as agent_mod
from gm import client
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


class _World:
    name = "Testholme"
    secret = ""
    premise: dict = {}
    entities: dict = {}
    unwritten: list = []
    chronology: list = []
    factions: list = []

    def ancestors(self, _):
        return []


@pytest.fixture
def gm(monkeypatch):
    from play import modelcfg

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=1))
    g = agent_mod.GMAgent(_World(), engine)
    monkeypatch.setattr(modelcfg, "for_role",
                        lambda role: {"model": "spare-model", "host": "http://x"}
                        if role == "fallback" else {})
    return g


def test_the_fallback_is_tried_when_the_primary_is_down(gm, monkeypatch):
    asked = []

    def chat(messages, model, *a, **kw):
        asked.append(model)
        if model != "spare-model":
            raise client.ModelUnavailable("timed out")
        return client.Reply(json.dumps({"narration": "", "intents": [
            {"op": "narrate_only", "because": "a look around"}]}), 0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    plan = gm.plan_turn("I look around.", [])
    assert asked[0] != "spare-model" and "spare-model" in asked
    assert asked.count(asked[0]) == 1, "a model that could not be reached was asked again"
    assert plan.intents


def test_with_every_model_down_the_player_is_told_to_start_ollama(gm, monkeypatch):
    def chat(*a, **kw):
        raise client.ModelUnavailable("cannot reach Ollama")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    with pytest.raises(client.ModelUnavailable):
        gm.plan_turn("I look around.", [])


def test_a_reply_cut_off_at_the_limit_is_said_in_the_log(monkeypatch, caplog):
    class Resp:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    body = {"message": {"content": '{"narration": "The woman stands by the'},
            "done_reason": "length", "prompt_eval_count": 16000, "eval_count": 10}
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *a, **kw: Resp(body))
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        client.chat([{"role": "user", "content": "x"}], model="gemma")
    assert any("token limit" in r.message for r in caplog.records)
