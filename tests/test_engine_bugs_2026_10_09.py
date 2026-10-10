"""Four engine bugs from one live run, 2026-10-09 (master ec1b4281, gemma-4-12B heretic,
Pangrella/Khalmorin, fixtures/pc-kesst.json — the narrator audit's town script, turns 7-12).

Each test is built from the run's own turn-log row: the reader's frame and the plan's
intents as recorded, fed through the code that turns them into a turn, without a model.

1. Turn 7, "I leave the shop and walk out towards the gate": the beat ("You turn your back
   on the smith's heat ... leaving the apprentice to their forge") was read as the smith and
   the apprentice ARRIVING, and both were walked in to the gate. Turn 8, "I ask the gate
   guard what lies north": the reading named the guard, the plan introduced him (c6) and
   wrote the say to c4, the smith — "You are in conversation with the smith."
2. Turn 11, "I make camp and sleep until dawn", at 11:57: "rests for 8 hours", the clock at
   7.57 pm. The reader's `time: until dawn` reached nothing.
3. Turn 12, "I break camp and head back to town": read `rest, go`; "rests for 9 hours".
4. Turn 10, "I look for tracks in the grass": read `search`, no op, no roll — the forage the
   plan reached for was struck — and the page wrote a cart's ruts nobody had made.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret
from rules import population
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
KHALMORIN = WORLD.by_name("Khalmorin", kind="CITY").id
HOUR = 60


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _khalmorin(clock=600):
    s = Scene(location_id=KHALMORIN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return s, e


def _go(e, place):
    return _run(e, [{"op": "travel", "because": "t", "params": {"place": place}}])


# --- 1(b). the people left behind do not walk in behind the party ---------------------------

def test_the_smith_and_the_apprentice_left_at_the_smithy_do_not_arrive_at_the_gate():
    """Turn 7's beat-reading row: `arrived: ["c5", "c4"]` for a passage that leaves them —
    and `seen-people ... walked_in: true` for both. The travel's own outcome had said who
    came along (nobody) and who was left. The step now reads the engine's outcome: anybody
    standing at the place this turn's walk left was left there, and the page's arrival of
    them is refused."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    s, e = _khalmorin(624)
    _go(e, "the smithy")
    smithy = s.at
    smith = next(a for a in s.actors.values() if not a.is_pc)
    apprentice = instantiate("guildhand", scene=s, name="tanner's apprentice")
    s.arrive(apprentice, place_id=smithy)
    out = _go(e, "the gate")
    gate = s.at
    assert gate != smithy and smith.ref not in s.actors
    beat = ("You turn your back on the smith's heat and begin the walk out, leaving the "
            "tanner's apprentice to their forge.")
    reading = stub.read(beat, s, engine=e,
                        who={"the smith's": smith.ref, "the tanner's": apprentice.ref},
                        arrived=[smith.ref, apprentice.ref])
    assert set(reading.arrived) == {smith.ref, apprentice.ref}   # the reader's mistake
    ctx = stub.ctx(s, reading, text=beat, engine=e, world=WORLD, turn=7)
    ctx.outcomes = tuple(out.outcomes)
    rows = seen_people.step(ctx)
    assert smith.at == smithy and apprentice.at == smithy
    assert smith.ref not in s.actors and apprentice.ref not in s.actors
    assert all(r.get("walked_in") is False for r in rows if r.get("same_as"))


