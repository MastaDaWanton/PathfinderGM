"""The labelled set and the interpreter's grounding stay honest (docs/the-interpreter.md).

No model here: the live benchmark is tools/interpreter_bench.py, which needs Ollama. What
a test can hold is that the labels are what the frame promises — every slot the player's
own words — and that the grounding step drops what is not.
"""
from __future__ import annotations

from gm import interpret
from tests.interpreter.gold import GOLD
from tests.interpreter.score import same, score


def test_every_label_quotes_the_player():
    """A slot that is not in the sentence would teach the scorer to reward invention —
    the failure the frame exists to catch."""
    bad = []
    for g in GOLD:
        for a in g["actions"]:
            assert a["act"] in interpret.ACTS, (g["text"], a)
            for s in interpret.SLOTS:
                if a.get(s) and a[s].lower() not in g["text"].lower():
                    bad.append((g["text"], s, a[s]))
        for c in g["claims"]:
            if c.lower() not in g["text"].lower():
                bad.append((g["text"], "claim", c))
    assert not bad, bad


def test_the_set_covers_what_broke():
    """Every live misreading of 2026-09-27 is in the set, labelled."""
    texts = {g["text"] for g in GOLD}
    for broke in ("I go to the market and look for the bread seller.",
                  "I ask around for the woman who sold me bread.",
                  "I ask her name.", "I wait at the well until ten at night.",
                  "I go to the market and buy a coil of rope.",
                  "I find somewhere to sleep until morning."):
        assert broke in texts, broke
    assert len(GOLD) >= 200


def test_the_gold_scores_itself_perfectly():
    got = [{"question": g["question"], "actions": g["actions"]} for g in GOLD]
    s = score(GOLD, got)
    assert s["frame_exact"] == 1.0 and s["slot_p_r_f1"][2] == 1.0


def test_slots_compare_as_answers_not_strings():
    assert same("the woman who sold me bread", "woman who sold me bread")
    assert same("his", "him")
    assert not same("the woman", "the woman who sold me bread")


def test_a_slot_that_is_not_the_players_words_is_dropped():
    """The object substitution the intfiction.org testers saw ("examine phone" came back
    "examine note") is exactly what this refuses."""
    frame, dropped = interpret.ground(
        {"question": False, "claims": ["the guards flee"],
         "actions": [{"act": "buy", "object": "hemp rope", "target": "the stallholder"}]},
        "I buy a coil of rope from the stallholder.")
    assert frame["actions"] == [{"act": "buy", "target": "the stallholder"}]
    assert any("hemp rope" in d for d in dropped) and frame["claims"] == []
