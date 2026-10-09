"""Mending a construct, and claiming it, are rules the engine resolves (house rule).

The owner's report, 2026-10-01, playing Sam (a 1st-level wizard): after a Magic Missile
left a Clockwork Spy "unconscious and dying", the player wrote

    "I attempt to use my knowledge of engineering and my deft hands to fix the spy in a
    way that makes it recognize me as its owner."

The prose described a full repair and a machine recognising its new master; the engine
resolved nothing ("did not heal the clockwork spy when I fixed it"). The next turn — "I
greet my new friend and I name him Bob" — printed "Clockwork Spy has bled out where they
fell." beside "You have tamed the heart of the spy, and it now waits for your command."

The owner's HOUSE RULE for it, verbatim: "Broken, then fixable and claimable — House rule:
a construct at 0 to -10 is broken, not destroyed (destroyed only past that). Anyone with
the skill can mend it with a Craft or Knowledge (engineering) check, which heals it. A
second, harder check rewrites its loyalty so it becomes yours: it follows you, obeys, and
you can name it." Ultimate Magic p.113 (Craft Construct, 100 gp a Hit Die, a day) is what
it departs from, and content/rules/repairs.json keeps both side by side.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gm import judgement
from gm.checks import BeatContext, registered, repair_claimed
from rules import repair, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

OWNERS_LINE = ("I attempt to use my knowledge of engineering and my deft hands to fix the "
               "spy in a way that makes it recognize me as its owner.")
OWNERS_NAMING = "I greet my new friend and I name him Bob"
OWNERS_NEXT_BEAT = ("You have tamed the heart of the spy, and it now waits for your "
                    "command.")


def _table(spy_hp: int = -1, *, engineering: int = 1, seed: int = 1):
    scene = Scene(location_id=None)
    pc = scene.add(load_pc("fixtures/pc-thessaly.json"))
    pc.purse = {"gp": 300}
    if engineering:
        pc.ranks = {**pc.ranks, "knowledge (engineering)": engineering}
    spy = scene.add(instantiate("clockwork-spy", scene=scene), zone="near")
    spy.hp = spy_hp
    spy.apply_hp_state()
    return scene, Engine(scene, Dice(seed)), pc, spy


def _repair(engine, ref, *, own=False, visibility="player"):
    raw = {"op": "repair", "actor": "pc", "target": ref, "visibility": visibility,
           "because": "test", "params": {"own": True} if own else {}}
    return engine.run(engine.validate([raw]))


def _rolled(engine, res, *faces):
    """Answer the player's popups with these faces, in order; the final Resolution."""
    for face in faces:
        assert res.awaiting, "the engine stopped asking for dice before the faces ran out"
        res = engine.resume(face)
    assert not res.awaiting
    return [o for o in res.outcomes if o.op == "repair"][-1]


def _risen_table():
    """A table whose hidden heal roll lifts the spy from -1 past 0 — a 1 on the 1d6
    mends it only to 0, which is still broken (the next test says so)."""
    for seed in range(1, 40):
        scene, engine, pc, spy = _table(-1, seed=seed)
        probe = Engine(scene, Dice(seed)).dice.roll("1d6").total
        if probe >= 2:
            return _table(-1, seed=seed)
    raise AssertionError("no seed in 1..39 rolls 2 or more on 1d6")


def test_mended_only_to_zero_it_is_still_broken():
    """"0 to -10 is broken": a made repair that rolls a 1 lifts the spy from -1 to 0, and
    at 0 it is still broken — the tell says so and no claim can follow."""
    for seed in range(1, 60):
        _scene, engine, _pc, spy = _table(-1, seed=seed)
        if Engine(_scene, Dice(seed)).dice.roll("1d6").total == 1:
            break
    else:
        raise AssertionError("no seed rolls a 1")
    out = _rolled(engine, _repair(engine, spy.ref), 20)
    assert out.verdict == "success" and spy.hp == 0
    assert spy.has_state("state.down.broken") and "still broken" in out.tell


# --- broken, then fixable ---------------------------------------------------------------

