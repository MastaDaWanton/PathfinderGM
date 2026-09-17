"""Who is allowed to reach a table that is listening to the network.

The app shipped with no authentication of any kind — `MIDDLEWARE` was `CommonMiddleware`
and `CsrfViewMiddleware` and nothing else — because `desktop.py` bound `127.0.0.1` and
"only this machine can talk to it" was the whole security model. `settings.py` had
already written down that this was a property of the launcher rather than a guarantee.
`desktop.py --lan` is the day it stops being true: without a door, `/api/say` is
something anybody on the same Wi-Fi can POST to.

The thing these mostly pin is the **off** state. A feature that quietly changed how the
ordinary loopback launch behaves would be a far worse bug than the one it was added for.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from pathfindergm import lan
from play import campaign as cm
from play import concurrency
from rules.sheet import load_pc

ELSEWHERE = "192.168.1.44"      # a phone on the same Wi-Fi


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns",
                           ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"]):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        cm.begin_with(load_pc("fixtures/pc-kesst.json")).save()
        yield Client()
        cm._LIVE.clear()
        lan.disarm()


@pytest.fixture
def armed():
    lan.arm("ABCDEFGHJK", 8917)
    yield "ABCDEFGHJK"
    lan.disarm()


def test_an_ordinary_launch_asks_nobody_for_anything(client):
    """The off state, and the most important test in this file.

    Nothing in `pathfindergm/lan.py` runs until `desktop.py --lan` arms it. A loopback
    launch keeps the posture it has had since 0.1.0 — no token, no cookie, and not one
    byte different on the wire."""
    assert not lan.enabled()
    assert client.get("/api/state", REMOTE_ADDR="127.0.0.1").status_code == 200
    # Even a request claiming to be from elsewhere: with the door disarmed there is no
    # door, and pretending otherwise would be security theatre that hides the real state.
    assert client.get("/api/state", REMOTE_ADDR=ELSEWHERE).status_code == 200


def test_the_desktops_own_browser_never_needs_a_pass(client, armed):
    """The app opens that window itself, on the far side of no network at all. Making it
    authenticate would be theatre the player pays for every launch."""
    assert client.get("/api/state", REMOTE_ADDR="127.0.0.1").status_code == 200


def test_a_stranger_with_no_pass_is_turned_away(client, armed):
    assert client.get("/api/state", REMOTE_ADDR=ELSEWHERE).status_code == 403


def test_a_stranger_cannot_take_a_turn(client, armed):
    """The endpoint this door exists for. Everything else is a screen; this one moves
    the campaign."""
    refused = client.post("/api/say", {"text": "I draw my sword"},
                          content_type="application/json", REMOTE_ADDR=ELSEWHERE)
    assert refused.status_code == 403


def test_a_wrong_pass_is_refused_and_a_right_one_is_spent_for_a_cookie(client, armed):
    """The pass rides in the query string exactly once.

    A token left sitting in the address bar is one that gets bookmarked, screenshotted,
    and written into browser history, so the answer is a redirect to the same path
    without it. Jupyter's shape, for Jupyter's reasons."""
    assert client.get(f"/api/state?k=WRONGPASS1",
                      REMOTE_ADDR=ELSEWHERE).status_code == 403

    opened = client.get(f"/api/state?k={armed}", REMOTE_ADDR=ELSEWHERE)
    assert opened.status_code == 302
    assert opened.headers["Location"] == "/api/state"
    assert lan.COOKIE in opened.cookies

    # And the cookie the redirect set carries the phone through afterwards.
    assert client.get("/api/state", REMOTE_ADDR=ELSEWHERE).status_code == 200


def test_the_pass_is_read_case_insensitively(client, armed):
    """The alphabet is upper-case and a phone keyboard is not. A player who typed their
    pass correctly and was refused for the shift key has been told the app is broken."""
    opened = client.get(f"/api/state?k={armed.lower()}", REMOTE_ADDR=ELSEWHERE)
    assert opened.status_code == 302


def test_the_redirect_does_not_replay_the_rest_of_the_query(client, armed):
    """`?new=1` on `/play/` archives the campaign and starts another one. A redirect that
    helpfully preserved the query string would do that a second time, on a phone, to a
    player who was only trying to log in."""
    opened = client.get(f"/play/?new=1&k={armed}", REMOTE_ADDR=ELSEWHERE)
    assert opened.headers["Location"] == "/play/"


def test_a_forged_cookie_is_not_a_pass(client, armed):
    """Signed rather than stored, so tampering has to be detected rather than looked up.
    A truncated or edited cookie reads as no cookie at all."""
    client.cookies[lan.COOKIE] = "yes"          # unsigned, the obvious forgery
    assert client.get("/api/state", REMOTE_ADDR=ELSEWHERE).status_code == 403


def test_arming_teaches_django_the_names_the_phone_will_use(client):
    """Two 400s and a 403 that all look like bugs, and none of which name the cause.

    Django refuses a Host header it was not told about, and `ALLOWED_HOSTS` shipped as
    `["127.0.0.1", "localhost", "testserver"]` — so the phone's `http://192.168.x.x:8917`
    is a `DisallowedHost` before any view runs. The matching `CSRF_TRUSTED_ORIGINS` is
    the same failure one step later: the page renders and every turn 403s, which is
    exactly what `views.table` records happening for the missing CSRF cookie."""
    from django.conf import settings

    lan.arm("ABCDEFGHJK", 8917)
    try:
        for address in lan.addresses():
            assert address in settings.ALLOWED_HOSTS
            assert f"http://{address}:8917" in settings.CSRF_TRUSTED_ORIGINS
    finally:
        lan.disarm()


def test_a_minted_pass_is_typeable_and_unambiguous(client):
    """Ten characters with no 0/O and no 1/l/I in the alphabet.

    Both halves are load-bearing. Fifty bits is past anything worth brute-forcing on a
    LAN; and a character misread on a phone screen is a player who cannot tell a typo
    from a broken app. The alternative — `secrets.token_urlsafe(16)` — is twenty-two
    characters of mixed case that a player gets wrong twice and gives up on."""
    minted = {lan.mint() for _ in range(200)}
    assert len(minted) == 200                       # not a constant, not a counter
    for one in minted:
        assert len(one) == lan.TOKEN_LENGTH
        assert not set(one) & set("0O1lI")
