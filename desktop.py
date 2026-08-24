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

  **Browser opened after the socket is listening, not before.** `webbrowser.open` returns
  immediately and the browser races the server; opening after `bind()` means the first
  request cannot arrive at a closed port. It is opened from the main thread and the server
  runs there too, so the open happens between bind and serve_forever.

The console window is deliberate for now: a first packaged build that dies silently is
undebuggable, and the request logs plus any traceback are the only thing a user could send
back. `console=False` in the spec is a later decision, and it needs a log file first.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

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

    import django
    from django.core.wsgi import get_wsgi_application

    django.setup()
    application = get_wsgi_application()

    server = _bind(HOST, PREFERRED_PORT)
    server.set_app(application)
    port = server.server_address[1]
    url = f"http://{HOST}:{port}/"

    from pathfindergm.paths import install_root, resource_root, user_data_root

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
    say("Close this window to stop the game.")

    if "--no-browser" not in argv:
        threading.Thread(target=_open_browser_when_up, args=(url, port),
                         daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
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