def test_the_owners_spy_at_minus_one_is_mended_by_a_knowledge_engineering_check():
    """The owner's state: the spy at -1 is broken. Sam's Knowledge (engineering) — the
    better of it and an untrained Craft — makes the check at DC 15 (the spy's crafting DC
    20, less 5); 1d6 per Hit Die comes back through the heal applicator stamped
    `rule:repair-construct`; ten minutes pass; no feat, no coin. Mended above 0 it is no
    longer broken, and it is nobody's yet: indifferent, not the hostile it fought as."""
    scene, engine, pc, spy = _risen_table()
    engine._set_attitude(spy, "hostile", None, "the fight")
    clock = scene.clock_minutes
    res = _repair(engine, spy.ref)
    assert res.awaiting["dc"] == 15 and "Knowledge (Engineering)" in res.awaiting["label"]
    out = _rolled(engine, res, 20)
    heals = [e for e in out.effects if e.get("kind") == "heal"]
    assert out.verdict == "success" and heals
    assert heals[0]["origin"] == f"rule:{repair.RULE}"
    assert spy.hp > 0 and not spy.is_down and not spy.has_state("state.down.broken")
    assert states.attitude_of(spy) == "indifferent"
    assert not spy.has_state(states.OWNED_BY_YOU)
    assert scene.clock_minutes - clock == 10 and pc.purse == {"gp": 300}
    assert "working again, and it is nobody's yet" in out.tell


def test_a_failure_by_five_or_more_costs_an_hour_and_mends_nothing():
    """The row's HOUSE consequence: an hour gone, nothing else lost."""
    scene, engine, _pc, spy = _table(-1)
    clock = scene.clock_minutes
    out = _rolled(engine, _repair(engine, spy.ref), 1)
    assert out.verdict == "failure" and out.margin <= -5
    assert scene.clock_minutes - clock == 60 and spy.hp == -1
    assert spy.has_state("state.down.broken")
    assert "an hour is gone" in out.tell


def test_a_destroyed_construct_cannot_be_mended():
    """"destroyed only past that": at -11 the spy is parts, and nothing is rolled."""
    _scene, engine, _pc, spy = _table(-11)
    assert spy.is_dead
    (out,) = _repair(engine, spy.ref).outcomes
    assert out.status == "refused" and out.rolls == [] and "destroyed" in out.tell


def test_nobody_without_craft_or_knowledge_engineering_attempts_it_untrained_knowledge():
    """Craft is usable untrained in 1e, so anybody can try; Knowledge is trained-only,
    and a sheet with no engineering ranks falls back to Craft rather than being refused."""
    _scene, engine, _pc, spy = _table(-1, engineering=0)
    res = _repair(engine, spy.ref)
    assert res.awaiting and res.awaiting["label"].startswith("Craft")


def test_a_living_body_is_not_repaired():
    scene, engine, _pc, _spy = _table(2)
    thug = scene.add(instantiate("thug", scene=scene), zone="near")
    thug.hp = 3
    (out,) = _repair(engine, thug.ref).outcomes
    assert out.status == "refused" and "not a construct" in out.tell


def test_a_hostile_construct_still_working_is_not_repaired():
    """It has to be stopped first: a machine swinging at you is not mended."""
    _scene, engine, _pc, spy = _table(2)
    engine._set_attitude(spy, "hostile", None, "test")
    (out,) = _repair(engine, spy.ref).outcomes
    assert out.status == "refused" and "not for you" in out.tell


def test_the_player_rolls_and_nothing_moves_until_the_die_is_in():
    scene, engine, _pc, spy = _table(-1)
    clock = scene.clock_minutes
    res = _repair(engine, spy.ref)
    assert res.awaiting and scene.clock_minutes == clock and spy.hp == -1


# --- then claimable ----------------------------------------------------------------------

def test_the_owners_line_mends_and_then_claims_the_spy_in_one_turn():
    """Both checks, both the player's dice: the repair at DC 15, then — because the line
    asked for it and the spy is working by then — the claim at DC 25 (the repair DC +
    10). A made claim grants `bond.owned-by-you`, the companion bond the `company` op
    grants (source `company:<ref>`), and `devoted`, the top of the attitude track."""
    scene, engine, _pc, spy = _table(-1)
    res = _repair(engine, spy.ref, own=True)
    assert res.awaiting["dc"] == 15
    res = engine.resume(20)
    assert res.awaiting and res.awaiting["dc"] == 25
    assert "(claim)" in res.awaiting["label"]
    out = _rolled(engine, res, 20)
    assert out.verdict == "success"
    assert spy.has_state(states.OWNED_BY_YOU)
    assert spy.has_state(states.TRAVELS_WITH_YOU)
    assert any(e.source == f"company:{spy.ref}" for e in spy.effects)
    assert states.attitude_of(spy) == "devoted"
    assert "it follows and obeys" in out.tell


