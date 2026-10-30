"""A bite in hand whose race cannot be read made the whole save unplayable.

Measured 2026-10-29 on master 3175a72d: the owner's Sammy (an asura wizard 2, 410 turns
played) carries

    weapons  = ["bite", "slam", "claws", "unarmed"]
    equipped = "bite"

which is the intended shape: `creation.build` writes a race's natural attacks onto the
sheet by name, and `Actor.natural_weapon` reads their dice off the race document live.
The asura is the owner's own bench race (homebrew/races/asura.json). Loaded anywhere that
file could not be read — a reported save, a bench race deleted or edited — `from_dict`
raised `IllegalSheet: Sammy: unknown weapon 'bite'`, the roster card said "the sheet
cannot be read" and 410 turns could not be played. With the file present it loaded, on
master and on 0.2.22 alike: the defect is the missing document being fatal, and the bite
was the only part of the body whose absence was.
"""
from __future__ import annotations

import copy
import json
import logging

import pytest

from rules import races
from rules.sheet import IllegalSheet, from_dict

# The owner's bench race, abridged to the attacks (their file lists 59 evolutions).
ASURA = {
    "id": "asura", "name": "Asura", "type": "outsider", "size": "medium", "speed": 40,
    "choose": [{"amount": 2, "from": "any"}], "budget": {"feats": 1, "ranks": 1},
    "evolutions": [{"id": "bite", "choice": "", "times": 1},
                   {"id": "slam", "choice": "", "times": 1},
                   {"id": "claws", "choice": "", "times": 1}],
    "tags": ["race.asura"], "origin": "yours", "world": "", "converted": False,
}


def _sammy() -> dict:
    """A level-1 caster sheet in Sammy's shape: an asura with the bite in hand."""
    with open("fixtures/pc-caster.json", encoding="utf-8") as fh:
        d = json.load(fh)
    d.update(name="Sammy", race="asura",
             weapons=["bite", "slam", "claws", "unarmed"], equipped="bite")
    return d


@pytest.fixture
def no_asura(monkeypatch):
    real = {k: v for k, v in races.all_races().items() if k != "asura"}
    monkeypatch.setattr(races, "all_races", lambda: real)


@pytest.fixture
def asura(monkeypatch):
    real = races.all_races()
    doc = races.normalise(copy.deepcopy(ASURA))
    monkeypatch.setattr(races, "all_races", lambda: {**real, "asura": doc})


def test_the_save_loads_when_its_race_cannot_be_read(no_asura, caplog):
    """The measurement: "unknown weapon 'bite'" and an unplayable save. Now it loads,
    fights with fists, and says why in the log."""
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        pc = from_dict(_sammy(), ref="pc")
    assert pc.equipped == "unarmed"
    assert pc.weapon(pc.wielded_key()) is not None
    assert any("'bite'" in r.getMessage() and "'asura'" in r.getMessage()
               for r in caplog.records), [r.getMessage() for r in caplog.records]


def test_the_names_stay_so_the_race_coming_back_restores_them(no_asura, monkeypatch):
    """Nothing of the body is deleted: the names are the store, as `creation.build` wrote
    them, and the race document read live is what gives them dice."""
    pc = from_dict(_sammy(), ref="pc")
    assert pc.weapons == ["bite", "slam", "claws", "unarmed"]
    real = races.all_races()
    monkeypatch.setattr(races, "all_races",
                        lambda: {**real, "asura": races.normalise(copy.deepcopy(ASURA))})
    assert pc.natural_weapon("bite") is not None


def test_a_body_that_has_its_bite_keeps_it_in_hand(asura):
    """The fallback is for a missing source only: with the race on the shelf (the owner's
    own install) the bite is still the weapon in hand."""
    pc = from_dict(_sammy(), ref="pc")
    assert pc.equipped == "bite"
    assert pc.natural_weapon("bite")["natural"]


def test_an_unknown_table_weapon_is_still_refused(no_asura):
    """Only natural-attack names fall back. Anything else unknown in hand came from a
    hand-edited file or a bug, and unarming it quietly would hide which."""
    d = _sammy()
    d["equipped"] = "vorpal spoon"
    with pytest.raises(IllegalSheet, match="unknown weapon 'vorpal spoon'"):
        from_dict(d, ref="pc")
