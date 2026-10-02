"""No template opens a `{#` comment it closes on a later line.

Django's `{# ... #}` comment is single-line only; one that runs onto a second line is not
a comment at all, and its text prints on the page. Measured 2026-10-02: a two-line note
above the bench stage's scripts printed itself in the footer of the play table, where the
owner would have read "{# The stage's renderer (Lane F)..." under the game.
"""
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "play" / "templates"


def test_every_hash_comment_closes_on_its_own_line():
    bad = []
    for path in TEMPLATES.rglob("*.html"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            at = line.find("{#")
            while at != -1:
                end = line.find("#}", at + 2)
                if end == -1:
                    bad.append(f"{path.name}:{n}")
                    break
                at = line.find("{#", end + 2)
    assert bad == []
