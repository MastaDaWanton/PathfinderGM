""""Dead" is one predicate in narration: `states.lifeless` (ponytail audit #18).

The audit, 2026-11-07: "dead" meant three things. `GMAgent._groom` counted `hp < 0` as
dead, the read back (`beat_verify.facts_from`) did too and left out broken constructs,
and the plan (`planned.present`) called a broken construct below 0 "dying". Measured on
0.2.27: a bandit at -3 hit points — dying, CRB p.191 — had "The bandit groans on the
cobbles, clutching his side." cut by `_groom` as a dead man acting ("the dead stayed
dead: cut 1 sentence(s)"), against `_groom`'s own comment that an unconscious NPC may
stir or groan.
"""
from __future__ import annotations

from rules import states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _scene_with(hp_below: int, *, broken: bool = False):
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    b = s.add(instantiate("thug", scene=s, name="the bandit"))
    b.take_damage(b.hp + hp_below)
    b.apply_hp_state()
    if broken:
        b.add_condition(states.BROKEN_KEY)
    return s, b


def test_a_dying_bandit_who_groans_is_not_cut_as_a_dead_man():
    from gm import agent as agent_mod
    from tests.test_a_model_that_is_down_hands_on import _World

    s, b = _scene_with(3)
    assert b.hp < 0 and not b.has_state("state.down.dead")
    g = agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))
    text = ("The bandit groans on the cobbles, clutching his side. Blood seeps between "
            "his fingers. What do you do?")
    out, repairs, _ = g._groom(text, rewrite=False, claims=False, hand_back=False)
    assert "groans on the cobbles" in out, (out, repairs)
    assert not any("dead stayed dead" in r for r in repairs)


def test_a_dead_bandit_who_groans_is_still_cut():
    from gm import agent as agent_mod
    from tests.test_a_model_that_is_down_hands_on import _World

    s, b = _scene_with(0)
    b.die("test")
    g = agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))
    text = ("The bandit groans on the cobbles, clutching his side. Blood seeps between "
            "his fingers. What do you do?")
    out, repairs, _ = g._groom(text, rewrite=False, claims=False, hand_back=False)
    assert "groans on the cobbles" not in out


def test_the_predicate_reads_the_tags_never_hit_points():
    _s, dying = _scene_with(3)
    assert not states.lifeless(dying)
    _s, dead = _scene_with(0)
    dead.die("test")
    assert states.lifeless(dead)
    _s, broken = _scene_with(0, broken=True)
    assert broken.has_state("state.down.broken") and states.lifeless(broken)
    assert not states.lifeless(None)


def test_the_read_back_and_the_plan_agree():
    """`beat_verify` counted the dying as dead and a broken construct as alive; `planned`
    called the broken one dying. Each now asks `states.lifeless`."""
    from types import SimpleNamespace

    from gm import beat_verify, planned

    s, b = _scene_with(3)
    eng = Engine(s, Dice(seed=1))
    ctx = SimpleNamespace(engine=eng, scene=s, text="", outcomes=[], was_at=None)
    people = {p.ref: p for p in beat_verify.facts_from(ctx).people}
    assert people[b.ref].dead is False
    row = next(r for r in planned.present(eng) if r["ref"] == b.ref)
    assert "dying" in row["what"] and "dead" not in row["what"].replace("dying", "")

    s, b = _scene_with(0, broken=True)
    eng = Engine(s, Dice(seed=1))
    ctx = SimpleNamespace(engine=eng, scene=s, text="", outcomes=[], was_at=None)
    people = {p.ref: p for p in beat_verify.facts_from(ctx).people}
    assert people[b.ref].dead is True
    row = next(r for r in planned.present(eng) if r["ref"] == b.ref)
    assert "dying" not in row["what"]
