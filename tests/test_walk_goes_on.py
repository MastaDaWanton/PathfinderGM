"""A walk cut short by the crowd goes on once the crowd is pushed through (owner report
2026-11-01, Corvin, turns 12-15).

"walk to the weapon smith" was stopped at the north crossing by a squabble ("the crowd
round them will not part … You were making for the smithy and got no further than the
north crossing"). "Try to push through the crowd" made its Strength check by 6 — and
nothing walked on. "keep going" was read with no action at all and "keep walking" as a
`go` with no place: both narrated, neither moved. The walk's end lived only in that turn's
tell (`stopped_short` / `meant_for` on the travel record, read by nothing).

Now the cut walk is an intent the walker holds (`states.MAKING_FOR`, one effect through
the applicator); a push past the people in the way that succeeds, or a walk with nowhere
named, carries it on to where it was for.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import ontheway, states
from rules.dice import Dice
from tests.test_on_the_way import EAST, ZHIL, _go, _meetings, _walker

SQUARE = f"{ZHIL}~urban:the-great-square"


def _cut(monkeypatch):
    """Market → east crossing, stopped by a squabble in the great square."""
    s, e, pc = _walker()
    _meetings(monkeypatch, None, "squabble", None)
    out = _go(e, pc, EAST)
    assert s.at == SQUARE and out.effects[0]["stopped_short"], out.tell
    _meetings(monkeypatch)                                   # quiet streets from here on
    return s, e, pc


def _turn(e, s, frame, face=None):
    rows = acts_to_ops.table(frame, s, places=tuple(e.places()))
    raw = [i for r in rows for i in r.intents]
    return rows, _settle(e, e.run(e.validate(raw)), face)


def _settle(e, res, face):
    """The player's own d20, as the page sends it (`Engine.resume`)."""
    while res.awaiting and face is not None:
        done = list(res.outcomes)
        res = e.resume(face)
        res.outcomes[:0] = [o for o in done if o not in res.outcomes]
    return res


def test_a_cut_walk_is_held_as_where_the_walker_is_making_for(monkeypatch):
    s, e, pc = _cut(monkeypatch)
    walk = ontheway.walk_cut(s, pc)
    assert walk is not None and walk["to"] == EAST and walk["at"] == SQUARE
    assert walk["kind"] == "squabble" and len(walk["by"]) >= 1
    assert pc.has_state(states.MAKING_FOR)


def test_pushing_through_the_crowd_and_making_it_walks_on(monkeypatch):
    """Corvin's turn 13: an exert at "the crowd" where the walk was cut is a push past the
    people in the way; a Strength check made carries the walk on to the east crossing."""
    s, e, pc = _cut(monkeypatch)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "exert", "commit": "tried", "target": "the crowd",
         "span": "Try to push through the crowd"}]}
    rows, out = _turn(e, s, frame, face=20)
    assert rows[0].intents[0]["params"].get("past") is True, rows[0].note
    check = next(o for o in out.outcomes if o.op == "check")
    assert check.verdict == "success"
    assert s.at == EAST, [o.tell for o in out.outcomes]
    assert out.outcomes[-1].op == "travel"
    assert ontheway.walk_cut(s, pc) is None, "the walk was carried on"
    assert not pc.has_state(states.MAKING_FOR)


def test_a_push_that_fails_leaves_the_walker_where_the_crowd_held_them(monkeypatch):
    s, e, pc = _cut(monkeypatch)
    res = e.run(e.validate([{"op": "check", "actor": pc.ref, "because": "t",
                             "params": {"skill": "strength", "dc": {"band": "formidable"},
                                        "past": True}}]))
    out = _settle(e, res, 1)
    assert [o.op for o in out.outcomes] == ["check"]
    assert out.outcomes[0].verdict == "failure"
    assert s.at == SQUARE
    assert ontheway.walk_cut(s, pc) is not None, "a failed push forgot the walk"


def test_keep_walking_with_nowhere_named_goes_on_to_where_the_walk_was_for(monkeypatch):
    """Corvin's turn 15: `go` with no place, while a walk is cut, is that walk carried on."""
    s, e, pc = _cut(monkeypatch)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "span": "keep walking"}]}
    rows, out = _turn(e, s, frame)
    assert s.at == EAST, [o.tell for o in out.outcomes]
    assert "east crossing" in out.outcomes[-1].tell


def test_a_bare_go_with_no_cut_walk_builds_nothing(monkeypatch):
    s, e, pc = _walker()
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "go", "span": "keep walking"}]}, s, places=tuple(e.places()))
    assert rows[0].intents == []


def test_any_walk_lifts_the_cut_walk(monkeypatch):
    """Gone somewhere else, the old intent is gone: "keep going" from the tavern does
    not march the walker back to yesterday's destination."""
    s, e, pc = _cut(monkeypatch)
    _go(e, pc, f"{ZHIL}~urban:the-market")
    assert ontheway.walk_cut(s, pc) is None
    assert not pc.has_state(states.MAKING_FOR)


def test_helping_somebody_else_with_their_load_is_still_aid_another(monkeypatch):
    """A cut walk does not turn every heave into a shove: an exert whose target is somebody
    here who did NOT stop the walk is Aid Another on their effort, as before."""
    from rules.bestiary import instantiate

    s, e, pc = _cut(monkeypatch)
    carter = instantiate("guildhand", scene=s, name="the carter")
    s.add(carter)
    s.move(carter.ref, s.at)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "exert", "target": "the carter", "span": "help the carter with his cart"}]}
    rows = acts_to_ops.table(frame, s, places=tuple(e.places()))
    params = rows[0].intents[0]["params"]
    assert params.get("aid") and not params.get("past")
