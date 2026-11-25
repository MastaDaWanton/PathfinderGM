"""Feat loop batch 2, the actions lane: the action economy the feats needed, and each feat's
numbers measured through the engine.

Before this batch (worklist 2026-11-22, b2-actions.tsv): no swift or immediate action was
counted anywhere (two quickened spells in one turn cost nothing, and every "as a swift
action" feat had nothing to spend), there was no charge ("a full-round action this engine
does not compose", `_toward_before`), the grapple had no pin ("damage only — no move/pin/
tie-up", the ledger), and the combat bar's Declare section could offer none of Charge,
Spring Attack, Lunge or Whirlwind Attack. Each test below rolls the real op and reads what
it did.
"""
from __future__ import annotations

import pytest

from rules import feats as feats_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture(autouse=True)
def _prerequisites_met(monkeypatch):
    """Kesst is a 1st-level rogue; the options' prerequisites (BAB +4 for Spring Attack)
    are the feat index's, tested elsewhere. Here every held feat is usable."""
    real = feats_mod.meets
    monkeypatch.setattr(feats_mod, "meets", lambda actor, fid: dict(real(actor, fid),
                                                                     unmet=[]))


@pytest.fixture(autouse=True)
def _the_provoked_swing_waived(monkeypatch):
    """A manoeuvre without its Improved feat provokes (tests/test_reactions.py); the swing
    would land before the manoeuvre these tests read."""
    from rules import reactions as _reactions

    monkeypatch.setattr(_reactions, "provoked_by_maneuver", lambda *a, **k: [])


class _Scripted(Dice):
    """A d20 whose face is chosen by the roll's label (the first matching words), else
    `face`; every other die rolls as usual."""

    def __init__(self, face: int = 10, **by_label):
        super().__init__(seed=20261122)
        self.face = face
        self.by_label = by_label

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation.strip() == "1d20":
            face = next((f for words, f in self.by_label.items()
                         if words.replace("_", " ").lower() in (label or "").lower()),
                        self.face)
            return self.given(face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(pc_at=(2, 10), foe_at=(8, 10), feats=(), foe="thug", dice=None, ally_at=None,
           ally_feats=()):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate(foe, scene=scene, name=f"the {foe}"))
    engine = Engine(scene, dice or _Scripted())
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = pc_at, foe_at
    if ally_at is not None:
        ally = load_pc("fixtures/pc-borin.json")
        ally.ref, ally.kind = "ally", "npc"
        ally.feats = list(ally.feats) + list(ally_feats)
        scene.add(ally)
        scene.positions["ally"] = ally_at
        scene.sides = {"pc": ["pc", "ally"], "them": ["c1"]}
        scene.initiative = [("pc", 20), ("ally", 15), ("c1", 5)]
    else:
        scene.initiative = [("pc", 20), ("c1", 5)]
    scene.turn = 0
    scene.resync_zones()
    return scene, engine, scene.get("pc"), scene.get("c1")


def _run(engine, *raws, face=10):
    res = engine.run(engine.validate([dict({"visibility": "hidden"}, **r) for r in raws]))
    while res.awaiting:
        ask = res.awaiting
        res = engine.resume(max(int(ask.get("min") or 1), min(face, int(ask.get("max") or 20))))
    return res


def _attack(by="pc", target="c1", **params):
    return {"op": "attack", "actor": by, "target": target, "params": params}


def _terms(outcome, label_words: str) -> dict:
    roll = next(r for r in outcome.rolls if label_words in (r.label or ""))
    return {m.source: m.value for m in roll.modifiers}


# --- the swift and immediate budget ---------------------------------------------------

