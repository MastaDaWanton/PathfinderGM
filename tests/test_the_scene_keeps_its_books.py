"""What the scene keeps has a place of its own, and a bound.

Measured 2026-09-25 by the engine and pipeline reviews:
- `scene.said`, documented as the narrator's line rotation, also carried a crowd's
  experience debt (`routed_xp`) and the payments agreed in a room (`agreements`), in a
  dict with no schema;
- `scene.log` was appended every outcome, read by nothing in the app, never trimmed, and
  deep-copied by every snapshot;
- `prompts.pack` sent a prompt whose fixed parts were already over budget without a word;
- `KEEP_EXCHANGES = 3` kept `history[-6:]`, and a turn writes three messages, so it kept two.
"""
from __future__ import annotations

import json
import logging

from django.test import override_settings

from gm import prompts
from rules.engine import Scene


def test_the_log_is_bounded():
    from rules.dice import Dice
    from rules.engine import Engine
    from rules.sheet import load_pc

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1))
    for _ in range(Scene.LOG_KEPT + 30):
        e.run(e.validate([{"op": "narrate_only", "because": "time passes"}]))
    assert len(s.log) == Scene.LOG_KEPT


def test_the_two_records_have_their_own_fields_and_survive_a_save(tmp_path):
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.routed_xp = [{"who": "the raiders", "fallen": 3, "xp": 300}]
        c.scene.agreements = ["Kesst paid the ferryman 2 × sp for the crossing"]
        c.save()
        back = cm.Campaign.load(c.path())
        cm._LIVE.clear()
    assert back.scene.routed_xp == c.scene.routed_xp
    assert back.scene.agreements == c.scene.agreements
    assert "routed_xp" not in back.scene.said and "agreements" not in back.scene.said


def test_a_save_that_kept_them_in_said_is_moved_over(tmp_path):
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.save()
        raw = json.loads(c.path().read_text(encoding="utf-8"))
        raw["scene"].pop("routed_xp", None)
        raw["scene"].pop("agreements", None)
        raw["scene"]["said"] = {"routed_xp": [{"who": "x", "fallen": 1, "xp": 50}],
                                "agreements": ["paid"], "death_lines": [3]}
        c.path().write_text(json.dumps(raw), encoding="utf-8")
        back = cm.Campaign.load(c.path())
        cm._LIVE.clear()
    assert back.scene.routed_xp == [{"who": "x", "fallen": 1, "xp": 50}]
    assert back.scene.agreements == ["paid"]
    assert back.scene.said == {"death_lines": [3]}


def _turn(n):
    return [{"role": "user", "content": f"line {n}"},
            {"role": "assistant", "content": f"plan {n}"},
            {"role": "assistant", "content": f"prose {n}"}]


def test_three_exchanges_are_three_turns():
    history = sum((_turn(n) for n in range(6)), [])
    report = {}
    out = prompts.pack([{"role": "system", "content": "s"}], [], history,
                       [{"role": "user", "content": "now"}], keep=3, report=report,
                       budget=10 ** 6)
    users = [m["content"] for m in out if m["content"].startswith("line")]
    assert users[-3:] == ["line 3", "line 4", "line 5"]


def test_a_prompt_over_budget_is_said(caplog):
    report = {}
    with caplog.at_level(logging.WARNING, logger="pathfindergm"):
        prompts.pack([{"role": "system", "content": "x" * 500}], [], [],
                     [{"role": "user", "content": "now"}], budget=100, report=report)
    assert report["over_budget"] is True
    assert any("over the" in r.message for r in caplog.records)
