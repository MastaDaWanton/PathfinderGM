"""Feat loop batch 6, lane b6-rules (2026-11-27): the feats the lane's base rules unblocked,
and the leftover list, proved through the engine.

Measured before this lane, on integrate/feats-b5 3520f6a8: none of these feats had a
document. Improved Counterspell, Parry Spell and Disrupting Shot had no counterspell or
readied shot to hang on until b5-core; Dispel Synergy, Tenacious Transmutation, Atheist
Abjurations and Tenebrous Spell's dispel clause waited on a dispel check that never ran.
"""
from __future__ import annotations

import json
from pathlib import Path

from rules import classbuilder, dispel
from tests.test_dispel import _haste_on, _two_casters
from tests.test_feats_b4_moves import _board, _pc, _run, _tells
from tests.test_readied_action import _caster, _ready, _thugs_turn

LANE = Path("content/feats/mechanics/b6-rules.json")


def test_the_lane_file_validates():
    doc = json.loads(LANE.read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


def _countering(feats, prepared, faces=None):
    pc = _caster("pc", prepared=prepared, feats=feats)
    s, e = _board(pc, ("thug", (8, 5)), faces=faces or {"Vell": 19})
    foe = _caster("c1", name="Orsk the Witch-Eye")
    s.people.pop("c1")
    s.add(foe, at=(8, 5))
    _ready(e, trigger="casts", action="counterspell")
    _thugs_turn(s)
    return s, e, pc, foe


# --- the counterspell feats ------------------------------------------------------------------

def test_improved_counterspell_counters_with_a_higher_spell_of_the_school():
    """CRB: "you may use a spell of the same school that is one or more spell levels higher
    than the target spell". A wizard holding scorching ray (evocation 2nd) and neither magic
    missile nor dispel magic cannot counter the missile; with the feat the ray answers it
    and its slot is spent."""
    for feats, countered in (((), False), (("Improved Counterspell",), True)):
        s, e, pc, foe = _countering(feats, ("scorching-ray",))
        before = pc.pool("spell slot 2").current
        res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                       "params": {"spell": "magic-missile"}})
        hit = any(x.get("kind") == "countered" for o in res.outcomes for x in o.effects)
        assert hit is countered, (feats, _tells(res))
        if countered:
            assert "Improved Counterspell" in _tells(res)
            assert pc.pool("spell slot 2").current == before - 1


def test_parry_spell_turns_the_countered_missile_back_on_its_caster():
    """APG: "Whenever you successfully counter a spell, it returns back to its caster. This
    works exactly like the spell turning spell." The missile aimed at the wizard is
    countered with the same spell and strikes the one who cast it."""
    s, e, pc, foe = _countering(("Parry Spell",), ("magic-missile",))
    hp_pc, hp_foe = pc.hp, foe.hp
    res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                   "params": {"spell": "magic-missile"}})
    said = _tells(res)
    assert pc.hp == hp_pc, said
    assert foe.hp < hp_foe, said
    assert "turns back on Orsk" in said, said


def test_without_parry_spell_a_countered_missile_strikes_nobody():
    s, e, pc, foe = _countering((), ("magic-missile",))
    hp_foe = foe.hp
    _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
             "params": {"spell": "magic-missile"}})
    assert foe.hp == hp_foe


def test_the_counterspell_dispel_check_is_capped_and_uses_the_funnel():
    """The readied counterspell's dispel check added the whole caster level (a 14th-level
    wizard rolled 1d20 + 14); the book caps it at +10. It goes through rules/dispel.py now:
    the check's roll carries "caster level (max +10)"."""
    pc = _caster("pc", prepared=("dispel-magic",))
    pc.level = 14
    s, e = _board(pc, ("thug", (8, 5)))
    foe = _caster("c1", name="Orsk the Witch-Eye")
    s.people.pop("c1"); s.add(foe, at=(8, 5))
    from rules import spells

    beat, roll, dc = dispel.counter_check(e, pc, 14, "dispel-magic", "abjuration", foe,
                                          spells.get("magic-missile"))
    assert dc == 18
    assert sum(m.value for m in roll.modifiers) == 10, [m.as_dict() for m in roll.modifiers]


