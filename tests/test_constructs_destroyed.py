"""Constructs and undead are destroyed at 0 hit points, not dying.

The owner's report, 2026-10-01, playing Sam: a Magic Missile left a Clockwork Spy (a Tiny
construct) at -1 hit points, and the engine's tell read "Clockwork Spy takes 3 untyped.
Clockwork Spy is unconscious and dying." Two turns later: "Clockwork Spy has bled out
where they fell." A machine, bleeding. The cause was one line: `apply_hp_state` put the
bottom of the ladder at -Con, and a body with no Constitution reads its missing score as
10 — so the spy had ten rungs of dying to fall through.

The book (Bestiary, Creature Types, read 2026-10-01): a construct is "immediately
destroyed when reduced to 0 hit points or less" and has "immunity to bleed"; an undead
creature is "immediately destroyed when reduced to 0 hit points". The type is asked as a
tag (`type.construct`, from the stat block's own `creature_type`), never a name.
"""
from __future__ import annotations

from rules import states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _table(template: str = "clockwork-spy", seed: int = 1):
    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-thessaly.json"))
    body = scene.add(instantiate(template, scene=scene), zone="engaged")
    return scene, Engine(scene, Dice(seed)), body


def test_the_clockwork_spy_is_a_construct_by_its_stat_block():
    """The type is the stat block's `creature_type`, read as a tag — not "construct" in
    its `notes` line ("CR 1/2 construct"), and not its name."""
    _scene, _engine, spy = _table()
    assert spy.has_state(states.CONSTRUCT)
    assert spy.has_state("subtype.clockwork")
    assert states.destroyed_at_zero(spy)
    assert spy.death_floor() == 0


def test_a_printed_trait_bundle_alone_makes_the_type():
    """A homebrew block that prints "Immune construct traits" and no `creature_type` is a
    construct all the same."""
    assert states.type_tags("", "", ["construct traits"]) == ("type.construct",)
    assert states.type_tags("Undead", "", ["undead traits"]) == ("type.undead",)
    assert states.type_tags("magical beast", "", []) == ("type.magical-beast",)


def test_a_living_body_keeps_its_dying_rungs():
    """The thug still falls through -Con: the fix touches only bodies with no dying rung."""
    _scene, _engine, thug = _table("thug")
    assert not states.destroyed_at_zero(thug)
    assert thug.death_floor() == -thug.ability_score("con")
    thug.hp = -1
    assert "dying" in thug.apply_hp_state()


def test_the_owners_magic_missile_destroys_the_spy_instead_of_leaving_it_dying():
    """The measured turn: 3 points on a 5-hit-point spy with 2 left took it to -1, and the
    tell said "unconscious and dying". Now the same 3 points destroy it, and the tell says
    so in the Bestiary's word."""
    scene, engine, spy = _table()
    spy.hp = 2
    out = engine.run(engine.validate([{
        "op": "damage", "actor": "pc", "target": spy.ref, "because": "a magic missile",
        "params": {"amount": 3, "type": "force", "to": spy.ref}}],
        origin="author:test")).outcomes[0]
    assert spy.hp == -1
    assert spy.is_dead and spy.has_state("state.down.dead")
    assert not spy.has_state("state.down.dying")
    assert not spy.has_state("state.down.unconscious")
    assert "is destroyed" in out.tell, out.tell
    assert "dying" not in out.tell, out.tell


def test_exactly_zero_destroys_rather_than_disabling():
    """"0 hit points or less": a construct at exactly 0 is not "disabled: still standing,
    but any real effort now costs blood" — it has no blood and no rung at 0."""
    _scene, _engine, spy = _table()
    spy.hp = 0
    assert spy.apply_hp_state() == ["dead"]


def test_an_undead_creature_is_destroyed_at_zero_too():
    _scene, _engine, bones = _table("human-skeleton")
    assert bones.has_state(states.UNDEAD)
    bones.hp = -2
    bones.apply_hp_state()
    assert bones.is_dead and not bones.has_state("state.down.dying")


def test_a_spy_saved_dying_is_destroyed_on_its_next_tick_and_never_bleeds_out():
    """The owner's own save holds the spy at -1 with `unconscious` and `dying` written
    before this fix. Its next round (`bleed_out`) and the off-screen resolution
    (`_resolve_dying`) both destroy it — neither rolls a Constitution it does not have,
    and the off-screen tell is not "has bled out where they fell"."""
    scene, engine, spy = _table()
    spy.hp = -1
    spy.add_condition("unconscious", source="hit points")
    spy.add_condition("dying", source="hit points")
    res = spy.bleed_out(Dice(3))
    assert res["outcome"] == "dead" and spy.is_dead
    assert spy.hp == -1, "a machine does not lose a hit point of blood"

    scene2, engine2, spy2 = _table(seed=4)
    spy2.hp = -1
    spy2.add_condition("unconscious", source="hit points")
    spy2.add_condition("dying", source="hit points")
    tells = engine2._resolve_dying(spy2)
    assert spy2.is_dead
    assert tells and "bled out" not in tells[0] and "destroyed" in tells[0], tells
