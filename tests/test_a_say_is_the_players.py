"""A `say` in the player's character's mouth carries the player's words (item 6).

Measured on the Bobby playtest, 2026-09-28, turn 3: "I ask him about the girl in the
market" reached the engine as Bobby saying the watchman's line — "She doesn't like the
desperate ones, but she's a friend to those who know what they're looking for" — minted
by `_merge_declared` with `because: "the player's words commit the turn to it"`, and told
as "Bobby speaks, to the effect that…". Across the seven PC says in the five saves the
content-word overlap with the player's line was 1.0 six times and 0.0 once: this one.
"""
from __future__ import annotations

import pytest

import replays
from gm import judgement
from gm.agent import GMAgent

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


@corpus
def test_the_watchmans_line_is_no_longer_bobbys():
    r = replays.case("watchman-line-booked-as-bobby")["record"]
    said = [i for i in r["plan"]["intents"] if i["op"] == "say"]
    assert said[0]["params"]["words"].startswith("She doesn't like the desperate ones")
    raw = [{k: i[k] for k in ("op", "actor", "target", "because", "params")}
           for i in r["plan"]["intents"]]
    notes: list[str] = []
    out = judgement.own_words_only(raw, r["player"], r["plan"]["reading"], notes=notes)
    say = [i for i in out if i["op"] == "say"]
    assert say[0]["params"]["words"] == "about the girl in the market"
    assert "desperate" not in str(out)
    assert notes and "never wrote" in notes[0]


def test_the_merge_no_longer_mints_the_models_words():
    raw = GMAgent._merge_declared([], {"say": {"params": {"words": "Fine day for it."},
                                               "target": "c1"}})
    assert raw == [{"op": "say", "params": {}, "target": "c1",
                    "because": "the player's words commit the turn to it"}]
    out = judgement.own_words_only(raw, 'I tell him "Good morning to you."', None)
    assert out[0]["params"]["words"] == "Good morning to you."


def test_the_players_own_words_stand_and_an_npcs_say_is_theirs():
    mine = {"op": "say", "params": {"words": "Where is the well?"}}
    theirs = {"op": "say", "actor": "c1", "params": {"words": "Go away."}}
    out = judgement.own_words_only([mine, theirs], 'I ask "Where is the well?"', None)
    assert out == [mine, theirs]


def test_a_say_with_no_words_of_the_players_to_give_is_dropped():
    out = judgement.own_words_only(
        [{"op": "say", "params": {"words": "Lovely weather."}},
         {"op": "travel", "params": {"place": "the market"}}],
        "I head to the market", None)
    assert [i["op"] for i in out] == ["travel"]
