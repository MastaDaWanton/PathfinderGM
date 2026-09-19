"""People have names and faces.

The 2026-09-18 play-test, items 12, 21 and 13c (docs/playtest-2026-09-18.md). Asked his
name, an NPC called himself "the stranger" — our placeholder — because nothing on an
actor held a real name behind the descriptor; when the model DID give one ("Kaelen") the
un-namer struck it inside his own line. The woman in the doorway was never described: no
guard required a body, only the wrong body was stopped, and the brief carried no
appearance for anyone though every world resident has an Appearance fact and every
people a body. And the homebrew asura's body line rendered EMPTY (its evolutions were
never converted), so the NPC turn wrote "the beast" for the player.

The material was there and unused: the export's `play.names` — 80 pools of given and
family names by people — and `play.races` with each people's body in sentences.
"""
from __future__ import annotations

import pytest

from gm import judgement, narration
from play import campaign as cm
from rules import names as names_mod
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc


@pytest.fixture(scope="module")
def world():
    return cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))


@pytest.fixture
def step(world):
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


# --- 12: a true name from the world's own pools ---------------------------------------------

def test_the_pools_are_read_and_a_name_is_drawn_from_the_towns_people(world, step):
    assert len(names_mod.pools(world)) == 80
    people = names_mod.people_of(world, step.location_id)
    assert people in names_mod.peoples(world), "Vormoor's residents name their people"
    pool = names_mod.pool_for(world, step.location_id)
    assert pool["people_id"] == people
    name = names_mod.true_name(world, step.location_id, "c1")
    given, family = name.split()
    assert given in pool["given"] and family in pool["family"]
    # Deterministic, and never a name already worn here.
    assert names_mod.true_name(world, step.location_id, "c1") == name
    other = names_mod.true_name(world, step.location_id, "c2", taken=[name])
    assert other != name


def test_a_promoted_person_carries_a_true_name_and_a_face_and_the_brief_says_both(world, step):
    from gm import prompts

    added = judgement.note_cast(step, "A stranger shares the step with you.", turn=1)
    judgement.promote_cast(step, added, world=world)
    stranger = next(a for a in step.actors.values() if a.name == "stranger")
    assert stranger.true_name and stranger.true_name != "stranger"
    assert stranger.appearance and ":" in stranger.appearance
    brief = prompts.scene_brief(world, step, None, [])
    # The true name is NOT in the brief: shown it, the narrator used it before it was
    # given ("Soren's eyes narrow", "the woman beside you, Kael Throk" — two replays).
    # The model's own guess is replaced with it in code when the person introduces
    # themselves.
    assert stranger.true_name not in brief
    assert "Looks (fact, use it when they are first described):" in brief
    # The panel still shows the descriptor until the name is given in play.
    assert stranger.name == "stranger"


def test_a_name_given_in_play_renames_the_panel_and_an_invented_one_becomes_the_true_one(world, step):
    added = judgement.note_cast(step, "A stranger shares the step with you.", turn=1)
    judgement.promote_cast(step, added, world=world)
    stranger = next(a for a in step.actors.values() if a.name == "stranger")
    true = stranger.true_name
    beat = ("The stranger shrugs and does not look at you. 'Call me Kaelen,' he says. "
            "'Kaelen will do.' What do you do?")
    assert narration.introductions(beat) == [("stranger", "Kaelen")]
    settled, swaps = narration.settle_introductions(beat, {"stranger": true})
    assert f"Call me {true}" in settled and "Kaelen" not in settled
    assert swaps == [f"Kaelen -> {true}"]
    renamed = judgement.apply_introductions(step, settled)
    assert renamed == [(stranger.ref, true)]
    assert stranger.name == true
    # Refusing to give a name stays legitimate: nothing is introduced, nothing renamed.
    assert narration.introductions("'I'm not telling you my name,' he says.") == []
    # A quoted "I am" opening on a common word is not a name.
    assert narration.introductions("'I am Sorry,' she says, 'the name is Not yours.'") == []


def test_the_un_namer_keeps_a_name_the_scene_holds(world, step):
    added = judgement.note_cast(step, "A stranger shares the step with you.", turn=1)
    judgement.promote_cast(step, added, world=world)
    stranger = next(a for a in step.actors.values() if a.name == "stranger")
    text = f"'Call me {stranger.true_name},' he says."
    kept, unnamed = narration.unname_strangers(text, {stranger.true_name, *stranger.true_name.split()})
    assert kept == text and unnamed == []


# --- 21: a face on arrival ------------------------------------------------------------------

