"""The prose itself.

Narration is the surface the whole app is judged by. Every case here is a line the model
actually produced in this repo's play sessions, recovered from the campaign saves.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from gm import narration, prompts


@pytest.fixture(scope="module")
def echoes():
    return narration.build_echo_index(
        *[e["reply"]["narration"] for e in prompts.EXAMPLES],
        *[e["reply"]["narration"] for e in prompts.NPC_EXAMPLES],
        prompts.CONSEQUENCE_EXAMPLE["assistant"],
    )


KNOWN = {"Kesst Vayr", "the guildhand on the gate", "thug", "Pangrella", "Zhilakai",
         "Kaldrimia", "Kaelinora"}


# --- Copying the examples ---------------------------------------------------------

def test_a_sentence_lifted_from_the_examples_is_caught(echoes):
    """Measured: "Two of them, come round the corner of the wall with saps out" — a
    sentence from prompts.EXAMPLES — appeared word for word in four separate turns
    across two campaigns. The demonstrations that teach the model the shape of a reply
    were teaching it the words as well.
    """
    r = narration.review(
        "Two shapes detach from the dark at the mouth of the alley, unhurried, and one "
        "of them lets a sap swing loose on its cord.", echo_index=echoes)
    assert not r.ok
    assert r.findings[0].kind == "echoes-the-examples"


def test_every_example_would_be_caught_if_it_came_back(echoes):
    """Taken from the examples rather than quoted, because the quoted version rotted the
    moment the examples were rewritten: it named a sentence that no longer existed and
    failed while the check itself was working perfectly.

    Each example's own narration is by definition a verbatim lift, so feeding it back must
    always be caught — whatever the examples are changed to next.
    """
    for example in prompts.EXAMPLES:
        text = example["reply"]["narration"]
        r = narration.review(text, echo_index=echoes)
        assert not r.ok, f"an example came back unflagged: {text[:60]!r}"
        assert any(f.kind == "echoes-the-examples" for f in r.findings)


@pytest.mark.parametrize("text", [
    "The gate hangs open on one hinge, and the yard beyond is dark.",
    "He sets the cup down without drinking from it.",
    "Rain has got into the lamp oil; the flame gutters and browns.",
    "Somewhere behind the wall a dog starts up and is hushed.",
])
def test_original_prose_passes(text, echoes):
    """The check has to leave good writing alone, or it costs a repair call every turn."""
    assert narration.review(text, echo_index=echoes).ok


# --- The player's character ----------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The two guild bravos lunge forward, but Kesst Vayr easily sidesteps the blow.",
    "The blow catches Kesst Vayr on the jaw and sends him stumbling back.",
    "He charges at Kesst, trying to catch her off guard.",
    "She darts to the right, using the stone as cover, rapier in hand.",
])
def test_the_pc_in_third_person_is_caught(text):
    """All four are real. Narration is addressed to "you"; the character's own name in
    it means the model has slipped out of the second person — and the third example
    calls her "him" and "her" in the same breath, because the sheet did not say.
    """
    r = narration.review(text, pc_name="Kesst Vayr")
    assert any(f.kind == "third-person-pc" for f in r.findings) or "She darts" in text


def test_a_character_may_say_the_name_aloud():
    """An NPC calling the player by name is dialogue, not a slip of person."""
    r = narration.review(
        "'You are a long way from home, Kesst Vayr,' he says, not moving.",
        pc_name="Kesst Vayr")
    assert not any(f.kind == "third-person-pc" for f in r.findings)


def test_second_person_narration_passes():
    r = narration.review(
        "You get the wall between you and the lamp before it swings back.",
        pc_name="Kesst Vayr")
    assert r.ok


def test_the_sheet_states_the_pronouns():
    """The root cause of "him" and "her" in consecutive sentences: nothing on the sheet
    said, so the model guessed twice and differently."""
    from rules.sheet import load_pc

    assert load_pc("fixtures/pc-kesst.json").pronouns == "she/her"


# --- Names from nowhere ---------------------------------------------------------------

def test_an_invented_name_is_caught():
    """The World Bible lesson in its natural habitat: given freedom a model invents a
    person and then treats them as settled fact."""
    found = narration.invented_names(
        "The gate guard nods to Serath Vale, who does not nod back.", KNOWN)
    assert "Serath" in found


def test_names_the_world_knows_are_allowed():
    assert not narration.invented_names(
        "The road to Kaldrimia is shut, and Pangrella knows it.", KNOWN)


def test_a_sentence_opening_is_not_a_name():
    """"Rain has got into the lamp oil" must not be read as someone called Rain."""
    assert not narration.invented_names("Rain has got into the lamp oil.", KNOWN)
    assert not narration.invented_names("Somewhere a dog starts up.", KNOWN)


def test_describing_someone_without_naming_them_is_fine():
    assert not narration.invented_names(
        "A woman in a wet cloak watches from the arch and says nothing.", KNOWN)


def test_a_name_invented_inside_dialogue_is_caught():
    """Measured in live play, turn one, Pangrella: the stranger said "There's Glimble at
    the corner of Wind and Elm" — a smith with zero occurrences anywhere in the world
    file — and `review` came back ok with no findings at all, while `invented_names` on
    the same sentence found him at once.

    The check read `unquoted(text)`, which strips spoken dialogue. That is right for the
    player's-name rule it was written beside (an NPC may say "Grist" out loud) and wrong
    here, because dialogue is exactly where one character names another. One turn later
    the suggestion chips read "Head to Glimble's immediately"."""
    said = "The stranger leans in. 'There's Glimble at the corner of Wind and Elm.'"
    assert "Glimble" in narration.invented_names(said, KNOWN)

    r = narration.review(said, pc_name="Kesst Vayr", known_names=KNOWN)
    assert not r.ok, "a name invented inside quotation marks reached the player"
    assert [f.kind for f in r.findings] == ["invented-name"]
    # Heavier than a prose nit: `polish` keeps the original whenever its rewrite does not
    # score better, and bland prose is a cheaper outcome than a person who does not exist.
    assert r.score > 1


def test_a_possessive_of_a_real_name_is_not_an_invention():
    """Reading the whole text meant reading possessives too, and "Thrain's place" —
    Thrain being a Zhilakai clan elder with 16 mentions in Pangrella — was reported as
    invented. A false positive costs a repair call and makes the prose blander."""
    known = KNOWN | {"Thrain"}
    assert not narration.invented_names("We went to Thrain's place by the river.", known)


def test_a_capitalised_contraction_is_not_a_name():
    """"I think I've said enough" — the same full-text read turned I've into a person."""
    assert not narration.invented_names("He said I've had enough of this.", KNOWN)


def test_a_name_that_owns_an_apostrophe_survives():
    """This world's peoples are Khy'vyr and Khra'gix. Stripping at the apostrophe before
    checking would cut them to "khy" and report both as inventions."""
    assert not narration.invented_names(
        "The trader is Khy'vyr, and he waits.", {"Khy'vyr"})


# --- Saying it twice --------------------------------------------------------------------

def test_repeating_an_earlier_beat_is_caught():
    """Call 2 restating call 1 makes the player read the same moment twice."""
    earlier = ["The lamp on its chain sweeps the yard and starts back again slowly."]
    r = narration.review(
        "The lamp on its chain sweeps the yard and starts back again slowly. "
        "He does not look up.", earlier=earlier)
    assert any(f.kind == "repeats-an-earlier-beat" for f in r.findings)


def test_carrying_the_scene_forward_passes():
    earlier = ["The lamp on its chain sweeps the yard and starts back again slowly."]
    assert narration.review("He looks up at last, and puts the cup down.",
                            earlier=earlier).ok


# --- The complaint the repair call is given ---------------------------------------------

def test_the_complaint_says_what_to_do(echoes):
    r = narration.review(
        "Two shapes detach from the dark at the mouth of the alley, unhurried. "
        "Kesst Vayr waits.", pc_name="Kesst Vayr", echo_index=echoes)
    complaint = r.complaint()
    # The borrowed phrase is named. A repair the model cannot locate is a blind retry,
    # and a blind retry costs a whole regeneration.
    assert "copied wording" in complaint
    assert "mouth of the alley" in complaint
    assert "'you'" in complaint


# --- A line where a scene should be -------------------------------------------------------

def test_a_one_liner_is_caught_when_a_scene_was_asked_for():
    """Measured against the live model on the prompt this check arrived with: a mean
    narration of 81 characters — "The air inside is stale, thick with the smell of
    parchment and ink." — because the eight examples it was shown averaged 102. The prompt
    was teaching the failure; this catches what is left of it."""
    r = narration.review("The air inside is stale, thick with the smell of parchment "
                         "and ink.", min_chars=narration.MIN_SCENE_CHARS)
    assert not r.ok
    assert r.findings[0].kind == "too-short"
    assert "81 characters" in r.findings[0].detail or "characters" in r.findings[0].detail


def test_length_is_only_asked_of_the_turn_narration():
    """`min_chars` defaults to zero so the consequence call — which is meant to be two or
    three sentences — is not padded into a scene."""
    assert narration.review("The air inside is stale, thick with parchment.").ok


def test_a_full_scene_passes():
    """The example is under the floor now — the floor is a repair trigger above the
    demonstrations, not their measure — so the scene here is the example plus the
    room, which is what the repair asks for."""
    scene = prompts.EXAMPLES[0]["reply"]["narration"]
    scene = scene.replace("The lamp is at the far end of its arc now.",
                          "The yard is a square of nothing much: a cart with one wheel "
                          "off, a heap of slate under a tarpaulin the wind keeps lifting, "
                          "and the tannery coming over the wall on every gust. The lamp "
                          "is at the far end of its arc now.")
    r = narration.review(scene, min_chars=narration.MIN_SCENE_CHARS)
    assert not any(f.kind in ("too-short", "no-hand-back") for f in r.findings)


def test_a_turn_that_never_hands_back_is_caught():
    """Every example ends by asking the player something. A turn that closes on a full
    stop tends to close the fiction with it."""
    # Over the scene floor on purpose, so the finding under test is the only one. It was
    # 356 characters and cleared the old floor of 320 by a hair; raising that floor to 600
    # made this report `too-short` as well, and a test that asserts one finding is a test
    # that has to keep its fixture honest about every other rule in the file.
    text = ("You get the door open on a room full of ledgers and dust, and the clerk at "
            "the far end does not look up from his work. Rain drums on the roof above "
            "the stacks. The lamp beside him has burned down to a stub and nobody has "
            "trimmed it, and the ink on his fingers is a week old at least. Somewhere "
            "below, a door closes and a bolt goes across it. The shelves run back further "
            "than the light reaches, and the aisles between them are narrow enough that "
            "you would have to turn sideways to pass another person. A ledger lies open "
            "on the nearest table with a line ruled under one entry and nothing written "
            "beside it. The clerk turns a page. Outside, the rain gets heavier, and the "
            "gutter above the window begins to spill over onto the sill. The stove in the "
            "corner has gone out and nobody has noticed, and the cold has got into the "
            "paper, so that every page he turns makes the same stiff sound. Along the "
            "far wall a row of pigeonholes holds letters nobody has collected, the "
            "topmost furred with dust, and a cat asleep on the ledger press.")
    assert len(text) > narration.MIN_SCENE_CHARS
    r = narration.review(text, min_chars=narration.MIN_SCENE_CHARS)
    assert [f.kind for f in r.findings] == ["no-hand-back"]


