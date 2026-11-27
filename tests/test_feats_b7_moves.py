"""Feat loop batch 7, lane b7-moves: moves spliced around an action, movement modes on the
board, charge variants, mounted combat, the monk's slow fall, quivering palm and abundant
step, a full attack of throws, and the run — each feat's clause measured through the engine.

The ledger (docs/feats-partial-ledger.md, groups 1, 2, 8, 14, 23, 26, 27 and 40) named each
clause the engine did not run; every test here names the measurement it was taken against.
"""
from __future__ import annotations

import re

import pytest

from rules import bodyskills
from rules import feat_moves
from rules import stepping
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import new_turn


class _Faces(Dice):
    """Each roll whose label starts with a key lands on that key's face; the rest roll
    seeded."""

    def __init__(self, faces: dict | None = None):
        super().__init__(seed=20261127)
        self.faces = dict(faces or {})

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        for prefix, face in self.faces.items():
            if (label or "").startswith(prefix):
                if notation == "1d20":
                    return self.given(face, modifiers, label)
                m = re.fullmatch(r"(\d*)d(\d+)", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _pc(cls: str = "fighter", level: int = 8, feats=(), base="fixtures/pc-kesst.json",
        **extra):
    d = to_dict(load_pc(base))
    d.update({"class": cls, "level": level, "ranks": {}})
    d.pop("paths", None)
    d["feats"] = list(feats)
    d["weapons"] = ["rapier", "dagger", "shortbow"]
    d.update(extra)
    pc = from_dict(d, ref="pc")
    pc.goods.update({"arrows": 40})
    return pc


def _board(pc, *foes, at=(5, 5), faces=None, allies=(), size=30):
    """A fight on a square map, the PC's turn: `foes` are (template, (x, y)), refs c1.."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc, at=at)
    for a, square in allies:
        s.add(a, at=square)
    for i, (template, square) in enumerate(foes, start=1):
        s.add(instantiate(template, scene=s, name=f"the {template} {i}"), at=square)
    s.grid = Grid(width=size, height=size)
    mine = {a.ref for a, _ in allies}
    them = [r for r in s.actors if r != pc.ref and r not in mine]
    s.initiative = [(pc.ref, 30)] + [(a.ref, 20) for a, _ in allies] + [
        (r, 10 - i) for i, r in enumerate(them)]
    s.sides = {"pc": [pc.ref] + sorted(mine), "them": them}
    s.round, s.turn = 1, 0
    s.resync_zones()
    for ref in s.actors:                   # everyone has acted: nobody is flat-footed
        s.acted.add(ref) if isinstance(s.acted, set) else s.acted.append(ref)
    return s, Engine(s, dice=_Faces(faces))


def _settle(e, res):
    while res.awaiting:
        label = str(res.awaiting.get("label") or "")
        face = next((f for k, f in e.dice.faces.items() if label.startswith(k)), 10)
        res = e.resume(max(int(res.awaiting.get("min") or 1),
                           min(face, int(res.awaiting.get("max") or 20))))
    return res


def _run(e, *raws):
    return _settle(e, e.run(e.validate([dict({"because": "test"}, **r) for r in raws])))


def _move(x, y, actor="pc"):
    return {"op": "move", "actor": actor, "params": {"square": [x, y]}}


def _hit(target="c1", actor="pc", **params):
    return {"op": "attack", "actor": actor, "target": target, "visibility": "hidden",
            "params": params}


def _tells(res) -> str:
    return " ".join(o.tell or "" for o in res.outcomes)


def _of(res, op, actor="pc"):
    return [o for o in res.outcomes if o.op == op and o.actor == actor]


def _named(roll, name: str) -> int:
    d = roll.as_dict() if hasattr(roll, "as_dict") else roll
    return sum(int(m["value"]) for m in d.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


# --- group 1: moves spliced around an action ------------------------------------------------

def test_a_move_a_shot_and_another_move_is_three_actions_and_the_third_is_refused():
    """CRB, Action Types: a standard and a move, or a full-round action. Measured before:
    a fighter walked 30 ft, shot, and walked 30 ft more in one batch, every part resolved —
    nothing asked a walk what the turn had left."""
    pc = _pc()
    s, e = _board(pc, ("thug", (20, 5)), faces={"Attack with": 15})
    res = _run(e, _move(11, 5), _hit(weapon="shortbow"), _move(5, 5))
    assert _of(res, "move")[0].status == "resolved"
    refused = [o for o in res.outcomes if o.status == "refused"]
    assert [o.code for o in refused] == ["standard_spent"], _tells(res)
    assert tuple(s.positions["pc"])[:2] == (11, 5)


def test_shot_on_the_run_splits_one_speed_of_walking_around_a_single_shot():
    """Shot on the Run (CRB): "As a full-round action, you can move up to your speed and
    make a single ranged attack at any point during your movement." Measured before (its
    not_yet line): a turn moved once, before or after its blow. Now 15 ft, the shot, and
    the 15 ft left go; a walk past what is left is refused with the feet."""
    pc = _pc(feats=["Dodge", "Mobility", "Point-Blank Shot", "Shot on the Run"])
    s, e = _board(pc, ("thug", (20, 5)), faces={"Attack with": 15})
    res = _run(e, _move(8, 5), _hit(weapon="shortbow"))
    assert feat_moves.allowance(pc).payload["feet"] == 15, _tells(res)
    too_far = _run(e, _move(8, 9))
    assert too_far.outcomes[0].code == "too_far", _tells(too_far)
    ok = _run(e, _move(8, 8))
    assert ok.outcomes[0].status == "resolved", _tells(ok)
    assert feat_moves.allowance(pc) is None
    again = _run(e, _move(8, 7))
    assert again.outcomes[0].code == "standard_spent", _tells(again)


def test_shot_on_the_run_is_for_a_ranged_attack_only():
    """Normal: "You cannot move before and after an attack with a ranged weapon" — the
    feat names a ranged attack; a melee blow after a walk earns no second walk."""
    pc = _pc(feats=["Dodge", "Mobility", "Point-Blank Shot", "Shot on the Run"])
    s, e = _board(pc, ("thug", (9, 5)), faces={"Attack with": 15})
    _run(e, _move(8, 5), _hit(weapon="rapier"))
    assert feat_moves.allowance(pc) is None
    assert _run(e, _move(5, 5)).outcomes[0].code == "standard_spent"


def test_a_five_foot_step_then_a_coup_de_grace_is_allowed():
    """CRB: a 5-foot step may go with a full-round action. Measured before this lane: the
    step wrote `Scene.move_spent`, and the coup de grâce behind it was refused "already
    moved this turn"."""
    pc = _pc()
    s, e = _board(pc, ("thug", (7, 5)), faces={"Attack with": 15})
    s.get("c1").add_condition("helpless", source="bound hand and foot")
    res = _run(e, _move(6, 5), _hit(weapon="rapier", coup_de_grace=True))
    coup = _of(res, "attack")[-1]
    assert coup.status == "resolved", _tells(res)


