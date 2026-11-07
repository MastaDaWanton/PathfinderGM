"""The turn's budget: how many deeds of one line are this turn's (Part 1, steps 1-2).

The owner's ruling, 2026-11-06 (docs/turn-budget-and-fixtures-plan.md): multi-step plans
are fine outside a fight, "but once a limit of actions has been hit the world doesnt
stand still it moves as well". Moving about is free; a turn holds up to two quick deeds
(take, give, open, eat, look); the turn ends at once on a deed that takes time (cook,
craft, search a room, rest) or on words to somebody here who would answer (ask, offer,
threaten, insult), so they reply first. The words not reached go back to the pen in the
existing `unfinished` shape ("Not yet done: ...").

His example: "I run to the other side of the room and begin cooking dinner then i serve
the food i made to everyone". Before this, every clause ran in one turn — the run, the
cooking and the serving — and the family sat still while dinner was cooked and served
in a breath. Now the run is free, the cooking takes time and ends the turn, and "serve
the food" waits in the pen.

What each deed costs is the reader's closed `cost` (gm/interpret.py `COSTS`), checked
against the engine, with the act's own cost when the reading names none — never a regex
over the words (the owner's direction of 2026-10-03). No model is called here: the
reading is handed in with `interpret.remember`, as every turn test since 2026-10-03.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import interpret, sequence
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc

DINNER = ("I run to the other side of the room and begin cooking dinner then i serve "
          "the food i made to everyone")


# --- the server: one line, cut where the budget ends ----------------------------------------

@pytest.fixture
def room(tmp_path, monkeypatch):
    """A campaign with the player and a clerk standing in the room, the narrator stubbed,
    and the planner stubbed to record the words it was asked to plan and the reading it
    was handed (`interpret.handed`, taken as the real `plan_turn` takes it)."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import TurnPlan
    from play import campaign as cm
    from play import concurrency, views

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    plans: list[dict] = []

    def plan(agent, text, *a, **kw):
        handed = interpret.handed(text)
        plans.append({"text": text, "reading": handed if handed is not None
                      else interpret.reading_of(text),
                      "fighting": agent.engine.scene.in_encounter})
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    def chat(*a, **k):
        class R:
            text = json.dumps({"narration": "The room goes about its evening. " * 6,
                               "suggestions": ["I look around"]})
            seconds, model, prompt_tokens, reply_tokens, done_reason = 0.0, "s", 0, 0, "stop"

            def json(self):
                return json.loads(self.text)
        return R()

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-thessaly.json"))
        if c.scene.in_encounter:
            c.scene.end_encounter()
        clerk = c.scene.add(instantiate("guildhand", scene=c.scene, name="the clerk"))
        pc = c.scene.pc()
        for ref in [r for r in c.scene.people if r not in (pc.ref, clerk.ref)]:
            c.scene.people.pop(ref)
        c.save()
        yield {"c": c, "plans": plans, "clerk": clerk.ref}
        cm._LIVE.clear()


def _say(text):
    return Client().post("/api/say", content_type="application/json",
                         data=json.dumps({"text": text}))


def _act(span, act, **slots):
    return {"span": span, "act": act, **slots}


def _read(line, *actions):
    interpret.remember(line, {"question": False, "claims": [], "actions": list(actions)})


def _players(c):
    return [b["text"] for b in c.transcript if b["who"] == "player"]


def test_the_owners_dinner_keeps_serving_the_food_for_the_pen(room):
    """The owner's own example. The run is free, the cooking takes time and ends the turn,
    and "serve the food" comes back to the pen with "Not yet done: ...". Before: all three
    deeds in one turn. The planner is asked for the run and the cooking only, and handed
    the reading of those two deeds — no second reader call — and the player's beat is the
    words done now. The lower-case "i" comes back as "I", never "I i serve"."""
    _read(DINNER,
          _act("run to the other side of the room", "go",
               place="the other side of the room"),
          _act("begin cooking dinner", "other", object="dinner", cost="takes_time"),
          _act("serve the food i made to everyone", "give", object="the food i made",
               target="everyone"))
    r = _say(DINNER)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["text"] == "I run to the other side of the room and begin cooking dinner."
    assert [a["act"] for a in plan["reading"]["actions"]] == ["go", "other"]
    left = r.json()["unfinished"]
    assert left["text"] == "I serve the food i made to everyone."
    assert left["line"] == "Not yet done: serve the food i made to everyone."
    assert left["keep_chip"] is False and "takes time" in left["why"]
    assert _players(room["c"])[-1] == plan["text"]


