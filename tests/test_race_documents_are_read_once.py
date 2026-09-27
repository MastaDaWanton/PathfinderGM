"""A race document is parsed when its file changes, not on every question.

Measured 2026-09-23 with a profiler under `Actor.has_state`: 5 ms and 29 JSON files per
call, because `standing_tags` -> `_race_doc` -> `races.document` -> `all_races` ->
`shipped` re-read `content/races` and `homebrew/races` and re-normalised every entry
every time. `has_state` sits under every modifier funnel in the game. Two thousand calls
— a fight's worth — took 7.3 seconds.

`shipped` refused a cache on purpose, citing the stale-cache trap CLAUDE.md records.
That trap is a derived cache in the user's data directory answering "fresh" from a
timestamp across reinstalls. This cache is in the process and re-checked; an edit on the
bench is seen on the next read. These tests pin both halves: read once, and read again
when the file moves.

Measured again 2026-09-27: the re-check itself had become the cost. The homebrew folder
was listed, stat-ed and read for a checksum on every call — 1,500 `has_state` calls took
1.32 s, 1.28 s of it `_signature` and 0.26 s a deepcopy nobody needed. The app's own
writes now announce themselves at the write door (`files.write_text`, `files.remove`),
anything else is found by a look at most every `_SIGNATURE_TTL`, and the same 1,500 calls
take 0.05 s. So a test that stands in for the bench writes through the door, as the
bench does; one that stands in for a person with a text editor writes around it.
"""
from __future__ import annotations

import copy
import json
import os
import time

import pytest
from django.conf import settings

from pathfindergm import files
from rules import races
from rules.sheet import load_pc

_DEFAULT_TTL = races._SIGNATURE_TTL
TESTFOLK = {"id": "testfolk", "name": "Testfolk", "size": "medium", "speed": 30}


@pytest.fixture
def homebrew(tmp_path, monkeypatch):
    """A homebrew folder of our own, and a look that is never trusted for long."""
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(races, "_SIGNATURE_TTL", 0.0)
    races._CACHE.clear()
    races._SIGNATURES.clear()
    folder = races.homebrew_dir(make=True)
    yield folder
    races._CACHE.clear()
    races._SIGNATURES.clear()


def _by_hand(folder, name, doc, *, mtime_ns=None):
    """A write from OUTSIDE the app — Notepad, Explorer — which no door announces."""
    path = folder / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    if mtime_ns is not None:
        os.utime(path, ns=(mtime_ns, mtime_ns))
    return path


def _by_the_bench(folder, name, doc):
    """A write from INSIDE the app, through the door every writer in it uses."""
    return files.write_text(folder / f"{name}.json", json.dumps(doc))


def _age_the_looks(seconds: float) -> None:
    for key, (at, count, sig) in list(races._SIGNATURES.items()):
        races._SIGNATURES[key] = (at - seconds, count, sig)


class TestReadOnce:
    def test_the_folders_are_parsed_once_across_many_questions(self, homebrew, monkeypatch):
        _by_the_bench(homebrew, "testfolk", TESTFOLK)
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
        _by_the_bench(homebrew, "testfolk", TESTFOLK)
        one = races.get("testfolk")
        one["name"] = "Vandalised"
        assert races.get("testfolk")["name"] == "Testfolk"
        doc = races.document("testfolk")
        doc["traits"].append("not really")
        assert "not really" not in races.document("testfolk")["traits"]

    def test_the_shared_document_survives_the_sheet_reading_it(self, homebrew):
        """`_race_doc` hands out the registry's own dict (`races.shared`) rather than a
        deepcopy — the copy was 0.26 s of 1,500 `has_state` calls. That is safe only
        while every reader behind it reads; this walks each one and checks the dict is
        as it was, so the first reader that writes to it fails here and not in play,
        where it would quietly rewrite every character of the race."""
        _by_the_bench(homebrew, "testfolk", {
            **TESTFOLK, "choose": list(races.STANDARD_CHOOSE),
            "evolutions": [{"id": "claws"}, {"id": "bite"}, {"id": "flight"},
                           {"id": "skilled", "choice": "perception"}]})
        before = copy.deepcopy(races.shared("testfolk"))
        assert races.shared("testfolk") is races.shared("testfolk")

        pc = load_pc("fixtures/pc-kesst.json")
        pc.race = "testfolk"
        assert pc.has_state("race.testfolk")
        assert pc.weapon("claws")["natural"]
        assert pc.movement_modes().get("fly")
        assert pc.can_move_vertically() == "fly"
        assert pc.skill_modifiers("perception")
        pc.cmd()
        assert races.body_line(pc._race_doc())
        assert races.shared("testfolk") == before