def test_one_swift_action_a_turn_and_an_immediate_off_turn_spends_the_next():
    """CRB: "You can perform only a single swift action per turn"; an immediate taken off
    your turn "counts as your swift action for your next turn". Before this nothing counted
    either: `Scene` had no record of a swift action at all."""
    scene, engine, pc, thug = _fight()
    assert engine._spend_swift(pc) is None
    assert "already used the swift action" in engine._spend_swift(pc)
    # The thug's turn, after Kesst's: an immediate of his spends his own turn, still to
    # come this round? No — his slot (5) is after the turn holder's, so this round's.
    scene.turn = 1
    assert engine._swift_turn(pc) == scene.round + 1
    assert engine._spend_swift(pc) is not None          # a swift off-turn: refused
    scene.acted.add("pc")
    assert engine._spend_swift(pc, immediate=True) is None
    scene.turn = 0
    scene.round += 1
    assert "already used" in (engine._spend_swift(pc) or "")


def test_a_flat_footed_creature_takes_no_immediate_action():
    """CRB: "You also cannot use an immediate action if you are flat-footed." The thug has
    not acted in this fight, so he is flat-footed (`Engine._flat_footed`)."""
    scene, engine, pc, thug = _fight()
    assert "flat-footed" in (engine._spend_swift(thug, immediate=True) or "")


def test_nothing_is_counted_out_of_a_fight():
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=1))
    assert engine._spend_swift(pc) is None and engine._spend_swift(pc) is None


# --- the charge -------------------------------------------------------------------------

def test_a_charge_walks_straight_in_strikes_at_plus_two_and_drops_the_guard():
    """CRB, Charge: up to double speed straight at the foe, "+2 bonus on the attack roll
    and ... a -2 penalty to your AC until the start of your next turn", a full-round
    action. Before this the word charge reached no op at all."""
    scene, engine, pc, thug = _fight(pc_at=(2, 10), foe_at=(8, 10))
    ac = pc.ac()
    res = _run(engine, _attack(charge=True))
    move, blow = res.outcomes[0], next(o for o in res.outcomes if o.op == "attack")
    assert move.op == "move" and "charges 25 ft straight at" in move.tell
    assert scene.positions["pc"][:2] == (7, 10)
    assert _terms(blow, "Attack with")["charging"] == 2
    assert pc.ac() == ac - 2
    assert scene.move_spent["pc"] == scene.standard_spent["pc"] == scene.round
    after = _run(engine, _attack())
    assert after.outcomes[0].status != "resolved" or "already used" in after.outcomes[0].tell


@pytest.mark.parametrize("pc_at,foe_at,words", [
    ((7, 10), (8, 10), "already within reach"),
    ((0, 10), (14, 10), "a charge covers 60 ft"),
    ((7, 10), (8, 10), "at least 10 ft"),
])
def test_a_charge_is_refused_for_the_book_s_reasons(pc_at, foe_at, words):
    """Adjacent (no 10 ft to move), and beyond double speed: refused, with the reason."""
    scene, engine, pc, thug = _fight(pc_at=pc_at, foe_at=foe_at)
    res = _run(engine, _attack(charge=True))
    assert words in res.outcomes[0].tell
    assert scene.positions["pc"][:2] == pc_at


def test_a_charge_line_through_anybody_is_refused():
    """"If any line from your starting space to the ending space ... contains a creature
    (even an ally), you can't charge." Borin stands in the line."""
    scene, engine, pc, thug = _fight(pc_at=(2, 10), foe_at=(8, 10), ally_at=(4, 10))
    res = _run(engine, _attack(charge=True))
    assert "even an ally" in res.outcomes[0].tell
    assert scene.positions["pc"][:2] == (2, 10)


def test_charge_of_the_righteous_keeps_the_guard_against_undead():
    """Charge of the Righteous: "When you charge an undead creature or an evil outsider,
    you do not take the -2 penalty" — the `charge_ac` term, asked of the one charged."""
    scene, engine, pc, bones = _fight(feats=["Charge of the Righteous"], foe="skeleton")
    ac = pc.ac()
    _run(engine, _attack(charge=True))
    assert pc.ac() == ac
    scene, engine, pc, thug = _fight(feats=["Charge of the Righteous"])
    ac = pc.ac()
    _run(engine, _attack(charge=True))
    assert pc.ac() == ac - 2


