"""Three defects the live check of 2026-11-07 found on the turn-budget build.

The check ran fifteen lines from one saved tavern scene (Kesst, "quiet-the-common-room",
gemma-4-12B reading and narrating) through the real `/api/say`. The readings below are the
reader's, copied from that run's record (check2.json, outside the repo); the planner is
stubbed with the plan the run logged, so no model is called.

  1. In-room movement refused as an unknown place. "I run to the other side of the room
     and begin cooking dinner…" was read `go: the other side of the room`; the walk-to-
     nowhere answer (`acts_to_ops._nowhere`) refused it as "You don't know of anywhere
     called "the other side of the room" here", and the beat said "You move toward the
     hearth and begin cooking dinner … You remain where you are".
  2. The budget did not cut inside a clause — tests/test_turn_budget.py.
  3. A raw engine tell on the page. "I mutter "fool" and walk out": a repair cut the whole
     of the provoke's slot, the engine's line stood in for it, and the beat opened "the
     potboy cools: has no time for you." in lower case. And the provoke itself came from
     `judgement.inject_provoke` reading the insulting word in the quotation, though the
     reader had read the mutter as said to nobody (`talk`, no target, cost `free`).
"""
from __future__ import annotations

import copy
import json

from gm import acts_to_ops, agent, interpret, planned
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
PANGRELLA = WORLD.by_name("Pangrella", kind="CITY").id

# Line 1's reading, as the run recorded it (the turn's reading, cut to the deeds done now).
LINE_1 = ("I run to the other side of the room and begin cooking dinner then i serve the "
          "food i made to everyone")
READ_1 = {"question": False, "claims": [], "actions": [
    {"act": "go", "place": "the other side of the room",
     "span": "run to the other side of the room"},
    {"act": "other", "object": "dinner", "cost": "takes_time",
     "span": "begin cooking dinner"}]}
# Line 9's, as the turn_log recorded it.
LINE_9 = 'I mutter "fool" and walk out'
READ_9 = {"question": False, "claims": [], "actions": [
    {"act": "talk", "says": "fool", "cost": "free", "span": 'mutter "fool"'},
    {"act": "leave", "span": "walk out"}]}


def _room(with_potboy=False):
    s = Scene(location_id=PANGRELLA)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    potboy = None
    if with_potboy:
        made = e._bring_in("guildhand", name="the potboy")
        potboy = s.people[made[0]["ref"]]
        assert potboy.ref in s.actors
    return s, e, potboy


class _Reply:
    """The planner's reply, stubbed: no model is called."""

    def __init__(self, plan):
        self.text = json.dumps({"narration": "", "intents": plan})
        self.seconds, self.model = 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


# --- 1. moving inside the place is never travel -------------------------------------------

def test_the_other_side_of_the_room_is_a_move_inside_it_not_nowhere():
    """Line 1 of the live check of 2026-11-07: "the other side of the room" was refused as
    nowhere known — the old test read the phrase's last word, "room", which is no fixture.
    The part of the room is the word before "of" ("side"): a move inside the place. The
    plan of nothing but `narrate_only` is left alone, so the engine refuses nothing and
    the narrator is never told the walk failed."""
    s, e, _p = _room()
    was = s.at
    frame = copy.deepcopy(READ_1)
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].nowhere == "" and rows[0].ops == [] and rows[0].intents == []
    plan = [{"op": "narrate_only", "because": "the player crosses the room and cooks"}]
    raw = acts_to_ops.nowhere_to_go(acts_to_ops.apply(plan, rows, frame, s, notes=[]), rows)
    assert not any((r.get("params") or {}).get("not_here") for r in raw)
    out = e.run(e.validate(raw))
    assert [o.status for o in out.outcomes] == ["resolved"]
    assert "anywhere called" not in " ".join(o.tell for o in out.outcomes)
    assert s.at == was


def test_line_one_through_the_real_plan_turn_refuses_nothing(monkeypatch):
    """The same line through `GMAgent.plan_turn`, the stubbed planner writing the bare
    `narrate_only` it wrote live: no `not_here` on the plan, so the beat cannot say "You
    remain where you are" beside "You move toward the hearth"."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent

    s, e, _p = _room()
    said = "I run to the other side of the room and begin cooking dinner."
    interpret.remember(said, copy.deepcopy(READ_1))
    plan = [{"op": "narrate_only", "because": "the player crosses the room and cooks"}]
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(plan))
    got = GMAgent(WORLD, e).plan_turn(said, history=[])
    assert not any((i.params or {}).get("not_here") for i in got.intents)
    out = e.run(got.intents)
    assert not any(o.status == "refused" for o in out.outcomes), [o.tell for o in
                                                                  out.outcomes]


def test_parts_and_fixtures_of_the_room_are_inside_it_and_the_quarters_are_not():
    """The closed list (`judgement._FIXTURES` and the few it lacks) read at the phrase's
    head or before its "of"; a part of ANOTHER place the town has is that place; and the
    owner's 2026-11-05 row 69, "the quarters", is still nowhere known."""
    s, e, _p = _room()
    here = str(s.at)
    places = e.places()

    def inside(place):
        return interpret.within_place({"act": "go", "place": place}, places, here)

    for place in ("the other side of the room", "the far end of the hall", "the hearth",
                  "the fire", "the back corner", "the middle of the taproom",
                  "the stairs", "the rear of the inn"):
        assert inside(place), place
    assert not inside("the quarters")
    assert not inside("the docks")
    elsewhere = next(p for p in places if p.id != here)
    assert not inside(f"the far side of {elsewhere.name}")
    # A go only: "the side of the room" under another act is not a walk.
    assert not interpret.within_place({"act": "look", "place": "the side of the room"})
    rows = acts_to_ops.table({"actions": [{"act": "go", "place": "the quarters",
                                           "span": "walk toward the quarters"}]},
                             s, places=places)
    assert rows[0].nowhere == 'You don\'t know of anywhere called "the quarters" here.'


