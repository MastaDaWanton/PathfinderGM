"""One creature's action reads as one beat, told from what the engine did.

The 2026-10-16 report (0.2.19, free narrator): "the npc took multiple turns". The engine
resolved exactly one attack by the woman each round (npc-turn rows 45 and 54 of the turn
log), and the page showed each as two beats — the wind-up as its own paragraph ("lunges
forward, her grip tightening on the club as she swings it in a desperate, heavy arc") and
then the result as another ("The heavy club whistles through the air, missing your skull
by a hair's breadth"). In round one a repair had cut the wind-up down to its filler, and
"The woman with a thick braid of hair eyes you with a sharp, calculating gaze." stood on
the page as a beat of its own in which nothing happened.

The split is the intent protocol's (docs/intent-protocol.md §2): the plan call writes only
what is true however the dice land, the consequence call the landing — two CALLS, never
meant to be two beats. And the wind-up, written before the dice and held to nothing on the
creature's sheet, drew a weapon the barkeep did not have on 4 of 6 free turns and 6 of 6
planned ones in the fight audits of the same day (a crossbow; he swung a sap), which the
consequence call, shown it, then fired. So a turn the engine told is told from its tells
alone, in one beat (`_told_by_its_blows`, the planned-fights lane's rule, for both
narrators); a companion keeps its wind-up, which carries its manner, in the same beat.
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


WINDUP = "The woman with the braid reaches beneath the counter for a heavy crossbow."
RESULT = "Her sap whistles past your ear and thuds into the dirt."


def _agent(result: str, raw: list | None = None):
    from gm.agent import Attempt, TurnPlan

    class _Agent:
        engine = None
        last_added: list = []
        shown: list = []

        def npc_turn(self, ref, **k):
            intents = self.engine.validate(
                raw or [{"op": "attack", "actor": ref, "target": "pc",
                         "because": "she swings"}],
                origin="creature:thug", origin_name="the woman with the braid")
            return TurnPlan(narration=WINDUP, intents=intents,
                            attempts=[Attempt(kind="npc", seconds=1.0, model="m")])

        def narrate_outcome(self, narration, tells, *a, **k):
            self.shown.append(narration)
            return result, Attempt(kind="consequence", seconds=1.0, model="m")

    return _Agent()


def _creature_beats(c):
    return [b for b in c.transcript if b.get("who") == "gm"
            and not str(b.get("text", "")).startswith("The fight is over")]


def test_a_blow_is_one_beat_told_from_its_tells(fight, monkeypatch):
    """Two beats for one swing before 2026-10-16; one now, and the wind-up's crossbow
    neither on the page nor shown to the call that writes the swing."""
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    agent = _agent(RESULT)
    views._run_npc_turns(fight, agent)
    rows = [r for r in fight.turn_log if r.get("kind") == "npc-turn"]
    assert len(rows) == 1 and len(rows[0]["outcomes"]) == 1, "the premise: one attack"
    beats = _creature_beats(fight)
    assert len(beats) == 1, [b["text"] for b in beats]
    assert beats[0]["text"] == RESULT and "crossbow" not in beats[0]["text"]
    assert agent.shown == [""], "the consequence call is not told the wind-up"
    assert beats[0]["kind"] == "setup", "the narrator's prose, as every narrated beat is"


def test_with_no_prose_for_the_blow_the_engines_line_is_the_one_beat(fight, monkeypatch):
    """The consequence call whiffed: the plain tell stands, one beat, as a consequence."""
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    views._run_npc_turns(fight, _agent(""))
    beats = _creature_beats(fight)
    assert len(beats) == 1, [b["text"] for b in beats]
    assert beats[0]["kind"] == "consequence" and "crossbow" not in beats[0]["text"]
    assert beats[0]["text"][:1].isupper()
    assert "the woman with the braid" in beats[0]["text"].lower()


def test_a_companion_keeps_its_wind_up_in_the_same_beat(fight, monkeypatch):
    """Its manner and its in-character choice live in the wind-up (the owner's rulings of
    2026-10-01): one beat, the wind-up first, the consequence shown it."""
    from gm import companions
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    monkeypatch.setattr(companions, "is_companion", lambda actor: True)
    monkeypatch.setattr(companions, "manner_line", lambda *a, **k: "")
    monkeypatch.setattr(companions, "shows_manner", lambda *a, **k: True)
    monkeypatch.setattr(views, "_told_by_its_blows", lambda resolution: False)
    agent = _agent(RESULT)
    views._run_npc_turns(fight, agent)
    beats = _creature_beats(fight)
    assert len(beats) == 1 and beats[0]["text"] == f"{WINDUP} {RESULT}"
    assert agent.shown == [WINDUP]


def test_a_told_turn_with_no_blow_drops_the_wind_up_too(fight, monkeypatch):
    """The planned lane's gap: a move-only turn still put the wind-up on the page, and
    once, mid-fight, that was a creature polishing glasses. Any turn the engine told is
    told from its tells; here the blow rule is switched off to stand in for a move."""
    from play import views

    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    monkeypatch.setattr(views, "_told_by_its_blows", lambda resolution: False)
    agent = _agent(RESULT)
    views._run_npc_turns(fight, agent)
    beats = _creature_beats(fight)
    assert [b["text"] for b in beats] == [RESULT] and agent.shown == [""]
