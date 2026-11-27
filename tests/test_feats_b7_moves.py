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

def _mounted(feats, foes=(("thug", (14, 3)),), faces=None, at=(15, 15)):
    """A rider on a war-trained heavy horse (Large: its anchor is the rider's square, the
    body reaching east and south), charging north at a thug ahead and to the left."""
    pc = _pc(feats=["Mounted Combat"] + list(feats))
    pc.ranks["ride"] = 8
    s, e = _board(pc, *foes, at=at, faces=faces)
    horse = s.add(instantiate("heavy-horse", scene=s, name="the bay"), at=at)
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


# --- group 40: the run ----------------------------------------------------------------------

def test_a_straight_walk_past_a_double_move_is_a_run_that_spends_the_round_and_the_dex():
    """CRB, Run: "You can run as a full-round action ... up to four times your speed in a
    straight line ... You lose any Dexterity bonus to AC unless you have the Run feat."
    Measured before (the Run feat's not_yet line): no action carried a body past its
    speed — 90 ft in a line was refused "too far". Now it runs, the round is spent, and the
    runner is denied Dexterity until the round ends."""
    pc = _pc()
    s, e = _board(pc, ("thug", (5, 28)), at=(2, 2))
    res = _run(e, _move(20, 2))
    went = _of(res, "move")[0]
    assert went.status == "resolved" and "runs 90 ft" in went.tell, _tells(res)
    assert pc.has_state("state.moving.running") and pc.loses_dex_to_ac
    assert s.standard_spent.get("pc") == s.round
    assert _run(e, _move(26, 2)).outcomes[0].code == "standard_spent"
    blow = _run(e, _hit(target="c1", weapon="shortbow"))
    assert _of(blow, "attack")[0].status == "refused"


def test_the_run_feat_runs_five_times_speed_and_keeps_the_dexterity():
    """Run (CRB): "you move five times your normal speed ... While running, you retain
    your Dexterity bonus to your Armor Class." Measured before: the feat's only working
    clause was the jump's +4."""
    pc = _pc(feats=["Run"])
    s, e = _board(pc, ("thug", (5, 28)), at=(0, 2))
    res = _run(e, _move(28, 2))
    assert "runs 140 ft" in _of(res, "move")[0].tell, _tells(res)
    assert pc.has_state("state.moving.running") and not pc.loses_dex_to_ac


def test_a_run_needs_a_straight_line_clear_of_difficult_ground():
    """CRB, Run: "You can't run across difficult terrain". A route around is a walk, not a
    run, so the far square stays out of reach."""
    pc = _pc()
    s, e = _board(pc, ("thug", (5, 28)), at=(2, 2))
    s.grid.difficult.add((10, 2))
    with pytest.raises(IntentError):
        _run(e, _move(20, 2))


def test_endurance_helps_the_constitution_check_to_keep_running():
    """CRB, Run: past rounds equal to the Constitution score, "a DC 10 Constitution check
    to continue running"; failed, the runner stops and must rest a minute. Endurance (CRB):
    +4 on "Constitution checks made to continue running". Measured before (its not_yet
    line): running was not an action, and the check never rolled."""
    def runner(feats, face):
        pc = _pc(feats=feats)
        s, e = _board(pc, ("thug", (5, 28)), at=(2, 2), faces={"Kesst Vayr Constitution": face})
        held = ActiveEffect(name="running", kind="situation", key=feat_moves.RUN_STREAK,
                            source="Run", origin="rule:run", duration="rounds", rounds_left=2,
                            payload={"rounds": pc.ability_score("con"), "checks": 0,
                                     "round": 0})
        pc.apply_effect(held)
        return pc, s, _run(e, _move(20, 2))

    pc, s, res = runner([], 7)               # 7 + 1 (Con 12) = 8 < 10
    assert _of(res, "move")[0].status == "prevented", _tells(res)
    assert pc.has_state(feat_moves.RUN_SPENT)
    pc, s, res = runner(["Endurance"], 7)    # 8 + 4 = 12
    assert _of(res, "move")[0].status == "resolved", _tells(res)


