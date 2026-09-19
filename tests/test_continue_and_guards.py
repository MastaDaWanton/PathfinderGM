"""Continue, polish and the guards that over-reached.

The 2026-09-18 play-test, items 23, 22, 11, 10 (docs/playtest-2026-09-18.md). The
ruling on Continue: "my character should keep doing whatever he is doing and the scene
should move forward without any addition from me … if I keep hitting continue the fight
should play out further and further." The shipped design was the inverse — Continue's
examples demonstrated "nobody acts, nothing new arrives" — and its directive reached the
planner as the player's words: `say` of "in their own words…", `give` of "scene on" ×3.
In the brothel, five of our own mechanisms stopped a scene the model was writing: the
polish rewrite replaced the woman's actions with the timberer's mallet; the escape
guard cut "She doesn't pull away" as an escape, negated, with nobody held; the phrase
guards fired on "the woman"/"the girl" in a two-person room. "the Reeve's men" became
"the the stranger men" because the world says "reeve" in lowercase. And the opening fell
to the template because the model wrote "Maste" for "Masta".
"""
from __future__ import annotations

import pytest

from gm import judgement, narration, prompts
from rules import intents
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc


@pytest.fixture
def room():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the woman"))
    return s


# --- 23: Continue is a directive; the standing action holds; the world moves ------------------

def test_continue_asks_the_model_for_no_plan_and_the_directive_never_reaches_the_injectors(room):
    import inspect

    from gm import agent as agent_mod

    src = inspect.getsource(agent_mod.GMAgent.plan_turn)
    assert "if player_input == prompts.CARRY_ON:" in src
    assert "return self._continue_plan()" in src
    # And the directive buys nothing and says nothing when it does reach an injector.
    raw = judgement.inject_goods([{"op": "narrate_only", "params": {}}], prompts.CARRY_ON, room)
    assert [r["op"] for r in raw] == ["narrate_only"]


def test_the_standing_action_is_a_fact_for_the_continue_beat_and_survives_a_fight(room):
    judgement.update_thread(room, "I keep running the machine")
    judgement.update_thread(room, "I watch the woman")
    said = judgement.standing_action(room)
    assert said.startswith("THE PLAYER'S STANDING ACTION (fact): they go on watching the woman")
    assert "THE WORLD MOVES ONE BEAT" in said and "Nobody merely waits" in said
    # A fight keeps it as `standing`, silent to the anchor and the brief, alive for Continue.
    woman = next(a for a in room.actors.values() if a.name == "the woman")
    judgement.bind_thread(room, [woman.ref])
    judgement.update_thread(room, "I hit her", ["begin_encounter", "attack"])
    assert room.thread["opponent"] == woman.ref
    assert room.thread["standing"] == {"doing": "watching", "subject": "the woman"}
    assert judgement.thread_brief(room) == ""
    assert "watching the woman" in judgement.standing_action(room)


def test_the_continue_examples_show_a_standing_action_held_while_the_scene_moves():
    """None may show a stalled room: each example has somebody DOING something and a
    thing that happens; none says nobody acts or nothing is decided."""
    for ex in prompts.CARRY_ON_EXAMPLES:
        text = ex["reply"]["narration"]
        assert len(narration.action_sentences(text)) >= 3, text[:80]
        low = text.lower()
        for stalled in ("nobody fills the gap", "nothing has been decided", "he waits.",
                        "has not moved", "nothing has come apart"):
            assert stalled not in low, stalled


# --- 22: polish keeps the events ------------------------------------------------------------------

DRAFT = ("The woman continues her work, her hands steady on your tunic as she works to "
         "discard the layers between you. She sets the tray down and reaches for the basin. "
         "Steam rises from the water. She leans in, close enough that you feel her breath. "
         "What do you do?")
POLISHED = ("The timberer's rhythmic thud provides a steady pulse against the heavy air of "
            "the room. Steam rises from the basin in thick plumes, carrying the fragrance of "
            "jasmine. The woman with the basin remains a shadow, her presence fading into "
            "the periphery. Beyond the door the market continues. What do you do?")


def test_action_sentences_are_the_events_and_the_polish_that_dropped_them_is_measured():
    events = narration.action_sentences(DRAFT, ["the woman"])
    assert len(events) == 3, events
    assert "Steam rises from the water." not in events
    assert narration.actions_kept(DRAFT, POLISHED, ["the woman"]) < 0.6
    assert narration.actions_kept(DRAFT, DRAFT, ["the woman"]) == 1.0
    # Reworded but kept: the same people doing the same things in other words.
    kept = ("Her hands stay steady on your tunic while she works the layers off you. "
            "The tray goes down on the stool and she reaches for the basin. She leans "
            "close, her breath on your face. What do you do?")
    assert narration.actions_kept(DRAFT, kept, ["the woman"]) >= 0.6


