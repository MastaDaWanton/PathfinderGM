"""The craft-action excursion, and the checks a declaration earns.

Two findings from the same play session. Foraging lived only on the bench page — a
button and a table, no narration, no time passing, no way back into the fiction. And
"I was able to sneak out of the tavern without a roll": the narrator narrated the
slipping-out and emitted `narrate_only`, the same shape as the 54-turn session where
nothing ever reached the engine.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement
from rules.engine import Scene
from rules.sheet import load_pc
from tests._places import stand_on


@pytest.fixture
def client(tmp_path, monkeypatch):
    from play import campaign as cm, craft_views

    # The model is deliberately absent: the excursion's contract is that narration is
    # decoration, and a model being down costs colour, never the herbs.
    monkeypatch.setattr(craft_views, "_narrate", lambda *a, **k: None)
    # The closing is the table's own narrator since the gathering door was shared
    # (`GMAgent.narrate_outcome`); absent here for the same reason.
    monkeypatch.setattr(craft_views, "_narrate_outcome", lambda *a, **k: "")
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        stand_on(c.scene, "forest")
        c.save()
        yield Client()
        cm._LIVE.clear()


def _forage(client, hours=2):
    """The excursion is two posts now: the first suspends on the player's own Survival
    check, the second carries the face back and gets the tally."""
    r = client.post("/api/craftaction",
                    data=json.dumps({"action": "forage", "hours": hours}),
                    content_type="application/json")
    if r.status_code != 200 or "roll" not in r.json():
        return r
    assert "Survival" in r.json()["roll"]["label"]
    return client.post("/api/craftaction", data=json.dumps({"face": "auto"}),
                       content_type="application/json")


def test_the_excursion_is_three_beats_and_a_question(client):
    """Opening, finding-with-tally, and "What do you do?" — the shape of a GM turn."""
    from play import campaign as cm

    before = len(cm.current().transcript)
    r = _forage(client)
    assert r.status_code == 200, r.json()
    book = cm.current().transcript[before:]
    assert len(book) == 3
    assert "satchel" in book[0]["text"] or "search" in book[0]["text"].lower()
    assert "Gathered:" in book[1]["text"]
    assert book[2]["text"] == "What do you do?"


def test_three_suggestions_always_arrive(client):
    """The model is down in this fixture, so these are the fallbacks — the player is
    never left without a next move."""
    d = _forage(client).json()
    assert len(d["suggestions"]) == 3
    from play import campaign as cm

    assert cm.current().suggestions == d["suggestions"]


def test_the_die_the_player_sees_is_a_die_the_engine_rolled(client):
    """Flaked twice before it was chased: a barren day rolls no d100 picks at all —
    only the hourly Survival checks — and the endpoint used to come back with an empty
    rolls list and nothing for the promised die to land on. The checks travel now, and
    one or the other must always be there."""
    d = _forage(client, hours=3).json()
    assert d["rolls"] or d["checks"], "nothing for the die to land on"
    assert all(1 <= r <= 100 for r in d["rolls"])
    assert all(c["roll"] >= 1 and c["dc"] > 0 for c in d["checks"])


def test_time_actually_passes(client):
    from play import campaign as cm

    before = cm.current().scene.clock_minutes
    _forage(client, hours=4)
    assert cm.current().scene.clock_minutes >= before + 4 * 60


def test_a_refused_forage_says_so_in_the_fiction_and_costs_nothing(client):
    """A busy forage is a refusal *outcome* now, not an IntentError — raising made the
    spoken path 502 after five doomed attempts, because the schema requires the very op
    the engine kept refusing. So the excursion narrates the refusal instead of
    unwriting the attempt: the character set out, was told why it cannot happen, and no
    time passed, no roll was asked for, and nothing landed in the satchel."""
    from play import campaign as cm
    from rules.bestiary import instantiate

    c = cm.current()
    c.scene.add(instantiate("thug", scene=c.scene, name="a road warden"))
    clock = c.scene.clock_minutes
    satchel = dict(c.scene.pc().inventory)
    r = _forage(client)
    assert r.status_code == 200
    d = r.json()
    assert "road warden" in d["tell"]
    assert d["found"] == []
    c = cm.current()
    assert c.scene.awaiting is None, "a refused forage still asked for a roll"
    assert c.scene.clock_minutes == clock
    assert dict(c.scene.pc().inventory) == satchel


def test_the_excursion_call_never_spends_its_budget_thinking(monkeypatch):
    """`_narrate` was the one chat call in the app without `think=False`. Measured on the
    owner's thinking model (gemma-4-12B): 140 of 140 tokens went to thinking, the content
    came back empty, and 4 of 4 excursion narrations fell to their template floors."""
    from gm import client as gm_client
    from play import craft_views

    seen = []

    class _Reply:
        text = "You set off."

        def json(self):
            return {"narration": "x"}

    def chat(*a, **k):
        seen.append(k)
        return _Reply()

    monkeypatch.setattr(gm_client, "chat", chat)
    cfg = {"model": "m", "host": "h"}
    craft_views._narrate([{"role": "user", "content": "x"}], cfg)
    craft_views._narrate([{"role": "user", "content": "x"}], cfg, as_json=True)
    craft_views._narrate([{"role": "user", "content": "x"}], cfg,
                         schema=craft_views._SCENE_SCHEMA)
    assert len(seen) == 3 and all(k.get("think") is False for k in seen), seen
    assert seen[2]["schema"] == craft_views._SCENE_SCHEMA


def test_the_opening_floor_names_where_the_party_stands_and_no_clock(client):
    """The floor said "work away from Ledgerwarren" while the party stood at the
    outskirts: it named the settlement, not the place. And the prompt was handed "day 1,
    17 hours in" — a number, to a narrator that must never write one."""
    from play import campaign as cm, craft_views

    c = cm.current()
    here = c.engine().here().name
    place, when = craft_views._forage_scene(c)
    assert place == here and not any(ch.isdigit() for ch in when), (place, when)
    before = len(c.transcript)
    _forage(client)
    opening = cm.current().transcript[before]["text"]
    assert here in opening and not any(ch.isdigit() for ch in opening), opening


