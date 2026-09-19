"""Group 8 of the 2026-09-19 fix pass: nobody is invented.

Three reported items and one found in group 7's own live check
(docs/playtest-2026-09-18.md items 29, 30, 34).

  * **"I turn to find the mayor" spawned a mayor.** Six repairs in `gm/judgement.py` can
    create somebody because the player named them, and not one of them consulted the
    world, though `World.by_name` and `World.residents` could answer the whole time —
    their only caller was the `/gm` lookup tool. `repair_unknown_refs` turned the model's
    invented target `"mayor"` into a 13-hp Warrior-1 *called* mayor, carrying a sap, in a
    town whose `Formal Power` fact is a reeve and which has no mayor among the export's 256
    characters. The asymmetry was the whole bug: a *sale* to an absent person was dropped
    and the turn survived, an *attack* or a *talk* invented them.

  * **Raiders in the prose and nobody on the board.** Measured: `"a band of twelve
    raiders"` booked **zero** — no ledger entry, no actor, not even a `cast_brief` mention
    — because `raider` was in no form in `_CAST_ROLES`, while a Raider at 29 hp has shipped
    in the bestiary all along. `"a band of twelve soldiers"` was wrong three ways at once:
    `_NUMBER_WORDS` had no **twelve**, so the ledger booked a person called "twelve
    soldier"; the count was clamped to the promotion cap at booking time, so nothing
    downstream could know the fiction said twelve; and `promote_cast` returned immediately
    mid-fight, which is exactly when a band arriving matters. And the drift the player
    reported — soldiers becoming raiders — was held by one sentence of prompt text.

  * **A person invented out of somebody's own words.** Found live 2026-09-19: the beat
    said, of the woman being asked her name, "Most just call me the stranger", and a new
    actor called **stranger** was booked and promoted. `note_cast` read the whole beat,
    quoted speech included.
"""
from __future__ import annotations

import inspect

import pytest

from gm import judgement
from rules import scope
from rules.bestiary import instantiate, split_collective_name
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def scene():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


# --- 29: the three answers of scope -----------------------------------------------------

def test_the_world_answers_who_exists_and_where():
    """Inform's scope, in three states. Measured against the shipped export: no mayor
    exists among the 256 characters — the offices are law-speaker, harbor-reeve,
    guildmaster — and every city's Formal Power fact names an office and never a person."""
    nobody = scope.look_for(WORLD, "mayor", None, VORMOOR)
    assert nobody["scope"] == scope.NOWHERE
    assert "no mayor in Vormoor" in nobody["line"]
    assert "reeve" in nobody["line"], "the settlement's own record says what it has instead"

    away = scope.look_for(WORLD, "harbour-reeve", None, VORMOOR)
    assert away["scope"] == scope.ELSEWHERE
    assert away["who"] and away["where"] and "not here" in away["line"]

    # A person the world holds in THIS town but not in this room: the nearer answer, and
    # the one the player can act on.
    near = scope.look_for(WORLD, "Drenn Ironvale", None, VORMOOR)
    assert near["scope"] == scope.ELSEWHERE
    assert "Vormoor but not in this room" in near["line"]


def test_a_vague_phrase_is_not_a_question_the_world_can_answer():
    """"the man", "somebody", "a stranger" name no office and no name. A nameless figure
    in a crowd is a fair thing for prose to produce, and scope says nothing about it —
    otherwise the answer to every sentence would be a refusal."""
    for phrase in ("the man", "somebody", "a woman", "the stranger", "a guard"):
        assert scope.look_for(WORLD, phrase, None, VORMOOR)["scope"] == ""


def test_the_trade_gets_no_lecture_about_who_governs():
    """The first version answered "there is no blacksmith in Vormoor, its authority is a
    local reeve", which is a non sequitur: a town plainly has a smith and the world simply
    never wrote one up. The authority clause belongs to offices."""
    smith = scope.look_for(WORLD, "blacksmith", None, VORMOOR)
    assert smith["scope"] == scope.NOWHERE
    assert "authority" not in smith["line"]
    assert "reeve" not in smith["line"]


def test_somebody_standing_here_is_here(scene):
    who = instantiate("guildhand", scene=scene, name="the weaver")
    scene.add(who)
    found = scope.look_for(WORLD, "the weaver", scene, VORMOOR)
    assert found["scope"] == scope.HERE and found["ref"] == who.ref
    assert found["line"] == "", "nothing to say: they are standing here"


