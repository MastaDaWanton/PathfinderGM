"""The dispel check (feat loop b6-rules, rules/dispel.py).

Measured on integrate/feats-b5 3520f6a8: dispel magic's document was one narrative line
("No effect vocabulary can say 'dispel'"), so a cast of it spent a 3rd-level slot and ended
nothing; no effect on any creature recorded the caster level a dispel is rolled against;
the readied counterspell's dispel check added the full caster level with no +10 cap. These
tests cast the real spells through the engine and read the sheet.
"""
from __future__ import annotations

from rules import dispel
from tests.test_feats_b4_moves import _board, _pc, _run, _tells
from tests.test_readied_action import _caster


def _two_casters(faces=None, feats=(), level=7, prepared=("haste", "dispel-magic",
                                                           "magic-missile")):
    pc = _caster("pc", prepared=prepared, feats=feats)
    pc.level = level
    from rules import casting

    casting.define_slots(pc)
    for sid in prepared:
        casting.prepare(pc, sid, 1)
    s, e = _board(pc, ("thug", (8, 5)), faces=faces)
    foe = _caster("c1", prepared=("haste", "dispel-magic"), name="Orsk the Witch-Eye")
    s.people.pop("c1")
    s.add(foe, at=(8, 5))
    return s, e, pc, foe


def _haste_on(e, who="c1"):
    res = _run(e, {"op": "cast", "actor": who, "target": who, "visibility": "hidden",
                   "params": {"spell": "haste", "at": who}})
    return res


def test_a_cast_stamps_its_caster_level_on_every_effect_it_laid():
    """No effect carried a caster level: a dispel's DC (11 + the effect's caster level)
    had nothing to be computed from. Haste cast at caster level 7 leaves five terms, every
    one stamped 7, its caster and its school."""
    s, e, pc, foe = _two_casters()
    s.turn = 1
    _haste_on(e)
    laid = [x for x in foe.effects if x.origin == "spell:haste"]
    assert laid, [x.as_dict() for x in foe.effects]
    assert {dispel.cast_of(x)["cl"] for x in laid} == {7}
    assert {dispel.cast_of(x)["by"] for x in laid} == {"c1"}
    assert {dispel.cast_of(x)["school"] for x in laid} == {"transmutation"}


def test_dispel_magic_ends_the_haste_when_the_check_beats_eleven_plus_its_level():
    """The defect: dispel magic cast at a hasted foe spent its slot and ended nothing. Now
    1d20 + 7 against DC 18 (11 + haste's caster level 7): a 12 on the die is 19 and every
    term of haste goes; a 5 is 12 and they all stay."""
    for face, ends in ((12, True), (5, False)):
        s, e, pc, foe = _two_casters(faces={"Vell the Hedge-Mage's dispel": face})
        s.turn = 1
        _haste_on(e)
        ac = foe.ac()
        s.turn = 0
        res = _run(e, {"op": "cast", "actor": "pc", "target": "c1", "visibility": "hidden",
                       "params": {"spell": "dispel-magic", "at": "c1"}})
        said = _tells(res)
        left = [x for x in foe.effects if x.origin == "spell:haste"]
        assert (not left) is ends, (face, said)
        assert ("ends Haste" in said) is ends, said
        if ends:
            assert foe.ac() == ac - 1, "the dodge bonus went with the record"
        checks = [x for o in res.outcomes for x in o.effects if x.get("kind") == "dispel_check"]
        assert checks and checks[0]["dc"] == 18, checks


def test_the_check_adds_at_most_ten_caster_levels():
    """CRB: "1d20 + your caster level (maximum +10)". A 14th-level caster's check carries
    +10, greater dispel magic's +14 (its cap is +20)."""
    pc = _pc("wizard", level=14)
    assert sum(m.value for m in dispel.check_mods(pc, 14, "dispel-magic", {})) == 10
    assert sum(m.value for m in dispel.check_mods(pc, 14, "dispel-magic-greater", {})) == 14


def test_the_check_walks_down_from_the_highest_caster_level():
    """CRB: "compare that to the spell with highest caster level ... If not, compare the
    same result to the spell with the next highest". A CL 12 spell (DC 23) the roll of 19
    misses; the same 19 beats a CL 5 spell (DC 16), which is the one that ends."""
    from rules.activeeffect import ActiveEffect

    s, e, pc, foe = _two_casters(faces={"Vell the Hedge-Mage's dispel": 12})
    for name, cl in (("Strong", 12), ("Weak", 5)):
        foe.apply_effect(ActiveEffect(
            name=name, kind="buff", source=name, origin=f"spell:{name.lower()}",
            duration="rounds", rounds_left=50,
            modifiers=[{"kind": "combat_mod", "target": "ac", "amount": 1,
                        "bonus_type": "deflection" if cl > 6 else "dodge"}],
            payload={"cast": {"cl": cl, "by": "someone", "school": "abjuration"}}))
    got, said, rolls = dispel.targeted(e, pc, foe, 7, "dispel-magic", "abjuration",
                                       "spell:dispel-magic")
    assert [x.source for x in foe.effects if x.origin.startswith("spell:")] == ["Strong"]
    assert "ends Weak" in " ".join(said), said
