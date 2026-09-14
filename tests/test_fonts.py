"""The display face has to be in the build, and its licence has to travel with it.

The defect these were written against, measured 2026-09-09 against the packaged build on
port 8917: `/static/fonts/Cinzel-Regular.woff2` returned **404 on every page load** of the
home page, the table, the craft bench and the class builder, logged as a console error each
time. `Cinzel-SemiBold.woff2` was the same. `play/static/fonts/` held a README and nothing
else, and had done since the templates first asked for the font.

It hid for so long because of how the `@font-face` is written — `src: local("Cinzel"),
url(...)`. On a machine with Cinzel installed, `local()` wins and there is no request at
all, so the author never saw it; everywhere else the page silently wore the Palatino
fallback and looked merely a bit plainer. Headings, the dice mat and the engraved numerals
on the 3D dice all lost their intended face without anything reporting a failure.

So the first test here does not check for Cinzel by name. It checks that *every* asset any
template asks for through `{% static %}` is a file that exists, because a graceful fallback
is exactly the condition under which a missing asset stops announcing itself.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(settings.BASE_DIR)
STATIC = ROOT / "play" / "static"
FONTS = STATIC / "fonts"

STATIC_TAG = re.compile(r"\{%\s*static\s+['\"]([^'\"]+)['\"]\s*%\}")


def _referenced() -> set[str]:
    found: set[str] = set()
    for template in (ROOT / "play" / "templates").rglob("*.html"):
        found |= set(STATIC_TAG.findall(template.read_text(encoding="utf-8")))
    return found


def test_every_static_asset_a_template_asks_for_is_actually_there():
    """The general form of the 404 above. Sixteen references across the templates; the two
    font files were the two that pointed at nothing."""
    referenced = _referenced()
    assert referenced, "no {% static %} references found — the regex has gone stale"
    missing = sorted(name for name in referenced if not (STATIC / name).is_file())
    assert not missing, f"referenced by a template but not in play/static: {missing}"


def test_both_weights_the_templates_declare_are_present():
    """Named explicitly as well, because the test above would go quiet if a template
    stopped asking — and a face dropped from the CSS is a different bug from a face
    dropped from the folder, not a fix for it."""
    for weight in ("Cinzel-Regular.woff2", "Cinzel-SemiBold.woff2"):
        assert (FONTS / weight).is_file(), f"{weight} is missing from play/static/fonts"


@pytest.mark.parametrize("name", ["Cinzel-Regular.woff2", "Cinzel-SemiBold.woff2"])
def test_the_font_files_are_real_woff2(name):
    """A placeholder, an HTML error page saved under the right name, or a `.ttf` renamed
    would all satisfy `is_file()` and all fail to render. woff2 declares itself in its
    first four bytes."""
    head = (FONTS / name).read_bytes()[:4]
    assert head == b"wOF2", f"{name} starts {head!r}, which is not a woff2 signature"


@pytest.mark.parametrize("name", ["Cinzel-Regular.woff2", "Cinzel-SemiBold.woff2"])
def test_the_app_serves_them(client, name):
    """The 404 was found in a browser log, not in a test, so the request itself is what
    gets pinned — through the same staticfiles path a page load uses."""
    res = client.get(f"/static/fonts/{name}")
    assert res.status_code == 200, f"/static/fonts/{name} returned {res.status_code}"
    body = b"".join(res.streaming_content) if res.streaming else res.content
    assert body[:4] == b"wOF2"
    assert len(body) > 10_000, f"{name} served {len(body)} bytes — too small to be the font"


def test_the_open_font_licence_ships_beside_the_font():
    """The OFL's condition on redistribution, and this app redistributes: the font is
    inside the `.exe`. Same obligation as the OGL's section 10, and the same failure mode —
    a build that went out without it is already distributed."""
    licence = (FONTS / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in licence
    assert "Copyright 2020 The Cinzel Project Authors" in licence
    assert licence.strip().endswith("OTHER DEALINGS IN THE FONT SOFTWARE.")


def test_the_font_licence_is_reachable_from_inside_the_app(client):
    """The same standard the OGL is held to by `test_licence.py`: a copy sitting beside the
    source in a repository the user never sees satisfies nothing, because the user gets one
    `.exe`. `play/static` ships whole, so the OFL is served at `/static/fonts/OFL.txt` — the
    font's equivalent of `/licence`."""
    res = client.get("/static/fonts/OFL.txt")
    assert res.status_code == 200
    body = b"".join(res.streaming_content) if res.streaming else res.content
    assert b"SIL OPEN FONT LICENSE Version 1.1" in body


# The other half of the licence obligation — that the OFL notice is in each font's own
# `name` table, so a woff2 copied out of this app still carries it — is asserted in
# `tools/build_fonts.py` instead of here, and deliberately.
#
# A first draft of it lived in this file and searched the file's raw bytes for "SIL Open
# Font License". It failed, correctly: woff2 is brotli-compressed, so no string in the
# name table is visible without decompressing, and reading it needs `fonttools`.
# `requirements.txt` is two lines on purpose — every dependency is another thing
# PyInstaller has to be told about — so the check stays where fonttools is present by
# definition, and runs whenever the binaries are regenerated.


def test_the_readme_does_not_still_describe_the_font_as_absent():
    """The folder's README was install instructions for a font that was not here. Leaving
    it that way after shipping the font is the stale-copy shape CLAUDE.md names — a rule
    corrected in one place and left wrong in the one nobody looked at."""
    readme = (FONTS / "README.md").read_text(encoding="utf-8")
    assert "tools/build_fonts.py" in readme, \
        "the README should point at how these two files are regenerated"
