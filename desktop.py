"""The thing the .exe actually runs.

The standing constraint is "the user installs one file, no terminal, no Python". That
means the executable has to *be* the server and the launcher at once: bind a socket, put
Django behind it, open the browser at it, and stay alive until the window is closed.

Choices worth writing down, because each of them was the alternative to something worse:

  **Not `runserver`.** The management command brings the autoreloader, which under
  PyInstaller re-executes `sys.executable` with `-m django` arguments the frozen exe has
  no idea what to do with — the classic frozen-Django failure is a fork bomb of app
  windows. `ThreadedWSGIServer` is the same server `runserver` wraps, minus the reloader
  and minus the command layer, and it is already inside Django so it costs no dependency.

  **Port 0 when the preferred port is busy.** A desktop app that refuses to start because
  something else owns 8917 is a support ticket. Bind the preferred port if it is free,
  otherwise let the OS choose, and tell the browser whichever one we got. Two copies of
  the app can therefore run at once, which is also what makes the packaging checks able to
  drive a build while a dev server is up.

  **The game ends when its last window does, not when its console does.** Closing the
  console has always been the documented stop and still works, but the window a player
  closes is the browser's, and a WSGI server is never told its last client left. Measured
  2026-09-01: the exe was double-clicked at 10:35, the browser closed at 12:01, and it was
  still holding port 8917 and a handle on its own `.exe` four hours later — which broke
  the next build with `WinError 5`. Every page now sends a heartbeat and
  `_reap_when_the_last_window_closes` shuts the server down when they stop.
  `pathfindergm/liveness.py` carries the measurement and the designs that were refused.

  **Browser opened after the socket is listening, not before.** `webbrowser.open` returns
  immediately and the browser races the server; opening after `bind()` means the first
  request cannot arrive at a closed port. It is opened from the main thread and the server
  runs there too, so the open happens between bind and serve_forever.

The console window is deliberate for now: a first packaged build that dies silently is
undebuggable, and the request logs plus any traceback are the only thing a user could send
back. `console=False` in the spec is a later decision, and it needs a log file first.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# The port is arbitrary but fixed, so a bookmark keeps working between launches. High
# enough to be outside anything registered, and not one of the common dev-server ports
# (8000, 8080, 5000) precisely because the developer's own runserver may hold those.
PREFERRED_PORT = 8917
HOST = "127.0.0.1"


def _bind(host: str, port: int):
    """A listening socket on `port` if it is free, otherwise on whatever the OS gives.

    Returned as a bound-but-not-serving socket so the caller knows the real port before
    anything is told where to look.
    """
    from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler

    for candidate in (port, 0):
        try:
            # `allow_reuse_address=False` is the load-bearing argument, and Django
            # defaults it to True. On Windows SO_REUSEADDR does not mean "reuse a socket
            # in TIME_WAIT" as it does on Unix — it means "bind even though somebody else
            # already has this port", and the two servers then split incoming connections
            # between them at random. With the default left alone, launching the app
            # twice produced two processes both claiming 8917, the fallback to port 0
            # never ran, and which copy a request reached was a coin toss. Turning it off
            # makes the second bind raise, which is what makes the fallback work at all.
            server = ThreadedWSGIServer((host, candidate), WSGIRequestHandler,
                                        ipv6=False, allow_reuse_address=False)
        except OSError:
            continue
        return server
    raise SystemExit(f"could not bind {host} on any port")


class _Tee(io.TextIOBase):
    """Everything the console sees, the log file sees too.

    A wrapper rather than a redirect, because the console window is still the only
    quit affordance the unwrapped build has and blanking it would strand the user.
    Both streams go through this — Django's request lines arrive on stderr, the banner
    on stdout, and a diagnosis that only holds half the story has misled once already
    (the first packaged run logged requests and no banner). Write failures are
    swallowed: a full disk must degrade to "no log", never to "no game".
    """

    def __init__(self, console, logfile):
        self._console = console
        self._log = logfile

    def write(self, s: str) -> int:
        n = self._console.write(s)
        try:
            self._log.write(s)
            self._log.flush()
        except OSError:
            pass
        return n

    def flush(self) -> None:
        self._console.flush()
        try:
            self._log.flush()
        except OSError:
            pass


def _start_log(data_root: Path):
    """The log file the Electron shell needs to exist before it can hide the console.

    Under the user data directory, appended across launches with a dated header —
    the run *before* the crash is usually the one a bug report needs — and truncated
    at 2 MB on launch rather than rotated, because a desktop game's log is a
    diagnostic, not an archive. This is runtime output like a save, not a derived
    cache: nothing ever reads it back, so it cannot go stale and does not carry
    `paths.CACHE_VERSION`.

    Returns the open file, or None with the app running fine without it.
    """
    try:
        logdir = data_root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        path = logdir / "pathfindergm.log"
        if path.exists() and path.stat().st_size > 2_000_000:
            path.unlink()
        log = open(path, "a", encoding="utf-8", errors="replace")
        log.write(f"\n=== launch {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
        log.flush()
    except OSError:
        return None
    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)
    return log


def _write_portfile(data_root: Path, port: int, url: str) -> Path | None:
    """Where the server actually is, machine-readable, for whatever launched us.

    The Electron shell cannot assume 8917 — the fallback to a free port is real and
    verified — and parsing a human banner is how the browser-thread ValueError
    happened. Written atomically (tmp then replace) so a reader never sees half a
    JSON document, and carrying the pid so a shell that finds a stale file from a
    dead run can tell it is stale. The caller deletes it on clean shutdown; the pid
    check is for the unclean ones.

    Frozen, this pid is NOT the process the launcher spawned: a onefile exe is a
    bootloader whose child runs the app, and `os.getpid()` here is the child — the
    process actually holding the port, which is the one a liveness check or an axe
    should be aimed at. The build prover measured the difference the first time it
    looked (launched 2064, portfile 22556).
    """
    try:
        path = data_root / "server.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "port": port, "url": url, "pid": os.getpid(), "host": HOST,
        }), encoding="utf-8")
        os.replace(tmp, path)
        return path
    except OSError:
        # A shell that cannot find the portfile falls back to scraping the banner or
        # trying the preferred port; the game itself owes it nothing.
        return None


def _reap_when_the_last_window_closes(server) -> None:
    """Stop serving once no page has checked in for the grace period.

    The defect, measured 2026-09-01: the exe was double-clicked at 10:35:08, the browser
    was closed at 12:01:35 (`Broken pipe from ('127.0.0.1', 49967)` in the log), and the
    server was still up four hours later — two processes, 27840 and 30176, holding
    127.0.0.1:8917 and an exclusive handle on `dist\\PathfinderGM.exe`. The port made
    `test_the_launcher_falls_back_to_a_free_port` fail; the handle made the rebuild fail
    with `PermissionError: [WinError 5] Access is denied`. Neither symptom named the
    cause, which was simply that closing a browser window tells the server nothing.

    The console window has always been the documented way to stop the bare exe, and it
    stays. This is for the far more likely thing a player does — close the game and walk
    away — and it is a backstop under the Electron shell too, whose stdin handshake is a
    better signal but only exists when the shell is the launcher. The bad run was the
    bare exe: the log line reads `installed H:\\coding\\PathfinderGM\\dist`.

    Polls rather than waits on a condition because the arming is one-way and the grace is
    minutes: a five-second tick costs nothing and cannot deadlock with the request
    threads that call `liveness.touch()`. Daemon, so it can never be the thing holding
    the exit open — which is the failure mode this whole function is about.

    `server.shutdown()` is the same graceful stop `--watch-stdin` uses: the request in
    flight finishes, `serve_forever` returns, and `main`'s `finally` removes the
    portfile, so an abandoned game still exits *cleanly* and leaves no stale handshake.
    """
    from pathfindergm import liveness

    while True:
        time.sleep(5)
        if liveness.the_last_window_is_gone():
            # Said out loud, because a game that stops on its own must not look like a
            # crash to the next person reading the log.
            print(f"No window has checked in for {liveness.grace_seconds():.0f}s — "
                  f"closing the game.", flush=True)
            server.shutdown()
            return


def _open_browser_when_up(url: str, port: int) -> None:
    """Poll the port, then open. Belt and braces over "bind happened before serve".

    The socket is already listening by the time this thread starts, so the poll normally
    succeeds first try; it exists because a browser opened at a URL that answers
    connection-refused shows an error page the user then has to reload by hand, and the
    cost of being wrong once is worse than a 50ms wait.

    The port is passed in rather than parsed back out of the URL. The first version did
    `int(url.rsplit(":", 1)[1])` and got `"8917/"` — the trailing slash — so this thread
    died with a ValueError on every launch and no browser ever opened. Nothing else
    noticed: the server came up fine and answered every request, so all the API checks
    passed against a build whose one user-facing job (open without being told to) was
    broken. It took running the packaged exe *with* the browser path enabled to see it,
    which is CLAUDE.md's "prove it against the packaged build" rule collecting again.
    """
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), 0.25):
                break
        except OSError:
            time.sleep(0.05)
    # Report the outcome. `webbrowser.open` returns False when it cannot find a browser
    # to hand the URL to, and a silent False is how "the app does nothing when I run it"
    # becomes an unanswerable bug report.
    if not webbrowser.open(url):
        print(f"Could not open a browser. Go to {url} yourself.", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

    # `--check` exists for the packaging proof. CLAUDE.md's rule is that a packaging fix
    # is only real once it has been run against the built exe, and the things worth
    # checking (can the bundle see its content directories? do the string-imported
    # loaders resolve?) are answers the exe has to give about *itself*. A flag is the
    # only way to ask it without a browser in the loop.
    if "--check" in argv:
        return _self_check()

    from pathfindergm.paths import install_root, resource_root, user_data_root

    # The tee must exist before django.setup(): logging.StreamHandler captures
    # sys.stderr at configuration time, so a tee installed after setup leaves the
    # log with launch banners and nothing else. Measured on a live 500: the user
    # saw "Server Error (500)" and the log held not one request line and no
    # traceback — the only debuggable artefact of a frozen app was blind.
    _start_log(user_data_root())

    import django
    from django.core.wsgi import get_wsgi_application

    django.setup()
    application = get_wsgi_application()

    server = _bind(HOST, PREFERRED_PORT)
    server.set_app(application)
    port = server.server_address[1]
    url = f"http://{HOST}:{port}/"

    # The portfile after the log, so nothing that launched us reads an address the
    # log has not yet vouched for.
    portfile = _write_portfile(user_data_root(), port, url)

    # The line the Electron shell waits for — same contract as World Bible's, whose
    # shell this app's is ported from. Printed after bind so the URL is real, before
    # serve_forever so the shell is never waiting on a server that is already up.
    print(f"PATHFINDERGM_READY {url}", flush=True)

    if "--watch-stdin" in argv:
        # Stdin closing is how the shell says stop — the graceful half of shutdown.
        # The taskkill fallback exists for shells that die without closing it, but a
        # clean quit should not need the axe: `server.shutdown()` lets the request in
        # flight finish, and the `finally` below removes the portfile, which is what
        # marks the exit as clean. Daemon, so a broken stdin cannot hold the exit.
        def _watch():
            try:
                sys.stdin.read()
            except Exception:
                pass
            server.shutdown()
        threading.Thread(target=_watch, daemon=True).start()

    # Always, shell or no shell. Inert until a page checks in, so nothing that drives the
    # exe without a browser — `tools/prove_build.py`, `--check`, a curl — can be reaped
    # out from under itself.
    threading.Thread(target=_reap_when_the_last_window_closes, args=(server,),
                     daemon=True).start()

    # `flush=True` on every line, and it is not decoration. Frozen, stdout is a pipe
    # rather than a console whenever anything captures it, so Python block-buffers it and
    # nothing appears until 8 KB have accumulated — which for six lines is never. The
    # first packaged run logged Django's requests (they go to stderr, which is unbuffered)
    # and not one line of this banner, so the window that is supposed to tell the user
    # where their saves live told them nothing at all.
    say = lambda line: print(line, flush=True)                       # noqa: E731
    say("Pathfinder GM")
    say(f"  content   {resource_root()}")
    say(f"  installed {install_root()}")
    say(f"  your data {user_data_root()}")
    say(f"  serving   {url}")
    say("Close this window to stop the game — or just close the game's window; it "
        "shuts down a few minutes later.")

    if "--no-browser" not in argv:
        threading.Thread(target=_open_browser_when_up, args=(url, port),
                         daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        # Best-effort: a portfile left by a crash still carries our (now dead) pid,
        # which is what lets a shell distinguish stale from current.
        if portfile is not None:
            try:
                portfile.unlink()
            except OSError:
                pass
    return 0


def _self_check() -> int:
    """Report what the *running* build can actually see, and fail loudly if it cannot.

    Every line here is one of the things that silently breaks when frozen: a content
    directory that was never added to the spec reads as an empty folder rather than an
    error, and a loader named by string is simply absent from the bundle. Both produce an
    app that starts, serves a page and has nothing in it — which is why this prints counts
    rather than "ok".
    """
    import django

    django.setup()

    from django.conf import settings

    from pathfindergm.paths import install_root, is_frozen, resource_root, user_data_root
    from rules import benches, registry

    problems: list[str] = []

    print(f"frozen        {is_frozen()}")
    print(f"resource_root {resource_root()}")
    print(f"install_root  {install_root()}")
    print(f"user_data     {user_data_root()}")
    print(f"campaign_dir  {settings.CAMPAIGN_DIR}")

    content = resource_root() / "content"
    if not content.is_dir():
        problems.append(f"content/ missing at {content}")
    else:
        for sub in sorted(p for p in content.iterdir() if p.is_dir()):
            files = list(sub.glob("*.json"))
            print(f"content/{sub.name:<14} {len(files)} file(s)")
            if not files:
                problems.append(f"content/{sub.name} is empty in the bundle")

    for name in ("pangrella-campaign.json", "pc-kesst.json"):
        p = resource_root() / "fixtures" / name
        print(f"fixtures/{name:<26} {'ok' if p.is_file() else 'MISSING'}")
        if not p.is_file():
            problems.append(f"fixtures/{name} missing")

    for name in ("OGL.txt", "OGL-NOTICE.md"):
        p = resource_root() / name
        print(f"{name:<35} {'ok' if p.is_file() else 'MISSING'}")
        if not p.is_file():
            problems.append(f"{name} missing — must not be distributed without it")

    # The string-imported halves of the app. PyInstaller's static analysis cannot see
    # `import_module("rules.spells")`, so these are exactly the modules that go missing.
    for kind_id, kind in registry.KINDS.items():
        for target in (kind.shipped_loader, kind.derive):
            if not target:
                continue
            module_name, _, func = target.partition(":")
            try:
                __import__(module_name)
            except Exception as exc:
                problems.append(f"registry {kind_id}: {target} -> {exc!r}")
    for track, module_name in benches.BENCHES.items():
        try:
            __import__(module_name)
        except Exception as exc:
            problems.append(f"bench {track}: {module_name} -> {exc!r}")
    for mode, (_owner, module_name) in benches.MODES.items():
        try:
            __import__(module_name)
        except Exception as exc:
            problems.append(f"mode {mode}: {module_name} -> {exc!r}")

    from rules import spells

    try:
        n_spells = len(spells.all_spells())
    except Exception as exc:
        n_spells = -1
        problems.append(f"spells did not load: {exc!r}")
    print(f"spells loaded {n_spells}")

    from django.contrib.staticfiles import finders

    for asset in ("js/dice3d.js", "img/leather-tile.jpg"):
        found = finders.find(asset)
        print(f"static {asset:<22} {'ok' if found else 'MISSING'}")
        if not found:
            problems.append(f"static {asset} not findable")

    from django.template.loader import get_template

    for tpl in ("play/home.html", "play/table.html", "play/craft.html",
                "play/classbuilder.html"):
        try:
            get_template(tpl)
            print(f"template {tpl:<24} ok")
        except Exception as exc:
            problems.append(f"template {tpl}: {exc!r}")

    if problems:
        print("\nFAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
