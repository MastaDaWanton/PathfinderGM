"""The owner's 2026-11-17 bug list, items 10-13: inns, talk and answers.

Read off the owner's own saves (frag and jack, 0.4.0-0.4.2):

  #10 frag T106-T128, jack T205-T225: "the cheapest room" bought the good one, "go to the
      room i paid for" was nowhere, a bed was refused for talking to the innkeeper, "the
      best room" was no room, and "I hand over 2 gold for the private room" was a gift,
      so the night upstairs was billed again.
  #11 jack T208/T211: the innkeeper's reply was written and cut by our own checks.
  #12 jack T276: "I ask how to get to the docks?" went to nobody, in a town with no docks
      whose stables were labelled "docks, stables and the ways out".
  #13 jack: a bench's 16 hours ended the full-night marker, told as "a full night's rest
      wears off", and the next beat had him just waking up.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import Client, override_settings

from gm import acts_to_ops, agent, deed_reader, planned
from gm.brief import inn as inn_brief
from gm.checks import narration_in_quotes, time_kept
from rules import goods, keepers, lodging, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, _ended_records, _silent_end
from rules.sheet import from_dict, load_pc

from test_a_take_is_not_a_boast import SAM

LOC = "5bbd0c40345f"
INN = f"{LOC}~urban:the-inn"
UP = places.storey_id(INN, 1)


@pytest.fixture(autouse=True)
def _book_terms(monkeypatch):
    """The book's prices, unmoved by a seller's own terms (pinned elsewhere)."""
    from rules import pricing

    monkeypatch.setattr(pricing, "seller_terms", lambda scene, seller: (0, []))


def _inn(purse=None):
    s = Scene(location_id=LOC)
    s.at = INN
    pc = from_dict(dict(SAM, purse=dict(purse or {"gp": 5})), ref="pc")
    s.add(pc)
    keeper = instantiate("thug", scene=s, name="the innkeeper")
    keeper.world_entity_id = keepers.entity_id(INN)
    s.add(keeper)
    return s, pc, keeper, Engine(s, Dice(seed=3))


def _known():
    return (places.Place(id=INN, name="the inn", about="", terrain="urban", exits=(UP,)),
            places.Place(id=UP, name="the upper floor of the inn", about="", terrain="urban",
                         exits=(INN,), parent=INN, origin="storey"))


def _run(engine, *ops):
    return engine.run(engine.validate([dict(o, actor="pc", because="t") for o in ops]))


# --- #10: the paid room ------------------------------------------------------------------------

@pytest.mark.parametrize("want,stay", [
    ("the cheapest room available", "poor"),     # frag T106: bought the good one
    ("the best room", "good"),                   # frag T128: no such room
    ("the private room", "good"),                # jack T205
    ("a spot by the hearth", "poor"),
    ("a room for the night", "common"),
    ("the best ale", None),                      # a rank word beside no bed is not a room
])
def test_a_stay_asked_for_by_its_rank_is_that_stay(want, stay):
    found = lodging.find(want)
    assert (found and found["quality"]) == stay


def test_the_held_room_keeps_its_stay_and_covers_every_floor_of_the_house():
    """jack T225: paid downstairs, walked up to the upper floor of the inn, and billed
    5 sp a second time there. The hold is the house's, and carries the stay bought."""
    s, pc, _keeper, engine = _inn()
    assert _run(engine, {"op": "buy", "params": {"item": lodging.PREFIX + "good"}}
                ).outcomes[-1].status == "resolved"
    assert lodging.room_held(pc) == (INN, "good")
    down = places.storey_id(INN, -1)          # this town's inn has an undercroft
    assert lodging.held(pc, down)
    engine.place_party(down)
    left = goods.in_copper(pc.purse)
    night = _run(engine, {"op": "rest", "params": {"kind": "night"}}).outcomes[-1]
    assert night.status != "refused", night.tell
    assert goods.in_copper(pc.purse) == left, "the night upstairs was billed again"
    assert "good room" in night.tell and lodging.ABOUT["good"] in night.tell


def test_talk_with_the_innkeeper_is_no_bar_to_the_bed():
    """frag T101: "talk to the innkeeper to get a bed so that i can get some rest" — the
    rest was refused "You are still in conversation with the innkeeper"."""
    s, pc, keeper, engine = _inn()
    out = _run(engine, {"op": "say", "params": {"to": keeper.ref, "words": "a bed?"}},
               {"op": "rest", "params": {"kind": "night"}})
    night = out.outcomes[-1]
    assert night.op == "rest" and night.status != "refused", night.tell
    assert night.tell.startswith(f"You take your leave of {keeper.name}.")
    assert lodging.held(pc, INN) and not engine.talking_to()


def test_talk_with_anybody_else_still_bars_the_bed():
    s, _pc, _keeper, engine = _inn()
    other = instantiate("thug", scene=s, name="the drover")
    s.add(other)
    out = _run(engine, {"op": "say", "params": {"to": other.ref, "words": "evening"}},
               {"op": "rest", "params": {"kind": "night"}})
    assert out.outcomes[-1].status == "refused"