def test_slaying_sprint_walks_half_speed_with_a_coup_de_grace():
    """Slaying Sprint (UC): "You can move up to half your speed instead of taking a 5-foot
    step when taking a full-round action to perform a coup de grace." Measured before (its
    not_yet line): the coup spent the move, so no move followed it — and a walk before it
    refused the coup."""
    def sleeper(s):
        s.get("c1").add_condition("helpless", source="bound hand and foot")

    plain = _pc()
    s, e = _board(plain, ("thug", (9, 5)), faces={"Attack with": 15})
    sleeper(s)
    res = _run(e, _move(8, 5), _hit(weapon="rapier", coup_de_grace=True))
    assert _of(res, "attack")[-1].status == "refused", _tells(res)

    pc = _pc(level=13, feats=["Dodge", "Mobility", "Spring Attack", "Slaying Sprint"])
    s, e = _board(pc, ("thug", (9, 5)), faces={"Attack with": 15})
    sleeper(s)
    res = _run(e, _move(8, 5), _hit(weapon="rapier", coup_de_grace=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)

    pc2 = _pc(level=13, feats=["Dodge", "Mobility", "Spring Attack", "Slaying Sprint"])
    s, e = _board(pc2, ("thug", (6, 5)), faces={"Attack with": 15})
    sleeper(s)
    res = _run(e, _hit(weapon="rapier", coup_de_grace=True), _move(5, 8))
    assert _of(res, "move")[-1].status == "resolved", _tells(res)
    assert tuple(s.positions["pc"])[:2] == (5, 8)


def _wand(pc, spell="magic-missile"):
    from rules import spellitems

    pc.add_stock(spellitems.make("wand", spell, how="bought"), 1)
    sid = next(k for k, v in pc.stock.items() if spellitems.kind_of(v) == "wand")
    return pc.stock[sid].name


def test_wand_dancer_moves_before_and_after_the_wand_and_spares_its_target():
    """Wand Dancer (UM): "you can move both before and after triggering the item, as long
    as the total distance moved is not greater than your speed ... Your movement does not
    provoke attacks of opportunity from that creature only." Measured before (its not_yet
    line): no split move was kept around a use."""
    pc = _pc(cls="wizard", feats=["Dodge", "Mobility", "Wand Dancer"])
    name = _wand(pc)
    s, e = _board(pc, ("thug", (12, 5)), faces={"Attack with": 15})
    res = _run(e, _move(10, 5), {"op": "use_item", "actor": "pc", "params": {
        "item": name, "power": "magic-missile", "to": "c1"}})
    assert feat_moves.allowance(pc) is not None, _tells(res)
    assert feat_moves.allowance(pc).payload["feet"] == 5
    assert pc.has_state("movement.unprovoking.c1")
    away = _run(e, _move(9, 5))
    assert away.outcomes[0].status == "resolved", _tells(away)
    assert not [o for o in away.outcomes if o.op == "attack" and o.actor == "c1"]


# --- Tiger Pounce -----------------------------------------------------------------------------

def _tiger(pc):
    pc.apply_effect(ActiveEffect(name="tiger style", kind="buff", key="tiger style",
                                 source="Tiger Style", origin="rule:feat-tiger-style",
                                 tags=("style.tiger-style",)))


def test_tiger_pounce_pays_a_half_speed_move_closer_with_the_swift_action():
    """Tiger Pounce (UC): "once per round as a swift action, you can move up to half your
    speed closer to a target you hit with an unarmed strike ... on this turn or your last
    turn." Measured before (its not_yet line): a swift move was not priced. Now, with the
    turn's move and standard spent, 15 ft back toward the foe struck is the swift action;
    further, or away, is refused."""
    feats = ["Improved Unarmed Strike", "Power Attack", "Tiger Style", "Tiger Claws",
             "Tiger Pounce"]
    pc = _pc(cls="monk", level=9, feats=feats)
    _tiger(pc)
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 18})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="unarmed"), _move(5, 11))
    assert _of(res, "move")[-1].status == "resolved", _tells(res)
    far = _run(e, _move(5, 7))
    assert far.outcomes[0].code == "standard_spent", _tells(far)
    away = _run(e, _move(5, 13))
    assert away.outcomes[0].code == "standard_spent", _tells(away)
    closer = _run(e, _move(5, 8))
    assert closer.outcomes[0].status == "resolved", _tells(closer)
    assert s.swift_spent.get("pc") == s.round
    again = _run(e, _move(5, 7))
    assert again.outcomes[0].code == "standard_spent", _tells(again)


