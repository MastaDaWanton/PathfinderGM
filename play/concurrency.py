"""One game, one writer at a time, and one number that says whether it moved.

The app has always assumed exactly one window. `play/campaign.py` keeps the live game in
a process-global `_LIVE` dict and `desktop.py` serves it on `ThreadedWSGIServer`, which
spawns a thread per request — so two clients on one campaign are two threads mutating one
object with no lock between them. That is reachable today by opening two browser tabs on
the desktop; it has simply never been provoked, because the app opens one window. Serving
on the LAN so a phone can join makes it the normal case.

`docs/lan-play.md` carries the full design record and the prior-art sweep. The short
version of why this file is shaped the way it is:

  **The lock and the counter answer different questions, so they are different things.**
  The lock stops two threads corrupting one `Campaign`. The counter stops a player acting
  on a screen that is twenty minutes out of date. A single mechanism for both would have
  to choose one of the two jobs to do badly.

  **The counter has its own small lock, and that is not an oversight.** Reading the
  revision must answer *instantly* while a turn holds the game lock, because a turn is
  10-95 s of local model and the whole point of the polling channel is to let the other
  device notice. If `/api/revision` queued behind the game lock, the second device could
  not even discover that it was waiting.

  **The revision is a number, never a state.** Clients that are behind re-fetch
  `/api/state` through the path they already use. Pushing state down a side channel would
  mean a second serialiser to keep in step with `_state()`, which is exactly the shape
  CLAUDE.md's "when you fix a rule, grep for every copy of it" was written about.

  **It over-bumps on purpose.** Any successful unsafe request counts, including ones that
  changed nothing a player can see. Over-bumping costs one redundant `/api/state` fetch;
  under-bumping costs a stale screen with nothing to notice it by. If somebody later
  makes this cleverer, that is the direction the cleverness must not go.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from django.http import JsonResponse

# The header a client sends to say which revision it composed a write against, and which
# every answer carries back so the client can keep up. One name, used in both directions.
HEADER = "X-Game-Revision"

# How long an unsafe request waits for the game lock before giving up and saying so.
#
# Two seconds rather than zero: a single client can put two writes in flight across a
# fast double-click, and refusing those would be a regression for the one-device case
# that has always worked. Two seconds rather than sixty: when the lock is held it is
# almost always held by a GM turn, which is up to ~95 s of local model, and a player who
# double-acted deserves to be told so now rather than after the turn they cannot see.
WRITE_WAIT = 2.0

# A read waits as long as a turn can reasonably take. This is a deadlock backstop, not a
# timeout anybody should meet: a state poll arriving mid-turn *should* wait, because there
# is nothing new to show until the turn lands.
READ_WAIT = 300.0

# Paths that must never take the game lock.
#
#   /api/alive     is documented as the cheapest view in the app and loads no campaign.
#                  Making liveness wait on the game lock would let a long turn reap the
#                  server that was resolving it.
#   /api/revision  is the channel that reports the lock is busy; queueing it behind the
#                  lock would make it useless at the one moment it is needed.
#   /api/setup     talks to Ollama over the network, and /api/setup/pull streams a
#                  multi-gigabyte model download. Middleware releases its lock when the
#                  view *returns*, which for a StreamingHttpResponse is before a byte of
#                  the body has been produced — so a streaming endpoint cannot be guarded
#                  here even if it wanted to be. Neither touches the campaign.
#   /manual        and /licence are documents. Neither loads a campaign, and a player
#   /licence       who opened the rules on their phone while the laptop was ninety
#                  seconds into a turn would otherwise watch the manual hang — for a
#                  page that could not have been affected by the turn either way.
#   /static/       is files.
EXEMPT = ("/static/", "/api/alive", "/api/revision", "/api/setup", "/manual", "/licence")

_GAME = threading.RLock()

_counter_lock = threading.Lock()
_revision = 0


class Busy(RuntimeError):
    """Another request is holding the game and did not let go in time."""


def revision() -> int:
    """The number of times anything has mutated the game in this process."""
    with _counter_lock:
        return _revision


def bump() -> int:
    """Say that something changed. The only way the number ever moves."""
    global _revision
    with _counter_lock:
        _revision += 1
        return _revision


def reset_for_tests() -> None:
    """Put the counter back to zero between tests, and nothing else.

    The lock is deliberately not touched: a test that leaves it held has a bug worth
    seeing rather than papering over.
    """
    global _revision
    with _counter_lock:
        _revision = 0


@contextmanager
def held(timeout: float):
    """The game lock, or `Busy` if it could not be had inside `timeout`."""
    if not _GAME.acquire(timeout=timeout):
        raise Busy()
    try:
        yield
    finally:
        _GAME.release()


def _sent_revision(request) -> int | None:
    """What revision the client says it composed this write against.

    `None` means the client is not taking part in the protocol, and that is a supported
    answer rather than an error: only `table.html` sends the header, and every other page
    in the app — the forge, the benches, the class builder — posts without one and must
    carry on working untouched. Absent means "no precondition", exactly as a missing
    `If-Match` does in RFC 9110.
    """
    raw = request.headers.get(HEADER)
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        # Unparseable is treated as absent rather than as a refusal. A client that sends
        # nonsense here is a bug or a probe, and the house rule for those is already
        # written down in `play/apiutil.py`: read nothing out of it and carry on.
        return None


def _stale(sent: int | None):
    """A 412 if the client's copy has been overtaken, otherwise None.

    412 rather than 409, and the split is load-bearing. **412 means the client's copy was
    stale** — re-render, look at what happened, decide again. **409 means the game itself
    says no right now** — a roll is waiting, or another device holds the lock. The client
    has to handle those differently, so they are different codes, exactly as RFC 9110
    separates a failed precondition from a conflict in the request's own semantics.

    The refusal carries only the two numbers. It deliberately does *not* carry the fresh
    state: the client already has one path that fetches and renders state, and a second
    one here would be the duplicate this whole design exists to avoid.
    """
    if sent is None:
        return None
    now = revision()
    if sent == now:
        return None
    return JsonResponse(
        {"error": "Another device has moved the game on since this screen was drawn.",
         "stale": True, "your_revision": sent, "revision": now},
        status=412)


class OneGameAtATime:
    """Serialise anything that touches the campaign, and count when it changes.

    A middleware rather than a decorator on forty view functions, so there is exactly one
    line that can be forgotten and it is not in a file anybody edits to add a feature.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT):
            return self.get_response(request)
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return self._read(request)
        return self._write(request)

    def _read(self, request):
        try:
            with held(READ_WAIT):
                response = self.get_response(request)
        except Busy:
            return self._busy()
        return self._stamp(response)

    def _write(self, request):
        sent = _sent_revision(request)
        # Checked twice on purpose. Once here, so a client that is *already* behind is
        # told now rather than after waiting out a turn it cannot see — the whole reason
        # a double-tap across two devices is cheap to refuse. Once again under the lock,
        # because the revision can move while this request is queued and only the check
        # inside the lock is authoritative.
        early = _stale(sent)
        if early is not None:
            return early
        try:
            with held(WRITE_WAIT):
                late = _stale(sent)
                if late is not None:
                    return late
                response = self.get_response(request)
                if 200 <= response.status_code < 300:
                    bump()
        except Busy:
            return self._busy()
        return self._stamp(response)

    def _busy(self):
        return self._stamp(JsonResponse(
            {"error": "The table is resolving something else. Try that again in a "
                      "moment.", "busy": True, "revision": revision()},
            status=409))

    def _stamp(self, response):
        """Every answer says what revision it was drawn at.

        Stamped after the view has run, so a response that bumped the counter reports the
        number it produced rather than the one it started from — a client that stored the
        older number would refuse its own next write.
        """
        response[HEADER] = str(revision())
        return response
