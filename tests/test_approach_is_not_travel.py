"""Walking up to somebody here is not going somewhere else (item 8, the approach part).

Measured on the owner's 2026-09-30 save, turn_log row 82. A forage at the outskirts met a
Clockwork Spy, put in the scene beside Sam. The player typed **"I aprouch the clockwork
Spy"**; the reading was `seek target: the clockwork Spy`; the plan was ONE `travel` to the
gate. The tell read "You come back into Ledgerwarren … You are at the gate now … Left
behind: Clockwork Spy", and the prose, written at the gate, said the Spy did not exist.

Three causes, three fixes: `travel` was the only movement op the prompt taught out of a
fight (the prompt now says so); `interpret.supported` let `seek` license a travel whatever
the target (a seek of somebody HERE no longer does); and nothing refused a travel that
leaves behind the very person sought (`judgement.refuse_leaving_the_sought`, raised into
the planner's correction path with the fix named).
"""
from __future__ import annotations

import pytest

from gm import interpret, judgement, prompts
from rules.bestiary import instantiate
from rules.intents import IntentError

from test_suggestions_held_to_the_sheet import _market

ROW_82 = "I aprouch the clockwork Spy"
READ_82 = {"question": False, "actions": [{"act": "seek", "target": "the clockwork Spy"}],
           "claims": []}
PLAN_82 = [{"id": "i1", "op": "travel", "params": {"place": "the gate"}}]


def _with_the_spy(worlds):
    s, e = _market(worlds)
    spy = instantiate("thug", scene=s, name="Clockwork Spy")
    s.add(spy)
    return s, e, spy


def test_row_82_is_refused_with_the_move_named(worlds):
    s, e, spy = _with_the_spy(worlds)
    with pytest.raises(IntentError) as err:
        judgement.refuse_leaving_in_place([dict(r) for r in PLAN_82], ROW_82, s,
                                          reading=dict(READ_82))
    said = str(err.value)
    assert f"Clockwork Spy ({spy.ref}) is HERE" in said
    assert "would leave Clockwork Spy behind" in said
    assert '"op": "move"' in said or "narrate the approach" in said


def test_the_fix_names_a_square_beside_them_when_there_is_a_map(worlds):
    s, e, spy = _with_the_spy(worlds)
    if not s.has_grid or spy.ref not in s.positions or "pc" not in s.positions:
        pytest.skip("this world's market has no map")
    from rules import position

    found = position.square_in_reach(s, s.pc(), spy, 5)
    fix = judgement._approach_fix(s, spy)
    if found is not None and found[1] > 0:
        (x, y), _ = found
        assert f'"square": [{x}, {y}]' in fix
    else:
        assert "narrate the approach" in fix


def test_without_a_reading_the_words_themselves_are_read(worlds):
    s, e, spy = _with_the_spy(worlds)
    with pytest.raises(IntentError):
        judgement.refuse_leaving_the_sought([dict(r) for r in PLAN_82], ROW_82, s)


@pytest.mark.parametrize("plan,reading,text", [
    # Taking them along is not leaving them behind.
    ([{"op": "travel", "params": {"place": "the gate", "with": ["SPY"]}}], READ_82, ROW_82),
    # The words themselves ask for the walk.
    (PLAN_82, {"actions": [{"act": "seek", "target": "the clockwork Spy"},
                           {"act": "go", "place": "the gate"}]},
     "I approach the clockwork Spy, then head back to the gate"),
    # Somebody sought who is NOT here: the travel is how you find them.
    (PLAN_82, {"actions": [{"act": "seek", "target": "the harbourmaster"}]},
     "I go looking for the harbourmaster"),
    # No travel at all.
    ([{"op": "narrate_only"}], READ_82, ROW_82),
])
def test_what_is_left_alone(worlds, plan, reading, text):
    s, e, spy = _with_the_spy(worlds)
    plan = [dict(r, params={k: ([spy.ref] if v == ["SPY"] else v)
                            for k, v in (r.get("params") or {}).items()}) for r in plan]
    assert judgement.refuse_leaving_the_sought(plan, text, s, reading) == plan


def test_a_place_chip_is_the_players_own_walk(worlds):
    s, e, spy = _with_the_spy(worlds)
    chip = ({"kind": "place", "id": "x~urban:the-gate", "name": "the gate"},)
    plan = [dict(r) for r in PLAN_82]
    assert judgement.refuse_leaving_in_place(plan, ROW_82, s, reading=dict(READ_82),
                                             attached=chip) == plan


def test_a_seek_of_somebody_here_does_not_license_a_travel(worlds):
    """`_OP_NEEDS["travel"]` holds `seek`; a seek whose target is in the room no longer
    stands behind a detector's travel."""
    s, e, spy = _with_the_spy(worlds)
    frame = {"actions": [{"act": "seek", "target": "the clockwork Spy"}]}
    interpret.ops_for(frame, s, e.places())
    assert frame["actions"][0]["here"] == spy.ref
    assert interpret.supported(["travel"], frame) == ([], ["travel"])
    away = {"actions": [{"act": "seek", "target": "the harbourmaster"}]}
    interpret.ops_for(away, s, e.places())
    assert "here" not in away["actions"][0]
    assert interpret.supported(["travel"], away) == (["travel"], [])


