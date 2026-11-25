"""Feat loop batch 2, lane b2-attack-a: each feat's clauses measured through the engine.

Before this batch none of these feats had a document: a name on the sheet that moved no
roll (worklist 2026-11-22, the audit's "attack-shape / other combat" sort, 68 feats).
Many are not attack options at all. Sociable, Shared Insight and Shared Manipulation are
move actions that lift the allies around the user; Punishing Kick, Touch of Serenity,
Gorgon's Fist, Crushing Blow and Jawbreaker are blows declared before the roll — Stunning
Fist's shape. They are documents in content/class-abilities/feats-b2-attack-a.json, held
by whoever holds the feat (`class_abilities._docs_for`), run by the one executor the class
abilities use.
"""
from __future__ import annotations

import pytest

from rules import class_abilities as ca
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _pc(cls: str = "fighter", level: int = 8, feats=(), **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = cls
    d["level"] = level
    d["ranks"] = {}
    d.pop("paths", None)
    d["feats"] = list(d.get("feats") or ()) + list(feats)
    d.update(extra)
    return from_dict(d, ref="pc")


def _fight(pc, *foes, allies=(), seed=11):
    scene = Scene()
    scene.add(pc)
    for a in allies:
        scene.add(a)
    for f in foes or ("thug",):
        scene.add(instantiate(f, scene=scene, name=f"the {f}"))
    them = [r for r in scene.actors if r != "pc" and r not in {a.ref for a in allies}]
    e = Engine(scene, dice=Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter", "params": {
        "sides": {"pc": ["pc"] + [a.ref for a in allies], "them": them}}}]))
    return scene, e