def test_a_short_draft_that_carries_its_events_ships_at_its_own_length():
    import inspect

    from gm import agent as agent_mod

    src = inspect.getsource(agent_mod.GMAgent.polish)
    assert 'kinds <= {"too-short", "no-hand-back"}' in src
    assert "actions_kept(text, candidate, cast_names) >= 0.6" in src


# --- 22: the escape claim needs a restraint and respects negation ------------------------------

def test_an_escape_is_a_claim_only_when_somebody_is_held_and_only_when_asserted():
    text = ("She doesn't pull away; instead, she lets out a low breath against your neck, "
            "her hands steady as she works to discard the layers between you.")
    assert intents.find_outcome_claims(text, restrained=False) == []
    assert intents.find_outcome_claims(text, restrained=True) == [], "negated"
    slips = "You squirm and twist, managing to slip free of the grapple."
    whys = {c.why for c in intents.find_outcome_claims(slips, restrained=True)}
    assert "states an escape" in whys
    assert "states an escape" not in {c.why for c in intents.find_outcome_claims(slips, restrained=False)}
    kept, cut = intents.cut_outcome_claims(text, restrained=False)
    assert kept == text and cut == []


# --- 22: the phrase guards exempt the only other person -------------------------------------------

def test_the_only_other_persons_handle_is_not_a_formula_in_a_two_person_room():
    earlier = ["The woman sets the tray down. Steam rises.", "The woman lifts the basin. It is hot.",
               "The woman looks at you and says nothing."]
    text = "The woman leans in and takes the cup from your hand. What do you do?"
    with_crowd = narration.review(text, earlier=earlier, others=("the woman", "the girl", "a guard"))
    alone = narration.review(text, earlier=earlier, others=("the woman",))
    assert "formulaic-opening" in {f.kind for f in with_crowd.findings}
    assert "formulaic-opening" not in {f.kind for f in alone.findings}
    # And a recurring phrase that is her handle is not a tic when she is the room.
    beats = ["The woman with the basin sets it down and the water steams.",
             "The woman with the basin turns to the door and listens for a step."]
    now = "The woman with the basin kneels and wrings the cloth out. What do you do?"
    tics_alone = narration.review(now, earlier=beats, others=("woman with the basin",))
    assert "recurring-phrase" not in {f.kind for f in tics_alone.findings}


# --- 11: the world's lowercase vocabulary; the renamer's article ---------------------------------

def test_a_word_the_world_uses_in_lowercase_is_not_a_name_from_nowhere():
    known = {"Vormoor", "reeve", "council", "elders"}      # as the vocabulary now supplies them
    assert narration.invented_names("The Reeve's men and the Council stand by.", known) == []
    assert narration.invented_names("By the well, Kaida waves to Vorgath.", known) == ["Kaida", "Vorgath"]


def test_the_renamer_minds_the_article_already_in_front():
    known = {"Vormoor", "Masta"}
    text = "Someone is making a scene at the gate, and the Reeve's men are trying to contain it."
    assert narration.unname_strangers(text, known)[0] == \
        "Someone is making a scene at the gate, and the men are trying to contain it."
    assert narration.unname_strangers("The guard nods at the Reeve and spits.", known)[0] == \
        "The guard nods at the stranger and spits."
    assert "the the" not in narration.unname_strangers(text, known)[0]


# --- 10: the opening's near-miss name, and a spliced fact's article --------------------------------

def test_a_name_one_letter_off_is_the_real_name_before_the_checks_run():
    from play import opening, opening_prose

    draft = "Maste sits on the step in Vormoor and eats. Vormor is loud. What do you do?"
    fixed, swaps = opening_prose.repair_near_misses(draft, {"Vormoor"}, "Masta", "Vormoor")
    assert fixed == "Masta sits on the step in Vormoor and eats. Vormoor is loud. What do you do?"
    assert swaps == ["Maste -> Masta", "Vormor -> Vormoor"]
    # A genuine invention is left for the checks to catch.
    assert opening_prose.repair_near_misses("Kaida waits.", {"Vormoor"}, "Masta")[1] == []
    assert opening._clause("A local reeve confirmed by Kragmoor Horde's central authority.") == \
        "a local reeve confirmed by Kragmoor Horde's central authority"
    assert opening._clause("Khy'vyr-centric clans.") == "Khy'vyr-centric clans"
