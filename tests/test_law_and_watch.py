"""Crime to custody, link by link: the 2026-11-15 playtest (a human outlaw in Zhilvarnia).

Measured on the installed 0.3.6: a merchant was beaten senseless and stripped in the
warrens, "It was seen: somebody will be telling the watch" was said, and nothing ever came
of it. An hour waited over him, no watch (#48); Continue and an open wait moved no clock
(#46, #47); the gate's guards were a sentence and never actors (#51); "shout for the city
watch" found another city's captain (#55); a confession to the sergeant was talk (#57); a
surrender mid-fight was read as a follow and the sergeant speared her kneeling (#59, #61);
two convictions read as one fine (#69); the robbery was no theft (#70); and the exits row
offered a walk away to a woman lying dying (#67). Each test names its item.
"""
from __future__ import annotations

from rules import deeds, states, trial
from rules.activeeffect import ActiveEffect
from tests.test_trial import _guard, _run, _seller, _steal_an_apple, _tells
from tests.test_wanted import TOWN, WORLD, _table, _want


def _watch(s):
    return [a for a in s.actors.values() if not a.is_pc and a.has_state(states.GUARD)]


def _wait(e, minutes):
    return _run(e, {"op": "advance_time", "actor": "pc", "because": "t",
                    "params": {"amount": minutes, "unit": "minutes"}})


def _seen_theft():
    """A theft off one seller, seen by a second civilian and no guard: the report is on
    its way, and the player is only suspected yet."""
    s, e, pc = _table()
    _seller(s)
    _seller(s, ref="c91", name="the cooper")
    _steal_an_apple(e, s)
    assert states.standing_with_the_law(pc, TOWN) == "suspected"
    assert not _watch(s)
    return s, e, pc


def test_48_a_report_reaches_the_watch_on_the_clock_and_the_watch_comes():
    """#48: an hour waited beside a witnessed mugging and no watch came — the report was a
    `suspected` tag that nothing read on the clock. Now: report.minutes later the report is
    a warrant, the watch comes to where it happened, and the arrest begins."""
    s, e, pc = _seen_theft()
    res = _wait(e, 5)
    assert not _watch(s), _tells(res)                 # not there yet
    res = _wait(e, int(trial.document()["report"]["minutes"]))
    assert states.standing_with_the_law(pc, TOWN) == "wanted", _tells(res)
    assert len(_watch(s)) == trial.document()["report"]["watch"], _tells(res)
    assert "The watch comes" in _tells(res)
    assert pc.has_state(states.ARRESTING), _tells(res)


def test_48_a_report_whose_witnesses_are_dead_carries_nothing():
    """Skyrim's rule (law.json `report`): the last witness dead before the guards are told,
    the crime is dropped."""
    s, e, pc = _seen_theft()
    told = next(x for x in pc.effects if states.suspected_tag(TOWN) in x.tags)
    for r in told.payload["witnesses"]:
        s.people[r].apply_effect(ActiveEffect(name="dead", kind="situation", key="dead",
                                              source="rule:test", tags=("state.down.dead",),
                                              duration="until-dismissed"))
    _wait(e, 30)
    assert states.standing_with_the_law(pc, TOWN) != "wanted"
    assert not _watch(s)


def test_48_a_witness_lying_senseless_carries_the_report_when_they_come_to():
    """The playtest's save: the mugged merchant was the assault's one witness, unconscious
    and dying beside her. Nobody else saw; the report waits for him to get up."""
    s, e, pc = _seen_theft()
    told = next(x for x in pc.effects if states.suspected_tag(TOWN) in x.tags)
    for r in told.payload["witnesses"]:
        s.people[r].apply_effect(ActiveEffect(name="out", kind="situation", key="out",
                                              source="rule:test",
                                              tags=("state.down.unconscious",),
                                              duration="until-dismissed"))
    _wait(e, 30)
    assert states.standing_with_the_law(pc, TOWN) == "suspected" and not _watch(s)
    for r in told.payload["witnesses"]:
        s.people[r].remove_effects(source="rule:test")
    res = _wait(e, 1)
    assert states.standing_with_the_law(pc, TOWN) == "wanted" and _watch(s), _tells(res)


def test_48_a_report_saved_before_reports_had_a_clock_is_healed_from_its_deed():
    s, e, pc = _seen_theft()
    told = next(x for x in pc.effects if states.suspected_tag(TOWN) in x.tags)
    old = {k: told.payload[k] for k in ("crime", "deed", "what")}
    pc.remove_effects(match=lambda x: x is told)
    pc.apply_effect(ActiveEffect(name=told.name, kind="situation", key=told.key,
                                 source=told.source, origin=told.source,
                                 duration="until-dismissed", tags=told.tags, payload=old))
    res = _wait(e, 1)
    assert states.standing_with_the_law(pc, TOWN) == "wanted" and _watch(s), _tells(res)


def test_48_away_from_the_crime_the_report_is_a_warrant_and_nobody_comes_to_an_empty_street():
    s, e, pc = _seen_theft()
    s.at = f"{TOWN}~urban:the-tavern"
    _wait(e, 30)
    assert states.standing_with_the_law(pc, TOWN) == "wanted"
    assert not _watch(s)


