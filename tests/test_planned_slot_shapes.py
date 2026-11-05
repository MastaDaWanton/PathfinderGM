"""What each planned slot is asked, and the enemy's turn written the planned way.

The 2026-11-04 diagnosis (docs/narration-diagnosis.md): 704 beats blind-scored by two
scorers, 0.20 errors a beat on today's code, and the errors systematic — slot temperature
0.1 changed nothing, a stock model failed the same way. They come from what the narrator is
told. This file holds the patterns that were the plan's own (the measurements are in
docs/narration-diagnosis.md, "The plan's own patterns"):

  1. the declared fight's act slot, told to show the squaring-up "and stop there", never
     told the rest of its own tell — the witnesses and the warrant (14% of the baseline);
  2. somebody else's turn in a fight written as free prose outside the plan, with no tells
     check: "Its teeth graze your skin" for a miss, "though it remains standing" for a wolf
     knocked prone a moment before (11%);
  3. the player's line shown done beyond what the engine decided: "a brutal blow that ends
     the bandit's struggle" for a blow banded "down", "You nod your head and accept the
     task" with no tell, "The smith takes the coins from your hand" against "pays nothing
     more" (about 9%, and 5% refused payments).

Each was found by re-asking the slot's own recorded call with one thing changed; the counts
are in the docstrings. Pattern 4 of the lane ("makes the check by 0" told as failed) is the
tell's wording, not the slot's: the same call with only "by 0" taken off the tell came back
failed 0 of 6 times against 6 of 6 — it is left to the tell-wording lane.
"""
from __future__ import annotations

import json

from gm import planned, prompts
from rules import trial
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc
from tests.test_narration_faithfulness import _chat, _Reply, _verdicts
from tests.test_trial import _guard, _seller, _steal_an_apple
from tests.test_wanted import _table

LAST_BEAT = "The market is loud around you."


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    foe = instantiate("thug", scene=s, name="the bandit")
    s.add(foe)
    ally = instantiate("guildhand", scene=s, name="Marra")
    s.add(ally)
    return s, Engine(s, Dice(seed=3)), foe, ally


def _say(slots, key):
    return next(x["say"] for x in slots if x["key"] == key)


# --- 1. the declared fight ----------------------------------------------------------------

def test_a_witnessed_crime_carries_its_own_sentence_on_its_record():
    """The report's tell is appended to the act's own (`Engine.run`): "… Nothing has landed
    yet. Seen by Pallo Farrow, the guardsman and the second guardsman: there will be a
    warrant for assault." The plan tells it as its own fact, so the sentence rides the
    effect (`told`) — read off the record, never cut out of the joined English."""
    s, e, pc = _table()
    _seller(s)
    _guard(s)
    res = _steal_an_apple(e, s)
    give = next(o for o in res.outcomes if o.op == "give")
    wanted = next(x for x in give.effects if x.get("kind") == "wanted")
    assert wanted["told"].startswith("Seen by") and wanted["told"] in give.tell


def test_the_declared_fight_tells_the_whole_of_its_tell_after_the_squaring_up():
    """7 of 7 baseline runs of the declared punch, 2 of 7 of the declared cruelty (14% of
    the diagnosis's errors): the slot was told to show the squaring-up "and stop there", and the
    witnesses and the warrant in the same tell were never on the page. Re-asked with the
    recorded call, 0 of 4 told the warrant; as THE MOMENT, in order, 8 of 8."""
    s, engine, foe, _ally = _scene()
    told = "Seen by the guardsman: there will be a warrant for assault."
    joined = Outcome("i1", "attack",
                     tell=f"Battle is joined: Kesst Vayr squares off against the bandit. "
                          f"Nothing has landed yet. {told}",
                     effects=[{"kind": "battle_joined", "ref": "pc", "target": foe.ref},
                              {"kind": "wanted", "town": "t", "charge": "assault",
                               "told": told}])
    say = _say(planned.build_plan(engine, "I punch the bandit.", [joined],
                                  last_beat=LAST_BEAT), "fact1")
    assert "stop there" not in say
    moment = say.split("THE MOMENT (engine facts, in order):\n", 1)[1]
    assert moment.index("squares up") < moment.index(told)
    assert "every one of them is told" in say
    assert "I punch the bandit." not in say, "the line carries a blow nobody struck"


# --- 3. the player's line ------------------------------------------------------------------

def test_a_blow_slot_is_the_engines_facts_and_never_the_players_intent():
    """"I finish off the dying bandit with my longsword": a blow the engine banded "down",
    no death in the tell. Re-asked six times with its recorded call: killed 6 of 6 with the
    line in the slot and "a brutal blow that could end it" among the facts; 3 of 6 without
    the line; 0 of 6 without either."""
    s, engine, foe, _ally = _scene()
    hit = Outcome("i1", "attack", actor="pc",
                  tell="Kesst Vayr hits the bandit with the longsword for 6 slashing.",
                  blows=[{"result": "hit", "ref": foe.ref, "weapon": "longsword",
                          "severity": "brutal", "left": "down"}])
    say = _say(planned.build_plan(engine, "I finish off the dying bandit", [hit],
                                  last_beat=LAST_BEAT), "fact1")
    assert "finish off" not in say and "THE BLOW" in say
    for pool in planned._SEVERITY.values():
        assert not any("end" in w.split() or "ends" in w for w in pool), pool