def test_horde_charge_adds_two_when_an_ally_with_it_charged_this_round():
    """Horde Charge: "When charging during the same round as an ally with this feat, you
    gain a +2 bonus on attack and damage rolls" — Borin's charging stance this round."""
    scene, engine, pc, thug = _fight(feats=["Horde Charge"], ally_at=(12, 4),
                                     ally_feats=["Horde Charge"])
    blow = next(o for o in _run(engine, _attack(charge=True)).outcomes if o.op == "attack")
    assert "Horde Charge" not in _terms(blow, "Attack with")
    scene, engine, pc, thug = _fight(feats=["Horde Charge"], ally_at=(12, 4),
                                     ally_feats=["Horde Charge"])
    engine._lay_attack_stances(scene.get("ally"), ("charge",))
    blow = next(o for o in _run(engine, _attack(charge=True)).outcomes if o.op == "attack")
    assert _terms(blow, "Attack with")["Horde Charge"] == 2


# --- Spring Attack, Whirlwind Attack, Lunge -------------------------------------------------

def test_spring_attack_walks_in_strikes_and_walks_out_without_the_target_s_swing():
    """Spring Attack: "move up to your speed and make a single melee attack without
    provoking any attacks of opportunity from the target ... the total distance that you
    move cannot be greater than your speed". 25 ft in, then 5 ft out is allowed and draws
    no swing; a walk past the remaining 5 ft is refused."""
    scene, engine, pc, thug = _fight(feats=["Spring Attack"])
    res = _run(engine, _attack(spring_attack=True),
               {"op": "move", "actor": "pc", "params": {"square": [6, 10]}})
    ops = [(o.op, o.actor) for o in res.outcomes]
    assert ops[0] == ("move", "") or res.outcomes[0].op == "move"
    assert not any(o.op == "attack" and getattr(o, "actor", "") == "c1" for o in res.outcomes)
    assert scene.positions["pc"][:2] == (6, 10)
    scene, engine, pc, thug = _fight(feats=["Spring Attack"])
    res = _run(engine, _attack(spring_attack=True),
               {"op": "move", "actor": "pc", "params": {"square": [4, 10]}})
    assert "left after the blow" in res.outcomes[-1].tell


def test_whirlwind_attack_strikes_each_foe_in_reach():
    """Whirlwind Attack: "make one melee attack at your highest base attack bonus against
    each opponent within reach" — two thugs beside Kesst, two blows."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=["Whirlwind Attack"])
    scene.add(instantiate("thug", scene=scene, name="the second thug"))
    other = [r for r in scene.actors if r not in ("pc", "c1")][0]
    scene.positions[other] = (6, 10)
    scene.sides = {"pc": ["pc"], "them": ["c1", other]}
    scene.initiative = [("pc", 20), ("c1", 5), (other, 4)]
    res = _run(engine, _attack(whirlwind_attack=True))
    struck = {o.intent_id.rsplit("-", 1)[0] and next(
        (e.get("ref") for e in o.effects if e.get("ref") in ("c1", other)), None)
        for o in res.outcomes if o.op == "attack"}
    assert len([o for o in res.outcomes if o.op == "attack"]) == 2
    assert scene.standard_spent["pc"] == scene.move_spent["pc"] == scene.round


def test_lunge_reaches_ten_feet_on_the_lunger_s_own_turn():
    """Lunge: "increase the reach of your melee attacks by 5 feet until the end of your turn
    by taking a -2 penalty to your AC until your next turn". At 10 ft Kesst strikes without
    a closing step; on the thug's turn her reach is 5 ft again."""
    from rules import reactions

    scene, engine, pc, thug = _fight(pc_at=(6, 10), feats=["Lunge"])
    ac = pc.ac()
    res = _run(engine, _attack(lunge=True))
    assert [o.op for o in res.outcomes][0] == "attack"
    assert scene.positions["pc"][:2] == (6, 10)
    assert pc.ac() == ac - 2
    scene.turn = 1
    from rules.sheet import situated
    with situated(scene):
        assert reactions.reach_with(pc, "rapier")[0] == 5
    scene.turn = 0
    with situated(scene):
        assert reactions.reach_with(pc, "rapier")[0] == 10


