"""A drink in a fight is a standard action that provokes (owner ruling 2026-11-13).

Measured on master before this (2026-10-08 note, "use door and action economy", and
again 2026-11-13): the Equipment tab's Drink in a fight, on the player's turn, with a
thug in the next square, drew no swing and left the turn whole — the player could then
strike from the combat bar as well, two standard actions in one round. The same held for
a narrated "I drink the potion", which reaches the same `use_item` op.

The rule (Core Rulebook Table 8-2): "Drink a potion or apply an oil — standard action,
attack of opportunity: yes". Magic Items, Potions: administering a potion to an
unconscious creature is a full-round action that provokes. Quick Draw changes nothing,
and no fetch-from-pack move is modelled. Out of a fight nothing changes.
"""
from __future__ import annotations

from rules import crafting, reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _tea(count=3):
    return crafting.Stock(
        base="Acacia Tea", tier="common", count=count, potency=1.0, craft="herbalist",
        effects=["+1 Will saves"],
        specs=[{"type": "save_mod", "amount": 1, "target": "will",
                "bonus_type": "untyped", "from": "Acacia",
                "duration": {"amount": 1, "unit": "hour"}}])


def _scene(gap: int = 1, fight: bool = True, seed: int = 3):
    """Kesst with three doses of tea, a thug `gap` squares east; her turn."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.stock.clear()
    tea = _tea()
    pc.add_stock(tea, tea.count)
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    thug.hp = thug.hp_base = 200
    pc.hp = pc.hp_max = 500              # never dropped by the swing it draws
    e = Engine(s, Dice(seed=seed))
    if fight:
        e._ensure_encounter("pc")
        s.turn = next(i for i, (r, _) in enumerate(s.initiative) if r == "pc")
        s.acted.add("c1")                # not flat-footed: he may take the swing
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (2 + gap, 10)
    s.resync_zones()
    assert bool(reactions.provoked_by_action(s, "pc")) == (fight and gap == 1)
    return s, e, pc


def _tea_id(pc):
    return next(k for k, v in pc.stock.items() if v.base == "Acacia Tea")


def _drink(e, pc, to="pc"):
    return {"op": "use_item", "actor": "pc", "because": "she drinks",
            "params": {"item": _tea_id(pc), "how": "drink", "to": to}}


def _run(e, raw):
    res = e.run(e.validate(raw))
    while res.status != "complete":
        res = e.resume(face=min(11, int(res.awaiting["max"])))
    return res.outcomes


def _swings(outs):
    return [o for o in outs if o.op == "attack" and o.actor == "c1"]


def test_a_drink_beside_a_foe_draws_his_swing_and_still_goes_down():
    """The finding: no swing at all for a drink with a thug in the next square."""
    s, e, pc = _scene()
    outs = _run(e, [_drink(e, pc)])
    assert len(_swings(outs)) == 1, [o.tell for o in outs]
    assert outs.index(_swings(outs)[0]) < next(
        i for i, o in enumerate(outs) if o.op == "use_item"), "the swing comes first"
    assert "drinks" in next(o for o in outs if o.op == "use_item").tell
    assert pc.stock[_tea_id(pc)].count == 2
    assert s.standard_spent["pc"] == s.round


def test_a_blow_after_the_drink_is_refused_but_a_move_is_not():
    """The second half of the finding: the Equipment drink and then the combat bar's
    blow was two standard actions in one round. Refused with the reason; the move
    action is still hers."""
    s, e, pc = _scene()
    _run(e, [_drink(e, pc)])
    outs = _run(e, [{"op": "attack", "actor": "pc", "target": "c1", "because": "stab"}])
    blow = next(o for o in outs if o.op == "attack" and o.actor == "pc")
    assert blow.status == "refused" and "standard action" in blow.tell, blow.tell
    assert s.actors["c1"].hp == 200
    outs = _run(e, [{"op": "move", "actor": "pc", "because": "steps back",
                     "params": {"square": [1, 10]}}])
    assert next(o for o in outs if o.op == "move").status == "resolved"


def test_a_second_drink_in_the_round_is_refused_and_the_dose_kept():
    s, e, pc = _scene(gap=4)
    _run(e, [_drink(e, pc)])
    outs = _run(e, [_drink(e, pc)])
    use = next(o for o in outs if o.op == "use_item")
    assert use.status == "refused" and "standard action" in use.tell, use.tell
    assert pc.stock[_tea_id(pc)].count == 2


def test_a_drink_after_a_blow_in_the_same_turn_is_refused_and_provokes_nothing():
    """"I stab him and drink my tea" in one spoken turn: the blow was the standard
    action. A refused drink invents no opening."""
    s, e, pc = _scene()
    outs = _run(e, [{"op": "attack", "actor": "pc", "target": "c1", "because": "stab"},
                    _drink(e, pc)])
    use = next(o for o in outs if o.op == "use_item")
    assert use.status == "refused", use.tell
    assert not _swings(outs), "a refused drink drew a swing"
    assert pc.stock[_tea_id(pc)].count == 3


def test_next_round_the_standard_action_is_back():
    s, e, pc = _scene(gap=4)
    _run(e, [_drink(e, pc)])
    s.round += 1
    outs = _run(e, [_drink(e, pc)])
    assert next(o for o in outs if o.op == "use_item").status == "resolved"


def test_no_foe_in_reach_no_swing_but_the_action_is_still_spent():
    s, e, pc = _scene(gap=4)
    outs = _run(e, [_drink(e, pc)])
    assert not _swings(outs)
    assert s.standard_spent["pc"] == s.round


def test_out_of_a_fight_nothing_changes():
    s, e, pc = _scene(fight=False)
    assert not s.in_encounter
    for _ in range(2):
        outs = _run(e, [_drink(e, pc)])
        assert next(o for o in outs if o.op == "use_item").status == "resolved"
        assert not _swings(outs)
    assert not s.standard_spent and "pc" not in s.move_spent


def test_a_potion_given_to_the_unconscious_takes_the_whole_round():
    """CRB, Potions: administering to an unconscious creature is a full-round action. It
    is refused after a move, and it spends the move as well as the standard action."""
    s, e, pc = _scene(gap=4)
    friend = s.add(instantiate("thug", scene=s, name="the friend"))
    friend.nonlethal = friend.hp + 3
    friend.apply_hp_state()
    assert friend.has_state("state.down.unconscious")
    s.positions[friend.ref] = (2, 11)
    s.resync_zones()
    s.move_spent["pc"] = s.round
    outs = _run(e, [_drink(e, pc, to=friend.ref)])
    use = next(o for o in outs if o.op == "use_item")
    assert use.status == "refused" and "whole round" in use.tell, use.tell
    del s.move_spent["pc"]
    outs = _run(e, [_drink(e, pc, to=friend.ref)])
    assert next(o for o in outs if o.op == "use_item").status == "resolved"
    assert s.move_spent["pc"] == s.round and s.standard_spent["pc"] == s.round


def test_the_record_survives_a_save():
    """Saved for the reason `move_spent` is: a fight put down mid-turn would hand the
    drink's standard action back."""
    import inspect

    from play import campaign

    src = inspect.getsource(campaign)
    assert '"standard_spent": (dict(self.scene.standard_spent), {})' in src
    assert "standard_spent={k: int(v)" in src