def test_no_miss_is_worded_as_a_touch():
    """A graze is a hit. The wolf's close misses came back "Its teeth graze your skin" on 6
    of its baseline turns (3 scored), and "grazes past" was one of the close-miss words."""
    assert not any("graze" in w for pool in planned._MISS.values() for w in pool)


def test_the_players_own_say_carries_the_words_the_engine_heard_not_the_line():
    """"I agree to his price and pay": the line rode the say slot and came back "reaching
    into your pouch to settle the payment"; the say's tell already holds the words."""
    s, engine, _foe, _ally = _scene()
    said = Outcome("i1", "say", tell="Kesst Vayr speaks to the bandit, to the effect that "
                                     "I agree to your price.",
                   effects=[{"kind": "said", "who": "pc", "to": "zz"}])
    say = _say(planned.build_plan(engine, "I agree to his price and pay", [said]), "fact1")
    assert "and pay" not in say and "to the effect that I agree" in say


def test_a_refused_act_is_told_as_not_happening_and_never_rides_the_line():
    """The refused payment "pays nothing more: the smith took the fee with the job", asked
    "Show it as it happens": the smith took the coins on 6 of 6 re-asks, whether or not the
    say slot carried the line. Asked as a refusal, in the model's own words: 1 of 8."""
    s, engine, _foe, _ally = _scene()
    pay = Outcome("i1", "commission", status="refused",
                  tell="Kesst Vayr pays nothing more: the smith took the fee with the job.")
    say = _say(planned.build_plan(engine, "I pay him", [pay]), "fact1")
    assert say.startswith("What the player tried here did not happen: the engine refused it")
    assert "I pay him" not in say and planned._AS_IT_HAPPENS not in say


def test_an_act_slot_puts_the_engines_decision_first_and_the_line_after():
    """"I take the job": "Show the player doing it and what came of it" invented what came
    of it — "the guild clerk hands you the supplies to deliver" — on 2 of 8 re-asks; with
    the decision first and the line as how they went about it, 0 of 8."""
    s, engine, _foe, _ally = _scene()
    took = Outcome("i1", "quest", tell="Kesst Vayr takes it on: Courier to the North Gate.")
    say = _say(planned.build_plan(engine, "I take the job", [took]), "fact1")
    assert say.startswith("The engine decided this: Kesst Vayr takes it on")
    assert say.index("takes it on") < say.index('"I take the job"')
    assert "what came of it" not in say


def test_a_doing_slot_with_no_tell_asks_for_the_attempt_not_the_deed():
    """No tell at all: "does what the player said … Show exactly that" wrote "You nod your
    head and accept the task" (6 of 6 re-asks) and "you purchase the silver bracelet" (2 of
    3) with nothing taken or sold. Asked as an attempt: 1 of 8 and 0 of 4."""
    s, engine, _foe, _ally = _scene()
    say = _say(planned.build_plan(engine, "I take the job", [], last_beat=LAST_BEAT), "doing")
    assert "decided nothing" in say and "nothing that comes of it" in say
    assert "does what the player said" not in say


def test_the_dying_are_not_called_dead_and_the_prone_are_on_the_ground():
    """The plan's PEOPLE HERE and THE SCENE NOW called anybody under 0 hit points "dead",
    beside a blow the engine banded "down": the dying bandit's blow was written as the kill.
    Dead is the engine's tag. And the trip line's wolf, knocked prone, was "still standing"
    on the next turn: prone is said."""
    s, engine, foe, ally = _scene()
    foe.hp = -3
    ally.add_condition("prone")
    what = {p["name"]: p["what"] for p in planned.present(engine)}
    assert what["the bandit"].startswith("dying") and "dead" not in what["the bandit"]
    assert what["Marra"].startswith("prone")
    block = prompts.scene_now(s)
    assert "dead on the ground" not in block and "down but alive: the bandit" in block


# --- 2. somebody else's turn, planned -----------------------------------------------------

def _wolf_turn(foe, ally):
    """Marra's turn: she closes and clubs the bandit, then a second swing misses."""
    return [Outcome("i1-close", "move", actor=ally.ref,
                    tell="Marra closes 25 ft on the bandit to strike."),
            Outcome("i1", "attack", actor=ally.ref,
                    tell="Marra hits the bandit with the club for 3 bludgeoning. Marra's "
                         "attack with the club misses the bandit (9 against AC 14).",
                    blows=[{"result": "hit", "ref": foe.ref, "weapon": "club",
                            "severity": "glancing", "left": "hurt"},
                           {"result": "miss", "ref": foe.ref, "weapon": "club",
                            "how": "close"}])]


