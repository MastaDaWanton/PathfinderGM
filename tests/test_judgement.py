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
from tests._places import stand_on


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
    "I put my back to the wall and draw.",
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
    ], origin="author:test"))
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

def test_how_many_enemies_there_are_is_the_GMs_to_decide(scene):
    """This once worked the other way round, and that was the boundary backwards.

    An earlier version read a number out of the player's sentence and overrode the GM
    with it — so "a guild bravo steps out of the dark" forced the spawn down to one. But
    the player says what their character *does*; who is round the corner comes from the
    world. `play/player_input.py` now refuses that shape of input outright, and nothing
    here second-guesses the count.
    """
    intents = parse_all([{"op": "spawn", "params": {"template": "thug", "count": 3}}])
    v = judgement.review("I put my back to the wall and draw.", intents, scene)
    assert intents[0].params["count"] == 3
    assert not any(c.kind.startswith("spawn-count") for c in v.corrections)


# --- The NPC fallback -------------------------------------------------------------------

def test_a_creature_the_GM_cannot_speak_for_still_swings(scene):
    """It used to "hesitate", which reads as a bug even when it is a fallback: the player
    stood there being attacked by nobody."""
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ], origin="author:test"))
    fallback = judgement.default_npc_action(scene, "c1")
    assert fallback and fallback[0]["op"] == "attack"
    assert fallback[0]["target"] == "pc"
    engine.validate(fallback, origin="author:test")              # the fallback is not exempt from validation


def test_the_fallback_picks_the_most_hurt_enemy(scene):
    other = instantiate("watchman", scene=scene, name="the watchman")
    scene.add(other)
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([{
        "op": "begin_encounter",
        "params": {"sides": {"them": ["c1"], "pc": ["pc", other.ref]}},
    }], origin="author:test"))
    scene.get("pc").hp = 2
    assert judgement.default_npc_action(scene, "c1")[0]["target"] == "pc"


def test_there_is_no_fallback_for_a_creature_that_cannot_act(scene):
    engine = Engine(scene, Dice(seed=8))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ], origin="author:test"))
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
        raw, "I put my back to the wall and draw.", scene)

    assert out[0]["op"] == "spawn"
    # Two, because the GM named two — not because the player said a number. How many
    # enemies there are is the GM's to decide.
    assert out[0]["params"]["count"] == 2
    assert out[1]["target"] == "c2" and out[2]["actor"] == "c3"


def test_the_repair_reaches_opposed_by_as_well(scene):
    """A turn was lost to `opposed_by: {ref: "thug1"}` while only actor and target were
    being repaired — the ref registry refuses every place a ref can appear, so the repair
    has to reach every one of them too."""
    raw = [{"op": "check", "actor": "pc",
            "params": {"skill": "stealth",
                       "opposed_by": {"ref": "thug1", "skill": "perception"}}}]
    out = judgement.repair_unknown_refs(raw, "I keep to the shadows.", scene)
    assert out[0]["op"] == "spawn"
    assert out[1]["params"]["opposed_by"]["ref"] == "c2"


def test_the_repair_reads_the_creature_from_the_players_words(scene):
    raw = [{"op": "attack", "actor": "watch1", "target": "pc"}]
    out = judgement.repair_unknown_refs(
        raw, "I back away from the watchman coming down the alley.", scene)
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
    v = judgement.review("I spin round and go for whoever is behind me.",
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
    ], origin="author:test"))
    scene.get("pc").add_condition("unconscious")
    assert judgement.default_npc_action(scene, "c1") is None


# --- the attack that landed on the wrong body (playtest, 2026-08-22) ----------------------

