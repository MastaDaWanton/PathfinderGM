"""Feat loop batch 6, lane b6-partials (2026-11-27): the feats that carried a `not_yet`
line, finished where the book defines the rule and the machinery is small. The ledger of
every line, grouped by what each is missing, is docs/feats-partial-ledger.md.

Measured on integrate/feats-b5 3520f6a8 before this lane: 256 `not_yet` lines on 216
feats. Twelve of them named a blocker ("lane b2-actions' charge_ac", "until that lane
merges") that had merged weeks before, so the feat sat PARTIAL with its machinery built.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import classbuilder, reactions
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.engine import Engine
from tests.test_feats_b4_moves import _attack, _board, _pc, _run, _tells

MECH = Path("content/feats/mechanics")


@pytest.mark.parametrize("name", sorted(p.name for p in MECH.glob("*.json")))
def test_every_feat_file_still_validates(name):
    doc = json.loads((MECH / name).read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


def _held_by(actor, key, tags, rounds=5):
    actor.apply_effect(ActiveEffect(name=key, kind="buff", key=key, source="test",
                                    origin="author:test", duration="rounds",
                                    rounds_left=rounds, tags=tuple(tags)))


# --- the stale lines: machinery merged, the feat left PARTIAL ------------------------------

def test_improved_snap_shot_threatens_fifteen_feet_with_a_bow():
    """UC: "You threaten an additional 10 feet with Snap Shot." The line said the reader
    was another lane's and unmerged; `reactions.ranged_threat` has read the tag since b2."""
    pc = _pc("fighter", feats=["Snap Shot", "Weapon Focus (longbow)"], equipped="longbow")
    assert reactions.ranged_threat(pc) == 5
    pc.feats.append("Improved Snap Shot")
    assert reactions.ranged_threat(pc) == 15


def test_janni_style_charges_at_only_minus_one_ac():
    """UC, Janni Style: "you take only a -1 penalty to AC for charging." The charge's
    `charge_ac` offset has existed since b2; the style never wrote a term for it."""
    pc = _pc("monk", feats=["Janni Style"])
    assert Engine._stance_terms(pc, "charge")[0]["amount"] == -2
    _held_by(pc, "janni style", ["style.janni-style"])
    assert Engine._stance_terms(pc, "charge")[0]["amount"] == -1


def test_two_weapon_defense_gives_two_when_fighting_defensively():
    """CRB: "When you are fighting defensively ... this shield bonus increases to +2."
    Before: +1 whatever the stance."""
    pc = _pc("fighter", feats=["Two-Weapon Fighting", "Two-Weapon Defense"])
    plain = pc.ac()
    Engine._lay_attack_stances(pc, ("two_weapon",))
    assert pc.ac() == plain + 1
    Engine._lay_attack_stances(pc, ("two_weapon", "fighting_defensively"))
    from rules.sheet import defensive_dodge

    assert pc.ac() == plain + 2 + defensive_dodge(pc)


def test_monkey_lunge_waives_the_lunge_s_ac_only_on_a_standard_action():
    """Monkey Lunge: "As a standard action, you can use the Lunge feat ... without
    suffering a penalty to your AC." Before: the waiver held after a full attack's lunge
    too. A single lunging blow keeps the AC; a full attack's lunge pays the -2."""
    pc = _pc("fighter", feats=["Lunge", "Monkey Lunge"])
    s, e = _board(pc, ("thug", (7, 5)))
    ac = pc.ac()
    _attack(e, lunge=True)
    assert pc.has_state("buff.stance.lunging") and pc.ac() == ac
    pc2 = _pc("fighter", feats=["Lunge", "Monkey Lunge"])
    s2, e2 = _board(pc2, ("thug", (7, 5)))
    ac2 = pc2.ac()
    _attack(e2, lunge=True, full_attack=True)
    assert pc2.has_state("buff.stance.lunging") and pc2.ac() == ac2 - 2


def _cleaver(*feats):
    pc = _pc("fighter", feats=["Power Attack", "Cleave", "Goblin Cleaver", *feats])
    s, e = _board(pc, ("thug", (6, 5)), ("orc", (4, 5)))
    return s, e, pc


def _next_blow(e, s, pc):
    from rules.intents import Intent

    intent = Intent(op="attack", actor="pc", target="c1", params={"cleave": True})
    return e._cleave_next(pc, s.actors["c1"], pc.wielded_key(), intent, True)


