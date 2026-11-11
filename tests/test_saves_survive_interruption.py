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