@pytest.fixture
def stale_scene():
    """The exact shape the playtest produced: the PC, and one NPC dying at 0 hp who was
    dragged along from a previous scene. Nobody else exists, whatever the fiction says."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    gatekeeper = instantiate("guildhand", scene=s, name="the guildhand on the gate")
    gatekeeper.hp = 0
    s.add(gatekeeper)
    return s


def test_a_dying_man_is_not_the_obvious_target(stale_scene):
    """Verbatim from the playtest: every attack on the people the narration described was
    filled onto the gatekeeper dying at 0 hp, because he was the only body in the room.
    Being the only body must not make a bleeding man the reading of "I attack"."""
    raw = [{"op": "attack", "actor": "pc"}]
    assert judgement.fill_obvious_targets(raw, stale_scene)[0].get("target") is None


def test_a_conscious_thug_still_is(scene):
    raw = [{"op": "attack", "actor": "pc"}]
    assert judgement.fill_obvious_targets(raw, scene)[0]["target"] == "c1"


def test_an_attack_on_somebody_who_does_not_exist_creates_them(stale_scene):
    """The playtest turn, replayed: the narration had introduced a winged woman, she was
    never spawned, the player wrote "I rush the winged woman and run her through", and
    the GM answered `attack c1` — a valid ref belonging to the dying gatekeeper three
    scenes away. Every check passed and the wrong man was stabbed to -4."""
    raw = [{"op": "attack", "actor": "pc", "target": "c1"}]
    amended = judgement.repair_misaimed_attack(
        raw, "I don't trust her. I rush the winged woman and run her through.",
        stale_scene)
    assert amended is not None
    assert amended[0]["op"] == "spawn"
    assert amended[0]["params"]["name"] == "winged woman"
    assert amended[1]["op"] == "attack"
    assert amended[1]["target"] == "c2"          # the ref the spawn will mint


def test_naming_the_actual_target_repairs_nothing(scene):
    raw = [{"op": "attack", "actor": "pc", "target": "c1"}]
    assert judgement.repair_misaimed_attack(
        raw, "I attack the thug before he can move.", scene) is None


def test_a_pronoun_repairs_nothing(stale_scene):
    """"I attack him" names nobody, so there is no disagreement to detect — and spawning
    a creature called "him" would be worse than the misaim."""
    raw = [{"op": "attack", "actor": "pc", "target": "c1"}]
    assert judgement.repair_misaimed_attack(raw, "I attack him now.", stale_scene) is None


def test_the_spawned_victim_survives_validation(stale_scene):
    """The repair's output must pass the engine's own checks, projected ref and all —
    otherwise the repair is a different way of losing the turn."""
    raw = [{"op": "attack", "actor": "pc", "target": "c1"}]
    amended = judgement.repair_misaimed_attack(
        raw, "I charge the winged woman.", stale_scene)
    engine = Engine(stale_scene, Dice(seed=7))
    intents = engine.validate(amended, origin="author:test")
    assert [i.op for i in intents] == ["spawn", "attack"]


def test_the_template_follows_the_players_wording(stale_scene):
    amended = judgement.repair_misaimed_attack(
        [{"op": "attack", "actor": "pc", "target": "c1"}],
        "I rush the guard dog and stab it.", stale_scene)
    assert amended[0]["params"]["template"] == "guard dog"


# --- sleep and meals declared at the table (playtest, 2026-08-22) --------------------------

def test_a_declared_sleep_becomes_a_rest_intent(scene):
    """Measured in both sessions: "I sleep until morning" charged 20 minutes in one and
    nothing in the other. The prompt carries a worked rest example and a briefing line;
    both models ignored both. So the declaration is detected mechanically."""
    out = judgement.inject_survival(
        [{"op": "narrate_only"}], "I bed down by the embers and sleep until dawn.", scene)
    assert {"op", "actor", "params"} <= set(out[-1])
    assert out[-1]["op"] == "rest" and out[-1]["params"]["kind"] == "night"


def test_eating_and_drinking_reach_the_engine(scene):
    out = judgement.inject_survival(
        [{"op": "narrate_only"}],
        "I eat from my rations and drink from my waterskin.", scene)
    ops = [r["op"] for r in out]
    assert "eat" in ops and "drink" in ops


def test_a_question_about_sleep_is_not_sleeping(scene):
    out = judgement.inject_survival(
        [{"op": "narrate_only"}], "Should I sleep here, or is it too exposed?", scene)
    assert [r["op"] for r in out] == ["narrate_only"]


def test_a_refusal_to_sleep_is_not_sleeping(scene):
    out = judgement.inject_survival(
        [{"op": "narrate_only"}], "No sleep tonight - I keep watch.", scene)
    assert "rest" not in [r["op"] for r in out]


def test_making_camp_alone_is_not_sleeping(scene):
    """The playtest's own player made camp and then scouted for an hour. Camp is where
    you sleep, not the sleeping."""
    out = judgement.inject_survival(
        [{"op": "narrate_only"}], "I make a small camp off the trail.", scene)
    assert "rest" not in [r["op"] for r in out]


def test_a_rest_the_model_proposed_is_not_doubled(scene):
    out = judgement.inject_survival(
        [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}],
        "I go to sleep.", scene)
    assert [r["op"] for r in out].count("rest") == 1


def test_an_untargeted_attack_on_a_named_stranger_creates_them(scene):
    """Found in the confirmation session, live: "I rush the careful walker, blade out"
    came back as an attack with no target at all. The misaim repair declined it — it only
    read targeted attacks — and `fill_obvious_targets` then handed the blow to the only
    body in the yard, all over again. An attack with nobody on it, on a turn where the
    player named somebody who does not exist, is aimed at that somebody."""
    amended = judgement.repair_misaimed_attack(
        [{"op": "attack", "actor": "pc"}],
        "I spin and rush the careful walker, blade out.", scene)
    assert amended is not None
    assert amended[0]["op"] == "spawn"
    assert amended[0]["params"]["name"] == "careful walker"
    assert amended[1]["target"] == "c2"


def test_an_untargeted_attack_with_no_named_victim_is_left_for_the_fill(scene):
    """"I attack" names nobody; the lone-conscious-candidate fill is the right reading
    there, and the misaim repair must stay out of its way."""
    assert judgement.repair_misaimed_attack(
        [{"op": "attack", "actor": "pc"}], "I attack!", scene) is None


def test_a_declared_journey_moves_the_engines_ground(scene):
    """Playtest finding 8, reproduced verbatim in the confirmation session: "I head out
    the gates for the treeline" was narrated as a whole journey and arrived as
    narrate_only — the biome stayed urban, the forage tables were wrong, and the city
    gatekeeper was still in the scene because travel is the transition and never fired."""
    stand_on(scene, "urban")
    out = judgement.inject_travel(
        [{"op": "narrate_only"}],
        "I head out the gates for the treeline before this city causes me more trouble.",
        scene)
    assert out[-1]["op"] == "travel"
    assert out[-1]["params"]["biome"] == "forest"


def test_mentioning_ground_without_going_there_travels_nowhere(scene):
    stand_on(scene, "urban")
    for text in ("I like these woods.", "Should we head into the woods?",
                 "I walk across the yard to the gate."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert all(r.get("op") != "travel" for r in out), text


def test_travelling_to_the_ground_underfoot_is_not_a_transition(scene):
    stand_on(scene, "forest")
    out = judgement.inject_travel(
        [{"op": "narrate_only"}], "I head deeper into the forest.", scene)
    assert all(r.get("op") != "travel" for r in out)


def test_ground_the_narrator_names_but_the_list_did_not(scene):
    """Measured in live play, one turn after leaving the market: "I leave the step and
    walk out past the edge of Zhilvarnia into the open scrub" matched `_DEPARTS` cleanly
    and then found no ground word at all, because "scrub" was not among them.

    So the party stayed in `urban` while the narrator wrote dry underbrush and a sun
    overhead, the market stranger walked out into the wilderness alongside them, and
    every biome-gated excursion stayed locked on ground nobody was standing on any more.
    The same law as the outcome-claim verbs: each session reaches for a noun the list
    does not have, and the list is what has to grow."""
    stand_on(scene, "urban")
    said = ("I leave the step and walk out past the edge of Zhilvarnia into the open "
            "scrub, looking for something dangerous to fight.")
    out = judgement.inject_travel([{"op": "narrate_only"}], said, scene)
    assert out[-1]["op"] == "travel"
    assert out[-1]["params"]["biome"] == "grassland"

    for text, biome in (("I head out to the heath before dark.", "grassland"),
                        ("We ride for the badlands.", "desert"),
                        ("I make my way down to the shoreline.", "coast"),
                        ("I set out for the foothills.", "hills"),
                        ("I go down to the catacombs.", "underground")):
        got = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert got[-1].get("op") == "travel", text
        assert got[-1]["params"]["biome"] == biome, text


def test_a_word_that_is_only_sometimes_ground_does_not_move_anybody(scene):
    """A false travel is far worse than a missed one — it teleports the party
    mid-sentence and sheds whoever was talking to them. So bare "brush", "wood" and
    "mine" stay out of the list: brushing past a guard, a wooden door and a sword that
    is mine are all commoner than the terrain reading."""
    stand_on(scene, "urban")
    for text in ("I brush past the guard and keep going.",
                 "I pull the wooden door to and bar it.",
                 "The sword is mine, and I take it to the table."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert all(r.get("op") != "travel" for r in out), text


def test_going_home_is_a_journey_too(scene):
    """"Return to Zhilvarnia" is one of the app's own suggestion chips, and none of the
    ways of saying it were in `_DEPARTS`: return, turn back, double back, retrace. Going
    home is as common a move as setting out, and the safety net had no word for it."""
    stand_on(scene, "grassland")
    for text, biome in (("I return to the city.", "urban"),
                        ("I turn back towards the city walls.", "urban"),
                        ("I double back to the forest.", "forest"),
                        ("I retrace my steps to the coast.", "coast")):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert out[-1].get("op") == "travel", text
        assert out[-1]["params"]["biome"] == biome, text


def test_returning_something_to_somebody_is_not_a_journey(scene):
    """The ground noun is what keeps the new verbs honest: handing a sword back names
    no terrain, so nobody travels."""
    stand_on(scene, "grassland")
    for text in ("I return the sword to him.", "I turn back to face him.",
                 "I give the coin to the boy."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert all(r.get("op") != "travel" for r in out), text


def _pangrella():
    from world import loader
    return loader.load("fixtures/pangrella-campaign.json")


def test_a_place_with_a_name_is_a_destination(scene):
    """The ground-noun list can only hold terrain words, and the commonest way of saying
    where you are going is to name the place — "Return to Zhilvarnia" is one of the app's
    own suggestion chips. Matched against the world's real settlements rather than a
    pattern, the same "ground every name" rule the invented-name check works by.

    This began to matter when a market started requiring urban ground underfoot: leave
    town, come back by naming the town, and without this the biome stays out in the
    grass and every stall in the city is shut."""
    world = _pangrella()
    stand_on(scene, "grassland")
    for text in ("Return to Zhilvarnia.", "I head back to Zhilvarnia.",
                 "I walk to Mirabalos.", "I set out for Torvathys."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene, world)
        assert out[-1].get("op") == "travel", text
        assert out[-1]["params"]["biome"] == "urban", text


def test_already_in_the_town_you_named_is_not_a_journey(scene):
    stand_on(scene, "urban")
    out = judgement.inject_travel(
        [{"op": "narrate_only"}], "Return to Zhilvarnia.", scene, _pangrella())
    assert all(r.get("op") != "travel" for r in out)


def test_talking_about_a_journey_is_not_taking_one(scene):
    """"I think about going to Zhilvarnia one day" has a movement verb, a preposition and
    a real city in it, and the party must not be somewhere else by the end of the
    sentence. The hole was there for terrain too — this closes both."""
    world = _pangrella()
    stand_on(scene, "grassland")
    for text in ("I think about going to Zhilvarnia one day.",
                 "I wonder whether to head for the woods.",
                 "I ask the guard about going to Torvathys.",
                 "I talk about heading into the hills."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene, world)
        assert all(r.get("op") != "travel" for r in out), text


def _empty_room():
    from rules.engine import Scene
    from rules.sheet import load_pc
    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene


def test_a_fight_the_player_starts_actually_starts(scene):
    """Measured in live play, four turns in a row with `outcomes: []`. "I shoulder my way
    into the worst tavern on the street and pick a fight with the biggest bruiser in the
    room" came back as a paragraph about a hulking mass of muscle and tattoos, no actor
    in the scene and no encounter. The GM has a spawn op, a begin_encounter op, a worked
    example of both and a briefing line, and narrated the fight instead of proposing it.

    Same defence as `repair_unknown_refs`: the player is not deciding who exists, they
    are declaring what they do, and the world owes them an opponent."""
    for text in ("I shoulder my way into the tavern and pick a fight with the bruiser.",
                 "I attack the man at the bar.", "I punch him.",
                 "I take a swing at the nearest drunk.", "We charge the camp.",
                 # The app writes its own suggestion chips as imperatives, and they
                 # arrive in the box verbatim when clicked. The chip under the tavern
                 # scene read exactly this, and a rule demanding "I" ignored the app's
                 # own offer to start the fight.
                 "Just start swinging at him", "Attack the watchman.",
                 "Start swinging."):
        out = judgement.inject_fight([{"op": "narrate_only"}], text, _empty_room())
        ops = [i.get("op") for i in out]
        assert "spawn" in ops and "begin_encounter" in ops, text


def test_an_idiom_does_not_conjure_a_thug(scene):
    """Each of these is a sentence a player will type, and each would otherwise create a
    creature and roll initiative. Kept per verb: written as one shared noun list, "We
    charge the camp" stopped being a fight because "camp" was there for "strike camp"."""
    for text in ("I hit the road at first light.", "I strike a match.", "I strike camp.",
                 "I jump the queue.", "I attack the problem from another angle.",
                 "I shove the door open.", "I charge the toll and let him pass.",
                 "Should I attack him?", "I think about attacking him."):
        out = judgement.inject_fight([{"op": "narrate_only"}], text, _empty_room())
        assert all(i.get("op") != "spawn" for i in out), text