def test_the_excursion_reaches_history_and_the_turn_log(client):
    """`craft_action` wrote only the transcript. Measured on the owner's save: history
    jumped from the outskirts arrival straight to "I aprouch the clockwork Spy", so the
    planner and narrator never knew a forage happened or that a creature was there."""
    from play import campaign as cm

    c = cm.current()
    hist, log = len(c.history), len(c.turn_log)
    assert _forage(client).status_code == 200
    c = cm.current()
    added = c.history[hist:]
    assert [m["role"] for m in added] == ["user", "assistant"], added
    assert "forages" in added[0]["content"] and added[1]["content"].strip()
    rows = [r for r in c.turn_log[log:] if r.get("door") == "excursion"]
    assert len(rows) == 1 and any(o["op"] == "forage" for o in rows[0]["outcomes"])


def _spy_turns_up(monkeypatch):
    from rules import bestiary, gathering

    spy = bestiary.search(text="clockwork spy", limit=1)[0]
    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "creature", 80, creature=spy, aggressive=False))


def test_a_creature_met_while_foraging_gets_its_scene_after_the_haul(client, monkeypatch):
    """The owner asked for an encounter found while foraging to get a call that sets the
    whole scene — a brass construct perched over the thicket, glass eye whirring, holding
    its ground. One grounded call, schema {narration}; the scene lands between the haul
    and the question, and the creature is in the history the planner reads."""
    from play import campaign as cm, craft_views

    _spy_turns_up(monkeypatch)
    calls = []
    good = ("Dusk settles over the slope, and the scree is going grey. Over the patch you "
            "were making for crouches a Clockwork Spy, brass plates ticking as it cools, "
            "its glass eye whirring as it settles on you. It does not come at you and it "
            "does not give way.")

    def narrate(messages, cfg, **k):
        calls.append(k)
        return {"narration": good} if k.get("schema") else None

    monkeypatch.setattr(craft_views, "_narrate", narrate)
    c = cm.current()
    before, hist = len(c.transcript), len(c.history)
    d = _forage(client).json()
    book = cm.current().transcript[before:]
    assert [b["text"] for b in book][-2:] == [good, "What do you do?"], book
    assert sum(1 for k in calls if k.get("schema")) == 1, "one scene call, no repair"
    assert d["scene"] == good
    assert "Clockwork Spy" in cm.current().history[-1]["content"]
    assert any("Approach" in s or "Spy" in s for s in d["suggestions"]), d["suggestions"]
    spy = next(a for a in cm.current().scene.actors.values() if a.name == "Clockwork Spy")
    assert spy.has_state("state.holding-ground")


