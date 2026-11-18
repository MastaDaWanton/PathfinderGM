"""Playtest 2026-11-17 (b), the speech-and-order lane: items 14, 15, 16, 18, 19, 22, 25, 28, 30.

Vesna Kroll on 0.4.2 (master de9a7d09), round 5, T453-T482 of the save in play-043-data.
Each test names the turn and what was measured.
"""
from __future__ import annotations

from gm import acts_to_ops, judgement, prompts
from rules import faces, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, reported_speech
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = WORLD.play["settlements"][0]["id"]


def _party():
    s = Scene(location_id=TOWN)
    pc = instantiate("guildhand", scene=s, name="Vesna Kroll")
    pc.kind = "pc"
    pc.pronouns = "she/her"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return s, e, pc


def _person(s, name):
    who = instantiate("guildhand", scene=s, name=name)
    s.add(who)
    return who


# --- #14, #18, #22, #25: the planner speaking for the NPC ------------------------------

def test_an_npcs_line_in_the_players_plan_is_dropped():
    """#14 (T454): asked for a gold a day, the plan carried the clerk's own say before the
    Diplomacy roll — "The guild doesn't haggle … the private listings of the merchant
    houses" — settling the haggle before the dice and inventing a world fact. #25 (T471)
    the same with the master of the games. Four NPC lines in one session's plans."""
    s, e, pc = _party()
    clerk = _person(s, "the clerk of the guild")
    line = '"Three silver a day is a pittance for a blade like mine. Make it a gold a day."'
    raw = [{"op": "say", "actor": clerk.ref, "target": pc.ref,
            "params": {"words": "The guild doesn't haggle over standard contracts, but you "
                                "might find more favorable terms in the private listings "
                                "of the merchant houses."}},
           {"op": "check", "actor": pc.ref, "target": clerk.ref,
            "params": {"skill": "diplomacy"}}]
    notes: list = []
    out = judgement.no_npc_lines(raw, line, s, notes=notes)
    assert [r["op"] for r in out] == ["check"], out
    assert notes and "dropped" in notes[0]
    # With the clerk's line gone, the player's own demand becomes the say (`inject_say`
    # stood aside for ANY say in the list, which is why T454 had none of hers).
    said = judgement.inject_say(out, line, s)
    assert [r for r in said if r["op"] == "say"][0].get("actor") in (None, "pc", pc.ref)


def test_the_players_words_in_the_npcs_mouth_are_the_players_say_to_them():
    """#18 (T463, BIG): "'You look like you can handle a blade. Are you for hire?' I ask the
    man in the corner" was planned `say actor=c42` with her words, and told "The man in
    corner speaks, to the effect that You look like you can handle a blade"."""
    s, e, pc = _party()
    man = _person(s, "man in corner")
    line = '"You look like you can handle a blade. Are you for hire?" I ask the man in the corner.'
    raw = [{"op": "say", "actor": man.ref, "target": pc.ref,
            "params": {"words": "You look like you can handle a blade. Are you for hire?"}}]
    out = judgement.no_npc_lines(raw, line, s)
    assert out[0]["actor"] == "pc" and out[0]["params"]["to"] == man.ref
    assert out[0]["target"] == man.ref
    told = e.run(e.validate(out, origin="author:test")).outcomes[0].tell
    assert told.startswith("Vesna Kroll"), told
    assert "man in corner speaks" not in told


def test_a_wordless_npc_say_never_reaches_validation():
    """#22 (T467): seven attempts refused "say: missing required param(s) words" — a say for
    the man in the corner with nothing in it — and the turn went to the fallback model."""
    s, e, pc = _party()
    man = _person(s, "man in corner")
    out = judgement.no_npc_lines([{"op": "say", "actor": man.ref, "target": pc.ref}],
                                 '"Then I\'ll hire you for a week. Name your price."', s)
    assert all(r["op"] != "say" for r in out), out
    e.validate(out, origin="author:test")     # no "missing required param(s) words"


def test_a_companions_own_line_is_kept():
    """The rule is the player's plan speaks for nobody it should not: a companion out of a
    fight may still be acted for (`companions.on_their_own_turn`'s docstring)."""
    s, e, pc = _party()
    friend = _person(s, "Marra")
    e.settle_attitude(friend, "friendly", None, "test")
    e.run(e.validate([{"op": "company", "actor": pc.ref, "because": "t",
                       "params": {"who": friend.ref}}], origin="author:test"))
    assert friend.has_state(states.TRAVELS_WITH_YOU)
    raw = [{"op": "say", "actor": friend.ref, "params": {"words": "Lead on, then."}}]
    assert judgement.no_npc_lines(raw, "I nod to Marra.", s) == raw