# --- Ride-By Attack and Mounted Blade ---------------------------------------------------------

def _mounted(feats, foes=(("thug", (14, 3)),), faces=None):
    """A rider on a war-trained heavy horse (Large: its anchor is the rider's square, the
    body reaching east and south), charging north at a thug ahead and to the left."""
    pc = _pc(feats=["Mounted Combat"] + list(feats))
    pc.ranks["ride"] = 8
    s, e = _board(pc, *foes, at=(15, 15), faces=faces)
    horse = s.add(instantiate("heavy-horse", scene=s, name="the bay"), at=(15, 15))
    horse.apply_effect(ActiveEffect(name="trained for war", kind="trait", key="war-trained",
                                    source="test", origin="author:test",
                                    tags=("trained.combat-riding",)))
    s.sides["pc"].append(horse.ref)
    s.initiative.insert(1, (horse.ref, 25))
    pc.apply_effect(ActiveEffect(name="riding the bay", kind="situation", key="mounted",
                                 source=bodyskills.RIDE_SOURCE, origin=bodyskills.RIDE_SOURCE,
                                 tags=(bodyskills.MOUNTED,), payload={"mount": horse.ref}))
    horse.apply_effect(ActiveEffect(name="ridden", kind="situation", key="ridden",
                                    source=bodyskills.RIDE_SOURCE,
                                    origin=bodyskills.RIDE_SOURCE,
                                    tags=(bodyskills.RIDDEN,), payload={"by": pc.ref}))
    bodyskills.carry_rider(s, horse.ref)
    s.resync_zones()
    return s, e, pc, horse