def test_orc_hewer_cleaves_on_into_a_foe_its_own_size():
    """ARG: "your additional attacks can be made against creatures your size or smaller"
    and "+2 circumstance ... against humanoids (orc)". Goblin Cleaver alone passes over
    the Medium orc behind the bearer (not beside the first foe); Orc Hewer takes it."""
    s, e, pc = _cleaver()
    nxt, _ = _next_blow(e, s, pc)
    assert nxt is None
    s, e, pc = _cleaver("Orc Hewer")
    nxt, _ = _next_blow(e, s, pc)
    assert nxt and nxt["target"] == "c2"
    orc = s.actors["c2"]
    on = sum(m.value for m in pc.attack_modifiers(defender=orc, choices=("cleave", "cleaving_on")))
    off = sum(m.value for m in pc.attack_modifiers(defender=orc, choices=("cleave",)))
    assert on - off == 2


def test_giant_killer_reaches_one_size_larger():
    """ARG: "one size category larger than you or smaller". The ogre (Large) beside the
    bearer, not beside the first foe: Orc Hewer passes it, Giant Killer takes it."""
    pc = _pc("fighter", feats=["Power Attack", "Cleave", "Goblin Cleaver", "Orc Hewer"])
    s, e = _board(pc, ("thug", (6, 5)), ("ogre", (3, 5)))
    assert _next_blow(e, s, pc)[0] is None
    pc.feats.append("Giant Killer")
    nxt, _ = _next_blow(e, s, pc)
    assert nxt and nxt["target"] == "c2"


def _pounce(feats, acted=False):
    from tests.test_feats_b4_moves import _rolls

    pc = _pc("fighter", feats=feats)
    s, e = _board(pc, ("thug", (11, 5)), faces={"Attack with": 17, "Confirm": 2})
    if not acted:
        s.acted.discard("c1")
    res = _attack(e, charge=True)
    assert any(o.op == "move" for o in res.outcomes), _tells(res)
    return _rolls(res, "Confirm")


def test_jaguar_pounce_threatens_as_improved_critical_on_a_charge_at_the_flat_footed():
    """Sargava: "When making a charge ... against an opponent who is flat-footed or
    helpless, you treat your first melee attack ... as if you had the Improved Critical
    feat." Before: the line waited on a charge that had merged. A natural 17 with a
    19-20 blade is no threat without it; with it the blade threatens 17-20 and the
    confirmation is rolled — only while the thug has not acted."""
    assert _pounce([]) == []
    assert len(_pounce(["Jaguar Pounce"])) == 1
    assert _pounce(["Jaguar Pounce"], acted=True) == []


def _grappled_at(feats, foe="thug", acted=True):
    pc = _pc("fighter", feats=feats)
    pc.race, pc.size = "halfling", "small"
    s, e = _board(pc, (foe, (6, 5)), faces={"Grapple": 1, "Trip": 15})
    if not acted:
        s.acted.discard("pc")
    s.turn = 1                                            # the foe's turn
    return s, e, pc, _run(e, {"op": "attack", "actor": "c1", "target": "pc",
                              "visibility": "hidden", "params": {"manoeuvre": "grapple"}})


def test_under_and_over_trips_the_larger_grappler_who_failed():
    """APG: "If an opponent larger than you attempts to grapple you and fails, you may
    make a trip attack as an immediate action against that opponent with a +2 bonus."
    Before: the line waited on an immediate-action budget that had merged. The thug's
    grapple fails (a natural 1): the halfling's trip follows, its +2 named, and it
    spends her next swift."""
    from tests.test_feats_b4_moves import _rolls

    s, e, pc, res = _grappled_at(["Agile Maneuvers", "Under and Over"])
    trips = _rolls(res, "Trip (CMB)")
    assert trips and any(m.get("source") == "Under and Over" and m.get("value") == 2
                         for m in trips[0].get("modifiers") or ()), _tells(res)
    assert "Under and Over" in _tells(res)
    assert s.swift_spent.get("pc") is not None


def test_under_and_over_is_not_offered_flat_footed_or_without_the_feat():
    from tests.test_feats_b4_moves import _rolls

    s, e, pc, res = _grappled_at(["Agile Maneuvers"])
    assert _rolls(res, "Grapple (CMB)") and not _rolls(res, "Trip (CMB)")
    s, e, pc, res = _grappled_at(["Agile Maneuvers", "Under and Over"], acted=False)
    assert not _rolls(res, "Trip (CMB)") and "flat-footed" in _tells(res)


# --- single book rules ---------------------------------------------------------------------

