"""A deed in the player's own line that ends the talk takes their leave first.

The owner's ruling, 2026-10-17 (docs/conversation.md): going to bed or up to a room,
walking off, leaving, taking the road — said in the player's line — end the conversation
first (the free `leave_talk`, with its tell), then the rest of the line happens in order.
Only from the player's words, never from silence.

Measured live the same day (hv-data scratch campaign, the inn off Khalmorin's market, c8
the keeper "the one behind the bar", gemma-4-12B), both refused:

* "I pay for a room for the night and go to bed" — the plan's `rest` refused: "You are
  still in conversation with the one behind the bar. Take your leave first."
* "I say goodbye to the barkeep, go back up to my room and sleep until dawn" — the plan
  wrote `leave_talk` FIRST: "You are not in conversation with c8"; then the `say` opened
  the talk; then the `rest` was refused the same way.
"""
from __future__ import annotations

import json

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ROOM = "I pay for a room for the night and go to bed."
ROOM_READ = {"actions": [
    {"act": "buy", "object": "a room for the night", "span": "pay for a room for the night"},
    {"act": "rest", "place": "bed", "span": "go to bed"}]}
GOODBYE = "I say goodbye to the barkeep, go back up to my room and sleep until dawn."
# The reading the live turns logged for it, verbatim.
GOODBYE_READ = {"actions": [
    {"act": "talk", "target": "the barkeep", "says": "goodbye",
     "span": "say goodbye to the barkeep"},
    {"act": "go", "place": "my room", "span": "go back up to my room"},
    {"act": "rest", "time": "until dawn", "span": "sleep until dawn"}]}
ROAD = "I ask the barkeep about the road."
ROAD_READ = {"actions": [{"act": "talk", "target": "the barkeep", "says": "about the road",
                          "span": "ask the barkeep about the road"}]}


def _inn(talking=True):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    keeper = instantiate("guildhand", scene=s, name="the one behind the bar")
    s.add(keeper)
    e = Engine(s, Dice(seed=2))
    if talking:
        e.join_talk(keeper)
    return s, e, keeper


def _ops(raw):
    return [r["op"] for r in raw]


def test_paying_for_a_room_and_going_to_bed_takes_leave_before_the_rest():
    s, e, keeper = _inn()
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    out = judgement.leave_before_leaving(raw, '', s, ROOM_READ)
    assert _ops(out) == ["leave_talk", "rest"]
    res = e.run(e.validate(out))
    tells = {o.op: (o.status, o.tell) for o in res.outcomes}
    assert tells["leave_talk"][0] == "resolved"
    assert "take your leave of the one behind the bar" in tells["leave_talk"][1].lower()
    assert tells["rest"][0] == "resolved", tells["rest"]


