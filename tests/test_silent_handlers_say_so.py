"""A handler that swallows everything still says what it swallowed.

Review 2026-11-11, finding 20: eleven `except Exception` handlers returned a quiet
default with no log line, so a programming error behind one read exactly like the
ordinary case it was written for — a loader that raised looked like a kind that ships
nothing, a formula that raised looked like no bonus. Control flow is unchanged in every
one; these pin that the log now names what happened.
"""
from __future__ import annotations

import logging

from pathfindergm import files


def test_a_shipped_loader_that_raises_is_logged_and_still_answers_empty(monkeypatch, caplog):
    from rules import ingredients, registry

    def boom():
        raise RuntimeError("the loader is broken")

    monkeypatch.setattr(ingredients, "all_ingredients", boom)
    with caplog.at_level(logging.ERROR, logger="rules.registry"):
        assert registry.shipped("ingredients") == {}
    assert any("ingredients" in r.getMessage() and r.exc_info for r in caplog.records)


def test_a_formula_that_raises_is_said_once_not_on_every_roll(caplog):
    """These two handlers sit in the modifier funnel and run on every roll: once per
    document, or the log is a thousand lines a turn."""
    from rules import classfeatures

    classfeatures._BAD_FORMULAS.clear()
    spec = {"type": "attack", "formula": "rank +"}
    with caplog.at_level(logging.WARNING, logger="rules.classfeatures"):
        for _ in range(50):
            classfeatures.bad_formula(spec, ValueError("not a formula"))
    assert len([r for r in caplog.records if "rank +" in r.getMessage()]) == 1


def test_an_unreadable_roster_entry_is_named(tmp_path, monkeypatch, caplog):
    from play import roster

    bad = tmp_path / "corvin.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(roster, "path_for", lambda character_id: bad)
    files._UNREADABLE_SAID.clear()
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        assert roster.load("corvin") is None
    assert any("corvin.json" in r.getMessage() for r in caplog.records)


def test_a_broken_watcher_proposal_is_logged_and_costs_nothing(monkeypatch, caplog):
    """`drain` skipped a proposal whose applier raised with a bare `continue`."""
    from types import SimpleNamespace

    from gm import watcher

    def boom(c, p):
        raise RuntimeError("the applier is broken")

    monkeypatch.setattr(watcher, "_apply_garnish", boom)
    monkeypatch.setattr(watcher, "_PENDING", [{"campaign": "t", "job": "garnish"}])
    with caplog.at_level(logging.ERROR, logger="gm.watcher"):
        assert watcher.drain(SimpleNamespace(id="t")) is False
    assert any("garnish" in r.getMessage() and r.exc_info for r in caplog.records)
