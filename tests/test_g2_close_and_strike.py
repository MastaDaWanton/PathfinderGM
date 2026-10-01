"""Close the distance and strike, when one move reaches (the owner's ruling, 2026-09-29).

The measurement, live 2026-09-28 (`tools/narrator_audit.py --script fight`): "I punch him
in the face." came back 422 — "Kesst Vayr reaches 5 ft and Gorvoth Vexarion is 15 ft
away; a melee attack needs them within reach. Click square 5,6 on the map to move there
(10 ft), then strike." Three turns in a row, and the fight never moved; the rest of the
script did nothing.

The ruling: "yes close the distance and strike if one move reaches." The rules it rests
on, from the Core Rulebook's Combat chapter as Archives of Nethys prints it:

- "In a normal round, you can perform a standard action and a move action, or you can
  perform a full-round action" (aonprd.com/Rules.aspx?ID=129, Action Types).
- "A move action allows you to move up to your speed" (ID=129); moving your speed is the
  simplest move action (ID=137, Move Actions).
- "Making an attack is a standard action" (ID=130, Standard Actions) — ONE attack at the
  highest bonus. "You must use a full-round action to get your additional attacks. The
  only movement you can take during a full attack is a 5-foot step" (ID=145).
- "Moving out of a threatened square usually provokes attacks of opportunity from
  threatening opponents" (ID=102, Attacks of Opportunity).
- "Each square of difficult terrain counts as 2 squares of movement" (ID=177).
- Charge is its own full-round action (ID=185); this engine has none, and the closing
  step is never one.

So: a blow one move short walks the step (a real `move`, told and provoking) and swings
once. Beyond one move, or with the move action already walked this round, today's
refusal stands.
"""
from __future__ import annotations

import json
import re

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import load_pc