def test_power_attack_is_not_taken_on_a_touch_or_a_blow_that_harms_no_hit_points():
    """CRB: "You can only choose to use this feat when making an attack with a melee
    weapon ... Power Attack cannot be used with touch attacks or effects that do not deal
    hit point damage." Before: a shadow given Power Attack swung its Strength-draining
    incorporeal touch at -2 for +4 damage. The ogre's greatclub still pays and gains."""
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    for template, gains in (("shadow", False), ("ogre", True)):
        foe = instantiate(template, scene=s)
        foe.feats = list(foe.feats) + ["Power Attack"]
        key = foe.wielded_key()
        hit = [m for m in foe.attack_modifiers(key, choices=("power_attack",))
               if m.source.startswith("Power Attack")]
        harm = [m for m in foe.damage_modifiers(key, choices=("power_attack",))
                if m.source.startswith("Power Attack")]
        assert bool(hit) is gains and bool(harm) is gains, template


def test_an_unarmed_body_threatens_nothing_and_its_punch_provokes_the_armed():
    """CRB, Unarmed Attacks: "An unarmed character can't take attacks of opportunity" and
    "Attacking unarmed provokes an attack of opportunity from the character you attack,
    provided she is armed." Improved Unarmed Strike: "you are considered to be armed even
    when you are unarmed." Before: a fist threatened like a sword and a punch drew
    nothing, so the feat's clause had nothing to waive. The thug's club is armed."""
    pc = _pc("fighter", equipped="unarmed")
    s, e = _board(pc, ("thug", (6, 5)))
    assert not reactions.threatens(s, "pc", (6, 5))
    res = _attack(e, weapon="unarmed")
    assert [o for o in res.outcomes if o.actor == "c1" and o.op == "attack"], _tells(res)
    pc2 = _pc("fighter", feats=["Improved Unarmed Strike"], equipped="unarmed")
    s2, e2 = _board(pc2, ("thug", (6, 5)))
    assert reactions.threatens(s2, "pc", (6, 5))
    res2 = _attack(e2, weapon="unarmed")
    assert not [o for o in res2.outcomes if o.actor == "c1" and o.op == "attack"]


def test_a_monk_a_clawed_body_and_a_printed_block_are_armed():
    from rules.engine import Scene

    assert not reactions.fights_unarmed(_pc("monk", equipped="unarmed"))
    s = Scene(location_id="5bbd0c40345f")
    for template in ("wolf", "ogre", "ghoul"):
        assert not reactions.fights_unarmed(instantiate(template, scene=s)), template


def test_necromantic_affinity_is_mended_by_an_inflict_and_hurt_by_a_cure():
    """Necromantic Affinity: "damage caused by inflict spells heals you as if you were an
    undead creature, but you also take damage from cure spells." Before: the cast loop
    turned the spell on `type.undead` alone, so the holder was wounded by an inflict."""
    from tests.test_audit_magic import _cleric, records, run, said, scene_with

    pc = _cleric()
    pc.feats = list(pc.feats) + ["Necromantic Affinity"]
    s, e = scene_with(pc)
    pc.hp = 3
    res = run(e, "cast", spell="inflict-light-wounds", at="pc")
    assert pc.hp > 3, said(res)
    assert records(res, "heal")
    before = pc.hp
    run(e, "cast", spell="cure-light-wounds", at="pc")
    assert pc.hp < before


def test_focused_disbelief_is_lowered_for_a_round_as_a_standard_action():
    """UM: "You can lower this resistance for 1 round as a standard action." Before: no
    way to lower it, so a friendly cleric's cure met the holder's SR 19."""
    from tests.test_feats_b4_moves import _use

    pc = _pc("fighter", feats=["Divine Defiance", "Focused Disbelief"])
    s, e = _board(pc, ("thug", (12, 5)))
    divine = {"against": ("spell", "divine_spell")}
    assert pc.spell_resistance_rating(divine)[0] == 19
    out = _use(e, "Lower Spell Resistance")
    assert out.status == "resolved", out.tell
    assert pc.spell_resistance_rating(divine)[0] == 0
    assert s.standard_spent.get("pc") == s.round
    pc.tick_effects(1)
    assert pc.spell_resistance_rating(divine)[0] == 19


def test_lookout_s_lifted_holder_acts_at_the_ally_s_roll_less_one():
    """APG Lookout: "If you would normally be denied the ability to act in the surprise
    round, your initiative is equal to your initiative roll or the roll of your ally -1,
    whichever is lower." Before: the lifted holder kept its own roll, here 25 over the
    ally's 12, and went first."""
    from rules import surprise
    from tests.test_feats_b4_other import _fight

    scene, engine, pc, thug = _fight(feats=["Lookout"], ally=((7, 11), ["Lookout"]))
    scene.initiative = [("ally", 25), ("c1", 15), ("pc", 12)]
    scene.turn = 1
    sides = {"pc": ["pc", "ally"], "them": ["c1"]}
    aware, unaware = ["c1", "pc"], ["ally"]
    surprise._lookouts(engine, sides, aware, unaware)
    assert scene.initiative == [("c1", 15), ("pc", 12), ("ally", 11)]
    assert scene.turn_holder() == "c1"


