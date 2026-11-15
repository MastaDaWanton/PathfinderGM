"""A Content Security Policy on every page: the second wall behind `esc()`.

The pages draw model narration, world files and the player's own homebrew, and on a LAN
game one player's typing is drawn on another player's screen. Every value going into
markup is escaped (`tools/html_sinks.py` holds the front end to that), but one missed
escape would otherwise be script running as the app, with every `/api/` endpoint behind
it. Under this policy an injected `<img onerror=...>` or `<script>` does not run: script
comes only from this origin's files or from an inline block carrying the request's nonce.

Only `script-src` and the directives that guard it are set. Styles, images, fonts, audio
and fetches stay as they were: the pages use inline `style=` everywhere and the board
draws `data:` images, and locking those down buys little against script injection while
risking a page that silently stops drawing. (Review 2026-11-11, finding 16; OWASP CSP
Cheat Sheet, "nonce-based strict policy"; MDN `script-src`: a nonce disables
'unsafe-inline', so inline event-handler attributes are refused.)

The nonce rides on the request (`request.csp_nonce`), which the templates read through the
`request` context processor: `<script nonce="{{ request.csp_nonce }}">`.
"""
from __future__ import annotations

import secrets

POLICY = ("script-src 'self' 'nonce-{nonce}'; object-src 'none'; base-uri 'self'; "
          "frame-ancestors 'self'; form-action 'self'")


class ContentSecurityPolicy:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if response.get("Content-Type", "").startswith("text/html") \
                and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = POLICY.format(nonce=request.csp_nonce)
        return response
