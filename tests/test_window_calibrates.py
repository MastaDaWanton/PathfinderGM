"""The prompt budget is measured off the model, not assumed (gm/window.py).

Measured 2026-10-08 in a player's log, igorls/gemma-4-12B-it-heretic on a 16k window:

    stopped at its token limit (prompt 16250 tokens of 16384, reply 134 tokens)

The budget was (16384 - 1400 - 600) x 3.6 = 51,782 characters, with 3.6 characters a
token measured on OUR fixture world. The player's world ran about 3.2, so a full prompt
was 16,182 tokens before the chat template's wrapping, and the reply had 134 tokens left.

These tests drive `gm.client.chat` against a fake Ollama that counts tokens at 3.2
characters a token, plus four for each message's wrapping, the way the real one reports
`prompt_eval_count`, and cuts the reply where the window ends.
"""
from __future__ import annotations

import json
import math

import pytest

from gm import client, prompts, window

RATIO = 3.2
WRAP = 4


def _tokens(messages) -> int:
    chars = sum(len(m.get("content") or "") for m in messages)
    return math.ceil(chars / RATIO) + WRAP * len(messages)


class _Ollama:
    """Answers /api/chat like Ollama does for a prompt that leaves too little room: the
    reply stops where the window ends, `done_reason=length`."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, req, *a, **kw):
        url = str(getattr(req, "full_url", req))
        if url.endswith("/api/ps"):
            return _Resp({"models": []})
        payload = json.loads(req.data.decode("utf-8"))
        prompt = _tokens(payload["messages"])
        ctx = payload["options"]["num_ctx"]
        want = payload["options"]["num_predict"]
        room = max(0, ctx - prompt)
        reply = min(want, room, 60)       # a short answer, unless the window cuts it
        cut = room < min(want, 60)
        self.calls.append({"prompt": prompt, "room": room, "want": want, "cut": cut,
                           "messages": payload["messages"]})
        return _Resp({"message": {"content": '{"narration": "ok"}'},
                      "done_reason": "length" if cut else "stop",
                      "prompt_eval_count": min(prompt, ctx), "eval_count": reply})


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


@pytest.fixture
def ollama(monkeypatch):
    fake = _Ollama()
    monkeypatch.setattr(client.urllib.request, "urlopen", fake)
    return fake


def _history(turns: int, beat: int = 850):
    out = []
    for n in range(turns):
        out += [{"role": "user", "content": f"I ask the trader about seal {n}"},
                {"role": "assistant", "content": "x" * beat}]
    return out


BRIEF = "HERE: the market.\n" + "a fact about this place\n" * 40


def test_the_shipped_ratio_overflows_a_world_that_tokenises_at_three_point_two():
    """The defect, measured in the player's log: the full shipped budget, counted at 3.2
    characters a token, leaves the reply far less than MAX_COMPLETION_TOKENS."""
    messages = prompts.call_one_messages(BRIEF, _history(200), "I ask again")
    tokens = _tokens(messages)
    assert prompts.NUM_CTX - tokens < prompts.MAX_COMPLETION_TOKENS, (
        f"{tokens} tokens left {prompts.NUM_CTX - tokens} for the reply")


def test_after_one_call_the_next_prompt_fits_with_room_to_answer(ollama):
    """Before: the first full prompt, sized at the shipped 3.6, is cut off by the window.
    After: the model's own count has been read, and the next prompt for that model
    leaves MAX_COMPLETION_TOKENS free."""
    first = prompts.call_one_messages(BRIEF, _history(200), "I ask again", model="gemma")
    reply = client.chat(first, "gemma", num_predict=prompts.MAX_COMPLETION_TOKENS)
    assert reply.cut_off, "the uncalibrated prompt should have overflowed (the defect)"
    assert ollama.calls[0]["room"] < prompts.MAX_COMPLETION_TOKENS

    # Read off the call. A little above 3.2: Ollama counts no more than the window of an
    # overflowing prompt, so that one reading is an upper bound, and still enough.
    assert window.chars_per_token("gemma") < 3.3
    second = prompts.call_one_messages(BRIEF, _history(200), "I ask again", model="gemma")
    reply = client.chat(second, "gemma", num_predict=prompts.MAX_COMPLETION_TOKENS)
    assert not reply.cut_off
    assert ollama.calls[1]["room"] >= prompts.MAX_COMPLETION_TOKENS, ollama.calls[1]["room"]
    # The prose call is packed the same way.
    prose = prompts.call_prose_messages(BRIEF, _history(200), "I ask again",
                                        tells=["The engine decided a thing."],
                                        earlier=["y" * 1600], model="gemma")
    assert prompts.NUM_CTX - _tokens(prose) >= prompts.MAX_COMPLETION_TOKENS


def test_a_retry_that_appends_its_failed_reply_is_cut_to_fit(ollama, caplog):
    """The calls `pack` never sees: a retry appends the failed reply (up to 1,400 tokens)
    and a correction to a prompt already at the budget. `client.chat` cuts the oldest
    conversation, keeps the system message, the pinned note and the last message, never
    opens on a reply, and says so in the log."""
    import logging

    from play.opening import NOTE_PREFIX

    window.observe("gemma", 40000, math.ceil(40000 / RATIO))
    note = {"role": "user", "content": NOTE_PREFIX + " the smugglers owe the reeve."}
    packed = prompts.call_one_messages(BRIEF, [note] + _history(200), "I ask again",
                                       model="gemma")
    retry = packed + [{"role": "assistant", "content": "z" * 5000},
                      {"role": "user", "content": "That reply was wrong: fix it."}]
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        reply = client.chat(retry, "gemma", num_predict=prompts.MAX_COMPLETION_TOKENS)
    assert not reply.cut_off
    sent = ollama.calls[-1]["messages"]
    assert ollama.calls[-1]["room"] >= prompts.MAX_COMPLETION_TOKENS
    assert sent[0] == retry[0] and sent[-1] == retry[-1]
    assert note in sent, "the GM's pinned note was cut"
    assert len(sent) < len(retry)
    kept = [m for m in sent[1:] if not str(m["content"]).startswith(NOTE_PREFIX)]
    assert kept[0]["role"] == "user", "what was kept opens on a reply"
    assert any("cut to fit the window" in r.message for r in caplog.records)


def test_the_ratio_is_held_between_the_floor_and_the_shipped_value():
    window.observe("m", 50000, 10000)            # 5.0: better than ours, not trusted
    assert window.chars_per_token("m") == window.SHIPPED
    window.observe("m", 50000, 50000)            # 1.0: a wild reading
    assert window.chars_per_token("m") == window.FLOOR
    assert window.prompt_budget_chars("m") >= int(
        (prompts.NUM_CTX - prompts.MAX_COMPLETION_TOKENS - prompts.SAFETY_TOKENS)
        * window.FLOOR)


def test_a_small_prompt_is_no_reading():
    """Four characters of chat template a message is a large share of a 500-character
    prompt: the ratio would read low for reasons that are not the text."""
    assert window.observe("m", 500, 400) is None
    assert window.chars_per_token("m") == window.SHIPPED


def test_one_model_reading_badly_does_not_shrink_another_models_prompt():
    window.observe("bad", 40000, 20000)
    assert window.chars_per_token("bad") == 2.0
    assert window.chars_per_token("good") == window.SHIPPED
    # A prompt that does not know its model is sized for the worst seen.
    assert window.chars_per_token(None) == 2.0


def test_the_worst_reading_survives_a_restart_and_a_stale_file_is_not_trusted():
    """CLAUDE.md: a cache in the data folder outlives every reinstall. It is stamped with
    its format and the shipped ratio it was measured against, and read back only when
    both match."""
    window._reset()
    window.observe("gemma", 40000, 12500)        # 3.2
    saved = json.loads(window._path().read_text(encoding="utf-8"))
    assert saved["format"] == window.FORMAT and saved["shipped"] == window.SHIPPED
    assert saved["models"]["gemma:latest"] == pytest.approx(3.2)

    window._SEEN.clear()
    window._LOADED = False                       # a new process
    assert window.chars_per_token("gemma") == pytest.approx(3.2)

    saved["shipped"] = 4.0                       # written by a build with another ratio
    window._path().write_text(json.dumps(saved), encoding="utf-8")
    window._SEEN.clear()
    window._LOADED = False
    assert window.chars_per_token("gemma") == window.SHIPPED

    window._path().write_text("{torn", encoding="utf-8")
    window._SEEN.clear()
    window._LOADED = False
    assert window.chars_per_token("gemma") == window.SHIPPED


def test_an_old_bad_reading_ages_out():
    window.observe("m", 40000, 16000)            # 2.5
    for _ in range(window.KEEP):
        window.observe("m", 40000, 11500)        # 3.48
    assert window.chars_per_token("m") == pytest.approx(40000 / 11500)


def test_the_budget_leaves_room_for_the_calls_own_reply():
    """A watcher call asks for 100 tokens and a prose call for 1,400; each is given the
    window less its own answer, not a fixed one."""
    small = window.prompt_budget_chars("m", completion=100)
    large = window.prompt_budget_chars("m", completion=1400)
    assert small - large == int(1300 * window.SHIPPED) or abs(
        (small - large) - 1300 * window.SHIPPED) < 2


def test_many_short_messages_do_not_read_as_a_worse_tokeniser():
    """Measured 2026-10-08 on the shipped model: the interpreter's call, 108 messages
    and 19,641 characters, came back as 6,287 tokens (3.12 raw) while the narrator's
    30-message calls read 3.9. The template's tokens a message are taken off first."""
    assert window.observe("gemma", 19641, 6287, messages=108) == pytest.approx(
        19641 / (6287 - 4 * 108))
    assert window.chars_per_token("gemma") > 3.3
