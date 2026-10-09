"""The comparison half of the round trip (`gm.beat_verify.diff`), claim by claim, with no
model: what the page claims, stated in the engine's words, against what the engine did.

Each case is one the retired regex checks were written for (their measurements are kept in
the docstrings: gm/checks/refused_move.py, thing_kept.py, trade_claimed.py,
time_of_day.py as they stood at 333b5f5). What those modules decided by pattern — whether
"takes the crate from you" hands the crate over — is now the reader's to answer; what is
pinned here is the part that stays code: given that claim, is it true?
"""
from __future__ import annotations

from gm import beat_verify as bv

PC = bv.Person("pc", "Kesst Vayr", pc=True)
SMITH = bv.Person("c13", "the smith", "Korvu")
CLERK = bv.Person("c12", "the clerk of the counting house")
PLACES = ("the market", "the docks", "the counting house", "the smithy")
REFUSED_SALE = {"intent_id": "i2", "op": "sell", "status": "refused", "effects": [],
                "tell": "The smith's counter is not open yet; it opens at first light."}


def facts(**kw):
    base = dict(start="the smithy", end="the smithy", places=PLACES, pack=("crate", "pouch"),
                people=(PC, SMITH, CLERK), clock=88)
    base.update(kw)
    return bv.Facts(**base)


def claim(category, sentence="The sentence as written.", **slots):
    return bv.Claim(category, slots, quote=sentence, sentence=sentence, valid=True)


def kinds(found):
    return [(d.kind, d.category) for d in found]


# --- the player's place (was gm/checks/refused_move.py) ---------------------------------------

def test_a_move_the_engine_refused_is_a_contradiction_with_the_refusal_named():
    """Bobby, 2026-09-28: "I walk to the nearest crossroads" was refused and the page said
    "You are standing where the paths diverge" — every later turn resolved from the way in.
    The backstop's line is the refusal's own `for_a_person` when the rule wrote one."""
    refused = {"intent_id": "i1", "op": "travel", "status": "refused", "effects": [],
               "tell": "There is no the crossroads here to go to.",
               "for_a_person": "There is no crossroads here."}
    f = facts(outcomes=(refused,))
    found = bv.diff([claim("move", place=bv.UNLISTED_PLACE)], f)
    assert kinds(found) == [("contradiction", "move")]
    assert "still at the smithy" in found[0].fact and found[0].line == "There is no crossroads here."


def test_staying_put_is_no_claim_at_all():
    """"You move toward the anvil" (the live check, item 1): the reader answers the place
    the beat began in, which `claims_of` never turns into a move — moving about inside a
    place is not going anywhere (Inform: only `going` changes the room)."""
    f = facts()
    answer = {"player_ends_at": {"place": "the smithy", "quote": "You move toward the anvil"}}
    assert bv.claims_of(answer, f) == []


def test_a_move_the_engine_made_may_be_shown_and_the_way_through_counts():
    f = facts(start="the market", end="the counting house", went_by=("the docks",))
    assert bv.diff([claim("move", place="the counting house")], f) == []
    assert bv.diff([claim("move", place="the docks")], f) == []
    assert bv.diff([claim("move", place=bv.UNLISTED_PLACE)], f) == []
    assert kinds(bv.diff([claim("move", place="the smithy")], f)) == [("contradiction", "move")]


# --- a thing still held (was gm/checks/thing_kept.py) ------------------------------------------

def test_a_thing_the_engine_kept_handed_away_is_a_contradiction():
    """The live check of 2026-10-03, item 5: the engine moved the crate into Kesst's goods
    and nothing out, and the page read "the smith, Korvu, … takes the crate from you"."""
    found = bv.diff([claim("hands", item="crate", **{"from": "pc"}, to="c13")], facts())
    assert kinds(found) == [("contradiction", "hands")]
    assert "still carries the crate" in found[0].fact


