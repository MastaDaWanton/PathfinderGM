"""The prose records people; bodies come from the plan or from the player engaging them.

Ruled 2026-09-27, option (a) of the declared-not-guessed review. Measured before
choosing: in ordinary play the planner introduced nobody on its own (the town script),
so every background person came from the prose — and a hand check of that door found 11
of 30 booked people wrong: the "elder" out of "the elder-quarter" inside a quote, a
second old man booked beside the first, "man in a stained leather", a thug named
"weapon", a crowd as one person. A body is what turned a misread into a phantom in a
fight. So the prose's people become RECORDS (the user's earlier ruling: "there is nothing
left of her?" must be answered no), and a record becomes an actor when the plan
introduces them or the player turns to them.

In a fight the prose brings nobody new in: item 30's raiders are the plan's `spawn`,
and a newcomer only the prose describes is rewritten out.

Overturned in part on 2026-10-01 by the owner: somebody the prose SHOWS here and now is a
full person at once ("if i can see them they should be in the scene"). The misread risk
above is why that door caps a beat at three (tests/test_seen_people.py). Somebody only
spoken of stays a record. Who is shown and who only spoken of was read here by
`judgement.seen_in_beat`'s cue words until 2026-10-03; it is the beat reader's answer now
(gm/beat_reader.py), stubbed in these tests with what a careful reader says.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement
from rules import population
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def live(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("records")
        c.save()
        yield cm
        cm._LIVE.clear()


def _turn(cm, monkeypatch, beat, said="I look around."):
    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: Reply(
        json.dumps({"narration": beat, "suggestions": ["I wait"]}), 0.1, "stub"))
    r = Client().post("/api/say", data=json.dumps({"text": said}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    return cm.current()


def test_somebody_the_prose_shows_here_is_a_record_with_a_body(live, monkeypatch):
    """Overturned 2026-10-01 by the owner — "if i can see them they should be in the scene
    as a fully made person" — after the woman at the top of the stairs in Sam's save stayed
    prose and "the woman" was refused as an unknown ref. Seen here and now, she is ONE
    record and ONE body: the record holds her ref and her life, the body wears it
    (tests/test_seen_people.py has the rest)."""
    beat = ("The square is busy with the noon trade. A woman watching from a doorway "
            "follows you with her eyes and does not look away when you notice. " * 3
            + "What do you do?")
    from gm import beat_reader
    from tests.beat_reader import stub

    real_read = beat_reader.read

    def read(text, scene, **kw):
        # Every "A woman" of the beat as it stands after grooming: the first new and here,
        # the rest the same woman.
        n = stub._mention_ids(text, scene).get("a woman", [])
        who = {"A woman": "new", **{f"A woman#{i}": "same as A woman"
                                    for i in range(2, len(n) + 1)}}
        kw["chat"] = stub.chat(stub.people_answer(
            text, scene, who=who, new=[("A woman", "here", "woman watching from a doorway")]))
        return real_read(text, scene, **kw)

    monkeypatch.setattr(beat_reader, "read", read)
    c = _turn(live, monkeypatch, beat)
    her = [r for r in c.scene.population.values() if "woman" in r["phrase"]]
    assert len(her) == 1, [r["phrase"] for r in c.scene.population.values()]
    assert her[0]["ref"] in c.scene.actors
    assert [a.ref for a in c.scene.actors.values() if "woman" in a.name] == [her[0]["ref"]]


def test_turning_to_her_gives_her_a_body_before_the_plan():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    Engine(s, Dice(seed=1), world=WORLD).place_party()
    rec = population.note(s, "woman watching from a doorway")
    ref = judgement.embody_sought(s, "I talk to the woman in the doorway.", WORLD)
    assert ref and rec["ref"] == ref and ref in s.actors
    assert rec["life"]["face"] in s.actors[ref].appearance
    # Once: a second turn to her finds the body she has.
    assert judgement.embody_sought(s, "I talk to the woman in the doorway.", WORLD) == ""


def test_in_a_fight_a_newcomer_only_the_prose_brings_is_rewritten_out(monkeypatch):
    from gm import client as gm_client
    from gm.agent import GMAgent
    from gm.client import Reply

    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party()
    thug = instantiate("thug", scene=s, name="thug")
    s.add(thug)
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}],
                     origin="author:test"))
    calm = "The thug staggers and spits blood, and comes on again. What do you do?"
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: Reply(
        json.dumps({"narration": calm}), 0.1, "stub"))
    beat = "A band of twelve raiders pours through the gate behind him. What do you do?"
    text, note, _ = GMAgent(WORLD, e)._undeclared_arrivals(beat, [], {})
    assert text == calm and "rewritten" in note
    assert s.cast == [] or all("raider" not in c.get("who", "") for c in s.cast)


def test_out_of_a_fight_the_prose_may_describe_whoever_it_likes():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party()
    from gm.agent import GMAgent

    beat = "A guard runs up the lane, sword drawn, shouting for someone to stop."
    assert GMAgent(WORLD, e)._undeclared_arrivals(beat, [], {}) == (beat, "", [])
