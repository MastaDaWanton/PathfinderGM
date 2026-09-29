"""A creature spawned into a world gets a people's name and face only if it is a person.

Measured 2026-09-29 while building the Phase 3 road starts: on Pangrella "the medium giant
scorpion" spawned with the appearance "Korvu: Korvu have four limbs ending in sharp talons
… a line of blue ink dots across the knuckles" and a person's true name, because
`Engine._bring_in` handed every arrival a true name and a face from the local people's
pools and could not tell a wolf from a woman. The brief's WHO IS HERE then gave that face
to the narrator. The same path serves the road's encounters (`rules/ontheway.road`) and
foraging's (`rules/gathering.creature_for`).

The rule (`engine._a_person`): a humanoid is a person; every other creature type is not;
the hand-made civilian blocks, which are not in the imported bestiary, are people.
"""
from __future__ import annotations

import pytest

from rules.dice import Dice
from rules.engine import Engine, Scene


def _spawn(world, template):
    settlement = (world.play.get("settlements") or [])[0]["id"]
    scene = Scene(location_id=settlement)
    made = Engine(scene, Dice(seed=5), world=world)._bring_in(template)
    return scene.people[made[0]["ref"]]


@pytest.mark.parametrize("template", ["wolf", "medium-giant-scorpion", "dire-rat"])
def test_a_beast_gets_no_true_name_and_no_peoples_face(worlds, template):
    beast = _spawn(worlds, template)
    assert not beast.true_name, f"{template} was given a person's name: {beast.true_name!r}"
    assert not beast.appearance, f"{template} wore a people's face: {beast.appearance[:80]!r}"


@pytest.mark.parametrize("template", ["bandit", "goblin", "guildhand"])
def test_a_person_still_gets_both(worlds, template):
    """A person keeps today's behaviour: whatever the world's pools give them here. A
    world with no name pool for this settlement names nobody, person or not, which is
    the pools' answer and not this rule's."""
    from rules import names

    person = _spawn(worlds, template)
    settlement = (worlds.play.get("settlements") or [])[0]["id"]
    can_name = bool(names.true_name(worlds, settlement, "probe", []))
    can_face = bool(names.appearance_for(worlds, settlement, ref="probe"))
    assert bool(person.true_name) == can_name, f"{template}: {person.true_name!r}"
    assert bool(person.appearance) == can_face, f"{template}: {person.appearance[:80]!r}"
    assert can_name or can_face or worlds.name == "Pangrella", \
        "only a world with no pools for this settlement may name nobody"