def test_somebody_from_elsewhere_still_walks_in_when_the_party_did_not_just_leave_them():
    """The rule is the walk's, not a ban: on a turn with no travel, the page's person known
    elsewhere in town walks in as the 2026-10-01 ruling has it."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    s, e = _khalmorin(624)
    _go(e, "the smithy")
    smithy = s.at
    smith = next(a for a in s.actors.values() if not a.is_pc)
    _go(e, "the gate")
    beat = "The smith comes up the road behind you, wiping his hands."
    reading = stub.read(beat, s, engine=e, who={"The smith": smith.ref}, arrived=[smith.ref])
    rows = seen_people.step(stub.ctx(s, reading, text=beat, engine=e, world=WORLD, turn=9))
    assert smith.at == s.at and smith.at != smithy
    assert any(r.get("walked_in") for r in rows)


# --- 1(a). the line goes to the one the words name ----------------------------------------

# Turn 8's row, as recorded: the reading and the plan.
TURN_8_FRAME = {"question": False, "claims": [], "actions": [
    {"act": "talk", "target": "the gate guard", "says": "what lies north",
     "span": "ask the gate guard what lies north"}]}
TURN_8_PLAN = [
    {"op": "introduce", "because": "the player's words commit the turn to it",
     "params": {"who": "guard", "how": "already_here", "template": "guard", "count": 1}},
    {"op": "say", "actor": "pc", "target": "c4",
     "params": {"words": "What lies north?", "to": "c4"}},
    {"op": "narrate_only", "because": "the guard is answering the question"},
]


def _the_gate_with_the_smith():
    """The board turn 8 was planned on: the party at the gate, the smith standing there."""
    s, e = _khalmorin(648)
    _go(e, "the smithy")
    smith = next(a for a in s.actors.values() if not a.is_pc)
    _go(e, "the gate")
    s.move(smith.ref, s.at)
    return s, e, smith


def test_the_question_to_the_gate_guard_goes_to_the_guard_not_the_smith():
    """"Kesst Vayr speaks to the smith, to the effect that What lies north? You are in
    conversation with the smith." The reading named the gate guard; nobody here is the gate
    guard; the plan brought one in. The say goes to the one it brought in."""
    s, e, smith = _the_gate_with_the_smith()
    plan = [dict(p) for p in TURN_8_PLAN]
    notes: list = []
    got = acts_to_ops.address_the_named(plan, TURN_8_FRAME, s, notes=notes)
    say = next(r for r in got if r["op"] == "say")
    assert say["params"]["to"] == "new1" and say["target"] == "new1", notes
    out = _run(e, got)
    said = next(o for o in out.outcomes if o.op == "say")
    guard = next(a for a in s.actors.values() if a.name == "guard")
    assert said.effects[0]["to"] == guard.ref
    assert "the smith" not in said.tell and e.talking_to() == [guard]


def test_a_line_to_somebody_here_goes_to_them_whoever_the_plan_picked():
    s, e, smith = _the_gate_with_the_smith()
    frame = {"actions": [{"act": "talk", "target": "the smith", "says": "about the ore"}]}
    plan = [{"op": "say", "actor": "pc", "params": {"words": "About the ore?", "to": "c99"}}]
    got = acts_to_ops.address_the_named(plan, frame, s)
    assert got[0]["params"]["to"] == smith.ref


def test_a_bare_pronoun_the_engine_cannot_settle_is_left_alone():
    s, e, smith = _the_gate_with_the_smith()
    frame = {"actions": [{"act": "talk", "target": "him", "says": "what lies north"}]}
    plan = [dict(p) for p in TURN_8_PLAN]
    other = instantiate("guildhand", scene=s, name="the carter")
    s.add(other)
    got = acts_to_ops.address_the_named(plan, frame, s)
    assert got == plan


# --- 2. "until dawn" is the next dawn ------------------------------------------------------

def _grasslands(clock):
    s, e = _khalmorin(clock)
    _go(e, "the grasslands")
    s.clock_minutes = clock
    return s, e


def test_sleeping_until_dawn_at_noon_wakes_at_the_next_dawn_with_one_nights_rest():
    """Turn 11: at 11:57 "rests for 8 hours" and the clock at 19:57. Now the clock runs to
    the next 06:00. Nobody sleeps eighteen hours: the camp is kept awake (a wait, charged to
    the body) and the last eight are the night, healed once (CRB p.191)."""
    s, e = _grasslands(717)
    pc = s.pc()
    pc.hp = pc.hp_max - 3
    out = _run(e, [{"op": "rest", "actor": "pc", "because": "a night in the wild",
                    "params": {"kind": "night", "until": "until dawn"}}])
    rest = out.outcomes[0]
    assert s.clock_minutes == 30 * HOUR, s.clock_minutes            # six, the next day
    assert rest.effects[0]["hours"] == 8 and rest.effects[0]["healed"] == 1
    assert "keeps the camp awake" in rest.tell and "until dawn" in rest.tell
    assert pc.awake_minutes == 0


def test_sleeping_until_dawn_at_one_in_the_morning_is_short_of_a_night():
    """Five hours is not "a full night's rest (8 hours of sleep or more)": the clock runs to
    dawn as asked, and nothing heals."""
    s, e = _grasslands(25 * HOUR)
    pc = s.pc()
    pc.hp = pc.hp_max - 3
    out = _run(e, [{"op": "rest", "actor": "pc", "because": "t",
                    "params": {"kind": "night", "until": "until dawn"}}])
    rest = out.outcomes[0]
    assert s.clock_minutes == 30 * HOUR
    assert rest.effects[0].get("short") and rest.effects[0]["healed"] == 0
    assert pc.hp == pc.hp_max - 3 and "short of a full night's rest" in rest.tell


def test_a_night_with_no_time_named_is_the_night_it_always_was():
    s, e = _grasslands(17 * HOUR)
    _run(e, [{"op": "rest", "actor": "pc", "because": "t", "params": {"kind": "night"}}])
    assert s.clock_minutes == 30 * HOUR
    s.clock_minutes = 2 * HOUR
    _run(e, [{"op": "rest", "actor": "pc", "because": "t", "params": {"kind": "night"}}])
    assert s.clock_minutes == 10 * HOUR


TURN_11_FRAME = {"question": False, "claims": [], "actions": [
    {"act": "rest", "span": "make camp", "time": "until dawn"}]}
TURN_11_PLAN = [{"op": "rest", "actor": "pc", "because": "a night in the wild",
                 "params": {"kind": "night"}}]


def test_the_readings_time_reaches_the_rest():
    """The turn-11 plan, as recorded, carried `kind: night` and nothing else."""
    got = acts_to_ops.timed_rests([dict(TURN_11_PLAN[0])], TURN_11_FRAME)
    assert got[0]["params"] == {"kind": "night", "until": "until dawn"}


def test_a_waking_time_the_player_never_named_is_struck():
    frame = {"actions": [{"act": "rest", "span": "make camp"}]}
    plan = [{"op": "rest", "actor": "pc", "params": {"kind": "night", "until": "noon"}}]
    assert acts_to_ops.timed_rests(plan, frame)[0]["params"] == {"kind": "night"}


def test_the_wait_door_and_the_sleep_door_read_one_table_of_times():
    from gm import judgement
    from rules import timewords

    assert judgement.minutes_until("I wait until dawn.", 22 * HOUR) == 8 * HOUR
    assert timewords.minutes_until("until dawn", 717) == 30 * HOUR - 717
    assert timewords.minutes_until("till first light", 23 * HOUR) == 7 * HOUR
    assert timewords.minutes_until("for a while", 600) is None


# --- 3. breaking camp is not a rest --------------------------------------------------------

TURN_12_FRAME_AS_READ = {"question": False, "claims": [], "actions": [
    {"act": "rest", "span": "break camp"}, {"act": "go", "place": "town",
                                            "span": "head back to town"}]}


def test_the_reader_has_a_word_for_the_end_of_a_rest_and_it_owes_no_op():
    """The vocabulary had `rest` ("make camp") and nothing for breaking it, and the sampler,
    held to the enum, took the nearest: turn 12 was read `rest, go` and slept nine hours.
    Probed on the live reader before the change — "I break camp at first light and walk to
    the ford" came back `rest, time: at first light` — and after it, 8 of 8 probe lines read
    as meant: three break-camp/pack-up/get-up lines `rise`, both make-camp lines and "I
    sleep until dawn and head back to town" still `rest`. The enum carries it; nothing in
    code reads the word "break"."""
    assert "rise" in interpret.ACTS and interpret.ACT_SLOTS["rise"] == ()
    schema = interpret.per_act_schema()
    acts = {a["properties"]["act"]["const"]
            for a in schema["properties"]["actions"]["items"]["anyOf"]}
    assert "rise" in acts
    s, e = _grasslands(30 * HOUR)
    frame = {"actions": [{"act": "rise", "span": "break camp"},
                         {"act": "go", "place": "town", "span": "head back to town"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert rows[0].ops == [] and rows[0].intents == []
    assert "rest" not in interpret.ops_for(frame, s, e.places())
    # The recorded misreading owed a rest; that is the row the reader no longer writes.
    assert "rest" in interpret.ops_for(TURN_12_FRAME_AS_READ, s, e.places())


# --- 4. looking for tracks rolls Survival, and finds only what the engine holds ------------

def _track(e, face):
    res = e.run(e.validate([{"op": "track", "actor": "pc", "because": "t"}],
                           origin="author:test"))
    assert res.awaiting is not None and "Survival" in res.awaiting["label"]
    return e.resume(face).outcomes[0]


def test_tracks_on_empty_grass_are_none_and_none_is_invented():
    """Turn 10 rolled nothing, and the page wrote "a clear, recent path — not from a
    person, but from a heavy cart". Nobody had crossed the grass. The roll beats firm
    ground (DC 15, CRB p.107: "lawns, fields, woods") and the tell says nobody has."""
    s, e = _grasslands(717)
    out = _track(e, 18)
    assert out.op == "track" and out.rolls and out.dc["value"] == 15
    assert out.effects[0]["found"] == []
    assert "no tracks here but the party's own" in out.tell


def test_somebody_seen_here_who_has_gone_left_a_trail_and_a_low_roll_finds_nothing():
    s, e = _grasslands(717)
    rider = population.note(s, "a lone rider")
    body = population.embody(s, "a lone rider", "guildhand", world=WORLD, rec=rider)
    assert rider["seen_at"] == s.at and body.at == s.at
    s.move(body.ref, f"{KHALMORIN}~urban:the-gate")
    s.clock_minutes += 2 * HOUR
    found = _track(e, 18)
    assert [t["ref"] for t in found.effects[0]["found"]] == [body.ref]
    assert "Tracks:" in found.tell and body.name in found.tell
    missed = _track(e, 1)
    assert missed.effects[0]["found"] == [] and "No sign" in missed.tell


def test_the_ground_sets_the_dc():
    from rules import tracking

    assert tracking.SURFACE_DC[tracking.SURFACE["grassland"]] == 15
    assert tracking.SURFACE_DC[tracking.SURFACE["swamp"]] == 5
    assert tracking.SURFACE_DC[tracking.SURFACE["mountain"]] == 20


TURN_10_FRAME = {"question": False, "claims": [], "actions": [
    {"act": "track", "place": "the grass", "span": "look for tracks in the grass"}]}


def test_the_reading_builds_the_track_whole_and_the_plans_forage_goes():
    """Turn 10's plan reached for a forage, struck as "not a forage", and nothing rolled.
    The table builds the `track` op itself; the plan's forage or Survival check for the
    same look is replaced, never rolled beside it."""
    s, e = _grasslands(717)
    rows = acts_to_ops.table(TURN_10_FRAME, s, places=e.places())
    assert [i["op"] for i in rows[0].intents] == ["track"]
    plan = [{"op": "forage", "actor": "pc", "params": {}},
            {"op": "check", "actor": "pc", "params": {"skill": "survival", "dc": 15}}]
    got = acts_to_ops.apply(plan, rows, TURN_10_FRAME, s)
    assert [r["op"] for r in got] == ["track"]
    assert "track" in interpret.ACTS and "tracks" not in interpret._WHAT_EACH_IS.split(
        "\nsearch")[1].split("\n")[0]