def test_being_attacked_is_not_attacking(scene):
    """"The thug attacks me" has a violence verb and a first-person pronoun in it and is
    a report of being hit. Co-occurrence is not enough — the pronoun has to come before
    the verb with no other subject between them."""
    for text in ("The thug attacks me.", "I watch as the thug attacks me.",
                 "He punches me in the ribs.", "They start fighting each other."):
        out = judgement.inject_fight([{"op": "narrate_only"}], text, _empty_room())
        assert all(i.get("op") != "spawn" for i in out), text


def test_swinging_at_somebody_already_there_rolls_an_attack():
    """This test used to assert the opposite — that an enemy already in the scene was
    "left to `fill_obvious_targets`" — and play disproved it within the hour.

    `fill_obvious_targets` puts a target on an attack that already exists, and the whole
    problem is that no attack was proposed at all. Measured in the tavern at round 2,
    three turns running: the encounter was live, the player typed "I punch the bruiser
    in the face", the narration described the punch landing, and the turn log read
    `outcomes: []`. No attack roll, nothing in the roll tracker, and the only hit points
    that moved were the player's when the thug swung back.

    So a declared attack on somebody standing there becomes an attack intent, and a
    second opponent is never spawned."""
    from rules.bestiary import instantiate
    room = _empty_room()
    room.add(instantiate("thug", scene=room, name="a thug"))
    out = judgement.inject_fight([{"op": "narrate_only"}], "I attack the thug.", room)
    ops = [i["op"] for i in out]
    assert "attack" in ops, ops
    assert "spawn" not in ops, "a second opponent was conjured"
    hit = next(i for i in out if i["op"] == "attack")
    assert hit["target"] == "c1" and hit["actor"] == "pc"


def test_a_brawl_opens_within_reach_and_rolls_the_first_punch():
    """Reported from play: "thug is still 15ft away from you and no rolls have been
    tracked in the roll tracker".

    Two causes, both here. `begin_encounter` lays an unplaced combatant out by zone and
    everything spawned defaulted to `near`, which is three squares — fifteen feet, out
    of reach of the punch that started the fight. And starting the fight proposed no
    attack, so nothing was ever rolled: the roll tracker was empty because there was no
    roll, not because it failed to display one."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    raw = judgement.inject_fight([], "I punch the bruiser in the face.", scene)
    assert [i["op"] for i in raw] == ["spawn", "begin_encounter", "attack"]

    engine = Engine(scene, Dice(seed=5))
    res = engine.run(engine.validate(raw, origin="author:test"))
    assert scene.zones["c1"] == "engaged"
    assert scene.distance_between("pc", "c1") == 5, "not within reach of a punch"
    # The swing itself is DEFERRED now, not rolled: a battle that begins and resolves
    # inside one spoken paragraph was the 2026-08-27 playtest's finding (a spawned
    # thug fought, killed and paid out without the combat panel ever appearing). The
    # encounter stands, the tell announces it, and the first blow is the player's to
    # declare at the panel.
    assert scene.in_encounter and scene.grid is not None
    assert not scene.awaiting
    assert any("Battle is joined" in (o.tell or "") for o in res.outcomes)
    assert all(e.get("kind") != "damage" for o in res.outcomes for e in o.effects)


def test_engaged_is_closer_than_near():
    """`away = 3 if zone == "near" else 8` put the one zone that means "close enough to
    hit" further away than "near" — eight squares, forty feet, across the room."""
    from rules.engine import SQUARES_BY_ZONE

    assert SQUARES_BY_ZONE["engaged"] < SQUARES_BY_ZONE["near"] < SQUARES_BY_ZONE["far"]
    assert SQUARES_BY_ZONE["engaged"] == 1


