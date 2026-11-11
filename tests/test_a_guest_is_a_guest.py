"""A device on the network plays the game; it does not run the machine.

Measured 2026-09-25: `TheDoor` was all or nothing. With the pass a phone could repoint a
hosted provider's `host` at its own server (and be sent the saved API key on the next
turn), delete characters and their saves, import worlds, write homebrew files and start
the Ollama installer. The pass cookie was the signed literal "yes" with no max_age, so
a device that got in once got back in after the door closed and after a relaunch. And
the addresses printed at launch carried `?k=PASS` into the log file.
"""
from __future__ import annotations

import io
import json
import pathlib
import re

import pytest
from django.test import Client, override_settings

from pathfindergm import lan
from play import campaign as cm
from play import concurrency
from rules.sheet import load_pc

ELSEWHERE = "192.168.1.44"


@pytest.fixture
def phone(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns",
                           ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"]):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        cm.begin_with(load_pc("fixtures/pc-kesst.json")).save()
        lan.arm("ABCDEFGHJK", 8917)
        c = Client(REMOTE_ADDR=ELSEWHERE)
        assert c.get("/?k=ABCDEFGHJK").status_code == 302
        yield c
        cm._LIVE.clear()
        lan.disarm()


@pytest.mark.parametrize("path,body", [
    ("/api/settings/models", {"roles": {}, "keys": {}}),
    ("/api/character/delete", {"id": "kesst"}),
    ("/api/worlds/import", {}),
    ("/api/setup/install", {}),
    ("/api/homebrew/rules", {}),
    ("/api/bench/consumables/save", {"id": "x", "name": "x"}),
    ("/api/spells/save", {"id": "x", "name": "x"}),
    ("/api/classes/save", {"id": "x"}),
    ("/api/lan/close", {}),
])
def test_the_hosts_own_doors_are_shut_to_a_guest(phone, path, body):
    r = phone.post(path, data=json.dumps(body), content_type="application/json")
    assert r.status_code == 403, path
    assert "machine the game is running on" in r.json()["error"]


def test_a_guest_still_plays(phone):
    assert phone.get("/api/state").status_code == 200
    r = phone.post("/api/character/gender", data=json.dumps({"gender": "woman"}),
                   content_type="application/json")
    assert r.status_code != 403


def test_the_host_is_not_a_guest(phone):
    local = Client(REMOTE_ADDR="127.0.0.1")
    r = local.post("/api/homebrew/rules", data=json.dumps({}),
                   content_type="application/json")
    assert r.status_code != 403


def test_a_pass_from_a_door_since_closed_is_worthless(phone):
    lan.disarm()
    lan.arm("ZZZZZZZZZZ", 8917)       # the door opened again: a new pass
    assert phone.get("/api/state").status_code == 403


def test_the_cookie_expires():
    assert lan.PASS_SECONDS <= 24 * 60 * 60


def _template_urls(name):
    text = pathlib.Path("play/templates/play", name).read_text(encoding="utf-8")
    return set(re.findall(r"[\"'`](/api/[A-Za-z0-9/_.-]+)", text))


@pytest.mark.parametrize("page", ["table.html", "craft.html", "outfit.html"])
def test_every_write_the_play_pages_make_is_open_to_a_guest(page):
    """The allowlist's other half: a phone playing the table must never meet the host's
    refusal on a button the table itself draws."""
    for url in _template_urls(page):
        if url.startswith("/api/outfit/"):
            url = "/api/outfit/kesst/buy"
        assert lan.guest_may("POST", url), f"{page} posts to {url}, which a guest may not"


def test_the_log_never_holds_the_pass(monkeypatch):
    import desktop

    console, log = io.StringIO(), io.StringIO()
    monkeypatch.setattr(desktop.sys, "stdout", desktop._Tee(console, log))
    address = "http://192.168.1.2:8917/?k=ABCDEFGHJK"
    desktop._console_only(f"    {address}", redacted=f"    {desktop._without_pass(address)}")
    assert "ABCDEFGHJK" in console.getvalue()
    assert "ABCDEFGHJK" not in log.getvalue()


def test_a_guests_reads_leave_out_the_hosts_own_facts(phone):
    """Review 2026-11-11, finding 14: reads were open to a guest whole, so
    `GET /api/settings/models` gave a phone the last four characters of every stored
    key and each role's host, and `GET /api/homebrew/rules` a path holding the Windows
    user name. Redacted, not refused: the Settings panel a guest opens from the table
    draws from both answers, so the shape has to stay."""
    from play import modelcfg

    assert modelcfg.save({"narrator": {"provider": "openai", "model": "gpt"}},
                         {"openai": "sk-secret-9876"}) == []
    guest = phone.get("/api/settings/models")
    assert guest.status_code == 200
    body = guest.json()
    assert "9876" not in guest.content.decode()
    assert body["keys"]["openai"] == {"set": True, "tail": ""}
    assert all(r["host"] == "" for r in body["roles"])
    assert {"roles", "providers", "keys", "installed"} <= set(body)   # the page's shape

    rules = phone.get("/api/homebrew/rules").json()
    assert rules["intimate_examples"] == ""
    assert rules["rules"] and rules["tiers"]

    # The person at the machine still sees all of it.
    local = Client(REMOTE_ADDR="127.0.0.1")
    mine = local.get("/api/settings/models").json()
    assert mine["keys"]["openai"]["tail"] == "9876"
    assert mine["roles"][0]["host"] == "https://api.openai.com/v1"
    assert "intimate" in local.get("/api/homebrew/rules").json()["intimate_examples"]