def test_the_plan_schema_gives_say_the_players_voice_and_words():
    """#14/#18/#22: one intent shape for every op offered every ref as a say's actor and
    let a say carry no words. With `speakers`, a say has its own branch: the actor enum is
    the speakers and `words` is required."""
    schema = prompts.turn_schema(refs=("pc", "c42"), speakers=("pc",))
    branches = schema["properties"]["intents"]["items"]["anyOf"]
    said = next(b for b in branches if b["properties"]["op"]["enum"] == ["say"])
    rest = next(b for b in branches if b is not said)
    assert said["properties"]["actor"]["enum"] == ["pc"]
    assert said["properties"]["params"]["required"] == ["words"]
    assert "say" not in rest["properties"]["op"]["enum"]
    # A companion's or a cheat's plan keeps the one shape.
    assert "anyOf" not in prompts.turn_schema(refs=("pc", "c42"))["properties"]["intents"][
        "items"]
    # And the declared say (the required key) names no speaker at all.
    declared = prompts.turn_schema(refs=("pc", "c42"), must_contain=("say",),
                                   speakers=("pc",))["properties"]["declared"]
    assert "actor" not in declared["properties"]["say"]["properties"]["params"]["properties"]


def test_the_history_remembers_a_says_words():
    """#22: every remembered say was `{"op": "say", "actor": "pc", "target": "c45"}`, a say
    with nothing in it, and the plans copied that shape: 10 refusals of "say: missing
    required param(s) words" on 4 of round 5's turns."""
    from play.views import _remembered
    from rules.intents import Intent

    said = _remembered(Intent(op="say", actor="pc", target="c45",
                              params={"words": "Sergeant, fancy a bout?", "to": "c45"}))
    assert said == {"op": "say", "actor": "pc", "target": "c45",
                    "params": {"words": "Sergeant, fancy a bout?"}}
    assert "params" not in _remembered(Intent(op="travel", params={"place": "the docks"}))


# --- #15: the week told before it was agreed ---------------------------------------------

def test_spoken_agreement_comes_before_the_job_it_takes():
    """#15 (T457): "Fine. I'll take the guard work." The table built `job accept` on the
    talk, put it ahead of the say (a built op goes first within its action), and the beat
    told the whole week and the pay, then her agreement."""
    frame = {"question": False, "actions": [
        {"act": "talk", "says": "Fine. I'll take the guard work.",
         "span": "Fine. I'll take the guard work."}]}
    job = {"op": "job", "actor": "pc", "target": "c40", "params": {"do": "accept"}}
    rows = [acts_to_ops.Row(index=0, act="talk", ops=["say"], intents=[job])]
    raw = [{"op": "narrate_only"}, job,
           {"op": "say", "params": {"words": "Fine. I'll take the guard work."}}]
    assert [r["op"] for r in acts_to_ops.order(raw, rows, frame)] == \
        ["narrate_only", "say", "job"]
    # A walk still carries what it picked up first (the built op of a non-speaking act).
    give = {"op": "give", "params": {"item": "crate"}}
    rows = [acts_to_ops.Row(index=0, act="go", ops=["travel"], intents=[give])]
    raw = [{"op": "travel", "params": {"place": "the market"}}, give]
    assert [r["op"] for r in acts_to_ops.order(raw, rows)] == ["give", "travel"]


# --- #30: the challenge spoken before the walk -------------------------------------------

def test_a_say_no_talk_owns_goes_where_its_words_were_said():
    """#30 (T475): "I go to the barracks and challenge one of the soldiers to a friendly
    sparring bout, fists only" was read `go` + `attack`; the plan's say came first, went to
    the alchemist she was leaving, and nobody at the barracks was challenged."""
    frame = {"question": False, "actions": [
        {"act": "go", "place": "the barracks", "span": "go to the barracks"},
        {"act": "attack", "target": "one of the soldiers",
         "span": "challenge one of the soldiers to a friendly sparring bout, fists only"}]}
    rows = [acts_to_ops.Row(index=0, act="go", ops=["travel"]),
            acts_to_ops.Row(index=1, act="attack")]
    raw = [{"op": "say", "params": {"words": "I challenge you to a friendly sparring bout, "
                                             "fists only.", "to": "c44"}},
           {"op": "travel", "params": {"place": "the barracks"}}]
    assert [r["op"] for r in acts_to_ops.order(raw, rows, frame)] == ["travel", "say"]


