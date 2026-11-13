"""An op's own list of effects finishes inside the op, even when it stops for the player.

The defect, measured 2026-10-02 on `ui/table-v2` (21f9193) while fixing poison save gates:
`_op_use_item` and `_deliver_coating` resolved the effects they produced with `self.run`,
the batch's own entry point, from INSIDE an op. A hemlock jar drunk by the PC put a
Fortitude save on the player's own d20, so the inner batch suspended — it wrote the
scene's pending queue and set `scene.awaiting` — and the op ignored that. The drink's
outcome was built as if finished ("Kesst Vayr drinks Hemlock Tincture.", no save in it),
and the OUTER batch returned `status == "complete"` with `awaiting is None` while
`scene.awaiting` said "Fortitude save". Measured, each consequence:

1. An NPC's Perception check queued behind the drink resolved while the save waited.
2. A PC check queued behind it suspended the outer batch too, overwrote the frozen queue
   with `[check]`, and the save, its paralysis, and the jar's other two effects were gone:
   after the resume the PC was not paralysed and no save had been rolled.
3. The world's schemes ticked with the save still on the table (`_tick_schemes` read the
   resolution, not the scene): one tick, `scene.awaiting` set at the time. And a healing
   draught that never stopped ticked them twice in one batch — once inside the op's
   nested `run`, once after the batch.
4. The player-turn view reads the resolution too: `/api/say` made 3 prose calls and wrote
   "You drink it and feel fine" BEFORE the save was rolled; the roll then landed the
   paralysis under it.

And one the brief did not list: every nested `run` reset the batch's own gates mid-batch.
A drink resolved after the turn's journey set `_journeyed` back to "", so the one-journey-
a-turn rule forgot the journey.

The fix is `Engine._run_within`: the inner list's frozen queue is parked in the op's own
state (`use_item_state`, the attack's `attack_state`) and the op suspends, so the outer
queue freezes with the op at its head and the resume re-enters it — the shape
`_roll_or_suspend_stage` already gave every multi-stage op.
"""
from __future__ import annotations

import json

import pytest

from rules import consumables
from rules import ingredients as ing_mod
from rules import schemes as schemes_mod
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._board import face_to_face


def _from(source: str, specs: list[dict]) -> list[dict]:
    return [dict(s, **{"from": source}) for s in specs]


HEMLOCK = _from("Hemlock", ing_mod.get("hemlock").specs)


@pytest.fixture
def board():
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the beast"))
    pc.stock["hemlock#1"] = Stock(base="Hemlock Tincture", count=3, specs=list(HEMLOCK))
    e = Engine(s, Dice(seed=9))
    face_to_face(s)
    return s, e


def drink(item="hemlock#1"):
    return {"op": "use_item", "actor": "pc", "because": "she drinks it",
            "params": {"item": item, "how": "drink"}}


def through_the_file(scene):
    """The frozen batch as the campaign file holds it between two requests."""
    scene.pending_intents = json.loads(json.dumps(scene.pending_intents))
    scene.pending_outcomes = json.loads(json.dumps(scene.pending_outcomes))
    scene.pending_partial = json.loads(json.dumps(scene.pending_partial))


def tells(res):
    return " ".join(o.tell for o in res.outcomes)


# --- the batch waits ------------------------------------------------------------------------

def test_the_batch_says_it_is_waiting_when_the_scene_is(board):
    """Measured: `status == "complete"`, `awaiting is None`, `scene.awaiting` "Fortitude
    save" — the resolution and the scene disagreed about whether the turn was over."""
    scene, engine = board
    res = engine.run(engine.validate([drink()]))
    assert scene.awaiting and scene.awaiting["label"] == "Fortitude save"
    assert res.status == "awaiting_player_roll"
    assert res.awaiting == scene.awaiting
    assert [i["op"] for i in scene.pending_intents] == ["use_item"]


def test_what_follows_the_drink_waits_for_its_save(board):
    """Measured: the beast's Perception check behind the drink resolved while the save
    waited ("the beast makes the perception check by 9")."""
    scene, engine = board
    res = engine.run(engine.validate([
        drink(), {"op": "check", "actor": "c1", "because": "t",
                  "params": {"skill": "perception", "dc": 10}}]))
    assert res.awaiting and not res.outcomes
    assert not any(o.get("op") == "check" for o in scene.log)
    through_the_file(scene)
    res = engine.resume(face=1)
    assert res.status == "complete"
    assert [o.op for o in res.outcomes] == ["use_item", "check"]
    assert "Fortitude save" in res.outcomes[0].tell


