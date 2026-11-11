"""No other site can put the game in a frame.

Review 2026-11-11, finding 16: no response carried `X-Frame-Options`, so any page the
player visited could load `http://127.0.0.1:8917/` in an invisible frame and place its
own buttons over the game's. SAMEORIGIN rather than DENY because the table frames this
server itself — Settings opens as `#settingsframe` — and DENY would blank that panel.
"""
from __future__ import annotations

import importlib
from pathlib import Path

from django.conf import settings
from django.test import Client

ROOT = Path(__file__).resolve().parent.parent


def test_every_kind_of_answer_carries_the_header():
    c = Client()
    for url in ("/", "/outfit/", "/api/setup", "/api/no-such-thing"):
        assert c.get(url).headers.get("X-Frame-Options") == "SAMEORIGIN", url


def test_the_table_still_frames_its_own_settings():
    """The reason it is not DENY. If this iframe goes, DENY becomes the right answer."""
    table = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    assert '<iframe id="settingsframe"' in table
    assert settings.X_FRAME_OPTIONS == "SAMEORIGIN"


def test_the_frozen_build_is_told_about_the_middleware():
    """A middleware is named in settings as a string; one missing from the bundle fails
    every request, not one. Each Django middleware is importable here and the new one
    is written into the spec's hidden imports."""
    for dotted in settings.MIDDLEWARE:
        module, _, name = dotted.rpartition(".")
        assert hasattr(importlib.import_module(module), name), dotted
    spec = (ROOT / "pathfindergm.spec").read_text(encoding="utf-8")
    assert '"django.middleware.clickjacking"' in spec