def test_the_say_after_the_walk_is_not_to_the_one_left_behind():
    """#30: the say kept `to` the alchemist, who was not at the barracks; asked where the
    words are said, the one it was meant for is not there."""
    s, e, pc = _party()
    places = tuple(e.places())
    here = s.at
    there = next(p for p in places if p.id != here and p.kind not in ("upper", "undercroft"))
    left = _person(s, "the alchemist")
    frame = {"question": False, "actions": [
        {"act": "go", "place": there.name, "span": f"go to {there.name}"},
        {"act": "attack", "target": "one of the soldiers",
         "span": "challenge one of the soldiers to a friendly sparring bout"}]}
    raw = [{"op": "say", "params": {"words": "I challenge you to a friendly sparring bout.",
                                    "to": left.ref}},
           {"op": "travel", "params": {"place": there.name}}]
    notes: list = []
    out = acts_to_ops.address_the_named(raw, frame, s, notes=notes, places=places)
    assert (out[0].get("params") or {}).get("to") != left.ref, (out, notes)


# --- #16: reported speech keeps the player's "I" ----------------------------------------

def test_reported_speech_says_the_speakers_i_as_her():
    """#16 (T459): the tell read "Vesna Kroll asks the clerk where I could hire a sellsword
    or two to watch my back"."""
    said = reported_speech("Vesna Kroll", " to the clerk of the guild",
                           "ask the clerk where I could hire a sellsword or two to watch "
                           "my back.", "the clerk of the guild", "she/her")
    assert said == ("Vesna Kroll asks the clerk where she could hire a sellsword or two to "
                    "watch her back.")
    assert reported_speech("Torvo", "", "ask him if I am welcome here.", "", "he/him") \
        == "Torvo asks him if he is welcome here."
    assert reported_speech("Ash", "", "ask whether I'm late.", "", "they/them") \
        == "Ash asks whether they're late."
    # A challenge is its own deed (the #30 replay told "to the effect that challenge…").
    assert reported_speech("Vesna Kroll", "", "challenge one of the soldiers to a bout.",
                           "", "she/her") ==         "Vesna Kroll challenges one of the soldiers to a bout."
    # No pronouns known: the words as said.
    assert reported_speech("V", "", "ask where I sleep.", "") == "V asks where I sleep."


# --- #19: the same face line on three NPCs in a row ---------------------------------------

def test_a_face_line_is_not_drawn_twice_while_another_is_unworn():
    """#19 (T447/T463/T477): the guild clerk (c40), the barkeep (c41) and the garrison
    sergeant (c45) all wore "a pale seam of scar tissue down one forearm", and c40/c41 the
    same hair — each pick a hash of the ref, blind to the town. Reproduced from the refs:
    the three draw that mark with nothing seen."""
    body = "Korvu have four limbs ending in sharp talons."
    scar = "a pale seam of scar tissue down one forearm"
    blind = [faces.details_for(body, ref, "7ef5e373c993") for ref in ("c40", "c41", "c45")]
    assert all(scar in f for f in blind), blind
    made: list[str] = []
    for ref in ("c40", "c41", "c45"):
        made.append("Korvu: " + body + " " + faces.details_for(
            body, ref, "7ef5e373c993", faces.worn(made)))
    marks = [next(m for m in faces.MARK if m in f) for f in made]
    assert len(set(marks)) == 3, made
    # A whole town: no mark worn twice before every mark is worn once.
    made = []
    for n in range(len(faces.MARK)):
        made.append("Korvu: " + body + " " + faces.details_for(
            body, f"c{n}", "7ef5e373c993", faces.worn(made)))
    assert {next(m for m in faces.MARK if m in f) for f in made} == set(faces.MARK)


def test_a_scene_face_is_spread_over_the_faces_already_there():
    """#19, through the door the keepers come by (`names.face_of` with the scene)."""
    from rules import names

    s, e, pc = _party()
    worn_marks = []
    for k in range(4):
        who = _person(s, f"keeper {k}")
        who.appearance = names.face_of(WORLD, TOWN, who, scene=s)
        worn_marks += [m for m in faces.MARK if m in who.appearance]
    assert len(worn_marks) == len(set(worn_marks)) == 4, worn_marks


# --- #28: the beggar told as a greeting ------------------------------------------------------

def test_the_beggar_on_the_way_is_named_a_beggar():
    """#28 (T473): the tell "a hand comes out, and the mouth above it knows your face is new;
    you are past it before the asking is done" named nobody and nothing asked for, and the
    page wrote "a hand reaches out to greet you, but you pass the question"."""
    from rules import ontheway

    said = ontheway.passing(ontheway.Meeting(kind="beggar", roll=1), "the west crossing")
    assert "beggar" in said and "coin" in said and "walk on" in said, said
