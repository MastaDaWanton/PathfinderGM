"""`/api/roll/face` — the number, before the turn that uses it.

Reported from the table 2026-09-16:

    "as it stands when dice are rolled the last die spins until a reply is sent to the
    user. I would prefer that the dice land show the number it landed on and then be
    able to be closed while the user waits."

The cause is the shape of `/api/roll`. It knows the face in its first few lines and
returns it only after resolution AND the narrator, which is a local model and the slow
part of a turn. So the die span for the whole generation, and the LAST die of a turn span
longest — every earlier one only had to be handed back so the next prompt could open.

This endpoint exists so the page can land the die at once. Everything here is about the
one property that makes that safe: **it decides a number and changes nothing**, so a
player who closes the mat, closes the tab, or loses the connection has spent nothing and
the pending roll is exactly where they left it.

`tests/test_dice3d.py` holds the page's half — that it asks for this before posting the
turn, and does not await the landing.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.save()
        yield Client()
        cm._LIVE.clear()


def _pending(client, die="1d20", lo=1, hi=20):
    """A campaign with a roll waiting on it.

    The prompt is set directly rather than driven out of the engine through foraging,
    which is how this started and which SKIPPED three of five tests on the first run —
    the fixture's opening scene has company in it and foraging needs solitude. A test
    that skips is a test that is not run, and these are the ones that matter.

    Writing the field is honest here because the field is the whole interface: `roll_face`
    reads `scene.awaiting` and nothing else, and this is the shape `engine.py` puts there
    (`rules/engine.py:7707`).
    """
    c = cm.current()
    c.scene.awaiting = {
        "label": "Perception", "die": die, "actor": "Kesst",
        "min": lo, "max": hi, "modifier": 3, "breakdown": [], "dc": 15,
        "dc_shown": True,
    }
    c.save()
    return c


def test_it_answers_with_a_face_the_pending_die_could_show(client):
    c = _pending(client)
    lo = c.scene.awaiting.get("min", 1)
    hi = c.scene.awaiting.get("max", 20)
    r = client.post("/api/roll/face", data="{}", content_type="application/json")
    assert r.status_code == 200
    face = r.json()["face"]
    assert isinstance(face, int)
    assert lo <= face <= hi, f"{face} is not a face of {c.scene.awaiting}"


def test_asking_for_a_face_does_not_spend_the_roll(client):
    """The property the whole design rests on. If this endpoint consumed `awaiting`, a
    player who closed the tab between the two requests would come back to a turn that had
    half happened — and the old single-request shape could not do that to them."""
    c = _pending(client)
    before = json.dumps(c.scene.awaiting, sort_keys=True, default=str)
    for _ in range(3):
        assert client.post("/api/roll/face", data="{}",
                           content_type="application/json").status_code == 200
    after = cm.current().scene.awaiting
    assert after, "asking what the die shows consumed the pending roll"
    assert json.dumps(after, sort_keys=True, default=str) == before


def test_two_asks_are_allowed_to_differ(client):
    """It rolls each time rather than remembering. Worth pinning because the tempting
    "fix" for that is to cache the face on the scene — which would make this endpoint
    stateful, and statefulness is the one thing it must not have. Nothing needs the two
    to agree: the page sends back the face it landed on, and `/api/roll` uses what it is
    given, exactly as it already does for a player rolling a real die on the desk."""
    _pending(client)
    seen = set()
    for _ in range(40):
        seen.add(client.post("/api/roll/face", data="{}",
                             content_type="application/json").json()["face"])
    assert len(seen) > 1, "40 asks gave one number; this is not rolling"


def test_it_refuses_when_nothing_is_waiting(client):
    c = cm.current()
    if c.scene.awaiting:
        pytest.skip("this campaign opened with a roll already pending")
    r = client.post("/api/roll/face", data="{}", content_type="application/json")
    assert r.status_code == 409
    assert "nothing is waiting" in r.json()["error"]


def test_it_is_a_post(client):
    """A GET that rolls a die is a link somebody's browser can prefetch."""
    assert client.get("/api/roll/face").status_code == 405
