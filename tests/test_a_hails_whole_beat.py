"""Being spoken to opens a conversation: tags first, quotations over the whole beat
(item 13).

Measured on the Bobby playtest, 2026-09-28, turn 4: the prose tagged both of Drenn
Ironvale's lines `who=c4 to=you`, and the turn log read `hails_tagged: []`,
`hails_guessed: []`. `hailed_by` split the beat into sentences first and looked for
whole quotations inside each; "'You!" ends a sentence and "…" and "Tell me…" split the
second line, so no sentence held a quotation, and neither the tag nor the guess was read.
"""
from __future__ import annotations

import pytest

import replays
from gm import judgement, speech
from gm.checks._people import spans_in_context
from gm.narration import _sentences, introduced_by

from _a_truth import MARKET, people_named, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _drenn():
    r = replays.case("drenn-hails")["record"]
    agent, refs = scene_at(MARKET, people_named("Drenn Ironvale"))
    said = [dict(s, who=refs.get(s["who"], s["who"])) for s in replays.said(r)]
    return agent.engine.scene, replays.beat_text(r), said, refs["c4"]


@corpus
def test_drenns_two_tagged_lines_hail_the_player_where_they_did_not():
    """G2: 2 of 2 tagged Drenn lines open a conversation, where there were 0."""
    scene, text, said, drenn = _drenn()
    assert replays.turn(4)["speech_tags"][0]["hails_tagged"] == []
    to_you = [s for s in said if s["who"] == drenn and s["to"] == "you"]
    assert len(to_you) == 2
    # The measured cause: sentence by sentence, neither line is a whole quotation.
    per_sentence = [s for sent in _sentences(text) for s in speech.spans(sent)]
    whole = speech.spans(text)
    lines = [text[a + 1:b - 1] for a, b in whole]
    assert all(speech.speaker(to_you, ln) is None
               for sent in _sentences(text)
               for ln in (sent[a + 1:b - 1] for a, b in speech.spans(sent))), \
        "no single sentence held a whole Drenn line"
    assert sum(1 for ln in lines if speech.speaker(to_you, ln)) == 2
    assert len(per_sentence) < len(whole) or per_sentence != whole
    assert judgement.hailed_by(scene, text, said=said) == [drenn]


@corpus
def test_every_quotation_is_found_once_over_the_whole_beat():
    """Twenty quotations on the seven Bobby beats with speech, fourteen sentence by
    sentence (design A): the whole-beat scan finds each once, with the narration around
    it."""
    beats = [b["text"] for t in replays.turns() for b in t["beats"]
             if speech.has_speech(b["text"])]
    whole = sum(len(spans_in_context(b)) for b in beats)
    split = sum(len(speech.spans(s)) for b in beats for s in _sentences(b))
    assert whole > split
    for b in beats:
        for a, e, context in spans_in_context(b):
            assert b[a] in "'\"‘“" and "'" not in context[:1]


def test_a_tag_to_somebody_else_is_not_a_hail_and_a_dead_man_hails_nobody():
    agent, _ = scene_at(MARKET, [("the carter", "guildhand"), ("the drover", "guildhand")])
    scene = agent.engine.scene
    carter = next(r for r, a in scene.actors.items() if a.name == "the carter")
    drover = next(r for r, a in scene.actors.items() if a.name == "the drover")
    text = "The carter turns. 'You! Over here. Now.' He waves. 'Fine weather,' he adds."
    said = [{"who": carter, "to": "you", "line": "You! Over here. Now."},
            {"who": carter, "to": drover, "line": "Fine weather,"}]
    assert judgement.hailed_by(scene, text, said=said) == [carter]
    scene.actors[carter].hp = -20
    assert judgement.hailed_by(scene, text, said=said) == []


def test_a_tagged_line_rewritten_off_the_page_hails_nobody():
    agent, _ = scene_at(MARKET, [("the carter", "guildhand")])
    scene = agent.engine.scene
    carter = next(r for r, a in scene.actors.items() if a.name == "the carter")
    said = [{"who": carter, "to": "you", "line": "You there, move along."}]
    assert judgement.hailed_by(scene, "The carter says nothing at all.", said=said) == []


def test_an_untagged_line_across_a_full_stop_is_still_read_with_its_narration():
    """The guess, for lines the prose did not tag: found over the whole beat, and the
    speaker read from the narration around the line — here the sentence after it."""
    agent, _ = scene_at(MARKET, [("the carter", "guildhand")])
    scene = agent.engine.scene
    carter = next(r for r, a in scene.actors.items() if a.name == "the carter")
    text = "'You! Yes, you. Come here,' the carter calls."
    assert judgement.hailed_by(scene, text) == [carter]


def test_a_name_given_in_the_second_sentence_of_a_tagged_line_keeps_its_tag():
    """`introduced_by` read its tags sentence by sentence too — every copy of the rule."""
    text = "He looks up. 'You! I am Drenn Ironvale, and I need help.' He waits."
    said = [{"who": "c4", "to": "you", "line": "You! I am Drenn Ironvale, and I need help."}]
    got = introduced_by(text, said=said)
    assert [(name, ref) for _, name, ref in got] == [("Drenn Ironvale", "c4")]
