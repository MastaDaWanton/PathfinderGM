"""Two views on one game, which the app has never had until now.

The app has always opened exactly one window, and every piece of state handling assumes
it. `play/campaign.py` keeps the live game in a process-global `_LIVE` dict and
`desktop.py` serves it on `ThreadedWSGIServer`, which spawns a thread per request — so
before this file existed there was **no lock anywhere in `play/`, `gm/` or `rules/`**
except the two in `gm/watcher.py` guarding its own job list. Two clients on one campaign
were two threads mutating one object.

Three separate defects hide under "the second device drifts", and they have three
different answers. These tests pin each one. `docs/lan-play.md` is the design record.

  1. **Staleness.** A view that did not act never learns anything changed: every
     re-render in `table.html` follows that client's *own* fetch. Act on the laptop and
     the phone shows the scene from twenty minutes ago — and a turn typed against text
     that is no longer true is the harm a single player actually meets.
  2. **Lost update.** Two writes into one `Campaign` on two threads. Reachable today by
     opening two browser tabs on the desktop; never provoked only because nothing opens a
     second one.
  3. **Double-acting.** Two declarations for one PC.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import concurrency
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.save()
        yield Client()
        cm._LIVE.clear()


# A cheap, honest 2xx write that touches the campaign and nothing else in the world.
WRITE = ("/api/character/gender", {"gender": "woman"})


def post(client, revision=None, url=WRITE[0], body=None):
    headers = {} if revision is None else {concurrency.HEADER: str(revision)}
    return client.post(url, body if body is not None else WRITE[1],
                       content_type="application/json", headers=headers)


@contextmanager
def the_lock_held_by_another_thread():
    """Hold the game lock from somewhere that is not the request thread.

    It has to be another thread. `_GAME` is an `RLock`, so a test that took it on the
    same thread the test client runs on would re-enter it happily and prove nothing —
    which is the trap this helper exists to keep anybody from walking into.
    """
    taken, release = threading.Event(), threading.Event()

    def hold():
        with concurrency.held(5.0):
            taken.set()
            release.wait(30)

    worker = threading.Thread(target=hold, daemon=True)
    worker.start()
    assert taken.wait(5), "the holding thread never got the lock"
    try:
        yield
    finally:
        release.set()
        worker.join(5)


# ---------------------------------------------------------------- 1. staleness

def test_a_write_moves_the_revision_and_a_read_does_not(client):
    """The number is the whole notification channel, so it has to mean exactly one
    thing: the game changed. A read that moved it would send every open device off to
    re-fetch a state nobody had touched, once per poll, forever."""
    start = client.get("/api/revision").json()["revision"]

    client.get("/api/state")
    assert client.get("/api/revision").json()["revision"] == start

    assert post(client).status_code == 200
    assert client.get("/api/revision").json()["revision"] == start + 1


def test_every_answer_says_what_revision_it_was_drawn_at(client):
    """A client cannot police its own writes without knowing which revision the screen
    in front of it was rendered from, and asking for it separately would race the render
    it is supposed to describe."""
    assert concurrency.HEADER in client.get("/api/state").headers
    assert concurrency.HEADER in post(client).headers


def test_a_write_answers_with_the_revision_it_produced_not_the_one_it_started_from(client):
    """The stamp is applied after the view has run, and it matters.

    Stamped before, a client would store the pre-write number, send it on its next write,
    and be told its own turn had made it stale — a single device locking itself out after
    one action, which is a worse bug than the one this whole file is about."""
    before = client.get("/api/revision").json()["revision"]
    answered = int(post(client, revision=before).headers[concurrency.HEADER])
    assert answered == before + 1
    # And the client can immediately write again using it.
    assert post(client, revision=answered).status_code == 200


def test_the_watcher_landing_on_a_read_moves_the_revision(client, monkeypatch):
    """`/api/state` is the one mutating GET in the app: it drains the watcher on the
    request thread. The middleware counts successful *unsafe* requests and this is
    neither, so without an explicit bump the phone sits on a stale screen until somebody
    happens to act — and the watcher's work is exactly the kind that arrives while
    nobody is touching the phone."""
    from gm import watcher

    monkeypatch.setattr(watcher, "drain", lambda c: True)
    start = client.get("/api/revision").json()["revision"]
    client.get("/api/state")
    assert client.get("/api/revision").json()["revision"] == start + 1


# ------------------------------------------------------------- 2. lost update

def test_a_write_composed_against_an_old_screen_is_refused(client):
    """The defect this exists to prevent, in one sentence: you act on the laptop from a
    scene the phone has already moved past, and the engine applies it to a world that no
    longer matches the text you read.

    412 rather than 409 deliberately — a failed precondition is "your copy was stale,
    look again", which is a different thing for the client to do than "the game says no
    right now"."""
    stale = client.get("/api/revision").json()["revision"]
    assert post(client, revision=stale).status_code == 200      # the phone acts
    refused = post(client, revision=stale)                      # the laptop, still behind
    assert refused.status_code == 412
    assert refused.json()["stale"] is True
    assert refused.json()["revision"] == stale + 1


