"""The unpack folders force-killed runs left behind are swept — only ours, never in use.

Measured 2026-09-05: 154 `_MEI*` folders (~40 MB each) in %TEMP% from force-killed
backends, and launches took 60-160 s while Defender caught up. The review of 2026-09-25
asked for a sweep at launch; the wrong deletion (another program's unpack, or a second
copy of the game still running) is worse than the leak, so the sweep is careful.
"""
from __future__ import annotations

import os

import desktop


def _unpack(root, name, ours=True):
    d = root / name
    (d / "play" / "templates" / "play").mkdir(parents=True)
    if ours:
        (d / "play" / "templates" / "play" / "table.html").write_text("x", encoding="utf-8")
    (d / "python313.dll").write_bytes(b"\0" * 16)
    return d


def test_an_abandoned_unpack_of_ours_is_swept(tmp_path):
    old = _unpack(tmp_path, "_MEI11111")
    swept = desktop._sweep_stale_unpacks(str(tmp_path), mine=str(tmp_path / "_MEI99999"))
    assert swept == [str(old)]
    assert not old.exists() and not (tmp_path / "_MEI11111.stale").exists()


def test_the_running_unpack_is_never_touched(tmp_path):
    me = _unpack(tmp_path, "_MEI22222")
    assert desktop._sweep_stale_unpacks(str(tmp_path), mine=str(me)) == []
    assert me.exists()


def test_another_programs_unpack_is_left_alone(tmp_path):
    theirs = _unpack(tmp_path, "_MEI33333", ours=False)
    assert desktop._sweep_stale_unpacks(str(tmp_path), mine="") == []
    assert theirs.exists()


def test_an_unpack_still_in_use_is_left_alone(tmp_path, monkeypatch):
    """Windows will not rename a directory with an open file in it; that refusal is the
    test for "a second copy of the game is still running from here"."""
    busy = _unpack(tmp_path, "_MEI44444")
    real = os.rename

    def locked(src, dst):
        if str(src) == str(busy):
            raise PermissionError(32, "in use")
        return real(src, dst)

    monkeypatch.setattr(desktop.os, "rename", locked)
    assert desktop._sweep_stale_unpacks(str(tmp_path), mine="") == []
    assert busy.exists()