def test_two_quick_deeds_fill_the_turn(room):
    """"I walk to the counter, take the key, open the box and read the letter": the walk
    is free, the key and the box are the turn's two quick deeds, and reading the letter
    is the third — it waits. Before: four deeds in one turn."""
    line = "I walk to the counter, take the key, open the box and read the letter"
    _read(line,
          _act("walk to the counter", "go", place="the counter"),
          _act("take the key", "take", object="the key"),
          _act("open the box", "other", object="the box"),
          _act("read the letter", "look", object="the letter"))
    r = _say(line)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["text"] == "I walk to the counter. I take the key. I open the box."
    assert [a["act"] for a in plan["reading"]["actions"]] == ["go", "take", "other"]
    left = r.json()["unfinished"]
    assert left["text"] == "I read the letter."
    assert left["why"] == "A turn holds two quick deeds."


def test_words_to_somebody_here_end_the_turn_so_they_answer(room):
    """"I ask the clerk for work, take the job and leave": the clerk is standing here and
    would answer, so the turn ends on the asking; taking the job and leaving wait for his
    reply. Before: the job was taken and the player gone before he said a word."""
    line = "I ask the clerk for work, take the job and leave"
    _read(line,
          _act("ask the clerk for work", "talk", target="the clerk", says="for work"),
          _act("take the job", "take", object="the job"),
          _act("leave", "leave"))
    r = _say(line)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["text"] == "I ask the clerk for work."
    left = r.json()["unfinished"]
    assert left["text"] == "I take the job. I leave."
    assert left["line"] == "Not yet done: take the job, leave."
    assert "answer" in left["why"]


def test_movement_never_spends_the_budget(room):
    """Two walks and two quick deeds are one turn: moving about the place is free, so
    "I walk to the hearth, take a cup, walk to the window and take a plate" runs whole,
    as one plan of the player's own words, with nothing put back."""
    line = "I walk to the hearth, take a cup, walk to the window and take a plate"
    reading = [_act("walk to the hearth", "go", place="the hearth"),
               _act("take a cup", "take", object="a cup"),
               _act("walk to the window", "go", place="the window"),
               _act("take a plate", "take", object="a plate")]
    _read(line, *reading)
    r = _say(line)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["text"] == line
    assert [a["act"] for a in plan["reading"]["actions"]] == ["go", "take", "go", "take"]
    assert "unfinished" not in r.json()
    # And walking alone, however far about the room, never ends a turn.
    walks = "I walk to the bar, cross to the window and step over to the door"
    assert sequence.within_budget(
        sequence.clauses(walks),
        [_act("walk to the bar", "go"), _act("cross to the window", "go"),
         _act("step over to the door", "go")],
        interpret.cost_of) is None


def test_a_fight_keeps_its_own_action_economy(room):
    """Inside a fight the budget is not spent: the four-deed line goes to the planner
    whole, as it did before, and the fight's own economy (the engine's) decides."""
    c = room["c"]
    line = "I walk to the counter, take the key, open the box and read the letter"
    _read(line,
          _act("walk to the counter", "go"), _act("take the key", "take"),
          _act("open the box", "other"), _act("read the letter", "look"))
    c.scene.initiative = [(c.scene.pc().ref, 20)]
    c.scene.turn = 0
    c.save()
    assert c.scene.in_encounter
    r = _say(line)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["fighting"] and plan["text"] == line
    assert "unfinished" not in r.json()