# --- the grapple's pin --------------------------------------------------------------------

def _grappling(feats=(), foe="thug", **faces):
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=feats, foe=foe,
                                     dice=_Scripted(15, **faces))
    from rules import reactions as _r

    pc.add_condition("grappled", source="test")
    thug.add_condition("grappled", source="test")
    from rules.engine import _held_by
    _held_by(thug, "grappled", "pc", grappler="pc")
    _held_by(pc, "grappled", "c1", grappler="pc")
    return scene, engine, pc, thug


def test_a_pin_replaces_grappled_and_costs_the_holder_dexterity():
    """CRB p.200, Pin: "You can give your opponent the pinned condition ... you still only
    have the grappled condition, but you lose your Dexterity bonus to AC." Before this a
    maintained grapple could only deal damage."""
    scene, engine, pc, thug = _grappling()
    hp = thug.hp
    res = _run(engine, _attack(manoeuvre="grapple", pin=True))
    assert thug.has_state("state.held.pinned") and not thug.has_condition("grappled")
    assert pc.loses_dex_to_ac and thug.hp == hp
    assert "pins" in res.outcomes[0].tell
    assert engine._holds(pc, thug)
    engine._end_grapple(thug, pc, "test")
    assert not pc.loses_dex_to_ac and not thug.has_state("state.held")


def test_a_chokehold_pins_at_minus_five_and_stops_spoken_spells():
    """Chokehold: "attempt a grapple combat maneuver with a -5 penalty ... you have pinned
    your opponent ... cannot breathe or speak, and thus cannot cast spells that have a
    verbal component"."""
    scene, engine, pc, thug = _grappling(feats=["Chokehold"])
    res = _run(engine, _attack(manoeuvre="grapple", chokehold=True))
    assert _terms(res.outcomes[0], "keeping hold")["a chokehold"] == -5
    assert thug.has_state("state.silenced.choked") and thug.has_state("state.held.pinned")
    engine._end_grapple(thug, pc, "test")
    assert not thug.has_state("state.silenced")


def test_pinning_knockout_doubles_and_pinning_rend_bleeds_on_a_pinned_foe():
    """Pinning Knockout: nonlethal grapple damage on a pinned foe "double your damage
    result"; Pinning Rend: "bleed damage equal to your unarmed strike or weapon damage
    dice". Kesst holds with her fist (nonlethal, 1d3)."""
    scene, engine, pc, thug = _grappling(feats=["Pinning Knockout", "Pinning Rend"])
    pc.equipped = "unarmed"
    _run(engine, _attack(manoeuvre="grapple", pin=True))
    res = _run(engine, _attack(manoeuvre="grapple"))
    o = res.outcomes[0]
    dmg = next(r for r in o.rolls if "Grapple damage" in (r.label or ""))
    hit = next(e for e in o.effects if e.get("kind") == "damage")
    assert hit["amount"] == 2 * max(0, dmg.total)
    assert "Pinning Knockout" in o.tell and "Pinning Rend" in o.tell
    assert any(e.origin == "rule:feat-pinning-rend" for e in thug.effects)


def test_sleeper_hold_knocks_out_after_the_constitution_rounds():
    """Sleeper Hold: after "consecutive rounds equal to your opponent's Constitution bonus
    (minimum 1 round)", Fortitude DC 10 + half level + Str or unconscious 1d4 rounds; -2 AC
    while used. The thug's save is scripted to fail."""
    scene, engine, pc, thug = _grappling(feats=["Sleeper Hold"], sleeper=1)
    ac = pc.ac()
    need = max(1, thug.ability_mod("con"))
    for _ in range(need):
        res = _run(engine, _attack(manoeuvre="grapple", sleeper_hold=True))
    assert pc.ac() == ac - 2
    assert thug.has_condition("unconscious"), res.outcomes[0].tell