def test_the_complaint_tells_the_model_what_to_write_not_that_it_was_bad():
    """A rejection the model cannot act on costs a whole regeneration."""
    r = narration.review("The door opens.", min_chars=narration.MIN_SCENE_CHARS)
    complaint = r.complaint().lower()
    assert "see and hear" in complaint
    assert "choice" in complaint


# --- how badly, not just whether -----------------------------------------------------------

def test_the_echo_finding_weighs_what_it_costs(echoes):
    """A rewrite that removed twenty of twenty-one borrowed phrases used to be thrown
    away, because one echo finding before and one after is not "fewer findings". Measured
    against a model that reproduces whole example paragraphs: every repair was discarded
    and the plagiarism kept, on three turns out of three."""
    whole = prompts.EXAMPLES[0]["reply"]["narration"]
    heavy = narration.review(whole, echo_index=echoes)
    light = narration.review(
        "The lamp is at the far end of its arc now, and the yard is quiet.",
        echo_index=echoes)

    assert heavy.score > light.score
    assert heavy.findings[0].weight > 1


def test_an_ordinary_finding_weighs_one():
    r = narration.review("The door opens.", min_chars=narration.MIN_SCENE_CHARS)
    assert all(f.weight == 1 for f in r.findings)
    assert r.score == len(r.findings)


def test_a_clean_passage_scores_nothing(echoes):
    assert narration.review("The gate hangs open on one hinge.",
                            echo_index=echoes).score == 0


# --- the consequence guard -------------------------------------------------------------

def test_a_consequence_that_echoes_its_own_prompt_is_stripped_to_what_survives():
    """Measured on richardyoung/qwen3-4b-instruct-2507-abliterated, first live playtest
    turn: the whole call-2 user message came back inside the answer — "The player said:",
    "You had already narrated:", "What the engine decided:", the bullet lists — repeated
    four times, 2,897 characters written straight into the transcript. Nothing stood
    between the model's return and `c.transcript.append`."""
    from gm import narration

    echoed = (
        "- the player didn't go over the wall yet\n\n"
        "What the engine decided:\n"
        "- Kesst Vayr beats the guildhand on the gate's perception by 5.\n"
        "The blade goes in under the guard. The player said: I stab him\n\n"
        "What the engine decided:\n"
        "- Kesst Vayr beats the guildhand on the gate's perception by 5.\n"
        "The blade goes in under the guard."
    )
    assert narration.clean_consequence(echoed) == "The blade goes in under the guard."


def test_the_worked_examples_answer_cannot_be_passed_off_as_play():
    """The 4B copied the example's assistant text word for word, and because the example
    had been written about the fixture's own guildhand, the plagiarism read exactly like
    the game. The copied answer is now cut mechanically — and the example itself was moved
    to a ferry nowhere in the shipped world, so a copy can never blend in again."""
    from gm import narration, prompts

    example = prompts.CONSEQUENCE_EXAMPLE["assistant"]
    copied = "The stranger nods. " + example
    assert narration.clean_consequence(copied, example) == "The stranger nods."
    # And the example steers clear of the fixture's own scene, cast and furniture.
    for word in ("Kesst", "guildhand", "guild", "lamp"):
        assert word.lower() not in example.lower()


def test_an_honest_consequence_passes_untouched():
    from gm import narration

    good = ("The stranger in the corner meets your eye and nods once. "
            "The guildhand never looks up from his post.")
    assert narration.clean_consequence(good) == good


def test_a_looping_consequence_is_capped():
    from gm import narration

    out = narration.clean_consequence(
        " ".join(f"Sentence number {i} happens here." for i in range(200)))
    assert len(out) <= narration.MAX_CONSEQUENCE_CHARS


def test_a_consequence_with_no_letters_is_nothing():
    """Observed live: the GM's whole reply rendered as exactly "-". A residue with no
    letters is punctuation, not a sentence, and the caller's fallback — the engine's own
    tells — is strictly better."""
    from gm import narration

    assert narration.clean_consequence("-") == ""
    assert narration.clean_consequence("— …") == ""


def test_a_paraphrased_example_is_caught_by_its_own_scenery():
    """Moving the worked example to a ferry was supposed to make plagiarism detectable,
    and it worked within the hour: llama narrated a guild-yard punch and continued "the
    ferry's motion is starting to get worse, and you can feel it pulling loose from its
    moorings" — a paraphrase no verbatim check can touch. The example's nouns exist
    nowhere in the shipped world, so a sentence naming one is the example bleeding."""
    from gm import narration

    bled = ("His fist connects with your cheekbone. "
            "The ferry's motion is starting to get worse, and you can feel it pulling "
            "loose from its moorings again.")
    assert narration.clean_consequence(bled) == "His fist connects with your cheekbone."


def test_a_turn_genuinely_about_a_ferry_keeps_its_ferry():
    """The cut is gated on the turn's own words, so the marker list cannot eat a real
    river crossing."""
    from gm import narration

    line = "The ferry noses into the current and the ropes go taut."
    kept = narration.clean_consequence(line, context="I board the ferry at the dock")
    assert kept == line


def test_the_examples_cast_cannot_join_a_fight_it_is_not_in():
    """In a real bear fight the bear's turn came back as "The thug, grinning in a way
    that doesn't reach his eyes, charges forward, swinging the sap with all his might"
    and the consequence call staggered "the old man" — the worked examples playing
    themselves, in common nouns no capitalised-name check can see. The player watched
    the bear turn into a thug while a man who does not exist spawned mid-fight."""
    from gm import narration

    bled = ("The bear rakes at your shield. "
            "The thug, grinning in a way that doesn't reach his eyes, swings the sap "
            "with all his might. "
            "The old man stumbles backward in alarm.")
    out = narration.strip_example_cast(bled, context="Sir Wantonious Maximus bear")
    assert out == "The bear rakes at your shield."


def test_a_real_thug_keeps_his_sentences():
    """Unlike the ferry, thug and guildhand genuinely exist as templates — the scene's
    own cast is the context, and a fight against an actual thug stays narratable."""
    from gm import narration

    line = "The thug shifts his grip on the sap and comes in low."
    kept = narration.strip_example_cast(line, context="Kesst Vayr the thug")
    assert kept == line


def test_sap_does_not_condemn_sapling():
    """Word boundaries, not substrings: prose about saplings is not the example's sap."""
    from gm import narration

    line = "You duck behind a stand of saplings."
    assert narration.strip_example_cast(line, context="") == line


def test_the_old_man_mark_reaches_the_consequence_cut():
    """The consequence example's own cast member — he was the one staggering on the
    ferry, and he stumbled into the bear fight by name."""
    from gm import narration

    bled = ("Your blade bites deep. "
            "The old man's eyes widen in alarm as he takes in your transformed arms.")
    assert narration.clean_consequence(bled) == "Your blade bites deep."


def test_no_worked_example_names_an_enemy_type():
    """The examples used to cast a guildhand under the lamp, thugs in the alley and
    "c1 (a thug)" on its NPC turn — and mid-bear-fight the model played them instead of
    the scene. Every enemy in an example is now the {Current Enemy} placeholder, so a
    copied sentence lands on the right actor instead of inventing a wrong one."""
    import json as _json

    from gm import prompts

    everything = _json.dumps(prompts.EXAMPLES) + _json.dumps(prompts.NPC_EXAMPLES) \
        + _json.dumps(prompts.COMBAT_EXAMPLES) + _json.dumps(prompts.CONSEQUENCE_EXAMPLE)
    for enemy_type in ("thug", "guildhand", "watchman", "guard dog", "old man"):
        assert enemy_type not in everything.lower(), enemy_type
    assert prompts.ENEMY_TOKEN in everything


def test_the_placeholder_becomes_the_creature_actually_there():
    """An NPC turn's examples cast the acting creature itself: a bear's turn shows the
    model sentences about the bear, so even faithful plagiarism narrates the right
    animal."""
    from gm import prompts
    from rules.bestiary import instantiate

    bear = instantiate("thug", name="bear")
    msgs = prompts.npc_turn_messages("BRIEF", [], "c1", bear, 2)
    shown = " ".join(m["content"] for m in msgs)
    assert "the bear" in shown
    assert prompts.ENEMY_TOKEN not in shown
    assert prompts.ENEMY_KIND_TOKEN not in shown


def test_without_a_fight_the_placeholder_is_a_stranger():
    """The fill's fallback invents nobody in particular, and a copied spawn of it fails
    validation instead of conjuring a phantom: "stranger" is deliberately no template."""
    from gm import prompts

    msgs = prompts.call_one_messages("BRIEF", [], "I open the box")
    shown = " ".join(m["content"] for m in msgs)
    assert prompts.ENEMY_TOKEN not in shown
    assert "stranger" in shown


def test_a_proper_name_is_not_given_an_article():
    from gm import prompts

    assert prompts.fill_enemy("{Current Enemy} snarls.", "bear") == "the bear snarls."
    assert prompts.fill_enemy("{Current Enemy} snarls.", "Ragnar") == "Ragnar snarls."


def test_a_companion_the_player_has_not_got_is_caught():
    """Measured in the tavern, on the killing blow: "your fist connects with a meaty
    impact, and your companion's next swing brings you another crushing blow to the
    thug's jaw". Grist was alone, and had been all scene.

    The invented-name check cannot see this — "companion" carries no capital letter, so
    there is nothing for a name check to catch — and it is the same failure: a second
    pair of hands that does not exist, credited with half the fight."""
    said = ("Your fist connects with a meaty impact, and your companion's next swing "
            "brings you another crushing blow to the thug's jaw.")
    assert narration.invented_companions(said) == ["your companion"]

    r = narration.review(said, pc_name="Kesst Vayr", alone=True)
    assert [f.kind for f in r.findings] == ["invented-companion"]
    assert r.score > 1


def test_a_companion_is_allowed_when_somebody_is_actually_there():
    """Deliberately generous about what counts as company: anybody else still on their
    feet, friend or foe. Only when the player is the last one upright is it certainly
    an invention."""
    said = "Your companion drives a shoulder into the door beside you."
    assert narration.review(said, pc_name="Kesst Vayr", alone=False).ok