def test_after_a_mounted_charge_the_steed_moves_no_further_without_ride_by_attack():
    """A charge is the whole round (CRB, Combat, Charge), the mount's as much as the
    rider's. Measured before: after a mounted charge the rider walked the horse on again,
    a double move on top of the charge."""
    s, e, pc, horse = _mounted([], faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="rapier", charge=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)
    here = tuple(s.positions[horse.ref])[:2]
    after = _run(e, _move(here[0], here[1] + 3))
    assert after.outcomes[0].code == "standard_spent", _tells(after)


def test_ride_by_attack_moves_on_down_the_line_of_the_charge():
    """Ride-By Attack (CRB): "you may move and attack as if with a standard charge and then
    move again (continuing the straight line of the charge). Your total movement for the
    round can't exceed double your mounted speed. You and your mount do not provoke an
    attack of opportunity from the opponent that you attack." Measured before (its not_yet
    line): nothing moved after a mounted charge, and the charged foe swung as they rode
    off."""
    s, e, pc, horse = _mounted(["Ride-By Attack"], faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="rapier", charge=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)
    owed = feat_moves.allowance(horse)
    assert owed is not None, _tells(res)
    here = tuple(s.positions[horse.ref])[:2]
    off_line = _run(e, _move(here[0] + 4, here[1]))
    assert off_line.outcomes[0].code == "off_the_line", _tells(off_line)
    on = _run(e, _move(here[0], here[1] - 3))
    assert on.outcomes[0].status == "resolved", _tells(on)
    assert not [o for o in on.outcomes if o.op == "attack" and o.actor == "c1"], _tells(on)


def test_mounted_blade_strikes_a_second_foe_beside_the_first_at_minus_five():
    """Mounted Blade (UC): "When you use the Ride-By Attack feat, if your attack hits, you
    may also make an attack against a target adjacent to your original target. This
    additional attack has a -5 penalty." Measured before (its not_yet line): Ride-By
    Attack was not built, and no second blow came."""
    s, e, pc, horse = _mounted(["Ride-By Attack", "Mounted Blade"],
                               foes=(("thug", (14, 3)), ("thug", (14, 4))),
                               faces={"Attack with": 15})
    for ref in ("c1", "c2"):
        s.get(ref).hp = s.get(ref).hp_max = 400
    res = _run(e, _hit(weapon="rapier", charge=True))
    blows = _of(res, "attack")
    assert len(blows) == 2 and blows[1].blows[0]["ref"] == "c2", _tells(res)
    second = [r for r in blows[1].rolls if (r.label or "").startswith("Attack with")][0]
    assert _named(second, "Mounted Blade") == -5


def test_tiger_pounce_moves_power_attacks_penalty_onto_ac_until_the_next_turn():
    """Tiger Pounce (UC): "While using the Tiger Style feat, you can apply the penalty from
    Power Attack to your AC instead of attack rolls." Measured before (its not_yet line): no
    option moved Power Attack's penalty — the -3 at base attack +9 always came off the
    blow. Now the blow keeps its bonus, the damage keeps Power Attack's +6, and AC is 3
    lower until the next turn; without Tiger Style the option is refused."""
    feats = ["Improved Unarmed Strike", "Power Attack", "Tiger Style", "Tiger Claws",
             "Tiger Pounce"]
    pc = _pc(cls="fighter", level=9, feats=feats,
             abilities={"str": 16, "dex": 17, "con": 12, "int": 13, "wis": 10, "cha": 14})
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    with pytest.raises(IntentError, match="Tiger Style"):
        _run(e, _hit(weapon="unarmed", power_attack=True, tiger_pounce=True))
    _tiger(pc)
    new_turn(s)
    ac = pc.ac()
    plain = _run(e, _hit(weapon="unarmed", power_attack=True))
    plain_roll = [r for r in _of(plain, "attack")[0].rolls
                  if (r.label or "").startswith("Attack with")][0]
    new_turn(s)
    res = _run(e, _hit(weapon="unarmed", power_attack=True, tiger_pounce=True))
    roll = [r for r in _of(res, "attack")[0].rolls
            if (r.label or "").startswith("Attack with")][0]
    assert roll.total - plain_roll.total == 3, _tells(res)
    assert pc.ac() == ac - 3
