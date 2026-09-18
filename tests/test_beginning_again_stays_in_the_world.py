"""Beginning again with somebody else is not leaving the world.

Reported 2026-09-18: "clicking any of the premade characters as a player start puts you
in Pangrella instead of the world you chose." Two doors start a game with a pregen. The
home page's (`home_views.start`) passes the chosen world's source; the table page's
picker posts `/api/character/new`, whose view called `begin_with(character)` with no
world at all, so `new_campaign` filled it with the shipped default — Pangrella — whatever
world the player had been standing in a moment before.
"""
from __future__ import annotations

import json

from django.test import Client, override_settings

from play import campaign as cm
from rules.sheet import load_pc

AURVANTIS = "fixtures/aurvantis-campaign.json"


def test_a_pregen_picked_from_the_table_starts_in_the_world_the_player_was_in(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"), world_source=AURVANTIS)
        assert "aurvantis" in str(first.world_source).lower()

        r = Client().post("/api/character/new", data=json.dumps({"source": "pc-borin"}),
                          content_type="application/json")
        assert r.status_code == 200, r.content[:200]
        again = cm.current()
        assert again.id != first.id
        assert again.scene.pc().name.startswith("Borin")
        assert "aurvantis" in str(again.world_source).lower(), again.world_source
        cm._LIVE.clear()


def test_with_no_campaign_to_keep_the_world_of_the_default_still_works(tmp_path):
    """The fallback is the old behaviour, not a crash: a picker used with nothing
    playable behind it starts in the shipped world."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        r = Client().post("/api/character/new", data=json.dumps({"source": "pc-borin"}),
                          content_type="application/json")
        assert r.status_code == 200, r.content[:200]
        assert cm.current().scene.pc().name.startswith("Borin")
        cm._LIVE.clear()


def test_the_title_bar_names_the_world_the_player_is_in(tmp_path):
    """"Why does the shell say Pangrella when I'm playing in Aurvantis?" — the table's
    <title> was the shipped world's name typed into the template, and the shell shows
    the page title. The state carries the world's name too, so a picker that begins
    again without a reload can retitle the window."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), world_source=AURVANTIS)
        name = c.world.name
        assert name and "pangrella" not in name.lower()
        page = Client().get("/play/").content.decode("utf-8", "replace")
        assert f"<title>Pathfinder GM — {name}</title>" in page, page[:300]
        assert "Pathfinder GM — Pangrella" not in page
        assert f'"world": "{name}"' in page
        cm._LIVE.clear()
