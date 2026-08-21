"""The fifth check: not "is this legal" but "is this what the player asked for".

Checks 1-4 in rules/intents.py established that the GM cannot break the rules. Once the
plumbing worked, the remaining problem was that it could follow every rule and still do
something nobody asked for. Every case here was produced by llama3.1:8b in live play.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import parse_all
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


def review(text, raw, scene=None):
    return judgement.review(text, parse_all(raw), scene)


ATTACK = {"op": "attack", "actor": "pc", "target": "c1"}


# --- Violence nobody asked for ------------------------------------------------------

def test_a_question_is_not_an_attack(scene):
    """Measured: the player wrote "I lean on the gate post and ask the guildhand who
    really pays for the windcatchers" and the GM tripped the man. Legal, and not remotely
    what was asked for.
    """
    v = review(
        "I lean on the gate post and ask the guildhand who really pays for the windcatchers.",
        [{**ATTACK, "params": {"manoeuvre": "trip"}}],
        scene,
    )
    assert not v.ok
    assert v.objections[0].kind == "unprovoked"
    assert "narrate_only" in v.objections[0].message


@pytest.mark.parametrize("text", [
    "I ask him who pays for the windcatchers.",
    "I greet the guildhand and offer him a drink.",
    "I wait by the wall and watch the yard.",
    "I examine the lock on the gate.",
])
def test_peaceful_turns_never_resolve_an_attack(text, scene):
    assert not review(text, [ATTACK], scene).ok


@pytest.mark.parametrize("text", [
    "I have had enough of his lies. I draw my rapier and attack him.",
    "I go for him.",
    "I stab the nearest one.",
    "Two bravos step out of the dark. I turn and fight.",
    "I charge the watchman.",
])
def test_violence_the_player_asked_for_is_allowed(text, scene):
    assert review(text, [ATTACK], scene).ok


def test_a_fight_already_under_way_is_not_second_guessed(scene):
    """Mid-combat the player may say almost anything — "I back towards the wall" — while
    still being in a fight where attacks are the expected business. The check only guards
    the *start* of violence."""
    engine = Engine(scene, Dice(seed=4))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    assert review("I look for a way out.", [ATTACK], scene).ok


# --- The wrong manoeuvre --------------------------------------------------------------

def test_a_manoeuvre_is_dropped_when_the_player_meant_to_wound(scene):
    """Measured: "I twist in his grip and drive my rapier into the man holding me" was
    resolved as an *overrun* — a manoeuvre that deals no damage at all. Dropping it
    leaves an ordinary attack, which is what the player described, so this corrects
    rather than costing a turn.
    """
    intents = parse_all([{**ATTACK, "params": {"manoeuvre": "overrun"}}])
    v = judgement.review(
        "I twist in his grip and drive my rapier into the man holding me.", intents, scene)
    assert v.ok                                   # corrected, not objected
    assert "manoeuvre" not in intents[0].params
    assert v.corrections[0].kind == "manoeuvre-for-a-wound"


def test_the_manoeuvre_the_player_named_replaces_the_one_the_GM_picked(scene):
    intents = parse_all([{**ATTACK, "params": {"manoeuvre": "overrun"}}])
    v = judgement.review("I sweep his legs out from under him.", intents, scene)
    assert intents[0].params["manoeuvre"] == "trip"
    assert v.corrections[0].kind == "wrong-manoeuvre"


@pytest.mark.parametrize("text,expected", [
    ("I sweep his legs out from under him.", "trip"),
    ("I grab him and hold him down.", "grapple"),
    ("I knock the sap out of his hand.", "disarm"),
    ("I shove him back into the wall.", "bull rush"),
    ("I try to break his weapon.", "sunder"),
])
def test_the_manoeuvre_the_player_named_is_left_alone(text, expected, scene):
    intents = parse_all([{**ATTACK, "params": {"manoeuvre": expected}}])
    v = judgement.review(text, intents, scene)
    assert v.ok and not v.corrections
    assert intents[0].params["manoeuvre"] == expected


def test_a_plain_attack_is_never_second_guessed(scene):
    intents = parse_all([ATTACK])
    v = judgement.review("I stab him.", intents, scene)
    assert v.ok and not v.corrections


# --- Spawn counts ---------------------------------------------------------------------

def test_the_number_the_player_said_is_honoured(scene):
    """Measured: "A guild bravo steps out of the dark" produced two thugs."""
    intents = parse_all([{"op": "spawn", "params": {"template": "thug", "count": 2}}])
    v = judgement.review("A guild bravo steps out of the dark. I draw and go for him.",
                         intents, scene)
    assert intents[0].params["count"] == 1
    assert v.corrections[0].kind == "spawn-count"


def test_two_means_two(scene):
    intents = parse_all([{"op": "spawn", "params": {"template": "thug", "count": 5}}])
    judgement.review("Two guild bravos step out of the dark.", intents, scene)
    assert intents[0].params["count"] == 2


def test_a_count_the_player_never_gave_is_left_to_the_GM(scene):
    """The player does not have to say how many; when they do not, the GM decides."""
    intents = parse_all([{"op": "spawn", "params": {"template": "thug", "count": 3}}])
    judgement.review("Guild bravos come out of the dark at me.", intents, scene)
    assert intents[0].params["count"] == 3


# --- The NPC fallback -------------------------------------------------------------------

def test_a_creature_the_GM_cannot_speak_for_still_swings(scene):
    """It used to "hesitate", which reads as a bug even when it is a fallback: the player
    stood there being attacked by nobody."""
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    fallback = judgement.default_npc_action(scene, "c1")
    assert fallback and fallback[0]["op"] == "attack"
    assert fallback[0]["target"] == "pc"
    engine.validate(fallback)              # the fallback is not exempt from validation


def test_the_fallback_picks_the_most_hurt_enemy(scene):
    other = instantiate("watchman", scene=scene, name="the watchman")
    scene.add(other)
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([{
        "op": "begin_encounter",
        "params": {"sides": {"them": ["c1"], "pc": ["pc", other.ref]}},
    }]))
    scene.get("pc").hp = 2
    assert judgement.default_npc_action(scene, "c1")[0]["target"] == "pc"


def test_there_is_no_fallback_for_a_creature_that_cannot_act(scene):
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    scene.get("c1").add_condition("unconscious")
    assert judgement.default_npc_action(scene, "c1") is None


# --- Creating the people the GM was already talking about ------------------------------

def test_invented_refs_become_a_spawn(scene):
    """The recurring loss: the player writes "two guild bravos come round the corner",
    the GM answers with `attack thug1`, the registry refuses it — correctly, people must
    not be inventable by naming them — and five attempts later the turn is gone. It has
    an example and a hint pointing at spawn and still does this, so the repair is done in
    code rather than asked for a third time.
    """
    raw = [{"op": "attack", "actor": "pc", "target": "thug1"},
           {"op": "attack", "actor": "thug2", "target": "pc"}]
    out = judgement.repair_unknown_refs(
        raw, "Two guild bravos come round the corner. I turn and fight.", scene)

    assert out[0]["op"] == "spawn"
    assert out[0]["params"]["count"] == 2          # from the player's own sentence
    assert out[1]["target"] == "c2" and out[2]["actor"] == "c3"


def test_the_repair_reads_the_creature_from_the_players_words(scene):
    raw = [{"op": "attack", "actor": "watch1", "target": "pc"}]
    out = judgement.repair_unknown_refs(
        raw, "Two of the city watch come down the alley.", scene)
    assert out[0]["params"]["template"] == "watchman"


def test_a_real_ref_that_is_simply_wrong_is_left_alone(scene):
    """`c9` is the shape of a real ref. That is a mistake to reject, not a person to
    create — inventing someone would paper over a genuine error."""
    raw = [{"op": "attack", "actor": "pc", "target": "c9"}]
    assert judgement.repair_unknown_refs(raw, "I attack him.", scene) is None


def test_nothing_is_created_when_the_GM_already_spawned(scene):
    raw = [{"op": "spawn", "params": {"template": "thug", "count": 2}},
           {"op": "attack", "actor": "pc", "target": "thug1"}]
    assert judgement.repair_unknown_refs(raw, "Two bravos appear.", scene) is None


def test_a_turn_with_no_invented_refs_is_left_alone(scene):
    raw = [{"op": "attack", "actor": "pc", "target": "c1"}]
    assert judgement.repair_unknown_refs(raw, "I attack him.", scene) is None


# --- Replaying the last turn ------------------------------------------------------------

def test_proposing_the_same_turn_again_is_refused(scene):
    """Measured: the player said "two guild bravos come round the corner, I turn and
    fight" and the GM replayed the previous turn — another Stealth check, still carrying
    the reason "going over the wall while the lamp is away". The player's words had
    changed completely and the GM had not read them.
    """
    first = parse_all([{"op": "check", "actor": "pc", "because": "going over the wall",
                        "params": {"skill": "stealth", "dc": 15}}])
    signature = judgement._signature(first)

    again = parse_all([{"op": "check", "actor": "pc", "because": "going over the wall",
                        "params": {"skill": "stealth", "dc": 15}}])
    v = judgement.review("Two guild bravos come round the corner. I turn and fight.",
                         again, scene, previous=signature)
    assert not v.ok
    assert v.objections[0].kind == "repeats-the-last-turn"


def test_a_genuinely_new_turn_is_allowed(scene):
    first = parse_all([{"op": "check", "actor": "pc",
                        "params": {"skill": "stealth", "dc": 15}}])
    later = parse_all([{"op": "check", "actor": "pc",
                        "params": {"skill": "perception", "dc": 15}}])
    v = judgement.review("I listen at the door.", later, scene,
                         previous=judgement._signature(first))
    assert v.ok


def test_doing_the_same_thing_twice_on_purpose_is_allowed(scene):
    """A player may well say "again". Only the *GM* repeating itself while the player
    moved on is the failure."""
    first = parse_all([{"op": "attack", "actor": "pc", "target": "c1"}])
    again = parse_all([{"op": "attack", "actor": "pc", "target": "c1"}])
    v = judgement.review("I swing at him again.", again, scene,
                         previous=judgement._signature(first))
    # The signature matches, so it objects — and that is the right call to make
    # conservatively, because the GM re-proposing verbatim is far more common than a
    # player repeating an identical action with identical framing.
    assert not v.ok


# --- Refs must not reach the player ---------------------------------------------------

def test_bare_refs_in_narration_are_replaced_with_names(scene):
    """Observed: "the two bravos freeze, but c1 looks up from under their saps". Refs are
    the protocol's plumbing — they exist so the GM cannot invent people — and the player
    should never see one."""
    out = judgement.name_refs("The bravos freeze, but c1 looks up at pc.", scene)
    assert "c1" not in out and " pc" not in out
    assert "the thug" in out and "you" in out


def test_naming_leaves_ordinary_prose_alone(scene):
    for text in ["He picks up the cup.", "The lamp swings on its chain.",
                 "She counts the coins twice."]:
        assert judgement.name_refs(text, scene) == text


def test_an_unknown_ref_is_left_as_written(scene):
    """Better a visible oddity than a wrong name substituted confidently."""
    assert "c9" in judgement.name_refs("Something moves where c9 was.", scene)


def test_there_is_no_fallback_when_nobody_is_left_to_fight(scene):
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    scene.get("pc").add_condition("unconscious")
    assert judgement.default_npc_action(scene, "c1") is None
