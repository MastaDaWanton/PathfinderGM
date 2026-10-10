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


def test_a_sleep_the_player_did_not_walk_to_walks_nowhere():
    """Found replaying turn 11 live on the branch: "I make camp and sleep until dawn", read
    as one `rest`, was planned `travel` to the outskirts and then the rest — an hour's walk
    nobody asked for. A travel stands only behind a walking act or a place the words name."""
    plan = [{"op": "travel", "params": {"place": "the outskirts"}},
            {"op": "rest", "actor": "pc", "params": {"kind": "night", "until": "until dawn"}}]
    got = acts_to_ops.unasked_travel([dict(p) for p in plan], TURN_11_FRAME)
    assert [r["op"] for r in got] == ["rest"]
    at_the_inn = {"actions": [{"act": "rest", "place": "the inn", "span": "sleep at the inn"}]}
    assert [r["op"] for r in acts_to_ops.unasked_travel(
        [dict(p) for p in plan], at_the_inn)] == ["travel", "rest"]
    walking = {"actions": [{"act": "go", "place": "town"}, {"act": "rest"}]}
    assert len(acts_to_ops.unasked_travel([dict(p) for p in plan], walking)) == 2


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


# =========================================================================================
# The second run, the same day: narrator_audit's `fight` script (master ec1b4281,
# gemma-4-12B heretic, Pangrella/Vylthysia, fixtures/pc-kesst.json), in "the worst tavern on
# the street" against "the one behind the bar" (c3, a barkeep: a man, he/him, Medium).
# =========================================================================================

def _fight(seed=5):
    from tests._board import face_to_face

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the one behind the bar"))
    engine = Engine(scene, Dice(seed=seed))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"you": ["pc"], "them": ["c1"]}}}]))
    face_to_face(scene)
    return scene, engine


def _swing(engine, **params):
    scene = engine.scene
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    return engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": params, "because": "test"}])).outcomes[-1]


# --- 5. "I keep hitting him" carries on with the fists ------------------------------------

def test_keep_hitting_him_after_two_punches_is_a_third_punch_not_the_rapier():
    """Turn 4 of the fight run: after "I punch him in the face" and "I punch him again"
    (both `weapon: unarmed`), "I keep hitting him" was planned `attack` with no weapon and
    resolved "Kesst Vayr hits the one behind the bar with the rapier for 7 piercing". The
    engine keeps what the player last struck with this fight (`Scene.means`), and a blow
    that names no means carries on with it."""
    scene, engine = _fight()
    assert scene.pc().wielded_key() == "rapier"
    _swing(engine, weapon="unarmed")
    _swing(engine, weapon="unarmed")
    plan = [{"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
             "params": {"full_attack": False}, "because": "test"}]
    assert engine.validate(plan)[0].params["weapon"] == "unarmed"
    out = _swing(engine)
    assert "rapier" not in out.tell
    assert not any("rapier" in str(e.get("weapon") or "") for e in out.effects)


def test_a_weapon_drawn_since_is_the_players_change_of_means():
    scene, engine = _fight()
    _swing(engine, weapon="unarmed")
    scene.pc().equipped = "dagger"
    plan = [{"op": "attack", "actor": "pc", "target": "c1", "params": {}}]
    assert not engine.validate(plan)[0].params.get("weapon")


def test_the_means_end_with_the_fight():
    scene, engine = _fight()
    _swing(engine, weapon="unarmed")
    assert scene.means["pc"]["weapon"] == "unarmed"
    scene.end_encounter()
    assert scene.means == {}


# --- 6. a take off a foe in a fight is a Steal, never a minted thing or a swing -----------

TURN_7_TEXT = "I take what he was carrying."
TURN_7_FRAME = {"question": False, "claims": [], "actions": [
    {"act": "take", "object": "what he was carrying", "span": "take what he was carrying"}]}
TURN_7_PLAN = [
    {"op": "attack", "actor": "pc", "target": "c1", "because": "stealing his belongings",
     "params": {"item": "the pouch", "manoeuvre": "steal", "full_attack": False}},
    {"op": "give", "actor": "pc", "because": "the player took it",
     "params": {"item": "what he was carrying", "to": "pc"}},
]


def test_taking_what_he_was_carrying_mid_fight_is_one_steal_and_nothing_minted():
    """Turn 7: "Kesst Vayr's attack with the rapier misses the one behind the bar" AND
    "Kesst Vayr takes the what he was carrying." — the table built a give of the phrase
    from nobody (the world minted it), and the review stripped the plan's steal to a plain
    swing because no steal word was in the sentence. Now the reading's take, in a fight, is
    1e's Steal at the foe, built whole; the plan's attack and give for it are replaced; the
    review keeps the manoeuvre the reading asked for."""
    from gm import judgement

    scene, engine = _fight()
    rows = acts_to_ops.table(TURN_7_FRAME, scene)
    assert [(i["op"], i["params"].get("manoeuvre")) for i in rows[0].intents] == \
        [("attack", "steal")]
    got = acts_to_ops.apply([dict(p) for p in TURN_7_PLAN], rows, TURN_7_FRAME, scene)
    assert [(r["op"], r.get("params", {}).get("manoeuvre")) for r in got] == \
        [("attack", "steal")]
    interpret.remember(TURN_7_TEXT, TURN_7_FRAME)
    intents = engine.validate(got)
    verdict = judgement.review(TURN_7_TEXT, intents, scene)
    assert intents[0].params.get("manoeuvre") == "steal", verdict.corrections
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = engine.run(intents)
    while res.awaiting is not None:
        res = engine.resume(15)
    tells = " ".join(o.tell for o in res.outcomes)
    assert "rapier" not in tells
    assert "what he was carrying" not in scene.pc().goods


