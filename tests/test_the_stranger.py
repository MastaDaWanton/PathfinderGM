"""A word that describes a person is not a person.

Reported at the table 2026-09-08, with a screenshot of the prose:

    "As for where the shadows do not reach, I speak of the Old the stranger cellar."

A place name with a person pasted into the middle of it, article and all, and the
player's report was that it happened constantly rather than once.

Two causes, both measured:

  * The word came from our own worked examples. `prompts.fill_enemy` renders
    {Current Enemy} as "the stranger" when there is no enemy, and the wall-climbing
    example used that token for a figure in a doorway who was never an enemy — so
    every out-of-combat turn showed the model "the stranger" twice, in prose and in a
    suggestion. Instruction volume loses to demonstration volume.
  * Once said, it stuck. `note_cast` files a person called "stranger" in the scene
    cast, `promote_cast` makes them a real actor, and the brief then carries them for
    the next twelve turns. That is the loop that made it constant rather than
    occasional — and it is NOT a bug. `test_a_noted_person_stands_in_the_scene`
    records the incident that put it there: a bare stranger in the prose, the player
    wanting to address him, and the engine holding nobody, so "he could not be
    attacked, addressed, or found again."

So the loop stays and the source goes. The word only ever entered the model's mouth
because our own examples put it there.
"""
from gm import judgement, prompts


def test_the_out_of_combat_prompt_does_not_teach_the_word():
    """Measured before the fix: twice in the first worked example alone, once in its
    narration and once in its suggestions, on every turn out of a fight."""
    import json

    shown = " ".join(
        prompts.fill_enemy(e["player"] + json.dumps(e["reply"]), None)
        for e in prompts.EXAMPLES)
    prose = shown.replace('"template": "stranger"', "")
    assert "stranger" not in prose, (
        "the examples still demonstrate the word in prose the model can copy")


def test_the_doorway_figure_was_never_an_enemy_anyway():
    """The token stood in for scenery. In a fight it rendered as whoever the player
    was fighting, which put the current enemy in a doorway in a wall-climbing example;
    out of one it rendered as the word that caused this bug."""
    import json

    first = json.dumps(prompts.EXAMPLES[0]["reply"])
    assert prompts.ENEMY_TOKEN not in first


def test_a_bare_pronoun_is_not_a_person():
    """"someone laughs behind you" is a way of saying nobody in particular, and
    booking it puts a person on the board that the prose never meant. Matched on the
    whole phrase, so a described person is untouched."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    noted = judgement.note_cast(
        c.scene, "Someone laughs behind you, and somebody drops a crate.", turn=3)
    assert noted == []


def test_a_bare_stranger_is_still_booked_because_an_older_incident_says_so():
    """Pulling the other way, and it wins. The docstring of
    `test_a_noted_person_stands_in_the_scene` records why: a bare stranger in the
    prose, the player wanting to address him, and the engine holding nobody — "he
    could not be attacked, addressed, or found again". So the fix for the 2026-09-08
    report is upstream, in the examples, not here."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    noted = judgement.note_cast(
        c.scene, "A stranger watches from the doorway.", turn=3)
    assert noted == ["stranger"]


def test_a_real_unnamed_person_is_still_filed():
    """The filter must not buy its silence by going deaf. This game's scenes are full
    of "the man at the far bank" who is a real person the player will meet again, which
    is why "man" and "woman" are deliberately not on the list."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    noted = judgement.note_cast(
        c.scene, "A woman with soot on her hands calls out from the forge.", turn=3)
    assert noted == ["woman"]


def test_a_described_stranger_is_still_a_person():
    """The line is the bare word, not the word. Two older tests in test_judgement.py
    insist that "a tall hooded stranger" is booked, and they are right: that is
    somebody the player will meet again. Matching on the whole phrase rather than its
    last word is what keeps both true."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    noted = judgement.note_cast(
        c.scene, "A tall hooded stranger steps out of the doorway.", turn=3)
    assert noted == ["tall hooded stranger"]
