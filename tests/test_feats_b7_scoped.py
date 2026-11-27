"""Feat loop batch 7, lane b7-scoped (2026-11-27): the PARTIAL feats of the ledger's
groups 5, 9, 10, 11, 12, 17, 19, 21, 28, 30, 31, 34, 36 and 38 (docs/feats-partial-ledger.md)
that this lane finished. Each test names what the engine did before.
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect
from rules.sheet import from_dict, load_pc, to_dict
from tests.test_feats_b4_moves import _attack, _board, _named, _pc, _rolls, _tells, _use


def _held_by(actor, key, tags, rounds=5):
    actor.apply_effect(ActiveEffect(name=key, kind="buff", key=key, source="test",
                                    origin="author:test", duration="rounds",
                                    rounds_left=rounds, tags=tuple(tags)))


def _ally(ref="ally", feats=(), cls="fighter", level=8):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "name": "Lia"})
    d.pop("paths", None)
    d["feats"] = list(feats)
    return from_dict(d, ref=ref)


# --- group 5: an effect on a creature scoped to its attacks on one named creature ----------

ARCHON = ["Combat Expertise", "Improved Unarmed Strike", "Archon Style"]


def _archon_board(feats=ARCHON):
    pc = _pc("monk", feats=list(feats))
    ally = _ally()
    s, e = _board(pc, ("thug", (6, 5)), allies=[(ally, (5, 6))])
    _held_by(pc, "archon style", ["style.archon-style"])
    return pc, ally, s, e


def test_archon_style_guards_the_adjacent_ally_against_one_foe_s_next_melee_blow():
    """Archon Style (Blood of Angels): "+2 dodge bonus to AC against that opponent's next
    melee attack ... but causes you to take a -2 penalty to AC against that opponent until
    your next turn." Measured before: no door laid a guard on an ally against one attacker
    (the feat's not_yet). Now Lia's AC against the thug is +2 and against anyone else is
    not; the monk's is -2 against the thug; the thug's next melee attack on Lia spends it."""
    pc, ally, s, e = _archon_board()
    thug = s.actors["c1"]
    ac_ally, ac_pc = ally.ac("melee", False, attacker=thug), pc.ac("melee", False,
                                                                   attacker=thug)
    out = _use(e, "Archon Guard", to="c1")
    assert out.status == "resolved", out.tell
    assert ally.ac("melee", False, attacker=thug) == ac_ally + 2
    assert ally.ac("melee", False) == ally.ac("melee", False)       # no foe, no term
    assert pc.ac("melee", False, attacker=thug) == ac_pc - 2
    assert "against the thug 1" in out.tell
    s.turn = 2
    _attack(e, by="c1", target="ally")
    assert ally.ac("melee", False, attacker=thug) == ac_ally


def test_archon_diversion_and_justice_quicken_the_guard_and_lift_the_penalty():
    """Archon Diversion: "The penalty to AC ... decreases to -1, and you can spend a move
    action"; Archon Justice: "You no longer take a penalty ... a swift action". Measured
    before: neither feat changed anything (both not_yet lines)."""
    from rules import class_abilities as ca

    pc, ally, s, e = _archon_board(ARCHON + ["Archon Diversion"])
    thug = s.actors["c1"]
    doc = ca.find(pc, "Archon Guard")[0]
    assert ca.action_of(doc, pc) == "move"
    ac_pc = pc.ac("melee", False, attacker=thug)
    _use(e, "Archon Guard", to="c1")
    assert pc.ac("melee", False, attacker=thug) == ac_pc - 1
    pc2, _a, s2, e2 = _archon_board(ARCHON + ["Archon Diversion", "Archon Justice"])
    assert ca.action_of(ca.find(pc2, "Archon Guard")[0], pc2) == "swift"
    ac2 = pc2.ac("melee", False, attacker=s2.actors["c1"])
    _use(e2, "Archon Guard", to="c1")
    assert pc2.ac("melee", False, attacker=s2.actors["c1"]) == ac2


def test_archon_guard_is_refused_at_a_foe_not_adjacent_or_outside_the_style():
    pc, ally, s, e = _archon_board()
    s.positions["c1"] = (9, 9)
    assert _use(e, "Archon Guard", to="c1").status == "refused"
    pc.remove_effects(name="archon style")
    s.positions["c1"] = (6, 5)
    assert _use(e, "Archon Guard", to="c1").status == "refused"


def test_broken_wing_gambit_opens_the_foe_after_a_hit_and_its_swing_provokes_the_partner():
    """Broken Wing Gambit (UC): "Whenever you make a melee attack and hit your opponent,
    you can use a free action to grant that opponent a +2 bonus on attack and damage rolls
    against you ... until your opponent attacks you ... it provokes attacks of
    opportunity from your allies who have this feat." Measured before: nothing (the
    feat's not_yet). Refused before a hit; after one the thug carries +2/+2 against the
    PC alone; its attack on the PC draws Lia's swing and spends the bonus."""
    pc = _pc("fighter", feats=["Broken Wing Gambit"])
    ally = _ally(feats=["Broken Wing Gambit"])
    s, e = _board(pc, ("thug", (6, 5)), allies=[(ally, (7, 5))],
                  faces={"Attack": 18, "Damage": 1})
    thug = s.actors["c1"]
    assert _use(e, "Broken Wing Gambit", to="c1").status == "refused"
    _attack(e, target="c1")
    out = _use(e, "Broken Wing Gambit", to="c1")
    assert out.status == "resolved", out.tell
    terms = [m for x in thug.effects for m in x.modifiers if m.get("vs") == "pc"]
    assert sorted((m["target"], m["amount"]) for m in terms) == [("attack", 2), ("damage", 2)]
    s.turn = 2
    res = _attack(e, by="c1", target="pc")
    assert any(o.op == "attack" and getattr(o, "intent_id", "") and "Lia" in (o.tell or "")
               for o in res.outcomes), _tells(res)
    assert not [m for x in thug.effects for m in x.modifiers if m.get("vs") == "pc"]


def test_caustic_slur_makes_a_favoured_enemy_power_attack_the_gnome_until_the_fight_ends():
    """Caustic Slur (Gnomes of Golarion): "Any creature of that type within 60 feet ... must
    make a Will saving throw or become angered. If an affected creature attacks you, it's
    treated as if it were using Power Attack ... These modifiers end when combat ends."
    Measured before: no effect on another creature was scoped to attacks against the user
    (the feat's not_yet). The near orc (a favoured enemy) is angered at its own BAB's
    Power Attack; the goblin (no favoured enemy) and the orc past 60 feet are not."""
    pc = _pc("ranger", level=5, feats=["Caustic Slur"])
    pc.class_choices = {"favored enemy": [{"pick": "humanoid-orc", "bonus": 2}]}
    pc.ranks["bluff"] = 5
    s, e = _board(pc, ("orc", (8, 5)), ("goblin", (5, 8)), ("orc", (19, 19)),
                  faces={"Will": 1, "Caustic Slur": 20})
    near, goblin, far = s.actors["c1"], s.actors["c2"], s.actors["c3"]
    out = _use(e, "Caustic Slur", to="c1")
    assert out.status == "resolved", out.tell
    terms = {m["target"]: m["amount"] for x in near.effects for m in x.modifiers
             if m.get("vs") == "pc" and not (m.get("when") or {}).get("weapon", {}).get(
                 "strength_share")}
    step = 1 + near.bab // 4
    assert terms == {"attack": -step, "damage": 2 * step}
    assert not any(m.get("vs") == "pc" for a in (goblin, far) for x in a.effects
                   for m in x.modifiers)
    s.turn = 1
    res = _attack(e, by="c1", target="pc")
    rolled = [r for r in _rolls(res, "") if "Caustic Slur" in str(r)]
    assert rolled and _named(rolled[0], "Caustic Slur") == -step, _tells(res)
    s.end_encounter()
    assert not any(m.get("vs") == "pc" for x in near.effects for m in x.modifiers)


# --- group 9: teamwork feats that read an ally's position and feats -------------------------

def _reaction_by(res, ref):
    return [o for o in res.outcomes if o.op == "attack" and any(
        b.get("ref") for b in (o.blows or ())) and (o.tell or "").startswith(
        {"pc": "Kesst", "ally": "Lia"}[ref])]


def test_paired_opportunists_shares_the_swing_a_trip_owes_the_partner():
    """Paired Opportunists (APG): "Enemies that provoke attacks of opportunity from your
    ally also provoke attacks of opportunity from you so long as you threaten them."
    Measured before: who was owed a swing was asked of each watcher alone, so the thug's
    untrained trip at Kesst drew Kesst's swing and nobody else's. Now Lia, who threatens the
    thug and holds the feat, swings too; without the feat she does not."""
    for feats, expect in ((["Paired Opportunists"], True), ([], False)):
        pc = _pc("fighter", feats=["Paired Opportunists"])
        ally = _ally(feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), allies=[(ally, (6, 6))],
                      faces={"Attack": 2, "Damage": 1})
        s.turn = 2
        res = _attack(e, by="c1", target="pc", manoeuvre="trip")
        assert bool(_reaction_by(res, "pc")), _tells(res)
        assert bool(_reaction_by(res, "ally")) is expect, _tells(res)


