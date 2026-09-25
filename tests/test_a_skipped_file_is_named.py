"""A content file that cannot be read is named in the log, and a save survives a renamed
rule.

Measured 2026-09-25: seventeen loaders read their JSON with `except Exception:
continue`. A homebrew class file with a stray comma vanished, every character built on
it then failed validation, and the player met an unreadable campaign with nothing in the
log naming the file. And `_overrides` raised on an unknown key during `from_dict`, so
renaming a rule would have made every save that overrode it unreadable.
"""
from __future__ import annotations

import logging

import pytest
from django.test import override_settings

from pathfindergm import files


def test_a_broken_homebrew_class_is_named_once(tmp_path, caplog):
    from rules import classes

    folder = tmp_path / "homebrew" / "classes"
    folder.mkdir(parents=True)
    (folder / "stormcaller.json").write_text('{"classes": [ {"id": "x",, }]}',
                                             encoding="utf-8")
    files._UNREADABLE_SAID.clear()
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        with caplog.at_level(logging.WARNING, logger="pathfindergm"):
            classes._ALL = None
            classes.all_classes()
            classes._ALL = None
            classes.all_classes()
    said = [r.message for r in caplog.records if "stormcaller.json" in r.message]
    assert len(said) == 1, said


def test_an_unknown_override_is_dropped_and_said(caplog):
    from rules.sheet import from_dict

    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                       "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis",
                                                     "cha")},
                       "overrides": {"a_rule_since_renamed": True}}, ref="c1")
    assert "a_rule_since_renamed" not in a.overrides
    assert any("a_rule_since_renamed" in r.message for r in caplog.records)