def test_a_thrown_weapon_opens_at_a_throwing_distance():
    """Asked during play: "what if i throw something, am i going to start at the correct
    range". Two bugs behind it. "throw" was not in the violence list at all, so throwing
    a knife started no fight; and once it did, `inject_fight` hardcoded `engaged`, which
    is the one range a thrown dagger is not for."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    def opens_at(said):
        scene = Scene()
        scene.add(load_pc("fixtures/pc-kesst.json"))
        raw = judgement.inject_fight([], said, scene)
        assert any(i["op"] == "spawn" for i in raw), f"no fight started: {said}"
        engine = Engine(scene, Dice(seed=5))
        engine.run(engine.validate(raw, origin="author:test"))
        return scene.distance_between("pc", "c1")

    # Each opens at its own range now rather than one generic fifteen feet: the weapon
    # named in the sentence decides, and a stated distance beats the weapon.
    for said, feet in (("I throw my dagger at him.", 10),
                       ("I hurl a bottle at the bruiser.", 10),
                       ("I shoot him with my crossbow.", 80),
                       ("I sling a stone at it.", 50)):
        assert opens_at(said) == feet, said
    # A ranged verb with no weapon named still opens with ground between you.
    assert opens_at("I loose an arrow at the watchman.") >= 15
    for said in ("I punch the bruiser in the face.", "I charge him."):
        assert opens_at(said) == 5, said


def _opens_at(said):
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    raw = judgement.inject_fight([], said, scene)
    assert any(i["op"] == "spawn" for i in raw), f"no fight started: {said}"
    engine = Engine(scene, Dice(seed=5))
    engine.run(engine.validate(raw, origin="author:test"))
    return scene.distance_between("pc", "c1"), scene.grid.width


def test_a_distance_the_player_stated_is_the_distance():
    """Asked during play: "what if i shoot someone with a bow at 120ft". It opened at
    forty — the `far` default — because a zone word has no way to say anything past
    `far`, and `begin_encounter` builds the grid *after* `spawn` runs, so the spawn could
    not place anybody and its distance was simply dropped."""
    assert _opens_at("I shoot him with my bow at 120 feet.")[0] == 120
    assert _opens_at("I loose an arrow at the watchman from 200 ft.")[0] == 200
    assert _opens_at("I shoot at him from 40 yards.")[0] == 120       # yards are tripled


def test_the_board_grows_to_hold_a_bowshot():
    """The default map is 20x20 — a hundred feet square — and a bowshot is not. Clamping
    put the target at the edge of the map and called it a hundred feet, which is a
    different fight from the one the player described."""
    feet, width = _opens_at("I loose an arrow at the watchman from 200 ft.")
    assert feet == 200
    assert width * 5 >= 200, f"the board is only {width * 5} feet across"


def test_a_named_weapon_opens_at_its_own_range():
    """No distance stated, so the weapon decides. The weapons table carries `crit_range`
    and no range increment at all, so these are the Core Rulebook's."""
    assert _opens_at("I shoot him with my longbow.")[0] == 100
    assert _opens_at("I shoot him with my crossbow.")[0] == 80
    assert _opens_at("I throw my dagger at him.")[0] == 10
    assert _opens_at("I punch the bruiser in the face.")[0] == 5


def test_swinging_when_everyone_is_down_ends_the_fight():
    """Found by `tools/narrator_audit.py` on its sixth turn: "I keep hitting him" scored
    `combat-turn-did-nothing`, because the thug was already down and the encounter had
    not closed, so the turn contained nothing at all.

    Saying the fight is over is the one thing that pays: XP and treasure settle on the
    way *out* of an encounter. Spawning fresh reinforcements instead would be inventing
    an enemy the GM never called for."""
    from rules.bestiary import instantiate

    room = _empty_room()
    thug = instantiate("thug", scene=room, name="a thug")
    thug.hp = -3
    room.add(thug)
    # `in_encounter` is derived from the initiative order, so the fight is begun rather
    # than asserted.
    room.initiative = [("pc", 15), ("c1", 9)]
    room.turn = 0
    out = judgement.inject_fight([{"op": "narrate_only"}], "I keep hitting him.", room)
    ops = [i["op"] for i in out]
    assert "end_encounter" in ops, ops
    assert "spawn" not in ops, "reinforcements nobody called for"


def test_a_turn_that_fails_every_attempt_degrades_to_narration():
    """Twice-measured path. First: the error report itself crashed (schedule
    unpacked as a pair). Then the honest error turned out to be the wrong answer
    anyway — seven failed attempts put a wall of red where a turn should have
    been, and the player ruled: "i should get a narrated text like 'you look for
    a group of guards to fight but none seem to be around'." The exhaustion path
    now returns a narrate_only TurnPlan with an honest sentence; it never raises."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "gm" / "agent.py").read_text(
        encoding="utf-8")
    tail = src[src.index("Every attempt failed"):][:900]
    assert "return TurnPlan" in tail
    assert "narrate_only" in tail
    assert "raise IntentError" not in tail


# --- a trade aimed at nobody --------------------------------------------------------------

def test_a_sale_to_a_merchant_who_is_not_there_is_dropped_not_fatal():
    """Measured in the adversarial audit: "I sell my legendary artifact collection to
    the nearest merchant for a million gold" became `sell` to a ref called
    'the merchant', the refs check refused it seven times across two models, and the
    turn died as a 502. Spawning a merchant would be inventing people; losing the turn
    was the only other path. Now the sale is dropped and the turn survives."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))

    raw = [{"op": "narrate_only", "actor": "pc", "params": {},
            "because": "she tries her luck"},
           {"op": "sell", "actor": "pc", "params": {"item": "anything",
                                                    "to": "the merchant"},
            "because": "selling to the merchant"}]
    amended = judgement.drop_unfulfillable_trades(raw, scene)
    assert [r["op"] for r in amended] == ["narrate_only"]

    # Alone, the drop leaves a narrate_only so the turn still validates.
    only = [{"op": "sell", "actor": "pc",
             "params": {"item": "x", "to": "nobody-here"}, "because": "x"}]
    amended = judgement.drop_unfulfillable_trades(only, scene)
    assert [r["op"] for r in amended] == ["narrate_only"]
    Engine(scene, Dice(seed=3)).validate(amended, origin="author:test")   # must not raise

    # A sale to somebody actually present is not this function's business.
    from rules.sheet import from_dict
    scene.add(from_dict({"name": "the stallholder", "kind": "npc",
                         "hp": 4, "hp_max": 4, "level": 1,
                         "class": ""}, ref="c1"))
    fine = [{"op": "sell", "actor": "pc", "params": {"item": "x", "to": "c1"},
             "because": "x"}]
    assert judgement.drop_unfulfillable_trades(fine, scene) is None


def test_a_check_opposed_by_a_ghost_rolls_against_the_ground_instead():
    """The pickpocket variant of the same death: Sleight of Hand `opposed_by` a ref
    that does not exist. The check is the player's own action, so it survives — moved
    onto a flat DC, because the person the GM imagined resisting is not there to
    resist."""
    from rules.engine import Scene
    from rules.sheet import load_pc

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    raw = [{"op": "check", "actor": "pc",
            "params": {"skill": "sleight of hand",
                       "opposed_by": {"ref": "the first person", "skill":
                                      "perception"}},
            "because": "picking a pocket"}]
    amended = judgement.drop_unfulfillable_trades(raw, scene)
    assert amended is not None
    p = amended[0]["params"]
    assert "opposed_by" not in p
    assert p["dc"] == {"band": "average"}



