"""An id the request supplies never becomes a path outside its folder.

Measured 2026-09-25: `save_thing` used `body["id"]` as the filename, `registry.save`
did the same for the spell and class builders, `open_thing` took the id from the URL,
and the roster built paths from character ids — so `..\\..\\campaigns\\slice` overwrote
a campaign and `..\\..\\models` the model settings. `library.safe_name` did this
properly for world uploads and nothing else used it.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from pathfindergm import files


@pytest.mark.parametrize("bad", [
    "../x", "..\\x", "..", ".", ".hidden", "a/b", "a\\b", "C:evil", "nul", "CON",
    "com1", "x\0y", " padded", "",
])
def test_a_name_that_escapes_is_refused(tmp_path, bad):
    with pytest.raises(files.BadName):
        files.child(tmp_path, bad)


@pytest.mark.parametrize("good", ["healing-draught", "blood_bending", "kesst-2", "a.b"])
def test_an_ordinary_id_is_a_file_in_the_folder(tmp_path, good):
    assert files.child(tmp_path, good) == tmp_path / f"{good}.json"


@pytest.fixture
def data(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "data" / "campaigns")):
        (tmp_path / "data" / "campaigns").mkdir(parents=True)
        yield tmp_path / "data"


def test_the_bench_will_not_write_outside_its_folder(data):
    target = data / "models.json"
    target.write_text('{"untouched": true}', encoding="utf-8")
    r = Client().post("/api/bench/consumables/save", content_type="application/json",
                      data=json.dumps({"id": "..\\..\\models", "name": "Evil",
                                       "effects": []}))
    assert r.status_code == 400, r.content
    assert "cannot be used as a name" in r.json()["error"]
    assert json.loads(target.read_text(encoding="utf-8")) == {"untouched": True}


def test_the_bench_will_not_read_outside_its_folder(data):
    (data / "secret.json").write_text('{"secret": 1}', encoding="utf-8")
    r = Client().get("/api/bench/consumables/open/..%5C..%5Csecret")
    assert r.status_code == 400
    assert "cannot be used as a name" in r.json()["error"]


def test_the_spell_builder_will_not_write_outside_its_folder(data):
    from rules import registry

    with pytest.raises(files.BadName):
        registry.save("spells", {"id": "..\\..\\campaigns\\slice", "name": "x"})


def test_the_roster_answers_nobody_for_an_id_that_is_a_path(data):
    from play import roster

    assert roster.load("..\\..\\models") is None
