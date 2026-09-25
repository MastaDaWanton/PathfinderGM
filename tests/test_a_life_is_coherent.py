"""A rolled life agrees with itself, and with what the prose already said.

The user's ruling (2026-09-25): roll a personality from a massive chart and a quirk for
everyone, and lock out results that are not coherent with what was already rolled. The
first eight people this module made showed what "not coherent" looks like in practice: a
boy "weathered well past what the years alone would do" with a brand on his wrist, owing a
moneylender and plotting revenge; a shaved head that "smooths their hair flat"; a man in a
stained leather apron made a dyer; and "to learn to read and write properly" as the goal of
three people in six. Each is a property checked here over thousands of rolls.
"""
from __future__ import annotations

import collections

import pytest

from rules import faces, lives

N = 3000
PHRASES = ["", "woman watching from a doorway", "the smith", "old fisherman", "a boy",
           "man in a stained leather apron", "a girl", "an old crone", "the priest",
           "a young guard", "a pilgrim"]


@pytest.fixture(scope="module")
def rolled():
    out = []
    for i in range(N):
        phrase = PHRASES[i % len(PHRASES)]
        out.append((phrase, lives.roll(f"test|{i}", phrase=phrase)))
    return out


def _row(table, text):
    return next(r for r in lives.tables()[table] if r["text"] == text)


def test_the_same_person_always_rolls_the_same_life():
    assert lives.roll("x|c7", phrase="the smith") == lives.roll("x|c7", phrase="the smith")


def test_every_row_rolled_agrees_with_everything_else(rolled):
    """Wants, goal and hobby add no tags, so the final tags are the ones each was checked
    against — a row that disagrees with them is a contradiction that got through."""
    for phrase, life in rolled:
        tags = set(life.tags)
        work_class = next(o for o in lives.tables()["occupations"]
                          if o["id"] == life.work)["class"]
        for table, text in (("wants", life.wants), ("goals", life.goal),
                            ("hobbies", life.hobby)):
            row = _row(table, text)
            if table in [f.split()[0] for f in life.fallbacks]:
                continue
            assert lives._fits(row, tags, work_class), (phrase, table, text, sorted(tags))
        frame = next(f for f in lives.tables()["frames"] if f["id"] == life.quirk_frame)
        assert set(frame.get("needs") or []) <= tags, (life.quirk, sorted(tags))
        assert lives._fits(frame, tags, work_class), (life.quirk, sorted(tags))


def test_a_child_is_a_child(rolled):
    adult_only = {r["text"] for t in ("wants", "goals", "hobbies")
                  for r in lives.tables()[t] if "minor" in (r.get("excludes") or [])}
    children = [life for phrase, life in rolled if life.work == "child"]
    assert children
    for life in children:
        assert not {life.wants, life.goal, life.hobby} & adult_only, life
        assert life.face.lower().startswith("a child"), life.face
        assert "brand" not in life.face and "razor" not in life.face, life.face


def test_what_the_prose_said_is_never_contradicted(rolled):
    for phrase, life in rolled:
        if phrase.startswith(("old", "an old")):
            assert any(life.face.lower().startswith(faces.YEARS[i].split(",")[0].lower())
                       for i in (4, 5, 6)), (phrase, life.face)
        if phrase == "the smith":
            assert life.work == "smith"
        if phrase == "man in a stained leather apron":
            assert life.work == "tanner"


def test_a_priest_never_mocks_the_gods(rolled):
    for phrase, life in rolled:
        if life.work in ("priest", "pilgrim"):
            assert "irreverent" not in life.trait_ids


def test_hair_is_only_smoothed_where_there_is_hair(rolled):
    for phrase, life in rolled:
        if "hair" in life.quirk:
            assert "shaved head" not in life.face and "under a cap" not in life.face


def test_hands_fit_the_work(rolled):
    for phrase, life in rolled:
        if "stained black at the tips with ink" in life.face:   # not the tattooed knuckles
            assert "letters" in life.tags, (life.work, life.face)
        if "smoke and hot iron" in life.face:
            assert "forge" in life.tags, (life.work, life.face)


def test_no_single_row_swamps_the_table(rolled):
    """One goal for three people in six was the first sample; weighting the specific rows
    fixed it. No goal, want or hobby may be carried by more than 12% of people."""
    for attr in ("goal", "wants", "hobby"):
        top, n = collections.Counter(getattr(l, attr) for _, l in rolled).most_common(1)[0]
        assert n / N <= 0.12, (attr, top, n)


def test_fallbacks_are_rare(rolled):
    """A pool emptied by exclusions falls back to an unconditional row and says so; if
    this climbs, a table needs rows, not a looser rule."""
    fell = sum(1 for _, l in rolled if l.fallbacks)
    assert fell / N < 0.02, fell


def test_no_two_neighbours_share_a_quirk_until_the_bag_is_empty():
    used: set[str] = set()
    frames = []
    for i in range(15):
        life = lives.roll(f"town|{i}", phrase="", used_frames=used)
        frames.append(life.quirk_frame)
        used.add(life.quirk_frame)
    assert len(set(frames)) == len(frames)


def test_the_quirk_pool_holds_no_impairment():
    """The user's ruling of 2026-09-25: habits and fascinations only."""
    banned = ("stutter", "tic", "phobia", "afraid", "addict", "drunk", "mad", "insane",
              "blind", "deaf", "lame", "cripple", "fit", "seizure", "compuls")
    for f in lives.tables()["frames"]:
        text = f" {f['text'].lower()} "
        assert not any(f" {b}" in text for b in banned), f["text"]