def test_a_bare_check_is_given_the_average_band_not_five_rejections():
    """`inject_checks` left its DC "to the engine's own default band" — a default that
    does not exist: validation refuses a check with neither dc nor opposed_by. Every
    injected check and every bare model check paid a retry to learn the correction,
    and on the 60-turn audit four turns (climb, track, search — check verbs all) never
    recovered. The band is a fact to fill, not a thing to ask a model to remember."""
    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    eng = Engine(scene, Dice(seed=3))

    raw = judgement.fill_bare_checks([
        {"op": "check", "actor": "pc", "params": {"skill": "climb"},
         "because": "the rise is steep"}])
    assert raw[0]["params"]["dc"] == {"band": "average"}
    assert [i.op for i in eng.validate(raw, origin="author:test")] == ["check"]

    # A check that already knows what it is up against is not touched.
    keep_dc = [{"op": "check", "actor": "pc",
                "params": {"skill": "climb", "dc": {"band": "tough"}},
                "because": "x"}]
    assert judgement.fill_bare_checks(keep_dc)[0]["params"]["dc"] == {"band": "tough"}
    opposed = [{"op": "check", "actor": "pc",
                "params": {"skill": "stealth",
                           "opposed_by": {"ref": "pc", "skill": "perception"}},
                "because": "x"}]
    assert "dc" not in judgement.fill_bare_checks(opposed)[0]["params"]

    # And the whole chain agrees: an injected check comes out the far end legal.
    chained = judgement.inject_checks(
        [{"op": "narrate_only", "actor": "pc", "params": {}, "because": "x"}],
        "I climb the nearest rise to see further.", scene)
    chained = judgement.fill_bare_checks(chained)
    assert [i.op for i in eng.validate(chained, origin="author:test")] == ["narrate_only", "check"]



def test_a_bent_attack_is_straightened_not_refused_seven_times():
    """Measured live: "I attack the closest person" died in SEVEN attempts across two
    models — target pocketed in params (the schema refuses unknown params), an
    invented `action` param, and a weapon name filed as a manoeuvre. Every one is
    information in the wrong pocket, movable in code."""
    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    thug = instantiate("thug", scene=scene, name="the thug")
    scene.add(thug)

    raw = [{"op": "attack", "actor": "pc",
            "params": {"target": thug.ref, "action": "full_attack",
                       "manoeuvre": "armed punch"},
            "because": "she swings"}]
    fixed = judgement.normalize_attacks(raw, scene)
    assert fixed is not None
    a = fixed[0]
    assert a["target"] == thug.ref
    assert "target" not in a["params"] and "action" not in a["params"]
    assert "manoeuvre" not in a["params"]
    assert a["params"]["weapon"] == "armed punch"

    # A real manoeuvre and a clean shape are not this function's business.
    fine = [{"op": "attack", "actor": "pc", "target": thug.ref,
             "params": {"manoeuvre": "trip"}, "because": "x"}]
    assert judgement.normalize_attacks(fine, scene) is None



def test_the_gm_cannot_end_the_fight_it_is_starting():
    """Read out of a live save's turn log: ['attack', 'end_encounter'] on turn after
    turn — the model closed every fight in the same breath it opened one, and the
    combat bar never appeared across a session of swinging. Travelling with an attack
    or spawn, end_encounter is stripped; alone (a surrender), it survives."""
    from gm import judgement

    swung = [{"op": "attack", "actor": "pc", "target": "c1", "params": {}},
             {"op": "end_encounter", "params": {}}]
    assert [r["op"] for r in judgement.drop_premature_end(swung)] == ["attack"]
    talked = [{"op": "end_encounter", "params": {}}]
    assert judgement.drop_premature_end(talked) == talked



def test_an_attack_on_a_corpse_spawns_the_fight_the_fiction_describes():
    """Live save: both refs were corpses, the prose had guardsmen for three turns, and
    every swing was aimed at a body — one living combatant, so no encounter could
    form and the combat bar never appeared. When the player's words name opposition,
    the attack gets a real target; a swing at the corpse with no such words stands."""
    from gm import judgement
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    body = instantiate("thug", scene=scene, name="the stranger")
    scene.add(body)
    body.hp = -9

    raw = [{"op": "attack", "actor": "pc", "target": body.ref, "params": {},
            "because": "swinging"}]
    fixed = judgement.redirect_attacks_off_corpses(
        raw, "i charge at them and punch the closest guard", scene)
    assert fixed is not None
    # A Guard out of the corpus since 2026-09-19, not the hand-written 11-hp watchman:
    # `judgement.template_for` asks `npcs.choose` first and takes its pick when the block
    # IS the role word (item 30). The watchman remains the floor for guard-shaped words the
    # corpus has no block for.
    assert fixed[0]["op"] == "spawn" and fixed[0]["params"]["template"] == "guard"
    assert fixed[1]["target"] not in (body.ref,)

    # No opposition named: kicking the fallen is a thing a player may mean.
    assert judgement.redirect_attacks_off_corpses(
        raw, "I kick him while he is down", scene) is None



def test_an_attack_on_a_corpse_does_not_satisfy_the_fight_the_player_wants():
    """Live: "I attack it" — a well-creature the prose had described for two turns —
    arrived as an attack on a long-dead ref. inject_fight read "attack", stood aside,
    and the player swung at a body while the monster existed only in sentences. An
    attack aimed at the dead means the fight still needs making."""
    from gm import judgement
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    corpse = instantiate("thug", scene=scene, name="the stranger")
    scene.add(corpse)
    corpse.hp = -9

    raw = [{"op": "attack", "actor": "pc", "target": corpse.ref, "params": {},
            "because": "swinging"}]
    out = judgement.inject_fight(raw, "I attack it", scene)
    ops = [r["op"] for r in out]
    assert "spawn" in ops, ops

    # A living target: the guard holds, no second fight is made.
    corpse.hp = 9
    assert judgement.inject_fight(raw, "I attack it", scene) == raw


def test_a_group_in_the_players_sentence_spawns_a_group():
    """Measured live: "I move towards the group of guards and clansmen and get ready
    to fight" spawned exactly one watchman, and the player fought the crowd one man
    at a time, fight after fight, because inject_fight hard-coded count=1."""
    out = judgement.inject_fight(
        [{"op": "narrate_only"}],
        "I move towards the group of guards and clansmen and get ready to fight",
        _empty_room())
    spawn = next(i for i in out if i.get("op") == "spawn")
    enc = next(i for i in out if i.get("op") == "begin_encounter")
    assert spawn["params"]["count"] == 4
    assert len(enc["params"]["sides"]["them"]) == 4
    atk = next(i for i in out if i.get("op") == "attack")
    assert atk["target"] == enc["params"]["sides"]["them"][0]


def test_opponent_count_reads_the_players_own_words():
    """A stated number is honoured in full — the player's own ruling: "if i run
    into a deadly situation I should have to reap what I've sown." A collective
    noun means four, a bare plural three, a lone man one. No cap: death is
    survivable by design (the patron pays for the raising), so the injector owes
    the player the fight they picked."""
    cases = (("I attack the two bravos", 2), ("I fight both of them", 2),
             ("I charge the gang", 4), ("I swing at the man", 1),
             ("I attack all 10 wolves", 10), ("I punch him", 1),
             ("I take on the whole dozen", 12))
    for text, want in cases:
        assert judgement.opponent_count(text) == want, text


