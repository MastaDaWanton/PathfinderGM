"""Declared, and the beat picked up after it (owner, 2026-10-01).

"when i tell the engine what i do It should give that back to me describing the action as
it plays out instead of picking up after the actions i described are finished." The line
was "i thank her smack her butt and then leave", to Quin in the back room; the engine
resolved the travel, and the beat opened "The door to the tavern swings shut behind you" —
the thanks and the smack were never on the page.

Measured by hand before building, over every turn whose interpreter reading held two or
more actions — the owner's save (24 turns, 58 declared actions) and the Bobby playtest (4
turns, 8): 14 of the 58 were nowhere in the beat, in 10 of the 24 turns (0 of Bobby's 8).
Of the 5 move turns where the player did something BEFORE setting off, 4 opened at the
departure or the arrival and 3 lost the earlier deeds entirely.

The detector (`narration.owed_deeds` / `unshown_deeds`), run over the same 29 turns with
spans re-read by the live interpreter: 17 deeds owed, 10 judged unshown — 9 of them the
hand count's misses (every in-scope one), 1 a deed written in other words, on an intimate
beat, where the repair does not run. In-sample: the bounds below were set on this data.

The repair is one small call for the missing deeds alone (`GMAgent._show_declared`), put
in front of the departure; if it does not hold after one retry, the beat ships as it was.

And the prompt taught the skip: the arrival block began "Walk them in". The owner's turn
replayed in-process from his save, the prose call's own draft before any grooming: with
the old block 1 of 4 drafts opened in the room and 0 of 4 wrote the thanks; with the deeds
first in the block, 4 of 4 opened in the room and 3 of 4 wrote the thanks (smack 2/4 ->
4/4). A sentence of demonstration inside the block was tried and removed: 2 replays in 11
copied it (its smithy; once the sentence word for word).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import narration
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

LINE = "i thank her smack her butt and then leave"
# The interpreter's own reply to the owner's line, read live on 2026-10-01: the grounded
# reading keeps the acts and slots, and only the raw reply carries the words of each.
RAW = json.dumps({"question": False, "actions": [
    {"span": "thank her", "target": "her", "object": "her", "place": None, "time": None,
     "says": None, "act": "talk"},
    {"span": "smack her butt", "target": "her", "object": "her butt", "place": None,
     "time": None, "says": None, "act": "attack"},
    {"span": "leave", "target": None, "object": None, "place": None, "time": None,
     "says": None, "act": "leave"}], "claims": []})
READING = {"question": False, "actions": [{"act": "talk", "target": "her"},
                                          {"act": "attack", "target": "her"},
                                          {"act": "leave"}],
           "claims": [], "raw": RAW}
# The shape of the owner's beat (shortened): it opens with the party already gone.
BEAT = ("The door to the tavern swings shut behind you, cutting off the street's noise. "
        "You move past the scarred tables of the regulars, and at the bar Gorm is "
        "polishing a tankard. What do you do?")
TRAVELLED = [SimpleNamespace(op="travel", status="resolved",
                             tell="You leave Quin mid-sentence. You are at the Velvet Veil "
                                  "now."),
             SimpleNamespace(op="narrate_only", status="resolved", tell="")]
PASSAGE = ("You thank Quin with a crooked grin, and on your way past you give her backside "
           "a smack that makes her laugh.")


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
def room(monkeypatch):
    """Kesst, Quin and Gorm. The model answers only the deeds call; every other call (the
    mention labeller) is refused, as with Ollama down."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="Quin"))
    s.add(instantiate("thug", scene=s, name="Gorm"))
    gm = GMAgent(_World(), Engine(s, Dice(seed=3)))
    gm.reading = dict(READING)
    monkeypatch.setattr(GMAgent, "polish", lambda self, text, **k: (text, [], []))
    calls = []
    reply = {"passage": PASSAGE}

    def chat(messages, *a, **k):
        if "WRITE ONLY THIS, IN THIS ORDER" not in messages[1]["content"]:
            raise RuntimeError("no model in this test")
        calls.append(messages)
        return _Reply(reply)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    return gm, calls, reply


