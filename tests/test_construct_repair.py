"""Mending a construct is a rule the engine resolves, and the page cannot claim it did.

The owner's report, 2026-10-01, playing Sam (a 1st-level wizard): after a Magic Missile
left a Clockwork Spy "unconscious and dying", the player wrote

    "I attempt to use my knowledge of engineering and my deft hands to fix the spy in a
    way that makes it recognize me as its owner."

The prose described a full repair and a machine recognising its new master; the engine
resolved nothing ("did not heal the clockwork spy when I fixed it"). The next turn — "I
greet my new friend and I name him Bob" — printed "Clockwork Spy has bled out where they
fell." beside "You have tamed the heart of the spy, and it now waits for your command."

The book: a construct is "immediately destroyed when reduced to 0 hit points or less"
(Bestiary), "a construct that has been completely destroyed cannot be repaired", and a
damaged one is repaired with the Craft Construct feat, 100 gp per Hit Die, a crafting
check at DC less 5, a day, 1d6 per Hit Die back (Ultimate Magic p.113). Nothing in 1e
makes a mended construct its mender's — it obeys its maker (`rules/repair.py`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gm import judgement
from gm.checks import BeatContext, registered, repair_claimed
from rules import repair
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

OWNERS_LINE = ("I attempt to use my knowledge of engineering and my deft hands to fix the "
               "spy in a way that makes it recognize me as its owner.")
OWNERS_NEXT_BEAT = ("You have tamed the heart of the spy, and it now waits for your "
                    "command.")


def _table(spy_hp: int = -1, *, feat: bool = False, gp: int = 300, seed: int = 1):
    scene = Scene(location_id=None)
    pc = scene.add(load_pc("fixtures/pc-thessaly.json"))
    pc.purse = {"gp": gp}
    if feat:
        pc.feats = [*pc.feats, "Craft Construct"]
    spy = scene.add(instantiate("clockwork-spy", scene=scene), zone="near")
    spy.hp = spy_hp
    spy.apply_hp_state()
    return scene, Engine(scene, Dice(seed)), pc, spy


def _repair(engine, ref, *, own=False, visibility="hidden"):
    raw = {"op": "repair", "actor": "pc", "target": ref, "visibility": visibility,
           "because": "test", "params": {"own": True} if own else {}}
    return engine.run(engine.validate([raw]))


# --- the words become the op ------------------------------------------------------------

def test_the_owners_words_declare_a_repair_on_the_spy_and_ask_to_own_it():
    """The owner's line, with the check the model dressed it as: the dressing is dropped
    and the `repair` op written, aimed at the spy, with `own` because the words asked."""
    scene, _engine, _pc, spy = _table()
    model = [{"op": "check", "actor": "pc",
              "params": {"skill": "knowledge (engineering)", "dc": {"band": "average"}}}]
    out = judgement.declare_repair(model, OWNERS_LINE, scene)
    assert out == [{"op": "repair", "actor": "pc", "target": spy.ref,
                    "because": "the player mends it; the rule decides whether it can be",
                    "params": {"own": True}}]


@pytest.mark.parametrize("line", [
    "I repair the clockwork spy.",
    "i try to patch the spy back up",
    "I put it back together.",
    "I tinker with the machine until I get it working again.",
])
def test_mending_words_at_the_only_machine_declare_a_repair(line):
    scene, _engine, _pc, spy = _table(2)
    out = judgement.declare_repair([], line, scene)
    assert [r["op"] for r in out] == ["repair"] and out[0]["target"] == spy.ref


@pytest.mark.parametrize("line", [
    "Can I fix the spy?",                         # a question
    "I search the wreckage for something useful.",  # no mending verb
    "\"I will fix you,\" I tell the spy.",        # speech, not action
])
def test_questions_speech_and_other_acts_declare_nothing(line):
    scene, _engine, _pc, _spy = _table()
    assert judgement.declare_repair([], line, scene) == []


def test_the_plan_chain_runs_the_declaration_beside_the_coup_de_grace():
    """One line in gm/agent.py's chain; without it the injector exists and is never
    asked — the dice rebuild's lesson (trace the real path first)."""
    src = (Path(__file__).resolve().parent.parent / "gm" / "agent.py").read_text(
        encoding="utf-8")
    assert "raw = judgement.declare_repair(raw, player_input, self.engine.scene)" in src


# --- the engine decides ----------------------------------------------------------------

def test_the_destroyed_spy_cannot_be_repaired_and_no_repair_makes_it_yours():
    """The owner's exact state: the spy at -1 is destroyed (no dying rung), so the
    repair is refused with the book's reason, nothing is rolled, charged or healed, and
    the ownership the words asked for is refused in the same tell."""
    scene, engine, pc, spy = _table(-1, feat=True)
    clock = scene.clock_minutes
    res = _repair(engine, spy.ref, own=True)
    (out,) = res.outcomes
    assert out.status == "refused" and out.rolls == []
    assert "completely destroyed cannot be repaired" in out.tell
    assert "does not make it yours" in out.tell
    assert spy.hp == -1 and spy.is_dead
    assert pc.purse == {"gp": 300} and scene.clock_minutes == clock


def test_without_craft_construct_a_wizard_cannot_mend_a_damaged_construct():
    """Sam's sheet: Knowledge ranks, no Craft Construct. The feat is the rule's gate."""
    _scene, engine, _pc, spy = _table(2)
    (out,) = _repair(engine, spy.ref).outcomes
    assert out.status == "refused" and "Craft Construct feat" in out.tell
    assert spy.hp == 2


