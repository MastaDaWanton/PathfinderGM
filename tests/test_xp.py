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


def test_a_renamed_creature_still_knows_what_it_is_worth():
    """"I got 0 Exp from killing the bear."

    `instantiate` overwrites `name` with whatever the GM calls the creature, so "a bear"
    spawned from `black-bear` lost every link back to its stat block — and `worth` reads
    the stat block. A creature was worth nothing the moment anybody named it. The
    template is kept now, because the display name is the GM's to change and the
    template is not."""
    from rules import xp
    from rules.bestiary import instantiate

    bear = instantiate("black-bear", name="a bear")
    assert bear.from_template == "black-bear"
    assert xp.worth(bear) == 800


def test_a_creature_from_an_older_save_is_recovered_by_name():
    """Healed on read rather than migrated, the way `Campaign.biome` heals a save
    written before biomes existed: every creature already in a scene when `xp_value`
    arrived carries a zero."""
    from rules import xp
    from rules.sheet import from_dict

    old = from_dict({"name": "black bear", "kind": "npc", "hp": 1,
                     "abilities": {"str": 10, "dex": 10, "con": 10,
                                   "int": 2, "wis": 10, "cha": 5}}, ref="c1")
    assert old.xp_value == 0            # nothing was stored
    assert xp.worth(old) == 800         # and it is recovered anyway


def test_a_name_that_names_no_creature_is_worth_nothing_and_says_so():
    """"a bear" is not a creature in the corpus — there are black bears and dire bears
    and guessing which would be inventing a number. Zero is the honest answer, and the
    fight's tell has to say the award is the GM's to make rather than staying silent."""
    from rules import xp
    from rules.sheet import from_dict

    lost = from_dict({"name": "a bear", "kind": "npc", "hp": 1,
                      "abilities": {"str": 10, "dex": 10, "con": 10,
                                    "int": 2, "wis": 10, "cha": 5}}, ref="c1")
    assert xp.worth(lost) == 0


def test_a_fight_that_pays_nothing_explains_itself(tmp_path):
    from django.test import override_settings

    from play import campaign as cm
    from rules.sheet import from_dict

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        nameless = from_dict({"name": "a bear", "kind": "npc", "hp": 0,
                              "abilities": {"str": 10, "dex": 10, "con": 10,
                                            "int": 2, "wis": 10, "cha": 5}}, ref="c1")
        c.scene.add(nameless)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        line = e._settle_xp()
        cm._LIVE.clear()
    assert "No experience" in line and "GM's to make" in line