def test_press_the_death_writes_the_kill_the_prose_flinched_from():
    """Measured live: a watchman at -21 of 11 hit points was narrated as "his eyes
    widen in shock as he struggles to catch his breath". The pass appends an
    authored death scaled by overkill, and leaves prose alone that already kills."""
    from gm import narration

    flinched = ("His eyes widen in shock as he struggles to catch his breath, "
                "clutching at his battered armor.")
    out, added = narration.press_the_death(
        flinched, [{"name": "the watchman", "margin": 10, "hp_max": 11,
                    "subj": "he", "obj": "him", "poss": "his"}])
    assert added == ["the watchman"]
    assert "dead" in out

    # The top rung used to be ONE sentence — "…as unmake him…" — and the player quoted
    # it back as the narrator's tic (docs/narrator-guards.md). Now it is a pool chosen
    # by the blow's axes, and that word is gone from it.
    gore, _ = narration.press_the_death(
        "", [{"name": "the thug", "margin": 30, "hp_max": 13,
              "subj": "he", "obj": "him", "poss": "his"}])
    assert "dead" in gore and "unmake" not in gore

    already = "The watchman drops, dead before he hits the boards."
    same, added = narration.press_the_death(
        already, [{"name": "the watchman", "margin": 2, "hp_max": 11}])
    assert same == already and not added


def test_press_the_death_slips_in_before_the_hand_back():
    from gm import narration

    out, _ = narration.press_the_death(
        "Your fist lands with a crack. What do you do next?",
        [{"name": "the thug", "margin": 1, "hp_max": 13}])
    assert out.endswith("What do you do next?")
    assert "dead" in out


def test_a_pair_of_guards_is_two_guards():
    """Measured live: the scene panel showed a single 11-hp actor named "pair of
    guards" holding a doorway two men wide. A collective name entering the spawn op
    splits into its count and its singular at the one chokepoint every creature
    arrives by."""
    from rules.bestiary import split_collective_name
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    assert split_collective_name("pair of guards") == (2, "guard")
    assert split_collective_name("a group of clansmen") == (4, "clansman")
    assert split_collective_name("three wolves") == (1, "three wolves")  # no "of"
    assert split_collective_name("pack of wolves") == (4, "wolf")
    assert split_collective_name("the watchman") == (1, "the watchman")

    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=2))
    out = e.run(e.validate([{"op": "spawn", "because": "t",
                             "params": {"template": "watchman",
                                        "name": "pair of guards"}}], origin="author:test")).outcomes[0]
    made = out.effects[0]["actors"]
    assert len(made) == 2
    assert all(m["name"] == "guard" for m in made)


def test_a_spawn_the_model_could_not_shape_is_shaped_here():
    """Measured live: "I turn to fight the next group of guards" died in seven
    attempts — six on spawn missing template, one on the model reaching for `type`
    — and the player got a wall of red. The schema requires the op the model
    proposed, so the mechanical layer finishes it: aliases read, cues filled,
    thug when nothing cues."""
    out = judgement.repair_bare_spawns(
        [{"op": "spawn", "params": {"type": "watchman"}}], "I fight the guards")
    assert out[0]["params"]["template"] == "watchman"

    out = judgement.repair_bare_spawns(
        [{"op": "spawn", "params": {}}], "I turn to fight the next group of guards")
    assert out[0]["params"]["template"]          # cued or thug, never bare

    out = judgement.repair_bare_spawns(
        [{"op": "spawn", "params": {"template": "thug", "count": 2}}], "whatever")
    assert out[0]["params"] == {"template": "thug", "count": 2}


# --- the scene thread: what the player is engaged in between ops ----------------------

def test_the_thread_survives_a_continue():
    """Measured live: "I follow the guards that walked away", then "I continue to
    follow" — and the narrator, holding nothing but four words, dropped the guards
    and wrote a haunted house. The thread is engine state: set by the declaration,
    held by the continue, cleared by the fight or the journey, aged out after six
    quiet turns."""
    from rules.engine import Scene

    s = Scene()
    judgement.update_thread(s, "I follow the guards that walked away")
    assert s.thread["doing"] == "following"
    assert "guards" in s.thread["subject"]

    judgement.update_thread(s, "I continue to follow")
    assert s.thread["age"] == 0                      # held, not aged

    for _ in range(7):
        judgement.update_thread(s, "I look at the sky.")
    assert s.thread == {}                            # aged out

    judgement.update_thread(s, "I watch the tall stranger by the well")
    assert s.thread["doing"] == "watching"
    judgement.update_thread(s, "I punch him", ["begin_encounter"])
    # The fight IS the engagement: no subject for the anchor or the brief — but the
    # standing action is kept for Continue ("if I am running a machine and a fight
    # breaks out … I will be running the machine", the ruling of 2026-09-18).
    assert "subject" not in s.thread and "doing" not in s.thread
    assert s.thread["standing"]["doing"] == "watching"


def test_walking_away_ends_the_engagement():
    """Found in a live session, and it dragged the scene backwards two turns running.

    The player spent a turn talking to a merchant, then wrote "I leave the building and
    search the city for the largest group of powerful fighters I can find". The GM
    narrated the square, four men in chainmail, the lot. Then "I walk over to them" — and
    the next beat was back inside the building, by the fire, with a woman who had been
    dead for several turns.

    The thread was still on the books at age 2, and `thread_brief` states it to the prose
    call as FACT: "the player is currently talking to them… Keep them and the present
    surroundings in the scene; do not change location". The model obeyed. Ageing was
    never going to catch it — the thread rots after six quiet turns and the scene had
    already been pulled back twice by then.

    Leaving is not a quiet turn. It ends the engagement.
    """
    from rules.engine import Scene

    s = Scene()
    judgement.update_thread(s, "I ask the merchant what he sells")
    assert s.thread.get("subject"), "no thread to lose; this proves nothing"
    assert "do not change location" in judgement.thread_brief(s)

    judgement.update_thread(
        s, "I leave the building and search the city for the largest group of "
           "powerful fighters I can find")
    assert s.thread == {}, f"the merchant conversation followed them out: {s.thread}"
    assert judgement.thread_brief(s) == ""

    # An ordinary turn still holds the engagement — this must not clear on everything.
    s2 = Scene()
    judgement.update_thread(s2, "I ask the merchant what he sells")
    judgement.update_thread(s2, "I ask him where he got it")
    assert s2.thread.get("subject"), "a follow-up question dropped the thread"


def test_the_thread_brief_and_the_anchor():
    """The two halves of the constraint: the brief states the engagement as fact,
    and a beat that drops the subject gets it re-tethered before the hand-back."""
    from gm import narration
    from rules.engine import Scene

    s = Scene()
    judgement.update_thread(s, "I follow the two guards in chain shirts")
    brief = judgement.thread_brief(s)
    assert "guards" in brief and "do not change location" in brief

    haunted = ("You push forward into the house, dust and decay all around. "
               "What do you do next?")
    out, anchored = narration.keep_the_thread(haunted, s.thread)
    assert anchored and "guards" in out
    assert out.endswith("What do you do next?")

    kept = "The guards ahead slow at the market's edge. What do you do?"
    same, anchored = narration.keep_the_thread(kept, s.thread)
    assert same == kept and not anchored


