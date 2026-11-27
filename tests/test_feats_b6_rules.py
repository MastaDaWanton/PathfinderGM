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
