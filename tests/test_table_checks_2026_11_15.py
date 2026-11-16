"""The table-checks lane, 2026-11-15: the older live-play bugs re-checked on 0.3.4 with real
model turns (Fizspark's inn, Kesst Vayr, gemma-4-12B), and what still happened fixed.

Each test names the turn that was measured; docs/recheck-2026-11-15.md has the before and
after prose.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, scenery
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def inn():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the innkeeper"))
    s.add(instantiate("thug", scene=s, name="the potboy"))
    return s


def _ref(s, name):
    return next(r for r, a in s.actors.items() if a.name == name)


# --- a muttered line goes to nobody the plan picked -------------------------------------------

def test_a_muttered_word_is_not_said_to_the_potboy(inn):
    """'I mutter "fool" and walk out' was read `talk`, no target, cost `free`; the plan
    wrote the say to the potboy, one of two people here, and the page had Kesst call him
    a fool (2026-11-07, again 2026-11-15). The reader's own cost says nobody would answer."""
    frame = {"actions": [{"act": "talk", "span": 'mutter "fool"', "says": "fool",
                          "cost": "free"},
                         {"act": "leave", "span": "walk out"}]}
    raw = [{"op": "say", "actor": "pc", "target": _ref(inn, "the potboy"),
            "params": {"words": "fool", "to": _ref(inn, "the potboy")}}]
    notes: list = []
    out = acts_to_ops.address_the_named(raw, frame, inn, notes=notes)
    assert "to" not in out[0]["params"] and "target" not in out[0]
    assert notes and "nobody" in notes[0]


def test_a_line_said_to_the_room_where_somebody_would_answer_keeps_its_addressee(inn):
    """Only the reader's `free` cost strips the plan's pick: "I ask what is on the menu"
    with two people here costs `addresses`, and the plan's innkeeper stands."""
    keeper = _ref(inn, "the innkeeper")
    frame = {"actions": [{"act": "talk", "span": "ask what is on the menu",
                          "cost": "addresses"}]}
    raw = [{"op": "say", "actor": "pc", "params": {"words": "menu?", "to": keeper}}]
    assert acts_to_ops.address_the_named(raw, frame, inn) == raw


# --- a doze is a wait, never a night ---------------------------------------------------------

def test_a_doze_by_the_fire_rents_no_room(inn):
    """"I stroll to the fire, warm my hands and doze off" was read `wait` and the plan wrote
    `rest`; the rest door asked the innkeeper 5 sp for a room (2026-11-07, again with the
    reading fixed on 2026-11-15). A wait and no rest act strikes the plan's rest."""
    frame = {"actions": [{"act": "go", "span": "stroll to the fire"},
                         {"act": "wait", "span": "doze off", "until": "a while"}]}
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    out = acts_to_ops.timed_waits(raw, frame, inn)
    # No rest; the doze is an open wait, the engine's few minutes on the clock (playtest
    # 2026-11-15 #46: an untimed wait used to pass no time at all).
    assert [r["op"] for r in out] == ["narrate_only", "advance_time"]
    assert out[1]["params"]["amount"] == acts_to_ops.OPEN_WAIT_MINUTES


def test_a_rest_the_words_ask_for_beside_a_wait_stays(inn):
    frame = {"actions": [{"act": "wait", "span": "wait for the innkeeper"},
                         {"act": "rest", "span": "take a room and sleep"}]}
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    assert acts_to_ops.timed_waits(raw, frame, inn) == raw


# --- things the deeds handle that are not here -----------------------------------------------