# --- the Strike feats on a critical -------------------------------------------------------

def test_tripping_strike_trips_on_a_critical_whose_confirmation_beats_cmd():
    """Tripping Strike: "If your confirmation roll exceeds your opponent's CMD, you may
    knock your opponent prone". A natural 20, confirmed on a 20."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=["Tripping Strike"],
                                     dice=_Scripted(20))
    thug.hp = thug.hp_max = 200            # standing after the blow, to be tripped
    res = _run(engine, _attack())
    assert thug.has_state("state.position.prone")
    assert "Tripping Strike" in res.outcomes[0].tell


def test_disarming_strike_drops_the_weapon_and_only_one_strike_feat_applies():
    """"You can only apply the effects of one of the following feats to a given critical
    hit": Disarming Strike first on the sheet, so the sap drops and the thug stays up."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(20),
                                     feats=["Disarming Strike", "Tripping Strike"])
    thug.hp = thug.hp_max = 200
    held = engine._held_items(thug)
    res = _run(engine, _attack())
    assert held and not engine._held_items(thug)
    assert not thug.has_state("state.position.prone")


# --- the swift and immediate riders ---------------------------------------------------------

def test_felling_smash_trips_after_a_power_attack_hit_for_the_swift_action():
    """Felling Smash: a single attack-action blow with Power Attack that hits "can spend a
    swift action to attempt a trip". The swift is spent; a second rider this turn is not."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(15),
                                     feats=["Power Attack", "Felling Smash"])
    res = _run(engine, _attack(power_attack=True))
    assert any("Felling Smash" in (o.because or "") for o in res.outcomes)
    assert scene.swift_spent.get("pc") == scene.round


def test_drag_down_trips_back_whoever_tripped_you():
    """Drag Down: "Whenever an opponent successfully trips you, you can attempt to trip
    that opponent as an immediate action." The thug trips Kesst; she drags him down."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(15),
                                     feats=["Drag Down"])
    scene.acted.add("pc")
    scene.turn = 1
    res = _run(engine, _attack(by="c1", target="pc", manoeuvre="trip"))
    assert pc.has_state("state.position.prone")
    back = [o for o in res.outcomes if o.op == "attack" and "Kesst Vayr" in o.tell.split(" ")[0:2]
            or o.tell.startswith("Kesst Vayr")]
    assert back and "trip" in back[0].tell


def test_felling_escape_trips_the_holder_after_breaking_free():
    """Felling Escape: "When you break an opponent's grapple ... you can spend a swift
    action to make a trip attempt against that opponent." The thug holds Kesst."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(18),
                                     feats=["Felling Escape"])
    from rules.engine import _held_by
    pc.add_condition("grappled", source="test")
    thug.add_condition("grappled", source="test")
    _held_by(pc, "grappled", "c1", grappler="c1")
    _held_by(thug, "grappled", "pc", grappler="c1")
    res = _run(engine, {"op": "escape", "actor": "pc", "params": {}})
    assert not pc.has_state("state.held")
    assert any("Felling Escape" in (o.because or "") for o in res.outcomes)


def test_dirty_trick_master_turns_a_dazzle_into_a_daze():
    """Dirty Trick Master: against a foe still under a dirty trick, "dazzled to become
    dazed ... lasts for the duration of the dirty trick (including any rounds remaining)"."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(18),
                                     feats=["Dirty Trick Master"])
    thug.add_condition("dazzled", rounds=2, source="dirty trick by the test")
    _run(engine, _attack(manoeuvre="dirty trick", trick="dazzled"))
    assert thug.has_condition("dazed") and not thug.has_condition("dazzled")
    dazed = next(e for e in thug.effects if e.key == "dazed")
    assert dazed.rounds_left > 2


