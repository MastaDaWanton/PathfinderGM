"""Lane C — the new-campaign screen: the outfit page is creation only, and the start picker
is built as a path and labelled not built yet (owner's answers, 2026-09-28).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.test import Client, override_settings

from play import campaign as cm
from play import library, roster
from rules.sheet import load_pc

HOME = Path("play/templates/play/home.html")


def test_the_outfitter_refuses_a_character_whose_game_has_begun(tmp_path):
    """Measured by the lead at G1: buying on the outfit page after the campaign began
    changed the roster's sheet (`weapons: [unarmed, longsword]`) and not the running
    game's (`unarmed strike`). The owner: "outfit page should not be reachable". The buy
    is refused, 409, with the reason named; a character still being made may shop."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        playing = roster.load(c.character_id)
        waiting = roster.enrol(load_pc("fixtures/pc-borin.json"))
        client = Client()
        buy = json.dumps({"buys": [{"kind": "gear", "key": "rope, hemp (50 ft.)"}]})
        r = client.post(f"/api/outfit/{playing.id}/buy", data=buy,
                        content_type="application/json")
        assert r.status_code == 409, r.content
        assert "already begun" in r.json()["error"]
        assert client.get(f"/api/outfit/{playing.id}").json()["begun"] is True
        state = client.get(f"/api/outfit/{waiting.id}").json()
        assert state["begun"] is False and state["closed"] == ""
        cards = {x["id"]: x for x in library.recent_characters()}
        assert cards[playing.id]["begun"] is True
        assert cards[waiting.id]["begun"] is False
        cm._LIVE.clear()


def test_nothing_on_the_roster_links_a_begun_character_to_the_outfitter():
    """The card's Outfit button is drawn only for a character whose game has not begun."""
    page = HOME.read_text(encoding="utf-8")
    button = page[page.index('data-outfit="${esc(c.id)}"') - 200:
                  page.index('data-outfit="${esc(c.id)}"')]
    assert "!c.begun" in button


def test_the_start_picker_is_on_the_screen_and_says_it_is_not_built_yet():
    """Owner's answer Q20: "make the button/path for it and then label it not built yet".
    "Surprise me" is the working default; the chooser is shown, disabled and labelled;
    the page's text uses no em or en dash (the UI rule the owner gave with it)."""
    page = HOME.read_text(encoding="utf-8")
    start = page.index('<fieldset class="startwhere">')
    block = page[start:page.index("</fieldset>", start)]
    assert re.search(r'value="surprise" checked', block)
    assert re.search(r'value="choose" disabled', block)
    assert "not built yet" in block and "Surprise me" in block
    visible = re.sub(r"<[^>]+>", " ", block)
    assert "—" not in visible and "–" not in visible
    assert "START_CHOICE" in page
