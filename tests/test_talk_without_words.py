"""Speaking to somebody with no words given opens the talk (owner report 2026-11-01, Corvin).

Turns 61, 62 and 66: "go back to the gaurds and ask whatr they called me for", "Speak to
Snik Dunmoor." and "Address the guardsmen directly." The reading had a person and no
words, `say` needs words, so the act→op table owed nothing and three turns narrated with
no conversation opened. And "the guardsmen" did not find the guardsman standing there:
the room finder matched exact words, so a plural named nobody and the introduce detector
brought a second guardsman in beside the first.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import scope, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _market():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    snik = instantiate("guildhand", scene=s, name="Snik Dunmoor")
    s.add(snik)
    guard = instantiate("guildhand", scene=s, name="the guardsman")
    s.add(guard)
    return s, Engine(s, Dice(seed=2)), snik, guard


def _turn(s, e, actions):
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": actions}, s)
    raw = [i for r in rows for i in r.intents]
    return rows, (e.run(e.validate(raw)) if raw else None)


def test_speak_to_somebody_with_no_words_opens_the_talk():
    s, e, snik, guard = _market()
    rows, res = _turn(s, e, [{"act": "talk", "target": "Snik Dunmoor",
                              "span": "Speak to Snik Dunmoor"}])
    assert [i["op"] for i in rows[0].intents] == ["greet"]
    out = res.outcomes[0]
    assert out.status == "resolved", out.tell
    assert "You are in conversation with Snik Dunmoor" in out.tell
    assert snik.has_state(states.TALKING) and not guard.has_state(states.TALKING)


def test_the_guardsmen_finds_the_guardsman():
    s, e, snik, guard = _market()
    assert scope.in_the_room(s, "the guardsmen") == guard.ref
    assert scope.in_the_room(s, "the guards") == ""      # no guard is named a guard here
    rows, res = _turn(s, e, [{"act": "talk", "target": "the guardsmen",
                              "span": "Address the guardsmen directly"}])
    assert rows[0].intents and rows[0].intents[0]["params"]["who"] == guard.ref


def test_walking_up_to_them_and_asking_with_no_words_speaks_to_whom_was_walked_to():
    """Turn 61's shape: a `go` to a person here, then `talk` to "they" with no words."""
    s, e, snik, guard = _market()
    rows, res = _turn(s, e, [
        {"act": "go", "place": "the guardsman", "span": "go back to the guardsman"},
        {"act": "talk", "target": "they", "span": "ask what they called me for"}])
    greet = [i for r in rows for i in r.intents if i["op"] == "greet"]
    assert greet and greet[0]["params"]["who"] == guard.ref
    assert guard.has_state(states.TALKING)


def test_words_given_are_still_a_say_and_no_greeting_is_built():
    s, e, snik, guard = _market()
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "Snik Dunmoor", "says": "about the rumors",
         "span": "Speak to Snik Dunmoor about the rumors"}]}, s)
    assert not rows[0].intents and rows[0].ops == ["say"]


def test_somebody_already_in_the_talk_is_not_greeted_twice():
    s, e, snik, guard = _market()
    e.join_talk(snik)
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "Snik Dunmoor", "span": "Speak to Snik Dunmoor"}]}, s)
    assert not rows[0].intents


def test_a_greeting_is_code_only_and_never_offered_to_the_plan():
    from rules.intents import CODE_ONLY_OPS

    assert "greet" in CODE_ONLY_OPS


def test_a_plural_never_matches_a_different_word():
    """The singular is the only thing taken off: "guards" is not "guardsman"."""
    assert scope._one("guardsmen") == "guardsman" and scope._one("guards") == "guard"
    assert scope._one("glass") == "glass" and scope._one("ladies") == "lady"