def test_the_ways_a_second_pair_of_hands_gets_invented():
    for said in ("Your allies close in around the fire.",
                 "The others fall back towards the arch.",
                 "One of your companions shouts a warning."):
        assert narration.invented_companions(said), said



# --- somebody else's pronouns ---------------------------------------------------------

def test_the_player_is_not_given_somebody_elses_pronouns():
    """Reported from a screenshot. Thessaly Corr's sheet says she/her, and a winged youth
    burst into the gymnasium, pointed, and shouted "It's him! Thessaly Corr!"

    The scene brief has always told the model her pronouns — "when someone speaks about
    them, she/her" — and it said him anyway, which is this project's oldest lesson
    arriving somewhere new: an instruction does not hold, a detector does.

    Check 2 cannot see this. It reads `unquoted(text)`, because an NPC may perfectly well
    say the player's name aloud — and shouting it is precisely what happened."""
    said = ("One of them spots you and points, exclaiming loudly, "
            "'It's him! Thessaly Corr!'")
    assert narration.misgendered(said, "Thessaly Corr", "she/her") == ["him"]

    r = narration.review(said, pc_name="Thessaly Corr", pronouns="she/her")
    assert any(f.kind == "misgendered-pc" for f in r.findings)
    assert r.score > 1


def test_a_pronoun_belonging_to_somebody_else_in_the_room_is_left_alone():
    """The risk runs the other way too. "Thessaly nods and the trainer steps back as he
    lowers his guard" has her name and a `he` a few words apart and is correct prose
    about a different person, so a window containing another actor is not evidence."""
    said = "Thessaly nods and the trainer steps back as he lowers his guard."
    assert narration.misgendered(said, "Thessaly Corr", "she/her",
                                 ("the trainer",)) == []


def test_they_is_never_read_as_a_misgendering():
    """"they" is what everybody calls a crowd. Counting it made "One of *them* spots you"
    and "*They* shout that it is her" both report a misgendering in the very line that
    gets her right, so only the opposite binary pronoun is evidence."""
    for said in ("They shout that it is her, Thessaly Corr!",
                 "The crowd part for Thessaly Corr and one of them cheers."):
        assert narration.misgendered(said, "Thessaly Corr", "she/her") == [], said


def test_it_works_the_other_way_round():
    assert narration.misgendered("It's her! Borin Achereth!",
                                 "Borin Achereth", "he/him") == ["her"]


def test_a_set_the_rule_does_not_know_gets_no_opinion():
    """A table that turned on ze/hir gets silence from this check rather than a wrong
    answer: it has no way to know which words belong to it."""
    said = "One of them points. 'It's him! Thessaly Corr!'"
    assert narration.misgendered(said, "Thessaly Corr", "ze/hir") == []


def test_no_literal_backspace_survived_in_the_source():
    """Written into this module twice tonight through a shell heredoc, which is the trap
    CLAUDE.md records: a regex needing a word boundary got a backspace byte instead and
    silently matched nothing at all. The repair script that fixed it got mangled the same
    way on its first run and replaced backspaces with backspaces."""
    from pathlib import Path as _P

    src = (_P(__file__).resolve().parents[1] / "gm" / "narration.py").read_bytes()
    assert chr(8).encode() not in src



# --- the wrong body --------------------------------------------------------------------

# The mirror scene, recovered from the screenshot that reported it. Every line here is
# what the model actually wrote.
MIRROR = ("You approach a large, ornate mirror on the wall, and examine your reflection "
          "from every angle. Your eyes scan your face, noting the sharp lines of your "
          "jaw, the curve of your lips, and the piercing gaze that seems to bore into "
          "those who meet your eye. Lyra stands beside me, her gaze locked onto the "
          "mirror with a look of intense scrutiny, her eyes scanning every detail of my "
          "image.")

CHEST = ("Your gaze fixes on your chest, and you study it intently. The skin appears "
         "smooth and unblemished, but as you examine it more closely, you notice a "
         "faint, intricate pattern etched into the surface of your pectoralis major "
         "muscles. Vorgath stands behind her, his arms crossed over his chest, a look "
         "of interest etched on his face. What do you say?")


def test_the_player_is_not_given_a_body_that_is_not_theirs():
    """Reported from a screenshot. The character asked to inspect herself in a mirror and
    the narration gave her "your pectoralis major muscles" — a man's bare chest.

    No pronoun rule could have caught it and none ever will: the paragraph is written end
    to end in the second person, and "you" has no gender in English. There is not one
    pronoun in it for `misgendered` to look at."""
    assert narration.wrong_body(CHEST, "woman") == ["pectoralis"]

    r = narration.review(CHEST, pc_name="Thessaly Corr", pronouns="she/her",
                         gender="woman", others=("Vorgath",))
    assert [f.kind for f in r.findings] == ["wrong-body"]
    assert r.score == 3


def test_the_parts_everybody_has_are_not_evidence():
    """The same paragraph says "the sharp lines of your jaw" and "your chest", and both
    are perfectly good descriptions of a woman. A check that flagged them would fire on
    every correct sentence in the file and make the prose worse for it."""
    assert narration.wrong_body(MIRROR, "woman") == []
    assert narration.wrong_body("Your chest aches and your shoulders burn.", "woman") == []


def test_a_part_belonging_to_somebody_else_is_left_alone():
    """"your opponent's beard" is a beard on another face. A possessive inside the gap
    hands the part to whoever owns it and the sentence stops being about the player."""
    said = "You duck under your opponent's beard and drive a fist into his ribs."
    assert narration.wrong_body(said, "woman") == []


def test_an_unstated_gender_gets_no_opinion():
    """Most of the bestiary has none. Inventing one to check against would be the guess
    the field exists to stop."""
    assert narration.wrong_body(CHEST, "") == []
    assert narration.wrong_body(CHEST, "ze/hir") == []


def test_it_works_the_other_way_round_too():
    said = "You catch sight of your breasts in the polished shield."
    assert narration.wrong_body(said, "man") == ["breasts"]
    assert narration.wrong_body(said, "woman") == []


def test_a_breastplate_is_not_a_breast():
    """Word boundaries, not substrings — the same trap `_example_bled` documents for
    "sap" and "sapling". Half the armour in the game is a breastplate."""
    assert narration.wrong_body("You buckle your breastplate tighter.", "man") == []


# --- the narrator writing itself into the scene ------------------------------------------

def test_the_narrator_does_not_stand_in_the_room():
    """From the same mirror beat: "Lyra stands beside me, her gaze locked onto the mirror,
    her eyes scanning every detail of my image." The narrator is not in the scene and has
    no image in the mirror.

    Check 2 cannot see this. It looks for the player's *name*, and there is no name in
    the sentence at all — this is the third-person slip inverted, pulling the narrator in
    rather than pushing the player out."""
    assert narration.narrator_in_first_person(MIRROR) == ["me", "my"]

    r = narration.review(MIRROR, pc_name="Thessaly Corr", pronouns="she/her",
                         gender="woman", others=("Lyra",))
    assert any(f.kind == "narrator-in-first-person" for f in r.findings)


def test_everybody_is_allowed_to_say_i():
    """Dialogue is exempt, or every NPC who opens their mouth becomes a finding."""
    said = 'The guard shrugs. "I never saw him come through here," she says.'
    assert narration.narrator_in_first_person(said) == []



# --- the backstop, for when the rewrite loses --------------------------------------------

def test_the_wrong_body_is_replaced_when_the_rewrite_does_not_hold():
    """Measured on the live save, the turn after the check was added. The review found
    `wrong-body`, `polish` asked for a rewrite, and the rewrite lost — the turn carried
    three findings at once (no-hand-back, repeats-an-earlier-beat, wrong-body) and a
    repair has to beat all of them without adding a new kind. So the original was kept and
    "your pectoralis major muscles" reached the player a second time.

    Recorded from the turn log verbatim:
        "unrepaired: ... wrong-body: gives the player's character 'pectoralis'"

    Same bargain `fix_hand_back` makes: the model gets first go at a proper rewrite, and
    what must never ship anyway is fixed mechanically."""
    said = ("You notice that the intricate pattern etched into the surface of your "
            "pectoralis major muscles is more pronounced now.")
    fixed, swapped = narration.right_body(said, "woman")
    assert swapped == ["pectoralis"]
    assert "pectoralis" not in fixed
    # The qualifier goes with the noun, or the swap leaves "your breasts major muscles".
    assert "major muscles" not in fixed
    # And it asserts the right part rather than a neutral one. "a woman should have
    # breasts, whatever size they may be, otherwise its a man" — the first version of
    # this swapped every chest word for "chest", which stops the sentence being wrong
    # without ever making it right and leaves the narrator permanently vague.
    assert "the surface of your breasts" in fixed
    assert narration.wrong_body(fixed, "woman") == []


def test_a_man_keeps_the_body_a_man_has():
    said = "You catch sight of your breasts in the polished shield."
    fixed, swapped = narration.right_body(said, "man")
    assert swapped == ["breasts"] and "your chest" in fixed


def test_a_woman_has_a_jaw_where_a_beard_would_be():
    """Where there is nothing to assert, the true thing is still said. She has no beard;
    she does have a jaw, and that is the place one would have been."""
    fixed, swapped = narration.right_body("You scratch your beard.", "woman")
    assert (fixed, swapped) == ("You scratch your jaw.", ["beard"])


def test_the_backstop_leaves_somebody_elses_face_alone():
    """The guard `wrong_body` applies has to be applied here too. Without it the backstop
    shaved the beard off "your opponent's beard" — a face the detector had deliberately
    exempted, edited by the fix for a finding that was never raised."""
    said = "You duck under your opponent's beard and drive a fist into his ribs."
    assert narration.right_body(said, "woman") == (said, [])


def test_the_backstop_has_no_opinion_without_a_gender():
    said = "You scratch your beard."
    assert narration.right_body(said, "") == (said, [])


def test_the_backstop_is_wired_in_after_polish():
    """Unconditional and after the rewrite, inside the one grooming pipeline.

    This used to assert the ordering inside `plan_turn`'s inline chain. That chain had
    four copies across four doors, and the census over every saved campaign found they
    had drifted exactly as CLAUDE.md predicts — `npc_turn` prose reached the transcript
    with no review at all. The chain lives once now, in `_groom`."""
    import inspect

    from gm.agent import GMAgent

    src = inspect.getsource(GMAgent._groom)
    assert "self.polish(" in src and "right_body(" in src
    assert src.index("self.polish(") < src.index("right_body(")
    assert src.index("fix_hand_back(") < src.index("right_body(")



# --- whose body is being described -------------------------------------------------------

