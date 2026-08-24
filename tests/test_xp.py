"""Experience: earned by fights, spent by sleeping on it.

"leveling up is something i can just choose to do but it should be gated by Experience
gained from doing things or killing things... once i have enough Exp sleeping should
initiate the leveling process." Before this, /api/level-up was a free button pressed
twice in real play — the live save is level 2 with zero fights won.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import xp
from rules.sheet import load_pc


@pytest.fixture
def fight(tmp_path):
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        c.scene.add(instantiate("thug", scene=c.scene, name="the thug"))
        e = c.engine()
        e.run(e.validate([{
            "op": "begin_encounter",
            "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        yield c, e
        cm._LIVE.clear()


def test_a_creature_from_the_bestiary_knows_its_worth():
    """The thug is CR 1/2 in the book — worth 200 XP on the Core table. Before this,
    xp_value did not exist and every fight was worth nothing."""
    from play import campaign as cm
    from rules.bestiary import instantiate

    scene = cm.begin_with.__self__ if False else None  # instantiate needs no campaign
    thug = instantiate("thug", name="the thug")
    assert thug.xp_value > 0
    assert thug.xp == 0          # its worth is not its own ledger


def test_a_won_fight_pays_the_pc(fight):
    c, e = fight
    foe = c.scene.actors["c1"]
    foe.hp = 0
    line = e._settle_xp()
    pc = c.scene.pc()
    assert pc.xp == foe.xp_value
    assert f"{foe.xp_value:,} XP" in line or f"{foe.xp_value} XP" in line


def test_a_fled_enemy_pays_nothing(fight):
    """Mercy is the GM's `xp` op to reward, not a tax collected by the tally."""
    c, e = fight
    line = e._settle_xp()          # the thug still stands
    assert line == ""
    assert c.scene.pc().xp == 0


def test_the_level_gate_refuses_an_unearned_level(fight):
    from rules import leveling

    c, e = fight
    pc = c.scene.pc()
    out = leveling.level_up(pc, dice=e.dice)
    assert out["ok"] is False
    assert "XP" in out["why"]


def test_sleeping_on_enough_xp_takes_the_level(tmp_path):
    """The whole loop: XP over the threshold, one night's rest, and the character
    wakes a level higher with the night's tell saying so."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        pc = c.scene.pc()
        was = pc.level
        pc.xp = xp.total_for(was + 1)
        e = c.engine()
        res = e.run(e.validate([{"op": "rest", "params": {"kind": "night"}}]))
        cm._LIVE.clear()
    assert pc.level == was + 1
    assert f"level {was + 1} settles" in res.outcomes[-1].tell


def test_sleeping_without_the_xp_levels_nobody(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        pc = c.scene.pc()
        was = pc.level
        e = c.engine()
        e.run(e.validate([{"op": "rest", "params": {"kind": "night"}}]))
        cm._LIVE.clear()
    assert pc.level == was


def test_the_side_panel_reads_the_ledger_and_the_body(tmp_path):
    """summary() carries xp {have, next, ready} and the three needs, each with a
    consequence sentence — the panel says what going without costs before it happens."""
    pc = load_pc("fixtures/pc-kesst.json")
    s = pc.summary()
    assert s["xp"]["have"] == 0
    assert s["xp"]["next"] == xp.total_for(pc.level + 1)
    assert s["xp"]["ready"] is False
    labels = [n["label"] for n in s["needs"]]
    assert labels == ["Thirst", "Hunger", "Rest"]
    for n in s["needs"]:
        assert n["detail"]           # every need explains its consequence
        assert "state" in n and "danger" in n


def test_a_need_turns_dangerous_when_the_clock_runs_out(tmp_path):
    from rules import survival

    pc = load_pc("fixtures/pc-kesst.json")
    pc.awake_minutes = (survival.AWAKE_GRACE_HOURS + 3) * 60
    rest = next(n for n in pc.summary()["needs"] if n["label"] == "Rest")
    assert rest["danger"] is True
    assert "Will save" in rest["state"]