def test_sliding_axe_throw_slides_under_a_charging_targets_shield():
    """Sliding Axe Throw (APG): "If the target is flat-footed, running, or charging, this
    attack ignores any bonuses to the target's AC from its shield." Measured before (its
    not_yet line): no running or charging state was asked — a charging shieldbearer's +2
    stood against the axe."""
    foe = load_pc("fixtures/pc-borin.json")
    foe.ref, foe.kind = "c1", "npc"
    foe.hp = foe.hp_max = 400
    pc = _pc(feats=["Sliding Axe Throw"], weapons=["handaxe", "handaxe"])
    s, e = _board(pc, faces={"Attack with": 10}, allies=())
    s.add(foe, at=(8, 5))
    s.sides["them"] = ["c1"]
    s.initiative.append(("c1", 5))
    s.acted.add("c1") if isinstance(s.acted, set) else s.acted.append("c1")
    plain = _of(_run(e, _hit(weapon="handaxe", thrown=True, sliding_axe_throw=True)),
                "attack")[0]
    foe.apply_effect(ActiveEffect(name="charging", kind="buff", key="charging",
                                  source="Charge", origin="rule:charging", duration="rounds",
                                  rounds_left=1, tags=("buff.stance.charging",)))
    new_turn(s)
    slid = _of(_run(e, _hit(weapon="handaxe", thrown=True, sliding_axe_throw=True)),
               "attack")[0]
    assert "shield slid under" not in plain.dc["explain"], plain.dc
    assert "-2 the shield slid under" in slid.dc["explain"], slid.dc


def test_a_rider_shooting_from_a_running_mount_takes_minus_eight_or_minus_four_archer():
    """CRB, Mounted Combat: "-4 penalty on ranged attacks" from a double-moving mount, "-8
    if your mount is running"; Mounted Archery (CRB) halves it. Measured before (its
    not_yet line): the mount's double move and run were not tracked."""
    for feats, want in (([], -8), (["Mounted Archery"], -4)):
        s, e, pc, horse = _mounted(feats, foes=(("thug", (2, 2)),),
                                   faces={"Attack with": 10}, at=(15, 27))
        s.get("c1").hp = s.get("c1").hp_max = 400
        run = _run(e, _move(15, 2))
        assert horse.has_state("state.moving.running"), _tells(run)
        res = _run(e, _hit(weapon="shortbow"))
        roll = [r for r in _of(res, "attack")[0].rolls
                if (r.label or "").startswith("Attack with")][0]
        assert _named(roll, "shooting from a running mount") == want, _tells(res)


def test_dragon_style_charges_through_difficult_ground_and_an_ally():
    """Dragon Style (UC): "you can charge or run through difficult terrain and through
    squares occupied by allies". Measured before (its not_yet line): every charge line
    crossing rubble or a friend was refused."""
    ally = _pc(base="fixtures/pc-borin.json")
    ally.ref, ally.kind = "ally", "npc"
    pc = _pc(feats=["Improved Unarmed Strike", "Dragon Style"],
             abilities={"str": 14, "dex": 17, "con": 14, "int": 13, "wis": 14, "cha": 14})
    pc.ranks["acrobatics"] = 3
    s, e = _board(pc, ("thug", (12, 5)), at=(2, 5), allies=((ally, (5, 5)),),
                  faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    s.grid.difficult.add((8, 5))
    refused = _run(e, _hit(weapon="rapier", charge=True))
    assert _of(refused, "attack")[0].status == "refused", _tells(refused)
    pc.apply_effect(ActiveEffect(name="dragon style", kind="buff", key="dragon style",
                                 source="Dragon Style", origin="rule:feat-dragon-style",
                                 tags=("style.dragon-style",)))
    new_turn(s)
    res = _run(e, _hit(weapon="rapier", charge=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)


# --- group 2: crawling and standing up ------------------------------------------------------

def _prone(actor):
    actor.add_condition("prone", source="test")


def _stand(actor="pc"):
    return {"op": "condition", "actor": actor,
            "params": {"condition": "prone", "to": actor, "ends": True}}


def test_a_prone_body_crawls_five_feet_and_its_step_provokes():
    """CRB, Crawl: "You can crawl 5 feet as a move action. Crawling incurs attacks of
    opportunity ... You cannot take a 5-foot step while crawling." Measured before (Fast
    Crawl's not_yet line): no move asked whether the mover was prone — a prone fighter
    walked 30 ft, and a crawl out of a thug's reach was a free 5-foot step."""
    pc = _pc()
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 2})
    _prone(pc)
    with pytest.raises(IntentError, match="5 ft of movement"):
        _run(e, _move(5, 8))
    res = _run(e, _move(4, 5))
    assert [o for o in res.outcomes if o.op == "attack" and o.actor == "c1"], _tells(res)
    assert s.move_spent.get("pc") == s.round


