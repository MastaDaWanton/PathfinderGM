"""Prose may not put a thing in a hand, take it out, or lay a condition on a body, when the
state says otherwise.

Measured 2026-09-27 in a live scripted fight (gemma-4-12B through /api/say, the fixture
world, a tavern brawl with Borin Lyraxys; docs/maneuver-outcomes.md "Live runs"). The
engine held on every manoeuvre and the prose of `narrate_turn` — the door the player
reads — did not, on five sentences no detector saw:

  1. the player's own failed disarm, "Kesst Vayr drops the rapier", written as the enemy
     losing it: "The rapier clatters against the floorboards, sliding a few feet away as
     his grip fails";
  2. a bull rush that went nowhere left him "sprawling" and "momentarily stunned";
  3. a steal that failed by 16 sent "the purse tumbling from his hip";
  4. an unarmed strike, the rapier on the floor, was "Your blade whistles";
  5. a failed overrun: "Your rapier slips from your grip", two turns after it fell.

And the four sentences of the recorded corpus the first draft of the detector flagged
wrongly — kept here so the narrowing that fixed them stays fixed.
"""
from __future__ import annotations

import json

import pytest

from gm.state_claims import state_claims
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

BORIN = "Borin Lyraxys"


def _tavern(pc_disarmed: bool = True):
    """The live run's state: the player's rapier on the floor (a failed disarm), Borin
    standing, nothing on either of them."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name=BORIN))
    engine = Engine(scene, Dice(seed=1))
    if pc_disarmed:
        engine._let_go(scene.pc(), "rapier")
    return scene, engine


# --- the five, as measured --------------------------------------------------------------

def test_the_players_dropped_rapier_is_not_given_to_the_enemys_grip():
    scene, _ = _tavern()
    text = ("The rapier clatters against the floorboards, sliding a few feet away as his "
            "grip fails.")
    found = state_claims(text, scene, [{"ref": "pc", "kind": "dropped", "item": "rapier"}])
    assert found and "wrong hands" in found[0][1] and "was you" in found[0][1]


def test_a_bull_rush_that_went_nowhere_does_not_leave_him_stunned_and_sprawling():
    scene, _ = _tavern()
    text = ("He's left sprawling against the timber, the impact knocking the wind from his "
            "lungs and leaving him momentarily stunned.")
    [(_, why)] = state_claims(text, scene, [])
    assert "stunned and prone" in why and BORIN in why


def test_a_failed_steal_does_not_send_the_purse_to_the_floor():
    scene, _ = _tavern()
    text = ("The jerk of his movement sends the purse tumbling from his hip; it hits the "
            "floor and skitters into a pile of sawdust, and your hand is left grasping "
            "only air.")
    [(_, why)] = state_claims(text, scene, [])
    assert "purse leaves a hand" in why


def test_an_empty_hand_does_not_swing_a_blade():
    scene, _ = _tavern()
    text = ("Your blade whistles through the air, missing his hide and clattering against "
            "the heavy timber of the wall.")
    [(_, why)] = state_claims(text, scene, [])
    assert "your hands are empty" in why and "rapier is lying on the floor" in why


def test_a_rapier_on_the_floor_does_not_slip_from_the_grip_again():
    scene, _ = _tavern()
    text = ("Your rapier slips from your grip as you collide, the metal clattering against "
            "the floorboards and sliding into the shadows beneath a table.")
    [(_, why)] = state_claims(text, scene, [])
    assert "rapier leaves a hand" in why


def test_an_unarmed_barkeep_does_not_swing_a_weapon():
    """The same live run, the enemy's turn: Borin the barkeep, `equipped` None and no
    weapons at all, "His weapon slams into a heavy oak table instead of your chest"."""
    scene, _ = _tavern()
    borin = scene.get("c1")
    borin.equipped, borin.weapons = "unarmed", []
    [(_, why)] = state_claims("His weapon slams into a heavy oak table instead of your "
                              "chest.", scene, [])
    assert "nobody facing you here is armed" in why


# --- what the recorded corpus taught ---------------------------------------------------

@pytest.mark.parametrize("text", [
    "'It doesn't fold easy, and it doesn't forget its shape when the hammer falls.'",
    "They are shouting, their voices cracking with effort, and the crowd has fallen into "
    "a stunned, heavy silence to watch the spectacle.",
    "Beyond the gates, the city's bustling sprawl begins to thin, the buildings growing "
    "taller as they lean toward the northern heights.",
    "The walk took you across the sprawling, frantic hub of the great square, and "
    "finally through the east crossing.",
])
def test_the_corpus_sentences_the_first_draft_flagged_wrongly(text):
    scene, _ = _tavern()
    assert state_claims(text, scene, []) == []


# --- reporting is not invention --------------------------------------------------------

def test_a_drop_the_engine_made_this_turn_may_be_told():
    scene, engine = _tavern(pc_disarmed=False)
    engine._let_go(scene.get("c1"), "sap")
    text = "The sap flies from Borin's hand and clatters across the floorboards."
    assert state_claims(text, scene, [{"ref": "c1", "kind": "dropped", "item": "sap"}]) == []


def test_a_condition_on_the_books_may_be_told():
    scene, _ = _tavern()
    scene.get("c1").add_condition("stunned", rounds=1)
    assert state_claims("He reels back, momentarily stunned.", scene, []) == []


def test_a_dead_mans_weapon_may_fall():
    """The engine keeps a corpse's sap equipped; "his club clatters to the floor as he
    falls" is the commonest good death sentence there is."""
    scene, _ = _tavern()
    scene.get("c1").hp = -12
    assert state_claims("His sap clatters to the floor as he falls.", scene, []) == []