def test_underhanded_teamwork_holds_the_trick_a_round_longer():
    """Underhanded Teamwork: an ally with the feat threatening the same foe "can use an
    immediate action to increase the inflicted condition's duration by 1 round"."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), dice=_Scripted(18),
                                     feats=["Underhanded Teamwork"], ally_at=(9, 10),
                                     ally_feats=["Underhanded Teamwork"])
    scene.acted.add("ally")
    res = _run(engine, _attack(manoeuvre="dirty trick", trick="shaken"))
    trick = next(e for e in thug.effects if e.key == "shaken")
    plain = 1 + max(0, next(o for o in res.outcomes if o.op == "attack").margin or 0) // 5
    assert trick.rounds_left == plain + 1
    assert any("Underhanded Teamwork" in o.tell for o in res.outcomes)


# --- Step Up -------------------------------------------------------------------------------

def test_step_up_follows_a_five_foot_step_away():
    """Step Up: "Whenever an adjacent foe attempts to take a 5-foot step away from you, you
    may also make a 5-foot step as an immediate action so long as you end up adjacent".
    The thug steps from (8,10) to (9,10); Kesst follows to (8,10) and pays 5 ft next turn."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=["Step Up"])
    scene.acted.add("pc")
    scene.turn = 1
    speed = pc.speed_feet
    _run(engine, {"op": "move", "actor": "c1", "params": {"square": [9, 10]}})
    assert scene.positions["pc"][:2] == (8, 10)
    assert pc.speed_feet == speed - 5 and pc.has_state("movement.stepped")


def test_following_step_goes_ten_feet_and_step_up_and_strike_swings():
    """Following Step: "you may move up to 10 feet" and no price next turn; Step Up and
    Strike: "a single melee attack against that foe at your highest base attack bonus"."""
    scene, engine, pc, thug = _fight(pc_at=(6, 10), foe_at=(7, 10),
                                     feats=["Step Up", "Following Step", "Step Up and Strike"])
    scene.acted.add("pc")
    scene.turn = 1
    speed = pc.speed_feet
    res = _run(engine, {"op": "move", "actor": "c1", "params": {"square": [8, 10]}})
    assert scene.positions["pc"][:2] == (7, 10)
    assert pc.speed_feet == speed
    assert any(o.op == "attack" and "Step Up and Strike" in (o.because or "")
               for o in res.outcomes)


# --- the combat bar -------------------------------------------------------------------------

def test_the_declare_section_offers_charge_and_the_held_action_feats():
    """The bar's options are the engine's list (ATTACK_CHOICES through `can_choose`): a
    charge for anyone, Spring Attack, Lunge and Whirlwind Attack for their holders."""
    from play.views import _attack_options

    scene, engine, pc, thug = _fight(feats=["Spring Attack", "Lunge", "Whirlwind Attack"])
    opts = {o["id"]: o for o in _attack_options(pc)["options"]}
    assert {"charge", "spring_attack", "lunge", "whirlwind_attack"} <= set(opts)
    assert opts["charge"]["shape"] == "strike" and "+2 to hit" in opts["charge"]["says"]
    assert not opts["spring_attack"]["why"] and not opts["whirlwind_attack"]["why"]
    scene, engine, pc, thug = _fight()
    assert "spring_attack" not in {o["id"] for o in _attack_options(pc)["options"]}


# --- aid another, and the feats on it ----------------------------------------------------

def _aid_fight(feats=(), ally_at=(9, 10), **kw):
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=feats, ally_at=ally_at,
                                     dice=_Scripted(15), **kw)
    return scene, engine, pc, thug, scene.get("ally")


def test_aid_another_gives_the_friend_two_on_the_next_blow_against_that_foe():
    """CRB, Aid Another: an attack roll against AC 10, a standard action; "+2 bonus on his
    next attack roll against that opponent". Before this only a skill check could be aided.
    Borin's next swing at the thug carries the +2, and the one after it does not."""
    scene, engine, pc, thug, borin = _aid_fight()
    res = _run(engine, _attack(aid="attack", aid_ally="ally"))
    assert res.outcomes[0].verdict == "success" and scene.standard_spent["pc"] == scene.round
    first = next(o for o in _run(engine, _attack(by="ally")).outcomes if o.op == "attack")
    assert _terms(first, "Attack with").get("Kesst Vayr's aid") == 2
    again = next(o for o in _run(engine, _attack(by="ally")).outcomes if o.op == "attack")
    assert "Kesst Vayr's aid" not in _terms(again, "Attack with")