def test_fast_crawl_crawls_at_half_speed_and_steps():
    """Fast Crawl (APG): "While prone, you can move at half speed ... You can take a
    5-foot step while crawling." Measured before: its whole benefit was a not_yet line."""
    pc = _pc(feats=["Fast Crawl"])
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 2})
    _prone(pc)
    res = _run(e, _move(4, 5))
    assert not [o for o in res.outcomes if o.op == "attack" and o.actor == "c1"], _tells(res)
    new_turn(s)
    far = _run(e, _move(4, 8))
    assert _of(far, "move")[-1].status == "resolved", _tells(far)


def test_standing_up_is_a_move_action_that_provokes():
    """CRB, Stand Up: "Standing up from a prone position requires a move action and
    provokes attacks of opportunity." Measured before (Monkey Style's not_yet line):
    standing up cost nothing and drew no swing."""
    pc = _pc()
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 2})
    _prone(pc)
    res = _run(e, _stand())
    assert [o for o in res.outcomes if o.op == "attack" and o.actor == "c1"], _tells(res)
    assert not pc.has_state("state.position.prone")
    assert s.move_spent.get("pc") == s.round


def test_monkey_style_stands_without_provoking_and_as_a_swift_action_on_dc_20():
    """Monkey Style (UC): "you can crawl and stand up from lying prone without provoking
    attacks of opportunity, and you can stand up as a swift action if you succeed at a DC
    20 Acrobatics check." Measured before (its not_yet line): standing up was not an
    action the engine priced."""
    feats = ["Improved Unarmed Strike", "Monkey Style"]
    for face, swift in ((19, True), (2, False)):
        pc = _pc(cls="monk", level=6, feats=feats)
        pc.ranks["acrobatics"] = 6
        s, e = _board(pc, ("thug", (6, 5)),
                      faces={"Attack with": 2, "Kesst Vayr Acrobatics": face})
        pc.apply_effect(ActiveEffect(name="monkey style", kind="buff", key="monkey style",
                                     source="Monkey Style", origin="rule:feat-monkey-style",
                                     tags=("style.monkey-style",)))
        _prone(pc)
        res = _run(e, _stand())
        assert not [o for o in res.outcomes if o.op == "attack" and o.actor == "c1"]
        assert not pc.has_state("state.position.prone"), _tells(res)
        assert (s.swift_spent.get("pc") == s.round) is swift, _tells(res)
        assert (s.move_spent.get("pc") == s.round) is not swift, _tells(res)
        crawl = _pc(cls="monk", level=6, feats=feats)
        s, e = _board(crawl, ("thug", (6, 5)), faces={"Attack with": 2})
        crawl.apply_effect(ActiveEffect(name="monkey style", kind="buff", key="monkey style",
                                        source="Monkey Style", origin="rule:feat-monkey-style",
                                        tags=("style.monkey-style",)))
        _prone(crawl)
        away = _run(e, _move(4, 5))
        assert not [o for o in away.outcomes if o.op == "attack" and o.actor == "c1"]


