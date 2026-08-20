"""NPC templates.

A holding pen, not the destination. The real bestiary is an SRD import (d20PFSRD's
bestiary exports to CSV, and the OGL requires the licence to travel with the content) —
these are the handful of ordinary people a first scene in a town needs, written as flat
stat blocks so the engine has something to roll against today.

Every template is a plain NPC-level human, deliberately: a scene in Pangrella is about
guildhands and watchmen, not monsters.
"""
from __future__ import annotations

from .sheet import Actor, from_dict

TEMPLATES: dict[str, dict] = {
    "guildhand": {
        "name": "guildhand",
        "kind": "npc",
        "abilities": {"str": 11, "dex": 10, "con": 11, "int": 10, "wis": 10, "cha": 9},
        "hp": 4,
        "flat_ac": 10,
        "flat_attack": 0,
        "flat_saves": {"fort": 0, "ref": 0, "will": 0},
        "flat_skills": {"perception": 3, "sense motive": 1, "craft": 4},
        "flat_initiative": 0,
        "flat_cmd": 11,
        "equipped": "club",
        "weapons": ["club"],
        "notes": "Commoner 1. Tired, half-attentive, not paid enough to fight.",
    },
    "watchman": {
        "name": "watchman",
        "kind": "npc",
        "abilities": {"str": 13, "dex": 12, "con": 12, "int": 9, "wis": 11, "cha": 10},
        "hp": 11,
        "flat_ac": 15,
        "flat_attack": 2,
        "flat_saves": {"fort": 3, "ref": 1, "will": 0},
        "flat_skills": {"perception": 5, "intimidate": 4, "sense motive": 2},
        "flat_initiative": 1,
        "flat_cmd": 14,
        "equipped": "shortsword",
        "weapons": ["shortsword", "club"],
        "notes": "Warrior 1 in a chain shirt. Will shout before drawing.",
    },
    "thug": {
        "name": "thug",
        "kind": "npc",
        "abilities": {"str": 14, "dex": 13, "con": 13, "int": 9, "wis": 10, "cha": 8},
        "hp": 13,
        "flat_ac": 14,
        "flat_attack": 3,
        "flat_saves": {"fort": 3, "ref": 2, "will": 0},
        "flat_skills": {"perception": 4, "intimidate": 6, "stealth": 3},
        "flat_initiative": 1,
        "flat_cmd": 15,
        "equipped": "sap",
        "weapons": ["sap", "dagger"],
        "notes": "Warrior 1. Prefers a sap: a body that wakes up cannot testify to a killing.",
    },
    "guard dog": {
        "name": "dog",
        "kind": "npc",
        "size": "small",
        "abilities": {"str": 13, "dex": 17, "con": 15, "int": 2, "wis": 12, "cha": 6},
        "hp": 6,
        "flat_ac": 14,
        "flat_attack": 2,
        "flat_saves": {"fort": 4, "ref": 5, "will": 1},
        "flat_skills": {"perception": 8, "survival": 1, "stealth": 5},
        "flat_initiative": 3,
        "flat_cmd": 13,
        "flat_damage": "1d4",
        "equipped": "unarmed",
        "weapons": ["unarmed"],
        "notes": "Scent. Barks first.",
    },
}


class UnknownTemplate(KeyError):
    pass


def instantiate(
    template: str,
    scene=None,
    name: str | None = None,
    world_entity_id: str | None = None,
    index: int = 0,
) -> Actor:
    key = template.strip().lower()
    if key not in TEMPLATES:
        raise UnknownTemplate(
            f"no template {template!r}; have {sorted(TEMPLATES)}"
        )
    data = dict(TEMPLATES[key])
    if name:
        data["name"] = name
    data["world_entity_id"] = world_entity_id
    actor = from_dict(data, ref=_next_ref(scene))
    return actor


def _next_ref(scene) -> str:
    """Encounter-local refs: c1, c2, ... Short because the GM has to type them, and
    distinct from World Bible's 12-char ids so the two can never be confused."""
    if scene is None:
        return "c1"
    n = 1
    while f"c{n}" in scene.actors:
        n += 1
    return f"c{n}"