def test_extend_the_bulwark_lends_half_the_armour_bonus_and_takes_the_user_s():
    """Extend the Bulwark (UC): "you may give your ally a circumstance bonus to her AC
    equal to half the armor bonus provided by your armor ... During this round, you gain
    no bonus to your AC from your armor." Measured before: nothing (the feat's not_yet).
    In a breastplate (+6): Lia +3, Kesst -6; refused in light armour or for an ally
    without the feat."""
    pc = _pc("fighter", feats=["Extend the Bulwark"], armour="breastplate")
    ally = _ally(feats=["Extend the Bulwark"])
    s, e = _board(pc, ("thug", (8, 8)), allies=[(ally, (5, 6))])
    bonus = int(pc.armour_stats()["ac"])
    assert bonus == 6
    mine, hers = pc.ac(), ally.ac()
    out = _use(e, "Extend the Bulwark", to="ally")
    assert out.status == "resolved", out.tell
    assert (pc.ac(), ally.ac()) == (mine - bonus, hers + bonus // 2)
    lone = _ally(ref="lone")
    s.add(lone, at=(4, 5))
    assert _use(e, "Extend the Bulwark", to="lone").status == "refused"
    pc2 = _pc("fighter", feats=["Extend the Bulwark"], armour="leather")
    s2, e2 = _board(pc2, ("thug", (8, 8)), allies=[(_ally(feats=["Extend the Bulwark"]),
                                                    (5, 6))])
    assert "medium or heavy" in _use(e2, "Extend the Bulwark", to="ally").tell


# --- group 10: a save that says what forced it -----------------------------------------------

def test_dragon_style_adds_two_against_a_ghoul_s_paralysing_bite():
    """Dragon Style (UC): "a +2 bonus on saving throws against sleep effects, paralysis
    effects, and stunning effects." Measured before: no save said it was against paralysis
    or a stun, so the ghoul's paralysis save carried nothing from the style. Now the rider's
    save is against "paralysis" (`effectspec.harm_words`) and the +2 rides it."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Dragon Style"])
    _held_by(pc, "dragon style", ["style.dragon-style"])
    s, e = _board(pc, ("ghoul", (6, 5)), faces={"Attack": 18, "Fortitude": 10})
    s.turn = 1
    res = _attack(e, by="c1", target="pc")
    saves = [r for r in _rolls(res, "Fortitude save against") if "paralysis" in r["label"]]
    assert saves, _tells(res)
    assert _named(saves[0], "Dragon Style") == 2


def test_a_class_ability_s_save_says_who_forced_it_and_what_it_leaves():
    """Before: a class ability's save said "area" or nothing (Engine._class_ability saves),
    so Shieldwall Phalanx's "abilities of evil creatures", Storm-Lashed's "electrical
    effects", Necromantic Affinity's negative energy and Divine Defiance's "spell-like
    abilities granted by levels in a divine casting class" answered none of them."""
    from rules.engine import Engine

    cleric = _pc("cleric")
    ctx = Engine._ability_save_ctx(cleric, {"ability_type": "sp", "damage_type": "negative",
                                            "effect": {"condition": "stunned"}}, None)
    assert ctx["attacker_actor"] is cleric
    assert {"divine_sla", "negative_energy", "ability_harm", "stun",
            "stun_or_stagger"} <= set(ctx["against"])
    wizard = _pc("wizard")
    ctx = Engine._ability_save_ctx(wizard, {"ability_type": "sp", "damage_type": "electricity"},
                                   None)
    assert "divine_sla" not in ctx["against"] and "electricity" in ctx["against"]
    target = _pc("fighter", feats=["Divine Defiance", "Necromantic Affinity", "Storm-Lashed"])
    base = sum(m.value for m in target.save_modifiers("will"))
    both = Engine._ability_save_ctx(cleric, {"ability_type": "sp", "damage_type": "negative"},
                                    None)
    assert sum(m.value for m in target.save_modifiers("will", both)) == base + 4
    shock = Engine._ability_save_ctx(wizard, {"damage_type": "electricity"}, None)
    assert sum(m.value for m in target.save_modifiers("ref", shock)) == \
        sum(m.value for m in target.save_modifiers("ref")) + 2


def test_a_save_op_stamped_by_a_creature_names_it_for_shieldwall_phalanx():
    """Shieldwall Phalanx (Champions of Purity): "a sacred bonus to saves against the
    spells and abilities of evil creatures equal to the number of adjacent allies who also
    have this feat." Measured before: only a spell's save said who made it; a save the
    ogre's own ability called for (`creature:ogre`) carried no attacker, so no bonus."""
    from rules.engine import Engine

    pc = _pc("fighter", feats=["Shieldwall Phalanx"])
    ally = _ally(feats=["Shieldwall Phalanx"])
    s, e = _board(pc, ("ogre", (8, 5)), allies=[(ally, (5, 6))])
    assert e._stamped_creature(pc, "creature:ogre") is s.actors["c1"]
    assert e._stamped_creature(pc, "creature:wolf") is None
    res = e.run(e.validate([{"op": "save", "actor": "pc", "because": "test",
                             "params": {"save": "will", "dc": 15}}],
                           origin="creature:ogre"))
    from tests.test_feats_b4_moves import _settle

    res = _settle(e, res)
    roll = res.outcomes[-1].rolls[0].as_dict()
    assert _named(roll, "Shieldwall Phalanx") >= 1, roll


def test_luck_not_against_keeps_dauntless_destiny_off_a_trap_save():
    """Dauntless Destiny: "This effect does not apply on saving throws against traps or
    other objects." Its reroll entry now names `not_against: trap` (rules/luck.py covers)."""
    from rules import luck

    entry = {"reroll": "natural_1", "rolls": ["save", "attack"], "not_against": ["trap"]}
    assert luck.covers(entry, "save.ref", ("spell",))
    assert not luck.covers(entry, "save.ref", ("trap",))


# --- group 21: an action that removes a dirty trick's condition --------------------------------

def test_a_worsened_dirty_trick_costs_the_foe_a_standard_action_to_shake_off():
    """Dirty Trick Master: the worsened condition "lasts for the duration of the dirty trick
    ... or until the opponent uses a standard action to remove the condition". Measured
    before: no action removed a dirty trick's condition at all. The thug, shaken by an
    earlier trick, is made frightened; on its turn it spends its standard action (not its
    move) to shake it off (`Engine.trick_turn`)."""
    pc = _pc("fighter", feats=["Improved Dirty Trick", "Dirty Trick Master"])
    s, e = _board(pc, ("thug", (6, 5)), faces={"": 19})
    thug = s.actors["c1"]
    thug.add_condition("shaken", rounds=2, source="dirty trick by the test",
                       origin="rule:dirty-trick")
    res = _attack(e, target="c1", manoeuvre="dirty trick", trick="shaken")
    assert thug.has_condition("frightened"), _tells(res)
    assert e.trick_action(thug) == "standard"
    s.turn = 1
    res = e.trick_turn("c1")
    assert res is not None and not thug.has_condition("frightened"), _tells(res)
    assert s.standard_spent.get("c1") == s.round and s.move_spent.get("c1") != s.round


def test_the_player_shakes_off_a_trick_as_a_move_action_and_its_rider_goes_with_it():
    """APG, Dirty Trick: "Removing the condition requires the target to spend a move
    action"; Improved Underhanded Teamwork: "If the foe uses an action to remove the first
    condition, it also removes the condition imposed by your immediate action". The bar's
    Shake off sends `escape` how=trick; both conditions go, the move action is spent."""
    pc = _pc("fighter")
    s, e = _board(pc, ("thug", (6, 5)))
    first = pc.add_condition("dazzled", rounds=3, source="dirty trick by the thug 1",
                             origin="rule:dirty-trick")
    pc.add_condition("sickened", rounds=2, source="dirty trick by the thug 2",
                     origin="rule:dirty-trick", payload={"rides_with": first.key})
    from tests.test_feats_b4_moves import _run

    res = _run(e, {"op": "escape", "actor": "pc", "params": {"how": "trick"}})
    assert res.outcomes[-1].status == "resolved", _tells(res)
    assert not pc.has_condition("dazzled") and not pc.has_condition("sickened")
    assert s.move_spent.get("pc") == s.round


def test_mantis_wisdom_lifts_only_the_stunning_fist_its_holder_laid():
    """Mantis Wisdom (UC): "use a standard action and a successful melee touch attack to
    remove any Stunning Fist effect you have applied to a target." Measured before: no door
    removed a condition by its giver's touch. The thug's stun laid by Kesst goes; the
    fatigue another monk's Stunning Fist laid stays."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Stunning Fist", "Mantis Style",
                            "Mantis Wisdom"])
    s, e = _board(pc, ("thug", (6, 5)), faces={"Mantis Wisdom Touch": 19})
    thug = s.actors["c1"]
    thug.add_condition("stunned", rounds=1, source="Stunning Fist",
                       origin="ability:feat/stunning fist", payload={"by": "pc"})
    thug.add_condition("fatigued", rounds=3, source="Stunning Fist",
                       origin="ability:monk/stunning fist", payload={"by": "c9"})
    out = _use(e, "Mantis Wisdom Touch", to="c1")
    assert out.status == "resolved", out.tell
    assert not thug.has_condition("stunned") and thug.has_condition("fatigued")