def test_walking_away_resolves_the_dying_and_departs_nobody():
    """Measured live: "i leave and return to the market" kept the whole battlefield —
    four corpses in the scene panel scenes later, and a stranger "bleeding out" since
    the first fight, printing his tell every turn.

    This door used to answer that by departing the fallen, because a room had no way
    to keep its people. It has one now: the room keeps them and the party's `travel`
    is what stops the view holding them (stage 8b). What this door still owns is the
    story beat — the dying resolve by 1e's own odds before the party is out of
    earshot, never eternally bleeding — and the bodies stay where they fell for the
    ageing loop to sweep wherever the party has gone.
    """
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    corpse = instantiate("thug", scene=s, name="the thug")
    s.add(corpse); corpse.hp = -20; corpse.apply_hp_state()
    dying = instantiate("watchman", scene=s, name="the stranger")
    s.add(dying); dying.hp = -8; dying.apply_hp_state()
    assert dying.has_condition("dying")

    e = Engine(s, Dice(seed=9))
    assert judgement.player_departs("i leave and return to the market")
    assert not judgement.player_departs("I attack the merchant")
    tells = e.leave_behind()
    assert any("stranger" in t for t in tells)
    assert not dying.has_condition("dying")
    assert corpse.ref in s.people and dying.ref in s.people, \
        "leave_behind destroyed people; the room keeps them"


def test_an_unaimed_item_damage_is_a_refusal_not_a_dead_turn():
    """Measured live: the GM proposed item_damage with an amount and nobody's
    gear; validation only requires the amount, so the raise happened mid-run and
    the whole resolved turn died as a 502 red wall."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "item_damage", "because": "t",
                             "params": {"amount": 4}}], origin="author:test")).outcomes[0]
    assert "Nobody's gear" in out.tell


def test_the_thread_knows_where_and_nobody_arrives_there_twice():
    """The second live loss: the subject held but the setting drifted — "following
    them in the market" became following the stranger INTO the market both of them
    were already standing in. The place sticks to the thread from the player's own
    words, the brief states both parties are already there, and arrival language
    aimed at that place is rewritten in the smallest way that unbreaks geography."""
    from gm import narration
    from rules.engine import Scene

    s = Scene()
    judgement.update_thread(s, "i leave and return to the market")
    judgement.update_thread(s, "I find a person who is wandering around and i follow them")
    judgement.update_thread(s, "I keep to the shadows in the market")
    # The thread no longer carries a place: that was a second writer of "where the
    # party is" beside the engine's own, read out of the player's sentence, and one
    # brief could assert two rooms. The place is the engine's and is handed in.
    assert "where" not in s.thread
    assert s.thread.get("subject") == "them"

    brief = judgement.thread_brief(s, where="the market")
    assert "ALREADY at the market" in brief
    assert "ALREADY" not in judgement.thread_brief(s)

    beat = ("The stranger is heading towards the market, and you arrive at "
            "the market a few paces behind. What do you do?")
    out, done = narration.already_there(beat, "the market")
    assert done
    assert "heading through the market" in out
    assert "stand in the market" in out
    assert "towards the market" not in out


# --- the cast ledger: prose-people become scene state ---------------------------------

def test_the_prose_cast_is_on_the_books_and_in_the_brief():
    """The haunted-house class in its second form: a Kelvaxian merchant approached
    the player and two beats later had evaporated, because he lived nowhere but
    the model's short memory. Role-phrases in a final beat land in scene.cast,
    the brief feeds them back as fact, and walking away leaves them behind."""
    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    beat = ("One of them, a Kelvaxian merchant, notices your return and "
            "approaches you. Behind him an old priestess watches from a stall.")
    added = judgement.note_cast(s, beat, turn=3)
    assert any("merchant" in a for a in added)
    assert any("priestess" in a for a in added)

    brief = judgement.cast_brief(s)
    assert "Kelvaxian merchant" in brief and "priestess" in brief

    # The same beat again introduces nobody twice.
    assert judgement.note_cast(s, beat, turn=4) == []

    # A real actor's role never doubles into the ledger.
    from rules.bestiary import instantiate
    s2 = Scene(); s2.add(instantiate("watchman", scene=s2, name="the watchman"))
    assert judgement.note_cast(s2, "The watchman frowns at a watchman.", 1) == []

    judgement.clear_cast(s)
    assert s.cast == [] and judgement.cast_brief(s) == ""


def test_a_figure_of_speech_is_not_a_person_in_the_scene():
    """Found in a live session, and it put a woman back in a room the player had left.

    The beat opened "The blood on your hands has not yet dried, and the memory of the
    woman's end still hangs heavy in the air…" — and **the memory of the woman** went
    into `scene.cast` as somebody present. `cast_brief` feeds the ledger back as fact,
    so the next beat re-staged her by the fire, in a building the player had walked out
    of two turns earlier. One of the three cast entries recorded across the twelve real
    campaigns was this abstraction.

    The filler between the article and the role noun is three arbitrary words, which is
    what lets "a tall hooded stranger" through. A role reached across "of" is not
    somebody arriving — it is a possessive, a back-reference or a figure of speech.
    """
    from rules.engine import Scene
    from rules.sheet import load_pc

    def cast_from(beat):
        s = Scene()
        s.add(load_pc("fixtures/pc-kesst.json"))
        judgement.note_cast(s, beat, turn=1)
        return [e["who"] for e in s.cast]

    live = ("The blood on your hands has not yet dried, and the memory of the woman's "
            "end still hangs heavy in the air. As you step out into the square, a group "
            "of four men in chainmail stand near the corner.")
    got = cast_from(live)
    assert not any("memory" in w for w in got), f"a figure of speech joined the cast: {got}"
    assert any("man" in w for w in got), "the four men who are actually there were lost"

    # Real introductions still land; back-references still do not.
    assert cast_from("A tall hooded stranger steps out of the doorway.") == \
        ["tall hooded stranger"]
    assert cast_from("One of the men turns to look at you.") == []


def test_a_ledger_merchant_promotes_to_a_civilian_not_a_bruiser():
    """Attacking the merchant the prose introduced must spawn a commoner
    statline: promoting shopkeepers to warriors makes every stall a fight club."""
    out = judgement.inject_fight([{"op": "narrate_only"}],
                                 "I attack the merchant", _empty_room())
    spawn = next(i for i in out if i.get("op") == "spawn")
    assert spawn["params"]["template"] == "guildhand"


def test_the_dead_cannot_talk_their_way_past_the_scrubber():
    """Measured live: a merchant at -19 of 13 spat "You'll pay for this!" and
    nodded through two more beats — every sentence shielded by its own quotation
    marks, because the quote exemption was written for living speakers who
    *mention* the dead. A dead man speaking outside the quotes is cut now; a
    living speaker naming the dead inside a quote is still spared."""
    from gm import narration

    talking = ("The merchant, still reeling from your earlier strike, stumbles "
               "towards you. He spits at your feet, 'You'll pay for this!' "
               "The merchant you just spoke with nods towards him, saying "
               "'That one wants silk.'")
    out, cut = narration.cut_dead_men_walking(talking, ["merchant"])
    assert len(cut) >= 2 and "merchant" not in out.lower()

    spared = "The guard shakes his head: 'the merchant is dead, and that is that.'"
    same, cut = narration.cut_dead_men_walking(spared, ["merchant"])
    assert same == spared and not cut


def test_the_person_addressed_becomes_real():
    """Measured live, overruling an older refusal by the player's word: "i talk
    to another merchant" produced a vivid stranger who was never added to the
    scene, could not be traded with, and evaporated. Addressing a civilian role
    now spawns them peacefully as the commoner they are."""
    out = judgement.inject_company(
        [{"op": "narrate_only"}], "i talk to another merchant", _empty_room())
    spawn = next(i for i in out if i.get("op") == "spawn")
    assert spawn["params"]["template"] == "guildhand"
    assert spawn["params"]["name"] == "merchant"
    assert all(i.get("op") != "begin_encounter" for i in out)

    # Somebody by that role already alive: no double.
    from rules.bestiary import instantiate
    from rules.engine import Scene
    from rules.sheet import load_pc
    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    m = instantiate("guildhand", scene=s, name="merchant"); s.add(m)
    out = judgement.inject_company([{"op": "narrate_only"}],
                                   "I talk to the merchant", s)
    assert all(i.get("op") != "spawn" for i in out)


def test_a_public_killing_heats_the_scene_and_bodies_age_out():
    """Measured live: a merchant murdered mid-market, and the next stall-keeper
    chatted amiably about silk while four corpses stood in the scene panel. The
    kill writes scene.heat while anyone watches, the brief carries it, and the
    fallen depart on their own after two turns' grace."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Outcome, Scene
    from rules.sheet import load_pc

    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    victim = instantiate("guildhand", scene=s, name="merchant"); s.add(victim)
    s.cast.append({"who": "an old priestess", "turn": 1})
    fake = Outcome(intent_id="i1", op="attack", effects=[
        {"ref": victim.ref, "kind": "condition", "condition": "dead"}])
    victim.hp = -20; victim.apply_hp_state()
    judgement.note_heat(s, [fake])
    assert "killed merchant" in s.heat.get("note", "")
    assert "Nobody chats casually" in judgement.heat_brief(s)

    e = Engine(s, Dice(seed=4))
    e.tidy_the_fallen(); assert victim.ref in s.actors      # grace turn 1
    e.tidy_the_fallen(); assert victim.ref in s.actors      # grace turn 2
    e.tidy_the_fallen(); assert victim.ref not in s.actors  # swept


