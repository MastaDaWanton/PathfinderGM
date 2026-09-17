"""One unreadable campaign must not take the whole app with it.

Measured 2026-09-17 against a real save. A character whose sheet had gone over budget —

    IllegalSheet: Dorito: 3 skill ranks spent, 2 available (4 class + Int + race, x1)

— took `/` and `/play/` down together with an uncaught `UnreadableSave`, because
`home_views.home` opens by calling `campaign_mod.current()`. In the packaged build, where
DEBUG is off, that is "Server Error (500)" and nothing else: no way to switch character,
no way to read the reason, no way back into the app at all. The campaign was still on
disk and still fine — the player simply could not reach anything.

`play/roster.py::summary` learned this one level down, when a single unreadable character
took the page out through `recent_characters`. Its note is the rule here too: **listing a
campaign must be safe; playing one must not be.** So the failure is caught at the two
doors that only want to *show* something, and `current()` still raises for everybody who
is actually trying to play.

**How a save gets into this state.** Not usually by editing a sheet. Validation resolves
the character's class and race through the homebrew directory, so a homebrew class that is
renamed, edited or deleted takes every character built on it with it — and the app is
built around homebrew. That is the case this is really for, and it is one the player can
reach without doing anything wrong at all.

Nothing here repairs a sheet. The engine names the exact numbers, the file is left
untouched, and what the app owes the player is the reason and a way to keep playing —
not a guess at which rank they meant to drop.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules.sheet import load_pc


@pytest.fixture
def shelf(tmp_path):
    """A campaign on disk whose PC the rules will not accept."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.save()
        path = c.path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        # One rank more than any budget allows, which is what an edited homebrew class
        # does to every character built on it.
        raw["scene"]["people"]["pc"]["ranks"] = {
            name: 1 for name in ("perception", "stealth", "bluff", "acrobatics",
                                 "climb", "diplomacy", "disable device", "escape artist",
                                 "intimidate", "knowledge (local)", "linguistics",
                                 "appraise", "sense motive", "sleight of hand", "swim",
                                 "survival", "ride", "profession", "craft", "heal")
        }
        path.write_text(json.dumps(raw), encoding="utf-8")
        cm._LIVE.clear()
        yield Client()
        cm._LIVE.clear()


def test_the_save_really_is_unreadable(shelf):
    """The premise. If this stops raising the rest of the file is testing nothing."""
    with pytest.raises(cm.UnreadableSave):
        cm.current()


def test_the_shelf_still_loads(shelf):
    """The defect: this was a 500, and a 500 on `/` is an app with no way into it."""
    assert shelf.get("/").status_code == 200


def test_the_shelf_says_why(shelf):
    """In the engine's own words, numbers included. A missing Continue button on its own
    reads as the app having forgotten the game."""
    body = shelf.get("/").content.decode("utf-8", "replace")
    assert "unreadable" in body
    assert "skill ranks spent" in body


def test_the_table_sends_them_back_rather_than_breaking(shelf):
    """A bookmark straight to `/play/` must not be a dead end either."""
    r = shelf.get("/play/")
    assert r.status_code in (302, 200)
    if r.status_code == 302:
        assert "unreadable" in r.headers.get("Location", "")


def test_nothing_is_repaired_or_replaced_behind_the_player(shelf):
    """The rule `campaign.py` already states at length: a campaign that cannot be read is
    a thing to be told about, not a thing to be quietly replaced. Loading the shelf must
    not rewrite the save, archive it, or start a fresh character over it."""
    from django.conf import settings
    from pathlib import Path

    saves = sorted(Path(settings.CAMPAIGN_DIR).glob("*.json"))
    before = {p.name: p.read_bytes() for p in saves}
    shelf.get("/")
    shelf.get("/play/")
    after = {p.name: p.read_bytes()
             for p in sorted(Path(settings.CAMPAIGN_DIR).glob("*.json"))}
    assert after == before, "the shelf changed a save it could not read"


def test_an_ordinary_shelf_is_untouched(tmp_path):
    """The banner costs nothing on every normal load, and Continue still works."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json")).save()
        body = Client().get("/").content.decode("utf-8", "replace")
        assert '"unreadable": ""' in body
        cm._LIVE.clear()