def test_disrupting_shot_adds_four_to_the_struck_casters_concentration():
    """APG: "If you ready an action to shoot an opponent casting a spell within 30 feet and
    successfully hit that opponent with a ranged attack, the concentration DC ... is
    increased by +4." The readied arrow lands and the caster's struck check names it."""
    for feats, named in (((), False), (("Point-Blank Shot", "Disrupting Shot"), True)):
        pc = _pc("fighter", feats=feats, weapons=("longbow",))
        pc.equipped = "longbow"
        pc.goods["arrows"] = 20
        s, e = _board(pc, ("thug", (9, 5)), faces={"Kesst": 19})
        foe = _caster("c1")
        s.people.pop("c1"); s.add(foe, at=(9, 5))
        _ready(e, trigger="casts")
        _thugs_turn(s)
        res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                       "params": {"spell": "magic-missile"}})
        said = _tells(res)
        assert "while casting" in said, said
        assert ("Disrupting Shot" in said) is named, said


# --- the dispel feats --------------------------------------------------------------------------

def test_dispel_synergy_leaves_the_dispelled_foe_minus_two_on_saves_against_the_dispeller():
    """UC: "If you successfully dispel an ongoing magical effect on an opponent, that
    opponent takes a -2 penalty on saving throws against your spells until the end of your
    next turn." After the haste goes, the foe's Will save against the dispeller's spell is
    2 lower; against anyone else's it is not."""
    s, e, pc, foe = _two_casters(faces={"Vell the Hedge-Mage's dispel": 15},
                                 feats=("Dispel Synergy",))
    s.turn = 1
    _haste_on(e)
    s.turn = 0
    res = _run(e, {"op": "cast", "actor": "pc", "target": "c1", "visibility": "hidden",
                   "params": {"spell": "dispel-magic", "at": "c1"}})
    assert "Dispel Synergy" in _tells(res), _tells(res)

    def will(vs):
        return sum(m.value for m in foe.save_modifiers(
            "will", {"against": ("spell",), "attacker_actor": vs}))

    assert will(pc) == will(s.actors["c1"]) - 2
    foe.tick_effects(2)
    assert will(pc) == will(s.actors["c1"])


def test_tenacious_transmutation_raises_the_dc_and_lingers_a_round():
    """APG: "The DC of caster level checks to dispel or remove your transmutations increases
    by 2; even if the spell is negated, its effects persist for 1 additional round". The
    haste of a caster with the feat is DC 20 (11 + 7 + 2), not 18; beaten, it is still on
    for one round and the ticker ends it."""
    s, e, pc, foe = _two_casters(faces={"Vell the Hedge-Mage's dispel": 15})
    foe.feats = list(foe.feats) + ["Spell Focus (transmutation)", "Tenacious Transmutation"]
    s.turn = 1
    _haste_on(e)
    s.turn = 0
    res = _run(e, {"op": "cast", "actor": "pc", "target": "c1", "visibility": "hidden",
                   "params": {"spell": "dispel-magic", "at": "c1"}})
    checks = [x for o in res.outcomes for x in o.effects if x.get("kind") == "dispel_check"]
    assert checks[0]["dc"] == 20, checks
    left = [x for x in foe.effects if x.origin == "spell:haste"]
    assert left and {x.rounds_left for x in left} == {1}, _tells(res)
    foe.tick_effects(1)
    assert not [x for x in foe.effects if x.origin == "spell:haste"]


def test_atheist_abjurations_is_two_on_dispelling_a_divine_spell_only():
    """F&P: "+2 bonus to your caster level whenever you use an abjuration spell to dispel
    or counter a divine spell." The term rides the check against a cleric's spell and not
    an arcane one."""
    pc = _pc("wizard", level=7, feats=["Divine Defiance", "Atheist Abjurations"])
    divine = dispel.check_mods(pc, 7, "dispel-magic", {"divine": True, "by_school": "abjuration"})
    arcane = dispel.check_mods(pc, 7, "dispel-magic", {"divine": False, "by_school": "abjuration"})
    assert sum(m.value for m in divine) == 9 and sum(m.value for m in arcane) == 7


