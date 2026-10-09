"""`ActiveEffect.periodic` gets its heal and damage executors (plan §12.6).

The states-effects-tells ledger listed periodic damage and heal as "promised, not built":
the schema had a `periodic` list and one consumer (`spend_pool`, the rage's upkeep), so an
effect could SAY "fast healing 1" and nothing would ever heal anybody. Troll blood's quench
mark is fast healing; it needed a consumer before it could be written.
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect, PERIODIC_CLOCKS, from_dict
from rules.dice import Dice
from rules.engine import Engine, Scene, _ward_tell
from rules.sheet import load_pc


def _scene(seed=2):
    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    scene._dice = Dice(seed=seed)
    return scene, pc


def _rollover(scene):
    """Two bodies in an initiative order and one full pass: the top of a round, where the
    round's per-round work fires (`Scene._next_able`)."""
    from rules.bestiary import instantiate

    if len(scene.initiative) < 2:
        other = scene.add(instantiate("thug", scene=scene, name="the thug"))
        scene.enrol("pc", 20)
        scene.enrol(other.ref, 1)
    scene.advance_turn()                # the first turn of the fight: round one, no rollover
    first = scene.round
    for _ in range(4):
        scene.advance_turn()            # each call starts a fresh `hazards` list
        if scene.round == first + 1:
            return list(scene.hazards)
    raise AssertionError("no round rolled over")


def test_fast_healing_heals_each_round_and_is_told():
    """Before the executor an effect carrying `{"heal": 1}` healed 0 hit points across any
    number of rounds. Now one played round heals one point, through `Actor.heal`, and the
    round's record is a `heal` the narration already knows how to say (law 3)."""
    scene, pc = _scene()
    pc.hp = pc.hp_max - 5
    pc.apply_effect(ActiveEffect(name="troll-blood quench", kind="buff",
                                 source="item:troll-blade", origin="item:troll-blade",
                                 duration="rounds", rounds_left=10,
                                 periodic=[{"heal": 1}]))
    said = _rollover(scene)
    heals = [h for h in said if h.get("kind") == "heal" and h.get("ref") == "pc"]
    assert pc.hp == pc.hp_max - 4, said
    assert heals and heals[0]["amount"] == 1 and heals[0]["origin"] == "item:troll-blade"
    assert _ward_tell(scene, heals[0]) == "troll-blood quench restores 1 hit points to Kesst Vayr."


def test_healing_at_full_hit_points_says_nothing():
    """An application that changed nothing is not a tell: a narrator told "restores 1 hit
    point" at full health would describe a wound closing that was never open."""
    scene, pc = _scene()
    pc.hp = pc.hp_max
    pc.apply_effect(ActiveEffect(name="regrowth", kind="buff", rounds_left=5,
                                 duration="rounds", periodic=[{"heal": 2}]))
    assert pc.run_periodic("round", 1, scene._dice) == []


def test_a_burn_that_keeps_burning_goes_through_take_damage():
    """Periodic damage meets resistance in 1e's order, because it goes through
    `take_damage` like every other point: 1d4+3 fire against resist fire 5 can do at
    most 2, never the 7 a raw subtraction would take."""
    scene, pc = _scene()
    pc.resistances = {"fire": 5}
    before = pc.hp
    pc.apply_effect(ActiveEffect(name="burning pitch", kind="buff", rounds_left=3,
                                 duration="rounds",
                                 periodic=[{"damage": "1d4+3", "damage_type": "fire"}]))
    said = pc.run_periodic("round", 1, scene._dice)
    assert len(said) == 1 and said[0]["kind"] == "damage" and said[0]["type"] == "fire"
    assert 0 <= before - pc.hp <= 2 and said[0]["amount"] == before - pc.hp
    assert "fire damage from burning pitch" in _ward_tell(scene, said[0])


