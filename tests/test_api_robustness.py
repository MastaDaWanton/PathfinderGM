"""What the endpoints do with input no honest browser would send.

Found by probing one endpoint with twenty-seven hostile bodies: seven came back HTTP 500
with a traceback. In the packaged app a 500 is a button that does nothing and says
nothing, which is the same failure CLAUDE.md already records for a hidden required field
— "nothing happens, and nothing says why".

All seven were two lines repeated across the app:

* `json.loads(request.body or "{}")` followed by `body.get(...)`, which raises on
  malformed JSON *and* on a bare array, string or null — those parse fine and then die
  on `.get`. The pattern was at twenty-seven call sites in five modules.
* `int(body.get("hours", 1) or 1)`, which is fine for a number and raises for `"many"`,
  for `[1, 2]` and for `NaN`.

A refusal is the app working; only a 5xx or an exception is a break. These pin that.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play.apiutil import read_body, read_int
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.pc().purse = {"gp": 500}
        c.save()
        yield Client()
        cm._LIVE.clear()


HOSTILE_BODIES = [
    ("negative hours", {"action": "blacksmith:buy", "hours": -5}),
    ("huge hours", {"action": "blacksmith:buy", "hours": 10 ** 9}),
    ("string hours", {"action": "blacksmith:buy", "hours": "many"}),
    ("list hours", {"action": "blacksmith:buy", "hours": [1, 2]}),
    ("nan hours", {"action": "blacksmith:buy", "hours": float("nan")}),
    ("null hours", {"action": "blacksmith:buy", "hours": None}),
    ("unknown action", {"action": "wizard:handwave"}),
    ("null action", {"action": None}),
    ("list action", {"action": ["blacksmith:buy"]}),
    ("no action key", {}),
    ("very long action", {"action": "x" * 5000}),
    # Built with chr() rather than written as an escape: a literal NUL in the
    # source is the same trap CLAUDE.md records for backslashes, and pytest
    # cannot even parse the file.
    ("nul byte in action", {"action": "blacksmith:buy" + chr(0)}),
    ("path traversal", {"action": "../../etc/passwd"}),
    ("creature is a dict", {"action": "leatherworker:skin", "creature": {"a": 1}}),
]


@pytest.mark.parametrize("name,body", HOSTILE_BODIES, ids=[n for n, _ in HOSTILE_BODIES])
def test_a_hostile_body_is_refused_rather_than_raised(client, name, body):
    r = client.post("/api/craft/excursion", data=json.dumps(body),
                    content_type="application/json")
    assert r.status_code < 500, f"{name} -> {r.status_code}"


RAW_BODIES = [("not json", b"{not json"), ("empty", b""), ("array", b"[1,2,3]"),
              ("bare string", b'"hello"'), ("bare null", b"null"),
              ("bare number", b"42"), ("nested deep", b'{"a":' * 40 + b"1" + b"}" * 40)]


@pytest.mark.parametrize("name,raw", RAW_BODIES, ids=[n for n, _ in RAW_BODIES])
def test_a_body_that_is_not_an_object_is_refused_rather_than_raised(client, name, raw):
    """A JSON array parses perfectly well and then kills `.get`. Four of the original
    seven 500s were exactly this."""
    r = client.post("/api/craft/excursion", data=raw,
                    content_type="application/json")
    assert r.status_code < 500, f"{name} -> {r.status_code}"


def test_read_body_answers_with_an_object_or_nothing():
    class Req:
        def __init__(self, body):
            self.body = body

    assert read_body(Req(b'{"a": 1}')) == {"a": 1}
    for junk in (b"{not json", b"[1,2]", b'"hi"', b"null", b"42", b"", None):
        assert read_body(Req(junk)) == {}, junk


def test_read_int_never_raises_and_clamps():
    assert read_int({"n": 5}, "n", 1) == 5
    assert read_int({"n": "7"}, "n", 1) == 7
    assert read_int({"n": 2.9}, "n", 1) == 2
    assert read_int({}, "n", 3) == 3
    for junk in ("many", [1, 2], {"a": 1}, None, float("nan"), float("inf")):
        assert read_int({"n": junk}, "n", 1) == 1, junk
    # A JSON `true` is an int in Python and must not become one hour.
    assert read_int({"n": True}, "n", 4) == 4
    assert read_int({"n": 99}, "n", 1, lo=1, hi=12) == 12
    assert read_int({"n": -99}, "n", 1, lo=1, hi=12) == 1