def test_the_goodbye_is_said_then_the_leave_then_the_sleep():
    """The live plan, as written: leave_talk first, then the say, then the rest. The leave
    moves to after the words and before the sleep, and all three resolve."""
    s, e, keeper = _inn(talking=False)
    raw = [{"op": "leave_talk", "params": {"who": keeper.ref, "do": "leave"}},
           {"op": "say", "actor": "pc", "params": {"words": "goodbye", "to": keeper.ref}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night", "until": "until dawn"}}]
    out = judgement.leave_before_leaving(raw, '', s, GOODBYE_READ)
    assert _ops(out) == ["say", "leave_talk", "rest"]
    res = e.run(e.validate(out))
    assert [(o.op, o.status) for o in res.outcomes
            if o.op in ("say", "leave_talk", "rest")] == [
        ("say", "resolved"), ("leave_talk", "resolved"), ("rest", "resolved")]


def test_a_walk_across_the_room_that_was_struck_still_leaves_last():
    """"go back up to my room" is struck as a walk across the room; with no op to stand
    before, the leave goes after the words."""
    s, _e, keeper = _inn()
    raw = [{"op": "say", "actor": "pc", "params": {"words": "goodbye", "to": keeper.ref}}]
    read = {"actions": GOODBYE_READ["actions"][:2]}
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == ["say", "leave_talk"]


def test_a_walk_then_words_to_somebody_has_not_taken_leave():
    s, _e, keeper = _inn()
    read = {"actions": [{"act": "go", "place": "the bar"},
                        {"act": "talk", "target": "the barkeep", "says": "a drink"}]}
    raw = [{"op": "say", "actor": "pc", "params": {"words": "A drink.", "to": keeper.ref}}]
    assert judgement.leave_before_leaving(raw, '', s, read) == raw


def test_asking_about_the_road_stays_in_the_conversation():
    s, e, keeper = _inn()
    raw = [{"op": "say", "actor": "pc", "params": {"words": "What of the road?",
                                                   "to": keeper.ref}}]
    out = judgement.leave_before_leaving(raw, '', s, ROAD_READ)
    assert out == raw
    e.run(e.validate(out))
    assert e.talking_to() == [keeper]


def test_nobody_talking_and_nothing_said_adds_no_leave():
    """Silence never ends what was never open: no leave, so no refusal on the page."""
    s, _e, _keeper = _inn(talking=False)
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert judgement.leave_before_leaving(raw, '', s, ROOM_READ) == raw


def test_without_a_reading_nothing_is_read_from_the_words():
    s, _e, _keeper = _inn()
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert judgement.leave_before_leaving(raw, '', s, None) == raw


class _Reply:
    def __init__(self, plan):
        self.text = json.dumps({"narration": "", "intents": plan})
        self.seconds, self.model = 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


def test_the_measured_lines_through_the_planner(monkeypatch):
    """Both refused lines through the real `plan_turn`, the model writing the live plans."""
    from gm import agent as agent_mod
    from gm import interpret
    from _a_truth import MARKET, scene_at

    for said, read, plan in (
            (ROOM, ROOM_READ, [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]),
            (GOODBYE, GOODBYE_READ, [
                {"op": "leave_talk", "params": {"who": "c1", "do": "leave"}},
                {"op": "say", "actor": "pc", "params": {"words": "goodbye", "to": "c1"}},
                {"op": "rest", "actor": "pc", "params": {"kind": "night"}}])):
        gm, _refs = scene_at(MARKET, [("the one behind the bar", "guildhand")])
        keeper = gm.engine.scene.actors["c1"]
        gm.engine.join_talk(keeper)
        interpret.remember(said, read)

        monkeypatch.setattr(agent_mod.client, "chat", lambda *a, _p=plan, **k: _Reply(_p))
        got = gm.plan_turn(said, history=[])
        ops = [i.op for i in got.intents]
        assert "leave_talk" in ops and "rest" in ops, (said, ops, got.rejections)
        assert ops.index("leave_talk") < ops.index("rest")
        if "say" in ops:
            assert ops.index("say") < ops.index("leave_talk")
        res = gm.engine.run(got.intents)
        rest = next(o for o in res.outcomes if o.op == "rest")
        assert rest.status == "resolved", (said, rest.tell)


def test_words_the_plan_put_after_the_walk_still_come_before_the_leave():
    """Live 2026-10-17 on this branch, the goodbye line's plan: `travel` (no place),
    `say "goodbye"`, `rest`. The leave went before the walk, ahead of the words that opened
    the talk: "You are not in conversation with anybody", then the rest refused. The sleep
    outranks a stray walk, and the words go first."""
    s, e, keeper = _inn(talking=False)
    raw = [{"op": "travel", "actor": "pc", "params": {}},
           {"op": "say", "actor": "pc", "params": {"words": "goodbye", "to": keeper.ref}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night", "until": "until dawn"}}]
    out = judgement.leave_before_leaving(raw, "", s, GOODBYE_READ)
    assert _ops(out) == ["travel", "say", "leave_talk", "rest"]


def test_paying_comes_before_the_leave_even_after_a_stray_walk():
    """Live 2026-10-17: the room line's plan was travel (to the inn it stood in), a coin
    paid, rest; the leave went before the travel and so before the coin."""
    s, _e, keeper = _inn()
    raw = [{"op": "travel", "params": {"place": "the inn"}},
           {"op": "give", "actor": "pc", "target": keeper.ref, "params": {"item": "coin"}},
           {"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert _ops(judgement.leave_before_leaving(raw, "", s, ROOM_READ)) == [
        "travel", "give", "leave_talk", "rest"]