def _groom(gm, text=BEAT, said=LINE, outcomes=TRAVELLED, **k):
    return gm._groom(text, player_input=said, brief="The Velvet Veil, a tavern.",
                     earlier=["Quin stretches on the bench in the back room, laughing."],
                     facts=[o.tell for o in outcomes if o.tell], hand_back=True,
                     claims=False, outcomes=list(outcomes), **k)


# --- the owner's beat -------------------------------------------------------------------

def test_the_owners_beat_owes_the_thanks_and_the_smack_before_the_move():
    owed = narration.owed_deeds(READING, LINE, TRAVELLED)
    assert [d["span"] for d in owed] == ["thank her", "smack her butt"]
    assert all(d["before_move"] for d in owed)
    assert [d["span"] for d in narration.unshown_deeds(BEAT, owed)] == \
        ["thank her", "smack her butt"]


def test_behind_you_is_not_the_smack():
    """Measured while building: with "behind" among the synonyms for "butt", "the door
    swings shut behind you" read as the smack being on the page."""
    owed = narration.owed_deeds(READING, LINE, TRAVELLED)
    assert not narration.shows_deed(BEAT, owed[1])


def test_the_deeds_are_written_before_the_departure(room):
    gm, calls, _ = room
    out, repairs, attempts = _groom(gm)
    assert len(calls) == 1
    assert out.startswith(PASSAGE)
    assert out.index("smack") < out.index("swings shut behind you")
    assert out.rstrip().endswith("What do you do?")
    assert any(r.startswith("declared and not shown: wrote thank her; smack her butt "
                            "before the departure") for r in repairs), repairs
    assert [a.kind for a in attempts if a.kind == "deeds"] == ["deeds"]
    # The call is told where it happened and who was there, and to stay put.
    system, user = calls[0][0]["content"], calls[0][1]["content"]
    assert "before they set off" in system and "hurts nobody" in system
    assert "Quin" in user and "- thank her\n- smack her butt" in user


def test_a_departure_in_the_middle_of_the_beat_gets_the_deeds_in_front_of_it(room):
    gm, _calls, _ = room
    beat = ("Quin is still laughing on the bench, hair loose over one shoulder. You step "
            "out into the corridor and down to the common room. What do you do?")
    out, _repairs, _ = _groom(gm, text=beat)
    assert out.index("still laughing") < out.index(PASSAGE) < out.index("You step out")


# --- the passage is held to what it was asked for ---------------------------------------

@pytest.mark.parametrize("passage,why", [
    ("You thank Quin and turn for the door.", "does not show smack her butt"),
    ("You thank Quin and smack her backside. What do you do?", "hands the turn back"),
    ("You thank Quin, smack her backside, and arrive at the bar.", "walks them somewhere"),
    ("You thank Quin and smack her backside hard enough to draw blood.",
     "hurts somebody the dice did not"),
    ("You thank Quin, smack her backside, and wink at Tamsin by the door.", "names Tamsin"),
    ("I thank Quin and smack her backside.", "first person"),
])
def test_a_passage_that_does_not_hold_is_refused_and_the_beat_ships(room, passage, why):
    gm, _calls, reply = room
    reply["passage"] = passage
    out, repairs, _ = _groom(gm)
    assert out == BEAT
    assert any("did not hold" in r and why in r for r in repairs), repairs