def _fight(seed: int = 7):
    """The board test_maneuver_reach.py measured the reach defect on: Kesst at (4,10), the
    thug at (7,10), fifteen feet apart, the fight running and Kesst holding the turn."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter("pc", "c1")
    assert scene.positions["pc"] == (4, 10) and scene.positions["c1"] == (7, 10)
    assert scene.get("pc").speed_feet == 30
    return scene, engine


def _attack(params=None, actor="pc", target="c1"):
    return {"op": "attack", "actor": actor, "target": target, "visibility": "hidden",
            "because": "test", "params": dict(params or {})}


def _finish(engine, res):
    for _ in range(12):
        if not res.awaiting:
            break
        res = engine.resume(min(15, int(res.awaiting.get("max", 20))))
    return res


def _to_hit_rolls(outcome) -> list:
    """The d20s rolled to hit in one attack outcome (initiative and damage dice are not)."""
    return [r for r in outcome.rolls
            if r.die == "1d20" and "confirm" not in r.label.lower()]


# --- the measured line ------------------------------------------------------------------

def test_fifteen_feet_with_speed_thirty_closes_and_strikes_once():
    """The measurement: 15 ft off, speed 30, "I punch him" refused three turns running.
    Now the step the refusal named (10 ft to (6,10)) is walked as a move and ONE blow
    follows — a move action and a standard action (ID=129, ID=130)."""
    scene, engine = _fight()
    thug_hp = scene.get("c1").hp
    intents = engine.validate([_attack({"weapon": "unarmed"})])
    res = _finish(engine, engine.run(intents))
    ops = [o.op for o in res.outcomes]
    assert ops == ["move", "attack"], [o.tell for o in res.outcomes]
    step, blow = res.outcomes
    assert step.tell == "Kesst Vayr closes 10 ft on the thug to strike."
    assert step.effects[0]["kind"] == "position" and step.effects[0]["feet"] == 10
    assert step.effects[0]["closing_on"] == "c1"
    assert scene.positions["pc"] == (6, 10)
    assert scene.distance_between("pc", "c1") == 5
    assert blow.status != "refused" and len(_to_hit_rolls(blow)) == 1, blow.tell
    # The action economy: the move action is recorded as walked this round.
    assert scene.move_spent["pc"] == scene.round
    # The tell carries no number the model authored and no grid square.
    assert "[" not in step.tell and "{" not in step.tell
    assert scene.get("c1").hp <= thug_hp


def test_one_attack_not_a_full_attack_even_at_bab_six():
    """"The only movement you can take during a full attack is a 5-foot step" (ID=145):
    a blow that needs the step is a standard action, so a declared full attack at BAB +6
    swings once. The control, already in reach, swings twice — which is what shows the
    count measures the iteratives and not a quirk of the board."""
    scene, engine = _fight()
    pc = scene.get("pc")
    while pc.bab < 6:
        pc.level += 1
    assert len(pc.attack_plan("unarmed", True)) >= 2
    res = _finish(engine, engine.run(engine.validate(
        [_attack({"weapon": "unarmed", "full_attack": True})])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert len(_to_hit_rolls(res.outcomes[-1])) == 1

    control, engine2 = _fight()
    cpc = control.get("pc")
    while cpc.bab < 6:
        cpc.level += 1
    control.positions["pc"] = (6, 10)
    control.resync_zones()
    res2 = _finish(engine2, engine2.run(engine2.validate(
        [_attack({"weapon": "unarmed", "full_attack": True})])))
    assert [o.op for o in res2.outcomes] == ["attack"]
    assert len(_to_hit_rolls(res2.outcomes[-1])) >= 2


def test_a_second_blow_behind_the_closing_one_is_not_swung():
    """"I keep hitting him" planned as two attacks, or the combat panel's full attack
    split one swing per op: after the step, the second is a full attack after a move,
    which ID=145 forbids. It is refused in prose; only the first rolls."""
    scene, engine = _fight()
    res = _finish(engine, engine.run(engine.validate([
        _attack({"weapon": "unarmed", "iteration": 0}),
        _attack({"weapon": "unarmed", "iteration": 1})])))
    assert [o.op for o in res.outcomes] == ["move", "attack", "attack"]
    assert len(_to_hit_rolls(res.outcomes[1])) == 1
    last = res.outcomes[2]
    assert last.status == "refused" and not last.rolls
    assert "one blow" in last.tell


def test_forty_feet_with_speed_thirty_is_still_refused():
    """Beyond one move the ruling does not walk anybody: the nearest square in reach is
    35 ft off and Kesst moves 30, so today's refusal stands, naming the square — and a
    walk the player did not ask for is not taken in its place."""
    scene, engine = _fight()
    scene.positions["c1"] = (12, 10)
    scene.resync_zones()
    assert scene.distance_between("pc", "c1") == 40
    with pytest.raises(IntentError) as err:
        engine.validate([_attack({"weapon": "unarmed"})])
    assert err.value.code == "out_of_reach"
    assert "close in this turn and strike on the next" in err.value.for_a_person
    assert scene.positions["pc"] == (4, 10)
    assert "pc" not in scene.move_spent


def test_the_step_provokes_the_attack_of_opportunity_the_rules_give():
    """"Moving out of a threatened square usually provokes" (ID=102). A second thug
    stands beside Kesst; the closing step leaves the square he threatens, so his swing
    lands BEFORE the step completes — the same splice a declared move gets
    (`Engine._reactions_before`), not a copy of it."""
    scene, engine = _fight()
    other = scene.add(instantiate("thug", scene=scene, name="the other thug"))
    engine.join_fight(other.ref)
    scene.positions[other.ref] = (4, 9)
    scene.resync_zones()
    from rules import reactions

    assert reactions.threatens(scene, other.ref, (4, 10))
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    said = [(o.op, o.tell) for o in res.outcomes]
    assert [o.op for o in res.outcomes] == ["attack", "move", "attack"], said
    assert res.outcomes[0].tell.startswith("the other thug's attack"), said
    assert res.outcomes[1].tell.startswith("Kesst Vayr closes 10 ft"), said
    assert scene.reacted.get(f"{other.ref}:attack_of_opportunity") == 1


def test_an_attack_of_opportunity_that_drops_the_attacker_stops_the_blow():
    """The reason the step is a real intent: an attack of opportunity lands as the
    creature leaves the square, "so if it drops them they never arrive" (`_drive`) —
    and the blow behind a step never taken is never swung."""
    res = None
    for seed in range(40):
        scene2, engine2 = _fight(seed)
        thug_hp = scene2.get("c1").hp
        other2 = scene2.add(instantiate("thug", scene=scene2, name="the other thug"))
        engine2.join_fight(other2.ref)
        scene2.positions[other2.ref] = (4, 9)
        scene2.resync_zones()
        scene2.get("pc").hp = 1
        res = _finish(engine2, engine2.run(engine2.validate(
            [_attack({"weapon": "unarmed"})])))
        if scene2.get("pc").is_down:
            break
    else:
        pytest.skip("no seed in forty had the attack of opportunity drop Kesst")
    assert scene2.positions["pc"] == (4, 10), "dropped as he left, he never arrived"
    blow = res.outcomes[-1]
    assert blow.op == "attack" and not _to_hit_rolls(blow)
    assert scene2.get("c1").hp == thug_hp


def test_a_move_action_already_walked_this_round_leaves_the_refusal_standing():
    """"A standard action and a move action" — one move. Kesst walks sideways first
    (still 15 ft off), so the step is spent: the next blow is refused as it was before
    the ruling, and the same list [move, attack] is refused at the floor in prose."""
    scene, engine = _fight()
    engine.run(engine.validate([{"op": "move", "actor": "pc",
                                 "params": {"square": [4, 11]}}]))
    assert scene.distance_between("pc", "c1") == 15
    assert scene.move_spent["pc"] == scene.round
    with pytest.raises(IntentError) as err:
        engine.validate([_attack({"weapon": "unarmed"})])
    assert err.value.code == "out_of_reach"
    assert scene.positions["pc"] == (4, 11)

    scene, engine = _fight()
    res = engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"square": [4, 11]}},
        _attack({"weapon": "unarmed"})]))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert res.outcomes[-1].status == "refused"
    assert "Nothing is rolled" in res.outcomes[-1].tell
    assert scene.positions["pc"] == (4, 11)


def test_the_next_round_gives_the_move_action_back():
    """Spent is per round (`Scene.move_spent` holds the round number, so no second
    ticker clears it): the round after, the step is Kesst's again."""
    scene, engine = _fight()
    engine.run(engine.validate([{"op": "move", "actor": "pc",
                                 "params": {"square": [4, 11]}}]))
    scene.round += 1
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]


