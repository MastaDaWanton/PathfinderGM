"""Whether a window is still open on this game, and nothing else.

**The measurement, 2026-09-01.** `dist\\PathfinderGM.exe` was double-clicked at
10:35:08 and played until 12:01:35, when the log records `Broken pipe from
('127.0.0.1', 49967)` — the browser going away. It was still serving at 16:20. Two
processes were alive, 27840 and 30176, started nine seconds apart; they held
`127.0.0.1:8917` and an exclusive handle on the `.exe` they were running from. That
handle is what made `python -m PyInstaller pathfindergm.spec --noconfirm` fail with
`PermissionError: [WinError 5] Access is denied`, and the held port is what made
`tests/test_packaging.py::test_the_launcher_falls_back_to_a_free_port` fail. Both
symptoms landed two tools away from the cause and neither named it.

The nine-second gap looked like the "bound 8917 twice" bug that test documents, and it
is not. Reproduced 2026-09-01 against the same exe: parent 31548 spawns child 30748
nineteen seconds later, same command line, and the portfile carries the *child's* pid.
That is a one-file PyInstaller build — a bootloader that unpacks 38 MB and then runs the
app as a child. Two processes is what one running copy looks like.

**Why nothing caught it.** The exe's only stop affordance is closing the console window
behind the browser; the window a player closes is the browser's. A WSGI server is never
told its last client has gone. It is only ever told that no request has arrived — which
is equally true of a player who is reading. The Electron shell has an answer for this
(stdin closes, the backend shuts down) and the shell was not in the picture: the log
line for that launch reads `installed H:\\coding\\PathfinderGM\\dist`, the bare exe.

**Prior art, and what was refused.** Jupyter shipped exactly this as
`NotebookApp.shutdown_no_activity_timeout`, and its bug tracker carries the lesson worth
copying: with a UI open the timeout never fires, because the page polls — and people file
that as a bug when it is the feature. Activity has to mean *a page exists*, not *a request
happened*. So the page volunteers a heartbeat and this module is the ear.

Refused, with reasons:

  - **An exit beacon on `pagehide`/`beforeunload`.** It would make shutdown instant
    instead of costing a grace period, and it is the wrong trade twice over. Those events
    are documented as unreliable, MDN steers to `visibilitychange` instead — and
    `visibilitychange` fires when the player merely alt-tabs away, so a beacon on it
    would end the session of somebody who looked at something else. A positive heartbeat
    cannot make that mistake: silence is the only thing that ends a game, and a
    backgrounded window is not silent.

  - **A short grace.** Chrome throttles timers in a hidden tab to **once per minute**
    after five minutes, so any grace under 60 seconds kills live games belonging to
    players who minimised the window. 180 seconds tolerates two missed minutes and still
    frees the port and the exe handle long before a rebuild.

  - **Reaping on a timer from the start.** Jupyter's `--no-browser` shuts down after the
    timeout with no page ever attached, which would make `tools/prove_build.py` — which
    drives the packaged exe over HTTP and never runs a line of JavaScript — a race
    against its own subject. The reaper here is *armed by the first heartbeat*: an exe
    nobody has opened a window on runs forever, exactly as it does today.
"""
from __future__ import annotations

import logging
import os
import threading
import time

# How often a page checks in. Fast enough that the grace below, not this, is what decides
# how long an abandoned game lingers; slow enough that a throttled background tab still
# beats several times inside one grace. `QuietHeartbeat` keeps it out of the request log.
PING_SECONDS = 15


def grace_seconds() -> float:
    """How long silence has to last before the game is over.

    Read per call rather than captured at import so it can be turned down for a proof:
    `tools/prove_build.py` has to watch the packaged exe actually exit, and a check that
    takes three minutes of wall clock is a check that gets commented out. Same shape and
    same justification as `PATHFINDER_GM_DATA` — the override exists because a packaging
    fix that has not been run against the built artifact is not a fact.
    """
    try:
        return max(1.0, float(os.environ.get("PATHFINDER_GM_IDLE_GRACE", "") or 180))
    except ValueError:
        return 180.0


_lock = threading.Lock()
_last_seen: float | None = None


def touch() -> None:
    """A window said it is still there. Also what arms the reaper the first time."""
    global _last_seen
    with _lock:
        _last_seen = time.monotonic()


def armed() -> bool:
    """True once any page has ever checked in.

    Before that the app is being driven by something that is not a browser — the prover,
    `--check`, a curl — and none of those owe us a heartbeat.
    """
    with _lock:
        return _last_seen is not None


def idle_seconds() -> float:
    """Silence since the last window spoke; 0.0 while nothing has ever spoken."""
    with _lock:
        if _last_seen is None:
            return 0.0
        return time.monotonic() - _last_seen


def the_last_window_is_gone() -> bool:
    return armed() and idle_seconds() > grace_seconds()


class QuietHeartbeat(logging.Filter):
    """Keep `GET /api/alive` out of the request log.

    Four beats a minute is 5,760 lines a day at about 90 bytes each — half a megabyte
    against a log `desktop.py` truncates at 2 MB. Left in, the heartbeat would push the
    thing a bug report actually needs off the end of the file inside a week, which is the
    same failure as having no log: "a diagnosis that only holds half the story has misled
    once already" is already written on the tee this would be filling.

    Matched on the record's own arguments rather than the formatted line, because
    `django.server` formats with colour codes when it can and a substring search against
    a coloured string is the kind of thing that quietly stops matching.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = getattr(record, "args", None)
        if isinstance(args, tuple) and args:
            return "/api/alive" not in str(args[0])
        return True