def test_a_hand_over_the_engine_made_may_be_shown():
    sold = {"intent_id": "i3", "op": "sell", "status": "resolved", "tell": "",
            "effects": [{"ref": "pc", "kind": "sold", "item": "crate", "to": "c13"}]}
    f = facts(pack=("pouch",), outcomes=(sold,))
    assert bv.diff([claim("hands", item="crate", **{"from": "pc"}, to="c13")], f) == []
    set_down = {"intent_id": "i2", "op": "give", "status": "resolved", "tell": "",
                "effects": [{"ref": "pc", "kind": "give", "item": "crate", "how": "set_down",
                             "from": "pc", "to": ""}]}
    f = facts(pack=("pouch",), props=("crate",), outcomes=(set_down,))
    assert bv.diff([claim("hands", item="crate", **{"from": "pc"}, to=bv.FLOOR)], f) == []


def test_a_pick_up_the_engine_never_made_is_a_contradiction():
    """kesst:23 — the deeds repair wrote "You grip the edges of the wood and heave the
    heavy crate from the dirt" on a turn that resolved only narrate_only, the crate still
    lying in the props ledger. The regex check read the pack only and could not see it."""
    f = facts(pack=("pouch",), props=("crate",))
    found = bv.diff([claim("hands", item="crate", **{"from": bv.FLOOR}, to="pc")], f)
    assert kinds(found) == [("contradiction", "hands")]


def test_a_thing_the_engine_has_no_name_for_is_never_judged():
    f = facts()
    for c in (claim("hands", item=bv.OTHER_THING, **{"from": "pc"}, to="c13"),
              claim("hands", item="pouch", **{"from": "pc"}, to=bv.NOBODY)):
        assert bv.diff([c], f) == []


# --- a sale (was gm/checks/trade_claimed.py) ---------------------------------------------------

def test_a_refused_sale_settled_on_the_page_is_a_contradiction_and_the_refusal_stands():
    """2026-10-03: the engine refused the sale at half past one in the morning and the
    page opened "The transaction is finalized. The heavy clink of the coin…" with the
    refusal, the one thing the player needed to read, nowhere on it."""
    f = facts(outcomes=(REFUSED_SALE,))
    found = bv.diff([claim("trade", item="crate", seller="pc", buyer="c13", settled=True)], f)
    assert kinds(found) == [("contradiction", "trade")]
    assert found[0].line == REFUSED_SALE["tell"]


def test_a_sale_settled_with_no_sale_at_all_is_a_contradiction():
    """kesst:18 — "the transaction is finalized in the eyes of the guild", the crate in
    the pack for six more turns. The regex check needed a sell declared or refused to look
    at all; the engine's record is enough: nothing was sold."""
    found = bv.diff([claim("trade", item="crate", seller="pc", buyer="c12", settled=True)],
                    facts(start="the counting house", end="the counting house"))
    assert kinds(found) == [("contradiction", "trade")]


def test_a_sale_the_engine_made_may_be_shown_and_a_refusal_shown_is_right():
    sold = {"intent_id": "i3", "op": "sell", "status": "resolved", "tell": "Sold.",
            "effects": [{"ref": "pc", "kind": "sold", "item": "crate", "to": "c13"}]}
    assert bv.diff([claim("trade", item="crate", seller="pc", buyer="c13", settled=True)],
                   facts(pack=("pouch",), outcomes=(sold,))) == []
    assert bv.diff([claim("trade", item="crate", seller="pc", buyer="c13", settled=False)],
                   facts(outcomes=(REFUSED_SALE,))) == []


def test_somebody_elses_bargain_is_their_business():
    assert bv.diff([claim("trade", item=bv.OTHER_THING, seller="c12", buyer=bv.NEW_PERSON,
                          settled=True)], facts()) == []


def test_a_refusal_the_page_never_mentions_is_an_omission_unless_the_page_names_the_thing():
    f = facts(outcomes=(dict(REFUSED_SALE, params={"item": "crate"}),))
    found = bv.diff([], f, "The forge is quiet. What do you do?")
    assert kinds(found) == [("omission", "trade")] and found[0].line == REFUSED_SALE["tell"]
    # The page names the crate: the reader may simply have missed how; nothing is added.
    assert bv.diff([], f, "The smith looks the crate over. What do you do?") == []


# --- the hour (was gm/checks/time_of_day.py) -----------------------------------------------------