def test_a_failed_repair_leaves_the_claim_for_another_turn():
    _scene, engine, _pc, spy = _table(-1)
    out = _rolled(engine, _repair(engine, spy.ref, own=True), 2)
    assert out.verdict == "failure" and not spy.has_state(states.OWNED_BY_YOU)
    assert len(out.rolls) == 1


def test_a_claim_failed_by_five_or_more_turns_the_machine_hostile():
    """The row's HOUSE consequence for the claim."""
    _scene, engine, _pc, spy = _table(2)
    engine._set_attitude(spy, "indifferent", None, "test")
    spy.hp = spy.hp_max
    out = _rolled(engine, _repair(engine, spy.ref, own=True), 1)
    assert out.verdict == "failure" and states.attitude_of(spy) == "hostile"
    assert not spy.has_state(states.OWNED_BY_YOU)


def test_a_broken_construct_cannot_be_claimed_before_it_is_mended():
    _scene, engine, _pc, spy = _table(-1)
    reason = repair.claim_refusal(engine.scene, engine.scene.pc(), spy)
    assert "mended and working" in reason


def test_a_claim_needs_training():
    """Knowledge (engineering) and Disable Device are both trained-only in 1e."""
    _scene, engine, _pc, spy = _table(2, engineering=0)
    spy.hp = spy.hp_max
    (out,) = _repair(engine, spy.ref, own=True).outcomes
    assert out.status == "refused" and "training" in out.tell


# --- the words become the ops -------------------------------------------------------------

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


def test_any_check_aimed_at_the_machine_is_the_repair_dressed_up():
    """The replay of the owner's line on a copy of the save (2026-10-01) came back first
    as `check skill=use` aimed at the spy: refused as no such skill, a whole second plan
    spent before the repair op landed."""
    scene, _engine, _pc, spy = _table()
    model = [{"op": "check", "actor": "pc", "target": spy.ref,
              "params": {"skill": "use", "dc": {"band": "average"}}}]
    out = judgement.declare_repair(model, OWNERS_LINE, scene)
    assert [r["op"] for r in out] == ["repair"]


def test_a_skill_that_does_not_exist_beside_the_repair_is_the_dressing_too():
    """The house-rule replay (2026-10-01) wrote `check skill=use` with NO target, and the
    first plan was refused again for a skill that does not exist. A real skill with no
    target that is not repair dressing (Perception, say) is left alone."""
    scene, _engine, _pc, _spy = _table()
    model = [{"op": "check", "actor": "pc", "params": {"skill": "use"}},
             {"op": "check", "actor": "pc", "params": {"skill": "perception"}}]
    out = judgement.declare_repair(model, OWNERS_LINE, scene)
    assert [(r["op"], (r.get("params") or {}).get("skill")) for r in out] == [
        ("check", "perception"), ("repair", None)]


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
    assert not out[0]["params"].get("own")


@pytest.mark.parametrize("line", [
    "I rewrite its loyalty.",
    "I make the spy mine.",
    "I reprogram the spy.",
])
def test_claiming_words_alone_declare_the_claim(line):
    scene, _engine, _pc, spy = _table(2)
    out = judgement.declare_repair([], line, scene)
    assert out[0]["op"] == "repair" and out[0]["params"] == {"own": True}


@pytest.mark.parametrize("line", [
    "Can I fix the spy?",
    "I search the wreckage for something useful.",
    "\"I will fix you,\" I tell the spy.",
])
def test_questions_speech_and_other_acts_declare_nothing(line):
    scene, _engine, _pc, _spy = _table()
    assert judgement.declare_repair([], line, scene) == []


def test_the_plan_chain_runs_both_declarations():
    """Two lines in gm/agent.py's chain; without them the injectors exist and are never
    asked — the dice rebuild's lesson (trace the real path first)."""
    src = (Path(__file__).resolve().parent.parent / "gm" / "agent.py").read_text(
        encoding="utf-8")
    assert "raw = judgement.declare_repair(raw, player_input, self.engine.scene)" in src
    assert "raw = judgement.declare_name(raw, player_input, self.engine.scene)" in src


# --- and you can name it -----------------------------------------------------------------

def _owned_spy():
    scene, engine, _pc, spy = _risen_table()
    _rolled(engine, _repair(engine, spy.ref, own=True), 20, 20)
    assert spy.has_state(states.OWNED_BY_YOU)
    return scene, engine, spy