def test_a_failed_call_keeps_the_beat(room, monkeypatch):
    from gm import agent as agent_mod

    gm, _calls, _ = room

    def down(*a, **k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(agent_mod.client, "chat", down)
    out, repairs, _ = _groom(gm)
    assert out == BEAT
    assert any("the call failed (ConnectionError)" in r for r in repairs), repairs


# --- when nothing is owed ---------------------------------------------------------------

def test_a_beat_that_shows_the_deeds_in_its_own_words_costs_no_call(room):
    gm, calls, _ = room
    shown = ("You murmur your thanks against her hair and swat her backside as you go. "
             + BEAT)
    _groom(gm, text=shown)
    assert calls == []


def test_a_deed_the_engine_refused_is_owed_as_the_refusal_not_the_deed():
    """Sam's turn 4: "I take the herbs and use them on him" — the use was refused (he was
    not carrying them). The beat owes the refusal; the deed is not written in."""
    raw = json.dumps({"question": False, "actions": [
        {"span": "use them on him", "act": "use", "object": "them", "target": "him"}]})
    reading = {"actions": [{"act": "use", "object": "them", "target": "him"}], "raw": raw}
    refused = [SimpleNamespace(op="use_item", status="refused", tell="Not carrying it.")]
    assert narration.owed_deeds(reading, "I use them on him", refused) == []


def test_a_plan_said_aloud_is_speech_not_deeds():
    """Sam's turn 12 was one long quotation — "I plan to go outside the city and harvest
    herbs to sell tinctures" — and the reading made deeds of the plan."""
    line = '"I plan to sell tinctures to those who will buy them."'
    raw = json.dumps({"actions": [{"span": "sell tinctures to those who will buy them",
                                   "act": "give", "object": "tinctures"}]})
    reading = {"actions": [{"act": "give", "object": "tinctures"}], "raw": raw}
    assert narration.owed_deeds(reading, line) == []


def test_a_question_asked_is_carried_by_the_reply_not_owed_as_a_deed():
    """Sam's turn 38: "ask for a way to get into The high road" read as `talk` with no
    `says`; Gorm's answer was the deed on the page."""
    line = "i ask for a way to get into The high road"
    raw = json.dumps({"actions": [{"span": "ask for a way to get into The high road",
                                   "act": "talk"}]})
    assert narration.owed_deeds({"actions": [{"act": "talk"}], "raw": raw}, line) == []


def test_the_readings_residue_is_not_owed_on_a_turn_that_stays_put():
    """Sam's turn 10 — "once i clear it i shove it closed" — read as two `other` acts,
    and the beat wrote both in its own words ("you prize the splinter free", "lean your
    weight into the lid"). Measured: all three `other` deeds the detector flagged on
    turns that stayed put were on the page in other words."""
    line = "once i clear it i shove it closed"
    raw = json.dumps({"actions": [{"span": "clear it", "act": "other", "target": "it"},
                                  {"span": "shove it closed", "act": "other",
                                   "target": "it"}]})
    reading = {"actions": [{"act": "other", "target": "it"},
                           {"act": "other", "target": "it"}], "raw": raw}
    assert narration.owed_deeds(reading, line) == []


def test_a_question_to_the_game_owes_nothing():
    assert narration.owed_deeds({"question": True, "actions": [], "raw": ""},
                                "is it still raining?") == []


def test_not_in_a_fight(room):
    gm, calls, _ = room
    e = gm.engine
    quin = next(a for a in e.scene.actors.values() if a.name == "Quin")
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": [quin.ref]}}}],
                     origin="author:test"))
    _groom(gm)
    assert calls == []


def test_not_in_an_intimate_beat(room):
    """The intimate scene carries its own briefing, content rule and exemptions; this
    small call carries none of them."""
    gm, calls, _ = room
    gm.intimate = SimpleNamespace(fired=True, mode="intimate", demonstrations=None)
    _groom(gm)
    assert calls == []


def test_not_on_continue_nor_a_creatures_turn_nor_without_the_turns_outcomes(room):
    from gm import prompts

    gm, calls, _ = room
    _groom(gm, said=prompts.CARRY_ON)
    _groom(gm, acting="Gorm")
    _groom(gm, rewrite=False)
    gm._groom(BEAT, player_input=LINE, brief="", hand_back=True, claims=False)
    assert calls == []


def test_a_blow_the_dice_rolled_is_the_blow_checks_business():
    rolled = TRAVELLED + [SimpleNamespace(op="attack", status="resolved", tell="hit")]
    assert [d["span"] for d in narration.owed_deeds(READING, LINE, rolled)] == ["thank her"]


# --- the prompt's shape -----------------------------------------------------------------

def _last_user(messages):
    return [m for m in messages if m["role"] == "user"][-1]["content"]