def test_the_reader_says_a_walk_stays_inside_by_a_closed_field():
    """The reader's own answer first: `within_place`, a boolean on the go act's
    alternative (required, so the sampler cannot skip it), taught by two demonstrations,
    kept by `ground` only when true. A phrase the noun list does not know ("the spot
    where the light falls" is on it; "the drunk's elbow" is not) stands on the field."""
    alts = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    by_act = {a["properties"]["act"]["const"]: a for a in alts}
    assert by_act["go"]["properties"]["within_place"] == {"type": "boolean"}
    assert "within_place" in by_act["go"]["required"]
    assert "within_place" not in by_act["journey"]["properties"]
    taught = [a.get("within_place") for _said, f in interpret._DEMOS
              for a in json.loads(interpret._demo_reply(f))["actions"] if a["act"] == "go"]
    assert taught.count(True) >= 2 and False in taught
    line = "I sidle up to the drunk's elbow"
    frame, _dropped = interpret.ground({"actions": [
        {"span": "sidle up to the drunk's elbow", "act": "go", "place": "the drunk's elbow",
         "within_place": True}]}, line)
    assert frame["actions"][0]["within_place"] is True
    s, e, _p = _room()
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].nowhere == ""
    # Said false, or not said, the phrase is judged by the list: still nowhere known.
    frame, _dropped = interpret.ground({"actions": [
        {"span": "sidle up to the drunk's elbow", "act": "go", "place": "the drunk's elbow",
         "within_place": False}]}, line)
    assert "within_place" not in frame["actions"][0]
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].nowhere.startswith("You don't know of anywhere called")


# --- 3. a tell never reaches the page raw, and a mutter provokes nobody ---------------------

def test_the_engines_line_opens_its_sentence_with_a_capital():
    """Line 9 of the live check of 2026-11-07: a repair cut the provoke's slot, and its
    stand-in (`planned.engine_line`, through `agent.keep_act_slots`) opened the beat "the
    potboy cools: has no time for you." — the potboy's name as the scene holds it."""
    tell = "the potboy cools: has no time for you."
    assert planned.engine_line([tell]) == "The potboy cools: has no time for you."
    slots = ({"key": "fact1", "wrote": "The potboy's face hardens.", "tells": [tell]},
             {"key": "fact2", "wrote": "You push back from the table and walk out.",
              "tells": ["You are at the market now."]})
    before = ("The potboy's face hardens. You push back from the table and walk out. "
              "What do you do?")
    after = "You push back from the table and walk out. What do you do?"
    text, notes = agent.keep_act_slots(before, after, slots)
    assert text.startswith("The potboy cools: has no time for you. You push back")
    assert notes
    # Only the first letter of each tell: an initial is not a sentence's end.
    assert planned.engine_line(["Mira H. goes along with the escort."]) == \
        "Mira H. goes along with the escort."
    assert planned.engine_line(['"fool," says the potboy.']) == '"Fool," says the potboy.'


def test_a_mutter_to_nobody_provokes_nobody(monkeypatch):
    """The live line's provoke came from `judgement.inject_provoke` — "fool" in the
    quotation — aimed at the potboy as the only person standing there, though the reader
    read the mutter as `talk`, no target, cost `free`: said to nobody who would answer.
    Through the real `plan_turn`, the stubbed planner writing the `say` it wrote live:
    no provoke. Words the reader aimed at him, or
    read as an insult, still provoke him."""
    from gm import agent as agent_mod
    from gm.agent import GMAgent
    def turn(reading, line=LINE_9):
        s, e, potboy = _room(with_potboy=True)
        interpret.remember(line, copy.deepcopy(reading))
        plan = [{"op": "say", "actor": "pc",
                 "params": {"words": "fool.", "to": potboy.ref}}]
        monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(plan))
        got = GMAgent(WORLD, e).plan_turn(line, history=[])
        return s, potboy, [i.op for i in got.intents]

    talk_only = {"question": False, "claims": [], "actions": [READ_9["actions"][0]]}
    s, potboy, ops = turn(talk_only)
    assert "provoke" not in ops, ops
    assert interpret.said_to_nobody(talk_only, s)
    # Aimed at him: the reader's target, cost answered from the act.
    at_him = {"question": False, "claims": [], "actions": [
        {"act": "talk", "says": "fool", "target": "the potboy",
         "span": 'mutter "fool" at the potboy'}]}
    s, potboy, ops = turn(at_him, 'I mutter "fool" at the potboy')
    assert "provoke" in ops
    assert not interpret.said_to_nobody(at_him, s)
    # Read as an insult: always somebody's.
    insult = {"question": False, "claims": [], "actions": [
        {"act": "insult", "says": "fool", "cost": "free", "span": 'mutter "fool"'}]}
    assert not interpret.said_to_nobody(insult, s)
    # No reading at all: the turn as it always was.
    assert not interpret.said_to_nobody(None, s)