def test_the_hour_the_page_says_against_the_engines_clock():
    """The owner's saves, 2026-10-03: the clock went from 0 to 88 minutes and the page
    went "the frantic, rhythmic work of the morning", then "the first hint of dawn", then
    "the pre-dawn gloom". The windows are generous on purpose — 19:00 may be "night"."""
    at = lambda clock, part: bv.diff([claim("hour", part=part)], facts(clock=clock))  # noqa: E731
    assert kinds(at(88, "morning")) == [("contradiction", "hour")]
    assert kinds(at(88, "dawn")) == [("contradiction", "hour")]
    assert at(0, "night") == [] and at(360, "dawn") == [] and at(19 * 60, "night") == []
    assert bv.diff([claim("hour", part="morning")], facts(clock=None)) == []


# --- harm and presence ---------------------------------------------------------------------------

def test_harm_is_judged_against_the_state_and_the_rolls():
    """Bobby, 2026-09-28, turn 13: Burning Hands resolved with `targets: []` and the page
    burned the man in the jerkin anyway. "The clerk's eyes drop to the floor" (playtest item
    20) never becomes a claim at all — the reader answers nobody harmed."""
    cast = {"intent_id": "i1", "op": "cast", "status": "resolved", "tell": "",
            "effects": [{"ref": "pc", "kind": "cast", "targets": []}]}
    f = facts(outcomes=(cast,))
    assert kinds(bv.diff([claim("harm", who="c13", how="hurt")], f)) == [
        ("contradiction", "harm")]
    # A wound in a beat where nothing rolled harm is left alone: the engine holds no fact.
    assert bv.diff([claim("harm", who="c13", how="hurt")], facts()) == []
    assert kinds(bv.diff([claim("harm", who="c13", how="down")], facts())) == [
        ("contradiction", "harm")]
    downed = facts(people=(PC, bv.Person("c13", "the smith", down=True), CLERK))
    assert bv.diff([claim("harm", who="c13", how="down")], downed) == []
    assert kinds(bv.diff([claim("harm", who="c13", how="dead")], downed)) == [
        ("contradiction", "harm")]


def test_somebody_who_leaves_while_the_engine_keeps_them_here():
    found = bv.diff([claim("left", who="c12")], facts())
    assert kinds(found) == [("contradiction", "presence")]
    assert bv.diff([claim("left", who=bv.NEW_PERSON)], facts()) == []


def test_a_walk_in_from_open_ground_outside_town_is_a_move():
    """The owner's save, 2026-10-09: "I go to the tavern" from the ridgelines resolved (the
    walk went by the fields, the outskirts and the gate), but the read-back looked the old
    place up among the places known IN TOWN, found nothing, took start == end, and cut the
    true walk as "a move the engine did not make", ending the beat "You are still at the
    tavern." `facts_from` now names a start it cannot find here from its own id."""
    from types import SimpleNamespace

    tavern = SimpleNamespace(id="85addedc9153~urban:the-tavern", name="the tavern")
    gate = SimpleNamespace(id="85addedc9153~urban:the-gate", name="the gate")
    engine = SimpleNamespace(places=lambda: [tavern, gate], open_ground=lambda: [],
                             here=lambda: tavern)
    walk = {"intent_id": "i1", "op": "travel", "status": "resolved",
            "effects": [{"kind": "biome", "place": tavern.id,
                         "was_place": "85addedc9153~hills:@the-ridgelines",
                         "went_by": ["the fields", "the outskirts", "the gate"]}]}
    scene = SimpleNamespace(actors={}, clock_minutes=26 * 1440 + 8 * 60,
                            in_encounter=False, pc=lambda: None, props_here=lambda: [])
    ctx = SimpleNamespace(engine=engine, scene=scene, outcomes=[walk],
                          was_at="85addedc9153~hills:@the-ridgelines")
    f = bv.facts_from(ctx)
    assert f.start == "the ridgelines" and f.end == "the tavern"
    found = bv.diff([claim("move", "You push through the main gates of Scrapden.",
                           place="the gate")], f)
    assert not [d for d in found if d.category == "move"], found
