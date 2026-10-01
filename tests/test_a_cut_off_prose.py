"""Item 6 of docs/playtest-2026-09-30.md: prose cut off mid-word.

Measured: the rewrite (`polish`) ran under a 1,600-character grammar ceiling, lower than
the 1,800 the prose call writes under; Ollama closed the string at exactly 1,600
characters, mid-word; `_accept` took the cut rewrite and `ensure_hand_back` added
". What do you do?" — "They don't wait for you to pick it up. They'. What do you do?",
reproduced byte for byte. Nothing detected an unfinished ending.

Across the replay corpus (tests/replay/*.jsonl.gz) 18 of 341 prose replies end
mid-sentence — six of them polish rewrites at 1,621-1,914 raw characters ("…whether to
offer a more helpful", "…grip the l") and one turn's prose at 1,828.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from gm import agent as agent_mod
from gm import narration, prompts, speech

from _a_truth import MARKET, scene_at

REPLAY = Path(__file__).parent / "replay"


def test_the_measured_fragment_is_trimmed_not_given_a_full_stop():
    """"…pick it up. They'" + the hand-back became "…They'. What do you do?"."""
    text = ("Coins scatter across the boards. They don't wait for you to pick it up. "
            "They'")
    out, added = narration.ensure_hand_back(text)
    assert added
    assert out == ("Coins scatter across the boards. They don't wait for you to pick it "
                   "up. What do you do?")


def test_a_cut_inside_a_line_closes_the_line():
    kept, gone = narration.trim_unfinished(
        "He leans in. 'Some are willing for a few coins. Others require a heav")
    assert kept == "He leans in. 'Some are willing for a few coins.'"
    assert gone == "Others require a heav"


def test_finished_beats_are_left_alone():
    for text in ("The door shuts. What do you do?", "He waits. 'Go home.'",
                 "He nods. 'Go home,'", "It ends on an ellipsis..."):
        assert narration.trim_unfinished(text) == (text, "")
    # With no whole sentence to fall back to, nothing is cut.
    assert narration.trim_unfinished("A few,") == ("A few,", "")


def test_every_unfinished_reply_in_the_corpus_is_cut_to_a_sentence():
    """25 of 341 prose replies in the corpus end unfinished: 18 are real cut-offs, and
    every one of them, trimmed, ends on a whole sentence; the other 7 are the plan call's
    "-" placeholder, with no sentence to fall back to, and are left alone."""
    seen = cut = 0
    for path in sorted(REPLAY.glob("*.jsonl.gz")):
        for line in gzip.open(path, "rt", encoding="utf-8"):
            for call in json.loads(line).get("calls", []):
                try:
                    text = json.loads(call.get("raw") or "").get("narration", "")
                except (ValueError, AttributeError):
                    continue
                if not isinstance(text, str) or not text.strip():
                    continue
                text, _ = speech.lift(text)
                if not narration.ends_unfinished(text):
                    continue
                seen += 1
                kept, gone = narration.trim_unfinished(text)
                if gone:
                    cut += 1
                    assert not narration.ends_unfinished(kept)
    assert seen == 25 and cut == 18


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def test_polish_writes_under_the_grammar_ceiling_and_refuses_a_cut_rewrite(monkeypatch):
    """The ceiling was 1,600; it is the prose call's own 1,800. And a rewrite that still
    ends unfinished after trimming — no whole sentence in it — is never accepted."""
    agent, _ = scene_at(MARKET)
    schemas: list = []

    def fake_chat(messages, *a, **k):
        schemas.append(k.get("schema"))
        return _Reply(json.dumps({"narration": "and then the"}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    draft = "You stand in the market. " * 3   # too short, no hand-back: polish is asked
    out, notes, attempts = agent.polish(draft.strip(), min_chars=1500)
    assert schemas and schemas[0]["properties"]["narration"]["maxLength"] == \
        prompts.GRAMMAR_MAXLENGTH_CEILING == 1800
    assert out == draft.strip()
