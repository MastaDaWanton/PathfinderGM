"""Nobody is renamed to a name somebody else here already answers to.

Measured live 2026-09-27 (the manoeuvre audit, gemma-4-12B, fight script): a thug the
plan spawned under its placeholder "new" (`c3`) was renamed "Borin" from the prose, and
fought for the rest of the run as "Borin" beside Borin Lyraxys (`c2`), the one man in the
tavern. The refs never crossed; every check that reads NAMES read two men as one. The
appositive door refused only an exact whole-name duplicate, and the speech door refused
nothing (docs/who-the-prose-means.md, stage 0).

Since 2026-10-03 the name is read off the page by the beat reader, not by
`apply_introductions`' patterns; the refusal is the engine's, `beat_reader.name_refusal`,
the one check every name read goes through (`seen_people.name_them`).
"""
from __future__ import annotations

from gm import beat_reader
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
    assert beat_reader.name_refusal(s, None, thug.ref, "Borin") == \
        "Borin Lyraxys answers to it"


def test_a_name_said_in_speech_is_refused_the_same_way():
    """The speech door had no check at all; there is one door now, and one check."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    s, borin, thug = _tavern()
    text = "'Borin,' the thug growls. 'Remember it.'"
    reading = stub.read(text, s, who={"the thug": thug.ref},
                        lines={"Borin": (thug.ref, "you")}, names={thug.ref: "Borin"})
    rows = seen_people.name_them(stub.ctx(s, reading, text=text), reading)
    assert rows == [{"kind": "name-read", "ref": thug.ref, "name": "Borin",
                     "taken": False, "why": "Borin Lyraxys answers to it"}]
    assert thug.name == "new"


def test_a_brother_who_shares_a_surname_is_still_named():
    """Every word of the name has to be somebody else's, not any word: "Bren Varn" is
    not Aldo Varn's name."""
    s, _, thug = _tavern("Aldo Varn")
    assert beat_reader.name_refusal(s, None, thug.ref, "Bren Varn") == ""


def test_the_dead_still_answer_to_their_names():
    s, borin, thug = _tavern()
    borin.add_condition("dead")
    assert beat_reader.name_refusal(s, None, thug.ref, "Borin")


def test_a_true_name_held_behind_a_descriptor_counts():
    """The world may hold a name for somebody the panel still shows as "the smith"."""
    s, _, thug = _tavern()
    smith = instantiate("guildhand", scene=s, name="smith")
    smith.true_name = "Harl Mettin"
    s.add(smith)
    assert beat_reader.name_refusal(s, None, thug.ref, "Harl") == "smith answers to it"


def test_somebody_already_named_keeps_their_name():
    """A named person "introducing" themselves again changes nothing."""
    s, borin, _ = _tavern()
    assert beat_reader.name_refusal(s, None, borin.ref, "Borin Ash") == \
        "already named Borin Lyraxys"
