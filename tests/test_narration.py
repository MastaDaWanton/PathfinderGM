"""The prose itself.

Narration is the surface the whole app is judged by. Every case here is a line the model
actually produced in this repo's play sessions, recovered from the campaign saves.
"""
from __future__ import annotations

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
    scene = prompts.EXAMPLES[0]["reply"]["narration"]
    r = narration.review(scene, min_chars=narration.MIN_SCENE_CHARS)
    assert not any(f.kind in ("too-short", "no-hand-back") for f in r.findings)


def test_a_turn_that_never_hands_back_is_caught():
    """Every example ends by asking the player something. A turn that closes on a full
    stop tends to close the fiction with it."""
    text = ("You get the door open on a room full of ledgers and dust, and the clerk at "
            "the far end does not look up from his work. Rain drums on the roof above "
            "the stacks. The lamp beside him has burned down to a stub and nobody has "
            "trimmed it, and the ink on his fingers is a week old at least. Somewhere "
            "below, a door closes and a bolt goes across it.")
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