def test_coin_handed_to_the_keeper_for_a_room_buys_the_room():
    """jack T205: "I hand over 2 gold for the private room" was read `give 2 gold, place:
    the private room`, built a plain gift, and held no room."""
    s, pc, keeper, _engine = _inn()
    frame = {"actions": [{"act": "give", "object": "2 gold", "place": "the private room",
                          "span": "hand over 2 gold for the private room"}]}
    rows = acts_to_ops.table(frame, s, sentence="I hand over 2 gold for the private room")
    built = [i for r in rows for i in r.intents]
    assert built == [{"op": "buy", "actor": "pc",
                      "params": {"item": lodging.PREFIX + "good", "from_": keeper.ref},
                      "because": "the player paid the keeper for a room"}]
    # And the plan's own coin to the keeper beside it is not paid as well.
    plan = [{"op": "give", "actor": "pc", "params": {"item": "gp", "count": 2,
                                                     "from_": "pc", "to": keeper.ref}}]
    out = acts_to_ops.apply(plan, rows, frame, s)
    assert [o["op"] for o in out] == ["buy"]


def test_my_room_is_the_upper_floor_while_it_is_held():
    """frag T113: "go to the room i paid for" was "You don't know of anywhere called…"."""
    s, pc, _keeper, engine = _inn()
    _run(engine, {"op": "buy", "params": {"item": lodging.PREFIX + "good"}})
    row = acts_to_ops.Row(index=0, act="go")
    assert acts_to_ops._to_my_room(row, "the room i paid for", s, _known(), pc)
    assert row.intents == [{"op": "travel", "actor": "pc",
                            "params": {"place": "the upper floor of the inn"},
                            "because": "to the good room the player holds"}]
    # Held by nobody, "my room" is not settled here.
    bare = from_dict(dict(SAM), ref="pc")
    assert not acts_to_ops._to_my_room(acts_to_ops.Row(index=0, act="go"), "my room", s,
                                       _known(), bare)


def test_the_brief_states_the_room_held_and_where_it_is():
    """frag T111: a good room bought, the night narrated on the floor by the hearth."""
    s, _pc, _keeper, engine = _inn()
    _run(engine, {"op": "buy", "params": {"item": lodging.PREFIX + "good"}})
    text, facts = inn_brief.section(SimpleNamespace(scene=s, known=_known()))
    assert facts.get("room_held") == "good"
    assert "the good stay (a small private room with one bed)" in text
    assert "upstairs, on the upper floor" in text