def test_the_refusal_carries_numbers_and_not_a_second_copy_of_the_state(client):
    """The client already has one path that fetches and renders state. A second one
    inside middleware would be the duplicate the design exists to avoid — and it would
    have to build that state outside the game lock, which is a torn read to save the
    client a request it already knows how to make."""
    stale = client.get("/api/revision").json()["revision"]
    post(client, revision=stale)
    body = post(client, revision=stale).json()
    assert set(body) == {"error", "stale", "your_revision", "revision"}


def test_a_write_with_no_revision_is_not_checked(client):
    """Only `table.html` takes part. The forge, the benches and the three builders post
    without a revision and must be untouched by any of this — absent means "no
    precondition", exactly as a missing `If-Match` does in RFC 9110."""
    assert post(client).status_code == 200
    assert post(client).status_code == 200
    assert post(client, revision="not a number").status_code == 200


def test_writes_from_several_threads_are_serialised_and_each_counted_once(client,
                                                                          monkeypatch):
    """Eight simultaneous writes into one `Campaign` object. Before the lock this was
    eight threads in `play/views.py` with nothing between them; `_state()` iterates
    `c.scene.actors.items()`, which in CPython raises rather than answering wrongly if
    another thread adds an actor underneath it."""
    monkeypatch.setattr(concurrency, "WRITE_WAIT", 20.0)
    start = client.get("/api/revision").json()["revision"]
    codes, lock = [], threading.Lock()

    def write():
        code = post(Client()).status_code
        with lock:
            codes.append(code)

    threads = [threading.Thread(target=write) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert codes == [200] * 8
    assert client.get("/api/revision").json()["revision"] == start + 8


# ------------------------------------------------------------ 3. double-acting

def test_a_second_writer_is_refused_rather_than_left_on_a_spinner(client, monkeypatch):
    """When the lock is held it is almost always held by a GM turn, which is 10-95 s of
    local model. A player who hit Send on two devices gets one turn and one honest
    refusal now, rather than a spinner that sits for a minute and a half without saying
    why. 409, because this is the game saying no — not a stale copy."""
    monkeypatch.setattr(concurrency, "WRITE_WAIT", 0.05)
    with the_lock_held_by_another_thread():
        refused = post(client)
    assert refused.status_code == 409
    assert refused.json()["busy"] is True


def test_the_heartbeat_and_the_revision_never_wait_on_the_game_lock(client, monkeypatch):
    """Both would be useless at the only moment they are needed.

    `/api/alive` is what stops `desktop.py` reaping the server after 180 s of silence
    (`pathfindergm/liveness.py`), so a turn that blocked it would let a long turn reap
    the server that was resolving it. `/api/revision` is how the second device learns it
    is waiting rather than broken."""
    monkeypatch.setattr(concurrency, "READ_WAIT", 0.05)
    with the_lock_held_by_another_thread():
        assert client.get("/api/alive").status_code == 200
        assert client.get("/api/revision").status_code == 200


def test_the_documents_do_not_wait_on_the_game_lock_either(client, monkeypatch):
    """The manual and the licence load no campaign. A player who opened the rules on
    their phone while the laptop was ninety seconds into a turn would otherwise watch a
    document hang — for a page the turn could not have changed."""
    monkeypatch.setattr(concurrency, "READ_WAIT", 0.05)
    with the_lock_held_by_another_thread():
        assert client.get("/manual").status_code == 200
        assert client.get("/licence").status_code == 200


def test_a_read_of_the_state_does_wait_on_the_game_lock(client, monkeypatch):
    """The other half of the same rule, and the reason the two exempt endpoints above
    are listed by hand rather than inferred: `/api/state` walks the whole scene, so it
    must not run while a write is halfway through changing it."""
    monkeypatch.setattr(concurrency, "READ_WAIT", 0.05)
    with the_lock_held_by_another_thread():
        assert client.get("/api/state").status_code == 409
