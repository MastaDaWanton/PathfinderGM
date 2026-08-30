"""Combat as a distinct state: buttons straight to the engine.

Every combat action used to be a spoken turn — a model call to plan "I attack the thug"
before any die came out. The panel emits whitelisted ops directly; the free-text box
stays for the unconventional, and goes through the GM as it always did.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules.sheet import load_pc


@pytest.fixture
def fight(tmp_path):
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        # Seeded, because the NPC turn this fixture hands the round to rolls real
        # attacks against a 9-hit-point rogue. Measured over twelve unseeded runs of
        # the end-turn case: one dropped Kesst to -3, which ends the fight, and
        # `Scene.end_encounter` clears `acted` — so `assert "pc" in scene.acted` failed
        # about one run in five at suite level with nothing wrong with the code. A test
        # gate that lies two runs in five teaches you to re-run instead of investigate.
        c.seed = 20260830
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        c.scene.add(instantiate("thug", scene=c.scene, name="the thug"))
        e = c.engine()
        e.run(e.validate([{
            "op": "begin_encounter",
            "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        # The panel only serves the PC's turn; wind the order to them.
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _act(client, actions, label="", end_turn=True):
    return client.post("/api/combat/act",
                       data=json.dumps({"actions": actions, "label": label,
                                        "end_turn": end_turn}),
                       content_type="application/json")


def test_outside_a_fight_the_panel_is_refused(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        r = _act(Client(), [{"op": "attack", "target": "c1"}])
        cm._LIVE.clear()
    assert r.status_code == 409


def test_an_op_off_the_whitelist_is_refused(fight):
    client, cm = fight
    r = _act(client, [{"op": "give", "params": {"item": "everything"}}])
    assert r.status_code == 400
    assert "combat-panel" in r.json()["error"]


def test_a_strike_suspends_into_the_players_own_roll(fight):
    """The PC rolls their own to-hit: the attack suspends, the panel's response carries
    `awaiting`, and the existing dice popup answers it — one roll pipeline, not two."""
    client, cm = fight
    r = _act(client, [{"op": "attack", "target": "c1", "params": {}}],
             label="Strike the thug")
    assert r.status_code == 200
    d = r.json()
    assert d["awaiting"], "the attack should be waiting on the player's d20"
    assert cm.current().transcript[-2]["text"] == "Strike the thug" \
        or any(b["text"] == "Strike the thug" for b in cm.current().transcript[-3:])


def test_answering_the_roll_finishes_the_turn_and_the_thug_answers_back(fight):
    client, cm = fight
    _act(client, [{"op": "attack", "target": "c1", "params": {}}], label="Strike")
    guard = 0
    while cm.current().scene.awaiting and guard < 8:
        # Each stage asks for its own die — to-hit d20, then damage — so the answer has
        # to fit the prompt in front of it, not the one before.
        prompt = cm.current().scene.awaiting
        face = min(15, int(prompt.get("max", 20)))
        client.post("/api/roll", data=json.dumps({"face": face}),
                    content_type="application/json")
        guard += 1
    scene = cm.current().scene
    assert not scene.awaiting
    # The order moved: it is the player's turn again (the thug acted between), or the
    # fight ended on the spot — both are the machinery working.
    assert scene.current_ref() in ("pc", None)


def test_a_stated_iteration_swings_at_its_own_penalty(fight):
    """Blood Bond mixes abilities into a full attack, so the leftover weapon swings
    arrive one op each and must keep their -5: a mixed full attack whose swings all
    rolled at full BAB would be the panel quietly buffing the class it was built for."""
    client, cm = fight
    pc = cm.current().scene.pc()
    pc.flat_attack = None
    pc.level = 8                              # BAB +8/+3 as a monk-BAB stand-in
    cm.current().save()
    _act(client, [{"op": "attack", "target": "c1",
                   "params": {"iteration": 1}}], label="second swing")
    awaiting = cm.current().scene.awaiting
    assert awaiting, "should be waiting on the swing's d20"
    # The prompt's modifier is the sheet's second-iteration bonus, 5 below the first.
    first = [m for m in pc.attack_modifiers(None, 0)]
    second = [m for m in pc.attack_modifiers(None, 1)]
    assert sum(m.value for m in first) - sum(m.value for m in second) == 5
    assert awaiting["modifier"] == sum(m.value for m in second)


def test_end_turn_handss_the_round_onward(fight):
    client, cm = fight
    r = _act(client, [], end_turn=True)
    assert r.status_code == 200
    scene = cm.current().scene
    assert scene.current_ref() in ("pc", None)   # went round and came back, or ended
    assert "pc" in scene.acted                    # passing is still acting


def test_not_your_turn_is_refused(fight):
    client, cm = fight
    scene = cm.current().scene
    while scene.current_ref() == "pc":
        scene.advance_turn()
    cm.current().save()
    r = _act(client, [{"op": "attack", "target": "c1"}])
    assert r.status_code == 409
    assert "not your turn" in r.json()["error"].lower()


def test_a_fight_lays_the_ground_it_promised(fight):
    """"No ground is mapped. A grid is laid out when a fight starts" — the map tray has
    said so since the grid shipped, and nothing anywhere ever laid one: Scene.grid was
    assigned in tests and nowhere else. Every real fight played mapless."""
    client, cm = fight
    scene = cm.current().scene
    assert scene.grid is not None
    assert "pc" in scene.positions and "c1" in scene.positions
    # Zones drove the placement: a near foe stands a short walk away, not on top of you.
    px, py = scene.positions["pc"]
    fx, fy = scene.positions["c1"]
    assert abs(px - fx) + abs(py - fy) >= 2


def test_the_ground_goes_with_the_fight(fight):
    client, cm = fight
    scene = cm.current().scene
    e = cm.current().engine()
    e.run(e.validate([{"op": "end_encounter", "params": {}}]))
    assert scene.grid is None
    assert not scene.positions


def test_a_grid_the_gm_already_laid_is_kept(tmp_path):
    """`begin_encounter` lays a grid only when none exists: a deliberate battlefield —
    difficult terrain and all — must not be flattened by the default one."""
    from play import campaign as cm
    from rules.bestiary import instantiate
    from rules.grid import Grid

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.add(instantiate("thug", scene=c.scene, name="the thug"))
        laid = Grid(width=12, height=9)
        laid.difficult.add((3, 3))
        c.scene.grid = laid
        e = c.engine()
        e.run(e.validate([{
            "op": "begin_encounter",
            "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        assert c.scene.grid is laid
        assert (3, 3) in c.scene.grid.difficult
        cm._LIVE.clear()