def test_a_days_work_runs_once_per_day_crossed_and_never_per_round():
    """A `per: day` entry runs once per day boundary the clock crosses: three days, three
    times — never once per round of them.

    This test also pinned that a per-ROUND heal did nothing across `Scene.advance` ("an
    eight-hour rest is 4,800 rounds and firing a round's work that often would heal a
    troll 4,800 points"). That was the defect the owner hit on 2026-10-09 — fast healing
    5 and "my health is not going up" — and the book's answer to the troll is that it IS
    whole after eight hours. Per-round heals now run over the stretch, capped at full and
    at each effect's rounds left (`run_periodic(elapsed=True)`,
    tests/test_rest_and_fast_healing.py); per-round damage and saves still do not."""
    scene, pc = _scene()
    # Three days without water roll thirst checks on the clock's door since 2026-10-05
    # (rules/survival.py, `charge`); this measures the periodic heal alone.
    for need in ("needs.no_sleep", "needs.no_food", "needs.no_water"):
        pc.overrides[need] = True
    pc.hp = pc.hp_max - 10
    pc.apply_effect(ActiveEffect(name="slow mending", kind="buff",
                                 periodic=[{"heal": 2, "per": "day"}]))
    scene.clock_minutes = 600
    scene.advance(minutes=3 * 1440)
    assert pc.hp == pc.hp_max - 10 + 3 * 2
    scene.advance(minutes=60)                  # no boundary crossed
    assert pc.hp == pc.hp_max - 4


def test_a_daily_save_gate_rolls_and_lands_on_failure():
    """Viridium's daily price (a carried `save_gate`) is an `effect` entry on the day
    clock: the save is rolled with the body's own modifiers and the d20's face read by
    `dice.d20_succeeds`; failing lands the condition with the item as its origin."""
    scene, pc = _scene(seed=9)
    pc.apply_effect(ActiveEffect(
        name="carrying the viridium dagger", kind="carried", source="item:vd",
        origin="item:vd",
        periodic=[{"per": "day", "effect": {
            "type": "save_gate", "target": "fort", "dc": 99,
            "on_failure": [{"type": "apply_condition", "target": "sickened"}]}}]))
    said = pc.run_periodic("day", 1, scene._dice)
    sick = [e for e in pc.effects if e.key == "sickened"]
    # DC 99 fails on anything but a natural 20.
    if said and said[0]["kind"] == "ward_saved":
        assert not sick
    else:
        assert sick and sick[0].origin == "item:vd"


def test_the_upkeep_consumer_still_runs_beside_the_new_ones():
    """`spend_pool` stays `Scene._drain_periodic`'s and the executor skips it: one owner
    per job, so a rage is not charged twice a round."""
    scene, pc = _scene()
    pc.apply_effect(ActiveEffect(name="rage", kind="ability", source="rage",
                                 periodic=[{"spend_pool": "rage", "or_ends": True}]))
    assert pc.run_periodic("round", 1, scene._dice) == []


def test_periodic_entries_round_trip_with_their_clock():
    """The clock is part of the record: a `per: day` heal saved and loaded is still a day's
    work, not silently a round's."""
    e = ActiveEffect(name="mending", periodic=[{"heal": 2, "per": "day"}])
    back = from_dict(e.as_dict())
    assert back.periodic == [{"heal": 2, "per": "day"}]
    assert PERIODIC_CLOCKS == ("round", "day")


def test_engine_round_tick_reaches_the_executor():
    """The per-round firing is reached from the round rollover the engine already runs —
    the one place `tick_effects`, `tick_pools` and the upkeep run — not from a second
    ticker of its own."""
    scene, pc = _scene()
    Engine(scene, Dice(seed=1))
    pc.hp = pc.hp_max - 3
    pc.apply_effect(ActiveEffect(name="fast healing", kind="buff",
                                 periodic=[{"heal": 1}]))
    said = _rollover(scene)
    assert pc.hp == pc.hp_max - 2 and any(h.get("kind") == "heal" for h in said)
