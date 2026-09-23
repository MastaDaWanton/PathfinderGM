"""A race document is parsed when its file changes, not on every question.

Measured 2026-09-23 with a profiler under `Actor.has_state`: 5 ms and 29 JSON files per
call, because `standing_tags` -> `_race_doc` -> `races.document` -> `all_races` ->
`shipped` re-read `content/races` and `homebrew/races` and re-normalised every entry
every time. `has_state` sits under every modifier funnel in the game. Two thousand calls
— a fight's worth — took 7.3 seconds.

`shipped` refused a cache on purpose, citing the stale-cache trap CLAUDE.md records.
That trap is a derived cache in the user's data directory answering "fresh" from a
timestamp across reinstalls. This cache is in the process, keyed on every file's name,
size and modification time, and re-checked; an edit on the bench is seen on the next
read. These tests pin both halves: read once, and read again when the file moves.
"""
from __future__ import annotations

import json
import os
import time

import pytest
from django.conf import settings

from rules import races


@pytest.fixture
def homebrew(tmp_path, monkeypatch):
    """A homebrew folder of our own, and a signature that is never trusted for long."""
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(races, "_SIGNATURE_TTL", 0.0)
    races._CACHE.clear()
    races._SIGNATURES.clear()
    folder = races.homebrew_dir(make=True)
    yield folder
    races._CACHE.clear()
    races._SIGNATURES.clear()


def _write(folder, name, doc):
    path = folder / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    # A second write inside the same clock tick has the same mtime; push it forward so
    # the test is about the signature and not about the clock's resolution.
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


class TestReadOnce:
    def test_the_folders_are_parsed_once_across_many_questions(self, homebrew, monkeypatch):
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 30})
        reads = []
        real = races._read_folder

        def counting(folder):
            reads.append(str(folder))
            return real(folder)

        monkeypatch.setattr(races, "_read_folder", counting)
        for _ in range(50):
            assert races.document("testfolk") is not None
        assert len(reads) == 2, reads          # content/races once, homebrew once

    def test_a_caller_gets_a_copy_and_not_the_registry(self, homebrew):
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 30})
        one = races.get("testfolk")
        one["name"] = "Vandalised"
        assert races.get("testfolk")["name"] == "Testfolk"
        doc = races.document("testfolk")
        doc["traits"].append("not really")
        assert "not really" not in races.document("testfolk")["traits"]


class TestReadAgainWhenTheFileMoves:
    def test_an_edit_on_the_bench_is_seen_on_the_next_read(self, homebrew):
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 30})
        assert races.document("testfolk")["speed"] == 30
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 40})
        assert races.document("testfolk")["speed"] == 40

    def test_a_race_added_is_seen_and_one_removed_is_gone(self, homebrew):
        assert races.get("testfolk") is None
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 30})
        assert races.get("testfolk") is not None
        (homebrew / "testfolk.json").unlink()
        assert races.get("testfolk") is None

    def test_the_bench_folder_is_never_trusted_on_a_timer(self, homebrew, monkeypatch):
        """The change check was 1.6 ms of stat calls on Windows, nearly all of them the
        shipped files, so the SHIPPED folder's signature is trusted for `_SIGNATURE_TTL`.
        The homebrew folder is not: the bench writes it and reads it back in the same
        breath, and the first cut put both under the timer — eight tests in
        `test_races.py` and `test_natural_attacks.py` failed on the spot."""
        monkeypatch.setattr(races, "_SIGNATURE_TTL", 10.0)
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 30})
        assert races.document("testfolk")["speed"] == 30
        _write(homebrew, "testfolk", {"id": "testfolk", "name": "Testfolk", "size": "medium",
                                   "speed": 40})
        assert races.document("testfolk")["speed"] == 40

    def test_a_race_stood_in_front_of_the_sheet_is_honoured(self, homebrew, monkeypatch):
        """`test_natural_attacks` replaces `all_races` to hand the sheet a race with a
        bite. The first cut of the cache read past `all_races`, and the bite was gone."""
        real = races.all_races()
        doc = races.normalise({"id": "testfolk", "name": "Testfolk", "size": "medium",
                               "speed": 45})
        monkeypatch.setattr(races, "all_races", lambda: {**real, "testfolk": doc})
        assert races.document("testfolk")["speed"] == 45
        assert races.get("testfolk")["speed"] == 45