def test_a_tenebrous_spell_is_harder_to_dispel_in_the_dark_and_easier_in_bright_light():
    """Inner Sea Magic: "Any attempts at dispelling a tenebrous spell in darkness or dim
    light take a -2 penalty on the dispel check ... in bright light gain a +4 bonus" — the
    b3-arcane not_yet, closed by the stamp (the effect knows it was cast tenebrous)."""
    pc = _pc("wizard", level=7)
    base = {"tenebrous": True}
    assert sum(m.value for m in dispel.check_mods(pc, 7, "dispel-magic", base, "dim")) == 5
    assert sum(m.value for m in dispel.check_mods(pc, 7, "dispel-magic", base, "bright")) == 11
    assert sum(m.value for m in dispel.check_mods(pc, 7, "dispel-magic", base, "normal")) == 7


# --- haste's tag -----------------------------------------------------------------------------

def test_haste_carries_its_tag_and_slow_time_does_not_stack_with_it():
    """F&P Slow Time: "These effects do not stack with the haste spell". Haste's buffs had
    no tag (b5-other matched its origin string); every term of a cast haste carries
    `buff.haste` now, Slow Time asks the tag and adds nothing, and a haste cast on a monk
    already under Slow Time replaces it rather than stacking a second +1."""
    from tests.test_feats_b5_other import _monk_meditates

    s, e, pc, foe = _two_casters()
    s.turn = 1
    _haste_on(e)
    assert foe.has_state("buff.haste")

    monk, s2, e2, out = _monk_meditates("Slow Time")
    assert monk.has_state("buff.haste"), out.tell
    hit = sum(m.value for m in monk.attack_modifiers(monk.equipped or "unarmed"))
    wiz = _caster("c9", prepared=("haste",), name="Iri")
    s2.add(wiz, at=(1, 1))
    s2.sides.setdefault("pc", []).append("c9")
    res = e2.run(e2.validate([{"op": "cast", "actor": "c9", "target": "pc", "because": "t",
                               "visibility": "hidden", "params": {"spell": "haste", "at": "pc"}}]))
    assert not [x for x in monk.effects if x.name == "Slow Time"], _tells(res)
    assert monk.has_state("buff.haste")
    assert sum(m.value for m in monk.attack_modifiers(monk.equipped or "unarmed")) == hit


# --- Stalwart ----------------------------------------------------------------------------------

def _stalwart(*more, level=8):
    pc = _pc("fighter", level=level, feats=["Diehard", "Endurance", "Combat Expertise",
                                            "Stalwart", *more], weapons=("longsword",))
    pc.equipped = "longsword"
    s, e = _board(pc, ("thug", (6, 5)))
    return pc, s, e


def test_stalwart_trades_combat_expertise_s_dodge_for_damage_reduction():
    """ACG Stalwart: "you can forgo the dodge bonus to AC you would normally gain to instead
    gain an equivalent amount of DR, to a maximum of DR 5/-, until the start of your next
    turn." At base attack +8 Combat Expertise is +3 dodge: declared with Stalwart, the AC is
    the plain AC and a blow is soaked by DR 3/—; a round later both are gone."""
    pc, s, e = _stalwart()
    ac = pc.ac()
    _run(e, {"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
             "params": {"combat_expertise": True, "stalwart": True}})
    assert pc.ac() == ac
    dr = pc.damage_reduction("slashing")
    assert dr is not None and dr.amount == 3 and dr.bypass == "", dr
    pc.tick_effects(1)
    assert pc.damage_reduction("slashing") is None


def test_improved_stalwart_doubles_it_and_total_defense_trades_too():
    """Improved Stalwart (ACG): "Double the DR you gain from Stalwart, to a maximum of DR
    10/-." Total defense's +4 dodge with the trade is DR 8/—; without Improved, DR 4/—."""
    for more, want in (((), 4), (("Improved Stalwart",), 8)):
        pc, s, e = _stalwart(*more, level=12)
        res = _run(e, {"op": "total_defense", "actor": "pc", "params": {"stalwart": True}})
        assert "stalwart" in _tells(res).lower(), _tells(res)
        assert pc.damage_reduction("bludgeoning").amount == want