# --- 7. words at a foe open no conversation -----------------------------------------------

def test_telling_a_foe_to_stay_down_opens_no_conversation_to_close_as_turned_hostile():
    """Turn 6: "Kesst Vayr makes the intimidate check by 1." then "You are in conversation
    with the one behind the bar" then "the one behind the bar has turned hostile; the
    conversation with them is over" — in one batch. He had been hostile all fight; the say
    opened a conversation that `_settle_talk` closed at the end of the same batch."""
    from rules import attitude

    scene, engine = _fight()
    foe = scene.actors["c1"]
    foe.add_condition(attitude.HOSTILE, None, source="test")
    out = engine.run(engine.validate([{"op": "say", "actor": "pc", "params": {
        "words": "stay down", "to": "c1"}}], origin="author:test"))
    tells = " ".join(o.tell for o in out.outcomes)
    assert "stay down" in tells
    assert "in conversation" not in tells and "turned hostile" not in tells
    assert engine.talking_to() == []


# --- 8. somewhere quiet is next door, not the desert --------------------------------------

def test_somewhere_quiet_is_looked_for_next_door_not_outside_the_walls():
    """Turn 8: "I find somewhere quiet and sit down", read `search: somewhere quiet` and
    `wait`, travelled half an hour through the guildhall, the market and the gate to the
    outskirts in the desert — the plan chose from every place in Vylthysia. A search names
    no place; the travel's choices are the places one door from here, inside the walls."""
    vyl = WORLD.by_name("Vylthysia")
    s = Scene(location_id=vyl.id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 664
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    _run(e, [{"op": "found", "params": {"name": "the worst tavern on the street",
                                        "kind": "tavern", "parent": "the guildhall"}},
             {"op": "travel", "params": {"place": "the worst tavern on the street"}}])
    frame = {"actions": [{"act": "search", "object": "somewhere quiet"},
                         {"act": "wait", "span": "sit down"}]}
    choices = interpret.travel_choices(frame, s, e.places(), WORLD.get(vyl.id))
    assert choices and "the outskirts" not in choices and "the desert" not in choices
    assert "the guildhall" in choices
    # A walk the words named is the words', as before.
    named = {"actions": [{"act": "go", "place": "the outskirts"}]}
    assert "the outskirts" in interpret.travel_choices(named, s, e.places(),
                                                       WORLD.get(vyl.id))
    # And the plan's OWN travel, which no enum holds (the places enum binds only a
    # declared travel): turn 8's walk to the outskirts is struck; next door stands; a
    # place the plan founds for the search stands.
    out = acts_to_ops.unasked_travel(
        [{"op": "travel", "params": {"place": "the outskirts"}},
         {"op": "narrate_only"}], frame, s, e.places())
    assert [r["op"] for r in out] == ["narrate_only"]
    door = acts_to_ops.unasked_travel(
        [{"op": "travel", "params": {"place": "the guildhall"}}], frame, s, e.places())
    assert [r["op"] for r in door] == ["travel"]
    made = acts_to_ops.unasked_travel(
        [{"op": "found", "params": {"name": "a quiet back room", "kind": "room"}},
         {"op": "travel", "params": {"place": "a quiet back room"}}], frame, s, e.places())
    assert [r["op"] for r in made] == ["found", "travel"]


# --- 9. the biggest man in the room is the man in the room --------------------------------

def test_the_victim_question_is_shown_that_the_one_behind_the_bar_is_a_man():
    """The fight script's second line, "I pick a fight with the biggest man in the room",
    came back 422: refused "nobody here answers to the biggest man in the room", with the
    barkeep — a man on his sheet — the one person in the tavern. The question was shown
    "the one behind the bar" and nothing else; probed live, it answered [] 2 of 2 times,
    and ["c3"] 2 of 2 when shown "(a man)" or "(he/him)". The label now carries the
    sheet's gender (or pronouns) and a size that is not a person's."""
    scene, engine = _fight()
    scene.end_encounter()
    foe = scene.actors["c1"]
    foe.gender, foe.pronouns = "man", "he/him"
    assert "a man" in acts_to_ops.label(foe)
    shown = []

    def ask(span, words, people):
        shown.extend(people)
        return [r for r, lab in people if "a man" in lab]

    frame = {"actions": [{"act": "attack", "target": "the biggest man in the room",
                          "span": "pick a fight with the biggest man in the room"}]}
    rows = acts_to_ops.table(frame, scene)
    acts_to_ops.victims(rows, frame, scene, ask=ask)
    assert shown and "a man" in shown[0][1]
    assert rows[0].intents and rows[0].intents[0]["target"] == "c1"
    assert not rows[0].missing
