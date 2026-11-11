"""The JSON a page boots from cannot close the `<script>` block it is written into.

Measured 2026-11-11 (docs: python review, finding 1):
`GET /outfit/?character=</script><script>alert(1)</script>` came back 200 with the
payload raw in the page. Seven pages wrote `{{ state_json|safe }}` over a plain
`json.dumps`, which leaves `<` alone, and the HTML parser ends a script at the first
`</script>` regardless of the JavaScript string it sits in. Reflected through a query
string on two pages; stored through a character name, a world name, a homebrew entry or
a LAN guest's line on the others — the last of which ran on the host's next load.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.test import Client

from play.apiutil import script_json

PAYLOAD = "</script><script>alert(1)</script>"
TEMPLATES = Path(__file__).resolve().parent.parent / "play" / "templates" / "play"


def _body(url, params=None) -> str:
    r = Client().get(url, params or {})
    assert r.status_code == 200, f"{url} answered {r.status_code}"
    return r.content.decode("utf-8")


def _clean(page: str) -> None:
    assert PAYLOAD not in page, "the payload reached the page raw and ends the script"
    # And it did arrive, escaped — so the test is not passing because the field was lost.
    assert "\\u003c/script\\u003e" in page


def test_the_helper_round_trips_to_the_identical_object():
    """The escape must not change what the page reads: `\\u003c` inside a JSON string is
    the same character to `JSON.parse` and to a JavaScript literal."""
    obj = {"a": PAYLOAD, "b": ["<!--", "]]>", "a & b", "\u2028\u2029", 'q"\\'],
           "<k>": {"n": 1.5, "t": True, "z": None}}
    out = script_json(obj)
    assert json.loads(out) == obj
    assert not re.search(r"[<>&\u2028\u2029]", out)


def test_outfit_page_query_string():
    _clean(_body("/outfit/", {"character": PAYLOAD}))


def test_race_builder_query_string():
    _clean(_body("/homebrew/races/", {"open": PAYLOAD}))


def test_shelf_with_a_hostile_character_name(monkeypatch):
    from play import library

    monkeypatch.setattr(library, "recent_characters", lambda *a, **k: [{"name": PAYLOAD}])
    _clean(_body("/"))


def test_class_builder_with_a_hostile_homebrew_entry(monkeypatch):
    from play import class_views

    monkeypatch.setattr(class_views, "_catalogue", lambda: {"classes": [{"name": PAYLOAD}]})
    _clean(_body("/homebrew/classes/"))


def test_spell_builder_with_a_hostile_homebrew_entry(monkeypatch):
    from play import spell_views

    monkeypatch.setattr(spell_views.spells_mod, "vocabularies", lambda: {"schools": [PAYLOAD]})
    _clean(_body("/homebrew/spells/"))


@pytest.mark.parametrize("url", ["/play/", "/craft/"])
def test_table_and_craft_with_a_hostile_character_name(url, tmp_path, settings):
    """The stored route: the name is in the save, and the table and the craft page both
    write it into their boot state."""
    from play import campaign as campaign_mod

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    campaign_mod._LIVE.clear()
    try:
        campaign_mod.current().scene.pc().name = PAYLOAD
        _clean(_body(url))
    finally:
        campaign_mod._LIVE.clear()


def test_no_template_writes_unescaped_json_any_other_way():
    """`|safe` is allowed on `state_json` only, which every view fills through
    `script_json`. A new `|safe` or `mark_safe` sink is the same defect again."""
    for path in TEMPLATES.glob("*.html"):
        for m in re.finditer(r"\{\{\s*(\w+)\s*\|\s*safe\s*\}\}", path.read_text(encoding="utf-8")):
            assert m.group(1) == "state_json", f"{path.name}: {{{{ {m.group(1)}|safe }}}}"
    views = Path(__file__).resolve().parent.parent / "play"
    for path in views.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert '"state_json": json.dumps(' not in src, f"{path.name} boots from raw json.dumps"
        assert "mark_safe" not in src, f"{path.name} uses mark_safe"