def test_stalwart_dr_is_denied_with_the_dexterity_bonus():
    """ACG: "If you are denied your Dexterity bonus to AC, you are also denied this DR." The
    same trade, then flat-footed: no DR."""
    pc, s, e = _stalwart()
    _run(e, {"op": "total_defense", "actor": "pc", "params": {"stalwart": True}})
    assert pc.damage_reduction("slashing").amount == 4
    pc.add_condition("flat-footed", rounds=1)
    assert pc.damage_reduction("slashing") is None


def test_stalwart_is_on_the_declare_section():
    """The combat bar's Declare section lists Stalwart beside Combat Expertise, and the
    total defense trade as its own action (play/views.py `_attack_options`)."""
    from play.views import _attack_options

    pc, s, e = _stalwart()
    ids = {o["id"]: o for o in _attack_options(pc)["options"]}
    assert "stalwart" in ids and not ids["stalwart"]["why"], ids.get("stalwart")
    assert ids["total_defense_stalwart"]["op"] == {"op": "total_defense",
                                                   "params": {"stalwart": True}}
    assert "DR 4/—" in ids["total_defense_stalwart"]["says"]


# --- Stunning Fist for any class -----------------------------------------------------------------

def test_a_fighter_with_stunning_fist_stuns_level_over_four_times_a_day():
    """Measured before (audit 2026-11-22): Stunning Fist "runs only as the monk class ability
    ... a non-monk taking the feat gets no uses" — "use Stunning Fist" from a fighter was
    refused by name. CRB: "once per day for every four levels you have attained": a fighter
    8 has two; the unarmed hit's failed Fortitude save stuns."""
    from tests.test_feats_b2_attack_a import _adjacent, _fight, _swing, _use
    from tests.test_feats_b2_attack_a import _pc as pc2

    f = pc2("fighter", 8, feats=["Improved Unarmed Strike", "Stunning Fist"])
    f.abilities["wis"] = 40
    f.equipped = "unarmed"
    scene, e = _fight(f)
    _adjacent(scene)
    thug = scene.actors["c1"]
    thug.hp_max = thug.hp = 500
    out = _use(e, "Stunning Fist")
    assert out.status == "resolved", out.tell
    assert f.pool("stunning fist").maximum == 2
    res = _swing(e, face=19)
    assert thug.has_condition("stunned"), _tells(res)


def test_a_monk_keeps_one_stunning_fist_at_monk_level_uses():
    """The monk's own Stunning Fist (monk level times a day) stands in the feat's place:
    one ability, not two, and its pool is the class's."""
    from rules import class_abilities
    from tests.test_feats_b4_maneuver import _monk

    monk = _monk(["Stunning Fist"])
    docs = [d for d in class_abilities._docs_for(monk) if d.get("key") == "stunning fist"]
    assert len(docs) == 1 and docs[0]["class"] == "monk"


# --- the worn helmet -----------------------------------------------------------------------------

def test_dented_and_cloven_helm_add_to_ac_against_confirmation_only_while_a_helmet_is_worn():
    """Dwarves of Golarion: "When wearing a helmet, you add +1 to your AC against critical
    hit confirmation rolls" (Dented Helm; Cloven Helm's "stacks with Dented Helm"). Before
    this lane no helmet was a thing a sheet could wear, and both documents were not_yet. A
    leather cap in the head slot carries `gear.helmet`; the confirming roll against the
    wearer is -1, -2 with both feats; with the cap off, nothing."""
    from rules import helmet

    dwarf = _pc("fighter", level=12, race="dwarf",
                feats=["Hard-Headed", "Dented Helm", "Cloven Helm"])

    def against():
        return sum(m.value for m in dwarf._buff_mods("combat_mod", "crit_confirm_against"))

    assert not dwarf.has_state(helmet.TAG) and against() == 0
    dwarf.wear({"name": "Leather Cap", "slot": "head", "base": "cap"})
    assert dwarf.has_state(helmet.TAG)
    assert against() == -2
    dwarf.feats = [f for f in dwarf.feats if f != "Cloven Helm"]
    assert against() == -1


