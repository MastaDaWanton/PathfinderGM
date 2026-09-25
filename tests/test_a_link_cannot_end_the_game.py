"""No GET request changes the game.

Measured 2026-09-25: `/play/?new=1` archived the running campaign and started another
from a GET. CSRF protection does not cover GET and the desktop server sits on a fixed
port, so `<img src="http://127.0.0.1:8917/play/?new=1">` on any web page the player
opened reset their game. Nothing in the app linked to it.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings


@pytest.fixture
def playing(tmp_path, monkeypatch):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import preflight

        monkeypatch.setattr(preflight, "check", lambda: type("R", (), {"ok": True})())
        cm._LIVE.clear()
        c = cm.current()
        c.transcript.append({"who": "gm", "text": "The game the player was playing."})
        c.save()
        yield cm, c
        cm._LIVE.clear()


def test_a_link_with_new_1_does_not_reset_the_campaign(playing):
    cm, c = playing
    r = Client().get("/play/?new=1")
    assert r.status_code == 200
    after = cm.current()
    assert after.transcript[-1]["text"] == "The game the player was playing."
    assert not list(c.path().parent.glob(f"{c.id}-*.json")), "nothing was archived"
