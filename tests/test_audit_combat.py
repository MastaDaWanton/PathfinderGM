"""The combat lane of the ponytail audit (2026-11-07, read against 0.2.26).

Each section names the finding, the measurement the audit (or this lane's probe on
0.2.27) took, and the Core Rulebook line on aonprd.com the fix rests on. The audit's
report is C:\\Users\\natha\\pgm-work\\ponytail-audit-2026-11-07.md.
"""
from __future__ import annotations

from rules import bestiary
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _fight(template: str, seed: int = 7):
    """Kesst and one stat-block creature with the fight running, the creature's turn."""
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    foe = scene.add(bestiary.instantiate(template, scene=scene))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter(foe.ref)
    pc.hp = pc.hp_max = 500
    return engine, pc, foe


def _swings(outcome) -> list[str]:
    return [str(r.label) for r in outcome.rolls if str(r.label).startswith("Attack with")]


def _finish(engine, res):
    for _ in range(12):
        if not res.awaiting:
            break
        res = engine.resume(min(15, int(res.awaiting.get("max", 20))))
    return res


# --- #25: a full attack after a normal move -----------------------------------------------

def test_an_owlbear_that_walks_25_ft_makes_one_attack_not_its_routine():
    """Audit #25, reproduced on 0.2.27: an owlbear 30 ft off, `move` to Kesst's side
    (25 ft) then `attack full_attack`, rolled claws, claws, bite. "You must use a
    full-round action to get your additional attacks. The only movement you can take
    during a full attack is a 5-foot step" (CRB, Full Attack; aonprd.com/Rules.aspx?
    ID=145). Only the closing step the engine inserts had marked the blow behind it."""
    engine, pc, ob = _fight("owlbear")
    scene = engine.scene
    scene.positions["pc"] = (4, 5)
    scene.positions[ob.ref] = (10, 5)
    scene.resync_zones()
    res = engine.run(engine.validate([
        {"op": "move", "actor": ob.ref, "params": {"square": [5, 5]}, "because": "t"},
        {"op": "attack", "actor": ob.ref, "target": "pc",
         "params": {"full_attack": True}, "because": "t"}]))
    move, blow = res.outcomes[0], res.outcomes[-1]
    assert move.op == "move" and move.effects[0]["feet"] > 5
    assert _swings(blow) == ["Attack with claws"], blow.tell


def test_a_second_declared_blow_after_a_move_is_refused_in_words():
    """The panel's split full attack (one op per swing) behind a declared move: the
    first swings once, the second is refused as `after_close` refuses it."""
    engine, pc, ob = _fight("owlbear")
    scene = engine.scene
    scene.positions["pc"] = (4, 5)
    scene.positions[ob.ref] = (10, 5)
    scene.resync_zones()
    res = engine.run(engine.validate([
        {"op": "move", "actor": ob.ref, "params": {"square": [5, 5]}, "because": "t"},
        {"op": "attack", "actor": ob.ref, "target": "pc", "params": {}, "because": "t"},
        {"op": "attack", "actor": ob.ref, "target": "pc", "params": {}, "because": "t"}]))
    blows = [o for o in res.outcomes if o.op == "attack" and o.intent_id]
    assert len(_swings(blows[-2])) == 1
    assert blows[-1].status == "refused" and not blows[-1].rolls
    assert "one blow" in blows[-1].tell


def test_a_five_foot_step_still_leaves_the_full_attack():
    """The rule's own exception: a 5-foot step and then the whole routine."""
    engine, pc, ob = _fight("owlbear")
    scene = engine.scene
    scene.positions["pc"] = (4, 5)
    scene.positions[ob.ref] = (6, 5)
    scene.resync_zones()
    res = engine.run(engine.validate([
        {"op": "move", "actor": ob.ref, "params": {"square": [5, 5]}, "because": "t"},
        {"op": "attack", "actor": ob.ref, "target": "pc",
         "params": {"full_attack": True}, "because": "t"}]))
    assert res.outcomes[0].effects[0]["feet"] == 5
    assert _swings(res.outcomes[-1]) == ["Attack with claws", "Attack with claws",
                                         "Attack with bite"]


