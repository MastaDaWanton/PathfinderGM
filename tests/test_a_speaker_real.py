"""A speaker the prose introduced, who spoke to the player, is made real (item 20.4) — from
the beat reader's answer since 2026-10-03.

Measured on the Bobby playtest, 2026-09-28, turn 9: the man in the stained leather jerkin
spoke three lines to the player, tagged to `new1`, a ref nobody held — `speech-tags`
logged `unknown_refs: ["new1"]`, 3 lines, 0 attributed. He existed as a population record
only, no conversation opened, and he became c8 a turn later because the player addressed
him. Ruled 2026-09-28 (Q5): a speaker addressing the player gets a body through the
arrival door; widened by the seen-people ruling of 2026-10-01 to anybody the page shows.

The reading of the page that found him — a tag naming nobody, the record this beat wrote,
the words the narration used for it — was code until 2026-10-03 (`speaker_real._from_tags`
and `_from_the_page`). The beat reader answers it now: "a man" is somebody new, here, in
"a man in a stained leather jerkin", and the three lines are his. These tests stub that
answer (tests/beat_reader/stub.py) and pin what the "people" stage does with it.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import replays
from gm import judgement, speech
from play import aftermath
from play.aftermath import speaker_real
from rules import states
from tests.beat_reader import stub

from _a_truth import APPROACH, WORLD, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _people_stage(scene, engine, text, said, reading):
    campaign = SimpleNamespace(scene=scene, world=WORLD, transcript=[],
                               engine=lambda: engine)
    return aftermath.run("people", aftermath.context(
        "people", "turn", campaign, engine=engine, text=text, said=said,
        attribution=reading))


@corpus
def test_the_man_who_spoke_is_embodied_with_a_square_and_hails_the_player():
    r = replays.turn(9)
    assert r["speech_tags"][0]["unknown_refs"] == ["new1"]
    agent, _ = scene_at(APPROACH)
    engine, scene = agent.engine, agent.engine.scene
    text = replays.beat_text(r)
    said = [{"who": "", "to": "you", "line": ln, "was": "new1"}
            for ln in speech.lines(text)]
    assert len(said) == 3 and judgement.hailed_by(scene, text, said=said) == []
    reading = stub.read(text, scene, engine=engine, said=said, who={"a man": "new"},
                        new=[("a man", "here", "a man in a stained leather jerkin")],
                        lines={"The road to": ("a man", "you"),
                               "The trees have": ("a man", "you"),
                               "You looking for": ("a man", "you")})
    before = set(scene.actors)
    rows = _people_stage(scene, engine, text, said, reading)
    made = set(scene.actors) - before
    assert len(made) == 1, rows
    ref = made.pop()
    man = scene.actors[ref]
    assert man.name == "man in a stained leather jerkin" and man.appearance
    assert scene.grid is not None
    assert scene.positions.get(ref), "every arrival has a square (item 14)"
    assert all(r["who"] == ref and r["made"] == ref for r in said)
    assert {"kind": "speaker-read", "filled": ref, "lines": 3} in rows
    # The hail opens the conversation, through the engine's own door.
    assert judgement.hailed_by(scene, text, said=said) == [ref]
    assert engine.join_talk(man, how="they spoke to you")
    assert man.has_state(states.TALKING)


def test_a_line_the_reader_gives_to_nobody_is_booked_to_nobody():
    """The rule this replaced refused rather than guessed when two people could be meant
    ("'You there,' one of them calls", beside a woman with a basket and a man with a
    staff). The precision is the reader's now — "nobody" is always one of its choices —
    and a line it gives to nobody is booked to nobody."""
    agent, _ = scene_at(APPROACH)
    engine, scene = agent.engine, agent.engine.scene
    text = ("A woman with a basket and a man with a staff wait by the stone. "
            "'You there,' one of them calls.")
    said = [{"who": "", "to": "you", "line": "You there,", "was": "new1"}]
    reading = stub.read(text, scene, engine=engine, said=said,
                        who={"A woman": "new", "a man": "new"},
                        new=[("A woman", "here", "woman with a basket"),
                             ("a man", "here", "man with a staff")],
                        lines={"You there": ("nobody", "you")})
    rows = speaker_real.step(stub.ctx(scene, reading, text=text, engine=engine,
                                      world=WORLD, said=said))
    assert said[0]["who"] == "" and not [r for r in rows if r.get("booked")]


def test_in_a_fight_the_prose_makes_nobody():
    """The fight's rule (`GMAgent._undeclared_arrivals`): an arrival in a fight is the
    plan's `spawn`, never the prose's. A newcomer the reader says spoke is given no body,
    so the line is booked to nobody, and the row says why."""
    agent, _ = scene_at(APPROACH, [("the thug", "thug")])
    engine, scene = agent.engine, agent.engine.scene
    engine._ensure_encounter("pc", next(r for r in scene.actors if r != "pc"))
    text = "A guard on the ridge shouts. 'You are done!'"
    said = [{"who": "", "to": "you", "line": "You are done!", "was": "new1"}]
    reading = stub.read(text, scene, engine=engine, said=said, who={"A guard": "new"},
                        new=[("A guard", "here", "guard on the ridge")],
                        lines={"You are done": ("A guard", "you")})
    before = set(scene.actors)
    rows = _people_stage(scene, engine, text, said, reading)
    assert set(scene.actors) == before and said[0]["who"] == ""
    assert any(r.get("why") == "in a fight the prose brings nobody in" for r in rows)
    assert any(r.get("why") == "a newcomer with no body" for r in rows)


def test_no_reading_books_nothing_and_says_so():
    """When the reading call fails, nothing reads the page in its place — the owner's
    "endless loop" was the patterns that used to — and the turn log says the beat went
    unread."""
    agent, _ = scene_at(APPROACH)
    engine, scene = agent.engine, agent.engine.scene
    text = "A man by the stone looks up. 'You lost?' he asks."
    said = []
    reading = stub.read(text, scene, engine=engine, fail="people")
    assert reading.asked and not reading.read and "people" in reading.error
    before = set(scene.actors)
    rows = _people_stage(scene, engine, text, said, reading)
    assert set(scene.actors) == before and said == []
    assert [r["step"] for r in rows if r.get("kind") == "beat-unread"] == \
        ["seen_people", "speaker_real"]


def test_the_member_keeps_the_aftermath_contract():
    assert speaker_real in aftermath.registered()
    assert speaker_real.STAGE == "people" and speaker_real.ORDER == 20
