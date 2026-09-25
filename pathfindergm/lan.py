"""Letting a second device reach the table, and nothing else reach it.

The app has never needed authentication, because `desktop.py` binds `127.0.0.1` and
"only this machine can talk to it" was the entire security model. `settings.py` says so
in its own words: *"while this only ever listens on localhost, 'only localhost' is a
property of today's launcher rather than a guarantee"*. Serving on the LAN so a phone can
join is the day that stops being true, and `/api/say` becomes something anybody on the
café Wi-Fi can POST to.

**Off unless asked for.** Nothing in this module does anything until `open_the_door()` is
called, which happens when the player presses the button in Settings — or at launch with
`desktop.py --lan`, which is the same call with no window open yet. Until then the process
is listening on `127.0.0.1` and nothing else, exactly as it has since 0.1.0: no socket on
the network, no token, no cookie, not a byte different on the wire.

The button is the point. "The user installs one file. No terminal, no `pip install`, no
Python knowledge required to run it" is a standing constraint, and a feature reachable
only by a command-line flag breaks it — which is why the socket is bound on demand rather
than at launch.

The shape is Jupyter's, because Jupyter has been solving exactly this problem — a local
single-user server that sometimes has to be reachable from elsewhere — for a decade:

  **A token minted per launch, not a password.** There is no account here and nothing to
  remember. A secret that dies with the process cannot be reused, leaked from a config
  file, or left set to the default by somebody who never changed it.

  **The token is spent once and exchanged for a cookie, and the URL it arrived in is
  redirected away.** A token left sitting in the address bar is one that gets
  bookmarked, screenshotted over somebody's shoulder, and written into browser history.

  **Loopback never needs it.** The desktop's own browser is opened by the app itself and
  is on the far side of no network at all; making it authenticate would be theatre that
  the player pays for.

Ten characters from an alphabet with no `0`/`O` or `1`/`l`/`I` in it: fifty bits, which is
far past anything worth brute-forcing on a LAN. The QR code in the Settings panel is how
the pass is meant to travel — `pathfindergm/qr.py` draws it — and the short, unambiguous
alphabet is the fallback for a camera that will not focus, which is exactly when a player
has to read characters off a screen and type them.
"""
from __future__ import annotations

import hmac
import secrets
import socket
import threading

from django.http import HttpResponse
from django.shortcuts import redirect

# No 0/O, no 1/l/I. Misread once on a phone screen is a player who thinks the app is
# broken, and they have no way to tell that from a typo.
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
TOKEN_LENGTH = 10

# Signed rather than stored: there is no session backend in this app (INSTALLED_APPS has
# no `django.contrib.sessions` and MIDDLEWARE has no SessionMiddleware), and adding one
# to hold a single boolean would be a database and a migration inside a frozen exe.
COOKIE = "pathfindergm-pass"
COOKIE_SALT = "pathfindergm.lan.pass"

QUERY_KEY = "k"

_token: str | None = None


def mint() -> str:
    """A fresh pass for this launch."""
    return "".join(secrets.choice(ALPHABET) for _ in range(TOKEN_LENGTH))


def arm(token: str, port: int) -> None:
    """Turn the LAN door on, and tell Django it is allowed to answer on these names.

    Called after `bind()` rather than at import, because the port is not knowable until
    the socket exists — `desktop.py` falls back to an OS-chosen port when 8917 is busy,
    and a CSRF origin naming the wrong port refuses every POST the phone makes.
    """
    global _token
    from django.conf import settings

    _token = token
    names = ["127.0.0.1", "localhost", *addresses()]
    settings.ALLOWED_HOSTS = sorted({*settings.ALLOWED_HOSTS, *names})
    # Django only checks the Referer against this on HTTPS, but it checks a present
    # `Origin` header on any scheme, and a phone's browser sends one on every fetch the
    # table makes. Without these the phone renders the page perfectly and then 403s on
    # the first turn — the same failure `views.table` records for the missing CSRF
    # cookie, found the same way.
    settings.CSRF_TRUSTED_ORIGINS = sorted({
        *getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
        *(f"http://{name}:{port}" for name in names),
    })


def disarm() -> None:
    """Back to loopback-only. For tests; nothing in the app calls this."""
    global _token
    _token = None


# --- The door as a thing that opens and shuts --------------------------------------
#
# The socket is bound when the player asks for it, not at launch, and the main server
# stays on `127.0.0.1` either way. That is a change from the first version of this
# feature, which bound `0.0.0.0` for the whole process when `--lan` was passed, and it
# fixes a real defect rather than tidying one: a wildcard bind and a loopback bind are
# different addresses, so the OS grants both and Windows then splits loopback
# connections between whichever two servers happen to be running. With the game always
# on loopback and the network always on a separate OS-chosen port, the two cannot
# collide at all.
#
# It is also the only shape in which a *button* can work. `desktop.py` binds its socket
# before Django starts; nothing a page does could have changed that decision afterwards.

_server = None
_thread = None


def is_open() -> bool:
    return _server is not None


