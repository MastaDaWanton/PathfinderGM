"""The enemy-turn loop running out of budget, with and without the model.

Found reading the code for the architecture overview (2026-09-29), not in play: after the
loop's last iteration `_run_npc_turns` called `_log_turn(c, plan, resolution)`. `plan` is
assigned only when a creature's model call succeeds, so a loop in which every creature
fell back to the code rule — Ollama down, or every creature holding back — reached that
line with `plan` never bound. UnboundLocalError, which the one-game-at-a-time middleware
turns into a 500 that drops the live campaign, on a turn the player had already finished.

When the model did answer, the same line wrote a second row of kind "turn" for the last
creature's plan — a creature's turn logged as though the player had taken it, beside the
"npc-turn" row the iteration had already written. It was the only place an NPC turn's
timing and model were recorded, so those move onto the creature's own row.

The budget runs out in play when the player is down and the fight goes on without them:
the order skips the unconscious and never comes back round to the player.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from gm.client import ModelUnavailable
from rules.sheet import load_pc


@pytest.fixture
def player_down(tmp_path):
    """The player bleeding on the floor, a companion and a thug fighting on."""
    from play import campaign as cm
    from rules.bestiary import instantiate

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20261001
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c1"
        c.scene.add(thug)
        ally = instantiate("thug", scene=c.scene, name="the hired blade")
        ally.ref = "c2"
        c.scene.add(ally)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc", "c2"], "them": ["c1"]}}}]))
        c.scene.pc().hp = -1
        yield c
        cm._LIVE.clear()


class _Offline:
    """The agent with Ollama down: every creature's turn raises."""
    engine = None

    def npc_turn(self, *a, **k):
        raise ModelUnavailable("connection refused")


def test_a_loop_with_the_model_offline_hands_the_turn_back_rather_than_raising(
        player_down, monkeypatch):
    """Twelve iterations, every one on the fallback, and the line after the loop read a
    `plan` none of them had set: UnboundLocalError. Measured by reading play/views.py at
    the overview; reproduced here with the player down so the order never reaches them."""
    from gm import judgement
    from play import views

    c = player_down
    # Nobody swings, so nobody falls and the fight cannot end early on a lucky roll:
    # the budget is what stops the loop, which is the case being tested.
    monkeypatch.setattr(judgement, "default_npc_action", lambda scene, ref: None)
    views._run_npc_turns(c, _Offline())

    npc_rows = [r for r in c.turn_log if r.get("kind") == "npc-turn"]
    assert npc_rows, "the creatures' turns were not recorded"
    assert all("error" in r for r in npc_rows)
    assert not [r for r in c.turn_log if r.get("kind") == "turn"], (
        "a creature's turn was logged as the player's")


def test_a_creature_turn_is_logged_once_with_its_timing_and_model(player_down, monkeypatch):
    """With the model answering, the loop's tail wrote a "turn" row for the last
    creature's plan beside the "npc-turn" row it already had: two rows for one turn, and
    the turn log's "turn" kind — the player's — claiming it. The row it duplicated was the
    only one carrying the turn's seconds and which model wrote it, so those are on the
    creature's own row now."""
    from gm.agent import Attempt, TurnPlan
    from play import views

    c = player_down

    class _Answering:
        engine = None

        def npc_turn(self, ref, **k):
            return TurnPlan(narration="", intents=[],
                            attempts=[Attempt(kind="npc", seconds=2.5, model="m-test")])

        def narrate_outcome(self, *a, **k):
            return "", None

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    views._run_npc_turns(c, _Answering())

    assert not [r for r in c.turn_log if r.get("kind") == "turn"]
    rows = [r for r in c.turn_log if r.get("kind") == "npc-turn"]
    assert rows
    assert rows[0]["seconds"] == 2.5
    assert rows[0]["attempts"] == [{"kind": "npc", "seconds": 2.5, "note": "",
                                    "model": "m-test"}]