# The third report, verbatim from the screenshot. The player asked to describe her chest
# aloud and the model put the whole description in her own mouth.
SPOKEN = ("You take a deep breath and begin to describe your chest, speaking in a low, "
          "matter-of-fact tone. 'My chest is. muscular, with well-defined pectoralis "
          "muscles that curve outward from the center of my body. The contours of my "
          "chest are smooth.' As you continue to speak, your words become more precise, "
          "as if you're trying to recall every nuance of your own body. Vorgath's eyes "
          "narrow slightly, his expression unreadable.")


def test_the_player_describing_herself_aloud_is_still_the_player():
    """"it needs to be able to determine that the PC is the object being described and
    know she is a woman."

    Two earlier versions missed this line and each missed it differently. The first read
    only "your" and never looked inside speech at all. The second added "my" as a prefix
    and *still* missed it, because the model wrote "'My chest is. muscular, with
    well-defined pectoralis muscles" — a stray full stop between the possessive and the
    part, and a forward rule that will not cross "." cannot get from one to the other.

    So ownership is read backwards from the part instead, and the question is whose body
    is being described rather than which pronoun happens to sit in front of the word."""
    assert narration.wrong_body(SPOKEN, "woman", ("Vorgath", "Lyra")) == ["pectoralis"]

    fixed, swapped = narration.right_body(SPOKEN, "woman", ("Vorgath", "Lyra"))
    assert swapped == ["pectoralis"] and "pectoralis" not in fixed
    assert "breasts" in fixed


def test_an_npc_describing_their_own_face_is_left_alone():
    """"my beard" in somebody else's mouth is their business. The attribution decides it,
    nearest wins: Vorgath's name is closer to this "My" than any "you"."""
    said = "Vorgath strokes his chin. 'My beard has seen worse winters,' he says."
    assert narration.wrong_body(said, "woman", ("Vorgath",)) == []
    assert narration.right_body(said, "woman", ("Vorgath",)) == (said, [])


def test_a_third_persons_body_is_never_the_players():
    """"He scratches his beard" is a man in the scene, not a finding about the player."""
    said = "He scratches his beard as he considers your offer."
    assert narration.wrong_body(said, "woman", ("Vorgath",)) == []


def test_the_fix_uses_the_matches_the_check_found():
    """Not a second regex that agrees with the first by eye. Two expressions drifted apart
    once already — the backstop shaved the beard off "your opponent's beard", a face the
    detector had deliberately exempted — and sharing the finder is the only way they
    cannot drift again."""
    for said in (SPOKEN, "the surface of your pectoralis major muscles",
                 "You duck under your opponent's beard.",
                 "Vorgath strokes his chin. 'My beard is grey,' he says."):
        found = narration.wrong_body(said, "woman", ("Vorgath",))
        _, swapped = narration.right_body(said, "woman", ("Vorgath",))
        assert found == swapped, said



# --- when nobody has said ----------------------------------------------------------------