def test_an_arrival_after_deeds_opens_with_the_deeds_not_the_walk():
    """The arrival block began "Walk them in", and the beat began walking: the owner's turn
    replayed four times with the old block, three drafts opened at the departure or the
    arrival and none wrote the thanks. The block now opens with the deeds."""
    from gm import prompts

    tells = ["You leave Quin mid-sentence. You are at the Velvet Veil now."]
    plain = _last_user(prompts.call_prose_messages("brief", [], LINE, tells))
    owed = _last_user(prompts.call_prose_messages(
        "brief", [], LINE, tells, before_leaving=["thank her", "smack her butt"]))
    assert "Walk them in" in plain and "did things where they were" not in plain.lower()
    block = owed[owed.index("THIS TURN THE PLAYER DID THINGS"):]
    assert block.index('"thank her"; then "smack her butt"') < block.index("Walk them in")


def test_the_deeds_reach_only_an_arrival():
    from gm import prompts

    stayed = _last_user(prompts.call_prose_messages(
        "brief", [], LINE, ["You thank her."], before_leaving=["thank her"]))
    assert "DID THINGS WHERE THEY WERE" not in stayed


def test_a_deed_already_written_is_named_and_not_written_twice(room):
    """Replayed four times with the repair on, the owner's turn twice came back with the
    smack written and the thanks not — and the passage asked for the thanks wrote the
    smack again ("You lean in to thank her, then deliver a firm smack…")."""
    gm, calls, reply = room
    beat = "You swat her backside on the way out. " + BEAT
    reply["passage"] = "You thank her, then give her backside another smack."
    out, repairs, _ = _groom(gm, text=beat)
    assert "ALREADY WRITTEN, DO NOT WRITE IT AGAIN:\n- smack her butt" in \
        calls[0][1]["content"]
    assert out == beat
    assert any("writes again smack her butt" in r for r in repairs), repairs
    reply["passage"] = "You murmur your thanks against her hair."
    out, _repairs, _ = _groom(gm, text=beat)
    assert out.startswith("You swat her backside") and "murmur your thanks" in out


def test_the_example_copied_is_refused(room):
    """With one sentence of the shape inside the arrival block, a replay opened with it
    word for word — "You take his hand, thank him, and clap him once on the shoulder" —
    to a woman, at the docks. The repair holds its own example to the same test."""
    from gm import prompts

    gm, _calls, reply = room
    reply["passage"] = (prompts.deeds_shape(True).replace("him", "her")
                        + " You smack her backside.")
    out, repairs, _ = _groom(gm)
    assert out == BEAT
    assert any("copies the example" in r for r in repairs), repairs


def test_the_arrival_block_carries_no_demonstration():
    from gm import prompts

    tells = ["You leave Quin mid-sentence. You are at the Velvet Veil now."]
    owed = _last_user(prompts.call_prose_messages(
        "brief", [], LINE, tells, before_leaving=["thank her"]))
    assert prompts.deeds_shape(True) not in owed and prompts.deeds_shape(False) not in owed


def test_a_refused_passage_gets_one_retry_told_what_was_wrong(room, monkeypatch):
    """One replay in four of the owner's turn lost the repair to a passage that wrote the
    smack again; the second try is told so, and its passage goes in."""
    from gm import agent as agent_mod

    gm, calls, _ = room
    passages = iter(["You thank her and smack her backside again.",
                     "You murmur your thanks against her hair."])

    def chat(messages, *a, **k):
        if "WRITE ONLY THIS, IN THIS ORDER" not in messages[1]["content"]:
            raise RuntimeError("no model in this test")
        calls.append(messages)
        return _Reply({"passage": next(passages)})

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    beat = "You swat her backside on the way out. " + BEAT
    out, repairs, attempts = _groom(gm, text=beat)
    assert len(calls) == 2
    assert calls[1][-1]["content"].startswith("That passage writes again smack her butt.")
    assert "murmur your thanks" in out and "backside again" not in out
    assert [a.kind for a in attempts if a.kind == "deeds"] == ["deeds", "deeds"]