def test_a_second_roll_in_the_batch_does_not_lose_the_poison(board):
    """Measured: drink, then the PC's own Perception check. The check suspended the
    outer batch and overwrote the frozen queue with `[check]`; after the resume no save
    had been rolled and the PC was not paralysed — the jar's whole list was gone."""
    scene, engine = board
    res = engine.run(engine.validate([
        drink(), {"op": "check", "actor": "pc", "because": "t",
                  "params": {"skill": "perception", "dc": 10}}]))
    assert res.awaiting["label"] == "Fortitude save", "the drink's save comes first"
    through_the_file(scene)
    res = engine.resume(face=1)
    assert scene.pc().has_condition("paralyzed")
    assert res.awaiting and res.awaiting["label"].startswith("Perception")
    through_the_file(scene)
    res = engine.resume(face=10)
    assert res.status == "complete" and not scene.awaiting
    assert [o.op for o in res.outcomes] == ["use_item", "check"]
    assert "fails the Fortitude save" in res.outcomes[0].tell


def test_two_saves_in_one_jar_each_wait_for_the_player(board):
    """Hemlock and dragon flower in one jar: two Fortitude saves, both the drinker's, so
    the drink stops twice and carries its list across both popups."""
    scene, engine = board
    scene.pc().stock["brew#1"] = Stock(
        base="Witch's Brew", count=1,
        specs=list(HEMLOCK) + _from("Dragon Flower", ing_mod.get("dragon-flower").specs))
    res = engine.run(engine.validate([drink("brew#1")]))
    rolled = 0
    while res.awaiting:
        assert res.awaiting["label"] == "Fortitude save"
        through_the_file(scene)
        res = engine.resume(face=1)
        rolled += 1
    assert rolled == 2
    assert tells(res).count("Fortitude save") == 2
    assert [o.op for o in res.outcomes] == ["use_item"]


def test_the_last_dose_is_not_asked_for_again_on_the_resume(board):
    """The resume re-enters the op; the satchel check above the delivery must not run
    twice, or the last jar would be refused as "not carrying" on its own save."""
    scene, engine = board
    scene.pc().stock["hemlock#1"].count = 1
    engine.run(engine.validate([drink()]))
    assert "hemlock#1" not in scene.pc().stock
    through_the_file(scene)
    res = engine.resume(face=1)
    assert res.outcomes[0].status == "resolved", res.outcomes[0].tell
    assert scene.pc().has_condition("paralyzed")


# --- the world waits ------------------------------------------------------------------------

def test_the_schemes_do_not_tick_while_the_save_waits(board, monkeypatch):
    """Measured: one scheme tick ran with `scene.awaiting` set. And a drink that never
    stopped ticked them twice — once inside the op's nested batch, once after."""
    scene, engine = board
    seen: list[bool] = []
    real = schemes_mod.tick

    def spy(eng, outcomes):
        seen.append(bool(eng.scene.awaiting))
        return real(eng, outcomes)

    monkeypatch.setattr(schemes_mod, "tick", spy)
    engine.run(engine.validate([drink()]))
    assert seen == []
    engine.resume(face=1)
    assert seen == [False]

    seen.clear()
    scene.pc().stock["heal#1"] = Stock(base="Healing Draught", count=1,
                                       specs=[{"type": "heal", "dice": "1d8"}])
    engine.run(engine.validate([drink("heal#1")]))
    assert seen == [False], "one batch, one tick"


def test_a_drink_does_not_reset_the_turns_journey(board):
    """Measured: `_journeyed` was "Somewhere" before a drink resolved and "" after —
    the nested `run` reset the batch's one-journey-a-turn gate mid-batch."""
    scene, engine = board
    scene.pc().stock["heal#1"] = Stock(base="Healing Draught", count=1,
                                       specs=[{"type": "heal", "dice": "1d8"}])
    engine._journeyed = "Somewhere"
    engine._resolve_one(engine.validate([drink("heal#1")])[0], {})
    assert engine._journeyed == "Somewhere"


# --- the blade ------------------------------------------------------------------------------

