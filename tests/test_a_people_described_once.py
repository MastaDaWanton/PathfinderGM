"""A people is described once; every later person of it is themselves.

Reported 2026-09-24, on the second orc of the session: *"the description is the same
description for every other orc ever introduced."* `rules/faces.py` had given each orc
their own three details the day before, but the world's one sentence for what an orc IS
still opened every face — so the player read "Powerfully built, prominent lower tusks,
thick hide that resists minor scarring" for Korgath, then for the elder, then for whoever
came next. A table GM says what an orc looks like once.
"""
from __future__ import annotations

from gm import narration
from rules import faces
from rules.bestiary import instantiate
from rules.engine import Scene

ORC = "Orc: Powerfully built, prominent lower tusks, thick hide that resists minor scarring."
FIRST = ORC + " Somewhere in the middle of life; a limp favouring the right leg; hands soft."
SECOND = ORC + " Old enough to have stopped counting; a fringe cut straight across, badly."


def _two_orcs():
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    a = instantiate("guildhand", scene=s, name="Korgath Varn")
    a.appearance = FIRST
    s.add(a)
    b = instantiate("guildhand", scene=s, name="Ashla")
    b.appearance = SECOND
    s.add(b)
    return s, a, b


class TestTheHelpers:
    def test_the_people_and_their_own_details_are_told_apart(self):
        assert faces.people_of(SECOND) == "Orc"
        assert faces.own_details(SECOND) == ("Old enough to have stopped counting; a fringe "
                                             "cut straight across, badly.")
        assert faces.people_of("favors plain dress and one fine ring") == ""

    def test_the_first_of_a_people_gets_the_whole_line(self):
        assert faces.for_the_page(FIRST, people_seen=False) == FIRST

    def test_the_second_gets_the_people_and_their_own_details(self):
        assert faces.for_the_page(SECOND, people_seen=True) == \
            "Orc: Old enough to have stopped counting; a fringe cut straight across, badly."

    def test_a_residents_free_text_is_left_alone(self):
        assert faces.for_the_page("favors plain dress", people_seen=True) == "favors plain dress"


class TestOnceIsRead_OffWhoHasBeenDescribed:
    def test_nobody_described_yet_means_the_whole_line(self):
        s, a, b = _two_orcs()
        assert faces.people_seen_before(b, s.people.values()) is False

    def test_after_the_first_orc_the_second_is_themselves(self):
        s, a, b = _two_orcs()
        a.described = True
        assert faces.people_seen_before(b, s.people.values()) is True
        said = narration.a_face_for(b.name, faces.for_the_page(
            b.appearance, faces.people_seen_before(b, s.people.values())))
        assert said == ("Ashla is an Orc: Old enough to have stopped counting; a fringe "
                        "cut straight across, badly.")
        assert "Powerfully built" not in said

    def test_the_first_orc_is_not_shortened_by_the_second(self):
        s, a, b = _two_orcs()
        b.described = True
        assert faces.people_seen_before(a, s.people.values()) is True, \
            "whoever was described first fixes it; the other is the second"
        a.described = True
        b.described = False
        assert faces.people_seen_before(b, s.people.values()) is True