def test_the_player_looking_for_somebody_is_read_off_their_own_words():
    assert judgement.person_sought("I turn to find the mayor") == "mayor"
    assert judgement.person_sought(
        "I turn to the mayor of the town and ask him for a reward") == "mayor"
    assert judgement.person_sought("I look for Drenn Ironvale") == "Drenn Ironvale"
    # Not every sentence is a search, and speech is not action.
    assert judgement.person_sought("I attack the guard") == ""
    assert judgement.person_sought("I say 'where is the mayor?'") == ""


def test_nobody_is_created_for_a_person_the_player_named_who_is_not_here(scene):
    """The reported turn, reproduced and then refused. The model answered with a target
    `"mayor"`; validation raised `refs`; `_INVENTED_REF` matched; and because exactly one
    ref was invented, the ref became the actor's NAME — a Warrior-1 called mayor."""
    raw = [{"op": "say", "actor": "pc", "target": "mayor",
            "params": {"words": "what reward do you plan to give?"}}]
    amended = judgement.repair_unknown_refs(
        raw, "I turn to the mayor and ask him for a reward", scene, world=WORLD)
    assert amended is not None
    assert not any(r.get("op") == "spawn" for r in amended), "nobody is created"
    assert amended[-1]["op"] == "narrate_only"
    assert "no mayor in Vormoor" in amended[-1]["params"]["not_here"]
    # And the turn survives with the world's answer printed, not a lost turn and not a
    # person conjured to satisfy the sentence.
    engine = Engine(scene, Dice(seed=1), world=WORLD)
    res = engine.run(engine.validate(amended))
    assert any("no mayor in Vormoor" in o.tell for o in res.outcomes)
    assert [a.name for a in scene.actors.values()] == ["Masta"] or \
        all(a.is_pc for a in scene.actors.values()), "the scene gained nobody"


def test_the_prose_describing_an_arrival_still_creates_them(scene):
    """The narrow exception, and the reason the repair exists: the NARRATION describing
    people arriving is an arrival. The test is whose word it was — the player naming
    somebody is a question, and a question may be answered no."""
    raw = [{"op": "attack", "actor": "pc", "target": "bravo1", "params": {}}]
    amended = judgement.repair_unknown_refs(
        raw, "two guild bravos come round the corner and I swing at one", scene,
        world=WORLD)
    assert amended is not None
    assert amended[0]["op"] == "spawn"


def test_the_brief_states_the_answer_before_the_prose_is_written(scene):
    from gm import prompts

    answer = judgement.absent_answer(scene, WORLD, "I turn to find the mayor")
    assert "no mayor" in answer
    brief = prompts.scene_brief(WORLD, scene, WORLD.get(VORMOOR), [], absent=answer)
    assert "WHO THE PLAYER LOOKED FOR AND IS NOT HERE" in brief
    assert "no mayor" in brief
    quiet = prompts.scene_brief(WORLD, scene, WORLD.get(VORMOOR), [])
    assert "WHO THE PLAYER LOOKED FOR" not in quiet
    from play import views

    assert "absent=judgement.absent_answer" in inspect.getsource(views._finish)


# --- 30: the band that arrives ----------------------------------------------------------

def test_a_band_of_twelve_raiders_books_twelve_and_puts_raiders_on_the_board(scene):
    """The measurement: this sentence booked NOTHING — no ledger entry, no actor, not even
    a `cast_brief` mention — while the bestiary shipped a Raider at CR 2, 29 hp, worth 600
    XP, reachable by `spawn` today and by nothing else."""
    beat = "A band of twelve raiders comes up the road, steel already out."
    added = judgement.note_cast(scene, beat, turn=1)
    assert added == ["raider"], "not 'twelve raider', not nothing at all"
    assert scene.cast[0]["count"] == 12, "the ledger records what the prose said"
    made = judgement.promote_cast(scene, added, beat=beat, world=WORLD)
    bodies = [a for a in scene.actors.values() if not a.is_pc]
    assert made and bodies
    assert all(a.from_template == "raider" for a in bodies)
    assert all(a.hp > 20 for a in bodies), "a Raider, not a 4-hp guildhand"
    # Group 8 left this as four bodies against twelve in the prose and said the cap was the
    # real tension. Group 9 resolved it the way the record said it would: ONE unit of twelve
    # (item 33, tests/test_the_crowd.py). The ledger's number is what the unit is formed from.
    assert len(bodies) == 1
    assert bodies[0].troop is not None and bodies[0].troop.members == 12
    assert "raider ×12" in judgement.cast_brief(scene)


