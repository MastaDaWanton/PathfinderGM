"""Somebody knocked out is still somebody.

Measured 2026-09-25 by probe: unconscious and stable carry `state.down.fallen` beside
dead, and `tidy_the_fallen` departed every non-player with that tag after its two-turn
grace. An NPC knocked out with non-lethal damage, at FULL hit points, left the campaign
on the third call with no tell at all; a dying man who stabilised on the roll went the
same way. Prisoners, spared thugs and fallen companions vanished. Only a corpse ages out
now.
"""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _room():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    who = instantiate("thug", scene=s, name="thug")
    s.add(who, zone="near")
    return s, who, Engine(s, Dice(seed=11))


def test_a_man_knocked_out_at_full_health_is_still_in_the_room():
    s, thug, engine = _room()
    thug.add_condition("unconscious", source="non-lethal damage")
    assert thug.hp > 0 and thug.has_state("state.down.fallen")
    for _ in range(6):
        engine.tidy_the_fallen()
    assert thug.ref in s.people, "a knocked-out man left the campaign"
    assert thug.ref in s.actors, "and he was moved out of the room he fell in"


def test_a_man_who_stabilised_stays_where_he_lies():
    s, thug, engine = _room()
    thug.hp = -1
    thug.apply_hp_state()
    thug.remove_condition("dying")
    thug.add_condition("stable", source="a healer's hand")
    for _ in range(6):
        engine.tidy_the_fallen()
    assert thug.ref in s.actors


def test_a_corpse_still_ages_out():
    s, thug, engine = _room()
    thug.hp = -50
    thug.apply_hp_state()
    assert thug.has_state("state.down.dead")
    for _ in range(3):
        engine.tidy_the_fallen()
    assert thug.ref not in s.people


def test_the_dying_resolve_and_only_the_dead_of_them_go():
    """Whichever way the dice fall, the outcome and the room agree."""
    for seed in range(12):
        s, thug, _ = _room()
        engine = Engine(s, Dice(seed=seed))
        thug.hp = -1
        thug.apply_hp_state()
        assert thug.has_condition("dying")
        for _ in range(3):
            engine.tidy_the_fallen()
        dead = thug.has_state("state.down.dead")
        assert (thug.ref in s.people) is (not dead), seed