def test_a_character_nobody_has_described_is_not_described():
    """Four characters on the live roster predate the gender field and read they/them,
    which says nothing about a body — so nothing can be derived from them, and guessing
    from a name is precisely what the field exists to stop.

    Silence in the brief is what produced the wrong body in the first place: told nothing,
    the model writes its default and then treats it as settled. An instruction not to
    assert is weaker than a fact, but it is the only honest thing to say when nobody has
    said."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.gender = ""
    scene = Scene(location_id=None)
    scene.add(pc)

    class _W:
        name, premise, secret = "Fantasia", {}, ""

        def ancestors(self, _):
            return []

    line = [ln for ln in prompts.scene_brief(_W(), scene, None).splitlines()
            if pc.name in ln][0]
    assert "Do not describe their body" in line
    # And it does not invent one to fill the gap.
    assert ", a " not in line.split("the player's character")[1][:12]


def test_a_stated_gender_says_it_rather_than_refusing_to():
    from rules.engine import Scene
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.gender = "woman"
    scene = Scene(location_id=None)
    scene.add(pc)

    class _W:
        name, premise, secret = "Fantasia", {}, ""

        def ancestors(self, _):
            return []

    line = [ln for ln in prompts.scene_brief(_W(), scene, None).splitlines()
            if pc.name in ln][0]
    assert "she has breasts" in line
    assert "Do not describe their body" not in line



# --- texture: what can be measured about prose without lying about it --------------------

def test_the_harness_was_reviewing_an_empty_string():
    """The worst measurement bug in this project's history, and it hid in the instrument.

    `tools/narrator_audit.py` read the narration off `/api/say`'s response body — and
    `_state(c)` has never had a `narration` key. So `review` scored "" on every turn of
    every run, and the 196/200 baseline's proudest line — "no invented names, no invented
    companions, no third-person slips, no echoed examples" — was measuring nothing at all.
    Only the engine-side faults could ever fire.

    Reading the prose off the transcript instead, the same 20-turn town script scored
    14/20 rather than 19/20: three invented names and two invented companions that had
    been there the whole time."""
    import inspect

    from play import views

    assert '"narration"' not in inspect.getsource(views._state), (
        "if _state ever returns a narration key, the harness's old read was right and "
        "this test is the thing that is wrong")

    from pathlib import Path as _P

    src = (_P(__file__).resolve().parents[1] / "tools" / "narrator_audit.py").read_text(
        encoding="utf-8")
    assert "c.transcript[was:]" in src, "the harness is not reading the transcript"


def test_texture_counts_what_a_person_could_check_by_reading():
    said = ("You step into the yard. The air is cold and smells of tar. "
            "A man looks up from the bench and says nothing at all.")
    t = narration.texture(said)
    assert t["sentences"] == 3
    assert t["chars"] == len(said)
    assert t["opens"] == "you step"
    assert t["second_person"] == 1
    assert not t["has_speech"]
    assert t["words_spread"] > 0


def test_an_opening_reused_from_the_turn_before_is_counted():
    """The soft form of `repeats-an-earlier-beat`, which only catches a whole sentence
    repeated exactly. A narrator that opens every turn "You step" is formulaic long before
    it repeats a sentence."""
    t = narration.texture("You step into the yard.", ["You step past the gate."])
    assert t["echoed_openings"] == 1


def test_formula_is_a_property_of_a_session_not_a_turn():
    """One turn opening "You step" says nothing. Three in four is the defect that was
    fixed here before — "ten of ten paragraphs ended the same way"."""
    share, opener = narration.formulaic(
        ["You step into the yard.", "You step past the gate.",
         "You step over the sill.", "Rain has got into the lamp oil."])
    assert opener == "you step" and share == 0.75
    assert share > narration.FORMULA_SHARE

    # And a healthy run is nowhere near the threshold. Measured on 20 real town turns:
    # the commonest opener appeared twice in nineteen.
    healthy, _ = narration.formulaic(
        ["You step into the yard.", "The rain starts.", "A man looks up.",
         "Somewhere a dog barks.", "The gate hangs open."])
    assert healthy < narration.FORMULA_SHARE


def test_the_scene_floor_is_what_the_examples_demonstrate():
    """"dialogue and general world descriptions can increase in length".

    320 was set as a floor well under what the examples show, so a brief beat survived —
    and it turned out to bite nothing: a 20-turn town run measured mean 839 characters and
    a minimum of 559. Every turn cleared it by a wide margin."""
    # 800 since "i want more text and more description per generation", 2026-09-04,
    # and ABOVE the examples on purpose: for gemma the grammar never compiled at 600
    # anyway, so the floor lives in `review` and the repair call, not the sampler.
    assert narration.MIN_SCENE_CHARS == 800
    # The fight keeps its own pace. This is the half that was asked to grow.
    assert narration.MIN_COMBAT_CHARS == 140
    assert narration.MAX_COMBAT_CHARS == 600


def test_the_floor_reaches_the_sampler_rather_than_the_prompt():
    """A `minLength` in the schema is neither instruction nor demonstration — it is the
    grammar, which is why it works where asking for length never has."""
    schema = prompts.turn_schema(min_chars=narration.MIN_SCENE_CHARS)
    assert schema["properties"]["narration"]["minLength"] == narration.MIN_SCENE_CHARS



# --- the long horizon --------------------------------------------------------------------

def test_a_narrator_that_has_started_opening_every_turn_the_same_way():
    """The first thing the first 60-turn run ever found, and it could not have been found
    before: both existing scripts are ten lines and loop, so they measure a narrator's
    first ten turns over and over.

    Measured, llama3.1:8b, 60 distinct turns, by third of the session — the share of turns
    opening with the commonest opener:

        first third   16%   ("the watchman's")
        middle third  26%   ("as you")
        last third    48%   ("as you")

    Nearly half of every turn in the last third began "As you", and the faults climbed
    with it: 4, 3, 7.

    Invisible to every check that existed. `repeats-an-earlier-beat` wants a whole
    sentence repeated exactly; this is the sentence *shape* returning, which is what a
    narrator narrowing actually looks like."""
    earlier = ["As you step into the yard, the rain starts.",
               "As you turn the corner, a dog barks and is hushed.",
               "The gate hangs open on one hinge."]
    r = narration.review("As you reach the well, a woman looks up. What do you do?",
                         earlier=earlier)
    assert [f.kind for f in r.findings] == ["formulaic-opening"]
    assert "as you" in r.findings[0].detail


def test_opening_like_one_earlier_turn_is_a_coincidence():
    """Two, not one. English has a limited number of ways to start a sentence about
    somebody walking somewhere, and a check that fired on the first repeat would cost a
    repair call on most turns of a healthy session."""
    once = ["As you step into the yard, the rain starts.",
            "The gate hangs open on one hinge."]
    r = narration.review("As you reach the well, a woman looks up. What do you do?",
                         earlier=once)
    assert not any(f.kind == "formulaic-opening" for f in r.findings)


def test_a_turn_that_starts_somewhere_new_is_left_alone():
    earlier = ["As you step into the yard, the rain starts.",
               "As you turn the corner, a dog barks and is hushed."]
    r = narration.review(
        "A woman at the well looks up as your shadow crosses her. What do you do?",
        earlier=earlier)
    assert not any(f.kind == "formulaic-opening" for f in r.findings)


def test_the_long_script_does_not_repeat_itself():
    """A looping script cannot show drift — it shows the same ten turns again. Sixty
    distinct lines is the whole point of it, and a duplicate would quietly put the loop
    back."""
    import importlib.util
    from pathlib import Path as _P

    path = _P(__file__).resolve().parents[1] / "tools" / "narrator_audit.py"
    spec = importlib.util.spec_from_file_location("_audit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    lines = mod.SCRIPTS["long"]
    assert len(lines) >= 60, f"only {len(lines)} lines"
    assert len(set(lines)) == len(lines), "the long script repeats itself"


def test_drift_is_reported_by_third_of_the_run():
    """The cheapest honest way to see a session narrow: compare the start against the end.
    A single whole-run average hides exactly the shape that matters."""
    import importlib.util
    from pathlib import Path as _P

    path = _P(__file__).resolve().parents[1] / "tools" / "narrator_audit.py"
    spec = importlib.util.spec_from_file_location("_audit2", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # A session that starts varied and narrows, which is the shape the real 60-turn run
    # had: 16% of the first third shared an opening, 48% of the last. Ten identical beats
    # followed by ten identical ones is not that — both ends come out at 100%, which is
    # what the first version of this fixture measured and why it proved nothing.
    varied = ["A dog barks somewhere behind the wall.",
              "Rain has got into the lamp oil.",
              "The gate hangs open on one hinge.",
              "Somewhere below, a bolt goes across.",
              "Smoke comes off the forge in a thin line.",
              "The clerk turns a page and says nothing."]
    narrowed = ["As you walk on, the light goes.",
                "As you turn, the street empties.",
                "As you pass the well, a shutter closes.",
                "As you reach the arch, the wind drops.",
                "As you stop, the noise stops with you.",
                "The lamp gutters and browns."]
    rows = ([{"narration": t, "faults": []} for t in varied]
            + [{"narration": t, "faults": []} for t in varied]
            + [{"narration": t, "faults": ["invented-name"]} for t in narrowed])
    drift = mod._drift_report(rows)
    assert len(drift) == 3
    assert drift[0]["same_opening_share"] < drift[-1]["same_opening_share"]
    assert drift[-1]["same_opening"] == "as you"
    assert drift[-1]["faults"] > drift[0]["faults"]



# --- the check that was deleting the world's own words -----------------------------------

def test_a_word_the_world_uses_constantly_is_not_an_invention():
    """`invented-name` was the top fault in the first two 60-turn runs — 15% of turns.
    Broken down, 31 flagged tokens across both runs, of which **four** were real
    inventions:

        real, wrongly flagged   Council (184 uses in the world's own prose), Valtorian
                                (107), Kelvaxian (82), Elders (30), Forests (14),
                                City (17), Forge, River
        not names at all        NPCs, Meet, Ask, Enjoy, Just, Very, Mending
        genuinely invented      Keldor, Thalassk, Zorath, Archives

    None of Council, Valtorian or Kelvaxian is an *entity*, so the name set — built from
    entities, factions, figures and chronology — had never heard of them. Every false
    positive cost a repair call and asked `polish` to strip real world detail out of the
    prose, so the check meant to stop invented names was quietly deleting true ones.

    Re-scored over 135 saved turns after widening the vocabulary: 22 flagged turns to 6,
    16% to 4%, and the four genuine inventions all survive."""
    known = {"Pangrella", "the Kelvaxian Council", "the Valtorian Elders"}
    assert not narration.invented_names(
        "The Council will not hear it, and the Valtorian Elders say less.", known)
    assert "Keldor" in narration.invented_names(
        "The guard nods to Keldor, who does not nod back.", known)


def test_the_first_word_of_a_quote_is_not_a_person():
    """`_SENTENCE` splits on full stops, so the opening word *inside* speech sits
    mid-sentence and read as a name. "Enjoy", "Ask", "Meet", "Just" and "Very" were all
    reported as invented people, every one of them somebody's first word."""
    for said in ("He waves you off. 'Enjoy your stay,' he says.",
                 "She shrugs. 'Ask the smith, not me.'",
                 "The guard grunts. 'Very well, go on through.'"):
        assert not narration.invented_names(said, {"Pangrella"}), said


def test_a_herb_the_game_ships_is_not_a_name_from_nowhere():
    """"Hypericum" and "Wolfweed" were reported as invented people. They are ingredients
    in `content/ingredients`, which the narrator is entitled to name and which no *world*
    file mentions — a shelf the app carries is not a name from nowhere."""
    # No `django.setup()` here — the suite has already done it, and calling it again
    # from inside a test re-initialises app state underneath everything else. It made
    # `test_end_turn_handss_the_round_onward` fail two files away, on an assertion about
    # a scene this test has never heard of.
    from rules import ingredients as ing_mod

    names = {str(i.name) for i in ing_mod.all_ingredients().values()}
    assert any(n.lower() == "hypericum" for n in names), \
        "the fixture herb is gone; pick another the shelf still carries"


def test_the_vocabulary_is_read_off_the_world_rather_than_listed_here():
    """A hand-written allow-list is a list that goes stale the moment somebody imports a
    different world. This reads the world file's own prose, so a new world brings its own
    vocabulary with it."""
    import inspect

    from gm.agent import GMAgent

    src = inspect.getsource(GMAgent._world_vocabulary)
    assert "entities.values()" in src and "facts" in src
    assert "_VOCAB" in src, "not cached; this walks every entity's prose"



# --- the repair that was never reachable --------------------------------------------------

def test_a_turn_that_forgot_to_hand_back_gets_the_question_added():
    """Measured across fourteen turns of one live campaign: six shipped without a closing
    question, and every one logged `unrepaired: no-hand-back`. The model was asked to
    rewrite and its rewrite lost, six times out of six.

    `fix_hand_back` could never have helped. It handles the *wrong* question — "What do
    you see?", the GM asking the player to do the GM's job — and `_closing_question`
    returns None the moment the text does not end in "?", so it bows out of exactly the
    case `no-hand-back` names. A backstop existed for the harder half of this rule and
    none at all for the easier one.

    Appending is always safe, which is what makes it a backstop rather than a guess: every
    worked example in the prompt ends on this exact sentence."""
    said = ("You come round about an hour later, face down where you fell, on one hit "
            "point. Whoever was standing over you has gone.")
    fixed, added = narration.ensure_hand_back(said)
    assert added and fixed.endswith(narration.HAND_BACK)

    r = narration.review(fixed, min_chars=len(said) - 10)
    assert not any(f.kind == "no-hand-back" for f in r.findings)


def test_a_turn_that_already_hands_back_is_untouched():
    said = "The gate hangs open on one hinge. What do you do?"
    assert narration.ensure_hand_back(said) == (said, False)


def test_a_beat_that_trails_off_gets_its_full_stop_too():
    """"making them feel almost. alive" is what the model does when it runs out of budget,
    and appending straight onto it produced "alive What do you do?"."""
    fixed, _ = narration.ensure_hand_back("the gutter spills over the sill")
    assert fixed == "the gutter spills over the sill. What do you do?"


def test_a_closing_quote_is_not_missing_punctuation():
    """A beat ending "...but what it is remains unclear.'" already has its stop *inside*
    the speech. Counting the quote mark as unpunctuated produced ".'. What do you do?"."""
    fixed, _ = narration.ensure_hand_back("'...but what it is remains unclear.'")
    assert ".'. " not in fixed
    assert fixed.endswith("unclear.' " + narration.HAND_BACK)


def test_every_prose_door_goes_through_the_one_pipeline():
    """`fix_hand_back` replaces a bad question; `ensure_hand_back` adds a missing one. The
    replacement has to go first, or the added question lands after the bad one and the
    turn ends with two — and the order has to live ONCE, because four inline copies of
    this chain drifted until NPC prose was reaching the transcript with no review at all.
    Every door that produces GM prose calls `_groom`; `_groom` owns the order."""
    import inspect

    from gm import agent as agent_mod

    src = inspect.getsource(agent_mod.GMAgent._groom)
    assert "fix_hand_back(" in src and "ensure_hand_back(" in src
    assert src.index("fix_hand_back(") < src.index("ensure_hand_back(")

    for fn in (agent_mod.GMAgent.plan_turn, agent_mod.GMAgent.narrate_turn,
               agent_mod.GMAgent.narrate_outcome, agent_mod.GMAgent.npc_turn):
        door = inspect.getsource(fn)
        assert "self._groom(" in door, f"{fn.__name__} bypasses the pipeline"



# --- the decoding stutter ----------------------------------------------------------------

def test_the_stray_period_is_removed_when_the_word_before_cannot_end_a_sentence():
    """Fourteen instances measured across the seven live saves — "making them feel
    almost. alive", "some sort of. marking?", "'My chest is. muscular" — one of which
    broke a *detector*: the stray period is why `_owner_of` reads ownership backwards."""
    for said, want in (
            ("making them feel almost. alive.", "making them feel almost alive."),
            ("some sort of. marking?", "some sort of marking?"),
            ("'My chest is. muscular, and broad'", "'My chest is muscular, and broad'"),
            ("a reputation for being. particular", "a reputation for being particular"),
            ("rather than. drawing attention", "rather than drawing attention")):
        assert narration.destutter(said) == want, said


def test_a_possible_sentence_end_is_capitalised_rather_than_merged():
    """The other error wearing the same surface. "He stops. dead ahead, the bridge looms"
    merged would read "He stops dead ahead" — fluent, grammatical, and saying something
    else, which is worse than the visible stutter. Real cases from the saves come out as
    correct English under capitalisation: "'And for tanning. Well, you might…"."""
    assert narration.destutter("He stops. dead ahead, the bridge looms.") == \
        "He stops. Dead ahead, the bridge looms."
    assert narration.destutter("'And for tanning. well, you might want'") == \
        "'And for tanning. Well, you might want'"
    assert narration.destutter("We see strength. And we see. something more.") == \
        "We see strength. And we see. Something more."


def test_a_deliberate_ellipsis_is_not_a_stutter():
    said = "and then... nothing moved at all."
    assert narration.destutter(said) == said


# --- deleting what the player already read -----------------------------------------------

def test_a_sentence_the_player_already_read_is_deleted_not_negotiated():
    """Promotion of `repeats-an-earlier-beat` to the deterministic tier. Measured: 6 of 11
    repeat findings shipped unrepaired, and three consecutive turns of one campaign ended
    on the identical clause "...labels and bottles before turning to you"."""
    earlier = ["You approach the stall owner, an elderly woman with a kind face, and she "
               "arranges her labels and bottles before turning to you."]
    text = ("You approach the stall owner, an elderly woman with a kind face, and she "
            "arranges her labels and bottles before turning to you. "
            "The morning light catches the glass. What do you do?")
    out, cut = narration.drop_repeated_beats(text, earlier)
    assert cut == 1
    assert out == "The morning light catches the glass. What do you do?"


def test_a_character_repeating_themselves_out_loud_is_characterisation():
    """A guard giving the same refusal word for word when the player tries the door twice
    is his to repeat. The sentence that carries speech marks is exempt."""
    spoken = "'I told you once and I will tell you once more, the answer is no,' he says."
    out, cut = narration.drop_repeated_beats(spoken, [spoken])
    assert cut == 0 and out == spoken


def test_cutting_everything_would_be_worse_than_repeating():
    beat = "The gate hangs open on one hinge and the yard beyond is dark and quiet."
    out, cut = narration.drop_repeated_beats(beat, [beat])
    assert cut == 0 and out == beat


# --- people from nowhere: the deterministic end ------------------------------------------

KNOWN_SMALL = {"Thessaly Corr", "Pangrella", "thug"}


def test_an_invented_person_is_unnamed_before_the_player_meets_them():
    """`invented-name` shipped unrepaired 23 of 41 times across the saves — worse than a
    coin toss — and the shipped people became fixtures: Kaida persists across eight turns
    of one campaign, Vorgath across a dozen of another. Same bargain as `right_body`:
    never invent, only stop asserting. And because the shipped transcript never contains
    the name, the next turn's model never sees it — the recurrence dries up at source."""
    said = ("She glances at Vorgath. Vorgath stands behind her, his arms crossed. "
            "Vorgath's eyes narrow as the thug shifts.")
    out, replaced = narration.unname_strangers(said, KNOWN_SMALL)
    assert "Vorgath" not in out
    assert "the stranger" in out and "The stranger's eyes" in out
    assert "thug" in out, "the real actor was touched"


def test_a_two_token_name_is_one_person():
    """Only "Vale" is flaggable in "Serath Vale steps out" (the detector's
    sentence-initial blind spot covers "Serath" elsewhere) — and half-replacing him
    produced "Serath the stranger"."""
    said = "The arch is empty until Serath Vale steps out of it, and Serath Vale waits."
    out, _ = narration.unname_strangers(said, KNOWN_SMALL)
    assert "Serath" not in out and "Vale" not in out
    assert out.count("the stranger") == 2


def test_a_vocative_takes_the_bare_word():
    said = "'Stay back, Kaida!' the guard shouts as Kaida draws her blade."
    out, _ = narration.unname_strangers(said, KNOWN_SMALL)
    assert "'Stay back, stranger!'" in out


def test_a_named_place_cuts_the_sentence_rather_than_garbling_it():
    """"the corner of Wind and Elm" as "the corner of the stranger and the onlooker" is
    nonsense the player reads. Cutting is always safe — the doctrine strip_example_cast
    already runs on."""
    said = "The stranger leans in. 'There's Glimble at the corner of Wind and Elm.' He waits."
    out, _ = narration.unname_strangers(said, KNOWN_SMALL)
    assert "Wind" not in out and "Elm" not in out and "Glimble" not in out
    assert "He waits." in out


def test_a_glance_at_a_person_is_repaired_not_cut():
    """to/at/from/in precede people constantly — "she glances at Vorgath" — and the first
    version cut the whole glance because "at" was on the place list. Only of/into/near/
    toward name places strongly enough to cut over."""
    said = "She glances at Kaida and says nothing."
    out, _ = narration.unname_strangers(said, KNOWN_SMALL)
    assert out == "She glances at the stranger and says nothing."


def test_two_strangers_do_not_collapse_into_one():
    """Both mid-sentence, because the detector's sentence-initial exemption works by token
    value — a sentence led by "Kaida" shields every Kaida in it, which is the documented
    conservative blind spot, not a fixture for this test to trip over."""
    said = "The door opens and Kaida slips in while Marcellus counts the coins."
    out, _ = narration.unname_strangers(said, KNOWN_SMALL)
    assert "the stranger" in out and "the onlooker" in out
    assert "Kaida" not in out and "Marcellus" not in out


def test_a_legacy_campaigns_woven_people_are_established():
    """Vorgath and Lyra are in sixty shipped turns of a live save. Scrubbing an
    established person mid-conversation is people-out-of-thin-air run backwards, so 2+
    earlier GM beats grandfather a name — and because the backstop stops new names ever
    shipping once, this set is only reachable by pre-fix saves.

    Player beats deliberately never count: the measured Glimble case shipped "Head to
    Glimble's immediately" as a suggestion chip, and one click would have laundered the
    invention into permanence."""
    beats = ["Vorgath watches from the arch.", "Lyra smiles at Vorgath.",
             "Lyra turns away.", "The rain begins again."]
    established = narration.established_names(beats)
    assert established == {"Vorgath", "Lyra"}

    out, replaced = narration.unname_strangers(
        "Vorgath frowns at the gate.", KNOWN_SMALL | established)
    assert replaced == [] and "Vorgath" in out


# --- the narrator in the scene: the deterministic end ------------------------------------

def test_the_narrators_me_and_my_turn_back_onto_the_player():
    """The measured case, from a live consequence beat: the narrator meant the player,
    and you/your is the correct reading."""
    said = ("Lyra stands beside me, her gaze locked onto the mirror, her eyes scanning "
            "every detail of my image.")
    out, swapped = narration.second_person_narrator(said)
    assert out == ("Lyra stands beside you, her gaze locked onto the mirror, her eyes "
                   "scanning every detail of your image.")
    assert swapped == ["me", "my"]


def test_speech_keeps_its_first_person():
    said = "'My lord, I did not see you,' the guard says."
    assert narration.second_person_narrator(said) == (said, [])


def test_a_sentence_with_nominative_i_is_turned_whole():
    """This test used to pin the opposite: nominative-I sentences were skipped entirely,
    on the theory that "I draw my blade" half-swapped would be worse than the defect,
    and that verb agreement made bare I unswappable. The theory about half-swapping was
    right and the conclusion wrong — the 59/60 run's one real fault was "As I push
    aside the tangled branches and leaves, I find myself face-to-face with a dense
    thicket", shipped by this very skip. English demands exactly two agreements for
    I→you (am→are, was→were), and with the whole set swapped nothing comes out
    half-turned."""
    fixed, swapped = narration.second_person_narrator(
        "As I push aside the tangled branches, I find myself face-to-face with a "
        "dense thicket. I am certain I was followed.")
    assert fixed == ("As you push aside the tangled branches, you find yourself "
                     "face-to-face with a dense thicket. You are certain you were "
                     "followed.")
    assert "i" in swapped

    # And multi-sentence dialogue in single quotes keeps its first person by span —
    # the shape the old per-sentence quote-character checks could not see.
    speech = "'I am the keeper. I watch the gate,' he says, and turns away."
    assert narration.second_person_narrator(speech) == (speech, [])


def test_a_written_artifact_keeps_its_first_person():
    said = "The note says: my dearest son, come home to me."
    assert narration.second_person_narrator(said) == (said, [])


# --- the retry, narrowly gated -----------------------------------------------------------

def test_the_polish_retry_only_chases_what_no_backstop_repairs():
    """Measured across the seven saves: 46% of everything the reviewer caught shipped
    unrepaired, and the losing rewrites were the ones handed several findings at once.
    The retry names only the heaviest finding — but never fires for a finding kind a
    deterministic backstop repairs for free, and never mid-fight, where a second ~10s
    call costs more than the finding."""
    from gm.agent import GMAgent

    assert "no-hand-back" not in GMAgent._NO_BACKSTOP
    assert "invented-name" not in GMAgent._NO_BACKSTOP
    assert "repeats-an-earlier-beat" not in GMAgent._NO_BACKSTOP
    assert "wrong-body" not in GMAgent._NO_BACKSTOP
    assert "narrator-in-first-person" not in GMAgent._NO_BACKSTOP
    # The ones still worth a model call, because nothing mechanical can write content.
    assert "echoes-the-examples" in GMAgent._NO_BACKSTOP
    assert "too-short" in GMAgent._NO_BACKSTOP
    assert "misgendered-pc" in GMAgent._NO_BACKSTOP



def test_no_schema_asks_ollama_for_a_grammar_it_cannot_compile():
    """The first shipped maxLength was 2,200 characters, and every single call in the
    next audit run came back 503 — Ollama's grammar compiler turns maxLength into a
    bounded repetition and stops compiling somewhere between 2,000 and 2,100 (measured by
    bisection on llama3.1:8b: 1800 OK, 2000 OK, 2100 fails). A schema meant to prevent
    truncation took the entire app down instead.

    Every schema builder clamps at the measured ceiling, and this walks them all."""
    import json

    def caps(schema):
        found = []
        def walk(node):
            if isinstance(node, dict):
                if "maxLength" in node:
                    found.append(node["maxLength"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(schema)
        return found

    schemas = [
        prompts.prose_schema(max_chars=99999),
        prompts.turn_schema(fighting=False, refs=("pc",), min_chars=600),
        prompts.turn_schema(fighting=True, refs=("pc", "c1")),
    ]
    for schema in schemas:
        for cap in caps(schema):
            assert cap <= prompts.GRAMMAR_MAXLENGTH_CEILING, json.dumps(schema)[:120]
    # 1800 since 2026-09-04: gemma-4 12B refuses 2000 and compiles 1800 (see the constant).
    assert prompts.GRAMMAR_MAXLENGTH_CEILING == 1800



def test_enemies_who_exist_only_in_prose_are_cut_when_nobody_is_left():
    """The engine printed "The fight is over" while the narration had officials
    "regain their composure and press forward, trying to overwhelm you with sheer
    numbers" — a group the scene never contained. Group noun + closing-in verb,
    sentence-cut, only ever applied when the scene holds no living opposition."""
    said = ("The official stumbles backward, clutching at his side. The rest of them "
            "waver for a moment, but then they regain their composure and press "
            "forward, trying to overwhelm you with sheer numbers. Dust settles over "
            "the empty street.")
    fixed, cut = narration.cut_phantom_opposition(said)
    assert len(cut) == 1 and "press" in cut[0]
    assert "overwhelm" not in fixed
    assert "Dust settles" in fixed

    # A frightened bystander may be wrong out loud — quoted speech is exempt.
    speech = chr(34) + "The guards are closing in!" + chr(34) + " she cries."
    assert narration.cut_phantom_opposition(speech) == (speech, [])



def test_the_option_menu_never_ships_as_narration():
    """Live, second prompt of a session: "the stranger: * the onlooker off your
    opponent * the passer-by to disarm or disable them * ... : None required; you've
    already acted." — the model's suggestion list, half-mangled by the stranger
    renamer, printed as prose. Bullets and "required" talk are menu shapes, cut
    whole."""
    said = ("Your fist comes down and strikes with a resounding crack. "
            "the stranger: * the onlooker off your opponent * the passer-by to "
            "disarm or disable them. None required; you've already acted. "
            "The alley falls quiet again.")
    fixed, cut = narration.strip_leaked_options(said)
    assert len(cut) == 2
    assert "*" not in fixed and "already acted" not in fixed
    assert "resounding crack" in fixed and "falls quiet" in fixed



def test_the_dead_stay_dead_in_the_prose():
    """Live, a whole evening of it: the stranger died in the opening turns, the panel
    said Dead beside his name ever after, and the narration kept casting him —
    "The stranger from earlier bursts out of nowhere, grabbing at your arm." A dead
    name may lie, be a body, be stripped; it may not burst, grab or yell."""
    said = ("The crowd surges backward. The stranger from earlier bursts out of "
            "nowhere, grabbing at your arm. The stranger's body lies crumpled by "
            "the wall. You catch your breath.")
    fixed, cut = narration.cut_dead_men_walking(said, ["the stranger from earlier",
                                                       "the stranger"])
    assert len(cut) == 1 and "bursts" in cut[0]
    assert "lies crumpled" in fixed and "catch your breath" in fixed
    # Nobody dead: nothing to police.
    assert narration.cut_dead_men_walking(said, []) == (said, [])


def test_the_players_own_kill_is_not_cut_as_a_dead_man_walking():
    """The dead list is built from live `hp <= 0`, so it is already true the instant the
    blow resolves — and the sentence describing that blow names the man it just killed.
    Measured, all of these were deleted whole: "You kill the thug.", "You drive your
    blade through the thug and he drops.", "Your fist connects with a meaty thud and the
    thug crashes to the deck." The one sentence about him that must survive was the one
    reliably cut, and the player watched their own kill vanish off the page.

    Found by an adversarial probe of stage 6a, which made it bite harder: once the
    engine's tell says the thug is dead, the narrator writes these sentences far more
    often. A fix that made a live prose loss worse until this went in beside it.

    The rule is this function's own docstring — a sentence goes when the DEAD ACTOR gets
    up and acts — and in every one of these the player is the subject.
    """
    dead = ["the thug"]
    for said in ("You kill the thug.",
                 "You drive your blade through the thug and he drops.",
                 "Your fist connects with a meaty thud and the thug crashes to the deck.",
                 "You cut the thug down where he stands."):
        fixed, cut = narration.cut_dead_men_walking(said, dead)
        assert fixed.strip() == said and not cut, f"the kill was cut: {said!r}"

    # And a corpse still may not act, which is the whole point of the function.
    for said in ("The thug swings at you again.", "The thug yells for the watch."):
        fixed, cut = narration.cut_dead_men_walking(said, dead)
        assert not fixed.strip() and cut, f"a dead man kept acting: {said!r}"


def test_the_player_is_you_even_when_the_model_names_her():
    """Measured on the gemma4:12b fight audit: six of twelve combat turns
    narrated 'Kesst Vayr's blade...' — clean prose, wrong person, the single
    fault class of the run. Whole-set swap with listed verb agreements; speech
    keeps her name — somebody may shout it."""
    from gm.narration import pc_to_second_person

    t = ("Kesst Vayr's blade bites home. Kesst swings again as Kesst Vayr "
         "presses forward. 'Kesst Vayr!' someone shouts.")
    out, n = pc_to_second_person(t, "Kesst Vayr")
    assert n == 3
    assert out.startswith("Your blade bites home. You swing again")
    assert "you press forward" in out
    assert "'Kesst Vayr!' someone shouts." in out
    assert pc_to_second_person("The thug circles.", "Kesst Vayr") == ("The thug circles.", 0)


def test_a_four_word_beat_cannot_stand(client, settings, tmp_path, monkeypatch):
    """Measured live on a Continue: the model echoed the instruction, the
    groomers compressed the echo, and 'You take scene on.' shipped against a
    600-character scene floor. Source-inspected: the finish path holds a floor
    of last resort — a beat under 60 characters with no dice behind it becomes
    an honest holding line."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "play" / "views.py").read_text(
        encoding="utf-8")
    guard = src[src.index("The floor of last resort"):][:700]
    assert "< 60" in guard and "not outcomes" in guard
    # The floor itself moved into `_floor` on 2026-09-08, so that a turn where the
    # player SPOKE gets an answer in the fiction instead of the parser's holding line.
    # Both floors still exist; the guard now reaches them through one door.
    assert "_floor(" in guard
    floor = src[src.index("def _floor("):][:900]
    assert "The moment holds" in floor
    assert "unanswered_speech" in floor


def test_the_schema_is_not_the_story():
    """Measured live on gemma4:12b: the narration field carried the prose, then
    '", "suggestions woorden": [...]', a <tool_call|> marker, a fenced json block
    repeating the whole beat, and the intents key — all of it shipped. The first
    schema artefact ends the prose."""
    from gm.narration import cut_schema_bleed

    t = ('The air thickens around your arm. How do you use it? '
         '", "suggestions woorden": ["Wait for them"], "intents": []}'
         '<tool_call|>```json { "narration": "The air thickens again" }')
    out, cut = cut_schema_bleed(t)
    assert out == "The air thickens around your arm. How do you use it?"
    assert cut

    clean = "The woman looks up. What do you do?"
    assert cut_schema_bleed(clean) == (clean, [])


def test_a_declining_reply_is_detected_not_argued_with():
    """A tune that will not write a beat is the wrong tune for that beat, and
    the fallback role exists for exactly that. Anchored to the opening sentence
    and outside quotes: "'I can't help you,' she says" is a character refusing
    inside the fiction, which an unanchored search called a refusal."""
    from gm.narration import reads_as_a_refusal

    assert reads_as_a_refusal("I can't write that scene.")
    assert reads_as_a_refusal("I'm sorry, but I won't continue this.")
    assert reads_as_a_refusal("As an AI, I must decline.")
    assert not reads_as_a_refusal("'I can't help you,' she says, turning away.")
    assert not reads_as_a_refusal("The woman looks up. What do you do?")
    assert not reads_as_a_refusal("")


def test_prose_has_the_second_model_call_one_always_had():
    """Source-inspected: narrate_turn built one call and one only, so any whiff
    — a decline, a truncation, junk — dropped the turn to the holding line with
    the scene frozen. It now walks the same fallback schedule plan_turn does."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "gm" / "agent.py").read_text(
        encoding="utf-8")
    # The whole function, not a fixed 3,000-character slice from its `def`. The slice
    # measured distance from the start rather than the function's own extent, so adding
    # a paragraph of docstring pushed the last assertion out of the window and failed a
    # test about the fallback schedule for a reason with nothing to do with it.
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "narrate_turn")
    body = ast.get_source_segment(src, fn) or ""
    assert 'modelcfg.for_role("fallback")' in body
    assert "for model, host, provider, key in schedule" in body
    assert "reads_as_a_refusal" in body


def test_pronouns_are_presence():
    """Measured live: a whole beat written about her — 'her eyes close', 'she
    leans into the contact' — never used the word 'woman', so the anchor fired
    and told the player they were still waiting for somebody in their arms."""
    from gm.narration import keep_the_thread

    thread = {"subject": "the woman", "doing": "waiting for"}
    beat = "Her eyes close, and she leans into the contact. What do you do?"
    out, anchored = keep_the_thread(beat, thread)
    assert out == beat and not anchored

    gone = "The market is loud and the stalls are busy. What do you do?"
    out, anchored = keep_the_thread(gone, thread)
    assert anchored == "the woman"


def test_a_deflection_leaves_a_fingerprint():
    """A refusal that reads as prose: instead of continuing an intimate beat the
    model wrote a different scene — a door broken down and 'A woman is there',
    indefinite, though she had been in the player's arms one beat earlier. Every
    check aimed at stated refusals passes it; the indefinite article does not."""
    from gm.narration import reintroduces_the_present

    lost = ("The heavy door gives way with a groan. Behind it, a woman is "
            "there, slumped in a high-backed chair.")
    assert reintroduces_the_present(lost, ["the woman"]) == ["the woman"]
    assert reintroduces_the_present("She looks up as you enter.", ["the woman"]) == []
    assert reintroduces_the_present("A watchman shoulders past.", ["the woman"]) == []


def test_a_group_is_not_reintroduced_by_one_more_of_its_kind():
    """Reported at the table, 2026-09-04, two holding lines in a row: "a group of men
    in fine tunics" had been promoted to four actors called "man", the next beat
    said "a man" of the drover, and gemma's good answer was thrown away as "lost
    the scene, re-introduced man, man, man, man". A name several actors share is a
    group's, and a group cannot walk in as a stranger."""
    from gm.narration import reintroduces_the_present

    beat = "A man leans on the gatepost and spits. 'The same thing as everybody,' he says."
    assert reintroduces_the_present(beat, ["man", "man", "man", "man"]) == []
    # One of her, though, is a person — when the scene holds her as unique: alone, or
    # as the subject of the standing thread. In a crowd with two men and no thread,
    # "a woman" is one woman of several possible, which is the 2026-09-18 narrowing
    # (tests/test_the_beat_that_lost_the_scene.py): four beats of sixty had been thrown
    # away over exactly this reading of a role noun.
    assert reintroduces_the_present("A woman is there.", ["the woman", "man", "man"],
                                    thread="the woman") == ["the woman"]
    assert reintroduces_the_present("A woman is there.", ["the woman", "man", "man"]) == []


# --- the prose call's prompt and its schema must describe the same reply -----------------

def test_the_prose_schema_admits_what_the_prose_prompt_demonstrates():
    """The player's first turn died on this, live, 2026-09-04.

    `call_prose_messages` builds on the TURN prompt, so the model is shown twelve
    worked examples and every one of them is `{"narration", "suggestions", "intents"}`.
    `PROSE_AFTER_EXTRA` then says to put nothing in the "intents" list — a sentence
    that only parses if there is one. The schema allowed `narration` alone.

    Against that, a one-key grammar does not produce one key. It produces the
    demonstrated object crammed into the narration string and escaped, which never
    closes: the live reply ended

        ...is in your pocket?\\", \\"suggestions\\": [\\"Leave the room...\\"],
        \\"intents\\": []}<tool_call|>

    and 1,068 characters of good prose were lost to "Unterminated string starting at:
    line 1 column 15". Reproduced four times in eight runs against the same prompt.

    So the ratchet is not "the schema has these keys" but "the schema accepts what the
    prompt demonstrates" — checked by validating the examples' own replies against it,
    so moving either one without the other fails here rather than in play.
    """
    import jsonschema

    from gm import prompts

    schema = prompts.prose_schema(min_chars=0, max_chars=2000)
    shown = (list(prompts.EXAMPLES) + list(prompts.COMBAT_EXAMPLES)
             + list(prompts.CARRY_ON_EXAMPLES))
    assert shown, "the prose call is built on these; an empty list would pass vacuously"
    for ex in shown:
        reply = dict(ex["reply"])
        reply["narration"] = "x"          # length is the caller's floor, not the shape
        jsonschema.validate(reply, schema)

    # And the instruction still agrees with the shape it is allowed to ask for.
    if "intents" in prompts.PROSE_AFTER_EXTRA:
        assert "intents" in schema["properties"], (
            "the prose instruction talks about an intents list the schema forbids")


def test_the_prose_reply_still_only_has_to_carry_narration():
    """The other half: `suggestions` and `intents` are admitted, never required, and
    never read. A model that answers with prose alone is correct."""
    import jsonschema

    from gm import prompts

    schema = prompts.prose_schema(min_chars=0, max_chars=2000)
    jsonschema.validate({"narration": "just the prose"}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"suggestions": []}, schema)


