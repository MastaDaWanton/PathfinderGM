"""Guards who see a wanted character move to arrest them (owner ruling 2026-11-01).

Measured on the owner's report that day (Corvin, turns 56-61): wanted in Reedsink for a
killing, the player stood beside the captain and two guards for six turns and the law did
nothing — a warrant bit at the gate, the counter and in a fight, and nowhere a guard
could simply see you. Now a guard who sees a wanted player comes for them, and the
player's next batch answers: fight, run, talk (Diplomacy or Bluff), or go quietly.
"""
from __future__ import annotations

from rules import arrest, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from tests.test_wanted import MARKET, TOWN, _table, _want


def _guard(s, name="the guardsman"):
    g = s.add(instantiate("guildhand", scene=s, name=name), zone="near")
    g.apply_effect(ActiveEffect(name="of the watch", kind="situation", key="role:guard",
                                source="rule:test", duration="until-dismissed",
                                tags=(states.GUARD,)))
    return g


def _batch(e, *raw):
    raw = list(raw) or [{"op": "narrate_only", "because": "t"}]
    return e.run(e.validate(raw, origin="author:test"))


def _arrests(res):
    """The law's own outcomes: the arrest, and since 2026-11-01 the trial it leads to."""
    return [o for o in res.outcomes if o.op in ("arrest", "trial")]


def _settle(e, res, face):
    while res.awaiting:
        done = list(res.outcomes)
        res = e.resume(face)
        res.outcomes[:0] = [o for o in done if o not in res.outcomes]
    return res


def test_a_guard_who_sees_a_wanted_player_comes_for_them():
    """Corvin's turns 56-61: a guard here, the player wanted, and a batch ends — the watch
    comes, said with the four answers."""
    s, e, pc = _table()
    _want(pc)
    g = _guard(s)
    got = _arrests(_batch(e))
    assert got and "wanted in" in got[0].tell and "Still for Kesst Vayr to choose: go quietly" in got[0].tell, got
    assert "guardsman" in got[0].tell
    assert pc.has_state(states.ARRESTING)


def test_going_quietly_with_nothing_proven_is_questioning_and_release_with_the_warrant_lifted():
    """Going quietly is taken to the gaol and questioned (rules/trial.py, the owner's ruling
    of 2026-11-01). A warrant that says nothing about what it is for, and nothing the
    player did that anybody saw, proves nothing: let go for want of proof, and — the
    owner's "No proof, released" — the warrant lifted. Before the ruling this was a night
    held and release at morning whatever had been done; before the second ruling the
    warrant stood with three days' grace. Let go, they walk out of the gaol into the town
    (`trial.walk_out`, 2026-11-03), and the tell says where."""
    s, e, pc = _table()
    _want(pc)
    _guard(s)
    _batch(e)
    got = _arrests(_batch(e))                      # the player answers with nothing
    assert got and "take" in got[0].tell and "want of proof" in got[0].tell, got
    assert s.at != f"{TOWN}~urban:the-gaol", s.at
    assert f"walks out of the gaol to {e.here().name}" in got[0].tell, got[0].tell
    assert states.standing_with_the_law(pc, TOWN) == "", "the warrant is lifted"
    assert not pc.has_state(states.ARRESTING)
    assert not pc.has_state(states.CUSTODY)
    assert not _arrests(_batch(e)), "nothing left to arrest them on"


def test_talking_the_watch_down_with_diplomacy_stands_them_down_for_the_day():
    s, e, pc = _table()
    _want(pc)
    g = _guard(s)
    _batch(e)
    res = _settle(e, e.run(e.validate([{"op": "check", "actor": "pc", "target": g.ref,
                                        "because": "t", "params": {"skill": "diplomacy"}}])), 20)
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.verdict == "success" and "stand" in check.tell and "down" in check.tell
    assert not _arrests(res), [o.tell for o in res.outcomes]
    assert s.at == MARKET and arrest.stood_down(pc, TOWN)
    assert states.standing_with_the_law(pc, TOWN) == "wanted"


def test_a_failed_bluff_is_taken_in_the_same_turn():
    s, e, pc = _table()
    _want(pc)
    g = _guard(s)
    _batch(e)
    res = _settle(e, e.run(e.validate([{"op": "check", "actor": "pc", "target": g.ref,
                                        "because": "t", "params": {"skill": "bluff",
                                                                   "dc": 30}}])), 1)
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.verdict == "failure" and "not having it" in check.tell
    taken = _arrests(res)
    assert taken and "take" in taken[0].tell and "gaol" in taken[0].tell


def test_running_is_getting_away_with_the_warrant_standing():
    s, e, pc = _table()
    _want(pc)
    _guard(s)
    _batch(e)
    res = _batch(e, {"op": "travel", "actor": "pc", "because": "t",
                     "params": {"place": "the tavern"}})
    got = _arrests(res)
    assert got and "away before" in got[0].tell and "warrant still stands" in got[0].tell
    assert not pc.has_state(states.ARRESTING)


def test_fighting_is_a_fight_the_law_joins():
    s, e, pc = _table()
    _want(pc)
    g = _guard(s)
    _batch(e)
    res = _batch(e, {"op": "attack", "actor": "pc", "target": g.ref, "because": "t",
                     "params": {}})
    assert s.in_encounter and g.ref in s.sides["them"]
    assert not pc.has_state(states.ARRESTING)
    assert not [o for o in _arrests(res) if o.op == "trial"]


def test_nobody_comes_for_the_suspected_the_hidden_or_where_no_guard_stands():
    s, e, pc = _table()
    _want(pc, how="suspected")
    _guard(s)
    assert not _arrests(_batch(e))
    s, e, pc = _table()
    _want(pc)
    assert not _arrests(_batch(e)), "no guard here"
    s, e, pc = _table()
    _want(pc)
    g = _guard(s)
    from rules import awareness

    orig = awareness.sees
    try:
        awareness.sees = lambda scene, obs, sub: False
        assert not _arrests(_batch(e)), "a guard who cannot see the player"
    finally:
        awareness.sees = orig


def test_the_confrontation_is_one_effect_and_removing_it_ends_it():
    """Law 2: the pending arrest is one record; removed, nothing is owed."""
    s, e, pc = _table()
    _want(pc)
    _guard(s)
    _batch(e)
    pc.remove_effects(source=arrest.SOURCE)
    pc.apply_effect(ActiveEffect(name="t", kind="situation", key="x", source="rule:test",
                                 duration="rounds", rounds_left=24 * 600,
                                 tags=(states.stood_down_tag(TOWN),)))
    assert not _arrests(_batch(e))