def _use(e, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return e.run(e.validate([raw])).outcomes[-1]


def _swing(e, target="c1", face=15, **params):
    raw = {"op": "attack", "actor": "pc", "target": target, "because": "test",
           "params": dict(params)}
    res = e.run(e.validate([raw]))
    while res.awaiting:
        label = res.awaiting["label"]
        res = e.resume(face if label.startswith(("Attack", "Confirm"))
                       else int(res.awaiting["max"]))
    return res


def _adjacent(scene, a="pc", b="c1"):
    from tests._board import face_to_face

    face_to_face(scene, a, b)


def _ally(ref="ally"):
    a = load_pc("fixtures/pc-borin.json")
    a.ref, a.kind = ref, "npc"
    return a


def _tells(res) -> str:
    return " ".join(o.tell for o in res.outcomes)


# --- the door: a feat's activated use, for any class --------------------------------------

def test_a_feat_ability_is_had_by_the_feat_and_by_nobody_without_it():
    """Sociable was a name on the sheet; `use_ability` refused it on every class. The
    feat document is had by its holder whatever the class, and by nobody else."""
    holder, other = _pc("fighter", feats=["Sociable"]), _pc("fighter")
    assert ca.find(holder, "sociable")[0] is not None
    assert ca.find(other, "sociable")[0] is None
    assert not ca.validate_documents()


def test_sociable_lifts_diplomacy_for_the_user_and_allies_for_cha_rounds():
    """Sociable (APG): "+2 bonus on Diplomacy checks ... (including yourself)" for Cha
    rounds, a move action. Measured before: no Diplomacy moved for anybody."""
    pc = _pc("bard", feats=["Sociable"])
    pc.abilities["cha"] = 16                          # +3: three rounds
    ally = _ally()
    _scene, e = _fight(pc, allies=[ally])
    before_me = sum(m.value for m in pc.skill_modifiers("diplomacy"))
    before_ally = sum(m.value for m in ally.skill_modifiers("diplomacy"))
    out = _use(e, "Sociable")
    assert out.status != "refused", out.tell
    assert sum(m.value for m in pc.skill_modifiers("diplomacy")) == before_me + 2
    assert sum(m.value for m in ally.skill_modifiers("diplomacy")) == before_ally + 2
    assert "for 3 rounds" in out.tell
    for who in (pc, ally):
        who.tick_effects(3)
    assert sum(m.value for m in pc.skill_modifiers("diplomacy")) == before_me


def test_shared_insight_lifts_the_others_and_not_the_user():
    """Shared Insight (APG): "all friendly creatures within 30 feet ... +2 on Perception"
    — no "(including yourself)", which Sociable says and this does not."""
    pc = _pc("ranger", feats=["Shared Insight"])
    ally = _ally()
    _scene, e = _fight(pc, allies=[ally])
    mine = sum(m.value for m in pc.skill_modifiers("perception"))
    theirs = sum(m.value for m in ally.skill_modifiers("perception"))
    _use(e, "Shared Insight")
    assert sum(m.value for m in pc.skill_modifiers("perception")) == mine
    assert sum(m.value for m in ally.skill_modifiers("perception")) == theirs + 2


def test_shared_manipulation_lifts_the_skill_named_and_asks_which():
    pc = _pc("rogue", feats=["Shared Manipulation"])
    ally = _ally()
    _scene, e = _fight(pc, allies=[ally])
    asked = _use(e, "Shared Manipulation")
    assert asked.status == "refused" and "bluff" in asked.tell and "intimidate" in asked.tell
    bluff = sum(m.value for m in ally.skill_modifiers("bluff"))
    scare = sum(m.value for m in ally.skill_modifiers("intimidate"))
    _use(e, "Shared Manipulation (intimidate)")
    assert sum(m.value for m in ally.skill_modifiers("intimidate")) == scare + 2
    assert sum(m.value for m in ally.skill_modifiers("bluff")) == bluff


# --- Blinding Flash --------------------------------------------------------------------------

def test_blinding_flash_dazzles_on_a_failed_save_and_needs_bright_light():
    """Blinding Flash (Dragon Empires Primer): a move action, Fortitude DC 10 + 1/2 level
    + Dex or dazzled 1 round, only in bright light, and not on the blind."""
    pc = _pc("fighter", 8, feats=["Combat Expertise", "Blinding Flash"])
    pc.abilities["dex"] = 40                          # DC 10 + 4 + 15: the thug fails
    scene, e = _fight(pc)
    scene.ambient_light = lambda: "normal"            # a bare scene is lit as a room
    dim = _use(e, "Blinding Flash", to="c1")
    assert dim.status == "refused" and "bright" in dim.tell
    scene.ambient_light = lambda: "bright"
    out = _use(e, "Blinding Flash", to="c1")
    assert "DC 29" in out.tell and scene.actors["c1"].has_condition("dazzled"), out.tell
    blind = instantiate("thug", scene=scene, name="the blind thug")
    scene.add(blind)
    blind.add_condition("blinded", 10, source="test")
    again = _use(e, "Blinding Flash", to=blind.ref)
    assert again.status == "refused" and "cannot" in again.tell


# --- the declared blows -----------------------------------------------------------------------

def test_punishing_kick_knocks_prone_on_a_failed_save_and_counts_uses_by_level():
    """Punishing Kick (APG): once a day per four levels — a monk his monk level — and a
    hit knocks the target prone unless it makes Fortitude DC 10 + 1/2 level + Wis."""
    fighter = _pc("fighter", 8, feats=["Improved Unarmed Strike", "Punishing Kick"])
    _scene, e = _fight(fighter)
    _use(e, "Punishing Kick")
    assert fighter.pool("punishing kick").maximum == 2
    monk = _pc("monk", 8, feats=["Punishing Kick"])
    monk.abilities["wis"] = 30                        # DC 24
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    out = _use(e, "Punishing Kick")
    assert monk.pool("punishing kick").maximum == 8 and "DC 24" in out.tell
    res = _swing(e, face=19)
    assert scene.actors["c1"].has_condition("prone"), _tells(res)
    # "no more than once per round"
    again = _use(e, "Punishing Kick")
    assert again.status == "refused" and "recharges" in again.tell


def test_punishing_kick_can_push_the_target_five_feet_instead():
    monk = _pc("monk", 8, feats=["Punishing Kick"])
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    start = tuple(scene.positions["c1"])
    _use(e, "Punishing Kick (push)")
    res = _swing(e, face=19)
    moved = tuple(scene.positions["c1"])
    assert moved != start and "5 feet back" in _tells(res), _tells(res)
    assert not scene.actors["c1"].has_condition("prone")


def test_touch_of_serenity_wounds_nothing_and_stops_attacks_and_spells():
    """Touch of Serenity (APG): "the attack deals no damage ... the target cannot cast
    spells or attack (including attacks of opportunity ...) for 1 round" on a failed
    Will save — the `serene` state, which `states.BLOCKS` stops attack and cast by."""
    monk = _pc("monk", 8, feats=["Touch of Serenity"])
    monk.abilities["wis"] = 40
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    thug = scene.actors["c1"]
    hp = thug.hp
    _use(e, "Touch of Serenity")
    res = _swing(e, face=19)
    assert thug.hp == hp, _tells(res)
    assert "without harm" in _tells(res)
    assert thug.blocking_key("attack") and thug.blocking_key("cast")
    from rules import reactions

    assert reactions.reactions_for(thug) == []


def test_gorgons_fist_staggers_only_a_slowed_foe_and_never_in_a_full_attack():
    """Gorgon's Fist (CRB): "against a foe whose speed is reduced ... staggered ...
    unless it makes a Fortitude saving throw ... no effect on targets that are
    staggered"; a single unarmed attack as a standard action."""
    monk = _pc("monk", 8, feats=["Scorpion Style", "Gorgon's Fist"])
    monk.abilities["wis"] = 40
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    thug = scene.actors["c1"]
    _use(e, "Gorgon's Fist")
    res = _swing(e, face=19)
    assert not thug.has_condition("staggered") and "no hold" in _tells(res)
    thug.add_condition("entangled", 10, source="test")
    _use(e, "Gorgon's Fist")
    res = _swing(e, face=19)
    assert thug.has_condition("staggered"), _tells(res)


def test_crushing_blow_lowers_ac_by_wisdom_and_does_not_stack():
    """Crushing Blow (UC): a Stunning Fist attempt that, failed, reduces "the target's AC
    by an amount equal to your Wisdom modifier for 1 minute ... does not stack"."""
    monk = _pc("monk", 8, feats=["Crushing Blow"])
    monk.abilities["wis"] = 30                        # +10
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    thug = scene.actors["c1"]
    thug.hp_max = thug.hp = 500                      # standing, so its AC is not helpless
    ac = thug.ac()
    spent = monk.pool("stunning fist").current if monk.pool("stunning fist") else None
    _use(e, "Crushing Blow")
    res = _swing(e, face=19)
    assert thug.ac() == ac - 10, _tells(res)
    assert not thug.has_condition("stunned")
    if spent is not None:
        assert monk.pool("stunning fist").current == spent - 1
    _use(e, "Crushing Blow")
    _swing(e, face=19)
    assert thug.ac() == ac - 10, "a second Crushing Blow is laid again, not added"


def test_jawbreaker_bleeds_only_a_held_helpless_or_stunned_foe():
    monk = _pc("monk", 8, feats=["Jawbreaker"])
    monk.abilities["wis"] = 40
    monk.equipped = "unarmed"
    scene, e = _fight(monk)
    _adjacent(scene)
    thug = scene.actors["c1"]
    _use(e, "Jawbreaker")
    res = _swing(e, face=19)
    assert not thug.has_condition("bleed") and "no hold" in _tells(res)
    thug.add_condition("grappled", 10, source="test")
    _use(e, "Jawbreaker")
    res = _swing(e, face=19)
    assert thug.has_state("state.bleeding") or thug.has_condition("bleed"), _tells(res)


# --- the swing's moment, the AC line's board --------------------------------------------------

from rules.grid import Grid  # noqa: E402
from rules.sheet import situated  # noqa: E402


def _wren(feats=(), level=8, **extra):
    data = {"name": "Wren", "kind": "pc", "class": "fighter", "level": level,
            "abilities": {"str": 16, "dex": 14, "con": 12, "int": 12, "wis": 12, "cha": 12},
            "hp": 60, "weapons": ["greatsword", "longbow", "longsword"],
            "equipped": "greatsword", "feats": list(feats), "ranks": {}}
    data.update(extra)
    return from_dict(data, ref="pc")


def _board(*actors, foes=()):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    for a in actors:
        s.add(a)
    made = [s.add(instantiate(t, scene=s, name=f"{t} {i + 1}")) for i, t in enumerate(foes)]
    return (s, Engine(s, Dice(seed=3)), *made)


def _of(mods, name) -> list[int]:
    return [m.value for m in mods if m.source == name]


def _attack_roll(res) -> dict:
    o = next(o for o in res.outcomes if o.op == "attack")
    rolls = [r if isinstance(r, dict) else r.as_dict() for r in o.rolls]
    return next(r for r in rolls if str(r.get("label", "")).startswith("Attack"))


def _named(roll: dict, name: str) -> list[int]:
    return [int(m["value"]) for m in roll.get("modifiers") or ()
            if str(m.get("source") or m.get("label") or "") == name]


def test_furious_focus_lifts_power_attacks_penalty_from_the_first_attack_each_turn():
    """Furious Focus (APG): two-handed, "you do not suffer Power Attack's penalty on melee
    attack rolls on the first attack you make each turn. You still suffer the penalty on
    any additional attacks." Measured before: the -3 rode every swing of BAB +8's turn."""
    pc = _wren(["Power Attack", "Furious Focus"])
    s, e, thug = _board(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    first = _swing(e, target=thug.ref, face=10, power_attack=True)
    second = _swing(e, target=thug.ref, face=10, power_attack=True)
    assert _named(_attack_roll(first), "Furious Focus") == [3]
    assert _named(_attack_roll(second), "Furious Focus") == []
    one_handed = _wren(["Power Attack", "Furious Focus"], equipped="longsword")
    assert _of(one_handed.attack_modifiers("longsword", power_attack=True,
                                           choices=("first_attack",)), "Furious Focus") == []


def test_reach_defense_dodges_an_attack_of_opportunity_from_a_foe_not_adjacent():
    """Reach Defense: "+2 dodge bonus to Armor Class against attacks of opportunity from
    opponents that are not adjacent to you"."""
    pc = _wren(["Reach Defense"])
    s, e, ogre = _board(pc, foes=["thug"])
    s.positions.update({"pc": (5, 5), ogre.ref: (7, 5)})
    with situated(s):
        assert _of(pc.ac_modifiers(attacker=ogre, provoked_by="opportunity"),
                   "Reach Defense") == [2]
        assert _of(pc.ac_modifiers(attacker=ogre), "Reach Defense") == []
        s.positions[ogre.ref] = (6, 5)
        assert _of(pc.ac_modifiers(attacker=ogre, provoked_by="opportunity"),
                   "Reach Defense") == []


def test_death_from_below_on_an_attack_of_opportunity_at_a_flier():
    pc = _wren(["Death from Below"])
    s, e, bird = _board(pc, foes=["thug"])
    s.positions.update({"pc": (5, 5), bird.ref: (6, 5, 1)})
    bird.can_move_vertically = lambda: "fly"
    with situated(s):
        assert _of(pc.attack_modifiers(defender=bird, choices=("opportunity",)),
                   "Death from Below") == [2]
        assert _of(pc.attack_modifiers(defender=bird), "Death from Below") == []
        s.positions[bird.ref] = (6, 5)
        assert _of(pc.attack_modifiers(defender=bird, choices=("opportunity",)),
                   "Death from Below") == []


def test_a_bow_threatens_nothing_until_snap_shot_and_its_weapon_focus():
    """CRB: "While wielding a ranged weapon, you threaten no squares." Measured before:
    an archer threatened its neighbours and its attack of opportunity was a bow shot."""
    from rules import reactions

    archer = _wren(equipped="longbow")
    s, e, thug = _board(archer, foes=["thug"])
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    assert not reactions.threatens(s, "pc", (6, 5))
    archer.feats = ["Snap Shot"]
    assert not reactions.threatens(s, "pc", (6, 5)), "Snap Shot needs Weapon Focus"
    archer.feats = ["Snap Shot", "Weapon Focus (longbow)"]
    assert reactions.threatens(s, "pc", (6, 5))
    assert not reactions.threatens(s, "pc", (8, 5))
    archer.equipped = "greatsword"
    assert reactions.threatens(s, "pc", (6, 5))


def test_greater_snap_shot_adds_damage_and_confirmation_on_a_ranged_opportunity():
    pc = _wren(["Greater Snap Shot"], level=16, equipped="longbow")
    assert _of(pc.damage_modifiers("longbow", choices=("opportunity",)),
               "Greater Snap Shot") == [4]
    assert _of(pc.confirm_modifiers("longbow", choices=("opportunity",)),
               "Greater Snap Shot") == [4]
    assert _of(pc.damage_modifiers("longbow"), "Greater Snap Shot") == []
    assert _of(pc.damage_modifiers("greatsword", choices=("opportunity",)),
               "Greater Snap Shot") == []


def test_elven_battle_training_guards_the_blade_and_adds_an_opportunity():
    from rules import reactions

    elf = _wren(["Elven Battle Training"], equipped="longsword")
    assert _of(elf.cmd_modifiers(maneuver="disarm"), "Elven Battle Training") == [2]
    assert _of(elf.cmd_modifiers(maneuver="trip"), "Elven Battle Training") == []
    assert reactions.budget_for(elf) == 2
    elf.feats.append("Combat Reflexes")
    assert reactions.budget_for(elf) == 1 + max(1, 1 + elf.ability_mod("dex"))
    elf.equipped = "greatsword"
    assert _of(elf.cmd_modifiers(maneuver="disarm"), "Elven Battle Training") == []
    assert reactions.budget_for(elf) == max(1, 1 + elf.ability_mod("dex"))


def test_improved_improvisation_halves_nonproficiency_and_raises_untrained_to_four():
    pc = _wren(["Improvisation", "Improved Improvisation"], weapons=["heavy flail"],
               equipped="heavy flail", **{"class": "wizard"})
    attack = pc.attack_modifiers("heavy flail")
    assert any(m.value == -2 and "halved" in m.source for m in attack), attack
    untrained = sum(m.value for m in pc.skill_modifiers("climb"))
    pc.feats = ["Improvisation"]
    assert untrained - sum(m.value for m in pc.skill_modifiers("climb")) == 2


def test_medusas_wrath_strikes_twice_more_at_a_reeling_foe():
    """Medusa's Wrath (CRB): a full attack with an unarmed strike gains "two additional
    unarmed strikes at your highest base attack bonus ... against a dazed, flat-footed,
    paralyzed, staggered, stunned, or unconscious foe"."""
    monk = _pc("monk", 12, feats=["Medusa's Wrath"])
    monk.equipped = "unarmed"
    _scene, _e = _fight(monk)
    thug = _scene.actors["c1"]
    plain = monk.attack_plan("unarmed", True, defender=thug)
    thug.add_condition("staggered", 3, source="test")
    reeling = monk.attack_plan("unarmed", True, defender=thug)
    assert len(reeling) == len(plain) + 2
    assert [i for _k, i in reeling].count(0) == [i for _k, i in plain].count(0) + 2
    assert len(monk.attack_plan("unarmed", False, defender=thug)) == 1


# --- what a landed blow sets off --------------------------------------------------------------

def test_cornugon_smash_demoralizes_the_foe_a_power_attack_damaged():
    """Cornugon Smash (Cheliax): "When you damage an opponent with a Power Attack, you may
    make an immediate Intimidate check as a free action to attempt to demoralize"."""
    pc = _wren(["Power Attack", "Cornugon Smash"], ranks={"intimidate": 8})
    pc.abilities["cha"] = 40
    s, e, thug = _board(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    res = _swing(e, target=thug.ref, face=19)
    assert not thug.has_state("state.fear"), "no Power Attack, no smash"
    res = _swing(e, target=thug.ref, face=19, power_attack=True)
    assert "Cornugon Smash: Intimidate" in _tells(res) and thug.has_state("state.fear"), \
        _tells(res)


def test_dreadful_carnage_demoralizes_the_foes_who_saw_one_fall():
    pc = _wren(["Power Attack", "Furious Focus", "Dreadful Carnage"],
               ranks={"intimidate": 8}, level=12)
    pc.abilities["cha"] = 40
    s, e, one, two = _board(pc, foes=["thug", "thug"])
    e._ensure_encounter("pc")
    s.sides = {"pc": ["pc"], "them": [one.ref, two.ref]}
    s.positions.update({"pc": (5, 5), one.ref: (6, 5), two.ref: (5, 8)})
    one.hp = 1
    res = _swing(e, target=one.ref, face=19)
    assert one.hp <= 0
    assert "Dreadful Carnage" in _tells(res) and two.has_state("state.fear"), _tells(res)


def test_two_weapon_rend_adds_its_damage_once_when_both_hands_hit():
    pc = _wren(["Two-Weapon Fighting", "Two-Weapon Rend"], weapons=["shortsword", "dagger"],
               equipped="shortsword")
    pc.abilities["str"] = 18                           # +4: 1d10 + 6
    s, e, thug = _board(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    res = _swing(e, target=thug.ref, face=19, full_attack=True, off_hand="dagger")
    said = _tells(res)
    assert said.count("Two-Weapon Rend") == 1, said
    rend = next(f for o in res.outcomes for f in o.effects
                if f.get("origin") == "rule:feat-two-weapon-rend")
    assert 7 <= rend["amount"] <= 16


def test_impact_critical_shot_trips_when_the_confirmation_beats_cmd():
    pc = _wren(["Point-Blank Shot", "Impact Critical Shot"], equipped="longbow")
    pc.abilities["dex"] = 30
    pc.goods["arrows"] = 20
    s, e, thug = _board(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (8, 5)})
    res = _swing(e, target=thug.ref, face=20)
    assert thug.has_condition("prone"), _tells(res)


# --- the feint family -------------------------------------------------------------------------

def test_improved_feint_partner_opens_the_feinted_foe_to_the_partners_swing():
    """Improved Feint Partner (UC): "Whenever an ally who also has this feat successfully
    feints against an opponent, that opponent provokes an attack of opportunity from
    you." Measured before: the feint drew the guard and nobody swung."""
    from tests.test_feats_b1_maneuvers import _Faces, _fight as _b1_fight

    both = ["Feint Partner", "Improved Feint Partner"]
    scene, engine, pc, thug = _b1_fight(*both, ally_feats=both, ally_at=(8, 10))
    engine.dice = _Faces({"Bluff": 20})
    pc.feats.append("Improved Feint")
    scene.acted.update(scene.actors)
    res = engine.run(engine.validate([{"op": "check", "actor": "pc", "target": "c1",
                                       "visibility": "hidden",
                                       "params": {"skill": "bluff", "feint": True}}]))
    while res.awaiting:
        res = engine.resume(10)
    swings = [o for o in res.outcomes if o.op == "attack"]
    assert swings and swings[0].intent_id and any(
        e.get("ref") == "c1" for o in swings for e in o.effects or ()) or swings, \
        [o.tell for o in res.outcomes]
    assert any(o.op == "attack" for o in res.outcomes), [o.tell for o in res.outcomes]


def test_disruptive_raises_the_defensive_casting_dc_by_four_within_its_reach():
    """Disruptive (CRB): "The DC to cast spells defensively increases by +4 for all
    enemies that are within your threatened area ... only if you are ... capable of
    taking an attack of opportunity." Measured before: DC 17 beside a Disruptive fighter
    as beside anybody (the concentration docstring's own not-yet)."""
    from tests.test_feats_computed import Loaded, _board as _cast_board, _cast, _wizard

    def dc_beside(feats, spent=False):
        pc = _wizard("Combat Casting")
        s, e = _cast_board(pc, Loaded(12))
        s.actors["c1"].feats = list(feats)
        if spent:
            s.reacted["c1:attack_of_opportunity"] = 1
        res = _cast(e, defensively=True)
        conc = [r for r in res.outcomes[0].rolls if r.label.startswith("Concentration")]
        return conc[0].label

    assert "DC 17" in dc_beside([])
    assert "DC 21" in dc_beside(["Disruptive"]) and "Disruptive" in dc_beside(["Disruptive"])
    assert "DC 17" in dc_beside(["Disruptive"], spent=True)


def test_a_whip_cannot_hurt_the_armoured_until_whip_mastery():
    """CRB: "A whip deals no damage to any creature with an armor bonus of +1 or higher
    or a natural armor bonus of +3 or higher." Whip Mastery: "you can deal damage with a
    whip despite" both, and "can deal lethal damage with a whip" without the -4."""
    pc = _wren(["Weapon Focus (whip)"], weapons=["whip"], equipped="whip")
    thug = from_dict({"name": "the guard", "kind": "npc", "class": "fighter", "level": 1,
                      "abilities": {"str": 12, "dex": 10, "con": 12, "int": 10, "wis": 10,
                                    "cha": 10}, "hp": 500, "armour": "chain shirt",
                      "weapons": ["longsword"], "equipped": "longsword"}, ref="c1")
    s, e = _board(pc, thug)
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    res = _swing(e, target=thug.ref, face=19)
    assert thug.hp == 500 and "does no harm" in _tells(res), _tells(res)
    assert pc.lethality_swap("whip", "lethal")
    pc.feats.append("Whip Mastery")
    res = _swing(e, target=thug.ref, face=19, lethality="lethal")
    assert thug.hp < 500, _tells(res)
    assert pc.lethality_swap("whip", "lethal") == ""


def test_slaying_sprint_delivers_a_coup_de_grace_without_provoking():
    """Slaying Sprint (UC): "Performing a coup de grace does not provoke attacks of
    opportunity", with a light or one-handed weapon. The bandit at the shoulder swung
    first before (tests/test_narration_followups.py's coup); with the feat he does not."""
    from tests.test_narration_followups import _coup, _fight as _coup_fight, _run

    s, down, standing = _coup_fight()
    s.actors["pc"].feats = list(s.actors["pc"].feats) + ["Slaying Sprint"]
    res = _run(s, [_coup(down)])
    attacks = [o for o in res.outcomes if o.op == "attack"]
    assert [o.actor for o in attacks] == ["pc"], [o.tell for o in attacks]


def test_surprising_combatant_bluffs_an_aware_foe_into_surprise():
    """Surprising Combatant (Blood of the Moon): a Bluff before the first round; an
    opponent aware of you who fails Sense Motive against it "is treated as if it were not
    aware of you". Face to face there was no surprise round; a won bluff makes one."""
    from rules import states
    from tests.test_surprise_round import _room, _run

    scene, engine, pc, thug = _room({"Sense Motive": 1, "Bluff, Surprising": 20})
    pc.feats = list(pc.feats) + ["Surprising Combatant"]
    _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "brawl"})
    assert thug.has_state(states.SURPRISED), "the thug never saw through the act"
    scene, engine, pc, thug = _room({"Sense Motive": 20, "Bluff, Surprising": 1})
    pc.feats = list(pc.feats) + ["Surprising Combatant"]
    _run(engine, {"op": "attack", "actor": "pc", "target": "c1", "because": "brawl"})
    assert not thug.has_state(states.SURPRISED)


def test_perfect_awareness_takes_twenty_in_a_fight_once_a_day():
    """Perfect Awareness: "Once per day, you can take 20 on a Perception check as a move
    action." Without it a take 20 is refused in a fight (CRB p.86) and costs two minutes."""
    from tests.test_search_and_take import _room as _search_room, _run as _search

    s, engine = _search_room()
    s.initiative, s.turn = [("pc", 15)], 0
    s.round = 1
    s.pc().feats = list(s.pc().feats) + ["Perfect Awareness"]
    before = s.clock_minutes
    out = _search(engine, "check", {"skill": "perception", "search": True, "take": 20})
    assert out.status != "refused", out.tell
    assert out.rolls[0].faces == [20] and s.clock_minutes == before
    assert s.move_spent.get("pc") == s.round
    s.round = 2
    again = _search(engine, "check", {"skill": "perception", "search": True, "take": 20})
    assert again.status == "refused" and "today" in again.tell
