"""Feat loop batch 5, lane b5-maneuver: each feat's numbers measured through the engine.

Before this batch the thirteen elemental style feats (Djinni, Efreeti, Marid and Shaitan)
each carried a `not_yet` saying "Elemental Fist: the feat has no engine yet" — batch 4
built Elemental Fist and nothing of theirs ran: a Djinni Spirit monk's lightning deafened
nobody, an Efreeti Style miss burned nothing, Djinni Spin was refused by name. The rest of
b5-maneuver.tsv had no document at all. The tests make the real swing, use or manoeuvre
and read the terms it rolled with, the damage it dealt and the state it left.
"""
from __future__ import annotations

import pytest

from rules import feats as feats_mod, styles
from tests.test_feats_b4_combat import _attack, _cond, _monk, _tells, _use


def _style(actor, fid):
    actor.apply_effect(styles.stance(feats_mod.get(fid)))


def _damage(res, dtype):
    return [e for o in res.outcomes for e in o.effects
            if e.get("kind") == "damage" and e.get("type") == dtype]


ELEMENTAL = ["Improved Unarmed Strike", "Elemental Fist"]


# --- the elemental styles ---------------------------------------------------------------

def test_each_style_feat_adds_an_elemental_fist_attempt_a_day():
    """Djinni Style and Djinni Spirit each say "You gain one additional Elemental Fist
    attempt per day". Measured before: an 8th-level monk holding both had 8, as without."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"])
    _use(engine, "elemental fist (electricity)")
    assert pc.pool("elemental fist").maximum == 10


def test_djinni_style_holds_the_fist_to_lightning_and_adds_wisdom_to_it():
    """Djinni Style (UC): "While you are in this style you must use Elemental Fist to deal
    electricity damage and you gain a bonus on electricity damage rolls equal to your
    Wisdom bonus." Djinni Spirit: "Creatures that take electricity damage from your
    Elemental Fist attack must succeed at a Fortitude save ... or be deafened for 1d4
    rounds." Measured before: the cold fist was armed in the stance, the lightning rolled
    a bare 1d6, and the thug heard everything."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 4,
                                           "Fortitude save against djinni spirit": 1})
    pc.abilities["wis"] = 16
    _style(pc, "djinni-style")
    assert _use(engine, "elemental fist (cold)").status != "resolved"
    assert _use(engine, "elemental fist (electricity)").status == "resolved"
    res = _attack(engine, weapon="unarmed")
    zap = _damage(res, "electricity")
    assert zap and zap[0]["amount"] == 4 + 3, _tells(res)
    assert _cond(thug, "deafened") is not None, _tells(res)


def test_djinni_spirit_deafens_only_with_the_fists_lightning_in_the_stance():
    """Out of the stance the follow-up feat does nothing (UC: a feat with a style
    prerequisite works "only while in the stance"), and a cold fist deafens nobody."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 4,
                                           "Fortitude save against djinni spirit": 1})
    _use(engine, "elemental fist (electricity)")
    _attack(engine, weapon="unarmed")
    assert _cond(thug, "deafened") is None


def test_djinni_style_dodges_attacks_of_opportunity_while_attempts_remain():
    """Djinni Style: "while you are using this style and have remaining Elemental Fist
    attempts, you also gain a +2 dodge bonus to Armor Class against attacks of
    opportunity." Measured on the AC line: +2 against a swing a move provoked, none
    against an ordinary blow, none with the pool empty."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style"])
    _style(pc, "djinni-style")
    _use(engine, "elemental fist (electricity)")
    plain = pc.ac(attacker=thug)
    assert pc.ac(attacker=thug, provoked_by="movement") >= plain + 2
    pc.spend_pool("elemental fist", pc.pool("elemental fist").current)
    assert pc.ac(attacker=thug, provoked_by="movement") < plain + 2 or \
        pc.ac(attacker=thug) < plain