# --- the Ki Throw line ---------------------------------------------------------------------------

def _thrower(*more, faces=None):
    pc = _pc("monk", level=10, feats=("Improved Unarmed Strike", "Improved Trip", "Ki Throw",
                                      "Improved Bull Rush", *more))
    pc.equipped = "unarmed"
    pc.armour = "none"
    s, e = _board(pc, ("thug", (6, 5)), ("thug", (5, 6)), faces=faces or {"Trip": 20})
    return pc, s, e


def _throw(e, square):
    return _run(e, {"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
                    "params": {"manoeuvre": "trip", "weapon": "unarmed", "square": square}})


def test_improved_ki_throw_throws_into_a_foes_square_and_knocks_it_down():
    """APG: "you may throw your target into any square you threaten that is occupied by
    another creature. Make a bull rush combat maneuver check with a -4 penalty against the
    secondary target. If this check succeeds, the thrown creature lands prone in the
    secondary target's square, while the secondary target is pushed back and knocked prone".
    Before: a throw at an occupied square was refused ("can only be thrown into an open
    square"). With the feat and a high bull rush, thug 1 lands where thug 2 stood, and thug
    2 is pushed a square and prone."""
    for more, thrown in (((), False), (("Improved Ki Throw",), True)):
        pc, s, e = _thrower(*more, faces={"Trip": 20, "Kesst Vayr's bull rush": 20})
        res = _throw(e, [5, 6])
        said = _tells(res)
        one, two = s.actors["c1"], s.actors["c2"]
        assert (tuple(s.positions["c1"])[:2] == (5, 6)) is thrown, said
        if thrown:
            assert "-4" in " ".join(str(m.as_dict()) for o in res.outcomes for r in o.rolls
                                    for m in r.modifiers or ()), said
            assert two.has_state("state.position.prone") and \
                tuple(s.positions["c2"])[:2] != (5, 6), said


def test_a_failed_improved_ki_throw_lands_beside_the_secondary_target():
    """APG: "If the check fails, the thrown creature lands prone in the nearest square you
    threaten adjacent to the secondary target." Thug 2 keeps its square."""
    pc, s, e = _thrower("Improved Ki Throw", faces={"Trip": 20, "Kesst Vayr's bull rush": 1})
    res = _throw(e, [5, 6])
    assert tuple(s.positions["c2"])[:2] == (5, 6)
    assert tuple(s.positions["c1"])[:2] != (6, 5), _tells(res)
    assert not s.actors["c2"].has_state("state.position.prone")


def test_enhanced_ki_throw_spends_a_ki_point_for_unarmed_damage_on_landing():
    """APG: "you can expend 1 ki point ... If your ki throw succeeds, when the target hits
    the ground, it takes damage as if you had hit it with an unarmed strike." Measured
    before: no ki spent, no damage — the b4 document's not_yet."""
    pc, s, e = _thrower("Enhanced Ki Throw")
    thug = s.actors["c1"]
    thug.hp_max = thug.hp = 200
    ki = pc.pool("ki").current
    res = _throw(e, [4, 5])
    assert pc.pool("ki").current == ki - 1, _tells(res)
    assert thug.hp < 200 and "Enhanced Ki Throw" in _tells(res)


# --- the readied charge ------------------------------------------------------------------------

