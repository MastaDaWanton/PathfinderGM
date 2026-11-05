"""Four ways leave-by-deed misfired in one session (owner report 2026-11-01, Corvin).

The ruling (2026-10-17, docs/conversation.md) stands: a deed in the player's own line
that ends the talk takes their leave first. What went wrong was reading deeds that do not
end a talk as ones that do, and the reverse:

(a) "what is that as I walk next to her" — a `go` to "next to her", no walk in the plan —
    ended the talk with Lila Duskwatch; "walk to a herbalist stall", the walk struck as a
    walk across the market, ended the talk with Snik Dunmoor.
(b) "ask where the smithy is and then go there" — the leave was put after the plan's
    `say`, as if the say opened a talk; its addressee was a placeholder nobody introduced
    (emptied later by `settle_placeholders`), so nobody was in conversation and the leave
    was refused: "You are not in conversation with anybody".
(c) The plan's own bare `leave_talk` with nobody in conversation survived an early return
    and reached the player as the same refusal — turns 35 and 67.
(d) "go find a quiet place to sleep out of the way so noone sees me" was read `search,
    stealth`; the plan's `rest` stood and was refused "You are still in conversation with
    the smith. Take your leave first."
"""
from __future__ import annotations

from gm import judgement
from tests.test_leave_by_deed import _inn, _ops


def test_a_walk_up_to_her_while_talking_does_not_end_the_talk():
    s, e, keeper = _inn()
    read = {"question": True, "actions": [
        {"act": "go", "place": "necxt to her", "span": "walk necxt to her"}]}
    raw = [{"op": "narrate_only"}]
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == ["narrate_only"]


def test_a_walk_across_the_market_that_was_struck_does_not_end_the_talk():
    s, e, keeper = _inn()
    read = {"actions": [{"act": "go", "place": "a herbalist stall",
                         "span": "walk to a herbalist stall"}]}
    raw = [{"op": "narrate_only", "because": "the player moves within the scene"}]
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == ["narrate_only"]


def test_a_real_walk_out_still_takes_leave_first():
    s, e, keeper = _inn()
    read = {"actions": [{"act": "go", "place": "the market", "span": "go to the market"}]}
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == ["leave_talk", "travel"]


def test_a_say_to_a_placeholder_nobody_brings_in_opens_no_talk_to_leave():
    """Corvin's turn 16: nobody in conversation, the plan's say to `new1` with no introduce,
    then the walk. No leave is put in to be refused."""
    s, e, keeper = _inn(talking=False)
    read = {"actions": [
        {"act": "talk", "says": "where thbe smithy is", "span": "ask where thbe smithy is"},
        {"act": "go", "place": "there", "span": "go there as fast as posable"}]}
    raw = [{"op": "say", "actor": "pc", "params": {"words": "Where is the smithy?",
                                                   "to": "new1"}},
           {"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == ["say", "travel"]


def test_a_say_to_somebody_brought_in_by_the_same_plan_still_opens_the_talk():
    s, e, keeper = _inn(talking=False)
    read = {"actions": [
        {"act": "talk", "target": "a porter", "says": "where the smithy is",
         "span": "ask a porter where the smithy is"},
        {"act": "go", "place": "there", "span": "go there"}]}
    raw = [{"op": "introduce", "params": {"who": "a porter", "placeholders": ["new1"]}},
           {"op": "say", "actor": "pc", "params": {"words": "Where?", "to": "new1"}},
           {"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    assert _ops(judgement.leave_before_leaving(raw, '', s, read)) == [
        "introduce", "say", "leave_talk", "travel"]


def test_the_plans_own_leave_with_nobody_to_leave_is_dropped():
    """Turn 35, "go to the town": `leave_talk` then `travel`, nobody in conversation. The
    leave goes; the player never reads "You are not in conversation with anybody"."""
    s, e, keeper = _inn(talking=False)
    read = {"actions": [{"act": "go", "place": "the town", "span": "go to the town"}]}
    raw = [{"op": "leave_talk", "actor": "pc", "target": keeper.ref, "params": {}},
           {"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    notes: list = []
    assert _ops(judgement.leave_before_leaving(raw, '', s, read, notes=notes)) == ["travel"]
    assert any("nobody is in conversation" in n for n in notes)
    # With no reading at all, the same.
    assert _ops(judgement.leave_before_leaving(raw, '', s, {"error": "x"})) == ["travel"]


def test_finding_somewhere_to_sleep_ends_the_talk_before_the_sleep():
    """Turn 32: read `search, stealth`; the plan's rest is the sleep the search was for, so
    the leave is taken before it and the rest resolves."""
    s, e, keeper = _inn()
    read = {"actions": [
        {"act": "search", "object": "a quiet place to sleep",
         "span": "go find a quiet place to sleep"},
        {"act": "stealth", "span": "out of the way so noone sees me"}]}
    raw = [{"op": "rest", "actor": "pc", "params": {"kind": "night"},
            "because": "the player said they sleep"}]
    out = judgement.leave_before_leaving(raw, '', s, read)
    assert _ops(out) == ["leave_talk", "rest"]
    res = e.run(e.validate(out))
    assert [(o.op, o.status) for o in res.outcomes if o.op in ("leave_talk", "rest")] == [
        ("leave_talk", "resolved"), ("rest", "resolved")]
