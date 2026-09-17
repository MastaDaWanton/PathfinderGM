"""Who is allowed to reach a table that is listening to the network.

The app shipped with no authentication of any kind — `MIDDLEWARE` was `CommonMiddleware`
and `CsrfViewMiddleware` and nothing else — because `desktop.py` bound `127.0.0.1` and
"only this machine can talk to it" was the whole security model. `settings.py` had
already written down that this was a property of the launcher rather than a guarantee.
Opening the door — the button in Settings, or `--lan` at launch — is the day it stops
being true: without a door, `/api/say` is something anybody on the same Wi-Fi can POST to.

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

    Nothing in `pathfindergm/lan.py` runs until the door is opened. A launch nobody has
    pressed the button in keeps the posture it has had since 0.1.0 — no socket on the
    network, no token, no cookie, and not one byte different on the wire."""
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


# --- The door as a thing a button opens ---------------------------------------------

@pytest.fixture
def shut_afterwards():
    """Whatever a test does, the process must not be left listening to the network."""
    yield
    lan.close_the_door()


def test_the_door_starts_shut_and_binds_nothing(client):
    """The posture, restated as a test because it is the whole promise. Until somebody
    presses the button there is no socket on the network at all — not a refused one, not
    a guarded one, none."""
    assert not lan.is_open()
    assert lan.status() == {"open": False, "url": "", "pass": "", "qr": "",
                            "addresses": []}


def test_opening_the_door_binds_a_second_socket_and_leaves_the_game_on_loopback(
        client, shut_afterwards):
    """Two sockets, never one shared one.

    The first version of this feature bound `0.0.0.0` for the whole process, and a
    wildcard bind plus a loopback bind are different addresses — so the OS grants both
    and Windows splits loopback connections between them at random (measured 2026-09-17,
    two live servers on 8917). The game stays on `127.0.0.1` and the network gets its own
    OS-chosen port, which is a shape in which that cannot happen."""
    state = lan.open_the_door()
    assert state["open"] and lan.is_open()
    assert lan._server.server_address[0] == "0.0.0.0"
    assert lan._server.server_address[1] != 8917


def test_an_open_door_hands_over_a_scannable_code_and_the_text_behind_it(
        client, shut_afterwards):
    """The QR is the feature; the text is what a player falls back on when the camera
    will not focus. Both have to describe the same door."""
    state = lan.open_the_door()
    assert state["pass"] and len(state["pass"]) == lan.TOKEN_LENGTH
    assert state["pass"] in state["url"]
    assert state["url"].startswith("http://")
    assert state["qr"].startswith("<svg") and state["pass"] in "".join(state["addresses"])


def test_opening_twice_does_not_mint_a_second_pass(client, shut_afterwards):
    """A player pressing the button again — or a second window rendering the panel —
    must not invalidate the code their phone is already looking at."""
    first = lan.open_the_door()
    assert lan.open_the_door()["pass"] == first["pass"]


def test_closing_the_door_makes_the_pass_worthless(client, shut_afterwards):
    """Not merely unreachable. The token is forgotten, so a phone that kept the address
    cannot walk back in if the door is opened again later."""
    spent = lan.open_the_door()["pass"]
    lan.close_the_door()
    assert not lan.is_open() and not lan.enabled()
    assert lan.token() != spent


@pytest.mark.parametrize("path,method", [
    ("/api/lan", "get"), ("/api/lan/open", "post"), ("/api/lan/close", "post")])
def test_only_this_machine_may_work_the_door(client, path, method, shut_afterwards):
    """Two reasons, either sufficient. A phone that could close the door could lock the
    desktop out of its own game; and `close_the_door` waits for its server's loop to come
    round, so a request that server is itself serving would deadlock rather than fail."""
    answered = getattr(client, method)(path, content_type="application/json",
                                       REMOTE_ADDR=ELSEWHERE)
    assert answered.status_code == 403
    assert not lan.is_open()


def test_the_door_endpoints_never_wait_on_the_game_lock(client, monkeypatch,
                                                        shut_afterwards):
    """The one moment a player reaches for this is mid-turn, with the phone in their
    hand. A panel that hung for ninety seconds would be a panel they conclude is broken."""
    import threading

    from play import concurrency

    monkeypatch.setattr(concurrency, "READ_WAIT", 0.05)
    taken, release = threading.Event(), threading.Event()

    def hold():
        with concurrency.held(5.0):
            taken.set()
            release.wait(30)

    worker = threading.Thread(target=hold, daemon=True)
    worker.start()
    assert taken.wait(5)
    try:
        assert client.get("/api/lan", REMOTE_ADDR="127.0.0.1").status_code == 200
    finally:
        release.set()
        worker.join(5)