def test_an_offer_of_my_pelts_with_no_pelts_is_said_not_narrated(inn):
    """"I offer the smith my pelts, then leave" with no pelts in the pack was planned a bare
    narrate_only, and the page wrote "You reach into your pack and pull out the bundle of
    pelts" (2026-11-15). The pack answers, printed on the turn whatever else it does."""
    frame = {"actions": [{"act": "sell", "commit": "tried", "object": "my pelts",
                          "target": "the smith", "span": "offer the smith my pelts"},
                         {"act": "leave", "span": "leave"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I offer the smith my pelts, then leave")
    assert rows[0].unheld == "Kesst Vayr has no pelts"
    raw = [{"op": "travel", "actor": "pc", "params": {"to": "the market"}}]
    out = acts_to_ops.things_not_here(raw, rows)
    assert out[-1] == {"op": "narrate_only", "because": "the deed's thing is not here",
                       "params": {"not_here": "Kesst Vayr has no pelts."}}


def test_an_offer_to_help_is_still_talk_not_a_missing_thing(inn):
    """The guard the tried-offer branch was written for: "offer to help him with the crate"
    is no thing the pack must hold."""
    frame = {"actions": [{"act": "sell", "commit": "tried",
                          "object": "to help him with the crate", "span": "offer to help"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I offer to help him with the crate")
    assert not rows[0].unheld and not rows[0].missing


def _asker(answer):
    asked = []

    def ask(place, passages, thing):
        asked.append(thing)
        return answer, ""

    ask.asked = asked
    return ask


def test_a_lamp_no_page_showed_and_no_place_has_is_refused_on_the_turn(inn):
    """"I light the lamp, read the note and burn it" was a bare narrate_only and the page lit
    a lamp nothing recorded (2026-11-15). The reading's `use` object is asked the scenery
    question before the plan; refused, the turn prints it."""
    engine = Engine(inn, Dice(seed=1))
    frame = {"actions": [{"act": "use", "object": "the lamp", "span": "light the lamp"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I light the lamp")
    ask = _asker(scenery.WRONG_PLACE)
    got = scenery.handled(frame, rows, engine, ["The inn is quiet."], ask_fn=ask)
    assert ask.asked == ["the lamp"] and got[0]["answer"] == scenery.WRONG_PLACE
    assert rows[0].unheld == "there is no lamp here"
    assert inn.prop_named("lamp") is None


def test_a_commonplace_lamp_is_ledgered_and_nothing_is_said(inn):
    engine = Engine(inn, Dice(seed=1))
    frame = {"actions": [{"act": "use", "object": "the lamp", "span": "light the lamp"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I light the lamp")
    scenery.handled(frame, rows, engine, [], ask_fn=_asker(scenery.COMMON))
    assert not rows[0].unheld and inn.prop_named("the lamp") is not None


def test_my_rope_not_carried_is_answered_by_the_pack_without_asking(inn):
    engine = Engine(inn, Dice(seed=1))
    frame = {"actions": [{"act": "use", "object": "my grappling hook",
                          "span": "use my grappling hook"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I use my grappling hook")
    ask = _asker(scenery.COMMON)
    scenery.handled(frame, rows, engine, [], ask_fn=ask)
    assert ask.asked == [] and rows[0].unheld == "Kesst Vayr has no grappling hook"


def test_with_the_reader_off_nothing_is_asked_or_refused(inn):
    engine = Engine(inn, Dice(seed=1))
    frame = {"actions": [{"act": "use", "object": "the lamp", "span": "light the lamp"}]}
    rows = acts_to_ops.table(frame, inn, sentence="I light the lamp")
    assert scenery.handled(frame, rows, engine, [], ask_fn=None) == []
    assert not rows[0].unheld


# --- the welcome's gesture is not the same in every campaign ---------------------------------

def test_the_welcome_example_gesture_is_drawn_not_fixed(monkeypatch):
    """Two of three welcomes opened on the fixed example ("[I look at your character
    sheet.]", "[I glance at your sheet.]", 2026-11-07 and 2026-11-15); with no example, two
    of three opened "[Nods slowly.]". A welcome is said once a campaign, so the example is
    drawn each time from WELCOME_GESTURES instead."""
    from play import table_talk

    assert "sheet" not in " ".join(table_talk.WELCOME_GESTURES)
    picked = table_talk._gesture_rule(True, table_talk.WELCOME_GESTURES[2])
    assert table_talk.WELCOME_GESTURES[2] in picked
    assert "sheet" not in picked


# --- a fight in a short window ----------------------------------------------------------------

def test_a_fight_in_a_short_window_lowers_the_books_floor():
    """At 800x600 in a fight the desk's choices were 13px and at 900x600 37px, holding End
    turn (34px) (tools/table_hit_test.js, 2026-11-15); the book's 45% floor gives way in a
    fight under 640px tall, and the board's under 760. The layout itself was measured in
    the browser at 1024x700, 1000x640, 900x600 and 800x600; this pins only that the rule
    is still there."""
    from pathlib import Path

    css = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert ".stage:has(#combatbar:not([hidden]))" in css
    assert "max-height: 639.98px" in css and "max-height: 759.98px" in css


# --- small items off the 2026-09-30 fix plan, still open on 0.3.4 ----------------------------

def test_a_quote_handed_back_on_its_comma_closes_inside_the_quote():
    """`ensure_hand_back("He waits by the door. 'Go home,'")` returned "…'Go home,'. What
    do you do?" on 0.3.4 (docs/fix-plan-2026-09-30.md, Lane A, "a dangling ,'.")."""
    from gm import narration

    said, changed = narration.ensure_hand_back("He waits by the door. 'Go home,'")
    assert changed and said == "He waits by the door. 'Go home.' What do you do?"
    assert narration.ensure_hand_back('He says, "Fine."')[0] == 'He says, "Fine." What do you do?'


def test_searching_for_tracks_seeks_nobody():
    """`person_sought("I search for tracks")` was "tracks" on 0.3.4, and "look for signs of
    the beast" was "signs": the fallback minted a person for a trail (Lane B)."""
    from gm import judgement

    assert judgement.person_sought("I search for tracks") == ""
    assert judgement.person_sought("I look for signs of the beast") == ""
    assert judgement.person_sought("I look for the smith") == "smith"


# --- the opening's errand, away from its place -----------------------------------------------

def test_the_errand_card_says_where_its_facts_are_once_the_party_has_left(inn):
    """The opening's card is on every brief (`always_on`) and its facts are its place's:
    live 2026-11-15, 2 of 2 walks out of Fizspark's inn ended "You emerge into the lane …
    The lingering silence of the dining room … remains". Away from its place, the card
    says its facts are that place's; at its place, nothing is added."""
    from rules import cards

    inn.at = "a40700fc8b75~urban:the-inn"
    cards.open_card(inn, cards.Card(
        id="opening", title="A meal you could afford", place=inn.at, always_on=True,
        facts=["You have a bowl in front of you and half of it left."]), turn=1)
    assert "where the party is not now" not in cards.brief(inn, [], turn=1)
    inn.at = "a40700fc8b75~urban:the-lane"
    away = cards.brief(inn, [], turn=1)
    assert "[set at the inn, where the party is not now: its facts describe that place" in away
