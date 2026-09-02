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
    out = judgement.inject_checks([{"op": "narrate_only"}], said, _scene())
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
