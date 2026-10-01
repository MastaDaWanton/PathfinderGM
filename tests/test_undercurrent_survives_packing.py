"""The GM's private undercurrent note survives a long campaign's prompt.

The note is planted as the first message of `c.history` at campaign open
(`play/campaign.py:_open_the_world`) and rewritten in place by the watcher
(`gm/watcher.py:_apply_undercurrent`), so it stays first. `prompts.pack` cuts older history
oldest-first, which made the note the FIRST thing cut the moment a campaign's history
outgrew the window. Measured 2026-10-01 against the shipped budget (51,782 characters):
with the worked examples shown, the cut began at turn 32 of a talk-only campaign
(24,285 characters of history), and the one message it took was the note. Every turn
after that, the planner never saw the undercurrent again, while the watcher went on
rewriting a note nobody read.

The traditions pin standing notes outside the history that gets trimmed: NovelAI's Memory
is its own context section at the top with its own trim rule, apart from the story text;
SillyTavern places the story string before the chat history and truncates the history
oldest-first. `pack` now does the same: the note rides in its own slot ahead of the
history and is never a candidate for the cut.
"""
from __future__ import annotations

from gm import prompts
from play import opening


def _note() -> dict:
    return {"role": "user",
            "content": opening.private_note("The guild is skimming the grain tithe.")}


def _turns(n: int) -> list[dict]:
    out: list[dict] = []
    for i in range(n):
        out += [{"role": "user", "content": f"I look around the square, turn {i}. " * 4},
                {"role": "assistant", "content": '{"intents": []}'},
                {"role": "assistant", "content": "The square is busy. " * 30}]
    return out


def _has_note(messages) -> bool:
    return any(str(m.get("content", "")).startswith(opening.NOTE_PREFIX) for m in messages)


def test_the_note_survives_once_the_history_is_cut():
    """Turn 32 was where the cut started and the note was its first casualty."""
    history = [_note()] + _turns(60)
    report: dict = {}
    messages = prompts.call_one_messages("BRIEF " * 200, history, "I wait.", report=report)
    assert report["dropped"] > 0, "the premise: this history has outgrown the window"
    assert _has_note(messages), "the undercurrent was cut with the oldest history"


def test_the_note_is_pinned_ahead_of_the_history_it_used_to_lead():
    """Where it sat before when nothing was cut — after the examples, before the first
    exchange — so a campaign short enough to fit sends exactly the prompt it always did."""
    history = [_note()] + _turns(3)
    messages = prompts.call_one_messages("BRIEF", history, "I wait.")
    i = next(k for k, m in enumerate(messages)
             if str(m.get("content", "")).startswith(opening.NOTE_PREFIX))
    assert messages[i + 1]["content"] == history[1]["content"]
    assert messages == prompts.call_one_messages("BRIEF", history, "I wait.")


def test_a_note_the_watcher_appended_later_is_pinned_too():
    """A campaign opened with no undercurrent gets its first note appended by the watcher
    mid-history (`_apply_undercurrent`'s else branch). It is just as standing a note."""
    history = _turns(40) + [_note()] + _turns(40)
    messages = prompts.call_one_messages("BRIEF " * 200, history, "I wait.")
    assert _has_note(messages)
    assert sum(_has_note([m]) for m in messages) == 1


def test_the_ledger_edge_still_counts_original_history():
    """The ledger stamps each entry with the history length when it was written, and
    `pack` passes it the index of the first message still in the window. Taking the note
    out of the history must not shift that index by one: the kept stretch starts at the
    same original message whether or not the note rides in its own slot."""
    history = [_note()] + _turns(60)
    # One entry per history length, so whichever index the cut lands on, the entries
    # either side of it are there to check.
    ledger = [{"text": f"fact{h}.", "hist": h} for h in range(1, len(history) + 1)]
    report: dict = {}
    messages = prompts.call_one_messages("BRIEF " * 200, history, "I wait.",
                                         report=report, ledger=ledger)
    # The report counts what the model did not see; the pinned note is seen, so the
    # first message still in the window sits one past the count in the original history.
    first = report["dropped"] + 1
    assert messages[[m["content"] for m in messages].index(history[first]["content"])]
    system = messages[0]["content"]
    assert f"fact{first}." in system, "a turn wholly cut was not handed to the ledger"
    assert f"fact{first + 1}." not in system, "a turn still in the window was told twice"
