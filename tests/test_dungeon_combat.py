"""Leaving fights, hostile rooms on a route, and darkness: playtest 2026-11-16 #55, #65, #57.

Vesna Kroll, a human with no light, fought a dire rat in the turnkey's room of the
gardens' sewers, walked to the cells ("The fight is left behind"), and later walked back
out through the turnkey's room without meeting the rat. The next beat described the cells'
scorched plaster and a stranger's ink-dotted knuckles in a room she could not see.
"""
from __future__ import annotations

from gm import prompts
from rules import reactions, states
from tests.test_playtest_2026_11_16_travel import _city, _place, _run


def _sewers():
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    return s, e


def _rat_fight(s, e, speed=None):
    rat = e._bring_in("rat-dire")[0]["ref"]
    if speed is not None:
        s.actors[rat].speed = speed
    e._ensure_encounter(rat, target="pc")
    assert s.in_encounter
    return rat


def _eyes(actor, tag):
    actor.add_condition("probe-eyes", source="test")
    actor.effects[-1].tags = (tag,)


def test_a_hungry_beast_follows_the_walker_out_and_the_fight_goes_on():
    """#55 (T272): walking out of melee with a dire rat (speed 40) said "The fight is left
    behind" to a walker at 30. A beast at least as fast follows; the fight goes on where
    the walk stops, with the rat in it."""
    s, e = _sewers()
    rat = _rat_fight(s, e)
    tell = " ".join(o.tell for o in _run(e, {"op": "travel",
                                              "params": {"place": "the main channel"}}))
    assert s.at.endswith("the-main-channel"), tell
    assert "left behind" not in tell and "comes after you" in tell, tell
    assert s.people[rat].at == s.at and s.in_encounter
    assert any(rat in refs for refs in s.sides.values())


def test_a_slower_beast_keeps_the_grudge_and_waylays_the_way_back():
    """#65 (T283): the walk out went straight through the room where the rat had been
    left at full health one beat earlier. Left behind it is hostile, and a walk whose way
    runs through its room stops there and the fight opens."""
    s, e = _sewers()
    rat = _rat_fight(s, e, speed=20)
    tell = " ".join(o.tell for o in _run(e, {"op": "travel",
                                              "params": {"place": "the outfall"}}))
    assert "fight is left behind" in tell, tell
    assert states.attitude_of(s.people[rat]) == "hostile"
    tell = " ".join(o.tell for o in _run(e, {"op": "travel",
                                              "params": {"place": "the main channel"}}))
    assert s.at.endswith("the-gardens/the-sewers"), tell        # stopped in its room
    assert "got no further" in tell and "comes at you" in tell, tell
    assert s.in_encounter and any(rat in refs for refs in s.sides.values())


def test_no_attack_of_opportunity_at_what_the_dark_hides():
    """#55, the book half: "You can't execute an attack of opportunity against an opponent
    with total concealment" (CRB p.196), and darkness is total concealment to eyes without
    darkvision (CRB p.172). The rat has low-light vision only; the old reader treated a
    foe in the dark as seen, and the withdraw's start-square exemption with it."""
    s, e = _sewers()
    rat = _rat_fight(s, e)
    pc = s.pc()
    assert s.sees_nothing(s.actors[rat], pc) and s.sees_nothing(pc, s.actors[rat])
    assert reactions._cannot_see(s, rat, "pc")
    assert not reactions._seen_by(s, "pc", rat)
    _eyes(s.actors[rat], "sense.darkvision.60")
    assert not reactions._cannot_see(s, rat, "pc")              # darkvision sees her


def test_pitch_dark_is_said_on_every_beat_and_faces_go_unseen():
    """#57 (T273): out of a fight the narrator heard nothing of the dark, and the brief
    handed it a stranger's face. In pitch dark the light line goes in on every beat, and
    a lit hand takes it away."""
    s, e = _sewers()
    line = prompts.light_now(s, [])
    assert "sees nothing at all" in line and "hear, smell and feel" in line, line
    s.pc().add_condition("probe-torch", source="test")
    s.pc().effects[-1].payload = {"light": {"radius_ft": 20, "raised_ft": 40}}
    assert not s.sees_nothing(s.pc())
    assert "sees nothing" not in prompts.light_now(s, [])
