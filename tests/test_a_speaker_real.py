"""A speaker the prose introduced, who spoke to the player, is made real (item 20.4).

Measured on the Bobby playtest, 2026-09-28, turn 9: the man in the stained leather jerkin
spoke three lines to the player, tagged to `new1`, a ref nobody held — `speech-tags`
logged `unknown_refs: ["new1"]`, 3 lines, 0 attributed. He existed as a population record
only, no conversation opened, and he became c8 a turn later because the player addressed
him. Ruled 2026-09-28 (Q5): a speaker addressing the player gets a body through the
arrival door, matched to the record this beat wrote.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import replays
from gm import judgement, speech
from play import aftermath
from play.aftermath import speaker_real
from rules import states

from _a_truth import APPROACH, WORLD, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _turn_nine():
    r = replays.turn(9)
    assert r["speech_tags"][0]["unknown_refs"] == ["new1"]
    agent, _ = scene_at(APPROACH)
    engine, scene = agent.engine, agent.engine.scene
    text = replays.beat_text(r)
    judgement.record_people(scene, ["man in a stained leather jerkin"], turn=18,
                            world=WORLD)
    said = [{"who": "", "to": "you", "line": ln, "was": "new1"}
            for ln in speech.lines(text)]
    campaign = SimpleNamespace(scene=scene, world=WORLD, transcript=[],
                               engine=lambda: engine)
    return engine, scene, text, said, campaign


@corpus
def test_the_man_who_spoke_is_embodied_with_a_square_and_hails_the_player():
    engine, scene, text, said, campaign = _turn_nine()
    assert len(said) == 3 and judgement.hailed_by(scene, text, said=said) == []
    before = set(scene.actors)
    rows = aftermath.run("people", aftermath.context("people", "turn", campaign,
                                                     engine=engine, text=text, said=said))
    made = set(scene.actors) - before
    assert len(made) == 1
    ref = made.pop()
    assert rows == [dict(rows[0], kind="speaker-real", made=ref, lines=3)]
    man = scene.actors[ref]
    assert man.name == "man in a stained leather jerkin" and man.appearance
    assert scene.grid is not None
    assert scene.positions.get(ref), "every arrival has a square (item 14)"
    assert rows[0]["square"] == list(scene.positions[ref])
    assert all(r["who"] == ref and r["made"] == ref for r in said)
    # The hail opens the conversation, through the engine's own door.
    assert judgement.hailed_by(scene, text, said=said) == [ref]
    assert engine.join_talk(man, how="they spoke to you")
    assert man.has_state(states.TALKING)


def test_two_people_the_beat_could_mean_make_nobody():
    agent, _ = scene_at(APPROACH)
    engine, scene = agent.engine, agent.engine.scene
    text = ("A woman with a basket and a man with a staff wait by the stone. "
            "'You there,' one of them calls.")
    judgement.record_people(scene, ["woman with a basket", "man with a staff"], world=WORLD)
    said = [{"who": "", "to": "you", "line": "You there,", "was": "new1"}]
    campaign = SimpleNamespace(scene=scene, world=WORLD, transcript=[],
                               engine=lambda: engine)
    before = set(scene.actors)
    rows = speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                               text=text, said=said))
    assert set(scene.actors) == before and rows[0]["made"] == ""
    assert said[0]["who"] == ""


def test_in_a_fight_the_prose_makes_nobody():
    agent, _ = scene_at(APPROACH, [("the thug", "thug")])
    engine, scene = agent.engine, agent.engine.scene
    engine._ensure_encounter("pc", next(r for r in scene.actors if r != "pc"))
    judgement.record_people(scene, ["archer on the ridge"], world=WORLD)
    said = [{"who": "", "to": "you", "line": "You are done!", "was": "new1"}]
    rows = speaker_real.step(aftermath.context(
        "people", "turn", SimpleNamespace(scene=scene, world=WORLD, transcript=[],
                                          engine=lambda: engine),
        engine=engine, text="An archer on the ridge shouts. 'You are done!'", said=said))
    assert rows[0]["made"] == "" and said[0]["who"] == ""


def test_the_member_keeps_the_aftermath_contract():
    assert speaker_real in aftermath.registered()
    assert speaker_real.STAGE == "people" and speaker_real.ORDER == 10
