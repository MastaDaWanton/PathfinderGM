"""A save stops growing by its diagnostics, and its backups span turns.

Measured 2026-11-15 on the owner's 2026-11-05 save: the turn log was 94 rows for 13 turns,
75 KB, 5.7 KB a turn, and 45 KB of it diagnostics nothing reads past the last few turns;
slimmed, the same rows are 20 KB. And every save rotated the backups, so a turn that saves
three times (intents, prose, an NPC) pushed all three backups inside that one turn (review
2026-11-11 finding 22).
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from pathfindergm import files


@pytest.fixture
def campaigns(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm

        cm._LIVE.clear()
        yield cm
        cm._LIVE.clear()


def _turn(n: int) -> list[dict]:
    """One turn's rows as the live game writes them: a turn row heavy with the reader's
    working, a prose row with the narrator's attempts, and a diagnostic row."""
    return [
        {"kind": "turn", "clock": n * 10, "at": "here", "attempts": ["x" * 400],
         "repairs": ["r" * 200], "reading": {"r": "y" * 300},
         "intents": [{"id": "i1", "actor": "pc", "op": "move"}],
         "outcomes": [{"intent_id": "i1", "op": "move", "tell": f"Turn {n}.",
                       "effects": [{"kind": "xp", "ref": "pc", "amount": n}]}]},
        {"kind": "prose", "attempts": ["z" * 1600], "suggested": ["Look about"]},
        {"kind": "beat-verify", "checks": ["c" * 700]},
    ]


def test_old_rows_are_slimmed_and_none_is_dropped(campaigns):
    cm = campaigns
    log = [row for n in range(200) for row in _turn(n)]
    slim = cm._slim_turn_log(json.loads(json.dumps(log)))
    cut = len(log) - cm.TURN_LOG_WHOLE
    before, after = len(json.dumps(log[:cut])), len(json.dumps(slim[:cut]))
    assert len(slim) == len(log), "rows were dropped: turns played would move"
    assert slim[-cm.TURN_LOG_WHOLE:] == log[-cm.TURN_LOG_WHOLE:], "the window changed"
    old = slim[0]
    assert set(old) == {"kind", "clock", "at", "intents", "outcomes"}, old
    assert slim[1] == {"kind": "prose"} and slim[2] == {"kind": "beat-verify"}
    assert after < before / 5, (after, before)


def test_the_journal_history_reads_the_same_after_slimming(campaigns):
    """The one reader of the whole log: the Journal's history (play/history.py)."""
    from play import history

    cm = campaigns
    c = cm.current("growth")
    c.turn_log = [row for n in range(200) for row in _turn(n)]
    whole = history.history(c)
    c.save()
    assert len(c.turn_log) == 600
    assert c.turn_log[0].get("attempts") is None, "the save did not slim the old rows"
    assert history.history(c) == whole


def test_backups_keep_the_turn_before_through_a_turn_of_saves(campaigns):
    cm = campaigns
    c = cm.current("rotating")
    for n in range(1, 4):
        c.transcript.append({"who": "player", "text": f"line {n}"})
        for stage in ("intents", "prose", "npc"):
            c.transcript.append({"who": "gm", "text": f"turn {n} {stage}"})
            c.save()
    kept = [json.loads(p.read_text(encoding="utf-8"))["transcript"][-1]["text"]
            for p in files.backups(c.path(), keep=cm.BACKUPS_KEPT)]
    # Rotating on every save, all three of these were "turn 3 ...".
    assert kept[0] == "turn 2 npc", kept
    assert kept[1] == "turn 1 npc", kept


def test_a_new_campaigns_second_save_still_has_a_backup(campaigns):
    cm = campaigns
    c = cm.current("fresh")
    c.save()
    c.save()
    assert files.backups(c.path(), keep=1), "the torn-save restore would have nothing"
