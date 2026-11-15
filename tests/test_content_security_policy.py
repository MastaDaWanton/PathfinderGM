"""Every page refuses script it did not write, and still runs the script it did.

Review 2026-11-11, finding 16: no page sent a Content Security Policy, so one missed
`esc()` anywhere in ~400 markup sinks (tools/html_sinks.py) would have been script running
as the app. With `script-src 'self' 'nonce-…'` an injected `<img onerror>` does not run,
and the inline blocks the pages are built from carry the request's nonce so they still do.
The failure this guards against in the other direction is silent: an inline block
without the nonce is refused by the browser and the page simply never draws.
"""
from __future__ import annotations

import re

from django.test import Client

PAGES = ("/", "/play/", "/outfit/", "/craft/", "/manual", "/homebrew/classes/",
         "/homebrew/spells/", "/homebrew/races/")


def _nonce(policy: str) -> str:
    m = re.search(r"script-src 'self' 'nonce-([A-Za-z0-9_-]+)'", policy)
    assert m, policy
    return m.group(1)


def test_every_page_sends_a_nonced_script_policy():
    c = Client()
    for url in PAGES:
        r = c.get(url)
        if r.status_code in (301, 302):
            continue
        policy = r.headers.get("Content-Security-Policy", "")
        assert "object-src 'none'" in policy and "base-uri 'self'" in policy, url
        assert "'unsafe-inline'" not in policy.split("script-src", 1)[1].split(";")[0], url
        _nonce(policy)


def test_every_inline_script_carries_this_requests_nonce():
    """14 inline blocks across the templates when the policy went in (6 on the table)."""
    c = Client()
    seen = 0
    for url in PAGES:
        r = c.get(url)
        if r.status_code != 200:
            continue
        nonce = _nonce(r.headers["Content-Security-Policy"])
        html = r.content.decode("utf-8", "replace")
        for tag in re.findall(r"<script\b[^>]*>", html):
            if "src=" in tag or 'type="application/json"' in tag:
                continue
            seen += 1
            assert f'nonce="{nonce}"' in tag, (url, tag)
    assert seen >= 8, seen


def test_each_request_gets_its_own_nonce():
    c = Client()
    a = _nonce(c.get("/").headers["Content-Security-Policy"])
    b = _nonce(c.get("/").headers["Content-Security-Policy"])
    assert a != b


def test_a_json_answer_is_left_alone():
    r = Client().get("/api/setup")
    assert "Content-Security-Policy" not in r.headers
