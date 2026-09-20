"""One person is one card, even when the beat describes them twice.

Item 36 of the 2026-09-19 play-test (`docs/playtest-2026-09-18.md`), found by a live run
rather than reported. The ledger came back holding three people where the beat had two:

    {"who": "man in a heavy",   "turn": 82}   <- a separate defect, fixed in group 8
    {"who": "merchant",         "turn": 82}
    {"who": "shouting merchant","turn": 82}

out of one beat about the reeve:

    "A man in a heavy, grease-stained leather apron stands behind the counter ... and he
     is currently shouting at A MERCHANT over a dispute regarding a shipment of timber.
     ... The crowd is dense, and his attention is currently divided by THE SHOUTING
     MERCHANT."

The head-word dedup allows a second person when the description differs, on purpose:
"the man in the leather apron" after "desperate man" is a second man, and skipping him is
exactly how the man who swung first at the player was never put on the board (2026-09-18,
item 16b). So the dedup could not tell these two apart from the words alone.

The article can, and the account of why is old and settled. Heim's novelty/familiarity
condition — an indefinite noun phrase creates a new file card, a definite refers to one
that already exists — is about a ledger of cards for the people a discourse has
introduced, which is what `scene.cast` is. An indefinite always books. A definite is a
back-reference when the ledger can show who to — this beat's own booking, a bare card of
that role, or a booked description sharing a word with it.

The rule started at one beat and was widened by driving it: three turns in the market on
2026-09-20 booked ONE man three times across three beats, so the reported turn was the
narrowest case of item 36 rather than its whole shape. What stays untouched is Heim's
accommodation — a definite naming a role nobody booked still books — and, below, the
2026-09-18 case this must not undo.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.engine import Scene


@pytest.fixture
def market():
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    return s


# The reported beat, trimmed to the two sentences that did the booking.
REPORTED = ("A man in a heavy, grease-stained leather apron stands behind the counter, "
            "and he is currently shouting at a merchant over a dispute regarding a "
            "shipment of timber. The crowd is dense, and his attention is currently "
            "divided by the shouting merchant.")


def test_the_reported_beat_books_the_merchant_once(market):
    """The measured turn. Two mentions of one merchant, one card."""
    added = judgement.note_cast(market, REPORTED, turn=82)
    merchants = [w for w in added if judgement._role_head(w) == "merchant"]
    assert merchants == ["merchant"], added
    booked = [e["who"] for e in market.cast]
    assert "shouting merchant" not in booked, booked


def test_an_indefinite_still_books_a_second_person_in_the_same_beat(market):
    """Novelty: "a merchant ... another merchant" is two, and the rule must not reach
    it. Only the definite is a back-reference."""
    added = judgement.note_cast(
        market, "A merchant argues at the counter. A younger merchant watches him.",
        turn=1)
    assert len(added) == 2, added


def test_a_definite_naming_nobody_booked_still_books(market):
    """Heim's accommodation, and the ordinary case: the first mention of a person can
    perfectly well be definite, and refusing it would empty the ledger."""
    added = judgement.note_cast(market, "The merchant looks up from the counter.", turn=1)
    assert [judgement._role_head(w) for w in added] == ["merchant"], added


def test_the_second_man_across_beats_is_still_a_second_man(market):
    """The 2026-09-18 fix, which this rule must not undo — it is why the rule is held to
    one beat. "desperate man" a turn ago and "the man in the leather apron" now are two
    men, and skipping the second is how the one who swung first stayed off the board."""
    market.cast = [{"who": "desperate man", "turn": 1}]
    added = judgement.note_cast(
        market, "The man in the leather apron laughs and steps forward.", turn=2)
    assert added == ["man in the leather apron"], added


def test_a_bare_definite_repeat_is_still_the_same_person(market):
    """Unchanged behaviour, stated here because the new rule sits right beside it."""
    market.cast = [{"who": "desperate man", "turn": 1}]
    assert judgement.note_cast(market, "The man spits.", turn=2) == []


def test_a_booked_band_is_who_the_definite_means(market):
    """The group loop books in this same beat, so "the raiders" two sentences after
    "twelve raiders come up the road" is the band, not a second one."""
    added = judgement.note_cast(
        market, "Twelve raiders come up the road. The raiders fan out as they come.",
        turn=1)
    assert len([w for w in added if judgement._role_head(w) == "raiders"]) == 1, added


# --- what the live run of 2026-09-20 found, which item 36 had understated ---------------

def test_one_man_does_not_collect_three_cards_across_beats(market):
    """The reason the same-beat rule alone was not enough. Driven live 2026-09-20 in the
    market, three consecutive beats booked:

        turn 94: man with a distinctive      <- description truncated at the adjective
        turn 96: man with the distinctive
        turn 98: man with the satchel

    one man, three cards, and `cast_brief` would then assert all three as present.
    """
    judgement.note_cast(market, "A man with a distinctive satchel watches you.", turn=94)
    judgement.note_cast(market, "The man with the distinctive satchel tilts his head.", turn=96)
    judgement.note_cast(market, "The man with the satchel has shifted his position.", turn=98)
    men = [e["who"] for e in market.cast if judgement._role_head(e["who"]) == "man"]
    assert len(men) == 1, men
    assert men[0] == "man with a distinctive satchel", men


def test_the_description_is_no_longer_cut_at_the_adjective(market):
    """The truncation that made those three phrases fail to match each other. The closed
    adjective list carried "scarred" only because it ends in -ed; "distinctive" matched
    nothing and the satchel was dropped."""
    added = judgement.note_cast(market, "A man with a distinctive satchel waits.", turn=1)
    assert added == ["man with a distinctive satchel"], added


def test_a_porter_described_twice_is_one_porter(market):
    """The other pair from the same run: "a porter with a scarred forearm" (turn 96) and
    "the porter with the scarred forearm" (turn 98)."""
    judgement.note_cast(market, "A porter with a scarred forearm hesitates.", turn=96)
    added = judgement.note_cast(
        market, "The porter with the scarred forearm grips the crate.", turn=98)
    assert added == [], added


def test_a_definite_describing_a_bare_booked_role_is_that_person(market):
    """A bare card is somebody nobody has described yet; a definite describing them is
    the description arriving, not a second body."""
    market.cast = [{"who": "merchant", "turn": 1}]
    assert judgement.note_cast(market, "The merchant with the satchel spits.", turn=4) == []


def test_two_described_people_of_one_role_are_still_two(market):
    """The line this must not cross, stated once more against the widened rule: nothing
    bare, nothing shared, so they are two men however definite the second is."""
    market.cast = [{"who": "desperate man", "turn": 1}]
    added = judgement.note_cast(market, "The man in the leather apron laughs.", turn=4)
    assert added == ["man in the leather apron"], added
