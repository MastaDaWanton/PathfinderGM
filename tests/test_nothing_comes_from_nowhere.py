"""A thing does not enter play because somebody said it.

Item 37, reported 2026-09-20 with a screenshot. The player typed *"I pull out my crown and
display it for all to see"* and the narrator produced one — "you reach into the folds of
your traveler's outfit and produce the circlet … a heavy, brutal thing of worked metal",
the foreman's eyes going wide, the yard falling silent around it. The player's note:
**"I have no crown to display."**

Measured the same day against a sheet carrying one club:

    "I am the lost heir of the old kings"      false_claim -> "are the lost heir…"
    "I pull out my crown and display it"       false_claim -> ""
    "I show them my royal seal"                false_claim -> ""
    "I hand him the deed to the mill"          false_claim -> ""
    "I draw my longsword"                      false_claim -> ""

So it was never about crowns: **any** gear the player named was conjured, including a
weapon they had never bought. `false_claim` catches the shape of asserting what one IS and
there was nothing at all for asserting what one HAS, while `_sheet_vocabulary` had been
reading `pc.carried()` the whole time and nothing ever asked it this question.

It is the possession half of a law this app already keeps for people: group 8 built
`rules/scope.py` so nobody is created on the strength of a phrase. The tradition is the
one that settled group 8 — Inform's parser looks through what is in scope and refuses what
is not: *"You can't see any such thing."*

The machinery is not new and that is the point. The player's own 2026-09-18 ruling was
*"It should read as my character being delusional and the people should see it
similarly"*, so a claim PLAYS: a Bluff the room rolls against, prose told to hold it
false, a finding that catches prose making it true, and the crowd's reaction. A man
flourishing a crown he does not have is that act with a prop in it, so it goes the same
way.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.engine import Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    pc = load_pc("fixtures/pc-borin.json")
    pc.kind = "pc"
    s = Scene()
    s.add(pc)
    return s


def _claim(scene, line):
    return judgement.false_claim(line, scene)


class TestTheMeasuredLines:
    """Every line from the table above, which is the whole of the defect."""

    @pytest.mark.parametrize("line", [
        "I pull out my crown and display it for all to see",
        "I show them my royal seal",
        "I hand him the deed to the mill",
    ])
    def test_gear_the_sheet_cannot_account_for_is_a_claim(self, scene, line):
        assert _claim(scene, line), line

    def test_the_claim_is_in_the_players_own_words(self, scene):
        """It travels to the prose and to the crowd, so it has to be sayable."""
        assert _claim(scene, "I pull out my crown") == "produce a crown you do not have"

    @pytest.mark.parametrize("line", [
        "I draw my longsword",
        "I draw my sword",                  # the sheet says longsword; same thing
        "I draw my dagger and cut the rope",
        "I put on my armour",               # the sheet says chain shirt
    ])
    def test_gear_the_sheet_has_goes_through_untouched(self, scene, line):
        """The item's own caution: "a player saying 'I draw my sword' with a sword on
        the sheet must go through untouched, and the check has to be able to tell those
        apart on a sheet, not on a word list"."""
        assert _claim(scene, line) == "", line


class TestWhatItDoesNotFireOn:
    """Measured against the first cut, which fired on all of these. A guard that turns
    an innocuous line into a delusion beat costs more than the one it catches."""

    @pytest.mark.parametrize("line", [
        "I offer him a drink",              # a kind of thing, not a particular one
        "I hold up my hands",
        "I show him my scars",              # on the body, not in the pack
        "I take the bread from the stall",  # acquiring, which the engine has doors for
        "I take the coin off the table",
        "I take the jar out of my satchel",
        "I show them the way to the market",
    ])
    def test_it_stays_quiet(self, scene, line):
        assert _claim(scene, line) == "", line

    def test_a_question_is_never_a_claim(self, scene):
        assert _claim(scene, "Do I still have my crown?") == ""

    def test_somebody_with_no_sheet_is_not_judged(self):
        assert judgement.false_claim("I pull out my crown", Scene()) == ""


class TestTheSheetIsAsked:
    def test_what_is_carried_vouches(self, scene):
        pc = scene.pc()
        assert _claim(scene, "I show them the crown")
        pc.goods["crown"] = 1
        assert _claim(scene, "I show them the crown") == ""

    def test_what_is_held_by_the_props_ledger_vouches(self, scene):
        """A thing picked up in play is a thing you have, and it lives in the props
        ledger rather than in `carried()` (item 15)."""
        pc = scene.pc()
        assert _claim(scene, "I hold up the sealed jar")
        scene.props.append({"name": "sealed jar", "held_by": pc.ref, "owner": pc.ref})
        assert _claim(scene, "I hold up the sealed jar") == ""

    def test_coin_is_asked_of_the_purse(self, scene):
        pc = scene.pc()
        pc.purse = {}
        assert _claim(scene, "I hand him the gold")
        pc.purse = {"gp": 5}
        assert _claim(scene, "I hand him the gold") == ""


class TestItTravelsTheDoorThatExists:
    def test_it_becomes_the_same_bluff_a_claim_about_yourself_does(self, scene):
        """No second door: everything a false claim already travels is what a false
        possession needs, and a second copy of all of it is the drift CLAUDE.md names."""
        raw = judgement.inject_false_claim(
            [{"op": "narrate_only", "because": "t"}],
            "I pull out my crown and display it for all to see", scene)
        assert any(r.get("op") == "check"
                   and (r.get("params") or {}).get("skill") == "bluff" for r in raw)

    def test_the_prose_is_told_to_hold_it_false(self, scene):
        from gm import prompts

        block = prompts.false_claim_block(_claim(scene, "I pull out my crown"))
        assert "crown" in block

    def test_a_true_line_adds_no_bluff(self, scene):
        raw = judgement.inject_false_claim(
            [{"op": "narrate_only", "because": "t"}], "I draw my longsword", scene)
        assert all(r.get("op") != "check" for r in raw)


class TestItAbstainsRatherThanGuesses:
    def test_a_sheet_that_cannot_answer_judges_nothing(self):
        """Measured by the suite, not by design: a scene whose player is a thin double
        with no gear to read turned "I draw my sword and hold it low" into a delusion
        beat, and `test_a_drawn_blade_and_a_shout_are_heat_too` caught it. The same
        discipline as `fire_context` and `here` in the reviewer — a guard that guesses
        is worse than one that abstains."""
        class _Thin:
            ref, name, is_pc, is_down, hp = "pc", "Kesst", True, False, 10
            at = ""

        s = Scene()
        s.people = {"pc": _Thin()}
        assert judgement.false_claim("I draw my sword and hold it low.", s) == ""

    def test_an_abstract_noun_is_not_a_possession(self):
        """`_is_a_thing` is this file's own answer to that question and is reused rather
        than copied — the first cut defined its own `_NOT_A_THING` and SHADOWED the
        abstract-noun set the goods machinery reads, so "I accept the offer" started
        minting an item again. Seven tests caught it."""
        pc = load_pc("fixtures/pc-borin.json")
        pc.kind = "pc"
        s = Scene()
        s.add(pc)
        for line in ("I take the chance", "I show them the way", "I take the lead"):
            assert judgement.false_claim(line, s) == "", line
