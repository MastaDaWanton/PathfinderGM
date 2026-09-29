"""The sounds people make that are not words: `gm.speech.vocalisations` (Lane F, item 7.2).

The owner asked for a conversation log of "just the dialogue and vocalizations such as
grunting or laughing". The grunts are untagged prose, so they are DETECTED, in code, at the
precision end: a grunt booked to the wrong person puts a sound in somebody's mouth, which
is the very defect this fix pass exists for, while a missed one costs an italic row.

Measured on the owner's playtest of 2026-09-28 (the Bobby corpus, 13 beats): a reader
books four sounds — the watchman's "short, dry bark of a laugh" (beat 2) and "low, dry
grunt" (beat 3), and the man in the jerkin's "short, dry laugh" (beat 10) and "short,
barking laugh" (beat 11). All four are found, each to the right person, and none of the
eight near misses in those beats is booked to anybody: "the village hums", "the low moan of
the wind", "his voice a low growl", "'…,' he grunts" (a dialogue tag; the line is logged),
"he gasps for breath" and the rest. Every person in that save reads they/them while the
prose calls them "he", so pronoun agreement can only ever exclude, never require.
"""
from __future__ import annotations

import pytest

import replays
from gm import speech

PEOPLE = {
    "pc": {"name": "Bobby", "pronouns": "he/him", "is_pc": True},
    "c1": {"name": "the watchman waving traffic through", "pronouns": "they/them",
           "is_pc": False},
    "c2": {"name": "girl", "pronouns": "they/them", "is_pc": False},
    "c4": {"name": "Drenn Ironvale", "pronouns": "they/them", "is_pc": False},
    "c3": {"name": "Ashla Ironvale", "pronouns": "they/them", "is_pc": False},
    "c6": {"name": "Guard", "pronouns": "they/them", "is_pc": False},
    "c7": {"name": "second Guard", "pronouns": "they/them", "is_pc": False},
}


def _booked(text, said=(), people=PEOPLE, **kw):
    return [(v["who"], v["text"], v["src"]) for v in speech.vocalisations(text, said, people, **kw)
            if v["who"]]


def test_a_named_speaker_is_booked_with_the_phrase_the_page_used():
    """The explicit tier: the name is at the verb, which the literature scores at 98.6 %
    (PDNC, explicit quotes)."""
    assert _booked("Drenn lets out a low, dry grunt.") == [
        ("c4", "lets out a low, dry grunt", "named")]
    assert _booked("Drenn Ironvale laughs softly at you, then turns away.") == [
        ("c4", "laughs softly at you", "named")]
    assert _booked("The watchman chuckles.") == [("c1", "chuckles", "named")]
    assert _booked("Drenn clears his throat.") == [("c4", "clears his throat", "named")]


def test_at_you_is_said_to_you():
    (v,) = [v for v in speech.vocalisations("Drenn laughs at you.", (), PEOPLE)]
    assert v["to"] == "you"


def test_a_laugh_beside_a_tagged_line_is_that_speakers():
    """"'Two days,' he says with a short laugh": the pronoun is resolved by the line the
    prose call tagged in the same sentence."""
    said = [{"who": "c4", "to": "you", "line": "Two days,"}]
    assert _booked("'Two days,' he says with a short laugh.", said) == [
        ("c4", "says with a short laugh", "tag-adjacent")]


def test_he_between_two_men_is_nobody():
    """Two people it could mean are a miss, not a guess: the implicit tier costs about a
    third (68.9 % on PDNC), so it answers only when there is exactly one."""
    found = speech.vocalisations("The watchman and Drenn stand at the gate. He laughs.",
                                 (), PEOPLE)
    assert [v["who"] for v in found] == [""]
    assert found[0]["why"] == "ambiguous"


def test_gender_only_ever_excludes():
    """"he" is never the girl, whatever her stated pronouns; it is the watchman."""
    assert _booked("The girl looks at the watchman, and he chuckles.") == [
        ("c1", "chuckles", "pronoun")]


