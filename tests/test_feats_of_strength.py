"""Feats of strength: the reader's `exert`, the Strength check, and Aid Another.

The owner, 2026-10-16: "my wife was playing and a man needed help with his cart. When she
helped him the game narrated that i lifted his cart but never gave a strength check."
Measured the same day on gemma-4-12B heretic: five ways of saying it — "I help him with his
cart", "I help the man lift his cart", "I help him push the cart out of the mud", "I lift
the cart so he can fix the wheel", "I grab the other side and help him heave the cart up" —
were all read `other`, which commits no op: nothing was rolled, the engine could not have
rolled a Strength check if asked (`normalise_skill("strength")` was None and `aid` had no
reader), and the deeds backstop then echoed the player's own line onto the page as done.

The rules (Core Rulebook): Strength applies to "Strength checks (for breaking down doors and
the like)" (p.16); Aid Another on a check — "If you roll a 10 or higher on your check, the
character you're helping gets a +2 bonus on his or her check" (p.86); the size bonus on
Strength checks is the book's "to break open doors" (p.175), which is break_in's path.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, deed_reader, interpret, narration, prompts
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse
from rules.sheet import load_pc
from rules.tables import AID_ANOTHER_DC, ability_check_of


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _scene(seed=7):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    carter = instantiate("guildhand", scene=s, name="the carter")
    s.add(carter)
    return s, Engine(s, Dice(seed=seed)), carter


def _frame(*actions):
    return {"question": False, "claims": [], "actions": [dict(a) for a in actions]}


def _roll(engine, plan, face):
    res = engine.run(engine.validate(plan, origin="author:test"))
    assert res.awaiting is not None, "the player rolls their own"
    return res.awaiting, engine.resume(face).outcomes[0]


# --- the reading ------------------------------------------------------------------------

# The live readings of the owner's lines after the change (2026-10-16, gemma-4-12B heretic):
# five of five `exert`, the helper's target kept; the offer stays talk.
HELP_WITH_THE_CART = _frame({"act": "exert", "object": "his cart", "target": "the carter",
                             "span": "help the carter lift his cart"})
LIFT_IT_ALONE = _frame({"act": "exert", "object": "the cart",
                        "span": "lift the cart so he can fix the wheel"})


def test_exert_is_an_act_with_a_gloss_and_slots():
    assert "exert" in interpret.ACTS
    assert interpret.ACT_SLOTS["exert"] == ("object", "target", "place")
    assert "\nexert " in interpret._WHAT_EACH_IS
    # Demonstrated, and not with the probe lines' own words (the demonstration counts
    # more than the instruction, and a probe line in the prompt measures recall of it).
    demos = [text for text, frame in interpret._DEMOS
             if any(a["act"] == "exert" for a in frame["actions"])]
    assert len(demos) == 2 and not any("cart" in d for d in demos)


def test_helping_the_carter_builds_exactly_one_aid_another_check():
    """Read `other`, "I help the man lift his cart" owed no op at all. Read `exert` with the
    carter as the target, the table builds the player's Strength check as Aid Another on
    his effort — one check, the carter its target — and the plan's own Strength or Climb
    check for the same deed is replaced, its band carried over."""
    s, _e, carter = _scene()
    rows = acts_to_ops.table(HELP_WITH_THE_CART, s, sentence="I help the carter lift his cart.")
    assert rows[0].ops == ["check"]
    plan = [{"op": "check", "actor": "pc", "params": {"skill": "strength", "dc": "tough"}},
            {"op": "check", "actor": "pc", "params": {"skill": "climb", "dc": 15}}]
    notes: list = []
    got = acts_to_ops.apply(plan, rows, HELP_WITH_THE_CART, s, notes=notes)
    checks = [r for r in got if r["op"] == "check"]
    assert len(checks) == 1
    assert checks[0]["target"] == carter.ref and checks[0]["actor"] == "pc"
    assert checks[0]["params"] == {"skill": "strength", "aid": True,
                                   "dc": {"band": "tough"}}
    assert sum("feat of strength" in n for n in notes) == 2


def test_lifting_alone_is_the_players_own_check_at_the_plans_band():
    s, _e, _carter = _scene()
    rows = acts_to_ops.table(LIFT_IT_ALONE, s, sentence="I lift the cart so he can fix the wheel.")
    got = acts_to_ops.apply([{"op": "narrate_only"}], rows, LIFT_IT_ALONE, s)
    assert [r for r in got if r["op"] == "check"] == [
        {"op": "check", "actor": "pc", "because": "the player puts their strength to it",
         "params": {"skill": "strength", "dc": {"band": "average"}}}]
    # A plan that names a band gives it; a stated number lands in its band.
    got = acts_to_ops.apply([{"op": "check", "actor": "pc",
                              "params": {"skill": "strength", "dc": 20}}],
                            rows, LIFT_IT_ALONE, s)
    assert [r["params"]["dc"] for r in got] == [{"band": "challenging"}]
    # And the band is the plan's of THIS attempt: a retry naming none goes back to the
    # default, never keeping the last attempt's.
    got = acts_to_ops.apply([{"op": "narrate_only"}], rows, LIFT_IT_ALONE, s)
    assert got[-1]["params"]["dc"] == {"band": "average"}


def test_a_plans_other_checks_stand_beside_the_feat():
    """Only the body's own check is the same deed. A Diplomacy check the plan wrote for
    words said in the same turn is another deed and rolls."""
    s, _e, carter = _scene()
    rows = acts_to_ops.table(HELP_WITH_THE_CART, s)
    plan = [{"op": "check", "actor": "pc", "target": carter.ref,
             "params": {"skill": "diplomacy"}}]
    got = acts_to_ops.apply(plan, rows, HELP_WITH_THE_CART, s)
    assert sorted(r["params"]["skill"] for r in got) == ["diplomacy", "strength"]


def test_the_feat_is_not_a_deed_the_page_is_made_to_show():
    """The deeds backstop owed the `other` reading and wrote the player's line onto the
    page — "You help the man lift his cart" — whatever the dice said. A feat of strength is
    a check, like a climb or a door forced: the dice own its outcome, and the page is never
    made to show the attempt as done."""
    said = "I help the carter lift his cart."
    assert deed_reader.deeds_of(HELP_WITH_THE_CART, said) == []
    assert narration.owed_deeds(HELP_WITH_THE_CART, said, []) == []
    # The `other` reading of the same line WAS owed, which is how the lift got written.
    other = _frame({"act": "other", "object": "his cart", "target": "the carter",
                    "span": "help the carter lift his cart"})
    assert deed_reader.deeds_of(other, said)


# --- the engine -------------------------------------------------------------------------

def test_strength_is_a_check_the_engine_can_roll():
    assert ability_check_of("strength") == "str"
    assert ability_check_of("Strength check") == "str"
    assert ability_check_of("str") == "str"
    assert ability_check_of("athletics") is None
    intent = parse({"op": "check", "actor": "pc", "params": {"skill": "Strength",
                                                             "dc": "tough"}})
    assert intent.params["skill"] == "strength"


def test_a_strength_check_is_d20_plus_strength_and_nothing_a_skill_adds():
    """Kesst has Str 12 and ranks in skills; a Strength check is d20 + 1 and nothing else
    — no ranks, no class skill, no armour check penalty — with sickened's -2 on ability
    checks through the same funnel."""
    s, e, _carter = _scene()
    pc = s.pc()
    asked, out = _roll(e, [{"op": "check", "actor": "pc",
                            "params": {"skill": "strength", "dc": {"band": "tough"}}}], 14)
    assert asked["label"] == "Strength check" and asked["dc"] == 15
    assert asked["breakdown"] == [{"value": pc.ability_mod("str"), "source": "Str"}]
    assert out.rolls[0].total == 14 + pc.ability_mod("str")
    assert out.verdict == "success"
    pc.add_condition("sickened", rounds=10, source="test")
    asked, _out = _roll(e, [{"op": "check", "actor": "pc",
                             "params": {"skill": "strength", "dc": {"band": "tough"}}}], 14)
    assert asked["modifier"] == pc.ability_mod("str") - 2


def test_a_failed_lift_is_told_as_a_failure():
    """The narrator is fed the tell and nothing else about mechanics: a Strength check
    missed says so in words the page must follow, the verdict is a failure the claims
    scrubber backs as one, and the tell reaches the prose call."""
    s, e, _carter = _scene()
    _asked, out = _roll(e, [{"op": "check", "actor": "pc",
                             "params": {"skill": "strength", "dc": {"band": "tough"}}}], 2)
    assert out.verdict == "failure" and out.margin < 0
    assert out.tell == f"Kesst Vayr misses the Strength check by {-out.margin}: the attempt fails."
    msgs = prompts.call_prose_messages("brief", [], "I lift the cart.", [out.tell])
    assert "the attempt fails" in msgs[-1]["content"]


def test_aid_another_is_the_books_ten_and_a_made_aid_gives_the_two():
    """CRB p.86. The player's popup asks for 10, whatever band the task is; made, the
    carter rolls his own Strength check +2 against the task, hidden."""
    s, e, carter = _scene()
    plan = [{"op": "check", "actor": "pc", "target": carter.ref,
             "params": {"skill": "strength", "aid": True, "dc": {"band": "challenging"}}}]
    asked, out = _roll(e, plan, 12)
    assert asked["dc"] == AID_ANOTHER_DC == 10
    assert asked["label"] == "Strength check to help the carter"
    aid = out.effects[0]
    assert aid["kind"] == "aid" and aid["made"] and aid["bonus"] == 2 and aid["task_dc"] == 20
    theirs = out.rolls[1]
    assert theirs.visibility == "hidden"
    assert any(m.source == "aid from Kesst Vayr" and m.value == 2 for m in theirs.modifiers)
    assert out.dc["value"] == 10                    # the number the player's roll is shown against
    assert out.verdict == ("success" if theirs.total >= 20 else "failure")
    assert "lends the carter a hand" in out.tell
    assert e.judged == {"verdict": "success", "natural": 12}


def test_a_failed_aid_gives_no_bonus_and_the_task_rests_on_the_carter_alone():
    """A failure is a real outcome: no +2, the carter's own check decides, and the popup
    judges the player's roll a failure against its 10 whatever the carter then rolls."""
    s, e, carter = _scene()
    plan = [{"op": "check", "actor": "pc", "target": carter.ref,
             "params": {"skill": "strength", "aid": True, "dc": {"band": "challenging"}}}]
    _asked, out = _roll(e, plan, 2)
    aid = out.effects[0]
    assert aid["made"] is False and aid["bonus"] == 0
    assert not any("aid" in m.source for m in out.rolls[1].modifiers)
    assert "no help" in out.tell
    assert e.judged["verdict"] == "failure"
    assert out.verdict == ("success" if out.rolls[1].total >= 20 else "failure")


