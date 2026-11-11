"""What an interruption leaves behind (review 2026-11-11, findings 3, 7, 18, 22).

Each of these is a moment between two writes: the active pointer and the save it names,
the bytes of a world and the check that they read, a temporary file and its rename, a
backup rotation and a save that changed nothing.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules.sheet import load_pc


@pytest.fixture
def campaigns(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm

        cm._LIVE.clear()
        yield cm
        cm._LIVE.clear()


# --- finding 3: the active pointer is written after the save it names ---------------------

@pytest.mark.parametrize("breaks", ["new_campaign", "open_the_story"])
def test_an_interrupted_first_start_does_not_become_the_active_campaign(
        campaigns, monkeypatch, breaks):
    """`switch_to` wrote active.txt BEFORE building a never-played character's campaign.
    Measured on 7f63ab60 with either builder raising mid-switch: active.txt named the
    character's campaign, no save existed under it, and the next `current()` fell
    through to `_begin`, which saved the shipped pregen as `<character id>.json` — after
    which every switch to that character resumed the pregen's game. The pointer now
    moves only once the save is on disk, as `begin_with` already did it."""
    cm = campaigns
    from play import roster

    cm.current()                                   # somebody is already being played
    was = cm.active_id()
    entry = roster.enrol(load_pc("fixtures/pc-kesst.json"))
    cm._LIVE.clear()

    def dies(*_a, **_kw):
        raise RuntimeError("the app was closed while the opening was being written")

    monkeypatch.setattr(cm, breaks, dies)
    with pytest.raises(RuntimeError):
        cm.switch_to(entry.id)
    monkeypatch.undo()

    assert cm.active_id() == was, "the pointer names a campaign that was never saved"
    cm._LIVE.clear()
    cm.current()                                   # the next launch
    assert not cm._save_path(entry.id).exists(), \
        "a pregen was saved under the new character's campaign id"

    # And the character is still startable: nothing half-made stands in the way.
    c = cm.switch_to(entry.id)
    assert cm.active_id() == entry.id and c.character_id == entry.id
    assert c.scene.pc().name == entry.name


# --- finding 7: a world import never touches the world that is there until it reads -------

@pytest.fixture
def shelf(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import library

        good = open("fixtures/pangrella-campaign.json", "rb").read()
        library.import_upload("mine.json", good)
        yield library, library.user_dir() / "mine.json", good


def test_an_import_cut_off_mid_write_leaves_the_old_world_whole(shelf, monkeypatch):
    """`import_upload` wrote the upload straight over the world on the shelf
    (`target.write_bytes(data)`, outside its own try) and kept the old bytes only in
    memory. Measured on 7f63ab60 with the write cut off half-way, as a full disk or a
    hard kill leaves it: the 1,169,578-byte world that worked was a 584,789-byte file
    that no longer parsed, and every campaign set in it failed to load. Both doors are shut here — the
    in-place write the old code used and the rename the new one lands by — so the test
    fails on either shape if the file on the shelf is ever the one being written."""
    import pathlib

    from pathfindergm import files

    library, target, good = shelf
    newer = good.replace(b"Pangrella", b"Pangrolla")
    assert newer != good

    def torn(self, data):
        with open(self, "wb") as f:
            f.write(data[: len(data) // 2])
        raise OSError(28, "No space left on device")

    def killed(*_a, **_kw):
        raise OSError("the process died before the rename")

    monkeypatch.setattr(pathlib.Path, "write_bytes", torn)
    monkeypatch.setattr(files.os, "replace", killed)
    with pytest.raises(OSError):
        library.import_upload("mine.json", newer)
    monkeypatch.undo()

    assert target.read_bytes() == good, "the world on the shelf was written in place"
    assert [p.name for p in target.parent.iterdir()] == ["mine.json"], "no temp left"


def test_an_import_that_does_not_read_changes_nothing_and_names_the_upload(shelf):
    """The other failure, which the old code did handle by writing the old bytes back:
    kept true, and the refusal still names the file the player sent rather than the
    temporary one it was checked as (`.mine.json.k3x0_a9b.tmp: schema 9.0 ...`)."""
    from world.loader import UnsupportedSchema, load_cached

    library, target, good = shelf
    with pytest.raises(UnsupportedSchema) as refused:
        library.import_upload("mine.json", b'{"schema_version": "9.0"}')
    assert str(refused.value).startswith("mine.json: schema 9.0")
    with pytest.raises(ValueError):
        library.import_upload("mine.json", b"{ not json")
    assert target.read_bytes() == good
    assert [p.name for p in target.parent.iterdir()] == ["mine.json"]
    # And a good import over it is the one the shelf and the game then read.
    card = library.import_upload("mine.json", good.replace(b"Pangrella", b"Pangrolla"))
    assert target.read_bytes() != good and not card.problem
    assert load_cached(target).source == target


# --- finding 18: a temporary file orphaned by a kill is swept, and only that --------------

def _orphan(folder, name, age):
    import os
    import time

    path = folder / name
    path.write_text("half a save", encoding="utf-8")
    then = time.time() - age
    os.utime(path, (then, then))
    return path


def test_a_temp_file_orphaned_by_a_kill_is_swept_on_the_next_start(tmp_path):
    """`files.write_text` makes `.<name>.<8 random>.tmp` and renames it; a hard kill
    between the two (the desktop shell's fallback is `taskkill`) left it for good.
    Measured on 7f63ab60: an orphan an hour old was still there after any number of
    later saves — each one the size of a whole campaign. The first write this process
    makes in a folder now clears them. Only names of exactly the shape this module
    makes, and only old ones: a temporary file minutes old may be another thread's
    write in flight, and anything else in the folder is not ours to delete."""
    from pathfindergm import files

    stale = _orphan(tmp_path, ".kesst.json.a1b2c3_4.tmp", age=3600)
    in_flight = _orphan(tmp_path, ".kesst.json.zzzzzzzz.tmp", age=5)
    theirs = [_orphan(tmp_path, name, age=3600)
              for name in ("notes.tmp", ".kesst.json.tmp", ".kesst.json.TOOLONG99.tmp",
                           "kesst.json.a1b2c3_4.tmp", "kesst.json.1")]

    files.write_text(tmp_path / "kesst.json", "{}")
    assert not stale.exists(), "the orphan is still there"
    assert in_flight.exists(), "a write that may still be in flight was deleted"
    assert all(p.exists() for p in theirs), "a file this module did not make was deleted"


def test_an_orphan_held_open_elsewhere_does_not_fail_the_save(tmp_path, monkeypatch):
    """On Windows a file open in another process (an indexer, an antivirus scan)
    refuses `unlink` with PermissionError. The sweep is a courtesy; the save is not."""
    from pathfindergm import files

    stale = _orphan(tmp_path, ".kesst.json.a1b2c3_4.tmp", age=3600)
    real = files.os.unlink

    def held(path, *a, **kw):
        if str(path).endswith("a1b2c3_4.tmp"):
            raise PermissionError(13, "The process cannot access the file", str(path))
        return real(path, *a, **kw)

    monkeypatch.setattr(files.os, "unlink", held)
    files.write_text(tmp_path / "kesst.json", "{}")
    assert (tmp_path / "kesst.json").read_text(encoding="utf-8") == "{}"
    assert stale.exists()
