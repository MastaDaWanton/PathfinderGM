"""Asked something, and the beat stopped before the answer (owner, 2026-10-01).

The owner's screenshot: "I thank him and ask if he has anything to get me into such a
place" came back as

    Gorm's tail gives a sharp, nervous twitch, and he leans even closer across the sticky
    wood of the bar. He looks over his shoulder at the tavern's heavy door, then back to
    you, his voice barely a rasp over the roar of the crowd. What do you do?

— everything but the answer. "if we can detect a turn like this and make it better before
the user sees it that would be best. If not then they can just hit continue."

Measured before building (the committed recordings, 111 beats): 2 of 32 questions put to
somebody got no speech from anyone, and in both our own grooming lost an answer the model
had written or would have; the owner's exact shape was 0 of 111. Nothing detected it: the
`no-hand-back` finding that asks for the answer cannot fire on a beat ending "What do you
do?", and `was_speech` reads "ask if he has…" as no speech at all.

The repair is one small call for the spoken answer alone (`GMAgent._answer_the_question`),
put before the hand-back; if it does not hold, the beat ships as it was.
"""
from __future__ import annotations

import json

import pytest

from gm import narration
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ASKED = "I thank him and ask if he has anything to get me into such a place"
BEAT = ("Gorm's tail gives a sharp, nervous twitch, and he leans even closer across the "
        "sticky wood of the bar. He looks over his shoulder at the tavern's heavy door, "
        "then back to you, his voice barely a rasp over the roar of the crowd. "
        "What do you do?")
ANSWER = ('"There\'s a back stair off the alley," Gorm says. "The cook owes me. Tell her '
          'Gorm sent you, and do not dawdle."')


class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


class _Reply:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.seconds, self.model = 0.4, "stub"

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def bar(monkeypatch):
    """Kesst at the bar, in conversation with Gorm. The model answers only the answer
    call; every other call (the mention labeller) is refused, as with Ollama down."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    gorm = s.add(instantiate("thug", scene=s, name="Gorm"))
    engine = Engine(s, Dice(seed=3))
    engine.join_talk(gorm)
    gm = GMAgent(_World(), engine)
    monkeypatch.setattr(GMAgent, "polish",
                        lambda self, text, **k: (text, [], []))
    calls = []
    reply = {"answer": ANSWER}

    def chat(messages, *a, **k):
        if "Write ONLY" not in messages[0]["content"]:
            raise RuntimeError("no model in this test")
        calls.append(messages)
        return _Reply(reply)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    return gm, gorm, calls, reply


def _groom(gm, text=BEAT, said=ASKED, **k):
    return gm._groom(text, player_input=said, brief="Gorm keeps the bar at the Velvet "
                     "Veil and knows its cook.", hand_back=True, claims=False, **k)


# --- the owner's beat -------------------------------------------------------------------

def test_the_owners_beat_is_found_unanswered():
    assert narration.wants_an_answer(ASKED)
    assert not narration.answered(BEAT, "c1", [], ASKED)


def test_the_owners_beat_gets_gorms_answer_before_the_hand_back(bar):
    gm, gorm, calls, _ = bar
    out, repairs, attempts = _groom(gm)
    assert len(calls) == 1
    assert "back stair" in out
    assert out.rstrip().endswith("What do you do?")
    assert out.index("back stair") < out.index("What do you do?")
    assert "asked and not answered: Gorm answers" in repairs
    assert any(r.get("who") == gorm.ref for r in gm.last_said), gm.last_said
    assert [a.kind for a in attempts if a.kind == "answer"] == ["answer"]


def test_an_answer_that_is_not_speech_is_refused_and_the_beat_ships(bar):
    """"If not then they can just hit continue": the beat as it was, said in the log."""
    gm, _gorm, calls, reply = bar
    reply["answer"] = "He considers it for a long moment."
    out, repairs, _ = _groom(gm)
    assert out == BEAT
    assert any("did not hold" in r and "Continue carries it" in r for r in repairs)


def test_an_answer_that_hands_the_turn_back_itself_is_refused(bar):
    gm, _gorm, _calls, reply = bar
    reply["answer"] = '"Maybe," Gorm says. What do you do?'
    out, _repairs, _ = _groom(gm)
    assert out == BEAT


# --- when nothing is owed ---------------------------------------------------------------

@pytest.mark.parametrize("beat", [
    BEAT.replace("What do you do?", '"Back stair," he breathes. What do you do?'),
    BEAT.replace("What do you do?", "He shakes his head. What do you do?"),
    BEAT.replace("What do you do?", "He tells you the cook owes him a favour. "
                                    "What do you do?"),
])
def test_a_beat_that_answers_costs_no_call(bar, beat):
    gm, _gorm, calls, _ = bar
    _groom(gm, text=beat)
    assert calls == []


def test_the_players_own_words_echoed_back_are_not_an_answer():
    """A quotation of the player's own line is the beat repeating them, not Gorm."""
    beat = '"Anything to get me into such a place?" you ask. Gorm leans in. What do you do?'
    assert not narration.answered(beat, "c1", [], ASKED)


def test_thanks_alone_asks_nothing(bar):
    gm, _gorm, calls, _ = bar
    _groom(gm, said="I thank him and drink.")
    assert calls == []


def test_somebody_who_would_not_give_their_name_is_not_made_to_answer(bar):
    """An unwilling listener's silence is their answer — the same gate the name backstop
    uses (`attitude.tells_their_name`)."""
    gm, gorm, calls, _ = bar
    gm.engine._set_attitude(gorm, "hostile", None, "test")
    _groom(gm)
    assert calls == []


def test_not_in_a_fight(bar):
    gm, gorm, calls, _ = bar
    e = gm.engine
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": [gorm.ref]}}}],
                     origin="author:test"))
    _groom(gm)
    assert calls == []


def test_not_on_a_creatures_turn_nor_where_no_rewrite_is_allowed(bar):
    gm, _gorm, calls, _ = bar
    _groom(gm, acting="Gorm")
    _groom(gm, rewrite=False)
    assert calls == []


def test_continue_is_not_judged_as_a_question(bar):
    """Continue's own line asks for the answer already; it is not the player asking."""
    from gm import prompts

    gm, _gorm, calls, _ = bar
    _groom(gm, said=prompts.CARRY_ON)
    assert calls == []