def test_the_number_the_prose_said_is_read_in_full():
    """`_NUMBER_WORDS` stopped at eight and `dozen`; the collectives stopped at "bunch".
    So "a band of twelve raiders" was four, and twelve was neither read nor stripped from
    the name — the ledger held a person called "twelve soldier"."""
    assert judgement._NUMBER_WORDS["twelve"] == 12
    assert judgement._NUMBER_WORDS["score"] == 20
    assert split_collective_name("a band of twelve raiders") == (12, "raider")
    assert split_collective_name("a line of figures") == (4, "figure")
    assert split_collective_name("a column of soldiers") == (6, "soldier")


def test_a_line_of_figures_is_somebody(scene):
    """The reported beat's own words: "a line of figures silhouetted against the gray
    morning light, their forms heavy and armored". It matched nothing, so the board stayed
    empty and there was never a booked word for the next beat to contradict."""
    added = judgement.note_cast(
        scene, "A line of figures crests the hill, their forms heavy and armored.", turn=1)
    assert added and "figure" in added[0]


def test_the_role_word_reaches_the_corpus_but_never_drags_a_species_in():
    """Measured at level 1 before this was written: the chooser answers "bruiser" with a
    **gnoll** bruiser at CR 3, "fighter" with a *gillman* knife-fighter, "veteran" with a
    veteran *buccaneer* and "merchant" with a Tian merchant *sailor*. A CR 3 gnoll walking
    out of a market crowd is not the fiction anybody wrote, so the corpus's pick stands
    only when the block IS the role word."""
    assert judgement.template_for("raider") == "raider"
    assert judgement.template_for("twelve raiders") == "raider"
    assert judgement.template_for("bandit") == "bandit"
    assert judgement.template_for("an armed guard") == "guard"
    for phrase, floor in (("bruiser", "thug"), ("veteran", "thug"),
                          ("merchant", "guildhand"), ("woman", "guildhand"),
                          ("man in the leather apron", "guildhand")):
        assert judgement.template_for(phrase) == floor, phrase
    # The animal cue still wins outright: the corpus answers "guard dog" with a Guard.
    assert judgement.template_for("the guard dog") == "guard dog"
    # One rule, one home: five copies of the cue loop existed before this.
    src = inspect.getsource(judgement)
    assert src.count("for cue, name in _TEMPLATE_CUES:") == 1