# --- #26: debuffs reach a stat block's printed totals ---------------------------------------

def _total(mods) -> int:
    return sum(m.value for m in mods)


def test_an_entangled_goblin_loses_ac_reflex_and_cmd_to_its_minus_four_dex():
    """Audit #26: "an entangled goblin keeps AC 16 and Ref +2". Entangled is "-4 penalty
    to Dexterity" (CRB, Conditions; aonprd.com/Rules.aspx?ID=413): the goblin's Dex 15
    (+2) becomes 11 (+0), so AC 16 -> 14, Reflex +2 -> +0, CMD 12 -> 10 and Stealth
    10 -> 8. A printed total holds the block's own scores; what moves them since is the
    change in the modifier (`Actor.printed_shift`)."""
    g = bestiary.instantiate("goblin", scene=Scene())
    before = (g.ac(), _total(g.save_modifiers("ref")), g.cmd(),
              _total(g.skill_modifiers("stealth")))
    assert before == (16, 2, 12, 10)
    g.add_condition("entangled", source="test")
    assert (g.ac(), _total(g.save_modifiers("ref")), g.cmd(),
            _total(g.skill_modifiers("stealth"))) == (14, 0, 10, 8)


def test_an_ogre_with_eight_strength_damage_hits_softer_and_weaker():
    """Audit #26: "an ogre with 8 Str damage still hits +7 for +7". Str 21 (+5) to 13
    (+1) is -4 on the greatclub's attack, its damage and its CMB; the printed totals are
    the base, the change rides beside them."""
    o = bestiary.instantiate("ogre", scene=Scene())
    assert (_total(o.attack_modifiers()), _total(o.damage_modifiers())) == (7, 7)
    o.damage_ability("str", 8)
    assert (_total(o.attack_modifiers()), _total(o.damage_modifiers())) == (3, 3)
    assert _total(o.cmb_modifiers()) == 9 - 4


def test_a_flat_footed_creature_with_lowered_dex_keeps_the_penalty_not_the_bonus():
    """Losing Dex to AC takes the bonus that is left and keeps a penalty — the rule
    `ac_modifiers` applies to a derived AC. A goblin at Dex 7 (-2) is AC 12, flat-footed
    or not; the print's +2 is not taken away twice."""
    g = bestiary.instantiate("goblin", scene=Scene())
    g.damage_ability("dex", 8)
    assert g.ac() == 12 and g.ac(flat_footed=True) == 12


# --- #27: monster BAB and CMB from the block ------------------------------------------------

def test_an_ogre_has_its_printed_bab_and_cmb_not_its_club():
    """Audit #27: ogre CMB 7 against the printed +9 (every Large creature 2 short), BAB 7
    where the block says 3, and a touch attack +11 for +7 — all read off the
    greatclub's +7. The block's `base_attack` and `cmb` were stripped on import."""
    from rules.engine import Engine

    scene = Scene()
    o = bestiary.instantiate("ogre", scene=scene)
    goblin = bestiary.instantiate("goblin", scene=scene)
    assert o.bab == 3 and _total(o.cmb_modifiers()) == 9
    touch = Engine(scene, Dice(seed=1))._touch_mods(o, goblin, ranged=False)
    assert _total(touch) == 3 + 5 - 1             # BAB, Str, Large
    assert goblin.bab == 1 and _total(goblin.cmb_modifiers()) == 0


def test_bab_and_cmb_survive_a_save_and_an_old_save_keeps_the_stand_in():
    """Round-trip, and written only when set: a save from before carries no key and
    reads back with the attack bonus standing in, as it did."""
    from rules.sheet import from_dict, to_dict

    o = bestiary.instantiate("ogre", scene=Scene())
    d = to_dict(o)
    assert d["flat_bab"] == 3 and d["flat_cmb"] == 9
    back = from_dict(d)
    assert back.bab == 3 and _total(back.cmb_modifiers()) == 9
    old = {k: v for k, v in d.items() if k not in ("flat_bab", "flat_cmb")}
    stand_in = from_dict(old)
    assert stand_in.bab == 7 and _total(stand_in.cmb_modifiers()) == 7
    assert "flat_bab" not in to_dict(stand_in)


