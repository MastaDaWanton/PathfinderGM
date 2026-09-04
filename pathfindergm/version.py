"""The build the player is actually running, printed where they can see it.

Asked for in as many words: "add a version tracker to the main page and i dont
have to wonder" — after a session of findings filed against a build that had
already been superseded.

Two sources, and which one is asked is decided by whether the app is frozen:

  **Packaged: a file the spec wrote.** `pathfindergm.spec` asks git once, at build
  time, and ships the answer as `build-stamp.txt` beside the content. The app reads
  a file; it never runs anything. The first version of this module shelled out to
  git at request time whenever the stamp was missing — and it was always missing,
  because the stamper it relied on (`tools/stamp_version.py`, since deleted) was
  never wired into the build. Every home-page load of every packaged build ran
  `git log` from inside the exe. Under the Electron shell launched from Explorer
  (no console, piped stdio, the registry PATH with Git's cmd wrapper first) that
  git hung, the 5-second timeout killed the wrapper and left the real git
  holding the pipes, and `communicate()` then waited on those pipes forever —
  CPython's documented Windows behaviour (bpo-38207, bpo-31935). Three home
  requests were found parked on that join; the shell's window is `show: false`
  until first paint, so the user double-clicked twice and saw nothing at all.

  **Working copy: git, off the request thread.** Dev shows the live commit so a
  finding is never filed against a stale one, but the answer is fetched once, on
  a daemon thread started at import, with stdin closed. `build()` returns what is
  known and never waits — a page must not be held hostage by a version string.
"""
from __future__ import annotations

import subprocess
import threading

from . import paths

STAMP_FILE = "build-stamp.txt"
UNSTAMPED = "unstamped"

_GIT = ["git", "log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d %H:%M"]

_dev_stamp: str | None = None
_dev_thread: threading.Thread | None = None


def _ask_git() -> None:
    global _dev_stamp
    try:
        out = subprocess.run(_GIT, capture_output=True, text=True, timeout=10,
                             stdin=subprocess.DEVNULL, cwd=paths.install_root())
        if out.returncode == 0 and out.stdout.strip():
            _dev_stamp = out.stdout.strip() + " (dev)"
            return
    except Exception:
        pass
    _dev_stamp = UNSTAMPED


def _start_dev_lookup() -> threading.Thread:
    global _dev_thread
    if _dev_thread is None:
        _dev_thread = threading.Thread(target=_ask_git, name="build-stamp", daemon=True)
        _dev_thread.start()
    return _dev_thread


def build(wait: float = 0.0) -> str:
    """The stamp, or `unstamped` when it is not known (yet).

    `wait` is how long a caller may block for the dev lookup — the home view passes
    nothing, a test that wants the real answer passes seconds. Frozen, the answer is a
    file read and `wait` is meaningless.
    """
    if paths.is_frozen():
        stamp = paths.resource_root() / STAMP_FILE
        try:
            text = stamp.read_text(encoding="utf-8").strip()
        except OSError:
            return UNSTAMPED
        return text or UNSTAMPED
    thread = _start_dev_lookup()
    if wait:
        thread.join(wait)
    return _dev_stamp or UNSTAMPED


if not paths.is_frozen():
    _start_dev_lookup()
