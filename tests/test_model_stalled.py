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


# --- remembered (ponytail audit 2026-11-07, finding #6) ------------------------------------
#
# Only the planner honoured `ModelStalled`. The interpreter, the free narrator, the retries
# and every read-back caught it as a plain `Exception` and called again: a stall at the
# interpreter cost 120 s and the planner then waited another 120 s; a stall mid-groom cost
# 120 s per read-back.


def test_a_stalled_host_is_refused_at_once_for_the_next_call(monkeypatch):
    """The second call to a wedged Ollama raised after a fresh 120-second wait on 0.2.27;
    remembered, it never reaches `/api/chat` at all."""
    calls = []

    def silent(req, timeout):
        calls.append(timeout)
        raise TimeoutError("timed out")

    _ollama(monkeypatch, chat=silent)
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    with pytest.raises(client.ModelStalled) as exc:
        client.chat([{"role": "user", "content": "y"}], "other-model",
                    "http://localhost:11434/")
    assert len(calls) == 1, calls
    assert "start it again" in str(exc.value)


def test_a_restarted_ollama_is_let_through_inside_the_minute(monkeypatch):
    """The sentence says restart Ollama and send the line again. Restarted, the model is
    no longer loaded (`/api/ps` lists nothing), and the call goes to the new server
    rather than being answered "restart Ollama" for the rest of the minute."""
    _ollama(monkeypatch, chat=_silent)
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    _ollama(monkeypatch, ps=(), chat=lambda req, t: _Resp(json.dumps(
        {"message": {"content": "back"}, "done": True})))
    reply = client.chat([{"role": "user", "content": "x"}], "gemma",
                        "http://localhost:11434")
    assert reply.text == "back"
    assert client._stalls == {}


def test_a_stall_is_forgotten_after_the_minute(monkeypatch):
    _ollama(monkeypatch, chat=_silent)
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    when, *rest = client._stalls["http://localhost:11434"]
    client._stalls["http://localhost:11434"] = (when - client.STALL_MEMORY_SECONDS - 1,
                                                *rest)
    _ollama(monkeypatch, chat=lambda req, t: _Resp(json.dumps(
        {"message": {"content": "ok"}, "done": True})))
    assert client.chat([{"role": "user", "content": "x"}], "gemma",
                       "http://localhost:11434").text == "ok"


def test_stalled_since_names_a_stall_any_call_met(monkeypatch):
    """For the narrator's boundary (`agent.surfaces_a_stall`): a read-back that swallowed
    the stall still leaves it on record."""
    import time

    started = time.monotonic()
    assert client.stalled_since(started, ["http://localhost:11434"]) is None
    _ollama(monkeypatch, chat=_silent)
    try:
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    except Exception:  # noqa: BLE001 — swallowed, as a read-back does
        pass
    got = client.stalled_since(started, ["http://localhost:11434/"])
    assert isinstance(got, client.ModelStalled)
    assert client.stalled_since(time.monotonic() + 1, ["http://localhost:11434"]) is None
    assert client.stalled_since(started, ["http://elsewhere:11434"]) is None


def test_another_http_error_is_named_not_called_unreachable(monkeypatch):
    """Ponytail audit, smaller finding: any HTTP error but 400-grammar, 404 and a load
    failure was re-raised bare, and an `HTTPError` is a `URLError`, so the player read
    "cannot reach Ollama … Start Ollama" from a server that had just answered."""
    def refused(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 500, "Internal Server Error", {},
            __import__("io").BytesIO(b'{"error":"out of memory"}'))

    _ollama(monkeypatch, chat=refused)
    with pytest.raises(client.ModelUnavailable) as exc:
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    msg = str(exc.value)
    assert "cannot reach" not in msg and "Start Ollama" not in msg
    assert "HTTP 500" in msg and "out of memory" in msg
    assert not isinstance(exc.value, client.ModelStalled)


# --- the background watcher's stall is its own (review 2026-11-11, finding 11) -------------

def test_the_watchers_stall_is_not_the_players(monkeypatch):
    """`_stalls` is one memory per host, and the watcher's call wrote to it like any
    other. The watcher runs on a daemon thread after the turn; its request queues behind
    whatever the player's next line is doing on the same Ollama, hears nothing for
    `STALL_SECONDS`, and records a stall. Measured on 7f63ab60 with a stubbed transport:
    after one silent watcher call, the player's next call was refused in milliseconds
    with "The model has stopped answering" and never reached a server that would have
    answered it (0 requests sent). A call that passes `remember_stall=False` still
    raises its own ModelStalled, and leaves nothing behind for anybody else."""
    _ollama(monkeypatch, chat=_silent)
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434",
                    remember_stall=False)
    assert client._stalls == {}

    sent = []
    _ollama(monkeypatch, chat=lambda req, t: sent.append(1) or _Resp(json.dumps(
        {"message": {"content": "the smith looks up"}, "done": True})))
    started = 0.0
    reply = client.chat([{"role": "user", "content": "x"}], "gemma",
                        "http://localhost:11434")
    assert reply.text == "the smith looks up" and sent == [1]
    assert client.stalled_since(started, ["http://localhost:11434"]) is None


def test_the_watcher_still_stands_down_for_a_stall_the_player_met(monkeypatch):
    """The other direction is kept: a stall a foreground call recorded still refuses the
    watcher at once, so a wedged Ollama is not asked again from the background."""
    calls = []

    def silent(req, timeout):
        calls.append(1)
        raise TimeoutError("timed out")

    _ollama(monkeypatch, chat=silent)
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434")
    with pytest.raises(client.ModelStalled):
        client.chat([{"role": "user", "content": "x"}], "gemma", "http://localhost:11434",
                    remember_stall=False)
    assert len(calls) == 1


def test_the_watcher_is_the_caller_that_does_not_remember(monkeypatch):
    """The wiring: every watcher model call goes through `_ask`, on a daemon thread."""
    from gm import watcher

    seen = {}

    def chat(messages, model, host, **kw):
        seen.update(kw)
        raise client.ModelStalled("stalled")

    monkeypatch.setattr(watcher.client, "chat", chat)
    with pytest.raises(client.ModelStalled):
        watcher._ask([{"role": "user", "content": "x"}], {"model": "gemma"},
                     {"type": "object", "properties": {}})
    assert seen["remember_stall"] is False