# --- #31: Strength on damage by the weapon's grip and kind ----------------------------------

def _strong(*weapons):
    from rules.sheet import from_dict

    return from_dict({"name": "Brakka", "kind": "pc", "class": "fighter", "level": 1,
                      "abilities": {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10,
                                    "cha": 10},
                      "hp": 12, "weapons": list(weapons), "equipped": weapons[0]})


def _str_term(actor, key, **kw) -> int:
    return sum(m.value for m in actor.damage_modifiers(key, **kw) if m.source == "Str")


def test_a_greatsword_adds_one_and_a_half_strength_and_a_sling_adds_it_at_all():
    """Audit #31: with Str 16 (+3) a greatsword added +3 and a sling +0. CRB, Combat,
    Strength Bonus (legacy.aonprd.com/coreRulebook/combat.html): "When you deal damage
    with a weapon that you are wielding two-handed, you add 1-1/2 times your Strength
    bonus" (+4); a sling and a thrown weapon add the Strength modifier; a crossbow adds
    none; a bow that is not composite takes a penalty and never a bonus."""
    pc = _strong("greatsword", "longsword", "sling", "javelin", "light crossbow",
                 "longbow")
    assert _str_term(pc, "greatsword") == 4
    assert _str_term(pc, "longsword") == 3
    assert _str_term(pc, "sling") == 3
    assert _str_term(pc, "javelin") == 3
    assert _str_term(pc, "light crossbow") == 0
    assert _str_term(pc, "longbow") == 0
    weak = _strong("greatsword", "longbow")
    weak.abilities["str"] = 8                      # -1: whole, never 1.5 times, on a bow too
    assert _str_term(weak, "greatsword") == -1 and _str_term(weak, "longbow") == -1


# --- #37 and Fly: a printed skill holds its size --------------------------------------------

def test_small_monsters_stealth_is_the_print_not_the_print_plus_size():
    """Audit #37: the size term sat outside the printed-or-derived branch, so goblin
    Stealth 10 rolled at 14, dire rat 11 at 15, sprite 19 at 31."""
    scene = Scene()
    for key, printed in (("goblin", 10), ("dire-rat", 11), ("sprite", 19)):
        c = bestiary.instantiate(key, scene=scene)
        assert _total(c.skill_modifiers("stealth")) == printed, key


def test_a_derived_fly_check_takes_the_fly_size_modifier():
    """CRB, Fly: "Fine +8, Diminutive +6, Tiny +4, Small +2, Medium +0, Large -2, Huge
    -4, Gargantuan -6, Colossal -8". Nothing read a size on Fly; a printed Fly (the
    sprite's 21) already holds it and is left alone."""
    pc = _strong("longsword")
    base = _total(pc.skill_modifiers("fly"))
    pc.size = "small"
    assert _total(pc.skill_modifiers("fly")) == base + 2
    pc.size = "large"
    assert _total(pc.skill_modifiers("fly")) == base - 2
    assert _total(bestiary.instantiate("sprite", scene=Scene()).skill_modifiers("fly")) == 21


# --- #38: touch AC against a ranged touch ---------------------------------------------------

def test_a_prone_goblins_ranged_touch_ac_is_seventeen_not_nine():
    """Audit #38: `touch_ac_modifiers` always asked for melee, so a prone goblin's
    ranged touch AC was 9. Prone is "-4 penalty to Armor Class against melee attacks, but
    a +4 bonus to Armor Class against ranged attacks" (CRB, Conditions): touch 13, so 9
    against a hand and 17 against a ray."""
    g = bestiary.instantiate("goblin", scene=Scene())
    g.add_condition("prone", source="test")
    assert g.touch_ac() == 9 and g.touch_ac(against="ranged") == 17


# --- CMD: rage's penalty, and a stunned monster's Dex ---------------------------------------

