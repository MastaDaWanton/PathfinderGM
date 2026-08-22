"""The Open Game Licence has to ship with the thing it licenses.

Section 10: "You MUST include a copy of this License with every copy of the Open Game
Content You Distribute." The app ships as one executable, so the licence has to be
reachable from inside it — a copy sitting beside the source in a repository the user never
sees does not satisfy anything.

These tests are cheap and they guard something that cannot be fixed after the fact: a build
that went out without its licence is already distributed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings


@pytest.fixture
def licence_text():
    return (Path(settings.BASE_DIR) / "OGL.txt").read_text(encoding="utf-8")


def test_the_licence_file_exists():
    assert (Path(settings.BASE_DIR) / "OGL.txt").is_file()


def test_it_is_the_whole_licence_and_not_a_summary(licence_text):
    """A paraphrased or truncated licence satisfies nothing. Checked by its own
    landmarks — the version line, the section that requires this file to exist, and the
    end marker — rather than by length, which a reflow would pass."""
    assert "OPEN GAME LICENSE Version 1.0a" in licence_text
    assert "You MUST include a copy of this License" in licence_text
    assert "15. COPYRIGHT NOTICE" in licence_text
    assert licence_text.strip().endswith("END OF LICENSE")


def test_every_numbered_section_is_present(licence_text):
    """Fifteen sections. Dropping one in an edit is the kind of thing nobody notices."""
    for n in range(1, 16):
        assert f"\n{n}. " in licence_text, f"section {n} missing"


def test_the_app_serves_it(client):
    res = client.get("/licence")
    assert res.status_code == 200
    assert res["Content-Type"].startswith("text/plain")


def test_what_is_served_is_what_is_on_disk(client, licence_text):
    """Served as plain text precisely so nothing reflows or escapes it on the way out."""
    assert res_text(client) == licence_text


def res_text(client) -> str:
    return client.get("/licence").content.decode("utf-8")


def test_a_build_that_lost_the_licence_says_so_loudly(client, tmp_path, monkeypatch):
    """Rather than serving a blank page, which reads as a styling bug. A build missing
    its licence must not be distributed, so the failure has to be legible.

    Patched at `resource_root` rather than at `settings.BASE_DIR`, because that is what
    the view actually reads — anchoring this on `__file__` or on BASE_DIR would point
    inside the PyInstaller bundle and say nothing about the installed app."""
    import pathfindergm.paths as paths

    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    res = client.get("/licence")
    assert res.status_code == 404
    assert b"OGL-NOTICE" in res.content


def test_the_notice_lists_every_content_file_that_ships():
    """`OGL-NOTICE.md` is the human half — which files carry Open Game Content and which
    are the app's own. A content file missing from it is an attribution the build owes."""
    notice = (Path(settings.BASE_DIR) / "OGL-NOTICE.md").read_text(encoding="utf-8")
    for shipped in ("content/spells/spells.json", "content/bestiary/creatures.json",
                    "content/bestiary/core.json", "content/feats/feats.json",
                    "content/ingredients/herbs-and-parts.json"):
        assert shipped in notice, f"{shipped} is not declared in OGL-NOTICE.md"


def test_the_notice_still_flags_section_fifteen_as_outstanding():
    """Section 15 needs the exact copyright notice of every source the content came from,
    and the imports span hundreds of books. Until that is done this build is not
    distributable, and the file has to keep saying so."""
    notice = (Path(settings.BASE_DIR) / "OGL-NOTICE.md").read_text(encoding="utf-8")
    assert "outstanding" in notice.lower()
    assert "tools/ogl_sources.py" in notice
