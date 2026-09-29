"""A damage roll that reached nobody is not narrated as a hit (item 22.4).

Measured on the Bobby playtest, 2026-09-28, turn 13: Burning Hands from the Spells tab
resolved with `targets: []` and "1d4 — 1", the man in the jerkin at 4 of 4, and the page
burned him — "the heat licks across his face", "the man is thrown backward", "his face
blackened by soot, his hands clutching his scorched arms", "a raspy growl of pain".
`contradicts_state` found 0 sentences: "man" was dropped as a three-letter word, the
wound sentences said "he" and "his", and no wound word was a burn or a fall.
"""
from __future__ import annotations

import pytest

import replays
from gm import narration
from gm.checks import empty_roll
from gm.checks._people import about

from _a_truth import APPROACH, context, people_named, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _burn():
    r = replays.case("spells-tab-no-targets")["record"]
    agent, refs = scene_at(APPROACH, people_named("man in a stained leather jerkin"))
    return agent, refs["c8"], context(agent, replays.beat_text(r),
                                      outcomes=replays.outcomes(r), player=r["player"])


@corpus
def test_the_burning_hands_beat_is_flagged_on_at_least_three_sentences():
    """G2: empty-roll victim flagged on the Burning Hands beat."""
    agent, man, ctx = _burn()
    cast = replays.outcomes(replays.turn(13))[0]["effects"][0]
    assert cast["targets"] == [] and cast["kind"] == "cast"
    got = empty_roll.find(ctx)
    assert [f.kind for f in got] == ["harm-without-a-victim"]
    assert len(got[0].sentences) >= 3
    assert any("thrown backward" in s for s in got[0].sentences)
    assert any("scorched arms" in s for s in got[0].sentences)
    # The flame leaving the caster's hands is the spell being cast, which happened.
    assert not any("erupts from your hands" in s for s in got[0].sentences)


@corpus
def test_the_pronoun_carries_the_man_through_the_beat():
    """`about` is what the design called the gap that hid this: the sentence that names
    him, then "his face", "He hits the ground" — none of which name him."""
    agent, man, ctx = _burn()
    sentences = [w for w, _ in about(ctx, man)]
    assert sentences[0].startswith("The man in the stained leather jerkin")
    assert any(s.startswith("He hits the ground") for s in sentences)


@corpus
def test_contradicts_state_now_sees_the_burned_man():
    """Was 0 on this beat; the same linker and the burn and impact words now find him."""
    agent, man, ctx = _burn()
    name = agent.engine.scene.actors[man].name
    got = narration.contradicts_state(ctx.text, {name: {"alive": True, "hurt": False}})
    assert got, "the check that passed this beat must see it now"
    assert "man" in narration._name_stems(name)


@corpus
def test_the_backstop_cuts_the_harm_and_says_nobody_was_caught():
    agent, man, ctx = _burn()
    kept, notes = empty_roll.backstop(ctx, ctx.text, empty_roll.find(ctx))
    assert "scorched arms" not in kept and "thrown backward" not in kept
    assert "Burning Hands catches nobody; the man in a stained leather jerkin is " \
           "untouched." in kept
    assert empty_roll.find(context(agent, kept, outcomes=ctx.outcomes)) == []


def test_a_roll_that_landed_is_not_judged():
    agent, refs = scene_at(APPROACH, [("the thug", "thug")])
    thug = next(r for r, a in agent.engine.scene.actors.items() if a.name == "the thug")
    hit = [{"intent_id": "i1", "op": "cast", "status": "resolved", "tell": "",
            "rolls": [{"label": "Burning Hands — damage"}],
            "effects": [{"kind": "cast", "ref": "pc", "name": "Burning Hands",
                         "targets": [thug]},
                        {"kind": "damage", "ref": thug, "amount": 3}]}]
    text = "The thug is thrown backward, his coat scorched."
    assert empty_roll.find(context(agent, text, outcomes=hit)) == []