def _coated_beast_strikes(scene, engine, face):
    beast = scene.actors["c1"]
    beast.coating = consumables.Coating(item="Hemlock Tincture", weapon="dagger",
                                        specs=list(HEMLOCK)).as_dict()
    engine._ensure_encounter("c1", "pc")
    face_to_face(scene)
    rolled = engine.dice.roll

    def roll(notation, modifiers=None, label="", visibility="player"):
        if label.startswith("Attack with"):
            return engine.dice.given_total(face, notation, modifiers or [], label=label)
        return rolled(notation, modifiers, label=label, visibility=visibility)

    engine.dice.roll = roll
    return engine.run(engine.validate([
        {"op": "attack", "actor": "c1", "target": "pc", "because": "he cuts",
         "params": {"weapon": "dagger", "full_attack": False}}]))


def test_a_poisoned_blade_on_the_pc_waits_for_their_save_inside_the_blow(board):
    """The beast's coated dagger finds the PC: the poison's save is the PC's own d20, so
    the blow stops at it, and the resume finishes the SAME blow — the damage is not
    rolled again (the save's face would have been taken as the damage die)."""
    scene, engine = board
    pc = scene.pc()
    before = pc.hp
    res = _coated_beast_strikes(scene, engine, 18)
    assert res.awaiting and res.awaiting["label"] == "Fortitude save"
    assert [i["op"] for i in scene.pending_intents][:1] == ["attack"]
    assert pc.hp < before, "the wound landed before the dose"
    through_the_file(scene)
    res = engine.resume(face=1)
    assert res.status == "complete"
    assert pc.has_condition("paralyzed")
    blow = next(o for o in res.outcomes if o.op == "attack")
    assert "goes into the wound" in blow.tell and "Fortitude save" in blow.tell
    # One wound, one damage die: hemlock also carries a 1d4 heal, so hit points cannot
    # say whether the resume struck twice, and the blow's own record can.
    assert sum(r.label.startswith("Damage") for r in blow.rolls) == 1
    assert sum(e.get("kind") == "damage" and e.get("weapon") is not None
               for e in blow.effects) == 1


# --- the engine's own lists -----------------------------------------------------------------

def test_a_list_the_engine_rolls_that_stops_anyway_is_refused_not_left_hanging(board):
    """A race's rider, a stat block's drain, a taste: their lists are hidden, and have no
    state to park in. Should one ever stop for a die, the scene is not left awaiting a
    roll the op will never come back for."""
    scene, engine = board
    planted = engine.validate([{"op": "save", "actor": "pc", "because": "t",
                                "params": {"save": "fort", "dc": {"value": 15}}}],
                              origin="author:test", origin_name="the test")
    with pytest.raises(IntentError, match="engine rolls itself"):
        engine._run_within(planted, {})
    assert not scene.awaiting and not scene.pending_intents


# --- the table ------------------------------------------------------------------------------

@pytest.fixture
def live(tmp_path):
    from django.test import override_settings

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.current("inner-lists")
        c.save()
        yield cm
        cm._LIVE.clear()


def test_the_page_writes_no_prose_until_the_save_is_rolled(live, monkeypatch):
    """Measured through `/api/say`: 3 prose calls and "You drink it and feel fine" before
    the Fortitude save was rolled. Now the turn stops at the popup, and the prose the
    roll writes is handed the save."""
    from django.test import Client

    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    cm = live
    c = cm.current()
    c.scene.pc().stock["hemlock#1"] = Stock(base="Hemlock Tincture", count=3,
                                            specs=list(HEMLOCK))
    c.save()

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate([drink()]))

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    asked: list[str] = []

    def chat(*a, **k):
        asked.append(json.dumps([a, k], default=str))
        return Reply(json.dumps({"narration": "The tincture goes down bitter.",
                                 "suggestions": ["I wait"]}), 0.1, "stub")

    monkeypatch.setattr(gm_client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": "I drink the hemlock."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    assert r.json()["awaiting"]["label"] == "Fortitude save"
    assert asked == [], "no prose is written over a die still on the table"

    r = Client().post("/api/roll", data=json.dumps({"face": 1}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    assert cm.current().scene.pc().has_condition("paralyzed")
    assert not cm.current().scene.awaiting
    assert asked and any("fails the Fortitude save" in m for m in asked)
