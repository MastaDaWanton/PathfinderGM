"""The home page and the first request, made fast for 0.4.10 (measured 2026-11-21 on a copy
of the owner's save, 31 characters, GET "/" through the Django test client: 49 s first and
13-15 s every time after on 0.4.9; and 26-28 s on an empty data folder).

Each test names the cost it removed. They count work, never wall-clock, so a loaded
machine cannot fail them.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from rules import formulae, sheet
from rules.sheet import load_pc


def test_loading_plain_gear_never_copies_the_formula_book(monkeypatch):
    """The home page deep-copied the formula book 153 times for 31 characters: 25 s of a
    49 s first request as first measured, 11.6 s of every 12.6 s request after it.
    `alchemy_migration._bought_formula` looked every craftless row up by name through
    `formulae.all()`, which deep-copies all 485 rows (5.8M deepcopy calls), and a row of
    rope or rations reached the whole loop before it answered None."""
    copies = []
    real = formulae.all
    # Counted, not raised: `_migrated` swallows a migration's exception as "not mine".
    monkeypatch.setattr(formulae, "all", lambda: copies.append(1) or real())
    for row in ({"base": "rope", "name": "Rope", "craft": ""},
                {"base": "trail rations", "name": "Trail rations", "count": 4}):
        assert sheet._migrated(dict(row)) == row
    assert copies == []


def test_an_old_bought_jar_still_becomes_what_the_counter_sells(monkeypatch):
    """The migration's correctness kept through the uncopied table: an inert bought
    antitoxin still converts (its own suite, tests/test_alchemy_migration.py, has the
    whole corpus), and the table it read is not changed by reading it."""
    from rules import alchemy_migration

    before = formulae.all()
    monkeypatch.setattr(formulae, "all", lambda: pytest.fail("copied the book"))
    got = alchemy_migration.migrate_old_record({"base": "antitoxin", "name": "Antitoxin",
                                                "craft": "", "count": 2})
    assert got is not None and got.get("count") == 2
    assert alchemy_migration._formula_named("Antitoxin") is not None
    monkeypatch.undo()
    assert formulae.all() == before


def test_the_shelf_builds_each_character_once(tmp_path, monkeypatch):
    """`library.recent_characters` asked `summary()` and then `playable()`, and each built
    the whole Actor: every living character was built twice, half of the 12 s second
    request on the owner's save."""
    from play import campaign as cm
    from play import library, roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        built = []
        real = roster.from_dict
        monkeypatch.setattr(roster, "from_dict", lambda *a, **k: built.append(1) or real(*a, **k))
        cards = library.recent_characters()
        cm._LIVE.clear()
    assert cards and all(c["playable"] for c in cards)
    assert len(built) == len(cards)


def test_a_first_run_shelf_begins_no_game_and_asks_no_model(tmp_path, monkeypatch):
    """On an empty data folder the first "/" began a default campaign for a character
    nobody chose and read its opening through the narrator's model, on the request: 8.4 s
    with the models already loaded, a 60-100 s cold load otherwise, and the packaged
    proof's 30 s first GET failed twice on 0.4.9."""
    from gm import client as gm_client
    from play import campaign as cm

    monkeypatch.setattr(gm_client, "chat",
                        lambda *a, **k: pytest.fail("the shelf waited on a model"))
    monkeypatch.setattr(gm_client, "warm_roles", lambda *roles: None)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        r = Client().get("/")
        assert r.status_code == 200
        assert not cm.begun()
        assert not list((tmp_path / "campaigns").glob("*.json"))
        cm._LIVE.clear()