def test_the_prompt_teaches_the_move_out_of_a_fight():
    """`travel` was the only movement op the prompt documented in peacetime."""
    text = prompts.SYSTEM if hasattr(prompts, "SYSTEM") else ""
    import inspect

    src = text or inspect.getsource(prompts)
    assert "Going up to somebody who is HERE is never a travel" in src
    assert '{"op": "move", "actor": "pc", "params":' in src


# --- the approach is a move ---------------------------------------------------------------


def test_an_approach_planned_as_narration_becomes_a_move(worlds):
    """Lane D's live check, 2026-09-30: "I approach it" (reading `seek target: it`) was
    planned as `narrate_only` on the owner's model, so nothing moved and nothing that
    answers a body coming closer could answer it. The approach is a `move` now."""
    s, e, spy = _with_the_spy(worlds)
    s.zones[spy.ref] = "far"
    s.positions.pop(spy.ref, None)          # nobody placed: the zone is what closes
    for ref in [r for r in s.people if r not in ("pc", spy.ref)]:
        s.people.pop(ref)                   # "it" can mean only the Spy
    out = judgement.refuse_leaving_in_place(
        [{"op": "narrate_only"}], "I approach it", s,
        reading={"actions": [{"act": "seek", "target": "it"}]})
    assert out == [{"op": "move", "actor": "pc",
                    "params": {"who": spy.ref, "zone": "engaged"},
                    "because": "the player walks up to Clockwork Spy"}]
    res = e.run(e.validate(out))
    assert s.zones[spy.ref] == "engaged"
    assert res.outcomes[0].tell == f"{s.pc().name} closes on Clockwork Spy."


def test_on_a_map_the_approach_walks_to_a_square_beside_them(worlds):
    s, e, spy = _with_the_spy(worlds)
    if not s.has_grid or spy.ref not in s.positions or "pc" not in s.positions:
        pytest.skip("this world's market places nobody on a map")
    out = judgement.declare_approach([{"op": "narrate_only"}], ROW_82, s, dict(READ_82))
    if out == [{"op": "narrate_only"}]:
        return                                  # within reach already
    assert out[0]["op"] == "move" and "square" in out[0]["params"]
    e.run(e.validate(out))
    assert s.zones[spy.ref] == "engaged"


@pytest.mark.parametrize("plan", [
    [{"op": "move", "actor": "pc", "params": {"zone": "near"}}],
    [{"op": "attack", "actor": "pc", "target": "SPY"}],
])
def test_a_plan_that_already_closes_is_left_alone(worlds, plan):
    s, e, spy = _with_the_spy(worlds)
    plan = [dict(r, target=spy.ref) if r.get("target") == "SPY" else dict(r) for r in plan]
    assert judgement.declare_approach(plan, ROW_82, s, dict(READ_82)) == plan


def test_talking_to_somebody_here_is_not_walking_up_to_them(worlds):
    s, e, spy = _with_the_spy(worlds)
    reading = {"actions": [{"act": "talk", "target": "the clockwork Spy", "says": "hello"}]}
    plan = [{"op": "say", "params": {"to": spy.ref, "words": "hello"}}]
    assert judgement.declare_approach(list(plan), "I greet the clockwork Spy", s,
                                      reading) == plan


def test_approaching_a_creature_holding_its_ground_closes_on_it():
    """Lane D's rule (merged as 8f4d29d): a creature met while foraging holds its ground
    (`state.holding-ground`), and its reaction roll fires only when the player CLOSES on
    it. Live on the owner's model, "I approach it" moved nothing and the roll never
    fired. Here the reading's own `seek target: it` is declared as the move, and the
    engine's batch answers it with the stance outcome — the reaction roll ran."""
    from rules.engine import Engine as _Engine

    if not hasattr(_Engine, "_holding_ground_settles"):
        pytest.skip("Lane D's holding-ground rule is not on this branch yet (8f4d29d)")
    import test_rewards_and_gathering as d

    s, engine = d._room()
    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    try:
        _, _, ref = d._spy(mp, s, engine)
        d._set_2d6(mp, engine, 7 - s.pc().ability_mod("cha"))
        plan = judgement.declare_approach([{"op": "narrate_only"}], "I approach it", s,
                                          {"actions": [{"act": "seek", "target": "it"}]})
        assert plan[0]["op"] == "move", plan
        res = engine.run(engine.validate(plan))
        stance = [o for o in res.outcomes if o.op == "stance"]
        assert stance and "does not give way as you come closer" in stance[0].tell, \
            [o.tell for o in res.outcomes]
    finally:
        mp.undo()


def test_in_a_fight_the_round_moves_bodies(worlds):
    s, e, spy = _with_the_spy(worlds)
    e._ensure_encounter("pc", spy.ref)
    plan = [{"op": "narrate_only"}]
    assert judgement.declare_approach(plan, ROW_82, s, dict(READ_82)) == plan
