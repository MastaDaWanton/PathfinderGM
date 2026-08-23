"""Turns that used to die in five attempts, salvaged in code.

Every case here is from one live session (2026-08-22, screenshot in the log): the
player said "I want to go to the gym and work out", the GM proposed op "exercise",
retried it as a `check` with no skill three attempts running, tripped the
repeats-the-last-turn objection on a politely-declined offer, and the player got a
wall of red where the game should be. Rejection teaches the model nothing here —
these are read for what they plainly mean and fixed before validation, the same
shape as every repair that has held.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.intents import parse, parse_all
from rules.sheet import load_pc


# --- invented ops -----------------------------------------------------------------------

def test_exercise_is_a_story_turn():
    """The live turn: op "exercise", which 1e has no mechanic for."""
    intent = parse({"op": "exercise", "actor": "pc",
                    "because": "training at the gymnasium"})
    assert intent.op == "narrate_only"
    assert intent.because == "training at the gymnasium"


def test_an_op_nobody_ever_heard_of_becomes_story_not_an_error():
    intent = parse({"op": "juggle_flaming_swords", "actor": "pc",
                    "params": {"flair": "maximum"}})
    assert intent.op == "narrate_only"
    # The params died with the op that owned them — narrate_only takes none, and
    # carrying them over would fail the very schema check this repair exists to dodge.
    assert intent.params == {}


def test_a_misspelled_real_op_snaps_to_the_real_one():
    """"atack" is not a new idea, it is "attack" typed badly — snapping beats both
    rejecting it and quietly narrating away a swing the GM meant."""
    intent = parse({"op": "atack", "actor": "pc", "target": "c1"})
    assert intent.op == "attack"


def test_a_skill_named_as_an_op_is_a_check_by_another_spelling():
    intent = parse({"op": "stealth", "actor": "pc", "params": {"dc": 15}})
    assert intent.op == "check"
    assert intent.params["skill"] == "stealth"


def test_a_blank_op_is_still_refused():
    """Absence stays loud. A missing op is not an invented one — nothing was meant,
    so there is nothing to read the meaning of."""
    from rules.intents import IntentError

    with pytest.raises(IntentError):
        parse({"actor": "pc"})


# --- the check that never says what to roll ---------------------------------------------

def test_a_check_whose_reason_names_the_skill_gets_it_filled():
    intent = parse({"op": "check", "actor": "pc", "params": {"dc": {"band": "average"}},
                    "because": "she tries to climb the scaffold quietly"})
    assert intent.op == "check"
    assert intent.params["skill"] == "climb"


def test_a_check_about_nothing_rollable_is_a_story_turn():
    """Attempts 3, 4 and 5 of the live turn: `check` with no skill, no recoverable
    skill anywhere in the reason. There is nothing to roll, so nothing is rolled."""
    intent = parse({"op": "check", "actor": "pc",
                    "because": "a hard morning of lifting and sweating"})
    assert intent.op == "narrate_only"


# --- the repeat objection on a quiet turn -----------------------------------------------

@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the trainer"))
    return s


def test_two_quiet_turns_in_a_row_are_not_an_objection(scene):
    """Attempt 1 of the live turn: the player declined a trainer's offer, the GM
    quite reasonably proposed another narrate_only, and the objection called that
    "the same thing as last turn". Saying nothing twice is just two quiet turns."""
    raw = [{"op": "narrate_only", "actor": "pc", "because": "polite conversation"}]
    intents = parse_all(raw)
    previous = judgement._signature(parse_all(raw))
    verdict = judgement.review("I regret to inform you that I must decline.",
                               intents, scene, previous=previous)
    assert verdict.ok


def test_the_same_roll_again_still_objects(scene):
    """The original defence stands: replaying a *mechanical* turn against new words
    is the GM not reading, and that is the measured case the objection was built on."""
    raw = [{"op": "check", "actor": "pc", "because": "over the wall while the lamp is away",
            "params": {"skill": "stealth", "dc": {"band": "average"}}}]
    intents = parse_all(raw)
    previous = judgement._signature(parse_all(raw))
    verdict = judgement.review("two bravos come round the corner, I turn and fight",
                               intents, scene, previous=previous)
    assert not verdict.ok


# --- the second model -------------------------------------------------------------------

def test_the_turn_is_handed_to_the_fallback_model_before_the_player_sees_red(monkeypatch):
    """llama3.1 burning five attempts used to be a wall of red. Now the schedule has
    two more slots on the configured fallback model; here the primary refuses in
    every slot and the 'fallback' answers legally, and the player sees a turn."""
    from django.conf import settings

    from gm import agent as agent_mod
    from rules.dice import Dice
    from rules.engine import Engine

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=7))

    class FakeWorld:
        name = "Testholme"
        secret = ""
        premise: dict = {}
        entities: dict = {}
        unwritten: list = []
        chronology: list = []
        factions: list = []

        def ancestors(self, _):
            return []

    class FakeReply:
        def __init__(self, text):
            self.text, self.seconds, self.model = text, 0.0, "fake"

        def json(self):
            import json as j

            return j.loads(self.text)

    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        if model == settings.MODELS["fallback"]["model"]:
            return FakeReply('{"narration": "The morning passes in honest sweat.", '
                             '"intents": [{"op": "narrate_only", "actor": "pc"}]}')
        return FakeReply("I refuse to emit JSON today.")

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    gm = agent_mod.GMAgent(FakeWorld(), engine)
    plan = gm.plan_turn("I head to the gymnasium and work out", history=[])

    assert plan.intents and plan.intents[0].op == "narrate_only"
    assert "honest sweat" in plan.narration
    # The first five slots belong to the narrator; the sixth is the hand-off. (Later
    # polish calls may use the narrator again — that is its job, not a retry.)
    assert calls[:5] == [settings.MODELS["narrator"]["model"]] * 5
    assert calls[5] == settings.MODELS["fallback"]["model"]
    assert any("handing the turn to" in r for r in plan.rejections)