def test_a_reading_with_no_cost_falls_back_to_the_act(room):
    """A reading from before the field existed (or a failed reader call, or a provider
    that does not hold the enum) names no cost: the act's own answers (`ACT_COSTS`).
    A `search` takes time, so "give the ring to the clerk" waits."""
    line = "I walk to the well, search the courtyard for the ring and give the ring to the clerk"
    _read(line,
          _act("walk to the well", "go", place="the well"),
          _act("search the courtyard for the ring", "search", object="the ring",
               place="the courtyard"),
          _act("give the ring to the clerk", "give", object="the ring",
               target="the clerk"))
    r = _say(line)
    assert r.status_code == 200, r.content[:300]
    (plan,) = room["plans"]
    assert plan["text"] == "I walk to the well. I search the courtyard for the ring."
    assert r.json()["unfinished"]["text"] == "I give the ring to the clerk."


def test_one_clause_and_an_unread_line_run_exactly_as_before(room):
    """A single clause is never cut, whatever it costs; and a line with no reading at all
    runs whole, as every line did before the budget."""
    _read("I begin cooking dinner", _act("begin cooking dinner", "other", cost="takes_time"))
    r = _say("I begin cooking dinner")
    assert r.status_code == 200 and "unfinished" not in r.json()
    r = _say("I search the room, then take the key and leave")
    assert r.status_code == 200 and "unfinished" not in r.json()
    assert [p["text"] for p in room["plans"]] == [
        "I begin cooking dinner", "I search the room, then take the key and leave"]


# --- the cost: the reader's closed answer, checked against the engine ----------------------

def _scene_with(name="the clerk", down=False):
    s = Scene(location_id="nowhere")
    s.add(load_pc("fixtures/pc-thessaly.json"))
    who = s.add(instantiate("guildhand", scene=s, name=name))
    if down:
        who.hp = -1
    return s, who


def test_every_act_has_a_cost_and_no_reading_needs_one():
    """The closed table covers every act, in the four costs, so a reading that names no
    cost is never without one."""
    assert set(interpret.ACT_COSTS) == set(interpret.ACTS)
    assert set(interpret.ACT_COSTS.values()) <= set(interpret.COSTS)
    assert interpret.cost_of({"act": "go"}) == "free"
    assert interpret.cost_of({"act": "take"}) == "quick"
    assert interpret.cost_of({"act": "craft"}) == "takes_time"
    assert interpret.cost_of({"act": "talk"}) == "addresses"
    # A plan, a purpose or a question does nothing this turn, so it costs nothing.
    assert interpret.cost_of({"act": "talk", "commit": "intended"}) == "free"


def test_the_engines_facts_overrule_the_reader():
    """Ollama holds the enum, not the sense: code checks the answer against what the
    engine knows. A take is instant whatever the reader says; a craft is a work on the
    clock; `addresses` needs somebody here who would answer — said to an empty room,
    words are free and a purchase is quick; struck at somebody down, a blow is quick."""
    assert interpret.cost_of({"act": "take", "cost": "takes_time"}) == "quick"
    assert interpret.cost_of({"act": "craft", "cost": "quick"}) == "takes_time"
    assert interpret.cost_of({"act": "other", "cost": "takes_time"}) == "takes_time"
    s, clerk = _scene_with()
    assert interpret.cost_of({"act": "talk", "target": "the clerk"}, s) == "addresses"
    empty = Scene(location_id="nowhere")
    empty.add(load_pc("fixtures/pc-thessaly.json"))
    assert interpret.cost_of({"act": "talk", "says": "hello"}, empty) == "free"
    assert interpret.cost_of({"act": "buy", "object": "bread"}, empty) == "quick"
    s, man = _scene_with("the bandit", down=True)
    assert man.is_down
    assert interpret.cost_of({"act": "attack", "target": "the bandit"}, s) == "quick"
    # A visit is answered at a door elsewhere: nobody here need answer it.
    assert interpret.cost_of({"act": "call_on", "target": "the cooper"}, empty) == "addresses"


