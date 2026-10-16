"""The body's conditions read back off the beat and held to the engine's tags.

The 2026-10-16 report (0.2.19, free narrator, a market brawl): "it was unclear if the user
was grappled or if the narration just described it that way and the latter shouldn't
happen." The engine never grappled anyone — no grapple op, no `state.held.grappled` — and
across three beats the page had a woman's hands "reaching out to grab you by the throat",
then "her fingers digging into your throat", then "Her fingers tighten around your
throat … her grip intended to crush your wind". The English reader of the day
(gm/state_claims.py) had no grappled row at all; its one hit in that fight was a false
"prone" on "aiming to knock you off your feet" — an aim — which cut the wind-up down to
its filler.

So the question moves to the read back (gm/beat_verify.py): on a fight's beats the reader
reports `conditions` — who, and which, from the tag vocabulary's closed list — each with a
quote held to the page, and code judges each against `has_state` for that person.
These tests pin the code half; the reader's numbers are in docs/beat-verify.md.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_verify as bv

PC = bv.Person("pc", "Kesst Vayr", pc=True)
WOMAN = bv.Person("c4", "woman with the braid", "commoner")
ATTACK_MISS = {"intent_id": "i1", "op": "attack", "status": "resolved", "effects": [],
               "tell": "Kesst Vayr's attack with the dagger misses the woman with the "
                       "braid (6 against AC 10)."}


def facts(**kw):
    base = dict(start="the market", end="the market", places=("the market",),
                people=(PC, WOMAN), clock=600, outcomes=(ATTACK_MISS,), in_fight=True)
    base.update(kw)
    return bv.Facts(**base)


def claim(sentence="Her fingers dig into your throat.", **slots):
    return bv.Claim("condition", slots, quote=sentence, sentence=sentence, valid=True)


def test_a_grip_the_engine_never_made_is_a_contradiction_about_the_player():
    """The report's beat 13: "her fingers digging into your throat" with nobody grappled."""
    found = bv.diff([claim(who="pc", condition="grappled")], facts())
    assert [(d.kind, d.category) for d in found] == [("contradiction", "condition")]
    assert found[0].fact.startswith("You (the player) are not grappled: nobody has hold of you")


def test_a_condition_the_engine_holds_is_reporting_not_invention():
    held = bv.Person("pc", "Kesst Vayr", pc=True, holds=("grappled",))
    assert bv.diff([claim(who="pc", condition="grappled")], facts(people=(held, WOMAN))) == []


def test_a_condition_this_turn_gave_or_took_is_not_judged():
    """A trip that landed and was stood up from inside one batch, a grapple broken this
    turn: the effect names the condition for that body, so the prose may say it."""
    tripped = {"intent_id": "i1", "op": "attack", "status": "resolved", "tell": "",
               "effects": [{"ref": "c4", "kind": "condition", "condition": "prone"}]}
    f = facts(outcomes=(tripped,))
    assert bv.diff([claim("She goes down hard.", who="c4", condition="prone")], f) == []
    # ... and only for that body.
    assert bv.diff([claim("You go down hard.", who="pc", condition="prone")], f)


def test_a_body_on_the_floor_is_not_judged_for_prone():
    down = bv.Person("c4", "woman with the braid", "commoner", down=True)
    assert bv.diff([claim("She lies sprawled in the dirt.", who="c4", condition="prone")],
                   facts(people=(PC, down))) == []


def test_somebody_away_held_by_the_page_is_absent():
    away = bv.Person("c4", "woman with the braid", "commoner", here=False)
    found = bv.diff([claim(who="c4", condition="grappled")], facts(people=(PC, away)))
    assert [d.category for d in found] == ["absent"]


def test_the_slot_is_asked_only_on_a_fights_beats():
    """Every other beat is asked exactly what it was before: the `shown_here` rule, for
    the reason docs/beat-verify.md measured (a slot shown where it cannot apply competes
    with its neighbours)."""
    calm = facts(in_fight=False, outcomes=())
    assert "conditions" not in bv.schema(calm)["properties"]
    assert all("conditions" not in m["content"] for m in bv.messages("x", calm))
    fight = facts()
    s = bv.schema(fight)
    assert s["properties"]["conditions"]["items"]["properties"]["condition"]["enum"] == \
        list(bv.CONDITIONS)
    assert "conditions" in s["required"]
    # A blow resolved outside a declared fight counts too (the turn that opens one).
    assert bv.Facts(start="x", end="x", places=(), outcomes=(ATTACK_MISS,)).bodies
    # Never in an intimate scene between adults.
    assert not facts(intimate=True).bodies


def test_the_demonstration_shows_an_attempt_as_no_condition_and_a_hold_as_one():
    msgs = bv.messages("x", facts())
    demo = msgs[3]["content"]
    answer = json.loads(msgs[4]["content"])
    assert "meaning to pull you off your feet" in demo, "an aim, reported as nothing"
    assert answer["conditions"] == [{"who": "c5", "condition": "grappled",
                                     "quote": "seizes the drover by the arm and holds "
                                              "him fast"}]
    assert answer["harmed"], "the demonstration still teaches harm"
    # Every demonstrated quote is the demonstration's own words (`place_quote` holds a
    # live answer to the page in exactly this way).
    for row in answer["conditions"] + answer["harmed"]:
        assert row["quote"] in demo


def _reply(answer):
    class R:
        text = json.dumps(answer)
        seconds = 0.1

        def json(self):
            return answer
    return R()


def test_a_scripted_read_round_trips_to_a_finding():
    """The whole member, with the model's answer scripted: the claim validated against the
    page, compared, and confirmed by the second read."""
    text = ("She is inches away, her fingers digging into your throat. The crowd draws "
            "back. What do you do?")
    f = facts()
    answer = {"player_ends_at": {"place": "the market", "quote": ""}, "changed_hands": [],
              "trades": [], "harmed": [], "arrived": [], "left": [], "time_of_day": [],
              "conditions": [{"who": "pc", "condition": "grappled",
                              "quote": "her fingers digging into your throat"}]}
    reading = bv.read(text, f, chat=lambda *a, **k: _reply(answer), model="m")
    assert [c.category for c in reading.claims] == ["condition"]
    found = bv.diff(reading.claims, f, text)
    kept, refuted, _s = bv.confirm(found, text, f, chat=lambda *a, **k: _reply(
        {"answer": "yes"}), model="m")
    assert [d.category for d in kept] == ["condition"] and not refuted
    assert "grappled — held fast" in bv.question(kept[0], f)
    assert "not only grabbed at, aimed at" in bv.question(kept[0], f)


def test_an_off_vocabulary_condition_is_dropped():
    text = "Fear grips you as she raises the club."
    answer = {"conditions": [{"who": "pc", "condition": "frightened",
                              "quote": "Fear grips you as she raises the club"}]}
    reading = bv.read(text, facts(), chat=lambda *a, **k: _reply(answer), model="m")
    assert not reading.claims


@pytest.mark.parametrize("cond", bv.CONDITIONS)
def test_every_condition_is_a_key_of_the_tag_vocabulary(cond):
    """One vocabulary (law one): each value the reader may answer is a `states.TAGS` key,
    asked through its leaf tag, never matched as a string."""
    from rules import states

    assert cond in states.TAGS
    assert states.tags_for(cond)[0].startswith("state.")
