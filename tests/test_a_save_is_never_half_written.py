"""A campaign is never the only copy of itself, and never half-written.

Measured 2026-09-25: `Campaign.save` was `p.write_text(...)` — truncate, then write — on
the only copy of the game, rewritten whole every turn, in an app whose shell falls back
to a hard `taskkill`. A save cut off mid-write was an `UnreadableSave` with nothing
behind it. Ten more writers (roster, model settings, house rules, the secret key, every
homebrew bench) had the same shape. Now every write lands by rename, a campaign keeps
its last three saves, and a load that fails opens the newest backup that reads.
"""
from __future__ import annotations

import json
import os
import pathlib
import re

import pytest
from django.test import override_settings

from pathfindergm import files


def test_a_write_that_fails_leaves_the_old_file_whole(tmp_path, monkeypatch):
    target = tmp_path / "save.json"
    files.write_text(target, '{"turn": 1}')

    def killed(*_a, **_kw):
        raise OSError("the process died between the write and the rename")

    monkeypatch.setattr(files.os, "replace", killed)
    with pytest.raises(OSError):
        files.write_text(target, '{"turn": 2, "half": ')
    assert json.loads(target.read_text(encoding="utf-8")) == {"turn": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["save.json"], "no temp file left"


def test_backups_rotate_newest_first(tmp_path):
    target = tmp_path / "c.json"
    for turn in range(1, 6):
        files.keep_backup(target, keep=3)
        files.write_text(target, str(turn))
    kept = files.backups(target, keep=3)
    assert [p.read_text() for p in kept] == ["4", "3", "2"]
    assert target.read_text() == "5"


@pytest.fixture
def campaigns(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm

        cm._LIVE.clear()
        yield cm
        cm._LIVE.clear()


def _new(cm, cid):
    c = cm.current(cid)
    c.save()
    return c


def test_a_torn_save_opens_from_the_turn_before(campaigns):
    cm = campaigns
    c = _new(cm, "torn")
    c.transcript.append({"who": "gm", "text": "The second turn."})
    c.save()
    path = c.path()
    # Cut off mid-write, as a hard kill would leave it.
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: len(text) // 2], encoding="utf-8")
    cm._LIVE.clear()

    back = cm.current("torn")
    assert back.transcript[-1]["kind"] == "aside"
    assert "restored from the one before" in back.transcript[-1]["text"]
    kept = list(path.parent.glob("torn.json.unreadable-*"))
    assert len(kept) == 1, "the unreadable file is kept, never deleted"
    assert json.loads(path.read_text(encoding="utf-8"))["save_version"]


def test_with_no_backup_that_reads_the_refusal_still_stands(campaigns):
    cm = campaigns
    c = _new(cm, "gone")
    path = c.path()
    for p in files.backups(path, keep=cm.BACKUPS_KEPT):
        p.unlink()
    path.write_text("{", encoding="utf-8")
    cm._LIVE.clear()
    with pytest.raises(cm.UnreadableSave):
        cm.current("gone")


def test_no_writer_truncates_a_file_in_place():
    """The ratchet: `Path.write_text` in shipped code is the shape this replaced."""
    offenders = []
    for folder in ("play", "rules", "gm", "pathfindergm", "world"):
        for path in pathlib.Path(folder).rglob("*.py"):
            if path.as_posix() == "pathfindergm/files.py":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"(?<!files)\.write_text\(", line) and not line.lstrip().startswith("#"):
                    offenders.append(f"{path.as_posix()}:{n}")
    assert offenders == [], "use pathfindergm.files.write_text: " + ", ".join(offenders)