@pytest.fixture
def at_the_market(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = LOC
        c.scene.clock_minutes = 10 * 60
        if c.scene.in_encounter:
            c.scene.end_encounter()
        c.engine().place_party(f"{LOC}~urban:the-market")
        c.save()
        yield cm
        cm._LIVE.clear()


def test_a_counter_trade_is_on_the_turn_log(at_the_market):
    """frag T109: the good room bought at the counter left no turn-log row at all."""
    got = Client().post("/api/trade/do", data=json.dumps({"op": "buy", "item": "gear:rope"}),
                        content_type="application/json").json()
    assert got.get("ok"), got
    row = at_the_market.current().turn_log[-1]
    assert row["kind"] == "turn" and row["door"] == "trade"
    assert row["intents"][0]["op"] == "buy" and row["outcomes"][0]["op"] == "buy"


# --- #11: the reply our own checks cut ---------------------------------------------------------

def test_the_players_own_quote_is_never_narration_in_quotes():
    """jack T208: the player's quote and the innkeeper's reply were read as one quotation
    naming the innkeeper, and both were cut."""
    s, _pc, keeper, _engine = _inn()
    words = ("could you perhaps look into if there are any women capable of fighting and "
             "willing to go adventuring if I pay them")
    text = (f'You say, "{words}." The innkeeper considers it. "I will ask about," the '
            f"innkeeper says.")
    said = [{"who": keeper.ref, "words": "I will ask about"}]
    mine = narration_in_quotes.pc_words(f'I ask the innkeeper "{words}"')
    lines = narration_in_quotes.quoted_narration(text, said, dict(s.actors), mine)
    assert not any(words[:30] in ln for ln, _ in lines), lines


def _slept_ctx(monkeypatch, answer, *, was, now, text, slots=()):
    monkeypatch.setattr(deed_reader, "ENABLED", True)
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = now

    class _R:
        def __init__(self):
            self.text, self.seconds, self.model = json.dumps({"sentence": answer}), 0.1, "s"

        def json(self):
            return json.loads(self.text)

    real = deed_reader.read_slept
    monkeypatch.setattr(deed_reader, "read_slept",
                        lambda *a, **k: real(*a, **dict(k, chat=lambda *x, **y: _R())))
    return SimpleNamespace(scene=s, text=text, was_clock=was, outcomes=(),
                           reading={"actions": [{"act": "wait"}]},
                           reader={"model": "stub", "host": "h"},
                           planned=bool(slots), slots=tuple(slots))


def test_a_moved_clock_is_never_told_it_stood_still_and_the_cut_keeps_other_slots(monkeypatch):
    """jack T211: ten minutes passed, "as the minutes pass" was read as hours, the cut ran
    to the end of the page, and "The hour has not moved" was printed beside "10 minutes
    pass"."""
    wait = "You wait as the minutes pass. The fire settles."
    reply = "'I will ask about,' the innkeeper says."
    text = f"{wait} {reply}"
    slots = [{"key": "fact1", "wrote": wait, "tells": ["10 minutes pass."]},
             {"key": "reply", "wrote": reply}]
    ctx = _slept_ctx(monkeypatch, 1, was=1300, now=1310, text=text, slots=slots)
    found = time_kept.find(ctx)
    assert found and "only 10 minutes" in found[0].fix_hint.lower()
    out, _notes = time_kept.backstop(ctx, text, found)
    assert reply in out, out
    assert "minutes pass" not in out
    assert not time_kept.authored_in(out)


def test_a_reply_cut_whole_is_put_back():
    """jack T208/T211: the reply slot had no tells, so `keep_act_slots` never restored it."""
    reply = "'I will ask about,' the innkeeper says."
    before = f"You make the offer. {reply}"
    after = "You make the offer."
    slots = [{"key": "fact1", "wrote": "You make the offer.", "tells": ["Jack says x."]},
             {"key": "reply", "wrote": reply}]
    out, notes = agent.keep_act_slots(before, after, slots)
    assert reply in out and notes


# --- #12: directions --------------------------------------------------------------------------

def test_a_category_is_labelled_by_the_kinds_the_town_has():
    """jack T276: Featherperch has no docks; its stables were labelled "(docks, stables and
    the ways out)", and the page gave directions to docks that do not exist."""
    present = {"the stables", "the gate", "the inn"}
    assert planned._category_label("transport", present) == "stables and the ways out"
    assert "docks" in planned._kinds_absent(present, "Featherperch")
    full = {"the docks", "the stables", "the well", "the workshops"}
    assert planned._category_label("transport", full) == planned._CATEGORY_WORDS["transport"]
    assert planned._kinds_absent(full, "Featherperch") == ""


def test_a_question_put_to_the_room_goes_to_the_nearest_who_can_answer():
    """jack T276: "I ask how to get to the docks?" at the market had no `to`, so nobody
    answered."""
    s = Scene(location_id=LOC)
    s.at = f"{LOC}~urban:the-market"
    pc = from_dict(dict(SAM), ref="pc")
    s.add(pc)
    far = instantiate("thug", scene=s, name="the fishmonger")
    s.add(far)
    near = instantiate("thug", scene=s, name="the chandler")
    s.add(near)
    s.positions = {"pc": (0, 0, 0), far.ref: (6, 6, 0), near.ref: (2, 2, 0)}
    # The reading as the reader gave it live (no cost: the act's own, `addresses`).
    frame = {"actions": [{"act": "talk", "says": "how to get to the docks",
                          "span": "ask how to get to the docks"}]}
    raw = [{"op": "say", "params": {"words": "How do I get to the docks?"}}]
    got = acts_to_ops.address_the_named(raw, frame, s)
    assert got[0]["params"].get("to") == near.ref, got
    # And as the plan wrote it live: to a placeholder nobody introduced.
    raw = [{"op": "say", "params": {"words": "How do I get to the docks?", "to": "new1"}}]
    got = acts_to_ops.address_the_named(raw, frame, s)
    assert got[0]["params"].get("to") == near.ref, got
    # And aimed by `target` alone, which the engine never reads: the plan's aim is kept.
    raw = [{"op": "say", "target": far.ref, "params": {"words": "How do I get there?"}}]
    got = acts_to_ops.address_the_named(raw, frame, s)
    assert got[0]["params"].get("to") == far.ref, got


# --- #13: the false wake-up -------------------------------------------------------------------

def test_the_full_night_marker_ends_in_silence():
    """jack: "a full night's rest wears off Jack" at the end of a 16-hour bench, and the
    next beat had him waking up."""
    s, pc, _keeper, engine = _inn()
    engine._slept_a_night(pc)
    mark = next(e for e in pc.effects if e.key == "rested-tonight")
    assert _silent_end(mark)
    had = list(pc.effects)
    pc.effects.remove(mark)
    assert _ended_records(pc, had) == []
    pc.effects.append(mark)
    s.advance(17 * 60)
    assert not any("night's rest" in str(r.get("what")) for r in s.take_ended_said())


def test_bench_hours_reach_the_models_memory():
    """jack: the bench's 16 hours were in the transcript and on the clock and nowhere the
    planner and narrator read."""
    from play import bench_clock

    s, pc, _keeper, engine = _inn()
    c = SimpleNamespace(scene=s, transcript=[], history=[])
    bench_clock.pass_time(c, engine, pc, 16 * 60, "at the forge")
    assert [h["role"] for h in c.history] == ["user", "assistant"]
    assert "works 16 hours at the forge" in c.history[1]["content"]
    assert s.take_ended_said() == []
