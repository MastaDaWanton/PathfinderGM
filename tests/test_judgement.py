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
