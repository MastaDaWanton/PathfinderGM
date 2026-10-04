"""A wedged Ollama is said in two minutes, not half an hour (`client.ModelStalled`).

Measured 2026-10-03 on this machine. After a normal reply at 20:50, Ollama took every
later request and answered none: the game's turn and a five-token probe both sat silent,
while `/api/ps` went on answering and listing the model as loaded. At 21:35 the idle model
was unloaded, and every reload failed in Ollama's log ("llama-server GPU discovery watchdog
timed out", "Load failed … timed out waiting for llama-server"), on a healthy, nearly empty
GPU. The game waited its full 600-second cold-load allowance on every call, several calls a
turn, with the page reading "The GM is thinking." The owner asked for the plain answer
instead: the model has stopped; restart Ollama.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from gm import client


class _Resp:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.text.encode("utf-8")


def _ollama(monkeypatch, *, ps=("gemma:latest",), chat=None):
    """A fake Ollama: `/api/ps` lists `ps`; `/api/chat` runs `chat(req, timeout)`."""
    seen = {}

    def urlopen(req, *a, timeout=None, **kw):
        url = str(getattr(req, "full_url", req))
        if url.endswith("/api/ps"):
            return _Resp(json.dumps({"models": [{"name": n} for n in ps]}))
        seen["timeout"] = timeout
        seen["payload"] = json.loads(req.data.decode("utf-8"))
        return chat(req, timeout)

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    return seen


def _silent(req, timeout):
    raise TimeoutError("timed out")


def test_a_loaded_model_that_sends_nothing_is_a_stall_said_plainly(monkeypatch):
    """The 20:51 turn: the model listed as loaded, nothing back. Given up after
    `STALL_SECONDS`, not 600, and the player is told what to do."""
    seen = _ollama(monkeypatch, chat=_silent)
    with pytest.raises(client.ModelStalled) as exc:
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    assert seen["timeout"] == client.STALL_SECONDS < 600
    msg = str(exc.value)
    assert "restart" in msg.lower() or "start it again" in msg
    assert "not your game" in msg and "not been lost" in msg


def test_a_model_not_loaded_keeps_the_cold_load_allowance(monkeypatch):
    """A cold load is genuinely slow (104.8 s on a three-token reply): not loaded, the
    caller's own allowance stands, and running out of it is the old 'did not answer'."""
    seen = _ollama(monkeypatch, ps=(), chat=_silent)
    with pytest.raises(client.ModelUnavailable) as exc:
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    assert seen["timeout"] == 600
    assert not isinstance(exc.value, client.ModelStalled)


def test_ollama_that_cannot_start_the_model_is_the_same_answer(monkeypatch):
    """The 21:35 and 22:23 loads: Ollama answered, and could not start the model."""
    def failed(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 500, "Internal Server Error", {},
            __import__("io").BytesIO(b'{"error":"timed out waiting for llama-server to '
                                     b'start: context deadline exceeded"}'))

    _ollama(monkeypatch, ps=(), chat=failed)
    with pytest.raises(client.ModelStalled) as exc:
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    assert "llama-server" in str(exc.value) and "start it again" in str(exc.value)


def test_a_streamed_reply_is_read_whole(monkeypatch):
    """Streamed so silence can be told from work: the chunks' content is joined, the last
    chunk's counts kept, and the request asks for the stream."""
    lines = [{"message": {"content": '{"narration": "The'}, "done": False},
             {"message": {"content": ' smith nods."}'}, "done": False},
             {"message": {"content": ""}, "done": True, "done_reason": "stop",
              "eval_count": 9}]
    seen = _ollama(monkeypatch, chat=lambda req, t: _Resp(
        "\n".join(json.dumps(x) for x in lines)))
    reply = client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    assert seen["payload"]["stream"] is True
    assert reply.json() == {"narration": "The smith nods."}


def test_an_error_line_in_the_stream_is_not_a_reply(monkeypatch):
    _ollama(monkeypatch, chat=lambda req, t: _Resp(json.dumps({"error": "out of memory"})))
    with pytest.raises(client.ModelUnavailable, match="out of memory"):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")


def test_a_stall_does_not_hand_the_turn_to_a_backup_on_the_same_ollama(monkeypatch):
    """A wedged Ollama is wedged for every model it serves: the backup on the same host
    would stall too, two more minutes of the player's turn for nothing."""
    from gm import agent as agent_mod
    from play import modelcfg
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc
    from tests.test_a_model_that_is_down_hands_on import _World

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    g = agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))
    monkeypatch.setattr(modelcfg, "for_role",
                        lambda role: {"model": "spare-model", "host": g.host}
                        if role == "fallback" else {})
    monkeypatch.setattr(client, "probe",
                        lambda *a, **k: client.Probe(True, installed=("spare-model:latest",)))
    asked = []

    def chat(messages, model, *a, **kw):
        asked.append(model)
        raise client.ModelStalled("stopped answering")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    with pytest.raises(client.ModelStalled):
        g.plan_turn("I look around.", [])
    assert asked == [g.model], asked