def test_somebody_elses_turn_is_one_slot_a_blow_with_whose_turn_beside_the_plan():
    """The consequence call wrote a creature's turn in one free passage: a model asked for N
    things answers in parallel (CLAUDE.md), and nothing checked it against its tells."""
    s, engine, foe, ally = _scene()
    slots = planned.turn_plan(engine, _wolf_turn(foe, ally), said={})
    assert [x["key"] for x in slots] == ["fact1", "fact1-2"]
    assert "HIT — Marra at the bandit" in slots[0]["say"] and "MISS" not in slots[0]["say"]
    assert "MISS — Marra at the bandit" in slots[1]["say"] and "HIT" not in slots[1]["say"]
    assert slots[0]["tells"] and not slots[1]["tells"], "the act's tells ride its first slot"
    block = planned.turn_block(engine, _wolf_turn(foe, ally), "Marra")
    assert block.startswith("WHOSE TURN: Marra's, not the player's")
    assert "No blow this turn was aimed at you" in block


def test_a_turn_in_a_fight_goes_through_the_tells_check_and_its_remake(monkeypatch):
    """The trip line: the wolf knocked prone, then a companion's blow at it written "though
    it remains standing to face the next strike" — free prose no check read. Written the
    planned way, the tells check reads the turn and remakes only the slot that broke one."""
    s, engine, foe, ally = _scene()
    outcomes = _wolf_turn(foe, ally)
    answers = ["Marra's club cracks against the bandit's ribs, though it remains standing.",
               "Marra swings again and the club passes a finger's width wide.",
               "Marra's club cracks against the bandit's ribs as he lies in the dirt."]
    asked = []

    def call_slot(slot, messages, who, **kw):
        asked.append((slot["key"], messages))
        reply = _Reply(json.dumps({"text": answers.pop(0)}))
        return reply, reply.json()

    monkeypatch.setattr(planned, "call_slot", call_slot)
    chat = _chat(_verdicts(("contradicts", "F1", "it remains standing"),
                           ("agrees", "F1", "")),
                 _verdicts(("agrees", "F1", "")))
    from gm import beat_verify as bv

    def faith(text, tells):
        return bv.against_tells(text, tells, who="Kesst Vayr", chat=chat)

    out = planned.write(engine, brief="", outcomes=outcomes, player_input="",
                        who=("stub", "", "ollama", ""), faith=faith, acting="Marra",
                        last_beat="The bandit is knocked prone.")
    assert [k for k, _m in asked] == ["fact1", "fact1-2", "fact1"], "only the clash remade"
    assert "remains standing" not in out.text and "lies in the dirt" in out.text
    assert out.suggestions == [], "the player's own beat offers what to do next"
    plan = asked[0][1][-1]["content"]
    assert "WHOSE TURN: Marra's" in plan and "The bandit is knocked prone." in plan


def _declared(engine, foe, told):
    return Outcome("i1", "attack",
                   tell=f"Battle is joined: Kesst Vayr squares off against the bandit. "
                        f"Nothing has landed yet. {told}",
                   effects=[{"kind": "battle_joined", "ref": "pc", "target": foe.ref},
                            {"kind": "wanted", "town": "t", "charge": "assault",
                             "told": told}])


def _write_declared(monkeypatch, engine, foe, answers):
    told = "Seen by the guardsman: there will be a warrant for assault."
    asked = []

    def call_slot(slot, messages, who, **kw):
        asked.append((slot["key"], messages[-1]["content"]))
        text = answers.pop(0) if slot["key"] == "fact1" else "Stalls crowd the square."
        reply = _Reply(json.dumps({"text": text}))
        return reply, reply.json()

    monkeypatch.setattr(planned, "call_slot", call_slot)

    def faith(text, tells):
        from gm import beat_verify as bv

        return bv.TellsRead()

    faith.second = lambda text, fact: ("tells it" if "warrant" in text
                                       else "says nothing about it")
    out = planned.write(engine, brief="", outcomes=[_declared(engine, foe, told)],
                        player_input="I punch the bandit.", who=("stub", "", "ollama", ""),
                        faith=faith, last_beat=LAST_BEAT)
    return out, asked, told


def test_a_declared_fight_that_leaves_the_warrant_out_is_asked_once_more(monkeypatch):
    """On the bench of the declared-fight shape the warrant was told on 5 of 6 declared
    beats; the sixth wrote the witnesses "noting your defiance" and stopped. An omission
    contradicts nothing, so the tells check cannot see it: the slot is read back for each
    fact it must tell, the fact first, and asked again with the missing one named."""
    s, engine, foe, _ally = _scene()
    out, asked, told = _write_declared(monkeypatch, engine, foe, [
        "You square up to the bandit while the guardsman watches.",
        "You square up to the bandit; the guardsman saw it, and there will be a warrant."])
    acts = [a for k, a in asked if k == "fact1"]
    assert len(acts) == 2 and told in acts[1] and "It leaves out" in acts[1]
    assert "there will be a warrant" in out.text


def test_a_remake_that_still_leaves_it_out_keeps_the_first_answer(monkeypatch):
    s, engine, foe, _ally = _scene()
    out, asked, _told = _write_declared(monkeypatch, engine, foe, [
        "You square up to the bandit while the guardsman watches.",
        "You raise your fists at the bandit."])
    assert "the guardsman watches" in out.text and "raise your fists" not in out.text
    assert any("still untold" in n for n in out.notes)
