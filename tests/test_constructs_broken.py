"""A construct at 0 to -10 hit points is broken, not dying and not destroyed (house rule).

The owner's report, 2026-10-01, playing Sam: a Magic Missile left a Clockwork Spy (a Tiny
construct) at -1 hit points, and the engine's tell read "Clockwork Spy takes 3 untyped.
Clockwork Spy is unconscious and dying." Two turns later: "Clockwork Spy has bled out
where they fell." A machine, bleeding — because `apply_hp_state` put the bottom of the
ladder at -Con, and a missing Constitution reads as 10.

The first fix followed the Bestiary ("immediately destroyed when reduced to 0 hit points
or less"). The owner then ruled a HOUSE RULE, verbatim: "Broken, then fixable and
claimable — House rule: a construct at 0 to -10 is broken, not destroyed (destroyed only
past that)." Undead keep the book: "immediately destroyed when reduced to 0 hit points".
The type is asked as a tag (`type.construct`, from the stat block's own `creature_type`),
never a name.
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
    its `notes` line ("CR 1/2 construct"), and not its name. Its floor is the house
    rule's -10, read off content/rules/repairs.json."""
    _scene, _engine, spy = _table()
    assert spy.has_state(states.CONSTRUCT)
    assert spy.has_state("subtype.clockwork")
    assert states.breaks_below_zero(spy) and not states.destroyed_at_zero(spy)
    assert spy.death_floor() == -11      # dead at or below: -10 is the last broken rung


def test_a_printed_trait_bundle_alone_makes_the_type():
    """A homebrew block that prints "Immune construct traits" and no `creature_type` is a
    construct all the same."""
    assert states.type_tags("", "", ["construct traits"]) == ("type.construct",)
    assert states.type_tags("Undead", "", ["undead traits"]) == ("type.undead",)
    assert states.type_tags("magical beast", "", []) == ("type.magical-beast",)


def test_a_living_body_keeps_its_dying_rungs():
    """The thug still falls through -Con: the rule touches only constructs and undead."""
    _scene, _engine, thug = _table("thug")
    assert thug.death_floor() == -thug.ability_score("con")
    thug.hp = -1
    assert "dying" in thug.apply_hp_state()


def test_the_owners_magic_missile_leaves_the_spy_broken_not_dying():
    """The measured turn: 3 points on a spy with 2 left took it to -1, and the tell said
    "unconscious and dying". Under the house rule the same blow leaves it broken — down,
    helpless, not dying, not unconscious, not dead — and the tell says so."""
    _scene, engine, spy = _table()
    spy.hp = 2
    out = engine.run(engine.validate([{
        "op": "damage", "actor": "pc", "target": spy.ref, "because": "a magic missile",
        "params": {"amount": 3, "type": "force", "to": spy.ref}}],
        origin="author:test")).outcomes[0]
    assert spy.hp == -1
    assert spy.has_state("state.down.broken") and spy.is_down and spy.is_helpless
    assert not spy.is_dead
    assert not spy.has_state("state.down.dying")
    assert not spy.has_state("state.down.unconscious")
    assert "is broken" in out.tell and "dying" not in out.tell, out.tell


def test_exactly_zero_is_broken_rather_than_disabled():
    """"0 to -10 is broken": at exactly 0 a construct is not "disabled: still standing,
    but any real effort now costs blood"."""
    _scene, _engine, spy = _table()
    spy.hp = 0
    assert spy.apply_hp_state() == ["broken"]


def test_past_minus_ten_a_construct_is_destroyed():
    """"destroyed only past that": -10 is the last broken rung, -11 is destroyed."""
    _scene, _engine, spy = _table()
    spy.hp = -10
    assert spy.apply_hp_state() == ["broken"] and not spy.is_dead
    spy.hp = -11
    assert spy.apply_hp_state() == ["dead"] and spy.is_dead
    assert not spy.has_state("state.down.broken")


def test_a_broken_construct_never_bleeds_out_off_screen():
    """`tidy_the_fallen` ages the dead out of a scene; a broken machine is not dead, so it
    lies where it fell until somebody mends it."""
    scene, engine, spy = _table()
    spy.hp = -3
    spy.apply_hp_state()
    for _ in range(5):
        engine.tidy_the_fallen()
    assert spy.ref in scene.people and spy.hp == -3 and not spy.is_dead


def test_an_undead_creature_is_still_destroyed_at_zero():
    """The ruling is about constructs only; undead keep the Bestiary's 0."""
    _scene, _engine, bones = _table("human-skeleton")
    assert bones.has_state(states.UNDEAD) and bones.death_floor() == 0
    bones.hp = -2
    bones.apply_hp_state()
    assert bones.is_dead and not bones.has_state("state.down.dying")


def test_the_spy_as_the_save_holds_it_is_settled_broken_and_never_bleeds_out():
    """The owner's own save holds the spy at -1 with `unconscious` and `dying` written
    before any of this. Its next round (`bleed_out`) and the off-screen resolution
    (`_resolve_dying`) both settle it onto the house ladder: broken, the book's rungs
    lifted, no hit point lost, no Constitution rolled, and no "has bled out" line."""
    _scene, _engine, spy = _table()
    spy.hp = -1
    spy.add_condition("unconscious", source="hit points")
    spy.add_condition("dying", source="hit points")
    res = spy.bleed_out(Dice(3))
    assert res["outcome"] == "broken" and spy.hp == -1
    assert spy.has_state("state.down.broken")
    assert not spy.has_state("state.down.dying") and not spy.has_state("state.down.unconscious")

    _scene2, engine2, spy2 = _table(seed=4)
    spy2.hp = -1
    spy2.add_condition("unconscious", source="hit points")
    spy2.add_condition("dying", source="hit points")
    tells = engine2._resolve_dying(spy2)
    assert spy2.has_state("state.down.broken") and not spy2.is_dead
    assert tells and "bled out" not in tells[0] and "broken" in tells[0], tells
