"""The two deferred arrival rows of docs/fix-interfaces.md, both from the live caravan run
of 2026-09-29 (Borin, Glimgear; the save borin-achereth-3):

  * **A person narrated who is not there.** Withdrawing to the crossroads, the scene held
    only the PC, and the arrival put "a laborer … struggling with a heavy crate of
    timber" there who "looks up as you approach". Its cause was in our own prompt: the
    arrival paragraph ended on "ONE particular thing one particular person is doing",
    asked whatever the brief said.
  * **The continuity slip.** Arriving at the outskirts next, the passage opened the
    crossroads' laborer again, word for word — "a man is struggling with a heavy crate of
    timber… looks up as you approach". The prose call shows the model its last two beats
    as "the scene as it stands, which you are continuing, not restarting", and after a
    move that scene is the one the party left.

The beats below are the save's own text, verbatim.
"""
from __future__ import annotations

import json

from gm import agent as agent_mod
from gm import checks, prompts
from gm.checks import absent_person

from _a_truth import APPROACH, MARKET, context, scene_at

CROSSROADS = (
    "The grass gives way to the loam of the forest floor, and the trees close in until the "
    "light is filtered and green. The frantic shouting and the clash of steel at the wagon "
    "are replaced by the heavy thrum of insects and the distant, rhythmic thud of a "
    "woodcutter's axe. You reach the crossroads, where the road splits under the shadow of "
    "a massive, ancient oak. Here, the air smells of damp earth and pine resin. A few yards "
    "from the center of the junction, a team of pack-mules is being unloaded by a laborer "
    "who is currently struggling with a heavy crate of timber. The man wipes sweat from "
    "his brow with a stained kerchief and looks up as you approach, his eyes weary and "
    "searching. What do you do?")
OUTSKIRTS = (
    "Near the center of the junction, a man is struggling with a heavy crate of timber, "
    "his muscles straining against the weight. He wipes sweat from his brow with a stained "
    "kerchief and looks up as you approach, his eyes weary and searching. He is the only "
    "one in your immediate vicinity who seems to notice you. What do you do?")


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def test_the_crossroads_laborer_is_found_with_the_sentence_that_brought_him_on():
    """The scene held only the PC; the page put a laborer there looking at the player."""
    agent, _ = scene_at(APPROACH)
    assert [a for a in agent.engine.scene.actors.values() if not a.is_pc] == []
    found = absent_person.find(context(agent, CROSSROADS))
    assert [f.kind for f in found] == ["person-not-there"]
    assert any("by a laborer who is currently struggling" in s for s in found[0].sentences)
    assert any("looks up as you approach" in s for s in found[0].sentences)


def test_a_failed_rewrite_falls_to_the_cut_and_the_place_stands(monkeypatch):
    agent, _ = scene_at(APPROACH)
    ctx = context(agent, CROSSROADS)
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(json.dumps(
        {"sentence": "A laborer looks up at you from his crate."})))
    out, notes, _ = agent._repair_sentences(CROSSROADS, absent_person.find(ctx), ctx)
    assert "laborer" not in out and "looks up as you approach" not in out
    assert "You reach the crossroads, where the road splits" in out
    assert out.endswith("What do you do?")
    assert absent_person.find(context(agent, out)) == []


def test_a_held_pronoun_run_goes_with_the_person():
    """The outskirts beat: "a man is struggling…", then "He wipes sweat… looks up as you
    approach", then "He is the only one…" — all one phantom."""
    agent, _ = scene_at(APPROACH)
    (f,) = absent_person.find(context(agent, OUTSKIRTS))
    assert len(f.sentences) == 3 and f.sentences[0].startswith("Near the center")
    assert f.sentences[-1].startswith("He is the only one")


def test_where_somebody_is_here_the_check_stands_aside():
    """A place the engine already holds people at: a nameless figure there is fair prose
    (docs/nobody-is-invented.md)."""
    agent, _ = scene_at(MARKET, [("the watchman waving traffic through", "watchman")])
    assert absent_person.find(context(agent, CROSSROADS)) == []


def test_the_check_is_a_registered_member():
    assert absent_person in checks.registered()


def _prose_prompt(tells, earlier):
    msgs = prompts.call_prose_messages("BRIEF", [], "I head to the outskirts", tells,
                                       earlier=earlier)
    return msgs[-1]["content"]


def test_an_arrival_is_not_shown_the_scene_it_left_as_the_one_it_continues():
    """Beat 6 of the caravan save carried the crossroads' laborer to the outskirts."""
    arrived = _prose_prompt(["You are at the outskirts now."], [CROSSROADS])
    assert "struggling with a heavy crate" not in arrived
    assert "THIS TURN THE PARTY ARRIVED SOMEWHERE" in arrived
    # A beat that stays put is still shown what it continues.
    stayed = _prose_prompt(["You search the ground."], [CROSSROADS])
    assert "struggling with a heavy crate" in stayed


def test_the_arrival_paragraph_no_longer_demands_a_person():
    arrived = _prose_prompt(["You are at the outskirts now."], [])
    assert "one particular person is doing" not in arrived
    assert "when the brief names nobody here, something of the place itself" in arrived