def test_51_the_gate_is_watched_by_people_of_the_scene_once():
    """#51: "the guards at the gate know [your name]" and "In the scene" held only the
    player, so no arrest could ever happen at the gate."""
    s, e, pc = _table()
    _run(e, {"op": "travel", "actor": "pc", "because": "t",
             "params": {"place": "the gate"}})
    assert not _watch(s), "a clean visit is told without guards, and posts none"
    _run(e, {"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the market"}})
    _want(pc, how="suspected")
    _run(e, {"op": "travel", "actor": "pc", "because": "t",
             "params": {"place": "the gate"}})
    assert s.at.endswith(":the-gate")
    posted = _watch(s)
    assert len(posted) == trial.document()["gate_watch"]["count"]
    for g in posted:
        g.apply_effect(ActiveEffect(name="dead", kind="situation", key="dead",
                                    source="rule:test", tags=("state.down.dead",),
                                    duration="until-dismissed"))
    _run(e, {"op": "narrate_only", "because": "t"})
    assert len(_watch(s)) == len(posted), "a gate cleared of its watch is not refilled"


def _fight_the_guard():
    s, e, pc = _table()
    g = _guard(s)
    _run(e, {"op": "attack", "actor": "pc", "target": g.ref, "because": "t", "params": {}})
    assert s.in_encounter
    return s, e, pc, g


def test_59_61_a_surrender_to_the_watch_mid_fight_ends_the_fight_and_goes_to_custody():
    """#59 (read `follow`, nothing applied) and #61 (kneeling, "I yield and will go
    quietly", speared for 7): yielding to the law stops the fight and takes the player in
    by the go-quietly door."""
    s, e, pc, g = _fight_the_guard()
    res = _run(e, {"op": "surrender", "actor": "pc", "target": g.ref, "because": "t"})
    assert not s.in_encounter, _tells(res)
    held = trial.custody(pc)
    assert held is not None and held.payload["stage"] == "questioning", _tells(res)
    assert any(c["kind"] == "assault" for c in held.payload["charges"])
    assert "yields to" in _tells(res)


def test_57_a_confession_to_the_watch_is_the_proof_and_custody_begins():
    """#57: "I tell the sergeant of the watch that I am the one who beat and robbed the
    merchant" got "nor do I care". A deed nobody saw, owned up to a guard's face, is
    charged as caught."""
    s, e, pc = _table()
    v = _seller(s)
    deeds.record(pc, "deed.theft", scene=s, subject=v.ref, subject_name=v.name,
                 what="apple", witnesses=[])          # nobody saw it
    assert states.standing_with_the_law(pc, TOWN) == ""
    g = _guard(s)
    res = _run(e, {"op": "surrender", "actor": "pc", "target": g.ref, "because": "t"})
    held = trial.custody(pc)
    assert held is not None, _tells(res)
    assert [(c["kind"], c["proof"]) for c in held.payload["charges"]] == [("theft", "caught")]


def test_57_nothing_to_own_up_to_is_heard_out_and_let_be():
    s, e, pc = _table()
    g = _guard(s)
    res = _run(e, {"op": "surrender", "actor": "pc", "target": g.ref, "because": "t"})
    assert trial.custody(pc) is None
    assert "nothing to hold" in _tells(res)


def test_55_a_call_for_the_watch_with_none_here_brings_them_on_the_clock():
    """#55: the call found another city's watch; now the local watch comes, and takes the
    player who called for them."""
    s, e, pc = _table()
    _seller(s)
    _seller(s, ref="c91", name="the cooper")
    _steal_an_apple(e, s)
    res = _run(e, {"op": "surrender", "actor": "pc", "because": "t"})
    assert "call goes out" in _tells(res)
    res = _wait(e, int(trial.document()["report"]["minutes"]))
    assert trial.custody(pc) is not None, _tells(res)


def test_55_the_city_watch_is_never_another_citys_captain():
    """#55: "I shout for the city watch" in Zhilvarnia was refused "Xandroslyn,
    Torvathys' City Watch, is in Torvathys, not here"."""
    from types import SimpleNamespace

    from rules import scope

    here = SimpleNamespace(id="here", name="Zhilvarnia", kind="SETTLEMENT", parent_id="")
    there = SimpleNamespace(id="there", name="Torvathys", kind="SETTLEMENT", parent_id="")
    captain = SimpleNamespace(id="x", name="Xandroslyn", kind="CHARACTER", parent_id="there",
                              facts={"Role": "Torvathys' City Watch"})
    world = SimpleNamespace(entities={"here": here, "there": there, "x": captain})
    world.get = lambda i: world.entities.get(i)
    got = scope.look_for(world, "the city watch", None, "here")
    assert got["scope"] != scope.ELSEWHERE and not got["line"], got
    # A name still finds the person: only the office is every town's own.
    assert scope.look_for(world, "Xandroslyn", None, "here")["scope"] == scope.ELSEWHERE