class TestReadAgainWhenTheFileMoves:
    def test_an_edit_on_the_bench_is_seen_on_the_next_read(self, homebrew):
        """Measured 2026-09-25: this failed one run in five when the check was mtime and
        size — "speed": 30 and "speed": 40 are the same size, and two writes inside one
        clock tick share an mtime. Twenty-five rounds under a ten-second look, with no
        help from the clock: the door has to carry every one."""
        races._SIGNATURE_TTL = 10.0
        for n in range(25):
            speed = 30 if n % 2 else 40
            _by_the_bench(homebrew, "testfolk", {**TESTFOLK, "speed": speed})
            assert races.document("testfolk")["speed"] == speed, n

    def test_a_race_added_is_seen_and_one_removed_is_gone(self, homebrew):
        races._SIGNATURE_TTL = 10.0
        assert races.get("testfolk") is None
        _by_the_bench(homebrew, "testfolk", TESTFOLK)
        assert races.get("testfolk") is not None
        files.remove(homebrew / "testfolk.json")
        assert races.get("testfolk") is None

    def test_a_hand_edit_is_seen_once_the_look_expires(self, homebrew):
        """What the timer costs, pinned so it is a decision and not a surprise: an edit
        made outside the app waits for the next look, at most `_SIGNATURE_TTL` (half a
        second) — shorter than a person can alt-tab back to the game."""
        races._SIGNATURE_TTL = 10.0
        _by_hand(homebrew, "testfolk", TESTFOLK)
        assert races.document("testfolk")["speed"] == 30
        path = _by_hand(homebrew, "testfolk", {**TESTFOLK, "speed": 40})
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        assert races.document("testfolk")["speed"] == 30        # the look still holds
        _age_the_looks(11)
        assert races.document("testfolk")["speed"] == 40

    def test_a_racily_young_file_is_read_by_its_bytes(self, homebrew):
        """git's racy-clean rule: a file whose mtime is as young as the look can change
        again without its stat changing. The same size and the SAME mtime, forced — the
        exact 2026-09-25 flake, but from outside the app where no door can help — and
        the new speed is still seen, because a young file's bytes are part of the look."""
        now = time.time_ns()
        _by_hand(homebrew, "testfolk", TESTFOLK, mtime_ns=now)
        assert races.document("testfolk")["speed"] == 30
        _by_hand(homebrew, "testfolk", {**TESTFOLK, "speed": 40}, mtime_ns=now)
        assert races.document("testfolk")["speed"] == 40

    def test_an_old_file_is_not_read_to_be_checked(self, homebrew, monkeypatch):
        """And the rule's other half: a file older than the racy window is judged by its
        stat alone. Reading every file's bytes on every look is what cost 1.3 s."""
        _by_hand(homebrew, "testfolk", TESTFOLK, mtime_ns=time.time_ns() - 3600 * 10**9)
        sums = []
        real = races.zlib.crc32
        monkeypatch.setattr(races.zlib, "crc32", lambda b, *a: sums.append(1) or real(b, *a))
        for _ in range(20):
            assert races.document("testfolk")["speed"] == 30
        assert sums == []

    def test_a_race_stood_in_front_of_the_sheet_is_honoured(self, homebrew, monkeypatch):
        """`test_natural_attacks` replaces `all_races` to hand the sheet a race with a
        bite. The first cut of the cache read past `all_races`, and the bite was gone."""
        real = races.all_races()
        doc = races.normalise({**TESTFOLK, "speed": 45})
        monkeypatch.setattr(races, "all_races", lambda: {**real, "testfolk": doc})
        assert races.document("testfolk")["speed"] == 45
        assert races.get("testfolk")["speed"] == 45


def test_fifteen_hundred_has_state_calls_do_not_touch_the_disk(homebrew, monkeypatch):
    """Measured 2026-09-27 on the Windows dev box: 1,500 `has_state` calls for a
    character of a homebrew race took 1.32 s — `nt.stat` 0.45 s, `scandir` 0.25 s, `open`
    0.22 s, `deepcopy` 0.26 s — because the homebrew folder was listed, stat-ed and
    checksummed on every call. After the write door, `scandir` and `races.shared`: 0.05 s.

    Two bounds. The mechanical one cannot flake: at the real half-second look, the
    folders are looked at a handful of times across all 1,500 calls, not 1,500 times,
    and no file's bytes are read. The clock one is set ten times above the measurement
    so a busy 12-worker run passes, and still well under the 1.32 s it replaced."""
    monkeypatch.setattr(races, "_SIGNATURE_TTL", _DEFAULT_TTL)
    _by_hand(homebrew, "testfolk", {**TESTFOLK, "evolutions": [{"id": "claws"}]},
             mtime_ns=time.time_ns() - 3600 * 10**9)
    pc = load_pc("fixtures/pc-kesst.json")
    pc.race = "testfolk"
    assert pc.has_state("race.testfolk")

    looks, sums = [], []
    real_look, real_crc = races._look, races.zlib.crc32
    monkeypatch.setattr(races, "_look", lambda folder: looks.append(1) or real_look(folder))
    monkeypatch.setattr(races.zlib, "crc32", lambda b, *a: sums.append(1) or real_crc(b, *a))
    start = time.perf_counter()
    for _ in range(1500):
        pc.has_state("state.down")
    took = time.perf_counter() - start

    budget = 2 * (2 + int(took / _DEFAULT_TTL))       # two folders, one look per TTL each
    assert len(looks) <= budget, f"{len(looks)} looks at the folders in {took:.2f} s"
    assert sums == [], "a file's bytes were read to check a folder nothing had written to"
    assert took < 0.5, f"1,500 has_state calls took {took:.2f} s (1.32 s before, 0.05 s after)"


def test_nothing_removes_a_file_around_the_door():
    """`files.remove` is how a cache of a folder hears a file go; `Path.unlink` in code
    that works in the homebrew folders is invisible to it. `rules/npcs.py:forget` was
    the one such site on 2026-09-27. `files.write_text` has its own ratchet in
    `test_a_save_is_never_half_written.py`."""
    import pathlib
    import re

    offenders = []
    for folder in ("rules", "play"):
        for path in pathlib.Path(folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if not re.search(r"homebrew_dir|[\"']homebrew[\"']", text):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if ".unlink(" in line and not line.lstrip().startswith("#"):
                    offenders.append(f"{path}:{n}")
    assert offenders == [], "use pathfindergm.files.remove: " + ", ".join(offenders)