def test_a_penalty_to_ac_from_an_effect_reaches_cmd():
    """"Any penalties to a creature's AC also apply to its CMD" (CRB p.199). Only the
    condition rows' penalties were read; rage's -2 AC is an effect's `combat_mod`, and
    CMD did not move."""
    from rules.activeeffect import ActiveEffect

    for actor in (_strong("longsword"), bestiary.instantiate("goblin", scene=Scene())):
        before = actor.cmd()
        actor.apply_effect(ActiveEffect(
            name="Rage", kind="ability", source="Rage",
            modifiers=[{"kind": "combat_mod", "target": "ac", "amount": -2}]))
        assert actor.cmd() == before - 2, actor.name


def test_a_stunned_monster_loses_its_dex_from_a_printed_cmd():
    """A stunned creature "loses its Dexterity bonus to AC" (CRB, Stunned), and a printed
    CMD holds Dex. Only the `flat_footed` argument was asked, so a stunned goblin kept
    its +2: CMD 12 should be 12 - 2 (Dex) - 2 (stunned's AC penalty) = 8."""
    g = bestiary.instantiate("goblin", scene=Scene())
    g.add_condition("stunned", source="test")
    assert g.cmd() == 8


# --- deafened and blinded -------------------------------------------------------------------

def test_deafened_takes_four_off_initiative():
    """CRB, Deafened: "takes a -4 penalty on initiative checks". The row carried the -4
    from the day the table was written; `initiative_modifiers` never read it."""
    pc = _strong("longsword")
    before = _total(pc.initiative_modifiers())
    pc.add_condition("deafened", source="test")
    assert _total(pc.initiative_modifiers()) == before - 4
    g = bestiary.instantiate("goblin", scene=Scene())
    before = _total(g.initiative_modifiers())
    g.add_condition("deafened", source="test")
    assert _total(g.initiative_modifiers()) == before - 4


def test_blinded_takes_four_off_strength_dexterity_and_perception_only():
    """CRB, Blinded: "-4 penalty on most Strength- and Dexterity-based skill checks and
    on opposed Perception skill checks". The row said -4 on every skill, Knowledge and
    Spellcraft included."""
    pc = _strong("longsword")
    pc.ranks.update({"climb": 1, "acrobatics": 1, "perception": 1, "spellcraft": 1,
                     "diplomacy": 1})
    names = ("climb", "acrobatics", "perception", "spellcraft", "diplomacy")
    before = {s: _total(pc.skill_modifiers(s)) for s in names}
    pc.add_condition("blinded", source="test")
    after = {s: _total(pc.skill_modifiers(s)) for s in names}
    assert {s: after[s] - before[s] for s in names} == {
        "climb": -4, "acrobatics": -4, "perception": -4, "spellcraft": 0, "diplomacy": 0}


# --- #32: no attack of opportunity while flat-footed ----------------------------------------

def _kesst_and_thug(thug_acted: bool):
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=7))
    engine._ensure_encounter("pc", "c1")
    scene.positions["pc"], scene.positions["c1"] = (6, 10), (7, 10)
    scene.resync_zones()
    if thug_acted:
        scene.acted.add("c1")
    scene.get("pc").hp = scene.get("pc").hp_max = 500
    return scene, engine


def _walk_away(engine):
    res = engine.run(engine.validate([{"op": "move", "actor": "pc",
                                       "params": {"square": [3, 10]}, "because": "t"}]))
    return _finish(engine, res)


def test_a_thug_who_has_not_acted_takes_no_attack_of_opportunity():
    """Audit #32: in round 1 a thug who had not yet acted hit Kesst for 8 as she stepped
    away. "A flat-footed character can't make attacks of opportunity, unless he has the
    Combat Reflexes feat" (CRB, Combat; legacy.aonprd.com/coreRulebook/combat.html). The
    control: once he has acted, the same walk draws the same swing."""
    scene, engine = _kesst_and_thug(thug_acted=False)
    assert [o.op for o in _walk_away(engine).outcomes] == ["move"]
    scene, engine = _kesst_and_thug(thug_acted=True)
    assert [(o.op, o.actor) for o in _walk_away(engine).outcomes][0] == ("attack", "c1")


