"""The page reads every answer the same careful way, and a bad query is not a crash.

Measured 2026-09-25: `post()` parsed replies carefully (a non-JSON error page became
"The server failed (HTTP 500)"), but eight other `r.json()` calls in the play table did
not, so a failure there showed the player "JSON.parse: unexpected character". Two views
did `int(request.GET["limit"])`, a 500 on "?limit=many". And `busy()` disabled only the
send button, leaving the combat bar, Cast, Use and the talk panel live mid-turn.
"""
from __future__ import annotations

import pathlib
import re

from django.test import Client


def _page():
    return pathlib.Path("play/templates/play/table.html").read_text(encoding="utf-8")


def test_no_reply_is_parsed_around_readjson():
    code = "\n".join(l for l in _page().splitlines() if not l.strip().startswith("//"))
    assert re.findall(r"\.json\(\)", code) == [], "a reply parsed without readJSON"


def test_busy_reaches_every_action_control():
    page = _page()
    body = page[page.index("function busy(on)"):][:600]
    assert 'classList.toggle("resolving", on)' in body
    for sel in ("#combatbar button", ".castbtn", "[data-use]", "#talk button"):
        assert f"body.resolving {sel}" in page, sel


def test_a_bad_limit_is_not_a_crash():
    c = Client()
    assert c.get("/api/feats?limit=many").status_code < 500
    assert c.get("/api/spells?limit=many").status_code < 500