def test_the_task_is_decided_by_the_helped_persons_check_not_the_aid_roll():
    """Why not "the player's 10 does the job": a cart sunk to the axles would come up for
    anybody who rolled 10. Against a nearly impossible task (DC 40) a made aid still
    fails — the carter's d20 + 2 cannot reach it."""
    s, e, carter = _scene()
    plan = [{"op": "check", "actor": "pc", "target": carter.ref,
             "params": {"skill": "strength", "aid": True,
                        "dc": {"band": "nearly_impossible"}}}]
    _asked, out = _roll(e, plan, 20)
    assert out.effects[0]["made"] and out.verdict == "failure"
    assert "the attempt fails" in out.tell


def test_aid_needs_somebody_to_help_and_is_never_a_contest():
    with pytest.raises(IntentError, match="aid helps somebody else"):
        parse({"op": "check", "actor": "pc",
               "params": {"skill": "strength", "aid": True, "dc": "tough"}})
    with pytest.raises(IntentError, match="never a contest"):
        parse({"op": "check", "actor": "pc", "target": "c1",
               "params": {"skill": "strength", "aid": True,
                          "opposed_by": {"ref": "c1", "skill": "perception"}}})


def test_the_whole_turn_from_the_reading_rolls_one_strength_check():
    """End to end below the models: the reading, the table, the plan's declared check, the
    engine. One roll, the player's, against 10; then the carter's."""
    s, e, carter = _scene()
    rows = acts_to_ops.table(HELP_WITH_THE_CART, s)
    declared = {"op": "check", "actor": "pc", "params": {"skill": "strength", "dc": "tough"},
                "because": "the player's words commit the turn to it"}
    raw = acts_to_ops.apply([declared], rows, HELP_WITH_THE_CART, s)
    res = e.run(e.validate(raw))
    assert res.awaiting is not None and res.awaiting["dc"] == 10
    outs = e.resume(11).outcomes
    assert [o.op for o in outs if o.op == "check"] == ["check"]
    assert outs[0].effects[0]["task_dc"] == 15
