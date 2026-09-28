"""Somebody else's first blow is declared in the plan and rolled before the prose.

docs/declared-not-guessed.md, the blows door (2026-09-25). Until now the only way an
NPC's blow at the player reached the dice was `attacked_by` reading it out of the
finished prose and `struck_first` rolling it afterwards — and that regex read "the
barmaid rushes over to you with a tankard" as a blow and opened a fight on her. A plan
could declare an NPC's attack, but the first-swing gate deferred the swing, so the blow
waited for the NPC loop — the wait the user refused: "I should be put into combat when I
am attacked, it shouldn't wait for me" (2026-09-18).
"""
from __future__ import annotations

import pytest

from gm import judgement, prompts
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def table():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party()
    thug = instantiate("thug", scene=s, name="big man by the bar")
    s.add(thug)
    return s, e, thug


def test_a_blow_the_plan_declares_is_rolled_before_the_prose(table):
    s, e, thug = table
    res = e.run(e.validate([{"op": "attack", "actor": thug.ref, "target": "pc",
                             "because": "he will not be laughed at"}]))
    assert s.in_encounter
    assert [o.op for o in res.outcomes] == ["attack", "attack"]
    assert "Battle is joined" in res.outcomes[0].tell
    assert thug.name in res.outcomes[1].tell and "Battle is joined" not in res.outcomes[1].tell


def test_the_players_own_first_swing_still_waits_for_their_dice(table):
    s, e, thug = table
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                             "because": "t"}]))
    assert [o.op for o in res.outcomes] == ["attack"]
    assert "Battle is joined" in res.outcomes[0].tell


def test_struck_first_is_one_blow_not_two(table):
    """It ran the attack twice by hand; `run` now rolls the initiator's blow itself, and
    two runs would have been two blows."""
    s, e, thug = table
    outs = e.struck_first(thug.ref)
    assert [o.op for o in outs] == ["attack", "attack"]
    assert sum("Battle is joined" not in o.tell for o in outs) == 1


def test_the_declared_weapon_is_the_one_rolled(table):
    s, e, thug = table
    thug.weapons = list(thug.weapons) + ["shortbow"]
    res = e.run(e.validate([{"op": "attack", "actor": thug.ref, "target": "pc",
                             "params": {"weapon": "shortbow"}, "because": "t"}]))
    assert res.outcomes[0].effects[0]["params"]["weapon"] == "shortbow"


def test_the_planner_is_shown_an_npc_striking_first():
    shown = [i for e in prompts.EXAMPLES for i in (e["reply"].get("intents") or [])]
    assert any(i["op"] == "attack" and i.get("actor") not in (None, "pc")
               and i.get("target") == "pc" for i in shown)


@pytest.mark.parametrize("said, drinks", [
    ("I knock the drink out of the biggest man's hand and laugh.", False),
    ("I buy him a drink.", False),
    ("I drink from my waterskin.", True),
    ("I have a drink at the bar.", True),
    ("I sit and drink.", True),
])
def test_the_drink_is_a_thing_until_the_player_drinks_it(said, drinks):
    """Measured live 2026-09-25: "I knock the drink out of the biggest man's hand"
    came back with "Kesst Vayr drinks." — the noun read as the player drinking."""
    assert judgement._drinks_declared(said) is drinks


# --- the prose door is a check now --------------------------------------------------

@pytest.fixture
def live(tmp_path):
    from django.test import override_settings

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("blows")
        c.save()
        yield cm, c
        cm._LIVE.clear()


def _say_with_prose(cm, monkeypatch, replies):
    """One turn through /api/say: a quiet plan, and the prose calls answered in turn."""
    import json

    from django.test import Client

    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    queue = list(replies)

    def chat(*a, **k):
        text = queue.pop(0) if len(queue) > 1 else queue[0]
        return Reply(json.dumps({"narration": text, "suggestions": ["I back off"]}), 0.1, "stub")

    monkeypatch.setattr(gm_client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": "I tell him he is all talk."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    return r.json()


def _blow_beat(c):
    """A striker the detector is known to read (tests/test_fight_from_either_side.py),
    put in the room — the opening's own companion may be "the old man ahead of you",
    whose name holds "you" and hides him from the striker search."""
    who = "man in the leather apron"
    from play import campaign as cm

    c = cm.current()            # the campaign the view will load, not the fixture's
    c.scene.add(instantiate("thug", scene=c.scene, name=who))
    c.save()
    pad = ("The room has gone quiet around the two of you, and somebody at the back sets "
           "a cup down very carefully so as not to be the one who made a sound. ")
    return who, (pad * 3 + f"The {who} lunges at you with the blade. "
                 "Everybody else steps back. What do you do?")


def test_a_blow_the_plan_never_declared_is_rewritten_not_rolled(live, monkeypatch):
    """Measured live 2026-09-25: the one blow the prose door read on the provoke script
    was "He doesn't reach for a weapon, but he slams a heavy, calloused fist onto the
    bar" — and it opened a fight. The door is a check now: one rewrite naming the fix."""
    cm, c = live
    who, beat = _blow_beat(c)
    calm = beat.replace(f"The {who} lunges at you with the blade.",
                        f"The {who} squares up to you, blade low, and does not move.")
    out = _say_with_prose(cm, monkeypatch, [beat, calm])
    shown = next(b for b in reversed(out["transcript"]) if b.get("who") == "gm")
    assert "squares up" in shown["text"] and "lunges" not in shown["text"]
    assert not cm.current().scene.in_encounter, "no fight opened on the prose's word"


def test_a_blow_the_rewrite_keeps_is_cut_and_still_opens_nothing(live, monkeypatch):
    cm, c = live
    who, beat = _blow_beat(c)
    out = _say_with_prose(cm, monkeypatch, [beat, beat])
    shown = next(b for b in reversed(out["transcript"]) if b.get("who") == "gm")
    assert "lunges at you" not in shown["text"]
    assert not cm.current().scene.in_encounter


def test_a_blow_by_somebody_the_prose_only_now_describes_is_checked_too(live, monkeypatch):
    """Nobody the scene holds: "a man in a stained coat" lunging at the player is a blow
    the plan never declared, from a striker the code cannot name — and it was the case
    the first version of the check let through."""
    cm, c = live
    pad = ("The room has gone quiet around the two of you, and somebody at the back sets "
           "a cup down very carefully so as not to be the one who made a sound. ")
    beat = pad * 3 + "Someone lunges at you from the crowd. What do you do?"
    out = _say_with_prose(cm, monkeypatch, [beat, beat])
    shown = next(b for b in reversed(out["transcript"]) if b.get("who") == "gm")
    assert "lunges at you" not in shown["text"]
    assert not cm.current().scene.in_encounter


def test_a_smith_at_his_forge_is_not_swinging_at_the_player():
    """Measured live 2026-09-27: "He stops mid-swing, the hammer hanging heavy in his
    grip…" — a contact verb and a weapon, and no player in the sentence — was read as a
    blow at the player and the check cut it. A weapon makes a swing a blow AT YOU only
    when you are in the sentence."""
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="smith"))
    forge = ("He stops mid-swing, the hammer hanging heavy in his grip, and the glowing rod "
             "he was shaping rests on the anvil with a dull hiss.")
    assert judgement.attacked_by(s, forge) == []
    assert judgement.attacked_by(s, "The smith swings the hammer at your head.")
