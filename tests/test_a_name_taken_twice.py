"""Nobody is renamed to a name somebody else here already answers to.

Measured live 2026-09-27 (the manoeuvre audit, gemma-4-12B, fight script): a thug the
plan spawned under its placeholder "new" (`c3`) was renamed "Borin" from the prose, and
fought for the rest of the run as "Borin" beside Borin Lyraxys (`c2`), the one man in the
tavern. The refs never crossed; every check that reads NAMES read two men as one. The
appositive door refused only an exact whole-name duplicate, and the speech door refused
nothing (docs/who-the-prose-means.md, stage 0).
"""
from __future__ import annotations

from gm import judgement
from rules.bestiary import instantiate
from rules.engine import Scene


def _tavern(*extra):
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Kesst Vayr")
    pc.kind = "pc"
    s.add(pc)
    borin = instantiate("thug", scene=s, name="Borin Lyraxys")
    s.add(borin)
    thug = instantiate("thug", scene=s, name="new")
    s.add(thug)
    for name in extra:
        s.add(instantiate("thug", scene=s, name=name))
    return s, borin, thug


def test_the_thug_is_not_renamed_borin_beside_borin_lyraxys():
    s, borin, thug = _tavern()
    refused: list = []
    got = judgement.apply_introductions(
        s, "The thug—Borin—lets out a guttural roar.", "I keep hitting him",
        refused=refused)
    assert got == []
    assert thug.name == "new" and borin.name == "Borin Lyraxys"
    assert refused == [(thug.ref, "Borin", "Borin Lyraxys")]


def test_a_name_said_in_speech_is_refused_the_same_way():
    """The speech door had no check at all."""
    s, borin, thug = _tavern()
    got = judgement.apply_introductions(
        s, "'Borin,' the thug growls. 'Remember it.'", "I ask the thug his name")
    assert got == []
    assert thug.name == "new"


def test_a_brother_who_shares_a_surname_is_still_named():
    """Every word of the name has to be somebody else's, not any word: "Bren Varn" is
    not Aldo Varn's name."""
    s, _, thug = _tavern("Aldo Varn")
    got = judgement.apply_introductions(
        s, "The thug—Bren Varn—spits on the boards.", "I look at him")
    assert got == [(thug.ref, "Bren Varn")]


def test_the_dead_still_answer_to_their_names():
    s, borin, thug = _tavern()
    borin.add_condition("dead")
    assert judgement.apply_introductions(
        s, "The thug—Borin—stands over the body.", "I look at him") == []


def test_a_true_name_held_behind_a_descriptor_counts():
    """The world may hold a name for somebody the panel still shows as "the smith"."""
    s, _, thug = _tavern()
    thug.name = "thug"      # found by his head word, so only the guard can stop it
    smith = instantiate("guildhand", scene=s, name="smith")
    smith.true_name = "Harl Mettin"
    s.add(smith)
    assert judgement.apply_introductions(
        s, "The thug—Harl—cracks his knuckles.", "I look at him") == []
    assert thug.name == "thug"
