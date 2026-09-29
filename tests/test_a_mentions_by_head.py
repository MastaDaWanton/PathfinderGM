"""A person is found on the page by their head noun, never by the last word of their name
(item 4).

Measured 2026-09-28: `judgement._mentions` keyed a person on the last word of their name,
wrong for 12 of 12 opening companions ("through", "you" twice, "door", "table"…); "the old
man ahead of you" was "mentioned" in every beat by "you". `mentions._head` was wrong on 10
of 12. Bobby's watchman ("the watchman waving traffic through") was owed his face on the
beat that said "the way through" — his third — and on neither beat that said "the
watchman".
"""
from __future__ import annotations

import re

import pytest

import replays
from gm import judgement, mentions, narration
from play.opening import SITUATIONS

from _a_truth import WAY_IN, people_named, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")

WANT = ["woman", "man", "foreman", "man", "watchman", "crier", "apprentice", "servant",
        "drover", "stranger", "lamplighter", "neighbour"]


def _last_word_mentions(beat: str, name: str) -> bool:
    """The rule this replaces, kept here as the measurement."""
    words = [w for w in re.findall(r"[a-z]+", name.lower()) if len(w) >= 3]
    return bool(words) and bool(re.search(rf"\b{re.escape(words[-1])}s?\b", beat, re.I))


def test_mentions_head_is_right_for_the_twelve_companions():
    names = [s.who for s in SITUATIONS]
    assert [mentions._head(n) for n in names] == WANT


def test_the_old_man_ahead_of_you_is_not_in_every_beat():
    old_man = next(s.who for s in SITUATIONS if "ahead of you" in s.who)
    beat = "You look around the square. Nobody meets your eye."
    assert _last_word_mentions(beat, old_man), "the measured defect"
    assert not judgement._mentions(beat, old_man)
    assert judgement._mentions("The old man coughs.", old_man)


@corpus
def test_the_watchman_is_owed_a_face_on_beat_one_where_it_was_beat_three():
    """G2: the mentions proof. Beats 1–3 of the corpus in order, the watchman not yet
    described: the old rule reached him first on beat 3 ("the way through"); the head
    reaches him on beat 1, which uses him and does not describe him ("the heavy leather
    of his gloves creaking" is one worn thing, not a face)."""
    w = dict(people_named("the watchman waving traffic through")[0], described=False)
    agent, refs = scene_at(WAY_IN, [w])
    scene, ref = agent.engine.scene, refs["c1"]
    name = scene.actors[ref].name
    beats = [replays.beat_text(replays.turn(n)) for n in (1, 2, 3)]
    assert [_last_word_mentions(b, name) for b in beats] == [False, False, True]
    first_owed = next(i for i, b in enumerate(beats, 1)
                      if ref in judgement.settle_descriptions(scene, b))
    assert first_owed == 1


def test_a_gaze_or_one_worn_thing_is_not_a_face_and_a_body_is():
    assert narration.faceless("The watchman stands, his eyes fixed on the wagon.",
                              "the watchman waving traffic through")
    assert narration.faceless("The watchman shifts, the heavy leather of his gloves "
                              "creaking.", "the watchman waving traffic through")
    assert not narration.faceless("The watchman is an old Orc with rope-coloured hair.",
                                  "the watchman waving traffic through")
    assert not narration.faceless("The watchman wears a heavy coat and muddy boots.",
                                  "the watchman waving traffic through")


def test_the_page_keeps_the_first_description():
    agent, _ = scene_at(WAY_IN, [("the watchman waving traffic through", "watchman")])
    scene = agent.engine.scene
    ref = next(r for r, a in scene.actors.items() if not a.is_pc)
    beat = "The watchman is a grizzled Orc with a scar across his jaw. He nods."
    assert judgement.settle_descriptions(scene, beat) == []
    assert scene.actors[ref].described
    assert scene.actors[ref].described_as == [
        "The watchman is a grizzled Orc with a scar across his jaw."]


def test_going_through_the_gate_does_not_address_the_watchman():
    agent, _ = scene_at(WAY_IN, [("the watchman waving traffic through", "watchman")])
    scene = agent.engine.scene
    assert judgement.settle_descriptions(scene, "The gate is busy.",
                                         "I go through the gate") == []


def test_head_words_across_the_worlds_peoples(worlds):
    """A description headed by one of the world's own peoples is found by it, and the
    last word ("well") is not the person."""
    from rules import names as names_mod

    people = next(iter(names_mod.peoples(worlds).values()))
    name = f"the {people} by the well"
    assert judgement._mentions(f"The {people} nods slowly.", name)
    assert not judgement._mentions("The well is dry.", name)
    assert _last_word_mentions("The well is dry.", name)


def test_the_attribution_answers_first():
    class _Said:
        def mentioned_in(self, beat, ref):
            return ref == "c9"

    assert judgement._mentions("He says nothing.", "the drover", ref="c9",
                               attribution=_Said())
    assert not judgement._mentions("He says nothing.", "the drover", ref="c8",
                                   attribution=_Said())


def test_the_name_stems_keep_a_short_head_noun():
    assert "man" in narration._name_stems("man in a stained leather jerkin")