def test_efreeti_style_burns_on_a_miss_and_efreeti_stance_sets_the_foe_alight():
    """Efreeti Style: "if your Elemental Fist melee attack misses while you are using it
    to deal fire damage, you still deal 1d6 points of fire damage to your target."
    Efreeti Stance: "Creatures that take fire damage from your Elemental Fist attack must
    succeed at a Reflex save ... or catch on fire." Measured before: the miss spent the
    fist and did nothing; a hit set nobody alight."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Efreeti Style", "Efreeti Stance"],
                                    faces={"Attack with": 2, "Damage": 2,
                                           "Elemental Fist": 5,
                                           "Reflex save against catching fire": 1})
    _style(pc, "efreeti-style")
    _use(engine, "elemental fist")                           # flame, the default
    res = _attack(engine, weapon="unarmed")
    fire = _damage(res, "fire")
    assert fire and fire[0]["amount"] == 5 and "still reaches" in _tells(res), _tells(res)
    engine.dice.faces["Attack with"] = 18
    scene.round += 1
    pc.tick_effects()
    _use(engine, "elemental fist")
    res = _attack(engine, weapon="unarmed")
    assert thug.has_state("state.burning"), _tells(res)


def test_marid_style_reaches_further_with_the_cold_fist_and_marid_spirit_ices_the_foe():
    """Marid Style: "While using this style and Elemental Fist to deal cold damage ...
    your reach with your unarmed strike increases by 5 feet." Marid Spirit: Fortitude or
    "entangled in ice for 1d4 rounds ... a break DC of 15 + your base attack bonus or monk
    level" — the escape op's hold."""
    from rules import reactions

    scene, engine, pc, thug = _monk(ELEMENTAL + ["Marid Style", "Marid Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 3,
                                           "Fortitude save against marid spirit": 1})
    _style(pc, "marid-style")
    before = reactions.reach_with(pc, "unarmed")[0]
    _use(engine, "elemental fist (cold)")
    assert reactions.reach_with(pc, "unarmed")[0] == before + 5
    assert reactions.reach_with(pc, "longsword")[0] == before
    _attack(engine, weapon="unarmed")
    ice = _cond(thug, "entangled")
    assert ice is not None
    assert (ice.payload or {})["ends_when"]["escape"]["dc"] == 15 + max(pc.bab, 8)


def test_shaitan_skin_staggers_with_the_acid_fist():
    """Shaitan Skin: "Creatures that take acid damage from your Elemental Fist attack must
    succeed at a Reflex save ... or be staggered for 1 round.\""""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Shaitan Style", "Shaitan Skin"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 3,
                                           "Reflex save against shaitan skin": 1})
    _style(pc, "shaitan-style")
    _use(engine, "elemental fist (acid)")
    _attack(engine, weapon="unarmed")
    assert _cond(thug, "staggered") is not None


def test_djinni_spin_spends_two_attempts_and_lands_fist_and_lightning_on_the_adjacent():
    """Djinni Spin: "spend two Elemental Fist attempts ... Creatures adjacent to you take
    your unarmed strike damage plus the electricity damage from your Elemental Fist and
    are deafened for 1d4 rounds" (deafened even on a save, by its prerequisite Djinni
    Spirit). Measured before: "use Djinni Spin" was refused by name."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit",
                                                 "Djinni Spin"],
                                    faces={"Djinni Spin": 4,
                                           "Fortitude save against Djinni Spin": 20})
    _style(pc, "djinni-style")
    out = _use(engine, "djinni spin")
    assert out.status == "resolved", out.tell
    assert pc.pool("elemental fist").current == pc.pool("elemental fist").maximum - 2
    kinds = {e.get("type") for e in out.effects if e.get("kind") == "damage"
             and e.get("ref") == thug.ref}
    assert {"electricity", "bludgeoning"} <= kinds, out.tell
    assert _cond(thug, "deafened") is not None, out.tell


def test_djinni_spin_is_refused_out_of_the_stance_and_nothing_is_spent():
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit",
                                                 "Djinni Spin"])
    _use(engine, "elemental fist (electricity)")
    left = pc.pool("elemental fist").current
    assert _use(engine, "djinni spin").status != "resolved"
    assert pc.pool("elemental fist").current == left


@pytest.mark.parametrize("feats,style,use,energy,save,check", [
    (["Efreeti Style", "Efreeti Stance", "Efreeti Touch"], "efreeti-style",
     "efreeti touch", "fire", "Reflex", lambda t: t.has_state("state.burning")),
    (["Marid Style", "Marid Spirit", "Marid Coldsnap"], "marid-style",
     "marid coldsnap", "cold", "Reflex",
     lambda t: (_cond(t, "entangled").payload or {}).get("ends_when", {}).get("escape")),
    (["Shaitan Style", "Shaitan Skin", "Shaitan Earthblast"], "shaitan-style",
     "shaitan earthblast", "acid", "Reflex", lambda t: _cond(t, "staggered") is not None),
])
def test_the_two_attempt_areas_land_fist_and_energy_and_their_rider_on_a_failed_save(
        feats, style, use, energy, save, check):
    """Efreeti Touch's 15-foot cone ("catch on fire"), Marid Coldsnap's 30-foot line
    ("entangled in ice as per the Marid Spirit feat"), Shaitan Earthblast's 5-foot column
    within 30 feet ("staggered for 1 round"): two Elemental Fist attempts, the user's
    unarmed strike plus the energy, the rider on a failed save. Measured before: each was
    a feat with no use at all."""
    scene, engine, pc, thug = _monk(ELEMENTAL + feats, level=12,
                                    faces={f"{save} save against": 1})
    _style(pc, style)
    out = _use(engine, use, to=thug.ref)
    assert out.status == "resolved", out.tell
    kinds = {e.get("type") for e in out.effects if e.get("kind") == "damage"
             and e.get("ref") == thug.ref}
    assert {energy, "bludgeoning"} <= kinds, out.tell
    assert check(thug), out.tell
    assert pc.pool("elemental fist").current == pc.pool("elemental fist").maximum - 2