def test_70_stripping_a_man_you_beat_is_a_theft_priced_on_the_haul():
    """#70: the merchant had fought back, so he was "hostile", and the stripping was no
    theft: the only charge was assault, with no confiscation and no double-value fine."""
    s, e, pc = _table()
    victim = _seller(s)
    deeds.record(pc, "deed.violence.unprovoked", scene=s, subject=victim.ref,
                 subject_name=victim.name)

    class _Out:
        op, status, effects, mode = "loot", "resolved", [
            {"ref": pc.ref, "kind": "took", "from": victim.ref,
             "items": ["dagger", "5 sp"]}], ""

    class _Intent:
        actor = pc.ref

        def targets(self):
            return [victim.ref]

    before = {"fight": False, "who": {victim.ref: {
        "hostile": True, "helpless": True, "dying": True, "dead": False, "hurt": True,
        "party": False, "sapient": True, "poor": False}}}
    pc.goods["dagger"] = pc.goods.get("dagger", 0) + 1
    found = deeds.read(e, _Intent(), _Out(), before)
    theft = [r for r in found if r.get("tag") == "deed.theft"]
    assert theft, found
    row = deeds.of(pc, "deed.theft")[-1]
    assert row["items"] == ["dagger", "5 sp"]
    assert trial._items_worth(row["items"]) == 2.0 + 0.5
    # Nobody saw the stripping (he was senseless), but the dagger is on her: caught with
    # it, priced fourfold on the haul, and the dagger goes back.
    row["witnesses"] = []
    theft = [c for c in trial.charges(e, pc, TOWN) if c.kind == "theft"]
    assert theft and theft[0].proof == "caught" and theft[0].taken == ["dagger"], theft
    assert trial.fine_cp(theft[0]) == 4 * 250


def test_69_two_fined_counts_are_each_said():
    """#69: "for assault the law's sentence will be a fine of 1 pp" — two 5 gp fines
    summed and said as one."""
    s, e, pc = _table()
    chs = [trial.Charge(kind="assault", proof="witnessed", what="the merchant"),
           trial.Charge(kind="assault", proof="caught", what="the sergeant")]
    said = trial._fines_said(e, chs)
    assert "for assault (the merchant)" in said and "for assault (the sergeant)" in said
    assert trial._fines_said(e, chs[:1]) == ""


def test_67_no_way_on_is_open_to_a_player_who_cannot_act():
    """#67: dying in the street, the row offered "the bathhouse · withdraw"."""
    from play import exits as exits_mod

    s, e, pc = _table()
    assert any(not r["blocked"] for r in exits_mod.exits(e, WORLD))
    pc.hp = -2
    pc.apply_hp_state()
    rows = exits_mod.exits(e, WORLD)
    assert rows and all(r["blocked"] for r in rows)


def test_46_an_open_wait_puts_time_on_the_clock():
    """#46: "wait to see who comes" was read `wait`, the plan was a bare narrate_only,
    and the clock stuck at 8h 32m."""
    from gm import acts_to_ops

    s, e, pc = _table()
    frame = {"actions": [{"act": "wait", "span": "wait to see who comes"}]}
    raw = acts_to_ops.timed_waits([{"op": "narrate_only"}], frame, s)
    timed = [r for r in raw if r.get("op") == "advance_time"]
    assert timed and timed[0]["params"]["amount"] == acts_to_ops.OPEN_WAIT_MINUTES
    # A wait the plan already timed is left to it.
    raw = [{"op": "advance_time", "params": {"amount": 60, "unit": "minutes"}}]
    assert acts_to_ops.timed_waits(raw, frame, s) == raw


def test_47_continue_out_of_a_fight_moves_the_clock():
    """#47: Continue advanced nothing — same clock, no watch — against the 2026-09-18
    ruling that the world moves a beat."""
    from gm import agent as agent_mod

    s, e, pc = _table()
    me = agent_mod.GMAgent.__new__(agent_mod.GMAgent)
    me.engine = e
    ops = [i.op for i in me._continue_plan().intents]
    assert ops == ["narrate_only", "advance_time"]


def test_55_a_surrender_at_the_gate_finds_its_watch_first_and_is_said_once():
    """Live 2026-11-15 at the gate, suspected: "I shout ... for the city watch, telling
    everyone I beat a merchant" was read as two surrenders, both said "None of the watch is
    here", and only then was the gate's watch posted."""
    from gm import acts_to_ops

    s, e, pc = _table()
    v = _seller(s)
    deeds.record(pc, "deed.violence.unprovoked", scene=s, subject=v.ref,
                 subject_name=v.name, witnesses=[])
    _want(pc, how="suspected")
    e.place_party(f"{TOWN}~urban:the-gate")        # stood there, no batch run yet
    assert not _watch(s)
    frame = {"actions": [{"act": "surrender", "target": "the city watch", "span": "a"},
                         {"act": "surrender", "target": "everyone", "span": "b"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence="a b")
    assert sum(1 for r in rows for b in r.intents if b.get("op") == "surrender") == 1
    res = _run(e, {"op": "surrender", "actor": "pc", "because": "t"})
    assert trial.custody(pc) is not None, _tells(res)
    assert "The gate is watched" in _tells(res) and "None of the watch" not in _tells(res)
