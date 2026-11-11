"""A homebrew file that parses but is malformed costs only itself, and is named.

Review 2026-11-11, finding 4. Only JSON syntax errors were caught. Measured with seven
hostile files in every homebrew folder (`probe5.py`): 23 crashes across spells, feats,
ingredients, classes, races and world classes — `homebrew/spells/x.json` holding
`{"id": "my-spell"}` raised `TypeError: Spell.__init__() missing 1 required positional
argument: 'name'` from EVERY `all_spells()` call, with no file named. A bad world-class
file was worse: the first `tracks()` call raised, and every later one answered with the
shipped set alone, so every homebrew world class vanished silently. After the fix the
same probe found none in any loader.
"""
from __future__ import annotations

import json
import logging

import pytest
from django.test import override_settings

from pathfindergm import files


def _spells():
    from rules import spells
    return spells.all_spells()


def _feats():
    from rules import feats
    return feats.all_feats()


def _ingredients():
    from rules import ingredients
    return ingredients.all_ingredients()


def _classes():
    from rules import classes
    return classes.all_classes()


def _tracks():
    from rules import worldclass
    return worldclass.tracks()


def _races():
    from rules import races
    return races.all_races()


BARE = {"id": "zz-bare"}                     # the review's payload: an id and nothing else
ROWS = [None, 5, "x", {"id": "zz-row"}]      # rows that are not objects, then a bare one

CASES = [
    # folder, payload, loader, an id the shipped catalogue must still hold
    ("spells", BARE, _spells, "fireball"),              # TypeError, spells.py:2116
    ("spells", {"spells": ROWS}, _spells, "fireball"),  # AttributeError, spells.py:2094
    ("spells", None, _spells, "fireball"),
    ("spell-mechanics", None, _spells, "fireball"),     # AttributeError, spells.py:2009
    ("spell-mechanics", {"spells": "oops"}, _spells, "fireball"),
    ("feats", BARE, _feats, "power-attack"),            # TypeError, feats.py:135
    ("feats", {"feats": ROWS}, _feats, "power-attack"),  # AttributeError, feats.py:130
    ("ingredients", BARE, _ingredients, None),          # KeyError 'name', ingredients.py:318
    ("classes", {"classes": ROWS}, _classes, "fighter"),  # AttributeError, classes.py:72
    ("world-classes", BARE, _tracks, "herbalist"),      # KeyError 'name', worldclass.py:758
    ("world-classes", None, _tracks, "herbalist"),      # TypeError, worldclass.py:758
    ("races", {"races": [{"id": "zz-row", "name": "Zed", "choose": 5}]}, _races, None),
]


@pytest.mark.parametrize("folder, payload, loader, kept", CASES)
def test_one_bad_homebrew_file_costs_only_itself(tmp_path, folder, payload, loader, kept):
    """Each payload above raised out of the loader named beside it, taking the whole
    catalogue down. Now the catalogue loads, shipped entries are all there, and the
    entry that could not be built is simply absent."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        before = set(loader())
    home = tmp_path / "homebrew" / folder
    home.mkdir(parents=True)
    (home / "zz-bad.json").write_text(json.dumps(payload), encoding="utf-8")
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "other" / "campaigns")):
        pass                                 # moves the setting, so the caches are dropped
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        after = set(loader())
    assert before <= after, sorted(before - after)[:5]
    assert not {"zz-bare", "zz-row"} & after or folder == "classes"
    if kept:
        assert kept in after


def test_a_bad_world_class_does_not_hide_the_good_homebrew_ones(tmp_path, caplog):
    """`_TRACKS` was assigned from shipped content before homebrew loaded, so one bad
    file raised once and then every call answered without ANY homebrew world class —
    the good file beside it included, and nothing said so."""
    from rules import worldclass

    home = tmp_path / "homebrew" / "world-classes"
    home.mkdir(parents=True)
    (home / "aa-bad.json").write_text(json.dumps(BARE), encoding="utf-8")
    (home / "zz-good.json").write_text(json.dumps(
        {"id": "zz-good", "name": "Tinker", "levels": [{"level": 1}]}), encoding="utf-8")
    files._UNREADABLE_SAID.clear()
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        with caplog.at_level(logging.WARNING, logger="pathfindergm"):
            first = worldclass.tracks()
            second = worldclass.tracks()
    assert "zz-good" in first and "zz-good" in second
    assert "herbalist" in first
    assert any("aa-bad.json" in r.message for r in caplog.records)


def test_the_bad_spell_file_is_named(tmp_path, caplog):
    """"No message names the file": the entry is built after files are merged, so the
    loader has to remember which file an id came from to say it."""
    home = tmp_path / "homebrew" / "spells"
    home.mkdir(parents=True)
    (home / "my-spell.json").write_text(json.dumps(BARE), encoding="utf-8")
    files._UNREADABLE_SAID.clear()
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        with caplog.at_level(logging.WARNING, logger="pathfindergm"):
            _spells()
    assert any("my-spell.json" in r.message for r in caplog.records)
