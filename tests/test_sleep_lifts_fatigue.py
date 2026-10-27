"""Fatigue and exhaustion lift by the hours actually slept, the night says so, and a bench's
toll is told before the night that followed it.

The owner's 0.2.21 report (2026-10-27), turn-log row 84, transcript beat 57: after some
21 hours at the herb bench, "I will sleep in my bedroll until morning" resolved

    "Jason rests for 15 hours. The bedroll kept the ground off Jason … Jason was already
    unhurt."  then  "Jason fails a Will save against sleep (8 against DC 12) … Jason is
    fatigued. Jason is exhausted."

and the beat wrote "the grueling struggle leaves you drained and exhausted". The save then
held `fatigued (source: slept off exhaustion)`, and every later beat said "your limbs
heavy and your movements sluggish". Three defects, none of them hunger or thirst (both
counts 0 in the save):

  * the sleep-ladder toll was rolled by the bench's hours, queued, and told behind the
    batch's first op — the rest — so the night read as its cause;
  * `Actor.rest` counted every night as eight hours, so exhaustion only ever became fatigue
    (CRB Appendix 2: an hour of complete rest turns exhausted into fatigued, eight hours
    lift fatigued — nine in all, and Jason slept fifteen);
  * the night lifted or kept the conditions in silence, so nothing said why he was tired.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from rules import ontheway, survival  # noqa: E402
from rules.crafting import Stock  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import load_pc  # noqa: E402


@pytest.fixture
def quiet_night(monkeypatch):
    monkeypatch.setattr(ontheway, "night", lambda *a, **k: None)


def _pc():
    return load_pc("fixtures/pc-kesst.json")


def _camp(seed=3):
    from _a_truth import APPROACH, VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    pc = _pc()
    s.add(pc)
    pc.add_stock(Stock(base="bedroll", craft=""), 1)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(APPROACH)
    return s, e, pc


def _sleep(e, until=""):
    params = {"kind": "night", **({"until": until} if until else {})}
    return e.run(e.validate([{"op": "rest", "actor": "pc", "params": params}]))


def test_fifteen_hours_lift_exhaustion_and_fatigue():
    """The owner's night: exhausted, fifteen hours slept. It woke fatigued because every
    night counted as eight; 1 + 8 hours of complete rest lift both."""
    pc = _pc()
    pc.add_condition("exhausted", source="awake too long")
    got = pc.rest("night", slept=15)
    assert not pc.has_condition("exhausted") and not pc.has_condition("fatigued")
    assert got["fatigue"] == {"lifted": ["exhausted", "fatigued"], "left": "", "why": ""}
    assert survival.fatigue_said(pc, got) == f"The sleep lifts {pc.name}'s exhaustion and fatigue."


def test_eight_hours_ease_exhaustion_only_to_fatigue_and_say_how_long_is_left():
    """Eight hours is one short of nine: fatigued is right by the book, and now it is said."""
    pc = _pc()
    pc.add_condition("exhausted", source="awake too long")
    got = pc.rest("night")
    assert pc.has_condition("fatigued") and not pc.has_condition("exhausted")
    assert got["fatigue"]["left"] == "fatigued" and got["fatigue"]["why"] == "short"
    assert "eases" in survival.fatigue_said(pc, got)
    assert "8 more hours of rest" in survival.fatigue_said(pc, got)


def test_a_night_lifts_plain_fatigue_and_says_so():
    pc = _pc()
    pc.add_condition("fatigued", source="a long march")
    got = pc.rest("night")
    assert not pc.has_condition("fatigued")
    assert survival.fatigue_said(pc, got) == f"The sleep lifts {pc.name}'s fatigue."


def test_thirsts_fatigue_stays_and_the_night_says_what_holds_it():
    """CRB p.444 and the owner's ruling of 2026-10-05: the fatigue thirst leaves stays
    until they drink. Kept as it was — and now said, so the player sees why."""
    pc = _pc()
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    toll = survival.Toll()
    survival._harm(pc, 3, toll, need="thirst")
    pc.add_condition("fatigued", source="thirst")
    assert pc.withheld_nonlethal()
    got = pc.rest("night", slept=12)
    assert pc.has_condition("fatigued")
    assert survival.fatigue_said(pc, got) == (
        f"{pc.name} wakes still fatigued: thirst holds it until {pc.name} drinks, and no "
        f"sleep lifts it.")


def test_the_rest_op_passes_the_hours_slept_and_tells_the_lift(quiet_night):
    """End to end through `_op_rest`, the owner's night: "until morning" at five in the
    afternoon is fifteen hours in the bedroll, and an exhausted sleeper wakes clear, said.
    Before: "rests for 15 hours" and a fatigue nothing explained."""
    s, e, pc = _camp()
    s.clock_minutes = 24 * 60 + 17 * 60
    pc.add_condition("exhausted", source="awake too long")
    rest = next(o for o in _sleep(e, "until morning").outcomes if o.op == "rest")
    assert next(x["hours"] for x in rest.effects if x.get("kind") == "rest") == 15
    assert not pc.has_condition("fatigued") and not pc.has_condition("exhausted")
    assert "rests for 15 hours, until morning. The sleep lifts" in rest.tell
    assert "exhaustion and fatigue" in rest.tell


def test_an_eight_hour_night_leaves_the_fatigue_and_says_how_much_more(quiet_night):
    s, e, pc = _camp()
    pc.add_condition("exhausted", source="awake too long")
    rest = next(o for o in _sleep(e).outcomes if o.op == "rest")
    assert pc.has_condition("fatigued") and not pc.has_condition("exhausted")
    assert "eases Kesst Vayr's exhaustion to fatigue; it takes 8 more hours" in rest.tell


def test_a_bench_toll_is_told_before_the_night_not_after_it(quiet_night):
    """The report's order: the bench's hours rolled the sleep ladder outside any op, and the
    toll was told behind the batch's first op — after "rests for 15 hours" — so the beat
    wrote the night as what exhausted him. Told first now, as what came before."""
    s, e, pc = _camp()
    pc.awake_minutes = 20 * 60
    passed = s.advance(6 * 60)                     # a bench's hours: outside any op
    assert passed.get("body"), "the awake ladder was rolled and queued"
    res = _sleep(e)
    ops = [o.op for o in res.outcomes]
    assert "body" in ops and "rest" in ops
    assert ops.index("body") < ops.index("rest"), ops
    body = next(o for o in res.outcomes if o.op == "body")
    assert "fatigued" in body.tell, "the bench left the fatigue (seed 3)"
    # And the night that follows lifts it, said after the toll that laid it.
    rest = next(o for o in res.outcomes if o.op == "rest")
    assert "The sleep lifts Kesst Vayr's fatigue." in rest.tell
    assert not pc.has_condition("fatigued")


def test_the_planned_slot_gives_the_players_line_to_their_own_act():
    """With the bench's toll told first, the plan's first act is the engine's own; the
    player's words ride the first act that came of them ("I sleep" on the rest), never the
    toll."""
    from gm import planned
    from rules.engine import Outcome

    s = Scene(location_id="5bbd0c40345f")
    s.add(_pc())
    e = Engine(s, Dice(seed=1))
    outs = [Outcome(intent_id="", op="body", tell="Kesst fails a Will save against sleep."),
            Outcome(intent_id="i1", op="rest", tell="Kesst rests for 15 hours.")]
    slots = planned.build_plan(e, "I sleep in my bedroll", outs)
    facts = [sl for sl in slots if sl["key"].startswith("fact")]
    assert len(facts) == 2
    assert 'The player said' not in facts[0]["say"]
    assert facts[1]["say"].startswith('The player said: "I sleep in my bedroll"')