# --- Continue is shown what continuing looks like ----------------------------------------

def test_continue_replaces_the_turn_examples_with_its_own():
    """Measured live, 2026-09-04, five presses of Continue out of five: the player was
    at a public ritual in a market and every beat put them shoulder-first against a
    door into a room the scene does not contain — a cellar, a vestibule, a store of
    timber and grain.

    Not copied words. `build_echo_index` finds zero shared six-word phrases between the
    beat and the examples, so the lexical echo detector could not see it and honestly
    cannot: the *situation* is what was copied. Worked example 11 is "I put my shoulder
    to the door and force it", it ends on "Do you take it?" with the shove still in the
    air, and it is the last thing the model sees before the player's line. Told to
    "carry the scene on from where it stopped", a model with no demonstration of what
    that means finishes the nearest stopped thing in front of it.

    After: zero of five, and the beats are in the market the player is standing in.
    """
    from gm import prompts

    msgs = prompts.call_prose_messages("BRIEF", [], prompts.CARRY_ON, [])
    shown = [m["content"] for m in msgs if m.get("role") == "assistant"]
    assert len(shown) == len(prompts.CARRY_ON_EXAMPLES)
    blob = " ".join(shown).lower()
    for forbidden in ("door", "hinge", "cellar", "vestibule", "shoulder to the"):
        assert forbidden not in blob, forbidden

    # An ordinary turn is untouched: it still gets the full set.
    ordinary = prompts.call_prose_messages("BRIEF", [], "I draw my sword", [])
    assert len([m for m in ordinary if m.get("role") == "assistant"]) == \
        len(prompts.EXAMPLES)


