"""A reader reply that cannot be parsed is a failed reading, not a reading of nothing.

Review 2026-11-11, finding 9. `interpret.interpret` caught the parse failure with
`except Exception: raw = {}` and returned a frame with no "error" key — `{"question":
False, "actions": [], "claims": []}`, which both callers (`gm/agent.py` and
`play/views.py`, each testing `"error" not in reading`) took as a GOOD reading in which
the player declared no deed. `interpret.gets_nothing` then answered True for it, the
answer that strips a give the plan made, and `acts_to_ops.table` built an empty table.
A reader that raised took the other, correct path: the plan alone.
"""
from __future__ import annotations

from gm import client, interpret

TEXT = "I take the knife from the table."


def _reply(monkeypatch, text):
    monkeypatch.setattr(client, "chat", lambda *a, **k: client.Reply(
        text=text, seconds=0.0, model="test"))


def test_a_reply_that_is_not_json_is_marked_failed(monkeypatch):
    """`reply.json()` raises ValueError on "I cannot help with that"; the frame came
    back without "error" and read as nothing declared."""
    _reply(monkeypatch, "I cannot help with that")
    frame = interpret.interpret(TEXT)
    assert frame.get("error") == "unreadable reply"
    assert frame["raw"] == "I cannot help with that"       # kept, for the turn log
    # What the consumers do with it: no reading to judge by, so nothing is stripped.
    assert interpret.gets_nothing(frame) is False


def test_a_reply_that_parses_is_still_a_reading(monkeypatch):
    _reply(monkeypatch, '{"question": false, "actions": [{"act": "take", '
                        '"object": "the knife", "span": "take the knife"}], "claims": []}')
    frame = interpret.interpret(TEXT)
    assert "error" not in frame
    assert [a["act"] for a in frame["actions"]] == ["take"]


def test_a_failed_reading_is_not_remembered_as_one():
    """The later readers ask `reading_of(text)` and most test only for None: an error
    frame left there would be the empty reading again, by another door — and a good
    reading of the same words from an earlier turn must not answer for the failed one."""
    interpret.remember(TEXT, {"question": False, "actions": [{"act": "take"}], "claims": []})
    interpret.remember(TEXT, {"question": False, "actions": [], "claims": [],
                              "error": "unreadable reply"})
    assert interpret.reading_of(TEXT) is None