def test_swift_aid_is_plus_one_for_the_swift_action_and_team_up_a_move():
    """Swift Aid: "As a swift action ... a +1 bonus"; Team Up: "When you and at least two
    of your allies are adjacent to an opponent, ... the aid another action as a move
    action"."""
    scene, engine, pc, thug, borin = _aid_fight(feats=["Swift Aid"])
    _run(engine, _attack(aid="ac", aid_ally="ally", aid_with="swift"))
    aid = next(e for e in borin.effects if e.origin == "rule:aid-another")
    assert aid.modifiers[0]["amount"] == 1 and scene.swift_spent["pc"] == scene.round
    assert "pc" not in scene.standard_spent
    scene, engine, pc, thug, borin = _aid_fight(feats=["Team Up"])
    friend = load_pc("fixtures/pc-thessaly.json")
    friend.ref, friend.kind = "friend", "npc"
    scene.add(friend)
    third = "friend"
    scene.positions[third] = (8, 9)
    scene.sides["pc"].append(third)
    scene.standard_spent["pc"] = scene.round
    res = _run(engine, _attack(aid="attack", aid_ally="ally"))
    assert res.outcomes[0].verdict == "success" and scene.move_spent["pc"] == scene.round


def test_bodyguard_spends_an_attack_of_opportunity_on_the_ally_s_guard():
    """Bodyguard: "When an adjacent ally is attacked, you may use an attack of opportunity
    to attempt the aid another action to improve your ally's AC." The thug swings at Borin
    beside Kesst; her aid lands first and his roll is against AC +2."""
    scene, engine, pc, thug, borin = _aid_fight(feats=["Bodyguard"], ally_at=(8, 9))
    scene.acted.update({"pc", "ally"})
    scene.turn = 2
    res = _run(engine, _attack(by="c1", target="ally"))
    assert any(e.get("kind") == "aid" and e.get("made") for o in res.outcomes
               for e in o.effects)
    assert not any(e.origin == "rule:aid-another" for e in borin.effects)   # spent
    assert scene.reacted


def test_uncanny_defense_adds_half_the_defensive_dodge_to_reflex_and_cmd():
    """Uncanny Defense: "While fighting defensively or taking the total defense action, you
    gain a bonus on your Reflex saving throws and to your CMD equal to 1/2 of the dodge
    bonus" — with Cautious Fighter's +4 when fighting defensively, +2."""
    scene, engine, pc, thug = _fight(feats=["Cautious Fighter", "Uncanny Defense"])
    ref, cmd = (sum(m.value for m in pc.save_modifiers("ref")), pc.cmd())
    engine._lay_attack_stances(pc, ("fighting_defensively",))
    assert sum(m.value for m in pc.save_modifiers("ref")) - ref == 2
    assert pc.cmd() - cmd >= 2


def test_surprise_follow_through_denies_dexterity_to_the_second_foe_cleaved():
    """Surprise Follow-Through: "When using Cleave ... the second foe you attack on your
    turn is denied its Dexterity bonus against you." The cleave's carried blow is rolled
    against the second thug's flat-footed AC."""
    scene, engine, pc, thug = _fight(pc_at=(7, 10), feats=["Surprise Follow-Through"])
    from rules.intents import Intent

    # The carried blow is engine-written (`_cleave_on`), never parsed: built so here.
    intent = Intent(op="attack", actor="pc", target="c1", visibility="hidden",
                    params={"cleaving": ["c9"], "cleave": True})
    scene.acted.add("c1")
    plain = engine._flat_footed(thug)
    assert not plain
    o = next(o for o in engine.run([intent]).outcomes if o.op == "attack")
    assert "flat-footed" in (o.dc or {}).get("explain", "") or "flat-footed" in o.tell