def test_monkey_moves_climbs_at_half_speed_with_dexterity_and_steps_after_two_hits():
    """Monkey Moves (UC): "climb and crawl at half your speed ... you retain your Dexterity
    bonus to AC while climbing ... when you use your unarmed strike to hit an opponent
    twice or more on your turn, you can spend a swift action to take a 5-foot step even if
    you have moved this round." Measured before (its not_yet line): a climb went a quarter
    of speed and dropped Dexterity, and no step followed a walk."""
    from rules import bodyskills as bs

    feats = ["Improved Unarmed Strike", "Monkey Style", "Monkey Moves"]
    pc = _pc(cls="monk", level=8, feats=feats)
    pc.apply_effect(ActiveEffect(name="monkey style", kind="buff", key="monkey style",
                                 source="Monkey Style", origin="rule:feat-monkey-style",
                                 tags=("style.monkey-style",)))
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 18, "Climb": 19})
    s.get("c1").hp = s.get("c1").hp_max = 400
    climbed = _run(e, {"op": "check", "actor": "pc",
                       "params": {"skill": "climb", "dc": {"band": "tough"},
                                  "height_ft": 60}})
    held = next(x for x in pc.effects if bs.CLIMBING in (x.tags or ()))
    assert held.payload["at"] == pc.speed_feet // 2, _tells(climbed)
    assert not pc.loses_dex_to_ac
    pc.remove_effects(match=lambda x: bs.CLIMBING in (x.tags or ()))
    new_turn(s)
    s.positions["pc"] = (4, 5)
    first = _run(e, _move(5, 5), _hit(weapon="unarmed", full_attack=True))
    assert len([b for o in _of(first, "attack") for b in o.blows
                if b["result"] == "hit"]) >= 2, _tells(first)
    step = _run(e, _move(5, 6))
    assert _of(step, "move")[-1].status == "resolved", _tells(step)
    assert s.swift_spent.get("pc") == s.round


# --- group 8: charge variants ---------------------------------------------------------------

def test_charging_hurler_charges_to_throwing_range_and_throws():
    """Charging Hurler (APG): "use the charge rules to make a thrown weapon attack ... you
    must only move closer to your opponent, and you must end your movement within 30 feet
    of that opponent", with the charge's +2. Measured before (its not_yet line): a charge's
    walk always ended within melee reach, so a thrown charge was never laid."""
    pc = _pc(feats=["Point-Blank Shot", "Charging Hurler"], weapons=["javelin", "javelin"])
    s, e = _board(pc, ("thug", (20, 5)), at=(2, 5), faces={"Attack with": 10})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="javelin", thrown=True, charge=True))
    blow = _of(res, "attack")[-1]
    assert blow.status == "resolved", _tells(res)
    gap = e._gap_ft(pc, s.get("c1"))
    assert 5 < gap <= 30, gap
    roll = [r for r in blow.rolls if (r.label or "").startswith("Attack with")][0]
    assert _named(roll, "charging") == 2
    assert pc.has_state("buff.stance.charging")


def test_improved_charging_hurler_throws_from_further_and_adds_two_damage_close():
    """Improved Charging Hurler (APG): "your target can be at any range up to your
    weapon's maximum range. If your target is within 30 feet, you gain a +2 bonus on damage
    rolls." Measured before (its not_yet line): nothing of Charging Hurler existed to
    widen. A javelin (30 ft increment) charges to end 10 ft on, far beyond 30 ft."""
    pc = _pc(feats=["Point-Blank Shot", "Charging Hurler", "Improved Charging Hurler"],
             weapons=["javelin", "javelin"])
    s, e = _board(pc, ("thug", (28, 5)), at=(2, 5), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="javelin", thrown=True, charge=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)
    assert tuple(s.positions["pc"])[:2] == (4, 5)
    near = _pc(feats=["Point-Blank Shot", "Charging Hurler", "Improved Charging Hurler"],
               weapons=["javelin"])
    s, e = _board(near, ("thug", (12, 5)), at=(2, 5), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="javelin", thrown=True, charge=True))
    dmg = [r for o in _of(res, "attack") for r in o.rolls
           if not (r.label or "").startswith(("Attack with", "Confirm"))]
    assert any(_named(r, "Improved Charging Hurler") == 2 for r in dmg), _tells(res)


