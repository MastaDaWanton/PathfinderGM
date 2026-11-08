"""Every endpoint a page's buttons call is pinned into the page that serves them.

The drink button rendered for eleven commits over a handler that no longer existed: it
was inserted into the slice between two functions, and a later rewrite replaced that
slice wholesale. The buttons kept rendering; the code behind them was gone; clicking did
nothing, silently — "this is a reoccurring problem", and it is, because template surgery
by slice is how this file is edited. These tests make the next swallow fail here.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from rules.sheet import load_pc
from pagesource import served


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


# What each page must carry: the endpoint its buttons call, and the marker of the
# handler that calls it. A page that renders the button without the handler is the
# defect this file exists for.
WIRING = {
    "/play/": [
        "/api/use", 'closest("[data-use]")',            # the drink button, lost once
        "/api/say", "/api/roll",
        "/api/combat/act", "#cb-commit",                # the combat panel
        # Every trade's open-ground gathering (the shared door, 2026-10-06); the
        # forage button is one `data-gather` among them.
        "/api/craftaction", 'closest("[data-gather]")',
        "/api/level-up",
        "dice3d.js", "Dice3D.ask",                      # the dice
        "[data-gloss]",                                 # the glossary popover
        "The body", "Experience",                       # the ledger and the needs
        "/api/craft/actions", "/api/craft/excursion",   # the acquisition hub
        "cp-biomepick",                                 # the debug picker, moved here
        "/api/wear", "[data-wear]",                     # wearing what you crafted
    ],
    "/craft/": [
        # Every tab is a door to its bench at the table. The old chain bench's shelf,
        # chain, preview, batch Craft and station tooltips went with its routes on
        # 2026-11-08 (audit finding #20); no tab could reach them.
        'closest("[data-craft]")',
        "renderHerbalismMoved", "/play/#bench",
        "renderForgeMoved", "/play/#forge",
        "renderEnchantMoved", "/play/#enchant",
        "renderAlchemyMoved", "/play/#alchemy",
        "renderLeatherMoved", "/play/#leather",
    ],
    "/": [
        "/api/worlds/import", "#worldfile",             # the import button
        "/api/start", "/api/resume",
    ],
}


@pytest.mark.parametrize("page,needles", list(WIRING.items()),
                         ids=list(WIRING.keys()))
def test_the_page_carries_the_code_its_buttons_need(client, page, needles):
    html = served(client, page)
    missing = [n for n in needles if n not in html]
    assert not missing, f"{page} renders buttons over nothing: {missing}"