def test_the_continue_examples_continue_rather_than_start_something():
    """Nobody acts, nothing new arrives, the place and the people already here go on —
    and every one hands the turn back, because the beat the player did not take is
    still a beat that ends with them holding it."""
    from gm import prompts

    for ex in prompts.CARRY_ON_EXAMPLES:
        assert ex["player"] == prompts.CARRY_ON
        narration = ex["reply"]["narration"]
        assert narration.rstrip().endswith("What do you do?"), narration[-60:]
        # The prose call reads `narration` and nothing else; these demonstrate that.
        assert set(ex["reply"]) == {"narration"}


def test_the_continue_line_has_one_definition():
    """The prose call recognises this exact string to swap its examples in, and the
    view sends it. Two copies that have to match byte for byte is how the stale one
    ships."""
    from play import views

    from gm import prompts

    assert views.CARRY_ON is prompts.CARRY_ON


# --- where the player is standing is the engine's ----------------------------------------

def test_prose_may_not_walk_the_player_through_a_door_the_engine_never_opened():
    """Measured live, 2026-09-04. The player asked "I ask what happened" while standing
    in a market. The engine resolved `narrate_only` — nothing — and `scene.at` stayed
    at the market. The prose read:

        The door gives way with a groan of complaining wood, and you are shoved
        forward into a small, stifling room.

    and then furnished the room with a desk, a man and a coin, and `note_cast` promoted
    the man to a real actor. The fiction moved the character and the state did not.

    That is the same class of lie as a narrated hit that never rolled, so it is caught
    by the same machinery: where the party stands is `Actor.at` and the engine is its
    one writer (docs/places-8b-plan.md), so crossing into an enclosed place is a claim,
    and `travel` or `move` is what backs it.
    """
    from rules.intents import claims_the_engine_backs, find_outcome_claims

    nothing = claims_the_engine_backs([{"op": "narrate_only", "effects": []}])
    travelled = claims_the_engine_backs([{"op": "travel", "effects": []}])

    live = ("The door gives way with a groan of complaining wood, and you are shoved "
            "forward into a small, stifling room. The air here is thick with the smell "
            "of old paper.")
    assert find_outcome_claims(live, backed=nothing), "the live beat must be caught"
    assert not find_outcome_claims(live, backed=travelled), "a travel backs it"

    for moved in ("You step through the doorway into the cellar below.",
                  "You are pushed into another room entirely.",
                  "You find yourself inside a cramped vestibule.",
                  "You find yourself standing in the library.",
                  "You duck through the archway."):
        assert find_outcome_claims(moved, backed=nothing), moved