def test_combat_reflexes_lets_a_flat_footed_creature_swing():
    """The feat's second sentence: "you may also make attacks of opportunity while
    flat-footed". Read off the document's `budget` line, as the allowance is."""
    scene, engine = _kesst_and_thug(thug_acted=False)
    scene.get("c1").feats = list(scene.get("c1").feats or []) + ["combat reflexes"]
    assert [(o.op, o.actor) for o in _walk_away(engine).outcomes][0] == ("attack", "c1")


# --- sneak attack and concealment -----------------------------------------------------------

def test_no_sneak_attack_into_concealment_however_it_arises():
    """"A rogue cannot sneak attack while striking a creature with concealment" (CRB,
    Rogue; legacy.aonprd.com/coreRulebook/classes/rogue.html). The dice asked only
    `state.hidden` while the attack roll asked `_concealment_of` — the rule written two
    ways. A blurred thug (20% miss chance) gave Kesst her 1d6 anyway."""
    scene, engine = _kesst_and_thug(thug_acted=False)
    pc, thug = scene.get("pc"), scene.get("c1")
    dice, _ = engine._sneak_for(pc, thug, pc.weapon(), flat_footed=True)
    assert dice
    thug.add_buff("concealment", "miss_chance", 20, source="blur")
    assert engine._concealment_of(pc, thug)[0] == 20
    dice, why = engine._sneak_for(pc, thug, pc.weapon(), flat_footed=True)
    assert dice == "" and "concealed" in why


# --- natural attacks take no iteratives -----------------------------------------------------

def test_a_bite_at_bab_six_is_one_roll_and_claws_are_one_per_claw():
    """"You do not receive additional natural attacks for a high base attack bonus.
    Instead, you receive additional attack rolls for multiple limb and body parts" (CRB,
    Combat, Natural Attacks). A bite at BAB +6 rolled +6/+1 like a sword."""
    from rules.activeeffect import ActiveEffect

    pc = _strong("longsword")
    pc.level = 6
    assert pc.bab == 6
    pc.apply_effect(ActiveEffect(
        name="wolf shape", kind="buff", source="test", payload={"natural_weapons": [
            {"key": "bite", "name": "bite", "damage": {"medium": "1d6"},
             "type": "piercing"},
            {"key": "claws", "name": "claws", "count": 2, "damage": {"medium": "1d4"},
             "type": "slashing"}]}))
    assert pc.attack_sequence("bite", full_attack=True) == [0]
    assert pc.attack_sequence("claws", full_attack=True) == [0, 0]
    assert pc.attack_sequence("longsword", full_attack=True) == [0, 1]


# --- shooting into melee --------------------------------------------------------------------

def _shooting_board(precise: bool = False):
    from rules import position
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    thug = scene.add(instantiate("thug", scene=scene, name="the thug"))
    friend = scene.add(instantiate("thug", scene=scene, name="Dace"))
    engine = Engine(scene, Dice(seed=7))
    engine._ensure_encounter("pc", thug.ref)
    scene.sides = {"pc": ["pc", friend.ref], "them": [thug.ref]}
    scene.positions["pc"] = (2, 10)
    scene.positions[thug.ref] = (8, 10)
    scene.positions[friend.ref] = (9, 10)
    scene.resync_zones()
    if precise:
        pc.feats = list(pc.feats) + ["precise shot"]
    bow = {"category": "ranged", "name": "shortbow"}
    return scene, pc, thug, friend, position.attack_mods(scene, pc, thug, bow)


def test_a_shot_at_a_foe_engaged_with_a_friend_is_minus_four():
    """CRB, Combat: "If you shoot or throw a ranged weapon at a target engaged in melee
    with a friendly character, you take a -4 penalty on your attack roll". Nothing charged
    it. Precise Shot waives it ("without taking the standard -4 penalty"), and a foe with
    no friend beside him is shot at plain."""
    scene, pc, thug, friend, mods = _shooting_board()
    assert [(m.value, m.source) for m in mods] == [(-4, "shooting into melee with Dace")]
    *_, waived = _shooting_board(precise=True)
    assert waived == []
    scene.positions[friend.ref] = (14, 10)
    scene.resync_zones()
    from rules import position

    assert position.attack_mods(scene, pc, thug, {"category": "ranged"}) == []