# --- Swap Places and Cleave Through ---------------------------------------------------------

def test_swap_places_trades_squares_with_an_ally_who_has_the_feat():
    """Swap Places (UC): "you can move into your ally's square as part of normal movement.
    At the same time, your ally moves into your previous space as an immediate action."
    Measured before (its not_yet line): a move into an occupied square was refused."""
    ally = _pc(base="fixtures/pc-borin.json", feats=["Swap Places"])
    ally.ref, ally.kind = "ally", "npc"
    pc = _pc(feats=["Swap Places"])
    s, e = _board(pc, ("thug", (15, 15)), at=(5, 5), allies=((ally, (6, 5)),))
    res = _run(e, _move(6, 5))
    assert _of(res, "move")[0].status == "resolved", _tells(res)
    assert tuple(s.positions["pc"])[:2] == (6, 5)
    assert tuple(s.positions["ally"])[:2] == (5, 5)
    assert s.swift_spent.get("ally") is not None
    plain = _pc()
    other = _pc(base="fixtures/pc-borin.json")
    other.ref, other.kind = "ally", "npc"
    s, e = _board(plain, ("thug", (15, 15)), at=(5, 5), allies=((other, (6, 5)),))
    with pytest.raises(IntentError, match="taken"):
        _run(e, _move(6, 5))


def test_cleave_through_steps_to_bring_a_new_foe_into_reach():
    """Cleave Through (Dwarves of Golarion): "if your initial attack hits, you may take a
    single 5-foot step as a free action before making your additional attacks", and a foe
    it brings into reach is a legal target. Measured before (its not_yet line): the cleave
    ended "no other foe stands beside" when the second foe was 10 ft away."""
    feats = ["Power Attack", "Cleave", "Cleave Through"]
    pc = _pc(level=11, feats=feats,
             abilities={"str": 16, "dex": 17, "con": 12, "int": 13, "wis": 10, "cha": 14})
    s, e = _board(pc, ("thug", (6, 5)), ("thug", (7, 6)), at=(5, 5),
                  faces={"Attack with": 18})
    for ref in ("c1", "c2"):
        s.get(ref).hp = s.get(ref).hp_max = 400
    res = _run(e, _hit(weapon="rapier", cleave=True))
    blows = _of(res, "attack")
    assert [o.blows[0]["ref"] for o in blows] == ["c1", "c2"], _tells(res)
    assert tuple(s.positions["pc"])[:2] != (5, 5)
    assert stepping.walked(s, "pc") == "step"


# --- group 27: a full attack of throws ------------------------------------------------------