def test_a_living_body_is_not_repaired():
    scene, engine, _pc, _spy = _table(2, feat=True)
    thug = scene.add(instantiate("thug", scene=scene), zone="near")
    thug.hp = 3
    (out,) = _repair(engine, thug.ref).outcomes
    assert out.status == "refused" and "not a construct" in out.tell


def test_a_repair_is_refused_short_of_the_coin():
    _scene, engine, pc, spy = _table(2, feat=True, gp=40)
    (out,) = _repair(engine, spy.ref).outcomes
    assert out.status == "refused" and "100 gp" in out.tell
    assert pc.purse == {"gp": 40}


def test_a_hostile_construct_still_working_is_not_repaired():
    """"Only while the construct is inanimate or nonfunctioning.\""""
    scene, engine, _pc, spy = _table(2, feat=True)
    engine._set_attitude(spy, "hostile", None, "test")
    (out,) = _repair(engine, spy.ref).outcomes
    assert out.status == "refused" and "inanimate or nonfunctioning" in out.tell


def test_a_made_repair_spends_the_day_and_the_coin_and_heals_by_the_rule():
    """Over a range of seeds both answers occur. Always: 100 gp per Hit Die spent and a
    day passed (the rule's order: spend, then check). On a success the hit points are
    the row's 1d6 per Hit Die through the heal applicator, stamped
    `rule:repair-construct`; on a failure nothing is healed."""
    seen = set()
    for seed in range(30):
        scene, engine, pc, spy = _table(1, feat=True, seed=seed)
        clock = scene.clock_minutes
        (out,) = _repair(engine, spy.ref).outcomes
        assert out.op == "repair" and out.dc["value"] == 15
        assert pc.purse == {"gp": 200}
        assert scene.clock_minutes - clock == 1440
        heals = [e for e in out.effects if e.get("kind") == "heal"]
        made = out.verdict == "success"
        seen.add(made)
        if made:
            assert heals and heals[0]["origin"] == f"rule:{repair.RULE}"
            assert 1 < spy.hp <= spy.hp_max
            assert "from repairing a construct" in out.tell
        else:
            assert not heals and spy.hp == 1
    assert seen == {True, False}


def test_a_player_rolled_repair_charges_nothing_until_the_die_is_in():
    """The player rolls their own Craft; while the engine waits for the die, no coin has
    moved and no day has passed — so a resumed roll is not charged twice."""
    scene, engine, pc, spy = _table(1, feat=True)
    clock = scene.clock_minutes
    res = _repair(engine, spy.ref, visibility="player")
    assert res.awaiting and res.awaiting["dc"] == 15
    assert pc.purse == {"gp": 300} and scene.clock_minutes == clock
    res2 = engine.resume(20)
    (out,) = [o for o in res2.outcomes if o.op == "repair"]
    assert out.verdict == "success" and pc.purse == {"gp": 200}


# --- the page cannot claim it ----------------------------------------------------------

def _ctx(engine, text, outcomes=(), door="turn"):
    return BeatContext(
        door=door, text=text, player_text=OWNERS_LINE, engine=engine, scene=engine.scene,
        world=None, location=None, reading=None, outcomes=tuple(outcomes), tells=(),
        said=(), attribution=None, brief="", brief_facts={}, pull=None, was_at="",
        acting="", turn=0)


def test_the_check_is_registered():
    assert repair_claimed in registered()


def test_the_owners_tamed_sentence_is_flagged_and_cut():
    """The owner's next beat. Nothing granted the spy to the player; the backstop cuts the
    sentence and ends on the engine's fact."""
    _scene, engine, _pc, _spy = _table(-1)
    (found,) = repair_claimed.find(_ctx(engine, OWNERS_NEXT_BEAT))
    assert found.kind == "ownership-claimed"
    assert found.sentences == (OWNERS_NEXT_BEAT,)
    text, notes = repair_claimed.backstop(_ctx(engine, OWNERS_NEXT_BEAT),
                                          OWNERS_NEXT_BEAT, [found])
    assert "waits for your command" not in text and notes
    assert "destroyed" in text and "answers to its maker" in text


def test_a_repair_the_engine_did_not_resolve_is_flagged():
    _scene, engine, _pc, _spy = _table(-1)
    beat = ("You work the bent spring loose and reseat the gears. The spy whirs back to "
            "life, its lenses turning toward you.")
    kinds = {f.kind for f in repair_claimed.find(_ctx(engine, beat))}
    assert kinds == {"repair-claimed"}


def test_a_repair_the_engine_resolved_may_be_told():
    """After a made repair, "it whirs back to life" is the truth; the ownership half is
    still nobody's to grant."""
    scene, engine, _pc, spy = _table(1, feat=True, seed=3)
    res = _repair(engine, spy.ref)
    for seed in range(3, 40):
        if res.outcomes[0].verdict == "success":
            break
        scene, engine, _pc, spy = _table(1, feat=True, seed=seed)
        res = _repair(engine, spy.ref)
    assert res.outcomes[0].verdict == "success"
    beat = "The spy whirs back to life. It recognizes you as its new master."
    kinds = [f.kind for f in repair_claimed.find(_ctx(engine, beat, res.outcomes))]
    assert kinds == ["ownership-claimed"]


@pytest.mark.parametrize("sentence", [
    "The spy is beyond repair.",
    "You try to repair it, but the mainspring is snapped.",
    "It will never obey you.",
    "Its lenses stay fixed on you.",
    "The spy lies in pieces, its gears scattered across the rock.",
])
def test_denials_attempts_and_stillness_are_not_claims(sentence):
    assert not repair_claimed.mends(sentence) and not repair_claimed.owns(sentence)