def test_a_band_arriving_mid_fight_arrives(scene):
    """Zero bodies if a fight was running, because `promote_cast` returned immediately —
    and a band arriving mid-battle is exactly when it matters. They walk on as bystanders,
    outside the initiative, and the two doors that already exist take them into the fight:
    `joiners` when the beat says they draw, `attacked_by` when it says they strike."""
    foe = instantiate("thug", scene=scene, name="the thug")
    scene.add(foe)
    engine = Engine(scene, Dice(seed=2), world=WORLD)
    engine.run(engine.validate([{"op": "begin_encounter", "because": "a brawl",
                                 "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    assert scene.in_encounter
    beat = "A band of twelve raiders comes up the road."
    added = judgement.note_cast(scene, beat, turn=3)
    made = judgement.promote_cast(scene, added, beat=beat, world=WORLD)
    assert made, "a band arriving mid-fight used to put nobody on the board"
    raiders = [a for a in scene.actors.values() if a.from_template == "raider"]
    assert raiders
    assert all(a.has_state("role.bystander") for a in raiders), "in the room, not the order"
    sides = {r for refs in (scene.sides or {}).values() for r in refs}
    assert not any(a.ref in sides for a in raiders), "nobody is quietly inserted"


def test_a_booked_band_keeps_the_word_it_was_booked_under(scene):
    """The reported drift: the scene opened on "the soldiers ahead of you" and by the next
    beat they were raiders, with nothing comparing the second word to the first."""
    scene.cast = [{"who": "soldier", "turn": 1, "count": 12}]
    text, swapped = judgement.hold_the_booked_word(
        scene, "The raiders ahead of you are forced to halt.")
    assert text == "The soldiers ahead of you are forced to halt."
    assert swapped == ["raiders -> soldiers"]
    # His words are his: a character may call them whatever they like.
    said = "'Those raiders will kill us,' she says."
    assert judgement.hold_the_booked_word(scene, said) == (said, [])
    # Two bands booked is two bands: nothing is renamed.
    scene.cast.append({"who": "raider", "turn": 1, "count": 3})
    both = "The raiders and the soldiers close in."
    assert judgement.hold_the_booked_word(scene, both) == (both, [])
    from gm import agent

    assert "judgement.hold_the_booked_word" in inspect.getsource(agent.GMAgent._groom)


# --- 34: a person invented out of somebody's own words ----------------------------------

def test_dialogue_puts_nobody_in_the_room(scene):
    """Found live 2026-09-19 in group 7's check: "Most just call me the stranger" booked a
    person called **stranger** out of the woman's own words about herself. What a character
    says is not what the room contains — and even a genuine announcement is a warning about
    people who have not arrived."""
    assert judgement.note_cast(
        scene, "She shifts. 'Names are heavy. Most just call me the stranger,' she says.",
        turn=1) == []
    assert scene.cast == []
    assert judgement.note_cast(
        scene, '"Three raiders are coming!" he shouts from the wall.', turn=1) == []
    # The narrator's own sentence still books, and the blanking keeps the offsets so the
    # zone a person was mentioned in is still read off the right words.
    added = judgement.note_cast(
        scene, '"Get back!" she cries. A raider comes through the far door.', turn=1)
    assert added == ["raider"]
    assert scene.cast[0]["zone"] == "far"


def test_the_answer_is_stated_whether_or_not_the_plan_reached_for_anybody(scene):
    """Measured live 2026-09-19, run 2: with the fact in the brief the model stopped
    inventing the mayor and then said nothing about him either — "I find the mayor and grab
    him by the collar" came back as a plain `narrate_only` and a paragraph about the room.
    The reported half was fixed and the asked half was not."""
    out = judgement.answer_the_absent(
        [{"op": "narrate_only", "because": "", "params": {}}],
        "I find the mayor and grab him by the collar", scene, WORLD)
    assert "no mayor in Vormoor" in out[0]["params"]["not_here"]
    engine = Engine(scene, Dice(seed=1), world=WORLD)
    assert any("no mayor" in o.tell for o in engine.run(engine.validate(out)).outcomes)
    # A turn that looked for nobody is untouched, and the answer is never doubled up.
    plain = [{"op": "narrate_only", "params": {}}]
    assert judgement.answer_the_absent(plain, "I wait", scene, WORLD) == plain
    from gm import agent

    assert "judgement.answer_the_absent" in inspect.getsource(agent.GMAgent.plan_turn)


def test_a_description_cut_off_mid_phrase_is_not_a_description(scene):
    """Measured live 2026-09-19: "A man in a heavy, grease-stained leather apron stands
    behind the counter" booked a person called **man in a heavy**, because the comma stood
    where the pattern wanted the noun. The man is a man.

    The comma is the signal and the WORD is not, which the first version of this got wrong
    and the suite caught: "the man in the scarred leather" ends on the same word list and is
    a whole description."""
    assert judgement.note_cast(
        scene, "A man in a heavy, grease-stained leather apron stands behind the counter.",
        turn=1) == ["man"]

    def fresh():
        s = Scene(location_id=VORMOOR)
        s.add(load_pc("fixtures/pc-kesst.json"))
        return s

    # Descriptions that ARE whole still ride along: two men differently described are two
    # men, which is why the tail exists at all.
    assert judgement.note_cast(fresh(), "The man in the leather apron squares off.",
                               turn=1) == ["man in the leather apron"]
    assert judgement.note_cast(fresh(), "A man in the scarred leather steps up.",
                               turn=1) == ["man in the scarred leather"]


def test_the_blanker_keeps_the_length_and_leaves_apostrophes_alone():
    blanked = judgement.narration_quotes_blanked(
        "The guard's hand moves. 'Stay back,' he says. She waits.")
    assert len(blanked) == len("The guard's hand moves. 'Stay back,' he says. She waits.")
    assert "guard's hand moves" in blanked, "an apostrophe is not a quote"
    assert "Stay back" not in blanked
    assert "She waits." in blanked
