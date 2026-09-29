"""I3: charm and magical sleep count as harm — before an unfriendly eye only.

Lane E left both out of `HARMFUL_STATES` ("a charm opening a fight would be absurd",
docs/design-e-magic.md §4.5), and with sleep's conditions (unconscious, helpless) already
harm, the Sleep spell cost a companion 10 regard and made a friendly innkeeper hostile
exactly as a fireball did. The owner, 2026-09-28 (fix-interfaces §3.4): "yes if the people
who saw are not friendly" — charm and magical sleep count when the source is perceived,
and only for the witnesses, the victim included, whose attitude towards the caster is
below friendly.
"""
from __future__ import annotations

import pytest

from rules import attitude, grid as gridmod, spells as spells_mod, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


def caster(prepared):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = 18
    d["prepared"] = prepared
    d["spellbook"] = list(d["spellbook"]) + ["charm-person"]
    return from_dict(d, ref="pc")


def board(worlds, prepared, seed=4):
    row = (worlds.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(caster(prepared))
    man = s.add(instantiate("guildhand", scene=s, name="a drover"))
    stand_on(s, "grassland")
    s.grid = gridmod.Grid(20, 20)
    s.positions["pc"], s.positions[man.ref] = (4, 7), (8, 7)
    return s, Engine(s, Dice(seed=seed), world=worlds), man.ref


def cast(e, spell, ref):
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "t",
                              "params": {"spell": spell, "aim": f"ref:{ref}"}}])).outcomes


def befriend(actor, travels=False):
    attitude.set_regard(actor, 60, "test")
    actor.apply_effect(ActiveEffect(name="friendly", kind="condition", key="friendly",
                                    source="test", duration="until-dismissed",
                                    tags=("attitude.friendly",)))
    if travels:
        actor.apply_effect(ActiveEffect(name="company", kind="bond", key="company",
                                        source="company", duration="until-dismissed",
                                        tags=(states.TRAVELS_WITH_YOU,)))


@pytest.mark.parametrize("spell, kind", [
    ("sleep", "gated"), ("deep-slumber", "gated"), ("charm-person", "gated"),
    ("charm-monster", "gated"), ("burning-hands", "harm"), ("hold-person", "harm"),
    ("color-spray", "harm"), ("night-terrors", "harm"), ("mage-armor", "")])
def test_i3_which_harm_is_gated(spell, kind):
    """Magical sleep is known by its effect document (a sleep condition, or unconscious and
    helpless noted as slumber — six spells in the corpus); a charm by the book's own
    enchantment (charm) subschool. Night terrors' "ruined sleep" lands fatigue, which is
    ordinary harm; hold person and color spray stay ordinary harm (Q34)."""
    assert attitude.harm_of(spells_mod.get(spell), 5) == kind


def test_i3_the_families_join_harm_as_prefixes():
    assert attitude.harmful_condition("charmed") and attitude.gated_condition("charmed")
    assert attitude.harmful_condition("asleep") and attitude.gated_condition("asleep")
    assert attitude.harmful_condition("nauseated") and not attitude.gated_condition("nauseated")


def test_i3_sleep_on_a_stranger_is_harm(worlds):
    """An indifferent stranger — below friendly — put to sleep in plain sight holds it
    against the caster: the fight opens through the battle gate, as any first harm does."""
    s, e, man = board(worlds, {"sleep": 1})
    outs = cast(e, "sleep", man)
    assert s.in_encounter
    assert [x["kind"] for o in outs for x in o.effects] == ["battle_joined"]


def test_i3_sleep_on_a_friend_opens_no_fight_and_moves_nothing(worlds):
    """A friendly onlooker does not turn on the caster for it. Before, the Sleep spell was
    ordinary harm: a friendly drover became hostile and the fight opened."""
    s, e, man = board(worlds, {"sleep": 1})
    befriend(s.actors[man])
    outs = cast(e, "sleep", man)
    assert not s.in_encounter
    assert not [x for o in outs for x in o.effects if x.get("kind") == "attitude"]
    assert attitude.of(s.actors[man]) == "friendly"


def test_i3_a_companion_slept_loses_no_regard(worlds):
    """Owner Q35's 10 regard is for harm; a companion charmed or put to sleep by their own
    party is not an unfriendly eye (measured before: regard 60 → 50 for a Sleep)."""
    s, e, man = board(worlds, {"sleep": 1})
    befriend(s.actors[man], travels=True)
    s.initiative = [("pc", 20)]
    s.sides = {"pc": ["pc", man]}
    s.round, s.turn = 1, 0
    cast(e, "sleep", man)
    assert attitude.regard_of(s.actors[man]) == 60


def test_i3_charm_on_an_unfriendly_eye_is_harm(worlds):
    """Charm person cast openly at somebody who has no time for you: harm, and the fight
    opens — the owner's ruling, which reverses Lane E's "a charm is not harm"."""
    s, e, man = board(worlds, {"charm-person": 1})
    s.actors[man].apply_effect(ActiveEffect(
        name="unfriendly", kind="condition", key="unfriendly", source="test",
        duration="until-dismissed", tags=("attitude.unfriendly",)))
    cast(e, "charm-person", man)
    assert s.in_encounter


def test_i3_harmed_honours_the_gate():
    """The one rule both doors share: with `gated`, a friendly victim is not moved."""
    s = Scene(location_id="x")
    pc = s.add(caster({}))
    friend = s.add(instantiate("guildhand", scene=s, name="a friend"))
    befriend(friend)
    e = Engine(s, Dice(seed=1))
    assert attitude.harmed(e, friend, pc, "spell:sleep", seen=True, gated=True) is None
    stranger = s.add(instantiate("guildhand", scene=s, name="a stranger"))
    got = attitude.harmed(e, stranger, pc, "spell:sleep", seen=True, gated=True)
    assert got and got["to"] == attitude.HOSTILE
