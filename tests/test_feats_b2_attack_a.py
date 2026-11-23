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
