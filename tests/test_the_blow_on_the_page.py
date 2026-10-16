"""Every blow the player's dice rolled is on the page of the beat that answers it.

The 2026-10-16 report (0.2.19, free narrator, a market brawl), round two: the engine rolled
the player's dagger thrust at the woman with the braid, a miss (6 against AC 10; turn-log
resolution row 53), and the beat never named the dagger or the miss. It wrote an invented
grip on the player's throat instead (her fingers tightening round it).

Why nothing caught it: the declared-deed check owes nothing in a fight — "an attack in a
fight or one the dice rolled (the blow's own checks own that page)" (`deed_reader.deeds_of`)
— and no blow check owned that page. The blow checks that exist read the other direction:
a blow put in the wrong hands, a blow landed before the dice. A combat-panel turn has no
words of the player's either, so there was no reading to owe a deed from.

Now `_show_blows`: the engine's own line for each of the player's rolled blows is the deed,
the deed reader says whether the page shows it, and a missing one is written onto the
beat — one small call, read back, or the engine's line itself.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import deed_reader
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._board import face_to_face

LABEL = "full attack: weapon on the woman with the braid"
# The report's beat, paraphrased: an invented grip, no dagger, no miss.
GRIP = ("Her fingers tighten around your throat as the shards settle between you. She "
        "snarls, close enough that you can smell her sweat. What do you do?")


class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


class _Reply:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.seconds, self.model = 0.2, "stub"

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def fight(monkeypatch):
    """The player's dagger thrust that missed, resolved by the engine; the deed reader on,
    every model call scripted: `reads` the reader's answers in order, `passages` the
    blow call's."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent

    monkeypatch.setattr(deed_reader, "ENABLED", True)
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the woman with the braid"))
    e = Engine(s, Dice(seed=3))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    face_to_face(s)
    s.turn = next(i for i, (r, _) in enumerate(s.initiative) if r == "pc")
    e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                       "because": "the combat panel", "params": {"weapon": "rapier"}}]))
    res = e.resume(2)
    blow = next(o for o in res.outcomes if o.op == "attack" and o.rolls)
    assert blow.verdict == "miss", "the premise: a blow that missed"
    gm = GMAgent(_World(), e)
    gm.reading = None
    monkeypatch.setattr(GMAgent, "polish", lambda self, text, **k: (text, [], []))
    state = SimpleNamespace(reads=[], passages=[], read_calls=[], blow_calls=[],
                            outcomes=list(res.outcomes))

    def chat(messages, *a, **k):
        system = messages[0]["content"]
        if system.startswith("You check one passage"):
            state.read_calls.append(messages)
            return _Reply(state.reads.pop(0))
        if "WRITE ONLY THIS, IN THIS ORDER" in messages[1]["content"]:
            state.blow_calls.append(messages)
            return _Reply({"passage": state.passages.pop(0)})
        raise RuntimeError("no model in this test")

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    real = deed_reader.read

    def read(*a, **k):
        k["chat"] = chat
        return real(*a, **k)

    monkeypatch.setattr(deed_reader, "read", read)
    return gm, state


def _groom(gm, state, text=GRIP):
    gm.deed_lines = []
    return gm._groom(text, player_input=LABEL, brief="The market.",
                     earlier=["The market lane is crowded."], facts=[], hand_back=True,
                     claims=False, outcomes=state.outcomes)


def test_a_missing_blow_is_written_onto_the_beat_first(fight):
    gm, state = fight
    state.reads = [{"d1": {"sentence": "0", "how": "absent"}},
                   {"d1": {"sentence": "1", "how": "shown"}}]
    state.passages = ["You lunge with the rapier, but she twists aside and the point "
                      "finds only air."]
    text, repairs, _ = _groom(gm, state)
    deed = state.read_calls[0][-1]["content"]
    assert "Your attack with the rapier misses the woman with the braid" in deed, \
        "the engine's own line is the deed the page owes"
    assert "(" not in deed.split("DEEDS:")[1].split("PASSAGE")[0], "no numbers"
    assert text.startswith("You lunge with the rapier"), "the player's act comes first"
    assert "Her fingers tighten" in text, "the rest of the beat is kept"
    assert any(r.startswith("a blow left off the page: wrote") for r in repairs)
    assert "It hurts nobody" in state.blow_calls[0][0]["content"], "a miss wounds nobody"


def test_a_blow_already_on_the_page_costs_one_read_and_nothing_else(fight):
    gm, state = fight
    state.reads = [{"d1": {"sentence": "1", "how": "shown"}}]
    shown = "Your thrust goes wide of her hip. She snarls and steps in. What do you do?"
    text, repairs, _ = _groom(gm, state, shown)
    assert text == shown and not state.blow_calls
    assert not any("blow left off" in r for r in repairs)


def test_a_passage_that_wounds_on_a_miss_gives_way_to_the_engines_line(fight):
    gm, state = fight
    state.reads = [{"d1": {"sentence": "0", "how": "absent"}}]
    state.passages = ["You drive the rapier into her side and blood wells up.",
                      "Your blade cuts her arm and draws blood."]
    text, repairs, _ = _groom(gm, state)
    assert text.startswith("Your attack with the rapier misses the woman with the braid.")
    assert "blood" not in text
    assert "the engine's own line" in " ".join(repairs)
    assert gm.deed_lines and text.startswith(gm.deed_lines[0]), "marked ours (D4)"


def test_the_reader_off_judges_nothing(fight, monkeypatch):
    """No cue words stand in: with the reader off (the suite) or failed, the page is not
    read for blows at all."""
    gm, state = fight
    monkeypatch.setattr(deed_reader, "ENABLED", False)
    text, repairs, _ = _groom(gm, state)
    assert text == GRIP and not state.read_calls