def test_quick_draw_throws_daggers_at_the_full_rate_each_one_landing():
    """Quick Draw (CRB): "A character who has selected this feat may throw weapons at his
    full normal rate of attacks." Measured before (its not_yet line): a thrown weapon was
    one throw an op — a level-8 fighter's full attack of daggers threw one."""
    pc = _pc(feats=["Quick Draw"], weapons=["dagger", "dagger", "dagger"])
    s, e = _board(pc, ("thug", (8, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="dagger", thrown=True, full_attack=True))
    blows = [b for o in _of(res, "attack") for b in o.blows]
    assert len(blows) == 2, _tells(res)
    assert pc.weapons.count("dagger") == 1
    plain = _pc(weapons=["dagger", "dagger", "dagger"])
    s, e = _board(plain, ("thug", (8, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _hit(weapon="dagger", thrown=True, full_attack=True))
    assert len([b for o in _of(res, "attack") for b in o.blows]) == 1, _tells(res)
    again = _run(e, _hit(weapon="dagger", thrown=True, iteration=1))
    assert _of(again, "attack")[0].code == "one_throw", _tells(again)


def test_a_two_handed_throw_is_the_whole_round_without_two_handed_thrower():
    """Two-Handed Thrower (APG): "Using two hands to throw any weapon requires only a
    standard action for you. If you also have the Quick Draw feat, you can throw two-handed
    weapons at your full normal rate"; Normal: "Throwing a two-handed weapon is a full-round
    action." Measured before (its not_yet line): a spear thrown cost what a dagger did, and
    no full attack of throws was offered."""
    pc = _pc(weapons=["spear"])
    s, e = _board(pc, ("thug", (10, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _move(6, 5), _hit(weapon="spear", thrown=True))
    assert _of(res, "attack")[-1].status == "refused", _tells(res)
    feats = ["Quick Draw", "Two-Handed Thrower"]
    pc = _pc(feats=feats, weapons=["spear", "spear"],
             abilities={"str": 15, "dex": 17, "con": 12, "int": 13, "wis": 10, "cha": 14})
    s, e = _board(pc, ("thug", (10, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    res = _run(e, _move(6, 5), _hit(weapon="spear", thrown=True))
    assert _of(res, "attack")[-1].status == "resolved", _tells(res)
    new_turn(s)
    res = _run(e, _hit(weapon="spear", thrown=True, full_attack=True))
    assert len([b for o in _of(res, "attack") for b in o.blows]) == 1   # one spear left
    assert "spear" not in pc.weapons


def test_raging_hurler_throws_two_handed_as_a_standard_and_doubles_the_increment():
    """Raging Hurler (APG): "While raging, you can throw a two-handed weapon as a standard
    action, and you double the range increment for weapons you throw." Measured before
    (its not_yet line): neither held. A spear (20 ft) at 35 ft is one increment past the
    first (-2); raging, the increment is 40 ft and there is no penalty."""
    pc = _pc(cls="barbarian", feats=["Throw Anything", "Raging Hurler"], weapons=["spear"])
    s, e = _board(pc, ("thug", (13, 5)), faces={"Attack with": 15})
    s.get("c1").hp = s.get("c1").hp_max = 400
    pc.apply_effect(ActiveEffect(name="rage", kind="condition", key="rage", source="Rage",
                                 origin="ability:barbarian/rage", tags=("buff.stance.rage",)))
    res = _run(e, _move(6, 5), _hit(weapon="spear", thrown=True))
    blow = _of(res, "attack")[-1]
    assert blow.status == "resolved", _tells(res)
    roll = [r for r in blow.rolls if (r.label or "").startswith("Attack with")][0]
    assert _named(roll, "range") == 0, roll.as_dict()


# --- group 23: the monk's slow fall ---------------------------------------------------------

def test_a_monks_slow_fall_shortens_a_fall_beside_a_wall_by_the_class_ladder():
    """CRB, Monk, Slow Fall: "a monk within arm's reach of a wall ... takes damage as if the
    fall were 20 feet shorter" at 4th level, improving "until at 20th level he can ... fall
    any distance without harm." Measured before (Spider Step's and Cloud Step's not_yet
    lines): slow fall was a name on the class table, with no distance read."""
    from rules import bodyskills as bs

    for level, feet, left in ((4, 30, 10), (20, 200, 0), (8, 30, 0)):
        pc = _pc(cls="monk", level=level)
        s, e = _board(pc, ("thug", (20, 20)), at=(5, 5))
        s.grid.blocked.add((4, 5))
        assert feat_moves.slow_fall_ft(pc) in (20, 40, feat_moves.ANY_DISTANCE)
        rolls, fx, said = bs.fall(e, pc, feet)
        slow = [x for x in fx if x.get("kind") == "slow_fall"]
        assert slow and slow[0]["as_feet"] == left, (level, said)
    pc = _pc(cls="monk", level=4)
    s, e = _board(pc, ("thug", (20, 20)), at=(5, 5))
    rolls, fx, said = bs.fall(e, pc, 30)                 # no wall in arm's reach
    assert not [x for x in fx if x.get("kind") == "slow_fall"]