def test_the_reader_is_held_to_the_cost_by_its_schema():
    """Ollama enforces required properties and enums and nothing more (probed 2026-10-03,
    6/6), so `cost` is a required enum on every act's alternative, and on the flat shape."""
    for alt in interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]:
        assert alt["properties"]["cost"] == {"type": "string", "enum": list(interpret.COSTS)}
        assert "cost" in alt["required"]
    flat = interpret.schema()["properties"]["actions"]["items"]
    assert "cost" in flat["required"] and flat["properties"]["cost"]["enum"] == list(
        interpret.COSTS)


def test_every_demonstration_teaches_a_cost_and_the_budget_ones_say_theirs():
    """Demonstration volume beats instruction volume (CLAUDE.md): every demonstration
    writes a cost — the act's own unless it names one — and the cooking-like task under
    `other`, the words said to nobody and the killing stroke say theirs."""
    taught = {}
    for said, frame in interpret._DEMOS:
        reply = json.loads(interpret._demo_reply(frame))
        for a in reply["actions"]:
            assert a["cost"] in interpret.COSTS, (said, a)
            taught[(said, a["span"])] = a["cost"]
    assert taught[("I cross to the hearth and set a pot of stew on to simmer for supper.",
                   "set a pot of stew on to simmer for supper")] == "takes_time"
    assert taught[("I mutter a curse under my breath.",
                   "mutter a curse under my breath")] == "free"
    assert taught[("I kneel and slit the bound smuggler's throat.",
                   "kneel and slit the bound smuggler's throat")] == "quick"
    # And none of them is a line the tests or the owner wrote: recall is not reading.
    lines = {said for said, _f in interpret._DEMOS}
    assert DINNER not in lines and not any("serve the food" in s for s in lines)


def test_the_cost_is_kept_only_when_it_says_something():
    """As `commit` and `means` are: the act's own cost is not written into the frame, a
    different one is, and one outside the enum is dropped and said."""
    line = "I begin cooking dinner and take the pot"
    frame, dropped = interpret.ground({"actions": [
        {"span": "begin cooking dinner", "act": "other", "cost": "takes_time"},
        {"span": "take the pot", "object": "the pot", "act": "take", "cost": "quick"}]},
        line)
    assert frame["actions"][0]["cost"] == "takes_time"
    assert "cost" not in frame["actions"][1]
    frame, dropped = interpret.ground({"actions": [
        {"span": "take the pot", "object": "the pot", "act": "take", "cost": "ages"}]},
        line)
    assert "cost" not in frame["actions"][0] and "take.cost='ages'" in dropped


def test_the_cut_falls_only_between_clauses():
    """A deed that shares a clause with one already done cannot be held back alone, and a
    line whose later clauses hold no deed the reader read is not cut: nothing comes back
    to the pen that the reader did not read as a deed."""
    parts = ["I take the cup and the plate", "take the knife"]
    # Three takes, two of them in the first clause: the third sits alone and waits.
    got = sequence.within_budget(parts, [
        _act("take the cup", "take"), _act("the plate", "take"),
        _act("take the knife", "take")], interpret.cost_of)
    assert got == (["I take the cup and the plate"], ["take the knife"], "quick")
    # A search with nothing read after it: nothing to put back.
    assert sequence.within_budget(["I search the room", "humming softly"],
                                  [_act("search the room", "search")],
                                  interpret.cost_of) is None
    # An action the reader placed nowhere in the words: the line stays whole.
    assert sequence.within_budget(["I search the room", "take the key"],
                                  [_act("rummage everywhere", "search"),
                                   _act("take the key", "take")],
                                  interpret.cost_of) is None


def test_a_lower_case_i_comes_back_as_i():
    """The owner types "i": the pen must say "I serve the food", never "I i serve"."""
    assert sequence.as_sentence("i serve the food i made") == "I serve the food i made."
    assert sequence.plain(["i serve the food"]) == "serve the food"