@pytest.mark.parametrize("text", [
    "The wind moans through the stones.",
    "The kettle whistles on the hook.",
    "Laughter drifts from the inn.",
    "The crowd laughs at the juggler.",
    "The guard laughs.",                     # two guards: the head noun names nobody
])
def test_what_is_not_one_person_makes_no_sound_in_the_log(text):
    assert _booked(text) == []


@pytest.mark.parametrize("text", [
    "Drenn does not laugh.",
    "Drenn never laughs at that.",
    "Drenn nods without a laugh.",
    "Drenn stifles a laugh.",
    "Drenn hits the ground, and he gasps for breath.",
])
def test_a_sound_somebody_did_not_make_is_refused(text):
    """Refused outright — not even counted as a miss, because nothing was missed."""
    assert speech.vocalisations(text, (), PEOPLE) == []


def test_a_quoted_hmph_is_a_line_not_a_vocalisation():
    """Nothing inside quotation marks is ever a vocalisation (`blanked`)."""
    assert _booked('"Hmph. He laughs at nothing," Drenn says.') == []


def test_a_dialogue_tag_that_is_a_sound_is_how_the_line_was_said():
    """Bobby, beat 12: "'You're making a lot of noise…,' he grunts". The line is logged
    from the tag; a second row for the grunt would log the same moment twice."""
    said = [{"who": "c4", "to": "you", "line": "Enough,"}]
    assert _booked("'Enough,' he grunts, his voice like stones.", said) == []
    assert _booked('Drenn growls, "Get out."', said) == []


def test_the_player_character_never_makes_a_sound_in_the_gm_prose():
    """The narrator does not decide what the player's character did."""
    assert _booked("Bobby laughs.") == []


def test_the_players_own_words_are_the_players_sounds():
    got = speech.vocalisations('I laugh and say "fine". *grunts*', (), PEOPLE, player=True)
    assert [(v["who"], v["text"], v["src"]) for v in got] == [
        ("pc", "laugh", "player"), ("pc", "grunts", "player")]
    # And in the player's text an NPC's sound is the player narrating it: not booked.
    assert speech.vocalisations("Drenn laughs.", (), PEOPLE, player=True) == []


# --- the owner's playtest --------------------------------------------------------------------

# Hand labels over all thirteen beats: every sound a reader books, to whom.
LABELLED = {
    (2, "c1", "lets out a short, dry bark of a laugh"),
    (3, "c1", "lets out a low, dry grunt"),
    (10, "c8", "gives a short, dry laugh"),
    (11, "c8", "lets out a short, barking laugh"),
}


def _bobby_people():
    save = replays.save("bobby.json")
    return {p["ref"]: {"name": p["name"], "pronouns": p.get("pronouns", ""),
                       "is_pc": p["ref"] == "pc"} for p in save["people"]}


@pytest.mark.skipif(not replays.available(), reason="the Bobby corpus is not on this disk")
def test_on_the_bobby_beats_every_sound_booked_is_right():
    """Precision is gated at 95 % (design F §8); it measures 4 of 4. Recall is reported, not
    gated, and measures 4 of 4 too — the two sounds the lead named are among them: "lets
    out a low, dry grunt" and "a short, dry bark of a laugh"."""
    people = _bobby_people()
    booked, misses = set(), []
    for t in replays.turns():
        for beat in t["beats"]:
            for v in speech.vocalisations(beat["text"], beat.get("said") or [], people):
                if v["who"]:
                    booked.add((t["n"], v["who"], v["text"]))
                else:
                    misses.append((t["n"], v["text"], v["why"]))
    right = booked & LABELLED
    precision = len(right) / len(booked) if booked else 0.0
    recall = len(right) / len(LABELLED)
    assert precision >= 0.95, sorted(booked - LABELLED)
    assert recall == 1.0, sorted(LABELLED - booked)
    # The one unresolved sound is the village humming, reported as a miss for counting.
    assert misses == [(5, "hums with the start of the day's labor", "no person")]


@pytest.mark.skipif(not replays.available(), reason="the Bobby corpus is not on this disk")
def test_the_bobby_players_words_hold_no_sounds():
    people = _bobby_people()
    assert all(speech.vocalisations(t["player"], (), people, player=True) == []
               for t in replays.turns())