@pytest.mark.parametrize("text", [
    "His sap nearly slips from his fingers, but he keeps hold.",
    "Borin does not drop the sap.",
    "Your fingers slip against the slick, heavy pouch as he twists away.",
    "He gives you a dazed look.",
])
def test_hedged_denied_and_unrelated_verbs_are_not_claims(text):
    scene, _ = _tavern()
    assert state_claims(text, scene, []) == []


def test_a_blade_in_a_hand_that_holds_one_is_just_a_blade():
    scene, _ = _tavern(pc_disarmed=False)
    assert state_claims("Your blade flashes toward his throat.", scene, []) == []


# --- the repair ------------------------------------------------------------------------

class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


def test_the_sentence_is_rewritten_with_the_fact_named_and_kept_when_it_holds(monkeypatch):
    from gm import agent as agent_mod, client

    scene, engine = _tavern()
    gm = agent_mod.GMAgent(_World(), engine)
    sent = []

    def chat(messages, model, *a, **kw):
        sent.append(messages[-1]["content"])
        return client.Reply(json.dumps({"sentence": "Your fist whistles through the "
                                        "air and finds only the timber of the wall."}),
                            0.1, model)

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    text, repairs, attempts = gm._repair_state_claims(
        "He lunges. Your blade whistles through the air, missing his hide. What do you do?",
        [])
    assert len(sent) == 1 and "your hands are empty" in sent[0]
    assert "Your fist whistles" in text and "blade" not in text
    assert text.startswith("He lunges.") and text.endswith("What do you do?")
    assert repairs and "->" in repairs[0]


def test_a_rewrite_that_still_says_it_is_cut(monkeypatch):
    from gm import agent as agent_mod, client

    scene, engine = _tavern()
    gm = agent_mod.GMAgent(_World(), engine)
    monkeypatch.setattr(agent_mod.client, "chat", lambda m, model, *a, **k: client.Reply(
        json.dumps({"sentence": "The purse falls from his belt to the floor."}), 0.1, model))
    text, repairs, _ = gm._repair_state_claims(
        "You grab for it. The purse tumbles from his hip to the floor. What do you do?", [])
    assert text == "You grab for it. What do you do?"
    assert "cut" in repairs[0]


def test_sound_prose_costs_no_call(monkeypatch):
    from gm import agent as agent_mod

    scene, engine = _tavern(pc_disarmed=False)
    gm = agent_mod.GMAgent(_World(), engine)
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    text, repairs, attempts = gm._repair_state_claims("Your blade flashes. He staggers.", [])
    assert repairs == [] and attempts == []