def test_a_scene_that_has_it_attack_is_repaired_once_then_floored(client, monkeypatch):
    """Detect in code, repair with a targeted call: the creature as the subject of a blow
    or a departure, an invented name and a number are each found by code and named in
    the one repair; a second failure takes the floor, which says where it is and what it
    is doing — unlike "has the ground you wanted, and has not moved off it", which the
    owner could not parse."""
    from play import campaign as cm, craft_views

    _spy_turns_up(monkeypatch)
    bad = ("Three paces off, the Clockwork Spy lunges at you while Captain Veyrith "
           "watches from the rocks.")
    asked = []

    def narrate(messages, cfg, **k):
        if k.get("schema"):
            asked.append(messages[-1]["content"])
            return {"narration": bad}
        return None

    monkeypatch.setattr(craft_views, "_narrate", narrate)
    c = cm.current()
    before = len(c.transcript)
    d = _forage(client).json()
    assert len(asked) == 2, "the scene call and exactly one repair"
    assert "lunges" in asked[1] and "Veyrith" in asked[1] and "Three" in asked[1]
    scene = d["scene"]
    assert scene != bad and "has the ground you wanted" not in scene
    assert "Clockwork Spy" in scene and "does not come at you" in scene
    assert not any(ch.isdigit() for ch in scene)
    log = cm.current().turn_log[-1]
    assert log.get("door") == "excursion" and any("floor" in r for r in log["repairs"])


@pytest.mark.parametrize("text,found", [
    ("The Clockwork Spy lunges at you.", "lunges"),
    ("It suddenly bolts for the ridge.", "bolts"),
    ("The spy scuttles away into the scree.", "scuttles away"),
    ("Captain Veyrith's construct waits on the rock.", "Veyrith"),
    ("It has watched you for 3 hours.", "3"),
])
def test_the_scene_checks_find_each_defect(text, found):
    from play import craft_views

    row = {"creature_type": "construct", "subtype": "clockwork"}
    got = craft_views.scene_defects("Dusk falls. " + text, name="Clockwork Spy", row=row,
                                    known={"Clockwork Spy", "Sam"})
    assert any(found in g for g in got), got


def test_a_scene_that_keeps_it_still_passes_the_checks():
    """The owner's own example passes untouched: "neither attacks nor flees" and "does
    not come at you" are negations, not the creature acting."""
    from play import craft_views

    text = ("Over the thicket you were heading for perches a brass construct, a "
            "Clockwork Spy, its glass eye whirring and focusing on you. It does not come "
            "at you, and it neither attacks nor flees; it holds the thicket.")
    assert craft_views.scene_defects(
        text, name="Clockwork Spy", row={"creature_type": "construct"},
        known={"Clockwork Spy"}) == []


def test_the_bench_forage_is_untouched(client):
    """The bench keeps its own button: the excursion is an addition, not a move that
    breaks the shelf's forage-refresh loop."""
    r = client.post("/api/forage", data=json.dumps({"hours": 1}),
                    content_type="application/json")
    assert r.status_code == 200


# --- declared risky actions reach the dice ---------------------------------------------

def _scene():
    s = Scene(location_id="x")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


@pytest.mark.parametrize("said,skill", [
    ("I sneak out of the tavern", "stealth"),          # the reported sentence
    ("I try to sneak past the guard", "stealth"),
    ("I quietly slip out the back", "stealth"),
    ("I climb the courtyard wall", "climb"),
    ("I pick the lock on the strongbox", "disable device"),
    ("I lie to the innkeeper about my name", "bluff"),
    ("I search the room for the ledger", "perception"),
])
def test_a_declared_risky_action_earns_its_check(said, skill):
    # Somebody in the tavern: since 2026-09-30 Stealth is opposed by "anyone who might
    # notice you" (CRB p.106) and is not rolled with nobody there
    # (tests/test_slipping_out_rolls_stealth.py).
    from rules.bestiary import instantiate

    s = _scene()
    s.add(instantiate("thug", scene=s, name="the innkeeper"))
    out = judgement.inject_checks([{"op": "narrate_only"}], said, s)
    checks = [i for i in out if i.get("op") == "check"]
    assert checks and checks[0]["params"]["skill"] == skill


@pytest.mark.parametrize("said", [
    "Could I sneak out of the tavern?",        # a question is not a declaration
    "The sneak thief eyes my purse",           # no first-person verb
    "I walk out of the tavern",                # nothing risky
])
def test_ordinary_sentences_do_not_roll(said):
    out = judgement.inject_checks([{"op": "narrate_only"}], said, _scene())
    assert not [i for i in out if i.get("op") == "check"]


def test_a_turn_already_rolling_is_not_double_charged():
    """A plan that carries its own check, attack or save is a turn where the dice are
    already coming out; a second roll for the same sentence would punish the model for
    doing its job."""
    raw = [{"op": "check", "params": {"skill": "stealth"}}]
    out = judgement.inject_checks(raw, "I sneak out of the tavern", _scene())
    assert sum(1 for i in out if i.get("op") == "check") == 1