def test_a_person_who_arrives_faceless_is_found_and_the_worlds_body_line_stands_in(world, step):
    beat = ("Steam rises from the basin. A woman waits in the doorway, her gaze steady, "
            "her manner unhurried. What do you do?")
    assert narration.faceless(beat, "woman in the doorway")
    described = ("A woman waits in the doorway, grey at the temples, a leather apron over "
                 "her dress. What do you do?")
    assert not narration.faceless(described, "woman in the doorway")
    face = names_mod.appearance_for(world, step.location_id, ref="c9")
    assert face and face.split(":")[0] in names_mod.peoples(world).values()
    # A world resident's own Appearance fact is theirs.
    drenn = world.by_name("Drenn Ironvale", kind="CHARACTER")
    assert names_mod.resident_appearance(world, drenn.id) == drenn.facts["Appearance"]


def test_a_bare_quoted_answer_to_the_question_is_an_introduction(world, step):
    """Group-3 replay, 2026-09-18: asked his name, the stranger answered '"Gorvothor
    Kragnir," he grunts' — the world's own name, from the brief — and the panel kept
    "stranger", because a bare quoted name is not one of the introduction phrases."""
    added = judgement.note_cast(step, "A stranger shares the step with you.", turn=1)
    judgement.promote_cast(step, added, world=world)
    stranger = next(a for a in step.actors.values() if a.name == "stranger")
    beat = (f"The stranger takes a slow breath before speaking. \"{stranger.true_name},\" "
            f"he grunts, finally. He does not look up. What do you do?")
    assert narration.introductions(beat) == []
    assert narration.introductions(beat, asked_for_name=True) == [("stranger", stranger.true_name)]
    renamed = judgement.apply_introductions(step, beat, "I ask the stranger for his name")
    assert renamed == [(stranger.ref, stranger.true_name)] and stranger.name == stranger.true_name
    # Not asked, a quoted capitalised word is not somebody's name.
    assert judgement.apply_introductions(step, '"Vormoor," he grunts.', "I wait") == []


def test_looking_somebody_over_owes_a_face_and_old_actors_get_names(world, step):
    woman = instantiate("guildhand", scene=step, name="woman in the doorway")
    step.add(woman)
    assert judgement.examined("I look the woman in the doorway over carefully", step) == woman.ref
    assert judgement.examined("I look around the market", step) is None
    # A save from before the fields existed: named here, once, deterministically.
    assert not woman.true_name
    named = judgement.name_the_nameless(step, world)
    assert named == [woman.ref] and woman.true_name and woman.appearance
    assert judgement.name_the_nameless(step, world) == []


def test_the_view_appends_the_face_when_the_beat_left_it_out():
    import inspect

    from play import views

    src = inspect.getsource(views._finish)
    assert "narration_mod.faceless(text, phrase)" in src
    assert "apply_introductions(c.scene, text, player_input)" in src


# --- 13c: the player is never a beast; the homebrew body is a body -------------------------

def test_the_player_is_not_a_creature_noun_in_narration_when_everyone_else_is_a_person():
    text = ("The beast lunges, and the man steps back. 'Stay back, you beast!' he shouts. "
            "The creature's shadow falls over the stall.")
    fixed, swapped = narration.creature_nouns_for_pc(text, "Masta", others_are_people=True)
    assert fixed.startswith("Masta lunges") and "Masta's shadow" in fixed
    assert "'Stay back, you beast!'" in fixed, "his own words are his"
    assert swapped == ["beast", "creature"]
    # With a creature present, the noun may be its own.
    same, none = narration.creature_nouns_for_pc(text, "Masta", others_are_people=False)
    assert same == text and none == []


def test_an_unconverted_homebrew_race_still_has_a_body_line():
    from rules import races

    card = {"id": "asura", "name": "Asura", "type": "outsider", "size": "medium",
            "effects": [], "tags": [], "weapons": [],
            "evolutions": [{"id": "bite", "choice": "", "times": 1},
                           {"id": "improved-damage", "choice": "claws", "times": 1},
                           {"id": "claws", "choice": "", "times": 1},
                           {"id": "tail", "choice": "", "times": 1},
                           {"id": "gills", "choice": "", "times": 1},
                           {"id": "limbs", "choice": "arms", "times": 2}]}
    line = races.body_line(card)
    assert "a medium outsider" in line
    assert "bite" in line and "claws" in line and "tail" in line and "limbs (arms)" in line
    assert "improved damage" not in line


def test_the_pc_line_names_the_race_when_the_heritage_is_blank(world, step):
    from gm import prompts

    pc = step.pc()
    pc.heritage = ""
    pc.race = "human"
    brief = prompts.scene_brief(world, step, None, [])
    line = next(ln for ln in brief.splitlines() if "the player's character" in ln)
    assert " human " in line.lower() or "Human " in line