def test_deadly_aim_holds_until_the_next_turn():
    """CRB Deadly Aim: "You must choose to use this feat before making an attack roll and
    its effects last until your next turn." Before: the -2/+4 rode the declared shot
    only, and the next ranged attack that round was made without it. A second shot in the
    round, undeclared, still carries both; the round's end takes them away."""
    from tests.test_feats_b4_moves import _rolls

    pc = _pc("fighter", feats=["Deadly Aim"], equipped="longbow")
    pc.weapons = list(pc.weapons) + ["longbow"]
    pc.goods["arrows"] = 20
    s, e = _board(pc, ("thug", (12, 5)), faces={"Attack with": 15})
    _attack(e, deadly_aim=True)
    assert pc.has_state("buff.stance.deadly-aim")
    second = _rolls(_attack(e), "Attack with")
    assert any(m.get("source", "").startswith("Deadly Aim") for m in second[0]["modifiers"])
    pc.tick_effects(1)
    assert not pc.has_state("buff.stance.deadly-aim")


def test_drunken_brawler_s_courage_ends_with_its_temporary_hit_points():
    """Faiths of Purity: "These bonuses last an hour or until the temporary hit points
    gained by this effect are spent ... The penalties last for a full hour." Before: the
    +2 Fortitude and Will held the hour after a blow had spent all five hit points."""
    from rules.dice import Dice
    from rules.engine import Scene
    from tests.test_feats_b5_spells import _wren

    pc = _wren(["Endurance", "Drunken Brawler"], level=5)
    pc.goods["mug of ale"] = 1
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, Dice(seed=1))
    reflex = sum(m.value for m in pc.save_modifiers("ref"))
    e.run(e.validate([{"op": "drink", "actor": pc.ref, "because": "test",
                       "params": {"item": "mug of ale"}}]))

    def alchemical(save):
        return sum(m.value for m in pc.save_modifiers(save) if m.type == "alchemical")

    assert (pc.temp_hp, alchemical("fort"), alchemical("will")) == (5, 2, 2)
    pc.take_damage(5)
    assert (pc.temp_hp, alchemical("fort"), alchemical("will")) == (0, 0, 0)
    assert sum(m.value for m in pc.save_modifiers("ref")) == reflex - 2


def test_prone_shooter_counts_from_the_end_of_the_prone_body_s_own_turn():
    """UC Prone Shooter: "If you have been prone since the end of your last turn". Before:
    the softer AC held the moment the archer dropped. Dropped on her turn, she is plain
    prone; the turn passing to the thug settles it."""
    pc = _pc("fighter", feats=["Prone Shooter"])
    s, e = _board(pc, ("thug", (12, 5)))
    standing = pc.ac("ranged")
    pc.add_condition("prone")
    assert pc.ac("ranged") == standing + 4
    assert s.advance_turn() == "c1"
    assert pc.ac("ranged") == standing + 6


# --- what a blow is made of ------------------------------------------------------------------

def test_a_blow_s_own_damage_type_passes_a_reduction_naming_it():
    """CRB, Damage Reduction: DR 5/bludgeoning is overcome by bludgeoning weapons. Measured
    before: `damage_reduction` asked the blow's `strikes_as` traits only, so a club met a
    skeleton's full 5 exactly as a sword did."""
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    bones = instantiate("skeleton", scene=s)
    assert bones.damage_reduction("bludgeoning") is None
    assert bones.damage_reduction("slashing").amount == 5


def test_boar_style_s_fist_cuts_past_a_zombie_s_slashing_reduction():
    """UC Boar Style: "You can deal bludgeoning damage or slashing damage with your unarmed
    strikes"; Snake Style and Boar Ferocity add piercing. Before: a fist was bludgeoning
    whatever the style. The zombie's DR 5/slashing meets a plain fist and not Boar Style's."""
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    zombie = instantiate("zombie", scene=s)
    for feats, gets_past in (([], False), (["Boar Style"], True), (["Snake Style"], False)):
        pc = _pc("monk", feats=["Improved Unarmed Strike", *feats], equipped="unarmed")
        fist = pc.weapon("unarmed")
        passed = zombie.damage_reduction(fist["type"], tuple(fist.get("strikes_as") or ()))
        assert (passed is None) is gets_past, feats
    snake = _pc("monk", feats=["Snake Style"], equipped="unarmed").weapon("unarmed")
    assert "piercing" in snake["strikes_as"]
