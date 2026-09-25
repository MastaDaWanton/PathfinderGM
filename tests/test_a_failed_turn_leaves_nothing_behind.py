"""A request that fails half-way leaves no half-applied game behind it.

Measured 2026-09-25: the turn's rollback restored the scene only on IntentError,
ValueError and KeyError, and the campaign stays in memory between requests — so any
other exception after the engine had run (a TypeError in `_finish`, an IndexError in an
NPC turn) left mechanics and history applied in memory, and the next turn that succeeded
saved them. And a turn the model could not plan (503) had already moved the player's
free actions into the history and emptied the list that carries them.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings


@pytest.fixture
def live(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("crash")
        c.save()
        yield cm, c
        cm._LIVE.clear()


def test_a_crash_after_the_engine_ran_is_not_saved_by_the_next_turn(live, monkeypatch):
    cm, c = live
    from play import views

    before = json.loads(c.path().read_text(encoding="utf-8"))
    pc = c.scene.pc()
    hp = pc.hp

    def half_applied_then_crash(camp, *a, **kw):
        # The engine has changed the game in memory; then something unexpected breaks.
        camp.scene.pc().hp = hp - 5
        camp.transcript.append({"who": "gm", "text": "A beat that never finished."})
        raise TypeError("an unexpected failure after resolution")

    monkeypatch.setattr(views, "_finish", lambda c_, *a, **kw: half_applied_then_crash(c_))
    monkeypatch.setattr(views, "_advance",
                        lambda c_, *a, **kw: half_applied_then_crash(c_))

    class Plan:
        narration = ""
        intents = []
        suggestions = []
        repairs = []

    monkeypatch.setattr(views.GMAgent, "plan_turn", lambda *a, **kw: Plan())
    client = Client(raise_request_exception=False)
    r = client.post("/api/say", data=json.dumps({"text": "I look around."}),
                    content_type="application/json")
    assert r.status_code == 500
    assert "not saved" in r.json()["error"], "the page is told, in words"

    # The memory copy is gone; the next read is the save, not the half-applied game.
    again = cm.current("crash")
    assert again is not c
    assert again.scene.pc().hp == hp
    assert len(again.transcript) == len(before["transcript"])


def test_a_turn_the_model_could_not_plan_keeps_the_free_actions(live, monkeypatch):
    cm, c = live
    from gm.client import ModelUnavailable
    from play import views

    c.pending_free = ["formed the blood armament"]
    history_before = list(c.history)

    def down(*a, **kw):
        raise ModelUnavailable("Ollama is not running")

    monkeypatch.setattr(views.GMAgent, "plan_turn", down)
    r = Client().post("/api/say", data=json.dumps({"text": "I look around."}),
                      content_type="application/json")
    assert r.status_code == 503
    c = cm.current("crash")
    assert c.pending_free == ["formed the blood armament"]
    assert c.history == history_before