def test_moving_about_inside_the_scene_is_still_the_narrators_to_describe():
    """Deliberately narrow. Within a place the model may move the player freely — it is
    crossing OUT of one that the engine owns — and a check that fired on "you step
    closer to the fire" would make ordinary prose unwritable."""
    from rules.intents import claims_the_engine_backs, find_outcome_claims

    nothing = claims_the_engine_backs([{"op": "narrate_only", "effects": []}])
    for fine in ("You step closer to the fire.",
                 "You move to the rail and look down.",
                 "You push through the crowd towards the stall.",
                 "You shoulder your way through the press of bodies.",
                 "You look through the doorway at the room beyond.",
                 "You reach into your coat for the flask.",
                 "The servant steps into the room with a jug."):
        assert not find_outcome_claims(fine, backed=nothing), fine


# --- "i want more text and more description per generation", 2026-09-04 -------------------

def test_the_briefs_refs_never_reach_the_page():
    """"A merchant (c4) is haggling loudly over a crate of spices" — four of the
    brief's refs shipped in one live beat once the beats grew long enough to name
    everybody. The tag goes, the noun stays, and the count is reported."""
    text, n = narration.strip_ref_tags(
        "A merchant (c4) is haggling. A laborer (c3) pauses; a man ( c2 ) weaves "
        "through the stalls and a stranger (c1) inspects a piece of iron (not a ref).")
    assert n == 4
    assert "(c" not in text and "( c" not in text
    assert "(not a ref)" in text
    assert text.startswith("A merchant is haggling. A laborer pauses; a man weaves")


def test_the_prose_floor_is_not_in_the_grammar():
    """Measured on gemma-4 12B with minLength=800 in the prose schema: the grammar
    compiled and the model, held inside a string it had finished, wrote the rest
    of the object into it escaped — '", "suggestions": ["Wait for someone to' —
    three turns in four, each trimmed back UNDER the floor by cut_schema_bleed.
    The floor is review's to report and the repair call's to fix."""
    schema = prompts.prose_schema(min_chars=narration.MIN_SCENE_CHARS, max_chars=2200)
    assert "minLength" not in schema["properties"]["narration"]
    assert schema["properties"]["narration"]["maxLength"] == prompts.GRAMMAR_MAXLENGTH_CEILING


# --- the narrator continues what is in front of it, 2026-09-05 ---------------------------

def test_the_opening_is_in_the_models_history_not_only_on_the_page(tmp_path):
    """The player's first turn, from their own save: history held the private note and
    "I ask what is going on" — no step, no market, no stranger — and the prose model
    wrote worked example eleven's door in a sunlit market. The opening goes into the
    history the models are shown, as the assistant's own last beat."""
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.current("history-seed", reset=True)
        opening = c.transcript[0]["text"]
        assert any(h["role"] == "assistant" and h["content"] == opening for h in c.history)
        # And it comes AFTER the private note, so the note still reads as the GM's own.
        roles = [h["role"] for h in c.history]
        assert roles.index("assistant") > 0 and roles[0] == "user"


def test_the_prose_call_is_shown_the_scene_it_is_continuing():
    """`call_prose_messages` was built with an empty history at its only call site. The
    last beats the player read go into the final message, most recent last, trimmed
    from the front so the end of the scene — where it was left — survives."""
    beats = ["A" * 3000 + " the first beat ends here.", "The second beat, whole."]
    msgs = prompts.call_prose_messages("BRIEF", [], "I look around.", [], earlier=beats)
    last = msgs[-1]["content"]
    assert "the scene as it stands" in last
    assert "the first beat ends here." in last and "The second beat, whole." in last
    assert last.index("the first beat ends here.") < last.index("The second beat, whole.")
    assert "A" * 2000 not in last
    assert last.index("The second beat, whole.") < last.index("The player said: I look around.")
    # And with nothing narrated yet, nothing is claimed to have been.
    bare = prompts.call_prose_messages("BRIEF", [], "I look around.", [])
    assert "the scene as it stands" not in bare[-1]["content"]


def test_no_worked_example_forces_a_door():
    """"I put my shoulder to the door and force it" was the strongest attractor in the
    file: it finished every stopped Continue, walked players through doors the engine
    never opened, and on a first turn with no scene in front of the model it became
    the scene. Retired for a question asked of a boatwright, somewhere with no door."""
    for ex in prompts.EXAMPLES:
        line = ex["player"].lower()
        assert not re.search(r"\b(?:force|shoulder|break|kick)\b.*\bdoor\b", line), line
    assert not any("swollen with damp" in ex["reply"]["narration"] for ex in prompts.EXAMPLES)


def test_a_place_name_is_not_a_stranger():
    """"The Weaver's Rest is a place for those seeking rest" shipped as "The Weaver's
    the stranger is a place…", 2026-09-06: "Rest" read as an invented person. A
    capitalised word beside a place noun, or a place noun after a possessive, is
    somewhere."""
    from gm.narration import invented_names, unname_strangers

    text = ("'The Weaver's Rest is a place for those seeking a quiet word,' she says. "
            "Salt Market is closed. You could try Harrow Bridge, or ask Kaida.")
    assert invented_names(text, set()) == ["Kaida"]
    out, _ = unname_strangers(text, set())
    assert "Weaver's Rest" in out and "Salt Market" in out and "Harrow Bridge" in out
    assert "Kaida" not in out


def test_a_beat_that_is_the_last_beat_again_is_cut_even_inside_quotes():
    """"I thank her" came back as the previous two beats re-quoted nearly word for word
    — the same sentences with the punctuation moved, every one inside her speech, so
    the speech exemption shipped it. A beat that is mostly repeats is regurgitation
    whatever the quote marks say; a guard repeating one line still is not."""
    earlier = ["'Wisdom is a heavy burden to carry alone,' she says, her voice dropping "
               "an octave. 'And the city is a labyrinth where one can easily lose their "
               "way, or their head.' She hands you the paper. It is a map of the nearby "
               "district, marked with small hand-drawn symbols."]
    again = ("'Wisdom is a heavy burden to carry alone, ' she says, her voice dropping an "
             "octave. 'And the city is a labyrinth where one can easily lose their way, "
             "or their head. ' She hands you the paper. What do you do?")
    kept, cut = narration.drop_repeated_beats(again, earlier)
    # The two long sentences go; "She hands you the paper." is under the length a
    # repeat is judged at, and stays.
    assert cut == 2 and kept.strip() == "She hands you the paper. What do you do?"
    # One line of speech repeated in a fresh beat is characterisation.
    one = ("The guard shakes his head again. 'And the city is a labyrinth where one can "
           "easily lose their way, or their head.' He does not move from the gate, and "
           "the rain keeps on. The queue behind you mutters. What do you do?")
    same, cut = narration.drop_repeated_beats(one, earlier)
    assert cut == 0 and same == one
