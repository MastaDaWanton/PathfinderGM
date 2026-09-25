"""A helpless creature is still in the fight.

Measured 2026-09-25 by probe: `helpless` was tagged `state.down.helpless`, so `is_down`
was true for a bound NPC and `Scene.conscious` false. Attacks on him were held back as
"already down", `sides_standing` stopped counting his side, and a foe made helpless by
any of the ten spell specs that apply it ended the fight — paralysis wearing off or not.
1e keeps a helpless creature in the fight; the coup de grace exists for it.
"""
from __future__ import annotations

from rules import activeeffect, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _fight():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    foe = instantiate("thug", scene=s, name="thug")
    s.add(foe, zone="engaged")
    e = Engine(s, Dice(seed=5))
    e.run(e.validate([{"op": "begin_encounter", "because": "test",
                       "params": {"sides": {"pc": ["pc"], "them": [foe.ref]}}}]))
    return s, foe, e


def test_a_bound_foe_is_helpless_and_not_down():
    s, foe, _ = _fight()
    foe.add_condition("helpless", source="bound hand and foot")
    assert foe.is_helpless
    assert not foe.is_down
    assert s.conscious(foe.ref)
    assert not foe.can_act()


def test_making_the_last_foe_helpless_does_not_end_the_fight():
    s, foe, _ = _fight()
    foe.add_condition("paralyzed", source="hold person")
    assert foe.is_helpless and not foe.is_down
    assert s.in_encounter
    assert foe.ref in [r for r, _ in s.initiative]


def test_every_row_that_was_helpless_still_is():
    """The flag on the rows is no longer read; the tag family must cover the same rows."""
    from rules.tables import CONDITIONS

    flagged = {k for k, row in CONDITIONS.items() if row.get("helpless")}
    tagged = {k for k in CONDITIONS if "state.helpless" in states.tags_for(k)}
    assert flagged == tagged


def test_a_helpless_prisoner_saved_before_the_change_loads_in_the_fight():
    """Saved tags are unioned with today's vocabulary, so without WITHDRAWN an old
    save's `state.down.helpless` would have kept him down for the life of the campaign."""
    s = Scene()
    who = instantiate("thug", scene=s, name="prisoner")
    who.add_condition("helpless", source="bound")
    d = to_dict(who)
    for e in d.get("active_effects", []):
        if e.get("key") == "helpless":
            e["tags"] = ["state.down.helpless", "state.unable"]      # as written before
    back = from_dict(d)
    assert back.is_helpless and not back.is_down


def test_a_bound_body_can_be_searched():
    s, foe, e = _fight()
    foe.add_condition("helpless", source="bound")
    out = e.run(e.validate([{"op": "loot", "actor": "pc", "because": "search him",
                             "params": {"from_": foe.ref}}]))
    assert not any("very much attached" in o.tell for o in out.outcomes)
