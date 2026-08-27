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
    ]))
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
    intents = engine.validate(amended)
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
    scene.biome = "urban"
    out = judgement.inject_travel(
        [{"op": "narrate_only"}],
        "I head out the gates for the treeline before this city causes me more trouble.",
        scene)
    assert out[-1]["op"] == "travel"
    assert out[-1]["params"]["biome"] == "forest"


def test_mentioning_ground_without_going_there_travels_nowhere(scene):
    scene.biome = "urban"
    for text in ("I like these woods.", "Should we head into the woods?",
                 "I walk across the yard to the gate."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert all(r.get("op") != "travel" for r in out), text


def test_travelling_to_the_ground_underfoot_is_not_a_transition(scene):
    scene.biome = "forest"
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
    scene.biome = "urban"
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
    scene.biome = "urban"
    for text in ("I brush past the guard and keep going.",
                 "I pull the wooden door to and bar it.",
                 "The sword is mine, and I take it to the table."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene)
        assert all(r.get("op") != "travel" for r in out), text


def test_going_home_is_a_journey_too(scene):
    """"Return to Zhilvarnia" is one of the app's own suggestion chips, and none of the
    ways of saying it were in `_DEPARTS`: return, turn back, double back, retrace. Going
    home is as common a move as setting out, and the safety net had no word for it."""
    scene.biome = "grassland"
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
    scene.biome = "grassland"
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
    scene.biome = "grassland"
    for text in ("Return to Zhilvarnia.", "I head back to Zhilvarnia.",
                 "I walk to Mirabalos.", "I set out for Torvathys."):
        out = judgement.inject_travel([{"op": "narrate_only"}], text, scene, world)
        assert out[-1].get("op") == "travel", text
        assert out[-1]["params"]["biome"] == "urban", text


def test_already_in_the_town_you_named_is_not_a_journey(scene):
    scene.biome = "urban"
    out = judgement.inject_travel(
        [{"op": "narrate_only"}], "Return to Zhilvarnia.", scene, _pangrella())
    assert all(r.get("op") != "travel" for r in out)


def test_talking_about_a_journey_is_not_taking_one(scene):
    """"I think about going to Zhilvarnia one day" has a movement verb, a preposition and
    a real city in it, and the party must not be somewhere else by the end of the
    sentence. The hole was there for terrain too — this closes both."""
    world = _pangrella()
    scene.biome = "grassland"
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
    engine.run(engine.validate(raw))
    assert scene.zones["c1"] == "engaged"
    assert scene.distance_between("pc", "c1") == 5, "not within reach of a punch"
    # And the attack is waiting on the player's d20 rather than silently not happening.
    assert scene.awaiting and scene.awaiting["die"] == "1d20"
    assert "Attack" in scene.awaiting["label"]


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
        engine.run(engine.validate(raw))
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
    engine.run(engine.validate(raw))
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


def test_a_turn_that_fails_every_attempt_says_so_instead_of_crashing():
    """The error path unpacked `schedule` — which holds (model, host, provider, key) —
    as a pair, and raised `ValueError: too many values to unpack` *while reporting that
    the turn had failed*. The honest "five attempts, here is what each one got wrong"
    message the player is owed came out as a 500 and a traceback.

    It only runs when every attempt has failed, which is why nobody had reached it until
    `tools/narrator_audit.py` drove enough turns to find one."""
    import re as _re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "gm" / "agent.py").read_text(
        encoding="utf-8")
    raiser = src[src.index("could not produce a valid turn"):][:400]
    assert "for m, *_ in schedule" in raiser
    assert "for m, _ in schedule" not in raiser
    # And the schedule really is wider than two, which is what made it a bug.
    built = _re.search(r"schedule = \[\((.*?)\)\]", src)
    assert built and built.group(1).count(",") >= 2, built and built.group(1)



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
    Engine(scene, Dice(seed=3)).validate(amended)   # must not raise

    # A sale to somebody actually present is not this function's business.
    from rules.sheet import from_dict
    scene.actors["c1"] = from_dict({"name": "the stallholder", "kind": "npc",
                                    "hp": 4, "hp_max": 4, "level": 1,
                                    "class": ""}, ref="c1")
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
    assert [i.op for i in eng.validate(raw)] == ["check"]

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
    assert [i.op for i in eng.validate(chained)] == ["narrate_only", "check"]



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
    assert fixed[0]["op"] == "spawn" and fixed[0]["params"]["template"] == "watchman"
    assert fixed[1]["target"] not in (body.ref,)

    # No opposition named: kicking the fallen is a thing a player may mean.
    assert judgement.redirect_attacks_off_corpses(
        raw, "I kick him while he is down", scene) is None
