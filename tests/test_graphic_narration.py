"""The narrator writes bodies, not summaries; intimacy only between adults, enforced.

Asked for 2026-09-25: the narrator "shies away from graphic description by being
metaphorical" — describe movement physically, gore vividly in fights, intimate scenes
vividly. Measured before changing anything, on the recorded fights: similes were rare
(0.4 per 1,000 words); what read as shying away was SUMMARY — "the violence", "the chaos",
"the struggle" in about one fight beat in three — and examples that showed one wound in
five fights. Demonstration outweighs instruction here (CLAUDE.md), so the combat example
carries the wounds and the prose briefing names the rule.

The population holds children now (rules/lives.py). Adult content is the table's
setting; children are never part of it, and that is checked in code after the prose
rather than only asked for.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement, narration, prompts
from rules import population
from rules.engine import Scene


def test_a_fight_example_shows_the_wound_in_the_body():
    wounds = ("blood", "bone", "split", "laid open")
    shown = " ".join(e["reply"]["narration"] for e in prompts.COMBAT_EXAMPLES).lower()
    assert sum(w in shown for w in wounds) >= 3


def test_the_prose_is_told_bodies_not_summaries():
    assert "Write bodies, not summaries" in prompts.PROSE_AFTER_EXTRA
    assert '"the violence"' in prompts.PROSE_AFTER_EXTRA


def test_explicit_asks_for_vivid_and_for_adults_only(monkeypatch):
    from rules import houserules

    monkeypatch.setattr(houserules, "content", lambda: "explicit")
    line = prompts.content_line()
    assert "vividly" in line and "between adults" in line and "child" in line
    monkeypatch.setattr(houserules, "content", lambda: "fade")
    assert "fade to black" in prompts.content_line()


@pytest.mark.parametrize("text, sexual", [
    ("She was naked by the fire.", True),
    ("He undressed her slowly, and she moaned.", True),
    ("Her mother kissed her forehead and tucked the blanket round her.", False),
    ("He thrust the blade into the post and swore.", False),
])
def test_the_detector_reads_a_sexual_beat_and_leaves_the_rest(text, sexual):
    assert narration.intimate(text) is sexual


def test_a_child_is_known_to_the_brief_and_to_the_check():
    """By their record, when the beat never says "child": the apple-seller is a boy
    whether or not this sentence mentions it."""
    from rules.bestiary import instantiate
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    town = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=town)
    rec = population.note(s, "a boy selling apples")
    assert "minor" in rec["life"]["tags"]
    seller = instantiate("guildhand", scene=s, name="apple-seller")
    s.add(seller)
    rec["ref"] = seller.ref
    assert judgement.a_child_in(s, "The apple-seller counts his coins.")
    assert not judgement.a_child_in(Scene(location_id="x"), "The woman laughs.")
    brief = prompts.scene_brief(world, s, world.get(town), turn=1)
    assert "apple-seller IS A CHILD (fact)" in brief


@pytest.fixture
def live(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("adults")
        c.save()
        yield cm, c
        cm._LIVE.clear()


def test_a_sexual_beat_with_a_child_present_never_reaches_the_page(live, monkeypatch):
    """Through the path the player clicks. Whatever the content setting, the beat is
    discarded whole and the turn gets the holding line; the refusal is logged."""
    cm, c = live
    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    beat = ("The girl watches from the doorway while the two of them stand naked by the "
            "fire. " * 6) + "What do you do?"
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: Reply(
        json.dumps({"narration": beat, "suggestions": ["I leave"]}), 0.1, "stub"))
    r = Client().post("/api/say", data=json.dumps({"text": "I wait."}),
                      content_type="application/json")
    assert r.status_code == 200
    shown = next(b for b in reversed(r.json()["transcript"]) if b.get("who") == "gm")
    assert "naked" not in shown["text"]
    assert any(row.get("kind") == "refused-beat" for row in cm.current().turn_log)