def test_continue_holds_the_thread_and_the_ledger_rots():
    """Measured live from the save's own ledger: at the Continue turn the thread
    was {} — browsing and walking-up were not thread verbs — and the cast held
    one stale "stranger" from a dozen turns back. Continue arrived with no
    constraint and a bread stall became a library. The Continue instruction now
    counts as a continue, browsing somebody is an engagement, and ledger entries
    older than twelve turns rot out."""
    from play.views import CARRY_ON
    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    judgement.update_thread(s, "i browse her bread")
    assert s.thread.get("doing") == "talking to"

    for _ in range(5):
        judgement.update_thread(s, CARRY_ON)
    assert s.thread.get("age") == 0                 # held, not aged out

    s.cast = [{"who": "stranger", "turn": 1}]
    judgement.note_cast(s, "An elderly Kelvaxian vendor waves.", turn=20)
    assert all(e["who"] != "stranger" for e in s.cast)
    assert any("vendor" in e["who"] for e in s.cast)


def test_a_noted_person_stands_in_the_scene():
    """The ruling after the library beat: the place held but 'there should have
    been a stranger' — the ledger knew about him and the engine did not, so he
    could not be attacked, addressed, or found again. Newly noted cast promote
    to living civilians (armed roles get an armed statline), capped at four,
    and walking away takes them off the board with the ledger."""
    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene(); s.add(load_pc("fixtures/pc-kesst.json"))
    added = judgement.note_cast(
        s, "A stranger watches from the doorway. Nearby, an armed guard "
           "leans on his spear.", turn=2)
    made = judgement.promote_cast(s, added)
    assert len(made) == 2
    names = {a.name for a in s.actors.values() if not a.is_pc}
    assert any("stranger" in n for n in names)
    assert any("guard" in n for n in names)
    guard = next(a for a in s.actors.values() if "guard" in a.name)
    assert guard.from_template == "guard",         "the corpus has a Guard at CR 1; the watchman is the floor, not the answer"

    # The ledger empties; the people stay. `clear_cast` used to depart the promoted
    # civilians because a room had no way to keep them — it does now, and it is the
    # party WALKING OUT that stops the view holding them, not the regex.
    judgement.clear_cast(s)
    assert s.cast == []
    assert not all(a.is_pc for a in s.actors.values()), \
        "clear_cast still departs people; the room should keep them"
    s.move("pc", "somewhere~urban:else")
    assert all(a.is_pc for a in s.actors.values())
    assert len(s.people) == 3, "moving the party destroyed the people it left"


def test_a_crowd_is_people():
    """Measured live: "a group of six men and women gathered in a circle, their
    armor heavy with the marks of use" registered NOBODY — the ledger only
    spoke singular — so the scene held zero actors, and the very next beat
    invented a merchant in a stall where six armed fighters had been standing.
    The player's read was right: the world state was doing it."""
    from rules.engine import Scene

    s = Scene()
    added = judgement.note_cast(
        s, "You find them: a group of six men and women gathered in a circle, "
           "their armor heavy with the marks of use.", turn=1)
    assert added == ["man"]                      # not "six man", not the phrase
    # Six, as the prose said. This read 4 until 2026-09-19: the promotion cap was applied
    # at BOOKING, so nothing downstream could know the fiction had said six and
    # `cast_brief` told the model four (item 30). The cap now lives where bodies are made.
    assert s.cast[0]["count"] == 6
    judgement.promote_cast(s, added)
    assert len([a for a in s.actors.values() if not a.is_pc]) == 4

    # A group and a singleton in one beat are three people, not four.
    s2 = Scene()
    added = judgement.note_cast(
        s2, "A pair of guards blocks the door, and a merchant watches.", turn=1)
    assert added == ["guard", "merchant"]
    judgement.promote_cast(s2, added)
    assert sorted(a.name for a in s2.actors.values()) == [
        "guard", "guard", "merchant"]


def test_the_ledger_books_people_not_turns_of_phrase():
    """Seen in the scene panel, 2026-09-06: "is a man", "other a woman", "right
    people", "Weaver's the stranger", beside real people. A filler word that is a
    verb, an article, a pronoun or a possessive is not an adjective; a possessive
    means a place; a generic plural is nobody."""
    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    beat = ("The weaver is a man of few words. Beside him the other a woman waits. "
            "It is where the right people find their way. The Weaver's the stranger "
            "is a place for rest. A tall hooded stranger watches from the door.")
    added = judgement.note_cast(s, beat, turn=3)
    assert "is a man" not in added and "other a woman" not in added
    assert "right people" not in added and not any("Weaver" in a for a in added)
    assert "man" in added and "woman" in added
    assert "tall hooded stranger" in added
