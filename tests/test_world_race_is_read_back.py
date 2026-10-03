"""A character forged as a world's drafted race reads that race back, on a fresh install.

Reported 2026-10-02 from a friend's install: "running into an issue with character
creation, seems like the bite attack is the issue". Reproduced on a fresh data directory
with Aurvantis on the shelf: creating a goblin returned HTTP 500,
`IllegalSheet: T goblin: unknown weapon 'bite'`. Five of Aurvantis's sixteen races failed
the same way — goblin, orc, half-orc and tengu by their bite, catfolk by its claws.

The forge offered `races.for_world(world)` — the world's drafted documents, built from its
own sentences — and saved the character with nothing but `race: "goblin"`. The sheet reads
its race live through the registry, which holds the Core seven and whatever the Races
bench has written; a world's draft is on neither until somebody presses Import there. The
owner's install had pressed it, so it worked on the owner's machine and nowhere else.

The crash was only the loud half. Measured on the same run: nine of the sixteen drafts had
no registry entry at all (every live trait — darkvision, a climb speed, the bite — gone the
moment the forge closed), and seven shared an id with a Core race that is a different
people (Aurvantis's half-orc has a bite, the core one does not; its dwarf is +2 Int/Cha,
the core one +2 Con/Wis). Writing the drafts onto the bench under their own ids would have
changed every other world's dwarf too, so the sheet now carries which world its race came
from (`race_world`) and reads that world's draft first.
"""
from __future__ import annotations

import json

import pytest

from rules import creation, races
from rules.sheet import from_dict, to_dict

WORLD = "aurvantis-campaign"


def _forge(race: str) -> dict:
    built, problems = creation.build({
        "name": f"Test {race}", "race": race, "class": "fighter", "world": WORLD,
        "pronouns": "they/them", "choices": ["str", "int", "cha"],
        "skills": [], "feats": [],
        "abilities": {"str": 14, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}})
    assert problems == [], (race, problems)
    return built["sheet"]


def _armed_drafts() -> list[str]:
    offered = creation._races_for(WORLD)
    return sorted(rid for rid, d in offered.items()
                  if str(d.get("origin", "")).startswith("world:") and d.get("weapons"))


def test_the_fixture_still_has_drafted_races_with_natural_attacks():
    """Without this the test below could pass by finding nothing to forge."""
    armed = _armed_drafts()
    assert {"goblin", "catfolk", "half-orc"} <= set(armed), armed
    # The point of the fix: none of these are on the bench in a fresh data directory.
    assert all(races.authored().get(rid) is None for rid in armed)


@pytest.mark.parametrize("race", ["goblin", "orc", "half-orc", "tengu", "catfolk"])
def test_a_drafted_race_with_a_natural_attack_can_be_forged_and_reloaded(race):
    if race not in _armed_drafts():
        pytest.skip(f"{race} no longer drafts a natural attack in {WORLD}")
    sheet = _forge(race)
    assert sheet["race_world"] == WORLD
    assert sheet["equipped"] not in ("", "unarmed"), sheet["weapons"]
    actor = from_dict(sheet, ref="pc")              # raised IllegalSheet before the fix
    swing = actor.weapon(sheet["equipped"])
    assert swing.get("natural") is True and swing.get("damage"), swing
    assert actor.is_proficient(sheet["equipped"])
    # And it survives the save: the field travels, so the next load reads the same body.
    again = from_dict(json.loads(json.dumps(to_dict(actor))), ref="pc")
    assert again.race_world == WORLD
    assert again.natural_weapon(sheet["equipped"]) is not None


def test_a_world_race_sharing_a_core_id_reads_the_worlds_people():
    """Aurvantis's half-orc carries a bite; the Core Rulebook's does not. The sheet read the
    core one, so the character it built could not swing the weapon it was handed."""
    offered = creation._races_for(WORLD).get("half-orc") or {}
    if not offered.get("weapons"):
        pytest.skip("Aurvantis's half-orc no longer drafts a bite")
    assert not (races.shared("half-orc") or {}).get("weapons")
    actor = from_dict(_forge("half-orc"), ref="pc")
    assert actor._race_doc().get("people_id") == offered.get("people_id")


def test_a_core_race_forged_in_a_world_is_still_the_core_race():
    """A race offered from the registry carries no world, so nothing about it changes."""
    built, problems = creation.build({
        "name": "Plain", "race": "human", "class": "fighter", "world": "",
        "pronouns": "they/them", "choices": ["str"], "skills": [], "feats": ["toughness"],
        "abilities": {"str": 14, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}})
    assert problems == []
    assert built["sheet"]["race_world"] == ""


def test_a_world_gone_from_the_shelf_falls_back_to_the_registry():
    """A save outlives the world file it was made in; the read must not raise."""
    assert races.world_shared("no-such-world", "goblin") is None