def test_rhino_charge_readies_a_charge_that_moves_up_to_speed():
    """APG Rhino Charge: "You may ready a charge, though you may only move up to your speed
    on the charge." Before: the b4 not_yet, "the engine has no readied action", and since
    b5-core only an attack or a counterspell could be readied. Without the feat the readied
    charge is refused; with it, a caster 25 feet off who begins a spell is charged and
    struck first; one 45 feet off is past the fighter's speed and is not reached."""
    plain = _pc("fighter", feats=("Power Attack", "Improved Bull Rush"), weapons=("longsword",))
    s, e = _board(plain, ("thug", (10, 5)))
    assert _ready(e, trigger="casts", action="charge").outcomes[-1].status == "refused"
    for x, reached in ((10, True), (14, False)):
        pc = _pc("fighter", feats=("Power Attack", "Improved Bull Rush", "Rhino Charge"),
                 weapons=("longsword",))
        pc.equipped = "longsword"
        s, e = _board(pc, ("thug", (x, 5)), faces={"Kesst": 18})
        foe = _caster("c1")
        s.people.pop("c1"); s.add(foe, at=(x, 5))
        res = _ready(e, trigger="casts", action="charge")
        assert res.outcomes[-1].status == "resolved", _tells(res)
        _thugs_turn(s)
        res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                       "params": {"spell": "magic-missile"}})
        mine = [o for o in res.outcomes if o.actor == "pc" and o.op == "attack"
                and o.status == "resolved"]
        assert bool(mine) is reached, _tells(res)
        if reached:
            assert [o.actor for o in res.outcomes].index("pc") < \
                [o.actor for o in res.outcomes].index("c1"), _tells(res)


def test_the_readied_charge_is_offered_on_the_declare_section_to_rhino_charge_only():
    from play.views import _attack_options

    for feats, offered in ((("Power Attack", "Improved Bull Rush"), False),
                           (("Power Attack", "Improved Bull Rush", "Rhino Charge"), True)):
        pc = _pc("fighter", feats=feats, weapons=("longsword",))
        _board(pc, ("thug", (9, 5)))
        ids = {o["id"]: o for o in _attack_options(pc)["options"]}
        assert ("ready_charge_cast" in ids) is offered
        if offered:
            assert ids["ready_charge_cast"]["op"]["params"]["action"] == "charge"


# --- Antagonize ---------------------------------------------------------------------------------

def _antagonist(skill, face, ranks=8):
    pc = _pc("fighter", feats=("Antagonize",), weapons=("longsword",))
    pc.ranks[skill] = ranks
    s, e = _board(pc, ("thug", (8, 5)), ("thug", (9, 9)),
                  faces={f"{skill.title()} check": face})
    res = _run(e, {"op": "check", "actor": "pc", "target": "c1", "visibility": "hidden",
                   "params": {"skill": skill, "antagonize": True}})
    return pc, s, e, res


def test_antagonize_by_diplomacy_flusters_the_foe_against_everyone_else():
    """UM Antagonize, Diplomacy: "For the next minute, the target takes a -2 penalty on all
    attacks rolls made against creatures other than you". Before: no document, and "I goad
    him" had no door. The thug's swing at the other thug carries -2, at the antagonist
    nothing; a second try the same day is refused."""
    from rules import compulsion

    pc, s, e, res = _antagonist("diplomacy", 18)
    thug = s.actors["c1"]
    assert "flustered" in _tells(res), _tells(res)
    assert sum(m.value for m in compulsion.penalty_against(thug, "c2")) == -2
    assert compulsion.penalty_against(thug, "pc") == []
    assert s.standard_spent.get("pc") == s.round
    s.standard_spent.pop("pc", None)
    again = _run(e, {"op": "check", "actor": "pc", "target": "c1", "visibility": "hidden",
                     "params": {"skill": "diplomacy", "antagonize": True}})
    assert again.outcomes[-1].status == "refused" and "today" in _tells(again)


def test_antagonize_by_intimidate_turns_the_foe_on_the_antagonist_and_a_miss_does_nothing():
    """UM Antagonize, Intimidate: "On its next turn, the target must attempt to make a melee
    attack against you" — the compulsion's pull, -4 at anyone else (owner call: the app's
    compulsion penalises and never prohibits). A check under DC 10 + HD + Wis lays nothing."""
    from rules import compulsion

    pc, s, e, res = _antagonist("intimidate", 18)
    assert sum(m.value for m in compulsion.penalty_against(s.actors["c1"], "c2")) == -4
    pc, s, e, res = _antagonist("intimidate", 1, ranks=0)
    assert compulsion.penalty_against(s.actors["c1"], "c2") == [], _tells(res)