def test_a_zone_relabel_is_not_a_move_action_walked():
    """The model's habit on this board: `move zone=engaged` before the blow, which on a
    mapped fight relabels the zone and leaves the body where it stood (docs/fix-interfaces
    §3.4). It moved nobody, so it spends nothing — counting it would put the stall
    straight back, one turn later."""
    scene, engine = _fight()
    res = _finish(engine, engine.run(engine.validate([
        {"op": "move", "actor": "pc", "params": {"zone": "engaged"}},
        _attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes] == ["move", "move", "attack"]
    assert scene.distance_between("pc", "c1") == 5
    assert _to_hit_rolls(res.outcomes[-1])


# --- difficult terrain ------------------------------------------------------------------

def _terrain_board(walk_squares: int, difficult: bool):
    """Kesst at (2,10); the thug far enough east that the walk to the square beside him
    is `walk_squares` squares; with `difficult`, every square from column 3 to the thug
    is rubble, top to bottom, so no route goes round it."""
    scene, engine = _fight()
    thug_x = 2 + walk_squares + 1
    grid = Grid(width=20, height=20)
    if difficult:
        grid.difficult = {(x, y) for x in range(3, thug_x + 1) for y in range(20)}
    scene.grid = grid
    scene.positions["pc"] = (2, 10)
    scene.positions["c1"] = (thug_x, 10)
    scene.resync_zones()
    return scene, engine


def test_difficult_terrain_doubles_a_fifteen_foot_walk_to_thirty_and_it_still_fits():
    """Three squares of rubble cost 30 ft ("each square of difficult terrain counts as
    2 squares of movement", ID=177) — exactly Kesst's speed, so one move reaches."""
    scene, engine = _terrain_board(3, difficult=True)
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert res.outcomes[0].effects[0]["feet"] == 30
    assert "closes 30 ft" in res.outcomes[0].tell


def test_a_twenty_foot_walk_through_difficult_terrain_does_not_fit():
    """Four squares of rubble are 40 ft of a 30-ft move: refused, as before the ruling.
    The control — the same twenty feet of open floor — fits."""
    scene, engine = _terrain_board(4, difficult=True)
    with pytest.raises(IntentError) as err:
        engine.validate([_attack({"weapon": "unarmed"})])
    assert err.value.code == "out_of_reach"
    assert scene.positions["pc"] == (2, 10)

    scene, engine = _terrain_board(4, difficult=False)
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert res.outcomes[0].effects[0]["feet"] == 20


def test_an_occupied_square_is_walked_round_not_through():
    """"Occupied squares respected": the square straight ahead of the thug is somebody
    else's, so the step goes to the next best square in reach — one the move op itself
    would accept — and never onto another body."""
    scene, engine = _fight()
    other = scene.add(instantiate("thug", scene=scene, name="a drunk"))
    other.add_condition("bystander", source="test")
    scene.positions[other.ref] = (6, 10)
    scene.resync_zones()
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes] == ["move", "attack"]
    assert scene.positions["pc"] != (6, 10)
    assert scene.distance_between("pc", "c1") == 5


# --- what it does not touch -------------------------------------------------------------

def test_a_manoeuvre_closes_the_same_way():
    """The reach refusal covers the manoeuvres (docs/maneuver-outcomes.md), and so does
    the ruling: a trip made in place of a melee attack is a standard action too."""
    scene, engine = _fight()
    res = _finish(engine, engine.run(engine.validate([_attack({"manoeuvre": "trip"})])))
    # The step, then — since 2026-09-30, a trip without Improved Trip provoking its
    # target (tests/test_reactions.py) — the thug's swing, then the trip.
    assert [o.op for o in res.outcomes] == ["move", "attack", "attack"]
    assert res.outcomes[1].tell.startswith("the thug"), res.outcomes[1].tell
    assert res.outcomes[-1].status != "refused", res.outcomes[-1].tell


def test_the_swing_that_opens_a_fight_still_only_joins_battle():
    """Out of combat the first swing opens the fight through the battle gate and rolls
    nothing, and so it closes nothing either: the step is taken with the blow, on the
    attacker's first combat turn."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"), at=(4, 10))
    scene.add(instantiate("thug", scene=scene, name="the thug"), at=(7, 10))
    scene.grid = Grid(width=20, height=20)
    engine = Engine(scene, Dice(seed=3))
    res = engine.run(engine.validate([_attack({"weapon": "unarmed"})]))
    assert "Battle is joined" in res.outcomes[0].tell
    assert [o.op for o in res.outcomes if o.op == "move"] == []
    assert scene.positions["pc"] == (4, 10)
    # And the blow on that first turn closes and lands.
    res = _finish(engine, engine.run(engine.validate([_attack({"weapon": "unarmed"})])))
    assert [o.op for o in res.outcomes][:2] == ["move", "attack"]


def test_a_reaction_and_a_coup_de_grace_never_walk():
    """An attack of opportunity is taken where you stand; a coup de grâce is a
    full-round action with no move beside it (ID=145). Neither closes."""
    scene, engine = _fight()
    from rules.intents import Intent

    pc, thug = scene.get("pc"), scene.get("c1")
    for params in ({"reaction": "attack_of_opportunity"}, {"coup_de_grace": True}):
        intent = Intent(op="attack", actor="pc", target="c1", params=dict(params))
        assert engine._closing_step(intent, pc, thug, "unarmed") is None


def test_a_pick_up_spends_the_move_so_a_rearmed_swing_out_of_reach_closes_instead():
    """Picking a weapon up is a move action (Table 7-2), and it is a `give`, not a walk,
    so the engine's `move_spent` cannot see it. Without the rearm settling it, a disarmed
    thug's model plan [attack] out of reach became pick-up + closing step + swing: two
    move actions AND a standard. Now the swing goes and the second move action closes."""
    from gm import judgement
    from test_creature_rearms import _disarmed

    scene, engine, pc, thug = _disarmed()
    scene.positions["pc"] = (2, 10)
    scene.resync_zones()
    raw, repairs = judgement.rearm(scene, "c1", [
        {"op": "attack", "actor": "c1", "target": "pc"}])
    assert [r["op"] for r in raw] == ["give", "move"], raw
    assert "rearm: the target is out of reach; it closes instead of swinging" in repairs


# --- the fight script's opening line, through the plan ------------------------------------

class _Reply:
    def __init__(self, text, model="fake"):
        self.text, self.seconds, self.model = text, 0.0, model

    def json(self):
        return json.loads(self.text)


def test_the_fight_scripts_punch_through_the_plan_advances_the_fight(monkeypatch):
    """G2's replay proof. "I punch him in the face." through `plan_turn`, the model
    answering the attack it answered live. Before: a player-fixable refusal
    (`out_of_reach`), the turn ended on it, three turns running. Now: no refusal, one
    plan call, and the plan's own intents run to a closing step and a rolled blow."""
    from gm import agent as agent_mod

    scene, engine = _fight()
    from _a_truth import WORLD

    engine.world = WORLD
    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        return _Reply(json.dumps({"narration": "", "intents": [
            {"op": "attack", "actor": "pc", "target": "c1",
             "params": {"weapon": "unarmed"}}]}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    gm = agent_mod.GMAgent(WORLD, engine)
    plan = gm.plan_turn("I punch him in the face.", history=[])
    assert plan.refusal is None, plan.refusal
    assert len(calls) == 1
    assert [i.op for i in plan.intents] == ["attack"]
    res = _finish(engine, engine.run(plan.intents))
    assert [o.op for o in res.outcomes][:2] == ["move", "attack"]
    assert scene.distance_between("pc", "c1") == 5
    assert _to_hit_rolls(res.outcomes[1])
    assert re.search(r"closes \d+ ft on the thug", res.outcomes[0].tell)


def test_the_step_is_spent_across_a_save_and_a_reload():
    """`move_spent` is saved beside `reacted`, for its reason: a fight put down mid-turn
    must not hand back a move action already walked."""
    from django.test import override_settings

    import tempfile
    from pathlib import Path

    from play import campaign as cm

    with tempfile.TemporaryDirectory() as tmp, \
            override_settings(CAMPAIGN_DIR=Path(tmp) / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.move_spent = {"pc": 3}
        c.save()
        cm._LIVE.clear()
        again = cm.current()
        assert again.scene.move_spent == {"pc": 3}
        cm._LIVE.clear()
