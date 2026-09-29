"""A described person keeps their face (item 16.7): closed slots, never free comparison.

Measured on the Bobby playtest, 2026-09-28: the watchman, described as an Orc with hair
like wet rope and blue ink dots on the knuckles, was followed two beats later by "an older
man with a face like cracked leather … the hilt of a broadsword". Whether that man was
the watchman at all could not be settled (the attribution labelled one of its two
mentions "unknown"), and the slots below cannot see it either — "an older man" agrees
with an old Orc — so that beat is deliberately NOT asserted here; the brief is its fix
(`gm/brief/faces.py`). Re3 (Yang et al. 2022) is why the slots are closed: free
comparison scored 0.528 ROC-AUC, near chance.
"""
from __future__ import annotations

import pytest

from gm.checks import face_kept

from _a_truth import WAY_IN, context, scene_at


def _described(world=None, location=None, place=WAY_IN, **face):
    from _a_truth import WORLD

    world = world or WORLD
    agent, _ = scene_at(place, [("the watchman waving traffic through", "watchman")],
                        world=world, location=location)
    scene = agent.engine.scene
    ref = next(r for r, a in scene.actors.items() if not a.is_pc)
    a = scene.actors[ref]
    a.described = True
    a.appearance = face.get("appearance", "")
    a.described_as = face.get("said", [])
    if "weapons" in face:
        a.weapons = face["weapons"]
    return agent, a


def _flags(agent, text):
    return face_kept.find(context(agent, text))


def test_each_people_of_each_world_is_a_slot(worlds):
    """The peoples are the world's own (`names.peoples`) — a Pangrella Korvu, a synthetic
    Fenwic — never a list of ours."""
    from rules import names as names_mod

    peoples = list(names_mod.peoples(worlds).values())
    if len(peoples) < 2:
        pytest.skip("a world with one people has no second to contradict")
    first, other = peoples[0], peoples[1]
    row = (worlds.play.get("settlements") or [])[0]
    location = worlds.get(row["id"])
    agent, a = _described(world=worlds, location=location, place="",
                          appearance=f"{first}: broad and quiet.")
    assert _flags(agent, f"The watchman is a {other}, and he nods.")
    assert not _flags(agent, f"The watchman is a {first}, and he nods.")
    assert not _flags(agent, f"The watchman eyes the {other} by the well.")


def test_age_is_young_against_old_and_nothing_finer():
    agent, _ = _described(appearance="Orc: old enough to have stopped counting.")
    assert _flags(agent, "The watchman is a young man with a quick grin.")
    assert not _flags(agent, "The watchman, an older man, waves you on.")
    assert not _flags(agent, "The watchman walks the old road with you.")


def test_hair_bald_against_colour():
    agent, _ = _described(appearance="Human: bald, a scar over one eye.")
    assert _flags(agent, "The watchman pushes back his black hair.")
    agent, _ = _described(appearance="Human: red hair in a braid.")
    assert _flags(agent, "The watchman runs a hand over his bald head.")
    assert _flags(agent, "The watchman's black hair is wet with rain.")
    assert not _flags(agent, "The watchman's hair is wet with rain.")


def test_what_they_carry():
    agent, _ = _described(appearance="Orc: broad.", weapons=["club"])
    assert _flags(agent, "The watchman rests his hand on the hilt of a broadsword.")
    assert not _flags(agent, "The watchman grips his club.")
    assert not _flags(agent, "The watchman eyes your dagger.")


def test_a_new_detail_that_contradicts_nothing_is_not_a_finding():
    """The owner's ruling on Q9: faces are handled in the brief; a new detail is drift,
    not a contradiction."""
    agent, _ = _described(appearance="Orc: hair the colour of wet rope.")
    assert not _flags(agent, "The watchman has a face like cracked leather.")


def test_nobody_undescribed_is_judged():
    agent, a = _described(appearance="Orc: old.")
    a.described = False
    assert not _flags(agent, "The watchman is a young man.")
