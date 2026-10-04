"""Begin the sandbox from the outfitter shows that it is working.

Asked for 2026-10-03: "add a throbber from the outfitter to the sandbox so people know its
loading up". The click posts /api/resume, which writes the opening scene — tens of
seconds on a local model — and then loads /play/. The page sat unchanged the whole time
with all three buttons still live, so it read as broken and got pressed again.
"""
from __future__ import annotations

from pathlib import Path

PAGE = Path("play/templates/play/outfit.html")


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_the_page_has_a_veil_that_says_what_is_happening():
    page = _page()
    assert 'id="loading"' in page and 'role="status"' in page
    assert "Setting the scene" in page


def test_the_begin_click_raises_the_veil_and_locks_the_buttons_before_it_waits():
    page = _page()
    go = page[page.index("async function go("):page.index("function busy(")]
    assert go.index("busy(true)") < go.index('fetch("/api/resume"'), \
        "the veil goes up after the wait it is meant to cover"
    busy = page[page.index("function busy("):]
    assert "#begin, #buy, #shelf" in busy and ".disabled = on" in busy


def test_a_failed_begin_takes_the_veil_down_so_the_error_can_be_read():
    go = _page()[_page().index("async function go("):_page().index("function busy(")]
    assert go.count("busy(false)") >= 2, "a refusal or a dead server leaves the page veiled"


def test_the_ring_respects_reduced_motion():
    assert "prefers-reduced-motion" in _page()