def open_the_door() -> dict:
    """Start listening on the network and mint the pass. Idempotent."""
    global _server, _thread

    if _server is not None:
        return status()

    from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler
    from django.core.wsgi import get_wsgi_application

    # Port 0: the OS picks. A fixed one would buy a bookmarkable address, and the pass
    # changes every launch anyway, so there is nothing to bookmark.
    server = ThreadedWSGIServer(("0.0.0.0", 0), WSGIRequestHandler,
                                ipv6=False, allow_reuse_address=False)
    server.set_app(get_wsgi_application())
    port = server.server_address[1]

    arm(mint(), port)
    _server = server
    _thread = threading.Thread(target=server.serve_forever, daemon=True,
                               name="pathfindergm-lan")
    _thread.start()
    return status()


def close_the_door() -> dict:
    """Stop listening, and make the pass worthless.

    Must not be called from a request being served *by the LAN server itself*:
    `shutdown()` waits for `serve_forever` to come back round, and a thread waiting on
    its own server's loop is a deadlock. The views that call this refuse anything that
    did not come from this machine, which rules that out — see `_from_this_machine`.
    """
    global _server, _thread

    server, _server, _thread = _server, None, None
    disarm()
    if server is not None:
        server.shutdown()
        server.server_close()
    return status()


def status() -> dict:
    """Everything a page needs to show the panel, including the code itself."""
    if not is_open():
        return {"open": False, "url": "", "pass": "", "qr": "", "addresses": []}

    from pathfindergm import qr as qr_mod

    found = addresses()
    port = _server.server_address[1]
    url = f"http://{found[0]}:{port}/?{QUERY_KEY}={token()}" if found else ""
    return {
        "open": True,
        "url": url,
        "pass": token(),
        # Every address, because a machine on both Wi-Fi and Ethernet has two and only
        # the player knows which one their phone can see.
        "addresses": [f"http://{a}:{port}/?{QUERY_KEY}={token()}" for a in found],
        "qr": qr_mod.svg(url) if url else "",
    }


def enabled() -> bool:
    return _token is not None


def token() -> str:
    return _token or ""


def addresses() -> list[str]:
    """This machine's addresses on the network, best effort.

    The UDP trick first: connecting a datagram socket sends nothing, it only asks the
    routing table which local address *would* be used to reach the outside, which is the
    one a phone on the same Wi-Fi can reach. `gethostbyname_ex` is the fallback and is
    kept rather than used first because on a machine with Docker, WSL or a VPN it
    cheerfully returns virtual adapters the phone cannot see, ahead of the one it can.
    """
    found: list[str] = []
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        found.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    try:
        found.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return [a for i, a in enumerate(found)
            if a and not a.startswith("127.") and a not in found[:i]]


def _from_this_machine(request) -> bool:
    # Trustworthy because there is no proxy in front of this server — it is the socket
    # `desktop.py` bound, talking to the browser directly. Behind a reverse proxy
    # REMOTE_ADDR would be the proxy and this check would let the world in, which is
    # worth a sentence here in case anybody ever puts one there.
    return request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1")


def _carries_the_pass(request) -> bool:
    try:
        return request.get_signed_cookie(COOKIE, salt=COOKIE_SALT, default=None) == "yes"
    except Exception:
        # A tampered or truncated cookie reads as no cookie. There is nothing to report
        # and nobody to report it to.
        return False


class TheDoor:
    """Everything from off this machine presents a pass, or gets a page saying how."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not enabled() or _from_this_machine(request) or _carries_the_pass(request):
            return self.get_response(request)

        given = str(request.GET.get(QUERY_KEY, "")).strip().upper()
        if given and hmac.compare_digest(given, token()):
            # Redirect to the same path *without* the token, so the address bar, the
            # history and any screenshot of this phone stop carrying the secret. Query
            # string dropped deliberately and not preserved: the table used to read
            # `?new=1` from it (a reset, removed 2026-09-25), and a query that changes
            # the game must never be replayed by a redirect.
            response = redirect(request.path)
            response.set_signed_cookie(
                COOKIE, "yes", salt=COOKIE_SALT,
                httponly=True, samesite="Lax",
                # No `secure`: this is plain HTTP on a LAN by necessity — a phone cannot
                # be given a trusted certificate for 192.168.x.x. Marking it secure would
                # mean the browser never sends it and the door never opens.
                secure=False,
            )
            return response

        return HttpResponse(
            "<!doctype html><meta name='viewport' "
            "content='width=device-width, initial-scale=1'>"
            "<style>body{font:16px/1.5 system-ui;margin:12vh auto;max-width:30ch;"
            "padding:0 6vw;color:#e8dcc0;background:#151109}"
            "code{font-size:22px;letter-spacing:.12em;color:#d9b166}</style>"
            "<h1>Pathfinder GM</h1><p>This table is being played on another machine. "
            "Add the pass it is showing to the address:</p>"
            f"<p><code>?{QUERY_KEY}=YOURPASS</code></p>",
            status=403, content_type="text/html; charset=utf-8")
