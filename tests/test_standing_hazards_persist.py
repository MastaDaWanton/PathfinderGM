"""A restart used to delete every standing hazard in the scene.

`Ward.as_dict`/`from_dict` and `Manifestation.as_dict`/`from_dict` were all written, and
`play/campaign.py` called none of them: the scene's two hazard stores were never saved, so
closing the app mid-fight silently removed every fog cloud, wall of stone, thorn body and
bleed ward — while the grid kept the squares they had claimed. The constructors had zero
call sites in the whole repo and had never been exercised by a real save.
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from rules.engine import Manifestation, Ward
from rules.sheet import load_pc


def _campaign(tmp_path, cid="hazards"):
    from play import campaign as cm

    cm._LIVE.clear()
    c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.id = cid
    return c


def test_a_fog_cloud_survives_closing_the_app(tmp_path):
    from play import campaign as cm
    from rules.grid import Grid

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        c = _campaign(tmp_path)
        c.scene.grid = Grid(width=20, height=20)
        c.scene.place(Manifestation(
            what="a bank of fog", terrain="obscuring",
            squares=[(4, 4), (4, 5)], rounds_left=50, source="fog cloud"))
        squares = set(c.scene.grid.obscuring)
        assert squares, "the fog claimed no squares to begin with"
        c.save()

        cm._LIVE.clear()
        back = cm.current(c.id)

    assert len(back.scene.manifests) == 1, "the fog was deleted by the restart"
    made = back.scene.manifests[0]
    assert made.what == "a bank of fog" and made.rounds_left == 50
    assert set(back.scene.grid.obscuring) == squares, "its squares moved"


def test_the_squares_are_not_claimed_twice_on_reload(tmp_path):
    """A restored manifestation must NOT go through `Scene.place`. The grid is saved
    with the fog's squares already in `grid.obscuring`, so place() would recompute
    `added` as empty — and `lift()` would then leave the room permanently opaque with
    no fog in it to explain why."""
    from play import campaign as cm
    from rules.grid import Grid

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        c = _campaign(tmp_path, "twice")
        c.scene.grid = Grid(width=20, height=20)
        c.scene.place(Manifestation(what="fog", terrain="obscuring",
                                    squares=[(6, 6)], rounds_left=5, source="fog"))
        c.save()
        cm._LIVE.clear()
        back = cm.current("twice")
        made = back.scene.manifests[0]
        assert made.added == [(6, 6)], "the squares it changed were lost"
        back.scene.lift(made)
        assert (6, 6) not in back.scene.grid.obscuring, "the room stayed blind"


def test_a_ward_and_the_area_it_belongs_to_stay_joined(tmp_path):
    """Manifestation ids are a foreign key: `Ward.manifest_id` resolves through them in
    `_aimed_at`'s area branch. Re-minting ids on load would silently detach every area
    ward — it would return nobody and the hazard would fire on no one, with nothing
    reported anywhere."""
    from play import campaign as cm
    from rules.grid import Grid

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        c = _campaign(tmp_path, "joined")
        c.scene.grid = Grid(width=20, height=20)
        made = c.scene.place(Manifestation(
            what="acid fog", terrain="obscuring", squares=[(3, 3)],
            rounds_left=10, source="acid fog"))
        c.scene.wards.append(Ward(owner="", trigger="each_round", recipient="area",
                                  manifest_id=made.id, source="acid fog",
                                  rounds_left=10, spec={}))
        c.save()
        cm._LIVE.clear()
        back = cm.current("joined")

    assert len(back.scene.wards) == 1 and len(back.scene.manifests) == 1
    assert back.scene.wards[0].manifest_id == back.scene.manifests[0].id != ""


def test_a_damaged_hazard_record_is_dropped_not_fatal(tmp_path):
    """`Ward.from_dict` was `cls(**{...})` and `owner`/`trigger` have no defaults, so a
    truncated record raised TypeError inside `Campaign.load` — which `_resume` turns
    into UnreadableSave, which means the whole campaign refuses to open because one
    ward was written badly. A hazard that cannot be read is a hazard to drop."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        c = _campaign(tmp_path, "damaged")
        c.save()
        path = c.path()
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["scene"]["wards"] = [{"source": "a corrupted ward"}, {"trigger": "each_round"}]
        path.write_text(json.dumps(raw), encoding="utf-8")

        cm._LIVE.clear()
        back = cm.current("damaged")          # must not raise UnreadableSave

    assert len(back.scene.wards) == 1, "the readable ward should survive"
    assert back.scene.wards[0].trigger == "each_round"


def test_both_hazard_stores_are_saved_and_named_as_such():
    """The unsaved-field allowlist loses two entries, which is this substage's proof."""
    from tests.test_three_laws import _UNSAVED_SCENE_FIELDS

    assert "wards" not in _UNSAVED_SCENE_FIELDS
    assert "manifests" not in _UNSAVED_SCENE_FIELDS
