"""One creature's action reads as one beat: the wind-up and what the dice made of it.

The 2026-10-16 report (0.2.19, free narrator): "the npc took multiple turns". The engine
resolved exactly one attack by the woman each round (npc-turn rows 45 and 54 of the turn
log), and the page showed each as two beats — the wind-up as its own paragraph ("lunges
forward, her grip tightening on the club as she swings it in a desperate, heavy arc") and
then the result as another ("The heavy club whistles through the air, missing your skull
by a hair's breadth"). In round one a repair had cut the wind-up down to its filler, and
"The woman with a thick braid of hair eyes you with a sharp, calculating gaze." stood on
the page as a beat of its own in which nothing happened.

The split is the intent protocol's (docs/intent-protocol.md §2): the plan call writes only
what is true however the dice land, the consequence call the landing. That is two CALLS.
It was never meant to be two beats, and `_run_npc_turns` now puts them on the page as one.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules.sheet import load_pc


@pytest.fixture
def fight(tmp_path):
    """The player and a thug at arm's length, the player holding the turn."""
    from play import campaign as cm
    from rules.bestiary import instantiate
    from tests._board import face_to_face

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20261016
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the woman with the braid")
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        face_to_face(c.scene)
        c.scene.turn = next(i for i, (r, _) in enumerate(c.scene.initiative) if r == "pc")
        c.transcript = []
        yield c
        cm._LIVE.clear()


WINDUP = "The woman with the braid lunges forward, swinging her club at your head."
RESULT = "The club whistles past your ear and thuds into the dirt."


def _agent(result: str):
    from gm.agent import Attempt, TurnPlan

    class _Agent:
        engine = None
        last_added: list = []

        def npc_turn(self, ref, **k):
            intents = self.engine.validate(
                [{"op": "attack", "actor": ref, "target": "pc", "because": "she swings"}],
                origin="creature:thug", origin_name="the woman with the braid")
            return TurnPlan(narration=WINDUP, intents=intents,
                            attempts=[Attempt(kind="npc", seconds=1.0, model="m")])

        def narrate_outcome(self, narration, tells, *a, **k):
            assert narration == WINDUP, "the consequence call is shown the wind-up"
            return result, Attempt(kind="consequence", seconds=1.0, model="m")

    return _Agent()


def _creature_beats(c):
    return [b for b in c.transcript if b.get("who") == "gm"
            and not str(b.get("text", "")).startswith("The fight is over")]


def test_the_wind_up_and_the_result_are_one_beat(fight, monkeypatch):
    """Two beats for one swing before 2026-10-16; one now, the wind-up first."""
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    views._run_npc_turns(fight, _agent(RESULT))
    rows = [r for r in fight.turn_log if r.get("kind") == "npc-turn"]
    assert len(rows) == 1 and len(rows[0]["outcomes"]) == 1, "the premise: one attack"
    beats = _creature_beats(fight)
    assert len(beats) == 1, [b["text"] for b in beats]
    assert beats[0]["text"] == f"{WINDUP} {RESULT}"
    assert beats[0]["kind"] == "setup", "the narrator's prose, as every narrated beat is"
    assert "added" not in beats[0]


def test_with_no_prose_for_the_result_the_engine_line_joins_the_wind_up(fight, monkeypatch):
    """The consequence call whiffed: the plain tell stands in, in the SAME beat, and is
    marked ours so the next prose call is not shown it as its own (narrator-guards D4)."""
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    views._run_npc_turns(fight, _agent(""))
    beats = _creature_beats(fight)
    assert len(beats) == 1, [b["text"] for b in beats]
    assert beats[0]["text"].startswith(WINDUP + " ")
    assert beats[0]["added"], "the engine's line is marked as ours"
    assert all(s in beats[0]["text"] for s in beats[0]["added"])
    assert "the woman with the braid" in beats[0]["text"].lower()