def test_the_owners_naming_line_names_the_claimed_spy_bob():
    """"I greet my new friend and I name him Bob": on the replay the turn resolved to
    narrate_only, the prose said "Bob", and the un-namer struck it and wrote "The name
    'the stranger' hangs in the air". Now the name is declared from the line and written
    by the engine to `name` and `true_name` — the fields `GMAgent._known_names` reads —
    before any prose exists."""
    scene, engine, spy = _owned_spy()
    raw = judgement.declare_name([], OWNERS_NAMING, scene)
    assert raw == [{"op": "rename", "target": spy.ref,
                    "because": "the player names what is theirs",
                    "params": {"name": "Bob"}}]
    (out,) = engine.run(engine.validate(raw)).outcomes
    assert spy.name == "Bob" and spy.true_name == "Bob"
    assert "answers to Bob" in out.tell


def test_a_name_is_not_given_to_what_is_not_yours():
    """"I call him a coward" is an insult, and a stranger's name is theirs to give."""
    scene, engine, _pc, spy = _table(2)
    assert judgement.declare_name([], "I name him Bob", scene) == []
    (out,) = engine.run(engine.validate([{"op": "rename", "target": spy.ref,
                                          "params": {"name": "Bob"}}])).outcomes
    # A printed kind goes by its kind (`bestiary.kind_word`, 2026-10-09).
    assert out.status == "refused" and spy.name == "clockwork spy"
    scene2, _e2, spy2 = _owned_spy()
    assert judgement.declare_name([], "I call him a coward", scene2) == []


# --- the page cannot claim what the engine did not do ---------------------------------------

def _ctx(engine, text, outcomes=(), door="turn"):
    return BeatContext(
        door=door, text=text, player_text=OWNERS_LINE, engine=engine, scene=engine.scene,
        world=None, location=None, reading=None, outcomes=tuple(outcomes), tells=(),
        said=(), attribution=None, brief="", brief_facts={}, pull=None, was_at="",
        acting="", turn=0)


def test_the_check_is_registered():
    assert repair_claimed in registered()


def test_the_owners_tamed_sentence_is_flagged_while_the_spy_is_nobodys():
    """The owner's next beat, on a turn where nothing was granted: the backstop cuts it
    and ends on the engine's fact."""
    _scene, engine, _pc, _spy = _table(-1)
    (found,) = repair_claimed.find(_ctx(engine, OWNERS_NEXT_BEAT))
    assert found.kind == "ownership-claimed"
    text, notes = repair_claimed.backstop(_ctx(engine, OWNERS_NEXT_BEAT),
                                          OWNERS_NEXT_BEAT, [found])
    assert "waits for your command" not in text and notes
    assert "broken" in text and "does not answer to you" in text


def test_the_house_rule_replays_waiting_sentence_is_flagged():
    """Replayed 2026-10-01 under the house rule: "I greet my new friend and I name him
    Bob" on a spy mended but NOT claimed, and the page ended "The construct sits before
    you, a hunk of repaired brass and steel, waiting for your next command." The first
    cut of the pattern read "your command" and missed "your next command"."""
    _scene, engine, _pc, spy = _risen_table()
    _rolled(engine, _repair(engine, spy.ref), 20)
    beat = ("The construct sits before you, a hunk of repaired brass and steel, waiting "
            "for your next command.")
    assert [f.kind for f in repair_claimed.find(_ctx(engine, beat))] == ["ownership-claimed"]


def test_the_same_sentence_is_true_once_the_engine_granted_it():
    """Since the house rule the engine CAN make it the player's; then the page may say so."""
    _scene, engine, _spy = _owned_spy()
    assert repair_claimed.find(_ctx(engine, OWNERS_NEXT_BEAT)) == []


def test_a_broken_machine_written_as_working_is_flagged():
    _scene, engine, _pc, _spy = _table(-1)
    beat = "The spy whirs back to life, its lenses turning toward you."
    assert {f.kind for f in repair_claimed.find(_ctx(engine, beat))} == {"repair-claimed"}


def test_a_mended_machine_may_be_written_as_working():
    _scene, engine, _pc, spy = _table(-1)
    _rolled(engine, _repair(engine, spy.ref), 20)
    beat = "The spy whirs back to life, its lenses turning toward you."
    assert repair_claimed.find(_ctx(engine, beat)) == []


@pytest.mark.parametrize("sentence", [
    "The spy is beyond repair.",
    "You try to repair it, but the mainspring is snapped.",
    "It will never obey you.",
    "Its lenses stay fixed on you.",
    "The spy lies in pieces, its gears scattered across the rock.",
])
def test_denials_attempts_and_stillness_are_not_claims(sentence):
    assert not repair_claimed.mends(sentence) and not repair_claimed.owns(sentence)
